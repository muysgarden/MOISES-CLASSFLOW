import math
import re
import sqlite3

from PyQt5.QtCore import QTime, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QHeaderView, QButtonGroup, QCheckBox, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QSizePolicy, QVBoxLayout, QWidget,
)

import db
import logic
from ui.widgets import (
    Card, Combo, Page, Spin, TimeEdit, action_icon, button, clear_layout, empty_row, label, labeled, make_table,
    set_combo, text_item, widget_cell,
)

PAGE_SIZE = 8
CCS_PROGRAM_CODES = tuple(code for code, _ in db.CCS_PROGRAMS)
CCS_PROGRAM_SQL = ", ".join(f"'{code}'" for code in CCS_PROGRAM_CODES)


def F(key, label_, kind="text", **kw):
    return {"key": key, "label": label_, "kind": kind, **kw}


ENTITIES = {
    "programs": {
        "tab": "Programs", "singular": "Program", "plural": "programs", "table": "programs",
        "sql": f"SELECT id, name FROM programs WHERE code IN ({CCS_PROGRAM_SQL}) ORDER BY code",
        "headers": ["Program Name"],
        "fields": [F("name", "Program Name", "choice", options=[(name, name) for _, name in db.CCS_PROGRAMS])],
        "hint": "Program codes must be unique.",
        "in_use": "It still has sections or subjects.",
        "flex": {0: 1},
    },
    "sections": {
        "tab": "Sections", "singular": "Section", "plural": "sections", "table": "sections",
        "sql": f"""SELECT s.id, s.name, s.enrollment FROM sections s
              JOIN programs p ON p.id = s.program_id
              WHERE p.code IN ({CCS_PROGRAM_SQL}) ORDER BY s.name""",
        "headers": ["Section", "Enrolled"],
        "fields": [F("name", "Section Name", ph="e.g. BSCS 2A"),
                                     F("program_id", "Academic Program", "fk",
                                         sql=f"SELECT id, code FROM programs WHERE code IN ({CCS_PROGRAM_SQL}) ORDER BY code",
                     placeholder="Select a program"),
                   F("enrollment", "Enrolled", "int", min=1, max=500, default=30, suffix=" students")],
        "hint": "Enrollment is checked against room capacity in Module 4.",
        "in_use": "It still has scheduled classes.",
        "widths": {1: 140}, "flex": {0: 1},
    },
    "subjects": {
        "tab": "Subjects", "singular": "Subject", "plural": "subjects", "table": "subjects",
        "sql": f"""SELECT s.id, s.code, s.title, s.units,
                         COALESCE((SELECT group_concat(p.code, ' / ') FROM subject_programs sp
                                   JOIN programs p ON p.id = sp.program_id WHERE sp.subject_id = s.id
                                   AND p.code IN ({CCS_PROGRAM_SQL})), '—'),
                         s.type, COALESCE((SELECT c.room_type FROM classrooms c
                                           WHERE c.id = s.preferred_room_id), s.room_type)
                  FROM subjects s WHERE EXISTS (
                      SELECT 1 FROM subject_programs sp JOIN programs p ON p.id = sp.program_id
                      WHERE sp.subject_id = s.id AND p.code IN ({CCS_PROGRAM_SQL})) ORDER BY s.code""",
        "headers": ["Subject Code", "Subject Title", "Units", "Program", "Type", "Room"],
        "fields": [F("code", "Subject Code", ph="e.g. CS 320"),
                   F("title", "Subject Title", ph="Enter subject title"),
                   F("units", "Units", "int", min=1, max=9, default=3, suffix=" units", pair=True),
                   F("type", "Subject Type", "choice", options=db.SUBJECT_TYPES),
                   F("programs", "Academic Program", "multi"),
                                     F("preferred_room_id", "Preferred Room", "fk",
                                         sql="SELECT id, name FROM classrooms ORDER BY name", placeholder="Select a room")],
        "hint": "Subject codes must be unique.",
        "in_use": "It is already scheduled for a section.",
        "pill_col": 3,
        "fmt": {
            5: lambda value: {"Lecture": "Lecture", "Laboratory": "Lab", "Lecture + Lab": "Lec + Lab"}.get(value, value),
        },
        "widths": {0: 100, 2: 64}, "flex": {1: 4, 3: 3, 4: 2, 5: 2},
    },
    "faculty": {
        "tab": "Faculty", "singular": "Faculty", "plural": "faculty members", "table": "faculty",
        "sql": "SELECT id, name, email, department, max_units FROM faculty ORDER BY name",
        "headers": ["Name", "Email", "Department", "Max Units"],
        "fields": [F("name", "Full Name", ph="e.g. Dr. Jane Doe"),
                   F("email", "Email Address", ph="e.g. jane.doe@college.edu", required=False, maxlen=254),
                   F("department", "Department", ph="e.g. Computer Science"),
                   F("max_units", "Maximum Teaching Load", "int", min=1, max=40, default=18, suffix=" units")],
        "hint": "The maximum load is used to flag overloaded faculty in Module 4.",
        "in_use": "They are assigned to scheduled classes.",
        "widths": {3: 120}, "flex": {0: 2, 1: 3, 2: 2},
    },
    "classrooms": {
        "tab": "Classrooms", "singular": "Classroom", "plural": "classrooms", "table": "classrooms",
        "sql": "SELECT id, name, floor, room_type, capacity FROM classrooms ORDER BY name",
        "headers": ["Room", "Floor", "Type", "Capacity"],
        "fields": [F("name", "Room Name", ph="e.g. Room 107"),
               F("floor", "Floor", ph="e.g. 1st Floor", required=False),
                   F("room_type", "Room Type", "choice", options=[("Lecture","Lecture"),("Laboratory","Laboratory")]),
                   F("capacity", "Capacity", "int", min=1, max=500, default=40, suffix=" seats")],
        "hint": "Capacity is compared against section enrollment.",
        "in_use": "It is used by scheduled classes.",
        "widths": {0: 150, 3: 110}, "flex": {1: 1, 2: 2},
    },
    "terms": {
        "tab": "Academic Terms", "singular": "Academic Term", "plural": "terms", "table": "terms",
        "sql": "SELECT id, name, CASE is_current WHEN 1 THEN 'Yes' ELSE 'No' END FROM terms ORDER BY id DESC",
        "headers": ["Term", "Current"],
        "fields": [F("name", "Term Name", ph="e.g. 1st Semester, A.Y. 2025–2026"),
                   F("is_current", "Current Term", "bool", checkbox="Use as the current term")],
        "hint": "The current term is selected by default when the app opens.",
        "in_use": "It already has scheduled classes.",
        "widths": {1: 120}, "flex": {0: 1},
    },
    "periods": {
        "tab": "School Periods", "singular": "School Period", "plural": "school periods", "table": "periods",
        "sql": "SELECT id, name, start_min, end_min FROM periods ORDER BY start_min",
        "headers": ["Name", "Start", "End"],
        "fields": [F("name", "Period Name", ph="e.g. Regular Classes"),
                   F("start_min", "Start Time", "time", default=7 * 60, pair=True),
                   F("end_min", "End Time", "time", default=20 * 60)],
        "hint": "Classes outside these hours are flagged as Invalid Time.",
        "in_use": "It is in use.",
        "widths": {1: 140, 2: 140}, "flex": {0: 1},
        "fmt": {2: logic.fmt, 3: logic.fmt},
        "validate": lambda v: {"end_min": "End time must be after the start time."}
        if v["end_min"] <= v["start_min"] else {},
    },
}
ORDER = ["programs", "sections", "subjects", "faculty", "classrooms", "terms", "periods"]


class MultiCheck(QWidget):

    def __init__(self):
        super().__init__()
        self.boxes = {}
        g = QGridLayout(self)
        g.setContentsMargins(0, 2, 0, 0)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(6)
        progs = db.rows(f"SELECT id, code FROM programs WHERE code IN ({CCS_PROGRAM_SQL}) ORDER BY code")
        if not progs:
            g.addWidget(label("Add a program first (Programs tab).", "muted"), 0, 0)
        for i, p in enumerate(progs):
            cb = QCheckBox(p["code"])
            self.boxes[p["id"]] = cb
            g.addWidget(cb, i // 3, i % 3)

    def ids(self):
        return [i for i, cb in self.boxes.items() if cb.isChecked()]

    def set_ids(self, ids):
        for i, cb in self.boxes.items():
            cb.setChecked(i in ids)


class FormPanel(QFrame):

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setObjectName("recordPanel")
        self.setFixedWidth(310)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setColor(QColor(18, 39, 82, 28))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        self.ent, self.widgets, self.errors = None, {}, {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        surface = QFrame()
        surface.setObjectName("recordPanelSurface")
        outer.addWidget(surface)
        v = QVBoxLayout(surface)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName("formHead")
        hv = QHBoxLayout(head)
        hv.setContentsMargins(16, 12, 16, 10)
        hv.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title = label("", "formTitle")
        self.sub = label("", "formSub")
        title_col.addWidget(self.title)
        title_col.addWidget(self.sub)
        hv.addLayout(title_col, 1)
        v.addWidget(head)
        body = QWidget()
        self.fl = QVBoxLayout(body)
        self.fl.setContentsMargins(16, 12, 16, 14)
        self.fl.setSpacing(10)
        v.addWidget(body)

    def build(self, ent):
        self.ent, self.widgets, self.errors = ent, {}, {}
        clear_layout(self.fl)
        self.edit_banner = label("", "editing", wrap=True)
        self.edit_banner.hide()
        self.fl.addWidget(self.edit_banner)

        fields = ent["fields"]
        i = 0
        while i < len(fields):
            f = fields[i]
            if f.get("pair") and i + 1 < len(fields):
                row = QHBoxLayout()
                row.setSpacing(10)
                row.addWidget(self._field(f), 1)
                row.addWidget(self._field(fields[i + 1]), 1)
                self.fl.addLayout(row)
                i += 2
            else:
                self.fl.addWidget(self._field(f))
                i += 1

        hint = label("✓  " + ent["hint"], "hint", wrap=True)
        self.fl.addWidget(hint)
        self.fl.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.clear_btn = button("Clear", "small", self.page.clear_form)
        actions.addWidget(self.clear_btn)
        self.save_btn = button("", "primary", self.page.save)
        self.save_btn.setMinimumHeight(36)
        actions.addWidget(self.save_btn, 1)
        self.fl.addLayout(actions)
        self.set_mode(None)

    def _field(self, f):
        kind, key = f["kind"], f["key"]
        if kind == "text":
            w = QLineEdit()
            w.setPlaceholderText(f.get("ph", ""))
            if f.get("maxlen"):
                w.setMaxLength(f["maxlen"])
            w.returnPressed.connect(self.page.save)
        elif kind == "int":
            w = Spin()
            w.setRange(f["min"], f["max"])
            w.setValue(f["default"])
            w.setSuffix(f.get("suffix", ""))
        elif kind == "choice":
            w = Combo()
            for value, text in f["options"]:
                w.addItem(text, value)
        elif kind == "fk":
            w = Combo()
            w.addItem(f.get("placeholder", "Select…"), None)
            for r in db.rows(f["sql"]):
                w.addItem(r[1], r[0])
        elif kind == "bool":
            w = QCheckBox(f.get("checkbox", ""))
        elif kind == "time":
            w = TimeEdit()
            w.setTime(QTime(f["default"] // 60, f["default"] % 60))
        else:  # multi
            w = MultiCheck()
        self.widgets[key] = w

        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lab = label(f["label"].upper(), "fieldLabel")
        v.addWidget(lab)
        v.addWidget(w)
        err = label("", "err", wrap=True)
        err.hide()
        v.addWidget(err)
        self.errors[key] = err
        return box

    def set_mode(self, edit_name):
        s = self.ent["singular"]
        editing = edit_name is not None
        self.title.setText(f"{'Edit' if editing else 'Add'} {s}")
        self.sub.setText("Update this record" if editing else f"Create a {s.lower()} record for scheduling")
        self.save_btn.setText(f"💾  Save Changes" if editing else f"＋  Add {s}")
        self.clear_btn.setText("Cancel Edit" if editing else "Clear")
        self.edit_banner.setVisible(editing)
        if editing:
            self.edit_banner.setText(f"Editing “{edit_name}”. Save your changes or cancel editing.")

    def reset(self):
        for f in self.ent["fields"]:
            w, k = self.widgets[f["key"]], f["kind"]
            if k == "text":
                w.clear()
            elif k == "int":
                w.setValue(f["default"])
            elif k in ("choice", "fk"):
                w.setCurrentIndex(0)
            elif k == "bool":
                w.setChecked(False)
            elif k == "time":
                w.setTime(QTime(f["default"] // 60, f["default"] % 60))
            else:
                w.set_ids([])
        self.show_errors({})

    def load(self, row, multi=None):
        for f in self.ent["fields"]:
            w, k, key = self.widgets[f["key"]], f["kind"], f["key"]
            if k == "multi":
                w.set_ids(multi or [])
                continue
            v = row[key]
            if k == "text":
                w.setText(v)
            elif k == "int":
                w.setValue(v)
            elif k in ("choice", "fk"):
                set_combo(w, v)
            elif k == "bool":
                w.setChecked(bool(v))
            elif k == "time":
                w.setTime(QTime(v // 60, v % 60))
        self.show_errors({})

    def values(self):
        out, errs = {}, {}
        for f in self.ent["fields"]:
            w, k, key = self.widgets[f["key"]], f["kind"], f["key"]
            if k == "text":
                v = w.text().strip()
                if f.get("upper"):
                    v = v.upper()
                if not v and f.get("required", True):
                    errs[key] = f"{f['label']} is required."
            elif k == "int":
                v = w.value()
            elif k in ("choice", "fk"):
                v = w.currentData()
                if k == "fk" and v is None:
                    errs[key] = f"Please select a {f['label'].lower().replace('academic ', '')}."
            elif k == "bool":
                v = 1 if w.isChecked() else 0
            elif k == "time":
                t = w.time()
                v = t.hour() * 60 + t.minute()
            else:
                v = w.ids()
            out[key] = v
        return out, errs

    def show_errors(self, errs):
        for key, lab in self.errors.items():
            msg = errs.get(key)
            lab.setText(msg or "")
            lab.setVisible(bool(msg))
        if errs:
            first = next((f["key"] for f in self.ent["fields"] if f["key"] in errs), None)
            w = self.widgets.get(first)
            if w is not None:
                w.setFocus()


class AcademicPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.tab, self.edit_id, self.page_no = "subjects", None, 0

        self.add_header("MODULE 01", "Academic Data Management",
            "Manage the core academic records used to build accurate class schedules.",
            [button("+  Add New Record", "primary", self.new_record)])

        bar = QFrame()
        bar.setObjectName("tabbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 4, 4, 4)
        bl.setSpacing(4)
        self.tab_group = QButtonGroup(self)
        self.tab_btns = {}
        for key in ORDER:
            b = button(ENTITIES[key]["tab"], "tab")
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            self.tab_group.addButton(b)
            self.tab_btns[key] = b
            bl.addWidget(b)
        self.lay.addWidget(bar)

        self.search = QLineEdit()
        self.search.setFixedWidth(190)
        self.search.textChanged.connect(self._filters_changed)
        self.prog_filter = Combo()
        self.prog_filter.setFixedWidth(135)
        self.prog_filter.currentIndexChanged.connect(self._filters_changed)
        self.type_filter = Combo()
        self.type_filter.setFixedWidth(120)
        self.type_filter.currentIndexChanged.connect(self._filters_changed)
        self.card = Card("Subjects", "", right=[self.search, self.prog_filter, self.type_filter])
        self.table_holder = QVBoxLayout()
        self.table_holder.setContentsMargins(0, 0, 0, 0)
        holder = QWidget()
        holder.setLayout(self.table_holder)
        self.card.add(holder)
        foot = QFrame()
        foot.setObjectName("cardFoot")
        foot.hide()
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 8, 16, 8)
        self.showing = label("", "muted", wrap=True)
        fl.addWidget(self.showing)
        fl.addStretch()
        self.pager = QHBoxLayout()
        self.pager.setSpacing(6)
        fl.addLayout(self.pager)
        self.card.add(foot)
        self.card_foot = foot

        self.form = FormPanel(self)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self.card, 1)
        content_layout.addWidget(self.form)
        self.lay.addWidget(content, 1)

        self._ids = []
        self.set_tab("subjects")

    def new_record(self):
        self.edit_id = None
        self.form.reset()
        self.form.set_mode(None)
        self.form.widgets[self.ent["fields"][0]["key"]].setFocus()

    @property
    def ent(self):
        return ENTITIES[self.tab]

    def open(self, tab=None, edit_id=None):
        if tab and tab != self.tab:
            self.set_tab(tab)
        else:
            self.refresh()
        if edit_id:
            self.edit(edit_id)

    def set_tab(self, key):
        self.tab, self.edit_id, self.page_no = key, None, 0
        self.tab_btns[key].setChecked(True)
        ent = self.ent
        self.search.blockSignals(True)
        self.search.clear()
        self.search.setPlaceholderText(f"Search {ent['plural']}…")
        self.search.blockSignals(False)
        self.card.title_label.setText(ent["tab"])
        self._fill_program_filter()
        self._fill_type_filter()
        self.prog_filter.setVisible(key == "subjects")
        self.type_filter.setVisible(key == "subjects")
        self.form.build(ent)
        self._rebuild_table()
        self.refresh()

    def _fill_program_filter(self):
        self.prog_filter.blockSignals(True)
        self.prog_filter.clear()
        self.prog_filter.addItem("All programs", None)
        for r in db.rows(f"SELECT code FROM programs WHERE code IN ({CCS_PROGRAM_SQL}) ORDER BY code"):
            self.prog_filter.addItem(r["code"], r["code"])
        self.prog_filter.blockSignals(False)

    def _fill_type_filter(self):
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self.type_filter.addItem("All types", None)
        for value, text in db.SUBJECT_TYPES:
            self.type_filter.addItem(text, value)
        self.type_filter.blockSignals(False)

    def _filters_changed(self, *_):
        self.page_no = 0
        self.refresh()

    def new_record(self):
        self.clear_form()

    def clear_form(self):
        self.edit_id = None
        self.form.reset()
        self.form.set_mode(None)
        self.table.clearSelection()
        self.refresh()

    def _rebuild_table(self):
        clear_layout(self.table_holder)
        n = len(self.ent["headers"])
        fixed = {0: 44, n + 1: 170, **{col + 1: width for col, width in self.ent.get("widths", {}).items()}}
        flex = {col + 1: weight for col, weight in (self.ent.get("flex") or {}).items()}
        self.table = make_table(["#"] + self.ent["headers"] + ["Actions"], row_h=50,
                    fixed=fixed, flex=flex)
        if self.tab == "subjects":
            program_col = self.ent["headers"].index("Program") + 1
            self.table.horizontalHeaderItem(program_col).setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._row_action(r))
        self.table_holder.addWidget(self.table)

    def _row_action(self, row):
        if 0 <= row < len(self._ids):
            self.edit(self._ids[row])

    def _all_rows(self):
        fmt = self.ent.get("fmt", {})
        out = []
        for r in db.rows(self.ent["sql"]):
            vals = list(tuple(r))
            for i, fn in fmt.items():
                vals[i] = fn(vals[i])
            out.append(tuple(vals))
        return out

    def refresh(self, focus_id=None):
        ent = self.ent
        everything = self._all_rows()
        rows = everything
        q = self.search.text().strip().lower()
        if q:
            rows = [r for r in rows if any(q in str(c).lower() for c in r[1:])]
        if self.tab == "subjects" and self.prog_filter.currentData():
            code = self.prog_filter.currentData()
            rows = [r for r in rows if code in str(r[4]).split(" / ")]
        if self.tab == "subjects" and self.type_filter.currentData():
            subject_type = self.type_filter.currentData()
            subject_type = {"Laboratory": "Lab", "Lecture + Lab": "Lec + Lab"}.get(subject_type, subject_type)
            rows = [r for r in rows if r[5] == subject_type]
        total = len(rows)
        pages = max(1, math.ceil(total / PAGE_SIZE))
        if focus_id is not None:
            idx = next((i for i, r in enumerate(rows) if r[0] == focus_id), None)
            if idx is not None:
                self.page_no = idx // PAGE_SIZE
        self.page_no = max(0, min(self.page_no, pages - 1))
        start = self.page_no * PAGE_SIZE
        chunk = rows[start:start + PAGE_SIZE]

        if self.tab == "subjects":
            n_prog = db.row("SELECT COUNT(*) AS n FROM programs")["n"]
            self.card.subtitle.setText(f"{len(everything)} subjects across {n_prog} academic programs")
        else:
            self.card.subtitle.setText(f"{len(everything)} {ent['plural']}")

        t = self.table
        t.clearSpans()
        t.setRowCount(0)
        self._ids = [r[0] for r in chunk]
        if not chunk:
            empty_row(t, "No matching records." if q or self.prog_filter.currentData() or self.type_filter.currentData()
                      else f"No {ent['plural']} yet — add one using the form.")
        else:
            t.setRowCount(len(chunk))
            n = len(ent["headers"])
            for ri, r in enumerate(chunk):
                number = text_item(start + ri + 1, muted=True)
                number.setTextAlignment(Qt.AlignCenter)
                t.setItem(ri, 0, number)
                for ci in range(n):
                    val = r[ci + 1]
                    if ent.get("pill_col") == ci:
                        pill = label(str(val), "pill")
                        pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                        widget_cell(t, ri, ci + 1, pill, Qt.AlignCenter)
                    else:
                        t.setItem(ri, ci + 1, text_item(val, bold=(ci == 0)))
                self._action_cell(ri, n + 1, r)
        t.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        for row_index in range(t.rowCount()):
            t.setRowHeight(row_index, 50 if chunk else 70)
        t.clearSelection()
        if self.edit_id in self._ids:
            t.selectRow(self._ids.index(self.edit_id))

        self.card_foot.hide()
        self._build_pager(pages)

    def _action_cell(self, ri, col, r):
        host = QWidget()
        host.setObjectName("cell")
        h = QHBoxLayout(host)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(2)
        h.addStretch()
        rid, name = r[0], r[1]
        e = button("Edit", "linkbtn", lambda _=False, i=rid: self.edit(i))
        e.setIcon(action_icon("pencil", "#236995"))
        d = button("Delete", "danger", lambda _=False, i=rid, n=name: self.delete(i, n))
        d.setIcon(action_icon("trash", "#71819b"))
        e.setToolTip("Edit this record")
        d.setToolTip("Delete this record")
        h.addWidget(e)
        h.addWidget(d)
        self.table.setCellWidget(ri, col, host)

    def _build_pager(self, pages):
        clear_layout(self.pager)
        if pages <= 1:
            return
        prev = button("Previous", "pg", lambda: self._goto(self.page_no - 1))
        prev.setEnabled(self.page_no > 0)
        self.pager.addWidget(prev)
        lo = max(0, min(self.page_no - 2, pages - 5))
        for p in range(lo, min(pages, lo + 5)):
            b = button(str(p + 1), "pg", lambda _=False, i=p: self._goto(i))
            b.setCheckable(True)
            b.setChecked(p == self.page_no)
            self.pager.addWidget(b)
        nxt = button("Next", "pg", lambda: self._goto(self.page_no + 1))
        nxt.setEnabled(self.page_no < pages - 1)
        self.pager.addWidget(nxt)

    def _goto(self, p):
        self.page_no = p
        self.refresh()

    def edit(self, rid):
        ent = self.ent
        r = db.row(f"SELECT * FROM {ent['table']} WHERE id=?", (rid,))
        if r is None:
            self.refresh()
            return
        multi = None
        if self.tab == "subjects":
            multi = [x["program_id"] for x in db.rows("SELECT program_id FROM subject_programs WHERE subject_id=?", (rid,))]
        self.edit_id = rid
        self.form.load(r, multi)
        self.form.set_mode(r[ent["fields"][0]["key"]])
        self.form.widgets[ent["fields"][0]["key"]].setFocus()
        self.refresh()

    def save(self):
        ent, tab = self.ent, self.tab
        vals, errs = self.form.values()
        if not errs and ent.get("validate"):
            errs = ent["validate"](vals)
        self.form.show_errors(errs)
        if errs:
            return

        cols = [f["key"] for f in ent["fields"] if f["kind"] != "multi"]
        if tab == "programs":
            code_by_name = {name: code for code, name in db.CCS_PROGRAMS}
            vals["code"] = code_by_name[vals["name"]]
            cols = ["code", "name"]
        params = [vals[c] for c in cols]
        editing = self.edit_id is not None
        try:
            with db.conn:
                if editing:
                    db.conn.execute(f"UPDATE {ent['table']} SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                                    params + [self.edit_id])
                    rid = self.edit_id
                else:
                    cur = db.conn.execute(
                        f"INSERT INTO {ent['table']}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})", params)
                    rid = cur.lastrowid
                if tab == "subjects":
                    db.conn.execute("DELETE FROM subject_programs WHERE subject_id=?", (rid,))
                    for pid in vals["programs"]:
                        db.conn.execute("INSERT INTO subject_programs VALUES(?,?)", (rid, pid))
                if tab == "terms" and vals["is_current"]:
                    db.conn.execute("UPDATE terms SET is_current=0 WHERE id<>?", (rid,))
        except sqlite3.IntegrityError as e:
            self._integrity_error(e)
            return

        name = vals[cols[0]]
        self.edit_id = None
        self.form.reset()
        self.form.set_mode(None)
        self.refresh(focus_id=rid)
        self.win.data_changed()
        self.win.notify(f"{ent['singular']} “{name}” {'updated' if editing else 'added'}.", "success")

    def _integrity_error(self, e):
        m = re.search(r"UNIQUE constraint failed: \w+\.(\w+)", str(e))
        if m and m.group(1) in self.form.widgets:
            key = m.group(1)
            label_ = next(f["label"] for f in self.ent["fields"] if f["key"] == key)
            self.form.show_errors({key: f"{label_} already exists. Please use a different one."})
        else:
            self.win.notify("That record could not be saved because it conflicts with existing data.", "error")

    def confirm(self, title, text):
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No) == QMessageBox.Yes

    def delete(self, rid, name):
        ent = self.ent
        if not self.confirm(f"Delete {ent['singular'].lower()}",
                            f"Delete {ent['singular'].lower()} “{name}”?\nThis cannot be undone."):
            return
        try:
            with db.conn:
                if self.tab == "subjects":
                    db.conn.execute("DELETE FROM subject_programs WHERE subject_id=?", (rid,))
                db.conn.execute(f"DELETE FROM {ent['table']} WHERE id=?", (rid,))
        except sqlite3.IntegrityError:
            self.win.notify(f"“{name}” can't be deleted. {ent['in_use']}", "error")
            return
        if self.edit_id == rid:
            self.edit_id = None
            self.form.reset()
            self.form.set_mode(None)
        self.refresh()
        self.win.data_changed()
        self.win.notify(f"{ent['singular']} “{name}” deleted.", "success")
