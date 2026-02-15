# Workflow Analyst Report
## Report: 01 - Callie's AR Email Workflow
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 1 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (full ~1:44:00 meeting transcript, all 1841 subtitle entries)
- `A:\Downloads\Action items.md` (meeting summary and action items)
- `A:\Downloads\picc Mail - A_R Email Formatting.pdf` (Callie's 3 canonical email templates, sent Feb 10 2026)
- `A:\Downloads\picc Mail - RE_ 1-29 Day Email Body fix.pdf` (corrected 1-29 day template, sent Feb 11 2026)

## Verdict: Callie manually builds AR collection emails weekly by downloading a Google Sheets export, looking up recipient contacts in Notion one-by-one, selecting the correct template from 3 tiers, filling in variable fields by hand, and scheduling sends for 7 AM PT (10 AM ET). The process is ripe for automation -- the body construction, data lookup, and recipient resolution are all mechanizable, with human review/approval as the final gate.

---

## Executive Summary

Callie Speerstra (New York Sales Admin, PICC Platform) is responsible for sending accounts receivable (AR) reminder emails to dispensary customers weekly. She downloads the "NY Accounts Receivable Overdue" Google Sheet, manually determines which stores need emails, selects from 3 email templates based on days past due, looks up recipient email addresses in Notion (following a primary > billing > associate contact hierarchy), fills in dynamic variables (invoice number, due date, amount, Nabis account manager), and schedule-sends all emails for 7 AM Pacific / 10 AM Eastern. The meeting (Feb 10, 2026) with Travis, Joe, and Callie reviewed a prototype automation tool (Streamlit-based) that Joe built, identified discrepancies between the AI-generated output and the canonical templates, and established a parallel testing plan where Callie continues manual sends while Joe iterates on the automated version.

## Step-by-Step Workflow (As Callie Does It Today)

| Step | Action | Data Source | Can Automate? |
|------|--------|-------------|---------------|
| 1 | Download the "NY Accounts Receivable Overdue" Google Sheet | Google Sheets (auto-updated daily via Nabis API sync through Justin's pipeline) | YES - API read directly from Google Sheets |
| 2 | Open the downloaded XLS/CSV file | Local download | YES - eliminated if reading from API |
| 3 | Review each store's days past due to categorize into tiers | Column in AR spreadsheet | YES - simple date math |
| 4 | Determine which template to use based on days past due tier | Mental decision based on 3-tier rules | YES - rule-based logic |
| 5 | Open Notion dispensary master list for each store | Notion database | YES - Notion API |
| 6 | Look up primary contact email for the store | Notion: Primary Contact field | YES - Notion API pull |
| 7 | If no primary contact, check billing/AP contact | Notion: Billing Contact field | YES - fallback logic |
| 8 | If no billing contact, check associated contacts (prefer Nabis POC source) | Notion: Associated Contacts field | PARTIAL - requires source-label filtering |
| 9 | Look up the PICC rep assigned to the store | AR spreadsheet / Notion | YES - from sheet data |
| 10 | Look up Nabis Account Manager name and phone for the store | Separate reference sheet (static, from Nabis); also present on the AR export sheet itself | YES - static lookup table |
| 11 | Copy the appropriate email template from Notion | Notion page | YES - hardcoded templates |
| 12 | Fill in all bracketed variables: [Dispensary Name], [Invoice Number], [Date Due], [Amount], [Nabis Account Manager Name - Phone], [person/s] | AR spreadsheet + Nabis account manager sheet | YES - template variable substitution |
| 13 | Construct subject line with dynamic days-past-due tier | Mental formatting | YES - string formatting |
| 14 | Set TO recipients: store contacts (primary + billing if available) | Notion lookup result | YES - once contact resolution is automated |
| 15 | Set CC recipients: PICC rep for that store, ny.ar@nabis (Nabis group AR email), Martin, Mario, Laura | Static + per-store rep | YES - rep from data, rest static |
| 16 | Review the composed email for accuracy | Manual visual check | PARTIAL - human approval step should remain |
| 17 | Schedule-send for 7:00 AM Pacific Time (10:00 AM Eastern) | Gmail scheduled send | YES - Gmail API scheduled send |
| 18 | Attach Nabis ACH payment form PDF | Static PDF attachment | YES - same attachment every time |
| 19 | After sending, add notes/status to the AR spreadsheet for tracking | Google Sheet (her working copy) | PARTIAL - could auto-log send status |
| 20 | Archive the current week's working copy for records | Manual file management | YES - automatic archiving |

## The Three Email Templates (Canonical, from Callie's Feb 10 + Feb 11 emails)

### Template 1: PICC A/R Payment Coming Due Reminder
- **Tier**: -7 to 0 days (coming due, not yet past due)
- **Subject**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Coming Due`
- **Body opening**: "I hope you're well. This is a courtesy reminder that your payment is due soon."
- **Body data block**: Invoice/Order, Due Date, Amount, Nabis Account Manager
- **Body closing**: Mentions attached ACH form, commitment to service, thank you
- **Tone**: Courteous, gentle reminder

### Template 2: PICC A/R Payment 1-29 Days Past Due
- **Tier**: 1 to 29 days past due
- **Subject**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Overdue`
- **Body opening**: "I hope you're having a great day."
- **Body text**: ~~"nearing two weeks past due"~~ CORRECTED to "invoice is overdue" (per Feb 11 fix email)
- **Body data block**: Invoice/Order, Due Date, Amount, Nabis Account Manager
- **Body closing**: Mentions attached ACH form, "please let us know if there's anything we can do to assist you"
- **Tone**: Friendly but direct

### Template 3: PICC A/R Payment 30+ Days Past Due
- **Tier**: 30+ days past due (same template for 30, 40, 50+ days)
- **Subject**: `PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - [X]0+ Days Past Due` (dynamic: 30+, 40+, 50+ etc.)
- **Body opening**: "I hope this message finds you well. I am with PICC Platform..."
- **Body text**: References Nabis OCM reporting policy -- notifications at 45 days, OCM reporting at 52 days
- **Body data block**: Invoice/Order, Due Date, Nabis Account Manager, Amount
- **Body closing**: Mentions attached ACH form, understanding tone, recommends adhering to timeline to avoid OCM reporting, values partnership
- **Tone**: Serious, mentions regulatory consequences but not threatening. NO "final notice" language ever.
- **Special**: For 30+ day emails, include dynamic urgency line: "We request that payment be submitted by [X date] to avoid account restrictions or OCM reporting"

### Variable Fields Across All Templates (in brackets)
- `[Dispensary Name (Location-if multiple)]` - store name, with location qualifier if chain
- `[Invoice Number]` - from AR spreadsheet
- `[Date Due]` - from AR spreadsheet
- `[Amount]` - from AR spreadsheet
- `[Name - Phone]` - Nabis Account Manager name and phone (from reference sheet)
- `[person/s]` - recipient name(s) for greeting

## Pain Points Identified

- **Manual contact lookup is the biggest time sink**: Callie must open each store in Notion, scroll to find primary contact, check billing, check associates. Many stores lack primary contacts entirely.
- **Contact data is fragmented**: Primary contacts are manually entered, associated contacts come from various sources (Nabis import, CRM, Revelry buyers list) with varying reliability. Bryce/Mary are working on consolidation but it is incomplete.
- **Template drift from AI learning**: When Joe fed historical emails to the AI, it created 5 tiers instead of 3 and altered wording by learning from slight variations in past emails. The AI added "final notice" language that was never authorized.
- **No editable UI for templates**: The prototype tool has templates hardcoded in the backend, not editable through the UI.
- **No save functionality**: Settings changes in the prototype are lost on regeneration.
- **Scheduling not built yet**: The tool cannot schedule-send; Callie needs schedule-send for 7 AM PT.
- **Manual download step**: Callie must download the AR Google Sheet manually and upload it to the tool, rather than the tool reading from the sheet directly.
- **Inconsistent Notion data**: The "overdue" label in Notion did not match the agreed tier names, causing confusion.
- **Wording inconsistency**: The 1-29 day template said "nearing two weeks past due" which is inaccurate for invoices that could be 1 day or 29 days overdue. Callie corrected this on Feb 11.

## Automation Opportunities

### Immediate (V1 - Save Callie time now)
1. **Template-based email body generation**: Hardcode 3 templates, auto-fill all bracketed variables from spreadsheet data
2. **Tier assignment**: Auto-categorize each store into Coming Due / 1-29 Days / 30+ Days based on days past due column
3. **Subject line generation**: Dynamic subject line with tiered days past due
4. **Nabis Account Manager lookup**: Auto-fill from the reference sheet (static, rarely changes)
5. **CC auto-population**: Always include rep email, ny.ar@nabis, Martin, Mario, Laura
6. **Batch preview with approve/reject**: Let Callie review all emails before sending

### Near-term (V2 - Full automation)
7. **Direct Google Sheets API read**: Eliminate the download/upload step entirely
8. **Notion API contact resolution**: Auto-lookup primary > billing > associate contacts with source-priority logic (Nabis POC > CRM > Revelry)
9. **Gmail scheduled send**: Push approved emails into Gmail's scheduled-send queue for 7 AM PT
10. **App-specific password integration**: Enable sending from Callie's PICC email via Gmail API

### Future (V3 - Intelligence layer)
11. **Auto-attach ACH PDF**: Attach the Nabis ACH payment form to every email
12. **Send history tracking**: Log which stores received emails and when
13. **Chronic offender flagging**: Tag stores that are repeatedly 50+ days late
14. **Integration with PICC Platform intranet**: Make AR email tool a module in the intranet alongside the proposal generator

## Schedule & Timing

- **When emails are prepared**: Callie works on building AR emails during her workday (Pacific Time)
- **When emails are sent**: Schedule-sent for **7:00 AM Pacific Time** (10:00 AM Eastern Time)
- **Why 7 AM PT**: So that emails land in recipients' inboxes at 10 AM Eastern (New York business hours opening)
- **Frequency**: Weekly. Callie downloads the updated AR sheet, builds emails, sends them out. The AR sheet auto-updates daily via the Nabis API sync.
- **Typical workflow day**: First thing she does is send out emails, then uses the same spreadsheet throughout the week for tracking/notes. The clean sheet is always available at the start before she adds notes.
- **Schedule-send mechanism**: Currently uses Gmail's built-in schedule-send. The tool needs to replicate this.

## Team Roles

| Person | Role | AR Email Involvement |
|--------|------|---------------------|
| **Callie (Kali Speerstra)** | NY Sales Admin | Primary operator -- builds, reviews, and sends all AR emails. Uses her PICC email (kali@piccplatform.com) as sender. Maintains templates in Notion. |
| **Travis** | Management/Operations Lead | Oversees the AR process, drives the automation initiative, ensures templates and procedures are correct. Bridges between Callie's operational knowledge and Joe's technical implementation. |
| **Joe (Joe Smith)** | Developer | Built the AR email automation prototype (Streamlit app). Manages the Nabis API sync, Google Sheets data pipeline, and will integrate Notion API for contact lookup. |
| **Justin** | Data/API Engineer | Manages the Nabis-to-Google-Sheets sync pipeline. The orders and details tabs that feed the Sync Master Sales Sheet are his work. Not directly involved in email sending. |
| **Martin** | Management | CC'd on all AR emails for visibility. Careful about wording (no "final notice" language). Helped develop the OCM warning verbiage with Callie. |
| **Mario** | Management | CC'd on all AR emails for visibility. Reminded the team about an external Nabis Brand AR Summary document for contact information. |
| **Laura** | Management | CC'd on all AR emails for visibility. Originally trained Callie on the AR process. Previously the sender of AR emails before Callie took over. Showed Callie how to use the Balances export from Nabis. |
| **Bryce/Mary** | Data/CRM | Working on consolidating contact data in Notion. Bryce manages the dispensary master list and associated contacts, importing from Nabis, CRM, and other sources. Does not overwrite primary contacts. |

## Data Sources Map

| Data Point | Source | How Accessed | Update Frequency |
|-----------|--------|-------------|-----------------|
| Store names, invoice numbers, due dates, amounts, days past due | NY Accounts Receivable Overdue Google Sheet | Manual download (currently) | Daily (auto-synced from Nabis API via Justin's pipeline) |
| Nabis Account Manager name & phone | Separate reference sheet from Nabis | Static file uploaded to tool | Rarely changes; updated every 1-2 months |
| Primary contact email | Notion dispensary master list | Manual lookup per store | Manually maintained by reps |
| Billing/AP contact email | Notion dispensary master list | Manual lookup per store | Manually maintained |
| Associated contacts | Notion dispensary master list | Manual lookup per store | Auto-imported by Bryce from Nabis, CRM, Revelry |
| PICC rep assignment | AR spreadsheet (rep column) | From sheet data | Updated with orders |
| Nabis POC contacts for stores | Nabis Brand AR Summary document | Separate document from Nabis | Nabis-provided |
| Credit status | Orders data in Sync Master Sales Sheet | Derived from order status + date math | Daily sync |

## Contact Resolution Logic (SOP)

Callie's standard operating procedure for determining who to email, in priority order:

1. **Primary Contact** (Notion > dispensary page > Primary Contact field) -- always include if available
2. **Billing/AP Contact** (Notion > dispensary page > Billing Contact field) -- always include if available
3. **Associated Contacts** (Notion > dispensary page > Associated Contacts) -- use as fallback if no primary/billing, with source priority:
   - **Highest trust**: Nabis Import, Nabis POC (labeled in Notion)
   - **Medium trust**: CRM contacts
   - **Lowest trust**: Revelry Buyers List (deprioritize)
4. **If none found**: Callie manually researches or skips (edge case)

**CC recipients (always included)**:
- The PICC rep assigned to the account (e.g., Bryce's email)
- ny.ar@nabis (Nabis group AR email -- routes to the correct Nabis account manager internally)
- Martin (CC for visibility)
- Mario (CC for visibility)
- Laura (CC for visibility)

## Key Meeting Quotes

> **Travis** (00:04:11): "I'm gonna let you guys take it over a little bit. Let me just give you an overview of what I think. Because I want to make sure that the logic that you had this AR done, Joe, is correct."

> **Joe** (00:07:59): "You go over here to browse files and, first thing you do is you go to the NY Accounts Receivable Overdue Google Sheet, and you download it to your computer, and then you go to Browse Files... click on that, and then it will show up right here."

> **Travis** (00:09:14): "We usually do a schedule send on the emails. Can you do the same thing through here?"

> **Travis** (00:09:32): "Usually what she does is she checks them, because we're on Pacific time, and then she schedules sends it for early in the morning, like at 7, so that it populates everybody at 10 a.m. in New York time."

> **Callie** (00:20:06): "The coming due, we were doing anything that was negative... but we only wanted it to read negative seven."

> **Travis** (00:24:44): "Let's change the overdue to 1-29 days... we should just call them all the same. Coming due, 1-29 days past due, 30-plus days past due."

> **Callie** (00:25:08): "We would use the same body [for 30+ days], and nothing in the body really relates to the amount of days. So we would use the same body but change the subject line to match 30, 40, or 50."

> **Callie** (00:29:45): "Inside it says invoice number or due date or... it's in brackets."

> **Callie** (00:30:14): "It says NABIS account manager and then we have name and phone in brackets."

> **Joe** (00:36:23): "It read the database and it made five tiers, either that or something about the ways you guys were sending emails at some point was slightly different... and it read that as an actual thing that I have to do."

> **Travis** (00:55:00): "No final notice shit... remove 'this is a final notice' from all email bodies because we're always just going to keep sending them until the sun burns out."

> **Joe** (01:02:30): "Navis is all being pulled from the API, which was the... I modeled after the reports that were being used."

> **Callie** (01:07:37): "You go to balances, and then you filter -- only show delivered and delivered with edits -- and there's a button that emails you a CSV."

> **Travis** (01:18:02): "Here's her order of operations. The first thing she does is send out emails. So she runs the report. We get that sheet. Nothing's filled out. Because those are notes as she's tracking it down."

> **Callie** (01:19:55): "I usually go into Notion, and I open up the store's main overview and I was just going off of the main contact that's listed there. The primary contact or the buyer. But there is lower down a billing or AP contact."

> **Callie** (01:20:29): "Yeah, typically I would send it to both [primary and billing]."

> **Bryce** (01:28:28): "If it says Navis import or Navis POC, that's probably pretty highly regarded, and then like if it says Revelry buyers list, that would probably be like a lower [trust]."

> **Callie** (01:35:06): "With what I've been doing, I've been CC'ing Martin, Mario, and Laura just to keep everybody on the same [page]."

> **Joe** (01:35:29): "It just has Martin, Mario, and Laura on the automatic send... but we can make this dynamic in the future because these are just always CC recipients."

> **Callie** (01:35:23): "We always CC the Nabis account manager... and we email it to the ny.accounts [ny.ar@nabis] email -- their system will automatically send it to the correct manager."

> **Travis** (01:40:57): "This is pretty amazing. For it to pump this out and you building your box to get it this far... it's absolutely, with the limited that we gave you and direction, that's pretty frickin' amazing."

> **Joe** (01:40:25): "It got us like 90, 95% of the way there basically, we just needed to clean up these little data points."

## Nabis Data Relationship

The Nabis ERP system is the ultimate source of truth for AR data:

1. **Nabis API** syncs order data to Google Sheets via Justin's pipeline (orders + details tabs)
2. The **Sync Master Sales Sheet** is the central Google Sheet that auto-updates from these synced tabs
3. The **NY Accounts Receivable Overdue** sheet is either part of or derived from this sync
4. **However**: The specific AR/Balances export from Nabis is currently done manually (Callie goes to Balances in Nabis, filters for "delivered" and "delivered with edits," clicks to email herself a CSV)
5. **Open question**: Can the AR fields be sourced from the already-syncing orders/details tabs instead of requiring the separate Balances export? Justin was to check this the morning after the meeting.
6. The **Nabis Account Manager** data comes from a separate static sheet that Nabis provided -- it maps each store to its Nabis account manager name and phone number. This is on the AR export sheet itself (already solved).

## Prototype Tool Status (Joe's Streamlit App)

| Feature | Status | Notes |
|---------|--------|-------|
| File upload (browse for XLS) | Working | User downloads AR sheet, uploads to tool |
| Email generation from templates | Working (90-95%) | Templates had drifted from canonical versions |
| Email preview | Working | Shows Gmail-formatted preview |
| Approve/reject per email | Working | Can exclude stores from batch |
| Invoice detail tab | Working | Shows underlying data for verification |
| Auto-CC recipients | Working | Martin, Mario, Laura hardcoded |
| Template editing UI | NOT BUILT | Templates sealed in backend code |
| Save button for settings | NOT BUILT | Settings revert on regeneration |
| Tier boundary editing | Partially working | UI exists but doesn't persist |
| Scheduled send | NOT BUILT | Needs Gmail API integration |
| Recipient editing (TO/CC/BCC) | NOT BUILT | Edit button exists but non-functional |
| Notion API for contacts | NOT BUILT | Requires API key setup |
| Direct Google Sheets reading | NOT BUILT | Still requires manual download/upload |
| Cloud hosting | JUST DEPLOYED | Pushed to Streamlit cloud during meeting |

## Suggested Agent Prompts for Wave 1+

### Suggested: Template Engine Builder (Wave 1)
```
ROLE: Email Template Engine Developer
OBJECTIVE: Build the email template rendering engine that takes AR spreadsheet data and produces
fully-formed HTML emails using the 3 canonical templates.

INPUT:
- The 3 canonical templates (exact text from 01_workflow_analyst.md)
- AR spreadsheet schema (columns: store name, invoice number, due date, amount, days past due, rep, etc.)
- Nabis Account Manager lookup table

REQUIREMENTS:
1. Implement 3-tier classification: Coming Due (-7 to 0), 1-29 Days Past Due (1-29), 30+ Days Past Due (30+)
2. For 30+ tier, generate dynamic subject line: "30+ Days Past Due", "40+ Days Past Due", "50+ Days Past Due" etc.
3. Never use the words "final notice" anywhere
4. All bracketed variables must be replaced with actual data
5. Subject line format: PICC - [Store Name (Location)] - Nabis Invoice [#] - [Tier Label]
6. For 1-29 day template, use corrected wording: "invoice is overdue" (NOT "nearing two weeks past due")
7. For 30+ day template, include dynamic urgency line with calculated date
8. Output: list of {to, cc, bcc, subject, html_body, store_name, tier} objects
```

### Suggested: Contact Resolution Agent (Wave 1)
```
ROLE: Contact Resolution Engine Developer
OBJECTIVE: Build the recipient resolution logic that determines TO/CC/BCC for each AR email.

CONTACT RESOLUTION PRIORITY (for TO field):
1. Primary Contact (from Notion dispensary page)
2. Billing/AP Contact (from Notion dispensary page)
3. Associated Contacts filtered by source: Nabis Import/POC > CRM > Other (exclude Revelry)

CC RECIPIENTS (always):
- PICC rep assigned to account (from AR spreadsheet)
- ny.ar@nabis (static Nabis group email)
- Martin (static)
- Mario (static)
- Laura (static)

DATA SOURCES:
- Notion API (dispensary master list database)
- AR spreadsheet (rep assignment)
- Nabis Brand AR Summary (supplemental contact data)
```

### Suggested: Gmail Integration Agent (Wave 2)
```
ROLE: Gmail Scheduled Send Integration Developer
OBJECTIVE: Build the Gmail API integration that takes approved emails and pushes them into
Gmail's scheduled-send queue for 7:00 AM Pacific Time.

REQUIREMENTS:
1. Use Gmail API with app-specific password authentication
2. Send from Callie's PICC email (kali@piccplatform.com) initially
3. Future: support sending from a shared accounts-receivable@piccplatform.com email
4. All emails scheduled for 7:00 AM Pacific (10:00 AM Eastern)
5. Attach Nabis ACH payment form PDF to every email
6. Log send status for each email (sent, failed, scheduled time)
7. Support the approve/reject workflow -- only send approved emails
```

### Suggested: Data Pipeline Agent (Wave 2)
```
ROLE: AR Data Pipeline Developer
OBJECTIVE: Eliminate the manual download/upload step by reading AR data directly from Google Sheets API.

REQUIREMENTS:
1. Connect to the NY Accounts Receivable Overdue Google Sheet via API
2. Read-only access (never write to the source sheet)
3. Handle the Nabis Account Manager lookup (static reference sheet or from the AR sheet itself)
4. Provide data freshness indicator (last sync time)
5. Fall back to manual upload if API is unavailable
6. Investigate whether AR fields can be derived from the already-syncing orders/details tabs
   (eliminating need for separate Balances export from Nabis)
```
