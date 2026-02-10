# AR Email Automation - CEO Briefing

Prepared for: Travis (CEO) & Laura (Operations)
Presenter: Joe
Date: February 2026

---

## VERSION 1: Talking Points

- **Time savings**: Laura currently spends about 9 minutes per collection email -- this tool processes all 70 invoices in under a second, turning roughly 10 hours of manual work into a 15-minute review session.

- **Accuracy**: The tool automatically matches 98.3% of dispensaries to their correct contact emails using license numbers and store names, eliminating copy-paste errors.

- **Smart prioritization**: It reads the Past Due spreadsheet and auto-sorts all 70 invoices across 60 dispensaries into five urgency tiers, from "Coming Due" through "50+ Days Past Due," with the email tone escalating appropriately at each level.

- **Laura stays in control**: Nothing sends without her -- she opens the dashboard, reviews each drafted email, and can approve, edit, or reject every one before anything goes out.

- **Built-in safeguards**: The tool automatically skips accounts that have already been contacted, already paid, or have payment en route, so nobody gets a duplicate or incorrect notice.

- **Reliability**: 352 automated tests pass, covering the matching logic, email generation, and tier classification.

- **What's next**: With your approval, we can connect it directly to Google Sheets so Laura doesn't need to export a file, and eventually add auto-send through Outlook so approved emails go out with one click.

---

## VERSION 2: Script

Travis, Laura -- I want to walk you through the AR collection tool I built. Two minutes, then I want your feedback.

**The problem.** Laura, right now every time you sit down to send collection emails, you're pulling up the past-due spreadsheet, finding the dispensary, looking up the contact, figuring out how overdue they are, writing the email, and sending it. That's about nine minutes per email. With 70 invoices across 60 dispensaries, that's a full day of work just on collections.

**What the tool does.** You upload the past-due spreadsheet export, and the tool does the rest in about a fifth of a second. It reads every invoice, matches each dispensary to the right contact email -- it gets 98% of them right automatically using license numbers -- and sorts everything into five buckets: coming due, overdue, 30 days, 40 days, 50 days past due. Then it drafts a professional email for each one, and the tone gets more serious the further past due they are.

**Here's the important part.** Laura, nothing goes out without you. You open the dashboard, you see the whole queue, and for each email you can approve it, edit the wording, or reject it entirely. It also skips anyone who already paid, anyone with payment on the way, and anyone you already contacted -- so no embarrassing double-sends.

Once you approve the batch, it packages everything into email files you open right in Outlook and send.

**What I'm asking for.** Laura, I'd love for you to try it on this week's batch and tell me what feels right and what doesn't. Travis, if it works the way we expect, the next step is connecting it live to the Google Sheet so Laura doesn't even need to export a file -- and eventually we can have approved emails send themselves automatically.

That's it. Happy to show you a quick demo right now if you want to see it.
