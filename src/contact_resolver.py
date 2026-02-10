"""Contact Resolver for AR Email Automation.

Matches overdue invoices to retailer contact records using a multi-tier
matching strategy. The primary matching key is License Number + Store Name,
as identified by Travis as the critical link for accuracy. When license
numbers are unavailable (current XLSX lacks them), the resolver falls back
to store-name-only matching with fuzzy matching support.

Matching strategy (priority order):
    1. Exact License Number + Exact Store Name   -> 100% confidence
    2. Exact License Number + Fuzzy Store Name    ->  90% confidence
    3. Exact License Number only                  ->  80% confidence
    4. Fuzzy Store Name only                      ->  60% confidence
    5. No match                                   ->   0% (manual review)

Uses difflib.SequenceMatcher for fuzzy matching (no external dependencies).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum similarity ratio (0.0-1.0) for a fuzzy store name match to be
# considered valid. Tuned to handle known variations like:
#   "HUB Dispensary" vs "HUB Dispensary."        -> ratio ~0.97
#   "Transcend Wellness" vs "Transcend wellness"  -> ratio  1.0 (after lower)
#   "The Travel Agency (SoHo)" vs "Travel Agency - SoHo" -> ratio ~0.72
FUZZY_THRESHOLD: float = 0.70

# Confidence scores for each match tier
CONFIDENCE_EXACT_LICENSE_EXACT_NAME: float = 1.00
CONFIDENCE_EXACT_LICENSE_FUZZY_NAME: float = 0.90
CONFIDENCE_EXACT_LICENSE_ONLY: float = 0.80
CONFIDENCE_FUZZY_NAME_ONLY: float = 0.60
CONFIDENCE_NO_MATCH: float = 0.00


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class MatchTier(Enum):
    """Describes how an invoice was matched to a contact."""
    EXACT_LICENSE_EXACT_NAME = "exact_license_exact_name"
    EXACT_LICENSE_FUZZY_NAME = "exact_license_fuzzy_name"
    EXACT_LICENSE_ONLY = "exact_license_only"
    FUZZY_NAME_ONLY = "fuzzy_name_only"
    NO_MATCH = "no_match"


@dataclass
class MatchResult:
    """Result of matching a single invoice (or invoice group) to a contact.

    Attributes:
        invoice_order_nos: The order number(s) for the matched invoice(s).
        invoice_location: The Location value from the overdue sheet.
        contact: The resolved Contact object, or None if unmatched.
        confidence: Float 0.0-1.0 representing match confidence.
        match_tier: Which tier of the matching strategy produced this result.
        fuzzy_score: The SequenceMatcher ratio if fuzzy matching was used.
        matched_contact_name: The retailer name from the Managers sheet that
            was matched (may differ slightly from invoice location).
        notes: Human-readable notes about the match for audit/review.
    """
    invoice_order_nos: list[int]
    invoice_location: str
    contact: object | None = None  # Will be a Contact dataclass instance
    confidence: float = 0.0
    match_tier: MatchTier = MatchTier.NO_MATCH
    fuzzy_score: float = 0.0
    matched_contact_name: str = ""
    notes: str = ""


@dataclass
class ResolutionReport:
    """Summary report from a full contact resolution run.

    Attributes:
        matched: Successfully matched invoice-contact pairs.
        unmatched: Invoices that could not be matched to any contact.
        total_invoices: Total number of invoices processed.
        match_rate: Percentage of invoices successfully matched.
        confidence_distribution: Count of matches per confidence tier.
    """
    matched: list[MatchResult] = field(default_factory=list)
    unmatched: list[MatchResult] = field(default_factory=list)
    total_invoices: int = 0
    match_rate: float = 0.0
    confidence_distribution: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Name normalization helpers
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a store name for comparison.

    Applies the following transformations:
    - Lowercase
    - Strip leading/trailing whitespace
    - Remove trailing punctuation (periods, commas)
    - Collapse multiple spaces into one
    - Normalize common separators (parentheses to hyphens)

    Examples:
        >>> _normalize_name("HUB Dispensary.")
        'hub dispensary'
        >>> _normalize_name("Transcend wellness")
        'transcend wellness'
        >>> _normalize_name("  Aroma  Farms  ")
        'aroma farms'
    """
    if not name:
        return ""
    result = name.strip().lower()
    # Remove trailing punctuation
    result = result.rstrip(".,;:")
    # Collapse multiple whitespace
    result = re.sub(r"\s+", " ", result)
    return result


def _normalize_for_fuzzy(name: str) -> str:
    """Aggressive normalization for fuzzy comparison.

    Beyond basic normalization, this also:
    - Strips common articles ("the")
    - Normalizes parenthesized location qualifiers to hyphens
    - Removes all punctuation except hyphens and spaces
    - Strips "dispensary", "cannabis", "inc" suffixes for core comparison

    Examples:
        >>> _normalize_for_fuzzy("The Travel Agency (SoHo)")
        'travel agency soho'
        >>> _normalize_for_fuzzy("Travel Agency - SoHo")
        'travel agency soho'
        >>> _normalize_for_fuzzy("My Bud 420 Inc.")
        'my bud 420'
    """
    if not name:
        return ""
    result = name.strip().lower()
    # Replace parenthesized content with hyphen-separated equivalent
    # "(SoHo)" -> "- SoHo" before further processing
    result = re.sub(r"\s*\(([^)]+)\)\s*", r" \1 ", result)
    # Remove hyphens and extra separators, replace with spaces
    result = re.sub(r"\s*[-/]\s*", " ", result)
    # Remove all remaining punctuation except alphanumeric and spaces
    result = re.sub(r"[^\w\s]", "", result)
    # Remove common articles from start
    result = re.sub(r"^the\s+", "", result)
    # Remove common suffixes that don't help matching
    result = re.sub(r"\s+(inc|llc|ltd|corp|dispensary|cannabis|club)\s*$", "", result)
    # Collapse whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _compute_similarity(name_a: str, name_b: str) -> float:
    """Compute the similarity ratio between two store names.

    Uses a two-pass approach:
    1. Basic normalized comparison (preserves structure)
    2. Aggressive normalized comparison (strips noise)
    Returns the higher of the two scores.

    Args:
        name_a: First store name (e.g., from invoice).
        name_b: Second store name (e.g., from contacts).

    Returns:
        Float between 0.0 and 1.0 representing similarity.
    """
    # Pass 1: basic normalization
    norm_a = _normalize_name(name_a)
    norm_b = _normalize_name(name_b)
    if norm_a == norm_b:
        return 1.0
    basic_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()

    # Pass 2: aggressive normalization
    fuzzy_a = _normalize_for_fuzzy(name_a)
    fuzzy_b = _normalize_for_fuzzy(name_b)
    if fuzzy_a == fuzzy_b:
        return 1.0
    fuzzy_ratio = SequenceMatcher(None, fuzzy_a, fuzzy_b).ratio()

    return max(basic_ratio, fuzzy_ratio)


# ---------------------------------------------------------------------------
# Contact selection helpers
# ---------------------------------------------------------------------------

def _select_primary_contact(contacts: list) -> object | None:
    """Select the primary contact when a retailer has multiple contacts.

    Priority order:
    1. Contact with "(AP)" or "Accounting" or "accounts payable" in title
       (best for AR/collections emails)
    2. Contact with "Owner" or "Manager" in title
    3. First listed contact (default)

    Args:
        contacts: List of Contact objects for a single retailer.

    Returns:
        The selected primary Contact, or None if the list is empty.
    """
    if not contacts:
        return None
    if len(contacts) == 1:
        return contacts[0]

    # Score each contact based on title relevance for AR emails
    def _ar_relevance_score(contact) -> int:
        """Higher score = more relevant for AR emails."""
        poc_name = ""
        # Handle the POC name field which may contain title info
        if hasattr(contact, "poc_name") and contact.poc_name:
            poc_name = contact.poc_name.lower()
        # Also check a dedicated title field if it exists
        poc_title = ""
        if hasattr(contact, "poc_title") and contact.poc_title:
            poc_title = contact.poc_title.lower()

        combined = f"{poc_name} {poc_title}"

        if "(ap)" in combined or "accounts payable" in combined:
            return 100
        if "accounting" in combined or "invoic" in combined:
            return 90
        if "finance" in combined or "billing" in combined:
            return 80
        if "owner" in combined:
            return 50
        if "manager" in combined or "gm" in combined:
            return 40
        return 10

    ranked = sorted(contacts, key=_ar_relevance_score, reverse=True)
    return ranked[0]


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def _build_license_index(contacts: list) -> dict[str, list]:
    """Build an index from license_number -> list of Contact objects.

    Contacts without a license number are excluded from this index.
    The license number is normalized (stripped, uppercased) as the key.

    Args:
        contacts: List of Contact objects.

    Returns:
        Dict mapping normalized license numbers to lists of contacts.
    """
    index: dict[str, list] = {}
    for contact in contacts:
        license_num = getattr(contact, "license_number", None)
        if not license_num or str(license_num).strip() in ("", "None", "#N/A"):
            continue
        key = str(license_num).strip().upper()
        if key not in index:
            index[key] = []
        index[key].append(contact)
    return index


def _build_name_index(contacts: list) -> dict[str, list]:
    """Build an index from normalized retailer_name -> list of Contact objects.

    Uses basic normalization (lowercase, strip punctuation) as the key.

    Args:
        contacts: List of Contact objects.

    Returns:
        Dict mapping normalized retailer names to lists of contacts.
    """
    index: dict[str, list] = {}
    for contact in contacts:
        retailer_name = getattr(contact, "retailer_name", None)
        if not retailer_name or str(retailer_name).strip() == "":
            continue
        key = _normalize_name(str(retailer_name))
        if key not in index:
            index[key] = []
        index[key].append(contact)
    return index


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------

class ContactResolver:
    """Resolves invoice-to-contact matches using tiered matching strategy.

    The resolver pre-indexes contacts by license number and store name
    for efficient lookups, then applies matching tiers in priority order.

    Usage:
        resolver = ContactResolver(contacts)
        report = resolver.resolve(invoices)

        for match in report.matched:
            print(f"{match.invoice_location} -> {match.matched_contact_name} "
                  f"({match.confidence:.0%})")

        for miss in report.unmatched:
            print(f"UNMATCHED: {miss.invoice_location} - {miss.notes}")
    """

    def __init__(
        self,
        contacts: list,
        fuzzy_threshold: float = FUZZY_THRESHOLD,
    ) -> None:
        """Initialize the resolver with a contact directory.

        Args:
            contacts: List of Contact objects (from Managers sheet).
            fuzzy_threshold: Minimum SequenceMatcher ratio for fuzzy
                matches (default 0.70).
        """
        self.contacts = contacts
        self.fuzzy_threshold = fuzzy_threshold

        # Build lookup indexes
        self._license_index = _build_license_index(contacts)
        self._name_index = _build_name_index(contacts)

        # Pre-compute all normalized names for fuzzy scanning
        self._name_candidates: list[tuple[str, str, list]] = []
        for contact in contacts:
            retailer_name = getattr(contact, "retailer_name", None)
            if retailer_name and str(retailer_name).strip():
                raw = str(retailer_name)
                norm = _normalize_name(raw)
                # Group by normalized name
                self._name_candidates.append((raw, norm, [contact]))

        logger.info(
            "ContactResolver initialized: %d contacts, %d license keys, "
            "%d name keys",
            len(contacts),
            len(self._license_index),
            len(self._name_index),
        )

    # -------------------------------------------------------------------
    # Single-invoice matching
    # -------------------------------------------------------------------

    def match_invoice(self, invoice) -> MatchResult:
        """Match a single invoice to a contact.

        Applies the matching tiers in priority order:
        1. Exact License + Exact Name
        2. Exact License + Fuzzy Name
        3. Exact License only
        4. Fuzzy Name only
        5. No match

        Args:
            invoice: An Invoice object with at least `order_no` and
                `location` attributes. May also have `license_number`.

        Returns:
            A MatchResult describing the match outcome.
        """
        order_no = getattr(invoice, "order_no", 0)
        location = str(getattr(invoice, "location", "") or "").strip()
        license_num = str(getattr(invoice, "license_number", "") or "").strip()

        result = MatchResult(
            invoice_order_nos=[order_no],
            invoice_location=location,
        )

        if not location and not license_num:
            result.notes = "Invoice has no location and no license number"
            logger.warning(
                "Invoice %s: no location or license number, cannot match",
                order_no,
            )
            return result

        # Normalize the license number for lookup
        license_key = license_num.upper() if license_num else ""

        # Normalize the store name for lookup
        name_key = _normalize_name(location)

        # ---------------------------------------------------------------
        # Tier 1: Exact License + Exact Name (100% confidence)
        # ---------------------------------------------------------------
        if license_key and license_key in self._license_index:
            license_contacts = self._license_index[license_key]
            for contact in license_contacts:
                contact_name = _normalize_name(
                    str(getattr(contact, "retailer_name", ""))
                )
                if contact_name == name_key:
                    primary = _select_primary_contact([contact])
                    result.contact = primary
                    result.confidence = CONFIDENCE_EXACT_LICENSE_EXACT_NAME
                    result.match_tier = MatchTier.EXACT_LICENSE_EXACT_NAME
                    result.fuzzy_score = 1.0
                    result.matched_contact_name = str(
                        getattr(contact, "retailer_name", "")
                    )
                    result.notes = (
                        f"Exact match on license '{license_num}' "
                        f"and store name '{location}'"
                    )
                    logger.debug(
                        "Invoice %s: Tier 1 match (license+name) -> %s",
                        order_no, result.matched_contact_name,
                    )
                    return result

            # ---------------------------------------------------------------
            # Tier 2: Exact License + Fuzzy Name (90% confidence)
            # ---------------------------------------------------------------
            best_score = 0.0
            best_contact = None
            best_name = ""
            for contact in license_contacts:
                contact_name_raw = str(
                    getattr(contact, "retailer_name", "")
                )
                score = _compute_similarity(location, contact_name_raw)
                if score > best_score:
                    best_score = score
                    best_contact = contact
                    best_name = contact_name_raw

            if best_contact and best_score >= self.fuzzy_threshold:
                primary = _select_primary_contact([best_contact])
                result.contact = primary
                result.confidence = CONFIDENCE_EXACT_LICENSE_FUZZY_NAME
                result.match_tier = MatchTier.EXACT_LICENSE_FUZZY_NAME
                result.fuzzy_score = best_score
                result.matched_contact_name = best_name
                result.notes = (
                    f"License '{license_num}' exact match; "
                    f"store name fuzzy match '{location}' -> "
                    f"'{best_name}' (score: {best_score:.3f})"
                )
                logger.debug(
                    "Invoice %s: Tier 2 match (license+fuzzy name) -> %s "
                    "(score=%.3f)",
                    order_no, best_name, best_score,
                )
                return result

            # ---------------------------------------------------------------
            # Tier 3: Exact License only (80% confidence)
            # ---------------------------------------------------------------
            primary = _select_primary_contact(license_contacts)
            if primary:
                result.contact = primary
                result.confidence = CONFIDENCE_EXACT_LICENSE_ONLY
                result.match_tier = MatchTier.EXACT_LICENSE_ONLY
                result.matched_contact_name = str(
                    getattr(primary, "retailer_name", "")
                )
                result.notes = (
                    f"License '{license_num}' matched but store name "
                    f"'{location}' did not match any contact name for "
                    f"this license (best was '{best_name}' at "
                    f"{best_score:.3f}). Using license match only."
                )
                logger.info(
                    "Invoice %s: Tier 3 match (license only) -> %s",
                    order_no, result.matched_contact_name,
                )
                return result

        # ---------------------------------------------------------------
        # Tier 4: Fuzzy Name only (60% confidence)
        # ---------------------------------------------------------------
        if name_key:
            # First try exact name match in the name index
            if name_key in self._name_index:
                name_contacts = self._name_index[name_key]
                primary = _select_primary_contact(name_contacts)
                if primary:
                    result.contact = primary
                    # Exact name match without license is still tier 4
                    # but we give it a slight boost since the name is exact
                    result.confidence = CONFIDENCE_FUZZY_NAME_ONLY
                    result.match_tier = MatchTier.FUZZY_NAME_ONLY
                    result.fuzzy_score = 1.0
                    result.matched_contact_name = str(
                        getattr(primary, "retailer_name", "")
                    )
                    if license_key:
                        result.notes = (
                            f"Exact store name match '{location}'; "
                            f"license '{license_num}' not found in "
                            f"contacts directory"
                        )
                    else:
                        result.notes = (
                            f"Exact store name match '{location}'; "
                            f"no license number available"
                        )
                    logger.debug(
                        "Invoice %s: Tier 4 match (exact name, no license) "
                        "-> %s",
                        order_no, result.matched_contact_name,
                    )
                    return result

            # Fuzzy scan all contact names
            best_score = 0.0
            best_contacts: list = []
            best_name = ""
            for raw_name, _norm, contact_list in self._name_candidates:
                score = _compute_similarity(location, raw_name)
                if score > best_score:
                    best_score = score
                    best_contacts = contact_list
                    best_name = raw_name

            if best_score >= self.fuzzy_threshold and best_contacts:
                primary = _select_primary_contact(best_contacts)
                if primary:
                    result.contact = primary
                    result.confidence = CONFIDENCE_FUZZY_NAME_ONLY
                    result.match_tier = MatchTier.FUZZY_NAME_ONLY
                    result.fuzzy_score = best_score
                    result.matched_contact_name = best_name
                    if license_key:
                        result.notes = (
                            f"Fuzzy store name match '{location}' -> "
                            f"'{best_name}' (score: {best_score:.3f}); "
                            f"license '{license_num}' not found in "
                            f"contacts directory"
                        )
                    else:
                        result.notes = (
                            f"Fuzzy store name match '{location}' -> "
                            f"'{best_name}' (score: {best_score:.3f}); "
                            f"no license number available"
                        )
                    logger.info(
                        "Invoice %s: Tier 4 fuzzy match -> %s (score=%.3f)",
                        order_no, best_name, best_score,
                    )
                    return result

        # ---------------------------------------------------------------
        # Tier 5: No match (0% confidence)
        # ---------------------------------------------------------------
        best_hint = ""
        if name_key:
            # Provide the closest near-miss for manual review
            hint_score = 0.0
            for raw_name, _norm, _contacts in self._name_candidates:
                score = _compute_similarity(location, raw_name)
                if score > hint_score:
                    hint_score = score
                    best_hint = f" (closest: '{raw_name}' at {score:.3f})"

        result.notes = (
            f"No match found for '{location}'"
            f"{f' with license {license_num}' if license_key else ''}"
            f"{best_hint}. Flagged for manual review."
        )
        logger.warning(
            "Invoice %s: NO MATCH for '%s'%s%s",
            order_no,
            location,
            f" (license: {license_num})" if license_key else "",
            best_hint,
        )
        return result

    # -------------------------------------------------------------------
    # Batch resolution
    # -------------------------------------------------------------------

    def resolve(
        self,
        invoices: list,
        group_by_location: bool = False,
    ) -> ResolutionReport:
        """Resolve contacts for a batch of invoices.

        Args:
            invoices: List of Invoice objects to match.
            group_by_location: If True, group invoices by Location before
                matching so that a single contact lookup is used for
                multi-invoice dispensaries. If False, each invoice is
                matched independently (though results will be identical
                for same-location invoices).

        Returns:
            A ResolutionReport with matched/unmatched lists and statistics.
        """
        report = ResolutionReport(total_invoices=len(invoices))

        if group_by_location:
            results = self._resolve_grouped(invoices)
        else:
            results = [self.match_invoice(inv) for inv in invoices]

        # Partition results
        for result in results:
            if result.match_tier == MatchTier.NO_MATCH:
                report.unmatched.append(result)
            else:
                report.matched.append(result)

        # Compute statistics
        if report.total_invoices > 0:
            # Count total matched invoices (accounting for grouped results)
            total_matched_invoices = sum(
                len(m.invoice_order_nos) for m in report.matched
            )
            report.match_rate = total_matched_invoices / report.total_invoices

        # Build confidence distribution
        confidence_buckets = {
            "100%": 0,
            "90%": 0,
            "80%": 0,
            "60%": 0,
            "0% (unmatched)": 0,
        }
        for result in report.matched + report.unmatched:
            count = len(result.invoice_order_nos)
            if result.confidence >= 1.0:
                confidence_buckets["100%"] += count
            elif result.confidence >= 0.9:
                confidence_buckets["90%"] += count
            elif result.confidence >= 0.8:
                confidence_buckets["80%"] += count
            elif result.confidence >= 0.6:
                confidence_buckets["60%"] += count
            else:
                confidence_buckets["0% (unmatched)"] += count
        report.confidence_distribution = confidence_buckets

        # Log summary
        logger.info(
            "Contact resolution complete: %d/%d matched (%.1f%%), "
            "%d unmatched",
            len(report.matched),
            len(report.matched) + len(report.unmatched),
            report.match_rate * 100,
            len(report.unmatched),
        )
        if report.unmatched:
            for miss in report.unmatched:
                logger.warning(
                    "  UNMATCHED: %s (orders: %s) - %s",
                    miss.invoice_location,
                    ", ".join(str(o) for o in miss.invoice_order_nos),
                    miss.notes,
                )

        return report

    def _resolve_grouped(self, invoices: list) -> list[MatchResult]:
        """Group invoices by location and resolve each group once.

        This is more efficient and ensures multi-invoice dispensaries
        get a single consistent match result. The MatchResult's
        invoice_order_nos will contain all order numbers for the group.

        Args:
            invoices: List of Invoice objects.

        Returns:
            List of MatchResult objects, one per unique location.
        """
        # Group invoices by normalized location
        groups: dict[str, list] = {}
        location_raw: dict[str, str] = {}  # normalized -> first raw value

        for invoice in invoices:
            loc = str(getattr(invoice, "location", "") or "").strip()
            key = _normalize_name(loc)
            if key not in groups:
                groups[key] = []
                location_raw[key] = loc
            groups[key].append(invoice)

        results: list[MatchResult] = []
        for key, group in groups.items():
            # Use the first invoice in the group as the representative
            representative = group[0]
            result = self.match_invoice(representative)

            # Replace the single order number with all order numbers
            result.invoice_order_nos = [
                getattr(inv, "order_no", 0) for inv in group
            ]
            # Use the raw location from the first invoice
            result.invoice_location = location_raw[key]

            if len(group) > 1:
                result.notes += (
                    f" [Multi-invoice: {len(group)} invoices for "
                    f"this location]"
                )

            results.append(result)

        return results


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def resolve_contacts(
    invoices: list,
    contacts: list,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    group_by_location: bool = True,
) -> ResolutionReport:
    """One-shot convenience function for contact resolution.

    Creates a ContactResolver and runs it against the provided invoices.
    This is the primary entry point for most use cases.

    Args:
        invoices: List of Invoice objects (from the Overdue sheet).
        contacts: List of Contact objects (from the Managers sheet).
        fuzzy_threshold: Minimum similarity for fuzzy name matching.
        group_by_location: If True, combine multi-invoice dispensaries.

    Returns:
        A ResolutionReport with all match results and statistics.

    Example:
        >>> from src.models import Invoice, Contact
        >>> invoices = [Invoice(order_no=906858, location="Aroma Farms", ...)]
        >>> contacts = [Contact(retailer_name="Aroma Farms", ...)]
        >>> report = resolve_contacts(invoices, contacts)
        >>> print(report.match_rate)
        1.0
    """
    resolver = ContactResolver(contacts, fuzzy_threshold=fuzzy_threshold)
    return resolver.resolve(invoices, group_by_location=group_by_location)


def format_resolution_report(report: ResolutionReport) -> str:
    """Format a ResolutionReport as a human-readable string.

    Useful for logging, CLI output, or inclusion in review UIs.

    Args:
        report: The resolution report to format.

    Returns:
        A multi-line string summary.
    """
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("CONTACT RESOLUTION REPORT")
    lines.append("=" * 70)
    lines.append(f"Total invoices:  {report.total_invoices}")
    lines.append(f"Matched:         {len(report.matched)} groups")
    lines.append(f"Unmatched:       {len(report.unmatched)} groups")
    lines.append(f"Match rate:      {report.match_rate:.1%}")
    lines.append("")

    # Confidence distribution
    lines.append("Confidence Distribution:")
    for tier, count in report.confidence_distribution.items():
        bar = "#" * count
        lines.append(f"  {tier:>15s}: {count:3d}  {bar}")
    lines.append("")

    # Matched details
    if report.matched:
        lines.append("-" * 70)
        lines.append("MATCHED INVOICES:")
        lines.append("-" * 70)
        for match in sorted(report.matched, key=lambda m: -m.confidence):
            orders = ", ".join(str(o) for o in match.invoice_order_nos)
            lines.append(
                f"  [{match.confidence:5.0%}] {match.invoice_location} "
                f"(orders: {orders})"
            )
            lines.append(f"         -> {match.matched_contact_name}")
            lines.append(f"         Tier: {match.match_tier.value}")
            if match.fuzzy_score < 1.0:
                lines.append(
                    f"         Fuzzy score: {match.fuzzy_score:.3f}"
                )
            lines.append(f"         {match.notes}")
            lines.append("")

    # Unmatched details
    if report.unmatched:
        lines.append("-" * 70)
        lines.append("UNMATCHED - MANUAL REVIEW REQUIRED:")
        lines.append("-" * 70)
        for miss in report.unmatched:
            orders = ", ".join(str(o) for o in miss.invoice_order_nos)
            lines.append(
                f"  [  0%] {miss.invoice_location} (orders: {orders})"
            )
            lines.append(f"         {miss.notes}")
            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
