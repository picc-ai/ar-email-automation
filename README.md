# AR Email Automation

Automated accounts receivable email drafting tool for PICC Platform. Turns a weekly 7.5-hour manual email process into a 30-minute review-and-approve workflow.

---

## For Laura: User Guide

### What This Tool Does

Every Wednesday you compose around 50 AR reminder emails by hand, looking up store contacts, picking the right template, and filling in invoice details. This tool does all of that automatically. You upload the same spreadsheet you already use, and the tool reads every overdue invoice, looks up the right contact for each store, writes the email using the correct template, and shows you the result. You review each email, approve the ones that look good, and export them. Your job goes from writing emails to checking emails.

### How to Use It (Step by Step)

**Step 1 -- Open the tool in your browser**

Go to:
```
http://localhost:8501
```
You will see the PICC AR Email Automation dashboard with summary cards across the top.

**Step 2 -- Upload the spreadsheet**

In the left sidebar, you will see an "Upload XLSX" area. You have two options:

- **Upload a file**: Click the upload area and select your "NY Account Receivables_Overdue.xlsx" file (the same one you download from Google Sheets each week).
- **Use the default file**: Check the "Use default file" box if the most recent spreadsheet is already saved in the tool's data folder.

Then click the **"Generate Emails"** button. The tool will process the spreadsheet and build all the email drafts in a few seconds.

If you just want to explore the tool without real data, click **"Load Demo Data"** to see 15 sample emails.

**Step 3 -- Review the email queue**

After processing, the Queue page shows all generated emails in a list. Each row displays:
- The store name
- The tier (color-coded badge showing urgency level)
- The dollar amount owed
- How many days overdue
- Current status (Pending, Approved, Rejected)
- Warning flags if anything needs extra attention (see "What the Flags Mean" below)

You can filter the list using the sidebar dropdowns:
- **Filter by Tier**: Show only Coming Due, Overdue, 30+ days, etc.
- **Filter by Status**: Show only Pending, Approved, or Rejected emails.

**Step 4 -- Preview each email**

Click the **"Preview"** button on any email row to see the full email exactly as the store will receive it. The preview shows:

- **From / To / CC** addresses
- **Subject line**
- **Full email body** with the store's name, invoice number, amount, due date, and account manager filled in
- **Attachment**: Nabis ACH Payment Form (automatically included)

The dynamic content (store name, amounts, dates, contact names) is highlighted so you can quickly scan and verify the data is correct without reading the entire template.

**Step 5 -- Approve or Reject**

For each email, you have these options:

| Button | What It Does |
|--------|-------------|
| **Approve** | Marks the email as good to send. |
| **Edit** | Lets you change the To, CC, Subject, or body text before approving. |
| **Reject** | Removes the email from the send list. You can add a note explaining why (e.g., "Spoke to them on the phone already"). |
| **Next** | Skips to the next email without taking action. |

To save time, use the **"Approve All Pending"** button at the top of the Queue page. This approves every email that does not have a warning flag. You can then go through the flagged ones individually.

**Step 6 -- Export approved emails**

Once you have reviewed everything, click **"Export Approved"** in the sidebar or queue page. This creates `.eml` files (one per approved email) in the `output/` folder on the computer, plus a summary report.

You can also click **"Download All (.zip)"** to download a zip file containing all the `.eml` files to your computer.

**Step 7 -- Send from Outlook**

Open each `.eml` file by double-clicking it. It will open in Outlook (or your default email program) with the To, CC, Subject, body, and attachment already filled in. Review it one final time and click Send.

### What Each Tier Means

The tool sorts every invoice into a tier based on how many days overdue it is. Each tier uses a different email tone:

| Tier | Days | What It Means | Email Tone |
|------|------|---------------|------------|
| **T1: Coming Due** | Not yet due (negative days) | Payment deadline is approaching | Friendly courtesy reminder |
| **T2: Overdue** | 1 to 29 days past due | Payment is late | Friendly nudge, empathetic |
| **T3: 30+ Days** | 30 to 39 days past due | Significantly overdue | Formal, mentions OCM reporting |
| **T4: 40+ Days** | 40 to 49 days past due | Approaching OCM threshold | Formal, OCM warning |
| **T5: 50+ Days** | 50 or more days past due | Critical -- OCM reporting imminent | Formal escalation, Mario sends instead of Kali |

### What the Flags Mean

Some emails get a warning flag that tells you to look more closely:

| Flag | What It Means |
|------|---------------|
| **MULTI-INVOICE** | This store has more than one overdue invoice. The tool combined them into one email. Double-check both amounts. |
| **MISSING_CONTACT** | The tool could not find this store's contact info. You will need to add the email address manually. |
| **MISSING_AM** | The account manager field is blank or shows an error in the spreadsheet. The email will say "your Nabis Account Manager" as a placeholder. |
| **HIGH_VALUE** | The invoice is over $5,000. Worth a closer look. |
| **CHRONIC_DELINQUENT** | The invoice is more than 80 days overdue. |

### FAQ

**Q: What if a store is missing from the contact list?**
A: The tool will flag it with "MISSING_CONTACT" and will not generate an email for that store. You will see it in the queue marked as needing attention. You can either add the contact to the Managers tab in the spreadsheet for next time, or compose that email manually.

**Q: What if the dollar amount looks wrong?**
A: The amounts come directly from the spreadsheet. If an amount is wrong, fix it in the Google Sheet, re-download the XLSX, and re-run the pipeline. Do not approve an email with a wrong amount.

**Q: What if I already called a store this week?**
A: Click "Reject" on that email and add a note like "Spoke on phone 2/9." The email will be removed from the send list.

**Q: What if a store already paid?**
A: If the "Paid" column is marked TRUE in the spreadsheet, the tool automatically skips it. If a payment came in after the spreadsheet was downloaded, reject the email with a note.

**Q: What if I need to change who the email is sent from?**
A: T1 through T4 emails are sent from Kali. T5 emails (50+ days) are flagged because Mario should send those instead. The tool will remind you of this.

**Q: What if an email was already sent this week?**
A: If the "Email Sent" column is TRUE in the spreadsheet, the tool skips that invoice automatically. You will not see a duplicate.

**Q: Can I change the email text before sending?**
A: Yes. Click "Edit" on any email in the preview to change the To, CC, Subject, or body text.

---

## For Joe: Developer Guide

### Project Structure

```
ar-email-automation/
├── app.py                    # Streamlit web UI (1697 lines)
├── config.yaml               # Main configuration file
├── conftest.py               # Pytest shared fixtures
├── requirements.txt          # Python dependencies
├── run.bat                   # Windows batch launcher
│
├── src/
│   ├── __init__.py
│   ├── main.py               # Pipeline orchestrator (entry point)
│   ├── config.py             # YAML config loader + defaults
│   ├── data_loader.py        # XLSX parser (openpyxl)
│   ├── models.py             # Pydantic/dataclass models
│   ├── tier_classifier.py    # Days-past-due -> tier mapping
│   ├── contact_resolver.py   # Location -> POC email/name matching
│   ├── template_engine.py    # Jinja2 HTML/text rendering
│   └── email_queue.py        # Queue management + .eml generation
│
├── templates/
│   ├── coming_due.html       # T1 template
│   ├── overdue.html          # T2 template
│   ├── past_due_30.html      # T3 template
│   ├── past_due_40.html      # T4 template
│   └── past_due_50.html      # T5 template
│
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_data_loader.py
│   ├── test_tier_classifier.py
│   ├── test_contact_resolver.py
│   └── test_integration.py
│
├── data/
│   ├── NY Account Receivables_Overdue.xlsx   # Production input
│   ├── Nabis_ACH_Payment_Form.pdf            # Attachment (4.4 MB)
│   ├── emails/                                # Historical .eml samples
│   └── meeting-summary.md                     # Stakeholder notes
│
├── output/
│   ├── drafts/               # Generated JSON + CSV exports
│   └── sent/                 # Exported .eml files
│
└── agent-outputs/            # Design docs (read-only reference)
    ├── 01-coming-due-email-analysis.md
    ├── 02-overdue-email-analysis.md
    ├── 03-past-due-email-analysis.md
    ├── 04-xlsx-schema-analysis.md
    ├── 05-xlsx-data-patterns.md
    ├── 06-business-requirements.md
    ├── 07-cross-email-patterns.md
    ├── 11-system-requirements.md
    ├── 12-architecture-design.md
    ├── 15-pipeline-run-report.md
    └── 15-ui-test-report.md
```

### Installation

```bash
cd "PICC Projects/ar-email-automation"
pip install -r requirements.txt
```

Dependencies: `streamlit`, `openpyxl`, `jinja2`, `pydantic`, `pyyaml`, `python-dateutil`, `pandas`.

### Running the Pipeline (CLI)

```bash
python -m src.main
```

This parses the XLSX, classifies invoices, resolves contacts, renders templates, and exports JSON + CSV drafts to `output/drafts/`. No UI required.

### Running the UI

```bash
python -m streamlit run app.py
```

Or on Windows, double-click `run.bat`.

The app launches at `http://localhost:8501`. Note: `streamlit` may not be on PATH; use `python -m streamlit` if needed.

### Running Tests

```bash
python -m pytest tests/ -v
```

Test files cover models, data_loader, tier_classifier, contact_resolver, and integration. Shared fixtures are in `conftest.py`.

### Architecture Overview

The pipeline runs in 7 sequential stages:

```
XLSX File
  |
  v
data_loader.py     -- Parse "Overdue X-X" + "Managers" sheets -> Invoice[], Contact[]
  |
  v
tier_classifier.py -- Assign T1-T5 tier based on days_over; apply skip filters
  |
  v
email_queue.py     -- Group invoices by dispensary (multi-invoice handling)
  |
  v
contact_resolver.py -- Match Location -> Managers record; parse POC name/email
  |
  v
template_engine.py -- Jinja2 render: tier template + variables -> HTML + plaintext
  |
  v
email_queue.py     -- Enqueue drafts with status=pending
  |
  v
app.py (Streamlit) -- Present queue for human review -> approve/reject -> export .eml
```

Key design decisions:
- **Deterministic, not AI-driven**: Template selection and variable population use formula logic, not LLM inference.
- **Human-in-the-loop**: No email can be sent without explicit approval.
- **Graceful degradation**: Missing contacts or data are flagged, never silently skipped. The Streamlit app wraps all module imports in try/except so it can launch even if a module is broken.

### Configuration (config.yaml)

The `config.yaml` file at the project root controls:

| Section | What It Controls |
|---------|-----------------|
| `data_source` | XLSX file path, sheet names |
| `sender` | Default sender name/email (Kali Speerstra) |
| `signature` | Address, tagline, URLs for the email signature block |
| `tiers` | Day ranges for T1-T5, template file names, tier labels |
| `cc_rules` | Always-CC list (ny.ar@nabis.com, mario@, martinm@, laura@) |
| `attachments` | Path to Nabis ACH Payment Form PDF |
| `skip_filters` | Skip if paid, payment enroute, or email already sent |
| `flag_rules` | Thresholds for HIGH_VALUE ($5k+), CHRONIC (80+ days), etc. |
| `rep_mapping` | Sales rep short name -> full name + email address |
| `smtp` | SMTP host/port/TLS settings (disabled by default) |

SMTP credentials are read from environment variables (`SMTP_USERNAME`, `SMTP_PASSWORD`), never stored in config.

### How to Add or Modify Email Templates

Templates live in `templates/` as Jinja2 HTML files. Each template has access to these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `CONTACT_FIRST_NAME` | Recipient's first name | "Emily" |
| `LOCATION` | Store name | "Aroma Farms" |
| `ORDER_NO` | Invoice number (integer) | 906858 |
| `DUE_DATE` | Due date (formatted) | "Feb 05, 2026" |
| `AMOUNT` | Dollar amount | "$1,510.00" |
| `ACCOUNT_MANAGER` | Nabis AM name | "Mildred Verdadero" |
| `AM_PHONE` | Nabis AM phone | "(415) 839-8232" |
| `TIER_LABEL` | Tier display name | "30+ Days Past Due" |
| `DAYS_DESCRIPTION` | Time-relative phrase (T2 only) | "over two weeks past due" |
| `INVOICE_BLOCKS` | List of invoice dicts (for multi-invoice) | Iterable in `{% for %}` |
| `SIGNATURE_BLOCK` | Full HTML signature block | Pre-rendered HTML |

To create a new template:
1. Add a new `.html` file in `templates/` (use an existing one as a starting point).
2. Update the tier configuration in `config.yaml` to point to the new template name.
3. Run `python -m pytest tests/ -v` to verify nothing breaks.

### Data Model (Key Classes in models.py)

| Class | Purpose |
|-------|---------|
| `Invoice` | Raw invoice row from the Overdue sheet |
| `Contact` | Resolved contact info (name, email, phone) from Managers sheet |
| `EmailDraft` | Complete email draft: addressing, subject, body, tier, flags, status |
| `EmailQueue` | List of EmailDraft objects with approve/reject/export methods |
| `Tier` | Enum: COMING_DUE, OVERDUE, THIRTY_PLUS, FORTY_PLUS, FIFTY_PLUS |
| `EmailStatus` | Enum: PENDING, APPROVED, REJECTED, SENT, FAILED |

### Known Limitations

- **No direct sending**: MVP exports `.eml` files only. There is no SMTP/Gmail API integration yet.
- **No Google Sheets API**: Data must be manually downloaded as XLSX and uploaded or placed in `data/`.
- **No write-back**: After sending, the "Email Sent" column in the spreadsheet must be updated manually.
- **One unmatched store**: "DeMarinos" has no record in the Managers sheet. Must be handled manually every cycle.
- **Matt M rep email**: The email for sales rep "Matt M" is a placeholder (`matt@piccplatform.com`) -- needs confirmation.
- **T3/T4/T5 template language**: These tiers currently use very similar escalation language. Future versions may differentiate them further.
- **Single-user**: No authentication on the Streamlit UI. It runs on localhost and is not suitable for public-facing deployment without adding auth.

### Future Integrations Roadmap

| Phase | Feature | Description |
|-------|---------|-------------|
| **V2** | SMTP / Gmail API | Send approved emails directly from the tool instead of exporting .eml files |
| **V2** | Google Sheets API | Pull data directly from the live Google Sheet -- no manual XLSX download |
| **V2** | Slack Notification | Bot pings Laura when a new batch is ready for review |
| **V2** | Write-back | Auto-update "Email Sent" and "Notes" columns in the Google Sheet after sending |
| **V3** | n8n Scheduling | Cron trigger runs the pipeline every Wednesday automatically |
| **V3** | Auto-send T1 | Coming Due emails sent automatically without review (lowest risk tier) |
| **V3** | Open/Reply Tracking | Track whether recipients opened or replied to AR emails |
| **V4** | Nabis API | Pull AR data directly from Nabis ERP instead of the spreadsheet |
| **V4** | PICC Platform | Integrate the AR module into the PICC Platform intranet web app |
