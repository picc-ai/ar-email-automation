# PICC AR Email Automation -- User Guide

**For: Kali and Laura (PICC Operations)**
**Last updated: February 10, 2026**

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Setting Your Sender Name](#2-setting-your-sender-name)
3. [Generating Emails](#3-generating-emails)
4. [Reviewing Emails (The Queue)](#4-reviewing-emails-the-queue)
5. [Previewing an Email](#5-previewing-an-email)
6. [Editing an Email](#6-editing-an-email)
7. [Approving and Rejecting](#7-approving-and-rejecting)
8. [Sending Emails](#8-sending-emails)
9. [Settings Page](#9-settings-page)
10. [Do Not Contact List](#10-do-not-contact-list)
11. [Tips and Common Tasks](#11-tips-and-common-tasks)

---

## 1. Getting Started

### How to Open the App

1. Open a terminal or command prompt window.
2. Navigate to the AR email automation folder:
   ```
   cd "C:\Users\smith\Antigravity\PICC Projects\ar-email-automation"
   ```
3. Run the app:
   ```
   streamlit run app.py
   ```
4. A browser tab will open automatically with the app. If it does not, look at the terminal -- it will show a URL (usually `http://localhost:8501`). Copy and paste that into your browser.

### What You See When the App Opens

The app has two main areas:

- **Sidebar (left side)** -- This is your control panel. It has sections for uploading data, setting your name, generating emails, filtering, viewing stats, and navigating to different pages.
- **Main area (center/right)** -- This is where you review, preview, and take action on emails.

### The Sidebar Sections (Top to Bottom)

| Section | What It Does |
|---------|--------------|
| **PICC / AR EMAIL AUTOMATION** | The app logo at the top. Just branding, nothing to click. |
| **Upload Data** | Where you upload the weekly AR spreadsheet or use the default file. |
| **Sender Name** | Where you type your name so it appears in the email signature. |
| **Generate Emails** | The main button that creates all the email drafts. |
| **Load Demo Data** | Practice button -- loads fake sample data so you can explore without real data. Only shows before you generate. |
| **Filters** | Narrow down which emails you see by tier or status. Only appears after emails are generated. |
| **Summary** | Shows counts of pending, approved, rejected, and sent emails plus dollar totals. Only appears after emails are generated. |
| **Navigation** | Buttons to switch between pages: Email Queue, History, Do Not Contact, and Settings. |

### Loading Demo Data to Practice

If you want to explore the app without using real data:

1. Look in the sidebar for the **Load Demo Data** button (it appears below the **Generate Emails** button before any data is loaded).
2. Click **Load Demo Data**.
3. The app will fill in with sample stores and invoices. You can preview, approve, reject, and export these to get comfortable with the workflow.

> **Tip:** Demo data is completely fake. Nothing will be sent to real customers. It is safe to click every button while practicing.

---

## 2. Setting Your Sender Name

In the sidebar, you will see a section called **Sender Name** with a text field labeled **"Your name (appears in email signature)"**.

### What This Does

The name you type here gets placed into the email signature block at the bottom of every email. This is the name the customer sees when they read the email.

### How to Use It

- **Type your name** (for example: `Kali` or `Laura`) into the text field.
- If you leave it blank, the emails will use **"PICC Accounts Receivable"** as the default name.

### Examples

| What You Type | What Appears in the Email Signature |
|---------------|-------------------------------------|
| `Kali` | Kali |
| `Laura` | Laura |
| *(left blank)* | PICC Accounts Receivable |

> **Important:** Set your name BEFORE you click **Generate Emails**. The sender name gets written into the email body when the emails are created. If you change your name after generating, you will need to re-generate the emails (or use the **Re-generate from template** button on individual emails).

---

## 3. Generating Emails

### Step-by-Step

1. **Upload your data.** You have two choices:
   - **Upload an XLSX file:** Click the **Upload AR Overdue XLSX** area in the sidebar and select the weekly AR spreadsheet from your computer.
   - **Use the default file:** Check the box labeled **"Use default file"**. This uses the spreadsheet already saved in the app's data folder.
2. **Set your sender name** (see Section 2 above).
3. **Click "Generate Emails"** (the green button in the sidebar).

### What Happens Next

The app reads the spreadsheet, groups invoices by store, and creates one email per store. You will see:

- A success message telling you how many email drafts were created.
- The **Email Queue** page will appear in the main area with all the drafts listed.
- **Stat cards** appear at the top of the queue showing counts and totals.

### Understanding the Stat Cards

At the top of the queue page, you will see six boxes:

| Card | What It Shows |
|------|---------------|
| **Pending** | How many emails are waiting for your review |
| **Approved** | How many you have approved and are ready to send |
| **Rejected** | How many you have decided to skip |
| **Sent** | How many have actually been sent via Gmail |
| **Total Emails** | The total number of emails in the queue |
| **Total AR** | The combined dollar amount across all emails (shown in gold) |

### Understanding the Tier System

Each email is assigned a "tier" based on how overdue the invoice is. The tier controls the tone of the email -- from friendly to urgent.

| Tier | Days Past Due | Tone |
|------|---------------|------|
| **Coming Due** | Not yet due (payment due soon) | Friendly courtesy reminder |
| **Overdue** | 1 to 29 days past due | Gentle nudge, still friendly |
| **30+ Days Past Due** | 30 to 39 days | More formal, mentions OCM reporting |
| **40+ Days Past Due** | 40 to 49 days | Urgent, subject line says "ACTION REQUIRED" |
| **50+ Days Past Due** | 50 or more days | Final notice, mentions possible account hold |

The tier is automatically assigned based on the data in the spreadsheet. You do not need to choose it manually.

---

## 4. Reviewing Emails (The Queue)

The Email Queue is the main page where you see all your email drafts listed in a table.

### Reading the Queue Table

Each row is one email (one store). The columns are:

| Column | What It Shows |
|--------|---------------|
| **#** | Row number |
| **Tier** | A colored badge showing the urgency level (Coming Due, Overdue, 30+, 40+, 50+) |
| **Store Name** | The dispensary name. If there are multiple invoices, it shows the count in parentheses, like "(2 invoices)" |
| **Amount** | Total dollar amount owed across all invoices for that store |
| **Days** | The maximum number of days past due. Green text means not yet due. Orange means 30+ days. Red means 50+ days. |
| **Status** | A badge showing where this email is in the workflow: pending, approved, rejected, or sent |
| **Actions** | Buttons to Approve, Preview, or Reject the email |

### What the Colored Tier Badges Mean

- **Green badge (Coming Due)** -- Payment is not yet late. This is a heads-up reminder.
- **Yellow badge (Overdue)** -- Just past due. Gentle follow-up.
- **Dark yellow badge (30+ Days Past Due)** -- Getting serious. Email mentions OCM reporting.
- **Light red badge (40+ Days Past Due)** -- Urgent. "ACTION REQUIRED" in the subject line.
- **Red badge (50+ Days Past Due)** -- Final notice. Mentions account hold.

### What the Flags Mean

Some emails have small yellow flag badges under the store name. These call your attention to special situations:

| Flag | What It Means |
|------|---------------|
| **MULTI-INVOICE** | This store has more than one overdue invoice bundled into one email |
| **HIGH VALUE** | At least one invoice is over $5,000 |
| **CHRONIC** | At least one invoice is more than 80 days past due |
| **MISSING AM** | The Account Manager field is blank or shows "#N/A" in the spreadsheet |
| **CHECK NOTES** | There is an "@" symbol in the notes field (may contain an email address or mention) |
| **DISPUTE** | The invoice status is marked as "Issue" in the spreadsheet |

### Using Filters

In the sidebar under **Filters**, you can narrow down which emails you see:

- **Filter by Tier** -- Select one or more tiers to show only those. Leave it empty to show all tiers.
- **Filter by Status** -- Select one or more statuses (pending, approved, rejected, sent) to show only those. Leave it empty to show all.

The filter shows how many emails match at the top of the table (for example: "Showing 5 of 12 emails").

---

## 5. Previewing an Email

### How to Open a Preview

In the queue table, click the **Preview** button on any email row. This takes you to the Email Preview page.

### What You See on the Preview Page

The preview page has several sections, from top to bottom:

1. **Back to Queue** button -- Click this to return to the queue list.

2. **Status bar** -- Shows the current Status, Tier, Days Past Due, and any Flags for this email.

3. **Email Headers** -- Shows the From, To, CC, Subject, and Attachment fields. This is the information that will appear at the top of the email in Gmail.
   - If the **To** field says "(no contact found)", the app could not find an email address for this store. You will need to edit it before sending (see Section 6).

4. **Invoice Details** (collapsible section) -- Click the arrow to expand this section. It shows a breakdown of each invoice included in this email:
   - Order number
   - Dollar amount
   - Days past due
   - Due date
   - Sales rep name
   - Any notes from the spreadsheet

5. **Email Body** -- This is a white box that shows the email EXACTLY as the customer will see it in Gmail. Scroll down to read the entire message, including the signature block at the bottom.

6. **Action Buttons** -- At the bottom you will find buttons for APPROVE, EDIT, REJECT, and NEXT.

7. **Previous / Next** navigation -- Buttons at the very bottom to move between emails without going back to the queue.

---

## 6. Editing an Email

### How to Open the Editor

On the preview page, click the **EDIT** button. The editor opens below the action buttons.

> **Note:** You can edit ANY email, not just ones with a "pending" status. This lets you fix something even after you have already approved it.

### Quick Edit Tab (Default)

The **Quick Edit** tab is the one you will use most often. It lets you change three things without touching any code:

- **To (comma-separated)** -- The recipient email addresses. If there are multiple recipients, separate them with commas.
- **CC (comma-separated)** -- The CC email addresses.
- **Subject** -- The email subject line.

After making your changes:
- Click **Save Changes** to keep your edits.
- Click **Cancel** to throw away your changes and go back to the preview.

#### The Re-generate from Template Button

If you made changes to an email and want to undo everything and start fresh:

1. Click **Re-generate from template**.
2. This resets the email body, subject line, and CC list back to what the original template would produce.
3. It keeps your **To** address changes (so you do not lose any recipient email fixes you made).

> **Tip:** This is especially useful if you changed your sender name and want it to take effect on emails that were already generated.

### Edit HTML Tab (Advanced)

The **Edit HTML** tab shows the same To, CC, and Subject fields, plus a large text box containing the raw HTML code of the email body.

> **Warning:** The HTML code controls how the email looks in Gmail. If you accidentally delete or change the wrong part, the email formatting could break. Only use this tab if you know what you are doing, or if you need to make a specific text change in the email body that you cannot do any other way.

After editing:
- Click **Save Changes** to keep your edits.
- Click **Cancel** to throw away your changes.

---

## 7. Approving and Rejecting

### Approving a Single Email

There are two places to approve an email:

- **From the queue:** Click the **Approve** button in the Actions column of any pending email row.
- **From the preview page:** Click the **APPROVE** button.

After you approve an email, its status changes from "pending" to "approved" (green badge). If you are on the preview page, the app automatically jumps to the next pending email so you can keep reviewing.

### Rejecting a Single Email

- **From the queue:** Click the **Reject** button in the Actions column.
- **From the preview page:** Type an optional reason in the **Rejection reason** text field, then click **REJECT**.

Rejected emails are skipped and will not be sent. The reason you type is saved for your records.

After rejecting, the app automatically moves to the next pending email.

### Batch Actions

At the top of the queue page (above the email table), there are buttons for bulk actions:

| Button | What It Does |
|--------|--------------|
| **Approve All Pending** | Approves every email that currently has "pending" status. One click, all done. |
| **Approve Coming Due** | Approves only the "Coming Due" tier emails (the friendly reminders). Useful if you want to send the easy ones first and review the overdue ones individually. |

> **Tip:** You can always change an approved email back to a different state by rejecting it from the preview, or you can edit it even after approval.

---

## 8. Sending Emails

Once you have approved the emails you want to send, you have two options.

### Option A: Send Directly via Gmail

This sends emails straight from the app through Gmail. The customer receives the email in their inbox immediately.

**Requirements:**
- You must have a **Gmail App Password** set up in Settings (see Section 9).
- You must have a **Sender Email** configured in Settings.

**Steps:**
1. Make sure all the emails you want to send are marked as "approved."
2. At the top of the queue page, click the **Send via Gmail** button.
3. A progress bar appears showing which email is being sent (for example: "Sending 3/12: Royal Blend...").
4. When finished, the app shows results:
   - Green messages for emails that sent successfully.
   - Red messages for any that failed (with the reason).
5. Successfully sent emails change their status to "sent."

> **Important:** If the **Send via Gmail** button is grayed out (disabled), it means either (a) you have no approved emails, or (b) Gmail is not configured. Check Settings.

Each email sent through Gmail also has the **Nabis ACH Payment Form** PDF automatically attached (if the file exists in the app's data folder).

### Option B: Export as .eml Files

If you prefer not to send directly, you can export the emails as files and open them manually in Gmail or Outlook.

**Two export buttons are available at the top of the queue page:**

| Button | What It Does |
|--------|--------------|
| **Export Approved** | Saves each approved email as a separate .eml file in the app's `output/` folder. Also creates a summary report. |
| **Download All (.zip)** | Creates a .zip file containing all approved emails. A download button appears -- click it to save the .zip to your computer. |

**To send an exported .eml file:**
1. Find the .eml file on your computer (in the `output/` folder, or wherever you saved the .zip).
2. Double-click the .eml file. It will open in your default email program (Outlook or similar).
3. Click Send from your email program.

Alternatively, in Gmail you can use the "Import" or drag-and-drop method to open .eml files.

---

## 9. Settings Page

To get to Settings, click the **Settings** button in the sidebar under Navigation.

### Sender Configuration

- **Sender Name** -- Same as the sidebar field. Your name that appears in the email signature. Also editable here.
- **Sender Email** -- The email address that appears in the "From" line. The default is `laura@piccplatform.com`. Change this if you are sending from a different address.
- **Sender Title** -- The job title that appears in the signature (for example: "Accounts Receivable Department").
- **Company** -- The company name in the signature (default: "PICC Platform").

### CC List Management

The **Always CC Recipients** section shows the list of email addresses that get copied on every outgoing email. Each address is on its own line. You can add or remove addresses here.

The default list includes:
- ny.ar@nabis.com
- martinm@piccplatform.com
- mario@piccplatform.com
- laura@piccplatform.com

### Gmail App Password Setup

To send emails directly from the app, you need a special password from Google (not your regular Gmail password). This is called an **App Password**.

**Step-by-step instructions:**

1. Go to [Google Account Security](https://myaccount.google.com/security) in your browser.
2. Make sure **2-Step Verification** is turned ON for your Google account. If it is not, you need to enable it first.
3. Go to [App Passwords](https://myaccount.google.com/apppasswords).
4. Select **Mail** as the app and **Windows Computer** as the device.
5. Click **Generate**.
6. Google will show you a 16-character password (it looks like `xxxx xxxx xxxx xxxx`). Copy it.
7. Go back to the app's Settings page and paste the password into the **Gmail App Password** field.
8. Click the **Test Connection** button to make sure it works.
   - If you see a green "Connected! Gmail is ready to send." message, you are all set.
   - If you see a red error, double-check the password and try again.

> **Tip:** You only need to do this setup once per session. The password is stored while the app is running but is not saved to disk, so you may need to re-enter it if you restart the app.

### System Module Status

At the bottom of the Settings page, you will see a list of system modules with a green or red indicator next to each one. All modules should show **green/Available** for the app to work properly. If any show **red/Not loaded**, let the development team know.

| Module | What It Does |
|--------|--------------|
| Models | Core data structures (required) |
| Config | App configuration and settings |
| Data Loader | Reads and parses the XLSX spreadsheet |
| Tier Classifier | Assigns urgency tiers to invoices |
| Contact Resolver | Finds email addresses for each store |
| Template Engine | Creates the HTML email body from templates |

---

## 10. Do Not Contact List

To get to the Do Not Contact page, click the **Do Not Contact** button in the sidebar under Navigation.

### What It Does

Stores on this list are automatically **skipped** when you generate emails. No email will be created for them, even if they appear in the spreadsheet with overdue invoices.

### Adding a Store

1. On the Do Not Contact page, type the **exact store name** into the text field at the top.
2. Click **Add**.
3. The store appears in the list below.

> **Important:** The store name must match exactly as it appears in the spreadsheet. For example, if the spreadsheet says "Dazed - New York", you must type "Dazed - New York" -- not "Dazed" or "dazed - new york".

### Removing a Store

Next to each store name in the list, there is a **Remove** button. Click it to take the store off the Do Not Contact list. The next time you generate emails, that store will be included again.

### When Does It Take Effect?

The Do Not Contact list is checked at the time you click **Generate Emails**. If you add a store to the list after generating, you will need to generate again for the change to take effect. Alternatively, you can just reject that store's email from the queue.

---

## 11. Tips and Common Tasks

### "I need to fix a recipient email address."

1. Find the email in the queue and click **Preview**.
2. Click **EDIT**.
3. In the **Quick Edit** tab, change the **To** field to the correct email address.
4. Click **Save Changes**.

### "The wrong name is in the email signature."

1. In the sidebar, type the correct name in the **Sender Name** field.
2. Go back to the email preview and click **EDIT**.
3. Click **Re-generate from template**. This rebuilds the email body with the new name.

### "I want to skip a store this week."

You have two options:

- **One-time skip:** On the queue page, click **Reject** on that store's email. Type a reason if you want (for example: "Payment expected Friday").
- **Permanent skip:** Go to the **Do Not Contact** page and add the store. It will be excluded every time you generate.

### "I want to add someone to the CC line on one specific email."

1. Click **Preview** on the email.
2. Click **EDIT**.
3. In the **Quick Edit** tab, find the **CC** field.
4. Add the new email address at the end, separated by a comma (for example: `ny.ar@nabis.com, mario@piccplatform.com, newperson@example.com`).
5. Click **Save Changes**.

### "I want to start over with a fresh batch."

Click **Generate Emails** in the sidebar again. This creates a completely new set of email drafts and replaces the current queue.

> **Warning:** Generating again will erase any approvals, rejections, or edits you have made in the current session. Make sure you have sent or exported everything you need before regenerating.

### "The app says 'no contact found' for a store."

This means the spreadsheet does not have an email address on file for that store. You will need to:

1. Click **Preview** on that email.
2. Click **EDIT**.
3. In the **Quick Edit** tab, type the correct email address in the **To** field.
4. Click **Save Changes**.

### "I want to review only the high-urgency emails."

In the sidebar under **Filters**, select the tiers you want to focus on (for example, select "40+ Days Past Due" and "50+ Days Past Due"). The queue will show only those emails. Clear the filter to see all emails again.

### "How do I know which emails have already been sent?"

- The **Sent** stat card at the top of the queue shows the count.
- In the sidebar, use the **Filter by Status** dropdown and select "sent" to see only sent emails.
- Go to the **History** page (sidebar navigation) to see a log of all exported and sent emails with timestamps.

### "I want to download a record of everything I did."

Go to the **History** page and click **Download History as CSV**. This gives you a spreadsheet with the store name, tier, amount, recipient, and timestamp for every email you exported or sent during this session.

---

**End of User Guide**

If you run into problems not covered here, reach out to the development team. Keep this guide bookmarked for quick reference during your weekly AR email runs.
