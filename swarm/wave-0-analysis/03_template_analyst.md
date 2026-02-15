# Template & Tier Analyst Report
## Report: 03 - Template Specification
## Timestamp: 2026-02-14
## Agent: Wave 0 Agent 3 (opus)
## Input files read:
- `A:\Downloads\AR Email Automation meeting (1).srt` (meeting transcript, partial reads covering template/tier/subject discussions)
- `A:\Downloads\Action items.md` (full)
- `A:\Downloads\picc Mail - A_R Email Formatting.pdf` (canonical templates - source of truth)
- `A:\Downloads\picc Mail - RE_ 1-29 Day Email Body fix.pdf` (corrected 1-29 day body)
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\coming_due.html`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\overdue.html`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\past_due_30.html`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\past_due_40.html`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\templates\past_due_50.html`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\tier_classifier.py`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\models.py`
- `C:\Users\smith\Antigravity\PICC Projects\ar-email-automation\src\template_engine.py`

## Verdict: SIGNIFICANT STRUCTURAL MISMATCH -- App has 5 tiers with heavily AI-embellished bodies; canonical spec requires exactly 3 tiers with a SINGLE body for all 30+ day emails and dynamic subject lines only. Templates need to be rebuilt from canonical PDF text, not patched.

---

## Executive Summary

The current app implements a **5-tier system** (Coming Due, Overdue, 30+, 40+, 50+) with five distinct, progressively escalating HTML template bodies. The meeting and canonical emails from Kali establish that there should be exactly **3 templates** with **3 body variants**:

1. **Coming Due** (-7 to 0 days) -- its own body
2. **1-29 Days Past Due / Overdue** (1 to 29 days) -- its own body (with a corrected wording fix)
3. **30+ Days Past Due** (30+ days) -- a SINGLE body used for ALL invoices 30+ days past due, with only the **subject line** varying dynamically (30+, 40+, 50+ etc.)

The app's 40+ and 50+ templates are entirely AI-fabricated escalation content (second notice, final notice, account holds, collections threats, red-styled warnings) that **never existed in Kali's canonical templates** and must be removed.

Additionally, the 1-29 Day body has a specific correction from the fix PDF: "nearing two weeks past due" must be changed to just "overdue" in the body text.

---

## 1. Canonical Template Text (from PDFs)

### 1.1 Coming Due Template (from A/R Email Formatting PDF)

**Title/Label:** PICC A/R Payment Coming Due Reminder

**Subject Line:**
```
PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Coming Due
```

**Body (exact canonical text):**
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

### 1.2 1-29 Day Overdue Template (CORRECTED per fix PDF)

**Title/Label:** PICC A/R Payment 1-29 Days Past Due

**Subject Line:**
```
PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - Overdue
```

**Body (corrected canonical text -- fix PDF changes "nearing two weeks past due" to "overdue"):**
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

**CRITICAL CORRECTION from fix PDF:** The original PDF had "This is a friendly reminder that your invoice is nearing two weeks past due." Kali's follow-up email (RE: 1-29 Day Email Body fix.pdf, Feb 11, 2026) specifically struck through "nearing two weeks past due" and noted it should be just "overdue" -- because this template covers 1-29 days, and saying "nearing two weeks" is only accurate for a narrow window.

### 1.3 30+ Days Past Due Template (from A/R Email Formatting PDF)

**Title/Label:** PICC A/R Payment 30 Days Past Due

**Subject Line (DYNAMIC -- changes based on actual days tier):**
```
PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - 30+ Days Past Due
PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - 40+ Days Past Due
PICC - [Dispensary Name (Location-if multiple)] - Nabis Invoice [Invoice Number] - 50+ Days Past Due
```

**Body (exact canonical text -- SINGLE body for all 30+ day invoices):**
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

**NOTE on bullet point order:** In the 30+ template, the canonical order is: Invoice/Order, Due, **Nabis Account Manager**, Amount. This differs from Tier 1 and Tier 2 where Amount comes before Nabis Account Manager.

---

## 2. Current App Templates -- Summary

### 2.1 coming_due.html (T1)
- Generally close to canonical
- Uses `{{CONTACT_FIRST_NAME}}` instead of `[person/s]`
- Attachment line says "Attached is" instead of canonical "Attached you'll find"
- Includes multi-invoice scaffold comments ({{#EACH INVOICE}}) -- not in canonical
- Has a CHANGE LOG comment documenting AI modifications
- Includes `{{SENDER_NAME}}`, `{{SENDER_TITLE}}` signature block

### 2.2 overdue.html (T2)
- Has AI-added `{{OVERDUE_TIMEFRAME}}` dynamic variable with ranges (4-10: "now past due", 11-17: "nearing two weeks past due", 18-24: "over two weeks past due", 25-29: "over three weeks past due")
- Canonical says simply "overdue" (per fix PDF correction)
- Has multi-invoice separator block with {{#IF HAS_ADDITIONAL_INVOICES}}
- Has `{{INVOICE_NOTE}}` variable -- not in canonical

### 2.3 past_due_30.html (T3)
- Body is close to canonical BUT has an **EXTRA paragraph** not in canonical:
  > "As a reminder, our standard payment terms require invoices to be settled within the agreed timeframe. This invoice is now over 30 days past due."
- Attachment line says "Attached is" instead of "Attached you'll find"
- Nabis AM separator uses " - " (dash) while canonical uses " - " in the bullet (same in practice)
- "past-due invoice" (singular) vs canonical "past-due invoices" (plural)
- Uses em dash in closing ("--") instead of canonical em dash ("--")

### 2.4 past_due_40.html (T4) -- ENTIRELY AI-FABRICATED
- Does NOT exist in canonical. This is a fabricated escalation tier.
- Adds "second notice" language
- Adds bold "Your account is approaching the OCM reporting threshold"
- Adds `{{DAYS_UNTIL_OCM_REPORT}}` countdown
- Adds "Days Past Due" as a bullet item -- not in any canonical template
- Adds account hold warning ("continued non-payment may result in a hold")
- Adds explicit deadline: "We request that payment be submitted by {{PAYMENT_DEADLINE}}"
- Subject adds "- ACTION REQUIRED" suffix
- Complete fabrication -- must be removed as a distinct body

### 2.5 past_due_50.html (T5) -- ENTIRELY AI-FABRICATED
- Does NOT exist in canonical. This is a fabricated escalation tier.
- Adds "This is a final notice" language -- **explicitly prohibited** by meeting decision
- Adds red-bordered warning box with `{{OCM_STATUS_PHRASE}}`
- Changes "According to our records" to "The outstanding invoice details are as follows"
- Adds red-colored days past due and amount
- "Original Due Date" label instead of "Due"
- "Amount Due" label instead of "Amount"
- Adds account flag/hold statement as active (not potential)
- Adds collections/legal threat language
- Adds `{{FINAL_PAYMENT_DEADLINE}}` with 48-hour ultimatum
- Subject adds "- FINAL NOTICE" suffix -- **explicitly prohibited**
- Complete fabrication -- must be removed as a distinct body

---

## 3. Current App vs Canonical: Diff Report

| # | Section | Canonical (PDF) | Current App | Action Required |
|---|---------|----------------|-------------|-----------------|
| 1 | **Number of tiers** | 3 (Coming Due, 1-29 Overdue, 30+ Past Due) | 5 (Coming Due, Overdue, 30+, 40+, 50+) | Collapse to 3 body templates; keep dynamic subject |
| 2 | **T1 greeting** | `Hello [person/s],` | `Hello {{CONTACT_FIRST_NAME}},` | Keep app's Jinja2 variable -- maps `[person/s]` to contact name |
| 3 | **T1 attachment line** | "Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | "Attached is the Nabis ACH payment form (PDF) to facilitate your payment." | Fix to match canonical exactly |
| 4 | **T2 overdue phrase** | "your invoice is overdue" (per fix PDF) | "your invoice is {{OVERDUE_TIMEFRAME}}" with 6 dynamic ranges | **Remove dynamic timeframe.** Replace with static "overdue" per Kali's correction |
| 5 | **T2 attachment line** | "Attached, you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | Matches canonical (includes comma after "Attached") | OK -- no change needed |
| 6 | **T3 extra paragraph** | Not present | "As a reminder, our standard payment terms require invoices to be settled within the agreed timeframe. This invoice is now over 30 days past due." | **Remove** -- not in canonical |
| 7 | **T3 attachment line** | "Attached you'll find the Nabis ACH payment form (PDF) to help facilitate your payment." | "Attached is the Nabis ACH payment form (PDF) to facilitate your payment." | Fix to match canonical |
| 8 | **T3 invoice singular/plural** | "past-due invoices" (plural) | "past-due invoice" (singular) | Fix to canonical plural |
| 9 | **T3 bullet order** | Invoice, Due, Nabis AM, Amount | Invoice, Due, Nabis AM, Amount | Matches canonical -- OK |
| 10 | **T4 template (40+ body)** | Does not exist | Full AI-fabricated escalation email | **Delete** -- use T3 body with dynamic subject |
| 11 | **T5 template (50+ body)** | Does not exist | Full AI-fabricated escalation email | **Delete** -- use T3 body with dynamic subject |
| 12 | **"Final notice" language** | Never used, explicitly banned | T5 subject: "FINAL NOTICE", T5 body: "This is a final notice" | **Remove all instances** |
| 13 | **"ACTION REQUIRED" language** | Never used | T4 subject: "ACTION REQUIRED" | **Remove** |
| 14 | **"Second notice" language** | Never used | T4 body: "This is a second notice" | **Remove** |
| 15 | **Account hold warnings** | Never used | T4: "continued non-payment may result in a hold"; T5: "account has been flagged and future orders may not be processed" | **Remove** |
| 16 | **Collections/legal threats** | Never used | T5: "refer this matter for further collection action" | **Remove** |
| 17 | **Red-styled warning boxes** | Not in canonical | T5: red border-left box with OCM status | Remove as standalone; meeting says red-bar style is OK for 30+ if using canonical wording |
| 18 | **Dynamic payment deadline** | Not in canonical | T4: {{PAYMENT_DEADLINE}}, T5: {{FINAL_PAYMENT_DEADLINE}} | Meeting liked this feature for 30+ -- add to merged 30+ template |
| 19 | **Closing sign-off** | "Regards," (T3 only) | "Regards," (T3-T5) | Keep "Regards," for 30+ template |
| 20 | **T1 closing** | "Thank you for your business. You're much appreciated. Have a great day!" | Matches | OK |
| 21 | **T2 closing** | "Please let us know if there's anything we can do to assist you." | Matches | OK |

---

## 4. Three-Tier Specification

| Tier | Name | Days Range | Subject Format | Body Template File | Body Source |
|------|------|-----------|----------------|-------------------|-------------|
| **T1** | Coming Due | -7 to 0 | `PICC - {{STORE_NAME}} - Nabis Invoice {{INVOICE_NUMBER}} - Coming Due` | `coming_due.html` | Canonical PDF |
| **T2** | 1-29 Days Past Due | 1 to 29 | `PICC - {{STORE_NAME}} - Nabis Invoice {{INVOICE_NUMBER}} - Overdue` | `overdue.html` | Canonical PDF + fix PDF correction |
| **T3** | 30+ Days Past Due | 30+ | `PICC - {{STORE_NAME}} - Nabis Invoice {{INVOICE_NUMBER}} - {{DYNAMIC_DAYS_LABEL}}` | `past_due_30.html` (single file) | Canonical PDF |

### T3 Dynamic Subject Line Tiers

The 30+ template uses ONE body but the subject line dynamically reflects the days-past-due tier:

| Days Past Due | Subject Line Suffix | Example |
|--------------|--------------------|---------|
| 30-39 | `30+ Days Past Due` | `PICC - Green Garden - Nabis Invoice 903480 - 30+ Days Past Due` |
| 40-49 | `40+ Days Past Due` | `PICC - Green Garden - Nabis Invoice 903480 - 40+ Days Past Due` |
| 50-59 | `50+ Days Past Due` | `PICC - Green Garden - Nabis Invoice 903480 - 50+ Days Past Due` |
| 60-69 | `60+ Days Past Due` | `PICC - Green Garden - Nabis Invoice 903480 - 60+ Days Past Due` |
| 70-79 | `70+ Days Past Due` | `PICC - Green Garden - Nabis Invoice 903480 - 70+ Days Past Due` |
| 80+ | `80+ Days Past Due` | (continues in 10-day increments) |

The subject tier label is calculated as: `floor(days_past_due / 10) * 10` when >= 30.

**No "ACTION REQUIRED" suffix. No "FINAL NOTICE" suffix. Ever.**

---

## 5. Variable Mapping

### Placeholders from Canonical Templates

| Placeholder in Template | Jinja2 Variable | Data Source | Notes |
|------------------------|-----------------|-------------|-------|
| `[Dispensary Name (Location-if multiple)]` | `{{STORE_NAME}}` | XLSX: Location (col B) / Nabis retailer name | Include location suffix if multi-location retailer |
| `[Invoice Number]` | `{{INVOICE_NUMBER}}` | XLSX: Order No (col A) | Stored as string for display |
| `[person/s]` | `{{CONTACT_FIRST_NAME}}` | Managers sheet: POC Name (col D), first name extracted | Falls back to "Team" if no contact |
| `[Date Due]` | `{{DUE_DATE}}` | XLSX: Due Date (col I) | Format: "Feb 05, 2026" |
| `[Amount]` | `{{AMOUNT}}` | XLSX: Total Due (col K) | Format: "$1,510.00" |
| `[Name - Phone]` | `{{NABIS_AM_NAME}} - {{NABIS_AM_PHONE}}` | XLSX: Account Manager (col C) + Phone (col D) | Dash separator between name and phone in T3, space in T1/T2 |
| *(subject line days label)* | `{{DAYS_LABEL}}` | Calculated from days_past_due | "Coming Due", "Overdue", "30+ Days Past Due", "40+ Days Past Due", etc. |

### Additional Computed Variables (for enhanced 30+ template per meeting decisions)

| Variable | Purpose | Calculation |
|----------|---------|-------------|
| `{{DYNAMIC_DAYS_LABEL}}` | Subject line suffix for 30+ | `floor(days/10)*10` + "+ Days Past Due" |
| `{{PAYMENT_DEADLINE_DATE}}` | Dynamic deadline date | due_date + 52 days (OCM threshold) or send_date + 7 business days, whichever is earlier |

### Sender Signature Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `{{SENDER_NAME}}` | e.g., "Kali Speerstra" | From config |
| `{{SENDER_TITLE}}` | e.g., "New York Sales Admin" | From config |

---

## 6. "Final Notice" Instances to Remove

### In Templates

| File | Location | Text | Action |
|------|----------|------|--------|
| `past_due_50.html` | Line 7 (comment) | `Tier: T5 - 50+ Days Past Due` | Remove entire template file |
| `past_due_50.html` | Line 19 | Subject: `- FINAL NOTICE` | Remove |
| `past_due_50.html` | Line 23 | `"FINAL NOTICE" language` | Remove |
| `past_due_50.html` | Line 55 | Body: `<strong>This is a final notice</strong>` | Remove |
| `past_due_40.html` | Line 18 | Subject: `- ACTION REQUIRED` | Remove |
| `past_due_40.html` | Line 51 | Body: `This is a <strong>second notice</strong>` | Remove |

### In Code

| File | Location | Text | Action |
|------|----------|------|--------|
| `tier_classifier.py` line 38 | Tier enum | `PAST_DUE_50 = "50+ Days Past Due"` | Remove as distinct tier; fold into PAST_DUE_30 logic |
| `tier_classifier.py` line 37 | Tier enum | `PAST_DUE_40 = "40+ Days Past Due"` | Remove as distinct tier; fold into PAST_DUE_30 logic |
| `template_engine.py` line 206 | Subject builder | `"40+ Days Past Due" ... "ACTION REQUIRED"` | Remove ACTION REQUIRED suffix |
| `template_engine.py` line 207 | Subject builder | `"50+ Days Past Due" ... "FINAL NOTICE"` | Remove FINAL NOTICE suffix |
| `models.py` line 42 | Tier enum | `T3 = "40+ Days Past Due"` | Remove as distinct tier |
| `models.py` line 43 | Tier enum | `T4 = "50+ Days Past Due"` | Remove as distinct tier |

---

## 7. Current Code Analysis

### 7.1 tier_classifier.py

**Current behavior:** Defines 5 tiers via `Tier(str, Enum)`:
- `COMING_DUE` = <= 0 days
- `OVERDUE` = 1-29 days
- `PAST_DUE_30` = 30-39 days
- `PAST_DUE_40` = 40-49 days
- `PAST_DUE_50` = 50+ days

Each tier has separate `TierMetadata` with different `template_name`, `urgency_level`, `cc_rules`, and `subject_label`.

**What needs to change:**
1. **Reduce to 3 tiers in the enum:** `COMING_DUE`, `OVERDUE`, `PAST_DUE` (covers 30+)
2. **Subject label for PAST_DUE must be dynamically calculated**, not static. The tier's subject_label should be computed from the actual days_past_due value, not from the tier enum.
3. **Remove `PAST_DUE_40` and `PAST_DUE_50`** from the Tier enum and all TIER_METADATA entries.
4. **Remove `get_overdue_timeframe_description()`** -- the canonical template uses static "overdue" (per fix PDF). If the team later wants this back, it can be re-added, but current canonical says no.
5. **Update `classify()`** to map 30+ to a single `PAST_DUE` tier.
6. **Add a helper function** to compute the dynamic subject label: `get_dynamic_subject_label(days_past_due) -> str` that returns "30+ Days Past Due", "40+ Days Past Due", etc.

### 7.2 models.py

**Current behavior:** Has its own independent `Tier` enum (distinct from tier_classifier.py's):
```python
class Tier(Enum):
    T0 = "Coming Due"
    T1 = "Overdue"
    T2 = "30+ Days Past Due"
    T3 = "40+ Days Past Due"
    T4 = "50+ Days Past Due"
```

Also has `TierConfig.default_tiers()` returning 5 configs with 5 template names.

**What needs to change:**
1. **Consolidate to 3 tiers:**
   ```python
   class Tier(Enum):
       T0 = "Coming Due"
       T1 = "Overdue"
       T2 = "30+ Days Past Due"
   ```
2. **Remove T3 and T4 from the enum and from `default_tiers()`.**
3. **Update `TierConfig.default_tiers()`** to return 3 entries with `max_days=None` for T2 (30+).
4. **Fix the dual-Tier-enum problem**: `models.py` and `tier_classifier.py` each define their own `Tier` enum. This should be consolidated into a single source of truth (likely models.py).

### 7.3 template_engine.py

**Current behavior:**
- `TemplateEngine._build_context()` calculates different variables for different tiers (T2 gets OVERDUE_TIMEFRAME, T4 gets DAYS_UNTIL_OCM_REPORT, T5 gets OCM_STATUS_PHRASE).
- `build_subject_line()` appends "- ACTION REQUIRED" for T4 and "- FINAL NOTICE" for T5.
- Uses `_SanitizingFileLoader` to strip pseudo-template markers from HTML comments.
- Has `_get_ocm_status_phrase()` and `_get_days_until_ocm()` for T5-specific content.

**What needs to change:**
1. **`build_subject_line()`**: Remove all "ACTION REQUIRED" and "FINAL NOTICE" suffixes. The `tier_label` parameter should receive the dynamic label (e.g., "40+ Days Past Due") directly.
2. **Add dynamic subject label calculation**: Instead of passing a static tier label, compute `f"{floor(days/10)*10}+ Days Past Due"` when days >= 30.
3. **Remove T4/T5-specific context building**: No more `DAYS_UNTIL_OCM_REPORT`, `OCM_STATUS_PHRASE`, `FINAL_PAYMENT_DEADLINE` as distinct tier variables.
4. **Keep `PAYMENT_DEADLINE_DATE`** as a variable for the merged 30+ template (meeting approved this feature).
5. **Remove `OVERDUE_TIMEFRAME`** dynamic ranges -- replace with static "overdue" for T2.
6. **Remove T5 sender escalation logic** (`_resolve_sender` escalation to Regional Account Manager).

---

## 8. Subject Line Logic

### Meeting Discussion Summary

The meeting had extensive discussion about subject lines (transcript sections around 55:03 - 59:00):

**Key quotes (paraphrased from transcript):**

1. **Travis (timestamp ~55:00):** "No final notice shit." / "Remove final notice from all email bodies."
2. **Travis (timestamp ~55:10):** "Remove 'this is a final notice' from all the email bodies because we're always just going to keep sending them until the sun burns out."
3. **Kali (timestamp ~56:44):** When asked what she puts in the subject for 45 days past due: "I would've just done 40 plus."
4. **Travis (timestamp ~57:15):** "A note, what we want in the subject line is that to be dynamic."
5. **Travis (timestamp ~57:22):** "We basically keep the tiered system... but the body of everything for the last three tiers is the same except for the subject, then just the subject will be different."
6. **Travis (timestamp ~58:33):** "Can we make the subject dynamic?" followed by Joe confirming: "Subject will be dynamic."
7. **Travis (timestamp ~58:42):** "Subject will be dynamic. Body wouldn't."

**Key decisions on subject lines:**
- Subjects use tiered day labels: 30+, 40+, 50+, 60+, etc.
- No exact day counts (e.g., NOT "47 Days Past Due" -- that was "too cumbersome")
- No "FINAL NOTICE" or "ACTION REQUIRED" suffixes
- The format is always: `PICC - [Store] - Nabis Invoice [#] - [X+ Days Past Due]`

### Dynamic vs Tiered

The meeting resolved that subjects are **tiered but dynamically selected** -- meaning the tier label in the subject line changes based on the days_past_due value, but always in 10-day increments (30+, 40+, 50+, 60+, etc.). This is "dynamic" in the sense that the label is computed, not manually assigned, but "tiered" in the sense that it rounds to increments.

---

## 9. Key Meeting Quotes on Templates

| Timestamp | Speaker | Quote | Significance |
|-----------|---------|-------|--------------|
| ~22:25 | Travis | "The label? Like, the template? The subject line." | Clarifying that "label" != "template" |
| ~23:01 | Travis | "So, 1 is the coming dues correct, right? Negative 7 to negative 1 is the coming dues." | Confirming T1 bounds |
| ~23:07 | Kali | "Then the 0 to 30, what do we call that template? I believe that one is just overdue." | Confirming T2 name |
| ~25:08 | Kali | "Is there another one? ... We would use the same body... nothing in the body really relates to the amount of days. So we would use the same body. But change the subject line to match 30, 40, or 50." | **Definitive: single body for 30+** |
| ~25:55 | Kali | "Even if they're 80 days past due, we just send them that one." | No upper bound on 30+ template |
| ~27:53 | Travis | "Basically, then you have basically three templates... Coming due, 1 to 29 days past due, and then 30 plus days past due." Kali: "Correct." | **Definitive: 3 templates** |
| ~28:52 | Travis | "That way we know these are the templates of truth." | Canonical email from Kali = source of truth |
| ~48:30 | Kali | "I don't think we ever said final notice." | Final notice was AI-invented |
| ~55:00 | Travis | "No final notice shit." | Remove all final notice language |
| ~55:10 | Travis | "Remove 'this is a final notice' from all email bodies because we're always just going to keep sending them until the sun burns out." | Rationale: there is no "final" email |
| ~57:15 | Travis | "What we want in the subject line is that to be dynamic." | Subject = dynamic |
| ~58:42 | Joe | "Subject will be dynamic. Body wouldn't." | Subject dynamic, body static for 30+ |

---

## 10. Meeting-Approved Enhancements Beyond Canonical

While the canonical templates from Kali are the source of truth for the body text, the meeting approved certain **enhancements** that should be incorporated into the 30+ template:

1. **Dynamic payment deadline date** (Travis, ~51:20-51:55): "I want to be putting that [deadline date] on all the 30 plus emails." This was the `{{PAYMENT_DEADLINE}}` feature from the T4 template that Travis liked.

2. **Red-bar OCM warning section** (Travis, ~54:30): "I liked that though" / "Let's keep that. So all the 30 plus, we make it red and we just condense it." -- The red-bordered warning bar from the 50+ template was liked, but it should use the canonical OCM warning text, not the AI-escalated text.

3. **Nabis AM CC'd on 30+ emails** (from canonical template text): "Your Nabis account manager is CC'd on this email and can help with processing." -- This is already in the canonical template.

---

## 11. Suggested Agent Prompts for Wave 2 Template Build

### Prompt 1: Template Rebuilder Agent

```
ROLE: Template Rebuilder
OBJECTIVE: Rebuild the 3 HTML email templates from canonical text.

INPUT: Read report 03_template_analyst.md for canonical text and variable mappings.

ACTIONS:
1. Rebuild coming_due.html using Section 1.1 canonical text
   - Replace [Dispensary Name] with {{STORE_NAME}}
   - Replace [Invoice Number] with {{INVOICE_NUMBER}}
   - Replace [person/s] with {{CONTACT_FIRST_NAME}}
   - Replace [Date Due] with {{DUE_DATE}}
   - Replace [Amount] with {{AMOUNT}}
   - Replace [Name - Phone] with {{NABIS_AM_NAME}} {{NABIS_AM_PHONE}}
   - Keep signature block, confidentiality notice from current template
   - EXACT body text from canonical -- no AI embellishments

2. Rebuild overdue.html using Section 1.2 CORRECTED canonical text
   - Use "overdue" NOT "nearing two weeks past due" (per fix PDF)
   - Remove {{OVERDUE_TIMEFRAME}} dynamic variable entirely
   - Same variable mappings as above

3. Rebuild past_due_30.html using Section 1.3 canonical text
   - This is the ONLY past-due template (used for 30+, 40+, 50+, etc.)
   - Add {{PAYMENT_DEADLINE_DATE}} line per meeting decision
   - Add red-bar OCM warning using canonical wording
   - Bullet order: Invoice, Due, Nabis AM, Amount (canonical order)
   - NO "second notice", NO "final notice", NO account holds, NO collections threats

4. DELETE past_due_40.html
5. DELETE past_due_50.html

OUTPUT: Write rebuilt template files.
```

### Prompt 2: Tier Classifier Refactor Agent

```
ROLE: Tier Classifier Refactorer
OBJECTIVE: Reduce the 5-tier system to 3 tiers with dynamic subject labels.

INPUT: Read report 03_template_analyst.md for tier spec.

ACTIONS:
1. Consolidate Tier enum to 3 values: COMING_DUE, OVERDUE, PAST_DUE
2. Remove PAST_DUE_40 and PAST_DUE_50 from enum and metadata
3. Add get_dynamic_subject_label(days_past_due) function
4. Remove get_overdue_timeframe_description() function
5. Update classify() to map 30+ to single PAST_DUE tier
6. Update classify_batch() accordingly
7. Fix the dual-Tier-enum problem between models.py and tier_classifier.py
8. Remove "ACTION REQUIRED" and "FINAL NOTICE" from build_subject_line()
9. Update all tests

OUTPUT: Refactored tier_classifier.py, models.py, template_engine.py
```

---

## 12. Appendix: File-Level Change Impact Matrix

| File | Change Type | Priority | Effort |
|------|------------|----------|--------|
| `templates/coming_due.html` | Minor fix (attachment line wording) | Medium | Low |
| `templates/overdue.html` | Moderate fix (remove OVERDUE_TIMEFRAME, fix body text) | High | Medium |
| `templates/past_due_30.html` | Rebuild from canonical + add approved enhancements | High | Medium |
| `templates/past_due_40.html` | **DELETE** | Critical | Trivial |
| `templates/past_due_50.html` | **DELETE** | Critical | Trivial |
| `src/tier_classifier.py` | Major refactor (5 tiers -> 3, remove functions) | Critical | High |
| `src/models.py` | Major refactor (consolidate Tier enum, remove tiers) | Critical | High |
| `src/template_engine.py` | Major refactor (remove T4/T5 logic, fix subject builder) | Critical | High |
| `src/config.py` | Update tier configs (not read in this analysis but likely needs changes) | High | Medium |

---

*End of Report 03 - Template Specification*
