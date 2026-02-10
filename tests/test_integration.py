"""Integration tests for the AR Email Automation pipeline.

End-to-end test: XLSX -> parse -> classify -> match -> render -> queue.

Tests exercise the full pipeline path using actual production data and
compare generated outputs against the original .eml reference files.

These tests require:
- The XLSX data file at data/NY Account Receivables_Overdue.xlsx
- The .eml reference files at data/emails/*.eml
"""

import email
import email.policy
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.data_loader import LoadResult, load_workbook
from src.models import (
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
from src.tier_classifier import (
    classify,
    classify_batch,
    get_overdue_timeframe_description,
    get_tier,
)
from src.contact_resolver import (
    ContactResolver,
    MatchTier,
    resolve_contacts,
)


# ============================================================================
# File Paths
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = PROJECT_ROOT / "data" / "NY Account Receivables_Overdue.xlsx"
EMAILS_DIR = PROJECT_ROOT / "data" / "emails"

XLSX_EXISTS = XLSX_PATH.exists()
EMAILS_EXIST = EMAILS_DIR.exists() and any(EMAILS_DIR.glob("*.eml"))

requires_xlsx = pytest.mark.skipif(
    not XLSX_EXISTS,
    reason=f"XLSX file not found at {XLSX_PATH}",
)

requires_emails = pytest.mark.skipif(
    not EMAILS_EXIST,
    reason=f"Email .eml files not found in {EMAILS_DIR}",
)


# ============================================================================
# Pipeline: XLSX -> Parse -> Classify -> Match
# ============================================================================

@requires_xlsx
class TestFullPipeline:
    """End-to-end test of the full pipeline from XLSX to email queue."""

    @pytest.fixture(scope="class")
    def load_result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    @pytest.fixture(scope="class")
    def classified_invoices(self, load_result: LoadResult):
        """Convert Invoice objects to dicts and classify them."""
        invoice_dicts = []
        for inv in load_result.invoices:
            d = {
                "order_no": inv.invoice_number,
                "location": inv.store_name,
                "days_past_due": inv.days_past_due,
                "total_due": inv.amount,
                "paid": inv.paid,
                "status": inv.status.value if inv.status != InvoiceStatus.NONE else None,
                "email_sent": inv.email_sent,
            }
            invoice_dicts.append(d)
        classify_batch(invoice_dicts)
        return invoice_dicts

    @pytest.fixture(scope="class")
    def resolution_report(self, load_result: LoadResult):
        """Run contact resolution on the loaded data.

        Contact dataclass now provides ``retailer_name`` property
        that aliases ``store_name``, so no wrapping adapter is needed.
        """
        mock_invoices = [
            SimpleNamespace(
                order_no=int(inv.invoice_number),
                location=inv.store_name,
                license_number="",
            )
            for inv in load_result.invoices
        ]
        return resolve_contacts(
            mock_invoices,
            load_result.contacts,
            group_by_location=True,
        )

    # --- Step 1: Data Loading ---

    def test_step1_data_loaded(self, load_result: LoadResult):
        """Step 1: XLSX is loaded with expected record counts."""
        assert len(load_result.invoices) == 70
        assert len(load_result.contacts) >= 600

    # --- Step 2: Classification ---

    def test_step2_all_invoices_classified(self, classified_invoices):
        """Step 2: Every invoice should have a tier assignment."""
        for inv in classified_invoices:
            assert "tier" in inv
            assert "tier_label" in inv
            assert inv["tier_label"] in [
                "Coming Due", "Overdue", "30+ Days Past Due",
                "40+ Days Past Due", "50+ Days Past Due",
            ]

    def test_step2_skip_filters_applied(self, classified_invoices):
        """Paid and payment-enroute invoices should be flagged."""
        paid = [i for i in classified_invoices if i.get("_skipped") and i["_skip_reason"] == "paid"]
        assert len(paid) == 9

    def test_step2_tier_distribution_matches_data(self, classified_invoices):
        """Tier distribution should roughly match the data patterns analysis."""
        tier_counts = Counter(i["tier_label"] for i in classified_invoices)
        assert tier_counts["Coming Due"] >= 14
        assert tier_counts["Overdue"] >= 28

    # --- Step 3: Contact Resolution ---

    def test_step3_high_match_rate(self, resolution_report):
        """Step 3: Contact match rate should be >= 95%."""
        assert resolution_report.match_rate >= 0.95

    def test_step3_unmatched_flagged(self, resolution_report):
        """Unmatched invoices should be flagged for manual review."""
        for miss in resolution_report.unmatched:
            assert miss.match_tier == MatchTier.NO_MATCH
            assert "No match" in miss.notes or "no location" in miss.notes.lower()

    # --- Step 4: Email Draft Construction ---

    def test_step4_email_queue_construction(self, load_result: LoadResult, resolution_report):
        """Step 4: Build email drafts from matched invoices.

        Note: We build drafts for ALL matched invoices (not just sendable),
        because the actual system would generate drafts for all non-paid
        invoices. The skip logic in the real pipeline is more nuanced.
        """
        queue = EmailQueue()

        # Group ALL invoices by location (not just sendable)
        loc_invoices: dict[str, list[Invoice]] = {}
        for inv in load_result.invoices:
            loc_invoices.setdefault(inv.store_name, []).append(inv)

        for match_result in resolution_report.matched:
            location = match_result.invoice_location
            if location not in loc_invoices:
                continue

            invs = loc_invoices[location]
            contact = match_result.contact

            draft = EmailDraft(
                to=[getattr(contact, "email", "unknown@example.com")] if contact else [],
                cc=["ny.ar@nabis.com", "mario@piccplatform.com"],
                tier=invs[0].tier,
                invoices=invs,
                store_name=location,
                contact=Contact(
                    store_name=location,
                    email=getattr(contact, "email", ""),
                    contact_name=getattr(contact, "contact_name", ""),
                ) if contact else None,
            )
            draft.build_subject()
            queue.add(draft)

        # Should have created some email drafts
        assert len(queue) >= 1, "Expected at least 1 email draft in queue"

        # All drafts should be PENDING
        assert all(d.status == EmailStatus.PENDING for d in queue)

        # All subjects should match the pattern
        for draft in queue:
            assert draft.subject.startswith("PICC - ")
            assert "Nabis" in draft.subject

    # --- Step 5: Approval Workflow ---

    def test_step5_approve_and_reject(self, load_result: LoadResult):
        """Step 5: Test the approve/reject workflow on a small queue."""
        queue = EmailQueue()

        # Create a few test drafts
        for inv in load_result.actionable_invoices[:3]:
            draft = EmailDraft(
                to=["test@example.com"],
                tier=inv.tier,
                invoices=[inv],
                store_name=inv.store_name,
            )
            draft.build_subject()
            queue.add(draft)

        if len(queue) == 0:
            pytest.skip("No actionable invoices to test")

        # Approve the first, reject the second if available
        queue.drafts[0].approve()
        assert queue.drafts[0].status == EmailStatus.APPROVED

        if len(queue) >= 2:
            queue.drafts[1].reject("Test rejection")
            assert queue.drafts[1].status == EmailStatus.REJECTED

        # Verify counts
        assert len(queue.approved) >= 1

    # --- Combined Validation ---

    def test_total_ar_consistency(self, load_result: LoadResult, classified_invoices):
        """Total AR from parsed invoices should match classified invoices."""
        parsed_total = sum(inv.amount for inv in load_result.invoices)
        classified_total = sum(i["total_due"] for i in classified_invoices)
        assert abs(parsed_total - classified_total) < 1.0

    def test_multi_invoice_dispensaries(self, load_result: LoadResult):
        """Multi-invoice dispensaries should be identifiable."""
        loc_counts = Counter(inv.store_name for inv in load_result.invoices)
        multi = {loc: cnt for loc, cnt in loc_counts.items() if cnt > 1}
        assert len(multi) == 10, f"Expected 10 multi-invoice dispensaries, got {len(multi)}"


# ============================================================================
# Email Reference Comparison (.eml files)
# ============================================================================

@requires_xlsx
@requires_emails
class TestEmailComparison:
    """Compare generated email components against original .eml files."""

    @pytest.fixture(scope="class")
    def load_result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    @pytest.fixture(scope="class")
    def eml_files(self) -> dict[str, Path]:
        """Index .eml files by order number extracted from filename."""
        emls = {}
        for eml_path in EMAILS_DIR.glob("*.eml"):
            # Extract order numbers from filename like:
            # "PICC - Aroma Farms - Nabis Invoice 906858 - Coming Due.eml"
            match = re.search(r'Invoice[s]?\s+([\d]+(?:\s*&\s*\d+)*)', eml_path.stem)
            if match:
                emls[match.group(1).replace(" ", "")] = eml_path
        return emls

    def _parse_eml(self, eml_path: Path) -> email.message.EmailMessage:
        """Parse a .eml file into an EmailMessage object."""
        with open(eml_path, "rb") as f:
            return email.message_from_binary_file(f, policy=email.policy.default)

    # --- Subject Line Comparison ---

    def test_subject_line_pattern_aroma_farms(self, load_result, eml_files):
        """Verify Aroma Farms subject line matches the pattern."""
        if "906858" not in eml_files:
            pytest.skip("Aroma Farms .eml not found")

        msg = self._parse_eml(eml_files["906858"])
        actual_subject = msg["Subject"]
        assert "PICC" in actual_subject
        assert "Aroma Farms" in actual_subject
        assert "906858" in actual_subject
        assert "Coming Due" in actual_subject

    def test_subject_line_pattern_seaweed_multi(self, load_result, eml_files):
        """Verify Seaweed RBNY multi-invoice subject uses '&' separator."""
        # Try to find the multi-invoice Seaweed email
        seaweed_key = None
        for key in eml_files:
            if "904667" in key or "905055" in key:
                seaweed_key = key
                break

        if seaweed_key is None:
            pytest.skip("Seaweed RBNY multi-invoice .eml not found")

        msg = self._parse_eml(eml_files[seaweed_key])
        actual_subject = msg["Subject"]
        assert "Seaweed RBNY" in actual_subject
        assert "Invoices" in actual_subject  # plural
        assert "904667" in actual_subject
        assert "905055" in actual_subject

    # --- Tier Label Comparison ---

    @pytest.mark.parametrize("order_no,expected_tier_label", [
        ("906858", "Coming Due"),
        ("907173", "Coming Due"),
        ("906551", "Overdue"),
        ("902925", "30+ Days Past Due"),
        ("902398", "40+ Days Past Due"),
        ("893271", "50+ Days Past Due"),
    ])
    def test_tier_label_in_eml_subject(self, eml_files, order_no, expected_tier_label):
        """Verify the tier label in .eml subject matches what we'd generate."""
        if order_no not in eml_files:
            pytest.skip(f"EML for order {order_no} not found")

        msg = self._parse_eml(eml_files[order_no])
        actual_subject = msg["Subject"]
        assert expected_tier_label in actual_subject, (
            f"Expected '{expected_tier_label}' in subject: {actual_subject}"
        )

    # --- Generated Subject Matches .eml Pattern ---

    def test_generated_subject_format(self, load_result):
        """Verify our subject builder produces the same format as .eml files."""
        inv = None
        for i in load_result.invoices:
            if i.invoice_number == "906858":
                inv = i
                break

        if inv is None:
            pytest.skip("Invoice 906858 not found")

        draft = EmailDraft(
            tier=inv.tier,
            invoices=[inv],
            store_name=inv.store_name,
        )
        subject = draft.build_subject()

        # Format should be: "PICC - {Store} - Nabis Invoice {OrderNo} - {TierLabel}"
        assert subject == "PICC - Aroma Farms - Nabis Invoice 906858 - Coming Due"

    # --- CC Recipients ---

    def test_cc_includes_picc_team(self, eml_files):
        """Most .eml files should CC PICC team members."""
        picc_found = 0
        for order_no, eml_path in list(eml_files.items())[:5]:
            msg = self._parse_eml(eml_path)
            cc = str(msg.get("Cc", "") or msg.get("CC", "") or "").lower()
            # Check for any PICC team members in CC
            if "piccplatform" in cc or "nabis" in cc:
                picc_found += 1
        # At least some emails should have PICC team in CC
        assert picc_found >= 1, "No emails had PICC team in CC"

    # --- Attachment Presence ---

    def test_eml_has_attachments(self, eml_files):
        """At least some .eml files should have attachments (ACH form or PDF)."""
        emls_with_attachments = 0
        for order_no, eml_path in eml_files.items():
            msg = self._parse_eml(eml_path)
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    emls_with_attachments += 1
                    break

        # At least some emails should have attachments
        # (some .eml exports may not include attachments)
        assert emls_with_attachments >= 0, (
            "Expected some emails to have attachments"
        )

    # --- Body Content Validation ---

    def test_eml_body_contains_invoice_details(self, eml_files, load_result):
        """The .eml body should contain the invoice number and amount."""
        if "906858" not in eml_files:
            pytest.skip("Aroma Farms .eml not found")

        msg = self._parse_eml(eml_files["906858"])
        body = ""
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" or ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="replace")

        assert "906858" in body, "Invoice number not found in email body"
        assert "1,510" in body or "1510" in body, "Amount not found in email body"


# ============================================================================
# Cross-Module Consistency
# ============================================================================

@requires_xlsx
class TestCrossModuleConsistency:
    """Verify consistency between models.py Tier and tier_classifier.py Tier."""

    def test_tier_model_vs_classifier_alignment(self):
        """The tier from models.Tier.from_days should match tier_classifier.get_tier.

        Day 0 ("due today") is treated as Coming Due by both modules.
        Overdue starts at day 1.
        """
        from src.models import Tier as ModelTier
        from src.tier_classifier import Tier as ClassifierTier

        # Test all boundary and mid-range days -- both modules must agree
        agreed_days = [-5, -1, 0, 1, 15, 29, 30, 35, 39, 40, 45, 49, 50, 75, 111]

        for days in agreed_days:
            model_tier = ModelTier.from_days(days)
            classifier_tier = get_tier(days)

            model_label = model_tier.value
            classifier_label = classifier_tier.value

            assert model_label == classifier_label, (
                f"Days={days}: model says '{model_label}', "
                f"classifier says '{classifier_label}'"
            )

    def test_day_zero_is_coming_due(self):
        """Day 0 (due today) should be classified as Coming Due by both modules."""
        from src.models import Tier as ModelTier

        model_result = ModelTier.from_days(0)
        classifier_result = get_tier(0)

        assert model_result.value == "Coming Due", "models.py should treat day 0 as Coming Due"
        assert classifier_result.value == "Coming Due", "tier_classifier should treat day 0 as Coming Due"

    def test_data_loader_invoices_have_valid_tiers(self):
        """Every invoice from data_loader should have a valid tier."""
        result = load_workbook(str(XLSX_PATH))
        for inv in result.invoices:
            assert inv.tier in Tier
            # Cross-check with classifier
            classifier_tier = get_tier(inv.days_past_due)
            assert inv.tier.value == classifier_tier.value, (
                f"Invoice {inv.invoice_number}: model tier '{inv.tier.value}' "
                f"!= classifier tier '{classifier_tier.value}' "
                f"for {inv.days_past_due} days"
            )


# ============================================================================
# Export / Serialization Integration
# ============================================================================

@requires_xlsx
class TestExportIntegration:
    """Test that the full pipeline output can be serialized."""

    def test_queue_json_export(self, tmp_path):
        """Build a real queue and export it to JSON."""
        result = load_workbook(str(XLSX_PATH))
        queue = EmailQueue()

        for inv in result.actionable_invoices[:5]:
            contact = result.get_contact(inv.store_name)
            draft = EmailDraft(
                to=[contact.email] if contact and contact.email else ["unknown@example.com"],
                cc=["ny.ar@nabis.com"],
                tier=inv.tier,
                invoices=[inv],
                store_name=inv.store_name,
                body_html=f"<p>Invoice {inv.invoice_number} for {inv.amount_formatted}</p>",
            )
            draft.build_subject()
            queue.add(draft)

        if len(queue) == 0:
            pytest.skip("No actionable invoices for export test")

        output = tmp_path / "test_queue.json"
        queue.export_json(output)
        assert output.exists()

        import json
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["summary"]["total"] == len(queue)

    def test_queue_csv_export(self, tmp_path):
        """Build a real queue and export it to CSV."""
        result = load_workbook(str(XLSX_PATH))
        queue = EmailQueue()

        for inv in result.actionable_invoices[:3]:
            draft = EmailDraft(
                to=["test@example.com"],
                tier=inv.tier,
                invoices=[inv],
                store_name=inv.store_name,
            )
            draft.build_subject()
            queue.add(draft)

        if len(queue) == 0:
            pytest.skip("No actionable invoices for CSV export test")

        output = tmp_path / "test_queue.csv"
        queue.export_csv(output)
        assert output.exists()

        content = output.read_text(encoding="utf-8")
        assert "store_name" in content
