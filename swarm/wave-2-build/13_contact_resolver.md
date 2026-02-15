# Wave 2 Build: Contact Resolver Upgrade

**Agent**: Contact Resolver Upgrade (Wave 2 Build)
**Status**: COMPLETE
**Started**: 2026-02-14
**Completed**: 2026-02-14

## Objective
Fix contact selection logic to match meeting-defined SOP priority chain.

## Changes Summary
1. `src/contact_resolver.py` -- Implement correct TO recipient priority cascade
2. `src/contact_resolver.py` -- Fix CC list assembly (hardcoded base + dynamic sales rep)
3. `src/data_loader.py` -- Add Brand AR Summary XLSX loading support
4. Deprioritize revelry-sourced contacts
5. Update tests (33 new tests, all passing)
6. `config.yaml` -- Add Brand AR Summary path and rep email map

## Progress
- [x] Read all source files (contact_resolver.py, data_loader.py, models.py, config.yaml, tests, SOP spec)
- [x] Implement contact_resolver.py changes
- [x] Implement data_loader.py changes
- [x] Update config.yaml
- [x] Update tests
- [x] Final validation -- 85/85 tests passing

---

## Changes Made

### 1. `src/contact_resolver.py` -- Contact SOP Priority Chain

#### New Constants and Helpers Added (top of file):
- `SOURCE_TRUST` dict: Maps contact source labels to trust levels ("high", "low", "medium")
- `_get_source_trust(source)`: Returns trust level for a source label (case-insensitive)
- `REP_EMAIL_MAP` dict: Maps rep short names -> email addresses (hardcoded for now)
- `ALWAYS_CC` list: The 4 hardcoded base CC addresses per meeting SOP
- `NO_CONTACT_PLACEHOLDER` string: Editable placeholder for manual entry

#### Updated `MatchResult` Dataclass:
Added new fields:
- `resolution_chain: list[str]` -- Ordered audit trail of sources consulted
- `to_emails: list[str]` -- Resolved TO recipient list (may include primary + billing)
- `cc_emails: list[str]` -- Resolved CC list
- `contact_source: str` -- Which source provided the final contact

Added new properties:
- `contact_emails` -- Returns all available emails (prefers to_emails, falls back to contact fields)
- `primary_contact_name` -- Returns the name of the primary contact for email greeting

#### Updated `ContactResolver.__init__()`:
New parameters:
- `brand_ar_contacts: dict[str, object] | None` -- Brand AR Summary contacts for fallback lookup
- `rep_email_map: dict[str, str] | None` -- Custom rep name -> email mapping

Now pre-computes Brand AR Summary name candidates for fuzzy matching.

#### New Method: `resolve_to_recipients(match_result)`
Implements the meeting-defined SOP priority cascade:

```
Priority 1: Primary Contact email from matched contact
Priority 2: Billing/AP Contact (ADD to TO alongside primary, not replace)
Priority 3: Associated Contacts (filter by source trust: Nabis > CRM > unlabeled >> Revelry)
Priority 4: Brand AR Summary POC email (Nabis-provided XLSX fallback)
Priority 5: No contact found -> empty to_emails, contact_source = "manual"
```

Each step is recorded in `resolution_chain` for audit trail.

#### New Method: `build_cc_list(invoice, extra_cc=None)`
Builds CC list per meeting SOP:
- Always includes: ny.ar@nabis.com, martinm@piccplatform.com, mario@piccplatform.com, laura@piccplatform.com
- Dynamically adds the assigned PICC sales rep email from rep name lookup
- De-duplicates while preserving order
- Strips any unresolved {placeholder} tokens

#### New Private Helper Methods:
- `_find_billing_contacts(all_contacts, all_emails)` -- Identifies billing/AP contacts by title keywords and email patterns (ap@, accounting@, invoices@, billing@)
- `_filter_contacts_by_source(all_contacts, all_emails)` -- Splits contacts into trusted and untrusted lists based on source labels
- `_lookup_brand_ar_emails(location)` -- Fuzzy-matches a store name against Brand AR Summary data

#### Updated `resolve()` Method:
Now calls `resolve_to_recipients()` on every match result after matching, so batch resolution automatically populates `to_emails` and `resolution_chain`.

#### Updated `resolve_contacts()` Convenience Function:
Added `brand_ar_contacts` and `rep_email_map` parameters, passes them through to `ContactResolver`.

### 2. `src/data_loader.py` -- Brand AR Summary XLSX Loader

#### New Dataclass: `BrandARContact`
Fields:
- `retailer_name: str`
- `poc_emails: list[str]` -- Parsed from multi-line POC Email column
- `poc_phones: list[str]` -- Parsed from POC Phone column
- `retailer_type: str` -- "Good", "Weak", "Excellent", "Poor"
- `responsiveness: str` -- "Responsive", "Unresponsive", "Semi-Responsive"
- `notes: str`

#### New Function: `load_brand_ar_summary(source=None)`
- Loads the Nabis Brand AR Summary XLSX (header in row 3, data from row 4)
- Parses columns: Retailer (A), Retailer Type (B), Responsiveness (C), POC Email (O), POC Phone (P), Notes (Q)
- Handles multi-line email addresses (newline-delimited)
- Returns `dict[str, BrandARContact]` mapped by raw retailer name
- Gracefully handles missing file (returns empty dict with warning)
- Default path: `A:\Downloads\Brand AR Summary - PICC (1).xlsx`

### 3. `config.yaml` -- Configuration Updates

- Added `brand_ar_summary_xlsx` path under `data_files`
- Added new `rep_email_map` section with all 7 known rep mappings
- CC rules already had T4/T5 entries removed (prior wave)

### 4. Source Trust Filtering (Revelry Deprioritization)

The `SOURCE_TRUST` mapping classifies contact sources:
- **HIGH trust**: "nabis import", "nabis poc", "crm contact", "nabis order, point of contact"
- **LOW trust**: "revelry buyers list", "revelry"
- **MEDIUM trust**: any unlabeled/unknown source (default)

When selecting from associated contacts:
1. High-trust and medium-trust contacts are preferred
2. Low-trust (Revelry) contacts are only used as fallback when no other sources are available
3. The resolution chain notes when Revelry-sourced contacts are used

### 5. Tests -- `tests/test_contact_resolver.py`

33 new tests added across 7 new test classes:

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestSourceTrust` | 8 | Source trust level classification |
| `TestContactSOPPriorityChain` | 8 | Full priority cascade (primary, billing, associated, Brand AR, manual) |
| `TestSourceFiltering` | 2 | Revelry deprioritization and fallback |
| `TestCCListAssembly` | 7 | CC list building, dedup, rep resolution |
| `TestMatchResultProperties` | 6 | New MatchResult properties |
| `TestBatchResolutionWithSOP` | 2 | Batch resolution applies SOP chain |

All 85 tests pass (52 existing + 33 new).

---

## Key Design Decisions

1. **Preserving the existing fuzzy matching engine**: The existing 5-tier matching strategy (license + name) is preserved intact. The SOP priority chain is layered ON TOP as a post-processing step via `resolve_to_recipients()`.

2. **Brand AR Summary as fallback only**: The Brand AR Summary XLSX is consulted only when the Managers sheet match produces no usable email addresses. This matches the meeting consensus that Managers sheet data takes priority.

3. **CC list is deterministic**: The CC list is built from a hardcoded base + dynamic rep lookup, with no tier-based escalation. This matches the meeting consensus that CC is the same for all tiers.

4. **Revelry contacts are not deleted, just deprioritized**: If Revelry is the only source available, those contacts are still used (with a notation in the resolution chain). They are only skipped when higher-trust sources exist.

5. **No Notion API integration in this wave**: The meeting SOP mentions Notion as the primary source, but Notion API integration is a separate future task. The current implementation uses the Managers sheet as the primary source, which is the same data Callie uses manually.

---

## Files Modified

| File | Lines Added | Lines Modified | Lines Removed |
|------|-------------|---------------|---------------|
| `src/contact_resolver.py` | ~300 | ~30 | 0 |
| `src/data_loader.py` | ~120 | 0 | 0 |
| `config.yaml` | ~15 | 0 | 0 |
| `tests/test_contact_resolver.py` | ~350 | ~15 | 0 |

---

## How to Use the New Features

### Loading Brand AR Summary data:
```python
from src.data_loader import load_brand_ar_summary
brand_ar = load_brand_ar_summary("path/to/Brand AR Summary.xlsx")
```

### Full contact resolution with SOP chain:
```python
from src.contact_resolver import resolve_contacts
from src.data_loader import load_workbook, load_brand_ar_summary

# Load data
result = load_workbook("data/overdue.xlsx")
brand_ar = load_brand_ar_summary()

# Resolve with full SOP chain
report = resolve_contacts(
    invoices=mock_invoices,
    contacts=result.contacts,
    brand_ar_contacts=brand_ar,
    group_by_location=True,
)

# Access resolved recipients
for match in report.matched:
    print(f"TO: {match.to_emails}")
    print(f"Source: {match.contact_source}")
    print(f"Chain: {match.resolution_chain}")
```

### Building CC list:
```python
resolver = ContactResolver(contacts, brand_ar_contacts=brand_ar)
cc_list = resolver.build_cc_list(invoice)
# Returns: ['ny.ar@nabis.com', 'martinm@piccplatform.com',
#           'mario@piccplatform.com', 'laura@piccplatform.com',
#           'b.rosenthal@piccplatform.com']  # Ben's email
```
