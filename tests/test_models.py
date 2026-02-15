"""Tests for src.models -- Invoice, Contact, EmailDraft dataclasses.

Covers:
- Invoice creation, auto-tier assignment, skip reason detection, formatting
- Contact creation, name parsing, email parsing, phone parsing
- EmailDraft creation, subject building, status transitions, serialization
- EmailQueue operations (add, approve, reject, export)
- TierConfig matching and default tiers
"""

import json
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from src.models import (
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


# ============================================================================
# Tier Enum
# ============================================================================

class TestTierEnum:
    """Test the Tier enum and its from_days() classmethod."""

    def test_tier_values(self):
        assert Tier.T0.value == "Coming Due"
        assert Tier.T1.value == "Overdue"
        assert Tier.T2.value == "30+ Days Past Due"

    def test_tier_count(self):
        assert len(Tier) == 3

    def test_removed_tiers_do_not_exist(self):
        assert not hasattr(Tier, "T3")
        assert not hasattr(Tier, "T4")

    @pytest.mark.parametrize("days,expected", [
        (-100, Tier.T0),
        (-5, Tier.T0),
        (-1, Tier.T0),
        (0, Tier.T0),   # 0 is "due today" -> Coming Due (not yet overdue)
        (1, Tier.T1),
        (15, Tier.T1),
        (29, Tier.T1),
        (30, Tier.T2),
        (35, Tier.T2),
        (39, Tier.T2),
        (40, Tier.T2),   # was T3 (40+), now consolidated into T2
        (45, Tier.T2),
        (49, Tier.T2),
        (50, Tier.T2),   # was T4 (50+), now consolidated into T2
        (75, Tier.T2),
        (111, Tier.T2),
        (999, Tier.T2),
    ])
    def test_from_days(self, days, expected):
        assert Tier.from_days(days) == expected

    def test_from_days_float(self):
        """Float inputs should be handled."""
        assert Tier.from_days(-2.5) == Tier.T0
        assert Tier.from_days(15.7) == Tier.T1
        assert Tier.from_days(35.0) == Tier.T2


# ============================================================================
# InvoiceStatus Enum
# ============================================================================

class TestInvoiceStatusEnum:
    def test_statuses(self):
        assert InvoiceStatus.NONE.value == ""
        assert InvoiceStatus.EXPECTED_TO_PAY.value == "Expected to pay"
        assert InvoiceStatus.PAYMENT_ENROUTE.value == "Payment Enroute"
        assert InvoiceStatus.ISSUE.value == "Issue"

    def test_status_count(self):
        assert len(InvoiceStatus) == 4


# ============================================================================
# EmailStatus Enum
# ============================================================================

class TestEmailStatusEnum:
    def test_statuses(self):
        assert EmailStatus.PENDING.value == "pending"
        assert EmailStatus.APPROVED.value == "approved"
        assert EmailStatus.REJECTED.value == "rejected"
        assert EmailStatus.SENT.value == "sent"
        assert EmailStatus.FAILED.value == "failed"


# ============================================================================
# SkipReason Enum
# ============================================================================

class TestSkipReasonEnum:
    def test_reasons(self):
        assert SkipReason.ALREADY_PAID.value == "Paid column is True"
        assert SkipReason.PAYMENT_ENROUTE.value == "Status is Payment Enroute"
        assert SkipReason.EMAIL_ALREADY_SENT.value == "Email Sent is True for current cycle"
        assert SkipReason.NO_ACCOUNT_MANAGER.value == "Account Manager is blank or #N/A"
        assert SkipReason.NO_CONTACT_MATCH.value == "No matching record in Managers sheet"
        assert SkipReason.NO_POC_EMAIL.value == "Managers record exists but POC Email is empty"


# ============================================================================
# Invoice Dataclass
# ============================================================================

class TestInvoice:
    """Test Invoice creation, auto-tier, skip detection, properties."""

    def _make_invoice(self, **overrides) -> Invoice:
        """Factory for Invoice with sensible defaults."""
        defaults = dict(
            invoice_number="906858",
            store_name="Aroma Farms",
            amount=1510.00,
            due_date=date(2026, 2, 5),
            days_past_due=-2,
            account_manager="Mildred Verdadero",
            account_manager_phone="(415) 839-8232",
            sales_rep="Bryce J",
        )
        defaults.update(overrides)
        return Invoice(**defaults)

    def test_basic_creation(self):
        inv = self._make_invoice()
        assert inv.invoice_number == "906858"
        assert inv.store_name == "Aroma Farms"
        assert inv.amount == 1510.00
        assert inv.due_date == date(2026, 2, 5)
        assert inv.days_past_due == -2

    def test_auto_tier_assignment(self):
        """__post_init__ should auto-assign tier based on days_past_due."""
        inv_coming_due = self._make_invoice(days_past_due=-2)
        assert inv_coming_due.tier == Tier.T0

        inv_overdue = self._make_invoice(days_past_due=15)
        assert inv_overdue.tier == Tier.T1

        inv_30plus = self._make_invoice(days_past_due=35)
        assert inv_30plus.tier == Tier.T2

        inv_40plus = self._make_invoice(days_past_due=45)
        assert inv_40plus.tier == Tier.T2  # consolidated: was T3

        inv_50plus = self._make_invoice(days_past_due=111)
        assert inv_50plus.tier == Tier.T2  # consolidated: was T4

    def test_skip_reason_paid(self):
        inv = self._make_invoice(paid=True)
        assert inv.skip_reason == SkipReason.ALREADY_PAID
        assert not inv.is_sendable

    def test_skip_reason_payment_enroute(self):
        inv = self._make_invoice(status=InvoiceStatus.PAYMENT_ENROUTE)
        assert inv.skip_reason == SkipReason.PAYMENT_ENROUTE
        assert not inv.is_sendable

    def test_skip_reason_email_already_sent(self):
        inv = self._make_invoice(email_sent=True)
        assert inv.skip_reason == SkipReason.EMAIL_ALREADY_SENT
        assert not inv.is_sendable

    def test_skip_reason_no_account_manager_blank(self):
        inv = self._make_invoice(account_manager="")
        assert inv.skip_reason == SkipReason.NO_ACCOUNT_MANAGER
        assert not inv.is_sendable

    def test_skip_reason_no_account_manager_na(self):
        inv = self._make_invoice(account_manager="#N/A")
        assert inv.skip_reason == SkipReason.NO_ACCOUNT_MANAGER
        assert not inv.is_sendable

    def test_no_skip_reason_sendable(self):
        inv = self._make_invoice()
        assert inv.skip_reason is None
        assert inv.is_sendable

    def test_skip_reason_priority_paid_over_enroute(self):
        """Paid should be detected first even if status is also Payment Enroute."""
        inv = self._make_invoice(paid=True, status=InvoiceStatus.PAYMENT_ENROUTE)
        assert inv.skip_reason == SkipReason.ALREADY_PAID

    def test_amount_formatted(self):
        inv = self._make_invoice(amount=2700.56)
        assert inv.amount_formatted == "$2,700.56"

    def test_amount_formatted_large(self):
        inv = self._make_invoice(amount=18071.75)
        assert inv.amount_formatted == "$18,071.75"

    def test_amount_formatted_small(self):
        inv = self._make_invoice(amount=108.00)
        assert inv.amount_formatted == "$108.00"

    def test_due_date_formatted(self):
        inv = self._make_invoice(due_date=date(2026, 2, 5))
        assert inv.due_date_formatted == "Feb 05, 2026"

    def test_due_date_formatted_none(self):
        inv = self._make_invoice(due_date=None)
        assert inv.due_date_formatted == ""

    def test_tier_label(self):
        inv = self._make_invoice(days_past_due=-2)
        assert inv.tier_label == "Coming Due"

        inv2 = self._make_invoice(days_past_due=15)
        assert inv2.tier_label == "Overdue"

    def test_license_number_default_empty(self):
        inv = self._make_invoice()
        assert inv.license_number == ""

    def test_notes_and_followup(self):
        inv = self._make_invoice(
            notes="Customer called, will pay Friday",
            follow_up_date=date(2026, 2, 14),
        )
        assert inv.notes == "Customer called, will pay Friday"
        assert inv.follow_up_date == date(2026, 2, 14)


# ============================================================================
# Contact Dataclass
# ============================================================================

class TestContact:
    """Test Contact creation, parsing methods, properties."""

    def _make_contact(self, **overrides) -> Contact:
        defaults = dict(
            store_name="Aroma Farms",
            email="aromafarmsinc@gmail.com",
            contact_name="Emily Stratakos",
            role="AP",
        )
        defaults.update(overrides)
        return Contact(**defaults)

    def test_basic_creation(self):
        c = self._make_contact()
        assert c.store_name == "Aroma Farms"
        assert c.email == "aromafarmsinc@gmail.com"
        assert c.contact_name == "Emily Stratakos"

    def test_first_name(self):
        c = self._make_contact(contact_name="Emily Stratakos")
        assert c.first_name == "Emily"

    def test_first_name_hyphenated(self):
        c = self._make_contact(contact_name="Jo-Anne Rainone")
        assert c.first_name == "Jo-Anne"

    def test_first_name_empty(self):
        c = self._make_contact(contact_name="")
        assert c.first_name == ""

    def test_first_name_single_word(self):
        c = self._make_contact(contact_name="Herbwell Team")
        assert c.first_name == "Herbwell"

    def test_has_email_true(self):
        c = self._make_contact(email="test@example.com")
        assert c.has_email is True

    def test_has_email_false(self):
        c = self._make_contact(email="", all_emails=[])
        assert c.has_email is False

    def test_has_email_via_all_emails(self):
        c = self._make_contact(email="", all_emails=["test@example.com"])
        assert c.has_email is True

    # --- parse_poc_name_title ---

    def test_parse_poc_name_title_with_dash(self):
        name, title = Contact.parse_poc_name_title("Janti Eisakharian - Owner")
        assert name == "Janti Eisakharian"
        assert title == "Owner"

    def test_parse_poc_name_title_without_title(self):
        name, title = Contact.parse_poc_name_title("Jack Eisakharian")
        assert name == "Jack Eisakharian"
        assert title == ""

    def test_parse_poc_name_title_empty(self):
        name, title = Contact.parse_poc_name_title("")
        assert name == ""
        assert title == ""

    def test_parse_poc_name_title_with_extra_spaces(self):
        name, title = Contact.parse_poc_name_title("  Jo-Anne Rainone - Accounting  ")
        assert name == "Jo-Anne Rainone"
        assert title == "Accounting"

    # --- parse_multi_line_emails ---

    def test_parse_multi_line_emails_basic(self):
        result = Contact.parse_multi_line_emails("a@b.com\nc@d.com\n")
        assert result == ["a@b.com", "c@d.com"]

    def test_parse_multi_line_emails_empty(self):
        assert Contact.parse_multi_line_emails("") == []

    def test_parse_multi_line_emails_single(self):
        assert Contact.parse_multi_line_emails("test@example.com") == ["test@example.com"]

    def test_parse_multi_line_emails_strips_whitespace(self):
        result = Contact.parse_multi_line_emails("  a@b.com  \n  c@d.com  ")
        assert result == ["a@b.com", "c@d.com"]

    def test_parse_multi_line_emails_skips_empty_lines(self):
        result = Contact.parse_multi_line_emails("a@b.com\n\n\nc@d.com")
        assert result == ["a@b.com", "c@d.com"]

    # --- parse_multi_line_phones ---

    def test_parse_multi_line_phones(self):
        raw = "Jack - (917) 682-7576\nJanti - (917) 682-7576"
        result = Contact.parse_multi_line_phones(raw)
        assert len(result) == 2
        assert result[0] == "Jack - (917) 682-7576"

    def test_parse_multi_line_phones_empty(self):
        assert Contact.parse_multi_line_phones("") == []


# ============================================================================
# EmailDraft Dataclass
# ============================================================================

class TestEmailDraft:
    """Test EmailDraft creation, subject building, status transitions, serialization."""

    def _make_invoice(self, **overrides) -> Invoice:
        defaults = dict(
            invoice_number="906858",
            store_name="Aroma Farms",
            amount=1510.00,
            due_date=date(2026, 2, 5),
            days_past_due=-2,
            account_manager="Mildred Verdadero",
        )
        defaults.update(overrides)
        return Invoice(**defaults)

    def _make_draft(self, **overrides) -> EmailDraft:
        inv = self._make_invoice()
        defaults = dict(
            to=["aromafarmsinc@gmail.com"],
            cc=["ny.ar@nabis.com", "mario@piccplatform.com"],
            subject="",
            body_html="<p>Hello Emily</p>",
            tier=Tier.T0,
            invoices=[inv],
            store_name="Aroma Farms",
            attachments=["Nabis ACH Payment Form.pdf"],
        )
        defaults.update(overrides)
        return EmailDraft(**defaults)

    def test_basic_creation(self):
        draft = self._make_draft()
        assert draft.status == EmailStatus.PENDING
        assert draft.store_name == "Aroma Farms"
        assert len(draft.invoices) == 1

    def test_invoice_numbers(self):
        draft = self._make_draft()
        assert draft.invoice_numbers == ["906858"]

    def test_total_amount_single(self):
        draft = self._make_draft()
        assert draft.total_amount == 1510.00

    def test_total_amount_multi(self):
        inv1 = self._make_invoice(invoice_number="904667", amount=1723.00)
        inv2 = self._make_invoice(invoice_number="905055", amount=1721.00)
        draft = self._make_draft(invoices=[inv1, inv2])
        assert draft.total_amount == pytest.approx(3444.00)

    def test_total_amount_formatted(self):
        draft = self._make_draft()
        assert draft.total_amount_formatted == "$1,510.00"

    def test_is_multi_invoice_false(self):
        draft = self._make_draft()
        assert draft.is_multi_invoice is False

    def test_is_multi_invoice_true(self):
        inv1 = self._make_invoice(invoice_number="904667")
        inv2 = self._make_invoice(invoice_number="905055")
        draft = self._make_draft(invoices=[inv1, inv2])
        assert draft.is_multi_invoice is True

    def test_subject_invoice_part_single(self):
        draft = self._make_draft()
        assert draft.subject_invoice_part == "Invoice 906858"

    def test_subject_invoice_part_multi(self):
        inv1 = self._make_invoice(invoice_number="904667")
        inv2 = self._make_invoice(invoice_number="905055")
        draft = self._make_draft(invoices=[inv1, inv2])
        assert draft.subject_invoice_part == "Invoices 904667 & 905055"

    def test_subject_invoice_part_empty(self):
        draft = self._make_draft(invoices=[])
        assert draft.subject_invoice_part == ""

    def test_build_subject_single(self):
        draft = self._make_draft()
        subject = draft.build_subject()
        assert subject == "PICC - Aroma Farms - Nabis Invoice 906858 - Coming Due"
        assert draft.subject == subject

    def test_build_subject_multi(self):
        inv1 = self._make_invoice(invoice_number="904667")
        inv2 = self._make_invoice(invoice_number="905055")
        draft = self._make_draft(
            invoices=[inv1, inv2],
            store_name="Seaweed RBNY",
            tier=Tier.T1,
        )
        subject = draft.build_subject()
        assert "Invoices 904667 & 905055" in subject
        assert "Seaweed RBNY" in subject
        assert "Overdue" in subject

    # --- Status transitions ---

    def test_approve(self):
        draft = self._make_draft()
        draft.approve()
        assert draft.status == EmailStatus.APPROVED

    def test_approve_twice_raises(self):
        draft = self._make_draft()
        draft.approve()
        with pytest.raises(ValueError, match="PENDING"):
            draft.approve()

    def test_reject(self):
        draft = self._make_draft()
        draft.reject("Incorrect contact")
        assert draft.status == EmailStatus.REJECTED
        assert draft.rejection_reason == "Incorrect contact"

    def test_reject_twice_raises(self):
        draft = self._make_draft()
        draft.reject()
        with pytest.raises(ValueError, match="PENDING"):
            draft.reject()

    def test_mark_sent(self):
        draft = self._make_draft()
        draft.approve()
        draft.mark_sent()
        assert draft.status == EmailStatus.SENT
        assert draft.sent_at is not None
        assert isinstance(draft.sent_at, datetime)

    def test_mark_failed(self):
        draft = self._make_draft()
        draft.approve()
        draft.mark_failed("SMTP timeout")
        assert draft.status == EmailStatus.FAILED
        assert draft.error_message == "SMTP timeout"

    # --- Serialization ---

    def test_to_dict(self):
        draft = self._make_draft()
        draft.build_subject()
        d = draft.to_dict()
        assert d["to"] == ["aromafarmsinc@gmail.com"]
        assert d["tier"] == "Coming Due"
        assert d["store_name"] == "Aroma Farms"
        assert d["invoice_numbers"] == ["906858"]
        assert d["total_amount"] == "$1,510.00"
        assert d["status"] == "pending"

    def test_to_dict_json_serializable(self):
        draft = self._make_draft()
        draft.build_subject()
        d = draft.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)


# ============================================================================
# EmailQueue Dataclass
# ============================================================================

class TestEmailQueue:
    """Test EmailQueue CRUD, batch operations, and export."""

    def _make_invoice(self, **kw) -> Invoice:
        defaults = dict(
            invoice_number="906858",
            store_name="Test Store",
            amount=1000.00,
            days_past_due=5,
            account_manager="Test AM",
        )
        defaults.update(kw)
        return Invoice(**defaults)

    def _make_draft(self, store_name="Test Store", tier=Tier.T1) -> EmailDraft:
        inv = self._make_invoice(store_name=store_name)
        return EmailDraft(
            to=["test@example.com"],
            tier=tier,
            invoices=[inv],
            store_name=store_name,
        )

    def test_empty_queue(self):
        q = EmailQueue()
        assert len(q) == 0
        assert q.pending == []
        assert q.approved == []

    def test_add_draft(self):
        q = EmailQueue()
        draft = self._make_draft()
        q.add(draft)
        assert len(q) == 1
        assert len(q.pending) == 1

    def test_approve_all(self):
        q = EmailQueue()
        for _ in range(5):
            q.add(self._make_draft())
        count = q.approve_all()
        assert count == 5
        assert len(q.approved) == 5
        assert len(q.pending) == 0

    def test_reject_all(self):
        q = EmailQueue()
        for _ in range(3):
            q.add(self._make_draft())
        count = q.reject_all("Bad batch")
        assert count == 3
        assert len(q.rejected) == 3

    def test_approve_by_tier(self):
        q = EmailQueue()
        q.add(self._make_draft(tier=Tier.T0))
        q.add(self._make_draft(tier=Tier.T0))
        q.add(self._make_draft(tier=Tier.T1))
        q.add(self._make_draft(tier=Tier.T2))

        count = q.approve_by_tier(Tier.T0)
        assert count == 2
        assert len(q.approved) == 2
        assert len(q.pending) == 2

    def test_approve_by_index(self):
        q = EmailQueue()
        for i in range(5):
            q.add(self._make_draft(store_name=f"Store {i}"))
        count = q.approve_by_index([0, 2, 4])
        assert count == 3
        assert q.drafts[0].status == EmailStatus.APPROVED
        assert q.drafts[1].status == EmailStatus.PENDING
        assert q.drafts[2].status == EmailStatus.APPROVED

    def test_approve_by_index_out_of_range(self):
        q = EmailQueue()
        q.add(self._make_draft())
        count = q.approve_by_index([0, 5, -1])
        # Only index 0 is valid and pending
        assert count == 1

    def test_reject_by_index(self):
        q = EmailQueue()
        for _ in range(3):
            q.add(self._make_draft())
        count = q.reject_by_index([1], "Bad contact")
        assert count == 1
        assert q.drafts[1].status == EmailStatus.REJECTED

    def test_iteration(self):
        q = EmailQueue()
        q.add(self._make_draft())
        q.add(self._make_draft())
        drafts = list(q)
        assert len(drafts) == 2

    def test_getitem(self):
        q = EmailQueue()
        draft = self._make_draft(store_name="Special Store")
        q.add(draft)
        assert q[0].store_name == "Special Store"

    def test_summary(self):
        q = EmailQueue()
        q.add(self._make_draft(tier=Tier.T0))
        q.add(self._make_draft(tier=Tier.T1))
        q.drafts[1].approve()
        summary = q.summary()
        assert "Email Queue: 2 drafts" in summary
        assert "Pending:  1" in summary
        assert "Approved: 1" in summary

    def test_export_json(self, tmp_path):
        q = EmailQueue()
        q.add(self._make_draft())
        q.add(self._make_draft())

        output_path = tmp_path / "queue.json"
        result_path = q.export_json(output_path)
        assert result_path.exists()

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["summary"]["total"] == 2
        assert len(data["drafts"]) == 2

    def test_export_csv(self, tmp_path):
        q = EmailQueue()
        q.add(self._make_draft())

        output_path = tmp_path / "queue.csv"
        result_path = q.export_csv(output_path)
        assert result_path.exists()

        content = result_path.read_text(encoding="utf-8")
        assert "store_name" in content
        assert "Test Store" in content

    def test_queue_sent_and_failed(self):
        q = EmailQueue()
        d1 = self._make_draft()
        d2 = self._make_draft()
        q.add(d1)
        q.add(d2)
        d1.approve()
        d1.mark_sent()
        d2.approve()
        d2.mark_failed("Connection error")

        assert len(q.sent) == 1
        assert len(q.failed) == 1


# ============================================================================
# TierConfig Dataclass
# ============================================================================

class TestTierConfig:
    """Test TierConfig matching logic and defaults."""

    def test_matches_within_range(self):
        tc = TierConfig(
            tier_name=Tier.T1,
            min_days=1,
            max_days=29,
            template_name="overdue",
        )
        assert tc.matches(1) is True
        assert tc.matches(15) is True
        assert tc.matches(29) is True

    def test_matches_below_range(self):
        tc = TierConfig(
            tier_name=Tier.T1,
            min_days=1,
            max_days=29,
            template_name="overdue",
        )
        assert tc.matches(0) is False

    def test_matches_above_range(self):
        tc = TierConfig(
            tier_name=Tier.T1,
            min_days=1,
            max_days=29,
            template_name="overdue",
        )
        assert tc.matches(30) is False

    def test_matches_unbounded_max(self):
        tc = TierConfig(
            tier_name=Tier.T2,
            min_days=30,
            max_days=None,
            template_name="past_due_30",
        )
        assert tc.matches(30) is True
        assert tc.matches(999) is True
        assert tc.matches(29) is False

    def test_default_tiers(self):
        tiers = TierConfig.default_tiers()
        assert len(tiers) == 3
        assert tiers[0].tier_name == Tier.T0
        assert tiers[2].tier_name == Tier.T2

    def test_default_tiers_cover_all_ranges(self):
        """Default tiers should cover from -7 to unbounded."""
        tiers = TierConfig.default_tiers()
        # T0 covers -7 to 0
        assert tiers[0].min_days == -7
        assert tiers[0].max_days == 0
        # T2 covers 30+
        assert tiers[2].min_days == 30
        assert tiers[2].max_days is None

    def test_find_tier(self):
        assert TierConfig.find_tier(-5).tier_name == Tier.T0
        assert TierConfig.find_tier(15).tier_name == Tier.T1
        assert TierConfig.find_tier(35).tier_name == Tier.T2
        assert TierConfig.find_tier(45).tier_name == Tier.T2   # consolidated
        assert TierConfig.find_tier(100).tier_name == Tier.T2  # consolidated

    def test_find_tier_boundary_values(self):
        assert TierConfig.find_tier(-1).tier_name == Tier.T0
        assert TierConfig.find_tier(0).tier_name == Tier.T0
        assert TierConfig.find_tier(1).tier_name == Tier.T1
        assert TierConfig.find_tier(29).tier_name == Tier.T1
        assert TierConfig.find_tier(30).tier_name == Tier.T2
        assert TierConfig.find_tier(39).tier_name == Tier.T2
        assert TierConfig.find_tier(40).tier_name == Tier.T2   # consolidated
        assert TierConfig.find_tier(49).tier_name == Tier.T2   # consolidated
        assert TierConfig.find_tier(50).tier_name == Tier.T2   # consolidated

    def test_find_tier_extreme_negative(self):
        """Very negative values should match T0 (now -7 lower bound)."""
        assert TierConfig.find_tier(-7).tier_name == Tier.T0

    def test_find_tier_no_match_raises(self):
        """Values below -7 should raise ValueError with default tiers."""
        with pytest.raises(ValueError):
            TierConfig.find_tier(-8)

    def test_default_tiers_have_cc_rules(self):
        """Each default tier should include CC rules with the rep placeholder."""
        for tier_cfg in TierConfig.default_tiers():
            assert "{rep_email}" in tier_cfg.cc_rules

    def test_default_tiers_t2_plus_include_ocm_warning(self):
        tiers = TierConfig.default_tiers()
        assert tiers[0].include_ocm_warning is False  # T0
        assert tiers[1].include_ocm_warning is False  # T1
        assert tiers[2].include_ocm_warning is True   # T2 (30+ Days Past Due)
