# Data Flow Analyst Report

## Report: 02 - Data Sources & Field Mapping
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 2 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (full meeting transcript, ~7000 lines)
- `A:\Downloads\Action items.md` (meeting action items summary)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\data_loader.py` (1030 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\config.yaml` (243 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\models.py` (690 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\coming_due.html` (119 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\agent-outputs\04-xlsx-schema-analysis.md`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\agent-outputs\10-data-template-map.md`
- `A:\Downloads\Brand AR Summary - PICC (1).xlsx` (via openpyxl inspection)

## Verdict:
The AR email automation system draws from **five distinct data sources** across three systems (Nabis/Google Sheets, a static XLSX, and Notion). The primary source is the "NY Account Receivables Overdue" Google Sheet (downloaded as XLSX), which itself is fed by the Nabis API via the "Sync Master Sales Sheet." Contact email addresses -- the most critical dynamic field -- are currently the **largest data gap**: they require manual lookup from Notion and are NOT in the AR overdue spreadsheet. The Brand AR Summary XLSX from Nabis provides an alternative POC source but is a static document. The app's `data_loader.py` currently handles invoice data and Managers-sheet contacts well, but cannot yet pull from Notion or the Nabis API directly.

---

## Executive Summary

The AR email automation produces templated collection emails where most fields come from a single XLSX workbook (the "NY Account Receivables Overdue" Google Sheet). However, the critical "who do we email?" question requires cross-referencing multiple systems -- Notion CRM for primary/billing contacts, a separate Nabis-provided Brand AR Summary for POC emails, and the Managers tab within the XLSX itself. The meeting revealed that Callie currently performs **manual lookup per store** across these systems to assemble each email's recipient list. Automating this is the highest-priority gap.

---

## 1. Data Source Map

### 1.1 Complete Email Field-to-Source Mapping

| Email Field | Template Variable | Source System | Source File/Sheet/Column | Currently in App? | Meeting Notes |
|-------------|------------------|---------------|--------------------------|-------------------|---------------|
| **Store name** | `{{STORE_NAME}}` / `{{LOCATION}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col B: "Location" | YES | Pulled directly from the uploaded XLSX |
| **Contact first name** | `{{CONTACT_FIRST_NAME}}` | AR Overdue XLSX | Sheet: `Managers`, Col D: "POC Name & Title" | YES (from Managers tab) | Parsed from multi-line field. Falls back to "Team" if missing |
| **Contact email (TO)** | `{{RECIPIENT_EMAIL}}` | **Notion CRM** (primary) + **Managers sheet** (fallback) + **Brand AR Summary** (Nabis POC) | Notion: Primary Contact > Billing/AP > Associated Contacts (Nabis source preferred) | PARTIAL -- Managers tab only | **Biggest gap.** Callie manually looks up in Notion per store. Meeting: "that's a big one that we gotta check" (Travis, ~13:00). Brand AR Summary has POC Email column. |
| **Invoice number** | `{{INVOICE_NUMBER}}` / `{{ORDER_NO}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col A: "Order No" | YES | Cast float to int to string |
| **Amount due** | `{{AMOUNT}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col K: "Total Due" | YES | Formatted as `$X,XXX.XX` |
| **Due date** | `{{DUE_DATE}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col I: "Due Date" | YES | Formatted as `MMM DD, YYYY` |
| **Days past due** | `{{DAYS_PAST_DUE}}` (used for tier classification) | AR Overdue XLSX | Sheet: `Overdue {date}`, Col J: "Days Over" | YES | Drives tier assignment (T0-T4) and subject line |
| **Nabis Account Manager name** | `{{NABIS_AM_NAME}}` / `{{ACCOUNT_MANAGER}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col C: "Account Manager" | YES | Already in the overdue sheet. Was previously guessed from historical emails but now correctly pulled from Col C. Meeting confirmed this at ~01:12:00. |
| **Nabis AM phone** | `{{NABIS_AM_PHONE}}` / `{{AM_PHONE}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col D: "Acocunt Manager Phone Number" (typo in header) | YES | Header has typo "Acocunt" -- data_loader.py handles this with alias mapping |
| **Rep name (PICC sales rep)** | `{{REP}}` | AR Overdue XLSX | Sheet: `Overdue {date}`, Col L: "Rep" | YES | Used for CC routing. Rep email derived via lookup table in config. |
| **Rep email (for CC)** | `{{REP_EMAIL}}` | Derived | Lookup from Rep name -> email mapping in config/code | PARTIAL | Meeting: "The rep email, we always include whoever the rep is" (~01:34:56) |
| **CC recipients** | (base CC list) | Static config | `config.yaml` cc_rules.base_cc | YES | Always: `ny.ar@nabis.com`, `martinm@piccplatform.com`, `mario@piccplatform.com`, `laura@piccplatform.com` |
| **Sender name** | `{{SENDER_NAME}}` | Static config | `config.yaml` sender.name | YES | "PICC Accounts Receivable" (or Callie's name) |
| **Sender email** | From address | Static config + user input | `config.yaml` sender.email + UI input | YES | Currently `laura@piccplatform.com` in config; user enters their email in UI |
| **Tier label** | `{{TIER_LABEL}}` | Derived | Calculated from Days Over via tier boundaries | YES | Three agreed templates: Coming Due, 1-29 Days Past Due, 30+ Days Past Due |
| **OCM warning text** | (embedded in 30+ template) | Derived | Present when Days Over >= 30 | YES | "We request payment be submitted by [date] to avoid account restrictions or OCM reporting" |
| **Payment deadline date** | Dynamic date in 30+ emails | Derived | Calculated from current date + Nabis 45-day policy | PARTIAL | Meeting: Travis wants dynamic date on all 30+ emails |
| **Email sent flag** | (skip logic) | AR Overdue XLSX | Sheet: `Overdue {date}`, Col E: "Email Sent" | YES | Used to skip already-emailed invoices |
| **Paid flag** | (skip logic) | AR Overdue XLSX | Sheet: `Overdue {date}`, Col M: "Paid" | YES | Used to skip paid invoices |
| **Status** | (skip logic) | AR Overdue XLSX | Sheet: `Overdue {date}`, Col O: "Status" | YES | "Payment Enroute" skips sending |
| **ACH form attachment** | Static file | Local file | `data/Nabis_ACH_Payment_Form.pdf` | YES | Attached to all tiers |
| **Signature block** | Static HTML | `config.yaml` signature section | Static values: address, tagline, links | YES | Hardcoded in templates + config |

---

## 2. Data Source Systems

### 2.1 Primary Source: NY Account Receivables Overdue (Google Sheet / XLSX)

**What it is**: A Google Sheet that Callie downloads as XLSX before each email run. It contains the overdue invoice data plus a Managers contact directory.

**How it gets data**: The Google Sheet is populated by the **Sync Master Sales Sheet**, which itself is fed by Justin's Nabis API sync. The sync pulls from Nabis `orders` and `order details` endpoints. The Data sheet within the workbook uses `FILTER()` formulas against a `balances` sheet to produce the overdue view.

**Current workflow**: Callie goes to Nabis > Balances > filters "delivered" and "delivered with edits" > clicks "email CSV" > receives CSV via email. This is then loaded into the Google Sheet. This is a **manual step** that the team wants to eliminate.

**Sheets in the workbook**:

| Sheet | Purpose | Row Count | Key Columns |
|-------|---------|-----------|-------------|
| `Overdue {M-D}` | Weekly snapshot of overdue invoices (active) | ~70-90 rows | Order No, Location, Account Manager, AM Phone, Email Sent, Caller, Called, Made Contact, Due Date, Days Over, Total Due, Rep, Paid, F/U Date, Status, Notes |
| `Data` | Formula-driven live view (fallback if no Overdue sheet) | ~70 rows | Same as Overdue (mirrors balances via FILTER formulas) |
| `Managers` | Retailer POC directory | ~620 records | Retailer Name (DBA), Account Manager, Account Manager Phone#, POC Name & Title, POC Email, POC Phone |
| `balances` | Full AR ledger with financial breakdown | ~100 rows | Order No, Location, Due Date, Days Over, Total Due, etc. |
| `Territory` | Sales-rep territory assignments | varies | Rep name to territory mapping |

**Meeting quote** (Travis, ~01:04:08): "So this is automatically updating off of the Sync Master Sales Sheet... Yes. One of those."

**Meeting quote** (Travis, ~01:02:20): "What other places do we pull information from that you're pulling it from?"

### 2.2 Secondary Source: Managers Sheet (within XLSX)

The `Managers` sheet is the **contact directory** embedded in the same workbook. It has ~620 retailer records with:
- `Retailer Name (DBA)` -- join key to `Location` in overdue sheets
- `Account Manager` + phone
- `POC Name & Title` -- multi-line field (e.g., "Emily Stratakos (AP)\nJo-Anne Rainone - Accounting")
- `POC Email` -- multi-line field with multiple email addresses
- `POC Phone` -- multi-line field

The `data_loader.py` already parses this with sophisticated logic:
- Splits multi-line POC fields on newlines
- Prefers AP/Accounting/Billing contacts (via `_AR_TITLE_KEYWORDS`)
- Prefers `ap@`, `accounting@`, `invoices@` email prefixes
- Fuzzy matches store names (handles trailing periods, case differences)

### 2.3 Tertiary Source: Brand AR Summary XLSX (Nabis-provided)

**File**: `A:\Downloads\Brand AR Summary - PICC (1).xlsx`

**What it is**: A Nabis-provided spreadsheet mapping retailers to their AR status, aging buckets, POC contacts, and engagement notes. This is the document Callie references for Nabis POC emails.

**Structure** (1 sheet, "Sheet1"):
- **Rows**: 1002 (header row has "PICC" as brand identifier)
- **Columns**: 19 (17 meaningful + 2 empty)

**Headers** (row 3 after 2 title rows):

| Column | Header | Description | Example |
|--------|--------|-------------|---------|
| A | Retailer | Store/dispensary name | "A Cannaful Life" |
| B | Retailer Type | Quality classification | "Good", "Weak" |
| C | Responsiveness | Communication rating | "Unresponsive", "Semi-Responsive", "Responsive" |
| D | Number of Invoices (Current) | Count of current invoices | 2 |
| E | Number of Invoices (overdue) | Count of overdue invoices | 0 |
| F | Last Payment Date | Date of most recent payment | 2025-12-30 |
| G | Last Delivery Date | Date of most recent delivery | "No data" or date |
| H | Current | Current (not yet due) balance | 3875.26 |
| I | 0-30 | 0-30 day overdue balance | 0 |
| J | 30-60 | 30-60 day overdue balance | 0 |
| K | 60-90 | 60-90 day overdue balance | 0 |
| L | 90+ | 90+ day overdue balance | 0 |
| M | Total | Total balance | 3875.26 |
| N | Last Engage | Date of last engagement/contact | 2026-01-23 |
| O | POC Email | Point of contact email(s), newline-separated | "sageap@platformcanna.com\nteam@stayallgood.com" |
| P | POC Phone | Point of contact phone with name | "Sean (512) 298-9392" |
| Q | Notes | Detailed engagement notes | "Sent Anthony general reminder email..." |

**Mapping to template variables**:
- `POC Email` (col O) --> `{{RECIPIENT_EMAIL}}` -- **This is a key alternative source for contact emails**
- `POC Phone` (col P) --> Could supplement contact info
- `Retailer` (col A) --> Join key to `Location` in overdue sheet
- `Responsiveness` (col C) --> Could be used for prioritization/escalation logic
- `Notes` (col Q) --> Callie's engagement tracking
- Aging columns (H-L) --> Alternative aging data (but overdue sheet is primary)

**Meeting context** (~01:24:02): Callie mentions "the brand AR summary, I think, is the one I'm thinking of" when discussing where to get Nabis POC contacts. Travis confirms "Is that from Nabis? Yes, I believe so."

**Key insight**: This document provides Nabis's own point-of-contact information for each retailer. It is **not currently ingested by the app** but contains the very data that Callie manually looks up.

### 2.4 Tertiary Source: Notion CRM (Dispensary Master List)

**What it is**: The company's CRM/operational database in Notion. Each dispensary has a page with structured fields.

**Contact hierarchy** (as described by Callie at ~01:19:50 and confirmed by Bryce at ~01:28:00):

1. **Primary Contact** -- manually entered, not auto-overwritten by imports
2. **Billing/AP Contact** -- below primary, specifically for AR
3. **Associated Contacts** -- imported from various sources (Nabis POC, CRM imports, Revelry buyers list)
   - **Nabis import/POC** contacts are considered **most reliable**
   - **Revelry** contacts are considered **least reliable** (deprioritized)

**Current process**: Callie opens each store's Notion page, checks Primary Contact, then Billing/AP, then Associated Contacts (preferring Nabis-sourced ones). She copy-pastes the appropriate email address into each AR email.

**Meeting quote** (Callie, ~01:19:50): "I usually go into Notion, and I open up the store's overview and I was just going off of the main contact that's listed there. The primary, I guess, the primary contact or the buyer. But there is lower down a billing or AP contact."

**Meeting quote** (Bryce, ~01:27:28): "I don't ever overwrite the primary contact field... if I'm adding stuff from like, well, I got it from a Nabis exporter, from the revelry list, or whatever, then I add those as associates."

**API access**: Joe confirmed he can pull from Notion API ("Can this AI talk to Notion, Joe?" "Yes" ~01:21:02), but it requires setting up a Notion API key and a separate pull request integration. This was identified as a future enhancement.

### 2.5 Source: Nabis API (via Sync Master Sales Sheet)

**What it provides**: Order data, delivery data, payment status, and AR balances -- synced into Google Sheets by Justin's automation.

**Current sync**: The `orders` and `order details` tabs in the Sync Master Sales Sheet auto-update from Nabis API. These feed the formulas in the AR overdue Google Sheet.

**AR-specific data**: The `balances` endpoint requires a **manual export** (Nabis > Balances > filter > email CSV). This is NOT part of the current auto-sync.

**Meeting quote** (Justin via phone, ~01:07:04): "I didn't show him that one. That one is, uh, with... Like, have it sent an email to us."

**Meeting quote** (Travis, ~01:07:10): "So that's not a sync API... There's a fundamental difference between that and the other stuff."

**Key question resolved**: Travis asked Justin to check in the morning whether the `orders`-based Google Sheet contains equivalent AR fields, so they could eliminate the manual balances download. If so, Joe would read directly from the synced Google Sheet via API.

---

## 3. AR Overdue Spreadsheet Structure (Primary Input)

### 3.1 Most Recent Sheet Schema (`Overdue 2-3`)

| Col | Header | Type | Used By App? | Template Variable | Notes |
|-----|--------|------|-------------|-------------------|-------|
| A | Order No | float | YES | `{{INVOICE_NUMBER}}` | Cast to int, then string |
| B | Location | string | YES | `{{STORE_NAME}}` | Join key to Managers |
| C | Account Manager | string | YES | `{{NABIS_AM_NAME}}` | Nabis AM assigned to retailer |
| D | Acocunt Manager Phone Number | string | YES | `{{NABIS_AM_PHONE}}` | Typo in header handled by alias |
| E | Email Sent | boolean | YES | (skip logic) | If True, skip this invoice |
| F | Caller | string | NO | -- | Callie's tracking notes |
| G | Called | boolean | YES | (skip logic) | Tracking field |
| H | Made Contact | boolean | YES | (skip logic) | Tracking field |
| I | Due Date | datetime | YES | `{{DUE_DATE}}` | Formatted MMM DD, YYYY |
| J | Days Over | float | YES | Tier classification | Drives template selection |
| K | Total Due | float | YES | `{{AMOUNT}}` | Formatted $X,XXX.XX |
| L | Rep | string | YES | CC routing | PICC sales rep for this territory |
| M | Paid | boolean | YES | (skip logic) | If True, skip this invoice |
| N | F/U Date | datetime | YES | (metadata) | Follow-up date |
| O | Status | string | YES | (skip logic) | "Payment Enroute" = skip |
| P | Notes | string | YES | (metadata) | Free-text, ignored for email gen |

### 3.2 Managers Sheet Schema (Contact Directory)

| Col | Header | Type | Used By App? | Template Variable |
|-----|--------|------|-------------|-------------------|
| A | Retailer Name (DBA) | string | YES | Join key |
| B | Account Manager | string | YES | `{{ACCOUNT_MANAGER}}` |
| C | Account Manager Phone# | string | YES | `{{AM_PHONE}}` |
| D | POC Name & Title | string (multi-line) | YES | `{{CONTACT_FIRST_NAME}}` |
| E | POC Email | string (multi-line) | YES | `{{RECIPIENT_EMAIL}}` |
| F | POC Phone | string (multi-line) | YES | (metadata) |

---

## 4. Current data_loader.py Analysis

### 4.1 Architecture

The `data_loader.py` module (1030 lines) is a well-structured XLSX parser that:

1. **Opens** the workbook via openpyxl (supports file path or BytesIO buffer)
2. **Auto-detects** the most recent `Overdue M-D` sheet (sorts by month/day descending)
3. **Parses invoices** from the overdue sheet using a header-map system resilient to column reordering
4. **Parses contacts** from the `Managers` sheet with multi-line POC field splitting
5. **Matches** invoices to contacts via fuzzy store-name lookup
6. **Returns** a `LoadResult` containing invoices, contacts, and diagnostics

### 4.2 Header Mapping (Resilient to Column Reordering)

The loader uses alias dictionaries so it works even if columns move:

```python
_OVERDUE_HEADERS = {
    "order_no":       ["Order No", "Order Number"],
    "location":       ["Location"],
    "account_mgr":    ["Account Manager"],
    "am_phone":       ["Acocunt Manager Phone Number", "Account Manager Phone Number", "Account Manager Phone#"],
    "email_sent":     ["Email Sent"],
    "days_over":      ["Days Over", "Days Overdue", "Overdue"],
    "total_due":      ["Total Due"],
    "rep":            ["Rep"],
    "paid":           ["Paid"],
    "status":         ["Status"],
    # ... etc
}
```

### 4.3 Contact Resolution Logic

The loader implements a sophisticated contact-selection algorithm:

1. **Parse POC names**: Handles `"Emily Stratakos (AP)"` and `"Jo-Anne Rainone - Accounting"` formats
2. **Select primary contact**: Prefers contacts with titles containing "ap", "accounting", "finance", "billing", "accounts payable"
3. **Select primary email**: Prefers addresses containing `ap@`, `accounting@`, `invoices@`, `billing@`
4. **Fuzzy name matching**: Normalized (lowercased, stripped) exact match first, then substring containment

### 4.4 Skip Reason Detection

Invoices are automatically skipped (not emailed) when:
- `paid` is True
- `status` is "Payment Enroute"
- `email_sent` is True (already emailed this cycle)
- `account_manager` is blank or `#N/A`

### 4.5 What data_loader.py Does NOT Do

- Does NOT pull from Notion API (contact emails from CRM)
- Does NOT read the Brand AR Summary XLSX
- Does NOT connect to the Nabis API directly
- Does NOT read from Google Sheets API (requires manual XLSX download)
- Does NOT map rep names to rep email addresses (this is in the email builder)
- Does NOT handle the "associated contacts" priority logic from Notion (Nabis POC > CRM > Revelry)

---

## 5. config.yaml Field Definitions

### 5.1 Tier Boundaries

| Tier | Min Days | Max Days | Label | Template File |
|------|----------|----------|-------|---------------|
| T1 | -3 | 3 | Coming Due | `coming_due.html` |
| T2 | 4 | 29 | Overdue | `overdue.html` |
| T3 | 30 | 39 | 30+ Days Past Due | `past_due_30.html` |
| T4 | 40 | 49 | 40+ Days Past Due | `past_due_40.html` |
| T5 | 50 | 999 | 50+ Days Past Due | `past_due_50.html` |

**DISCREPANCY vs. Meeting Agreement**: The meeting agreed on **three** templates (Coming Due, 1-29 Days Overdue, 30+ Days Past Due), but `config.yaml` still has **five** tiers. The team decided T3/T4/T5 should all use the **same body template** with only the subject line varying dynamically. The config has not been updated to reflect this.

**DISCREPANCY vs. models.py**: The `Tier` enum in `models.py` defines T0-T4 (5 tiers) while config.yaml defines T1-T5 (5 tiers with different numbering). These are misaligned in naming but functionally equivalent.

### 5.2 CC Rules

```yaml
base_cc:
  - "ny.ar@nabis.com"
  - "martinm@piccplatform.com"
  - "mario@piccplatform.com"
  - "laura@piccplatform.com"
```

The assigned sales rep is added automatically from the contact sheet. This matches the meeting discussion (~01:37:06) where Callie confirmed she always CCs Martin, Mario, and Laura.

### 5.3 Sender Configuration

- Default sender: "PICC Accounts Receivable" / `laura@piccplatform.com`
- Escalation sender (T5+): "Mario Serrano" / `mario@piccplatform.com`
- Callie sends from her own PICC email currently

### 5.4 Other Config Fields

- **Attachment rules**: ACH form always attached; BOL/invoice PDF flagged at T4+
- **Subject line formula**: `PICC - {retailer_name} - Nabis Invoice {invoice_number} - {tier_label}`
- **Schedule**: Wednesday at 07:00 ET
- **Fuzzy match threshold**: 82 (fuzzywuzzy ratio)
- **Review flags**: Multi-invoice, credits, bounced contacts, T5+ escalation, disputes, >90 days

---

## 6. Brand AR Summary XLSX Analysis

### 6.1 Document Identity

- **Source**: Nabis (provided to PICC)
- **File**: `Brand AR Summary - PICC (1).xlsx`
- **Purpose**: Nabis's view of PICC's retailer AR portfolio with Nabis-assigned contacts
- **Records**: ~1000 retailers

### 6.2 Key Data It Contains That the App Needs

| Field | Column | Currently Used? | Could Replace |
|-------|--------|----------------|---------------|
| POC Email | O | NO | Manual email lookup from Notion |
| POC Phone | P | NO | Phone lookup |
| Retailer Type (Good/Weak) | B | NO | Could prioritize outreach |
| Responsiveness | C | NO | Could adjust tone/frequency |
| Aging buckets (0-30, 30-60, 60-90, 90+) | I-L | NO | Alternative to Days Over calculation |
| Last Payment Date | F | NO | Could inform skip logic |
| Last Engage date | N | NO | Could prevent over-contacting |
| Notes | Q | NO | Callie's engagement history |

### 6.3 How It Maps to AM Assignments

The Brand AR Summary does **NOT** contain a Nabis Account Manager column. The Account Manager data comes from the `Managers` sheet in the AR Overdue workbook and from Column C in the `Overdue {date}` sheets.

### 6.4 Integration Opportunity

The Brand AR Summary's `POC Email` column could serve as the Nabis-sourced contact that Bryce described as "highly regarded" in the meeting. Importing this as a fallback contact source would reduce Callie's manual Notion lookups significantly.

---

## 7. The "Sync Master Sales Sheet" Explained

### 7.1 What It Is

The Sync Master Sales Sheet is a Google Sheets workbook maintained by Justin that auto-syncs with the Nabis API. It has at minimum:
- **Orders** tab: All orders with delivery dates, amounts, payment status
- **Order Details** tab: Line-item detail per order

### 7.2 How It Feeds AR Data

```
Nabis API (orders/details)
    |
    v
Justin's sync script (runs daily)
    |
    v
Sync Master Sales Sheet (Google Sheets)
    |
    v
NY Account Receivables Overdue (Google Sheet)
    |-- Data sheet: uses FILTER() formulas against balances
    |-- balances sheet: fed by manual Nabis CSV export OR order calculations
    |-- Overdue {date} sheets: weekly snapshots (manual copy)
    |
    v
data_loader.py (reads downloaded XLSX)
    |
    v
Email templates + rendering
```

### 7.3 The Manual Gap

The `balances` data in the Google Sheet currently requires a **manual Nabis CSV export** (Balances > filter delivered > email CSV). Justin confirmed this is not part of the auto-sync. However, Travis proposed that if the `orders` tab contains equivalent fields (payment status, amounts, due dates), the orders sync could be used instead, eliminating the manual step.

**Meeting quote** (Justin, ~01:07:04): "I didn't show him that one. That one is, uh... Like, have it sent an email to us."

**Meeting quote** (Travis, ~01:09:00): "Technically, if you can get the ARs from that, then it's automatically gonna be synced all the time."

---

## 8. Data Gaps -- What Callie Currently Looks Up Manually

### 8.1 Critical Gaps (Block Email Generation)

| Gap | What Callie Does Now | Proposed Solution (from meeting) | Priority |
|-----|---------------------|----------------------------------|----------|
| **Recipient email address** | Opens Notion, checks Primary Contact > Billing/AP > Associated Contacts (prefers Nabis source) | 1. Pull from Notion API. 2. Fall back to Managers sheet POC Email. 3. Import Brand AR Summary POC Email as additional source. | **P0 -- Highest** |
| **Rep email for CC** | Knows which rep handles which territory | Add rep name-to-email lookup table. Currently the `Rep` column gives names, not emails. | **P1** |

### 8.2 Moderate Gaps (Require Manual Verification)

| Gap | What Callie Does Now | Impact |
|-----|---------------------|--------|
| **Which template to use** | Manually checks days overdue, selects Coming Due / Overdue / 30+ | Automated via tier classification -- DONE |
| **Subject line days** | Manually writes "40+ Days Past Due" etc. in subject | Needs dynamic subject line for 30+ tier -- DISCUSSED |
| **AR data freshness** | Downloads XLSX each Wednesday morning | Could be automated via Google Sheets API read |
| **Multi-invoice detection** | Notices same store appears multiple times | App handles this -- DONE |

### 8.3 Nice-to-Have Gaps (Future Enhancements)

| Gap | Source | Notes |
|-----|--------|-------|
| Store responsiveness rating | Brand AR Summary col C | Could adjust email tone |
| Last engagement date | Brand AR Summary col N | Prevent over-contacting |
| Payment history | Nabis API / Sync Master | Inform skip logic |
| OCM reporting deadline | Calculated from Nabis 45-day policy | Dynamic date in 30+ emails |
| BOL / Invoice PDF attachments | Nabis / document storage | Currently flagged at T4+ |

---

## 9. Key Meeting Quotes on Data Sources

### On the AR Overdue Sheet:
> "First thing you do is you go to the NY Accounts Receivable Overdue Google Sheet, and you download it to your computer, and then you go to Browse Files." -- Joe, ~08:02

### On the Sync Master Sales Sheet:
> "So this is automatically updating off of the Sync Master Sales Sheet." -- Travis, ~01:04:33

### On the Nabis Balances Manual Export:
> "You go to balances, and then you filter, it's only show delivered and delivered with edits, and there's a button that emails you a CSV." -- Justin (via phone), ~01:07:39

### On the Nabis Account Manager Source:
> "Account manager, phone number, Nabis Stepford... It's because it's not labeled. You know, the account manager and account manager phone number... Oh, well that's why it's always going to be correct then because it's pulling this from, it's already doing that." -- Travis + Joe, ~01:12:49

> "This is a separate document, because we have to just upload it. It's not like we're not getting fed it automated. Automatically, but it doesn't change much." -- Travis, ~01:01:39

### On Contact Email Lookup:
> "I usually go into Notion, and I open up the store's overview and I was just going off of the main contact that's listed there. The primary, I guess, the primary contact or the buyer. But there is lower down a billing or AP contact, which sometimes has someone in it." -- Callie, ~01:19:50

### On Contact Source Hierarchy:
> "Primary contact is like the first. And real quick... the billing is... the associate... we want to use the Navis associate, the one that says that it's from Navis, has a Navis distinction." -- Travis, ~01:29:55 and ~01:30:05

> "I would say that... if it says Navis import or Navis POC, that's probably pretty... highly regarded, and then... revelry buyers list, that would probably be like one that's like a lower..." -- Bryce, ~01:28:48

### On the Brand AR Summary:
> "The brand AR summary, I think, is the one I'm thinking of... It lists the retailers, their responsiveness... And does it have their contact in NABIS?... Yes, it's their point of contact email." -- Callie + Travis, ~01:24:19

### On Template Drift:
> "It went through the training data of all of the emails that it got and was like, oh, look at all these great interesting ways that they tried... Let me see what sounds the best. Oh, I'll use this version of it." -- Joe, ~01:49:54

---

## 10. Suggested Agent Prompts for Wave 1+

### Wave 1: Contact Resolution Engine
```
OBJECTIVE: Design and implement a contact resolution module that consolidates
recipient emails from three sources with fallback priority:
1. Notion CRM API (Primary Contact > Billing/AP > Associated Contacts with Nabis POC preferred)
2. Managers sheet in AR Overdue XLSX (POC Email column)
3. Brand AR Summary XLSX (POC Email column)

INPUT: Store name from Overdue sheet
OUTPUT: Ordered list of recipient emails with source attribution

CONSTRAINTS:
- Revelry-sourced contacts should be deprioritized
- AP/Accounting/Billing contacts preferred over general contacts
- Must handle multi-line email fields
- Must handle missing data gracefully (flag for review, don't block)
```

### Wave 1: Tier Consolidation
```
OBJECTIVE: Collapse config.yaml from 5 tiers to 3 tiers per meeting agreement:
- T1: Coming Due (-7 to 0 days) -> coming_due.html
- T2: 1-29 Days Past Due -> overdue.html
- T3: 30+ Days Past Due -> past_due_30.html (single template, dynamic subject)

Remove T4/T5 as separate tiers. Subject line for 30+ should dynamically show
"30+ Days Past Due", "40+ Days Past Due", "50+ Days Past Due" based on actual days.
Remove "final notice" from all templates.
```

### Wave 1: Brand AR Summary Ingestion
```
OBJECTIVE: Add a second data source to data_loader.py that reads the Brand AR
Summary XLSX and extracts POC Email, POC Phone, Retailer Type, and Responsiveness
per retailer. Join to overdue invoices on retailer name.

NOTE: The XLSX has a non-standard header layout:
- Row 1: [None, 'PICC', None, ...]
- Row 2: [None, None, None, 'Aging Tab', ...]
- Row 3: Actual column headers start here
Parser must skip rows 1-2 and read headers from row 3.
```

### Wave 2: Google Sheets API Integration
```
OBJECTIVE: Replace the manual XLSX download workflow with direct Google Sheets API
read. The app should authenticate to Google Sheets and read the NY Account
Receivables Overdue spreadsheet in place, detecting the most recent Overdue tab.

This eliminates the "download > browse files > upload" manual step in the UI.
```

### Wave 2: Notion API Contact Pull
```
OBJECTIVE: Implement Notion API integration to pull dispensary contact information.
For each store in the overdue list:
1. Query Notion Dispensary Master List by store name
2. Extract: Primary Contact, Billing/AP Contact, Associated Contacts
3. For Associated Contacts, check the "source" field -- prefer Nabis POC/import
4. Return structured contact list with source attribution

COMPLEXITY NOTE: This was identified in the meeting as "the harder lift" requiring
a Notion API key and separate pull request interaction.
```
