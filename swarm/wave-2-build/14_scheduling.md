# Schedule Send Implementation Report
## Document: 14 - Schedule Send Capability
## Timestamp: 2026-02-14
## Agent: Wave 2 Agent 14 (opus) - Schedule Send Implementer
## Status: COMPLETE

---

## Overview

Added schedule send capability with time picker to the AR email automation app. Callie currently schedule-sends emails for 7:00 AM PT (10:00 AM ET) using Gmail's built-in schedule send. This implementation adds a scheduling UI and display-only scheduling support, with the scheduled time tracked on each EmailDraft for visibility.

## Approach

**Go-live strategy (Option A - Display-only scheduling): IMPLEMENTED**
- Added time picker UI in the send/queue section of app.py
- Display scheduled time prominently in the queue view for each email
- Reminded Callie of the target send time so she can use Gmail's built-in schedule send
- Stored scheduled time in session state and EmailDraft model
- Shows PT to ET timezone conversion automatically

**Future upgrade path (Option B - Python threading):**
- Not implemented in this sprint
- Would use threading.Timer to delay SMTP send
- Gmail API (not SMTP) supports native scheduled send for full automation

## Changes Made

### 1. models.py - EmailDraft Enhancement
- [x] Added `from datetime import time` to imports (line 17)
- [x] Added `scheduled_send_time: time | None = None` field to EmailDraft (line 319)
- [x] Added `scheduled_timezone: str = "PT"` field to EmailDraft (line 320)
- [x] Added `scheduled_time_display` property with PT-to-ET conversion (lines 328-349)
- [x] Updated `to_dict()` to conditionally include `scheduled_send_time` and `scheduled_time_display` (lines 435-438)

### 2. config.yaml - Scheduling Defaults
- [x] Changed `timezone` from `"America/New_York"` to `"America/Los_Angeles"` (line 241)
- [x] Added `default_send_time: "07:00"` (line 242)
- [x] Added `default_timezone: "US/Pacific"` (line 243)

### 3. app.py - Schedule Send UI
- [x] Added `from datetime import time as dt_time` to imports (line 24)
- [x] Enhanced schedule time picker section with proper ET conversion display (lines 1140-1192)
  - Removed redundant inline `from datetime import time as dt_time` import
  - Added green-styled info card showing scheduled time with ET equivalent
  - Added note explaining that Gmail SMTP sends immediately; schedule-send requires manual timing
  - Applied `scheduled_send_time` to all drafts in queue automatically
  - Applied `scheduled_timezone` to all drafts when timezone changes
- [x] Added scheduled time display in queue email rows under store name (lines 1261-1269)
  - Shows "Send at: 7:00 AM PT (10:00 AM ET)" in green under each store name
- [x] Added scheduled time to preview page status bar (5th column, lines 1365-1372)
- [x] Added "Send at:" row in preview page email headers section (line 1394, 1409-1411)
- [x] Added scheduled time to send history entries (lines 1780-1781)

### 4. Line Ranges Modified (for Agent 12 coordination)

**IMPORTANT: These are the exact areas I modified in each file.**

#### models.py
- Line 17: import statement (added `time`)
- Lines 318-320: New fields in EmailDraft dataclass (scheduling section)
- Lines 328-349: New `scheduled_time_display` property
- Lines 435-438: Extended `to_dict()` method

#### config.yaml
- Lines 239-243: Schedule section (changed timezone, added defaults)
- Note: Tiers section (lines 14-34) was also updated to 3 tiers (by Agent 10 or externally)

#### app.py (SEND/QUEUE SECTION ONLY -- no conflict with Agent 12)
- Line 24: Import statement
- Lines 1140-1192: Schedule Send Time Picker section (enhanced existing)
- Lines 1254-1269: Queue email rows - added scheduled time display under store name
- Lines 1351-1375: Preview page status bar (changed from 4 to 5 columns, added scheduled time)
- Lines 1394, 1409-1411: Preview page email headers (added "Send at:" row)
- Lines 1780-1781: Send history logging (added scheduled_time field)

## Testing

All changes verified:
- `models.py`: Passes syntax check (python AST parse)
- `app.py`: Passes syntax check (python AST parse)
- `config.yaml`: Parses correctly with PyYAML
- `EmailDraft.scheduled_time_display` tested with:
  - 7:00 AM PT -> "7:00 AM PT (10:00 AM ET)" -- CORRECT
  - 10:30 PM PT -> "10:30 PM PT (1:30 AM ET)" -- CORRECT (midnight wrap)
  - 12:00 PM PT -> "12:00 PM PT (3:00 PM ET)" -- CORRECT
  - 6:00 AM PT -> "6:00 AM PT (9:00 AM ET)" -- CORRECT
  - No scheduled time -> "" -- CORRECT
- `to_dict()` includes scheduled fields only when set -- CORRECT
- Windows compatibility: Uses `%I` (zero-padded) + `lstrip("0")` instead of `%-I` (Linux-only)

## Architecture Notes

### Why Display-Only (Option A)?
Gmail SMTP (`smtplib`) does not support scheduled send. The only ways to schedule are:
1. **Gmail API** with `send()` using `scheduleSendTime` parameter (requires OAuth2 setup)
2. **Python threading** with `threading.Timer` (fragile; Streamlit Cloud may kill the process)
3. **Display-only** (current): Show the target time prominently so Callie remembers when to click Send

Option A was chosen because:
- It works today with zero infrastructure changes
- Callie is already comfortable with Gmail's schedule-send in the compose window
- The scheduled time is now tracked on each EmailDraft for audit/export purposes
- Upgrading to Gmail API is a clean future enhancement (just change the send function)

### Data Flow
```
st.time_input (7:00 AM default)
    |
    v
st.session_state.schedule_time = "07:00"
    |
    v
for each draft in queue:
    draft.scheduled_send_time = time(7, 0)
    draft.scheduled_timezone = "PT"
    |
    v
Queue view:  "Send at: 7:00 AM PT (10:00 AM ET)"  (green text under store name)
Preview:     "Send at: 7:00 AM PT (10:00 AM ET)"  (in status bar + email headers)
Export:      to_dict() includes scheduled_send_time + scheduled_time_display
History:     logged with scheduled_time field when sent
```

## No Conflicts with Other Agents

- **Agent 10 (Tier Consolidator)**: My changes to models.py are in the `EmailDraft` class (lines 318-349, 435-438). Agent 10 modifies the `Tier` enum and `TierConfig.default_tiers()` -- completely separate sections.
- **Agent 12 (UI Enhancer)**: My app.py changes are confined to the SEND/QUEUE section (batch action buttons area, queue rows, preview page). I did NOT modify the settings page, upload section, or sidebar -- those are Agent 12's domain.
- **config.yaml**: I only modified the `schedule` section (section 13). Agent 10 handles the `tiers` section (section 1). No overlap.
