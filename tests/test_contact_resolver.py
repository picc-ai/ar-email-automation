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
- Contact SOP priority chain (Wave 2)
- CC list assembly
- Source trust filtering (Nabis vs Revelry)
- Brand AR Summary fallback
"""

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.contact_resolver import (
    ALWAYS_CC,
    CONFIDENCE_EXACT_LICENSE_EXACT_NAME,
    CONFIDENCE_EXACT_LICENSE_FUZZY_NAME,
    CONFIDENCE_EXACT_LICENSE_ONLY,
    CONFIDENCE_FUZZY_NAME_ONLY,
    CONFIDENCE_NO_MATCH,
    FUZZY_THRESHOLD,
    NO_CONTACT_PLACEHOLDER,
    REP_EMAIL_MAP,
    SOURCE_TRUST,
    ContactResolver,
    MatchResult,
    MatchTier,
    ResolutionReport,
    _compute_similarity,
    _get_source_trust,
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
        "sales_rep": "Ben",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_brand_ar_contact(**overrides):
    """Create a mock Brand AR Summary contact."""
    defaults = {
        "retailer_name": "Test Dispensary",
        "poc_emails": ["test@dispensary.com"],
        "poc_phones": ["John - (555) 555-1234"],
        "retailer_type": "Good",
        "responsiveness": "Responsive",
        "notes": "",
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


# ============================================================================
# Source Trust Hierarchy
# ============================================================================

class TestSourceTrust:
    """Test source trust level classification for associated contacts."""

    def test_nabis_import_is_high(self):
        assert _get_source_trust("Nabis import") == "high"

    def test_nabis_poc_is_high(self):
        assert _get_source_trust("Nabis POC") == "high"

    def test_crm_contact_is_high(self):
        assert _get_source_trust("CRM Contact") == "high"

    def test_nabis_order_poc_is_high(self):
        assert _get_source_trust("Nabis Order, Point of Contact") == "high"

    def test_revelry_is_low(self):
        assert _get_source_trust("Revelry buyers list") == "low"
        assert _get_source_trust("revelry") == "low"

    def test_unknown_source_is_medium(self):
        assert _get_source_trust("Unknown Source") == "medium"

    def test_empty_source_is_medium(self):
        assert _get_source_trust("") == "medium"

    def test_case_insensitive(self):
        assert _get_source_trust("NABIS IMPORT") == "high"
        assert _get_source_trust("REVELRY") == "low"


# ============================================================================
# Contact SOP Priority Chain
# ============================================================================

class TestContactSOPPriorityChain:
    """Test the meeting-defined SOP priority chain for TO recipients."""

    def test_primary_contact_only(self):
        """When only a primary contact exists, TO should contain just that email."""
        contacts = [_make_contact(
            retailer_name="Test Store",
            email="primary@test.com",
            all_emails=["primary@test.com"],
            all_contacts=[{"name": "Jane", "title": "Owner"}],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Test Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "primary@test.com" in result.to_emails
        assert len(result.resolution_chain) > 0
        assert result.contact_source == "managers_sheet"

    def test_primary_plus_billing(self):
        """When both primary and billing contacts exist, TO should contain both."""
        contacts = [_make_contact(
            retailer_name="Test Store",
            email="primary@test.com",
            all_emails=["primary@test.com", "ap@test.com"],
            all_contacts=[
                {"name": "Jane", "title": "Owner"},
                {"name": "Bob", "title": "AP", "email": "ap@test.com"},
            ],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Test Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "primary@test.com" in result.to_emails
        assert "ap@test.com" in result.to_emails

    def test_billing_email_pattern_detected(self):
        """Emails with ap@/accounting@ prefixes should be identified as billing."""
        contacts = [_make_contact(
            retailer_name="Test Store",
            email="owner@test.com",
            all_emails=["owner@test.com", "accounting@test.com"],
            all_contacts=[{"name": "Jane", "title": "Owner"}],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Test Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "owner@test.com" in result.to_emails
        assert "accounting@test.com" in result.to_emails

    def test_no_contacts_found_empty_to(self):
        """When no contact is found at all, to_emails should be empty."""
        resolver = ContactResolver([])
        invoice = _make_invoice(location="Unknown Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert result.to_emails == []
        assert result.contact_source == "manual"
        assert any("No contact found" in s for s in result.resolution_chain)

    def test_brand_ar_summary_fallback(self):
        """When Managers sheet has no match, should fall back to Brand AR Summary."""
        brand_ar = {
            "Fallback Dispensary": _make_brand_ar_contact(
                retailer_name="Fallback Dispensary",
                poc_emails=["fallback@dispensary.com"],
            ),
        }
        resolver = ContactResolver([], brand_ar_contacts=brand_ar)
        invoice = _make_invoice(location="Fallback Dispensary")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "fallback@dispensary.com" in result.to_emails
        assert result.contact_source == "brand_ar_summary"

    def test_brand_ar_summary_fuzzy_match(self):
        """Brand AR Summary should also support fuzzy matching."""
        brand_ar = {
            "Fallback Dispensary.": _make_brand_ar_contact(
                retailer_name="Fallback Dispensary.",
                poc_emails=["fallback@dispensary.com"],
            ),
        }
        resolver = ContactResolver([], brand_ar_contacts=brand_ar)
        invoice = _make_invoice(location="Fallback Dispensary")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "fallback@dispensary.com" in result.to_emails
        assert result.contact_source == "brand_ar_summary"

    def test_managers_sheet_preferred_over_brand_ar(self):
        """When both Managers and Brand AR have the store, prefer Managers."""
        contacts = [_make_contact(
            retailer_name="Dual Store",
            email="managers@dual.com",
            all_emails=["managers@dual.com"],
        )]
        brand_ar = {
            "Dual Store": _make_brand_ar_contact(
                retailer_name="Dual Store",
                poc_emails=["brandar@dual.com"],
            ),
        }
        resolver = ContactResolver(contacts, brand_ar_contacts=brand_ar)
        invoice = _make_invoice(location="Dual Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert "managers@dual.com" in result.to_emails
        assert "brandar@dual.com" not in result.to_emails
        assert result.contact_source == "managers_sheet"

    def test_resolution_chain_audit_trail(self):
        """The resolution_chain should provide a clear audit trail."""
        contacts = [_make_contact(
            retailer_name="Audited Store",
            email="audit@store.com",
            all_emails=["audit@store.com"],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Audited Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        assert len(result.resolution_chain) > 0
        # Should mention Managers sheet match
        assert any("Managers sheet" in s for s in result.resolution_chain)


# ============================================================================
# Source-based Contact Filtering
# ============================================================================

class TestSourceFiltering:
    """Test that Revelry-sourced contacts are deprioritized."""

    def test_nabis_preferred_over_revelry(self):
        """When associated contacts have both Nabis and Revelry sources,
        the Nabis-sourced contact should be used."""
        contacts = [_make_contact(
            retailer_name="Mixed Source Store",
            email="",  # no primary email to force associated contacts path
            all_emails=[],
            all_contacts=[
                {"name": "Rev Contact", "title": "", "email": "rev@store.com",
                 "source": "Revelry buyers list"},
                {"name": "Nabis Contact", "title": "", "email": "nabis@store.com",
                 "source": "Nabis import"},
            ],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Mixed Source Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        # Nabis-sourced should be preferred
        assert "nabis@store.com" in result.to_emails
        # Revelry should not be included when better sources exist
        assert "rev@store.com" not in result.to_emails

    def test_revelry_only_contacts_used_as_fallback(self):
        """When only Revelry-sourced contacts are available, they should still be used."""
        contacts = [_make_contact(
            retailer_name="Revelry Only Store",
            email="",
            all_emails=[],
            all_contacts=[
                {"name": "Rev Contact", "title": "", "email": "rev@store.com",
                 "source": "Revelry buyers list"},
            ],
        )]
        resolver = ContactResolver(contacts)
        invoice = _make_invoice(location="Revelry Only Store")
        result = resolver.match_invoice(invoice)
        result = resolver.resolve_to_recipients(result)

        # Should use Revelry as fallback
        assert "rev@store.com" in result.to_emails
        # But resolution chain should note it's low trust
        assert any("Revelry" in s or "low trust" in s
                    for s in result.resolution_chain)


# ============================================================================
# CC List Assembly
# ============================================================================

class TestCCListAssembly:
    """Test CC list building per the meeting SOP."""

    def test_base_cc_always_included(self):
        """All 4 hardcoded base CC addresses should always be present."""
        resolver = ContactResolver([])
        invoice = _make_invoice(sales_rep="")
        cc = resolver.build_cc_list(invoice)

        assert "ny.ar@nabis.com" in cc
        assert "martinm@piccplatform.com" in cc
        assert "mario@piccplatform.com" in cc
        assert "laura@piccplatform.com" in cc

    def test_sales_rep_email_added(self):
        """The sales rep email should be dynamically added to CC."""
        resolver = ContactResolver([])
        invoice = _make_invoice(sales_rep="Ben")
        cc = resolver.build_cc_list(invoice)

        assert "b.rosenthal@piccplatform.com" in cc

    def test_unknown_rep_not_added(self):
        """An unknown rep name should not add any extra CC."""
        resolver = ContactResolver([])
        invoice = _make_invoice(sales_rep="Unknown Person")
        cc = resolver.build_cc_list(invoice)

        # Should only have the 4 base CCs
        assert len(cc) == 4

    def test_no_duplicate_cc(self):
        """CC list should not contain duplicates."""
        resolver = ContactResolver([])
        # Mario is both a base CC and a rep name
        invoice = _make_invoice(sales_rep="Mario")
        cc = resolver.build_cc_list(invoice)

        # mario@piccplatform.com should appear only once
        mario_count = sum(1 for addr in cc if "mario@piccplatform" in addr.lower())
        assert mario_count == 1

    def test_extra_cc_added(self):
        """Extra CC addresses should be appended."""
        resolver = ContactResolver([])
        invoice = _make_invoice(sales_rep="Ben")
        cc = resolver.build_cc_list(invoice, extra_cc=["extra@example.com"])

        assert "extra@example.com" in cc
        assert "b.rosenthal@piccplatform.com" in cc

    def test_placeholder_tokens_removed(self):
        """Any unresolved {placeholder} tokens should be stripped."""
        resolver = ContactResolver([])
        invoice = _make_invoice(sales_rep="")
        cc = resolver.build_cc_list(invoice, extra_cc=["{rep_email}"])

        assert all("{" not in addr for addr in cc)

    def test_custom_rep_email_map(self):
        """A custom rep email map should override the default."""
        custom_map = {"TestRep": "testrep@company.com"}
        resolver = ContactResolver([], rep_email_map=custom_map)
        invoice = _make_invoice(sales_rep="TestRep")
        cc = resolver.build_cc_list(invoice)

        assert "testrep@company.com" in cc


# ============================================================================
# MatchResult Properties
# ============================================================================

class TestMatchResultProperties:
    """Test the new MatchResult properties."""

    def test_contact_emails_from_to_emails(self):
        """contact_emails should return to_emails if populated."""
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
            to_emails=["a@b.com", "c@d.com"],
        )
        assert result.contact_emails == ["a@b.com", "c@d.com"]

    def test_contact_emails_from_contact_all_emails(self):
        """contact_emails should fall back to contact.all_emails."""
        contact = _make_contact(all_emails=["x@y.com"])
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
            contact=contact,
        )
        assert "x@y.com" in result.contact_emails

    def test_contact_emails_from_contact_email(self):
        """contact_emails should fall back to contact.email."""
        contact = SimpleNamespace(email="single@email.com", all_emails=[])
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
            contact=contact,
        )
        assert result.contact_emails == ["single@email.com"]

    def test_contact_emails_no_contact(self):
        """contact_emails should return empty list when no contact."""
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
        )
        assert result.contact_emails == []

    def test_primary_contact_name(self):
        """primary_contact_name should return the contact's name."""
        contact = _make_contact(contact_name="Emily Stratakos")
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
            contact=contact,
        )
        assert result.primary_contact_name == "Emily Stratakos"

    def test_primary_contact_name_no_contact(self):
        """primary_contact_name should return empty string when no contact."""
        result = MatchResult(
            invoice_order_nos=[1],
            invoice_location="Test",
        )
        assert result.primary_contact_name == ""


# ============================================================================
# Batch Resolution with SOP Chain
# ============================================================================

class TestBatchResolutionWithSOP:
    """Test that batch resolution applies the SOP priority chain."""

    def test_batch_populates_to_emails(self):
        """Batch resolve() should populate to_emails on all results."""
        contacts = [_make_contact(
            retailer_name="Store A",
            email="a@store.com",
            all_emails=["a@store.com"],
        )]
        invoices = [_make_invoice(order_no=1, location="Store A")]

        resolver = ContactResolver(contacts)
        report = resolver.resolve(invoices)

        assert len(report.matched) == 1
        assert "a@store.com" in report.matched[0].to_emails
        assert report.matched[0].contact_source == "managers_sheet"

    def test_batch_unmatched_has_empty_to_emails(self):
        """Unmatched results should have empty to_emails."""
        invoices = [_make_invoice(order_no=1, location="Nonexistent Store")]

        resolver = ContactResolver([])
        report = resolver.resolve(invoices)

        assert len(report.unmatched) == 1
        assert report.unmatched[0].to_emails == []
        assert report.unmatched[0].contact_source == "manual"
