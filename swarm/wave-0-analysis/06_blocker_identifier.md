# Blocker Identifier Report
## Report: 06 - Go-Live Blockers & Priority Matrix
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 6 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (full ~1:40:00 meeting transcript, ~6500 lines)
- `A:\Downloads\Action items.md` (72 lines, meeting summary + action items)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\app.py` (2069 lines, full Streamlit UI)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\config.yaml` (243 lines, tier/CC/SMTP config)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\USER_GUIDE.md` (491 lines, user documentation)

## Verdict: NOT YET READY FOR GO-LIVE. 5 P0 blockers remain. With focused effort, 3-4 can be resolved by Thursday morning. The tool can go live in a "semi-automated" mode where Callie manually inputs recipient emails but the tool handles body generation, formatting, and sending.

---

## Executive Summary

The AR Email Automation tool is a Streamlit-based web application that generates, previews, and sends accounts receivable collection emails for PICC Platform's NY operations. During the meeting, Travis (manager), Callie (end user/AR specialist), and Joe (developer) ran a live demo, compared generated emails against Callie's manual process, and identified specific gaps.

**Current State**: The tool successfully loads XLSX data, generates tiered emails, displays them in a preview queue, and can send via Gmail SMTP. However, it has the wrong number of tiers (5 instead of 3), templates that have drifted from the canonical versions, no editable recipient/CC fields that persist, and no scheduling capability.

**Go-Live Definition**: Callie needs to use this tool Thursday morning to prepare and send AR emails instead of (or in parallel with) doing it manually. The tool must produce emails that match what she would write by hand, with correct recipients, correct template text, and correct data.

---

## P0: Must Fix (Blocks Go-Live)

| # | Blocker | Why It Blocks | Effort Est | Fix Approach |
|---|---------|---------------|-----------|--------------|
| P0-1 | **Tier consolidation: 5 tiers -> 3 tiers** | config.yaml defines T1-T5 with separate templates for 30+, 40+, 50+ days. Meeting agreed on exactly 3 templates: Coming Due (-7 to 0), 1-29 Days Past Due (1-29), 30+ Days Past Due (30-999). The extra tiers (T4 40+, T5 50+) confuse Callie and generate wrong labels. | 1-2 hours | Update `config.yaml`: T1 = Coming Due (-7 to 0), T2 = 1-29 Days Past Due (1-29), T3 = 30+ Days Past Due (30-999). Remove T4 and T5 entries entirely. Update `src/models.py` Tier enum if it hardcodes 5 tiers. Update `src/tier_classifier.py` tier boundaries. Update `TIER_COLORS` dict in `app.py`. |
| P0-2 | **Template bodies must match Callie's canonical templates** | AI learned from historical email variations and drifted the wording. Meeting explicitly said: use the 3 templates Callie emailed to Joe as the "source of truth." Templates must NOT contain "final notice" anywhere. The 30+ template must include the dynamic OCM/Nabis reporting warning with a computed deadline date. | 2-4 hours | Replace `templates/coming_due.html`, `templates/overdue.html`, and create single `templates/past_due_30.html` based on Callie's emailed templates. Remove `past_due_40.html` and `past_due_50.html`. Ensure no "final notice" text exists in any template. Add dynamic "We request payment be submitted by [date] to avoid account restrictions or OCM reporting" block to the 30+ template. Verify the `_build_sample_html()` fallback in `app.py` also reflects correct wording. |
| P0-3 | **Recipient email resolution is broken/incomplete** | The AR XLSX does not contain contact emails. Currently the tool either shows "(no contact found)" or pulls from historical email data which is unreliable. Callie manually looks up contacts in Notion using a priority cascade: primary contact -> billing/AP contact -> associated contacts (prefer Nabis-sourced over Revelry). This Notion integration does NOT exist yet. | 2-3 hours (workaround) | **Workaround for go-live**: Make the Quick Edit "To" field prominent and functional (it already works per code review). Accept that Callie will manually paste recipient emails for each store. **Future**: Build Notion API integration to auto-resolve contacts per the SOP cascade (primary -> billing -> Nabis associate). For now, ensure the "(no contact found)" state is obvious and the edit flow is smooth. |
| P0-4 | **Settings do not persist (no save button)** | Tier boundary changes, CC list edits, and sender configuration in the Settings page are not saved. The meeting explicitly identified: "There's no save button here." Changes to tier boundaries revert on regeneration. | 1-2 hours | Add a "Save Settings" button on the settings page that writes changes back to `config.yaml` or session state that persists across regeneration. At minimum, ensure session state values for sender_name, sender_email, CC list, and tier boundaries survive a "Generate Emails" click. |
| P0-5 | **Subject line must be dynamic with tiered day count** | For 30+ tier, subject should say "30+ Days Past Due," "40+ Days Past Due," "50+ Days Past Due" etc. based on actual days -- not the template tier label. Meeting agreed: subject is dynamic, body is same for all 30+. Current `subject_line.single_template` in config uses `{tier_label}` which would just say "30+ Days Past Due" for everything. | 1-2 hours | Modify subject line generation logic: for the 30+ tier, compute the dynamic label as "30+ Days Past Due" if 30-39, "40+ Days Past Due" if 40-49, "50+ Days Past Due" if 50+. Keep body identical. Update `config.yaml` subject template or add logic in `template_engine.py`. |

**Total P0 estimated effort: 7-13 hours of focused development.**

---

## P1: Should Fix (Degrades Experience)

| # | Issue | Impact | Effort Est |
|---|-------|--------|-----------|
| P1-1 | **Scheduling/timed send not implemented** | Callie is on Pacific time, needs emails to arrive at 10am ET (7am PT). Currently must manually time when to click "Send." Travis explicitly requested this. Without it, Callie has to wake up early or send late. | 3-4 hours |
| P1-2 | **CC/BCC per-email editing does not persist properly** | The edit button exists and Quick Edit tab has CC field, but meeting said "the edit button is present but nonfunctional" for CC/BCC on the preview page. Need to verify this actually saves. | 1 hour |
| P1-3 | **Rep email not dynamically added to CC** | Each email should CC the assigned sales rep (Bryce, Eric, Donovan, etc.) in addition to the base CC list. Currently the base CC is static (ny.ar, martin, mario, laura). Rep email is not being added from the data. | 2-3 hours |
| P1-4 | **Template editing not exposed in UI** | Templates are "sealed" in HTML files. Travis asked if templates could be edited from the interface. Joe confirmed they cannot yet. For go-live this is a workaround via Edit HTML tab, but Callie should not need to touch HTML. | 3-4 hours |
| P1-5 | **"Use default file" checkbox defaults to True** | This means if Callie forgets to upload a new XLSX, it silently uses stale data. Should default to False or prompt a confirmation. | 15 min |
| P1-6 | **Coming Due tier boundary mismatch** | Config says -3 to 3 but meeting agreed -7 to 0 (negative seven to zero, inclusive). Must update config.yaml. | 15 min |
| P1-7 | **Sender name shows "Laura" hardcoded in preview** | Line 1290 of app.py hardcodes `f"Laura <{st.session_state.sender_email}>"` in the From field display. Should use `st.session_state.sender_name` or fall back to config. | 10 min |
| P1-8 | **Gmail App Password not persisted across sessions** | USER_GUIDE says "The password is stored while the app is running but is not saved to disk, so you may need to re-enter it if you restart the app." This means every time Streamlit restarts (common on Streamlit Cloud), Callie has to re-enter. | 1 hour |

---

## P2: Nice to Have (Future)

| # | Enhancement | Value |
|---|-------------|-------|
| P2-1 | **Auto-pull AR data from Google Sheets API instead of manual XLSX upload** | Eliminates manual download-upload step. Meeting discussed checking if synced orders sheet has same AR fields. |
| P2-2 | **Notion API integration for contact resolution** | Auto-populate To field with correct contact per SOP cascade. Eliminates Callie's manual email lookup. |
| P2-3 | **Integration into PICC Platform intranet** | Joe mentioned moving this under the main intranet site alongside proposal generator. |
| P2-4 | **Dropdowns instead of text fields for tier labels** | Joe mentioned converting settings text inputs to dropdowns once tiers are stabilized. |
| P2-5 | **Coda migration** | Joe mentioned Coda -> Notion migration opportunity. Not blocking AR emails. |
| P2-6 | **Red "immediate action required" banner for 30+ day emails** | Travis liked the AI-generated red warning bar. Want it on all 30+ day emails with dynamic date. Nice visual but not blocking. |
| P2-7 | **Automatic daily data sync from Nabis API** | Currently once-daily via Justin's sync. Future: more frequent updates on AWS. |
| P2-8 | **Email send history tracking across sessions** | Currently history is session-only. Persistent database would enable weekly/monthly reporting. |

---

## Timeline & Schedule

| Event | Timing | Notes |
|-------|--------|-------|
| Meeting held | ~Feb 12-13, 2026 | Based on context clues (references to "tomorrow morning", "Thursday") |
| Callie sends canonical templates to Joe | Same day as meeting | 3 email templates: Coming Due, 1-29 Past Due, 30+ Past Due |
| Callie checks morning AR data | Day after meeting | Verify if orders-based sheet has same AR fields as Balances export |
| Joe implements fixes | Day after meeting through Wednesday | Tier consolidation, template alignment, subject line, edit persistence |
| **HARD DEADLINE: Thursday morning** | **Callie must send AR emails** | She will either use the tool or do it manually. Parallel testing: she does both and compares. |
| First automated test run | Thursday or later in the week | Compare automated output against Callie's manual emails from the same week |

**Critical Path**: P0-1 (tiers) and P0-2 (templates) must be done first because everything else depends on correct tier assignment and correct email body generation.

---

## Testing Strategy

The meeting established a **parallel testing approach**:

1. **Callie continues to build and send AR emails manually** as she normally does
2. **Callie archives/saves her manual emails** for later comparison
3. **Joe runs the tool against the same weekly AR data** and generates the automated batch
4. **Side-by-side comparison**: for each store, compare:
   - Recipient email addresses (To)
   - CC list
   - Subject line (format and day count)
   - Email body (template text, variable substitution)
   - Invoice details (amounts, dates, order numbers)
   - Account Manager name and phone
5. **Any discrepancy is documented** with the correct source location so Joe can fix the mapping

**Testing Acceptance Criteria** (derived from meeting):
- All 3 tiers produce correct template text
- No "final notice" appears anywhere
- Subject lines show correct dynamic day ranges
- Invoice amounts and dates match the XLSX source
- Nabis Account Manager name and phone are correctly populated from the XLSX (already working per discovery during meeting)
- All base CC recipients are included (ny.ar@nabis.com, martinm, mario, laura)
- Sender signature shows correct name (Callie's name, not "Mario" or other defaults)

---

## Deployment Status

| Aspect | Current State | Needed for Go-Live |
|--------|--------------|-------------------|
| **Hosting** | Initially local on Joe's machine. Pushed to Streamlit Cloud during the meeting. | Streamlit Cloud is fine for go-live. URL was shared. |
| **Access** | Callie had trouble accessing local version. Streamlit Cloud resolved this. | Verify Callie can access the Streamlit Cloud URL reliably. |
| **Code repo** | Joe mentioned pushing to GitHub/Bitbucket during the meeting. | Repo exists at `PICC Projects/ar-email-automation/`. |
| **Dependencies** | Python + Streamlit + src modules. All 6 modules currently available per code review. | Ensure Streamlit Cloud deployment has all dependencies. |
| **Data files** | Default XLSX in `data/` folder. Nabis ACH PDF in `data/` folder. | Callie uploads fresh XLSX each week. ACH form is static. |
| **Authentication** | Gmail App Password entered per session (not persisted). | Callie needs to generate an App Password from her Google account. |

---

## Unresolved Decisions

| # | Decision Needed | Who Decides | Context |
|---|----------------|-------------|---------|
| 1 | **Can AR data come from the synced orders sheet instead of manual Balances CSV export?** | Callie + Justin | Callie was going to check in the morning if the orders-based Google Sheet has the same fields as the Balances export. If yes, eliminates manual download step. |
| 2 | **Which email address does the AR email come FROM?** | Travis | Currently `laura@piccplatform.com`. Travis mentioned possibly creating a dedicated `ar@piccplatform.com` or similar. Not decided. |
| 3 | **Should the "immediate action required" red banner appear on ALL 30+ day emails or only 40+/50+?** | Travis + Callie | Travis said he liked it. Callie confirmed the OCM warning text is already in the 30+ template. The visual red bar format was not definitively assigned to a tier threshold. Meeting leaned toward all 30+. |
| 4 | **Contact email priority: should Nabis POC contacts override Notion primary contacts?** | Travis + Callie + Bryce | Bryce said Nabis/CRM contacts are more reliable than Revelry. But the exact hierarchy was not formally documented. Current SOP per Callie: primary -> billing -> Nabis associate. |
| 5 | **Should the rep's email be in To or CC?** | Travis | Meeting said "the rep is always included" but did not specify To vs CC. Currently not implemented at all. Likely should be CC. |
| 6 | **Exact wording of the dynamic OCM/deadline sentence** | Joe + Callie | The AI-generated version says "We request payment be submitted by [date] to avoid account restrictions or OCM reporting." Need to confirm this matches the canonical 30+ template Callie sent. |
| 7 | **Day zero: Coming Due or Overdue?** | Travis + Callie | Meeting concluded that day 0 (the actual due date) should be included in Coming Due, not trigger an overdue email. Travis said "negative seven to zero." This means Coming Due = -7 to 0, Overdue = 1-29. |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Callie cannot access Streamlit Cloud URL** | Medium | High - tool is completely unusable | Test access before Thursday. Provide backup local run instructions. |
| **Gmail App Password setup fails for Callie's account** | Medium | High - cannot send from tool | Provide step-by-step with screenshots. Test with her actual account before Thursday. Fallback: export .eml files and send from Gmail directly. |
| **Template text does not match after edits** | Medium | Medium - embarrassing if wrong email goes to customer | Parallel testing: Callie reviews every email before approving. Never auto-send without review. |
| **Wrong recipient gets an AR email** | Low | Very High - sends confidential financial info to wrong person | Contact resolution is manual for go-live (Callie pastes emails). She already knows the correct contacts. The risk is the same as her current manual process. |
| **XLSX format changes break the data loader** | Low | High - tool cannot generate emails | Keep manual fallback process. Callie can always do it manually if the tool breaks. |
| **Streamlit Cloud has downtime Thursday morning** | Low | Medium - delays email sending | Can run locally as backup. USER_GUIDE has local instructions. |
| **"Final notice" text still appears somewhere in templates** | Medium | High - legal/relationship risk | Grep all template files and `app.py` for "final notice" before go-live. Remove any instance. |
| **Session state lost on Streamlit Cloud rerun/refresh** | High | Medium - loses approved/rejected state, app password | This is a known Streamlit limitation. Callie should do entire workflow in one session: upload, generate, review, approve, send. |
| **Nabis Account Manager data is stale** | Low | Low - wrong name/phone in email body | Data comes from XLSX which is refreshed weekly. Meeting confirmed the AM data in the XLSX is correct and rarely changes. |

---

## External Dependencies

| Dependency | Owner | Status | Blocks Go-Live? |
|------------|-------|--------|-----------------|
| **Callie's canonical email templates (3)** | Callie | Sent to Joe during the meeting | YES - templates must be ingested into the tool |
| **Gmail App Password for Callie's account** | Callie | Not yet generated | YES - needed for direct send. Workaround: export .eml |
| **Streamlit Cloud deployment** | Joe | Pushed during meeting | YES - must be accessible |
| **Nabis Account Manager reference sheet** | Callie/Nabis | Already in XLSX columns | NO - already working |
| **Justin/Nabis API sync for AR data** | Justin | Investigating if orders sheet has AR fields | NO - manual XLSX upload is the go-live plan |
| **Bryce/Mary contact consolidation in Notion** | Bryce/Mary | In progress | NO - manual email entry is the go-live plan |
| **Notion API access** | Joe | Not yet set up | NO - future enhancement for contact resolution |
| **Google Sheets API** | Joe | Not yet connected for AR | NO - future enhancement for auto-import |

---

## Key Meeting Quotes on Go-Live Requirements

**Travis on parallel testing** (~04:11):
> "Callie, if you can go through and manually do it on your side right now, while you're looking at his, and see where the discrepancies are."

**Travis on templates as source of truth** (~28:43):
> "Can you send Joe right now an email? That way he has your templates, right? That'd be great. That way we know these are the templates of truth."

**Travis on only 3 tiers** (~28:05):
> "Basically, then you have basically three templates, right? Coming due, 1 to 29 days past due, and then 30 plus days past due."

**Callie on tier boundaries** (~20:10):
> "The coming due, we were doing anything that was negative... we only wanted it to read negative seven."

**Travis on removing "final notice"** (~55:00):
> "Remove. This is a final. Notice from all email bodies because we're always just going to keep sending them until the sun burns out."

**Joe on no save button** (~38:02):
> "There's no save button here. That's why it didn't save... I just have to put a save button in."

**Travis on editable recipients** (~1:38:01):
> "We have to have the ability to edit the people who are getting and receiving the email... needs to be editable from the actual interface."

**Joe on edit button** (~1:38:30):
> "There is an edit button right now, but it is not functioning."

**Travis on workaround for contacts** (~1:34:01):
> "If we can get the body of it, that would still help Callie out tremendously... while you're working on the API key for that, we just manually put in the emails."

**Callie on manual email paste** (~1:34:12):
> "That doesn't take too long because I just copy and paste the ones I find most appropriate."

**Travis on scheduling** (~09:14):
> "We usually do a schedule send on the emails. Can you do the same thing through here?"

**Joe on scheduling** (~09:19):
> "I might not be able to right now, but I can probably literally fix that by the end of the conversation."

---

## Suggested Agent Prompts for All Subsequent Waves

### Wave 1: Config & Tier Fix Agent
```
ROLE: Configuration Fixer
OBJECTIVE: Consolidate tiers from 5 to 3 in config.yaml and all related source files.
INPUT: config.yaml, src/models.py, src/tier_classifier.py, app.py (TIER_COLORS dict)
CHANGES:
  T1 -> Coming Due: min=-7, max=0
  T2 -> 1-29 Days Past Due: min=1, max=29
  T3 -> 30+ Days Past Due: min=30, max=999 (single template, dynamic subject)
  REMOVE T4 and T5 entirely.
  Update Tier enum, TIER_COLORS, TIER_METADATA, classify() function.
  Ensure no references to T4/T5 remain in any file.
OUTPUT: Modified config.yaml, models.py, tier_classifier.py, app.py
```

### Wave 1: Template Alignment Agent
```
ROLE: Template Aligner
OBJECTIVE: Replace all email templates with Callie's canonical versions.
INPUT: Templates Callie emailed (need to find or recreate from meeting context)
  - templates/coming_due.html
  - templates/overdue.html (rename to match "1-29 Days Past Due")
  - templates/past_due_30.html (single template for all 30+)
CHANGES:
  Remove: past_due_40.html, past_due_50.html
  Ensure NO "final notice" text in any template
  Add dynamic OCM deadline warning to 30+ template
  Verify all variable placeholders use bracketed format
OUTPUT: 3 clean HTML templates
```

### Wave 1: Subject Line Dynamic Agent
```
ROLE: Subject Line Fixer
OBJECTIVE: Make subject lines dynamic for 30+ tier
INPUT: config.yaml subject_line section, src/template_engine.py
CHANGES:
  For 30+ tier, compute label based on actual days:
    30-39 days -> "30+ Days Past Due"
    40-49 days -> "40+ Days Past Due"
    50-59 days -> "50+ Days Past Due"
    60+ days -> "60+ Days Past Due"
  Keep format: "PICC - {store} - Nabis Invoice {num} - {dynamic_label}"
OUTPUT: Updated template_engine.py and/or config handling
```

### Wave 1: UI Persistence Agent
```
ROLE: Settings Persistence Fixer
OBJECTIVE: Ensure settings changes persist across regeneration
INPUT: app.py render_settings_page(), init_session_state()
CHANGES:
  Add "Save Settings" button that writes to config.yaml
  Ensure tier boundary changes in Settings survive "Generate Emails"
  Fix "From" display to use sender_name instead of hardcoded "Laura"
  Verify Quick Edit To/CC/Subject save actually works (code review shows it should)
OUTPUT: Updated app.py settings page with persistence
```

### Wave 2: Validation & Grep Agent
```
ROLE: Final Notice Eliminator
OBJECTIVE: Find and remove ALL instances of "final notice" from the entire codebase
INPUT: All .py, .html, .yaml, .md files in ar-email-automation/
COMMAND: grep -ri "final.notice" across all files
OUTPUT: List of all occurrences and confirmation they are removed
```

### Wave 2: Testing Agent
```
ROLE: Parallel Test Validator
OBJECTIVE: Generate emails from current XLSX and compare against expected output
INPUT: data/NY Account Receivables_Overdue.xlsx, templates, config
PROCESS:
  1. Run the tool with current data
  2. Check each generated email for:
     - Correct tier assignment
     - Correct template body
     - Correct subject line format
     - Nabis AM populated correctly
     - No "final notice" text
     - Signature shows correct sender name
OUTPUT: Validation report with pass/fail per email
```

---

## Appendix: Code Architecture Assessment

The codebase is well-structured for rapid iteration:

```
ar-email-automation/
  app.py              -- 2069 lines, monolithic Streamlit UI (clean, well-organized)
  config.yaml         -- 243 lines, externalized configuration (good)
  src/
    models.py         -- Core dataclasses (Invoice, Contact, EmailDraft, EmailQueue, Tier enum)
    config.py         -- Config loading from YAML
    data_loader.py    -- XLSX parsing -> Invoice objects
    tier_classifier.py -- Days -> Tier mapping
    contact_resolver.py -- Contact lookup (currently from XLSX only)
    template_engine.py -- Jinja2 HTML email rendering
  templates/          -- HTML email templates (Jinja2)
  data/               -- XLSX files, ACH PDF
  output/             -- Generated .eml files
```

All 6 src modules are present and loading (verified via code and Glob). The graceful import pattern in `app.py` means individual modules can be updated without breaking the whole app.

**Key finding from code review**: The Quick Edit functionality (lines 1411-1468 in app.py) DOES already work for editing To, CC, and Subject fields per-email. The meeting quote about "edit button not functioning" may refer to the Settings page persistence, not the per-email edit. This is good news -- P0-3 (recipient editing workaround) may already be partially solved.
