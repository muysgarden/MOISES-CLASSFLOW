import os
import sqlite3
import json
import sys
from pathlib import Path

DAYS = [("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"),
        ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday")]
SUBJECT_TYPES = [("Lecture", "Lecture"), ("Laboratory", "Laboratory"), ("Lecture + Lab", "Lecture + Lab")]
CCS_PROGRAMS = [("BSCS", "BS Computer Science"), ("BSIT", "BS Information Technology"),
                ("BSIS", "BS Information Systems")]

SCHEMA = """
CREATE TABLE IF NOT EXISTS programs(
    id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS terms(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, is_current INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS periods(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS subjects(
    id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 3, type TEXT NOT NULL DEFAULT 'Lecture',
    room_type TEXT NOT NULL DEFAULT 'Lecture', preferred_room_id INTEGER REFERENCES classrooms(id));
CREATE TABLE IF NOT EXISTS subject_programs(
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    program_id INTEGER NOT NULL REFERENCES programs(id),
    PRIMARY KEY(subject_id, program_id));
CREATE TABLE IF NOT EXISTS sections(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
    program_id INTEGER NOT NULL REFERENCES programs(id), enrollment INTEGER NOT NULL DEFAULT 30);
CREATE TABLE IF NOT EXISTS faculty(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', department TEXT NOT NULL DEFAULT '',
    max_units INTEGER NOT NULL DEFAULT 18);
CREATE TABLE IF NOT EXISTS classrooms(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, floor TEXT NOT NULL DEFAULT '',
    room_type TEXT NOT NULL DEFAULT 'Lecture', capacity INTEGER NOT NULL DEFAULT 40);
CREATE TABLE IF NOT EXISTS schedules(
    id INTEGER PRIMARY KEY,
    term_id INTEGER NOT NULL REFERENCES terms(id),
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    section_id INTEGER NOT NULL REFERENCES sections(id),
    faculty_id INTEGER NOT NULL REFERENCES faculty(id),
    room_id INTEGER NOT NULL REFERENCES classrooms(id),
    day TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sched_term_day ON schedules(term_id, day);
CREATE TABLE IF NOT EXISTS sample_records(
    table_name TEXT NOT NULL, record_id INTEGER NOT NULL, snapshot TEXT NOT NULL,
    PRIMARY KEY(table_name, record_id));
CREATE TABLE IF NOT EXISTS sample_subject_links(
    subject_id INTEGER NOT NULL, program_id INTEGER NOT NULL,
    PRIMARY KEY(subject_id, program_id));
"""

SAMPLE_TABLES = (
    "terms", "periods", "programs", "subjects", "sections",
    "faculty", "classrooms", "schedules",
)


def _snapshot(record):
    return json.dumps(list(tuple(record)), ensure_ascii=False)


def sample_count():
    """Count still-existing, explicitly marked sample rows (never infer from names)."""
    return sum(conn.execute(
        f"SELECT COUNT(*) FROM sample_records m JOIN {table} t ON t.id=m.record_id "
        "WHERE m.table_name=?", (table,)
    ).fetchone()[0] for table in SAMPLE_TABLES)


def clear_sample_data():
    """Remove only original tagged samples, atomically; leave other records alone.

    If samples were edited, or new records reference them, cleanup refuses
    rather than making irreversible guesses about ownership.
    """
    if not sample_count():
        return 0
    try:
        with conn:
            tagged = {}
            for table in SAMPLE_TABLES:
                tagged[table] = []
                for mark in conn.execute(
                    "SELECT record_id, snapshot FROM sample_records WHERE table_name=?",
                    (table,)
                ).fetchall():
                    record = conn.execute(
                        f"SELECT * FROM {table} WHERE id=?", (mark["record_id"],)
                    ).fetchone()
                    if record is None:
                        continue
                    if _snapshot(record) != mark["snapshot"]:
                        raise ValueError(
                            f"Sample {table} record #{mark['record_id']} was edited. "
                            "Review it manually before clearing samples."
                        )
                    tagged[table].append(mark["record_id"])
            sample_links = {
                (r["subject_id"], r["program_id"]) for r in conn.execute(
                    "SELECT subject_id, program_id FROM sample_subject_links"
                )
            }
            for sid in tagged["subjects"]:
                links = {
                    (r["subject_id"], r["program_id"]) for r in conn.execute(
                        "SELECT subject_id, program_id FROM subject_programs WHERE subject_id=?",
                        (sid,)
                    )
                }
                if not links <= sample_links:
                    raise ValueError(
                        "A demo subject has new program assignments. "
                        "Review those relationships before clearing samples."
                    )
            # Availability windows are entered by the administrator and are
            # not demo records. Never silently erase those windows or leave
            # them pointing at a resource removed by cleanup.
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"
            ).fetchone():
                for kind, table in (("faculty", "faculty"), ("room", "classrooms")):
                    for rid in tagged[table]:
                        if conn.execute(
                            "SELECT 1 FROM unavailable WHERE kind=? AND resource_id=? LIMIT 1",
                            (kind, rid)
                        ).fetchone():
                            raise ValueError(
                                "A demo faculty member or room has manually blocked times. "
                                "Remove those unavailable windows in Module 2 before clearing samples."
                            )
            for sid, pid in sample_links:
                if sid in tagged["subjects"]:
                    conn.execute(
                        "DELETE FROM subject_programs WHERE subject_id=? AND program_id=?",
                        (sid, pid)
                    )
            removed = 0
            for table in ("schedules", "subjects", "sections", "faculty",
                          "classrooms", "programs", "periods", "terms"):
                for rid in tagged[table]:
                    removed += conn.execute(
                        f"DELETE FROM {table} WHERE id=?", (rid,)
                    ).rowcount
            conn.execute("DELETE FROM sample_subject_links")
            conn.execute("DELETE FROM sample_records")
            return removed
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            "Some sample records are now used by other data. "
            "Review the linked schedules, subjects, or sections first; no records were removed."
        ) from exc

conn = None


def default_path():
    if os.environ.get("CLASSFLOW_DB"):
        return Path(os.environ["CLASSFLOW_DB"])
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    return base / "classflow.db"


def init(path=None):
    global conn
    conn = sqlite3.connect(str(path or default_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    faculty_columns = {r["name"] for r in conn.execute("PRAGMA table_info(faculty)")}
    if "email" not in faculty_columns:
        conn.execute("ALTER TABLE faculty ADD COLUMN email TEXT NOT NULL DEFAULT ''")
    subject_columns = {r["name"] for r in conn.execute("PRAGMA table_info(subjects)")}
    if "preferred_room_id" not in subject_columns:
        conn.execute("ALTER TABLE subjects ADD COLUMN preferred_room_id INTEGER REFERENCES classrooms(id)")
    room_renames = [
        ("Room 201", "Room 103", "1st Floor"),
        ("Room 202", "Room 104", "1st Floor"),
        ("Room 305", "Room 203", "2nd Floor"),
        ("Comp Lab 3", "Room 204", "2nd Floor"),
        ("Innovation Lab", "Room 205", "2nd Floor"),
    ]
    for old_name, new_name, floor in room_renames:
        existing = conn.execute("SELECT id FROM classrooms WHERE name=?", (old_name,)).fetchone()
        collision = conn.execute("SELECT 1 FROM classrooms WHERE name=?", (new_name,)).fetchone()
        if existing and not collision:
            conn.execute("UPDATE classrooms SET name=?, floor=? WHERE id=?", (new_name, floor, existing["id"]))

    conn.execute("""DELETE FROM programs WHERE code='BSEMC'
                    AND NOT EXISTS (SELECT 1 FROM sections WHERE sections.program_id=programs.id)
                    AND NOT EXISTS (SELECT 1 FROM subject_programs WHERE subject_programs.program_id=programs.id)""")
    conn.execute("""UPDATE subjects SET preferred_room_id = COALESCE(
                       (SELECT room_id FROM schedules WHERE schedules.subject_id=subjects.id ORDER BY id LIMIT 1),
                       (SELECT id FROM classrooms WHERE classrooms.room_type=subjects.room_type ORDER BY id LIMIT 1))
                    WHERE preferred_room_id IS NULL""")
    conn.execute("""UPDATE subjects SET room_type=(
                       SELECT room_type FROM classrooms WHERE classrooms.id=subjects.preferred_room_id)
                    WHERE preferred_room_id IS NOT NULL""")
    conn.commit()
    return conn


def rows(sql, params=()):
    return conn.execute(sql, params).fetchall()


def row(sql, params=()):
    return conn.execute(sql, params).fetchone()


def is_empty():
    return row("SELECT COUNT(*) AS n FROM programs")["n"] == 0


def seed(reset=False):
    c = conn
    if reset:
        for t in ("schedules", "subject_programs", "subjects", "sections", "faculty", "classrooms",
                  "programs", "periods", "terms"):
            c.execute(f"DELETE FROM {t}")
    if not is_empty():
        return False
    original_ids = {
        table: {r["id"] for r in rows(f"SELECT id FROM {table}")}
        for table in SAMPLE_TABLES
    }
    original_links = {
        tuple(r) for r in rows("SELECT subject_id, program_id FROM subject_programs")
    }

    def hm(h, m=0):
        return h * 60 + m

    c.execute("INSERT INTO terms(name, is_current) VALUES('1st Semester, A.Y. 2025–2026', 1)")
    c.execute("INSERT INTO terms(name, is_current) VALUES('2nd Semester, A.Y. 2025–2026', 0)")
    term = row("SELECT id FROM terms WHERE is_current=1")["id"]
    c.execute("INSERT INTO periods(name, start_min, end_min) VALUES('Regular Classes', ?, ?)", (hm(7), hm(17)))

    prog = {}
    for code, name in CCS_PROGRAMS:
        prog[code] = c.execute("INSERT INTO programs(code, name) VALUES(?,?)", (code, name)).lastrowid

    subj = {}
    for code, title, units, typ, plist, rt in [
        ("CS 101", "Introduction to Computing", 3, "Lecture", ["BSCS"], "Lecture"),
        ("CS 120", "Computer Programming 1", 3, "Lecture + Lab", ["BSCS"], "Laboratory"),
        ("CS 205", "Data Structures & Algorithms", 3, "Lecture + Lab", ["BSCS"], "Lecture"),
        ("IT 214", "Web Systems & Technologies", 3, "Laboratory", ["BSIT"], "Laboratory"),
        ("CS 220", "Software Engineering", 3, "Laboratory", ["BSCS"], "Laboratory"),
        ("CS 310", "Database Management Systems", 3, "Lecture + Lab", ["BSCS"], "Lecture"),
        ("IT 301", "Network Administration", 3, "Laboratory", ["BSIT"], "Laboratory"),
        ("IT 302", "Systems Integration & Architecture", 3, "Lecture", ["BSIT"], "Lecture"),
        ("CS 410", "Capstone Project 1", 3, "Lecture", ["BSCS"], "Lecture"),
        ("GE 108", "Ethics in Information Technology", 3, "Lecture", ["BSCS", "BSIT"], "Lecture"),
        ("MATH 204", "Discrete Mathematics", 3, "Lecture", ["BSCS"], "Lecture"),
    ]:
        sid = c.execute("INSERT INTO subjects(code,title,units,type,room_type) VALUES(?,?,?,?,?)",
                        (code, title, units, typ, rt)).lastrowid
        for p in plist:
            c.execute("INSERT INTO subject_programs VALUES(?,?)", (sid, prog[p]))
        subj[code] = sid

    sec = {}
    for name, p, n in [("BSCS 1A", "BSCS", 28), ("BSCS 1B", "BSCS", 38), ("BSCS 2A", "BSCS", 22),
                       ("BSCS 3A", "BSCS", 30), ("BSCS 4A", "BSCS", 28), ("BSIT 2A", "BSIT", 28),
                       ("BSIT 2B", "BSIT", 30), ("BSIT 3A", "BSIT", 29), ("BSIT 3B", "BSIT", 27)]:
        sec[name] = c.execute("INSERT INTO sections(name, program_id, enrollment) VALUES(?,?,?)",
                              (name, prog[p], n)).lastrowid

    fac = {}
    for name, dept, mx in [("Dr. Elena Santos", "Computer Science", 18), ("Prof. Miguel Cruz", "Information Technology", 12),
                           ("Dr. Andrea Lim", "Computer Science", 15), ("Prof. Paolo Garcia", "General Education", 18),
                           ("Prof. Rosa Dizon", "Mathematics", 18)]:
        fac[name.split()[-1]] = c.execute("INSERT INTO faculty(name, department, max_units) VALUES(?,?,?)",
                                          (name, dept, mx)).lastrowid

    room = {}
    for name, floor, rt, cap in [("Room 103", "1st Floor", "Lecture", 40), ("Room 104", "1st Floor", "Lecture", 30),
                                 ("Room 203", "2nd Floor", "Lecture", 45), ("Room 204", "2nd Floor", "Laboratory", 30),
                                 ("Room 205", "2nd Floor", "Laboratory", 30)]:
        room[name] = c.execute("INSERT INTO classrooms(name, floor, room_type, capacity) VALUES(?,?,?,?)",
                               (name, floor, rt, cap)).lastrowid

    def add(code, section, f, r, days, start, end):
        for d in days.split(","):
            c.execute("INSERT INTO schedules(term_id,subject_id,section_id,faculty_id,room_id,day,start_min,end_min)"
                      " VALUES(?,?,?,?,?,?,?,?)", (term, subj[code], sec[section], fac[f], room[r], d, start, end))

    add("CS 205", "BSCS 2A", "Santos", "Room 103", "Mon,Wed", hm(8), hm(9, 30))
    add("GE 108", "BSCS 2A", "Garcia", "Room 103", "Tue,Thu", hm(13), hm(14, 30))
    add("MATH 204", "BSCS 2A", "Dizon", "Room 203", "Mon,Thu", hm(15), hm(16, 30))
    add("CS 220", "BSCS 2A", "Lim", "Room 204", "Fri", hm(14), hm(17))
    add("IT 214", "BSIT 2B", "Cruz", "Room 204", "Tue,Thu", hm(10), hm(11, 30))
    add("IT 214", "BSIT 2A", "Cruz", "Room 204", "Mon,Wed", hm(10), hm(11, 30))
    add("CS 310", "BSCS 3A", "Lim", "Room 203", "Mon,Fri", hm(13), hm(14, 30))
    add("IT 302", "BSIT 3A", "Cruz", "Room 104", "Wed,Fri", hm(15), hm(16, 30))
    add("IT 302", "BSIT 3B", "Cruz", "Room 104", "Tue,Thu", hm(8), hm(9, 30))
    add("IT 214", "BSIT 3B", "Cruz", "Room 205", "Tue,Thu", hm(14), hm(15, 30))
    add("CS 101", "BSCS 1A", "Santos", "Room 103", "Mon,Wed", hm(10), hm(11, 30))
    add("CS 101", "BSCS 1B", "Santos", "Room 103", "Tue,Thu", hm(10, 30), hm(12))
    add("CS 410", "BSCS 4A", "Santos", "Room 203", "Mon", hm(8, 30), hm(10))
    add("IT 301", "BSIT 3A", "Lim", "Room 204", "Tue", hm(10), hm(11, 30))
    add("GE 108", "BSCS 3A", "Santos", "Room 103", "Mon", hm(14), hm(15, 30))
    add("GE 108", "BSCS 1B", "Garcia", "Room 104", "Mon,Wed", hm(13), hm(14, 30))
    add("CS 120", "BSCS 1A", "Lim", "Room 204", "Wed", hm(7), hm(9))

    c.execute("""UPDATE subjects SET preferred_room_id = COALESCE(
                     (SELECT room_id FROM schedules WHERE schedules.subject_id=subjects.id ORDER BY id LIMIT 1),
                     (SELECT id FROM classrooms WHERE classrooms.room_type=subjects.room_type ORDER BY id LIMIT 1))""")
    c.execute("""UPDATE subjects SET room_type=(
                     SELECT room_type FROM classrooms WHERE classrooms.id=subjects.preferred_room_id)
                 WHERE preferred_room_id IS NOT NULL""")
    for table in SAMPLE_TABLES:
        for record in rows(f"SELECT * FROM {table}"):
            if record["id"] not in original_ids[table]:
                c.execute(
                    "INSERT OR REPLACE INTO sample_records(table_name,record_id,snapshot) VALUES(?,?,?)",
                    (table, record["id"], _snapshot(record))
                )
    for link in rows("SELECT subject_id, program_id FROM subject_programs"):
        if tuple(link) not in original_links:
            c.execute("INSERT OR IGNORE INTO sample_subject_links VALUES(?,?)", tuple(link))
    c.commit()
    return True
