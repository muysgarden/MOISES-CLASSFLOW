# ClassFlow

A local Python / PyQt5 desktop system for classroom scheduling and academic timetabling, based on the supplied ClassFlow code and five-module UI reference. Data is stored in SQLite; no server or internet connection is required after installation.

## Run

Requires Python 3.10+ and a desktop display (Windows, macOS, or Linux).

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

On first launch, create your administrator username and password (minimum eight characters). Subsequent launches require those credentials. Passwords use salted PBKDF2-SHA256 hashes. Log out using the top bar. This is a local, single-office application; access to the database file should be limited to the office's authorized users.

After the first login, choose whether to load the demonstration academic records or start empty. `python main.py --seed` loads demonstration records only when the academic database is empty; it never resets existing data. The sample dataset deliberately contains conflicts to demonstrate validation.

The app creates `classflow.db` beside `main.py`. Set `CLASSFLOW_DB` to use another writable database path. Back up this database while the app is closed. The ZIP's existing database is not imported automatically or overwritten: to use it, copy that database to a separate location and set `CLASSFLOW_DB` to its full path. Back up your original first.

## Your photos and logo

Place your own files in `assets/`:

| File | Placement |
| --- | --- |
| `background.jpg` | Full login background |
| `building.jpg` | Left panel of the login card |
| `logo.png` | College logo over the left panel |

The login uses ClassFlow branding, a dark split card, username/password fields, password visibility toggle, inline login errors, and a blue-purple login button. Neutral placeholders appear until your images are supplied.

## Phase 1: Dashboard and navigation

After login, ClassFlow opens a new dashboard inspired by the supplied clean academic reference: a white sidebar, soft blue-gray workspace, blue-purple gradients, warm orange accents, spacious statistics and quick actions. Its six statistic cards, schedule summary and coverage bar use **actual data from the selected term**. "Saved schedules" shows assignments in recent database-ID order; it is not a timestamped activity log.

Use the global search box in the top bar, or press **Ctrl+K** to focus it. As you type, ClassFlow suggests matching subjects, faculty, classrooms, sections, programs, terms, periods and saved schedules from SQLite. Click a suggestion to open that specific record for editing or hit Enter to open the first match. If no record matches, a clear message appears.

The active academic term selector stays in the top bar. The sidebar links to Dashboard and the five original modules, with a clickable administrator account area. Click your username at the bottom of the sidebar to open a full workspace Settings page with Account and Security sections, while the main sidebar and search remain in place. Username and password changes both require the current password. Log out is a separate sidebar action, never part of the profile form. Scheduling progress appears in the dashboard's Scheduling Overview panel, not in the sidebar. All existing module operations are preserved for the later, module-by-module usability work.

To customize the appearance, edit the color values in `ui/theme.py`. Shared app-shell and component styling is appended in `PHASE1_QSS` inside `ui/style.py`; dashboard layout and content live in `ui/dashboard.py`. The login photo positions and logo slot have not changed.

The login remains intentionally dark while sharing the same gradient accent and typography as the new light dashboard.

## Phase 2: Academic Records (Module 1)

The existing seven Academic Records tabs remain intact. Records occupy the full table area by default; **Add New Record** or **Edit** reveals the inline form, and saving or cancelling restores the full-width table. The table's page controls appear when there are more than eight records.

New text and numeric fields start blank, and required numeric values are validated before saving. Program, room and other selection fields support typing with matching suggestions; unrecognized values are rejected. Edits update the existing SQLite record, while Delete removes records after confirmation if no dependent schedules or other references require them. A clear explanation names the dependent records when deletion is blocked. No existing data is silently discarded or reset.

### Demo data cleanup

The optional first-run demo dataset now tags the records it creates. Under **Settings → Data management**, an administrator can review the number of tagged demo records and, after explicit confirmation, remove only those original records. This is transactional: edited samples and references from non-demo records block cleanup and leave the database unchanged. Hand-entered data is never identified as sample data merely because its name resembles an example. Databases seeded in older versions have no trustworthy tags, so those historical records are *not* eligible for automatic cleanup; use normal record-by-record controls to review them.

## Phase 3: Faculty & Room Availability (Module 2)

Select a day and time range to see **Available**, **Scheduled**, **Unavailable**, or **Load full** status on readable faculty and classroom cards. Faculty and rooms have separate tabs, a name search filters both views, and classroom results have an additional room-type filter. The available counts reflect the selected time and, for faculty, whether their teaching-load limit has been reached.

Click **Manage Availability** beside the Module 2 heading to reveal an inline form immediately below the availability filters. Find a faculty member or classroom by typing, set a specific day and time interval, review existing blocked windows, or remove an individual window after confirmation. Click the header button again to hide the form. Scheduled classes and manually blocked intervals both affect availability. If a demo resource has administrator-created blocked windows, demo cleanup pauses until those windows are reviewed and removed; it never silently deletes them.

Blocked periods are listed in a readable **Blocked Time Records** table with Faculty/Room, Day, Time, Reason and Remove columns. Records can be removed individually with confirmation; the table scrolls when there are many entries.

In the blocked-time editor, **From** and **Until** offer 15-minute dropdown suggestions but also accept an exact typed time such as `8:17 AM` or `1:45 PM`. Invalid times, reversed ranges, and overlapping blocked windows are rejected. An optional **Reason** (for example, Faculty meeting or Room maintenance) is saved with the unavailable period and displayed alongside it; existing databases are upgraded without losing their earlier blocked times.

## Phase 4: Class Schedules (Module 3)

The class assignment form is hidden until the administrator clicks **New Schedule** or **Edit**, giving the saved schedules table the full workspace by default. The form uses two readable rows of inputs; subject, section, faculty and classroom selections support typing and matching suggestions without accepting unknown records. New forms begin unselected. **Class days** are checkboxes: select multiple days only when the meeting time is identical; for a Monday/Wednesday class with different hours, save one Monday assignment and one Wednesday assignment. The course/program is automatically shown from the selected section, avoiding duplicate course entry. Time fields use the same 15-minute suggestions and exact-time parsing as Module 2. Validation and conflict feedback appear directly under the form before saving, including a check that the chosen subject belongs to the section's course.

**Saved Schedules** and **Weekly Calendar** are separate views. Saved Schedules has distinct **Course**, **Section**, and **Subject** columns, a section filter, text search, and **8 assignments per page** with Previous/Next controls rather than a long, internally scrolling table. The calendar starts with an empty **Search section** field so unrelated classes do not overlap visually; typing offers matching section suggestions, and choosing a valid section displays its timetable against **30-minute** time markers (7:00, 7:30, 8:00, etc.). Saved schedules remain editable and deletable with the original safeguards.

## Phase 5: Conflict Checks (Module 4)

The conflict screen uses three color-coded **clickable** priority summaries instead of redundant dropdown filters: **Critical** (red, overlapping classes or unavailable resources), **Warning** (orange, capacity or teaching load), and **Review** (blue, time-window exceptions). Click a card to filter to that priority; click the active card again to show all issues. Issue priorities are also color-coded in the list. Actual database assignments determine the counts. Select a result row to view a simple detail panel explaining the conflict (including the overlapping time when applicable) and a single **View in Schedules** action that opens the corresponding assignment in Module 3. Editing is a manual correction; Module 4 does not claim to resolve conflicts automatically. Running the checks again refreshes the results.

## Typography

The desktop interface uses **Segoe UI Variable** where installed (Windows 11), falling back to **Segoe UI** on earlier Windows versions. Display headings have lighter, calmer weights, and navigation labels, table headers, and field captions use readable sizes. No internet download or external font installation is required. Concept illustrations generated on non-Windows machines may use a substitute font; the running application uses the configured Windows typeface.

## Modules

1. **Academic Data Management** — add, edit, delete, search, and filter programs, sections, subjects, faculty, classrooms, academic terms, and school periods. In-use records are protected from deletion.
2. **Faculty and Room Availability** — find available resources by day/time/type; view teaching loads and actual weekly availability blocks. Mark resource unavailability, or clear its saved windows. The three daily grid blocks are 8 AM–12 PM, 1 PM–5 PM, and 5 PM–8 PM. Unavailability preferences apply across academic terms.
3. **Schedule Management** — assign a subject, section, faculty member, room, days, and start/end time. Preview conflicts before saving, edit/delete assignments, search, and view section calendars. Critical conflicts block saving; warnings require confirmation.
4. **Conflict Detection and Validation** — detect faculty/room/section overlaps, room-capacity problems, excessive teaching loads, invalid school times, and unavailable resources. Filter results and open an affected assignment with Edit.
5. **Timetable Generation and Reports** — generate views from saved assignments, filter by program/section/faculty/room, view actual room utilization, faculty loads, conflict reports, and available rooms. Export PDF or CSV and use the system print dialog. Generate Timetable refreshes a timetable from assignments; it does not automatically assign unscheduled classes.

## Verification

```bash
# Windows
.venv\Scripts\python -m unittest discover -s tests -v

# macOS / Linux
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary in-memory databases and Qt's offscreen rendering. They exercise authentication, login interactions, conflict detection, resource unavailability, schedule create/edit/delete, all module screens, and PDF generation. Test screenshots and a sample PDF are written to the system temporary directory. A normal launch requires a desktop display; offscreen mode is for automated validation.

## Project files

- `main.py` — authenticated application startup.
- `auth.py` — local account creation and password verification.
- `db.py` — SQLite schema and optional sample records, retained from the supplied project.
- `logic.py` — scheduling, validation, loads, and progress.
- `ui/` — login, dashboard, shared theme, and five working module screens.
- `tests/test_system.py` — functional and UI checks.

The uploaded PDF is a visual reference. Its illustrative counts and percentages are replaced by computed values from the database.
