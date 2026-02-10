# AR Email Tool - Laura's Quick Start Guide

Welcome to your new AR Email Tool! This guide walks you through everything you need to know to use the system every week.

---

## What This Tool Does

Instead of writing 50+ collection emails by hand every Wednesday, you now upload your spreadsheet, review the emails the tool writes for you, and approve the ones that look good. What used to take 7 hours now takes about 30 minutes.

The tool:
- Reads your weekly AR spreadsheet
- Looks up the right contact person for each store
- Picks the correct email template based on how overdue they are
- Fills in all the details (amounts, invoice numbers, dates)
- Shows you the finished emails for review
- Lets you approve, edit, or skip any email
- Packages them up so you can send from Outlook or Gmail

---

## How to Access the Tool

Open your Chrome browser and go to:

```
http://192.168.15.59:8501
```

**If the page won't load:**
- Ask Joe to run `start_server.bat` on his computer
- Wait about 30 seconds, then refresh the page

You can bookmark this page for quick access.

---

## Step-by-Step: Weekly Workflow

### Step 1: Upload Your Data

In the left sidebar, you'll see **"Upload Data"** at the top.

**Option A - Upload the file:**
1. Click the upload area
2. Select your `NY Account Receivables_Overdue.xlsx` file (the one you download from Google Sheets)
3. Click **"Generate Emails"**

**Option B - Use the default file:**
1. Check the box that says **"Use default file"**
2. Click **"Generate Emails"**

This option works if Joe already saved the latest spreadsheet to the system.

The tool will process the data in a few seconds and show you a success message.

---

### Step 2: Review the Email Queue

After generating, you'll see the **Email Queue** page with all your draft emails listed.

Each row shows:
- **Store Name** - which dispensary the email goes to
- **Tier Badge** - color-coded urgency level (see "What the Tiers Mean" below)
- **Amount** - total dollars owed
- **Days** - how many days overdue (negative numbers = not due yet)
- **Status** - Pending, Approved, or Rejected
- **Action Buttons** - Preview, Approve, Reject

**Color-Coded Tier Badges:**
- **Green** = Coming Due (friendly reminder, not overdue yet)
- **Yellow** = Overdue (1-29 days late)
- **Orange** = 30+ Days Past Due
- **Light Red** = 40+ Days Past Due
- **Dark Red** = 50+ Days Past Due (needs escalation)

**Warning Flags:**
Some emails have small yellow badges that say things like:
- **MULTI-INVOICE** - This store has multiple overdue invoices (they're combined into one email)
- **HIGH VALUE** - Invoice over $5,000
- **MISSING AM** - No account manager listed in the spreadsheet
- **DISPUTE** - There's a note in the spreadsheet about this invoice
- **CHECK NOTES** - The notes column has something important

These flags help you spot emails that might need extra attention.

---

### Step 3: Preview Each Email

Click the **"Preview"** button on any email to see exactly what will be sent.

The preview shows:
- **From:** Kali Speerstra <kali@piccplatform.com>
- **To:** The store's contact email
- **CC:** The usual team (ny.ar@nabis.com, martinm@, mario@, laura@)
- **Subject:** Auto-generated subject line
- **Body:** Full email with all details filled in
- **Attachment:** Nabis ACH Payment Form (automatically included)

The parts that change for each email (like the store name, dollar amount, and invoice number) are **highlighted in yellow** so you can quickly check that everything looks right.

---

### Step 4: Approve, Edit, or Reject

For each email, you have these options:

**APPROVE** - Click this if the email looks good. It moves to the "Approved" pile.

**EDIT** - Click this if you need to change something:
- Change the To or CC email addresses
- Adjust the subject line
- Edit the email body text
- Then click **"Save Changes"** or **"Cancel"**

**REJECT** - Click this if you don't want to send this email (for example, you already called them, or they paid since you downloaded the spreadsheet). You can type a reason why you're rejecting it.

**NEXT** - Skips to the next email without taking action.

---

### Step 5: Bulk Approve (Save Time!)

If most emails look good and you just want to review the flagged ones, use these shortcuts:

**Approve All Pending** (top of the Queue page)
- Approves every email that doesn't have warning flags
- You can then go back and review just the flagged ones individually

**Approve Coming Due**
- Approves only the green "Coming Due" emails (lowest risk)
- Good for quickly clearing the easy ones

---

### Step 6: Send the Emails

Once you've approved all the emails you want to send, you have **two options**:

#### Option A: Gmail Direct Send (Recommended - Coming Soon!)

1. Go to the **Settings** page in the sidebar
2. Enter your Gmail App Password (see setup instructions below)
3. Go back to the Queue page
4. Click **"Send Approved"**
5. The emails send directly from your laura@piccplatform.com account
6. You'll see a confirmation message for each sent email

**Setting Up Gmail App Password (One-Time):**
1. Go to https://myaccount.google.com/security in Chrome
2. Make sure **2-Step Verification** is turned ON
3. Go to https://myaccount.google.com/apppasswords
4. Under "Select app" choose **Mail**
5. Under "Select device" choose **Windows Computer**
6. Click **Generate**
7. Google shows you a 16-character password (looks like `xxxx xxxx xxxx xxxx`)
8. Copy that password
9. In the AR Email tool, go to **Settings** → paste it in the **"Gmail App Password"** field
10. You only need to do this once - the tool remembers it

#### Option B: Download and Send from Outlook

1. Click **"Download All (.zip)"** at the top of the Queue page
2. Save the zip file to your computer
3. Right-click the zip file → **Extract All**
4. Open the extracted folder - you'll see one `.eml` file for each approved email
5. Double-click any `.eml` file
6. It opens in Outlook with everything pre-filled (To, CC, Subject, Body, Attachment)
7. Review it one last time
8. Click **Send** in Outlook
9. Repeat for each `.eml` file

---

## What Each Tier Means

The tool automatically picks the right email tone based on how overdue the invoice is:

| Tier | Days Past Due | What It Means | Email Tone |
|------|---------------|---------------|------------|
| **Coming Due** | Not due yet (negative days) | Payment deadline is coming up | Friendly courtesy reminder |
| **Overdue** | 1 - 29 days | Payment is late | Friendly nudge |
| **30+ Days** | 30 - 39 days | Significantly overdue | More formal, mentions OCM reporting |
| **40+ Days** | 40 - 49 days | Approaching critical threshold | Formal, stronger OCM warning |
| **50+ Days** | 50+ days | Critical - OCM reporting required | Formal escalation (Mario should send these) |

---

## Using the Filters

The left sidebar has filter options to help you focus:

**Filter by Tier:**
- Select one or more tiers to show only those
- Leave empty to show all tiers

**Filter by Status:**
- **Pending** - Emails you haven't decided on yet
- **Approved** - Emails ready to send
- **Rejected** - Emails you've decided not to send

---

## Other Pages

**History** - Shows all emails you've exported this session. Useful for checking what you already sent.

**Do Not Contact** - Add stores you don't want to email (they'll be excluded from future batches). For example, if a store closed or requested no contact, add them here.

**Settings** - Configure sender info, Gmail password, and system settings.

---

## Tips and Tricks

**What if a store is missing an email address?**
- The tool flags it with "MISSING_CONTACT"
- Click Preview → Edit → add the email address in the To field
- Then approve it

**What if the amount looks wrong?**
- Don't approve it!
- Check the Google Sheet - if the amount is wrong there, fix it
- Re-download the XLSX and run "Generate Emails" again

**What if I already called them this week?**
- Click Reject and type "Called on 2/9" as the reason
- This removes them from the send list

**What if they already paid?**
- If you marked "Paid" in the spreadsheet, the tool automatically skips it
- If they paid after you downloaded the sheet, just reject the email

**What if I need to send from a different person?**
- 50+ Days emails should be sent by Mario instead of Kali
- The tool flags these - forward the .eml file to Mario to send

---

## Troubleshooting

**The page won't load**
- Ask Joe to run `start_server.bat` on his computer
- Wait 30 seconds, then refresh the page in Chrome

**"No emails generated" message**
- Make sure you uploaded an XLSX file OR checked "Use default file"
- Click the "Generate Emails" button

**Only 2 emails showing (expected 50+)**
- This is normal if most invoices are already marked "Email Sent" in the spreadsheet
- The tool skips invoices where Email Sent = TRUE to prevent duplicates

**Contact info looks wrong**
- Click Preview → Edit to change the To or CC addresses
- Save your changes, then approve

**Download button doesn't work**
- Make sure you approved at least one email first
- Try the "Download All (.zip)" button instead

**Gmail sending fails**
- Check that you entered the App Password correctly in Settings
- Make sure it's an App Password (16 characters), not your regular Gmail password
- Try generating a new App Password if it still doesn't work

---

## Weekly Checklist

Here's your weekly routine (should take about 30 minutes):

- [ ] Download the latest `NY Account Receivables_Overdue.xlsx` from Google Sheets
- [ ] Open the AR Email Tool in Chrome
- [ ] Upload the file and click "Generate Emails"
- [ ] Review the summary stats at the top
- [ ] Click "Approve All Pending" to approve the clean ones
- [ ] Review any flagged emails individually
- [ ] Preview and approve/reject each flagged email
- [ ] Click "Send Approved" (Gmail) OR "Download All (.zip)" (Outlook)
- [ ] If using Outlook, open each .eml file and click Send
- [ ] Update the "Email Sent" column in Google Sheets

---

## Need Help?

**If something looks wrong with an email:**
- Don't approve it - ask Joe or Mario to take a look

**If the tool isn't working:**
- Ask Joe to check the server on his computer

**If you have ideas for improvements:**
- Let Joe know! The tool is designed to evolve based on your feedback.

---

**Last Updated:** February 9, 2026
