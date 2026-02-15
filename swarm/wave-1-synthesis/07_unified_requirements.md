# Unified Requirements Document
## Document: 07 - Synthesized Requirements Specification
## Timestamp: 2026-02-14
## Sources: Wave 0 Reports 01-06
## Synthesized by: Wave 1 Synthesis Agent (opus)

---

## 1. Executive Summary

The AR Email Automation tool is a Streamlit-based web application that automates the weekly process of generating, previewing, and sending accounts receivable collection emails for PICC Platform's New York cannabis dispensary operations. Callie Speerstra (NY Sales Admin) currently performs this process entirely manually: downloading an AR spreadsheet from Google Sheets, looking up recipient contacts one-by-one in Notion, selecting from 3 email templates based on days past due, filling in variable fields by hand, and schedule-sending all emails for 7:00 AM Pacific (10:00 AM Eastern). The automation tool, built by Joe Smith, has reached approximately 90-95% functional completeness but has critical structural mismatches that block go-live.

The six Wave 0 analysis reports reveal five categories of issues. First, a **tier/template structural mismatch**: the app implements 5 tiers with 5 progressively escalating email bodies (including AI-fabricated "second notice" and "final notice" language that was never authorized), while the canonical specification calls for exactly 3 tiers with 3 body variants and dynamic subject lines for the 30+ day tier. Second, a **contact resolution gap**: the biggest time sink in Callie's manual process is looking up recipient emails in Notion, and the tool has no Notion integration -- it currently pulls contacts only from the XLSX "Managers" sheet, missing the cascading priority chain (Primary > Billing/AP > Associated Contacts with Nabis-source preference > Brand AR Summary fallback). Third, **UI persistence failures**: settings changes do not survive email regeneration, the edit button for recipients is reportedly non-functional (though code review suggests it may work), and there is no save button anywhere in the settings page. Fourth, **missing scheduling**: Callie needs emails scheduled for 7 AM Pacific, but the tool can only send immediately. Fifth, **data pipeline friction**: Callie must manually download an XLSX file and upload it to the tool, rather than the tool reading directly from Google Sheets.

The go-live strategy agreed upon in the meeting is a **parallel testing approach**: Callie continues sending AR emails manually while Joe iterates on the automated version. The first test run should happen Thursday morning, with Callie comparing automated output against her manual emails for the same week. For go-live, the team accepts a "semi-automated" mode where Callie manually pastes recipient emails (since Notion integration is not yet built) while the tool handles body generation, formatting, tier assignment, and sending.

This document consolidates all findings, resolves conflicts between reports, provides the exact canonical template text, the exact contact selection SOP, the complete data source map, and a prioritized requirement list with file-level change mapping.

---

## 2. The 3-Tier Email System (Canonical Specification)

**Source of truth**: Callie's emails to Joe dated Feb 10 and Feb 11, 2026 (PDFs analyzed in Report 03).

**Current app state**: 5 tiers (T0-T4 in models.py, T1-T5 in config.yaml) with 5 separate HTML template bodies. The 40+ and 50+ templates are entirely AI-fabricated and contain prohibited language ("final notice", "second notice", "ACTION REQUIRED", account hold threats, collections/legal threats, red warning boxes with escalation content).

**Required state**: Exactly 3 tiers, 3 body templates, dynamic subject lines for 30+ tier only.

### Tier 1: Coming Due (-7 to 0 days)

- **Tier Range**: Days past due = -7 to 0 (inclusive). Day 0 is the due date itself.
- **Subject**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Coming Due`
- **Template file**: `coming_due.html`
- **Canonical Body**:

```
Hello [person/s],

I hope you're well. This is a courtesy reminder that your payment is due soon.

According to our records, the following invoice is coming due:

  * Invoice/Order: [Invoice Number]
  * Due: [Date Due]
  * Amount: [Amount]
  * Nabis Account Manager: [Name - Phone]

**Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment.**

PICC and I are committed to providing you with the best possible service and are always here to help. If you have any questions or require assistance with your payment, please do not hesitate to contact us.

Thank you for your business. You're much appreciated. Have a great day!
```

- **Tone**: Courteous, gentle reminder
- **Bullet order**: Invoice, Due, Amount, Nabis AM
- **Known app discrepancy**: Current template says "Attached is" instead of canonical "Attached you'll find"

### Tier 2: 1-29 Days Past Due

- **Tier Range**: Days past due = 1 to 29 (inclusive)
- **Subject**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Overdue`
- **Template file**: `overdue.html`
- **Canonical Body (CORRECTED per Feb 11 fix PDF)**:

```
Hello [person/s],

I hope you're having a great day.

This is a friendly reminder that your invoice is overdue. We understand how busy you can get with all the invoices on your plate, and we're here to help if you have any questions or need assistance with payment.

According to our records, the following invoice is past due:

  * Invoice/Order: [Invoice Number]
  * Due: [Date Due]
  * Amount: [Amount]
  * Nabis Account Manager: [Name - Phone]

**Attached, you'll find the Nabis ACH payment form (PDF) to help facilitate your payment.**

Please let us know if there's anything we can do to assist you.
```

- **Tone**: Friendly but direct
- **Bullet order**: Invoice, Due, Amount, Nabis AM
- **CRITICAL CORRECTION**: The original PDF had "nearing two weeks past due" -- Callie's Feb 11 follow-up email specifically struck this through and replaced it with just "overdue". The current app's `{{OVERDUE_TIMEFRAME}}` dynamic variable with 6 ranges must be entirely removed.
- **Known app discrepancy**: App uses `{{OVERDUE_TIMEFRAME}}` with dynamic ranges ("now past due", "nearing two weeks past due", "over two weeks past due", "over three weeks past due") instead of the static word "overdue".

### Tier 3: 30+ Days Past Due

- **Tier Range**: Days past due = 30+ (no upper bound -- "even if they're 80 days past due, we just send them that one")
- **Subject (DYNAMIC)**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - [X]0+ Days Past Due`
  - 30-39 days: "30+ Days Past Due"
  - 40-49 days: "40+ Days Past Due"
  - 50-59 days: "50+ Days Past Due"
  - 60-69 days: "60+ Days Past Due"
  - Formula: `floor(days_past_due / 10) * 10` when >= 30
  - **No "ACTION REQUIRED" suffix. No "FINAL NOTICE" suffix. Ever.**
- **Template file**: `past_due_30_plus.html` (SINGLE file for all 30+ day invoices)
- **Canonical Body**:

```
Hello [person/s],

I hope this message finds you well. I am with PICC Platform, and I'm reaching out with a reminder from the Accounts Receivable department regarding Nabis's OCM reporting policy for overdue invoices.

While their email notifications are typically issued at 45 days, if payments aren't received by 52 days past due, Nabis is required to report your account to OCM.

According to our records, the following invoice is past due:

  * Invoice/Order: [Invoice Number]
  * Due: [Date Due]
  * Nabis Account Manager: [Name - Phone]
  * Amount: [Amount]

**Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment.**

We completely understand that oversights can happen, and our goal is to make the payment process as seamless as possible. Payments can be conveniently submitted through Nabis. Your Nabis account manager is CC'd on this email and can help with processing.

We kindly ask that payment for the past-due invoices be made as soon as possible to bring the account current. Please don't hesitate to reach out if you have any questions or need any support with completing the payment.

We recommend adhering to this timeline to avoid service disruptions and the painstaking hassle of being reported to OCM.

Thank you for your prompt attention to this matter--we truly value your partnership and look forward to continuing our work together.

Regards,
```

- **Tone**: Serious, mentions regulatory consequences (OCM reporting) but not threatening. No "final notice" language ever.
- **Bullet order**: Invoice, Due, **Nabis AM**, Amount (NOTE: this differs from Tier 1 and Tier 2 where Amount comes before Nabis AM)
- **Meeting-approved enhancements beyond canonical**:
  1. **Dynamic payment deadline date** (Travis approved): Add "We request that payment be submitted by [X date] to avoid account restrictions or OCM reporting" to all 30+ emails
  2. **Red-bar OCM warning section** (Travis liked): The visual red-bordered warning bar from the AI-generated 50+ template was liked, but it must use the canonical OCM warning text, not AI-escalated text
- **Known app discrepancies**: Current `past_due_30.html` has an extra paragraph not in canonical ("As a reminder, our standard payment terms require invoices to be settled within the agreed timeframe. This invoice is now over 30 days past due."). `past_due_40.html` and `past_due_50.html` are entirely AI-fabricated and must be deleted.

### Variable Mapping (All Tiers)

| Placeholder in Canonical | Jinja2 Variable | Data Source | Notes |
|--------------------------|-----------------|-------------|-------|
| `[Dispensary Name (Location-if multiple)]` | `{{STORE_NAME}}` | XLSX: Location (col B) | Include location suffix for multi-location retailers |
| `[Invoice Number]` | `{{INVOICE_NUMBER}}` | XLSX: Order No (col A) | Cast float to int to string |
| `[person/s]` | `{{CONTACT_FIRST_NAME}}` | Managers sheet: POC Name (col D), first name extracted | Falls back to "Team" if no contact found |
| `[Date Due]` | `{{DUE_DATE}}` | XLSX: Due Date (col I) | Format: "Feb 05, 2026" (MMM DD, YYYY) |
| `[Amount]` | `{{AMOUNT}}` | XLSX: Total Due (col K) | Format: "$1,510.00" |
| `[Name - Phone]` | `{{NABIS_AM_NAME}} - {{NABIS_AM_PHONE}}` | XLSX: Account Manager (col C) + AM Phone (col D) | Dash separator |
| *(subject line days label)* | `{{DYNAMIC_DAYS_LABEL}}` | Calculated from days_past_due | "Coming Due", "Overdue", "30+ Days Past Due", etc. |
| *(payment deadline)* | `{{PAYMENT_DEADLINE_DATE}}` | Calculated: due_date + 52 days or send_date + 7 biz days | Only for 30+ tier |

### Files to Delete

- `templates/past_due_40.html` -- entirely AI-fabricated, contains "second notice", "ACTION REQUIRED"
- `templates/past_due_50.html` -- entirely AI-fabricated, contains "final notice", "FINAL NOTICE", collections threats, red warning boxes

---

## 3. Contact Selection SOP

**Source of truth**: Meeting transcript timestamps 01:19:42 - 01:33:03, confirmed by Callie, Travis, and Bryce. Documented in Report 01 and Report 05.

### 3.1 TO Field (Primary Recipients)

The contact resolution follows a strict cascading priority chain:

```
1. Look up store in Notion Dispensary Master List
2. IF Primary Contact exists:
     -> TO: Primary Contact email
     -> IF Billing/AP Contact also exists:
          -> TO: Add Billing/AP Contact email too (send to BOTH)
3. ELSE IF Billing/AP Contact exists (no primary):
     -> TO: Billing/AP Contact email
4. ELSE look at Associated Contacts:
     -> IF any with source = "Nabis import" / "Nabis POC" / "CRM Contact":
          -> TO: Use that contact's email (HIGH trust)
     -> ELSE IF any with source != "Revelry":
          -> TO: Use that contact's email (MEDIUM trust)
     -> ELSE IF only Revelry-sourced contacts:
          -> TO: Use with caution (FLAG for manual review)
5. IF still no email from Notion:
     -> Look at Brand AR Summary XLSX for Nabis POC Email (col O)
6. IF still no email from Brand AR Summary:
     -> Look at Managers sheet in AR XLSX for POC Email (col E)
7. IF still no email:
     -> Flag for manual review -- Callie manually enters
```

### 3.2 Associated Contact Source Trust Hierarchy

| Source Label in Notion | Trust Level | Action |
|------------------------|-------------|--------|
| "Nabis import" | HIGH | Use preferentially |
| "Nabis POC" | HIGH | Use preferentially |
| "CRM Contact" | HIGH | Fine to use |
| "Nabis Order, Point of Contact" | HIGH | Fine to use |
| (other/unlabeled) | MEDIUM | Use if nothing better available |
| "Revelry buyers list" / "Revelry" | LOW | Deprioritize; flag for review if only source |

Key quote -- Travis: "Just trust all of them except revelry. Or don't trust revelry." (01:32:52)

### 3.3 CC Recipients (Always Included)

| Recipient | Email Address | Source | Notes |
|-----------|--------------|--------|-------|
| Internal Sales Rep | `{rep_email}` (dynamic per account) | XLSX "Rep" column -> rep email lookup | Changes per store. Requires rep name-to-email mapping table. |
| Nabis AR Group | `ny.ar@nabis.com` | Static | Routes internally to the correct Nabis Account Manager. All Nabis AMs use this single group inbox. |
| Martin | `martinm@piccplatform.com` | Static | For visibility. May transition to BCC. |
| Mario | `mario@piccplatform.com` | Static | For visibility. May transition to BCC. |
| Laura | `laura@piccplatform.com` | Static | For visibility. May transition to BCC. |

### 3.4 BCC Rules

- Travis suggested BCC for Martin/Mario/Laura (01:37:25) but this was **not finalized**
- Currently all are CC'd, not BCC'd
- The UI needs editable CC/BCC fields before this can be configured per-email
- **Decision needed**: Should Martin/Mario/Laura be CC or BCC?

### 3.5 Rep Email Resolution

The "Rep" column in the XLSX contains first names only (e.g., "Ben", "Bryce", "Eric", "Donovan"). A lookup table is needed:

```
"Ben"      -> "ben@piccplatform.com"
"Bryce"    -> "bryce@piccplatform.com"
"Eric"     -> "eric@piccplatform.com"
"Donovan"  -> "donovan@piccplatform.com"
```

This mapping could come from:
- Territory sheet in the XLSX (short term)
- Hardcoded config mapping (immediate)
- Notion API (long term)

### 3.6 Conflict Resolution: Report 05 vs Report 01 on Contact Priority

Report 01 lists the priority as: (1) Primary Contact, (2) Billing/AP, (3) Associated Contacts with Nabis source preferred. Report 05 adds a 4th priority: Brand AR Summary POC Email, and provides the detailed source trust hierarchy. **Resolution**: Report 05's expanded chain is correct and more complete. The Brand AR Summary is a valid fallback source that Mario specifically reminded the team about (01:23:51). The full chain is: Notion Primary > Notion Billing > Notion Associated (source-filtered) > Brand AR Summary > Managers Sheet > Manual Entry.

### 3.7 Current Code Gap

The current `contact_resolver.py` (835 lines) does NOT implement this SOP. It:
- Only reads from the XLSX "Managers" sheet (no Notion, no Brand AR Summary)
- Selects ONE contact per match based on title relevance (AP > Accounting > Owner > Manager)
- Does NOT distinguish between Primary, Billing, and Associated contacts
- Does NOT consider contact SOURCE labels
- Does NOT send to BOTH primary and billing when both exist
- Does NOT deprioritize Revelry-sourced contacts

**Go-live workaround**: Callie will manually paste recipient emails using the Quick Edit TO field. Full Notion integration is a P2 enhancement.

---

## 4. Data Source Map

**Source of truth**: Report 02 (Data Flow Analyst). Cross-referenced with Reports 01 and 05.

### 4.1 Complete Email Field-to-Source Mapping

| Email Field | Template Variable | Source System | Source Location | Currently in App? | Priority |
|-------------|------------------|---------------|-----------------|-------------------|----------|
| Store name | `{{STORE_NAME}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col B: "Location" | YES | -- |
| Contact first name | `{{CONTACT_FIRST_NAME}}` | AR Overdue XLSX | `Managers` sheet, Col D: "POC Name & Title" | YES | -- |
| Contact email (TO) | `{{RECIPIENT_EMAIL}}` | Notion CRM (primary) > Managers sheet (fallback) > Brand AR Summary (Nabis POC) | See Contact SOP Section 3 | PARTIAL (Managers only) | P0 |
| Invoice number | `{{INVOICE_NUMBER}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col A: "Order No" | YES | -- |
| Amount due | `{{AMOUNT}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col K: "Total Due" | YES | -- |
| Due date | `{{DUE_DATE}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col I: "Due Date" | YES | -- |
| Days past due | (tier classification) | AR Overdue XLSX | `Overdue {date}` sheet, Col J: "Days Over" | YES | -- |
| Nabis AM name | `{{NABIS_AM_NAME}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col C: "Account Manager" | YES | -- |
| Nabis AM phone | `{{NABIS_AM_PHONE}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col D: "Acocunt Manager Phone Number" (typo in header) | YES | -- |
| Rep name (PICC) | `{{REP}}` | AR Overdue XLSX | `Overdue {date}` sheet, Col L: "Rep" | YES | -- |
| Rep email (CC) | `{{REP_EMAIL}}` | Derived | Rep name -> email lookup table | PARTIAL | P1 |
| Base CC list | (static) | Config | `config.yaml` cc_rules.base_cc | YES | -- |
| Email sent flag | (skip logic) | AR Overdue XLSX | Col E: "Email Sent" | YES | -- |
| Paid flag | (skip logic) | AR Overdue XLSX | Col M: "Paid" | YES | -- |
| Status | (skip logic) | AR Overdue XLSX | Col O: "Status" ("Payment Enroute" = skip) | YES | -- |
| ACH form | Static file | Local | `data/Nabis_ACH_Payment_Form.pdf` | YES | -- |
| Sender name | `{{SENDER_NAME}}` | Config/UI | `config.yaml` + session state | YES | -- |
| Tier label | `{{DYNAMIC_DAYS_LABEL}}` | Derived | Calculated from Days Over | PARTIAL | P0 |
| Payment deadline | `{{PAYMENT_DEADLINE_DATE}}` | Derived | due_date + 52 days or send_date + 7 biz days | PARTIAL | P1 |

### 4.2 Data Pipeline Architecture

```
Nabis API (orders/details endpoints)
    |
    v
Justin's sync script (runs daily, automated)
    |
    v
Sync Master Sales Sheet (Google Sheets)
    |
    v
NY Account Receivables Overdue (Google Sheet)
    |-- Data sheet: FILTER() formulas against balances
    |-- balances sheet: fed by manual Nabis CSV export OR order calculations
    |-- Overdue {date} sheets: weekly snapshots
    |-- Managers sheet: ~620 retailer POC records
    |
    v  (MANUAL DOWNLOAD as XLSX)
    v
data_loader.py (reads downloaded XLSX via openpyxl)
    |
    v
Email templates + rendering -> Preview queue -> Gmail SMTP send
```

### 4.3 Manual Gap in Pipeline

The `balances` data in the Google Sheet currently requires a **manual Nabis CSV export** (Nabis > Balances > filter "delivered" and "delivered with edits" > click "email CSV"). Justin confirmed this is NOT part of the auto-sync. Travis proposed checking whether the `orders` tab contains equivalent fields, which would eliminate the manual step. **Status**: Callie was asked to check this the morning after the meeting. Unresolved as of this synthesis.

### 4.4 AR Overdue Spreadsheet Schema

| Col | Header | Type | Template Variable | Notes |
|-----|--------|------|-------------------|-------|
| A | Order No | float | `{{INVOICE_NUMBER}}` | Cast to int, then string |
| B | Location | string | `{{STORE_NAME}}` | Join key to Managers sheet |
| C | Account Manager | string | `{{NABIS_AM_NAME}}` | Nabis AM assigned to retailer |
| D | Acocunt Manager Phone Number | string | `{{NABIS_AM_PHONE}}` | Typo in header; handled by alias mapping |
| E | Email Sent | boolean | (skip logic) | If True, skip |
| F | Caller | string | -- | Callie's tracking notes |
| G | Called | boolean | (skip logic) | Tracking field |
| H | Made Contact | boolean | (skip logic) | Tracking field |
| I | Due Date | datetime | `{{DUE_DATE}}` | Format: MMM DD, YYYY |
| J | Days Over | float | Tier classification | Drives template selection |
| K | Total Due | float | `{{AMOUNT}}` | Format: $X,XXX.XX |
| L | Rep | string | CC routing | PICC sales rep name |
| M | Paid | boolean | (skip logic) | If True, skip |
| N | F/U Date | datetime | (metadata) | Follow-up date |
| O | Status | string | (skip logic) | "Payment Enroute" = skip |
| P | Notes | string | (metadata) | Free-text |

### 4.5 Brand AR Summary XLSX Schema (Nabis-provided, ~999 retailers)

| Col | Header | Used For | Currently Ingested? |
|-----|--------|----------|---------------------|
| A | Retailer | Join key to Location | NO |
| B | Retailer Type | Prioritization (Good/Weak/Excellent/Poor) | NO |
| C | Responsiveness | Tone adjustment (Responsive/Unresponsive/Semi-Responsive) | NO |
| O | POC Email | Fallback contact email | NO |
| P | POC Phone | Supplemental phone | NO |
| Q | Notes | Engagement history | NO |

**Note**: Header rows 1-2 are title/brand rows. Actual column headers start at row 3. Parser must skip rows 1-2.

---

## 5. Prioritized Requirements

### P0: Go-Live Blockers (Must fix before Thursday morning)

| ID | Requirement | Source Reports | Why It Blocks | Effort | Files to Change |
|----|-------------|----------------|---------------|--------|-----------------|
| P0-1 | **Collapse 5 tiers to 3 tiers** | 01, 02, 03, 04, 06 | Extra tiers (40+, 50+) confuse Callie, generate wrong labels and AI-fabricated escalation content | 1-2 hrs | `config.yaml`, `src/models.py`, `src/tier_classifier.py`, `app.py` (TIER_COLORS dict) |
| P0-2 | **Rebuild templates from canonical text** | 03 | AI-drifted wording, "final notice" language, wrong body text for 1-29 day and 30+ templates. Must match Callie's emailed templates exactly. | 2-4 hrs | `templates/coming_due.html`, `templates/overdue.html`, `templates/past_due_30.html` (rebuild); DELETE `templates/past_due_40.html`, `templates/past_due_50.html` |
| P0-3 | **Make Quick Edit TO/CC fields work reliably** | 04, 05, 06 | Callie cannot correct recipient emails without functional edit. Go-live depends on her manually pasting correct emails. Code review suggests edit mode may already work (lines 1411-1468 in app.py) but meeting said it was non-functional. | 1-2 hrs | `app.py` (render_preview_page, editing_{idx} toggle) |
| P0-4 | **Add settings persistence (save button)** | 04, 06 | Tier boundary changes, CC list edits, and sender config revert on regeneration. Explicitly called out in meeting: "There's no save button here." | 1-2 hrs | `app.py` (render_settings_page), possibly `src/config.py` |
| P0-5 | **Dynamic subject line for 30+ tier** | 01, 03, 06 | Subject must show "30+ Days Past Due", "40+ Days Past Due", "50+ Days Past Due" etc. based on actual days. Body stays the same. | 1-2 hrs | `src/template_engine.py` (build_subject_line), `src/tier_classifier.py` |

**Total P0 estimated effort: 6-12 hours of focused development.**

### P1: Should Fix (Degrades Experience)

| ID | Requirement | Source Reports | Impact | Effort |
|----|-------------|----------------|--------|--------|
| P1-1 | **Scheduled send (7 AM PT / 10 AM ET)** | 01, 04, 06 | Callie must wake up early or delay sends without scheduling. Travis explicitly requested this. | 3-4 hrs |
| P1-2 | **Rep email dynamically added to CC** | 01, 04, 05, 06 | Each email should CC the assigned sales rep. Requires rep name-to-email lookup table. | 2-3 hrs |
| P1-3 | **Fix "Use Default File" checkbox** | 04, 06 | Defaults to True, silently uses stale data if Callie forgets to upload. Should default to False or be removed. | 15 min |
| P1-4 | **Fix Coming Due tier boundary** | 06 | Config says -3 to 3 but meeting agreed -7 to 0. Must update config.yaml. | 15 min |
| P1-5 | **Fix sender name hardcoded as "Laura"** | 06 | Line 1290 of app.py hardcodes `f"Laura <{sender_email}>"`. Should use session state sender_name. | 10 min |
| P1-6 | **CC/BCC per-email editing persistence** | 04, 05 | Verify that Quick Edit changes to CC/BCC actually persist after save. Add BCC field to edit interface. | 1 hr |
| P1-7 | **Template editing exposed in UI** | 04, 06 | Templates are "sealed" in HTML files, not viewable or editable from the interface. | 3-4 hrs |
| P1-8 | **Gmail App Password persistence** | 06 | App password must be re-entered every time Streamlit restarts (common on Streamlit Cloud). | 1 hr |
| P1-9 | **Remove OVERDUE_TIMEFRAME dynamic ranges** | 03 | Current overdue.html has 6 dynamic ranges instead of static "overdue". Remove entirely per Callie's correction. | 30 min |
| P1-10 | **Fix dual Tier enum problem** | 03 | `models.py` and `tier_classifier.py` each define their own `Tier` enum. Must consolidate to single source of truth. | 1 hr |

### P2: Nice to Have (Future Enhancements)

| ID | Requirement | Source Reports | Value |
|----|-------------|----------------|-------|
| P2-1 | **Google Sheets API auto-read** | 01, 02, 06 | Eliminates manual download/upload step entirely |
| P2-2 | **Notion API contact resolution** | 01, 02, 05, 06 | Auto-populate TO field per SOP cascade. Biggest time-saver for Callie. |
| P2-3 | **Brand AR Summary ingestion** | 02, 05 | Add Nabis POC contacts as fallback source in contact resolution chain |
| P2-4 | **PICC Platform intranet integration** | 04, 06 | Move from standalone Streamlit to module within intranet alongside proposal generator |
| P2-5 | **Dropdowns for settings fields** | 04, 06 | Convert text inputs to selectbox/radio widgets for tier labels |
| P2-6 | **Red OCM warning banner on all 30+ emails** | 03, 06 | Travis liked the visual red-bordered warning bar. Add to canonical 30+ template. |
| P2-7 | **Email send history tracking (persistent)** | 01, 06 | Log which stores received emails and when, across sessions |
| P2-8 | **Auto-attach ACH PDF** | 01 | Currently flagged; ensure always attached for all tiers |
| P2-9 | **Chronic offender flagging** | 01 | Tag stores repeatedly 50+ days late |
| P2-10 | **Store responsiveness/retailer type metadata** | 02, 05 | Use Brand AR Summary's Responsiveness and Retailer Type for prioritization |

---

## 6. File Change Matrix

| File | Changes Needed | Requirements Addressed | Priority |
|------|---------------|----------------------|----------|
| `config.yaml` | Collapse 5 tiers to 3: T1=Coming Due (-7 to 0), T2=Overdue (1-29), T3=30+ (30-999). Remove T4/T5. Fix Coming Due boundary from -3 to -7. | P0-1, P1-4 | **P0** |
| `src/models.py` | Consolidate Tier enum to 3 values (T0=Coming Due, T1=Overdue, T2=30+ Past Due). Remove T3, T4. Update `TierConfig.default_tiers()` to return 3 entries. | P0-1, P1-10 | **P0** |
| `src/tier_classifier.py` | Reduce Tier enum to 3 values. Update `classify()` to map 30+ to single tier. Remove `PAST_DUE_40` and `PAST_DUE_50`. Add `get_dynamic_subject_label(days)` function. Remove `get_overdue_timeframe_description()`. | P0-1, P0-5, P1-9, P1-10 | **P0** |
| `src/template_engine.py` | Remove "ACTION REQUIRED" and "FINAL NOTICE" subject suffixes. Remove T4/T5-specific context building. Remove `OVERDUE_TIMEFRAME` variable. Add dynamic subject label calculation for 30+. Remove T5 sender escalation logic. Keep `PAYMENT_DEADLINE_DATE`. | P0-2, P0-5, P1-9 | **P0** |
| `templates/coming_due.html` | Minor fix: "Attached is" -> "Attached you'll find" (match canonical) | P0-2 | **P0** |
| `templates/overdue.html` | Moderate: Remove `{{OVERDUE_TIMEFRAME}}` dynamic variable. Replace with static "overdue". Fix body text to match canonical corrected version. | P0-2, P1-9 | **P0** |
| `templates/past_due_30.html` | Rebuild from canonical text. Remove extra paragraph. Fix attachment line. Fix singular/plural ("invoice" -> "invoices"). Add `{{PAYMENT_DEADLINE_DATE}}` line per meeting decision. | P0-2 | **P0** |
| `templates/past_due_40.html` | **DELETE entirely** | P0-2 | **P0** |
| `templates/past_due_50.html` | **DELETE entirely** | P0-2 | **P0** |
| `app.py` | (1) Remove TIER_COLORS entries for 40+/50+. (2) Fix edit button functionality for TO/CC/BCC. (3) Add Save Settings button. (4) Remove "Use Default File" checkbox. (5) Fix hardcoded "Laura" in From display. (6) Add BCC field to Quick Edit. | P0-1, P0-3, P0-4, P1-3, P1-5, P1-6 | **P0/P1** |
| `src/contact_resolver.py` | (Future) Refactor to implement cascading SOP: Notion Primary > Billing > Associated (source-filtered) > Brand AR Summary > Managers. Support multiple TO recipients. | P2-2, P2-3 | **P2** |
| `src/data_loader.py` | (Future) Add Brand AR Summary XLSX ingestion. Add Google Sheets API read. | P2-1, P2-3 | **P2** |
| New: `src/scheduler.py` | Implement scheduled send (7 AM PT). Either Gmail API scheduled send or server-side scheduler. | P1-1 | **P1** |
| New: `src/notion_client.py` | Notion API integration for contact resolution. | P2-2 | **P2** |
| New: `data/rep_email_map.json` | Rep name -> email lookup table for dynamic CC. | P1-2 | **P1** |

---

## 7. User Flow Specification

**Source**: Report 04 (UX Requirements), refined with input from Reports 01 and 06.

### Step-by-Step Ideal User Flow

```
STEP 1: OPEN TOOL
  Callie opens the AR Email Automation web app via Streamlit Cloud URL
  (Future: opens PICC Platform intranet and clicks AR Emails section)

STEP 2: UPLOAD DATA
  Click "Browse Files" in sidebar
  Select the just-downloaded XLSX from Downloads folder
  (Future: tool auto-reads from Google Sheets API, no upload needed)

STEP 3: CONFIGURE SENDER
  Enter sender name (e.g., "Kali Speerstra")
  Enter sender email (e.g., "kali@piccplatform.com")
  Enter Gmail App Password (if not persisted)

STEP 4: GENERATE EMAILS
  Click "Generate Emails" button
  Tool processes:
    - Parses XLSX (auto-detects most recent Overdue sheet)
    - Classifies each invoice into 3 tiers based on Days Over
    - Skips: paid invoices, "Payment Enroute" status, already-emailed
    - Groups invoices by store
    - Generates email drafts using canonical templates
    - Fills in all dynamic variables
    - Resolves contacts (currently from Managers sheet; future: Notion API)
  Displays email queue sorted by urgency (worst overdue first)

STEP 5: REVIEW EACH EMAIL
  For each email in the queue:
    - Click "Preview" to see full email
    - Verify TO address (manually check against Notion if needed)
    - Verify CC includes: rep email, ny.ar@nabis.com, Martin, Mario, Laura
    - Check body content and invoice details
    - Approve or Reject each email
    - Use "Edit" button to fix TO/CC/Subject if needed

STEP 6: EDIT IF NEEDED
  Click "Edit" on preview page
  Quick Edit tab: modify TO, CC, BCC, Subject as comma-separated text
  Click "Save" to persist changes
  (Future: TO field auto-populated from Notion API)

STEP 7: SCHEDULE SEND
  Set send time: 7:00 AM Pacific (10:00 AM Eastern)
  (Currently not implemented -- emails send immediately)
  (Workaround: Callie clicks "Send via Gmail" at the right time)

STEP 8: SEND
  Click "Send via Gmail" on the queue page
  Tool sends all approved emails via Gmail SMTP
  Nabis ACH Payment Form PDF attached automatically
  Progress bar shows send status per email

STEP 9: VERIFY
  Check history page for send confirmation
  (Future: persistent send log across sessions)
```

### Order of Operations (from Travis)

> "Here's her order of operations. The first thing she does is send out emails. So she runs the report, we get that sheet... nothing's filled out because those are notes as she's tracking it down."

This means the XLSX is always clean (no manual notes) when uploaded. Callie adds notes AFTER sending emails, throughout the week.

---

## 8. Unresolved Questions

| # | Question | Who Decides | Context | Impact |
|---|----------|-------------|---------|--------|
| 1 | **Can AR data come from the synced orders sheet instead of manual Balances CSV export?** | Callie + Justin | Callie was asked to check the morning after the meeting. If the orders-based Google Sheet has equivalent fields (order number, due date, days over, total due, payment status), the manual Nabis Balances export can be eliminated. | P2-1: Eliminates manual download step |
| 2 | **Which email address should AR emails come FROM?** | Travis | Currently uses `laura@piccplatform.com` in config; Callie uses her own PICC email. Travis mentioned possibly creating a dedicated `ar@piccplatform.com`. Not decided. | Affects sender config and SMTP setup |
| 3 | **Should Martin/Mario/Laura be CC or BCC?** | Travis | Travis suggested BCC (01:37:25) but this was not finalized. Currently all are CC'd. | Affects CC/BCC field configuration |
| 4 | **Exact hierarchy: does Nabis POC override Notion Primary Contact?** | Travis + Callie + Bryce | Bryce said Nabis contacts are "highly regarded." But Callie's current SOP starts with Notion Primary Contact, with Nabis POC as a fallback. The exact hierarchy for edge cases (what if Notion Primary and Nabis POC disagree?) was not formally resolved. | Affects contact_resolver.py logic |
| 5 | **Should the rep's email be in TO or CC?** | Travis | Meeting said "the rep is always included" but did not specify TO vs CC. Almost certainly CC. | Affects CC builder |
| 6 | **Day zero: is it Coming Due or Overdue?** | Travis + Callie | Meeting concluded day 0 (the due date itself) is Coming Due, not Overdue. Travis: "negative seven to zero." This means Coming Due = -7 to 0, Overdue = 1 to 29. | Resolved: Coming Due includes day 0. |
| 7 | **Exact wording of the dynamic OCM/deadline sentence in 30+ emails** | Joe + Callie | The AI-generated version says "We request payment be submitted by [date] to avoid account restrictions or OCM reporting." Need to confirm this matches the canonical 30+ template Callie sent, or is an acceptable enhancement. | Affects 30+ template content |
| 8 | **Should the red warning bar appear on ALL 30+ emails or only specific sub-tiers?** | Travis + Callie | Meeting leaned toward all 30+. Travis: "I liked that though... let's keep that. So all the 30 plus, we make it red and we just condense it." But this was not definitively assigned. | Affects template visual design |

---

## 9. Risk Register

| # | Risk | Probability | Impact | Mitigation | Source Reports |
|---|------|------------|--------|------------|----------------|
| R1 | **"Final notice" text still appears somewhere in codebase** | Medium | High (legal/relationship risk) | Grep all .py, .html, .yaml, .md files for "final notice", "FINAL NOTICE", "final_notice" before go-live. Remove every instance. | 03, 06 |
| R2 | **Callie cannot access Streamlit Cloud URL** | Medium | High (tool unusable) | Test access before Thursday. Provide backup local run instructions from USER_GUIDE.md. | 04, 06 |
| R3 | **Gmail App Password setup fails for Callie's account** | Medium | High (cannot send) | Provide step-by-step with screenshots. Test with her actual account. Fallback: export .eml files and send from Gmail directly. | 06 |
| R4 | **Template text does not match canonical after edits** | Medium | Medium (embarrassing if wrong email reaches customer) | Parallel testing: Callie reviews every email before approving. Never auto-send without review. Diff templates against canonical text in this document. | 03, 06 |
| R5 | **Wrong recipient gets an AR email** | Low | Very High (confidential financial info to wrong person) | Contact resolution is manual for go-live (Callie pastes emails). Same risk as current manual process. | 05, 06 |
| R6 | **XLSX format changes break data_loader.py** | Low | High (tool cannot generate) | Keep manual fallback. data_loader.py has alias mapping for resilience. Test with each new XLSX before relying on tool. | 02, 06 |
| R7 | **Session state lost on Streamlit Cloud refresh** | High | Medium (loses approved/rejected state, app password) | Callie should do entire workflow in one session: upload, generate, review, approve, send. No multi-session workflow. | 06 |
| R8 | **Dual Tier enum causes runtime errors during tier consolidation** | Medium | High (app crashes) | Consolidate `models.py` and `tier_classifier.py` Tier enums to single source of truth FIRST, then modify tiers. | 03 |
| R9 | **AI-generated escalation text reappears after template rebuild** | Low | High (prohibited language in emails) | Use canonical text from this document as single source of truth. Add automated grep check in CI/CD for prohibited phrases. | 03 |
| R10 | **Streamlit Cloud has downtime Thursday morning** | Low | Medium (delays email sending) | Can run locally as backup. USER_GUIDE has local instructions. | 06 |
| R11 | **Config.yaml overwrites lose previously working settings** | Medium | Medium | Implement settings save with backup/rollback mechanism. | 06 |

---

## 10. Testing Strategy

### Parallel Testing Approach (from meeting)

1. **Callie continues to build and send AR emails manually** as she normally does
2. **Callie archives/saves her manual emails** for later comparison
3. **Joe runs the tool against the same weekly AR data** and generates the automated batch
4. **Side-by-side comparison** for each store:
   - Recipient email addresses (TO)
   - CC list completeness
   - Subject line format and day count
   - Email body text (template accuracy, variable substitution)
   - Invoice details (amounts, dates, order numbers)
   - Account Manager name and phone
5. **Any discrepancy is documented** with the correct source location

### Acceptance Criteria

- [ ] All 3 tiers produce correct canonical template text
- [ ] No "final notice" appears anywhere in generated emails
- [ ] No "second notice" appears anywhere
- [ ] No "ACTION REQUIRED" appears in subject lines
- [ ] Subject lines for 30+ show correct dynamic day ranges (30+, 40+, 50+, etc.)
- [ ] Invoice amounts match XLSX source (formatted as $X,XXX.XX)
- [ ] Due dates match XLSX source (formatted as MMM DD, YYYY)
- [ ] Nabis Account Manager name and phone are correctly populated
- [ ] Base CC recipients included: ny.ar@nabis.com, martinm, mario, laura
- [ ] Sender signature shows correct name (not "Mario" or "Laura" when it should be Callie)
- [ ] Tier boundaries correct: Coming Due (-7 to 0), Overdue (1 to 29), 30+ (30+)
- [ ] "Attached you'll find" wording matches canonical (not "Attached is")
- [ ] 1-29 day template says "overdue" not "nearing two weeks past due"
- [ ] 30+ template bullet order: Invoice, Due, Nabis AM, Amount (not Invoice, Due, Amount, Nabis AM)

---

## 11. Team Roles

| Person | Role | AR Email Involvement |
|--------|------|---------------------|
| **Callie (Kali Speerstra)** | NY Sales Admin | Primary operator. Builds, reviews, and sends all AR emails. Uses her PICC email as sender. Maintains canonical templates. |
| **Travis** | Operations Lead | Oversees AR process. Drives automation initiative. Makes decisions on tone, tiers, and procedures. |
| **Joe (Joe Smith)** | Developer | Built the AR email automation prototype. Manages Nabis API sync, Google Sheets pipeline, and will integrate Notion API. |
| **Justin** | Data/API Engineer | Manages Nabis-to-Google-Sheets sync pipeline. Not directly involved in email sending. |
| **Martin** | Management | CC'd on all AR emails for visibility. Careful about wording (no "final notice" language). |
| **Mario** | Management | CC'd on all AR emails for visibility. Reminded team about Brand AR Summary document. |
| **Laura** | Management | CC'd on all AR emails for visibility. Originally trained Callie on AR process. Previous AR email sender. |
| **Bryce/Mary** | Data/CRM | Working on consolidating contact data in Notion. Bryce manages dispensary master list and associated contacts. |

---

## 12. Implementation Roadmap

### Wave 1 (P0 Blockers -- Before Thursday)

| Task | Agent Type | Est. Hours | Dependencies |
|------|-----------|------------|--------------|
| Tier consolidation (5 -> 3) | Sonnet | 1-2 hrs | None (do first) |
| Template rebuild from canonical | Sonnet | 2-4 hrs | Tier consolidation |
| Dynamic subject line for 30+ | Sonnet | 1-2 hrs | Tier consolidation |
| Settings save button | Sonnet | 1-2 hrs | None |
| Edit button debugging | Sonnet | 1-2 hrs | None |
| "Final notice" grep + removal | Haiku | 30 min | After template rebuild |

### Wave 2 (P1 Items -- This Week)

| Task | Agent Type | Est. Hours | Dependencies |
|------|-----------|------------|--------------|
| Rep email lookup table + CC integration | Sonnet | 2-3 hrs | Wave 1 complete |
| Fix Coming Due boundary (-7 to 0) | Haiku | 15 min | Wave 1 tier consolidation |
| Fix "Laura" hardcoded sender name | Haiku | 10 min | None |
| Remove "Use Default File" checkbox | Haiku | 15 min | None |
| Gmail App Password persistence | Sonnet | 1 hr | None |
| Schedule send implementation | Opus | 3-4 hrs | Gmail SMTP working |

### Wave 3 (P2 Items -- Next Sprint)

| Task | Agent Type | Est. Hours | Dependencies |
|------|-----------|------------|--------------|
| Brand AR Summary XLSX ingestion | Sonnet | 3-4 hrs | None |
| Notion API contact resolution | Opus | 6-8 hrs | Notion API key setup |
| Google Sheets API auto-read | Sonnet | 4-5 hrs | Google API credentials |
| PICC intranet integration planning | Opus | 2-3 hrs | Intranet architecture review |
| Persistent send history database | Sonnet | 3-4 hrs | None |

---

## 13. Appendix: Conflict Resolution Log

| # | Conflict | Report A | Report B | Resolution |
|---|----------|----------|----------|------------|
| 1 | **Number of contact sources** | Report 01 lists 3 sources (Primary, Billing, Associated) | Report 05 lists 5 sources (Primary, Billing, Associated, Brand AR Summary, Managers Sheet) | **Report 05 is correct.** Brand AR Summary and Managers Sheet are valid fallback sources explicitly discussed in meeting. |
| 2 | **Coming Due boundary** | Report 01 says "-7 to 0" | Report 02/config.yaml says "-3 to 3" | **Report 01 is correct.** Meeting explicitly agreed -7 to 0. Config.yaml is stale and must be updated. |
| 3 | **Edit button functional?** | Report 04 says "edit button non-functional" (Travis's words) | Report 06 says code review shows Quick Edit works (lines 1411-1468) | **Both partially correct.** The code exists and may work, but there could be bugs preventing activation in the deployed version. Needs debugging and verification. |
| 4 | **Dynamic payment deadline: which tiers?** | Report 03 says "add to merged 30+ template" (all 30+) | Report 06 says "currently only on 40+/50+" and lists as P2 | **Report 03 is correct for scope, but priority is P1 not P2.** Travis explicitly said "I want to be putting that on all the 30 plus emails." Include in 30+ template during rebuild. |
| 5 | **Schedule day** | Report 06 config says "Wednesday at 07:00 ET" | Report 01 says "weekly, 7 AM PT" | **Report 01 is correct.** The schedule is 7:00 AM Pacific Time (10:00 AM Eastern). Config has wrong timezone. Day of week is flexible (Callie sends when data is ready). |
| 6 | **Tier enum naming** | Report 03: models.py uses T0-T4 | Report 02: config.yaml uses T1-T5 | **Both are stale.** After consolidation, there should be ONE Tier enum with 3 values. The dual-enum problem must be resolved during Wave 1. |
| 7 | **Red warning bar priority** | Report 03: P0 (include in template rebuild) | Report 06: P2 (nice to have) | **Resolution: P1.** Travis explicitly liked it and said to include it on all 30+ emails. Include during template rebuild but it is not a go-live blocker if the canonical text is correct without it. |

---

*End of Document 07 - Unified Requirements Specification*
*This document supersedes all individual Wave 0 reports for implementation purposes.*
*All agents in subsequent waves should read this document as their primary input.*
