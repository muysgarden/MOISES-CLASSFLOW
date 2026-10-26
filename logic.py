from collections import defaultdict

import db

DAY_CODES = [d for d, _ in db.DAYS]
DAY_NAMES = dict(db.DAYS)
CRITICAL, WARNING, REVIEW = "Critical", "Warning", "Review"

CARD_TYPES = [
    ("Faculty Conflict", "Faculty Conflicts"),
    ("Classroom Conflict", "Classroom Conflicts"),
    ("Section Conflict", "Section Conflicts"),
    ("Capacity Problem", "Capacity Problems"),
    ("Teaching-Load Issue", "Teaching-Load Issues"),
    ("Invalid Time", "Invalid Time Assignments"),
]

PATTERNS = [
    ("Mon,Wed", "Monday / Wednesday"), ("Tue,Thu", "Tuesday / Thursday"), ("Mon,Fri", "Monday / Friday"),
    ("Wed,Fri", "Wednesday / Friday"), ("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"),
    ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday"),
]

CAL_START, CAL_END = 7 * 60, 20 * 60
TIME_CHOICES = [(m, "") for m in range(CAL_START, CAL_END + 1, 30)]
BLOCKS = [(8 * 60, 12 * 60, "8 AM–12 PM"), (13 * 60, 17 * 60, "1 PM–5 PM"), (17 * 60, 20 * 60, "5 PM–8 PM")]


def fmt(m):
    h, mi = divmod(int(m), 60)
    return f"{h % 12 or 12}:{mi:02d} {'AM' if h < 12 else 'PM'}"


TIME_CHOICES = [(m, fmt(m)) for m in range(CAL_START, CAL_END + 1, 30)]


def overlap(a1, a2, b1, b2):
    return a1 < b2 and b1 < a2


def school_window():
    r = db.row("SELECT MIN(start_min) AS lo, MAX(end_min) AS hi FROM periods")
    if r is None or r["lo"] is None:
        return CAL_START, CAL_END
    return r["lo"], r["hi"]


def category(code, subject_type):
    if code.upper().startswith("GE"):
        return "ged"
    return "lab" if subject_type == "Laboratory" else "major"


ROW_SQL = """
SELECT s.id, s.term_id, s.day, s.start_min, s.end_min, s.subject_id, s.section_id, s.faculty_id, s.room_id,
       sub.code AS code, sub.title AS title, sub.units AS units, sub.type AS subject_type,
       sec.name AS section, sec.enrollment AS enrollment,
       f.name AS faculty, f.max_units AS max_units,
       r.name AS room, r.capacity AS capacity, r.room_type AS room_type
FROM schedules s
JOIN subjects sub ON sub.id = s.subject_id
JOIN sections sec ON sec.id = s.section_id
JOIN faculty f ON f.id = s.faculty_id
JOIN classrooms r ON r.id = s.room_id
WHERE s.term_id = ?
"""


def schedule_rows(term_id, extra_sql="", params=()):
    out = []
    for r in db.rows(ROW_SQL + extra_sql, (term_id, *params)):
        d = dict(r)
        d["category"] = category(d["code"], d["subject_type"])
        out.append(d)
    out.sort(key=lambda d: (DAY_CODES.index(d["day"]), d["start_min"]))
    return out


def group_rows(rows):
    groups = {}
    for r in rows:
        key = (r["subject_id"], r["section_id"], r["faculty_id"], r["room_id"], r["start_min"], r["end_min"])
        g = groups.get(key)
        if g is None:
            g = {k: r[k] for k in ("subject_id", "section_id", "faculty_id", "room_id", "start_min", "end_min",
                                   "code", "title", "units", "subject_type", "section", "enrollment", "faculty",
                                   "max_units", "room", "capacity", "room_type", "category")}
            g["days"], g["ids"] = [], []
            groups[key] = g
        g["days"].append(r["day"])
        g["ids"].append(r["id"])
    out = list(groups.values())
    for g in out:
        g["days"].sort(key=DAY_CODES.index)
        g["days_label"] = " / ".join(g["days"])
        g["days_csv"] = ",".join(g["days"])
        g["hours"] = (g["end_min"] - g["start_min"]) / 60
        g["time_label"] = f"{fmt(g['start_min'])} – {fmt(g['end_min'])}"
    out.sort(key=lambda g: (g["section"], DAY_CODES.index(g["days"][0]), g["start_min"]))
    return out


def faculty_loads(term_id):
    q = """SELECT faculty_id, SUM(units) AS u FROM (
               SELECT DISTINCT s.faculty_id, s.subject_id, s.section_id, sub.units
               FROM schedules s JOIN subjects sub ON sub.id = s.subject_id WHERE s.term_id = ?)
           GROUP BY faculty_id"""
    return {r["faculty_id"]: r["u"] for r in db.rows(q, (term_id,))}


def _issue(kind, severity, desc):
    return {"type": kind, "severity": severity, "desc": desc}


def check_candidate(term_id, subject_id, section_id, faculty_id, room_id, days, start, end, exclude_ids=()):
    if end <= start:
        return [_issue("Invalid Time", CRITICAL, "End time must be after the start time.")]
    subject = db.row("SELECT * FROM subjects WHERE id=?", (subject_id,))
    section = db.row("SELECT * FROM sections WHERE id=?", (section_id,))
    faculty = db.row("SELECT * FROM faculty WHERE id=?", (faculty_id,))
    room = db.row("SELECT * FROM classrooms WHERE id=?", (room_id,))
    issues = []
    lo, hi = school_window()
    if start < lo or end > hi:
        issues.append(_issue("Invalid Time", REVIEW,
                             f"Class falls outside the school period ({fmt(lo)}–{fmt(hi)})."))

    if not days or any(day not in DAY_CODES for day in days):
        return [_issue("Invalid Time", CRITICAL, "Select at least one valid day.")]
    if any(x is None for x in (subject, section, faculty, room)):
        return [_issue("Invalid Assignment", CRITICAL, "A selected record no longer exists. Refresh and try again.")]
    if db.row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"):
        for kind, rid, name in (("faculty", faculty_id, faculty['name']), ("room", room_id, room['name'])):
            for window in db.rows("SELECT * FROM unavailable WHERE kind=? AND resource_id=?", (kind, rid)):
                if window['day'] in days and overlap(start, end, window['start_min'], window['end_min']):
                    issues.append(_issue("Unavailable Resource", CRITICAL, f"{name} is marked unavailable on {window['day']} during this time."))

    marks = ",".join("?" * len(days))
    ex = ",".join("?" * len(exclude_ids))
    extra = f" AND s.day IN ({marks})" + (f" AND s.id NOT IN ({ex})" if exclude_ids else "")
    for r in schedule_rows(term_id, extra, (*days, *exclude_ids)):
        if not overlap(start, end, r["start_min"], r["end_min"]):
            continue
        when = f"{r['day']} {fmt(r['start_min'])}–{fmt(r['end_min'])}"
        if r["faculty_id"] == faculty_id:
            issues.append(_issue("Faculty Conflict", CRITICAL,
                                 f"{faculty['name']} already teaches {r['code']} ({r['section']}) on {when}."))
        if r["room_id"] == room_id:
            issues.append(_issue("Classroom Conflict", CRITICAL,
                                 f"{room['name']} is already occupied by {r['code']} ({r['section']}) on {when}."))
        if r["section_id"] == section_id:
            issues.append(_issue("Section Conflict", CRITICAL,
                                 f"{section['name']} already has {r['code']} on {when}."))

    if room["capacity"] < section["enrollment"]:
        issues.append(_issue("Capacity Problem", WARNING,
                             f"{room['name']} capacity ({room['capacity']}) is below section enrollment "
                             f"({section['enrollment']})."))

    q = """SELECT DISTINCT s.subject_id, s.section_id, sub.units FROM schedules s
           JOIN subjects sub ON sub.id = s.subject_id WHERE s.term_id=? AND s.faculty_id=?"""
    params = [term_id, faculty_id]
    if exclude_ids:
        q += f" AND s.id NOT IN ({ex})"
        params += list(exclude_ids)
    pairs = {(r["subject_id"], r["section_id"]): r["units"] for r in db.rows(q, params)}
    pairs[(subject_id, section_id)] = subject["units"]
    total = sum(pairs.values())
    if total > faculty["max_units"]:
        issues.append(_issue("Teaching-Load Issue", WARNING,
                             f"{faculty['name']} would exceed the maximum load by {total - faculty['max_units']} "
                             f"units ({total}/{faculty['max_units']})."))

    seen, unique = set(), []
    for i in issues:
        if (i["type"], i["desc"]) not in seen:
            seen.add((i["type"], i["desc"]))
            unique.append(i)
    return unique


def save_schedule(term_id, subject_id, section_id, faculty_id, room_id, days, start, end, replace_ids=()):
    with db.conn:
        if replace_ids:
            db.conn.execute(f"DELETE FROM schedules WHERE term_id=? AND id IN ({','.join('?' * len(replace_ids))})",
                            (term_id, *replace_ids))
        for d in days:
            db.conn.execute(
                "INSERT INTO schedules(term_id,subject_id,section_id,faculty_id,room_id,day,start_min,end_min)"
                " VALUES(?,?,?,?,?,?,?,?)", (term_id, subject_id, section_id, faculty_id, room_id, d, start, end))


def delete_schedules(term_id, ids):
    if ids:
        with db.conn:
            db.conn.execute(f"DELETE FROM schedules WHERE term_id=? AND id IN ({','.join('?' * len(ids))})",
                            (term_id, *ids))


def validate_term(term_id):
    rows = schedule_rows(term_id)
    groups = group_rows(rows)
    row_group = {rid: g for g in groups for rid in g["ids"]}
    lo, hi = school_window()
    issues, seen, bad = [], set(), set()

    def push(kind, severity, g, desc):
        bad.add(id(g))
        issues.append({"type": kind, "severity": severity, "label": f"{g['code']} · {g['section']}",
                       "desc": desc, "edit_ids": list(g["ids"]), "section_id": g["section_id"]})

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    for day in DAY_CODES:
        day_rows = by_day.get(day, [])
        for i, a in enumerate(day_rows):
            ga = row_group[a["id"]]
            for b in day_rows[i + 1:]:
                gb = row_group[b["id"]]
                if ga is gb or not overlap(a["start_min"], a["end_min"], b["start_min"], b["end_min"]):
                    continue
                for kind, same, desc in (
                    ("Faculty Conflict", a["faculty_id"] == b["faculty_id"],
                     f"{a['faculty']} is assigned to {a['code']} and {b['code']} at the same time ({day})."),
                    ("Classroom Conflict", a["room_id"] == b["room_id"],
                     f"{a['room']} is already occupied by {b['code']} ({b['section']}) on {day} "
                     f"{fmt(b['start_min'])}."),
                    ("Section Conflict", a["section_id"] == b["section_id"],
                     f"{a['section']} has {a['code']} and {b['code']} overlapping on {day}."),
                ):
                    key = (kind, frozenset((id(ga), id(gb))))
                    if same and key not in seen:
                        seen.add(key)
                        push(kind, CRITICAL, ga, desc)
                        bad.add(id(gb))

    load, last = defaultdict(int), {}
    load_pairs = set()
    for g in groups:
        if g["capacity"] < g["enrollment"]:
            push("Capacity Problem", WARNING, g,
                 f"{g['room']} capacity ({g['capacity']}) is below section enrollment ({g['enrollment']}).")
        if g["end_min"] <= g["start_min"]:
            push("Invalid Time", CRITICAL, g, "End time is not after the start time.")
        elif g["start_min"] < lo or g["end_min"] > hi:
            push("Invalid Time", REVIEW, g, "Class ends outside the designated school period."
                 if g["end_min"] > hi else "Class starts outside the designated school period.")
        pair = (g["faculty_id"], g["subject_id"], g["section_id"])
        if pair not in load_pairs:
            load[g["faculty_id"]] += g["units"]
            load_pairs.add(pair)
        if db.row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"):
            for kind, rid, name in (("faculty", g['faculty_id'], g['faculty']), ("room", g['room_id'], g['room'])):
                if any(w['day'] in g['days'] and overlap(g['start_min'],g['end_min'],w['start_min'],w['end_min']) for w in db.rows("SELECT * FROM unavailable WHERE kind=? AND resource_id=?",(kind,rid))):
                    push("Unavailable Resource", CRITICAL, g, f"{name} is marked unavailable during this assignment.")
        last[g["faculty_id"]] = g
    for fid, total in load.items():
        g = last[fid]
        if total > g["max_units"]:
            push("Teaching-Load Issue", WARNING, g,
                 f"{g['faculty']} will exceed the maximum load by {total - g['max_units']} units "
                 f"({total}/{g['max_units']}).")

    order = {CRITICAL: 0, WARNING: 1, REVIEW: 2}
    issues.sort(key=lambda i: (order[i["severity"]], i["type"]))
    counts = {k: sum(1 for i in issues if i["type"] == k) for k, _ in CARD_TYPES}
    n = len(groups)
    return {"issues": issues, "counts": counts, "total": n, "bad": len(bad),
            "score": round(100 * (1 - len(bad) / n)) if n else 100,
            "critical": sum(1 for i in issues if i["severity"] == CRITICAL),
            "bad_ids": {rid for g in groups if id(g) in bad for rid in g["ids"]}}


def progress(term_id):
    need = db.row("""SELECT COUNT(*) AS n FROM sections sec
                     JOIN subject_programs sp ON sp.program_id = sec.program_id""")["n"]
    done = db.row("SELECT COUNT(*) AS n FROM (SELECT DISTINCT section_id, subject_id FROM schedules WHERE term_id=?)",
                  (term_id,))["n"]
    return min(100, round(100 * done / need)) if need else 0
