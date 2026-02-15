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

Contact selection priority chain (SOP from meeting 2026-02):
    1. Primary Contact (from Managers sheet / Notion)
    2. Billing/AP Contact (send to BOTH primary AND billing)
    3. Associated Contacts (Nabis-sourced > CRM > unlabeled >> Revelry-sourced)
    4. Brand AR Summary POC email (Nabis-provided XLSX fallback)
    5. No contact found -> editable placeholder for manual entry

CC rules (always):
    - ny.ar@nabis.com
    - martinm@piccplatform.com
    - mario@piccplatform.com
    - laura@piccplatform.com
    - Dynamic: assigned PICC sales rep email for the account

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
# Source trust levels for associated contacts
# ---------------------------------------------------------------------------

SOURCE_TRUST: dict[str, str] = {
    "nabis import": "high",
    "nabis poc": "high",
    "crm contact": "high",
    "nabis order, point of contact": "high",
    "revelry buyers list": "low",
    "revelry": "low",
}


def _get_source_trust(source: str) -> str:
    """Return trust level for a contact source label.

    Returns 'high', 'low', or 'medium' (default for unknown sources).
    """
    if not source:
        return "medium"
    return SOURCE_TRUST.get(source.strip().lower(), "medium")


# ---------------------------------------------------------------------------
# Rep email mapping
# ---------------------------------------------------------------------------

REP_EMAIL_MAP: dict[str, str] = {
    "Ben": "b.rosenthal@piccplatform.com",
    "Bryce J": "bryce@piccplatform.com",
    "Donovan": "donovan@piccplatform.com",
    "Eric": "eric@piccplatform.com",
    "M Martin": "martinm@piccplatform.com",
    "Mario": "mario@piccplatform.com",
    "Matt M": "matt@piccplatform.com",
}

# Hardcoded base CC list per meeting SOP
ALWAYS_CC: list[str] = [
    "ny.ar@nabis.com",
    "martinm@piccplatform.com",
    "mario@piccplatform.com",
    "laura@piccplatform.com",
]

# Placeholder for no-contact-found emails
NO_CONTACT_PLACEHOLDER = "(no contact found - enter manually)"


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
        resolution_chain: Ordered list of sources that were consulted during
            contact resolution (for audit trail).
        to_emails: Resolved TO recipient list (may be multiple: primary + billing).
        cc_emails: Resolved CC recipient list (always includes base + rep).
        contact_source: Which source provided the final contact (e.g.,
            'managers_sheet', 'brand_ar_summary', 'manual').
    """
    invoice_order_nos: list[int]
    invoice_location: str
    contact: object | None = None  # Will be a Contact dataclass instance
    confidence: float = 0.0
    match_tier: MatchTier = MatchTier.NO_MATCH
    fuzzy_score: float = 0.0
    matched_contact_name: str = ""
    notes: str = ""
    resolution_chain: list[str] = field(default_factory=list)
    to_emails: list[str] = field(default_factory=list)
    cc_emails: list[str] = field(default_factory=list)
    contact_source: str = ""

    @property
    def contact_emails(self) -> list[str]:
        """Return all available email addresses from the resolved contact.

        Prefers the resolved to_emails list (which may include both primary
        and billing contacts). Falls back to the contact's all_emails or
        single email field.
        """
        if self.to_emails:
            return list(self.to_emails)
        if self.contact is None:
            return []
        if hasattr(self.contact, 'all_emails') and self.contact.all_emails:
            return list(self.contact.all_emails)
        if hasattr(self.contact, 'email') and self.contact.email:
            return [self.contact.email]
        return []

    @property
    def primary_contact_name(self) -> str:
        """Return the name of the primary contact for email greeting."""
        if self.contact is None:
            return ""
        if hasattr(self.contact, 'contact_name') and self.contact.contact_name:
            return self.contact.contact_name
        if hasattr(self.contact, 'first_name') and self.contact.first_name:
            return self.contact.first_name
        return ""


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
        brand_ar_contacts: dict[str, object] | None = None,
        rep_email_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize the resolver with a contact directory.

        Args:
            contacts: List of Contact objects (from Managers sheet).
            fuzzy_threshold: Minimum SequenceMatcher ratio for fuzzy
                matches (default 0.70).
            brand_ar_contacts: Optional dict mapping normalized retailer
                name -> BrandARContact objects (from Brand AR Summary XLSX).
                Used as fallback (Priority 4) when no contact is found in
                the Managers sheet.
            rep_email_map: Optional dict mapping sales rep short name
                (e.g. "Ben", "Bryce J") -> email address.  Used for
                building the CC list.  Falls back to REP_EMAIL_MAP.
        """
        self.contacts = contacts
        self.fuzzy_threshold = fuzzy_threshold
        self._brand_ar_contacts = brand_ar_contacts or {}
        self._rep_email_map = rep_email_map or REP_EMAIL_MAP

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

        # Pre-compute Brand AR Summary name candidates for fuzzy matching
        self._brand_ar_name_candidates: list[tuple[str, str, object]] = []
        for raw_name, ar_contact in self._brand_ar_contacts.items():
            norm = _normalize_name(raw_name)
            self._brand_ar_name_candidates.append(
                (raw_name, norm, ar_contact)
            )

        logger.info(
            "ContactResolver initialized: %d contacts, %d license keys, "
            "%d name keys, %d brand AR contacts",
            len(contacts),
            len(self._license_index),
            len(self._name_index),
            len(self._brand_ar_contacts),
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
    # Contact SOP priority chain
    # -------------------------------------------------------------------

    def resolve_to_recipients(self, match_result: MatchResult) -> MatchResult:
        """Apply the meeting-defined SOP priority chain to populate to_emails.

        Priority cascade for TO recipients:
          1. Primary Contact (from matched contact's primary email)
          2. Billing/AP Contact (if available, add to TO alongside primary)
          3. Associated Contacts (prefer Nabis-sourced over Revelry-sourced)
          4. Brand AR Summary POC email (fallback from Nabis-provided XLSX)
          5. No contact found -> leave placeholder for manual entry

        Also populates resolution_chain for audit trail.

        Args:
            match_result: A MatchResult from match_invoice().

        Returns:
            The same MatchResult, updated with to_emails and resolution_chain.
        """
        chain: list[str] = []
        to_emails: list[str] = []
        contact = match_result.contact

        # ------------------------------------------------------------------
        # Priority 1 & 2: Primary + Billing from matched contact
        # ------------------------------------------------------------------
        if contact is not None:
            primary_email = getattr(contact, "email", "")
            all_emails = getattr(contact, "all_emails", []) or []
            all_contacts = getattr(contact, "all_contacts", []) or []
            contact_role = getattr(contact, "role", "")

            chain.append(f"Managers sheet match: '{match_result.matched_contact_name}'")

            # Add primary email
            if primary_email:
                to_emails.append(primary_email)
                chain.append(f"  -> Primary email: {primary_email}")

            # Check for billing/AP contacts in all_contacts
            billing_emails = self._find_billing_contacts(all_contacts, all_emails)
            for be in billing_emails:
                if be and be.lower() not in [e.lower() for e in to_emails]:
                    to_emails.append(be)
                    chain.append(f"  -> Billing/AP email: {be}")

            # Priority 3: Associated Contacts (with source trust filtering)
            if not to_emails:
                chain.append("  -> No primary/billing email; checking associated contacts")
                trusted, untrusted = self._filter_contacts_by_source(all_contacts, all_emails)

                # Prefer high-trust sources first
                for email in trusted:
                    if email.lower() not in [e.lower() for e in to_emails]:
                        to_emails.append(email)
                        chain.append(f"  -> Trusted associated contact: {email}")

                # Fall back to low-trust (Revelry) only if nothing else
                if not to_emails and untrusted:
                    for email in untrusted:
                        if email.lower() not in [e.lower() for e in to_emails]:
                            to_emails.append(email)
                            chain.append(
                                f"  -> Revelry-sourced contact (low trust): {email}"
                            )

            if to_emails:
                match_result.contact_source = "managers_sheet"

        # ------------------------------------------------------------------
        # Priority 4: Brand AR Summary fallback
        # ------------------------------------------------------------------
        if not to_emails and match_result.invoice_location:
            chain.append("Checking Brand AR Summary XLSX fallback")
            ar_emails = self._lookup_brand_ar_emails(
                match_result.invoice_location
            )
            if ar_emails:
                to_emails.extend(ar_emails)
                match_result.contact_source = "brand_ar_summary"
                chain.append(
                    f"  -> Brand AR Summary POC: {', '.join(ar_emails)}"
                )
            else:
                chain.append("  -> No match in Brand AR Summary")

        # ------------------------------------------------------------------
        # Priority 5: No contact found
        # ------------------------------------------------------------------
        if not to_emails:
            chain.append("No contact found from any source. Manual entry needed.")
            match_result.contact_source = "manual"

        match_result.to_emails = to_emails
        match_result.resolution_chain = chain
        return match_result

    def build_cc_list(
        self,
        invoice: object,
        extra_cc: list[str] | None = None,
    ) -> list[str]:
        """Build the CC recipient list per the meeting SOP.

        Always CC (hardcoded base):
          - ny.ar@nabis.com
          - martinm@piccplatform.com
          - mario@piccplatform.com
          - laura@piccplatform.com

        Dynamic CC:
          - The assigned PICC sales rep email for the account

        Args:
            invoice: An Invoice object with a ``sales_rep`` attribute.
            extra_cc: Optional additional CC addresses.

        Returns:
            De-duplicated list of CC email addresses.
        """
        cc: list[str] = list(ALWAYS_CC)

        # Add the assigned sales rep email
        sales_rep = str(getattr(invoice, "sales_rep", "") or "").strip()
        if sales_rep:
            rep_email = self._rep_email_map.get(sales_rep, "")
            if rep_email and rep_email.lower() not in [c.lower() for c in cc]:
                cc.append(rep_email)

        # Add any extra CCs
        if extra_cc:
            for addr in extra_cc:
                if addr and addr.lower() not in [c.lower() for c in cc]:
                    cc.append(addr)

        # Remove any placeholder tokens
        cc = [addr for addr in cc if addr and "{" not in addr]

        # De-duplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for addr in cc:
            addr_lower = addr.strip().lower()
            if addr_lower not in seen:
                seen.add(addr_lower)
                deduped.append(addr.strip())

        return deduped

    # -------------------------------------------------------------------
    # Private helpers for SOP chain
    # -------------------------------------------------------------------

    @staticmethod
    def _find_billing_contacts(
        all_contacts: list[dict[str, str]],
        all_emails: list[str],
    ) -> list[str]:
        """Find billing/AP contacts from the all_contacts list.

        Returns emails of contacts whose title indicates billing/AP role.
        """
        billing_emails: list[str] = []
        billing_keywords = ["ap", "accounts payable", "billing", "accounting",
                            "finance", "invoic"]

        for contact_dict in all_contacts:
            title = (contact_dict.get("title") or "").lower()
            name = (contact_dict.get("name") or contact_dict.get("full_name") or "").lower()
            combined = f"{name} {title}"

            for kw in billing_keywords:
                if kw in combined:
                    # Try to find an email for this contact
                    email = contact_dict.get("email", "")
                    if email:
                        billing_emails.append(email)
                    break

        # Also check all_emails for AP/billing-pattern emails
        for email in all_emails:
            email_lower = email.lower()
            if any(prefix in email_lower for prefix in
                   ["ap@", "accounting@", "invoices@", "billing@"]):
                if email not in billing_emails:
                    billing_emails.append(email)

        return billing_emails

    @staticmethod
    def _filter_contacts_by_source(
        all_contacts: list[dict[str, str]],
        all_emails: list[str],
    ) -> tuple[list[str], list[str]]:
        """Split contacts into trusted and untrusted based on source labels.

        Returns:
            (trusted_emails, untrusted_emails) where untrusted = Revelry-sourced.
        """
        trusted: list[str] = []
        untrusted: list[str] = []

        for contact_dict in all_contacts:
            source = (contact_dict.get("source") or "").strip()
            email = contact_dict.get("email", "")
            if not email:
                continue

            trust = _get_source_trust(source)
            if trust == "low":
                untrusted.append(email)
            else:
                trusted.append(email)

        # If no contacts had source labels, treat all_emails as medium trust
        if not trusted and not untrusted and all_emails:
            trusted = list(all_emails)

        return trusted, untrusted

    def _lookup_brand_ar_emails(self, location: str) -> list[str]:
        """Look up POC emails from the Brand AR Summary by store name.

        Uses the same fuzzy matching logic as the main contact resolver.

        Args:
            location: The store name / location from the invoice.

        Returns:
            List of POC email addresses from the Brand AR Summary, or
            empty list if no match.
        """
        if not self._brand_ar_contacts:
            return []

        name_key = _normalize_name(location)

        # Exact match first
        for raw_name, norm, ar_contact in self._brand_ar_name_candidates:
            if norm == name_key:
                emails = getattr(ar_contact, "poc_emails", []) or []
                if emails:
                    logger.info(
                        "Brand AR Summary exact match: '%s' -> %s",
                        location, emails,
                    )
                    return emails

        # Fuzzy match
        best_score = 0.0
        best_contact = None
        for raw_name, _norm, ar_contact in self._brand_ar_name_candidates:
            score = _compute_similarity(location, raw_name)
            if score > best_score:
                best_score = score
                best_contact = ar_contact

        if best_score >= self.fuzzy_threshold and best_contact is not None:
            emails = getattr(best_contact, "poc_emails", []) or []
            if emails:
                logger.info(
                    "Brand AR Summary fuzzy match: '%s' (score=%.3f) -> %s",
                    location, best_score, emails,
                )
                return emails

        return []

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

        # Apply the SOP priority chain to resolve TO recipients
        for result in results:
            self.resolve_to_recipients(result)

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
    brand_ar_contacts: dict[str, object] | None = None,
    rep_email_map: dict[str, str] | None = None,
) -> ResolutionReport:
    """One-shot convenience function for contact resolution.

    Creates a ContactResolver and runs it against the provided invoices.
    This is the primary entry point for most use cases.

    Args:
        invoices: List of Invoice objects (from the Overdue sheet).
        contacts: List of Contact objects (from the Managers sheet).
        fuzzy_threshold: Minimum similarity for fuzzy name matching.
        group_by_location: If True, combine multi-invoice dispensaries.
        brand_ar_contacts: Optional dict mapping normalized retailer
            name -> BrandARContact objects (from Brand AR Summary XLSX).
        rep_email_map: Optional dict mapping rep short name -> email.

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
    resolver = ContactResolver(
        contacts,
        fuzzy_threshold=fuzzy_threshold,
        brand_ar_contacts=brand_ar_contacts,
        rep_email_map=rep_email_map,
    )
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
