"""Tests for src.tier_classifier -- tier classification engine.

Covers:
- Single invoice classification (classify function)
- Every tier boundary (exact boundary values, +-1)
- Edge cases: 0 days, negative days, 999 days, None, NaN, float
- Overdue timeframe descriptions
- Batch classification with skip filters
- Batch summary reporting
- Convenience functions (get_tier, get_metadata)
- OCM deadline calculations
"""

import math
from typing import Any

import pytest

from src.tier_classifier import (
    CCRules,
    ClassificationResult,
    Tier,
    TierMetadata,
    TIER_METADATA,
    TIER_BOUNDARY_OVERDUE,
    TIER_BOUNDARY_PAST_DUE_30,
    TIER_BOUNDARY_PAST_DUE_40,
    TIER_BOUNDARY_PAST_DUE_50,
    OCM_NOTIFICATION_DAY,
    OCM_REPORTING_DAY,
    UrgencyLevel,
    classify,
    classify_batch,
    get_overdue_timeframe_description,
    get_tier,
    get_metadata,
    summarize_batch,
)


# ============================================================================
# Constants Validation
# ============================================================================

class TestConstants:
    """Verify tier boundary constants match the business rules."""

    def test_overdue_boundary(self):
        assert TIER_BOUNDARY_OVERDUE == 1

    def test_past_due_30_boundary(self):
        assert TIER_BOUNDARY_PAST_DUE_30 == 30

    def test_past_due_40_boundary(self):
        assert TIER_BOUNDARY_PAST_DUE_40 == 40

    def test_past_due_50_boundary(self):
        assert TIER_BOUNDARY_PAST_DUE_50 == 50

    def test_ocm_notification_day(self):
        assert OCM_NOTIFICATION_DAY == 45

    def test_ocm_reporting_day(self):
        assert OCM_REPORTING_DAY == 52


# ============================================================================
# Tier Enum
# ============================================================================

class TestTierEnum:
    def test_tier_values(self):
        assert Tier.COMING_DUE.value == "Coming Due"
        assert Tier.OVERDUE.value == "Overdue"
        assert Tier.PAST_DUE_30.value == "30+ Days Past Due"
        assert Tier.PAST_DUE_40.value == "40+ Days Past Due"
        assert Tier.PAST_DUE_50.value == "50+ Days Past Due"

    def test_tier_is_string_enum(self):
        """Tier inherits from str, so values can be compared as strings."""
        assert isinstance(Tier.COMING_DUE, str)
        # The .value property gives the string representation
        assert Tier.COMING_DUE.value == "Coming Due"


# ============================================================================
# Single Classification (classify)
# ============================================================================

class TestClassifySingle:
    """Test the classify() function for single invoice classification."""

    # --- Tier boundaries: exact values ---

    @pytest.mark.parametrize("days,expected_tier", [
        # Coming Due: < 1 (i.e., <= 0)
        (-100, Tier.COMING_DUE),
        (-5, Tier.COMING_DUE),
        (-1, Tier.COMING_DUE),
        (0, Tier.COMING_DUE),

        # Overdue: 1-29
        (1, Tier.OVERDUE),
        (2, Tier.OVERDUE),
        (15, Tier.OVERDUE),
        (29, Tier.OVERDUE),

        # Past Due 30+: 30-39
        (30, Tier.PAST_DUE_30),
        (35, Tier.PAST_DUE_30),
        (39, Tier.PAST_DUE_30),

        # Past Due 40+: 40-49
        (40, Tier.PAST_DUE_40),
        (45, Tier.PAST_DUE_40),
        (49, Tier.PAST_DUE_40),

        # Past Due 50+: >= 50
        (50, Tier.PAST_DUE_50),
        (52, Tier.PAST_DUE_50),
        (75, Tier.PAST_DUE_50),
        (111, Tier.PAST_DUE_50),
        (999, Tier.PAST_DUE_50),
    ])
    def test_tier_assignment(self, days, expected_tier):
        result = classify(days)
        assert result.tier == expected_tier
        assert result.days_past_due == days

    # --- Boundary transitions (N-1 -> N) ---

    def test_boundary_overdue_transition(self):
        """Day 0 is COMING_DUE, day 1 is OVERDUE."""
        assert classify(0).tier == Tier.COMING_DUE
        assert classify(1).tier == Tier.OVERDUE

    def test_boundary_past_due_30_transition(self):
        """Day 29 is OVERDUE, day 30 is PAST_DUE_30."""
        assert classify(29).tier == Tier.OVERDUE
        assert classify(30).tier == Tier.PAST_DUE_30

    def test_boundary_past_due_40_transition(self):
        """Day 39 is PAST_DUE_30, day 40 is PAST_DUE_40."""
        assert classify(39).tier == Tier.PAST_DUE_30
        assert classify(40).tier == Tier.PAST_DUE_40

    def test_boundary_past_due_50_transition(self):
        """Day 49 is PAST_DUE_40, day 50 is PAST_DUE_50."""
        assert classify(49).tier == Tier.PAST_DUE_40
        assert classify(50).tier == Tier.PAST_DUE_50

    # --- Edge cases ---

    def test_zero_days(self):
        result = classify(0)
        assert result.tier == Tier.COMING_DUE
        assert result.days_past_due == 0
        assert result.input_was_null is False

    def test_negative_days(self):
        result = classify(-5)
        assert result.tier == Tier.COMING_DUE
        assert result.days_past_due == -5
        assert result.days_until_ocm is None
        assert result.is_past_ocm_deadline is False

    def test_very_large_days(self):
        result = classify(999)
        assert result.tier == Tier.PAST_DUE_50
        assert result.is_past_ocm_deadline is True
        assert result.days_until_ocm == 0

    def test_none_input(self):
        result = classify(None)
        assert result.tier == Tier.COMING_DUE
        assert result.input_was_null is True
        assert result.days_past_due == 0

    def test_nan_input(self):
        result = classify(float("nan"))
        assert result.tier == Tier.COMING_DUE
        assert result.input_was_null is True

    def test_float_input(self):
        result = classify(35.7)
        assert result.tier == Tier.PAST_DUE_30
        assert result.days_past_due == 35  # truncated to int

    def test_negative_float_input(self):
        result = classify(-2.5)
        assert result.tier == Tier.COMING_DUE
        assert result.days_past_due == -2  # truncated toward zero

    # --- Result structure ---

    def test_result_has_metadata(self):
        result = classify(15)
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.metadata, TierMetadata)
        assert result.metadata.tier == Tier.OVERDUE

    def test_result_metadata_matches_tier(self):
        for days, expected_tier in [(-2, Tier.COMING_DUE), (15, Tier.OVERDUE),
                                     (35, Tier.PAST_DUE_30), (45, Tier.PAST_DUE_40),
                                     (75, Tier.PAST_DUE_50)]:
            result = classify(days)
            assert result.metadata.tier == expected_tier
            assert result.metadata == TIER_METADATA[expected_tier]


# ============================================================================
# OCM Deadline Calculations
# ============================================================================

class TestOCMDeadline:
    """Test OCM (Office of Cannabis Management) deadline calculations."""

    def test_coming_due_no_ocm(self):
        result = classify(-3)
        assert result.days_until_ocm is None
        assert result.is_past_ocm_deadline is False

    def test_overdue_has_ocm_countdown(self):
        result = classify(15)
        assert result.days_until_ocm == 52 - 15  # 37
        assert result.is_past_ocm_deadline is False

    def test_at_ocm_deadline(self):
        result = classify(52)
        assert result.days_until_ocm == 0
        assert result.is_past_ocm_deadline is True

    def test_past_ocm_deadline(self):
        result = classify(111)
        assert result.days_until_ocm == 0
        assert result.is_past_ocm_deadline is True

    def test_day_51_before_ocm(self):
        result = classify(51)
        assert result.days_until_ocm == 1
        assert result.is_past_ocm_deadline is False

    def test_day_1_ocm_countdown(self):
        result = classify(1)
        assert result.days_until_ocm == 51


# ============================================================================
# Tier Metadata
# ============================================================================

class TestTierMetadata:
    """Test the TIER_METADATA dictionary for completeness."""

    def test_all_tiers_have_metadata(self):
        for tier in Tier:
            assert tier in TIER_METADATA

    def test_metadata_template_names(self):
        assert TIER_METADATA[Tier.COMING_DUE].template_name == "coming_due"
        assert TIER_METADATA[Tier.OVERDUE].template_name == "overdue"
        assert TIER_METADATA[Tier.PAST_DUE_30].template_name == "past_due_30"
        assert TIER_METADATA[Tier.PAST_DUE_40].template_name == "past_due_40"
        assert TIER_METADATA[Tier.PAST_DUE_50].template_name == "past_due_50"

    def test_metadata_urgency_levels(self):
        assert TIER_METADATA[Tier.COMING_DUE].urgency_level == UrgencyLevel.LOW
        assert TIER_METADATA[Tier.OVERDUE].urgency_level == UrgencyLevel.MODERATE
        assert TIER_METADATA[Tier.PAST_DUE_30].urgency_level == UrgencyLevel.HIGH
        assert TIER_METADATA[Tier.PAST_DUE_40].urgency_level == UrgencyLevel.CRITICAL
        assert TIER_METADATA[Tier.PAST_DUE_50].urgency_level == UrgencyLevel.SEVERE

    def test_metadata_subject_labels(self):
        assert TIER_METADATA[Tier.COMING_DUE].subject_label == "Coming Due"
        assert TIER_METADATA[Tier.OVERDUE].subject_label == "Overdue"
        assert TIER_METADATA[Tier.PAST_DUE_30].subject_label == "30+ Days Past Due"
        assert TIER_METADATA[Tier.PAST_DUE_40].subject_label == "40+ Days Past Due"
        assert TIER_METADATA[Tier.PAST_DUE_50].subject_label == "50+ Days Past Due"

    def test_ocm_warning_tiers(self):
        assert TIER_METADATA[Tier.COMING_DUE].includes_ocm_warning is False
        assert TIER_METADATA[Tier.OVERDUE].includes_ocm_warning is False
        assert TIER_METADATA[Tier.PAST_DUE_30].includes_ocm_warning is True
        assert TIER_METADATA[Tier.PAST_DUE_40].includes_ocm_warning is True
        assert TIER_METADATA[Tier.PAST_DUE_50].includes_ocm_warning is True

    def test_cc_rules_type(self):
        for tier in Tier:
            assert isinstance(TIER_METADATA[tier].cc_rules, CCRules)

    def test_past_due_50_includes_additional_contacts(self):
        cc = TIER_METADATA[Tier.PAST_DUE_50].cc_rules
        assert cc.include_additional_retailer_contacts is True
        assert cc.include_additional_picc_managers is True

    def test_coming_due_no_additional_contacts(self):
        cc = TIER_METADATA[Tier.COMING_DUE].cc_rules
        assert cc.include_additional_retailer_contacts is False
        assert cc.include_nabis_am is False


# ============================================================================
# Overdue Timeframe Description
# ============================================================================

class TestOverdueTimeframeDescription:
    """Test get_overdue_timeframe_description for the T2 (Overdue) tier."""

    @pytest.mark.parametrize("days,expected_phrase", [
        (0, "due soon"),
        (-1, "due soon"),
        (1, "now past due"),
        (2, "now past due"),
        (3, "now past due"),
        (4, "over a week past due"),
        (8, "over a week past due"),
        (10, "over a week past due"),
        (11, "nearing two weeks past due"),
        (12, "nearing two weeks past due"),
        (13, "nearing two weeks past due"),
        (14, "over two weeks past due"),
        (15, "over two weeks past due"),
        (20, "over two weeks past due"),
        (21, "over three weeks past due"),
        (22, "over three weeks past due"),
        (27, "over three weeks past due"),
        (28, "nearing a month past due"),
        (29, "nearing a month past due"),
    ])
    def test_timeframe_phrase(self, days, expected_phrase):
        assert get_overdue_timeframe_description(days) == expected_phrase

    def test_beyond_overdue_range(self):
        """Days > 29 should still return a reasonable phrase."""
        phrase = get_overdue_timeframe_description(35)
        assert "weeks past due" in phrase

    def test_zero_returns_due_soon(self):
        assert get_overdue_timeframe_description(0) == "due soon"


# ============================================================================
# Batch Classification
# ============================================================================

class TestClassifyBatch:
    """Test classify_batch for processing multiple invoices at once."""

    def _make_invoice_dict(self, **overrides) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "order_no": "906858",
            "location": "Aroma Farms",
            "days_past_due": -2,
            "total_due": 1510.00,
            "paid": False,
            "status": None,
        }
        defaults.update(overrides)
        return defaults

    def test_basic_classification(self):
        invoices = [
            self._make_invoice_dict(days_past_due=-2),
            self._make_invoice_dict(order_no="903480", days_past_due=27),
            self._make_invoice_dict(order_no="902925", days_past_due=31),
        ]
        results = classify_batch(invoices)
        assert len(results) == 3
        assert results[0]["tier_label"] == "Coming Due"
        assert results[1]["tier_label"] == "Overdue"
        assert results[2]["tier_label"] == "30+ Days Past Due"

    def test_skip_paid(self):
        invoices = [
            self._make_invoice_dict(paid=True),
        ]
        results = classify_batch(invoices)
        assert results[0]["_skipped"] is True
        assert results[0]["_skip_reason"] == "paid"

    def test_skip_payment_enroute(self):
        invoices = [
            self._make_invoice_dict(status="Payment Enroute"),
        ]
        results = classify_batch(invoices)
        assert results[0]["_skipped"] is True
        assert results[0]["_skip_reason"] == "payment_enroute"

    def test_skip_payment_enroute_case_insensitive(self):
        invoices = [
            self._make_invoice_dict(status="  payment enroute  "),
        ]
        results = classify_batch(invoices)
        assert results[0]["_skipped"] is True

    def test_no_skip_when_not_paid(self):
        invoices = [
            self._make_invoice_dict(paid=False, status=None),
        ]
        results = classify_batch(invoices)
        assert results[0]["_skipped"] is False
        assert results[0]["_skip_reason"] is None

    def test_skip_disabled(self):
        """When skip flags are disabled, paid/enroute invoices are not skipped."""
        invoices = [
            self._make_invoice_dict(paid=True),
            self._make_invoice_dict(status="Payment Enroute"),
        ]
        results = classify_batch(invoices, skip_paid=False, skip_payment_enroute=False)
        assert results[0]["_skipped"] is False
        assert results[1]["_skipped"] is False

    def test_batch_augments_in_place(self):
        invoices = [self._make_invoice_dict()]
        results = classify_batch(invoices)
        # Results should be the same list objects
        assert results is invoices
        assert "tier" in invoices[0]
        assert "tier_label" in invoices[0]
        assert "template_name" in invoices[0]

    def test_batch_adds_all_fields(self):
        invoices = [self._make_invoice_dict(days_past_due=35)]
        classify_batch(invoices)
        inv = invoices[0]
        assert "tier" in inv
        assert "tier_label" in inv
        assert "template_name" in inv
        assert "urgency_level" in inv
        assert "days_until_ocm" in inv
        assert "is_past_ocm_deadline" in inv
        assert "cc_rules" in inv
        assert "subject_label" in inv
        assert "includes_ocm_warning" in inv

    def test_batch_empty_list(self):
        results = classify_batch([])
        assert results == []

    def test_batch_custom_field_names(self):
        invoices = [
            {"days": 15, "is_paid": False, "invoice_status": None},
        ]
        results = classify_batch(
            invoices,
            days_field="days",
            paid_field="is_paid",
            status_field="invoice_status",
        )
        assert results[0]["tier_label"] == "Overdue"

    def test_batch_paid_string_variations(self):
        """Test that paid field handles various truthy string formats."""
        for paid_value in [True, "true", "True", "TRUE", "yes", "1", "paid"]:
            invoices = [self._make_invoice_dict(paid=paid_value)]
            results = classify_batch(invoices)
            assert results[0]["_skipped"] is True, f"Failed for paid={paid_value}"

    def test_batch_mixed_skip_and_classify(self):
        """Skipped invoices still get tier classification for reporting."""
        invoices = [
            self._make_invoice_dict(order_no="1", days_past_due=15, paid=True),
            self._make_invoice_dict(order_no="2", days_past_due=35, paid=False),
        ]
        results = classify_batch(invoices)
        # Paid invoice is skipped but still classified
        assert results[0]["_skipped"] is True
        assert results[0]["tier_label"] == "Overdue"
        # Unpaid invoice is not skipped
        assert results[1]["_skipped"] is False
        assert results[1]["tier_label"] == "30+ Days Past Due"


# ============================================================================
# Batch Summary
# ============================================================================

class TestSummarizeBatch:
    """Test the summarize_batch reporting function."""

    def test_summary_structure(self):
        invoices = [
            {"order_no": "1", "days_past_due": -2, "total_due": 1510.00,
             "paid": False, "status": None},
            {"order_no": "2", "days_past_due": 15, "total_due": 2565.00,
             "paid": False, "status": None},
        ]
        classify_batch(invoices)
        summary = summarize_batch(invoices)

        assert summary["total_invoices"] == 2
        assert summary["total_skipped"] == 0
        assert summary["total_actionable"] == 2
        assert "tiers" in summary

    def test_summary_tier_counts(self):
        invoices = [
            {"order_no": "1", "days_past_due": -2, "total_due": 1000, "paid": False, "status": None},
            {"order_no": "2", "days_past_due": -1, "total_due": 1000, "paid": False, "status": None},
            {"order_no": "3", "days_past_due": 15, "total_due": 2000, "paid": False, "status": None},
        ]
        classify_batch(invoices)
        summary = summarize_batch(invoices)

        assert summary["tiers"]["Coming Due"]["count"] == 2
        assert summary["tiers"]["Overdue"]["count"] == 1

    def test_summary_with_skipped(self):
        invoices = [
            {"order_no": "1", "days_past_due": 5, "total_due": 1000, "paid": True, "status": None},
            {"order_no": "2", "days_past_due": 5, "total_due": 2000, "paid": False, "status": None},
        ]
        classify_batch(invoices)
        summary = summarize_batch(invoices)
        assert summary["total_skipped"] == 1
        assert summary["total_actionable"] == 1

    def test_summary_empty(self):
        summary = summarize_batch([])
        assert summary["total_invoices"] == 0


# ============================================================================
# Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    """Test get_tier() and get_metadata()."""

    @pytest.mark.parametrize("days,expected", [
        (-5, Tier.COMING_DUE),
        (0, Tier.COMING_DUE),
        (1, Tier.OVERDUE),
        (29, Tier.OVERDUE),
        (30, Tier.PAST_DUE_30),
        (39, Tier.PAST_DUE_30),
        (40, Tier.PAST_DUE_40),
        (49, Tier.PAST_DUE_40),
        (50, Tier.PAST_DUE_50),
        (111, Tier.PAST_DUE_50),
        (None, Tier.COMING_DUE),
    ])
    def test_get_tier(self, days, expected):
        assert get_tier(days) == expected

    def test_get_metadata(self):
        meta = get_metadata(Tier.OVERDUE)
        assert meta.template_name == "overdue"
        assert meta.urgency_level == UrgencyLevel.MODERATE

    def test_get_metadata_all_tiers(self):
        for tier in Tier:
            meta = get_metadata(tier)
            assert meta.tier == tier


# ============================================================================
# Real Data Validation
# ============================================================================

class TestRealDataScenarios:
    """Test classification against known invoices from the XLSX analysis."""

    @pytest.mark.parametrize("order_no,days,expected_tier,description", [
        ("906858", -2, Tier.COMING_DUE, "Aroma Farms"),
        ("907173", -4, Tier.COMING_DUE, "Bronx Joint"),
        ("906906", -4, Tier.COMING_DUE, "Valley Greens LTD"),
        ("906898", -3, Tier.COMING_DUE, "THTree"),
        ("906467", -1, Tier.COMING_DUE, "Union Chill"),
        ("910841", 1, Tier.OVERDUE, "Blissful Buds"),
        ("906551", 2, Tier.OVERDUE, "Grounded"),
        ("904667", 17, Tier.OVERDUE, "Seaweed RBNY"),
        ("905055", 19, Tier.OVERDUE, "Seaweed RBNY #2"),
        ("903480", 27, Tier.OVERDUE, "Long Island Cannabis Club"),
        ("902925", 31, Tier.PAST_DUE_30, "Royal Blend Dispensary"),
        ("902398", 39, Tier.PAST_DUE_30, "Herbwell - Manhattan"),
        ("893271", 111, Tier.PAST_DUE_50, "The Travel Agency - SoHo"),
        ("893281", 111, Tier.PAST_DUE_50, "Dazed - New York"),
    ])
    def test_real_invoice(self, order_no, days, expected_tier, description):
        result = classify(days)
        assert result.tier == expected_tier, (
            f"Order {order_no} ({description}): {days}d -> "
            f"expected {expected_tier.value}, got {result.tier.value}"
        )
