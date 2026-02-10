"""AR Email Automation - Data Models and Queue Management.

Dataclasses for invoice records, contacts, email drafts, email queue,
and tier configuration. Designed around the NY Account Receivables
Overdue XLSX schema.

The EmailQueueManager provides persistent SQLite-backed queue operations
with audit logging, .eml export, and send history tracking.
"""

from .models import (
    AttachmentRule,
    Contact,
    EmailDraft,
    EmailQueue,
    EmailStatus,
    Invoice,
    InvoiceStatus,
    SkipReason,
    Tier,
    TierConfig,
)

from .email_queue import EmailQueueManager

__all__ = [
    "AttachmentRule",
    "Contact",
    "EmailDraft",
    "EmailQueue",
    "EmailQueueManager",
    "EmailStatus",
    "Invoice",
    "InvoiceStatus",
    "SkipReason",
    "Tier",
    "TierConfig",
]
