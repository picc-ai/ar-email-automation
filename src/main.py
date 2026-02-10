"""AR Email Automation -- Main Pipeline Orchestrator.

Orchestrates the full AR email generation pipeline:

    1. Load configuration (config.yaml or defaults)
    2. Load XLSX data (invoices + contacts) via data_loader
    3. Classify each invoice into a tier via tier_classifier
    4. Group invoices by dispensary (handle multi-invoice stores)
    5. Resolve contacts for each dispensary via contact_resolver
    6. Render email drafts via template_engine
    7. Add all drafts to email_queue
    8. Print summary: X emails generated, breakdown by tier
    9. Export drafts to output directory for review

Usage::

    # From the project root:
    python -m src.main

    # Or with a custom config:
    python -m src.main --config path/to/custom.yaml

    # Or with a custom XLSX:
    python -m src.main --xlsx path/to/data.xlsx

    # Dry run (skip export, just print summary):
    python -m src.main --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Internal imports -- always available
# ---------------------------------------------------------------------------
from .config import AREmailConfig, get_config, PROJECT_ROOT
from .models import (
    Contact,
    EmailDraft,
    EmailQueue,
    EmailStatus,
    Invoice,
    SkipReason,
    Tier,
    TierConfig,
)
from .data_loader import LoadResult, load_workbook
from .tier_classifier import (
    classify as classify_invoice,
    ClassificationResult,
    Tier as ClassifierTier,
    TIER_METADATA,
    get_overdue_timeframe_description,
)
from .contact_resolver import ContactResolver, resolve_contacts, format_resolution_report

# ---------------------------------------------------------------------------
# Optional imports -- modules being built in parallel by other agents.
# These are imported defensively so main.py is functional even before
# the parallel modules are committed.
# ---------------------------------------------------------------------------

# template_engine.py provides TemplateEngine with render_email() that returns
# a complete EmailDraft with subject, HTML body, CC list, and attachments.
try:
    from .template_engine import TemplateEngine
    _HAS_TEMPLATE_ENGINE = True
except ImportError:
    _HAS_TEMPLATE_ENGINE = False
    TemplateEngine = None  # type: ignore[assignment, misc]

# TODO: email_queue.py module is being built by another agent in parallel.
# The models.py already defines EmailQueue and EmailDraft dataclasses which
# we use directly.  The email_queue module may provide persistence (SQLite)
# and advanced queue management features.
try:
    from .email_queue import EmailQueueManager  # type: ignore[import-not-found]
    _HAS_EMAIL_QUEUE_MODULE = True
except ImportError:
    _HAS_EMAIL_QUEUE_MODULE = False
    EmailQueueManager = None  # type: ignore[assignment, misc]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Container for the full pipeline run output."""

    # Core outputs
    queue: EmailQueue = field(default_factory=EmailQueue)
    load_result: LoadResult | None = None

    # Statistics
    total_invoices_loaded: int = 0
    actionable_invoices: int = 0
    skipped_invoices: int = 0
    total_dispensaries: int = 0
    multi_invoice_dispensaries: int = 0
    emails_generated: int = 0
    contacts_resolved: int = 0
    contacts_unresolved: int = 0

    # Per-tier breakdown
    tier_counts: dict[str, int] = field(default_factory=dict)
    tier_amounts: dict[str, float] = field(default_factory=dict)

    # Skip reasons breakdown
    skip_reasons: dict[str, int] = field(default_factory=dict)

    # Output paths
    output_dir: Path | None = None
    json_export_path: Path | None = None
    csv_export_path: Path | None = None

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        """Pipeline execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


# ---------------------------------------------------------------------------
# Dispensary Grouping
# ---------------------------------------------------------------------------

@dataclass
class DispensaryGroup:
    """A group of invoices for a single dispensary.

    When a dispensary has multiple overdue invoices, they are combined
    into a single email.  The tier is determined by the HIGHEST
    days_past_due across all invoices in the group.
    """

    store_name: str
    invoices: list[Invoice] = field(default_factory=list)
    contact: Contact | None = None
    max_tier: Tier = Tier.T1
    max_days_past_due: int = 0
    total_amount: float = 0.0
    is_multi_invoice: bool = False
    classification: ClassificationResult | None = None

    def add_invoice(self, invoice: Invoice) -> None:
        """Add an invoice to this group, updating aggregates."""
        self.invoices.append(invoice)
        self.total_amount += invoice.amount
        if invoice.days_past_due > self.max_days_past_due:
            self.max_days_past_due = invoice.days_past_due
            self.max_tier = invoice.tier
        self.is_multi_invoice = len(self.invoices) > 1


def group_invoices_by_dispensary(invoices: list[Invoice]) -> dict[str, DispensaryGroup]:
    """Group actionable invoices by store name.

    Args:
        invoices: List of Invoice objects (should already be filtered
            to only actionable/sendable invoices).

    Returns:
        Dict mapping store_name -> DispensaryGroup.
    """
    groups: dict[str, DispensaryGroup] = {}

    for invoice in invoices:
        store = invoice.store_name
        if store not in groups:
            groups[store] = DispensaryGroup(store_name=store)
        groups[store].add_invoice(invoice)

    return groups


# ---------------------------------------------------------------------------
# CC List Builder
# ---------------------------------------------------------------------------

def build_cc_list(
    config: AREmailConfig,
    invoice: Invoice,
    contact: Contact | None,
    tier_name: str,
) -> list[str]:
    """Build the CC recipient list for an email.

    Always includes the base CC list from config.  Adds the sales rep
    email if available via rep lookup. Adds tier-specific extra CCs.

    Args:
        config: The AR email configuration.
        invoice: Representative invoice (for sales rep lookup).
        contact: Resolved contact (may have account manager info).
        tier_name: Tier identifier string (e.g. "T1", "T2").

    Returns:
        De-duplicated list of CC email addresses.
    """
    cc: list[str] = list(config.cc_rules.base_cc)

    # Add tier-specific extra CCs
    tier_extras = config.cc_rules.tier_extra_cc.get(tier_name, [])
    for email in tier_extras:
        if email and email not in cc:
            cc.append(email)

    # Remove any placeholder tokens like {rep_email}
    cc = [addr for addr in cc if not addr.startswith("{")]

    # De-duplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for addr in cc:
        addr_lower = addr.lower().strip()
        if addr_lower and addr_lower not in seen:
            seen.add(addr_lower)
            deduped.append(addr)

    return deduped


# ---------------------------------------------------------------------------
# Email Draft Builder
# ---------------------------------------------------------------------------

def build_email_draft(
    group: DispensaryGroup,
    config: AREmailConfig,
) -> EmailDraft:
    """Build an EmailDraft for a dispensary group.

    When template_engine is available, delegates to its render_email()
    which returns a complete EmailDraft with subject, HTML body, CC list,
    and attachments already populated.

    When template_engine is not yet available, builds a fallback draft
    with plaintext body, subject line, and CC list using local helpers.

    Args:
        group: The dispensary group with invoices and resolved contact.
        config: The AR email configuration.

    Returns:
        A fully populated EmailDraft ready for queue insertion.
    """
    contact = group.contact
    invoices = group.invoices

    # --- Try the full template engine first ---
    if _HAS_TEMPLATE_ENGINE and TemplateEngine is not None:
        try:
            engine = TemplateEngine(config=config)
            draft = engine.render_email(
                invoices=list(invoices),
                contact=contact,
                config=config,
            )
            logger.debug(
                "Template engine rendered email for %s (%d invoices, tier=%s)",
                group.store_name, len(invoices), draft.tier.value,
            )
            return draft
        except Exception as exc:
            logger.warning(
                "Template rendering failed for %s: %s. "
                "Falling back to plaintext draft.",
                group.store_name, exc,
            )
            # Fall through to the fallback builder below

    # --- Fallback: build draft manually without template engine ---
    tier_config_key = _resolve_tier_config_key(group.max_days_past_due, config)

    draft = EmailDraft(
        tier=group.max_tier,
        invoices=list(invoices),
        store_name=group.store_name,
        contact=contact,
    )

    # Set recipients
    if contact and contact.has_email:
        draft.to = list(contact.all_emails) if contact.all_emails else [contact.email]
    else:
        draft.to = []  # Will be flagged for manual review

    # Build CC list
    representative_invoice = invoices[0]
    draft.cc = build_cc_list(config, representative_invoice, contact, tier_config_key)

    # Build subject line
    draft.build_subject()

    # Resolve attachments
    _resolve_attachments(draft, config, tier_config_key)

    # Build plaintext fallback body
    draft.body_html = _build_fallback_body(group, config)

    return draft


def _resolve_tier_config_key(days_past_due: int, config: AREmailConfig) -> str:
    """Map days_past_due to the config tier key (T1, T2, T3, T4, T5).

    Iterates through config.tiers to find which tier range contains
    the given days_past_due value.

    Args:
        days_past_due: The maximum days past due for the group.
        config: The AR email configuration.

    Returns:
        Tier key string (e.g. "T1", "T3").  Falls back to "T2" if
        no tier matches.
    """
    for key, tier_cfg in config.tiers.items():
        if tier_cfg.min_days <= days_past_due <= tier_cfg.max_days:
            return key
    # Fallback
    return "T2"


def _resolve_attachments(
    draft: EmailDraft,
    config: AREmailConfig,
    tier_key: str,
) -> None:
    """Populate draft.attachments based on tier attachment rules.

    Args:
        draft: The email draft to populate.
        config: The AR email configuration.
        tier_key: The tier config key (e.g. "T1").
    """
    tier_rules = config.attachment_rules.tier_attachments.get(tier_key, {})

    # ACH form
    if tier_rules.get("ach_form") is True:
        ach_path = config.attachment_rules.ach_form_path
        resolved = str(PROJECT_ROOT / ach_path) if not Path(ach_path).is_absolute() else ach_path
        if Path(resolved).exists():
            draft.attachments.append(resolved)
        else:
            logger.warning("ACH form not found at %s", resolved)


def _build_template_variables(
    group: DispensaryGroup,
    config: AREmailConfig,
) -> dict:
    """Build the Jinja2 variable context for template rendering.

    Args:
        group: The dispensary group.
        config: The AR email configuration.

    Returns:
        Dict of template variables.
    """
    contact = group.contact
    invoices = group.invoices

    # Contact greeting
    if contact and contact.first_name:
        greeting = contact.first_name
    else:
        greeting = "Team"

    # Build per-invoice blocks
    invoice_blocks = []
    for inv in invoices:
        block = {
            "ORDER_NO": inv.invoice_number,
            "DUE_DATE": inv.due_date_formatted,
            "AMOUNT": inv.amount_formatted,
            "ACCOUNT_MANAGER": inv.account_manager or "your Nabis Account Manager",
            "AM_PHONE": inv.account_manager_phone or "",
        }
        invoice_blocks.append(block)

    # Overdue timeframe description (for T2/Overdue tier)
    overdue_timeframe = ""
    if group.max_days_past_due >= 1:
        overdue_timeframe = get_overdue_timeframe_description(group.max_days_past_due)

    variables = {
        "CONTACT_FIRST_NAME": greeting,
        "CONTACT_GREETING": greeting,
        "LOCATION": group.store_name,
        "TIER_LABEL": group.max_tier.value,
        "DAYS_DESCRIPTION": overdue_timeframe,
        "INVOICE_BLOCKS": invoice_blocks,
        "SIGNATURE_BLOCK": _build_signature_text(config),
        "IS_MULTI_INVOICE": group.is_multi_invoice,
        "TOTAL_AMOUNT": f"${group.total_amount:,.2f}",
    }

    # For single-invoice emails, also set top-level invoice fields
    if len(invoices) == 1:
        inv = invoices[0]
        variables["ORDER_NO"] = inv.invoice_number
        variables["DUE_DATE"] = inv.due_date_formatted
        variables["AMOUNT"] = inv.amount_formatted
        variables["ACCOUNT_MANAGER"] = inv.account_manager or "your Nabis Account Manager"
        variables["AM_PHONE"] = inv.account_manager_phone or ""

    return variables


def _build_signature_text(config: AREmailConfig) -> str:
    """Build a plaintext signature block from config."""
    sig = config.signature
    lines = [
        sig.sender_name,
        sig.company,
        sig.title,
        sig.address_line1,
        sig.address_line2,
        "",
        f'"{sig.tagline}"',
        "",
        f"IG: {sig.instagram}",
        f"Wholesale: {sig.website_wholesale}",
        f"Corporate: {sig.website_corporate}",
    ]
    return "\n".join(lines)


def _build_fallback_body(group: DispensaryGroup, config: AREmailConfig) -> str:
    """Build a plaintext fallback body when template engine is unavailable.

    This provides a human-readable draft that can be manually refined
    in the review UI.

    Args:
        group: The dispensary group.
        config: The AR email configuration.

    Returns:
        Plaintext email body string.
    """
    contact = group.contact
    greeting = contact.first_name if (contact and contact.first_name) else "Team"
    invoices = group.invoices

    lines = [
        f"Hello {greeting},",
        "",
    ]

    # Tier-specific opening
    tier = group.max_tier
    if tier == Tier.T0:
        lines.append(
            "I hope you're well. This is a courtesy reminder that "
            "your payment is due soon."
        )
    elif tier == Tier.T1:
        overdue_desc = get_overdue_timeframe_description(group.max_days_past_due)
        lines.append(
            f"I hope you're doing well. I wanted to reach out regarding "
            f"your account, as {overdue_desc}."
        )
    else:
        lines.append(
            f"I hope this message finds you well. I'm reaching out "
            f"regarding your outstanding balance that is "
            f"{group.max_days_past_due} days past due."
        )

    lines.append("")
    lines.append("According to our records, the following "
                 f"{'invoices are' if group.is_multi_invoice else 'invoice is'} "
                 "past due:")
    lines.append("")

    for i, inv in enumerate(invoices):
        lines.append(f"   - Invoice/Order: {inv.invoice_number}")
        lines.append(f"   - Due: {inv.due_date_formatted}")
        lines.append(f"   - Amount: {inv.amount_formatted}")
        am_name = inv.account_manager or "your Nabis Account Manager"
        am_phone = f" {inv.account_manager_phone}" if inv.account_manager_phone else ""
        lines.append(f"   - Nabis Account Manager: {am_name}{am_phone}")

        if i < len(invoices) - 1:
            lines.append("")
            lines.append("and")
            lines.append("")

    lines.append("")
    lines.append(
        "Attached is the Nabis ACH payment form (PDF) to facilitate "
        "your payment."
    )
    lines.append("")
    lines.append(
        "PICC and I are committed to providing you with the best "
        "possible service and are always here to help. If you have "
        "any questions or require assistance with your payment, "
        "please do not hesitate to contact us."
    )
    lines.append("")
    lines.append(
        "Thank you for your business. You're much appreciated. "
        "Have a great day!"
    )
    lines.append("")
    lines.append(_build_signature_text(config))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    *,
    config_path: str | Path | None = None,
    xlsx_path: str | Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> PipelineResult:
    """Execute the full AR email automation pipeline.

    Args:
        config_path: Path to config.yaml.  Uses default if None.
        xlsx_path: Path to the XLSX file.  Uses config default if None.
        dry_run: If True, skip file exports (just compute and print).
        verbose: If True, enable DEBUG-level logging.

    Returns:
        PipelineResult with all statistics and the generated EmailQueue.
    """
    result = PipelineResult(started_at=datetime.now())

    # ------------------------------------------------------------------
    # STEP 1: Load configuration
    # ------------------------------------------------------------------
    logger.info("=" * 65)
    logger.info("  AR Email Automation Pipeline")
    logger.info("=" * 65)

    config = get_config(config_path)
    logger.info("Configuration loaded from %s",
                config_path or "defaults + config.yaml")

    # Ensure output directories exist
    if not dry_run:
        config.output.ensure_dirs()

    # ------------------------------------------------------------------
    # STEP 2: Load XLSX data (invoices + contacts)
    # ------------------------------------------------------------------
    if xlsx_path is None:
        xlsx_path = config.data_files.resolve(config.data_files.ar_overdue_xlsx)

    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        logger.error("XLSX file not found: %s", xlsx_path)
        print(f"\nERROR: XLSX file not found: {xlsx_path}")
        print("Please provide a valid path with --xlsx or update config.yaml")
        result.completed_at = datetime.now()
        return result

    logger.info("Loading workbook: %s", xlsx_path)
    load_result = load_workbook(str(xlsx_path))
    result.load_result = load_result

    result.total_invoices_loaded = len(load_result.invoices)
    logger.info(
        "Loaded %d invoices, %d contacts",
        len(load_result.invoices), len(load_result.contacts),
    )

    # Print load summary
    load_result.print_summary()

    # ------------------------------------------------------------------
    # STEP 3: Filter to actionable invoices and classify tiers
    # ------------------------------------------------------------------
    actionable: list[Invoice] = []
    skipped: list[Invoice] = []

    for invoice in load_result.invoices:
        # The Invoice.__post_init__ already assigns tier and skip_reason
        if invoice.is_sendable:
            actionable.append(invoice)
        else:
            skipped.append(invoice)
            reason = invoice.skip_reason.value if invoice.skip_reason else "Unknown"
            result.skip_reasons[reason] = result.skip_reasons.get(reason, 0) + 1

    result.actionable_invoices = len(actionable)
    result.skipped_invoices = len(skipped)

    logger.info(
        "Actionable: %d, Skipped: %d", len(actionable), len(skipped),
    )

    if not actionable:
        logger.warning("No actionable invoices found. Pipeline complete.")
        print("\nNo actionable invoices to process.")
        result.completed_at = datetime.now()
        return result

    # Classify each actionable invoice with the tier_classifier for
    # enriched metadata (OCM warnings, urgency levels, etc.)
    for invoice in actionable:
        classification = classify_invoice(invoice.days_past_due)
        # The invoice.tier is already set by __post_init__, but we can
        # log the classifier's enriched metadata
        logger.debug(
            "Invoice %s: %s (%d days) -> %s [urgency=%s]",
            invoice.invoice_number,
            invoice.store_name,
            invoice.days_past_due,
            classification.tier.value,
            classification.metadata.urgency_level.value,
        )

    # ------------------------------------------------------------------
    # STEP 4: Group invoices by dispensary
    # ------------------------------------------------------------------
    groups = group_invoices_by_dispensary(actionable)
    result.total_dispensaries = len(groups)
    result.multi_invoice_dispensaries = sum(
        1 for g in groups.values() if g.is_multi_invoice
    )

    logger.info(
        "Grouped into %d dispensaries (%d multi-invoice)",
        result.total_dispensaries, result.multi_invoice_dispensaries,
    )

    # ------------------------------------------------------------------
    # STEP 5: Resolve contacts for each dispensary
    # ------------------------------------------------------------------
    resolved_count = 0
    unresolved_count = 0

    for store_name, group in groups.items():
        contact = load_result.get_contact(store_name)
        if contact is not None:
            group.contact = contact
            resolved_count += 1

            # Verify the contact has an email
            if not contact.has_email:
                logger.warning(
                    "Contact found for '%s' but has no email address",
                    store_name,
                )
        else:
            unresolved_count += 1
            logger.warning("No contact found for dispensary: %s", store_name)

    result.contacts_resolved = resolved_count
    result.contacts_unresolved = unresolved_count

    logger.info(
        "Contacts resolved: %d/%d (%.1f%%)",
        resolved_count,
        len(groups),
        (resolved_count / len(groups) * 100) if groups else 0,
    )

    # ------------------------------------------------------------------
    # STEP 6: Build email drafts (render via template_engine)
    # ------------------------------------------------------------------
    queue = EmailQueue()

    for store_name, group in sorted(groups.items()):
        # Classify the group for enriched metadata
        group.classification = classify_invoice(group.max_days_past_due)

        # Build the email draft
        draft = build_email_draft(group, config)

        # Track tier counts
        tier_label = draft.tier.value
        result.tier_counts[tier_label] = result.tier_counts.get(tier_label, 0) + 1
        result.tier_amounts[tier_label] = (
            result.tier_amounts.get(tier_label, 0.0) + group.total_amount
        )

        # ------------------------------------------------------------------
        # STEP 7: Add draft to queue
        # ------------------------------------------------------------------
        queue.add(draft)

    result.queue = queue
    result.emails_generated = len(queue)

    logger.info("Generated %d email drafts", len(queue))

    # ------------------------------------------------------------------
    # STEP 8: Print summary
    # ------------------------------------------------------------------
    _print_pipeline_summary(result, config)

    # ------------------------------------------------------------------
    # STEP 9: Export drafts to output directory
    # ------------------------------------------------------------------
    if not dry_run:
        output_dir = Path(config.output.output_dir)
        if not output_dir.is_absolute():
            output_dir = PROJECT_ROOT / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        result.output_dir = output_dir

        # Export JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"drafts_{timestamp}.json"
        result.json_export_path = queue.export_json(json_path)
        logger.info("JSON export: %s", json_path)

        # Export CSV summary
        csv_path = output_dir / f"drafts_{timestamp}.csv"
        result.csv_export_path = queue.export_csv(csv_path)
        logger.info("CSV export: %s", csv_path)

        print(f"\nExported to: {output_dir}")
        print(f"  JSON: {json_path.name}")
        print(f"  CSV:  {csv_path.name}")
    else:
        print("\n[DRY RUN] Skipping file export.")

    result.completed_at = datetime.now()
    logger.info(
        "Pipeline complete in %.1f seconds", result.duration_seconds,
    )

    return result


# ---------------------------------------------------------------------------
# Summary Printer
# ---------------------------------------------------------------------------

def _print_pipeline_summary(result: PipelineResult, config: AREmailConfig) -> None:
    """Print a human-readable summary of the pipeline run."""
    print()
    print("=" * 65)
    print("  AR Email Automation -- Pipeline Summary")
    print("=" * 65)
    print(f"  Invoices loaded     : {result.total_invoices_loaded}")
    print(f"  Actionable          : {result.actionable_invoices}")
    print(f"  Skipped             : {result.skipped_invoices}")
    print(f"  Dispensaries        : {result.total_dispensaries}")
    print(f"  Multi-invoice stores: {result.multi_invoice_dispensaries}")
    print("-" * 65)
    print(f"  Contacts resolved   : {result.contacts_resolved}/{result.total_dispensaries}")
    print(f"  Contacts unresolved : {result.contacts_unresolved}")
    print("-" * 65)
    print(f"  EMAILS GENERATED    : {result.emails_generated}")
    print("-" * 65)

    # Tier breakdown
    print("  Tier Breakdown:")
    for tier in Tier:
        count = result.tier_counts.get(tier.value, 0)
        amount = result.tier_amounts.get(tier.value, 0.0)
        if count > 0:
            print(f"    {tier.value:<22s}: {count:3d} emails  ${amount:>10,.2f}")

    # Skip reasons
    if result.skip_reasons:
        print("-" * 65)
        print("  Skip Reasons:")
        for reason, count in sorted(
            result.skip_reasons.items(), key=lambda x: -x[1]
        ):
            print(f"    {reason:<45s}: {count}")

    # Template engine status
    if not _HAS_TEMPLATE_ENGINE:
        print("-" * 65)
        print("  NOTE: template_engine.py not yet available.")
        print("  Email bodies contain plaintext fallback drafts.")

    if not _HAS_EMAIL_QUEUE_MODULE:
        print("  NOTE: email_queue.py module not yet available.")
        print("  Using in-memory EmailQueue from models.py.")

    print("=" * 65)

    # Queue summary from the models.EmailQueue
    print()
    print(result.queue.summary())


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point for the AR email automation pipeline.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(
        description="AR Email Automation - Generate collection email drafts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.main\n"
            "  python -m src.main --xlsx data/overdue.xlsx\n"
            "  python -m src.main --config custom_config.yaml --dry-run\n"
            "  python -m src.main --verbose\n"
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: project root config.yaml)",
    )
    parser.add_argument(
        "--xlsx",
        type=str,
        default=None,
        help="Path to the AR overdue XLSX file (overrides config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without exporting files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        result = run_pipeline(
            config_path=args.config,
            xlsx_path=args.xlsx,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if result.emails_generated == 0 and result.total_invoices_loaded > 0:
            print("\nAll invoices were skipped. Check skip reasons above.")
            return 0

        if result.emails_generated > 0:
            print(f"\nPipeline completed successfully: "
                  f"{result.emails_generated} emails generated "
                  f"in {result.duration_seconds:.1f}s")

        return 0

    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        print(f"\nERROR: {exc}")
        return 1
    except ValueError as exc:
        logger.error("Data error: %s", exc)
        print(f"\nERROR: {exc}")
        return 1
    except Exception as exc:
        logger.exception("Unexpected error in pipeline")
        print(f"\nUNEXPECTED ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
