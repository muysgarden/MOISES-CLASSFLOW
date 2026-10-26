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

The login uses ClassFlow branding, a dark split card, username/password fields, password visibility toggle, inline login errors, and the reference's purple login button. Neutral placeholders appear until your images are supplied. The five application screens follow the PDF's navy sidebar, teal accents, pale workspace, cards, tabs, forms, tables, calendars, and report layout. Native font rendering and window size can affect the final appearance.

## Modules

1. **Academic Data Management** — add, edit, delete, search, and filter programs, sections, subjects, faculty, classrooms, academic terms, and school periods. In-use records are protected from deletion.
2. **Faculty and Room Availability** — find available resources by day/time/type; view teaching loads and actual weekly availability blocks. Mark resource unavailability, or clear its saved windows. The three daily grid blocks are 8 AM–12 PM, 1 PM–5 PM, and 5 PM–8 PM. Unavailability preferences apply across academic terms.
3. **Schedule Management** — assign a subject, section, faculty member, room, days, and start/end time. Preview conflicts before saving, edit/delete assignments, search, and view section calendars. Critical conflicts block saving; warnings require confirmation.
4. **Conflict Detection and Validation** — detect faculty/room/section overlaps, room-capacity problems, excessive teaching loads, invalid school times, and unavailable resources. Filter results and open the affected assignment with Resolve.
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
- `ui/` — login and five working module screens.
- `tests/test_system.py` — functional and UI checks.

The uploaded PDF is a visual reference. Its illustrative counts and percentages are replaced by computed values from the database.
