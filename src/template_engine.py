"""
AR Email Automation -- Template Engine

Renders Jinja2 HTML email templates with invoice/contact data and produces
complete EmailDraft objects ready for the review queue.

Responsibilities:
  1. Load HTML templates from templates/ using Jinja2
  2. Build the full variable context from Invoice(s), Contact, and TierConfig
  3. Render HTML body with all variables substituted
  4. Generate a plain-text version from the rendered HTML
  5. Build subject lines per the tier-specific formula
  6. Determine CC lists based on tier rules + sales rep mapping
  7. Determine attachment file paths based on tier rules
  8. Handle multi-invoice rendering (list of invoice numbers, per-invoice blocks)
  9. Format dates (Mon DD, YYYY) and currency ($X,XXX.XX) consistently
 10. Return a complete EmailDraft object (from models.py)

Usage:
    from template_engine import TemplateEngine
    from config import get_config

    engine = TemplateEngine()
    draft = engine.render_email(
        invoices=[invoice],
        contact=contact,
        config=get_config(),
    )
    print(draft.subject)
    print(draft.body_html[:200])
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateNotFound

from .config import (
    AREmailConfig,
    get_config,
    get_t2_time_phrase,
    tier_for_days,
    PROJECT_ROOT,
    TierConfig as CfgTierConfig,
)
from .models import (
    AttachmentRule,
    Contact,
    EmailDraft,
    EmailStatus,
    Invoice,
    Tier,
)
from .tier_classifier import (
    classify,
    get_overdue_timeframe_description,
    OCM_REPORTING_DAY,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default template directory relative to project root
_DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "templates"

# Date format: "Feb 05, 2026"
_DATE_FORMAT = "%b %d, %Y"

# OCM reporting deadline in days
_OCM_DEADLINE_DAYS = OCM_REPORTING_DAY  # 52

# Business days for deadline calculations
_T4_DEADLINE_BIZ_DAYS = 7
_T5_DEADLINE_BIZ_DAYS = 5


# ---------------------------------------------------------------------------
# Helper: Business Day Calculator
# ---------------------------------------------------------------------------

def _add_business_days(start: date, biz_days: int) -> date:
    """Add N business days (Mon-Fri) to a start date.

    Args:
        start: The starting date.
        biz_days: Number of business days to add.

    Returns:
        The date that is ``biz_days`` business days after ``start``.
    """
    current = start
    added = 0
    while added < biz_days:
        current += timedelta(days=1)
        # Monday=0 .. Friday=4 are business days
        if current.weekday() < 5:
            added += 1
    return current


# ---------------------------------------------------------------------------
# Helper: Format Utilities
# ---------------------------------------------------------------------------

def format_date(d: date | None) -> str:
    """Format a date as 'Mon DD, YYYY' (e.g. 'Feb 05, 2026').

    Returns empty string for None.
    """
    if d is None:
        return ""
    return d.strftime(_DATE_FORMAT)


def format_currency(amount: float | None) -> str:
    """Format a float as USD currency: '$1,510.00'.

    Always includes 2 decimal places and comma thousands separator.
    Returns '$0.00' for None.
    """
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"


# ---------------------------------------------------------------------------
# Helper: OCM Phrase Generators
# ---------------------------------------------------------------------------

def _get_ocm_status_phrase(days_past_due: int) -> str:
    """Generate the OCM status phrase for T5 (50+ days) emails.

    Returns a phrase fragment starting with 'is...' or 'has...' that
    completes the sentence 'Your account {phrase}'.
    """
    if days_past_due <= 51:
        return "is within days of being reported to OCM"
    elif days_past_due == 52:
        return "has reached the OCM reporting threshold today"
    else:
        return (
            "has exceeded the 52-day threshold and may have already "
            "been reported to OCM"
        )


def _get_days_until_ocm(days_past_due: int) -> int:
    """Calculate days remaining until the 52-day OCM reporting deadline.

    Returns 0 if already at or past the threshold.
    """
    return max(0, _OCM_DEADLINE_DAYS - days_past_due)


# ---------------------------------------------------------------------------
# Helper: Subject Line Builder
# ---------------------------------------------------------------------------

def build_subject_line(
    store_name: str,
    invoice_numbers: list[str],
    tier_label: str,
) -> str:
    """Build the full email subject line.

    Rules:
      - Always starts with 'PICC - '
      - 'Invoice' (singular) for 1 invoice, 'Invoices' (plural) for 2+
      - For 2 invoices: joined with ' & '
      - For 3+ invoices: comma-separated, last joined with ' & '
      - T4 appends ' - ACTION REQUIRED'
      - T5 appends ' - FINAL NOTICE'
      - No period at end

    Args:
        store_name: The retailer's display name (as in Nabis).
        invoice_numbers: List of invoice number strings.
        tier_label: The tier label for the subject suffix.

    Returns:
        The fully formatted subject line string.
    """
    if not invoice_numbers:
        return f"PICC - {store_name} - {tier_label}"

    if len(invoice_numbers) == 1:
        inv_part = f"Nabis Invoice {invoice_numbers[0]}"
    elif len(invoice_numbers) == 2:
        inv_part = f"Nabis Invoices {invoice_numbers[0]} & {invoice_numbers[1]}"
    else:
        # 3+: "901234, 901235 & 901236"
        joined = ", ".join(invoice_numbers[:-1]) + " & " + invoice_numbers[-1]
        inv_part = f"Nabis Invoices {joined}"

    # Append urgency suffixes for T4 and T5 if not already present
    subject_label = tier_label
    if "40+ Days Past Due" in tier_label and "ACTION REQUIRED" not in tier_label:
        subject_label = f"{tier_label} - ACTION REQUIRED"
    elif "50+ Days Past Due" in tier_label and "FINAL NOTICE" not in tier_label:
        subject_label = f"{tier_label} - FINAL NOTICE"

    return f"PICC - {store_name} - {inv_part} - {subject_label}"


# ---------------------------------------------------------------------------
# Helper: CC List Builder
# ---------------------------------------------------------------------------

def build_cc_list(
    config: AREmailConfig,
    tier_config: CfgTierConfig,
    invoice: Invoice,
    contact: Contact | None = None,
) -> list[str]:
    """Build the CC recipient list for an email.

    Always includes:
      - Base CC list (ny.ar@nabis.com, martinm@, mario@, laura@)
      - Assigned sales rep (if known)

    Tier-specific additions:
      - T3+: Nabis AM email if available
      - T4+: Store owner/AP contacts if known
      - T5:  All additional retailer contacts

    Args:
        config: The full AREmailConfig.
        tier_config: The specific TierConfig for this tier.
        invoice: The primary invoice (for sales rep lookup).
        contact: The resolved contact (for additional emails at escalation tiers).

    Returns:
        De-duplicated list of CC email addresses.
    """
    cc: list[str] = list(config.cc_rules.base_cc)

    # Add sales rep from the rep mapping
    rep_key = invoice.sales_rep
    if rep_key and rep_key in config.tiers:
        # Not a tier key -- check the rep_mapping on config if it exists
        pass

    # Look up the rep email. The cc_rules in models.TierConfig uses '{rep_email}'
    # as a placeholder. We resolve it here from config.
    # The rep short name is on invoice.sales_rep (e.g. "Bryce J", "Ben").
    # We look it up in the rep mapping attached to the tier's cc_rules.
    # For now, we check known rep names against the static map.
    _rep_map: dict[str, str] = {
        "Ben": "b.rosenthal@piccplatform.com",
        "Bryce J": "bryce@piccplatform.com",
        "Donovan": "donovan@piccplatform.com",
        "Eric": "eric@piccplatform.com",
        "M Martin": "martinm@piccplatform.com",
        "Mario": "mario@piccplatform.com",
        "Matt M": "matt@piccplatform.com",
    }

    rep_email = _rep_map.get(invoice.sales_rep, "")
    if rep_email:
        cc.append(rep_email)

    # Tier-specific escalation
    tier_name = tier_config.name  # "T1", "T2", ..., "T5"

    # T3+: Add Nabis AM's personal email if we have one
    # (The base list already includes ny.ar@nabis.com generically.)
    # We don't have a separate AM email field, so this is a no-op unless
    # the contact resolver provides one in the future.

    # T4+: Add store owner / AP contacts from the Contact
    if tier_name in ("T4", "T5") and contact:
        for extra_email in contact.all_emails:
            if extra_email and extra_email not in cc:
                cc.append(extra_email)

    # T5: Add any additional retailer stakeholders
    if tier_name == "T5" and contact:
        for extra_contact in contact.all_contacts:
            email = extra_contact.get("email", "")
            if email and email not in cc:
                cc.append(email)

    # Remove any placeholder tokens that weren't resolved
    cc = [addr for addr in cc if addr and "{" not in addr]

    # De-duplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for addr in cc:
        addr_lower = addr.strip().lower()
        if addr_lower not in seen:
            seen.add(addr_lower)
            deduped.append(addr.strip())

    return deduped


# ---------------------------------------------------------------------------
# Helper: Attachment List Builder
# ---------------------------------------------------------------------------

def build_attachment_list(
    config: AREmailConfig,
    tier_config: CfgTierConfig,
    invoices: list[Invoice],
) -> list[str]:
    """Determine which files to attach based on tier rules.

    All tiers:  Nabis ACH Payment Form.pdf
    T4+:        Invoice PDF copy (optional, flagged)
    T5:         Invoice PDF copy + BOL + Account Statement (optional, flagged)

    Args:
        config: The full AREmailConfig.
        tier_config: The TierConfig for this tier.
        invoices: The invoice(s) included in this email.

    Returns:
        List of file path strings for attachments.
    """
    attachments: list[str] = []

    # ACH form is always attached
    ach_path = config.attachment_rules.ach_form_path
    if ach_path:
        attachments.append(ach_path)

    # T4/T5: Include invoice PDF copies and BOLs if available
    tier_rules = config.attachment_rules.tier_attachments.get(tier_config.name, {})

    if tier_rules.get("invoice_pdf"):
        for inv in invoices:
            pdf_name = f"NY{inv.invoice_number}-invoice.pdf"
            attachments.append(f"data/invoices/{pdf_name}")

    if tier_rules.get("bol"):
        for inv in invoices:
            bol_name = f"NY{inv.invoice_number}-bill-of-lading.pdf"
            attachments.append(f"data/bols/{bol_name}")

    return attachments


# ---------------------------------------------------------------------------
# Helper: HTML to Plain Text
# ---------------------------------------------------------------------------

def html_to_plaintext(html_content: str) -> str:
    """Convert rendered HTML email body to a reasonable plain-text version.

    This is a simple conversion suitable for the multipart/alternative
    text/plain part.  It strips HTML tags, collapses whitespace, and
    preserves basic structure.

    Args:
        html_content: The rendered HTML string.

    Returns:
        A plain-text string.
    """
    text = html_content

    # Replace common block elements with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "  - ", text, flags=re.IGNORECASE)
    text = re.sub(r"<ul[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</ul>", "\n", text, flags=re.IGNORECASE)

    # Extract link text + URL from anchor tags
    text = re.sub(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r"\2 (\1)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Handle bold/strong -> *text*
    text = re.sub(
        r"<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>",
        r"*\1*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Handle italic -> _text_
    text = re.sub(
        r"<(?:i|em)[^>]*>(.*?)</(?:i|em)>",
        r"_\1_",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Collapse multiple blank lines into at most 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace from each line, but preserve blank lines
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        lines.append(stripped)
    text = "\n".join(lines)

    # Final trim
    text = text.strip()

    return text


# ---------------------------------------------------------------------------
# Invoice Block Builder
# ---------------------------------------------------------------------------

def _build_invoice_block(
    invoice: Invoice,
    tier_name: str,
) -> dict[str, str]:
    """Build the template variable dict for a single invoice detail block.

    Different tiers display slightly different fields:
      - T1/T2: Invoice, Due, Amount, Nabis AM (space separator)
      - T3:    Invoice, Due, Nabis AM (dash separator), Amount
      - T4:    Invoice, Due, Days Past Due, Nabis AM (dash separator), Amount
      - T5:    Invoice, Original Due Date, Days Past Due, Nabis AM (dash), Amount Due

    The templates handle the actual display order via HTML.  This function
    provides all possible fields and lets the template decide what to show.

    Args:
        invoice: The Invoice dataclass instance.
        tier_name: The config tier name (T1-T5).

    Returns:
        Dict with all invoice-block variables.
    """
    return {
        "INVOICE_NUMBER": str(invoice.invoice_number),
        "DUE_DATE": format_date(invoice.due_date),
        "AMOUNT": format_currency(invoice.amount),
        "NABIS_AM_NAME": invoice.account_manager or "your Nabis Account Manager",
        "NABIS_AM_PHONE": invoice.account_manager_phone or "",
        "DAYS_PAST_DUE": str(invoice.days_past_due),
        "INVOICE_NOTE": "",  # Populated externally if credit notes exist
    }


# ---------------------------------------------------------------------------
# Sanitizing Jinja2 Loader
# ---------------------------------------------------------------------------

class _SanitizingFileLoader(BaseLoader):
    """A Jinja2 loader that wraps FileSystemLoader and escapes pseudo-template
    syntax inside HTML comments before Jinja2 parses the source.

    The existing HTML templates contain documentation-style markers like
    ``{{#EACH INVOICE}}`` and ``{{#IF HAS_ADDITIONAL_INVOICES}}`` inside
    HTML ``<!-- ... -->`` comment blocks.  These are not valid Jinja2 and
    cause TemplateSyntaxError.

    This loader replaces ``{{`` / ``}}`` inside HTML comments with safe
    literal strings so Jinja2 ignores them.
    """

    def __init__(self, searchpath: str) -> None:
        self._inner = FileSystemLoader(searchpath)

    def get_source(self, environment, template):
        source, filename, uptodate = self._inner.get_source(environment, template)
        source = self._sanitize_html_comments(source)
        return source, filename, uptodate

    @staticmethod
    def _sanitize_html_comments(source: str) -> str:
        """Remove HTML comments that contain pseudo-template markers.

        The existing templates use {{#EACH}}, {{/EACH}}, {{#IF}}, {{/IF}}
        inside HTML comments as documentation.  These are not valid Jinja2
        and must be stripped before parsing.

        This removes entire HTML comment blocks that contain template-like
        syntax (any {{ or {% or {# inside a comment).  Regular HTML comments
        without template syntax are preserved.
        """

        def _should_remove(match):
            comment = match.group(0)
            # Remove the comment if it contains template-like braces
            if "{{" in comment or "{%" in comment or "{#" in comment:
                return ""
            return comment

        return re.sub(r"<!--.*?-->", _should_remove, source, flags=re.DOTALL)


# ===========================================================================
# Main Template Engine Class
# ===========================================================================

class TemplateEngine:
    """Jinja2-based email template renderer for AR collection emails.

    Loads HTML templates from the templates/ directory, populates them with
    invoice and contact data, and returns complete EmailDraft objects.

    The templates use ``{{ VARIABLE }}`` Jinja2 syntax.  The existing HTML
    templates in the project already use this format (e.g. ``{{STORE_NAME}}``).

    Attributes:
        env: The Jinja2 Environment configured with the template directory.
        template_dir: Path to the templates/ directory.
    """

    def __init__(
        self,
        template_dir: str | Path | None = None,
        config: AREmailConfig | None = None,
    ) -> None:
        """Initialize the template engine.

        Args:
            template_dir: Path to the directory containing HTML templates.
                Defaults to ``<project_root>/templates/``.
            config: AREmailConfig instance.  If not provided, loads defaults
                via ``get_config()``.
        """
        if template_dir is None:
            self.template_dir = _DEFAULT_TEMPLATE_DIR
        else:
            self.template_dir = Path(template_dir)

        self.config = config or get_config()

        # Set up Jinja2 with the sanitizing loader.
        # The custom loader escapes pseudo-template markers ({{#EACH}}, etc.)
        # inside HTML comments so Jinja2 does not try to parse them.
        self.env = Environment(
            loader=_SanitizingFileLoader(str(self.template_dir)),
            # Keep default {{ }} delimiters -- matches the existing templates
            autoescape=False,  # HTML templates have inline styling, no escaping
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # Register custom filters
        self.env.filters["format_date"] = format_date
        self.env.filters["format_currency"] = format_currency

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def render_email(
        self,
        invoices: list[Invoice],
        contact: Contact | None = None,
        config: AREmailConfig | None = None,
        send_date: date | None = None,
    ) -> EmailDraft:
        """Render a complete email draft for one or more invoices.

        This is the primary entry point.  It:
          1. Determines the tier from the worst (highest days_past_due) invoice
          2. Selects the appropriate HTML template
          3. Builds the full variable context
          4. Renders the HTML template with Jinja2
          5. Generates a plain-text version
          6. Builds the subject line
          7. Determines CC list and attachments
          8. Returns a complete EmailDraft object

        Args:
            invoices: One or more Invoice objects for the same store.
                For multi-invoice emails, all should share the same store_name.
            contact: The resolved Contact for the store.  If None, uses
                fallback values ("Team" for greeting, empty email for TO).
            config: Optional config override.  Uses self.config if not provided.
            send_date: The date the email will be sent.  Defaults to today.
                Used for calculating payment deadlines (T4/T5).

        Returns:
            A fully populated EmailDraft instance.

        Raises:
            ValueError: If invoices list is empty.
            TemplateNotFound: If the tier's template file is missing.
        """
        if not invoices:
            raise ValueError("At least one Invoice is required")

        cfg = config or self.config
        today = send_date or date.today()

        # --- Determine tier from the worst invoice ---
        primary_invoice = max(invoices, key=lambda inv: inv.days_past_due)
        tier_cfg = tier_for_days(primary_invoice.days_past_due, cfg)

        if tier_cfg is None:
            # Fallback: use Coming Due config
            tier_cfg = cfg.tiers.get("T1", list(cfg.tiers.values())[0])

        # --- Determine sender ---
        sender_name, sender_email, sender_title, sender_phone_line = (
            self._resolve_sender(cfg, tier_cfg)
        )

        # --- Build template context ---
        context = self._build_context(
            invoices=invoices,
            contact=contact,
            tier_cfg=tier_cfg,
            config=cfg,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_title=sender_title,
            sender_phone_line=sender_phone_line,
            send_date=today,
        )

        # --- Render HTML ---
        template_file = tier_cfg.template_file
        html_body = self._render_template(template_file, context)

        # --- Generate plain text ---
        text_body = html_to_plaintext(html_body)

        # --- Build subject line ---
        invoice_numbers = [str(inv.invoice_number) for inv in invoices]
        subject = build_subject_line(
            store_name=primary_invoice.store_name,
            invoice_numbers=invoice_numbers,
            tier_label=tier_cfg.label,
        )

        # --- Build CC list ---
        cc_list = build_cc_list(cfg, tier_cfg, primary_invoice, contact)

        # --- Build attachment list ---
        attachment_paths = build_attachment_list(cfg, tier_cfg, invoices)

        # --- Build TO list ---
        to_list: list[str] = []
        if contact and contact.email:
            to_list.append(contact.email)
        elif contact and contact.all_emails:
            to_list.append(contact.all_emails[0])

        # --- Assemble EmailDraft ---
        draft = EmailDraft(
            to=to_list,
            cc=cc_list,
            bcc=[],
            subject=subject,
            body_html=html_body,
            tier=primary_invoice.tier,
            invoices=list(invoices),
            store_name=primary_invoice.store_name,
            contact=contact,
            attachments=attachment_paths,
            status=EmailStatus.PENDING,
        )

        return draft

    def render_template_string(
        self,
        template_file: str,
        context: dict,
    ) -> str:
        """Render a named template with the given context.

        Lower-level helper useful for previewing templates or testing.

        Args:
            template_file: Filename of the template (e.g. 'coming_due.html').
            context: Dict of template variables.

        Returns:
            The rendered HTML string.
        """
        return self._render_template(template_file, context)

    def get_available_templates(self) -> list[str]:
        """List all HTML template files in the template directory.

        Returns:
            Sorted list of template filenames.
        """
        if not self.template_dir.is_dir():
            return []
        return sorted(
            f.name
            for f in self.template_dir.iterdir()
            if f.suffix == ".html" and f.is_file()
        )

    # -------------------------------------------------------------------
    # Internal: Template Rendering
    # -------------------------------------------------------------------

    def _render_template(self, template_file: str, context: dict) -> str:
        """Load and render a Jinja2 template.

        Args:
            template_file: The template filename (e.g. 'coming_due.html').
            context: Dict of all template variables.

        Returns:
            The rendered HTML string.

        Raises:
            TemplateNotFound: If the template file doesn't exist.
        """
        template = self.env.get_template(template_file)
        return template.render(**context)

    # -------------------------------------------------------------------
    # Internal: Sender Resolution
    # -------------------------------------------------------------------

    def _resolve_sender(
        self,
        config: AREmailConfig,
        tier_cfg: CfgTierConfig,
    ) -> tuple[str, str, str, str]:
        """Determine sender info based on tier.

        T1-T4: Default sender (Sales Admin)
        T5:    Escalation sender (Regional Account Manager) if configured

        Args:
            config: The full config.
            tier_cfg: The tier config.

        Returns:
            Tuple of (name, email, title, phone_line_html).
            phone_line_html is empty string for non-T5 senders.
        """
        if tier_cfg.sender_override:
            esc = config.escalation_sender
            phone_html = (
                f'<span style="font-family:Arial,Helvetica,sans-serif;">'
                f"{esc.phone}</span><br>"
                if esc.phone
                else ""
            )
            return (esc.name, esc.email, esc.title, phone_html)

        return (config.sender.name, config.sender.email, config.sender.title, "")

    # -------------------------------------------------------------------
    # Internal: Context Building
    # -------------------------------------------------------------------

    def _build_context(
        self,
        invoices: list[Invoice],
        contact: Contact | None,
        tier_cfg: CfgTierConfig,
        config: AREmailConfig,
        sender_name: str,
        sender_email: str,
        sender_title: str,
        sender_phone_line: str,
        send_date: date,
    ) -> dict:
        """Build the full Jinja2 template variable context.

        This assembles all variables needed by any tier's template into a
        single dict.  Templates only reference the variables they need;
        extra variables are safely ignored.

        Args:
            invoices: The invoice(s) for this email.
            contact: Resolved contact info.
            tier_cfg: The config tier.
            config: Full config.
            sender_name: Resolved sender name.
            sender_email: Resolved sender email.
            sender_title: Resolved sender title.
            sender_phone_line: HTML phone line (T5 only).
            send_date: The send date for deadline calculations.

        Returns:
            Dict of all template variables.
        """
        primary = max(invoices, key=lambda inv: inv.days_past_due)
        is_multi = len(invoices) > 1

        # --- Contact / greeting ---
        contact_first_name = "Team"
        if contact and contact.first_name:
            contact_first_name = contact.first_name
        elif contact and contact.contact_name:
            contact_first_name = contact.contact_name.split()[0]

        # --- Single invoice variables (for the primary/only invoice) ---
        ctx: dict = {
            # Greeting
            "CONTACT_FIRST_NAME": contact_first_name,

            # Store (subject line only in templates, but provide anyway)
            "STORE_NAME": primary.store_name,

            # Invoice details (primary invoice for single-invoice templates)
            "INVOICE_NUMBER": str(primary.invoice_number),
            "DUE_DATE": format_date(primary.due_date),
            "AMOUNT": format_currency(primary.amount),
            "NABIS_AM_NAME": primary.account_manager or "your Nabis Account Manager",
            "NABIS_AM_PHONE": primary.account_manager_phone or "",

            # Sender / signature
            "SENDER_NAME": sender_name,
            "SENDER_EMAIL": sender_email,
            "SENDER_TITLE": sender_title,
            "SENDER_PHONE_LINE": sender_phone_line,

            # Tier info
            "TIER_LABEL": tier_cfg.label,

            # Days past due (used in T4, T5)
            "DAYS_PAST_DUE": str(primary.days_past_due),

            # Multi-invoice flag
            "IS_MULTI_INVOICE": is_multi,
            "INVOICE_COUNT": len(invoices),

            # Invoice note (empty unless set externally)
            "INVOICE_NOTE": "",
        }

        # --- T2 (Overdue): Timeframe phrase ---
        if tier_cfg.name == "T2":
            ctx["OVERDUE_TIMEFRAME"] = get_overdue_timeframe_description(
                primary.days_past_due
            )
        else:
            # Provide a fallback so templates don't error if they reference it
            ctx["OVERDUE_TIMEFRAME"] = "past due"

        # --- T4 (40+ Days): OCM countdown + payment deadline ---
        if tier_cfg.name == "T4":
            days_until_ocm = _get_days_until_ocm(primary.days_past_due)
            ctx["DAYS_UNTIL_OCM_REPORT"] = str(days_until_ocm)

            # Payment deadline: earlier of (send + 7 biz days) or (due + 52 days)
            deadline_from_send = _add_business_days(send_date, _T4_DEADLINE_BIZ_DAYS)
            if primary.due_date:
                deadline_from_due = primary.due_date + timedelta(days=_OCM_DEADLINE_DAYS)
                payment_deadline = min(deadline_from_send, deadline_from_due)
            else:
                payment_deadline = deadline_from_send
            ctx["PAYMENT_DEADLINE"] = format_date(payment_deadline)
        else:
            ctx["DAYS_UNTIL_OCM_REPORT"] = ""
            ctx["PAYMENT_DEADLINE"] = ""

        # --- T5 (50+ Days): OCM status phrase + final deadline ---
        if tier_cfg.name == "T5":
            ctx["OCM_STATUS_PHRASE"] = _get_ocm_status_phrase(primary.days_past_due)
            final_deadline = _add_business_days(send_date, _T5_DEADLINE_BIZ_DAYS)
            ctx["FINAL_PAYMENT_DEADLINE"] = format_date(final_deadline)
        else:
            ctx["OCM_STATUS_PHRASE"] = ""
            ctx["FINAL_PAYMENT_DEADLINE"] = ""

        # --- Multi-invoice: build per-invoice blocks ---
        if is_multi:
            invoice_blocks = []
            for inv in sorted(invoices, key=lambda i: i.due_date or date.min):
                invoice_blocks.append(_build_invoice_block(inv, tier_cfg.name))
            ctx["INVOICE_BLOCKS"] = invoice_blocks

            # Also provide numbered invoice variables for the subject template
            for i, inv in enumerate(sorted(invoices, key=lambda i: i.due_date or date.min)):
                suffix = f"_{i + 1}" if i > 0 else ""
                ctx[f"INVOICE_NUMBER{suffix}"] = str(inv.invoice_number)
                ctx[f"DUE_DATE{suffix}"] = format_date(inv.due_date)
                ctx[f"AMOUNT{suffix}"] = format_currency(inv.amount)

            # Total amount across all invoices
            total = sum(inv.amount for inv in invoices)
            ctx["TOTAL_AMOUNT"] = format_currency(total)
        else:
            ctx["INVOICE_BLOCKS"] = [_build_invoice_block(primary, tier_cfg.name)]
            ctx["TOTAL_AMOUNT"] = format_currency(primary.amount)

        # --- Sales rep info ---
        ctx["SALES_REP_NAME"] = invoice.sales_rep if (invoice := primary) else ""
        ctx["SALES_REP_EMAIL"] = ""  # Resolved by CC builder, not in template

        return ctx

    # -------------------------------------------------------------------
    # Convenience: Render for Preview
    # -------------------------------------------------------------------

    def preview(
        self,
        invoices: list[Invoice],
        contact: Contact | None = None,
        config: AREmailConfig | None = None,
        send_date: date | None = None,
    ) -> dict:
        """Render an email and return a preview dict (useful for UIs).

        Same as ``render_email`` but returns a JSON-friendly dict instead
        of an EmailDraft, including the variables used for rendering.

        Args:
            invoices: Invoice(s) for the email.
            contact: Resolved contact.
            config: Optional config override.
            send_date: Send date for deadline calculations.

        Returns:
            Dict with keys: subject, html_body, text_body, to, cc,
            attachments, tier, variables.
        """
        draft = self.render_email(
            invoices=invoices,
            contact=contact,
            config=config,
            send_date=send_date,
        )

        cfg = config or self.config
        today = send_date or date.today()
        primary = max(invoices, key=lambda inv: inv.days_past_due)
        tier_cfg = tier_for_days(primary.days_past_due, cfg)
        if tier_cfg is None:
            tier_cfg = cfg.tiers.get("T1", list(cfg.tiers.values())[0])

        sender_name, sender_email, sender_title, sender_phone_line = (
            self._resolve_sender(cfg, tier_cfg)
        )

        context = self._build_context(
            invoices=invoices,
            contact=contact,
            tier_cfg=tier_cfg,
            config=cfg,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_title=sender_title,
            sender_phone_line=sender_phone_line,
            send_date=today,
        )

        return {
            "subject": draft.subject,
            "html_body": draft.body_html,
            "text_body": html_to_plaintext(draft.body_html),
            "to": draft.to,
            "cc": draft.cc,
            "attachments": draft.attachments,
            "tier": draft.tier.value,
            "tier_label": tier_cfg.label,
            "store_name": primary.store_name,
            "is_multi_invoice": len(invoices) > 1,
            "invoice_count": len(invoices),
            "total_amount": format_currency(sum(inv.amount for inv in invoices)),
            "variables": {
                k: v
                for k, v in context.items()
                if isinstance(v, (str, int, float, bool))
            },
        }


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def render_email(
    invoices: list[Invoice],
    contact: Contact | None = None,
    config: AREmailConfig | None = None,
    send_date: date | None = None,
) -> EmailDraft:
    """Module-level convenience: create a TemplateEngine and render one email.

    Args:
        invoices: Invoice(s) for the email.
        contact: Resolved contact.
        config: Optional config override.
        send_date: Send date for deadline calculations.

    Returns:
        A fully populated EmailDraft.
    """
    engine = TemplateEngine(config=config)
    return engine.render_email(
        invoices=invoices,
        contact=contact,
        config=config,
        send_date=send_date,
    )


# ---------------------------------------------------------------------------
# Self-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import date as _date

    print("=" * 70)
    print("Template Engine - Self Test")
    print("=" * 70)

    # Create test data
    test_invoice = Invoice(
        invoice_number="906858",
        store_name="Aroma Farms",
        amount=1510.00,
        due_date=_date(2026, 2, 5),
        days_past_due=-2,
        account_manager="Mildred Verdadero",
        account_manager_phone="(415) 839-8232",
        sales_rep="Bryce J",
    )

    test_contact = Contact(
        store_name="Aroma Farms",
        email="aromafarmsinc@gmail.com",
        contact_name="Emily Stratakos",
        role="AP",
    )

    engine = TemplateEngine()

    print(f"\nAvailable templates: {engine.get_available_templates()}")

    # Test single invoice - Coming Due
    print("\n--- T1: Coming Due (single invoice) ---")
    draft = engine.render_email([test_invoice], test_contact)
    print(f"Subject: {draft.subject}")
    print(f"To:      {draft.to}")
    print(f"CC:      {draft.cc}")
    print(f"Tier:    {draft.tier.value}")
    print(f"Attach:  {draft.attachments}")
    print(f"HTML:    {len(draft.body_html)} chars")
    print(f"Text preview:\n{html_to_plaintext(draft.body_html)[:300]}...")

    # Test multi-invoice - Overdue
    test_inv_1 = Invoice(
        invoice_number="904667",
        store_name="Seaweed RBNY",
        amount=309.50,
        due_date=_date(2026, 1, 15),
        days_past_due=19,
        account_manager="Abbie Chavez",
        account_manager_phone="(510) 340-4267",
        sales_rep="Ben",
    )
    test_inv_2 = Invoice(
        invoice_number="905055",
        store_name="Seaweed RBNY",
        amount=3011.50,
        due_date=_date(2026, 1, 18),
        days_past_due=16,
        account_manager="Abbie Chavez",
        account_manager_phone="(510) 340-4267",
        sales_rep="Ben",
    )

    test_contact_2 = Contact(
        store_name="Seaweed RBNY",
        email="adam@seaweedrbny.com",
        contact_name="Adam",
    )

    print("\n--- T2: Overdue (multi-invoice) ---")
    draft2 = engine.render_email([test_inv_1, test_inv_2], test_contact_2)
    print(f"Subject: {draft2.subject}")
    print(f"To:      {draft2.to}")
    print(f"CC:      {draft2.cc}")
    print(f"Tier:    {draft2.tier.value}")
    print(f"Multi:   {draft2.is_multi_invoice}")
    print(f"Total:   {draft2.total_amount_formatted}")

    # Test T5 - 50+ Days
    test_inv_t5 = Invoice(
        invoice_number="893271",
        store_name="The Travel Agency - SoHo",
        amount=1552.55,
        due_date=_date(2025, 10, 15),
        days_past_due=111,
        account_manager="Itzel Hernandez",
        account_manager_phone="(831) 261-4014",
        sales_rep="Bryce J",
    )

    test_contact_t5 = Contact(
        store_name="The Travel Agency - SoHo",
        email="ap@thetravelagency.co",
        contact_name="Penelope",
    )

    print("\n--- T5: 50+ Days (single invoice) ---")
    draft5 = engine.render_email([test_inv_t5], test_contact_t5)
    print(f"Subject: {draft5.subject}")
    print(f"To:      {draft5.to}")
    print(f"Tier:    {draft5.tier.value}")
    print(f"Attach:  {draft5.attachments}")

    # Test format helpers
    print("\n--- Format Helpers ---")
    print(f"  format_date(2026-02-05): {format_date(_date(2026, 2, 5))}")
    print(f"  format_date(None):       {format_date(None)}")
    print(f"  format_currency(1510.0): {format_currency(1510.0)}")
    print(f"  format_currency(3692):   {format_currency(3692)}")
    print(f"  format_currency(628.75): {format_currency(628.75)}")
    print(f"  format_currency(None):   {format_currency(None)}")

    # Test subject line builder
    print("\n--- Subject Line Builder ---")
    print(f"  Single: {build_subject_line('Aroma Farms', ['906858'], 'Coming Due')}")
    print(f"  Multi:  {build_subject_line('Seaweed RBNY', ['904667', '905055'], 'Overdue')}")
    print(f"  Three:  {build_subject_line('Dazed - NY', ['893281', '898505', '901234'], '50+ Days Past Due - FINAL NOTICE')}")

    # Test OCM phrases
    print("\n--- OCM Status Phrases ---")
    for d in [50, 51, 52, 53, 60, 111]:
        print(f"  {d} days: '{_get_ocm_status_phrase(d)}'")

    # Test business day calculator
    print("\n--- Business Day Calculator ---")
    test_start = _date(2026, 2, 9)  # Monday
    print(f"  {test_start} + 5 biz days = {_add_business_days(test_start, 5)}")
    print(f"  {test_start} + 7 biz days = {_add_business_days(test_start, 7)}")

    print("\n" + "=" * 70)
    print("Self-test complete.")
    print("=" * 70)
