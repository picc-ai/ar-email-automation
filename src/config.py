"""
AR Email Automation -- Configuration Module

Centralizes all configuration for the AR email automation system.
Loads defaults from dataclasses, then overlays any overrides from config.yaml.

Usage:
    from config import get_config
    cfg = get_config()                         # loads config.yaml if present
    cfg = get_config("path/to/custom.yaml")    # loads a specific file
    print(cfg.sender.email)                    # j.smith@piccplatform.com
    print(cfg.tiers["T3"].label)               # "30+ Days Past Due"
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Path constants -- everything relative to the project root
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # src/
PROJECT_ROOT = _THIS_DIR.parent                       # ar-email-automation/
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


# ===================================================================
# 1. Tier Boundaries
# ===================================================================

@dataclass
class TierConfig:
    """Single tier definition: day-range, label, subject tag."""
    name: str
    min_days: int
    max_days: int
    label: str                      # appears in subject line
    template_file: str              # HTML file name under templates/
    sender_override: Optional[str] = None   # if tier needs a different sender


DEFAULT_TIERS: dict[str, TierConfig] = {
    "T1": TierConfig(
        name="T1",
        min_days=-7,
        max_days=0,
        label="Coming Due",
        template_file="coming_due.html",
    ),
    "T2": TierConfig(
        name="T2",
        min_days=1,
        max_days=29,
        label="Overdue",
        template_file="overdue.html",
    ),
    "T3": TierConfig(
        name="T3",
        min_days=30,
        max_days=999,
        label="30+ Days Past Due",
        template_file="past_due_30.html",
    ),
}


# ===================================================================
# 2. T2 time-relative language phrases
# ===================================================================

T2_TIME_PHRASES: dict[tuple[int, int], str] = {
    (4, 10):  "your invoice is now past due",
    (11, 17): "your invoice is nearing two weeks past due",
    (18, 24): "your invoice is over two weeks past due",
    (25, 29): "your invoice is over three weeks past due",
}


def get_t2_time_phrase(days_past_due: int) -> str:
    """Return the time-relative phrase for a T2 invoice."""
    for (lo, hi), phrase in T2_TIME_PHRASES.items():
        if lo <= days_past_due <= hi:
            return phrase
    return "your invoice is past due"


# ===================================================================
# 3. CC / BCC Rules
# ===================================================================

@dataclass
class CCRules:
    """CC recipients added per tier.  All tiers include base_cc.
    The sales rep for the retailer is always added from the contact sheet.
    """
    # Always CC'd on every outbound AR email, regardless of tier.
    base_cc: list[str] = field(default_factory=lambda: [
        "ny.ar@nabis.com",
        "martinm@piccplatform.com",
        "mario@piccplatform.com",
        "laura@piccplatform.com",
    ])

    # Per-tier additional CC recipients (beyond base + sales rep).
    # All 3 tiers use the same base CC list + sales rep. No escalation.
    tier_extra_cc: dict[str, list[str]] = field(default_factory=lambda: {
        "T1": [],
        "T2": [],
        "T3": [],
    })

    # BCC is not used in the current workflow.
    bcc: list[str] = field(default_factory=list)


# ===================================================================
# 4. Attachment Rules
# ===================================================================

@dataclass
class AttachmentRules:
    """Which files to attach at each tier."""
    # The ACH form is attached to ALL initial outreach emails.
    ach_form_path: str = "data/Nabis_ACH_Payment_Form.pdf"

    # Per-tier attachment rules.  True = always attach, False = never,
    # "flag" = flag for human review before attaching.
    tier_attachments: dict[str, dict[str, object]] = field(default_factory=lambda: {
        "T1": {"ach_form": True, "bol": False, "invoice_pdf": False},
        "T2": {"ach_form": True, "bol": False, "invoice_pdf": False},
        "T3": {"ach_form": True, "bol": False, "invoice_pdf": False},
    })


# ===================================================================
# 5. SMTP Settings (placeholder -- will use Gmail API in production)
# ===================================================================

@dataclass
class SMTPSettings:
    """SMTP configuration.  Not used in Phase 1 (Gmail API), but included
    for future flexibility or testing with a local mail relay."""
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    username: str = ""        # set via env var SMTP_USERNAME
    password: str = ""        # set via env var SMTP_PASSWORD

    def __post_init__(self):
        self.username = self.username or os.environ.get("SMTP_USERNAME", "")
        self.password = self.password or os.environ.get("SMTP_PASSWORD", "")


# ===================================================================
# 6. Template Paths
# ===================================================================

@dataclass
class TemplatePaths:
    """Where the HTML Jinja2 templates live."""
    template_dir: str = "templates"

    @property
    def resolved_dir(self) -> Path:
        p = Path(self.template_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


# ===================================================================
# 7. Sender Info
# ===================================================================

@dataclass
class SenderInfo:
    """Default FROM identity for outgoing AR emails."""
    name: str = "PICC Accounts Receivable"
    email: str = "laura@piccplatform.com"
    title: str = "Accounts Receivable Department"
    company: str = "PICC Platform"


@dataclass
class EscalationSender:
    """Sender used when management escalation kicks in (unused in 3-tier system)."""
    name: str = "Mario Serrano"
    email: str = "mario@piccplatform.com"
    title: str = "Regional Account Manager"
    phone: str = "702.592.5673"
    company: str = "PICC Platform"


# ===================================================================
# 8. Signature Block
# ===================================================================

@dataclass
class SignatureBlock:
    """Email signature appended to every outgoing email."""
    sender_name: str = "PICC Accounts Receivable"
    company: str = "PICC Platform"
    title: str = "Accounts Receivable Department"
    address_line1: str = "171 East 2nd St."
    address_line2: str = "Huntington Station, NY 11746"
    tagline: str = "Where innovation meets inhalation, PICC the perfect pre-roll."
    instagram: str = "@piccplatform"
    website_wholesale: str = "www.piccnewyork.com"
    website_corporate: str = "www.piccplatform.com"

    confidentiality_notice: str = (
        "Email Confidentiality Notice: This e-mail and any files transmitted "
        "with it are confidential and are intended solely for the use of the "
        "individual or entity to which they are addressed. The authorized "
        "recipient of this information is prohibited from disclosing this "
        "information to any other party unless authorized. If you are not the "
        "intended recipient of this e-mail please note that you have received "
        "this e-mail in error and any use, dissemination, forwarding, printing "
        "or copying of this e-mail is strictly prohibited. If you have received "
        "this e-mail in error, please immediately contact the sender of this "
        "message."
    )


# ===================================================================
# 9. Data File Paths
# ===================================================================

@dataclass
class DataFilePaths:
    """Paths to input data files (relative to project root unless absolute)."""
    ar_overdue_xlsx: str = "data/NY Account Receivables_Overdue.xlsx"
    emails_dir: str = "data/emails"
    ach_form_pdf: str = "data/Nabis_ACH_Payment_Form.pdf"

    # Future: Google Sheet IDs or Nabis API endpoints
    nabis_api_base_url: str = ""
    google_sheet_id: str = ""

    def resolve(self, rel_path: str) -> Path:
        p = Path(rel_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


# ===================================================================
# 10. Output Directory
# ===================================================================

@dataclass
class OutputConfig:
    """Where generated email drafts are written before sending."""
    output_dir: str = "output/drafts"
    sent_log_dir: str = "output/sent"
    log_file: str = "output/ar_automation.log"

    def ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        for d in [self.output_dir, self.sent_log_dir]:
            path = Path(d) if Path(d).is_absolute() else PROJECT_ROOT / d
            path.mkdir(parents=True, exist_ok=True)
        log_path = Path(self.log_file) if Path(self.log_file).is_absolute() else PROJECT_ROOT / self.log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)


# ===================================================================
# 11. Fuzzy Match Threshold
# ===================================================================

@dataclass
class MatchingConfig:
    """Settings for fuzzy matching retailer names / contacts."""
    fuzzy_threshold: int = 82              # 0-100, fuzzywuzzy ratio score
    exact_match_fields: list[str] = field(default_factory=lambda: [
        "license_number",
        "invoice_number",
    ])


# ===================================================================
# 12. Subject Line Formula
# ===================================================================

@dataclass
class SubjectLineConfig:
    """Subject line template and rules."""
    # Single invoice
    single_template: str = "PICC - {retailer_name} - Nabis Invoice {invoice_number} - {tier_label}"
    # Multiple invoices
    multi_template: str = "PICC - {retailer_name} - Nabis Invoices {invoice_numbers} - {tier_label}"
    # Join string for multiple invoice numbers
    multi_join: str = " & "


# ===================================================================
# 13. Human Review Flags
# ===================================================================

@dataclass
class ReviewFlags:
    """Conditions that force an email into the human review queue."""
    multi_invoice_per_retailer: bool = True
    invoice_has_credits: bool = True
    contact_previously_bounced: bool = True
    tier_gte_management_escalation: str = "T3"
    retailer_has_open_dispute: bool = True
    days_past_due_exit_threshold: int = 90   # beyond this, flag for non-email action


# ===================================================================
# 14. Schedule
# ===================================================================

@dataclass
class ScheduleConfig:
    """Batch run scheduling."""
    run_day: str = "Wednesday"       # day of week
    run_time: str = "07:00"          # 24h format, local time
    timezone: str = "America/New_York"


# ===================================================================
# Master Config
# ===================================================================

@dataclass
class AREmailConfig:
    """Top-level configuration container for the AR Email Automation system."""
    tiers: dict[str, TierConfig] = field(default_factory=lambda: dict(DEFAULT_TIERS))
    cc_rules: CCRules = field(default_factory=CCRules)
    attachment_rules: AttachmentRules = field(default_factory=AttachmentRules)
    smtp: SMTPSettings = field(default_factory=SMTPSettings)
    template_paths: TemplatePaths = field(default_factory=TemplatePaths)
    sender: SenderInfo = field(default_factory=SenderInfo)
    escalation_sender: EscalationSender = field(default_factory=EscalationSender)
    signature: SignatureBlock = field(default_factory=SignatureBlock)
    data_files: DataFilePaths = field(default_factory=DataFilePaths)
    output: OutputConfig = field(default_factory=OutputConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    subject_line: SubjectLineConfig = field(default_factory=SubjectLineConfig)
    review_flags: ReviewFlags = field(default_factory=ReviewFlags)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)


# ===================================================================
# YAML Loading
# ===================================================================

def _deep_update(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base dict."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _apply_yaml_to_config(cfg: AREmailConfig, data: dict) -> None:
    """Apply a parsed YAML dict onto an AREmailConfig instance."""

    # --- tiers ---
    if "tiers" in data:
        for tier_key, tier_data in data["tiers"].items():
            if tier_key in cfg.tiers:
                for attr, val in tier_data.items():
                    if hasattr(cfg.tiers[tier_key], attr):
                        setattr(cfg.tiers[tier_key], attr, val)
            else:
                cfg.tiers[tier_key] = TierConfig(**tier_data)

    # --- simple sub-configs ---
    _section_map = {
        "cc_rules": cfg.cc_rules,
        "attachment_rules": cfg.attachment_rules,
        "smtp": cfg.smtp,
        "template_paths": cfg.template_paths,
        "sender": cfg.sender,
        "escalation_sender": cfg.escalation_sender,
        "signature": cfg.signature,
        "data_files": cfg.data_files,
        "output": cfg.output,
        "matching": cfg.matching,
        "subject_line": cfg.subject_line,
        "review_flags": cfg.review_flags,
        "schedule": cfg.schedule,
    }

    for section_key, section_obj in _section_map.items():
        if section_key in data and isinstance(data[section_key], dict):
            for attr, val in data[section_key].items():
                if hasattr(section_obj, attr):
                    setattr(section_obj, attr, val)


def get_config(yaml_path: Optional[str | Path] = None) -> AREmailConfig:
    """Build an AREmailConfig, optionally overlaying values from a YAML file.

    Args:
        yaml_path: Path to a config.yaml file.  If None, looks for the
                   default config.yaml at the project root.  If that file
                   doesn't exist, returns pure defaults.

    Returns:
        Fully populated AREmailConfig instance.
    """
    cfg = AREmailConfig()

    path = Path(yaml_path) if yaml_path else DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _apply_yaml_to_config(cfg, data)

    return cfg


# ===================================================================
# Convenience: tier lookup by days past due
# ===================================================================

def tier_for_days(days_past_due: int, cfg: Optional[AREmailConfig] = None) -> Optional[TierConfig]:
    """Return the TierConfig matching the given days-past-due value."""
    if cfg is None:
        cfg = get_config()
    for tier in cfg.tiers.values():
        if tier.min_days <= days_past_due <= tier.max_days:
            return tier
    return None


# ===================================================================
# Quick smoke test when run directly
# ===================================================================

if __name__ == "__main__":
    cfg = get_config()
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Config path  : {DEFAULT_CONFIG_PATH}")
    print(f"Sender       : {cfg.sender.name} <{cfg.sender.email}>")
    print(f"Tiers loaded : {list(cfg.tiers.keys())}")
    print(f"Base CC      : {cfg.cc_rules.base_cc}")
    print(f"Fuzzy thresh : {cfg.matching.fuzzy_threshold}")
    print(f"Schedule     : {cfg.schedule.run_day} @ {cfg.schedule.run_time} {cfg.schedule.timezone}")
    print()
    for name, tier in cfg.tiers.items():
        print(f"  {name}: days [{tier.min_days}, {tier.max_days}] -> \"{tier.label}\" ({tier.template_file})")
    print()
    # Test tier lookup
    for test_days in [-2, 0, 5, 15, 25, 32, 45, 55, 100]:
        t = tier_for_days(test_days, cfg)
        label = t.label if t else "NO TIER"
        print(f"  {test_days:>4} days past due -> {label}")
