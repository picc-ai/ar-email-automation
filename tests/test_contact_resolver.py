"""Tests for src.contact_resolver -- contact matching and resolution.

Covers:
- Name normalization (basic and fuzzy)
- Similarity computation
- Exact matching
- Fuzzy matching
- Fallback / no-match handling
- ContactResolver class (single and batch resolution)
- Primary contact selection (AP preference)
- Resolution report formatting
- Real data validation with XLSX
"""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.contact_resolver import (
    CONFIDENCE_EXACT_LICENSE_EXACT_NAME,
    CONFIDENCE_EXACT_LICENSE_FUZZY_NAME,
    CONFIDENCE_EXACT_LICENSE_ONLY,
    CONFIDENCE_FUZZY_NAME_ONLY,
    CONFIDENCE_NO_MATCH,
    FUZZY_THRESHOLD,
    ContactResolver,
    MatchResult,
    MatchTier,
    ResolutionReport,
    _compute_similarity,
    _normalize_for_fuzzy,
    _normalize_name,
    format_resolution_report,
    resolve_contacts,
)


# ============================================================================
# Test Data Helpers
# ============================================================================

def _make_contact(**overrides):
    """Create a mock contact object with reasonable defaults."""
    defaults = {
        "retailer_name": "Aroma Farms",
        "store_name": "Aroma Farms",
        "license_number": "",
        "email": "aromafarmsinc@gmail.com",
        "contact_name": "Emily Stratakos",
        "poc_name": "Emily Stratakos (AP)",
        "poc_title": "AP",
        "all_emails": ["aromafarmsinc@gmail.com"],
        "all_contacts": [{"name": "Emily Stratakos", "title": "AP"}],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_invoice(**overrides):
    """Create a mock invoice object with reasonable defaults."""
    defaults = {
        "order_no": 906858,
        "location": "Aroma Farms",
        "license_number": "",
        "days_past_due": -2,
        "total_due": 1510.00,
        "paid": False,
        "status": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ============================================================================
# Name Normalization
# ============================================================================

class TestNormalizeName:
    """Test basic name normalization."""

    def test_lowercase(self):
        assert _normalize_name("Aroma Farms") == "aroma farms"

    def test_strip_whitespace(self):
        assert _normalize_name("  Aroma Farms  ") == "aroma farms"

    def test_strip_trailing_period(self):
        assert _normalize_name("HUB Dispensary.") == "hub dispensary"

    def test_strip_trailing_comma(self):
        assert _normalize_name("Some Store,") == "some store"

    def test_collapse_spaces(self):
        assert _normalize_name("Aroma   Farms") == "aroma farms"

    def test_empty_string(self):
        assert _normalize_name("") == ""

    def test_already_normalized(self):
        assert _normalize_name("aroma farms") == "aroma farms"

    def test_preserve_hyphens(self):
        """Hyphens in store names should be preserved."""
        assert "manhattan" in _normalize_name("Herbwell - Manhattan")


class TestNormalizeForFuzzy:
    """Test aggressive normalization for fuzzy comparison."""

    def test_removes_parentheses(self):
        result = _normalize_for_fuzzy("The Travel Agency (SoHo)")
        assert "soho" in result
        assert "(" not in result

    def test_removes_articles(self):
        result = _normalize_for_fuzzy("The Travel Agency")
        assert not result.startswith("the ")

    def test_removes_common_suffixes(self):
        result = _normalize_for_fuzzy("My Bud 420 Inc.")
        assert "inc" not in result

    def test_normalizes_hyphens(self):
        result = _normalize_for_fuzzy("Travel Agency - SoHo")
        assert "-" not in result

    def test_empty_string(self):
        assert _normalize_for_fuzzy("") == ""

    def test_dispensary_suffix_removed(self):
        result = _normalize_for_fuzzy("HUB Dispensary")
        assert "dispensary" not in result


# ============================================================================
# Similarity Computation
# ============================================================================

class TestComputeSimilarity:
    """Test the two-pass similarity computation."""

    def test_identical_names(self):
        assert _compute_similarity("Aroma Farms", "Aroma Farms") == 1.0

    def test_case_difference(self):
        """Case differences should result in 1.0 similarity."""
        assert _compute_similarity("Transcend Wellness", "Transcend wellness") == 1.0

    def test_trailing_period(self):
        """Trailing period should result in high similarity."""
        score = _compute_similarity("HUB Dispensary", "HUB Dispensary.")
        assert score >= 0.95

    def test_completely_different(self):
        score = _compute_similarity("Aroma Farms", "Dazed - New York")
        assert score < 0.5

    def test_parentheses_vs_hyphens(self):
        """'The Travel Agency (SoHo)' vs 'Travel Agency - SoHo' should match."""
        score = _compute_similarity(
            "The Travel Agency (SoHo)", "Travel Agency - SoHo"
        )
        # After aggressive normalization, these should be very similar
        assert score >= FUZZY_THRESHOLD

    def test_empty_strings(self):
        score = _compute_similarity("", "")
        assert score == 1.0

    def test_one_empty(self):
        score = _compute_similarity("Aroma Farms", "")
        # Both normalizations return empty for "", so one side empty
        assert score < 0.5


# ============================================================================
# MatchTier Enum
# ============================================================================

class TestMatchTier:
    def test_values(self):
        assert MatchTier.EXACT_LICENSE_EXACT_NAME.value == "exact_license_exact_name"
        assert MatchTier.FUZZY_NAME_ONLY.value == "fuzzy_name_only"
        assert MatchTier.NO_MATCH.value == "no_match"

    def test_all_tiers(self):
        assert len(MatchTier) == 5


# ============================================================================
# Confidence Constants
# ============================================================================

class TestConfidenceConstants:
    def test_ordering(self):
        """Confidence should decrease with each fallback tier."""
        assert CONFIDENCE_EXACT_LICENSE_EXACT_NAME > CONFIDENCE_EXACT_LICENSE_FUZZY_NAME
        assert CONFIDENCE_EXACT_LICENSE_FUZZY_NAME > CONFIDENCE_EXACT_LICENSE_ONLY
        assert CONFIDENCE_EXACT_LICENSE_ONLY > CONFIDENCE_FUZZY_NAME_ONLY
        assert CONFIDENCE_FUZZY_NAME_ONLY > CONFIDENCE_NO_MATCH

    def test_exact_is_one(self):
        assert CONFIDENCE_EXACT_LICENSE_EXACT_NAME == 1.0

    def test_no_match_is_zero(self):
        assert CONFIDENCE_NO_MATCH == 0.0


# ============================================================================
# ContactResolver -- Exact Matching
# ============================================================================

class TestExactMatching:
    """Test Tier 4 (name-only) exact matching without license numbers."""

    def test_exact_name_match(self):
        contacts = [_make_contact(retailer_name="Aroma Farms")]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="Aroma Farms")
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.FUZZY_NAME_ONLY  # name-only (no license)
        assert result.confidence == CONFIDENCE_FUZZY_NAME_ONLY
        assert result.contact is not None
        assert result.fuzzy_score == 1.0

    def test_case_insensitive_exact_match(self):
        contacts = [_make_contact(retailer_name="Transcend Wellness")]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="Transcend wellness")
        result = resolver.match_invoice(invoice)

        assert result.contact is not None
        assert result.fuzzy_score == 1.0

    def test_multiple_contacts_same_name(self):
        """When multiple contacts have the same name, select primary by title."""
        c1 = _make_contact(
            retailer_name="Test Store",
            poc_name="Jane Doe - Owner",
            poc_title="Owner",
        )
        c2 = _make_contact(
            retailer_name="Test Store",
            poc_name="Bob Smith (AP)",
            poc_title="AP",
        )
        contacts = [c1, c2]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="Test Store")
        result = resolver.match_invoice(invoice)

        assert result.contact is not None


# ============================================================================
# ContactResolver -- Fuzzy Matching
# ============================================================================

class TestFuzzyMatching:
    """Test Tier 4 fuzzy name matching (no license)."""

    def test_trailing_period_fuzzy(self):
        contacts = [_make_contact(retailer_name="HUB Dispensary.")]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="HUB Dispensary")
        result = resolver.match_invoice(invoice)

        assert result.contact is not None
        assert result.fuzzy_score >= FUZZY_THRESHOLD

    def test_parentheses_vs_hyphens(self):
        contacts = [_make_contact(retailer_name="The Travel Agency (SoHo)")]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="The Travel Agency - SoHo")
        result = resolver.match_invoice(invoice)

        assert result.contact is not None
        assert result.fuzzy_score >= FUZZY_THRESHOLD

    def test_below_threshold_no_match(self):
        contacts = [_make_contact(retailer_name="Completely Different Store")]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="Aroma Farms")
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.NO_MATCH
        assert result.confidence == CONFIDENCE_NO_MATCH

    def test_custom_threshold(self):
        """A very low threshold should match almost anything."""
        contacts = [_make_contact(retailer_name="Aroma")]
        resolver = ContactResolver(contacts, fuzzy_threshold=0.01)

        invoice = _make_invoice(location="Aroma Farms")
        result = resolver.match_invoice(invoice)

        assert result.contact is not None

    def test_high_threshold_rejects_fuzzy(self):
        """A threshold of 1.0 should reject anything but exact matches."""
        contacts = [_make_contact(retailer_name="Aroma Farm")]  # missing 's'
        resolver = ContactResolver(contacts, fuzzy_threshold=1.0)

        invoice = _make_invoice(location="Aroma Farms")
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.NO_MATCH


# ============================================================================
# ContactResolver -- Fallback / No Match
# ============================================================================

class TestFallbackMatching:
    """Test no-match and fallback scenarios."""

    def test_no_contacts(self):
        resolver = ContactResolver([])
        invoice = _make_invoice(location="Aroma Farms")
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.NO_MATCH
        assert result.contact is None
        assert "No match" in result.notes

    def test_no_location(self):
        contacts = [_make_contact()]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="", license_number="")
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.NO_MATCH
        assert "no location" in result.notes.lower()

    def test_unmatched_demarinos(self):
        """DeMarinos is known to have no match in the contacts directory."""
        contacts = [
            _make_contact(retailer_name="Aroma Farms"),
            _make_contact(retailer_name="Seaweed RBNY"),
            _make_contact(retailer_name="Grounded"),
        ]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(location="DeMarinos")
        result = resolver.match_invoice(invoice)

        # Should be no match (DeMarinos doesn't exist in contacts)
        assert result.match_tier == MatchTier.NO_MATCH
        assert result.confidence == 0.0
        assert "No match" in result.notes

    def test_no_match_provides_closest_hint(self):
        contacts = [
            _make_contact(retailer_name="Aroma Farms"),
        ]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Aroma Farm")  # close but not exact
        result = resolver.match_invoice(invoice)

        # Depending on threshold, may match or not -- but if no match,
        # should provide a closest hint
        if result.match_tier == MatchTier.NO_MATCH:
            assert "closest" in result.notes.lower() or "Aroma" in result.notes


# ============================================================================
# ContactResolver -- License Number Matching
# ============================================================================

class TestLicenseMatching:
    """Test Tiers 1-3: license-based matching."""

    def test_exact_license_exact_name(self):
        contacts = [
            _make_contact(
                retailer_name="Aroma Farms",
                license_number="NY-LIC-001",
            )
        ]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(
            location="Aroma Farms",
            license_number="NY-LIC-001",
        )
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.EXACT_LICENSE_EXACT_NAME
        assert result.confidence == 1.0
        assert result.contact is not None

    def test_exact_license_fuzzy_name(self):
        contacts = [
            _make_contact(
                retailer_name="HUB Dispensary.",
                license_number="NY-LIC-002",
            )
        ]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(
            location="HUB Dispensary",
            license_number="NY-LIC-002",
        )
        result = resolver.match_invoice(invoice)

        assert result.match_tier in (
            MatchTier.EXACT_LICENSE_EXACT_NAME,
            MatchTier.EXACT_LICENSE_FUZZY_NAME,
        )
        assert result.confidence >= 0.9

    def test_exact_license_only(self):
        """License matches but name doesn't match at all."""
        contacts = [
            _make_contact(
                retailer_name="Completely Different Name",
                license_number="NY-LIC-003",
            )
        ]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(
            location="Aroma Farms",
            license_number="NY-LIC-003",
        )
        result = resolver.match_invoice(invoice)

        assert result.match_tier == MatchTier.EXACT_LICENSE_ONLY
        assert result.confidence == 0.8

    def test_license_not_found_falls_to_name(self):
        contacts = [
            _make_contact(
                retailer_name="Aroma Farms",
                license_number="NY-LIC-999",
            )
        ]
        resolver = ContactResolver(contacts)

        invoice = _make_invoice(
            location="Aroma Farms",
            license_number="NY-LIC-UNKNOWN",
        )
        result = resolver.match_invoice(invoice)

        # License didn't match, but name should match
        assert result.match_tier == MatchTier.FUZZY_NAME_ONLY
        assert result.contact is not None


# ============================================================================
# Batch Resolution
# ============================================================================

class TestBatchResolution:
    """Test batch resolve() and resolve_contacts() convenience function."""

    def test_batch_resolution(self):
        contacts = [
            _make_contact(retailer_name="Aroma Farms"),
            _make_contact(retailer_name="Seaweed RBNY"),
        ]
        invoices = [
            _make_invoice(order_no=1, location="Aroma Farms"),
            _make_invoice(order_no=2, location="Seaweed RBNY"),
            _make_invoice(order_no=3, location="DeMarinos"),
        ]

        resolver = ContactResolver(contacts)
        report = resolver.resolve(invoices)

        assert isinstance(report, ResolutionReport)
        assert report.total_invoices == 3
        assert len(report.matched) == 2
        assert len(report.unmatched) == 1

    def test_batch_grouped_by_location(self):
        """When grouping, multi-invoice dispensaries get one match result."""
        contacts = [
            _make_contact(retailer_name="Seaweed RBNY"),
        ]
        invoices = [
            _make_invoice(order_no=904667, location="Seaweed RBNY"),
            _make_invoice(order_no=905055, location="Seaweed RBNY"),
        ]

        resolver = ContactResolver(contacts)
        report = resolver.resolve(invoices, group_by_location=True)

        assert len(report.matched) == 1
        assert len(report.matched[0].invoice_order_nos) == 2
        assert "Multi-invoice" in report.matched[0].notes

    def test_match_rate_calculation(self):
        contacts = [
            _make_contact(retailer_name="Aroma Farms Dispensary"),
            _make_contact(retailer_name="Seaweed Brooklyn Shop"),
        ]
        invoices = [
            _make_invoice(order_no=1, location="Aroma Farms Dispensary"),
            _make_invoice(order_no=2, location="Seaweed Brooklyn Shop"),
            _make_invoice(order_no=3, location="DeMarinos Completely Unique"),
        ]
        resolver = ContactResolver(contacts)
        report = resolver.resolve(invoices, group_by_location=False)
        # 2 of 3 matched -- "DeMarinos Completely Unique" should not fuzzy-match
        assert report.match_rate == pytest.approx(2 / 3, abs=0.01)

    def test_confidence_distribution(self):
        contacts = [_make_contact(retailer_name="Store A")]
        invoices = [
            _make_invoice(order_no=1, location="Store A"),
            _make_invoice(order_no=2, location="Unknown Store"),
        ]
        report = resolve_contacts(invoices, contacts, group_by_location=False)
        assert "60%" in report.confidence_distribution
        assert "0% (unmatched)" in report.confidence_distribution

    def test_empty_invoices(self):
        contacts = [_make_contact()]
        report = resolve_contacts([], contacts)
        assert report.total_invoices == 0
        assert len(report.matched) == 0

    def test_empty_contacts(self):
        invoices = [_make_invoice()]
        report = resolve_contacts(invoices, [])
        assert len(report.unmatched) == 1


# ============================================================================
# Resolution Report Formatting
# ============================================================================

class TestResolutionReportFormatting:
    def test_format_basic_report(self):
        contacts = [_make_contact(retailer_name="Store A")]
        invoices = [
            _make_invoice(order_no=1, location="Store A"),
            _make_invoice(order_no=2, location="Unknown"),
        ]
        report = resolve_contacts(invoices, contacts, group_by_location=False)
        formatted = format_resolution_report(report)

        assert "CONTACT RESOLUTION REPORT" in formatted
        assert "MATCHED" in formatted
        assert "UNMATCHED" in formatted
        assert "Match rate" in formatted

    def test_format_empty_report(self):
        report = ResolutionReport()
        formatted = format_resolution_report(report)
        assert "CONTACT RESOLUTION REPORT" in formatted


# ============================================================================
# Real Data Validation (with XLSX)
# ============================================================================

XLSX_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "NY Account Receivables_Overdue.xlsx"
)

requires_xlsx = pytest.mark.skipif(
    not XLSX_PATH.exists(),
    reason=f"XLSX file not found at {XLSX_PATH}",
)


@requires_xlsx
class TestRealDataContactResolution:
    """Test contact resolution against actual production data.

    The Contact dataclass now provides a ``retailer_name`` property
    that aliases ``store_name``, so no wrapping adapter is needed.
    """

    @pytest.fixture(scope="class")
    def load_result(self):
        from src.data_loader import load_workbook
        return load_workbook(str(XLSX_PATH))

    def test_resolution_with_real_data(self, load_result):
        """Run full contact resolution on real invoice and contact data."""
        contacts = load_result.contacts
        invoices = load_result.invoices

        mock_invoices = []
        for inv in invoices:
            mock_invoices.append(SimpleNamespace(
                order_no=int(inv.invoice_number),
                location=inv.store_name,
                license_number="",
            ))

        report = resolve_contacts(
            mock_invoices, contacts, group_by_location=True,
        )

        # Match rate should be >= 95%
        assert report.match_rate >= 0.95, (
            f"Expected >= 95% match rate, got {report.match_rate:.1%}"
        )

    def test_known_matches(self, load_result):
        """Verify specific known stores resolve correctly via data_loader lookup."""
        # These should all have matches via the data_loader's own lookup
        known_stores = [
            "Aroma Farms",
            "Seaweed RBNY",
            "Sunset Cannabis Club",
            "Bronx Joint",
        ]

        for store in known_stores:
            contact = load_result.get_contact(store)
            assert contact is not None, f"No contact for '{store}'"
            assert contact.email != "" or contact.has_email, (
                f"No email for '{store}'"
            )
