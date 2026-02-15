# UX Requirements Analyst Report
## Report: 04 - UI/UX Requirements Specification
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 4 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (full meeting transcript, ~1841 subtitle blocks, ~1h44m)
- `A:\Downloads\Action items.md` (meeting summary and action items)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\app.py` (2070 lines, full Streamlit application)
## Verdict: The app is ~90-95% functionally complete but has critical UX gaps: the edit button is non-functional, settings do not persist, the "Use Default File" checkbox is confusing, no scheduler exists, templates are sealed in code, and labels are text inputs rather than dropdowns. The meeting identified a clear "zero thinking required" user flow that must be realized through targeted UI fixes.

---

## Executive Summary

The AR Email Automation tool built on Streamlit is a working prototype that generates, previews, and can send AR collection emails via Gmail SMTP. During the meeting, Travis (manager), Callie (end user / AR admin), and Joe (developer) walked through the demo, identified discrepancies between what the AI generated and what Callie actually uses, and defined concrete UI requirements. The tool is approximately 90-95% of the way there (Travis's words: "it got us like 90, 95% of the way there"), but needs targeted fixes around editability, persistence, scheduling, template management, and cloud deployment before it can replace Callie's manual workflow.

---

## Feature Requests (from meeting)

| # | Feature | Priority | Currently Exists? | Meeting Quote/Context |
|---|---------|----------|-------------------|----------------------|
| 1 | **Editable TO/CC/BCC fields** | CRITICAL | Edit button exists but is non-functional (line ~1379 in app.py has edit mode code, but Travis confirmed "there is an edit button right now but it is not functioning") | Travis at 01:38:01: "We have to have the ability to edit the people who are getting and receiving the email... needs to be editable from the actual interface" |
| 2 | **Save button for settings** | CRITICAL | No save button; settings revert on re-generate | Joe at 00:38:02: "There's no save button here. That's why it didn't save that when I said that" |
| 3 | **Schedule send with time picker** | HIGH | Not implemented | Travis at 00:09:14: "We usually do a schedule send on the emails. Can you do the same thing through here?" Callie schedules for 7am Pacific / 10am Eastern |
| 4 | **Template editing in the UI** | HIGH | Templates are "sealed" in code, not exposed to users | Joe at 00:35:41: "The templates are sealed somewhere, so they are not actually modifiable yet" |
| 5 | **Remove "Use Default File" checkbox** | MEDIUM | Exists as `st.checkbox("Use default file")` on sidebar line ~849 | Joe at 00:08:21: "Click Off Default File. I have to figure out what the heck that even means. That's a weird button that was for the demo" |
| 6 | **Labels as dropdowns instead of text inputs** | MEDIUM | Currently text inputs in Settings for tier boundaries | Travis at 00:33:40: "Will those labels, do we have to write them out or are they gonna be like a drop down or something?" Joe: "Once this is properly set up... I'll probably just be dropdowns and stuff" |
| 7 | **Remove extra tiers (40+, 50+ days)** | HIGH | Five tiers exist in code (TIER_COLORS dict has Coming Due, Overdue, 30+, 40+, 50+) | Travis at 00:32:51: "Can we delete these labels, like the 40 days, just so it doesn't get confusing?" |
| 8 | **Consolidate to exactly 3 templates** | HIGH | AI generated 5 tiers from training data | Travis at 00:27:56: "You have basically three templates, right? Coming due, 1 to 29 days past due, and 30 plus days past due" |
| 9 | **Dynamic subject lines** | HIGH | Partially implemented | Travis at 00:57:18: "What we want in the subject line is that to be dynamic... the days past due" -- keep tiered system (30+, 40+, 50+) in subject only |
| 10 | **Remove "final notice" from all email bodies** | HIGH | AI added "final notice" language from training data | Travis at 00:54:59: "No final notice shit" / "Remove final notice from all email bodies" |
| 11 | **Dynamic "pay by X date" warning on 30+ day emails** | MEDIUM | Only on 40+ and 50+ currently | Travis at 00:51:20: "I want to be putting that on all the 30 plus emails" -- the red bar with "We request payment be submitted by [date] to avoid account restrictions or OCM reporting" |
| 12 | **Cloud deployment / web-accessible URL** | HIGH | Was running locally during demo; pushed to Streamlit Cloud mid-meeting | Joe at 00:14:29: "Currently it is being hosted off of my computer. It will be moved into the cloud in the coming day or two" |
| 13 | **Integration into PICC intranet** | LOW (future) | Not started | Joe at 00:42:38: "My actual goal... is to make this as part of the intranet eventually, so that you would just be able to log in there and right under the proposal generator would be the account receivables emails" |
| 14 | **Rep email as CC per-account** | MEDIUM | Static CC list currently | Travis at 01:34:53: "The rep email, we always include whoever the rep is. From our side, Joe" |
| 15 | **Nabis group email (ny.ar@nabis.com) always CC'd** | LOW (already done) | Already in CC list | Callie at 01:35:06: "We always CC the Nabis account manager" -- confirmed it goes to ny.ar@nabis.com which auto-routes |

---

## UI Issues Identified During Demo

| # | Issue | Severity | Meeting Context |
|---|-------|----------|-----------------|
| 1 | **Edit button present but non-functional** | CRITICAL | Travis at 01:38:06: "There is an edit button right now, but it is not functioning, so once we just plug in the edit button to work, it should be good to go" |
| 2 | **Settings don't persist / no save button** | CRITICAL | Changes to tier boundaries reverted when Generate Emails was clicked. Joe at 00:38:02: "There's no save button here" |
| 3 | **"Use Default File" checkbox confusing** | MODERATE | Callie did not understand what it meant. Joe acknowledged it was "a weird button that was for the demo" |
| 4 | **App not accessible from the internet initially** | MODERATE | Callie could not reach the page. Joe: "I thought you could just access it through the internet... you cannot, cause it's a little bit too complicated, apparently" -- fixed mid-call by pushing to Streamlit Cloud |
| 5 | **AI-generated extra tiers (40+, 50+) confusing** | MODERATE | The AI created 5 tiers by learning from historical email variations. Travis: "How do we get those labels all off of the programming?" |
| 6 | **Template text drifted from canonical versions** | MODERATE | AI used training data to modify wording. Joe at 00:49:43: "These have drifted slightly from original templates because it went through the training data of all the emails" |
| 7 | **"Final notice" language incorrectly added** | HIGH | AI added "final notice" wording that was never sanctioned. Travis: "I don't think we ever said final notice. Martin's really careful on his wording" |
| 8 | **Nabis Account Manager showing wrong name (Mario)** | MODERATE | Callie: "I just don't know why it says Mario" -- the AM lookup was using historical email data rather than the static reference sheet |
| 9 | **Email preview stretched on wide monitors** | LOW | Joe: "That was just because I have a very wide monitor, so everything looks gigantic" -- but it does scale dynamically |
| 10 | **CC recipients not editable from the preview page** | HIGH | Travis at 01:36:32: "I have to add that in so you can edit the CC recipients because it is not editable quite" |

---

## Ideal User Flow (from Callie's description)

The meeting established this as the target "zero thinking required" workflow:

```
1. [MORNING] Callie checks metrics / AR data
   - Google Sheet (NY Account Receivables Overdue) auto-updates overnight via API sync

2. [DOWNLOAD] Download AR spreadsheet
   - Go to the Google Sheet
   - Download as XLSX to local machine

3. [UPLOAD] Upload to AR Email Tool
   - Open the PICC AR Email Automation web app (cloud-hosted URL)
   - Click "Browse Files" in sidebar
   - Select the just-downloaded XLSX from Downloads folder
   - Enter sender email (Callie's PICC email)

4. [GENERATE] Click "Generate Emails"
   - Tool parses XLSX, classifies invoices into 3 tiers
   - Generates email drafts using canonical templates
   - Fills in all dynamic variables (store name, invoice #, due date, amount, Nabis AM)
   - Displays queue sorted by urgency (worst overdue first)

5. [REVIEW] Review each email
   - Click "Preview" on each email in the queue
   - Verify TO address is correct (currently manual: check Notion for primary/billing/associate contact)
   - Verify CC includes rep, ny.ar@nabis.com, and internal stakeholders
   - Check body content matches expectations
   - Approve or Reject each email

6. [EDIT if needed] Fix any issues
   - Edit TO/CC/BCC fields directly in the interface
   - Save changes

7. [SCHEDULE] Schedule send
   - Set send time (e.g., 7:00 AM Pacific = 10:00 AM Eastern)
   - Emails get queued into Gmail's scheduled send

8. [SEND] Emails go out automatically at scheduled time
   - All approved emails sent via Gmail SMTP
   - Nabis ACH Payment Form PDF attached automatically

9. [ARCHIVE] Callie's manual sends are archived for QA comparison
```

### Order of Operations (from Travis at 01:18:02):
> "Here's her order of operations. The first thing she does is send out emails. So she runs the report, we get that sheet... nothing's filled out because those are notes as she's tracking it down. She'll just upload it. Because her first step is to get all the email sent out."

This means the XLSX will always be clean (no manual notes) when uploaded, since Callie adds notes AFTER sending emails.

---

## Cloud Access & Sharing Requirements

### Current State
- App was initially hosted on Joe's local machine with a tunnel/port forward attempt that did not work for Callie
- Mid-meeting, Joe pushed to **Streamlit Cloud** (free hosting) which made it accessible
- Travis mentioned making a **GitHub/Bitbucket repo** for the code

### Future State (discussed)
- **PICC Platform Intranet integration**: Joe at 00:42:38: "My actual goal is to make this as part of the intranet eventually, so that you would just be able to log in there and right under the proposal generator would be the account receivables emails"
- This means the AR email tool should eventually be a page/section within the PICC Platform intranet (which already has a proposal generator)
- **No authentication discussed** -- currently the Streamlit Cloud app is open (no login)
- **No mobile requirements discussed** -- Callie works from a desktop/laptop

### Deployment Requirements
1. Must be accessible via a stable URL (not Joe's local machine)
2. Streamlit Cloud is acceptable for now
3. Eventually integrate into PICC Platform intranet
4. Should support multiple users (at minimum Callie, potentially Laura)

---

## Current UI State (from app.py analysis)

### Page Structure

The app has a **sidebar + main content** layout with 5 pages routed via `st.session_state.page`:

| Page Key | Page Name | Render Function | Description |
|----------|-----------|-----------------|-------------|
| `"queue"` | Email Queue | `render_queue_page()` | Main page: displays generated emails in a table with approve/reject/preview actions |
| `"preview"` | Email Preview | `render_preview_page()` | Detail view of a single email with headers, body preview in iframe, and edit mode |
| `"history"` | History | `render_history_page()` | Shows previously exported/sent emails with CSV download |
| `"dnc"` | Do Not Contact | `render_dnc_page()` | Manage stores excluded from AR outreach |
| `"settings"` | Settings | `render_settings_page()` | Sender config, CC rules, tier boundaries, Gmail SMTP setup |

**Navigation**: Sidebar buttons switch between pages. No URL routing (single Streamlit app).

### Session State Keys

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `queue` | `EmailQueue \| None` | `None` | The main data structure holding all email drafts |
| `load_result` | `LoadResult \| None` | `None` | Raw result from XLSX parsing |
| `selected_email_idx` | `int \| None` | `None` | Index of email being previewed |
| `page` | `str` | `"queue"` | Current page routing key |
| `filter_tiers` | `list` | `[]` | Active tier filter selections |
| `filter_status` | `list` | `[]` | Active status filter selections |
| `generated` | `bool` | `False` | Whether emails have been generated this session |
| `do_not_contact` | `list` | `[]` | Store names to exclude from email generation |
| `history` | `list` | `[]` | List of exported/sent email records (dicts) |
| `upload_key` | `int` | `0` | Key for file uploader widget (for resetting) |
| `gmail_app_password` | `str` | `""` | Gmail App Password for SMTP |
| `sender_email` | `str` | `"laura@piccplatform.com"` | Sender email address |
| `sender_name` | `str` | `""` | Sender display name (empty = "PICC Accounts Receivable") |
| `smtp_configured` | `bool` | `False` | Whether SMTP credentials have been tested |
| `send_results` | `list` | `[]` | Results from last send batch |
| `editing_{idx}` | `bool` | `False` (dynamic) | Per-email edit mode flag |

### Settings Page Implementation

The Settings page (`render_settings_page()`, lines 1828-2028) contains:

1. **Sender Configuration**: Two-column layout with:
   - Sender Name (text input, synced with session state)
   - Sender Email (text input, synced with session state)
   - Sender Title (text input, reads from config)
   - Company (text input, reads from config)

2. **Always CC Recipients**: Text area with one email per line. Default: ny.ar@nabis.com, martinm@piccplatform.com, mario@piccplatform.com, laura@piccplatform.com

3. **Tier Boundaries**: For each tier in config, shows:
   - Tier name (disabled text input)
   - Min Days (number input)
   - Max Days (number input)
   - Label (text input)
   - **PROBLEM**: These are text/number inputs, NOT dropdowns as requested. Changes are not persisted (no save button).

4. **Gmail SMTP Configuration**:
   - App Password input (password field)
   - Test Connection button
   - Instructions expander for generating App Password
   - Status indicator

5. **System Modules**: Shows availability of each backend module (models, config, data_loader, tier_classifier, contact_resolver, template_engine)

**Critical gap**: There is NO save/apply button on the Settings page. Changes to CC list, tier boundaries, and other settings are lost when the page refreshes or emails are regenerated.

### Upload Flow

1. Sidebar renders `st.file_uploader` accepting `.xlsx` files
2. A `st.checkbox("Use default file")` defaults to `True` -- loads `data/NY Account Receivables_Overdue.xlsx`
3. User enters sender name in sidebar text input
4. "Generate Emails" button triggers `load_data_from_xlsx()`:
   - If uploaded file: reads BytesIO
   - If "Use default file": reads from default path
   - Calls `load_workbook()` from `src/data_loader.py`
   - Groups invoices by store, checks DNC list
   - Uses `TemplateEngine` to render each email
   - Returns `EmailQueue` stored in session state
5. A "Load Demo Data" button is available when no data has been generated -- uses hardcoded sample data

### Preview Mechanism

The preview page (`render_preview_page()`, lines 1227-1528) shows:

1. **Back to Queue button** at top
2. **Status bar**: Status badge, Tier badge, Days Past Due, Flags
3. **Email Headers**: From, To, CC, Subject, Attachment (displayed as static text, NOT editable in preview mode)
4. **Invoice Details**: Collapsible expander showing per-invoice metrics
5. **Email Body**: Rendered in a `streamlit.components.v1.html()` iframe with dynamic height. Styled to look like a Gmail preview window.
6. **Action Buttons**: APPROVE, EDIT, REJECT (with reason text input), NEXT
7. **Edit Mode** (toggled by EDIT button):
   - Two tabs: "Quick Edit" and "Edit HTML"
   - Quick Edit: TO, CC, Subject fields as text inputs, with Save/Cancel/Re-generate buttons
   - Edit HTML: TO, CC, Subject, + raw HTML body textarea
   - **NOTE**: The edit functionality code EXISTS in app.py (lines 1404-1512) and appears functional -- the `editing_{idx}` session state flag toggles it. The meeting claim that "the edit button is not functioning" may refer to a deployment issue or to the fact that edits do not persist after regeneration.

### Queue/Send Flow

1. **Queue page** shows all drafts in a table with columns: #, Tier, Store Name, Amount, Days, Status, Actions
2. **Batch actions** across the top:
   - "Approve All Pending"
   - "Approve Coming Due" (tier-specific)
   - "Send via Gmail" (disabled until SMTP configured and emails approved)
   - "Export Approved" (saves .eml files to `output/` directory)
   - "Download All (.zip)" (browser download of .eml zip)
3. **Per-email actions**: Approve, Preview, Reject buttons per row
4. **Send flow**: `_send_approved_emails()` iterates approved drafts, sends each via Gmail SMTP with progress bar, marks as SENT, adds to history
5. **Export flow**: Generates .eml files, writes summary report, records to history

---

## Gap Analysis: Current vs Required

| Requirement | Current State | Gap | Effort |
|-------------|--------------|-----|--------|
| **Editable TO/CC/BCC fields** | Edit mode code exists in preview page with Quick Edit + HTML Edit tabs. TO and CC are editable as comma-separated text inputs. BCC field is missing. | Edit mode code exists but may have bugs preventing activation. BCC field needs to be added. Need to verify the `editing_{idx}` toggle works end-to-end. | LOW -- code exists, needs debugging and BCC field addition |
| **Save button for Settings** | Settings page has inputs but no save/apply mechanism. Changes to CC list and tier boundaries are read from config module, not written back. | Need a "Save Settings" button that persists to config file (YAML/JSON) or session state that survives regeneration. | MEDIUM -- need persistence layer (write to config YAML or database) |
| **Schedule send** | Not implemented. Send goes immediately via SMTP. | Need time picker UI, delay/queue mechanism. Could use Gmail's built-in scheduled send via API, or implement server-side scheduling. | HIGH -- requires either Gmail API integration or a task scheduler |
| **Template editing in UI** | Templates are rendered by `TemplateEngine` from `src/template_engine.py`. No UI for viewing or editing template text. | Need a template editor page or section showing Jinja2 templates with preview. Or a simpler approach: editable text areas pre-filled with current templates. | HIGH -- requires template management UI and persistence |
| **Remove "Use Default File" checkbox** | `st.checkbox("Use default file", value=True)` in sidebar | Remove checkbox. If no file uploaded, show helpful message instead of silently using a default. | LOW -- delete ~5 lines of code |
| **Labels as dropdowns** | Tier boundary labels are `st.text_input` fields in Settings | Change to `st.selectbox` or `st.radio` with predefined options | LOW -- simple widget swap |
| **Only 3 tiers** | `TIER_COLORS` dict has 5 entries. `Tier` enum (in models) likely has 5 values. | Remove T3 (40+ Days) and T4 (50+ Days). Consolidate to T0=Coming Due, T1=1-29 Days Past Due, T2=30+ Days Past Due. | MEDIUM -- requires changes to models.py, tier_classifier.py, config.py, and app.py |
| **Dynamic subject lines** | Subject already includes tier label and store name. The tiered day count (30+, 40+, 50+) comes from the tier classification. | With 3-tier consolidation, need subject to dynamically show actual day range (30+, 40+, 50+, 60+, etc.) while body stays constant for tier 3. | MEDIUM -- template engine change to interpolate day buckets into subject |
| **Remove "final notice"** | Likely in template files or hardcoded in template engine | Search-and-remove from all templates and generated HTML | LOW -- text find/replace |
| **Dynamic "pay by date" warning on 30+ emails** | Currently only on 40+ and 50+ (AI-generated) | Add the red warning bar with dynamic date to all 30+ day emails | LOW-MEDIUM -- template modification |
| **Cloud deployment** | Pushed to Streamlit Cloud mid-meeting | Already done, but may need stable URL and possible auth | DONE (needs polish) |
| **Rep email as dynamic CC** | Static CC list: martinm, mario, laura, ny.ar@nabis | Need to lookup rep from invoice data and add their email to CC per-draft | MEDIUM -- requires rep-to-email mapping |
| **Notion/API contact resolution** | Contact resolver module exists but pulls from XLSX only | Need Notion API integration to pull primary contact, billing contact, and Nabis-sourced associate contacts | HIGH -- new API integration |
| **Scheduler for timed sends** | Not built | Need time picker + Gmail scheduled send or server-side cron | HIGH |

---

## Key Meeting Quotes on UI/UX

### On the edit button being non-functional:
> **Travis** (01:38:00): "We have to have the ability to edit the people who are getting and receiving the email. That needs to be editable from the actual interface. And then every change that is made on this page needs to be able to be saved."
> **Joe** (01:38:28): "There is an edit button right now, but it is not functioning, so once we just plug in the edit button to work, it should be good to go."

### On the missing save button:
> **Joe** (00:38:02): "There's no save button here. That's why it didn't save that when I said that. I did this, but there is no save button yet."

### On schedule send:
> **Travis** (00:09:14): "We usually do a schedule send on the emails. Can you do the same thing through here?"
> **Travis** (00:09:32): "She checks them, because we're on Pacific time, and then she schedules sends it for early in the morning, like at 7, so it populates everybody at 10 a.m. in New York time."

### On dropdowns:
> **Travis** (00:33:40): "Will those labels, do we have to write them out or are they gonna be like a drop down or something?"
> **Joe** (00:33:43): "Once this is like properly set up and stuck, I'll probably just be dropdowns and stuff."

### On templates being sealed:
> **Joe** (00:35:41): "The templates are sealed somewhere, so they are not actually modifiable yet."
> **Joe** (00:35:53): "I will have to edit that in because basically I was just going off of the templates that I got."

### On the "Use Default File" button:
> **Joe** (00:08:21): "Click Off Default File. I have to figure out what the heck that even means. That's a weird button that was for the demo."

### On removing final notice:
> **Travis** (00:54:59): "No final notice shit."
> **Travis** (00:55:06): "Remove 'this is a final notice' from all email bodies because we're always just going to keep sending them until the sun burns out."

### On the AI being 90-95% there:
> **Joe** (01:40:25): "It got us like 90, 95% of the way there, basically. We just needed to clean up these little data points and stuff, and a few little quality of life things to make it more usable."

### On the zero-thinking-required experience:
> **Travis** (00:42:38): "This is also a temporary platform... my actual goal is to make this as part of the intranet eventually, so that you would just be able to log in there and right under the proposal generator would be the account receivables emails. It would just all be integrated."

---

## Suggested Agent Prompts for Wave 2 UI Build

### Agent 1: Settings Persistence & Tier Consolidation
```
ROLE: Backend/Settings Engineer
TASK:
1. Consolidate tiers from 5 to 3: T0=Coming Due (-7 to 0), T1=Overdue (1-29), T2=30+ Days Past Due (30-999)
2. Remove TIER_COLORS entries for "40+ Days Past Due" and "50+ Days Past Due"
3. Add a "Save Settings" button to the Settings page that persists changes to config.yaml
4. Ensure settings survive page navigation and email regeneration
5. Convert tier label inputs from text_input to selectbox widgets
FILES: app.py, src/config.py, src/models.py, src/tier_classifier.py
```

### Agent 2: Edit Button & Recipient Management
```
ROLE: UI/Feature Engineer
TASK:
1. Debug and fix the edit button on the preview page (verify editing_{idx} toggle works)
2. Add BCC field to Quick Edit and HTML Edit tabs
3. Make CC list editable per-email (not just global)
4. Add dynamic rep email to CC based on invoice sales_rep field
5. Ensure edits persist after save (do not revert on page change)
FILES: app.py (render_preview_page, lines 1227-1528)
```

### Agent 3: Scheduler Implementation
```
ROLE: Feature Engineer
TASK:
1. Add a time picker widget (st.time_input) to the queue page batch actions area
2. Implement scheduled send using one of:
   a. Gmail API scheduled send (requires OAuth2 setup)
   b. Server-side APScheduler with SMTP send at scheduled time
   c. Simple delay mechanism with Streamlit background task
3. Show scheduled time on queue page
4. Allow cancellation of scheduled sends
FILES: app.py, new file: src/scheduler.py
```

### Agent 4: Template Management & Cleanup
```
ROLE: Template/Content Engineer
TASK:
1. Remove "final notice" from all email templates and generated HTML
2. Add the dynamic "pay by X date" red warning bar to ALL 30+ day emails (not just 40+/50+)
3. Create a template viewer/editor in the Settings page or a new "Templates" page
4. Make subject lines dynamic within the 30+ tier (30+, 40+, 50+, 60+, etc.)
5. Remove the "Use Default File" checkbox from the sidebar
6. Ensure template body stays constant for all 30+ emails, only subject changes
FILES: app.py, src/template_engine.py, templates/ directory
```

### Agent 5: Cloud & Integration
```
ROLE: DevOps/Integration Engineer
TASK:
1. Ensure Streamlit Cloud deployment is stable with a permanent URL
2. Add Notion API integration for contact resolution (primary -> billing -> associate, prefer Nabis-sourced)
3. Connect to Google Sheets API to auto-pull AR data (eliminate manual download/upload step -- future phase)
4. Plan integration path into PICC Platform intranet
FILES: app.py, src/contact_resolver.py, new file: src/notion_client.py
```
