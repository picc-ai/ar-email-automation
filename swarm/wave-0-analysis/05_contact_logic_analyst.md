# Contact Logic Analyst Report
## Report: 05 - Contact Selection Specification
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 5 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (full meeting transcript, 7351+ lines)
- `A:\Downloads\Action items.md` (meeting action items summary)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\contact_resolver.py` (835 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\data_loader.py` (1030 lines)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\models.py` (690 lines)
- `A:\Downloads\Brand AR Summary - PICC (1).xlsx` (1002 rows, 19 columns)
## Verdict: SIGNIFICANT GAP between current code and meeting requirements. Contact selection uses wrong priority chain, CC list is hardcoded but correct, Nabis POC contacts from Brand AR Summary are not integrated, and Notion API integration is required for dynamic contact resolution.

---

## Executive Summary

The meeting (timestamps 01:18-01:38) reveals a detailed contact selection SOP that Callie follows manually in Notion. The current `contact_resolver.py` uses a fundamentally different approach: it matches invoices to contacts from the "Managers" sheet in the XLSX using store name/license number fuzzy matching, then selects the "primary" contact based on title relevance (AP > Accounting > Owner > Manager). However, the meeting establishes that the **actual SOP** cascades through Notion fields in a specific order: Primary Contact, then Billing/AP Contact, then Associated Contacts (with Nabis-sourced associates prioritized over Revelry-sourced ones). Furthermore, a separate document -- the "Brand AR Summary" XLSX from Nabis -- contains POC email and phone data that is considered "the most reliable when available" per Bryce's input.

The CC rules are partially implemented. The code hardcodes `ny.ar@nabis.com`, `mario@piccplatform.com`, `martinm@piccplatform.com`, `laura@piccplatform.com`, and `{rep_email}` in `TierConfig.default_tiers()`. This matches meeting consensus but is not yet editable from the UI.

---

## Contact Selection Priority Chain

Derived from meeting transcript (01:19:42 - 01:33:03), confirmed by Callie, Travis, and Bryce:

### For the TO field (primary recipient):

1. **Primary Contact** (Notion field: "Primary Contact")
   - Name, phone, and email are listed under the store's Notion page
   - Bryce stated: "I don't ever overwrite the primary contact field" (01:27:44) -- these are manually entered by reps
   - Callie: "I was just going off of the main contact that's listed there. The primary, I guess, the primary contact or the buyer." (01:20:00)

2. **Billing / AP Contact** (Notion field: "Billing Contact")
   - Callie: "there is lower down a billing or AP contact, which sometimes has someone in it" (01:20:06)
   - Travis confirmed: "She goes to the primary, then she goes and sees if there's billing" (01:29:02)
   - If billing contact exists, send to BOTH primary and billing: "typically I would send it to both" (01:20:29)

3. **Associated Contacts** (Notion field: "Associated Contacts")
   - Only used when Primary and Billing are empty
   - Callie: "kind of after that, there is the associated contacts... if there's anyone in there, I might look there" (01:22:22)
   - **CRITICAL**: Associated contacts have SOURCE LABELS that determine trust level

4. **Brand AR Summary Contacts** (Nabis-provided XLSX)
   - Mario reminded the team about this separate document (01:23:51)
   - Contains Nabis's POC email and phone for each retailer
   - Callie: "Yes. Yeah, it's their point of contact email." (01:24:56)
   - These are Nabis's AR contacts for the stores

### Associated Contact Source Trust Hierarchy (from Bryce, 01:29:18):

| Source Label | Trust Level | Action |
|---|---|---|
| "Nabis import" / "Nabis POC" | HIGH | Use these preferentially |
| "CRM Contact" | HIGH | Fine to use |
| "Nabis Order, Point of Contact" | HIGH | Fine to use |
| "Revelry buyers list" | LOW | Deprioritize / do not trust |
| (other/unlabeled) | MEDIUM | Use if nothing better available |

Bryce: "If it says Navis import or Navis POC, that's probably pretty... highly regarded. And then, like, if it says revelry buyers list, that would probably be like a lower [reliability]." (01:29:23)

Travis summarized: "Just trust all of them except revelry. Or don't trust revelry." (01:32:52)
"Just don't trust revelry and just allow other sources basically." (01:32:59)

### Decision Tree (SOP):

```
1. Look up store in Notion
2. IF Primary Contact exists:
     -> TO: Primary Contact email
     -> IF Billing/AP Contact also exists:
          -> TO: Add Billing/AP Contact email too
3. ELSE IF Billing/AP Contact exists:
     -> TO: Billing/AP Contact email
4. ELSE look at Associated Contacts:
     -> IF any with source = "Nabis import" / "Nabis POC" / "CRM":
          -> TO: Use that contact's email
     -> ELSE IF any with source != "Revelry":
          -> TO: Use that contact's email
     -> ELSE IF only Revelry-sourced contacts:
          -> TO: Use with caution (flag for review)
5. IF still no email:
     -> Look at Brand AR Summary XLSX for Nabis POC Email
6. IF still no email:
     -> Flag for manual review
```

---

## CC Rules

Confirmed at meeting timestamp 01:34:50 - 01:37:09:

| Recipient | Always/Conditional | Email Address | Source |
|---|---|---|---|
| Internal Sales Rep | ALWAYS | `{rep_email}` (dynamic per account) | Travis: "The rep email, we always include whoever the rep is." (01:34:53) |
| Nabis AR Group | ALWAYS | `ny.ar@nabis.com` | Callie: "we email it to the ny.accounts email... their system just sends it to the correct manager" (01:35:26). Joe confirmed this is in the CC already. |
| Martin | ALWAYS (currently) | `martinm@piccplatform.com` | Callie: "I've been CC'ing Martin, Mario, and Laura just to keep everybody on the same [page]" (01:37:15) |
| Mario | ALWAYS (currently) | `mario@piccplatform.com` | Same as above |
| Laura | ALWAYS (currently) | `laura@piccplatform.com` | Same as above |

### CC Notes:
- Travis asked if these should be CC or BCC (01:37:25): "BCCM, I suppose. Mm-hmm."
- The Martin/Mario/Laura CC is for **historical visibility** and may transition to BCC or become configurable
- Joe stated: "it just has Martin, Mario, and Laura on the automatic send... we can make this dynamic in the future because these are just always CC recipients" (01:36:10)
- The rep email is dynamic -- it changes per store based on who handles the account (e.g., if Bryce handles it, Bryce's email is CC'd)

### Nabis Account Manager CC:
- Callie confirmed: "we always CC the Nabis account manager" (01:35:09)
- The Nabis account manager is NOT the individual manager name -- it resolves to the group inbox `ny.ar@nabis.com`
- Callie: "all of the Navis account managers use the same email. So it's always the same email." (01:35:49)

---

## BCC Rules

- Travis suggested BCC for Martin/Mario/Laura (01:37:25) but this was not finalized
- Currently all are CC'd, not BCC'd
- The UI needs editable CC/BCC fields before this can be configured per-email

---

## Brand AR Summary Data (AM Mapping)

### File: `A:\Downloads\Brand AR Summary - PICC (1).xlsx`

**Structure:**
- Sheet: `Sheet1`
- Rows: 1002 (header rows + ~999 retailer records)
- The first two rows are title/header rows; actual column headers are in row 3

**Column Headers (row 3):**
| Column | Header |
|---|---|
| A | Retailer |
| B | Retailer Type |
| C | Responsiveness |
| D | Number of Invoices (Current) |
| E | Number of Invoices (overdue) |
| F | Last Payment Date |
| G | Last Delivery Date |
| H | Current |
| I | 0-30 |
| J | 30-60 |
| K | 60-90 |
| L | 90+ |
| M | Total |
| N | Last Engage |
| O | **POC Email** |
| P | **POC Phone** |
| Q | Notes |

**Key Fields for Contact Resolution:**

1. **Retailer (col A)**: Store name -- can be used for matching against invoice Location field
2. **POC Email (col O)**: Multi-line email addresses. Examples:
   - `Acannafullife@aol.com`
   - `sageap@platformcanna.com\nteam@stayallgood.com`
   - `andre@altocanna.nyc\nstephanie@altocanna.nyc\ninvoices@altocanna.nyc`
3. **POC Phone (col P)**: Contact name + phone. Examples:
   - `Anthony - (718) 610-9739`
   - `Sean (512) 298-9392`
   - `Andre - (718) 541 9810`
4. **Retailer Type (col B)**: Quality classification (Good, Weak, Excellent, Poor)
5. **Responsiveness (col C)**: Communication pattern (Responsive, Unresponsive, Semi-Responsive)
6. **Notes (col Q)**: Detailed AR interaction history with names, dates, actions taken

**How to Use for AM Lookup:**
- This is NOT an "Account Manager" lookup sheet -- it's a retailer contact directory from Nabis
- Match `Retailer` name to invoice `Location` to find POC Email and POC Phone
- These contacts represent who Nabis contacts at each store for AR purposes
- Email field may contain multiple addresses (newline-delimited)
- This data is considered "the most reliable when available" per Bryce

**Sample Data Quality:**
- 999+ retailer entries
- POC Email is populated for most entries
- Multi-contact stores have newline-separated emails
- Notes contain the most recent AR interaction details

---

## Current contact_resolver.py Analysis

### Architecture:
- `ContactResolver` class with tiered matching strategy
- Pre-indexes contacts by license number and store name
- Uses `difflib.SequenceMatcher` for fuzzy name matching (threshold: 0.70)

### Matching Tiers:
| Tier | Confidence | Method |
|---|---|---|
| 1 | 100% | Exact License Number + Exact Store Name |
| 2 | 90% | Exact License Number + Fuzzy Store Name |
| 3 | 80% | Exact License Number only |
| 4 | 60% | Fuzzy Store Name only |
| 5 | 0% | No match (manual review) |

### Contact Selection Logic (within a match):
The `_select_primary_contact()` function (lines 210-257) selects ONE contact from multiple contacts for a retailer based on title relevance:

```
Priority order:
1. Contact with "(AP)" or "accounts payable" in poc_name/poc_title -> score 100
2. Contact with "accounting" or "invoic" in poc_name/poc_title -> score 90
3. Contact with "finance" or "billing" in poc_name/poc_title -> score 80
4. Contact with "owner" in poc_name/poc_title -> score 50
5. Contact with "manager" or "gm" in poc_name/poc_title -> score 40
6. Default (first listed) -> score 10
```

### What It Does NOT Do:
1. Does NOT query Notion API -- only reads from XLSX "Managers" sheet
2. Does NOT distinguish between Primary, Billing, and Associated contacts
3. Does NOT consider contact SOURCE (Nabis vs. Revelry vs. CRM)
4. Does NOT consult the Brand AR Summary XLSX
5. Does NOT send to BOTH primary and billing when both exist
6. Does NOT deprioritize Revelry-sourced contacts
7. Returns only ONE contact per match -- the meeting SOP requires potentially MULTIPLE recipients

### What It Does Well:
1. Robust fuzzy name matching with two-pass normalization
2. Handles edge cases (trailing punctuation, parenthesized locations, common articles)
3. Provides detailed audit trail (MatchResult with notes, confidence scores)
4. Group-by-location support for multi-invoice stores
5. Clean separation of concerns (matching vs. selection)

---

## Current data_loader.py Analysis

### Contact Data Source:
- Reads from the **"Managers" sheet** in the XLSX workbook
- Header columns mapped: `Retailer Name (DBA)`, `Account Manager`, `Account Manager Phone#`, `POC Name & Title`, `POC Email`, `POC Phone`

### Contact Parsing Logic:
1. **Multi-line POC Name & Title**: `_parse_poc_names()` splits on newlines, extracts name and title from patterns like `"Emily Stratakos (AP)"` or `"Jo-Anne Rainone - Accounting"`
2. **Multi-line POC Email**: `_parse_emails()` splits on newline/comma/semicolon, validates with basic `@` check, de-duplicates
3. **Primary Email Selection**: `_select_primary_email()` prefers addresses containing `ap@`, `accounting@`, `invoices@`, `billing@` prefixes
4. **Primary Contact Selection**: `_select_primary_contact()` prefers contacts with AP/Accounting/Finance/Billing titles

### Contact Object Structure:
```python
Contact(
    store_name="Aroma Farms",
    email="primary@email.com",           # Selected primary
    phone="Emily - (347) 217-9976",      # First phone
    contact_name="Emily Stratakos",      # Primary contact name
    role="AP",                           # Primary contact title
    all_emails=["email1@...", "email2@..."],  # ALL emails
    all_phones=["phone1", "phone2"],
    all_contacts=[{"name": "...", "title": "...", "full_name": "..."}],
    account_manager="Justin",
    account_manager_phone="(555) 555-5555"
)
```

### Contact Lookup:
- `_lookup_contact()` in data_loader.py: exact normalized match, then substring containment fallback
- `ContactResolver` in contact_resolver.py: more sophisticated 5-tier matching
- Both operate on the same underlying Managers sheet data

---

## Gap: Current vs Required

| # | Requirement (from meeting) | Current State | Gap | Fix Needed |
|---|---|---|---|---|
| 1 | Primary Contact from Notion first | Managers sheet only; selects by title relevance | NO Notion integration | Add Notion API query for store Primary Contact field |
| 2 | Billing/AP Contact second | Code prioritizes AP/billing titles but returns ONLY ONE contact | Returns single contact, not cascading chain | Change to return multiple recipients; send to both primary AND billing |
| 3 | Associated Contacts third (with source filtering) | No concept of "associated contacts" or source labels | No source-awareness at all | Parse Notion associated contacts with source label filtering |
| 4 | Nabis POC contacts "most reliable" | Brand AR Summary not loaded or consulted | Entirely missing data source | Add Brand AR Summary XLSX as supplemental contact source |
| 5 | Revelry contacts deprioritized | No source tracking | No source distinction | Filter/deprioritize contacts with "revelry" source label |
| 6 | Rep email dynamically CC'd | `{rep_email}` placeholder in TierConfig | Placeholder exists but resolution unclear | Resolve rep email from invoice `sales_rep` field -> lookup rep's email |
| 7 | CC list editable from UI | Hardcoded in TierConfig.default_tiers() | Not UI-editable; edit button non-functional | Wire up settings UI to allow CC/BCC editing and persistence |
| 8 | TO field editable from UI | Programmatically determined | Not UI-editable | Add editable TO field with save capability |
| 9 | Send to both primary AND billing when both exist | Only one contact returned | Single-contact architecture | Refactor to build multi-recipient TO list |
| 10 | Nabis AM group email as CC | Hardcoded as `ny.ar@nabis.com` | Correct but not validated against meeting | DONE - already correct |
| 11 | Martin/Mario/Laura always CC'd | Hardcoded in TierConfig | Correct but should be editable | Partially done - make configurable |
| 12 | 5 tiers in code vs 3 templates from meeting | Code has T0-T4 (5 tiers); meeting agreed on 3 templates | Tier count mismatch | Collapse T2/T3/T4 into single template with dynamic subject line |

---

## Revelry Contact Deprioritization

### What Was Said:
- **Bryce** (01:29:23): "If it says Navis import or Navis POC, that's probably pretty... highly regarded. And then, like, if it says revelry buyers list, that would probably be like a lower [reliability]."
- **Travis** (01:32:52): "Just trust all of them except revelry. Or don't trust revelry."
- **Bryce** (01:32:59): "Just don't trust revelry and just allow other sources basically."

### How to Implement:
1. When reading Associated Contacts from Notion, each contact has a source label
2. Create a source trust mapping:
   ```python
   SOURCE_TRUST = {
       "nabis import": "high",
       "nabis poc": "high",
       "crm contact": "high",
       "nabis order, point of contact": "high",
       "revelry buyers list": "low",
       "revelry": "low",
   }
   ```
3. When selecting from associated contacts:
   - Prefer "high" trust sources first
   - Only use "low" trust (revelry) if no other sources available
   - Flag revelry-only contacts for manual review in the UI
4. This filtering applies ONLY to associated contacts -- Primary and Billing contacts are always trusted regardless of source

---

## Bryce/Mary Consolidation Work

### What's Being Consolidated:
- **Bryce and Mary are working on consolidating contact data in Notion** (01:26:36)
- Travis: "I think they're working on consolidating this right now. I think that's something that Bryce and Mary, I might be working on right now, so I think it's just like a matter of time." (01:26:36)
- The problem: Many stores lack Primary Contact data. "A lot of them don't have primary contacts listed." (01:25:51)
- Contacts are scattered across multiple sources (Nabis exports, CRM, Revelry lists, manual entry)
- Bryce adds imported contacts as "Associated Contacts" with source labels
- He never overwrites the Primary Contact field: "I don't ever overwrite the primary contact field... those ones I don't ever automatically feel, because people, like, submit to put stuff in there." (01:27:44)

### Impact on the Tool:
1. **Short term**: The tool cannot rely on Primary Contacts being populated -- must be resilient to empty fields
2. **Medium term**: As Bryce/Mary consolidate, more Primary Contact fields will be filled in, improving automated matching
3. **The tool should be designed to work with partial data**: If Notion has no Primary, fall back to associated contacts or Brand AR Summary
4. **Callie will manually enter emails in the interim**: "We just manually put in the emails... that doesn't take too long because I just copy and paste the ones, you know, I find most appropriate." (01:34:01)

---

## Key Meeting Quotes on Contact Logic

### Contact Selection SOP:
> **Callie** (01:19:42): "I usually go into Notion, and I open up the store's main overview and I was just going off of the main contact that's listed there. The primary, I guess, the primary contact or the buyer. But there is lower down a billing or AP contact, which sometimes has someone in it."

> **Travis** (01:20:15): "What is our standard operating procedure for which ones are we -- is that what it is? What we're supposed to do, the main buyer contact and if there's an AR filled out in there?"

> **Callie** (01:20:29): "Yeah, typically I would send it to both."

### Nabis POC as Most Reliable:
> **Bryce** (01:29:23): "If it says Navis import or Navis POC, that's probably pretty... highly regarded."

> **Travis** (01:32:52): "Just trust all of them except revelry."

### CC Rules:
> **Travis** (01:34:50): "What emails are always included. So here's one note that I know. The rep email, we always include whoever the rep is."

> **Travis** (01:35:06): "The account, the Nabis account manager, is that always a CC?"

> **Callie** (01:35:49): "All of the Navis account managers use the same email. So it's always the same email." [ny.ar@nabis.com]

> **Callie** (01:37:15): "With what I've been doing, I've been CC'ing Martin, Mario, and Laura just to keep everybody on the same [page]."

### Brand AR Summary:
> **Mario** (01:23:51): "Before I forget, Mario didn't remind me that there's an outside... I a document that we can use to get this contact information also."

> **Callie** (01:24:17): "Is it the Navis? Is it what Navis sent us for their contact? Yes. The Brand AR Summary."

> **Callie** (01:24:56): "Yes. Yeah, it's their point of contact email."

### UI Requirements:
> **Travis** (01:38:00): "We have to have the ability to edit the people who are getting and receiving the email. You need to be editable from the actual interface. And every change that is made on this page needs to be able to be saved."

> **Joe** (01:38:30): "There is an edit button right now, but it is not functioning."

---

## Email Addresses Mentioned

| Address | Role | Where Used |
|---|---|---|
| `ny.ar@nabis.com` | Nabis AR group inbox | Always CC'd; routes to correct Nabis AM internally |
| `mario@piccplatform.com` | Mario (PICC leadership) | Always CC'd for visibility |
| `martinm@piccplatform.com` | Martin (PICC leadership) | Always CC'd for visibility |
| `laura@piccplatform.com` | Laura (PICC leadership) | Always CC'd for visibility |
| `{rep_email}` | Internal sales rep | Always CC'd; dynamic per account (e.g., Bryce, Ben) |
| Callie's PICC email | Sender | Used as FROM address currently |

---

## Account Manager (AM) Lookup

### How AM Lookup Should Work:

1. **Nabis Account Manager** (in email body): This is NOT the rep; it's from a separate Nabis-provided document. Currently pulled from an older static sheet. The "Brand AR Summary" XLSX does NOT contain AM names -- it contains POC contacts. The AM data comes from the Overdue sheet's "Account Manager" column.

2. **Sales Rep** (for CC): Comes from the Overdue sheet's "Rep" column (e.g., "Ben", "Bryce"). The system needs to map rep name -> rep email address for the CC field.

3. **Rep Email Resolution**: Not yet implemented. Need a lookup table:
   ```
   "Ben"   -> "ben@piccplatform.com"
   "Bryce" -> "bryce@piccplatform.com"
   ```
   This could come from:
   - Territory sheet in the XLSX
   - Hardcoded mapping (short term)
   - Notion API (long term)

---

## Suggested Agent Prompts for Wave 2 Contact Build

### Agent: Contact Resolver Refactor (Sonnet)
```
ROLE: Contact Resolver Engineer
OBJECTIVE: Refactor contact_resolver.py to implement the cascading contact selection SOP

INPUT:
- Report 05 (this file): Contact priority chain and rules
- Current contact_resolver.py code
- Current data_loader.py code
- Current models.py Contact/EmailDraft classes

DELIVERABLES:
1. New ContactResolutionResult dataclass with:
   - to_emails: list[str] (multiple recipients supported)
   - cc_emails: list[str] (always includes rep + ny.ar@nabis.com + leadership)
   - bcc_emails: list[str]
   - primary_contact_name: str (for email greeting)
   - resolution_chain: list[str] (audit trail of which sources were consulted)
   - confidence: float

2. Refactored resolve() method implementing:
   Priority 1: Primary Contact (if populated)
   Priority 2: Billing/AP Contact (ADD to TO, not replace)
   Priority 3: Associated Contacts (filter by source trust)
   Priority 4: Brand AR Summary POC Email (fallback)
   Priority 5: Manual review flag

3. Source trust filtering for associated contacts:
   - HIGH: "nabis import", "nabis poc", "crm contact"
   - LOW: "revelry", "revelry buyers list"
   - Skip LOW sources unless no HIGH sources available

4. CC builder that resolves {rep_email} from rep name lookup
```

### Agent: Brand AR Summary Loader (Sonnet)
```
ROLE: Data Integration Engineer
OBJECTIVE: Add Brand AR Summary XLSX as supplemental contact source

INPUT:
- Brand AR Summary XLSX schema (from Report 05)
- Current data_loader.py

DELIVERABLES:
1. New function: load_brand_ar_summary(path) -> dict[str, BrandARContact]
2. BrandARContact dataclass with: retailer_name, poc_emails, poc_phones, retailer_type, responsiveness, notes
3. Fuzzy name matching to link Brand AR retailers to invoice Locations
4. Integration point in the contact resolution chain as Priority 4 fallback
```

### Agent: Notion Contact API Bridge (Opus)
```
ROLE: API Integration Architect
OBJECTIVE: Design and implement Notion API integration for dynamic contact data

INPUT:
- Report 05 contact field structure in Notion
- Notion API credentials (need API key)

DELIVERABLES:
1. Notion API client for reading dispensary pages
2. Extract: Primary Contact, Billing Contact, Associated Contacts with source labels
3. Cache layer to avoid hitting Notion API per-email
4. Fallback to XLSX data when Notion is unavailable
```

### Agent: Rep Email Resolver (Haiku)
```
ROLE: Lookup Table Builder
OBJECTIVE: Create rep name -> email mapping for CC resolution

INPUT:
- Territory sheet from XLSX
- Known rep names from Overdue sheet Rep column

DELIVERABLES:
1. rep_email_map.json with name -> email mappings
2. Fuzzy name matching for rep name variations
3. Integration with CC builder
```

---

## Appendix: Brand AR Summary Sample Data

First 5 rows showing contact data structure:

| Retailer | POC Email | POC Phone | Retailer Type | Responsiveness |
|---|---|---|---|---|
| A Cannaful Life | Acannafullife@aol.com | Anthony - (718) 610-9739 | Good | Unresponsive |
| All Good Cannabis Dispensary | sageap@platformcanna.com, team@stayallgood.com | Sean (512) 298-9392 | Good | Semi-Responsive |
| Alto Dispensary | andre@altocanna.nyc, stephanie@altocanna.nyc, invoices@altocanna.nyc | Andre - (718) 541 9810 | Good | Responsive |
| Amped | chris.casacci@gmail.com | Christopher - (716) 984-6520 | Weak | Semi-Responsive |
| Aroma Farms | Aromafarmsinc@gmail.com (x2) | Emily- (347) 217-9976, Lakisha - (516) 369-7415 | Good | Responsive |

Note: POC Email can contain multiple newline-delimited addresses. POC Phone follows "Name - (xxx) xxx-xxxx" format.
