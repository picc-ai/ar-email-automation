"""Data models for the AR Email Automation system.

All models are plain dataclasses with type hints.  No ORM, no Pydantic --
just stdlib so the module has zero dependencies beyond Python 3.11+.

Designed around the XLSX schema documented in:
  agent-outputs/04-xlsx-schema-analysis.md
  agent-outputs/04-xlsx-schema.json
  agent-outputs/05-xlsx-data-patterns.md
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Self


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Tier(Enum):
    """Email escalation tiers derived from days-past-due.

    Tier boundaries match the observed email examples in the XLSX analysis:
      T0  Coming Due     days <= 0  (not yet due, or due today)
      T1  Overdue        1-29 days
      T2  30+ Days       30-39 days
      T3  40+ Days       40-49 days
      T4  50+ Days       >= 50 days
    """

    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"
    T3 = "40+ Days Past Due"
    T4 = "50+ Days Past Due"

    @classmethod
    def from_days(cls, days_past_due: int | float) -> Tier:
        """Assign a tier based on days past due."""
        if days_past_due <= 0:
            return cls.T0
        if days_past_due <= 29:
            return cls.T1
        if days_past_due <= 39:
            return cls.T2
        if days_past_due <= 49:
            return cls.T3
        return cls.T4


class InvoiceStatus(Enum):
    """Status values from the Overdue sheet's Status column (O)."""

    NONE = ""
    EXPECTED_TO_PAY = "Expected to pay"
    PAYMENT_ENROUTE = "Payment Enroute"
    ISSUE = "Issue"


class EmailStatus(Enum):
    """Lifecycle states for an EmailDraft in the queue."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


class SkipReason(Enum):
    """Why an invoice was excluded from email generation."""

    ALREADY_PAID = "Paid column is True"
    PAYMENT_ENROUTE = "Status is Payment Enroute"
    EMAIL_ALREADY_SENT = "Email Sent is True for current cycle"
    NO_ACCOUNT_MANAGER = "Account Manager is blank or #N/A"
    NO_CONTACT_MATCH = "No matching record in Managers sheet"
    NO_POC_EMAIL = "Managers record exists but POC Email is empty"


class AttachmentRule(Enum):
    """Determines which files to attach per tier."""

    NONE = "none"
    ACH_FORM = "ach_form"
    ACH_FORM_AND_BOL = "ach_form_and_bol"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

@dataclass
class Invoice:
    """A single overdue invoice row from the Overdue / Data sheet.

    Fields map to the Overdue 2-3 sheet columns documented in
    04-xlsx-schema-analysis.md section 2.1.

    Note: There is NO license_number column in the XLSX.  The
    ``license_number`` field is included for future extensibility
    (e.g., OCM lookup) but will typically be empty.
    """

    # --- identifiers ---
    invoice_number: str                     # Order No (col A) -- stored as str for display
    store_name: str                         # Location (col B)
    license_number: str = ""                # Not in XLSX -- reserved for future OCM lookup

    # --- financials ---
    amount: float = 0.0                     # Total Due (col K)

    # --- dates & aging ---
    due_date: date | None = None            # Due Date (col I)
    days_past_due: int = 0                  # Days Over (col J)

    # --- classification ---
    status: InvoiceStatus = InvoiceStatus.NONE  # Status (col O)
    tier: Tier = Tier.T1                    # Derived from days_past_due

    # --- tracking flags from the spreadsheet ---
    paid: bool = False                      # Paid (col M)
    email_sent: bool = False                # Email Sent (col E)
    called: bool = False                    # Called (col G)
    made_contact: bool = False              # Made Contact (col H)

    # --- related personnel ---
    account_manager: str = ""               # Account Manager (col C)
    account_manager_phone: str = ""         # Acocunt Manager Phone Number (col D)
    sales_rep: str = ""                     # Rep (col L)

    # --- notes ---
    notes: str = ""                         # Notes (col P)
    follow_up_date: date | None = None      # F/U Date (col N)

    # --- skip tracking ---
    skip_reason: SkipReason | None = None   # Set if this invoice should be skipped

    def __post_init__(self) -> None:
        """Auto-assign tier from days_past_due and detect skip reasons."""
        self.tier = Tier.from_days(self.days_past_due)
        if self.skip_reason is None:
            self.skip_reason = self._detect_skip_reason()

    def _detect_skip_reason(self) -> SkipReason | None:
        """Return the first applicable skip reason, or None if sendable."""
        if self.paid:
            return SkipReason.ALREADY_PAID
        if self.status is InvoiceStatus.PAYMENT_ENROUTE:
            return SkipReason.PAYMENT_ENROUTE
        if self.email_sent:
            return SkipReason.EMAIL_ALREADY_SENT
        if not self.account_manager or self.account_manager == "#N/A":
            return SkipReason.NO_ACCOUNT_MANAGER
        return None

    @property
    def is_sendable(self) -> bool:
        """True when this invoice has no skip reason."""
        return self.skip_reason is None

    @property
    def amount_formatted(self) -> str:
        """Dollar-formatted amount, e.g. '$2,700.56'."""
        return f"${self.amount:,.2f}"

    @property
    def due_date_formatted(self) -> str:
        """Human-readable due date, e.g. 'Feb 05, 2026'."""
        if self.due_date is None:
            return ""
        return self.due_date.strftime("%b %d, %Y")

    @property
    def tier_label(self) -> str:
        """The tier's display label for subject lines."""
        return self.tier.value


@dataclass
class Contact:
    """A retailer contact record from the Managers sheet.

    Fields map to the Managers sheet columns documented in
    04-xlsx-schema-analysis.md section 2.10.

    The POC fields in the XLSX are multi-line (newline-delimited).
    This dataclass stores the *parsed* individual values -- the raw
    multi-line strings should be split before constructing Contact
    instances.
    """

    # --- identifiers ---
    store_name: str                         # Retailer Name (DBA) (col A)
    license_number: str = ""                # Not in XLSX -- reserved for future use

    # --- primary contact ---
    email: str = ""                         # Primary POC Email (col E, first line)
    phone: str = ""                         # Primary POC Phone (col F, first line)
    contact_name: str = ""                  # Parsed from POC Name & Title (col D)
    role: str = ""                          # Parsed title from POC Name & Title

    # --- all contacts (multi-line fields split into lists) ---
    all_emails: list[str] = field(default_factory=list)
    all_phones: list[str] = field(default_factory=list)
    all_contacts: list[dict[str, str]] = field(default_factory=list)
    # Each dict: {"name": "...", "title": "...", "email": "...", "phone": "..."}

    # --- account manager (also on Managers sheet) ---
    account_manager: str = ""               # Account Manager (col B)
    account_manager_phone: str = ""         # Account Manager Phone# (col C)

    @property
    def retailer_name(self) -> str:
        """Alias for store_name, used by contact_resolver module."""
        return self.store_name

    @property
    def first_name(self) -> str:
        """Extract first name for email greeting.

        Handles formats like:
          'Jack Eisakharian'          -> 'Jack'
          'Janti Eisakharian - Owner' -> 'Janti'
          ''                          -> ''
        """
        if not self.contact_name:
            return ""
        return self.contact_name.split()[0]

    @property
    def has_email(self) -> bool:
        """True when at least one email address is available."""
        return bool(self.email) or bool(self.all_emails)

    @classmethod
    def parse_poc_name_title(cls, raw: str) -> tuple[str, str]:
        """Split 'FirstName LastName - Title' into (name, title).

        >>> Contact.parse_poc_name_title("Janti Eisakharian - Owner")
        ('Janti Eisakharian', 'Owner')
        >>> Contact.parse_poc_name_title("Jack Eisakharian")
        ('Jack Eisakharian', '')
        """
        if not raw:
            return ("", "")
        if " - " in raw:
            name, title = raw.split(" - ", maxsplit=1)
            return (name.strip(), title.strip())
        return (raw.strip(), "")

    @classmethod
    def parse_multi_line_emails(cls, raw: str) -> list[str]:
        """Split a newline-delimited email field into individual addresses.

        Filters out empty lines and strips whitespace.

        >>> Contact.parse_multi_line_emails("a@b.com\\nc@d.com\\n")
        ['a@b.com', 'c@d.com']
        """
        if not raw:
            return []
        return [addr.strip() for addr in raw.splitlines() if addr.strip()]

    @classmethod
    def parse_multi_line_phones(cls, raw: str) -> list[str]:
        """Split a newline-delimited phone field.

        Raw format: 'Jack - (917) 682-7576\\nJanti - (917) 682-7576'
        Returns the full strings (name + number) for each line.

        >>> Contact.parse_multi_line_phones("Jack - (917) 682-7576\\nJanti - (917) 682-7576")
        ['Jack - (917) 682-7576', 'Janti - (917) 682-7576']
        """
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]


@dataclass
class EmailDraft:
    """A fully composed email ready for review and sending.

    Represents one outbound AR collection email.  May cover a single
    invoice or multiple invoices for the same dispensary (batched).
    """

    # --- recipients ---
    to: list[str] = field(default_factory=list)         # POC email(s)
    cc: list[str] = field(default_factory=list)         # Always includes ny.ar@nabis.com + team
    bcc: list[str] = field(default_factory=list)        # Optional

    # --- content ---
    subject: str = ""
    body_html: str = ""

    # --- metadata ---
    tier: Tier = Tier.T1
    invoices: list[Invoice] = field(default_factory=list)
    store_name: str = ""
    contact: Contact | None = None

    # --- attachments ---
    attachments: list[str] = field(default_factory=list)    # File paths

    # --- workflow ---
    status: EmailStatus = EmailStatus.PENDING
    rejection_reason: str = ""
    sent_at: datetime | None = None
    error_message: str = ""

    @property
    def invoice_numbers(self) -> list[str]:
        """All invoice/order numbers covered by this email."""
        return [inv.invoice_number for inv in self.invoices]

    @property
    def total_amount(self) -> float:
        """Sum of all invoice amounts in this email."""
        return sum(inv.amount for inv in self.invoices)

    @property
    def total_amount_formatted(self) -> str:
        """Dollar-formatted total, e.g. '$5,131.00'."""
        return f"${self.total_amount:,.2f}"

    @property
    def is_multi_invoice(self) -> bool:
        """True when this email covers more than one invoice."""
        return len(self.invoices) > 1

    @property
    def subject_invoice_part(self) -> str:
        """Build the invoice number portion of the subject line.

        Single:  'Invoice 906858'
        Multi:   'Invoices 904667 & 905055'
        """
        nums = self.invoice_numbers
        if len(nums) == 0:
            return ""
        if len(nums) == 1:
            return f"Invoice {nums[0]}"
        return f"Invoices {' & '.join(nums)}"

    def build_subject(self) -> str:
        """Build the full subject line per the observed pattern.

        Format: 'PICC - {Location} - Nabis {Invoice(s)} - {Tier Label}'
        """
        self.subject = (
            f"PICC - {self.store_name} - "
            f"Nabis {self.subject_invoice_part} - "
            f"{self.tier.value}"
        )
        return self.subject

    def approve(self) -> None:
        """Mark this draft as approved for sending."""
        if self.status is not EmailStatus.PENDING:
            raise ValueError(
                f"Can only approve PENDING drafts, current status: {self.status.value}"
            )
        self.status = EmailStatus.APPROVED

    def reject(self, reason: str = "") -> None:
        """Mark this draft as rejected (will not be sent)."""
        if self.status is not EmailStatus.PENDING:
            raise ValueError(
                f"Can only reject PENDING drafts, current status: {self.status.value}"
            )
        self.status = EmailStatus.REJECTED
        self.rejection_reason = reason

    def mark_sent(self) -> None:
        """Record that the email was successfully sent."""
        self.status = EmailStatus.SENT
        self.sent_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Record a send failure."""
        self.status = EmailStatus.FAILED
        self.error_message = error

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON export / review UI."""
        return {
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "subject": self.subject,
            "body_html": self.body_html,
            "tier": self.tier.value,
            "store_name": self.store_name,
            "invoice_numbers": self.invoice_numbers,
            "total_amount": self.total_amount_formatted,
            "attachments": self.attachments,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class EmailQueue:
    """Ordered collection of EmailDrafts with batch operations.

    The queue is the central data structure for the review-then-send
    workflow.  Drafts start as PENDING, get reviewed (approved/rejected),
    and then approved drafts are sent.
    """

    drafts: list[EmailDraft] = field(default_factory=list)

    # --- queries ---

    @property
    def pending(self) -> list[EmailDraft]:
        """Drafts awaiting review."""
        return [d for d in self.drafts if d.status is EmailStatus.PENDING]

    @property
    def approved(self) -> list[EmailDraft]:
        """Drafts approved and ready to send."""
        return [d for d in self.drafts if d.status is EmailStatus.APPROVED]

    @property
    def rejected(self) -> list[EmailDraft]:
        """Drafts that were rejected."""
        return [d for d in self.drafts if d.status is EmailStatus.REJECTED]

    @property
    def sent(self) -> list[EmailDraft]:
        """Drafts that were successfully sent."""
        return [d for d in self.drafts if d.status is EmailStatus.SENT]

    @property
    def failed(self) -> list[EmailDraft]:
        """Drafts that failed to send."""
        return [d for d in self.drafts if d.status is EmailStatus.FAILED]

    def __len__(self) -> int:
        return len(self.drafts)

    def __iter__(self):
        return iter(self.drafts)

    def __getitem__(self, index: int) -> EmailDraft:
        return self.drafts[index]

    # --- mutations ---

    def add(self, draft: EmailDraft) -> None:
        """Append a draft to the queue."""
        self.drafts.append(draft)

    def approve_all(self) -> int:
        """Approve every pending draft.  Returns count approved."""
        count = 0
        for d in self.pending:
            d.approve()
            count += 1
        return count

    def reject_all(self, reason: str = "Batch rejection") -> int:
        """Reject every pending draft.  Returns count rejected."""
        count = 0
        for d in self.pending:
            d.reject(reason)
            count += 1
        return count

    def approve_by_tier(self, tier: Tier) -> int:
        """Approve all pending drafts matching a specific tier."""
        count = 0
        for d in self.pending:
            if d.tier is tier:
                d.approve()
                count += 1
        return count

    def approve_by_index(self, indices: list[int]) -> int:
        """Approve specific drafts by their queue index."""
        count = 0
        for i in indices:
            if 0 <= i < len(self.drafts) and self.drafts[i].status is EmailStatus.PENDING:
                self.drafts[i].approve()
                count += 1
        return count

    def reject_by_index(self, indices: list[int], reason: str = "") -> int:
        """Reject specific drafts by their queue index."""
        count = 0
        for i in indices:
            if 0 <= i < len(self.drafts) and self.drafts[i].status is EmailStatus.PENDING:
                self.drafts[i].reject(reason)
                count += 1
        return count

    # --- export ---

    def export_json(self, path: str | Path) -> Path:
        """Write the full queue to a JSON file for review.

        Returns the Path written to.
        """
        path = Path(path)
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total": len(self.drafts),
                "pending": len(self.pending),
                "approved": len(self.approved),
                "rejected": len(self.rejected),
                "sent": len(self.sent),
                "failed": len(self.failed),
            },
            "drafts": [d.to_dict() for d in self.drafts],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def export_csv(self, path: str | Path) -> Path:
        """Write a summary CSV for quick spreadsheet review.

        One row per draft with key fields.  Returns the Path written to.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "index",
            "store_name",
            "tier",
            "invoice_numbers",
            "total_amount",
            "to",
            "status",
            "rejection_reason",
        ]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for i, d in enumerate(self.drafts):
                writer.writerow({
                    "index": i,
                    "store_name": d.store_name,
                    "tier": d.tier.value,
                    "invoice_numbers": "; ".join(d.invoice_numbers),
                    "total_amount": d.total_amount_formatted,
                    "to": "; ".join(d.to),
                    "status": d.status.value,
                    "rejection_reason": d.rejection_reason,
                })
        return path

    def summary(self) -> str:
        """Return a human-readable summary string."""
        tier_counts: dict[str, int] = {}
        for d in self.drafts:
            label = d.tier.value
            tier_counts[label] = tier_counts.get(label, 0) + 1

        lines = [
            f"Email Queue: {len(self.drafts)} drafts",
            f"  Pending:  {len(self.pending)}",
            f"  Approved: {len(self.approved)}",
            f"  Rejected: {len(self.rejected)}",
            f"  Sent:     {len(self.sent)}",
            f"  Failed:   {len(self.failed)}",
            "",
            "By tier:",
        ]
        for tier_label, count in sorted(tier_counts.items()):
            lines.append(f"  {tier_label}: {count}")

        return "\n".join(lines)


@dataclass
class TierConfig:
    """Configuration for a single email tier.

    Defines the day-range boundaries, which template to use, CC rules,
    and attachment rules.  A list of TierConfig instances constitutes
    the full escalation ladder.
    """

    tier_name: Tier
    min_days: int                            # Inclusive lower bound
    max_days: int | None                     # Inclusive upper bound (None = unbounded)
    template_name: str                       # e.g. 'coming_due', 'overdue', 'past_due_30'
    cc_rules: list[str] = field(default_factory=list)
    attachment_rules: AttachmentRule = AttachmentRule.ACH_FORM
    include_ocm_warning: bool = False

    def matches(self, days_past_due: int | float) -> bool:
        """Return True if days_past_due falls within this tier's range."""
        if days_past_due < self.min_days:
            return False
        if self.max_days is not None and days_past_due > self.max_days:
            return False
        return True

    @classmethod
    def default_tiers(cls) -> list[Self]:
        """Return the standard 5-tier escalation ladder.

        Based on the tier definitions in 05-xlsx-data-patterns.md section 4.

        CC rules use placeholder rep tokens.  The email builder should
        resolve '{rep_email}' to the actual sales rep email address.
        """
        always_cc = [
            "ny.ar@nabis.com",
            "mario@piccplatform.com",
            "martinm@piccplatform.com",
            "laura@piccplatform.com",
            "{rep_email}",
        ]
        return [
            cls(
                tier_name=Tier.T0,
                min_days=-999,
                max_days=0,
                template_name="coming_due",
                cc_rules=list(always_cc),
                attachment_rules=AttachmentRule.ACH_FORM,
                include_ocm_warning=False,
            ),
            cls(
                tier_name=Tier.T1,
                min_days=1,
                max_days=29,
                template_name="overdue",
                cc_rules=list(always_cc),
                attachment_rules=AttachmentRule.ACH_FORM,
                include_ocm_warning=False,
            ),
            cls(
                tier_name=Tier.T2,
                min_days=30,
                max_days=39,
                template_name="past_due_30",
                cc_rules=list(always_cc),
                attachment_rules=AttachmentRule.ACH_FORM,
                include_ocm_warning=True,
            ),
            cls(
                tier_name=Tier.T3,
                min_days=40,
                max_days=49,
                template_name="past_due_40",
                cc_rules=list(always_cc),
                attachment_rules=AttachmentRule.ACH_FORM,
                include_ocm_warning=True,
            ),
            cls(
                tier_name=Tier.T4,
                min_days=50,
                max_days=None,
                template_name="past_due_50",
                cc_rules=list(always_cc),
                attachment_rules=AttachmentRule.ACH_FORM,
                include_ocm_warning=True,
            ),
        ]

    @classmethod
    def find_tier(cls, days_past_due: int | float, tiers: list[TierConfig] | None = None) -> TierConfig:
        """Find the TierConfig matching the given days past due.

        Uses the default tiers if none are provided.

        Raises ValueError if no tier matches (should not happen with
        default config since T0 goes to -999 and T4 is unbounded).
        """
        if tiers is None:
            tiers = cls.default_tiers()
        for tier_cfg in tiers:
            if tier_cfg.matches(days_past_due):
                return tier_cfg
        raise ValueError(f"No tier matches {days_past_due} days past due")
