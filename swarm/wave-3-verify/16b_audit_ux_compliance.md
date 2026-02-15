# Wave 3 Agent 16b: UX Compliance Audit
**Status**: COMPLETED
**Timestamp**: 2026-02-14
**Agent**: Wave 3 Agent 16b (opus)
**Input files audited**:
- `swarm/wave-0-analysis/04_ux_requirements.md` (UX requirements source)
- `swarm/wave-0-analysis/06_blocker_identifier.md` (blocker/priority matrix)
- `app.py` (2246 lines, Streamlit UI)
- `config.yaml` (231 lines, tier/CC/SMTP config)
- `src/models.py` (717 lines, Tier enum, EmailDraft, EmailQueue)
- `src/tier_classifier.py` (695 lines, 3-tier classification)
- `src/template_engine.py` (1089 lines, Jinja2 rendering)
- `src/contact_resolver.py` (1243 lines, contact matching + CC rules)
- `templates/coming_due.html` (111 lines, T1 template)
- `templates/overdue.html` (113 lines, T2 template)
- `templates/past_due_30.html` (144 lines, T3 template)

---

## Requirements Checklist

| # | Requirement | Source | Verdict | Details |
|---|-------------|--------|---------|---------|
| 1 | 3 tiers only (not 5) | P0-1, UX #7/#8 | **PASS** | Consolidated to T0/T1/T2 |
| 2 | Templates match canonical PDF text | P0-2 | **PASS** | All 3 templates rebuilt from Callie's PDFs |
| 3 | No "final notice" language | P0-2, UX #10 | **PASS** | Zero occurrences in rendered content |
| 4 | Dynamic subject lines for 30+ | P0-5, UX #9 | **PASS** | Bucket logic: 30+, 40+, 50+, 60+, etc. |
| 5 | Editable TO/CC/BCC fields | P0-3, UX #1 | **PASS** | Quick Edit + HTML Edit tabs with BCC |
| 6 | Settings persist (save button) | P0-4, UX #2 | **PASS** | Save to data/settings.json implemented |
| 7 | Schedule send time picker | P1-1, UX #3 | **PASS** | time_input widget + timezone selector |
| 8 | "Use Default File" removed | P1-5, UX #5 | **PASS** | No checkbox; requires explicit upload |
| 9 | Sender name not hardcoded to "Laura" | P1-7 | **PASS** | Uses session_state.sender_name dynamically |
| 10 | CC list includes rep + ny.ar + Martin/Mario/Laura | UX #14/#15 | **PASS** | ALWAYS_CC + dynamic rep via REP_EMAIL_MAP |

**Compliance Score: 10/10 requirements met.**

---

## Tier Structure Compliance

**Verdict: PASS**

### Evidence

**`src/models.py` (lines 27-47) -- Tier enum:**
```python
class Tier(Enum):
    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"

    @classmethod
    def from_days(cls, days_past_due: int | float) -> Tier:
        if days_past_due <= 0:
            return cls.T0
        if days_past_due <= 29:
            return cls.T1
        return cls.T2
```

**`src/tier_classifier.py` (lines 26-34) -- Classifier Tier enum:**
```python
class Tier(str, Enum):
    COMING_DUE = "Coming Due"
    OVERDUE = "Overdue"
    PAST_DUE = "30+ Days Past Due"
```

**`config.yaml` (lines 14-34) -- Only 3 tiers defined:**
```yaml
tiers:
  T1: { min_days: -7, max_days: 0, label: "Coming Due", template_file: "coming_due.html" }
  T2: { min_days: 1, max_days: 29, label: "Overdue", template_file: "overdue.html" }
  T3: { min_days: 30, max_days: 999, label: "30+ Days Past Due", template_file: "past_due_30.html" }
```

**`app.py` (lines 119-124) -- TIER_COLORS only has 3 entries:**
```python
TIER_COLORS = {
    "Coming Due":          {"bg": "#d4edda", "text": "#155724", "icon": ""},
    "Overdue":             {"bg": "#fff3cd", "text": "#856404", "icon": ""},
    "30+ Days Past Due":   {"bg": "#f8d7da", "text": "#721c24", "icon": ""},
}
```

**Boundary correctness:**
- T0 Coming Due: -7 to 0 -- matches meeting requirement ("-7 to 0")
- T1 Overdue: 1 to 29 -- matches meeting requirement
- T2 30+ Days: 30 to 999 -- matches meeting requirement

**Old T4/T5 templates deleted:**
- `templates/past_due_40.html` -- confirmed NOT FOUND
- `templates/past_due_50.html` -- confirmed NOT FOUND

---

## Template Text Compliance

**Verdict: PASS**

### Templates audited

**`templates/coming_due.html`:**
- Body source comment: "Canonical PDF from Callie (A/R Email Formatting.pdf)"
- Opening: "I hope you're well. This is a courtesy reminder that your payment is due soon."
- Invoice intro: "According to our records, the following invoice is coming due:"
- Bullet format: Invoice/Order, Due, Amount, Nabis AM (space separator)
- Closing: "Thank you for your business. You're much appreciated. Have a great day!"
- Signature block: Uses `{{SENDER_NAME}}` and `{{SENDER_TITLE}}` variables
- No "final notice", no "ACTION REQUIRED", no escalation language

**`templates/overdue.html`:**
- Body source comment: "Canonical PDF from Callie (A/R Email Formatting.pdf)"
- Correction note: "nearing two weeks past due" changed to "overdue" per Callie's fix email
- Opening: "I hope you're having a great day."
- Purpose: "This is a friendly reminder that your invoice is overdue."
- Empathy clause present: "We understand how busy you can get..."
- Bullet format: Invoice/Order, Due, Amount, Nabis AM (space separator)
- No "final notice", no "ACTION REQUIRED"

**`templates/past_due_30.html`:**
- Comment explicitly states: "No 'second notice', 'final notice', 'ACTION REQUIRED', account holds, or collection threats. Ever."
- OCM warning present: references 45-day notification and 52-day reporting
- Bullet order: Invoice, Due, Nabis AM (dash separator), Amount -- matches canonical T3 format
- Payment facilitation paragraph present
- Consequence warning: "avoid service disruptions and the painstaking hassle of being reported to OCM"
- Formal sign-off "Regards," (different from T1/T2 which are warmer)
- Uses `{{DAYS_PAST_DUE_BUCKET}}` in title for dynamic subject

---

## "Final Notice" Ban Compliance

**Verdict: PASS**

### Grep results for "final notice" across the codebase

| Location | Context | Verdict |
|----------|---------|---------|
| `templates/past_due_30.html:25` | HTML comment: `No "second notice", "final notice"...` | **Documentation only** -- not rendered |
| `src/template_engine.py:159` | Code comment: `No "ACTION REQUIRED" or "FINAL NOTICE" suffixes` | **Documentation only** -- enforcing the ban |
| `src/template_engine.py:183` | Code comment: `or "FINAL NOTICE" in subject lines. Ever.` | **Documentation only** -- enforcing the ban |
| `app.py` | **ZERO matches** | Clean |
| `src/models.py` | **ZERO matches** | Clean |
| `src/tier_classifier.py` | **ZERO matches** | Clean |
| `config.yaml` | **ZERO matches** | Clean |

All "final notice" references in `src/` and `templates/` are strictly in comments that document the prohibition. No rendered email content contains the phrase. The `build_subject_line()` function in `template_engine.py` (line 183) explicitly comments that "FINAL NOTICE" must never appear in subject lines.

Remaining matches in `swarm/` directory files (analysis reports, build logs) are purely historical documentation and do not affect runtime behavior.

---

## Dynamic Subject Lines

**Verdict: PASS**

### Implementation chain

**`src/models.py` (lines 179-189) -- `Invoice.dynamic_subject_label` property:**
```python
@property
def dynamic_subject_label(self) -> str:
    if self.days_past_due < 30:
        return self.tier.value
    bucket = (self.days_past_due // 10) * 10
    return f"{bucket}+ Days Past Due"
```

**`src/models.py` (lines 384-403) -- `EmailDraft.build_subject()`:**
Uses `dynamic_subject_label` for T2 invoices to compute the bucket label.

**`src/template_engine.py` (lines 596-600) -- `render_email()` subject logic:**
```python
if primary_invoice.days_past_due >= 30:
    bucket = (primary_invoice.days_past_due // 10) * 10
    subject_tier_label = f"{bucket}+ Days Past Due"
else:
    subject_tier_label = tier_cfg.label
```

**`src/tier_classifier.py` (lines 430-456) -- `get_dynamic_subject_label()`:**
Standalone function with the same bucket logic, plus self-test cases validating:
- 35 days -> "30+ Days Past Due"
- 45 days -> "40+ Days Past Due"
- 52 days -> "50+ Days Past Due"
- 111 days -> "110+ Days Past Due"

**Template title in `past_due_30.html` (line 6):**
```html
<title>PICC - {{STORE_NAME}} - Nabis Invoice {{INVOICE_NUMBER}} - {{DAYS_PAST_DUE_BUCKET}}</title>
```

The dynamic bucket variable is correctly wired from `_build_context()` through to the template and subject line builder. The body stays constant for all 30+ invoices while only the subject varies.

---

## Editable TO/CC/BCC

**Verdict: PASS**

### Implementation in `app.py`

**Edit button (line 1494):** Always available regardless of email status:
```python
if st.button("EDIT", use_container_width=True):
    st.session_state[f"editing_{idx}"] = True
```

**Quick Edit tab (lines 1526-1566):**
- `st.text_input("To (comma-separated)", ...)` -- line 1529
- `st.text_input("CC (comma-separated)", ...)` -- line 1535
- `st.text_input("BCC (comma-separated)", ...)` -- line 1541
- `st.text_input("Subject", ...)` -- line 1547
- Save Changes button persists edits to the draft object (lines 1555-1562)

**HTML Edit tab (lines 1593-1641):**
- Same TO/CC/BCC/Subject fields plus raw HTML body textarea
- Save Changes button persists all fields including `body_html`

**BCC field present:**
- `EmailDraft` in `models.py` (line 303): `bcc: list[str] = field(default_factory=list)`
- BCC rendering in preview headers (lines 1404-1406): displays BCC alongside From/To/CC
- BCC included in SMTP send (lines 497-499, 554-555)
- BCC included in .eml export (lines 465-467)

The edit mode was identified as "non-functional" during the meeting. It is now fully functional with both Quick Edit and HTML Edit tabs, supporting TO, CC, BCC, Subject, and body editing. Changes persist to the draft object in session state.

---

## Settings Persistence

**Verdict: PASS**

### Implementation

**`app.py` (lines 337-359) -- File-based persistence:**
- `SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"` -- line 337
- `_load_saved_settings()` -- reads from disk on session init (lines 339-346)
- `_save_settings()` -- writes to disk when Save clicked (lines 349-359)

**`app.py` (lines 362-391) -- Session init loads saved settings:**
```python
def init_session_state():
    saved = _load_saved_settings()
    defaults = {
        "sender_email": saved.get("sender_email", "laura@piccplatform.com"),
        "sender_name": saved.get("sender_name", ""),
        "custom_cc": saved.get("custom_cc", None),
        "schedule_time": saved.get("schedule_time", "07:00"),
        "schedule_timezone": saved.get("schedule_timezone", "PT"),
    }
```

**`app.py` (lines 2088-2112) -- Save Settings button:**
- Button at line 2090: `st.button("Save Settings", type="primary", ...)`
- Persists: sender_name, sender_email, custom_cc, schedule_time, schedule_timezone
- Writes to `data/settings.json`
- Success/error feedback to user

Settings survive page navigation, email regeneration, and app restarts via the JSON file on disk.

---

## Schedule Send

**Verdict: PASS**

### Implementation

**`app.py` (lines 1142-1198) -- Schedule send time picker:**
- `st.time_input("Schedule send time", value=default_time, ...)` -- line 1146
- Default: 7:00 AM PT (Callie's preferred time)
- `st.selectbox("Timezone", options=["PT", "ET", "CT", "MT"], ...)` -- line 1159
- PT-to-ET conversion display (lines 1172-1198)
- Green info box shows scheduled time and timezone conversion
- Applies `scheduled_send_time` and `scheduled_timezone` to all drafts (lines 1153-1171)

**`src/models.py` (lines 318-348) -- EmailDraft scheduling fields:**
- `scheduled_send_time: time | None = None`
- `scheduled_timezone: str = "PT"`
- `scheduled_time_display` property with PT/ET conversion

**Display in preview page (lines 1361-1411):**
- Scheduled time shown in status bar
- Scheduled time shown in email headers

**Note:** The schedule send is informational -- emails are sent immediately when "Send via Gmail" is clicked. The UI displays a note (line 1193): "Emails will be sent immediately when you click Send via Gmail. To schedule-send, use Gmail's built-in schedule send feature, or run this tool at the target time." This is an acceptable implementation given that true server-side scheduling requires infrastructure beyond Streamlit.

---

## "Use Default File" Removal

**Verdict: PASS**

### Evidence

A grep for "default file" and "Use default" in `app.py` found only one match:
```
Line 775: st.error("No XLSX file provided and default file not found.")
```

This is a fallback error message in `load_data_from_xlsx()` that fires when no file is uploaded AND no default file exists on disk. This is correct behavior -- it informs the user to upload a file.

The original `st.checkbox("Use default file", value=True)` that was identified as confusing in the meeting (UX Issue #3, Feature Request #5) has been completely removed. The sidebar now shows only:
- File uploader widget (line 876)
- Sender name input (line 887)
- Generate Emails button (line 897)

If no file is uploaded and Generate is clicked, the user gets `st.warning("Please upload an XLSX file first.")` (line 909). This is the correct "zero thinking required" behavior.

---

## Sender Name Fix

**Verdict: PASS**

### Evidence

The blocker report (P1-7) identified: "Line 1290 of app.py hardcodes `f'Laura <{st.session_state.sender_email}>'` in the From field display."

**Current implementation (`app.py` lines 1397-1399):**
```python
sender_display = st.session_state.sender_name or "PICC Accounts Receivable"
st.markdown(f"{sender_display} <{st.session_state.sender_email}>")
```

A grep for `Laura\s*<` in `app.py` returned **ZERO matches**. The hardcoded "Laura" has been replaced with dynamic `sender_name` from session state. When no sender name is configured, it falls back to "PICC Accounts Receivable" -- not a person's name.

**Signature in templates:** All three templates use `{{SENDER_NAME}}` variable, resolved by `template_engine.py`'s `_resolve_sender()` method (line 713) which reads from `config.sender.name`.

**`config.yaml` (line 111):** `name: "PICC Accounts Receivable"` -- generic default, not hardcoded to any individual.

---

## CC List Rules

**Verdict: PASS**

### Meeting requirement

Travis specified (1:34:53): "The rep email, we always include whoever the rep is."
Callie confirmed (1:35:06): "We always CC the Nabis account manager" (ny.ar@nabis.com).

### Implementation

**`src/contact_resolver.py` (lines 83-89) -- ALWAYS_CC:**
```python
ALWAYS_CC: list[str] = [
    "ny.ar@nabis.com",
    "martinm@piccplatform.com",
    "mario@piccplatform.com",
    "laura@piccplatform.com",
]
```

**`src/contact_resolver.py` (lines 73-81) -- REP_EMAIL_MAP:**
```python
REP_EMAIL_MAP: dict[str, str] = {
    "Ben": "b.rosenthal@piccplatform.com",
    "Bryce J": "bryce@piccplatform.com",
    "Donovan": "donovan@piccplatform.com",
    "Eric": "eric@piccplatform.com",
    "M Martin": "martinm@piccplatform.com",
    "Mario": "mario@piccplatform.com",
    "Matt M": "matt@piccplatform.com",
}
```

**Dynamic rep CC logic (`contact_resolver.py` lines 847-854):**
```python
sales_rep = str(getattr(invoice, "sales_rep", "") or "").strip()
if sales_rep:
    rep_email = self._rep_email_map.get(sales_rep, "")
    if rep_email and rep_email.lower() not in [c.lower() for c in cc]:
        cc.append(rep_email)
```

**Same logic duplicated in `template_engine.py` (lines 227-239)** for the Jinja2 rendering path.

**`config.yaml` (lines 44-56) -- base_cc matches:**
```yaml
cc_rules:
  base_cc:
    - "ny.ar@nabis.com"
    - "martinm@piccplatform.com"
    - "mario@piccplatform.com"
    - "laura@piccplatform.com"
```

All required CC recipients are present. Dynamic sales rep CC is implemented. De-duplication logic prevents duplicate entries when a rep (e.g., Mario, M Martin) is already in the base CC list.

---

## Missing Requirements

### Items identified as P2 / future that remain unimplemented (acceptable -- not in scope for go-live)

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1 | Notion API integration for auto contact resolution | Not built | P2-2 from blocker report. Manual email entry via edit mode is the workaround. |
| 2 | Google Sheets auto-pull (eliminate manual XLSX upload) | Not built | P2-1. Manual upload is the go-live plan. |
| 3 | Template editing in UI | Not built | P1-4. Edit HTML tab provides a workaround for power users. |
| 4 | True server-side scheduled send | Not built | Schedule picker exists but sends immediately. Acceptable per meeting context -- Callie can use Gmail's built-in schedule-send. |
| 5 | Dropdowns for tier labels in Settings | **Implemented** | `st.selectbox` used at line 2074 instead of `st.text_input`. |
| 6 | Gmail App Password persistence across sessions | Partial | Password is not saved to disk (correct for security). Callie must re-enter on restart. |

None of these missing items were P0 blockers. All P0 and critical P1 items have been addressed.

---

## Verdict

**Compliance Score: 10/10 meeting requirements met.**

All 5 P0 blockers from the go-live blocker report have been resolved:
- P0-1: Tier consolidation (5 -> 3) -- **DONE**
- P0-2: Template bodies match canonical text -- **DONE**
- P0-3: Editable TO/CC/BCC fields functional -- **DONE**
- P0-4: Settings persistence with Save button -- **DONE**
- P0-5: Dynamic subject lines for 30+ tier -- **DONE**

All critical P1 items addressed:
- P1-1: Schedule send time picker -- **DONE** (informational; sends immediately)
- P1-5: "Use Default File" removed -- **DONE**
- P1-6: Coming Due boundary updated to -7 to 0 -- **DONE** (config.yaml line 17)
- P1-7: Sender name no longer hardcoded to "Laura" -- **DONE**

The implementation is architecturally sound:
- 3-tier system is consistent across `models.py`, `tier_classifier.py`, `config.yaml`, `app.py`, and all 3 templates
- No "final notice" text appears in any rendered email content
- Dynamic subject labels correctly bucket 30+/40+/50+/60+/etc.
- Edit mode supports TO, CC, BCC, Subject, and raw HTML body
- Settings persist to `data/settings.json` across sessions
- CC rules include all required recipients with dynamic rep resolution

**The AR Email Automation tool passes the UX compliance audit and is ready for go-live testing.**
