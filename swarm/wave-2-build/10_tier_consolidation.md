# Tier Consolidation Report
## Document: 10 - 5-Tier to 3-Tier Consolidation
## Timestamp: 2026-02-14
## Agent: Wave 2 Tier Consolidator (Opus)
## Status: COMPLETE

---

## Summary

Successfully consolidated the AR email automation from a 5-tier system (T0-T4) to a 3-tier system (T0-T2):
- **T0**: Coming Due (days <= 0)
- **T1**: Overdue (1-29 days)
- **T2**: 30+ Days Past Due (30+ days, with dynamic subject labels: 40+, 50+, etc.)

Removed tiers:
- T3 (40+ Days Past Due) -- merged into T2
- T4 (50+ Days Past Due) -- merged into T2

**All 224 tests pass after changes.**

---

## Files Modified

### 1. src/models.py
- [x] Tier enum collapsed from 5 to 3 values (removed T3, T4)
- [x] from_days() updated: <=0 -> T0, 1-29 -> T1, 30+ -> T2
- [x] TierConfig.default_tiers() reduced to 3 entries, T0 min_days changed from -999 to -7
- [x] Added Invoice.dynamic_subject_label property (computes "40+ Days Past Due" etc. for 30+ invoices)
- [x] Updated EmailDraft.build_subject() to use dynamic_subject_label for T2 tier

### 2. src/tier_classifier.py
- [x] Tier enum collapsed from 5 to 3 values (COMING_DUE, OVERDUE, PAST_DUE)
- [x] Removed TIER_BOUNDARY_PAST_DUE_40 and TIER_BOUNDARY_PAST_DUE_50 constants
- [x] Simplified TIER_METADATA from 5 entries to 3 entries
- [x] Simplified classify() function from 5-way to 3-way branching
- [x] Replaced get_overdue_timeframe_description() with get_dynamic_subject_label()
- [x] Updated all docstrings and self-test block for 3-tier system

### 3. config.yaml
- [x] Tiers section reduced from 5 to 3 entries (T1: -7 to 0, T2: 1-29, T3: 30-999)
- [x] Removed T4 and T5 from tier_extra_cc
- [x] Removed T4 and T5 from tier_attachments
- [x] Removed escalation_sender section (no sender escalation at any tier)
- [x] Updated review_flags.tier_gte_management_escalation from "T5" to "T3"

### 4. tests/test_models.py
- [x] Updated Tier enum tests: count from 5 to 3, removed T3/T4 value assertions
- [x] Added test_removed_tiers_do_not_exist test
- [x] Updated from_days() parametrized: 40+/50+ cases now expect T2
- [x] Updated test_auto_tier_assignment: 45 days -> T2, 111 days -> T2
- [x] Updated test_approve_by_tier: T4 -> T2
- [x] Updated TierConfig tests: default_tiers count 5->3, boundaries, find_tier assertions
- [x] Updated test_find_tier_no_match_raises: -1000 -> -8 (new lower bound is -7)
- [x] Updated test_default_tiers_t2_plus_include_ocm_warning: removed T3/T4 assertions

### 5. tests/test_tier_classifier.py
- [x] Removed TIER_BOUNDARY_PAST_DUE_40 and TIER_BOUNDARY_PAST_DUE_50 imports
- [x] Removed get_overdue_timeframe_description import, added get_dynamic_subject_label
- [x] Removed TestConstants.test_past_due_40_boundary and test_past_due_50_boundary
- [x] Updated TestTierEnum: removed PAST_DUE_40/50 assertions, added count and removed-tiers tests
- [x] Updated all parametrized classify() cases: 40+/50+ -> PAST_DUE
- [x] Replaced boundary transition tests for 40/50 with test_no_40_boundary/test_no_50_boundary
- [x] Updated test_very_large_days, test_float_input, test_result_metadata_matches_tier
- [x] Updated TestTierMetadata: 3 entries, removed PAST_DUE_40/50, added test_metadata_count
- [x] Replaced TestOverdueTimeframeDescription (19 tests) with TestDynamicSubjectLabel (21 tests)
- [x] Updated TestConvenienceFunctions.test_get_tier: all 40+/50+ -> PAST_DUE
- [x] Updated TestRealDataScenarios: 111 days -> PAST_DUE (was PAST_DUE_50)

---

## Detailed Changes

### src/models.py -- Tier Enum (lines 27-42)

**Before:**
```python
class Tier(Enum):
    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"
    T3 = "40+ Days Past Due"
    T4 = "50+ Days Past Due"
```

**After:**
```python
class Tier(Enum):
    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"
```

### src/models.py -- from_days() (lines 44-51)

**Before:** 5-way branching with boundaries at 0, 29, 39, 49
**After:** 3-way branching: <=0 -> T0, <=29 -> T1, else -> T2

### src/models.py -- dynamic_subject_label property (new)

```python
@property
def dynamic_subject_label(self) -> str:
    if self.days_past_due < 30:
        return self.tier.value
    bucket = (self.days_past_due // 10) * 10
    return f"{bucket}+ Days Past Due"
```

This allows subject lines to show "40+ Days Past Due", "50+ Days Past Due", etc. while all sharing the same T2 tier and template.

### src/models.py -- build_subject() (updated)

Now checks if tier is T2 and uses `dynamic_subject_label` from the primary invoice instead of the static tier value.

### src/models.py -- TierConfig.default_tiers()

Reduced from 5 entries to 3. Key change: T0 min_days from -999 to -7 (per meeting: Coming Due = -7 to 0).

### src/tier_classifier.py -- Tier Enum

Renamed PAST_DUE_30 to PAST_DUE. Removed PAST_DUE_40 and PAST_DUE_50.

### src/tier_classifier.py -- classify()

Simplified from 5-way to 3-way branching. Only checks TIER_BOUNDARY_PAST_DUE_30 and TIER_BOUNDARY_OVERDUE.

### src/tier_classifier.py -- get_dynamic_subject_label() (replaced get_overdue_timeframe_description)

New function computes dynamic subject labels for all tiers:
- <=0: "Coming Due"
- 1-29: "Overdue"
- 30+: "{bucket}+ Days Past Due" where bucket = floor(days/10)*10

### config.yaml

- T1: Coming Due, -7 to 0 (was -3 to 3)
- T2: Overdue, 1 to 29 (was 4 to 29)
- T3: 30+ Days Past Due, 30 to 999 (was 30 to 39; T4/T5 removed)
- escalation_sender section removed
- management_escalation threshold changed from T5 to T3

---

## Test Results

```
224 passed in 0.40s
```

All tests pass across both test files (test_models.py and test_tier_classifier.py).

### Test Changes Summary
- ~50 tests modified to reflect 3-tier system
- 19 tests removed (TestOverdueTimeframeDescription + boundary constants)
- 21 tests added (TestDynamicSubjectLabel + tier existence checks)
- Net: 224 tests (was ~240 across the full suite before; reduction from removing overdue timeframe tests)

---

## Dynamic Subject Label Examples

| Days Past Due | Tier | Subject Label |
|--------------|------|---------------|
| -2 | T0 | Coming Due |
| 15 | T1 | Overdue |
| 30 | T2 | 30+ Days Past Due |
| 39 | T2 | 30+ Days Past Due |
| 40 | T2 | 40+ Days Past Due |
| 45 | T2 | 40+ Days Past Due |
| 50 | T2 | 50+ Days Past Due |
| 111 | T2 | 110+ Days Past Due |

---

## Remaining Work for Other Build Agents

The following changes are specified in the implementation plan but are **outside this agent's scope** (Phases 3-6):

1. **src/template_engine.py** (Phase 3): Remove `get_overdue_timeframe_description` import, remove T4/T5 escalation logic, fix subject line "ACTION REQUIRED"/"FINAL NOTICE" suffixes, update `_build_context()`.
2. **templates/** (Phase 4): Fix coming_due.html attachment line, fix overdue.html OVERDUE_TIMEFRAME variable, rebuild past_due_30.html, DELETE past_due_40.html and past_due_50.html.
3. **src/contact_resolver.py** (Phase 5): Minor -- add `contact_emails` property to `MatchResult`.
4. **app.py** (Phase 6): Update TIER_COLORS dict, fix hardcoded "Laura" sender, remove ClassifierTier import.

---

*End of Document 10 - Tier Consolidation*
