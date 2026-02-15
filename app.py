"""
AR Email Automation -- Streamlit Web Interface

Dead-simple UI for Laura to review, approve, and export AR collection emails.

Usage:
    streamlit run app.py

The app imports from the src/ package (models, config, data_loader, etc.)
and handles missing modules gracefully since some are still being built.
"""

from __future__ import annotations

import io
import json
import logging
import os
import smtplib
import ssl
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, time as dt_time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Any

smtp_logger = logging.getLogger("ar_email.smtp")

import streamlit as st

# ---------------------------------------------------------------------------
# Project root setup -- ensure src/ is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Graceful imports from the src package
# ---------------------------------------------------------------------------

# Models -- required (core dataclasses)
try:
    from src.models import (
        Invoice,
        Contact,
        EmailDraft,
        EmailQueue,
        EmailStatus,
        Tier,
        InvoiceStatus,
        SkipReason,
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    MODELS_AVAILABLE = False
    _models_error = str(e)

# Config -- required
try:
    from src.config import get_config, AREmailConfig, PROJECT_ROOT as CFG_ROOT
    CONFIG_AVAILABLE = True
except ImportError as e:
    CONFIG_AVAILABLE = False
    _config_error = str(e)

# Data loader -- optional (can demo without it)
try:
    from src.data_loader import load_workbook, LoadResult
    DATA_LOADER_AVAILABLE = True
except ImportError as e:
    DATA_LOADER_AVAILABLE = False
    _loader_error = str(e)

# Tier classifier -- optional (used for enrichment)
try:
    from src.tier_classifier import (
        classify,
        get_dynamic_subject_label,
        Tier as ClassifierTier,
        TIER_METADATA,
    )
    CLASSIFIER_AVAILABLE = True
except ImportError as e:
    CLASSIFIER_AVAILABLE = False

# Contact resolver -- optional
try:
    from src.contact_resolver import ContactResolver, resolve_contacts
    RESOLVER_AVAILABLE = True
except ImportError as e:
    RESOLVER_AVAILABLE = False

# Template engine -- optional (renders real Jinja2 email templates)
try:
    from src.template_engine import TemplateEngine
    TEMPLATE_ENGINE_AVAILABLE = True
except ImportError as e:
    TEMPLATE_ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# PICC Brand Colors & Page Config
# ---------------------------------------------------------------------------

PICC_GOLD = "#a37e2c"
PICC_DARK_GREEN = "#032e23"
PICC_LIGHT_GOLD = "#d4a843"
PICC_LIGHT_GREEN = "#0a5c46"
PICC_WHITE = "#ffffff"
PICC_LIGHT_BG = "#f8f6f0"

# Tier badge colors (3-tier system: Coming Due, Overdue, 30+ Days Past Due)
TIER_COLORS = {
    "Coming Due":          {"bg": "#d4edda", "text": "#155724", "icon": ""},
    "Overdue":             {"bg": "#fff3cd", "text": "#856404", "icon": ""},
    "30+ Days Past Due":   {"bg": "#f8d7da", "text": "#721c24", "icon": ""},
}

# Status badge colors
STATUS_COLORS = {
    "pending":  {"bg": "#e2e3e5", "text": "#383d41"},
    "approved": {"bg": "#d4edda", "text": "#155724"},
    "rejected": {"bg": "#f8d7da", "text": "#721c24"},
    "sent":     {"bg": "#cce5ff", "text": "#004085"},
    "failed":   {"bg": "#f5c6cb", "text": "#721c24"},
}


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PICC AR Email Automation",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS -- PICC branding, clean professional look
# ---------------------------------------------------------------------------

st.markdown(f"""
<style>
    /* Global font and background */
    .stApp {{
        font-family: 'Segoe UI', -apple-system, sans-serif;
    }}

    /* Header bar */
    .picc-header {{
        background: linear-gradient(135deg, {PICC_DARK_GREEN}, {PICC_LIGHT_GREEN});
        color: {PICC_WHITE};
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }}
    .picc-header h1 {{
        color: {PICC_LIGHT_GOLD} !important;
        margin: 0 !important;
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }}
    .picc-header p {{
        color: {PICC_WHITE};
        margin: 0.25rem 0 0 0;
        font-size: 0.9rem;
        opacity: 0.85;
    }}

    /* Stat cards */
    .stat-card {{
        background: {PICC_WHITE};
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    .stat-card .stat-number {{
        font-size: 2rem;
        font-weight: 700;
        color: {PICC_DARK_GREEN};
        line-height: 1.2;
    }}
    .stat-card .stat-label {{
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.25rem;
    }}
    .stat-card.gold .stat-number {{
        color: {PICC_GOLD};
    }}

    /* Tier badges */
    .tier-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }}

    /* Status badges */
    .status-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }}

    /* Email card */
    .email-card {{
        background: {PICC_WHITE};
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s;
    }}
    .email-card:hover {{
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }}
    .email-card.flagged {{
        border-left: 4px solid #ffc107;
    }}

    /* Email preview */
    .email-preview {{
        background: {PICC_WHITE};
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }}
    .email-header-row {{
        display: flex;
        gap: 0.5rem;
        margin-bottom: 0.3rem;
    }}
    .email-header-label {{
        font-weight: 600;
        color: #555;
        min-width: 60px;
        font-size: 0.85rem;
    }}
    .email-header-value {{
        color: #333;
        font-size: 0.85rem;
    }}

    /* Variable highlights in email body */
    .var-highlight {{
        background: #fff9e6;
        border: 1px solid {PICC_GOLD};
        border-radius: 3px;
        padding: 0 4px;
        font-weight: 500;
    }}

    /* Flag badges */
    .flag-badge {{
        display: inline-block;
        background: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: 500;
        margin-right: 4px;
    }}

    /* Sidebar styling */
    section[data-testid="stSidebar"] {{
        background: {PICC_LIGHT_BG};
    }}
    section[data-testid="stSidebar"] .stMarkdown h3 {{
        color: {PICC_DARK_GREEN};
    }}

    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* Table-like row styling */
    .queue-row {{
        display: grid;
        grid-template-columns: 40px 80px 1fr 110px 80px 90px 120px;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 6px;
        margin-bottom: 6px;
        font-size: 0.85rem;
    }}
    .queue-row:hover {{
        background: #f8f9fa;
    }}

    /* Action buttons */
    .stButton > button {{
        border-radius: 6px !important;
    }}

    /* Divider */
    .section-divider {{
        border-top: 2px solid {PICC_GOLD};
        margin: 1.5rem 0;
        opacity: 0.3;
    }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"

def _load_saved_settings() -> dict:
    """Load persisted settings from JSON file on disk."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_settings(settings: dict) -> bool:
    """Save settings dict to JSON file on disk. Returns True on success."""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def init_session_state():
    """Initialize all session state variables, loading saved settings if available."""
    saved = _load_saved_settings()

    defaults = {
        "queue": None,              # EmailQueue instance
        "load_result": None,        # LoadResult from data_loader
        "selected_email_idx": None, # Index of email being previewed
        "page": "queue",            # Current page: queue, preview, history, settings, dnc
        "filter_tiers": [],         # Tier filter selections
        "filter_status": [],        # Status filter selections
        "generated": False,         # Whether emails have been generated
        "do_not_contact": [],       # List of store names to exclude
        "history": [],              # List of previously exported email dicts
        "upload_key": 0,            # Key for file uploader widget
        "gmail_app_password": "",   # Gmail App Password for SMTP sending
        "sender_email": saved.get("sender_email", "laura@piccplatform.com"),
        "sender_name": saved.get("sender_name", ""),
        "smtp_configured": False,   # Whether SMTP creds are set
        "send_results": [],         # Results from last send batch
        "custom_cc": saved.get("custom_cc", None),  # Persisted CC list (None = use config default)
        "schedule_time": saved.get("schedule_time", "07:00"),  # Schedule send time
        "schedule_timezone": saved.get("schedule_timezone", "PT"),  # Schedule timezone
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def tier_badge_html(tier_label: str) -> str:
    """Render a colored tier badge as HTML."""
    colors = TIER_COLORS.get(tier_label, {"bg": "#e2e3e5", "text": "#383d41", "icon": ""})
    return (
        f'<span class="tier-badge" style="background:{colors["bg"]};'
        f'color:{colors["text"]}">{colors["icon"]} {tier_label}</span>'
    )


def status_badge_html(status: str) -> str:
    """Render a colored status badge as HTML."""
    colors = STATUS_COLORS.get(status, {"bg": "#e2e3e5", "text": "#383d41"})
    return (
        f'<span class="status-badge" style="background:{colors["bg"]};'
        f'color:{colors["text"]}">{status}</span>'
    )


def format_currency(amount: float) -> str:
    """Format a dollar amount: $1,234.56"""
    return f"${amount:,.2f}"


def get_max_days_over(draft: EmailDraft) -> int:
    """Get the max days_past_due from a draft's invoices."""
    if not draft.invoices:
        return 0
    return max(inv.days_past_due for inv in draft.invoices)


def get_flags(draft: EmailDraft) -> list[str]:
    """Compute flags for an email draft."""
    flags = []
    if draft.is_multi_invoice:
        flags.append("MULTI-INVOICE")
    for inv in draft.invoices:
        if inv.amount > 5000:
            flags.append("HIGH VALUE")
        if inv.days_past_due > 80:
            flags.append("CHRONIC")
        if not inv.account_manager or inv.account_manager in ("", "#N/A"):
            flags.append("MISSING AM")
        if inv.notes and "@" in inv.notes:
            flags.append("CHECK NOTES")
        if inv.status == InvoiceStatus.ISSUE:
            flags.append("DISPUTE")
    return list(set(flags))


def _get_template_engine() -> "TemplateEngine | None":
    """Create a TemplateEngine with the sender name from session state applied."""
    if not TEMPLATE_ENGINE_AVAILABLE:
        return None
    engine = TemplateEngine()
    name = st.session_state.get("sender_name", "").strip()
    if name:
        engine.config.sender.name = name
        engine.config.signature.sender_name = name
    return engine


def generate_eml(draft: EmailDraft) -> str:
    """Generate an .eml file content string from an EmailDraft."""
    msg = MIMEMultipart("mixed")
    msg["From"] = st.session_state.get("sender_email", "laura@piccplatform.com")
    msg["To"] = ", ".join(draft.to) if draft.to else ""
    msg["Cc"] = ", ".join(draft.cc) if draft.cc else ""
    eml_bcc = getattr(draft, "bcc", []) or []
    if eml_bcc:
        msg["Bcc"] = ", ".join(eml_bcc)
    msg["Subject"] = draft.subject
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Body (HTML)
    if draft.body_html:
        html_part = MIMEText(draft.body_html, "html", "utf-8")
        msg.attach(html_part)
    else:
        text_part = MIMEText(
            f"Email for {draft.store_name} - {draft.tier.value}\n\n"
            f"Invoices: {', '.join(draft.invoice_numbers)}\n"
            f"Amount: {draft.total_amount_formatted}",
            "plain",
            "utf-8",
        )
        msg.attach(text_part)

    return msg.as_string()


def _build_smtp_message(draft: EmailDraft, sender_email: str) -> MIMEMultipart:
    """Build a fully-formed MIME message ready for SMTP sending.

    Includes HTML body and attaches the Nabis ACH Payment Form PDF if found.
    """
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = ", ".join(draft.to) if draft.to else ""
    msg["Cc"] = ", ".join(draft.cc) if draft.cc else ""
    smtp_bcc = getattr(draft, "bcc", []) or []
    if smtp_bcc:
        msg["Bcc"] = ", ".join(smtp_bcc)
    msg["Subject"] = draft.subject
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    # HTML body
    if draft.body_html:
        html_part = MIMEText(draft.body_html, "html", "utf-8")
        msg.attach(html_part)
    else:
        text_part = MIMEText(
            f"Email for {draft.store_name} - {draft.tier.value}\n\n"
            f"Invoices: {', '.join(draft.invoice_numbers)}\n"
            f"Amount: {draft.total_amount_formatted}",
            "plain",
            "utf-8",
        )
        msg.attach(text_part)

    # Attach ACH Payment Form PDF if it exists
    ach_paths = [
        PROJECT_ROOT / "data" / "Nabis_ACH_Payment_Form.pdf",
        PROJECT_ROOT / "data" / "emails" / "Nabis ACH Payment Form.pdf",
    ]
    for ach_path in ach_paths:
        if ach_path.exists():
            with open(ach_path, "rb") as f:
                pdf_part = MIMEBase("application", "pdf")
                pdf_part.set_payload(f.read())
                encoders.encode_base64(pdf_part)
                pdf_part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename="Nabis ACH Payment Form.pdf",
                )
                msg.attach(pdf_part)
            break  # Only attach once

    return msg


def send_email_smtp(
    draft: EmailDraft,
    sender_email: str,
    app_password: str,
) -> tuple[bool, str]:
    """Send a single email via Gmail SMTP.

    Returns (success: bool, message: str).
    """
    if not draft.to:
        return False, f"{draft.store_name}: No recipient email address"

    try:
        msg = _build_smtp_message(draft, sender_email)

        # All recipients (To + CC + BCC)
        all_recipients = list(draft.to) + list(draft.cc) + list(getattr(draft, "bcc", []) or [])

        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(sender_email, app_password)
            server.sendmail(sender_email, all_recipients, msg.as_string())

        smtp_logger.info(f"Sent email to {draft.store_name}: {', '.join(draft.to)}")
        return True, f"{draft.store_name}: Sent successfully"

    except smtplib.SMTPAuthenticationError:
        return False, (
            f"{draft.store_name}: Gmail authentication failed. "
            "Check your App Password in Settings."
        )
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"{draft.store_name}: Recipients refused: {e}"
    except Exception as e:
        smtp_logger.error(f"SMTP error for {draft.store_name}: {e}")
        return False, f"{draft.store_name}: Send failed - {e}"


def get_filtered_drafts() -> list[tuple[int, EmailDraft]]:
    """Return drafts filtered by sidebar selections, as (index, draft) tuples."""
    queue: EmailQueue = st.session_state.queue
    if queue is None:
        return []

    results = []
    for i, draft in enumerate(queue.drafts):
        # Tier filter
        if st.session_state.filter_tiers:
            if draft.tier.value not in st.session_state.filter_tiers:
                continue

        # Status filter
        if st.session_state.filter_status:
            if draft.status.value not in st.session_state.filter_status:
                continue

        results.append((i, draft))

    return results


def build_demo_queue() -> EmailQueue:
    """Build a demonstration EmailQueue with sample data for UI testing."""
    from datetime import timedelta

    queue = EmailQueue()
    today = datetime.now().date()

    sample_stores = [
        ("Aroma Farms", 906858, 1510.00, -2, "Bryce J", "Mildred Verdadero", "(415) 839-8232"),
        ("Seaweed RBNY", 904667, 309.50, 19, "Eric", "Zareena Barillas", "(415) 610-2255"),
        ("Seaweed RBNY", 905055, 3011.50, 16, "Eric", "Zareena Barillas", "(415) 610-2255"),
        ("Royal Blend", 902925, 2602.00, 31, "Ben", "Isa Parman", "(415) 839-8171"),
        ("Dazed - New York", 893281, 9531.75, 111, "Mario", "Isa Parman", "(415) 839-8171"),
        ("Dazed - New York", 898505, 8540.00, 80, "Mario", "Isa Parman", "(415) 839-8171"),
        ("Grounded", 906551, 3752.00, 2, "Bryce J", "Mildred Verdadero", "(415) 839-8232"),
        ("Long Island Cannabis Club", 903480, 2565.00, 27, "M Martin", "Isa Parman", "(415) 839-8171"),
        ("Terp Bros", 905388, 2180.00, 16, "Donovan", "Zareena Barillas", "(415) 610-2255"),
        ("HUB Dispensary", 904301, 1337.50, 37, "Ben", "Isa Parman", "(415) 839-8171"),
        ("Flynnstoned - Brooklyn", 894773, 4240.00, 108, "Mario", "Isa Parman", "(415) 839-8171"),
        ("Valley Greens LTD", 907020, 2700.56, -4, "Bryce J", "Mildred Verdadero", "(415) 839-8232"),
        ("My Bud 420", 901400, 3044.26, 52, "Eric", "Zareena Barillas", "(415) 610-2255"),
        ("THTree", 906990, 1850.00, -3, "Donovan", "Mildred Verdadero", "(415) 839-8232"),
        ("Paradise Cannabis", 896200, 2147.93, 80, "Mario", "Isa Parman", "(415) 839-8171"),
    ]

    # Group by store name for multi-invoice handling
    store_invoices: dict[str, list] = defaultdict(list)
    for store, order, amount, days, rep, am, am_phone in sample_stores:
        inv = Invoice(
            invoice_number=str(order),
            store_name=store,
            amount=amount,
            due_date=today - timedelta(days=days),
            days_past_due=days,
            sales_rep=rep,
            account_manager=am,
            account_manager_phone=am_phone,
        )
        store_invoices[store].append(inv)

    # Use real template engine if available, otherwise fall back to sample HTML
    engine = _get_template_engine()

    for store_name, invoices in store_invoices.items():
        if engine:
            draft = engine.render_email(invoices=invoices)
            # Override TO with demo placeholder (engine leaves TO empty without a Contact)
            if not draft.to:
                draft.to = [f"contact@{store_name.lower().replace(' ', '').replace('-', '')}.com"]
            queue.add(draft)
        else:
            max_days = max(inv.days_past_due for inv in invoices)
            tier = Tier.from_days(max_days)
            draft = EmailDraft(
                to=[f"contact@{store_name.lower().replace(' ', '').replace('-', '')}.com"],
                cc=[
                    "ny.ar@nabis.com",
                    "martinm@piccplatform.com",
                    "mario@piccplatform.com",
                    "laura@piccplatform.com",
                ],
                subject=f"PICC - {store_name} - Nabis {'Invoice' if len(invoices) == 1 else 'Invoices'} "
                        f"{' & '.join(inv.invoice_number for inv in invoices)} - {tier.value}",
                body_html=_build_sample_html(store_name, invoices, tier),
                tier=tier,
                invoices=invoices,
                store_name=store_name,
                status=EmailStatus.PENDING,
            )
            queue.add(draft)

    return queue


def _build_sample_html(store_name: str, invoices: list[Invoice], tier: Tier) -> str:
    """Build a sample HTML email body for demo purposes."""
    first_name = "Team"  # Placeholder

    if tier == Tier.T0:
        opener = (
            f"Hello <span class='var-highlight'>{first_name}</span>,<br><br>"
            "I hope you're well. This is a courtesy reminder that your payment is due soon."
        )
    elif tier == Tier.T1:
        opener = (
            f"Hello <span class='var-highlight'>{first_name}</span>,<br><br>"
            "I hope you're having a great day. This is a friendly reminder that your invoice is past due."
        )
    else:
        opener = (
            f"Hello <span class='var-highlight'>{first_name}</span>,<br><br>"
            "I hope this message finds you well. I am with PICC Platform, and I'm reaching out "
            "with a reminder from the Accounts Receivable department regarding Nabis's OCM reporting "
            "policy for overdue invoices."
        )

    invoice_blocks = ""
    for inv in invoices:
        invoice_blocks += f"""
        <div style="margin: 12px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
            <strong>Invoice/Order:</strong> <span class='var-highlight'>{inv.invoice_number}</span><br>
            <strong>Due:</strong> <span class='var-highlight'>{inv.due_date_formatted or 'N/A'}</span><br>
            <strong>Amount:</strong> <span class='var-highlight'>{inv.amount_formatted}</span><br>
            <strong>Nabis Account Manager:</strong> <span class='var-highlight'>{inv.account_manager}</span>
            <span class='var-highlight'>{inv.account_manager_phone}</span>
        </div>
        """

    html = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
        <p>{opener}</p>

        <p>According to our records, the following invoice{'s are' if len(invoices) > 1 else ' is'} past due:</p>

        {invoice_blocks}

        <p>Attached is the Nabis ACH payment form (PDF) to facilitate your payment.</p>

        <p>PICC and I are committed to providing you with the best possible service and are always
        here to help. If you have any questions or require assistance with your payment, please
        do not hesitate to contact us.</p>

        <p>Thank you for your business. You're much appreciated. Have a great day!</p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

        <div style="font-size: 12px; color: #666;">
            <strong>Kali Speerstra</strong><br>
            PICC Platform<br>
            New York Sales Admin<br>
            171 East 2nd St.<br>
            Huntington Station, NY 11746<br><br>
            <em>"Where innovation meets inhalation, PICC the perfect pre-roll."</em><br>
            IG: @piccplatform<br>
            www.piccnewyork.com | www.piccplatform.com
        </div>
    </div>
    """
    return html


# ---------------------------------------------------------------------------
# Load Data from XLSX
# ---------------------------------------------------------------------------

def load_data_from_xlsx(file_bytes: io.BytesIO | None = None, file_path: str | None = None) -> EmailQueue | None:
    """Load XLSX data and generate an EmailQueue from it.

    Uses data_loader if available, otherwise falls back to demo data.
    """
    if not DATA_LOADER_AVAILABLE:
        st.warning(
            "Data loader module not yet available. Using demo data instead. "
            "The data_loader.py module is being built by another agent."
        )
        return build_demo_queue()

    try:
        source = file_bytes if file_bytes else file_path
        if source is None:
            # Try default path from config
            if CONFIG_AVAILABLE:
                cfg = get_config()
                default_path = PROJECT_ROOT / cfg.data_files.ar_overdue_xlsx
                if default_path.exists():
                    source = str(default_path)
                else:
                    st.error(f"Default XLSX not found at: {default_path}")
                    return None
            else:
                default_path = PROJECT_ROOT / "data" / "NY Account Receivables_Overdue.xlsx"
                if default_path.exists():
                    source = str(default_path)
                else:
                    st.error("No XLSX file provided and default file not found.")
                    return None

        with st.spinner("Loading workbook..."):
            result: LoadResult = load_workbook(source)
            st.session_state.load_result = result

        # Build the email queue from loaded data
        queue = EmailQueue()
        actionable = result.actionable_invoices

        # Group invoices by store
        store_groups: dict[str, list[Invoice]] = defaultdict(list)
        for inv in actionable:
            # Check Do Not Contact list
            if inv.store_name in st.session_state.do_not_contact:
                continue
            store_groups[inv.store_name].append(inv)

        # Use real template engine if available
        engine = _get_template_engine()

        for store_name, invoices in store_groups.items():
            # Resolve contact if possible
            contact_obj = None
            if result.contacts_by_name:
                contact_obj = result.get_contact(store_name)

            if engine:
                draft = engine.render_email(
                    invoices=invoices,
                    contact=contact_obj,
                )
                queue.add(draft)
            else:
                max_days = max(inv.days_past_due for inv in invoices)
                tier = Tier.from_days(max_days)

                to_emails = []
                if contact_obj and contact_obj.has_email:
                    to_emails = contact_obj.all_emails if contact_obj.all_emails else [contact_obj.email]

                cc_list = [
                    "ny.ar@nabis.com",
                    "martinm@piccplatform.com",
                    "mario@piccplatform.com",
                    "laura@piccplatform.com",
                ]

                draft = EmailDraft(
                    to=to_emails,
                    cc=cc_list,
                    subject=(
                        f"PICC - {store_name} - Nabis "
                        f"{'Invoice' if len(invoices) == 1 else 'Invoices'} "
                        f"{' & '.join(inv.invoice_number for inv in invoices)} - "
                        f"{tier.value}"
                    ),
                    body_html=_build_sample_html(store_name, invoices, tier),
                    tier=tier,
                    invoices=invoices,
                    store_name=store_name,
                    contact=contact_obj,
                    status=EmailStatus.PENDING,
                )
                queue.add(draft)

        return queue

    except Exception as e:
        st.error(f"Error loading XLSX: {e}")
        return None


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

def render_sidebar():
    """Render the sidebar with file upload, generate button, filters, and stats."""

    with st.sidebar:
        # Logo / branding
        st.markdown(f"""
        <div style="text-align: center; padding: 0.5rem 0 1rem 0;">
            <div style="font-size: 1.8rem; font-weight: 700; color: {PICC_DARK_GREEN};">
                PICC
            </div>
            <div style="font-size: 0.75rem; color: {PICC_GOLD}; letter-spacing: 1px;">
                AR EMAIL AUTOMATION
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # ---------------------------------------------------------------
        # Data Source
        # ---------------------------------------------------------------
        st.markdown(f"### Upload Data")

        uploaded_file = st.file_uploader(
            "Upload AR Overdue XLSX",
            type=["xlsx"],
            help="Upload the weekly AR overdue spreadsheet exported from Google Sheets.",
            key=f"xlsx_upload_{st.session_state.upload_key}",
        )

        st.markdown("---")

        # Sender name -- who the email appears to come from
        st.markdown("### Sender Name")
        st.session_state.sender_name = st.text_input(
            "Your name (appears in email signature)",
            value=st.session_state.sender_name,
            placeholder="PICC Accounts Receivable",
            help="Leave blank for generic 'PICC Accounts Receivable', or enter your name (e.g. Laura, Kali).",
            key="sidebar_sender_name",
        )

        # Generate button
        st.markdown("")
        generate_clicked = st.button(
            "Generate Emails",
            type="primary",
            use_container_width=True,
            help="Parse the XLSX and generate email drafts for review.",
        )

        if generate_clicked:
            if uploaded_file is not None:
                file_bytes = io.BytesIO(uploaded_file.read())
                queue = load_data_from_xlsx(file_bytes=file_bytes)
            else:
                st.warning("Please upload an XLSX file first.")
                queue = None

            if queue is not None:
                st.session_state.queue = queue
                st.session_state.generated = True
                st.session_state.selected_email_idx = None
                st.success(f"Generated {len(queue)} email drafts!")
                st.rerun()

        # Load demo data button
        if not st.session_state.generated:
            st.markdown("")
            if st.button("Load Demo Data", use_container_width=True,
                         help="Load sample data to explore the interface."):
                st.session_state.queue = build_demo_queue()
                st.session_state.generated = True
                st.success("Demo data loaded!")
                st.rerun()

        st.markdown("---")

        # ---------------------------------------------------------------
        # Filters (only show when we have data)
        # ---------------------------------------------------------------
        if st.session_state.queue is not None:
            st.markdown("### Filters")

            # Tier filter
            all_tiers = [t.value for t in Tier]
            st.session_state.filter_tiers = st.multiselect(
                "Filter by Tier",
                options=all_tiers,
                default=[],
                help="Select tiers to show. Leave empty to show all.",
            )

            # Status filter
            all_statuses = [s.value for s in EmailStatus]
            st.session_state.filter_status = st.multiselect(
                "Filter by Status",
                options=all_statuses,
                default=[],
                help="Select statuses to show. Leave empty to show all.",
            )

            st.markdown("---")

            # ---------------------------------------------------------------
            # Summary Statistics
            # ---------------------------------------------------------------
            st.markdown("### Summary")

            queue: EmailQueue = st.session_state.queue

            # Status counts
            pending_count = len(queue.pending)
            approved_count = len(queue.approved)
            rejected_count = len(queue.rejected)
            sent_count = len(queue.sent)
            total_count = len(queue)

            st.metric("Total Emails", total_count)

            cols = st.columns(2)
            with cols[0]:
                st.metric("Pending", pending_count)
                st.metric("Approved", approved_count)
            with cols[1]:
                st.metric("Rejected", rejected_count)
                st.metric("Sent", sent_count)

            # Total AR
            total_ar = sum(d.total_amount for d in queue.drafts)
            st.metric("Total AR Amount", format_currency(total_ar))

            # Tier breakdown
            st.markdown("**By Tier:**")
            tier_counts: dict[str, dict] = {}
            for d in queue.drafts:
                label = d.tier.value
                if label not in tier_counts:
                    tier_counts[label] = {"count": 0, "amount": 0.0}
                tier_counts[label]["count"] += 1
                tier_counts[label]["amount"] += d.total_amount

            for tier_label in [t.value for t in Tier]:
                if tier_label in tier_counts:
                    data = tier_counts[tier_label]
                    st.markdown(
                        f"- **{tier_label}**: {data['count']} emails "
                        f"({format_currency(data['amount'])})"
                    )

        st.markdown("---")

        # ---------------------------------------------------------------
        # Navigation
        # ---------------------------------------------------------------
        st.markdown("### Navigation")

        nav_options = {
            "queue": "Email Queue",
            "history": "History",
            "dnc": "Do Not Contact",
            "settings": "Settings",
        }

        for key, label in nav_options.items():
            if st.button(
                label,
                use_container_width=True,
                type="primary" if st.session_state.page == key else "secondary",
            ):
                st.session_state.page = key
                st.session_state.selected_email_idx = None
                st.rerun()


# ---------------------------------------------------------------------------
# MAIN: Email Queue Page
# ---------------------------------------------------------------------------

def render_queue_page():
    """Render the email queue list with action buttons."""

    # Header
    st.markdown("""
    <div class="picc-header">
        <h1>AR Email Queue</h1>
        <p>Review, approve, and export AR collection emails</p>
    </div>
    """, unsafe_allow_html=True)

    queue: EmailQueue = st.session_state.queue

    if queue is None or not st.session_state.generated:
        st.info(
            "No emails generated yet. Use the sidebar to upload an XLSX file "
            "and click **Generate Emails**, or click **Load Demo Data** to explore."
        )
        # Show module availability status
        with st.expander("System Status"):
            modules = {
                "Models (src/models.py)": MODELS_AVAILABLE,
                "Config (src/config.py)": CONFIG_AVAILABLE,
                "Data Loader (src/data_loader.py)": DATA_LOADER_AVAILABLE,
                "Tier Classifier (src/tier_classifier.py)": CLASSIFIER_AVAILABLE,
                "Contact Resolver (src/contact_resolver.py)": RESOLVER_AVAILABLE,
                "Template Engine (src/template_engine.py)": TEMPLATE_ENGINE_AVAILABLE,
            }
            for name, available in modules.items():
                icon = "OK" if available else "MISSING"
                st.markdown(f"- **{name}**: {icon}")
        return

    # ---------------------------------------------------------------
    # Summary stat cards
    # ---------------------------------------------------------------
    total_ar = sum(d.total_amount for d in queue.drafts)
    total_invoices = sum(len(d.invoices) for d in queue.drafts)

    cols = st.columns(6)
    stat_data = [
        ("Pending", len(queue.pending), ""),
        ("Approved", len(queue.approved), ""),
        ("Rejected", len(queue.rejected), ""),
        ("Sent", len(queue.sent), ""),
        ("Total Emails", len(queue), ""),
        ("Total AR", format_currency(total_ar), "gold"),
    ]
    for col, (label, value, css_class) in zip(cols, stat_data):
        with col:
            st.markdown(f"""
            <div class="stat-card {css_class}">
                <div class="stat-number">{value}</div>
                <div class="stat-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # Batch Action Buttons
    # ---------------------------------------------------------------
    action_cols = st.columns([1, 1, 1, 1, 1, 1])

    with action_cols[0]:
        if st.button("Approve All Pending", type="primary",
                      disabled=len(queue.pending) == 0):
            count = queue.approve_all()
            st.success(f"Approved {count} emails!")
            st.rerun()

    with action_cols[1]:
        if st.button("Approve Coming Due",
                      disabled=not any(d.status == EmailStatus.PENDING and d.tier == Tier.T0 for d in queue.drafts)):
            count = queue.approve_by_tier(Tier.T0)
            st.success(f"Approved {count} Coming Due emails!")
            st.rerun()

    with action_cols[2]:
        smtp_ready = bool(st.session_state.gmail_app_password) and bool(st.session_state.sender_email)
        send_disabled = len(queue.approved) == 0 or not smtp_ready
        send_help = (
            "Send all approved emails via Gmail"
            if smtp_ready
            else "Set up Gmail App Password in Settings first"
        )
        if st.button(
            "Send via Gmail",
            type="primary",
            disabled=send_disabled,
            help=send_help,
        ):
            _send_approved_emails(queue)

    with action_cols[3]:
        if st.button("Export Approved",
                      disabled=len(queue.approved) == 0):
            _export_approved_emails(queue)

    with action_cols[4]:
        if st.button("Download All (.zip)",
                      disabled=len(queue.approved) == 0):
            _download_all_zip(queue)

    with action_cols[5]:
        if not smtp_ready:
            st.caption("Gmail not configured -- go to Settings")

    # ---------------------------------------------------------------
    # Schedule Send Time Picker
    # ---------------------------------------------------------------
    schedule_cols = st.columns([1, 1, 3])
    with schedule_cols[0]:
        default_time = dt_time(7, 0)  # 7:00 AM PT
        scheduled_time = st.time_input(
            "Schedule send time",
            value=default_time,
            help="Target send time (default: 7:00 AM PT = 10:00 AM ET). Callie schedules for 7 AM Pacific.",
            key="schedule_time_picker",
        )
        st.session_state.schedule_time = scheduled_time.strftime("%H:%M")
        # Apply scheduled time to all drafts in the queue
        if queue is not None:
            for draft in queue.drafts:
                draft.scheduled_send_time = scheduled_time
                draft.scheduled_timezone = st.session_state.get("schedule_timezone", "PT")
    with schedule_cols[1]:
        tz_option = st.selectbox(
            "Timezone",
            options=["PT (Pacific)", "ET (Eastern)", "CT (Central)", "MT (Mountain)"],
            index=0,
            key="schedule_tz_picker",
            help="Callie schedules for 7 AM Pacific = 10 AM Eastern",
        )
        tz_label = tz_option.split(" ")[0]
        st.session_state.schedule_timezone = tz_label
        # Update timezone on drafts
        if queue is not None:
            for draft in queue.drafts:
                draft.scheduled_timezone = tz_label
    with schedule_cols[2]:
        # Compute ET equivalent for display
        et_hour = scheduled_time.hour + 3  # PT -> ET offset
        et_min = scheduled_time.minute
        if et_hour >= 24:
            et_hour -= 24
        et_time_val = dt_time(et_hour, et_min)
        try:
            pt_display = scheduled_time.strftime("%I:%M %p").lstrip("0")
            et_display = et_time_val.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            pt_display = str(scheduled_time)
            et_display = str(et_time_val)

        tz_label = st.session_state.schedule_timezone
        st.markdown(
            f'<div style="background: #e8f5e9; border-left: 4px solid #4caf50; '
            f'padding: 0.75rem 1rem; border-radius: 4px; margin-top: 0.5rem;">'
            f'<strong>Scheduled for: {pt_display} {tz_label}</strong>'
            f'{"  (" + et_display + " ET)" if tz_label == "PT" else ""}<br>'
            f'<span style="font-size: 0.85rem; color: #666;">'
            f'Emails will be sent immediately when you click "Send via Gmail". '
            f'To schedule-send, use Gmail\'s built-in schedule send feature, '
            f'or run this tool at the target time.</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Show send results if any
    if st.session_state.send_results:
        with st.expander("Last Send Results", expanded=True):
            for success, message in st.session_state.send_results:
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("")

    # ---------------------------------------------------------------
    # Email Queue Table
    # ---------------------------------------------------------------
    filtered = get_filtered_drafts()

    if not filtered:
        st.info("No emails match the current filters.")
        return

    st.markdown(f"**Showing {len(filtered)} of {len(queue)} emails**")

    # Column headers
    header_cols = st.columns([0.5, 1.2, 2.5, 1.2, 0.8, 1, 2])
    with header_cols[0]:
        st.markdown("**#**")
    with header_cols[1]:
        st.markdown("**Tier**")
    with header_cols[2]:
        st.markdown("**Store Name**")
    with header_cols[3]:
        st.markdown("**Amount**")
    with header_cols[4]:
        st.markdown("**Days**")
    with header_cols[5]:
        st.markdown("**Status**")
    with header_cols[6]:
        st.markdown("**Actions**")

    st.markdown("---")

    # Email rows
    for idx, draft in filtered:
        flags = get_flags(draft)
        max_days = get_max_days_over(draft)

        row_cols = st.columns([0.5, 1.2, 2.5, 1.2, 0.8, 1, 2])

        with row_cols[0]:
            st.markdown(f"**{idx + 1}**")

        with row_cols[1]:
            st.markdown(tier_badge_html(draft.tier.value), unsafe_allow_html=True)

        with row_cols[2]:
            # Store name with flags and scheduled time
            store_display = f"**{draft.store_name}**"
            if draft.is_multi_invoice:
                store_display += f" ({len(draft.invoices)} invoices)"
            st.markdown(store_display)
            # Show scheduled send time under store name
            if draft.scheduled_send_time is not None:
                sched_display = draft.scheduled_time_display
                if sched_display:
                    st.markdown(
                        f'<span style="font-size: 0.75rem; color: #4caf50;">'
                        f'Send at: {sched_display}</span>',
                        unsafe_allow_html=True,
                    )
            if flags:
                flag_html = " ".join(
                    f'<span class="flag-badge">{f}</span>' for f in flags
                )
                st.markdown(flag_html, unsafe_allow_html=True)

        with row_cols[3]:
            st.markdown(f"**{draft.total_amount_formatted}**")

        with row_cols[4]:
            days_str = f"{max_days}d"
            if max_days < 0:
                st.markdown(f":green[{days_str}]")
            elif max_days >= 50:
                st.markdown(f":red[{days_str}]")
            elif max_days >= 30:
                st.markdown(f":orange[{days_str}]")
            else:
                st.markdown(days_str)

        with row_cols[5]:
            st.markdown(
                status_badge_html(draft.status.value),
                unsafe_allow_html=True,
            )

        with row_cols[6]:
            btn_cols = st.columns(3)

            with btn_cols[0]:
                if draft.status == EmailStatus.PENDING:
                    if st.button("Approve", key=f"approve_{idx}",
                                 type="primary"):
                        draft.approve()
                        st.rerun()

            with btn_cols[1]:
                if st.button("Preview", key=f"preview_{idx}"):
                    st.session_state.selected_email_idx = idx
                    st.session_state.page = "preview"
                    st.rerun()

            with btn_cols[2]:
                if draft.status == EmailStatus.PENDING:
                    if st.button("Reject", key=f"reject_{idx}"):
                        draft.reject("Rejected from queue")
                        st.rerun()


# ---------------------------------------------------------------------------
# MAIN: Email Preview Page
# ---------------------------------------------------------------------------

def render_preview_page():
    """Render the email preview/detail view."""

    queue: EmailQueue = st.session_state.queue
    idx = st.session_state.selected_email_idx

    if queue is None or idx is None or idx >= len(queue.drafts):
        st.session_state.page = "queue"
        st.rerun()
        return

    draft = queue.drafts[idx]
    flags = get_flags(draft)
    max_days = get_max_days_over(draft)

    # Back button
    if st.button("Back to Queue"):
        st.session_state.page = "queue"
        st.session_state.selected_email_idx = None
        st.rerun()

    # Header
    st.markdown("""
    <div class="picc-header">
        <h1>Email Preview</h1>
        <p>Review the email details before approving or rejecting</p>
    </div>
    """, unsafe_allow_html=True)

    # Status bar
    info_cols = st.columns(5)
    with info_cols[0]:
        st.markdown(f"**Status:** {status_badge_html(draft.status.value)}", unsafe_allow_html=True)
    with info_cols[1]:
        st.markdown(f"**Tier:** {tier_badge_html(draft.tier.value)}", unsafe_allow_html=True)
    with info_cols[2]:
        st.markdown(f"**Days Past Due:** {max_days}")
    with info_cols[3]:
        # Scheduled send time
        sched_display = draft.scheduled_time_display if draft.scheduled_send_time else ""
        if sched_display:
            st.markdown(
                f'**Send at:** <span style="color: #4caf50; font-weight: 600;">'
                f'{sched_display}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("**Send at:** Not scheduled")
    with info_cols[4]:
        if flags:
            flag_html = " ".join(f'<span class="flag-badge">{f}</span>' for f in flags)
            st.markdown(f"**Flags:** {flag_html}", unsafe_allow_html=True)
        else:
            st.markdown("**Flags:** None")

    st.markdown("---")

    # ---------------------------------------------------------------
    # Email Headers
    # ---------------------------------------------------------------
    st.markdown("#### Email Headers")

    header_container = st.container()
    with header_container:
        h_cols = st.columns([1, 5])

        with h_cols[0]:
            st.markdown("**From:**")
            st.markdown("**To:**")
            st.markdown("**CC:**")
            st.markdown("**BCC:**")
            st.markdown("**Subject:**")
            st.markdown("**Attach:**")
            st.markdown("**Send at:**")

        with h_cols[1]:
            sender_display = st.session_state.sender_name or "PICC Accounts Receivable"
            st.markdown(f"{sender_display} <{st.session_state.sender_email}>")
            to_str = ", ".join(draft.to) if draft.to else "(no contact found)"
            st.markdown(to_str)
            cc_str = ", ".join(draft.cc) if draft.cc else "(none)"
            st.markdown(cc_str)
            bcc_list = getattr(draft, "bcc", []) or []
            bcc_str = ", ".join(bcc_list) if bcc_list else "(none)"
            st.markdown(bcc_str)
            st.markdown(f"**{draft.subject}**")
            st.markdown("Nabis ACH Payment Form.pdf")
            # Scheduled send time
            sched_display = draft.scheduled_time_display if draft.scheduled_send_time else "Not scheduled"
            st.markdown(f":green[{sched_display}]" if draft.scheduled_send_time else sched_display)

    # ---------------------------------------------------------------
    # Invoice Details (collapsible, above the email body)
    # ---------------------------------------------------------------
    inv_label = (
        f"Invoice Details -- {len(draft.invoices)} invoice"
        f"{'s' if len(draft.invoices) != 1 else ''}, "
        f"{draft.total_amount_formatted}"
    )
    with st.expander(inv_label, expanded=False):
        for inv in draft.invoices:
            inv_cols = st.columns(5)
            with inv_cols[0]:
                st.metric("Order #", inv.invoice_number)
            with inv_cols[1]:
                st.metric("Amount", inv.amount_formatted)
            with inv_cols[2]:
                st.metric("Days Over", inv.days_past_due)
            with inv_cols[3]:
                st.metric("Due Date", inv.due_date_formatted or "N/A")
            with inv_cols[4]:
                st.metric("Rep", inv.sales_rep or "N/A")

            if inv.notes:
                st.info(f"Notes: {inv.notes}")

    st.markdown("---")

    # ---------------------------------------------------------------
    # Email Body (rendered in iframe for Gmail-accurate preview)
    # ---------------------------------------------------------------
    st.markdown("#### Email Body")

    if draft.body_html:
        import streamlit.components.v1 as components

        # Email window chrome: looks like a real email client
        st.markdown("""
        <div style="
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.10);
            margin: 0.5rem 0 1rem 0;
        ">
            <div style="
                background: #f6f6f6;
                border-bottom: 1px solid #e0e0e0;
                padding: 6px 14px;
                font-size: 0.78rem;
                color: #666;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            ">Email Preview -- as seen in Gmail</div>
        """, unsafe_allow_html=True)

        # Dynamic height: estimate from content length, clamp to [400, 1200]
        iframe_height = min(max(400, len(draft.body_html) // 2), 1200)
        components.html(draft.body_html, height=iframe_height, scrolling=True)

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No HTML body generated yet. The template engine module is being built by another agent.")

    st.markdown("---")

    # ---------------------------------------------------------------
    # Action Buttons
    # ---------------------------------------------------------------
    st.markdown("#### Actions")

    action_cols = st.columns([1, 1, 1, 1])

    with action_cols[0]:
        if draft.status == EmailStatus.PENDING:
            if st.button("APPROVE", type="primary", use_container_width=True):
                draft.approve()
                st.success("Email approved!")
                _advance_to_next_pending(idx)
                st.rerun()

    with action_cols[1]:
        # EDIT is always available regardless of status
        if st.button("EDIT", use_container_width=True):
            st.session_state[f"editing_{idx}"] = True
            st.rerun()

    with action_cols[2]:
        if draft.status == EmailStatus.PENDING:
            reject_reason = st.text_input(
                "Rejection reason",
                placeholder="Optional: why are you rejecting this?",
                key=f"reject_reason_{idx}",
            )
            if st.button("REJECT", use_container_width=True):
                draft.reject(reject_reason or "No reason provided")
                st.warning("Email rejected.")
                _advance_to_next_pending(idx)
                st.rerun()

    with action_cols[3]:
        if st.button("NEXT", use_container_width=True):
            _advance_to_next(idx)
            st.rerun()

    # ---------------------------------------------------------------
    # Edit Mode (Tabbed: Quick Edit | Edit HTML)
    # ---------------------------------------------------------------
    if st.session_state.get(f"editing_{idx}", False):
        st.markdown("---")
        st.markdown("#### Edit Email")

        quick_tab, html_tab = st.tabs(["Quick Edit", "Edit HTML"])

        # --- Quick Edit tab: simple fields, no HTML exposure ---
        with quick_tab:
            st.caption("Fix recipients, subject, or re-generate the email body from the template.")

            new_to_q = st.text_input(
                "To (comma-separated)",
                value=", ".join(draft.to),
                key=f"edit_to_q_{idx}",
                help="Recipient email addresses, separated by commas",
            )
            new_cc_q = st.text_input(
                "CC (comma-separated)",
                value=", ".join(draft.cc),
                key=f"edit_cc_q_{idx}",
                help="CC email addresses, separated by commas",
            )
            new_bcc_q = st.text_input(
                "BCC (comma-separated)",
                value=", ".join(getattr(draft, "bcc", []) or []),
                key=f"edit_bcc_q_{idx}",
                help="BCC email addresses, separated by commas",
            )
            new_subject_q = st.text_input(
                "Subject",
                value=draft.subject,
                key=f"edit_subject_q_{idx}",
            )

            btn_cols_q = st.columns(3)
            with btn_cols_q[0]:
                if st.button("Save Changes", type="primary", key=f"save_q_{idx}"):
                    draft.to = [e.strip() for e in new_to_q.split(",") if e.strip()]
                    draft.cc = [e.strip() for e in new_cc_q.split(",") if e.strip()]
                    draft.bcc = [e.strip() for e in new_bcc_q.split(",") if e.strip()]
                    draft.subject = new_subject_q
                    st.session_state[f"editing_{idx}"] = False
                    st.success("Changes saved!")
                    st.rerun()
            with btn_cols_q[1]:
                if st.button("Cancel", key=f"cancel_q_{idx}"):
                    st.session_state[f"editing_{idx}"] = False
                    st.rerun()
            with btn_cols_q[2]:
                if TEMPLATE_ENGINE_AVAILABLE and st.button(
                    "Re-generate from template",
                    key=f"regen_{idx}",
                    help="Re-render the email body from the original template. "
                         "Keeps your To address but regenerates body, subject, and CC.",
                ):
                    engine = _get_template_engine()
                    if engine:
                        saved_to = list(draft.to)  # preserve manual TO edits
                        new_draft = engine.render_email(
                            invoices=draft.invoices,
                            contact=draft.contact,
                        )
                        draft.body_html = new_draft.body_html
                        draft.subject = new_draft.subject
                        draft.cc = new_draft.cc
                        if not saved_to:
                            draft.to = new_draft.to
                        else:
                            draft.to = saved_to
                        st.session_state[f"editing_{idx}"] = False
                        st.success("Email re-generated from template!")
                        st.rerun()

        # --- Edit HTML tab: raw body for power users ---
        with html_tab:
            st.caption(
                "Advanced -- you are editing the raw HTML that gets sent to Gmail. "
                "Incorrect changes may break the email formatting."
            )

            new_to_h = st.text_input(
                "To (comma-separated)",
                value=", ".join(draft.to),
                key=f"edit_to_h_{idx}",
            )
            new_cc_h = st.text_input(
                "CC (comma-separated)",
                value=", ".join(draft.cc),
                key=f"edit_cc_h_{idx}",
            )
            new_bcc_h = st.text_input(
                "BCC (comma-separated)",
                value=", ".join(getattr(draft, "bcc", []) or []),
                key=f"edit_bcc_h_{idx}",
                help="BCC email addresses, separated by commas",
            )
            new_subject_h = st.text_input(
                "Subject",
                value=draft.subject,
                key=f"edit_subject_h_{idx}",
            )
            new_body_h = st.text_area(
                "HTML Body",
                value=draft.body_html,
                height=400,
                key=f"edit_body_h_{idx}",
            )

            btn_cols_h = st.columns(2)
            with btn_cols_h[0]:
                if st.button("Save Changes", type="primary", key=f"save_h_{idx}"):
                    draft.to = [e.strip() for e in new_to_h.split(",") if e.strip()]
                    draft.cc = [e.strip() for e in new_cc_h.split(",") if e.strip()]
                    draft.bcc = [e.strip() for e in new_bcc_h.split(",") if e.strip()]
                    draft.subject = new_subject_h
                    draft.body_html = new_body_h
                    st.session_state[f"editing_{idx}"] = False
                    st.success("Changes saved!")
                    st.rerun()
            with btn_cols_h[1]:
                if st.button("Cancel", key=f"cancel_h_{idx}"):
                    st.session_state[f"editing_{idx}"] = False
                    st.rerun()

    # ---------------------------------------------------------------
    # Navigation: Previous / Next
    # ---------------------------------------------------------------
    st.markdown("---")
    nav_cols = st.columns([1, 4, 1])
    with nav_cols[0]:
        if idx > 0:
            if st.button("Previous"):
                st.session_state.selected_email_idx = idx - 1
                st.rerun()
    with nav_cols[2]:
        if idx < len(queue.drafts) - 1:
            if st.button("Next"):
                st.session_state.selected_email_idx = idx + 1
                st.rerun()


def _advance_to_next_pending(current_idx: int):
    """Move to the next pending email after an action."""
    queue: EmailQueue = st.session_state.queue
    for i in range(current_idx + 1, len(queue.drafts)):
        if queue.drafts[i].status == EmailStatus.PENDING:
            st.session_state.selected_email_idx = i
            return
    # Wrap around
    for i in range(0, current_idx):
        if queue.drafts[i].status == EmailStatus.PENDING:
            st.session_state.selected_email_idx = i
            return
    # No more pending -- go back to queue
    st.session_state.page = "queue"
    st.session_state.selected_email_idx = None


def _advance_to_next(current_idx: int):
    """Move to the next email regardless of status."""
    queue: EmailQueue = st.session_state.queue
    if current_idx < len(queue.drafts) - 1:
        st.session_state.selected_email_idx = current_idx + 1
    else:
        st.session_state.page = "queue"
        st.session_state.selected_email_idx = None


# ---------------------------------------------------------------------------
# MAIN: Export Functions
# ---------------------------------------------------------------------------

def _export_approved_emails(queue: EmailQueue):
    """Export all approved emails as .eml files to the output directory."""
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for draft in queue.approved:
        eml_content = generate_eml(draft)
        safe_name = draft.store_name.replace(" ", "_").replace("/", "-")
        filename = f"{safe_name}_{draft.invoice_numbers[0] if draft.invoice_numbers else 'unknown'}.eml"
        filepath = output_dir / filename
        filepath.write_text(eml_content, encoding="utf-8")
        count += 1

        # Add to history
        st.session_state.history.append({
            "store_name": draft.store_name,
            "tier": draft.tier.value,
            "amount": draft.total_amount_formatted,
            "invoices": ", ".join(draft.invoice_numbers),
            "to": ", ".join(draft.to),
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "filename": filename,
        })

    st.success(f"Exported {count} .eml files to: {output_dir}")

    # Generate summary report
    _generate_summary_report(queue, output_dir)


def _download_all_zip(queue: EmailQueue):
    """Create a zip download of all approved .eml files."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for draft in queue.approved:
            eml_content = generate_eml(draft)
            safe_name = draft.store_name.replace(" ", "_").replace("/", "-")
            filename = f"{safe_name}_{draft.invoice_numbers[0] if draft.invoice_numbers else 'unknown'}.eml"
            zf.writestr(filename, eml_content)

    zip_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        label=f"Download {len(queue.approved)} emails (.zip)",
        data=zip_buffer,
        file_name=f"ar_emails_{timestamp}.zip",
        mime="application/zip",
    )


def _send_approved_emails(queue: EmailQueue):
    """Send all approved emails via Gmail SMTP, with progress bar."""
    sender = st.session_state.sender_email
    password = st.session_state.gmail_app_password

    if not sender or not password:
        st.error("Gmail not configured. Go to Settings and enter your App Password.")
        return

    approved = queue.approved
    if not approved:
        st.warning("No approved emails to send.")
        return

    results: list[tuple[bool, str]] = []
    progress_bar = st.progress(0, text="Sending emails...")

    for i, draft in enumerate(approved):
        progress_bar.progress(
            (i + 1) / len(approved),
            text=f"Sending {i + 1}/{len(approved)}: {draft.store_name}...",
        )
        success, message = send_email_smtp(draft, sender, password)
        results.append((success, message))

        if success:
            draft.status = EmailStatus.SENT
            # Add to history
            history_entry = {
                "store_name": draft.store_name,
                "tier": draft.tier.value,
                "amount": draft.total_amount_formatted,
                "invoices": ", ".join(draft.invoice_numbers),
                "to": ", ".join(draft.to),
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "filename": "(sent via Gmail)",
                "method": "gmail_smtp",
            }
            if draft.scheduled_send_time is not None:
                history_entry["scheduled_time"] = draft.scheduled_time_display
            st.session_state.history.append(history_entry)

    progress_bar.empty()

    # Store results for display
    st.session_state.send_results = results

    sent_count = sum(1 for s, _ in results if s)
    failed_count = len(results) - sent_count

    if failed_count == 0:
        st.success(f"All {sent_count} emails sent successfully via Gmail!")
        st.balloons()
    elif sent_count == 0:
        st.error(f"All {failed_count} emails failed to send. Check Settings.")
    else:
        st.warning(f"Sent {sent_count}, failed {failed_count}. See details below.")

    st.rerun()


def _generate_summary_report(queue: EmailQueue, output_dir: Path):
    """Write a summary report of the current batch."""
    report_lines = [
        "AR Email Automation -- Export Summary",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        f"Total Drafts:   {len(queue)}",
        f"Approved:       {len(queue.approved)}",
        f"Rejected:       {len(queue.rejected)}",
        f"Pending:        {len(queue.pending)}",
        f"Total AR:       {format_currency(sum(d.total_amount for d in queue.drafts))}",
        f"Approved AR:    {format_currency(sum(d.total_amount for d in queue.approved))}",
        "",
        "-" * 60,
        "APPROVED EMAILS:",
        "-" * 60,
    ]

    for d in queue.approved:
        report_lines.append(
            f"  {d.store_name:<35s}  {d.tier.value:<22s}  "
            f"{d.total_amount_formatted:>12s}  "
            f"Inv: {', '.join(d.invoice_numbers)}"
        )

    if queue.rejected:
        report_lines.extend([
            "",
            "-" * 60,
            "REJECTED EMAILS:",
            "-" * 60,
        ])
        for d in queue.rejected:
            report_lines.append(
                f"  {d.store_name:<35s}  {d.tier.value:<22s}  "
                f"Reason: {d.rejection_reason}"
            )

    report_path = output_dir / "export_summary.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# MAIN: History Page
# ---------------------------------------------------------------------------

def render_history_page():
    """Render the history tab showing previously exported emails."""

    st.markdown("""
    <div class="picc-header">
        <h1>Email History</h1>
        <p>Previously exported AR collection emails</p>
    </div>
    """, unsafe_allow_html=True)

    history = st.session_state.history

    if not history:
        st.info(
            "No emails have been exported yet. "
            "Approve emails from the queue and click **Export Approved** to see them here."
        )
        return

    st.markdown(f"**{len(history)} emails exported this session**")

    # Summary table
    for i, entry in enumerate(reversed(history)):
        cols = st.columns([2, 1.5, 1, 2, 1.5])
        with cols[0]:
            st.markdown(f"**{entry['store_name']}**")
        with cols[1]:
            st.markdown(tier_badge_html(entry["tier"]), unsafe_allow_html=True)
        with cols[2]:
            st.markdown(entry["amount"])
        with cols[3]:
            st.markdown(f"To: {entry['to']}")
        with cols[4]:
            st.markdown(f"_{entry['exported_at']}_")

    # Download history as CSV
    st.markdown("---")
    if st.button("Download History as CSV"):
        import csv
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=history[0].keys())
        writer.writeheader()
        writer.writerows(history)
        st.download_button(
            "Download CSV",
            csv_buffer.getvalue(),
            file_name=f"ar_email_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# MAIN: Do Not Contact Page
# ---------------------------------------------------------------------------

def render_dnc_page():
    """Render the Do Not Contact list management page."""

    st.markdown("""
    <div class="picc-header">
        <h1>Do Not Contact List</h1>
        <p>Manage stores that should be excluded from AR email outreach</p>
    </div>
    """, unsafe_allow_html=True)

    dnc_list = st.session_state.do_not_contact

    # Add new entry
    st.markdown("#### Add Store to Do Not Contact")
    add_cols = st.columns([3, 1])
    with add_cols[0]:
        new_store = st.text_input(
            "Store name",
            placeholder="Enter the exact store name to exclude...",
            label_visibility="collapsed",
        )
    with add_cols[1]:
        if st.button("Add", type="primary", use_container_width=True):
            if new_store and new_store.strip():
                if new_store.strip() not in dnc_list:
                    dnc_list.append(new_store.strip())
                    st.success(f"Added '{new_store.strip()}' to Do Not Contact list.")
                    st.rerun()
                else:
                    st.warning("Store already in the list.")
            else:
                st.warning("Please enter a store name.")

    st.markdown("---")

    # Current list
    st.markdown(f"#### Current List ({len(dnc_list)} stores)")

    if not dnc_list:
        st.info("No stores on the Do Not Contact list.")
    else:
        for i, store in enumerate(dnc_list):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"**{store}**")
            with cols[1]:
                if st.button("Remove", key=f"dnc_remove_{i}"):
                    dnc_list.remove(store)
                    st.rerun()


# ---------------------------------------------------------------------------
# MAIN: Settings Page
# ---------------------------------------------------------------------------

def render_settings_page():
    """Render the settings configuration page."""

    st.markdown("""
    <div class="picc-header">
        <h1>Settings</h1>
        <p>Configure sender info, CC rules, and system settings</p>
    </div>
    """, unsafe_allow_html=True)

    # Load current config
    if CONFIG_AVAILABLE:
        cfg = get_config()
    else:
        cfg = None

    # ---------------------------------------------------------------
    # Sender Configuration
    # ---------------------------------------------------------------
    st.markdown("#### Sender Configuration")

    sender_cols = st.columns(2)
    with sender_cols[0]:
        settings_sender_name = st.text_input(
            "Sender Name",
            value=st.session_state.sender_name,
            placeholder="PICC Accounts Receivable",
            help="Leave blank for generic 'PICC Accounts Receivable'. Also editable in the sidebar.",
            key="settings_sender_name",
        )
        if settings_sender_name != st.session_state.sender_name:
            st.session_state.sender_name = settings_sender_name
        sender_email = st.text_input(
            "Sender Email",
            value=st.session_state.sender_email,
            key="settings_sender_email",
        )
        if sender_email != st.session_state.sender_email:
            st.session_state.sender_email = sender_email
    with sender_cols[1]:
        sender_title = st.text_input(
            "Sender Title",
            value=cfg.sender.title if cfg else "Accounts Receivable Department",
        )
        sender_company = st.text_input(
            "Company",
            value=cfg.sender.company if cfg else "PICC Platform",
        )

    st.markdown("---")

    # ---------------------------------------------------------------
    # Always CC Recipients
    # ---------------------------------------------------------------
    st.markdown("#### Always CC Recipients")

    # Use saved custom CC if available, otherwise config defaults
    if st.session_state.get("custom_cc") is not None:
        current_cc = st.session_state["custom_cc"]
    elif cfg:
        current_cc = cfg.cc_rules.base_cc
    else:
        current_cc = [
            "ny.ar@nabis.com",
            "martinm@piccplatform.com",
            "mario@piccplatform.com",
            "laura@piccplatform.com",
        ]

    cc_text = st.text_area(
        "CC List (one email per line)",
        value="\n".join(current_cc),
        height=120,
    )

    st.markdown("---")

    # ---------------------------------------------------------------
    # Tier Boundaries
    # ---------------------------------------------------------------
    st.markdown("#### Tier Boundaries (Days Past Due)")

    tier_label_options = ["Coming Due", "Overdue", "30+ Days Past Due"]

    if cfg:
        for tier_key, tier_cfg in cfg.tiers.items():
            t_cols = st.columns([1, 1, 1, 2])
            with t_cols[0]:
                st.text_input(
                    "Tier",
                    value=tier_key,
                    disabled=True,
                    key=f"tier_name_{tier_key}",
                )
            with t_cols[1]:
                st.number_input(
                    "Min Days",
                    value=tier_cfg.min_days,
                    key=f"tier_min_{tier_key}",
                )
            with t_cols[2]:
                st.number_input(
                    "Max Days",
                    value=tier_cfg.max_days,
                    key=f"tier_max_{tier_key}",
                )
            with t_cols[3]:
                # Use dropdown instead of text input for tier labels
                current_label = tier_cfg.label
                label_idx = (
                    tier_label_options.index(current_label)
                    if current_label in tier_label_options
                    else 0
                )
                st.selectbox(
                    "Label",
                    options=tier_label_options,
                    index=label_idx,
                    key=f"tier_label_{tier_key}",
                )
    else:
        st.info("Config module not loaded. Default tier boundaries apply.")

    st.markdown("---")

    # ---------------------------------------------------------------
    # Save Settings Button
    # ---------------------------------------------------------------
    save_cols = st.columns([1, 3])
    with save_cols[0]:
        if st.button("Save Settings", type="primary", use_container_width=True):
            # Persist CC list
            parsed_cc = [e.strip() for e in cc_text.split("\n") if e.strip()]
            st.session_state["custom_cc"] = parsed_cc

            # Build settings dict
            settings_to_save = {
                "sender_name": st.session_state.sender_name,
                "sender_email": st.session_state.sender_email,
                "custom_cc": parsed_cc,
                "schedule_time": st.session_state.get("schedule_time", "07:00"),
                "schedule_timezone": st.session_state.get("schedule_timezone", "PT"),
            }

            if _save_settings(settings_to_save):
                st.success("Settings saved to disk! They will persist across sessions.")
            else:
                st.error("Failed to save settings to disk. Settings are saved for this session only.")
    with save_cols[1]:
        st.caption(
            "Saves sender name, sender email, CC list, and schedule preferences "
            "to data/settings.json so they persist across sessions."
        )

    st.markdown("---")

    # ---------------------------------------------------------------
    # Gmail SMTP Configuration
    # ---------------------------------------------------------------
    st.markdown("#### Gmail Send Configuration")

    st.info(
        "To send emails directly from this tool, you need a **Gmail App Password**. "
        "This is NOT your regular Gmail password -- it's a special 16-character code "
        "you generate from your Google Account security settings."
    )

    gmail_cols = st.columns([2, 1])
    with gmail_cols[0]:
        app_password = st.text_input(
            "Gmail App Password",
            value=st.session_state.gmail_app_password,
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
            help="Generate at: myaccount.google.com/apppasswords",
            key="settings_app_password",
        )
        if app_password != st.session_state.gmail_app_password:
            # Strip spaces from pasted app passwords (Google formats as "xxxx xxxx xxxx xxxx")
            st.session_state.gmail_app_password = app_password.replace(" ", "")

    with gmail_cols[1]:
        st.markdown("")  # spacing
        if st.session_state.gmail_app_password:
            # Test connection button
            if st.button("Test Connection"):
                with st.spinner("Testing Gmail connection..."):
                    try:
                        context = ssl.create_default_context()
                        with smtplib.SMTP("smtp.gmail.com", 587) as server:
                            server.starttls(context=context)
                            server.login(
                                st.session_state.sender_email,
                                st.session_state.gmail_app_password,
                            )
                        st.session_state.smtp_configured = True
                        st.success("Connected! Gmail is ready to send.")
                    except smtplib.SMTPAuthenticationError:
                        st.session_state.smtp_configured = False
                        st.error("Authentication failed. Check email and App Password.")
                    except Exception as e:
                        st.session_state.smtp_configured = False
                        st.error(f"Connection failed: {e}")

    # Status indicator
    if st.session_state.gmail_app_password:
        st.markdown(
            f"**Status:** Sending from **{st.session_state.sender_email}** via Gmail SMTP"
        )
    else:
        st.markdown("**Status:** Not configured -- emails can only be exported as .eml files")

    # Setup instructions
    with st.expander("How to get a Gmail App Password"):
        st.markdown("""
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Make sure **2-Step Verification** is turned ON
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** as the app, **Windows Computer** as the device
5. Click **Generate**
6. Copy the 16-character password and paste it above
7. Click **Test Connection** to verify it works
        """)

    st.markdown("---")

    # ---------------------------------------------------------------
    # Module Status
    # ---------------------------------------------------------------
    st.markdown("#### System Modules")

    modules = {
        "Models (src/models.py)": MODELS_AVAILABLE,
        "Config (src/config.py)": CONFIG_AVAILABLE,
        "Data Loader (src/data_loader.py)": DATA_LOADER_AVAILABLE,
        "Tier Classifier (src/tier_classifier.py)": CLASSIFIER_AVAILABLE,
        "Contact Resolver (src/contact_resolver.py)": RESOLVER_AVAILABLE,
        "Template Engine (src/template_engine.py)": TEMPLATE_ENGINE_AVAILABLE,
    }

    for name, available in modules.items():
        status = "Available" if available else "Not loaded"
        color = "green" if available else "red"
        st.markdown(f"- :{color}[{status}] {name}")


# ---------------------------------------------------------------------------
# MAIN: Router
# ---------------------------------------------------------------------------

def main():
    """Main application entry point -- routes to the active page."""

    # Check that models are available (minimum requirement)
    if not MODELS_AVAILABLE:
        st.error(
            f"Cannot start: the models module (src/models.py) failed to load.\n\n"
            f"Error: {_models_error}\n\n"
            f"Make sure you are running from the ar-email-automation/ directory."
        )
        return

    # Render sidebar (always visible)
    render_sidebar()

    # Route to active page
    page = st.session_state.page

    if page == "preview" and st.session_state.selected_email_idx is not None:
        render_preview_page()
    elif page == "history":
        render_history_page()
    elif page == "dnc":
        render_dnc_page()
    elif page == "settings":
        render_settings_page()
    else:
        render_queue_page()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
