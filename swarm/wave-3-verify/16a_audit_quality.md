# Wave 3 Agent 16a: Code Quality Audit
**Status**: COMPLETED
**Timestamp**: 2026-02-14T00:12:00Z

## Syntax Validation

All 7 Python files pass `ast.parse()` with zero errors:

| File | Result |
|------|--------|
| `app.py` | OK |
| `src/models.py` | OK |
| `src/tier_classifier.py` | OK |
| `src/template_engine.py` | OK |
| `src/contact_resolver.py` | OK |
| `src/data_loader.py` | OK |
| `src/config.py` | OK |

**Verdict: PASS**

## Import Consistency

### src/models.py
- Imports: `csv`, `json`, `dataclass`, `field`, `date`, `datetime`, `time`, `Enum`, `Path`, `Self` -- all used. PASS.

### src/tier_classifier.py
- Imports: `dataclass`, `field`, `Enum`, `Any`, `Optional` -- all used. PASS.
- No external dependencies (pure stdlib). PASS.

### src/config.py
- Imports: `os`, `dataclass`, `field`, `Path`, `Optional`, `yaml` -- all used. PASS.

### src/template_engine.py
- Imports from `.config`: `AREmailConfig`, `get_config`, `get_t2_time_phrase`, `tier_for_days`, `PROJECT_ROOT`, `TierConfig` -- all used. PASS.
- Imports from `.models`: `AttachmentRule`, `Contact`, `EmailDraft`, `EmailStatus`, `Invoice`, `Tier` -- all used. PASS.
- Imports from `.tier_classifier`: `classify`, `OCM_REPORTING_DAY` -- both used. PASS.
- Imports `html`, `re`, `date`, `datetime`, `timedelta`, `Path`, `Optional`, `jinja2` classes -- all used. PASS.

### src/contact_resolver.py
- Imports: `logging`, `re`, `dataclass`, `field`, `SequenceMatcher`, `Enum`, `Optional` -- all used. PASS.

### src/data_loader.py
- Imports: `io`, `logging`, `re`, `dataclass`, `field`, `date`, `datetime`, `timedelta`, `Path`, `IO`, `Optional`, `Union`, `openpyxl` -- all used. PASS.
- Imports from `.models`: `Contact`, `Invoice`, `InvoiceStatus`, `SkipReason`, `Tier` -- all used. PASS.

### app.py - ISSUE FOUND
- **Line 85**: Imports `get_overdue_timeframe_description` from `src.tier_classifier`, but this function was **removed** during Wave 2 tier consolidation.
- **Severity: WARNING** (not CRITICAL because the import is wrapped in `try/except ImportError` on line 82-91, so the app will not crash -- instead `CLASSIFIER_AVAILABLE` will be set to `False`, and the app degrades gracefully).
- **Impact**: The tier classifier enrichment features in the Streamlit app will be silently disabled. The rest of the app works fine.

**Verdict: WARNING** -- 1 stale import in app.py (non-blocking due to try/except guard)

## Banned Text Check ("final notice", "ACTION REQUIRED")

Searched all `.py`, `.html`, `.yaml` files under `src/`, `templates/`, `app.py`, `config.yaml`.

| Pattern | Matches | Context |
|---------|---------|---------|
| `final notice` (case-insensitive) | 3 matches | All are in **comments/documentation only** that explicitly say these phrases must NOT be used |
| `ACTION REQUIRED` (case-insensitive) | 3 matches | All are in **comments/documentation only** that explicitly say these phrases must NOT be used |

Details:
- `templates/past_due_30.html` line 25-26: HTML comment stating "No 'second notice', 'final notice', 'ACTION REQUIRED'... Ever."
- `src/template_engine.py` line 159: Docstring comment: "No 'ACTION REQUIRED' or 'FINAL NOTICE' suffixes (per meeting decision)"
- `src/template_engine.py` line 182-183: Code comment: "No urgency suffixes -- no 'ACTION REQUIRED' or 'FINAL NOTICE' in subject lines. Ever."

**None of these are actual email content -- they are all anti-pattern documentation telling developers NOT to use these phrases.**

**Verdict: PASS** -- Banned text appears only as documentation/guards, never in generated email content.

## Removed Tier References (T3, T4, past_due_40, past_due_50)

### past_due_40 / past_due_50
- **src/**: 0 matches. CLEAN.
- **templates/**: 0 matches. CLEAN.
- **app.py**: 0 matches. CLEAN.
- **config.yaml**: 0 matches. CLEAN.
- **tests/**: Present in `test_tier_classifier.py` lines 73-74, 108, 111, 521 -- these are **assertion tests verifying that PAST_DUE_40 and PAST_DUE_50 do NOT exist** (e.g., `assert not hasattr(Tier, "PAST_DUE_40")`). This is correct test behavior.
- **README.md, swarm/**: Documentation references to the old 5-tier system. Not active code.

### T4 / T5 references in active source code
Found in:
- `src/models.py` line 709: Comment in `TierConfig.find_tier()` docstring mentioning "T4" -- stale comment. **WARNING (INFO)**.
- `src/template_engine.py` line 244: Comment "No T4/T5 escalation tiers" -- acceptable anti-pattern documentation.
- `src/template_engine.py` line 398: Docstring says "T1-T5" -- stale range, should say "T1-T3". **WARNING (INFO)**.
- `src/template_engine.py` line 785: Comment "used in T4, T5" -- stale comment, should say "used in T3 (30+)". **WARNING (INFO)**.
- `src/main.py` line 324: Docstring says "T4, T5" -- stale reference. **WARNING (INFO)**.
- `src/email_queue.py` line 1832: Uses `Tier.T4` -- this file contains old/unrebuilt code. **WARNING**.

**Verdict: PASS** (no functional T4/T5 usage in rebuilt modules; stale comments are cosmetic only)

## Template Count Verification

```
templates/
  coming_due.html
  overdue.html
  past_due_30.html
```

**Exactly 3 templates.** No `past_due_40.html` or `past_due_50.html`. PASS.

## Config Structure (3 tiers)

### config.yaml
Defines exactly 3 tiers:
- `T1`: min_days=-7, max_days=0, label="Coming Due", template="coming_due.html"
- `T2`: min_days=1, max_days=29, label="Overdue", template="overdue.html"
- `T3`: min_days=30, max_days=999, label="30+ Days Past Due", template="past_due_30.html"

CC rules, attachment rules: all reference T1/T2/T3 only. No T4/T5.

### src/config.py DEFAULT_TIERS
Defines exactly 3 tiers matching config.yaml. PASS.

### cc_rules, tier_extra_cc, tier_attachments
All reference T1/T2/T3 only. PASS.

**Verdict: PASS**

## Tier Enum Verification (3 values)

### src/models.py Tier enum (lines 27-38)
```python
class Tier(Enum):
    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"
```
3 values. PASS.

### src/tier_classifier.py Tier enum (lines 26-34)
```python
class Tier(str, Enum):
    COMING_DUE = "Coming Due"
    OVERDUE = "Overdue"
    PAST_DUE = "30+ Days Past Due"
```
3 values. PASS.

**NOTE**: The two Tier enums use different naming conventions:
- `models.py`: `T0`, `T1`, `T2`
- `tier_classifier.py`: `COMING_DUE`, `OVERDUE`, `PAST_DUE`

Both map to the same 3 `.value` strings. This is a dual-enum design pattern (models uses index-style names, classifier uses descriptive names). Not a bug, but worth noting for future refactoring.

**Verdict: PASS**

## Error Handling Review

### src/models.py
- `Invoice.__post_init__`: Auto-assigns tier and detects skip reasons. No uncaught exceptions possible. PASS.
- `EmailDraft.approve()/reject()`: Raises `ValueError` if status is not PENDING. Proper guard. PASS.
- `EmailQueue.export_json()/export_csv()`: Creates parent directories with `mkdir(parents=True, exist_ok=True)`. PASS.

### src/tier_classifier.py
- `classify()`: Handles `None`, `NaN`, `float`, `int`. Robust null/NaN guard with `NaN != NaN` idiom. PASS.
- `classify_batch()`: Handles missing fields gracefully via `.get()`. PASS.

### src/config.py
- `get_config()`: Handles missing YAML file (returns defaults). PASS.
- `_apply_yaml_to_config()`: Uses `hasattr` checks before `setattr`. PASS.
- `SMTPSettings.__post_init__`: Falls back to env vars. PASS.

### src/template_engine.py
- `render_email()`: Raises `ValueError` for empty invoice list. PASS.
- `tier_for_days()` fallback: Falls back to T1 config if no tier matches. PASS.
- `_SanitizingFileLoader`: Strips pseudo-template markers from HTML comments to prevent Jinja2 TemplateSyntaxError. PASS.

### src/contact_resolver.py
- `match_invoice()`: Handles missing attributes via `getattr(obj, attr, default)`. PASS.
- `_compute_similarity()`: Returns 1.0 for exact matches, handles empty strings. PASS.
- Logging at appropriate levels (debug, info, warning). PASS.

### src/data_loader.py
- `_open_workbook()`: Raises `FileNotFoundError` for missing files. PASS.
- `_parse_invoices()`: Validates required columns, warns on parse failures, skips empty rows. PASS.
- `_parse_date()`: Handles datetime, date, Excel serial, string formats, with fallback warnings. PASS.
- `_parse_currency()`: Handles numeric, string with `$`, parenthesized negatives. PASS.

### app.py
- All module imports wrapped in `try/except ImportError`. Graceful degradation. PASS.
- Session state initialization with defaults dict. PASS.
- File upload handling with `st.spinner` and error display. PASS.
- SMTP sending with specific exception handling (`SMTPAuthenticationError`, `SMTPRecipientsRefused`, generic `Exception`). PASS.

**Verdict: PASS**

## Session State Consistency

All session state keys used in `app.py`:

| Key | Init Default | Used In |
|-----|-------------|---------|
| `queue` | `None` | Queue page, preview, export, send |
| `load_result` | `None` | Data loading |
| `selected_email_idx` | `None` | Preview page navigation |
| `page` | `"queue"` | Router, navigation |
| `filter_tiers` | `[]` | Sidebar filters |
| `filter_status` | `[]` | Sidebar filters |
| `generated` | `False` | Queue generation state |
| `do_not_contact` | `[]` | DNC page, data loading |
| `history` | `[]` | History page, export |
| `upload_key` | `0` | File uploader widget |
| `gmail_app_password` | `""` | Settings, SMTP sending |
| `sender_email` | Loaded from settings | Settings, export, send |
| `sender_name` | Loaded from settings | Settings, sidebar, template engine |
| `smtp_configured` | `False` | Settings connection test |
| `send_results` | `[]` | Queue page send results |
| `custom_cc` | Loaded from settings | Settings page |
| `schedule_time` | Loaded from settings | Schedule picker |
| `schedule_timezone` | Loaded from settings | Schedule picker |
| `editing_{idx}` | Dynamic | Preview page edit mode |

All keys initialized in `init_session_state()` are referenced correctly. Dynamic keys (`editing_{idx}`) are accessed with `.get()` fallback. No orphaned or undefined state keys found.

**Verdict: PASS**

## Issues Found

| # | Severity | File | Line | Description |
|---|----------|------|------|-------------|
| 1 | **WARNING** | `app.py` | 85 | Imports `get_overdue_timeframe_description` from `src.tier_classifier` -- function was removed in Wave 2. Import fails silently due to try/except guard, but causes `CLASSIFIER_AVAILABLE = False`, disabling tier enrichment features in the Streamlit UI. |
| 2 | INFO | `src/models.py` | 709 | Stale comment references "T4" in `TierConfig.find_tier()` docstring. Should say "T2". |
| 3 | INFO | `src/template_engine.py` | 398 | Stale docstring says "T1-T5". Should say "T1-T3". |
| 4 | INFO | `src/template_engine.py` | 785 | Stale comment says "used in T4, T5". Should say "used in T3 (30+)". |
| 5 | INFO | `src/main.py` | 324 | Stale docstring references "T4, T5". Should say "T1, T2, T3". |
| 6 | WARNING | `src/email_queue.py` | 1832 | References `Tier.T4` which does not exist in the 3-tier enum. This file appears to be old/unrebuilt code. |
| 7 | INFO | N/A | N/A | Dual Tier enum design: `models.py` uses T0/T1/T2, `tier_classifier.py` uses COMING_DUE/OVERDUE/PAST_DUE. Same values but different attribute names. Not a bug but a future refactoring candidate. |

## Verdict

**PASS WITH WARNINGS**

The core 3-tier consolidation is correctly implemented across all rebuilt modules:
- All 7 Python files pass syntax validation
- No banned text ("FINAL NOTICE", "ACTION REQUIRED") appears in generated email content
- No `past_due_40` / `past_due_50` references in active source or templates
- Exactly 3 templates, 3 config tiers, 3 enum values
- Config structure is consistent (T1/T2/T3)
- Error handling is thorough and defensive
- Session state is consistent with no orphaned keys

**2 warnings** that should be addressed:
1. `app.py` line 85: Remove `get_overdue_timeframe_description` from the import list (it was removed from tier_classifier in Wave 2). This silently disables the classifier integration in the Streamlit app.
2. `src/email_queue.py` line 1832: References non-existent `Tier.T4`. This file needs Wave 2 alignment or is dead code.

**5 INFO items**: Stale comments referencing old 5-tier system (T4/T5) in docstrings. Cosmetic only, no functional impact.
