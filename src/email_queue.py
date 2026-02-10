"""
AR Email Automation -- Email Queue Management Module

Persistent, SQLite-backed email queue with JSON file export for resume
capability.  Provides the full lifecycle for email drafts:

    PENDING -> APPROVED -> SENT
                       |-> REJECTED
                       |-> FAILED

Features:
    - SQLite storage for durable queue state and audit trail
    - JSON file persistence for human-readable backup / resume
    - .eml file export for manual sending in Outlook/Gmail
    - Batch operations: approve_all, reject_all, export_all
    - Filtering by tier, status, store name
    - Summary statistics: count by tier, count by status, total amount
    - Send history tracking (which stores were emailed, when, which tier)

Database schema:
    email_queue   - Main draft queue (mirrors EmailDraft fields)
    audit_log     - Every action logged for compliance
    emails_sent   - Historical record of sent emails (store, license, tier, date)
    batch_runs    - Tracks each pipeline execution

Usage:
    from email_queue import EmailQueueManager

    mgr = EmailQueueManager()                       # uses default db path
    mgr = EmailQueueManager("path/to/queue.db")     # custom path

    # Add drafts
    mgr.add(draft)

    # Review
    mgr.approve(queue_id)
    mgr.reject(queue_id, reason="Already paid by phone")
    mgr.edit(queue_id, subject="...", body_html="...")

    # Batch
    mgr.approve_all()
    mgr.approve_unflagged()

    # Export
    mgr.export_eml(queue_id, output_dir)
    mgr.export_all_approved_eml(output_dir)

    # Stats
    stats = mgr.get_stats()
    mgr.get_summary()

    # Send tracking
    mgr.record_send(queue_id)
    history = mgr.get_send_history(store_name="Aroma Farms")

Reference:
    agent-outputs/12-architecture-design.md  (Section 5.5, 9, 13)
    agent-outputs/11-system-requirements.md  (FR6, FR7, FR8, FR9)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, fields
from datetime import date, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

from .config import PROJECT_ROOT
from .models import (
    Contact,
    EmailDraft,
    EmailQueue,
    EmailStatus,
    Invoice,
    InvoiceStatus,
    SkipReason,
    Tier,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = PROJECT_ROOT / "ar_email_queue.db"
DEFAULT_JSON_PATH = PROJECT_ROOT / "output" / "queue_state.json"
DEFAULT_EML_DIR = PROJECT_ROOT / "output" / "eml"

# SQLite journal mode for better concurrency with Streamlit
_PRAGMA_SETTINGS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA busy_timeout=5000;",
]


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Main email queue table
CREATE TABLE IF NOT EXISTS email_queue (
    queue_id            TEXT PRIMARY KEY,
    batch_id            TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',

    -- Addressing
    from_name           TEXT NOT NULL DEFAULT '',
    from_email          TEXT NOT NULL DEFAULT '',
    to_emails           TEXT NOT NULL DEFAULT '[]',       -- JSON array
    cc_emails           TEXT NOT NULL DEFAULT '[]',       -- JSON array
    bcc_emails          TEXT NOT NULL DEFAULT '[]',       -- JSON array

    -- Content
    subject             TEXT NOT NULL DEFAULT '',
    body_html           TEXT NOT NULL DEFAULT '',

    -- Metadata
    tier                TEXT NOT NULL DEFAULT 'Overdue',
    tier_label          TEXT NOT NULL DEFAULT '',
    store_name          TEXT NOT NULL DEFAULT '',
    invoices_json       TEXT NOT NULL DEFAULT '[]',       -- JSON array of invoice dicts
    total_amount        REAL NOT NULL DEFAULT 0.0,
    max_days_over       INTEGER NOT NULL DEFAULT 0,
    is_multi_invoice    INTEGER NOT NULL DEFAULT 0,

    -- Template tracking
    template_name       TEXT NOT NULL DEFAULT '',
    variables_json      TEXT NOT NULL DEFAULT '{}',       -- JSON dict

    -- Attachments
    attachments_json    TEXT NOT NULL DEFAULT '[]',       -- JSON array of file paths

    -- Flags
    flags_json          TEXT NOT NULL DEFAULT '[]',       -- JSON array of flag codes
    flag_reasons_json   TEXT NOT NULL DEFAULT '[]',       -- JSON array of reasons

    -- Contact snapshot
    contact_name        TEXT NOT NULL DEFAULT '',
    contact_email       TEXT NOT NULL DEFAULT '',

    -- Audit timestamps
    created_at          TEXT NOT NULL DEFAULT '',
    reviewed_by         TEXT,
    reviewed_at         TEXT,
    sent_at             TEXT,
    rejection_reason    TEXT NOT NULL DEFAULT '',
    error_message       TEXT NOT NULL DEFAULT '',

    -- Edit history
    edit_history_json   TEXT NOT NULL DEFAULT '[]',       -- JSON array of edit records
    retry_count         INTEGER NOT NULL DEFAULT 0
);

-- Audit log: every action on every draft
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id    TEXT NOT NULL,
    batch_id    TEXT,
    action      TEXT NOT NULL,
    actor       TEXT NOT NULL DEFAULT 'system',
    details     TEXT NOT NULL DEFAULT '{}',
    timestamp   TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (queue_id) REFERENCES email_queue(queue_id)
);

-- Send history: permanent record of which stores were emailed
CREATE TABLE IF NOT EXISTS emails_sent (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id        TEXT NOT NULL,
    store_name      TEXT NOT NULL,
    license         TEXT NOT NULL DEFAULT '',
    tier            TEXT NOT NULL,
    tier_label      TEXT NOT NULL DEFAULT '',
    sent_date       TEXT NOT NULL,
    invoice_numbers TEXT NOT NULL DEFAULT '',             -- comma-separated
    total_amount    REAL NOT NULL DEFAULT 0.0,
    to_email        TEXT NOT NULL DEFAULT '',
    cc_emails       TEXT NOT NULL DEFAULT '',
    batch_id        TEXT,
    FOREIGN KEY (queue_id) REFERENCES email_queue(queue_id)
);

-- Batch run tracking
CREATE TABLE IF NOT EXISTS batch_runs (
    batch_id        TEXT PRIMARY KEY,
    source_file     TEXT NOT NULL DEFAULT '',
    sheet_name      TEXT NOT NULL DEFAULT '',
    total_invoices  INTEGER NOT NULL DEFAULT 0,
    skipped         INTEGER NOT NULL DEFAULT 0,
    queued          INTEGER NOT NULL DEFAULT 0,
    flagged         INTEGER NOT NULL DEFAULT 0,
    total_ar_amount REAL NOT NULL DEFAULT 0.0,
    created_at      TEXT NOT NULL DEFAULT '',
    completed_at    TEXT
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_queue_status ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_batch ON email_queue(batch_id);
CREATE INDEX IF NOT EXISTS idx_queue_store ON email_queue(store_name);
CREATE INDEX IF NOT EXISTS idx_queue_tier ON email_queue(tier);
CREATE INDEX IF NOT EXISTS idx_audit_queue ON audit_log(queue_id);
CREATE INDEX IF NOT EXISTS idx_audit_batch ON audit_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_sent_store ON emails_sent(store_name);
CREATE INDEX IF NOT EXISTS idx_sent_date ON emails_sent(sent_date);
CREATE INDEX IF NOT EXISTS idx_sent_tier ON emails_sent(tier);
CREATE INDEX IF NOT EXISTS idx_sent_batch ON emails_sent(batch_id);
"""


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()


def _invoice_to_dict(inv: Invoice) -> dict[str, Any]:
    """Serialize an Invoice dataclass to a JSON-safe dict."""
    return {
        "invoice_number": inv.invoice_number,
        "store_name": inv.store_name,
        "license_number": inv.license_number,
        "amount": inv.amount,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "days_past_due": inv.days_past_due,
        "status": inv.status.value if inv.status else "",
        "tier": inv.tier.value if inv.tier else "",
        "paid": inv.paid,
        "email_sent": inv.email_sent,
        "called": inv.called,
        "made_contact": inv.made_contact,
        "account_manager": inv.account_manager,
        "account_manager_phone": inv.account_manager_phone,
        "sales_rep": inv.sales_rep,
        "notes": inv.notes,
        "follow_up_date": inv.follow_up_date.isoformat() if inv.follow_up_date else None,
        "skip_reason": inv.skip_reason.value if inv.skip_reason else None,
    }


def _invoice_from_dict(d: dict[str, Any]) -> Invoice:
    """Deserialize a dict back into an Invoice dataclass."""
    # Parse dates
    due_date = None
    if d.get("due_date"):
        try:
            due_date = date.fromisoformat(d["due_date"])
        except (ValueError, TypeError):
            pass

    follow_up_date = None
    if d.get("follow_up_date"):
        try:
            follow_up_date = date.fromisoformat(d["follow_up_date"])
        except (ValueError, TypeError):
            pass

    # Parse enums
    status = InvoiceStatus.NONE
    status_val = d.get("status", "")
    if status_val:
        for s in InvoiceStatus:
            if s.value == status_val:
                status = s
                break

    skip_reason = None
    skip_val = d.get("skip_reason")
    if skip_val:
        for sr in SkipReason:
            if sr.value == skip_val:
                skip_reason = sr
                break

    return Invoice(
        invoice_number=str(d.get("invoice_number", "")),
        store_name=str(d.get("store_name", "")),
        license_number=str(d.get("license_number", "")),
        amount=float(d.get("amount", 0.0)),
        due_date=due_date,
        days_past_due=int(d.get("days_past_due", 0)),
        status=status,
        paid=bool(d.get("paid", False)),
        email_sent=bool(d.get("email_sent", False)),
        called=bool(d.get("called", False)),
        made_contact=bool(d.get("made_contact", False)),
        account_manager=str(d.get("account_manager", "")),
        account_manager_phone=str(d.get("account_manager_phone", "")),
        sales_rep=str(d.get("sales_rep", "")),
        notes=str(d.get("notes", "")),
        follow_up_date=follow_up_date,
        skip_reason=skip_reason,
    )


def _draft_to_row(draft: EmailDraft, batch_id: str = "", queue_id: str = "") -> dict[str, Any]:
    """Convert an EmailDraft dataclass to a dict matching the email_queue table columns."""
    qid = queue_id or str(uuid.uuid4())

    # Determine max_days_over from invoices
    max_days = 0
    if draft.invoices:
        max_days = max(inv.days_past_due for inv in draft.invoices)

    # Contact info snapshot
    contact_name = ""
    contact_email = ""
    if draft.contact:
        contact_name = draft.contact.contact_name
        contact_email = draft.contact.email

    return {
        "queue_id": qid,
        "batch_id": batch_id,
        "status": draft.status.value,
        "from_name": "",  # Populated from config at send time
        "from_email": "",
        "to_emails": json.dumps(draft.to),
        "cc_emails": json.dumps(draft.cc),
        "bcc_emails": json.dumps(draft.bcc),
        "subject": draft.subject,
        "body_html": draft.body_html,
        "tier": draft.tier.value,
        "tier_label": draft.tier.value,  # Tier.value is already the label string
        "store_name": draft.store_name,
        "invoices_json": json.dumps([_invoice_to_dict(inv) for inv in draft.invoices]),
        "total_amount": draft.total_amount,
        "max_days_over": max_days,
        "is_multi_invoice": 1 if draft.is_multi_invoice else 0,
        "template_name": "",
        "variables_json": "{}",
        "attachments_json": json.dumps(draft.attachments),
        "flags_json": "[]",
        "flag_reasons_json": "[]",
        "contact_name": contact_name,
        "contact_email": contact_email,
        "created_at": _now_iso(),
        "reviewed_by": None,
        "reviewed_at": None,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
        "rejection_reason": draft.rejection_reason,
        "error_message": draft.error_message,
        "edit_history_json": "[]",
        "retry_count": 0,
    }


def _row_to_draft(row: dict[str, Any]) -> EmailDraft:
    """Convert a SQLite row dict back into an EmailDraft dataclass."""
    # Parse tier enum
    tier = Tier.T1  # default
    tier_val = row.get("tier", "")
    for t in Tier:
        if t.value == tier_val:
            tier = t
            break

    # Parse status enum
    status = EmailStatus.PENDING
    status_val = row.get("status", "")
    for s in EmailStatus:
        if s.value == status_val:
            status = s
            break

    # Parse invoices
    invoices = []
    inv_json = row.get("invoices_json", "[]")
    try:
        inv_dicts = json.loads(inv_json) if inv_json else []
        invoices = [_invoice_from_dict(d) for d in inv_dicts]
    except (json.JSONDecodeError, TypeError):
        pass

    # Parse sent_at
    sent_at = None
    if row.get("sent_at"):
        try:
            sent_at = datetime.fromisoformat(row["sent_at"])
        except (ValueError, TypeError):
            pass

    # Parse list fields
    def _parse_json_list(val: Any) -> list:
        if not val:
            return []
        try:
            result = json.loads(val) if isinstance(val, str) else val
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    # Build contact if data exists
    contact = None
    if row.get("contact_name") or row.get("contact_email"):
        contact = Contact(
            store_name=row.get("store_name", ""),
            contact_name=row.get("contact_name", ""),
            email=row.get("contact_email", ""),
        )

    return EmailDraft(
        to=_parse_json_list(row.get("to_emails")),
        cc=_parse_json_list(row.get("cc_emails")),
        bcc=_parse_json_list(row.get("bcc_emails")),
        subject=row.get("subject", ""),
        body_html=row.get("body_html", ""),
        tier=tier,
        invoices=invoices,
        store_name=row.get("store_name", ""),
        contact=contact,
        attachments=_parse_json_list(row.get("attachments_json")),
        status=status,
        rejection_reason=row.get("rejection_reason", ""),
        sent_at=sent_at,
        error_message=row.get("error_message", ""),
    )


# ---------------------------------------------------------------------------
# EmailQueueManager -- the main public API
# ---------------------------------------------------------------------------

class EmailQueueManager:
    """Persistent email queue backed by SQLite.

    Wraps the in-memory EmailQueue/EmailDraft models from models.py with
    durable storage, audit logging, batch operations, filtering, stats,
    .eml export, and send history tracking.

    Thread safety: each method opens/closes its own cursor.  The WAL
    journal mode allows concurrent reads from Streamlit while a write
    is in progress.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        json_path: str | Path = DEFAULT_JSON_PATH,
        eml_dir: str | Path = DEFAULT_EML_DIR,
    ):
        self.db_path = Path(db_path)
        self.json_path = Path(json_path)
        self.eml_dir = Path(eml_dir)

        # Ensure parent directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.eml_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    # ------------------------------------------------------------------
    # Database connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Open a new SQLite connection with row_factory and pragmas."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        for pragma in _PRAGMA_SETTINGS:
            conn.execute(pragma)
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def add(self, draft: EmailDraft, batch_id: str = "", flags: list[str] | None = None,
            flag_reasons: list[str] | None = None) -> str:
        """Add a single EmailDraft to the persistent queue.

        Args:
            draft: The EmailDraft to enqueue.
            batch_id: Optional batch identifier grouping this run.
            flags: Optional list of flag codes (e.g. ["HIGH_VALUE", "MULTI_INVOICE"]).
            flag_reasons: Optional list of human-readable flag explanations.

        Returns:
            The generated queue_id (UUID string).
        """
        queue_id = str(uuid.uuid4())
        row = _draft_to_row(draft, batch_id=batch_id, queue_id=queue_id)

        if flags:
            row["flags_json"] = json.dumps(flags)
        if flag_reasons:
            row["flag_reasons_json"] = json.dumps(flag_reasons)

        columns = list(row.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)

        conn = self._get_conn()
        try:
            conn.execute(
                f"INSERT INTO email_queue ({col_str}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
            self._log_action(conn, queue_id, batch_id, "created", details={
                "store_name": draft.store_name,
                "tier": draft.tier.value,
                "total_amount": draft.total_amount,
                "invoice_count": len(draft.invoices),
            })
            conn.commit()
        finally:
            conn.close()

        return queue_id

    def add_batch(self, drafts: list[EmailDraft], batch_id: str = "",
                  source_file: str = "", sheet_name: str = "") -> list[str]:
        """Add multiple EmailDrafts in one transaction.

        Also records a batch_runs entry for tracking.

        Args:
            drafts: List of EmailDraft objects to enqueue.
            batch_id: Optional batch ID; auto-generated if empty.
            source_file: Name of the XLSX file that produced this batch.
            sheet_name: Name of the sheet within the XLSX.

        Returns:
            List of queue_id strings, one per draft.
        """
        if not batch_id:
            batch_id = str(uuid.uuid4())

        queue_ids = []
        conn = self._get_conn()
        try:
            total_ar = 0.0
            flagged_count = 0

            for draft in drafts:
                qid = str(uuid.uuid4())
                row = _draft_to_row(draft, batch_id=batch_id, queue_id=qid)

                columns = list(row.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_str = ", ".join(columns)
                conn.execute(
                    f"INSERT INTO email_queue ({col_str}) VALUES ({placeholders})",
                    [row[c] for c in columns],
                )

                self._log_action(conn, qid, batch_id, "created", details={
                    "store_name": draft.store_name,
                    "tier": draft.tier.value,
                })

                queue_ids.append(qid)
                total_ar += draft.total_amount

            # Record batch run
            conn.execute(
                """INSERT INTO batch_runs
                   (batch_id, source_file, sheet_name, total_invoices, skipped,
                    queued, flagged, total_ar_amount, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    batch_id, source_file, sheet_name,
                    sum(len(d.invoices) for d in drafts),
                    0,  # skipped count (caller can update)
                    len(drafts),
                    flagged_count,
                    total_ar,
                    _now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return queue_ids

    def get_by_id(self, queue_id: str) -> EmailDraft | None:
        """Retrieve a single draft by queue_id.

        Returns None if not found.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM email_queue WHERE queue_id = ?",
                (queue_id,),
            ).fetchone()
            if row is None:
                return None
            return _row_to_draft(dict(row))
        finally:
            conn.close()

    def get_all(self) -> list[tuple[str, EmailDraft]]:
        """Return all drafts as (queue_id, EmailDraft) tuples, ordered by created_at."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM email_queue ORDER BY created_at ASC"
            ).fetchall()
            return [(dict(r)["queue_id"], _row_to_draft(dict(r))) for r in rows]
        finally:
            conn.close()

    def get_raw_row(self, queue_id: str) -> dict[str, Any] | None:
        """Retrieve the raw SQLite row as a dict (includes all metadata fields)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM email_queue WHERE queue_id = ?", (queue_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Status Transitions
    # ------------------------------------------------------------------

    def approve(self, queue_id: str, reviewed_by: str = "Laura") -> bool:
        """Mark a draft as approved.

        Only transitions from 'pending' status.
        Returns True if the transition succeeded.
        """
        conn = self._get_conn()
        try:
            now = _now_iso()
            result = conn.execute(
                """UPDATE email_queue
                   SET status = ?, reviewed_by = ?, reviewed_at = ?
                   WHERE queue_id = ? AND status = ?""",
                (EmailStatus.APPROVED.value, reviewed_by, now, queue_id, EmailStatus.PENDING.value),
            )
            if result.rowcount == 0:
                return False
            self._log_action(conn, queue_id, "", "approved", actor=reviewed_by)
            conn.commit()
            return True
        finally:
            conn.close()

    def reject(self, queue_id: str, reason: str = "", reviewed_by: str = "Laura") -> bool:
        """Mark a draft as rejected.

        Only transitions from 'pending' status.
        Returns True if the transition succeeded.
        """
        conn = self._get_conn()
        try:
            now = _now_iso()
            result = conn.execute(
                """UPDATE email_queue
                   SET status = ?, rejection_reason = ?, reviewed_by = ?, reviewed_at = ?
                   WHERE queue_id = ? AND status = ?""",
                (
                    EmailStatus.REJECTED.value, reason, reviewed_by, now,
                    queue_id, EmailStatus.PENDING.value,
                ),
            )
            if result.rowcount == 0:
                return False
            self._log_action(conn, queue_id, "", "rejected", actor=reviewed_by,
                             details={"reason": reason})
            conn.commit()
            return True
        finally:
            conn.close()

    def edit(
        self,
        queue_id: str,
        subject: str | None = None,
        body_html: str | None = None,
        to_emails: list[str] | None = None,
        cc_emails: list[str] | None = None,
        edited_by: str = "Laura",
    ) -> bool:
        """Edit an email draft's content.

        Stores the previous values in the edit_history_json array.
        The draft remains in 'pending' status after editing.
        Returns True if the edit was applied.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM email_queue WHERE queue_id = ?", (queue_id,)
            ).fetchone()
            if row is None:
                return False

            row_dict = dict(row)

            # Only allow editing pending drafts
            if row_dict["status"] != EmailStatus.PENDING.value:
                return False

            # Build edit record with previous values
            edit_record = {
                "edited_by": edited_by,
                "edited_at": _now_iso(),
                "previous": {},
            }

            updates: dict[str, Any] = {}

            if subject is not None and subject != row_dict["subject"]:
                edit_record["previous"]["subject"] = row_dict["subject"]
                updates["subject"] = subject

            if body_html is not None and body_html != row_dict["body_html"]:
                edit_record["previous"]["body_html"] = row_dict["body_html"][:200] + "..."
                updates["body_html"] = body_html

            if to_emails is not None:
                old_to = row_dict["to_emails"]
                new_to = json.dumps(to_emails)
                if new_to != old_to:
                    edit_record["previous"]["to_emails"] = old_to
                    updates["to_emails"] = new_to

            if cc_emails is not None:
                old_cc = row_dict["cc_emails"]
                new_cc = json.dumps(cc_emails)
                if new_cc != old_cc:
                    edit_record["previous"]["cc_emails"] = old_cc
                    updates["cc_emails"] = new_cc

            if not updates:
                return False  # Nothing changed

            # Append to edit history
            try:
                history = json.loads(row_dict.get("edit_history_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                history = []
            history.append(edit_record)
            updates["edit_history_json"] = json.dumps(history)

            # Build UPDATE statement
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [queue_id]
            conn.execute(
                f"UPDATE email_queue SET {set_clause} WHERE queue_id = ?",
                values,
            )
            self._log_action(conn, queue_id, "", "edited", actor=edited_by,
                             details={"fields_changed": list(updates.keys())})
            conn.commit()
            return True
        finally:
            conn.close()

    def mark_sent(self, queue_id: str) -> bool:
        """Mark a draft as sent and record in emails_sent history.

        Only transitions from 'approved' status.
        Returns True if the transition succeeded.
        """
        conn = self._get_conn()
        try:
            now = _now_iso()
            result = conn.execute(
                """UPDATE email_queue
                   SET status = ?, sent_at = ?
                   WHERE queue_id = ? AND status = ?""",
                (EmailStatus.SENT.value, now, queue_id, EmailStatus.APPROVED.value),
            )
            if result.rowcount == 0:
                return False

            # Record in send history
            row = conn.execute(
                "SELECT * FROM email_queue WHERE queue_id = ?", (queue_id,)
            ).fetchone()
            if row:
                row_dict = dict(row)
                inv_nums = []
                try:
                    invs = json.loads(row_dict.get("invoices_json", "[]"))
                    inv_nums = [str(inv.get("invoice_number", "")) for inv in invs]
                except (json.JSONDecodeError, TypeError):
                    pass

                to_list = []
                try:
                    to_list = json.loads(row_dict.get("to_emails", "[]"))
                except (json.JSONDecodeError, TypeError):
                    pass

                conn.execute(
                    """INSERT INTO emails_sent
                       (queue_id, store_name, license, tier, tier_label,
                        sent_date, invoice_numbers, total_amount, to_email,
                        cc_emails, batch_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        queue_id,
                        row_dict.get("store_name", ""),
                        "",  # license -- not in current data
                        row_dict.get("tier", ""),
                        row_dict.get("tier_label", ""),
                        now,
                        ", ".join(inv_nums),
                        row_dict.get("total_amount", 0.0),
                        ", ".join(to_list),
                        row_dict.get("cc_emails", "[]"),
                        row_dict.get("batch_id", ""),
                    ),
                )

            self._log_action(conn, queue_id, "", "sent")
            conn.commit()
            return True
        finally:
            conn.close()

    def mark_failed(self, queue_id: str, error: str) -> bool:
        """Mark a draft as failed to send.

        Increments retry_count. Only transitions from 'approved' status.
        Returns True if the transition succeeded.
        """
        conn = self._get_conn()
        try:
            result = conn.execute(
                """UPDATE email_queue
                   SET status = ?, error_message = ?, retry_count = retry_count + 1
                   WHERE queue_id = ? AND status = ?""",
                (EmailStatus.FAILED.value, error, queue_id, EmailStatus.APPROVED.value),
            )
            if result.rowcount == 0:
                return False
            self._log_action(conn, queue_id, "", "failed", details={"error": error})
            conn.commit()
            return True
        finally:
            conn.close()

    def reset_to_pending(self, queue_id: str) -> bool:
        """Reset a failed or rejected draft back to pending for re-review.

        Useful for retry after fixing issues.
        Returns True if the reset succeeded.
        """
        conn = self._get_conn()
        try:
            result = conn.execute(
                """UPDATE email_queue
                   SET status = ?, error_message = '', rejection_reason = ''
                   WHERE queue_id = ? AND status IN (?, ?)""",
                (
                    EmailStatus.PENDING.value, queue_id,
                    EmailStatus.FAILED.value, EmailStatus.REJECTED.value,
                ),
            )
            if result.rowcount == 0:
                return False
            self._log_action(conn, queue_id, "", "reset_to_pending")
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    def approve_all(self, reviewed_by: str = "Laura") -> int:
        """Approve ALL pending drafts. Returns count approved."""
        conn = self._get_conn()
        try:
            now = _now_iso()
            # Get IDs first for audit logging
            rows = conn.execute(
                "SELECT queue_id FROM email_queue WHERE status = ?",
                (EmailStatus.PENDING.value,),
            ).fetchall()

            if not rows:
                return 0

            ids = [dict(r)["queue_id"] for r in rows]
            placeholders = ", ".join(["?"] * len(ids))
            conn.execute(
                f"""UPDATE email_queue
                    SET status = ?, reviewed_by = ?, reviewed_at = ?
                    WHERE queue_id IN ({placeholders})""",
                [EmailStatus.APPROVED.value, reviewed_by, now] + ids,
            )

            for qid in ids:
                self._log_action(conn, qid, "", "approved", actor=reviewed_by,
                                 details={"batch_action": "approve_all"})
            conn.commit()
            return len(ids)
        finally:
            conn.close()

    def approve_unflagged(self, reviewed_by: str = "Laura") -> int:
        """Approve all pending drafts that have NO flags.

        Flagged items (flags_json != '[]') remain pending for manual review.
        Returns count approved.
        """
        conn = self._get_conn()
        try:
            now = _now_iso()
            rows = conn.execute(
                """SELECT queue_id FROM email_queue
                   WHERE status = ? AND (flags_json = '[]' OR flags_json = '' OR flags_json IS NULL)""",
                (EmailStatus.PENDING.value,),
            ).fetchall()

            if not rows:
                return 0

            ids = [dict(r)["queue_id"] for r in rows]
            placeholders = ", ".join(["?"] * len(ids))
            conn.execute(
                f"""UPDATE email_queue
                    SET status = ?, reviewed_by = ?, reviewed_at = ?
                    WHERE queue_id IN ({placeholders})""",
                [EmailStatus.APPROVED.value, reviewed_by, now] + ids,
            )

            for qid in ids:
                self._log_action(conn, qid, "", "approved", actor=reviewed_by,
                                 details={"batch_action": "approve_unflagged"})
            conn.commit()
            return len(ids)
        finally:
            conn.close()

    def reject_all(self, reason: str = "Batch rejection", reviewed_by: str = "Laura") -> int:
        """Reject ALL pending drafts. Returns count rejected."""
        conn = self._get_conn()
        try:
            now = _now_iso()
            rows = conn.execute(
                "SELECT queue_id FROM email_queue WHERE status = ?",
                (EmailStatus.PENDING.value,),
            ).fetchall()

            if not rows:
                return 0

            ids = [dict(r)["queue_id"] for r in rows]
            placeholders = ", ".join(["?"] * len(ids))
            conn.execute(
                f"""UPDATE email_queue
                    SET status = ?, rejection_reason = ?, reviewed_by = ?, reviewed_at = ?
                    WHERE queue_id IN ({placeholders})""",
                [EmailStatus.REJECTED.value, reason, reviewed_by, now] + ids,
            )

            for qid in ids:
                self._log_action(conn, qid, "", "rejected", actor=reviewed_by,
                                 details={"batch_action": "reject_all", "reason": reason})
            conn.commit()
            return len(ids)
        finally:
            conn.close()

    def approve_by_tier(self, tier_value: str, reviewed_by: str = "Laura") -> int:
        """Approve all pending drafts matching a specific tier.

        Args:
            tier_value: The tier string (e.g. "Coming Due", "Overdue").
            reviewed_by: Who is approving.

        Returns:
            Count approved.
        """
        conn = self._get_conn()
        try:
            now = _now_iso()
            rows = conn.execute(
                "SELECT queue_id FROM email_queue WHERE status = ? AND tier = ?",
                (EmailStatus.PENDING.value, tier_value),
            ).fetchall()

            if not rows:
                return 0

            ids = [dict(r)["queue_id"] for r in rows]
            placeholders = ", ".join(["?"] * len(ids))
            conn.execute(
                f"""UPDATE email_queue
                    SET status = ?, reviewed_by = ?, reviewed_at = ?
                    WHERE queue_id IN ({placeholders})""",
                [EmailStatus.APPROVED.value, reviewed_by, now] + ids,
            )

            for qid in ids:
                self._log_action(conn, qid, "", "approved", actor=reviewed_by,
                                 details={"batch_action": "approve_by_tier", "tier": tier_value})
            conn.commit()
            return len(ids)
        finally:
            conn.close()

    def approve_selected(self, queue_ids: list[str], reviewed_by: str = "Laura") -> int:
        """Approve a specific list of drafts by queue_id.

        Only approves those currently in 'pending' status.
        Returns count approved.
        """
        if not queue_ids:
            return 0

        conn = self._get_conn()
        try:
            now = _now_iso()
            count = 0
            for qid in queue_ids:
                result = conn.execute(
                    """UPDATE email_queue
                       SET status = ?, reviewed_by = ?, reviewed_at = ?
                       WHERE queue_id = ? AND status = ?""",
                    (EmailStatus.APPROVED.value, reviewed_by, now, qid, EmailStatus.PENDING.value),
                )
                if result.rowcount > 0:
                    self._log_action(conn, qid, "", "approved", actor=reviewed_by,
                                     details={"batch_action": "approve_selected"})
                    count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Filtering & Queries
    # ------------------------------------------------------------------

    def filter(
        self,
        status: str | None = None,
        tier: str | None = None,
        store_name: str | None = None,
        batch_id: str | None = None,
        has_flags: bool | None = None,
    ) -> list[tuple[str, EmailDraft]]:
        """Filter queue items by one or more criteria.

        All arguments are optional.  When multiple are provided, they
        are ANDed together.

        Args:
            status: Filter by EmailStatus value (e.g. "pending", "approved").
            tier: Filter by tier value (e.g. "Coming Due", "50+ Days Past Due").
            store_name: Partial, case-insensitive match on store_name.
            batch_id: Exact match on batch_id.
            has_flags: If True, only items with flags; if False, only unflagged.

        Returns:
            List of (queue_id, EmailDraft) tuples matching all criteria.
        """
        conditions = []
        params: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        if tier is not None:
            conditions.append("tier = ?")
            params.append(tier)

        if store_name is not None:
            conditions.append("LOWER(store_name) LIKE ?")
            params.append(f"%{store_name.lower()}%")

        if batch_id is not None:
            conditions.append("batch_id = ?")
            params.append(batch_id)

        if has_flags is True:
            conditions.append("flags_json != '[]' AND flags_json != '' AND flags_json IS NOT NULL")
        elif has_flags is False:
            conditions.append("(flags_json = '[]' OR flags_json = '' OR flags_json IS NULL)")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM email_queue WHERE {where} ORDER BY created_at ASC"

        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [(dict(r)["queue_id"], _row_to_draft(dict(r))) for r in rows]
        finally:
            conn.close()

    def get_pending(self) -> list[tuple[str, EmailDraft]]:
        """Shortcut: get all pending drafts."""
        return self.filter(status=EmailStatus.PENDING.value)

    def get_approved(self) -> list[tuple[str, EmailDraft]]:
        """Shortcut: get all approved drafts."""
        return self.filter(status=EmailStatus.APPROVED.value)

    def get_sent(self) -> list[tuple[str, EmailDraft]]:
        """Shortcut: get all sent drafts."""
        return self.filter(status=EmailStatus.SENT.value)

    def get_flagged(self) -> list[tuple[str, EmailDraft]]:
        """Shortcut: get all pending drafts that have flags."""
        return self.filter(status=EmailStatus.PENDING.value, has_flags=True)

    # ------------------------------------------------------------------
    # Statistics & Summaries
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return queue statistics.

        Returns a dict with:
            counts_by_status: {pending: N, approved: N, rejected: N, sent: N, failed: N}
            counts_by_tier: {tier_label: N, ...}
            total_amount_by_status: {pending: $, approved: $, ...}
            total_amount_by_tier: {tier_label: $, ...}
            total_emails: N
            total_invoices: N
            total_ar_amount: $
            flagged_count: N
        """
        conn = self._get_conn()
        try:
            # Counts and amounts by status
            status_rows = conn.execute(
                """SELECT status, COUNT(*) as cnt, SUM(total_amount) as total
                   FROM email_queue GROUP BY status"""
            ).fetchall()

            counts_by_status = {}
            amounts_by_status = {}
            total_emails = 0
            total_ar = 0.0
            for r in status_rows:
                d = dict(r)
                counts_by_status[d["status"]] = d["cnt"]
                amounts_by_status[d["status"]] = d["total"] or 0.0
                total_emails += d["cnt"]
                total_ar += d["total"] or 0.0

            # Counts and amounts by tier
            tier_rows = conn.execute(
                """SELECT tier, COUNT(*) as cnt, SUM(total_amount) as total
                   FROM email_queue GROUP BY tier"""
            ).fetchall()

            counts_by_tier = {}
            amounts_by_tier = {}
            for r in tier_rows:
                d = dict(r)
                counts_by_tier[d["tier"]] = d["cnt"]
                amounts_by_tier[d["tier"]] = d["total"] or 0.0

            # Total invoices (sum across all drafts)
            inv_row = conn.execute(
                """SELECT SUM(
                     CASE WHEN is_multi_invoice = 1
                          THEN json_array_length(invoices_json)
                          ELSE 1
                     END
                   ) as total_inv FROM email_queue"""
            ).fetchone()
            total_invoices = dict(inv_row)["total_inv"] or 0

            # Flagged count
            flagged_row = conn.execute(
                """SELECT COUNT(*) as cnt FROM email_queue
                   WHERE flags_json != '[]' AND flags_json != '' AND flags_json IS NOT NULL"""
            ).fetchone()
            flagged_count = dict(flagged_row)["cnt"]

            return {
                "counts_by_status": counts_by_status,
                "counts_by_tier": counts_by_tier,
                "total_amount_by_status": amounts_by_status,
                "total_amount_by_tier": amounts_by_tier,
                "total_emails": total_emails,
                "total_invoices": total_invoices,
                "total_ar_amount": total_ar,
                "flagged_count": flagged_count,
            }
        finally:
            conn.close()

    def get_summary(self) -> str:
        """Return a human-readable summary string for CLI or logging."""
        stats = self.get_stats()
        lines = [
            f"Email Queue Summary ({stats['total_emails']} emails, "
            f"{stats['total_invoices']} invoices)",
            f"  Total AR: ${stats['total_ar_amount']:,.2f}",
            "",
            "  By Status:",
        ]
        for status_val in ["pending", "approved", "rejected", "sent", "failed"]:
            cnt = stats["counts_by_status"].get(status_val, 0)
            amt = stats["total_amount_by_status"].get(status_val, 0.0)
            lines.append(f"    {status_val:<12s}  {cnt:>3d} emails  ${amt:>12,.2f}")

        lines.append("")
        lines.append("  By Tier:")
        for tier_val, cnt in sorted(stats["counts_by_tier"].items()):
            amt = stats["total_amount_by_tier"].get(tier_val, 0.0)
            lines.append(f"    {tier_val:<22s}  {cnt:>3d} emails  ${amt:>12,.2f}")

        if stats["flagged_count"] > 0:
            lines.append("")
            lines.append(f"  Flagged for review: {stats['flagged_count']}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON Persistence (backup / resume)
    # ------------------------------------------------------------------

    def save_to_json(self, path: str | Path | None = None) -> Path:
        """Export the entire queue state to a JSON file.

        This provides human-readable backup and allows resuming a
        session if the database is lost.

        Returns the Path written to.
        """
        out_path = Path(path) if path else self.json_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM email_queue ORDER BY created_at ASC"
            ).fetchall()

            data = {
                "exported_at": _now_iso(),
                "db_path": str(self.db_path),
                "summary": self.get_stats(),
                "drafts": [dict(r) for r in rows],
            }

            out_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            return out_path
        finally:
            conn.close()

    def load_from_json(self, path: str | Path | None = None) -> int:
        """Load queue state from a previously exported JSON file.

        Inserts records that don't already exist (by queue_id).
        Returns the count of newly inserted records.

        This is intended for disaster recovery / session resume, not
        for normal operation.
        """
        in_path = Path(path) if path else self.json_path
        if not in_path.exists():
            return 0

        data = json.loads(in_path.read_text(encoding="utf-8"))
        drafts = data.get("drafts", [])

        conn = self._get_conn()
        try:
            count = 0
            for row_dict in drafts:
                qid = row_dict.get("queue_id")
                if not qid:
                    continue

                # Check if already exists
                existing = conn.execute(
                    "SELECT 1 FROM email_queue WHERE queue_id = ?", (qid,)
                ).fetchone()
                if existing:
                    continue

                columns = [k for k in row_dict if k in _get_table_columns(conn, "email_queue")]
                if not columns:
                    continue

                placeholders = ", ".join(["?"] * len(columns))
                col_str = ", ".join(columns)
                conn.execute(
                    f"INSERT INTO email_queue ({col_str}) VALUES ({placeholders})",
                    [row_dict[c] for c in columns],
                )
                count += 1

            conn.commit()
            return count
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # .eml File Export
    # ------------------------------------------------------------------

    def export_eml(self, queue_id: str, output_dir: str | Path | None = None) -> Path | None:
        """Export a single approved email to a .eml file.

        The .eml file can be opened in Outlook, Thunderbird, or Gmail
        for manual review and sending.

        Args:
            queue_id: The draft to export.
            output_dir: Directory to write the file. Defaults to self.eml_dir.

        Returns:
            Path to the generated .eml file, or None if the draft
            was not found or not in an exportable status.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM email_queue WHERE queue_id = ?", (queue_id,)
            ).fetchone()
            if row is None:
                return None

            row_dict = dict(row)

            # Allow exporting approved or pending drafts
            if row_dict["status"] not in (
                EmailStatus.APPROVED.value,
                EmailStatus.PENDING.value,
            ):
                return None

            return self._write_eml_file(row_dict, output_dir)
        finally:
            conn.close()

    def export_all_approved_eml(self, output_dir: str | Path | None = None) -> list[Path]:
        """Export all approved emails to .eml files.

        Returns list of Paths to the generated files.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM email_queue WHERE status = ? ORDER BY created_at ASC",
                (EmailStatus.APPROVED.value,),
            ).fetchall()

            paths = []
            for row in rows:
                p = self._write_eml_file(dict(row), output_dir)
                if p:
                    paths.append(p)
            return paths
        finally:
            conn.close()

    def export_all_eml(self, output_dir: str | Path | None = None) -> list[Path]:
        """Export ALL emails (any status) to .eml files for archival.

        Returns list of Paths to the generated files.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM email_queue ORDER BY created_at ASC"
            ).fetchall()

            paths = []
            for row in rows:
                p = self._write_eml_file(dict(row), output_dir)
                if p:
                    paths.append(p)
            return paths
        finally:
            conn.close()

    def _write_eml_file(self, row_dict: dict[str, Any],
                        output_dir: str | Path | None = None) -> Path | None:
        """Internal: build MIME message and write to .eml file.

        Returns the Path written to, or None on error.
        """
        out_dir = Path(output_dir) if output_dir else self.eml_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            to_list = json.loads(row_dict.get("to_emails", "[]"))
            cc_list = json.loads(row_dict.get("cc_emails", "[]"))
            bcc_list = json.loads(row_dict.get("bcc_emails", "[]"))
        except (json.JSONDecodeError, TypeError):
            to_list, cc_list, bcc_list = [], [], []

        # Build MIME message
        msg = MIMEMultipart("mixed")
        msg["Subject"] = row_dict.get("subject", "")
        msg["From"] = (
            f"{row_dict.get('from_name', '')} <{row_dict.get('from_email', '')}>"
            if row_dict.get("from_name")
            else row_dict.get("from_email", "")
        )
        msg["To"] = ", ".join(to_list) if to_list else ""
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        if bcc_list:
            msg["Bcc"] = ", ".join(bcc_list)
        msg["Date"] = row_dict.get("created_at", _now_iso())

        # Build alternative body (plain text + HTML)
        body_part = MIMEMultipart("alternative")

        # Plain text fallback: strip HTML tags for a rough plaintext version
        html_body = row_dict.get("body_html", "")
        text_body = _html_to_plaintext(html_body)
        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))

        msg.attach(body_part)

        # Attach files if they exist
        try:
            attachment_paths = json.loads(row_dict.get("attachments_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            attachment_paths = []

        for att_path_str in attachment_paths:
            att_path = Path(att_path_str)
            if not att_path.is_absolute():
                att_path = PROJECT_ROOT / att_path_str
            if att_path.exists():
                with open(att_path, "rb") as f:
                    attachment = MIMEApplication(f.read(), Name=att_path.name)
                    attachment["Content-Disposition"] = f'attachment; filename="{att_path.name}"'
                    msg.attach(attachment)

        # Generate filename
        store = row_dict.get("store_name", "unknown").replace(" ", "_").replace("/", "-")
        tier = row_dict.get("tier", "unknown").replace(" ", "_").replace("+", "plus")
        queue_id = row_dict.get("queue_id", "unknown")[:8]
        filename = f"{store}_{tier}_{queue_id}.eml"

        eml_path = out_dir / filename
        eml_path.write_text(msg.as_string(), encoding="utf-8")

        return eml_path

    # ------------------------------------------------------------------
    # Send History
    # ------------------------------------------------------------------

    def get_send_history(
        self,
        store_name: str | None = None,
        tier: str | None = None,
        since_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query the emails_sent history table.

        Args:
            store_name: Partial, case-insensitive match on store name.
            tier: Exact match on tier value.
            since_date: Only records after this ISO date (e.g. "2026-01-01").
            limit: Maximum records to return.

        Returns:
            List of dicts, each representing one sent email record.
        """
        conditions = []
        params: list[Any] = []

        if store_name:
            conditions.append("LOWER(store_name) LIKE ?")
            params.append(f"%{store_name.lower()}%")

        if tier:
            conditions.append("tier = ?")
            params.append(tier)

        if since_date:
            conditions.append("sent_date >= ?")
            params.append(since_date)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""SELECT * FROM emails_sent
                  WHERE {where}
                  ORDER BY sent_date DESC
                  LIMIT ?"""
        params.append(limit)

        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def was_recently_emailed(self, store_name: str, within_days: int = 7) -> bool:
        """Check if a store was emailed within the last N days.

        Useful for preventing duplicate emails in the same weekly cycle.
        """
        conn = self._get_conn()
        try:
            # SQLite date comparison using julianday
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM emails_sent
                   WHERE LOWER(store_name) = LOWER(?)
                   AND julianday('now') - julianday(sent_date) <= ?""",
                (store_name, within_days),
            ).fetchone()
            return dict(row)["cnt"] > 0
        finally:
            conn.close()

    def get_store_email_history(self, store_name: str) -> list[dict[str, Any]]:
        """Get the complete email history for a specific store.

        Returns all emails_sent records for this store, newest first.
        """
        return self.get_send_history(store_name=store_name, limit=500)

    # ------------------------------------------------------------------
    # Queue Management
    # ------------------------------------------------------------------

    def clear_pending(self) -> int:
        """Remove all pending (un-reviewed) drafts.

        Used when re-running the pipeline with fresh data. Approved,
        sent, and rejected records are preserved for audit.

        Returns count of records deleted.
        """
        conn = self._get_conn()
        try:
            # Log before deleting
            rows = conn.execute(
                "SELECT queue_id FROM email_queue WHERE status = ?",
                (EmailStatus.PENDING.value,),
            ).fetchall()

            ids = [dict(r)["queue_id"] for r in rows]
            for qid in ids:
                self._log_action(conn, qid, "", "cleared",
                                 details={"reason": "Queue cleared for fresh batch"})

            result = conn.execute(
                "DELETE FROM email_queue WHERE status = ?",
                (EmailStatus.PENDING.value,),
            )
            conn.commit()
            return result.rowcount
        finally:
            conn.close()

    def clear_all(self) -> int:
        """Remove ALL drafts from the queue (nuclear option).

        Preserves the emails_sent history and audit_log.
        Returns count of records deleted.
        """
        conn = self._get_conn()
        try:
            result = conn.execute("DELETE FROM email_queue")
            conn.commit()
            return result.rowcount
        finally:
            conn.close()

    def count(self, status: str | None = None) -> int:
        """Count queue items, optionally filtered by status."""
        conn = self._get_conn()
        try:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM email_queue WHERE status = ?",
                    (status,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM email_queue"
                ).fetchone()
            return dict(row)["cnt"]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Audit Log
    # ------------------------------------------------------------------

    def get_audit_log(self, queue_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Retrieve audit log entries.

        Args:
            queue_id: If provided, only entries for this draft.
            limit: Maximum entries to return.

        Returns:
            List of audit log dicts, newest first.
        """
        conn = self._get_conn()
        try:
            if queue_id:
                rows = conn.execute(
                    """SELECT * FROM audit_log
                       WHERE queue_id = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (queue_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _log_action(
        self,
        conn: sqlite3.Connection,
        queue_id: str,
        batch_id: str,
        action: str,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write an audit log entry (internal, must be within a transaction)."""
        conn.execute(
            """INSERT INTO audit_log (queue_id, batch_id, action, actor, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                queue_id,
                batch_id,
                action,
                actor,
                json.dumps(details or {}),
                _now_iso(),
            ),
        )

    # ------------------------------------------------------------------
    # Batch Run Tracking
    # ------------------------------------------------------------------

    def get_batch_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent batch run records."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM batch_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def complete_batch(self, batch_id: str) -> bool:
        """Mark a batch run as completed."""
        conn = self._get_conn()
        try:
            result = conn.execute(
                "UPDATE batch_runs SET completed_at = ? WHERE batch_id = ?",
                (_now_iso(), batch_id),
            )
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # In-Memory Queue Bridge
    # ------------------------------------------------------------------

    def to_email_queue(self) -> EmailQueue:
        """Convert the persistent queue to the in-memory EmailQueue model.

        Useful for compatibility with code that expects the models.EmailQueue
        dataclass (e.g., the export_json/export_csv methods on EmailQueue).
        """
        items = self.get_all()
        queue = EmailQueue()
        for _qid, draft in items:
            queue.add(draft)
        return queue

    def from_email_queue(self, queue: EmailQueue, batch_id: str = "") -> list[str]:
        """Import an in-memory EmailQueue into the persistent store.

        Returns list of generated queue_ids.
        """
        return self.add_batch(queue.drafts, batch_id=batch_id)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _html_to_plaintext(html: str) -> str:
    """Rough HTML-to-plaintext conversion for .eml fallback body.

    Not meant to be perfect -- just strips tags for a readable fallback.
    """
    import re
    # Replace <br> and </p> with newlines
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Get the set of column names for a table."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {dict(r)["name"] for r in rows}


# ---------------------------------------------------------------------------
# Module self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 70)
    print("Email Queue Manager -- Self-Test")
    print("=" * 70)

    # Use a temp directory for test DB
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_queue.db")
        json_path = os.path.join(tmpdir, "test_state.json")
        eml_dir = os.path.join(tmpdir, "eml")

        mgr = EmailQueueManager(db_path=db_path, json_path=json_path, eml_dir=eml_dir)

        # Create test drafts
        inv1 = Invoice(
            invoice_number="906858",
            store_name="Aroma Farms",
            amount=1510.00,
            due_date=date(2026, 2, 5),
            days_past_due=-2,
        )
        inv2 = Invoice(
            invoice_number="904667",
            store_name="Seaweed RBNY",
            amount=309.50,
            due_date=date(2026, 1, 20),
            days_past_due=19,
        )
        inv3 = Invoice(
            invoice_number="905055",
            store_name="Seaweed RBNY",
            amount=3011.50,
            due_date=date(2026, 1, 23),
            days_past_due=16,
        )
        inv4 = Invoice(
            invoice_number="893281",
            store_name="Dazed - New York",
            amount=18071.75,
            due_date=date(2025, 10, 15),
            days_past_due=111,
        )

        draft1 = EmailDraft(
            to=["aromafarmsinc@gmail.com"],
            cc=["ny.ar@nabis.com", "laura@piccplatform.com"],
            subject="PICC - Aroma Farms - Nabis Invoice 906858 - Coming Due",
            body_html="<p>Hello Emily, your payment is coming due.</p>",
            tier=Tier.T0,
            invoices=[inv1],
            store_name="Aroma Farms",
            attachments=["data/Nabis_ACH_Payment_Form.pdf"],
        )

        draft2 = EmailDraft(
            to=["adam@seaweedrbny.com"],
            cc=["ny.ar@nabis.com", "laura@piccplatform.com"],
            subject="PICC - Seaweed RBNY - Nabis Invoices 904667 & 905055 - Overdue",
            body_html="<p>Hello Adam, your invoices are overdue.</p>",
            tier=Tier.T1,
            invoices=[inv2, inv3],
            store_name="Seaweed RBNY",
        )

        draft3 = EmailDraft(
            to=["accounting@dazed.fun"],
            cc=["ny.ar@nabis.com", "mario@piccplatform.com"],
            subject="PICC - Dazed - Nabis Invoice 893281 - 50+ Days Past Due",
            body_html="<p>Hello, this is a serious past-due notice.</p>",
            tier=Tier.T4,
            invoices=[inv4],
            store_name="Dazed - New York",
        )

        # Test: add drafts
        qid1 = mgr.add(draft1)
        qid2 = mgr.add(draft2, flags=["MULTI_INVOICE"], flag_reasons=["Contains 2 invoices"])
        qid3 = mgr.add(draft3, flags=["HIGH_VALUE", "CHRONIC_DELINQUENT"],
                        flag_reasons=["Amount > $5000", "111 days overdue"])
        print(f"\n  Added 3 drafts: {qid1[:8]}... {qid2[:8]}... {qid3[:8]}...")

        # Test: get stats
        stats = mgr.get_stats()
        print(f"\n  Stats: {stats['total_emails']} emails, ${stats['total_ar_amount']:,.2f} AR")
        print(f"  By status: {stats['counts_by_status']}")
        print(f"  By tier: {stats['counts_by_tier']}")

        # Test: summary
        print(f"\n{mgr.get_summary()}")

        # Test: filter
        pending = mgr.get_pending()
        print(f"\n  Pending: {len(pending)}")
        flagged = mgr.get_flagged()
        print(f"  Flagged: {len(flagged)}")

        # Test: approve unflagged
        approved_count = mgr.approve_unflagged()
        print(f"\n  Approved unflagged: {approved_count}")

        # Test: approve remaining
        mgr.approve(qid2)
        mgr.approve(qid3)
        approved = mgr.get_approved()
        print(f"  Total approved: {len(approved)}")

        # Test: mark sent
        mgr.mark_sent(qid1)
        mgr.mark_sent(qid2)
        sent = mgr.get_sent()
        print(f"  Sent: {len(sent)}")

        # Test: send history
        history = mgr.get_send_history()
        print(f"\n  Send history records: {len(history)}")
        for h in history:
            print(f"    {h['store_name']} | {h['tier']} | {h['sent_date'][:10]} | "
                  f"invoices: {h['invoice_numbers']}")

        # Test: was recently emailed
        recent = mgr.was_recently_emailed("Aroma Farms", within_days=1)
        print(f"\n  Aroma Farms recently emailed: {recent}")

        # Test: export JSON
        json_out = mgr.save_to_json()
        print(f"\n  JSON exported to: {json_out}")
        json_size = json_out.stat().st_size
        print(f"  JSON size: {json_size:,} bytes")

        # Test: export EML
        eml_paths = mgr.export_all_approved_eml()
        print(f"\n  EML files exported: {len(eml_paths)}")
        for p in eml_paths:
            print(f"    {p.name} ({p.stat().st_size:,} bytes)")

        # Test: audit log
        audit = mgr.get_audit_log(limit=10)
        print(f"\n  Audit log entries: {len(audit)}")
        for entry in audit[:5]:
            print(f"    [{entry['action']}] {entry['queue_id'][:8]}... "
                  f"by {entry['actor']} at {entry['timestamp'][:19]}")

        # Test: edit
        edit_ok = mgr.edit(qid3, subject="EDITED: Dazed New York - Past Due Notice")
        print(f"\n  Edit draft (should fail, already approved): {edit_ok}")

        # Test: reject then reset
        # Can't reject approved, so let's add a new one and test
        draft4 = EmailDraft(
            to=["test@test.com"],
            subject="Test draft for reject/reset",
            body_html="<p>Test</p>",
            tier=Tier.T1,
            invoices=[inv2],
            store_name="Test Store",
        )
        qid4 = mgr.add(draft4)
        reject_ok = mgr.reject(qid4, reason="Test rejection")
        print(f"  Reject: {reject_ok}")
        reset_ok = mgr.reset_to_pending(qid4)
        print(f"  Reset to pending: {reset_ok}")

        # Final summary
        print(f"\n{mgr.get_summary()}")

    print("\n" + "=" * 70)
    print("ALL SELF-TESTS COMPLETE")
    print("=" * 70)
