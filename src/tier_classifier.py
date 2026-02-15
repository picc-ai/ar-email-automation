"""
AR Email Tier Classifier

Classifies invoices into email tiers based on days_past_due value.
Each tier determines the email template, urgency level, and CC routing rules.

3-Tier System (consolidated from original 5-tier):
    COMING_DUE:   days_past_due <= 0   (not yet past due; courtesy reminder)
    OVERDUE:      days_past_due 1-29   (friendly reminder, static "overdue")
    PAST_DUE:     days_past_due >= 30  (OCM warning, formal tone, dynamic subject)

Subject lines for 30+ use dynamic buckets: 30+, 40+, 50+, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Tier Enum
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    """
    AR collection tiers ordered by escalation severity.

    3-tier system. Subject lines for 30+ use dynamic bucket labels.
    """
    COMING_DUE = "Coming Due"
    OVERDUE = "Overdue"
    PAST_DUE = "30+ Days Past Due"


# ---------------------------------------------------------------------------
# Configurable Tier Boundaries
# ---------------------------------------------------------------------------
# These thresholds define the *lower bound* (inclusive) for each tier.
# Adjust these if business rules change. The upper bound is implicitly
# the next tier's lower bound minus one.

TIER_BOUNDARY_OVERDUE: int = 1          # Day 1 starts the "Overdue" window
TIER_BOUNDARY_PAST_DUE_30: int = 30    # Day 30 starts the "30+ Days Past Due" window

# OCM (Office of Cannabis Management) regulatory deadlines referenced in
# the Past Due email templates.
OCM_NOTIFICATION_DAY: int = 45     # Nabis sends their own notification
OCM_REPORTING_DAY: int = 52        # Nabis required to report to OCM


# ---------------------------------------------------------------------------
# Urgency Levels
# ---------------------------------------------------------------------------

class UrgencyLevel(str, Enum):
    """Urgency classification used for routing, prioritization, and display."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    SEVERE = "severe"


# ---------------------------------------------------------------------------
# CC Rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CCRules:
    """
    Defines who gets CC'd on an email for a given tier.

    Attributes:
        include_nabis_ar: Always CC ny.ar@nabis.com
        include_core_team: CC Mario, Martin, Laura (PICC internal)
        include_sales_rep: CC the assigned sales rep for the store
        include_nabis_am: Explicitly CC the Nabis Account Manager
        include_additional_retailer_contacts: Loop in extra store contacts (AP, owners)
        include_additional_picc_managers: Loop in senior PICC staff beyond core team
    """
    include_nabis_ar: bool = True
    include_core_team: bool = True
    include_sales_rep: bool = True
    include_nabis_am: bool = False
    include_additional_retailer_contacts: bool = False
    include_additional_picc_managers: bool = False


# ---------------------------------------------------------------------------
# Tier Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierMetadata:
    """
    All metadata associated with a single AR tier.

    Attributes:
        tier: The tier enum value.
        template_name: Identifier for the email template to use.
        urgency_level: How urgent this tier is considered.
        cc_rules: Who to CC on outbound emails.
        subject_label: The exact string appended to the email subject line.
        includes_ocm_warning: Whether the template body references OCM reporting.
        days_until_ocm_report: Approximate days remaining before the 52-day
            OCM reporting deadline, calculated from the tier's lower bound.
            None if not applicable.
        description: Human-readable description of this tier.
        recommended_follow_up: Guidance for manual follow-up actions.
    """
    tier: Tier
    template_name: str
    urgency_level: UrgencyLevel
    cc_rules: CCRules
    subject_label: str
    includes_ocm_warning: bool
    days_until_ocm_report: Optional[int]
    description: str
    recommended_follow_up: str


# Pre-built metadata for each tier (3-tier system).
TIER_METADATA: dict[Tier, TierMetadata] = {
    Tier.COMING_DUE: TierMetadata(
        tier=Tier.COMING_DUE,
        template_name="coming_due",
        urgency_level=UrgencyLevel.LOW,
        cc_rules=CCRules(
            include_nabis_ar=True,
            include_core_team=True,
            include_sales_rep=True,
            include_nabis_am=False,
            include_additional_retailer_contacts=False,
            include_additional_picc_managers=False,
        ),
        subject_label="Coming Due",
        includes_ocm_warning=False,
        days_until_ocm_report=None,
        description=(
            "Courtesy reminder sent before the invoice due date. "
            "Soft tone, no urgency language, ACH form attached."
        ),
        recommended_follow_up="None required. Monitor for payment after due date.",
    ),

    Tier.OVERDUE: TierMetadata(
        tier=Tier.OVERDUE,
        template_name="overdue",
        urgency_level=UrgencyLevel.MODERATE,
        cc_rules=CCRules(
            include_nabis_ar=True,
            include_core_team=True,
            include_sales_rep=True,
            include_nabis_am=False,
            include_additional_retailer_contacts=False,
            include_additional_picc_managers=False,
        ),
        subject_label="Overdue",
        includes_ocm_warning=False,
        days_until_ocm_report=None,
        description=(
            "Friendly reminder acknowledging the invoice is past due. "
            "Uses static 'overdue' phrasing. "
            "Covers days 1-29 past due."
        ),
        recommended_follow_up="Monitor. Follow up manually if no response within 7 days.",
    ),

    Tier.PAST_DUE: TierMetadata(
        tier=Tier.PAST_DUE,
        template_name="past_due_30",
        urgency_level=UrgencyLevel.HIGH,
        cc_rules=CCRules(
            include_nabis_ar=True,
            include_core_team=True,
            include_sales_rep=True,
            include_nabis_am=True,
            include_additional_retailer_contacts=False,
            include_additional_picc_managers=False,
        ),
        subject_label="30+ Days Past Due",
        includes_ocm_warning=True,
        days_until_ocm_report=22,  # 52 - 30
        description=(
            "Formal reminder referencing OCM reporting policy. "
            "Mentions 45-day Nabis notification and 52-day mandatory OCM report. "
            "Nabis AM is explicitly CC'd. Subject line uses dynamic bucket label."
        ),
        recommended_follow_up="Ensure Nabis AM is engaged. Verify correct contact info.",
    ),
}


# ---------------------------------------------------------------------------
# Classification Result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """
    The result of classifying a single invoice.

    Attributes:
        tier: The assigned tier.
        metadata: Full tier metadata (template, urgency, CC rules, etc.).
        days_past_due: The raw days_past_due value that was classified.
        days_until_ocm: Exact days until the 52-day OCM reporting deadline
            for this specific invoice. None if not yet past due.
        is_past_ocm_deadline: True if the invoice has exceeded 52 days.
        input_was_null: True if the original input was None (treated as COMING_DUE).
    """
    tier: Tier
    metadata: TierMetadata
    days_past_due: int
    days_until_ocm: Optional[int]
    is_past_ocm_deadline: bool
    input_was_null: bool = False


# ---------------------------------------------------------------------------
# Core Classification Functions
# ---------------------------------------------------------------------------

def classify(days_past_due: Optional[int | float]) -> ClassificationResult:
    """
    Classify a single invoice into an AR tier based on days_past_due.

    Args:
        days_past_due: Number of days past the invoice due date.
            - Negative values mean the invoice is not yet due.
            - Zero means the invoice is due today (classified as COMING_DUE).
            - None / NaN is treated as COMING_DUE with a flag.

    Returns:
        ClassificationResult with the tier assignment and all metadata.

    Examples:
        >>> result = classify(-3)
        >>> result.tier
        <Tier.COMING_DUE: 'Coming Due'>

        >>> result = classify(15)
        >>> result.tier
        <Tier.OVERDUE: 'Overdue'>

        >>> result = classify(35)
        >>> result.tier
        <Tier.PAST_DUE: '30+ Days Past Due'>

        >>> result = classify(75)
        >>> result.tier
        <Tier.PAST_DUE: '30+ Days Past Due'>
        >>> result.is_past_ocm_deadline
        True
    """
    input_was_null = False

    # Handle None and NaN
    if days_past_due is None:
        input_was_null = True
        days_past_due = 0
    elif isinstance(days_past_due, float):
        if days_past_due != days_past_due:  # NaN check (NaN != NaN)
            input_was_null = True
            days_past_due = 0
        else:
            days_past_due = int(days_past_due)

    days_past_due = int(days_past_due)

    # Determine tier (3-tier system)
    if days_past_due >= TIER_BOUNDARY_PAST_DUE_30:
        tier = Tier.PAST_DUE
    elif days_past_due >= TIER_BOUNDARY_OVERDUE:
        tier = Tier.OVERDUE
    else:
        # days_past_due <= 0: not yet due, or due today
        tier = Tier.COMING_DUE

    # Calculate OCM-specific fields
    if days_past_due > 0:
        days_until_ocm = max(0, OCM_REPORTING_DAY - days_past_due)
        is_past_ocm_deadline = days_past_due >= OCM_REPORTING_DAY
    else:
        days_until_ocm = None
        is_past_ocm_deadline = False

    return ClassificationResult(
        tier=tier,
        metadata=TIER_METADATA[tier],
        days_past_due=days_past_due,
        days_until_ocm=days_until_ocm,
        is_past_ocm_deadline=is_past_ocm_deadline,
        input_was_null=input_was_null,
    )


def classify_batch(
    invoices: list[dict[str, Any]],
    days_field: str = "days_past_due",
    *,
    skip_paid: bool = True,
    paid_field: str = "paid",
    skip_payment_enroute: bool = True,
    status_field: str = "status",
) -> list[dict[str, Any]]:
    """
    Classify a batch of invoice dicts, adding tier info to each one.

    Each invoice dict is augmented in-place with the following keys:
        - tier: Tier enum value
        - tier_label: Human-readable tier label (str)
        - template_name: Email template identifier (str)
        - urgency_level: UrgencyLevel enum value
        - days_until_ocm: int or None
        - is_past_ocm_deadline: bool
        - cc_rules: CCRules dataclass instance
        - _skipped: bool (True if the invoice was excluded from email sends)
        - _skip_reason: str or None (why it was skipped)

    Args:
        invoices: List of invoice dicts. Each must have a days_past_due field
            (or whatever ``days_field`` is set to).
        days_field: Key in each dict that holds the days_past_due value.
        skip_paid: If True, mark invoices with paid=True as skipped.
        paid_field: Key for the paid boolean.
        skip_payment_enroute: If True, mark invoices with status="Payment Enroute"
            as skipped.
        status_field: Key for the status string.

    Returns:
        The same list of invoice dicts, each augmented with tier metadata.
        Skipped invoices are included in the output but flagged.

    Examples:
        >>> invoices = [
        ...     {"order_no": "906858", "days_past_due": -2, "paid": False, "status": None},
        ...     {"order_no": "903480", "days_past_due": 27, "paid": False, "status": None},
        ...     {"order_no": "906551", "days_past_due": 2, "paid": True, "status": None},
        ...     {"order_no": "902925", "days_past_due": 31, "paid": False, "status": "Payment Enroute"},
        ... ]
        >>> results = classify_batch(invoices)
        >>> results[0]["tier_label"]
        'Coming Due'
        >>> results[1]["tier_label"]
        'Overdue'
        >>> results[2]["_skipped"]
        True
        >>> results[2]["_skip_reason"]
        'paid'
        >>> results[3]["_skipped"]
        True
        >>> results[3]["_skip_reason"]
        'payment_enroute'
    """
    for invoice in invoices:
        # --- Skip logic ---
        skip_reason = _get_skip_reason(
            invoice,
            skip_paid=skip_paid,
            paid_field=paid_field,
            skip_payment_enroute=skip_payment_enroute,
            status_field=status_field,
        )

        if skip_reason is not None:
            invoice["_skipped"] = True
            invoice["_skip_reason"] = skip_reason
            # Still classify so the tier info is available for reporting
            # even on skipped invoices.
        else:
            invoice["_skipped"] = False
            invoice["_skip_reason"] = None

        # --- Classify ---
        days_value = invoice.get(days_field)
        result = classify(days_value)

        invoice["tier"] = result.tier
        invoice["tier_label"] = result.tier.value
        invoice["template_name"] = result.metadata.template_name
        invoice["urgency_level"] = result.metadata.urgency_level
        invoice["days_until_ocm"] = result.days_until_ocm
        invoice["is_past_ocm_deadline"] = result.is_past_ocm_deadline
        invoice["cc_rules"] = result.metadata.cc_rules
        invoice["subject_label"] = result.metadata.subject_label
        invoice["includes_ocm_warning"] = result.metadata.includes_ocm_warning
        invoice["recommended_follow_up"] = result.metadata.recommended_follow_up

    return invoices


def _get_skip_reason(
    invoice: dict[str, Any],
    *,
    skip_paid: bool,
    paid_field: str,
    skip_payment_enroute: bool,
    status_field: str,
) -> Optional[str]:
    """
    Determine whether an invoice should be skipped for email sending.

    Returns a reason string if the invoice should be skipped, or None if
    it should be processed.
    """
    # Check paid status
    if skip_paid:
        paid_value = invoice.get(paid_field)
        if paid_value is True or (
            isinstance(paid_value, str) and paid_value.lower() in ("true", "yes", "1", "paid")
        ):
            return "paid"

    # Check payment enroute
    if skip_payment_enroute:
        status_value = invoice.get(status_field)
        if isinstance(status_value, str) and status_value.strip().lower() == "payment enroute":
            return "payment_enroute"

    return None


# ---------------------------------------------------------------------------
# Dynamic Subject Label Generator
# ---------------------------------------------------------------------------

def get_dynamic_subject_label(days_past_due: int) -> str:
    """
    Compute the dynamic subject line label for email subject lines.

    Returns 'Coming Due' for <=0, 'Overdue' for 1-29,
    and '{N}0+ Days Past Due' for 30+ (where N is the decade bucket).

    Examples:
        >>> get_dynamic_subject_label(-2)
        'Coming Due'
        >>> get_dynamic_subject_label(15)
        'Overdue'
        >>> get_dynamic_subject_label(35)
        '30+ Days Past Due'
        >>> get_dynamic_subject_label(45)
        '40+ Days Past Due'
        >>> get_dynamic_subject_label(52)
        '50+ Days Past Due'
        >>> get_dynamic_subject_label(111)
        '110+ Days Past Due'
    """
    if days_past_due <= 0:
        return "Coming Due"
    if days_past_due <= 29:
        return "Overdue"
    bucket = (days_past_due // 10) * 10
    return f"{bucket}+ Days Past Due"


# ---------------------------------------------------------------------------
# Batch Summary / Reporting Helpers
# ---------------------------------------------------------------------------

def summarize_batch(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Produce a summary of a classified batch, grouped by tier.

    Useful for dashboards, reports, and pre-send review.

    Args:
        invoices: List of invoice dicts that have already been processed
            by classify_batch().

    Returns:
        A summary dict with tier counts, totals, and skip stats.

    Example:
        >>> invoices = classify_batch([
        ...     {"days_past_due": -2, "total_due": 1510.00, "paid": False, "status": None},
        ...     {"days_past_due": 15, "total_due": 2565.00, "paid": False, "status": None},
        ...     {"days_past_due": 35, "total_due": 2602.00, "paid": False, "status": None},
        ... ])
        >>> summary = summarize_batch(invoices)
        >>> summary["total_invoices"]
        3
        >>> summary["total_skipped"]
        0
    """
    summary: dict[str, Any] = {
        "total_invoices": len(invoices),
        "total_skipped": 0,
        "total_actionable": 0,
        "tiers": {},
    }

    for tier in Tier:
        summary["tiers"][tier.value] = {
            "count": 0,
            "actionable_count": 0,
            "skipped_count": 0,
            "total_due": 0.0,
            "invoices": [],
        }

    for inv in invoices:
        tier_label = inv.get("tier_label")
        if tier_label is None:
            continue

        tier_data = summary["tiers"].get(tier_label)
        if tier_data is None:
            continue

        tier_data["count"] += 1
        tier_data["total_due"] += inv.get("total_due", 0.0) or 0.0

        if inv.get("_skipped"):
            tier_data["skipped_count"] += 1
            summary["total_skipped"] += 1
        else:
            tier_data["actionable_count"] += 1
            summary["total_actionable"] += 1

        tier_data["invoices"].append(inv.get("order_no", "unknown"))

    return summary


# ---------------------------------------------------------------------------
# Convenience: get tier for a single value without full result object
# ---------------------------------------------------------------------------

def get_tier(days_past_due: Optional[int | float]) -> Tier:
    """
    Quick lookup: return just the Tier enum for a given days_past_due value.

    Args:
        days_past_due: Number of days past due. None/NaN returns COMING_DUE.

    Returns:
        The Tier enum value.

    Examples:
        >>> get_tier(-5)
        <Tier.COMING_DUE: 'Coming Due'>
        >>> get_tier(0)
        <Tier.COMING_DUE: 'Coming Due'>
        >>> get_tier(1)
        <Tier.OVERDUE: 'Overdue'>
        >>> get_tier(29)
        <Tier.OVERDUE: 'Overdue'>
        >>> get_tier(30)
        <Tier.PAST_DUE: '30+ Days Past Due'>
        >>> get_tier(40)
        <Tier.PAST_DUE: '30+ Days Past Due'>
        >>> get_tier(50)
        <Tier.PAST_DUE: '30+ Days Past Due'>
        >>> get_tier(111)
        <Tier.PAST_DUE: '30+ Days Past Due'>
        >>> get_tier(None)
        <Tier.COMING_DUE: 'Coming Due'>
    """
    return classify(days_past_due).tier


def get_metadata(tier: Tier) -> TierMetadata:
    """
    Retrieve the full metadata for a tier.

    Args:
        tier: A Tier enum value.

    Returns:
        The TierMetadata dataclass for that tier.
    """
    return TIER_METADATA[tier]


# ---------------------------------------------------------------------------
# Module self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Validate against known data -- 3-tier system
    test_cases = [
        # (days_past_due, expected_tier, description)
        (-5, Tier.COMING_DUE, "DeMarinos: -5 days"),
        (-4, Tier.COMING_DUE, "Valley Greens LTD: -4 days"),
        (-3, Tier.COMING_DUE, "THTree: -3 days"),
        (-2, Tier.COMING_DUE, "Aroma Farms: -2 days"),
        (-1, Tier.COMING_DUE, "Union Chill: -1 days"),
        (0, Tier.COMING_DUE, "Due today edge case"),
        (1, Tier.OVERDUE, "Blissful Buds: 1 day"),
        (2, Tier.OVERDUE, "Grounded: 2 days"),
        (12, Tier.OVERDUE, "Hudson Charisma: 12 days"),
        (16, Tier.OVERDUE, "Terp Bros: 16 days"),
        (17, Tier.OVERDUE, "Seaweed RBNY: 17 days"),
        (25, Tier.OVERDUE, "Canna Buddha: 25 days"),
        (27, Tier.OVERDUE, "Kushmart: 27 days"),
        (29, Tier.OVERDUE, "Upper bound of Overdue"),
        (30, Tier.PAST_DUE, "Lower bound of 30+"),
        (31, Tier.PAST_DUE, "Royal Blend: 31 days"),
        (37, Tier.PAST_DUE, "Flowery Bronx: 37 days"),
        (39, Tier.PAST_DUE, "Herbwell - Manhattan: 39 days"),
        (40, Tier.PAST_DUE, "40 days (was separate tier, now 30+)"),
        (49, Tier.PAST_DUE, "49 days (was separate tier, now 30+)"),
        (50, Tier.PAST_DUE, "50 days (was separate tier, now 30+)"),
        (52, Tier.PAST_DUE, "My Bud 420: 52 days (at OCM deadline)"),
        (67, Tier.PAST_DUE, "DISPO: 67 days"),
        (80, Tier.PAST_DUE, "Paradise Cannabis: 80 days"),
        (108, Tier.PAST_DUE, "Flynnstoned Brooklyn: 108 days"),
        (111, Tier.PAST_DUE, "Dazed / Travel Agency SoHo: 111 days"),
        (None, Tier.COMING_DUE, "Null input"),
        (float("nan"), Tier.COMING_DUE, "NaN input"),
    ]

    print("=" * 70)
    print("AR Tier Classifier - Self-Test (3-Tier System)")
    print("=" * 70)

    all_passed = True
    for days, expected_tier, desc in test_cases:
        result = classify(days)
        passed = result.tier == expected_tier
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(
            f"  [{status}] days={str(days):>5s}  ->  {result.tier.value:<22s}  "
            f"(expected {expected_tier.value:<22s})  # {desc}"
        )

    print("-" * 70)

    # Test dynamic subject labels
    print("\nDynamic Subject Labels:")
    for d in [0, 1, 15, 29, 30, 35, 39, 40, 45, 49, 50, 52, 75, 111]:
        print(f"  {d:>3d} days -> \"{get_dynamic_subject_label(d)}\"")

    print("-" * 70)

    # Test batch classification
    sample_invoices = [
        {"order_no": "906858", "location": "Aroma Farms", "days_past_due": -2,
         "total_due": 1510.00, "paid": False, "status": None},
        {"order_no": "903480", "location": "Long Island CC", "days_past_due": 27,
         "total_due": 2565.00, "paid": False, "status": None},
        {"order_no": "902925", "location": "Royal Blend", "days_past_due": 31,
         "total_due": 2602.00, "paid": False, "status": None},
        {"order_no": "902398", "location": "Herbwell", "days_past_due": 39,
         "total_due": 1337.50, "paid": False, "status": None},
        {"order_no": "893271", "location": "Travel Agency SoHo", "days_past_due": 111,
         "total_due": 1552.55, "paid": False, "status": None},
        {"order_no": "906551", "location": "Grounded", "days_past_due": 2,
         "total_due": 3752.00, "paid": True, "status": None},
        {"order_no": "X99999", "location": "Enroute Co", "days_past_due": 5,
         "total_due": 1000.00, "paid": False, "status": "Payment Enroute"},
    ]

    results = classify_batch(sample_invoices)
    summary = summarize_batch(results)

    print(f"\nBatch Classification ({summary['total_invoices']} invoices):")
    print(f"  Actionable: {summary['total_actionable']}")
    print(f"  Skipped:    {summary['total_skipped']}")
    print()
    for tier_label, tier_data in summary["tiers"].items():
        if tier_data["count"] > 0:
            print(
                f"  {tier_label:<22s}  "
                f"count={tier_data['count']}  "
                f"actionable={tier_data['actionable_count']}  "
                f"skipped={tier_data['skipped_count']}  "
                f"total_due=${tier_data['total_due']:,.2f}"
            )

    print()
    print("Skipped invoices:")
    for inv in results:
        if inv.get("_skipped"):
            print(f"  {inv['order_no']} ({inv['location']}): {inv['_skip_reason']}")

    print()
    print("OCM deadline status:")
    for inv in results:
        if inv.get("days_until_ocm") is not None:
            ocm_status = "PAST DEADLINE" if inv["is_past_ocm_deadline"] else f"{inv['days_until_ocm']} days remaining"
            print(f"  {inv['order_no']} ({inv['location']}): {inv['days_past_due']}d overdue -> {ocm_status}")

    print("=" * 70)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 70)
