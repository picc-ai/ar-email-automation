# UI Enhancements Report
## Document: 12 - app.py UI/UX Fixes (Wave 2 Build)
## Timestamp: 2026-02-14
## Agent: Wave 2 UI Enhancer (Opus)
## Target File: `app.py` (~2070 lines -> ~2150 lines after changes)

---

## Status: COMPLETE

## Changes Made

### 1. TIER_COLORS dict updated to 3 tiers
- **Status**: DONE
- **Original Lines**: 120-126
- **Change**: Removed "40+ Days Past Due" and "50+ Days Past Due" entries from the `TIER_COLORS` dict. Updated "30+ Days Past Due" to use red color scheme (`#f8d7da` bg, `#721c24` text) matching the most severe tier. Now only 3 entries remain: Coming Due (green), Overdue (yellow), 30+ Days Past Due (red).

### 2. Fix hardcoded "Laura" in From display
- **Status**: DONE
- **Original Line**: 1290
- **Change**: Replaced `st.markdown(f"Laura <{st.session_state.sender_email}>")` with dynamic display using `st.session_state.sender_name or "PICC Accounts Receivable"`. The From field now shows the actual configured sender name.

### 3. Remove "Use Default File" checkbox
- **Status**: DONE
- **Original Lines**: 849-853
- **Change**: Removed the `st.checkbox("Use default file", value=True, ...)` widget entirely. Updated the generate button logic to simply warn "Please upload an XLSX file first" if no file is uploaded, instead of falling back to a default file. This eliminates the confusing checkbox that Joe called "a weird button that was for the demo."

### 4. Add "Save Settings" button with JSON persistence
- **Status**: DONE
- **Location**: Settings page (before Gmail SMTP section)
- **Change**:
  - Added `SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"` constant
  - Added `_load_saved_settings()` function to load settings from JSON on disk
  - Added `_save_settings()` function to write settings dict to JSON on disk
  - Updated `init_session_state()` to load saved settings for: `sender_name`, `sender_email`, `custom_cc`, `schedule_time`, `schedule_timezone`
  - Added "Save Settings" button on the Settings page that persists: sender name, sender email, CC list, schedule time, and schedule timezone
  - Settings now survive session restarts when saved
  - CC list uses saved `custom_cc` from session state if available, otherwise falls back to config defaults

### 5. Add BCC field to edit mode
- **Status**: DONE
- **Location**: Preview page edit mode (Quick Edit + HTML Edit tabs)
- **Changes**:
  - Added BCC text input to **Quick Edit** tab with save functionality
  - Added BCC text input to **HTML Edit** tab with save functionality
  - Added BCC display row in email headers (preview page)
  - Updated `generate_eml()` to include BCC header in .eml files
  - Updated `_build_smtp_message()` to include BCC header in SMTP messages
  - Updated `send_email_smtp()` to include BCC recipients in the actual send (`all_recipients` now includes `draft.bcc`)
  - Uses `getattr(draft, "bcc", [])` for backward compatibility if the EmailDraft model doesn't have a `bcc` field yet

### 6. Add schedule send time picker
- **Status**: DONE
- **Location**: Queue page, between batch action buttons and send results
- **Change**: Added a 3-column layout with:
  - `st.time_input()` defaulting to 7:00 AM
  - `st.selectbox()` for timezone selection: PT (Pacific), ET (Eastern), CT (Central), MT (Mountain)
  - Informational text showing the scheduled time and noting that true scheduled send requires Gmail API integration (future feature)
  - Schedule time and timezone are stored in session state and persist via Save Settings
  - Added `schedule_time` and `schedule_timezone` to the session state defaults

### 7. Convert tier label inputs to dropdowns
- **Status**: DONE
- **Original Lines**: ~2000-2005 (tier label text_input)
- **Change**: Replaced `st.text_input("Label", ...)` with `st.selectbox("Label", ...)` using predefined options: `["Coming Due", "Overdue", "30+ Days Past Due"]`. The dropdown auto-selects the current label if it matches one of the options, otherwise defaults to the first option.

---

## Detailed Change Log

### Files Modified
- `app.py` - All 7 changes applied

### New Session State Keys
| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `custom_cc` | `list[str] \| None` | `None` (falls back to config) | Persisted CC list from Save Settings |
| `schedule_time` | `str` | `"07:00"` | Scheduled send time (HH:MM) |
| `schedule_timezone` | `str` | `"PT"` | Timezone for scheduled send |

### New Functions
| Function | Purpose |
|----------|---------|
| `_load_saved_settings()` | Load settings from `data/settings.json` |
| `_save_settings(settings)` | Write settings dict to `data/settings.json` |

### New Files Created
- `data/settings.json` (created on first Save Settings click)

### Backward Compatibility Notes
- All existing session state keys are preserved
- BCC uses `getattr(draft, "bcc", [])` so it gracefully handles EmailDraft objects that don't have a `bcc` attribute
- The `_get_template_engine()` helper pattern is preserved
- All try/except import patterns with `*_AVAILABLE` flags are preserved
- No changes to routing, page structure, or CSS

### Known Limitations
- **Schedule send is UI-only**: The time picker is present but emails still send immediately via SMTP. True scheduled send requires Gmail API integration or a task scheduler, which is a future feature.
- **Settings persistence**: Gmail App Password is intentionally NOT persisted to disk for security reasons. It must be re-entered each session.
- **BCC field**: The `EmailDraft` model in `models.py` may not have a `bcc` field yet. The UI uses `getattr()` fallback, but for full support, `bcc: list[str] = field(default_factory=list)` should be added to `EmailDraft` in `models.py`.

---

## Testing Checklist

- [ ] Settings page: Enter sender name, email, CC list -> click Save Settings -> restart session -> values should load from `data/settings.json`
- [ ] Preview page: "From:" shows the configured sender name, not hardcoded "Laura"
- [ ] Preview page: Click EDIT -> Quick Edit tab shows TO, CC, BCC, Subject fields -> Save Changes persists edits
- [ ] Preview page: Click EDIT -> HTML Edit tab shows TO, CC, BCC, Subject, HTML Body -> Save Changes persists edits
- [ ] Preview page: BCC row appears in email headers
- [ ] Queue page: Schedule time picker and timezone selector are visible
- [ ] Queue page: Tier badges show 3 colors only (no 40+ or 50+ badges)
- [ ] Settings page: Tier labels are dropdowns (selectbox), not text inputs
- [ ] Sidebar: "Use Default File" checkbox is gone
- [ ] Sidebar: Clicking Generate without uploading shows warning message
- [ ] Export: .eml files include BCC header when BCC is set
- [ ] Send: SMTP send includes BCC recipients

---

*End of Document 12 - UI Enhancements*
