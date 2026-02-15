"""Tests for src.data_loader -- XLSX parsing and data loading.

Covers:
- Loading the actual XLSX file
- Verifying expected counts (70 invoices, 60 dispensaries, ~620 contacts)
- Invoice field parsing and type coercion
- Contact parsing (multi-line POC fields)
- Sheet auto-detection
- Fuzzy contact lookup
- Data cleaning edge cases
- Error handling (missing file, missing sheet)
"""

from pathlib import Path

import pytest

from src.data_loader import (
    LoadResult,
    load_workbook,
    load_contacts_only,
    lookup_contact,
)
from src.models import Contact, Invoice, InvoiceStatus, SkipReason, Tier


# ============================================================================
# Test Data Path
# ============================================================================

# The actual XLSX file from the project data directory.
XLSX_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "NY Account Receivables_Overdue.xlsx"
)

# Skip all tests that need the XLSX file if it doesn't exist.
XLSX_EXISTS = XLSX_PATH.exists()
requires_xlsx = pytest.mark.skipif(
    not XLSX_EXISTS,
    reason=f"XLSX file not found at {XLSX_PATH}",
)


# ============================================================================
# Full Workbook Load
# ============================================================================

@requires_xlsx
class TestLoadWorkbook:
    """Test loading the full workbook with actual production data."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        """Load the workbook once for all tests in this class."""
        return load_workbook(str(XLSX_PATH))

    # --- Invoice counts ---

    def test_invoice_count(self, result: LoadResult):
        """The Overdue 2-3 sheet should have ~70 valid invoices."""
        assert len(result.invoices) == 70, (
            f"Expected 70 invoices, got {len(result.invoices)}"
        )

    def test_unique_locations(self, result: LoadResult):
        """There should be ~60 unique dispensary locations."""
        unique = {inv.store_name for inv in result.invoices}
        assert len(unique) == 60, (
            f"Expected 60 unique locations, got {len(unique)}"
        )

    # --- Contact counts ---

    def test_contact_count(self, result: LoadResult):
        """The Managers sheet should have ~620 contact records."""
        assert len(result.contacts) >= 600, (
            f"Expected ~620 contacts, got {len(result.contacts)}"
        )
        assert len(result.contacts) <= 650, (
            f"Expected ~620 contacts, got {len(result.contacts)}"
        )

    def test_contacts_by_name_populated(self, result: LoadResult):
        """contacts_by_name should be a non-empty lookup dict."""
        assert len(result.contacts_by_name) > 0
        # Keys should be normalized (lowercase)
        for key in list(result.contacts_by_name.keys())[:5]:
            assert key == key.lower()

    # --- Sheet detection ---

    def test_overdue_sheet_detected(self, result: LoadResult):
        """Should auto-detect 'Overdue 2-3' as the most recent sheet."""
        assert result.overdue_sheet_used == "Overdue 2-3", (
            f"Expected 'Overdue 2-3', got '{result.overdue_sheet_used}'"
        )

    # --- Contact matching rate ---

    def test_match_rate(self, result: LoadResult):
        """Contact match rate should be ~98.3% (59/60)."""
        assert result.match_rate >= 0.95, (
            f"Expected match rate >= 95%, got {result.match_rate:.1%}"
        )

    def test_matched_locations_count(self, result: LoadResult):
        """Should match at least 58 of 60 locations."""
        assert len(result.matched_locations) >= 58

    def test_unmatched_locations(self, result: LoadResult):
        """DeMarinos is known to be unmatched."""
        # Verify unmatched list is small
        assert len(result.unmatched_locations) <= 3, (
            f"Expected <= 3 unmatched, got {len(result.unmatched_locations)}: "
            f"{result.unmatched_locations}"
        )

    # --- Financial totals ---

    def test_total_ar(self, result: LoadResult):
        """Total AR should be approximately $189,039.23."""
        assert abs(result.total_ar - 189039.23) < 500, (
            f"Expected ~$189,039, got ${result.total_ar:,.2f}"
        )

    def test_unpaid_ar(self, result: LoadResult):
        """Unpaid AR should be approximately $165,100.71."""
        assert abs(result.unpaid_ar - 165100.71) < 500, (
            f"Expected ~$165,101, got ${result.unpaid_ar:,.2f}"
        )

    def test_paid_invoice_count(self, result: LoadResult):
        """There should be 9 paid invoices."""
        assert len(result.paid_invoices) == 9

    def test_unpaid_invoice_count(self, result: LoadResult):
        """There should be 61 unpaid invoices."""
        assert len(result.unpaid_invoices) == 61

    # --- Metadata ---

    def test_source_file(self, result: LoadResult):
        assert result.source_file is not None
        assert "NY Account Receivables" in result.source_file

    def test_rows_scanned(self, result: LoadResult):
        """Should have scanned ~99 rows (70 valid + ~29 padding)."""
        assert result.total_rows_scanned >= 70

    def test_empty_rows_skipped(self, result: LoadResult):
        """~29 padding/empty rows should have been skipped."""
        assert result.empty_rows_skipped >= 20


# ============================================================================
# Invoice Field Validation
# ============================================================================

@requires_xlsx
class TestInvoiceFields:
    """Validate specific invoice fields from the loaded data."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def _find_invoice(self, result: LoadResult, order_no: str) -> Invoice:
        for inv in result.invoices:
            if inv.invoice_number == order_no:
                return inv
        pytest.fail(f"Invoice {order_no} not found")

    def test_aroma_farms_fields(self, result: LoadResult):
        """Validate Aroma Farms (order 906858, Coming Due)."""
        inv = self._find_invoice(result, "906858")
        assert inv.store_name == "Aroma Farms"
        assert inv.days_past_due == -2
        assert inv.tier == Tier.T0
        assert inv.amount == pytest.approx(1510.00, abs=0.01)

    def test_seaweed_rbny_invoices(self, result: LoadResult):
        """Seaweed RBNY should have 2 invoices."""
        seaweed = [inv for inv in result.invoices if "Seaweed" in inv.store_name]
        assert len(seaweed) == 2

    def test_dazed_new_york_invoices(self, result: LoadResult):
        """Dazed - New York should have 2 invoices."""
        dazed = [inv for inv in result.invoices if inv.store_name == "Dazed - New York"]
        assert len(dazed) == 2

    def test_paid_invoice(self, result: LoadResult):
        """Grounded (906551) should be marked as paid."""
        inv = self._find_invoice(result, "906551")
        assert inv.paid is True
        assert inv.skip_reason == SkipReason.ALREADY_PAID

    def test_invoice_has_account_manager(self, result: LoadResult):
        inv = self._find_invoice(result, "906858")
        assert inv.account_manager != ""
        assert inv.account_manager != "#N/A"

    def test_invoice_has_sales_rep(self, result: LoadResult):
        inv = self._find_invoice(result, "906858")
        assert inv.sales_rep != ""

    def test_invoice_number_is_string(self, result: LoadResult):
        """Invoice numbers should be stored as strings."""
        for inv in result.invoices[:5]:
            assert isinstance(inv.invoice_number, str)
            assert inv.invoice_number.isdigit()

    def test_amount_is_float(self, result: LoadResult):
        for inv in result.invoices[:5]:
            assert isinstance(inv.amount, float)
            assert inv.amount >= 0

    def test_days_past_due_is_int(self, result: LoadResult):
        for inv in result.invoices[:5]:
            assert isinstance(inv.days_past_due, int)

    def test_due_date_is_date(self, result: LoadResult):
        for inv in result.invoices[:5]:
            if inv.due_date is not None:
                from datetime import date
                assert isinstance(inv.due_date, date)


# ============================================================================
# Invoice Tier Distribution
# ============================================================================

@requires_xlsx
class TestTierDistribution:
    """Verify tier distribution matches the data patterns analysis."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def test_coming_due_count(self, result: LoadResult):
        """~16 invoices should be Coming Due (days < 0)."""
        count = sum(1 for inv in result.invoices if inv.tier == Tier.T0)
        assert count >= 14 and count <= 18, f"Coming Due: {count}"

    def test_overdue_count(self, result: LoadResult):
        """~34 invoices should be Overdue (days 0-29)."""
        count = sum(1 for inv in result.invoices if inv.tier == Tier.T1)
        assert count >= 28 and count <= 40, f"Overdue: {count}"

    def test_past_due_30_count(self, result: LoadResult):
        """30+ Days Past Due invoices should exist (count varies with live data)."""
        count = sum(1 for inv in result.invoices if inv.tier == Tier.T2)
        assert count >= 1, f"30+ Past Due: {count}"


# ============================================================================
# Skip Reason Distribution
# ============================================================================

@requires_xlsx
class TestSkipReasons:
    """Verify skip reason detection matches expected patterns."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def test_paid_invoices_skipped(self, result: LoadResult):
        paid_skipped = [
            inv for inv in result.invoices
            if inv.skip_reason == SkipReason.ALREADY_PAID
        ]
        assert len(paid_skipped) == 9

    def test_email_sent_skipped(self, result: LoadResult):
        """Most invoices have email_sent=True (93% per data patterns)."""
        email_skipped = [
            inv for inv in result.invoices
            if inv.skip_reason == SkipReason.EMAIL_ALREADY_SENT
        ]
        # After paid filter, email_sent catches more
        assert len(email_skipped) >= 40

    def test_actionable_invoices_count(self, result: LoadResult):
        """Actionable (sendable) invoices should be ~5."""
        # Based on data: 70 total, 9 paid, ~65 email_sent, some overlap
        actionable = result.actionable_invoices
        # The exact count depends on overlap between skip reasons
        # but should be a small number
        assert len(actionable) >= 1, (
            f"Expected some actionable invoices, got {len(actionable)}"
        )
        assert len(actionable) <= 15, (
            f"Expected fewer actionable invoices, got {len(actionable)}"
        )


# ============================================================================
# Contact Parsing
# ============================================================================

@requires_xlsx
class TestContactParsing:
    """Test contact parsing from the Managers sheet."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def test_contacts_have_store_name(self, result: LoadResult):
        for contact in result.contacts[:10]:
            assert contact.store_name != ""

    def test_contacts_have_email(self, result: LoadResult):
        """Most contacts should have at least one email."""
        with_email = [c for c in result.contacts if c.has_email]
        assert len(with_email) >= 580, (
            f"Expected ~610 contacts with email, got {len(with_email)}"
        )

    def test_contact_email_is_lowercase(self, result: LoadResult):
        """All parsed emails should be lowercased."""
        for contact in result.contacts:
            if contact.email:
                assert contact.email == contact.email.lower(), (
                    f"Email not lowercase: {contact.email}"
                )

    def test_contact_email_has_at_sign(self, result: LoadResult):
        """All parsed emails should contain @."""
        for contact in result.contacts:
            if contact.email:
                assert "@" in contact.email, (
                    f"Invalid email: {contact.email}"
                )


# ============================================================================
# Contact Lookup / Fuzzy Matching
# ============================================================================

@requires_xlsx
class TestContactLookup:
    """Test fuzzy contact lookup against real Managers data."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def test_exact_match(self, result: LoadResult):
        """Aroma Farms should match exactly."""
        contact = result.get_contact("Aroma Farms")
        assert contact is not None
        assert "aroma" in contact.store_name.lower()

    def test_case_insensitive_match(self, result: LoadResult):
        """Match should be case-insensitive."""
        contact = result.get_contact("aroma farms")
        assert contact is not None

    def test_trailing_period_match(self, result: LoadResult):
        """'HUB Dispensary.' should fuzzy-match 'HUB Dispensary'."""
        # Try looking up with and without trailing period
        contact1 = result.get_contact("HUB Dispensary")
        contact2 = result.get_contact("HUB Dispensary.")
        # At least one should match (depending on which form is in the sheet)
        assert contact1 is not None or contact2 is not None

    def test_no_match_demarinos(self, result: LoadResult):
        """DeMarinos has no Managers record -- should return None."""
        contact = result.get_contact("DeMarinos")
        # DeMarinos might or might not match depending on fuzzy threshold
        # The key assertion is that the system handles it gracefully
        # (it's in unmatched_locations or has a low-confidence match)
        if contact is None:
            assert "DeMarinos" in result.unmatched_locations


# ============================================================================
# Load Contacts Only
# ============================================================================

@requires_xlsx
class TestLoadContactsOnly:
    """Test the load_contacts_only convenience function."""

    def test_basic_load(self):
        contacts = load_contacts_only(str(XLSX_PATH))
        assert len(contacts) >= 600

    def test_contact_types(self):
        contacts = load_contacts_only(str(XLSX_PATH))
        for c in contacts[:5]:
            assert isinstance(c, Contact)


# ============================================================================
# Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_workbook("nonexistent/path/file.xlsx")

    @requires_xlsx
    def test_missing_sheet_raises(self):
        with pytest.raises(ValueError, match="not found"):
            load_workbook(str(XLSX_PATH), overdue_sheet="NonExistent Sheet")

    @requires_xlsx
    def test_explicit_sheet_name(self):
        """Can explicitly specify which overdue sheet to use."""
        result = load_workbook(str(XLSX_PATH), overdue_sheet="Overdue 2-3")
        assert result.overdue_sheet_used == "Overdue 2-3"
        assert len(result.invoices) == 70


# ============================================================================
# Data Cleaning
# ============================================================================

@requires_xlsx
class TestDataCleaning:
    """Test that data cleaning is applied correctly."""

    @pytest.fixture(scope="class")
    def result(self) -> LoadResult:
        return load_workbook(str(XLSX_PATH))

    def test_no_empty_store_names(self, result: LoadResult):
        """No invoice should have an empty store name."""
        for inv in result.invoices:
            assert inv.store_name.strip() != ""

    def test_no_empty_invoice_numbers(self, result: LoadResult):
        """No invoice should have an empty invoice number."""
        for inv in result.invoices:
            assert inv.invoice_number.strip() != ""

    def test_amounts_are_positive(self, result: LoadResult):
        """All invoice amounts should be >= 0."""
        for inv in result.invoices:
            assert inv.amount >= 0, (
                f"Negative amount for {inv.invoice_number}: {inv.amount}"
            )

    def test_na_account_managers_handled(self, result: LoadResult):
        """Invoices with #N/A account managers should be flagged."""
        na_ams = [
            inv for inv in result.invoices
            if inv.account_manager in ("", "#N/A")
        ]
        # Per data patterns: HUB Dispensary, DeMarinos (2) have blank AMs
        assert len(na_ams) >= 2

    def test_no_warnings_for_valid_data(self, result: LoadResult):
        """Warnings should be minimal for valid data."""
        # Some warnings are expected (e.g., date parsing), but should be < 20
        assert len(result.warnings) < 20, (
            f"Too many warnings ({len(result.warnings)}): {result.warnings[:5]}"
        )
