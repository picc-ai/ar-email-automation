# Test Plan
## Document: 09 - Test Specification
## Timestamp: 2026-02-14
## Agent: Wave 1 Test Planner (opus)
## Input files read:
- Wave 0 reports: 01 through 06 (workflow, data flow, template, UX, contact logic, blockers)
- Current test files: test_models.py, test_tier_classifier.py, test_data_loader.py, test_contact_resolver.py, test_integration.py, conftest.py

## Verdict: The current test suite has 180+ tests across 5 files with excellent coverage of the 5-tier system. The tier consolidation (5 to 3) will BREAK approximately 45-55 tests across all files. The overdue timeframe description function must be removed entirely (13+ tests). New tests are needed for dynamic subject line generation, canonical template text validation, "final notice" prohibition, and the full upload-classify-generate-preview flow under the 3-tier model.

---

## 1. Current Test Inventory

| Test File | Test Count | Coverage Area | Will Break? |
|-----------|-----------|---------------|-------------|
| `test_models.py` | ~85 tests | Tier enum (5 values), Invoice auto-tier, Contact parsing, EmailDraft subject building, EmailQueue CRUD, TierConfig matching (5 tiers) | **YES** -- Tier enum assertions, from_days() parametrized cases, TierConfig defaults, approve_by_tier references to T3/T4 |
| `test_tier_classifier.py` | ~60 tests | Tier boundaries (5-tier), classify() parametrized, OCM deadlines, overdue timeframe descriptions, batch classification, metadata templates/urgency/subject labels, convenience functions | **YES** -- Constants for 40/50 boundaries, Tier enum values, classify() parametrized expectations, metadata for PAST_DUE_40/50, overdue_timeframe_description entirely removed |
| `test_data_loader.py` | ~35 tests | XLSX loading, invoice counts, contact parsing, fuzzy matching, tier distribution, skip reasons, data cleaning | **PARTIAL** -- Tier distribution counts reference T0/T1/T2 which change meaning; financial totals unchanged |
| `test_contact_resolver.py` | ~35 tests | Name normalization, similarity, matching tiers, confidence, batch resolution, real data validation | **NO** -- Contact resolver tests do not reference email tiers directly |
| `test_integration.py` | ~25 tests | Full pipeline (XLSX->classify->match->queue), .eml comparison, cross-module tier consistency, export | **YES** -- tier_label assertions include "40+ Days Past Due" and "50+ Days Past Due"; cross-module consistency checks both Tier enums |
| `conftest.py` | 0 (setup only) | sys.path configuration | **NO** |

**Total current tests: ~240**
**Tests that will break: ~50-60**

---

## 2. Tests That Will Break (Due to Tier Consolidation)

### 2.1 test_models.py -- Broken Tests

| Test File | Test Name | Why It Breaks | Fix Strategy |
|-----------|-----------|---------------|-------------|
| test_models.py | `TestTierEnum.test_tier_values` | Asserts `Tier.T3.value == "40+ Days Past Due"` and `Tier.T4.value == "50+ Days Past Due"` -- these enum members will not exist | Remove T3/T4 assertions. Assert only T0, T1, T2. |
| test_models.py | `TestTierEnum.test_tier_count` | Asserts `len(Tier) == 5` | Change to `len(Tier) == 3` |
| test_models.py | `TestTierEnum.test_from_days` (parametrized) | Cases `(40, Tier.T3)`, `(45, Tier.T3)`, `(49, Tier.T3)`, `(50, Tier.T4)`, `(75, Tier.T4)`, `(111, Tier.T4)`, `(999, Tier.T4)` reference removed enum members | Change all 40+ and 50+ cases to map to `Tier.T2` (30+ Days Past Due) |
| test_models.py | `TestInvoice.test_auto_tier_assignment` | Asserts `inv_40plus.tier == Tier.T3` and `inv_50plus.tier == Tier.T4` | Change both to `Tier.T2` |
| test_models.py | `TestEmailQueue.test_approve_by_tier` | Uses `Tier.T4` to create a draft | Change to `Tier.T2` |
| test_models.py | `TestTierConfig.test_default_tiers` | Asserts `len(tiers) == 5` and `tiers[4].tier_name == Tier.T4` | Change to 3 tiers, update indices |
| test_models.py | `TestTierConfig.test_default_tiers_cover_all_ranges` | Asserts `tiers[4].min_days == 50` and `tiers[4].max_days is None` | Update: `tiers[2].min_days == 30` and `tiers[2].max_days is None` |
| test_models.py | `TestTierConfig.test_find_tier` | Asserts `find_tier(45).tier_name == Tier.T3` and `find_tier(100).tier_name == Tier.T4` | Change both to `Tier.T2` |
| test_models.py | `TestTierConfig.test_find_tier_boundary_values` | Asserts boundaries at 40/49/50 map to T3/T4 | All 30+ values map to `Tier.T2` |
| test_models.py | `TestTierConfig.test_matches_unbounded_max` | Uses `tier_name=Tier.T4` and `template_name="past_due_50"` | Change to `Tier.T2` and `"past_due_30"` |
| test_models.py | `TestTierConfig.test_default_tiers_t2_plus_include_ocm_warning` | Indexes into 5-element list at [3] and [4] | Reduce to 3-element list, only index [2] has OCM warning |
| test_models.py | `TestTierConfig.test_default_tiers_have_cc_rules` | Iterates 5 tiers | Will still work if reduced to 3, but verify |

### 2.2 test_tier_classifier.py -- Broken Tests

| Test File | Test Name | Why It Breaks | Fix Strategy |
|-----------|-----------|---------------|-------------|
| test_tier_classifier.py | `TestConstants.test_past_due_40_boundary` | Asserts `TIER_BOUNDARY_PAST_DUE_40 == 40` -- constant will be removed | Remove test entirely |
| test_tier_classifier.py | `TestConstants.test_past_due_50_boundary` | Asserts `TIER_BOUNDARY_PAST_DUE_50 == 50` -- constant will be removed | Remove test entirely |
| test_tier_classifier.py | `TestTierEnum.test_tier_values` | Asserts `Tier.PAST_DUE_40.value` and `Tier.PAST_DUE_50.value` | Remove PAST_DUE_40 and PAST_DUE_50 assertions |
| test_tier_classifier.py | `TestClassifySingle.test_tier_assignment` (parametrized) | 7 cases map to `PAST_DUE_40` or `PAST_DUE_50` | Change all 30+ to `Tier.PAST_DUE` (or whatever the new 30+ enum name is) |
| test_tier_classifier.py | `TestClassifySingle.test_boundary_past_due_40_transition` | Asserts day 40 transitions from PAST_DUE_30 to PAST_DUE_40 | Remove -- no 40-day boundary exists |
| test_tier_classifier.py | `TestClassifySingle.test_boundary_past_due_50_transition` | Asserts day 50 transitions from PAST_DUE_40 to PAST_DUE_50 | Remove -- no 50-day boundary exists |
| test_tier_classifier.py | `TestClassifySingle.test_very_large_days` | Asserts `Tier.PAST_DUE_50` for 999 days | Change to `Tier.PAST_DUE` (30+ tier) |
| test_tier_classifier.py | `TestClassifySingle.test_result_metadata_matches_tier` | Parametrized with `(45, Tier.PAST_DUE_40)` and `(75, Tier.PAST_DUE_50)` | Change both to `Tier.PAST_DUE` |
| test_tier_classifier.py | `TestTierMetadata.test_all_tiers_have_metadata` | Iterates all 5 Tier members | Will work if metadata dict matches new 3-member enum |
| test_tier_classifier.py | `TestTierMetadata.test_metadata_template_names` | Asserts `PAST_DUE_40` -> "past_due_40" and `PAST_DUE_50` -> "past_due_50" | Remove these two lines; only assert 3 templates |
| test_tier_classifier.py | `TestTierMetadata.test_metadata_urgency_levels` | Asserts `PAST_DUE_40` -> CRITICAL and `PAST_DUE_50` -> SEVERE | Remove; 30+ tier should have a single urgency level (HIGH or CRITICAL) |
| test_tier_classifier.py | `TestTierMetadata.test_metadata_subject_labels` | Asserts static labels for PAST_DUE_40 and PAST_DUE_50 | Remove; 30+ subject label is now DYNAMIC, not static |
| test_tier_classifier.py | `TestTierMetadata.test_ocm_warning_tiers` | Indexes PAST_DUE_40 and PAST_DUE_50 | Remove; only PAST_DUE has OCM warning |
| test_tier_classifier.py | `TestTierMetadata.test_past_due_50_includes_additional_contacts` | References `Tier.PAST_DUE_50` | Remove or merge into PAST_DUE test |
| test_tier_classifier.py | `TestOverdueTimeframeDescription` (entire class, 13 tests) | `get_overdue_timeframe_description()` function will be REMOVED per meeting decision (canonical template uses static "overdue") | **Delete entire class** |
| test_tier_classifier.py | `TestConvenienceFunctions.test_get_tier` (parametrized) | Cases `(40, PAST_DUE_40)`, `(49, PAST_DUE_40)`, `(50, PAST_DUE_50)`, `(111, PAST_DUE_50)` | Change to PAST_DUE |
| test_tier_classifier.py | `TestRealDataScenarios.test_real_invoice` (parametrized) | `("893271", 111, Tier.PAST_DUE_50, ...)` and `("893281", 111, Tier.PAST_DUE_50, ...)` | Change to `Tier.PAST_DUE` |
| test_tier_classifier.py | Import statement at top | Imports `TIER_BOUNDARY_PAST_DUE_40`, `TIER_BOUNDARY_PAST_DUE_50`, `get_overdue_timeframe_description` | Remove these imports |

### 2.3 test_data_loader.py -- Broken Tests

| Test File | Test Name | Why It Breaks | Fix Strategy |
|-----------|-----------|---------------|-------------|
| test_data_loader.py | `TestInvoiceFields.test_aroma_farms_fields` | Asserts `inv.tier == Tier.T0` -- this works if T0 stays as Coming Due | **OK if enum names stay T0/T1/T2**, but if enum names change to COMING_DUE/OVERDUE/PAST_DUE, the import path changes |
| test_data_loader.py | `TestTierDistribution.test_past_due_30_count` | Asserts `inv.tier == Tier.T2` for 30+ -- if T2 now covers ALL 30+ (not just 30-39), the count will be HIGHER | Update expected range: was 5-10 (30-39 only), should now be ~13+ (30+ all) |

### 2.4 test_integration.py -- Broken Tests

| Test File | Test Name | Why It Breaks | Fix Strategy |
|-----------|-----------|---------------|-------------|
| test_integration.py | `TestFullPipeline.test_step2_all_invoices_classified` | Asserts tier_label in list including "40+ Days Past Due" and "50+ Days Past Due" | Remove those two values from the expected list |
| test_integration.py | `TestEmailComparison.test_tier_label_in_eml_subject` (parametrized) | Cases `("902398", "40+ Days Past Due")` and `("893271", "50+ Days Past Due")` | These .eml files were generated with the OLD 5-tier system. Either: (a) update .eml files, or (b) reclassify: 902398 (39 days) -> "30+ Days Past Due"; 893271 (111 days) -> subject should show "110+ Days Past Due" with dynamic label |
| test_integration.py | `TestCrossModuleConsistency.test_tier_model_vs_classifier_alignment` | Tests days 40, 45, 49, 50, 75, 111 against both Tier enums | All should now map to the single 30+ tier; test still valid but expected values change |
| test_integration.py | `TestCrossModuleConsistency.test_data_loader_invoices_have_valid_tiers` | Cross-checks tier.value between models and classifier | Will work once both modules are aligned on 3 tiers |
| test_integration.py | Import statement | Imports `get_overdue_timeframe_description` | Remove this import |

---

## 3. New Tests Required

### 3.1 Tier Classification Tests

#### 3.1.1 New 3-Tier Boundary Tests

| Test Case | Input (days) | Expected Output | Priority |
|-----------|-------------|-----------------|----------|
| Coming Due lower bound | -8 | `Tier.COMING_DUE` (BUT: meeting said -7 to 0, so -8 should NOT generate an email. Test the filter, not the tier.) | P0 |
| Coming Due at -7 | -7 | `Tier.COMING_DUE` -- first day that generates a Coming Due email | P0 |
| Coming Due at -1 | -1 | `Tier.COMING_DUE` | P0 |
| Coming Due at 0 | 0 | `Tier.COMING_DUE` -- due today, still "coming due" | P0 |
| Overdue at 1 | 1 | `Tier.OVERDUE` -- first overdue day | P0 |
| Overdue at 29 | 29 | `Tier.OVERDUE` -- last day before 30+ tier | P0 |
| 30+ at 30 | 30 | `Tier.PAST_DUE` -- first day of 30+ tier | P0 |
| 30+ at 39 | 39 | `Tier.PAST_DUE` -- was boundary between 30+ and 40+ tiers; now same tier | P0 |
| 30+ at 40 | 40 | `Tier.PAST_DUE` -- previously started T3 (40+); now same 30+ tier | P0 |
| 30+ at 49 | 49 | `Tier.PAST_DUE` -- was boundary between 40+ and 50+ tiers | P0 |
| 30+ at 50 | 50 | `Tier.PAST_DUE` -- previously started T4 (50+); now same tier | P0 |
| 30+ at 111 | 111 | `Tier.PAST_DUE` -- extreme value, same tier | P0 |
| 30+ at 999 | 999 | `Tier.PAST_DUE` | P1 |
| Very negative (-100) | -100 | `Tier.COMING_DUE` (but should be filtered out by -7 minimum) | P1 |

#### 3.1.2 Tier Enum Reduction Tests

| Test Case | Validates | Priority |
|-----------|-----------|----------|
| `len(Tier) == 3` | Only 3 tier enum members exist | P0 |
| `Tier.PAST_DUE_40` raises `AttributeError` | Removed enum member does not exist | P0 |
| `Tier.PAST_DUE_50` raises `AttributeError` | Removed enum member does not exist | P0 |
| `Tier.COMING_DUE.value == "Coming Due"` | Correct string value | P0 |
| `Tier.OVERDUE.value == "Overdue"` | Correct string value | P0 |
| `Tier.PAST_DUE.value == "30+ Days Past Due"` | Correct string value (base label) | P0 |

#### 3.1.3 Coming Due Filter Boundary Test (-7 to 0)

| Test Case | Input | Expected Output | Priority |
|-----------|-------|-----------------|----------|
| Day -8: should NOT generate email | -8 | Invoice filtered out (no email generated) or classified but marked as out-of-range | P0 |
| Day -7: first coming-due email | -7 | `Tier.COMING_DUE`, email generated | P0 |
| Day 0: due today | 0 | `Tier.COMING_DUE`, email generated | P0 |

### 3.2 Template Tests

| Test Case | Validates | Priority |
|-----------|-----------|----------|
| **No "final notice" in coming_due.html** | `grep -i "final.notice" coming_due.html` returns 0 matches | P0 |
| **No "final notice" in overdue.html** | `grep -i "final.notice" overdue.html` returns 0 matches | P0 |
| **No "final notice" in past_due_30.html** | `grep -i "final.notice" past_due_30.html` returns 0 matches | P0 |
| **No "action required" in any template** | No template file contains "ACTION REQUIRED" | P0 |
| **No "second notice" in any template** | No template file contains "second notice" | P0 |
| **past_due_40.html does NOT exist** | `Path("templates/past_due_40.html").exists() == False` | P0 |
| **past_due_50.html does NOT exist** | `Path("templates/past_due_50.html").exists() == False` | P0 |
| **Only 3 template files exist** | `len(list(templates_dir.glob("*.html"))) == 3` (plus any base/layout) | P0 |
| **Coming Due body matches canonical** | Template output for Coming Due contains "courtesy reminder that your payment is due soon" | P0 |
| **Coming Due attachment line** | Contains "Attached you'll find the Nabis ACH payment form" (not "Attached is") | P1 |
| **Overdue body uses "overdue"** | Template output contains "your invoice is overdue" (NOT "nearing two weeks past due") | P0 |
| **No OVERDUE_TIMEFRAME variable** | overdue.html does not contain `{{OVERDUE_TIMEFRAME}}` | P0 |
| **30+ body matches canonical** | Contains "Nabis's OCM reporting policy for overdue invoices" | P0 |
| **30+ body has correct bullet order** | Invoice, Due, Nabis AM, Amount (NOT Amount before Nabis AM) | P1 |
| **30+ body has "past-due invoices" (plural)** | Not "past-due invoice" (singular) | P1 |
| **30+ body does NOT have extra paragraph** | Does not contain "our standard payment terms require" | P0 |
| **All templates have {{CONTACT_FIRST_NAME}}** | Greeting uses the variable, not a hardcoded name | P1 |
| **All templates have {{INVOICE_NUMBER}}** | Invoice number variable is present | P1 |
| **All templates have {{DUE_DATE}}** | Due date variable is present | P1 |
| **All templates have {{AMOUNT}}** | Amount variable is present | P1 |
| **All templates have {{NABIS_AM_NAME}}** | Account manager name variable | P1 |

### 3.3 Contact Resolution Tests

| Test Case | Validates | Priority |
|-----------|-----------|----------|
| **TO includes both primary AND billing when both exist** | If primary and billing contacts are both present, TO list has both emails | P0 |
| **TO uses only primary when billing is empty** | Fallback to primary only | P0 |
| **TO uses only billing when primary is empty** | Fallback to billing only | P0 |
| **Associated contacts used when primary AND billing are empty** | Correct fallback chain | P1 |
| **Nabis-sourced associated contacts preferred over Revelry** | Source filtering: "nabis import" > "revelry buyers list" | P1 |
| **Revelry-only contacts flagged for review** | When only Revelry contacts available, flag is set | P1 |
| **No email found -> flag for manual review** | When all contact sources are empty, a review flag is set | P0 |
| **CC always includes ny.ar@nabis.com** | Static CC member | P0 |
| **CC always includes martinm@piccplatform.com** | Static CC member | P0 |
| **CC always includes mario@piccplatform.com** | Static CC member | P0 |
| **CC always includes laura@piccplatform.com** | Static CC member | P0 |
| **CC includes dynamic rep email** | Rep name from invoice -> resolved to email address | P0 |
| **Rep email lookup handles unknown rep** | Unknown rep name -> graceful fallback (no crash) | P1 |
| **Multi-line POC emails split correctly** | `"a@b.com\nc@d.com"` -> `["a@b.com", "c@d.com"]` | P0 |
| **Empty contact email -> not added to TO** | Empty string or None not included in recipient list | P0 |

### 3.4 Subject Line Tests

| Test Case | Input | Expected Output | Priority |
|-----------|-------|-----------------|----------|
| Coming Due subject | store="Test Store", invoice="906858", days=-2 | `"PICC - Test Store - Nabis Invoice 906858 - Coming Due"` | P0 |
| Overdue subject | store="Test Store", invoice="903480", days=15 | `"PICC - Test Store - Nabis Invoice 903480 - Overdue"` | P0 |
| 30+ subject (30-39 days) | days=35 | Subject ends with `"30+ Days Past Due"` | P0 |
| 40+ subject (40-49 days) | days=45 | Subject ends with `"40+ Days Past Due"` (DYNAMIC, not separate tier) | P0 |
| 50+ subject (50-59 days) | days=55 | Subject ends with `"50+ Days Past Due"` | P0 |
| 60+ subject | days=65 | Subject ends with `"60+ Days Past Due"` | P0 |
| 70+ subject | days=75 | Subject ends with `"70+ Days Past Due"` | P1 |
| 80+ subject | days=85 | Subject ends with `"80+ Days Past Due"` | P1 |
| 110+ subject (extreme) | days=111 | Subject ends with `"110+ Days Past Due"` | P0 |
| Dynamic label formula | days=47 | `floor(47/10)*10 = 40` -> `"40+ Days Past Due"` | P0 |
| Dynamic label formula edge | days=30 | `floor(30/10)*10 = 30` -> `"30+ Days Past Due"` | P0 |
| Dynamic label formula edge | days=39 | `floor(39/10)*10 = 30` -> `"30+ Days Past Due"` | P0 |
| Dynamic label formula edge | days=40 | `floor(40/10)*10 = 40` -> `"40+ Days Past Due"` | P0 |
| Multi-invoice subject | 2 invoices | Subject says "Invoices X & Y" (plural) | P0 |
| Subject has NO "ACTION REQUIRED" | Any 30+ email | "ACTION REQUIRED" NOT in subject | P0 |
| Subject has NO "FINAL NOTICE" | Any 30+ email | "FINAL NOTICE" NOT in subject | P0 |
| `get_dynamic_subject_label()` function | days=52 | Returns `"50+ Days Past Due"` | P0 |

### 3.5 Integration Tests

| Test Case | Validates | Priority |
|-----------|-----------|----------|
| **Full pipeline with 3 tiers only** | XLSX -> parse -> classify -> all invoices get one of 3 tiers only | P0 |
| **No tier_label contains "40+" or "50+"** | After classification, no invoice has tier_label "40+ Days Past Due" or "50+ Days Past Due" | P0 |
| **Subject line dynamic bucket for real data** | Invoice 893271 (111 days) gets subject "110+ Days Past Due" in subject, NOT "50+ Days Past Due" | P0 |
| **Subject line dynamic bucket for 39 days** | Invoice at 39 days gets "30+ Days Past Due" (not "40+") | P0 |
| **Cross-module tier consistency (3-tier)** | `models.Tier.from_days(X)` and `tier_classifier.get_tier(X)` agree for all boundary values | P0 |
| **Dual Tier enum consolidated** | Only ONE Tier enum exists (models.py or tier_classifier.py, not both) | P0 |
| **Template rendering for 30+ produces correct body** | Render past_due_30 template with test data -> body contains canonical text | P0 |
| **Template rendering for 30+ does NOT contain "final notice"** | Rendered HTML does not contain "final notice" anywhere | P0 |
| **CC list assembly for real invoice** | Given an invoice with rep="Bryce J", CC includes rep email + base CC list | P1 |
| **Settings persistence: tier boundaries survive regeneration** | Change tier boundary in settings -> click Generate -> boundaries are still changed | P1 |
| **Email preview shows correct sender name** | Preview FROM field shows configured sender name, NOT hardcoded "Laura" | P1 |
| **Queue approve -> send -> mark sent** | Full status transition: PENDING -> APPROVED -> SENT with timestamp | P0 |
| **Export JSON with 3-tier data** | Export queue to JSON, verify tier values are only "Coming Due", "Overdue", "30+ Days Past Due" | P1 |

---

## 4. Regression Test Checklist

These capabilities must continue to work after the overhaul:

### 4.1 Data Loading (Must Not Regress)
- [ ] XLSX file loads successfully with openpyxl
- [ ] Auto-detects most recent "Overdue M-D" sheet
- [ ] Explicit sheet name override works
- [ ] Parses ~70 invoices from production XLSX
- [ ] Parses ~620 contacts from Managers sheet
- [ ] Multi-line POC name/email/phone fields split correctly
- [ ] Invoice numbers stored as strings (not floats)
- [ ] Amounts stored as floats with correct values
- [ ] Days past due stored as integers
- [ ] Due dates stored as date objects
- [ ] Missing file raises FileNotFoundError
- [ ] Missing sheet raises ValueError

### 4.2 Skip Reason Detection (Must Not Regress)
- [ ] `paid=True` -> skip with ALREADY_PAID reason
- [ ] `status="Payment Enroute"` -> skip (case-insensitive)
- [ ] `email_sent=True` -> skip with EMAIL_ALREADY_SENT
- [ ] `account_manager=""` or `"#N/A"` -> skip with NO_ACCOUNT_MANAGER
- [ ] Skip reason priority: paid > enroute > email_sent > no AM
- [ ] Non-skipped invoices have `is_sendable == True`

### 4.3 Contact Resolution (Must Not Regress)
- [ ] Exact name matching works (case-insensitive)
- [ ] Fuzzy matching above threshold works
- [ ] Below-threshold returns NO_MATCH
- [ ] License number matching (Tiers 1-3)
- [ ] Multiple contacts per store resolved by AP/billing title preference
- [ ] Empty contact list -> NO_MATCH with notes
- [ ] Empty location -> NO_MATCH with "no location" note
- [ ] Batch resolution with group_by_location
- [ ] Resolution report formatting
- [ ] Match rate calculation

### 4.4 Email Draft (Must Not Regress)
- [ ] Draft creation with invoices
- [ ] Subject line building with correct format
- [ ] Multi-invoice subject uses "Invoices X & Y" format
- [ ] Status transitions: PENDING -> APPROVED -> SENT
- [ ] Status transitions: PENDING -> REJECTED
- [ ] Status transitions: APPROVED -> FAILED
- [ ] Double-approve raises ValueError
- [ ] Double-reject raises ValueError
- [ ] mark_sent() sets sent_at timestamp
- [ ] to_dict() is JSON-serializable
- [ ] total_amount sums across invoices
- [ ] amount_formatted uses "$X,XXX.XX" format

### 4.5 Email Queue (Must Not Regress)
- [ ] Add, iterate, index access
- [ ] approve_all(), reject_all()
- [ ] approve_by_tier() with valid tier
- [ ] approve_by_index() with valid/invalid indices
- [ ] Export to JSON with summary stats
- [ ] Export to CSV
- [ ] Summary string formatting
- [ ] Sent/failed counts

### 4.6 Invoice Formatting (Must Not Regress)
- [ ] `amount_formatted` -> `"$1,510.00"`
- [ ] `due_date_formatted` -> `"Feb 05, 2026"`
- [ ] `due_date_formatted` with None -> `""`
- [ ] `tier_label` -> correct human-readable label

---

## 5. Edge Cases

### 5.1 Tier Boundary Edge Case Matrix

| Days | Old Tier | New Tier | Subject Label | Notes |
|------|----------|----------|---------------|-------|
| -100 | T0 (Coming Due) | Coming Due | "Coming Due" | Out of -7 to 0 range; should be filtered or treated as far-future |
| -8 | T0 (Coming Due) | Coming Due | "Coming Due" | **Outside -7 to 0 range per meeting**; should NOT generate email |
| -7 | T0 (Coming Due) | Coming Due | "Coming Due" | First valid Coming Due day |
| -1 | T0 (Coming Due) | Coming Due | "Coming Due" | Last negative day |
| 0 | T0 (Coming Due) | Coming Due | "Coming Due" | Due today -- still coming due |
| 1 | T1 (Overdue) | Overdue | "Overdue" | First overdue day |
| 15 | T1 (Overdue) | Overdue | "Overdue" | Mid-range overdue |
| 29 | T1 (Overdue) | Overdue | "Overdue" | Last day before 30+ |
| 30 | T2 (30+) | 30+ Past Due | "30+ Days Past Due" | First day of 30+ tier |
| 39 | T2 (30+) | 30+ Past Due | "30+ Days Past Due" | Was last day of T2 (30-39); now no boundary here |
| 40 | T3 (40+) **REMOVED** | 30+ Past Due | "40+ Days Past Due" | **Key change**: same body as 30, different subject |
| 49 | T3 (40+) **REMOVED** | 30+ Past Due | "40+ Days Past Due" | Was last day of T3; now just dynamic subject |
| 50 | T4 (50+) **REMOVED** | 30+ Past Due | "50+ Days Past Due" | **Key change**: was T4 with "FINAL NOTICE"; now normal 30+ |
| 52 | T4 (50+) **REMOVED** | 30+ Past Due | "50+ Days Past Due" | OCM reporting day; same template as 30+ |
| 75 | T4 (50+) **REMOVED** | 30+ Past Due | "70+ Days Past Due" | Dynamic label rounds to nearest 10 |
| 111 | T4 (50+) **REMOVED** | 30+ Past Due | "110+ Days Past Due" | Extreme case |
| 999 | T4 (50+) **REMOVED** | 30+ Past Due | "990+ Days Past Due" | Absurd but valid |

### 5.2 Missing/Empty Data Edge Cases

| Scenario | Input | Expected Behavior | Priority |
|----------|-------|-------------------|----------|
| No contact email found | All contact sources return empty | Flag for manual review; TO field blank or shows "(no contact found)" | P0 |
| Missing store name in XLSX | Location column is blank | Invoice skipped with appropriate skip reason or warning | P1 |
| Missing invoice number | Order No column is blank | Invoice skipped | P1 |
| Missing due date | Due Date column is None | `due_date_formatted` returns `""`, tier classification still works via days_past_due | P1 |
| Missing days_past_due | Column is None or NaN | Defaults to 0 (Coming Due), `input_was_null` flag set | P0 |
| Missing amount | Total Due is None or 0 | `amount_formatted` returns `"$0.00"`, invoice not skipped | P1 |
| Missing account manager | Account Manager is blank | Invoice skipped with NO_ACCOUNT_MANAGER reason | P0 |
| Account manager is "#N/A" | Literal string "#N/A" | Invoice skipped with NO_ACCOUNT_MANAGER reason | P0 |
| Missing sales rep | Rep column is blank | CC list includes base CC but no rep email | P1 |
| XLSX with no Overdue sheet | Sheet name doesn't match pattern | Raise ValueError | P1 |
| XLSX with multiple Overdue sheets | "Overdue 2-3" and "Overdue 1-29" | Auto-detect most recent by date sorting | P1 |

### 5.3 Template Variable Substitution Edge Cases

| Scenario | Variable | Input | Expected Output | Priority |
|----------|----------|-------|-----------------|----------|
| Missing contact name | `{{CONTACT_FIRST_NAME}}` | Contact has no name | Falls back to "Team" | P0 |
| Multi-word contact name | `{{CONTACT_FIRST_NAME}}` | "Jo-Anne Rainone" | "Jo-Anne" (first name only) | P1 |
| Large amount formatting | `{{AMOUNT}}` | 18071.75 | "$18,071.75" | P0 |
| Small amount formatting | `{{AMOUNT}}` | 108.00 | "$108.00" | P1 |
| Zero amount | `{{AMOUNT}}` | 0.00 | "$0.00" | P1 |
| Multi-invoice body | Multiple invoices | Body lists all invoices, not just first | P0 |
| Nabis AM name with special chars | `{{NABIS_AM_NAME}}` | "Mildred Verdadero" | Renders correctly, no HTML escaping issues | P1 |
| Store name with location suffix | `{{STORE_NAME}}` | "Herbwell - Manhattan" | Full name including location qualifier | P0 |

### 5.4 "Final Notice" Prohibition Tests

| Scenario | What to Check | Priority |
|----------|---------------|----------|
| Grep all .html templates for "final notice" (case-insensitive) | Zero matches | P0 |
| Grep all .py source files for "final notice" | Zero matches (except test assertions that verify its absence) | P0 |
| Grep all .yaml config files for "final notice" | Zero matches | P0 |
| Grep all .html templates for "FINAL NOTICE" | Zero matches | P0 |
| Grep all .html templates for "ACTION REQUIRED" | Zero matches | P0 |
| Grep all .html templates for "second notice" | Zero matches | P0 |
| Grep all .html templates for "account has been flagged" | Zero matches | P0 |
| Grep all .html templates for "collection action" | Zero matches | P0 |
| Render 30+ template at 50 days | Output does NOT contain "final notice" | P0 |
| Render 30+ template at 111 days | Output does NOT contain "final notice" | P0 |
| Subject line at 50+ days | Does NOT contain "FINAL NOTICE" | P0 |
| Subject line at 40+ days | Does NOT contain "ACTION REQUIRED" | P0 |

---

## 6. User Acceptance Test Script

### 6.1 Pre-Test Setup
1. Callie downloads fresh "NY Accounts Receivable Overdue" Google Sheet as XLSX
2. Callie opens the AR Email Automation tool (Streamlit Cloud URL)
3. Callie enters her sender email: `kali@piccplatform.com`
4. Callie enters her sender name: `Kali Speerstra`

### 6.2 Upload & Generate
5. Callie clicks "Browse Files" and selects the downloaded XLSX
6. **VERIFY**: "Use Default File" checkbox is NOT checked (or has been removed)
7. Callie clicks "Generate Emails"
8. **VERIFY**: Email queue populates with invoices grouped by store
9. **VERIFY**: Queue shows exactly 3 tier labels: "Coming Due", "Overdue", and "30+ Days Past Due"
10. **VERIFY**: No email in the queue shows "40+ Days Past Due" or "50+ Days Past Due" as a TIER (though subject lines for 30+ may show dynamic day labels)

### 6.3 Review Coming Due Emails
11. Click "Preview" on a Coming Due email (e.g., Aroma Farms, days=-2)
12. **VERIFY**: Subject line is `PICC - Aroma Farms - Nabis Invoice 906858 - Coming Due`
13. **VERIFY**: Email body opens with "Hello [First Name],"
14. **VERIFY**: Body contains "courtesy reminder that your payment is due soon"
15. **VERIFY**: Body contains "Attached you'll find the Nabis ACH payment form"
16. **VERIFY**: Invoice details section shows correct Invoice/Order, Due Date, Amount, Nabis AM
17. **VERIFY**: No mention of "final notice," "action required," or "second notice"
18. **VERIFY**: CC list includes ny.ar@nabis.com, Martin, Mario, Laura, and the assigned rep

### 6.4 Review 1-29 Day Overdue Emails
19. Click "Preview" on an Overdue email (e.g., Long Island Cannabis Club, days=27)
20. **VERIFY**: Subject line is `PICC - [Store] - Nabis Invoice [#] - Overdue`
21. **VERIFY**: Body contains "your invoice is overdue" (NOT "nearing two weeks past due")
22. **VERIFY**: Body contains "Attached, you'll find the Nabis ACH payment form"
23. **VERIFY**: No mention of "final notice," "action required," or "second notice"

### 6.5 Review 30+ Day Emails (Dynamic Subject Test)
24. Click "Preview" on a 30+ day email where days = 31 (e.g., Royal Blend Dispensary)
25. **VERIFY**: Subject line ends with "30+ Days Past Due"
26. **VERIFY**: Body mentions OCM reporting policy
27. **VERIFY**: Body contains "Attached you'll find the Nabis ACH payment form"

28. Click "Preview" on a 30+ day email where days = 39 (e.g., Herbwell - Manhattan)
29. **VERIFY**: Subject line ends with "30+ Days Past Due" (NOT "40+")

30. Click "Preview" on a 30+ day email where days = 111 (e.g., The Travel Agency - SoHo)
31. **VERIFY**: Subject line ends with "110+ Days Past Due" (dynamic)
32. **VERIFY**: Email body is IDENTICAL to the 30-day email (same template)
33. **VERIFY**: No "final notice," "action required," "second notice," "account has been flagged"

### 6.6 Edit Recipients
34. On any email preview, click "Edit"
35. **VERIFY**: TO field becomes editable
36. **VERIFY**: CC field becomes editable
37. Change TO to a test email address
38. Click "Save"
39. **VERIFY**: Changed email address persists (navigate away and back)

### 6.7 Settings Verification
40. Navigate to Settings page
41. **VERIFY**: Sender name shows "Kali Speerstra" (NOT "Laura" or other default)
42. **VERIFY**: CC list shows ny.ar@nabis.com, martinm@piccplatform.com, mario@piccplatform.com, laura@piccplatform.com
43. **VERIFY**: Tier boundaries show only 3 tiers: Coming Due (-7 to 0), Overdue (1 to 29), 30+ Past Due (30+)
44. **VERIFY**: There are NO tier entries for 40+ or 50+
45. Modify a CC email address
46. Click "Save Settings"
47. Navigate away and back to Settings
48. **VERIFY**: The change persisted

### 6.8 Approve & Send (Dry Run)
49. Return to Queue page
50. Click "Approve All Pending"
51. **VERIFY**: All emails move to APPROVED status
52. **VERIFY**: The "Send via Gmail" button becomes enabled (if SMTP configured)
53. **OPTIONAL**: Configure Gmail App Password and send a test email to a known address
54. **VERIFY**: Received email matches preview exactly

### 6.9 Parallel Comparison
55. Callie compares 3 emails (one per tier) against what she would have sent manually:
    - Same subject line format
    - Same email body wording
    - Same CC recipients
    - Same invoice details (number, date, amount, AM)
56. **VERIFY**: No discrepancies beyond expected differences (e.g., TO field may need manual entry until Notion integration is complete)
57. Document any discrepancies for Joe to fix

### 6.10 Pass/Fail Criteria
- **PASS**: All 3 tiers produce correct canonical template text, no "final notice" anywhere, dynamic subject lines work for 30+, settings persist, edit button works
- **FAIL**: Any "final notice" text appears, wrong template body is used, more than 3 tiers appear, subject line is wrong, settings don't persist

---

## 7. Test Implementation Priority

### Phase 1 (Must Have Before Build -- Wave 2 Blockers)
1. 3-tier enum tests (replaces all 5-tier tests)
2. Dynamic subject line label tests
3. "Final notice" prohibition tests (grep-based)
4. Template file existence tests (only 3 exist, 40/50 deleted)
5. Canonical template text assertions

### Phase 2 (During Build)
6. Updated boundary value parametrized tests
7. Contact resolution multi-recipient tests
8. CC list assembly tests
9. Integration pipeline tests with 3-tier expectations

### Phase 3 (Post-Build Validation)
10. Full UAT script execution
11. .eml comparison tests updated for dynamic subjects
12. Settings persistence tests
13. Edit button functional tests (may require Streamlit testing framework)

---

## 8. Test File Change Summary

| File | Action | Estimated Changes |
|------|--------|-------------------|
| `test_models.py` | UPDATE -- reduce Tier enum tests, TierConfig tests from 5 to 3, update from_days parametrized cases | ~20 test modifications |
| `test_tier_classifier.py` | MAJOR UPDATE -- remove PAST_DUE_40/50 constants, delete OverdueTimeframeDescription class (13 tests), update all parametrized classify cases, update metadata tests | ~30 test modifications, 13 deletions |
| `test_data_loader.py` | MINOR UPDATE -- update tier distribution expected ranges for Tier.T2 count | ~3 test modifications |
| `test_contact_resolver.py` | NO CHANGES needed for tier consolidation; NEW TESTS needed for multi-recipient TO and source filtering | ~0 modifications, ~15 new tests |
| `test_integration.py` | UPDATE -- remove "40+" and "50+" from expected tier labels, update .eml comparison tests, fix cross-module consistency tests | ~10 test modifications |
| `conftest.py` | NO CHANGES | 0 |
| **NEW: test_dynamic_subject.py** | CREATE -- dedicated tests for `get_dynamic_subject_label()` function and subject line generation | ~20 new tests |
| **NEW: test_template_content.py** | CREATE -- canonical template text validation, "final notice" prohibition, file existence checks | ~25 new tests |

**Total: ~50-60 modifications, 13 deletions, ~60 new tests**

---

*End of Report 09 - Test Specification*
