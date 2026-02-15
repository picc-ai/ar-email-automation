# Template Rebuild Report
## Document: 11 - Template Rebuild (Wave 2 Build)
## Timestamp: 2026-02-14
## Agent: Wave 2 Template Rebuilder (Opus)

---

## Status: COMPLETE

## Summary

Collapsed the 5-tier email template system to 3 tiers with canonical body text from Callie's PDFs. Deleted AI-fabricated T4 (40+) and T5 (50+) templates. Removed all "final notice", "ACTION REQUIRED", "second notice", account hold, and collection threat language from source code, templates, config, and user guide.

---

## Changes Made

### 1. templates/coming_due.html -- REBUILT
- [x] Replaced body with EXACT canonical text from Callie's PDF
- [x] Fixed attachment line: "Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." (was "Attached is...")
- [x] Fixed comment: trigger range now says "-7 to 0 days" (was "within 3 days")
- [x] Removed AI-generated CHANGE LOG comment
- [x] Removed multi-invoice scaffold comments ({{#EACH INVOICE}})
- [x] Preserved: Jinja2 variables ({{CONTACT_FIRST_NAME}}, {{STORE_NAME}}, {{INVOICE_NUMBER}}, {{DUE_DATE}}, {{AMOUNT}}, {{NABIS_AM_NAME}}, {{NABIS_AM_PHONE}}, {{SENDER_NAME}}, {{SENDER_TITLE}})
- [x] Preserved: Signature block, confidentiality notice

### 2. templates/overdue.html -- REBUILT
- [x] Replaced `{{OVERDUE_TIMEFRAME}}` with static "overdue" per Callie's Feb 11 fix email
- [x] Fixed trigger range to "1-29 days past due" (was "4-29 days past due")
- [x] Removed OVERDUE_TIMEFRAME comment block with dynamic ranges
- [x] Removed multi-invoice separator block ({{#IF HAS_ADDITIONAL_INVOICES}})
- [x] Removed {{INVOICE_NOTE}} variable from Amount line
- [x] Body text now exactly matches canonical corrected version
- [x] Preserved: Attachment line with comma ("Attached, you'll find...")

### 3. templates/past_due_30.html -- REBUILT (canonical body for ALL 30+ day emails)
- [x] Removed AI-fabricated "payment terms reminder" paragraph ("As a reminder, our standard payment terms...")
- [x] Fixed attachment line to canonical: "Attached you'll find..." (was "Attached is...")
- [x] Fixed "past-due invoice" to "past-due invoices" (canonical plural)
- [x] Added {{DAYS_PAST_DUE_BUCKET}} variable in HTML title for dynamic subject reference
- [x] Bullet order matches canonical: Invoice, Due, Nabis AM, Amount
- [x] Nabis AM separator uses dash (-) per canonical
- [x] Closing uses em dash (--) matching canonical
- [x] Comment header updated: trigger now says "30+ days past due (covers 30+, 40+, 50+, 60+, etc.)"
- [x] Comment explicitly states: No "second notice", "final notice", "ACTION REQUIRED", account holds, or collection threats. Ever.

### 4. templates/past_due_40.html -- DELETED
- [x] File removed via `rm` command
- [x] AI-fabricated content removed: "second notice", "ACTION REQUIRED", OCM countdown, account hold warning, payment deadline ultimatum

### 5. templates/past_due_50.html -- DELETED
- [x] File removed via `rm` command
- [x] AI-fabricated content removed: "final notice", "FINAL NOTICE", red warning box, account flag, collections/legal threats, 48-hour ultimatum, sender escalation

### 6. src/template_engine.py -- UPDATED
- [x] Removed "ACTION REQUIRED" and "FINAL NOTICE" suffix logic from `build_subject_line()` (lines 202-208)
- [x] Added dynamic subject label computation in `render_email()`: `floor(days/10)*10 + "+ Days Past Due"` for 30+ invoices
- [x] Removed `_get_ocm_status_phrase()` function (AI-fabricated T5-specific)
- [x] Removed `_T4_DEADLINE_BIZ_DAYS` and `_T5_DEADLINE_BIZ_DAYS` constants, replaced with `_PAST_DUE_DEADLINE_BIZ_DAYS = 7`
- [x] Removed `get_overdue_timeframe_description` import from tier_classifier
- [x] Replaced T2 context `OVERDUE_TIMEFRAME` from dynamic calculation to static `"overdue"`
- [x] Added `DAYS_PAST_DUE_BUCKET` variable to context for 30+ emails
- [x] Moved payment deadline logic from T4-specific to all 30+ emails
- [x] Removed T5-specific context building (`OCM_STATUS_PHRASE`, `FINAL_PAYMENT_DEADLINE`)
- [x] Removed T4/T5 CC escalation blocks (store owner/AP contacts, additional stakeholders)
- [x] Removed sender_override escalation in `_resolve_sender()` -- all tiers use default sender
- [x] Updated self-test block: T5 test replaced with T3 test (111 days -> "110+ Days Past Due")
- [x] Removed "FINAL NOTICE" from subject line builder self-test
- [x] Removed OCM status phrases self-test
- [x] Updated all docstrings to reflect 3-tier system

### 7. src/config.py -- UPDATED
- [x] Collapsed `DEFAULT_TIERS` from 5 entries to 3 (T1, T2, T3)
- [x] Fixed T1 boundaries: min=-7, max=0 (was min=-3, max=3)
- [x] Fixed T2 boundaries: min=1, max=29 (was min=4, max=29)
- [x] Set T3 boundaries: min=30, max=999 (unbounded)
- [x] Removed `sender_override` from all tiers
- [x] Removed T4 and T5 from `tier_extra_cc` dict
- [x] Removed T4 and T5 from `tier_attachments` dict
- [x] Updated `tier_gte_management_escalation` from "T5" to "T3"
- [x] Updated EscalationSender docstring to note unused in 3-tier system

### 8. USER_GUIDE.md -- UPDATED
- [x] Collapsed tier table from 5 rows to 3 rows
- [x] Removed "ACTION REQUIRED" reference from 40+ tier description
- [x] Removed "Final notice" reference from 50+ tier description
- [x] Updated tier badge descriptions: only 3 badges (Green, Yellow, Red)
- [x] Updated tier column description to show 3 tiers

---

## Global "Final Notice" Verification

Grepped entire project for prohibited language. Results:

### In source code (src/) and templates/ -- CLEAN
- `final notice` / `FINAL NOTICE`: Only appears in comments explicitly stating NOT to use it
- `ACTION REQUIRED`: Only appears in comments explicitly stating NOT to use it
- `second notice`: Only appears in comment prohibiting it
- `past_due_40` / `past_due_50`: Zero matches in src/

### In analysis/planning docs (swarm/) -- ACCEPTABLE
- Historical references exist in Wave 0 and Wave 1 analysis reports documenting what was wrong and what to remove. These are internal documentation, not sendable content.

### In USER_GUIDE.md -- FIXED
- Removed all references to "ACTION REQUIRED" and "final notice" from user-facing documentation

---

## Template File Inventory (After)

| File | Status | Lines |
|------|--------|-------|
| `templates/coming_due.html` | Rebuilt with canonical text | 112 |
| `templates/overdue.html` | Rebuilt with canonical corrected text | 114 |
| `templates/past_due_30.html` | Rebuilt with canonical text (single body for ALL 30+) | 145 |
| `templates/past_due_40.html` | **DELETED** | - |
| `templates/past_due_50.html` | **DELETED** | - |

---

## Canonical Text Fidelity Check

| Template | Canonical Element | Matches PDF? |
|----------|------------------|--------------|
| T1 Greeting | "Hello [person/s]," -> "Hello {{CONTACT_FIRST_NAME}}," | YES |
| T1 Opener | "I hope you're well. This is a courtesy reminder..." | YES (exact) |
| T1 Attachment | "Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | YES (fixed) |
| T1 Closing | "Thank you for your business. You're much appreciated. Have a great day!" | YES (exact) |
| T2 Opener | "I hope you're having a great day." | YES (exact) |
| T2 Overdue phrase | "your invoice is overdue" (static, per fix PDF) | YES (fixed) |
| T2 Attachment | "Attached, you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | YES (exact, with comma) |
| T2 Closing | "Please let us know if there's anything we can do to assist you." | YES (exact) |
| T3 OCM warning | "While their email notifications are typically issued at 45 days..." | YES (exact) |
| T3 Bullet order | Invoice, Due, Nabis AM, Amount | YES (canonical order) |
| T3 Attachment | "Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | YES (fixed) |
| T3 Payment request | "past-due invoices" (plural) | YES (fixed) |
| T3 Closing | "Thank you for your prompt attention to this matter--we truly value..." | YES (exact) |
| T3 Sign-off | "Regards," | YES (exact) |

---

## Variables Available Per Template

### coming_due.html
- `{{CONTACT_FIRST_NAME}}` -- Contact first name or "Team"
- `{{STORE_NAME}}` -- Retailer name
- `{{INVOICE_NUMBER}}` -- Invoice number
- `{{DUE_DATE}}` -- Formatted date (Mon DD, YYYY)
- `{{AMOUNT}}` -- Formatted currency ($X,XXX.XX)
- `{{NABIS_AM_NAME}}` -- Account manager name
- `{{NABIS_AM_PHONE}}` -- Account manager phone
- `{{SENDER_NAME}}` -- Sender name
- `{{SENDER_TITLE}}` -- Sender title

### overdue.html
Same variables as coming_due.html.

### past_due_30.html
Same variables as coming_due.html, plus:
- `{{DAYS_PAST_DUE_BUCKET}}` -- Dynamic label (e.g., "30+ Days Past Due", "40+ Days Past Due")
- `{{PAYMENT_DEADLINE}}` -- Computed deadline date (provided by template_engine.py)
- `{{DAYS_PAST_DUE}}` -- Raw days past due number

---

*End of Report 11 - Template Rebuild*
