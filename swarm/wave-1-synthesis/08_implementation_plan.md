# Implementation Plan
## Document: 08 - File-by-File Change Specification
## Timestamp: 2026-02-14
## Author: Wave 1 Implementation Planner (Opus)
## Input: Wave 0 Reports 01-06, all source files, all templates, config.yaml, app.py

---

## Overview

This document provides a precise, file-by-file change specification for collapsing the AR email automation from a 5-tier system to a 3-tier system, aligning templates with Callie's canonical versions, fixing the subject line logic, removing all "final notice" / "ACTION REQUIRED" language, and enabling UI persistence. Each section includes current state with line references, exact changes required, dependencies, and testing implications.

**Key Principle**: There are TWO independent `Tier` enums (one in `models.py`, one in `tier_classifier.py`). Both must be consolidated. The `models.py` version is the one used by `app.py` and `EmailDraft`; the `tier_classifier.py` version is used by the classification engine and template engine. They must agree.

---

## Change Order (Dependency-Sorted)

### Phase 1: Data Model Changes

#### 1.1 src/models.py
- **Current line count**: 690 lines
- **Current state summary**:
  - `Tier` enum (lines 27-56): 5 values T0-T4 mapping to "Coming Due", "Overdue", "30+ Days Past Due", "40+ Days Past Due", "50+ Days Past Due"
  - `Tier.from_days()` (lines 44-55): Classifies into 5 tiers with boundaries at 0, 29, 39, 49
  - `TierConfig` dataclass (lines 586-690): Configures per-tier settings, `default_tiers()` returns 5 configs
  - `TierConfig.default_tiers()` (lines 611-673): Returns 5 `TierConfig` instances with 5 different `template_name` values ("coming_due", "overdue", "past_due_30", "past_due_40", "past_due_50")
  - `Invoice.__post_init__()` (lines 146-150): Auto-assigns `self.tier = Tier.from_days(self.days_past_due)`
  - `Invoice.tier_label` property (line 182-184): Returns `self.tier.value` (static label)
  - `EmailDraft.build_subject()` (lines 353-363): Uses `self.tier.value` as the subject suffix -- always static

- **Required changes**:

  1. **Collapse `Tier` enum from 5 to 3 values** (lines 27-56):
     ```python
     class Tier(Enum):
         T0 = "Coming Due"
         T1 = "Overdue"
         T2 = "30+ Days Past Due"
     ```
     Remove T3 ("40+ Days Past Due") and T4 ("50+ Days Past Due").

  2. **Update `Tier.from_days()`** (lines 44-55):
     ```python
     @classmethod
     def from_days(cls, days_past_due: int | float) -> Tier:
         if days_past_due <= 0:
             return cls.T0
         if days_past_due <= 29:
             return cls.T1
         return cls.T2
     ```
     Remove the 39/49 boundary checks. Everything 30+ maps to T2.

  3. **Update `TierConfig.default_tiers()`** (lines 611-673):
     Reduce to 3 entries. Change T0 `min_days` from -999 to -7 (per meeting: Coming Due = -7 to 0). Remove T3 and T4 entries entirely. Set T2 `max_days=None` (unbounded). All three use `template_name` values: "coming_due", "overdue", "past_due_30".

     ```python
     return [
         cls(tier_name=Tier.T0, min_days=-7, max_days=0,
             template_name="coming_due", cc_rules=list(always_cc),
             attachment_rules=AttachmentRule.ACH_FORM, include_ocm_warning=False),
         cls(tier_name=Tier.T1, min_days=1, max_days=29,
             template_name="overdue", cc_rules=list(always_cc),
             attachment_rules=AttachmentRule.ACH_FORM, include_ocm_warning=False),
         cls(tier_name=Tier.T2, min_days=30, max_days=None,
             template_name="past_due_30", cc_rules=list(always_cc),
             attachment_rules=AttachmentRule.ACH_FORM, include_ocm_warning=True),
     ]
     ```

  4. **Add dynamic subject label helper** to `Invoice` or as a standalone function:
     ```python
     @property
     def dynamic_subject_label(self) -> str:
         """Compute dynamic subject label for 30+ tier emails."""
         if self.days_past_due < 30:
             return self.tier.value
         bucket = (self.days_past_due // 10) * 10
         return f"{bucket}+ Days Past Due"
     ```

  5. **Update `EmailDraft.build_subject()`** (lines 353-363): Use `dynamic_subject_label` from the primary invoice instead of `self.tier.value` when tier is T2.

  6. **Update docstring** (lines 28-36): Change to reflect 3-tier system.

- **Dependencies**: None -- this is the foundation layer.
- **Tests affected**: Any test that references `Tier.T3`, `Tier.T4`, `Tier.from_days(45)`, or `default_tiers()` with 5 entries will break. Update test assertions for 3-tier output. Tests for `from_days(45)` should now return `Tier.T2`, not `Tier.T3`.

---

#### 1.2 src/tier_classifier.py
- **Current line count**: 791 lines
- **Current state summary**:
  - Independent `Tier(str, Enum)` (lines 28-38): 5 values COMING_DUE through PAST_DUE_50
  - Boundary constants (lines 48-51): `TIER_BOUNDARY_OVERDUE=1`, `TIER_BOUNDARY_PAST_DUE_30=30`, `TIER_BOUNDARY_PAST_DUE_40=40`, `TIER_BOUNDARY_PAST_DUE_50=50`
  - `CCRules` dataclass (lines 76-94): Defines CC routing flags per tier
  - `TierMetadata` dataclass (lines 101-128): Full metadata per tier
  - `TIER_METADATA` dict (lines 131-253): 5 entries with separate template names, urgency levels, CC rules, subject labels
  - `classify()` function (lines 286-365): 5-way branching classification
  - `classify_batch()` function (lines 368-460): Batch classification with skip logic
  - `get_overdue_timeframe_description()` (lines 498-547): Dynamic phrases like "nearing two weeks past due" -- **MUST BE REMOVED** per meeting (use static "overdue")
  - `summarize_batch()` (lines 554-616): Iterates over all `Tier` enum values
  - Self-test block (lines 677-791): Contains 5-tier test cases

- **Required changes**:

  1. **Collapse `Tier` enum** (lines 28-38):
     ```python
     class Tier(str, Enum):
         COMING_DUE = "Coming Due"
         OVERDUE = "Overdue"
         PAST_DUE = "30+ Days Past Due"
     ```
     Remove `PAST_DUE_40` and `PAST_DUE_50`.

  2. **Remove boundary constants for 40+ and 50+** (lines 50-51): Delete `TIER_BOUNDARY_PAST_DUE_40` and `TIER_BOUNDARY_PAST_DUE_50`.

  3. **Simplify `TIER_METADATA`** (lines 131-253): Remove entries for `PAST_DUE_40` and `PAST_DUE_50`. Update `PAST_DUE_30` entry to rename to `PAST_DUE` with `max_days=None`, `subject_label="30+ Days Past Due"`.

  4. **Simplify `classify()`** (lines 337-348): Remove the 40+ and 50+ branches:
     ```python
     if days_past_due >= TIER_BOUNDARY_PAST_DUE_30:
         tier = Tier.PAST_DUE
     elif days_past_due >= TIER_BOUNDARY_OVERDUE:
         tier = Tier.OVERDUE
     else:
         tier = Tier.COMING_DUE
     ```

  5. **Remove `get_overdue_timeframe_description()`** entirely (lines 498-547): The canonical T2 template uses static "overdue" per Callie's Feb 11 fix. This function is no longer needed.

  6. **Add `get_dynamic_subject_label()` function**:
     ```python
     def get_dynamic_subject_label(days_past_due: int) -> str:
         """Compute the dynamic subject line label for 30+ tier emails.
         Returns 'Coming Due' for <=0, 'Overdue' for 1-29,
         and '{N}0+ Days Past Due' for 30+."""
         if days_past_due <= 0:
             return "Coming Due"
         if days_past_due <= 29:
             return "Overdue"
         bucket = (days_past_due // 10) * 10
         return f"{bucket}+ Days Past Due"
     ```

  7. **Update self-test block** (lines 677-791): Change expected tiers for 40+ and 50+ test cases to `Tier.PAST_DUE`. Remove separate 40+/50+ assertions.

  8. **Update `summarize_batch()`** (lines 586-616): The `for tier in Tier` loop will automatically work with 3 values.

- **Dependencies**: None directly, but the `Tier` import in `template_engine.py` comes from BOTH `models.py` AND `tier_classifier.py`. The two enums MUST be reconciled. **Recommendation**: Make `tier_classifier.py` import `Tier` from `models.py` instead of defining its own, OR eliminate the `models.py` `Tier` and use `tier_classifier.py`'s. The template engine currently imports from both.

  **CRITICAL DECISION**: `app.py` imports `Tier` from `src.models` (line 56). `template_engine.py` imports `Tier` from `src.models` (line 57) AND `classify` from `src.tier_classifier` (line 59). The `classify()` function returns `tier_classifier.Tier` values which are then compared to `models.Tier` values. **These two enums are different Python objects.** Either:
  - (A) Delete the `Tier` enum from `tier_classifier.py` and import from `models.py` everywhere, OR
  - (B) Delete from `models.py` and import from `tier_classifier.py` everywhere.

  **Recommendation**: Option (A) -- keep `Tier` in `models.py` (it's the core data model), import it into `tier_classifier.py`.

- **Tests affected**: All tier classifier tests expecting 5 tiers. `get_overdue_timeframe_description` tests must be removed. `classify(45)` should now return `PAST_DUE` not `PAST_DUE_40`.

---

### Phase 2: Configuration

#### 2.1 config.yaml
- **Current line count**: 243 lines
- **Current state summary**:
  - `tiers` section (lines 14-49): 5 tier definitions T1-T5 with separate template files
  - T1 boundaries: min=-3, max=3 (**WRONG**: should be -7 to 0 per meeting)
  - T2 boundaries: min=4, max=29 (**WRONG**: should be 1 to 29 per meeting)
  - T3: 30-39, T4: 40-49, T5: 50-999 -- all should collapse into one T3: 30-999
  - T5 has `sender_override: "mario@piccplatform.com"` -- **REMOVE** (no sender escalation per meeting)
  - `cc_rules.tier_extra_cc` (lines 67-71): Has T1-T5 entries
  - `attachment_rules.tier_attachments` (lines 85-105): Has T1-T5 entries with T4/T5 having "flag" for bol/invoice_pdf
  - `escalation_sender` section (lines 142-147): Used for T5 sender override -- **REMOVE**
  - `review_flags.tier_gte_management_escalation` (line 230): References "T5" -- update to "T3"
  - `schedule.run_time` (line 241): "07:00" -- should be 07:00 PT per meeting, but config says ET. Meeting says 7 AM Pacific = 10 AM Eastern. Config timezone says "America/New_York" (ET). **Clarify**: The schedule time should be "10:00" if timezone is ET, or change timezone to "America/Los_Angeles" and keep "07:00".

- **Required changes**:

  1. **Replace tiers section** (lines 14-49):
     ```yaml
     tiers:
       T1:
         name: "T1"
         min_days: -7
         max_days: 0
         label: "Coming Due"
         template_file: "coming_due.html"
       T2:
         name: "T2"
         min_days: 1
         max_days: 29
         label: "Overdue"
         template_file: "overdue.html"
       T3:
         name: "T3"
         min_days: 30
         max_days: 999
         label: "30+ Days Past Due"
         template_file: "past_due_30.html"
     ```
     Delete T4 and T5 entries entirely. Remove `sender_override` from all tiers.

  2. **Update `cc_rules.tier_extra_cc`** (lines 67-71): Remove T4 and T5 entries.

  3. **Update `attachment_rules.tier_attachments`** (lines 85-105): Remove T4 and T5 entries. T3 keeps `ach_form: true, bol: false, invoice_pdf: false`.

  4. **Remove `escalation_sender` section** (lines 142-147): No sender escalation at any tier per meeting decision.

  5. **Update `review_flags.tier_gte_management_escalation`** (line 230): Change from `"T5"` to `"T3"`.

  6. **Update `schedule`** (lines 239-242): Change to `run_time: "07:00"`, `timezone: "America/Los_Angeles"` (Callie schedules for 7 AM PT).

- **Dependencies**: Must happen after models.py/tier_classifier.py changes, because `src/config.py` parses this YAML and creates `TierConfig` objects that reference tier names.
- **Tests affected**: Any config-loading test expecting 5 tiers.

---

### Phase 3: Template Engine

#### 3.1 src/template_engine.py
- **Current line count**: 1152 lines
- **Current state summary**:
  - Imports `get_overdue_timeframe_description` from `tier_classifier` (line 61) -- **REMOVE**
  - `_T4_DEADLINE_BIZ_DAYS = 7` and `_T5_DEADLINE_BIZ_DAYS = 5` (lines 80-81) -- **CONSOLIDATE** to single deadline constant
  - `_get_ocm_status_phrase()` (lines 137-151): T5-specific -- **REMOVE**
  - `_get_days_until_ocm()` (lines 154-159): Keep (useful for 30+ template)
  - `build_subject_line()` (lines 166-209): Appends " - ACTION REQUIRED" for 40+ and " - FINAL NOTICE" for 50+ (lines 204-207) -- **REMOVE these suffixes**
  - `build_cc_list()` (lines 216-302): Has T4/T5-specific escalation logic adding extra contacts (lines 278-288) -- **REMOVE T4/T5 escalation**
  - `build_attachment_list()` (lines 309-348): References T4/T5 tier_rules -- **SIMPLIFY**
  - `_build_invoice_block()` (lines 429-459): Has T4/T5-specific comments about field order -- **SIMPLIFY**
  - `TemplateEngine._resolve_sender()` (lines 736-764): T5 sender escalation logic -- **REMOVE escalation**
  - `TemplateEngine._build_context()` (lines 770-907):
    - Line 848-854: Sets `OVERDUE_TIMEFRAME` using `get_overdue_timeframe_description()` -- **REPLACE with static "overdue"**
    - Lines 857-871: T4-specific `DAYS_UNTIL_OCM_REPORT` and `PAYMENT_DEADLINE` -- **MOVE to T3 (30+)**
    - Lines 874-880: T5-specific `OCM_STATUS_PHRASE` and `FINAL_PAYMENT_DEADLINE` -- **REMOVE**
  - Self-test block (lines 1020-1151): References T5 test cases

- **Required changes**:

  1. **Remove import** of `get_overdue_timeframe_description` (line 61). Keep `classify` and `OCM_REPORTING_DAY`.

  2. **Remove `_get_ocm_status_phrase()`** (lines 137-151): Entirely AI-fabricated.

  3. **Fix `build_subject_line()`** (lines 202-208): Remove the "ACTION REQUIRED" and "FINAL NOTICE" suffix logic entirely:
     ```python
     # DELETE lines 202-208 (the if/elif block)
     # Just use: subject_label = tier_label
     ```
     The dynamic label ("40+ Days Past Due", "50+ Days Past Due") should be passed IN as `tier_label` by the caller, not computed here.

  4. **Add dynamic subject label computation** in `render_email()` (around line 644-648): Instead of passing `tier_cfg.label` to `build_subject_line()`, compute the dynamic label:
     ```python
     if primary_invoice.days_past_due >= 30:
         bucket = (primary_invoice.days_past_due // 10) * 10
         subject_tier_label = f"{bucket}+ Days Past Due"
     else:
         subject_tier_label = tier_cfg.label
     subject = build_subject_line(
         store_name=primary_invoice.store_name,
         invoice_numbers=invoice_numbers,
         tier_label=subject_tier_label,
     )
     ```

  5. **Simplify `build_cc_list()`** (lines 278-288): Remove T4/T5 escalation blocks. All tiers get the same base CC + rep.

  6. **Remove `_resolve_sender()` escalation** (lines 754-762): Always return default sender. Delete the `sender_override` branch.

  7. **Fix `_build_context()`**:
     - Lines 848-854: Replace `OVERDUE_TIMEFRAME` with static string:
       ```python
       ctx["OVERDUE_TIMEFRAME"] = "overdue"
       ```
       Remove the conditional check for `tier_cfg.name == "T2"`.
     - Lines 857-871 (T4 block): **Move the payment deadline logic to work for T3 (30+)**. Change `tier_cfg.name == "T4"` to `tier_cfg.name == "T3"` (or check `primary.days_past_due >= 30`).
     - Lines 874-880 (T5 block): **Remove entirely**. Delete `OCM_STATUS_PHRASE` and `FINAL_PAYMENT_DEADLINE`.
     - Keep `PAYMENT_DEADLINE` for 30+ emails (Travis approved this feature).

  8. **Update self-test block** (lines 1020-1151): Remove T5 test case, update expected outputs.

  9. **Remove `_T5_DEADLINE_BIZ_DAYS`** (line 81). Rename `_T4_DEADLINE_BIZ_DAYS` to `_PAST_DUE_DEADLINE_BIZ_DAYS`.

- **Dependencies**: Depends on models.py Tier consolidation (Phase 1.1) and tier_classifier.py changes (Phase 1.2). Also depends on config.yaml (Phase 2.1) since `tier_for_days()` reads config tier boundaries.
- **Tests affected**: Subject line tests expecting "ACTION REQUIRED" or "FINAL NOTICE". Context building tests for T4/T5 variables.

---

### Phase 4: Template Files

#### 4.1 templates/coming_due.html (MINOR FIX)
- **Current line count**: 120 lines
- **Current state**:
  - Attachment line (line 68): `"Attached is the Nabis ACH payment form (PDF) to facilitate your payment."`
  - Canonical says: `"Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment."`
  - HTML comment trigger boundary (line 11): Says "within 3 days" -- should say "-7 to 0 days"

- **Required changes**:
  1. **Line 68**: Change `"Attached is the Nabis ACH payment form (PDF) to facilitate your payment."` to `"Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment."`
  2. **Line 11**: Update comment from "within 3 days" to "-7 to 0 days (before or on due date)"

- **Dependencies**: None
- **Tests affected**: None (HTML content test if exists)

#### 4.2 templates/overdue.html (MODERATE FIX)
- **Current line count**: 151 lines
- **Current state**:
  - Trigger range in comment (line 11): "4-29 days past due" -- should be "1-29 days past due"
  - OVERDUE_TIMEFRAME variable (line 64): `"your invoice is {{OVERDUE_TIMEFRAME}}"` -- **REPLACE with static "overdue"**
  - Comment block (lines 55-62): Documents dynamic timeframe calculation -- **REMOVE or update**

- **Required changes**:
  1. **Line 64**: Change `"your invoice is {{OVERDUE_TIMEFRAME}}"` to `"your invoice is overdue"`. Remove the Jinja2 variable entirely -- use static text.
  2. **Line 11**: Change trigger from "4-29 days past due" to "1-29 days past due"
  3. **Lines 55-62**: Remove or update the OVERDUE_TIMEFRAME comment block since the variable is no longer used.

- **Dependencies**: Must coordinate with template_engine.py changes (the engine can stop providing the variable, but the template must stop referencing it first, or vice versa -- either order works because Jinja2 ignores undefined variables with `trim_blocks`).
- **Tests affected**: None

#### 4.3 templates/past_due_30.html (REBUILD from canonical)
- **Current line count**: 160 lines
- **Current state**:
  - **Extra paragraph** (lines 62-64): "As a reminder, our standard payment terms require invoices to be settled within the agreed timeframe. This invoice is now over 30 days past due." -- **NOT IN CANONICAL, REMOVE**
  - Attachment line (line 87): `"Attached is the Nabis ACH payment form (PDF) to facilitate your payment."` -- should be `"Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment."`
  - Payment request (line 101): `"past-due invoice"` (singular) -- canonical uses `"past-due invoices"` (plural)
  - Closing em-dash (line 115): Uses `" -- "` (two hyphens with spaces) -- canonical uses em-dash (`--`)

- **Required changes**:
  1. **Delete lines 61-65** (the "payment terms reminder" paragraph + surrounding `<br>` tag): This paragraph is AI-fabricated and not in canonical.
  2. **Line 87**: Change attachment line to canonical: `"Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment."`
  3. **Line 101**: Change `"past-due invoice"` to `"past-due invoices"` (canonical plural).
  4. **Add `{{PAYMENT_DEADLINE}}` line**: Per meeting, Travis wants a dynamic deadline date on all 30+ emails. Add after the "We kindly ask..." paragraph:
     ```html
     {% if PAYMENT_DEADLINE %}
     <br>
     <div style="font-family:Arial,Helvetica,sans-serif;">
       <strong>We request that payment be submitted by {{PAYMENT_DEADLINE}} to avoid account restrictions or OCM reporting.</strong>
     </div>
     {% endif %}
     ```
  5. **Update comment** (line 10): Change trigger from "30-39 days" to "30+ days" since this is now the ONLY past-due template.

- **Dependencies**: Template engine must provide `PAYMENT_DEADLINE` variable in the context for 30+ emails (Phase 3.1).
- **Tests affected**: Template rendering tests

#### 4.4 templates/past_due_40.html -- DELETE
- **Current line count**: 156 lines
- **Action**: Delete this file entirely. It is AI-fabricated and contains:
  - "second notice" language (line 51)
  - "ACTION REQUIRED" in subject (line 18)
  - "DAYS_UNTIL_OCM_REPORT" countdown (line 58)
  - Account hold warning (lines 89-91)
  - Explicit payment deadline with {{PAYMENT_DEADLINE}} (lines 103-105)
- **Dependencies**: Template engine must stop referencing `past_due_40.html`. Config must not reference it.
- **Tests affected**: Any test rendering the T4 template.

#### 4.5 templates/past_due_50.html -- DELETE
- **Current line count**: 161 lines
- **Action**: Delete this file entirely. It contains:
  - "This is a final notice" (line 55) -- **explicitly banned by Travis**
  - "FINAL NOTICE" in subject (line 19) -- **explicitly banned**
  - Red-bordered OCM warning box (line 61)
  - Account hold/flag statement (lines 93-94)
  - Collections/legal threat (line 94)
  - {{FINAL_PAYMENT_DEADLINE}} with 48-hour ultimatum (line 108)
  - {{OCM_STATUS_PHRASE}} (line 62)
  - {{SENDER_PHONE_LINE}} for escalation sender (line 138)
- **Dependencies**: Template engine must stop referencing `past_due_50.html`. Config must not reference it.
- **Tests affected**: Any test rendering the T5 template.

---

### Phase 5: Contact Resolution

#### 5.1 src/contact_resolver.py
- **Current line count**: 835 lines
- **Current state**: Well-structured fuzzy matching system that resolves invoice-to-contact matches using license number + store name. Uses `_select_primary_contact()` to pick ONE contact by title relevance (AP > Accounting > Owner).
- **Problems identified by Wave 0**:
  - Returns only ONE contact per match -- meeting SOP requires MULTIPLE recipients (primary AND billing)
  - No Notion API integration
  - No Brand AR Summary XLSX integration
  - No contact SOURCE tracking (Nabis vs. Revelry)
  - No deprioritization of Revelry-sourced contacts

- **Required changes (for this sprint -- go-live workaround)**:
  1. **No major refactoring needed for go-live**. The meeting established that Callie will manually paste recipient emails using the Quick Edit TO field (which already works in app.py). Contact resolver improvements are a P2/future enhancement.
  2. **Minor fix**: Ensure `match_invoice()` returns ALL emails from the matched contact (not just one), so the Quick Edit TO field can pre-populate with multiple addresses. Currently `_select_primary_contact()` returns one contact. Change `MatchResult` to include `all_emails: list[str]` from the matched contact.
  3. **Add a `contact_emails` property to `MatchResult`** that returns all available emails:
     ```python
     @property
     def contact_emails(self) -> list[str]:
         if self.contact is None:
             return []
         if hasattr(self.contact, 'all_emails') and self.contact.all_emails:
             return self.contact.all_emails
         if hasattr(self.contact, 'email') and self.contact.email:
             return [self.contact.email]
         return []
     ```

- **Dependencies**: None for go-live. Future Notion API integration depends on API key setup.
- **Tests affected**: Minimal -- only if adding the `contact_emails` property.

#### 5.2 src/data_loader.py
- **Current line count**: 1030 lines
- **Current state**: Well-structured XLSX parser. Handles Overdue sheet + Managers sheet. Creates `Invoice` and `Contact` objects.
- **Problems**:
  - Does not load Brand AR Summary XLSX (future enhancement)
  - Uses `models.Tier` enum which will change from 5 to 3 values

- **Required changes**:
  1. **No changes needed for Tier consolidation**: The `Tier` enum is used via `Invoice.__post_init__()` which calls `Tier.from_days()`. Once `models.py` is updated, `data_loader.py` automatically gets the 3-tier behavior.
  2. **`_parse_invoice_status()` references and `Tier` import** (line 48): Already imports `Tier` from `.models` -- no change needed since we're keeping the import path.
  3. **`print_summary()` (line 199)**: Iterates `for tier in Tier` -- will automatically work with 3 tiers after models.py change.
  4. **Future**: Add `load_brand_ar_summary()` function to ingest the Nabis Brand AR Summary XLSX as supplemental contact source. **NOT NEEDED FOR GO-LIVE**.

- **Dependencies**: Depends on models.py Tier consolidation (Phase 1.1).
- **Tests affected**: Any test checking tier distribution output from `print_summary()`.

---

### Phase 6: UI / App

#### 6.1 app.py
- **Current line count**: 2070 lines
- **Current state summary (key sections)**:
  - Imports `Tier` from `src.models` (line 56) and `Tier as ClassifierTier` from `src.tier_classifier` (line 86)
  - `TIER_COLORS` dict (lines 120-126): 5 entries for 5 tier labels
  - `init_session_state()` (lines 339-361): Default sender email is `"laura@piccplatform.com"`
  - `tier_badge_html()` (lines 370-376): Uses `TIER_COLORS` dict
  - `_build_sample_html()` (lines 641-705): Fallback HTML builder with 3-way branch (T0, T1, else) -- already close to 3-tier
  - Sidebar `use_default` checkbox (lines 849-853): Defaults to `True` -- should be removed or default to `False`
  - Sidebar filter `all_tiers` (line 912): `[t.value for t in Tier]` -- will automatically reflect 3 tiers
  - Queue page batch action "Approve Coming Due" (line 1079): Uses `Tier.T0` -- still valid
  - Preview page "From" display (line 1290): **HARDCODED "Laura"** -- should use `st.session_state.sender_name`
  - Edit mode (lines 1404-1512): Quick Edit and HTML Edit tabs -- **ALREADY FUNCTIONAL**
  - Settings page (lines 1828-2028): No save button, tier boundaries shown as text inputs

- **Required changes**:

  1. **Update `TIER_COLORS` dict** (lines 120-126): Remove "40+ Days Past Due" and "50+ Days Past Due" entries. Keep 3 entries. Add a fallback for dynamic labels like "40+ Days Past Due" when used as badge labels by computing color from days range:
     ```python
     TIER_COLORS = {
         "Coming Due":          {"bg": "#d4edda", "text": "#155724", "icon": ""},
         "Overdue":             {"bg": "#fff3cd", "text": "#856404", "icon": ""},
         "30+ Days Past Due":   {"bg": "#f8d7da", "text": "#721c24", "icon": ""},
     }
     ```
     Since `draft.tier.value` will always be one of these 3 for the badge, and the dynamic label only appears in the subject line, this is sufficient.

  2. **Fix the "From" display** (line 1290): Change from:
     ```python
     st.markdown(f"Laura <{st.session_state.sender_email}>")
     ```
     To:
     ```python
     sender = st.session_state.sender_name or "PICC Accounts Receivable"
     st.markdown(f"{sender} <{st.session_state.sender_email}>")
     ```

  3. **Remove or fix "Use default file" checkbox** (lines 849-853): Per meeting, this is confusing. Either:
     - (A) Remove entirely (recommended for go-live). If no file uploaded, show message.
     - (B) Change default to `False` and add clearer label.

  4. **Add "Save Settings" button** to `render_settings_page()` (after line 1937): Add a button that writes changed tier boundaries and CC list back to session state (and optionally to config.yaml):
     ```python
     if st.button("Save Settings", type="primary"):
         # Persist CC list to session state
         st.session_state["custom_cc"] = [
             e.strip() for e in cc_text.split("\n") if e.strip()
         ]
         st.success("Settings saved for this session!")
     ```

  5. **Remove `ClassifierTier` import** (line 86) if we consolidate to a single `Tier` enum. Or update the import alias.

  6. **Update sender_email default** (line 353): Change from `"laura@piccplatform.com"` to Callie's email or keep as configurable. Per meeting, Callie sends from her own PICC email. Leave as configurable.

  7. **Remove references to T3/T4 tier values in code**: Search for any string comparison against "40+ Days Past Due" or "50+ Days Past Due" in conditional logic. The `_build_sample_html()` function (lines 641-705) already uses a 3-way branch (T0, T1, else), so it naturally handles the consolidation.

  8. **Update `_build_sample_html()` fallback** (lines 641-705): Ensure the "else" branch does not contain "final notice" or escalation language. Currently it uses the 30+ canonical opening -- **this is correct, no change needed**.

  9. **Days color thresholds** (lines 1185-1192): Currently uses `>= 50` for red color. With 3 tiers, any 30+ invoice is the highest tier. Consider changing `>= 50` to `>= 45` or keeping as-is for visual differentiation (this is display-only, not logic).

- **Dependencies**: Depends on all Phase 1-4 changes since app.py imports from models, tier_classifier, template_engine, and config.
- **Tests affected**: Integration tests if they exist. Manual QA is primary testing method for Streamlit UI.

---

## Critical Path

```
Phase 1 (MUST be first):
  1.1 models.py (Tier enum + TierConfig) ───┐
                                              ├──> Phase 2: config.yaml
  1.2 tier_classifier.py (classify + metadata)┘
                                                     │
                                                     v
Phase 3: template_engine.py ──> Phase 4: templates/ (rebuild/delete)
                                                     │
                                                     v
                                              Phase 5: contact_resolver.py (minor)
                                              Phase 5: data_loader.py (no changes)
                                                     │
                                                     v
                                              Phase 6: app.py (UI fixes)
```

**Strict ordering**:
1. `models.py` and `tier_classifier.py` can be done in parallel (or sequentially -- they must agree on enum values)
2. `config.yaml` must be updated after models.py changes
3. `template_engine.py` depends on both models.py AND tier_classifier.py AND config.yaml
4. Template files can be modified in parallel with template_engine.py changes
5. `contact_resolver.py` and `data_loader.py` are independent of template changes
6. `app.py` must be last since it imports from everything

---

## Risk Areas

### 1. Dual Tier Enum Problem (HIGH RISK)
`models.py` and `tier_classifier.py` each define their own `Tier` enum. `template_engine.py` imports from both. If they are not identical, comparisons like `draft.tier == Tier.T2` will silently fail because Python enums from different classes are never equal. **This is likely the source of existing bugs.**

**Mitigation**: Consolidate to a single `Tier` definition in `models.py`. Have `tier_classifier.py` import from `models.py`. Update all imports.

### 2. Config YAML Parsing (MEDIUM RISK)
`src/config.py` (not read in detail) parses `config.yaml` and creates `TierConfig` objects. If it hardcodes expectations about tier count or tier names (T4, T5), it will break when those are removed.

**Mitigation**: Read `src/config.py` before implementing. Check for hardcoded tier name references.

### 3. Template Variables No Longer Provided (LOW RISK)
If `past_due_30.html` references `{{OVERDUE_TIMEFRAME}}` or `{{OCM_STATUS_PHRASE}}` (it doesn't currently, but the template engine provides them as fallbacks), removing them from the context could cause Jinja2 `UndefinedError`.

**Mitigation**: The template engine uses `trim_blocks=True` and provides fallback empty strings for most variables. As long as `past_due_30.html` doesn't reference T4/T5-specific variables, this is safe. The current `past_due_30.html` does NOT reference them.

### 4. Session State Reset on Streamlit Cloud (MEDIUM RISK)
Streamlit Cloud resets session state on server restart. Settings changes, Gmail app password, and DNC list are all session-only. This is a known limitation noted in Wave 0 Report 06.

**Mitigation**: For go-live, instruct Callie to do entire workflow in one session. Future: persist settings to disk or database.

### 5. "Final Notice" Grep (LOW RISK but HIGH IMPACT)
Any remaining "final notice" text in templates, code, or comments would be a legal/relationship risk if sent to customers.

**Mitigation**: After all changes, run `grep -ri "final.notice" .` across the entire project to verify zero instances remain in any sendable content. Comments/documentation are acceptable to keep for historical context but should be marked as "REMOVED".

---

## Summary of Files Changed

| File | Action | Lines Changed | Effort |
|------|--------|---------------|--------|
| `src/models.py` | Major refactor | ~80 lines | 1-2 hours |
| `src/tier_classifier.py` | Major refactor | ~200 lines | 2-3 hours |
| `config.yaml` | Restructure | ~40 lines | 30 min |
| `src/template_engine.py` | Major refactor | ~100 lines | 2-3 hours |
| `templates/coming_due.html` | Minor fix | 2 lines | 10 min |
| `templates/overdue.html` | Moderate fix | 5 lines | 20 min |
| `templates/past_due_30.html` | Rebuild body | 15 lines | 30 min |
| `templates/past_due_40.html` | **DELETE** | -156 lines | 1 min |
| `templates/past_due_50.html` | **DELETE** | -161 lines | 1 min |
| `src/contact_resolver.py` | Minor enhancement | 10 lines | 20 min |
| `src/data_loader.py` | No changes needed | 0 lines | 0 min |
| `app.py` | Moderate fixes | ~30 lines | 1-2 hours |

**Total estimated effort**: 8-12 hours of focused development.

---

## Pre-Flight Checklist (Before Go-Live)

- [ ] `grep -ri "final.notice"` returns zero results in sendable content
- [ ] `grep -ri "action.required"` returns zero results in sendable content
- [ ] `grep -ri "second.notice"` returns zero results in sendable content
- [ ] `grep -ri "past_due_40"` returns zero results (file deleted, no references)
- [ ] `grep -ri "past_due_50"` returns zero results (file deleted, no references)
- [ ] `Tier` enum has exactly 3 values in models.py
- [ ] `Tier` enum in tier_classifier.py is eliminated (imports from models.py)
- [ ] config.yaml has exactly 3 tier entries
- [ ] Only 3 HTML template files exist in templates/
- [ ] Subject line for 45 days past due reads "40+ Days Past Due" (not "50+" or "30+")
- [ ] Subject line for 55 days past due reads "50+ Days Past Due"
- [ ] Subject line never contains "ACTION REQUIRED" or "FINAL NOTICE"
- [ ] T2 (Overdue) email body says "overdue" not "nearing two weeks past due"
- [ ] T3 (30+) email body does NOT contain "payment terms reminder" paragraph
- [ ] T3 (30+) email body says "past-due invoices" (plural) not "past-due invoice"
- [ ] Preview page "From:" shows sender name from session state, not hardcoded "Laura"
- [ ] Coming Due tier boundary is -7 to 0 (not -3 to 3)
- [ ] Overdue tier boundary is 1 to 29 (not 4 to 29)

---

*End of Document 08 - Implementation Plan*
