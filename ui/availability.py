"""Readable, time-specific faculty and room availability (Module 2)."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCompleter, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

import db
import logic
from ui.widgets import Page, Combo, button, clear_layout


def init_availability():
    db.conn.execute('''CREATE TABLE IF NOT EXISTS unavailable(
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, resource_id INTEGER NOT NULL,
        day TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER NOT NULL)''')
    db.conn.commit()


def unavailable(kind, rid, day, start, end):
    return any(logic.overlap(start, end, r['start_min'], r['end_min']) for r in db.rows(
        'SELECT start_min,end_min FROM unavailable WHERE kind=? AND resource_id=? AND day=?',
        (kind, rid, day),
    ))


def searchable_combo():
    combo = Combo()
    combo.setEditable(True)
    combo.setInsertPolicy(combo.NoInsert)
    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)
    return combo


class AvailabilityPage(Page):
    def __init__(self, win):
        super().__init__(win)
        init_availability()
        self.setObjectName("availabilityPage")
        self.setStyleSheet("""
            #availabilityPage QLabel#availHeading { color: #19263B; font-size: 18px; font-weight: 750; }
            #availabilityPage QLabel#availName { color: #19263B; font-size: 15px; font-weight: 700; }
            #availabilityPage QLabel#availInfo { color: #64748B; font-size: 12px; }
            #availabilityPage QLabel#availStatus { border-radius: 10px; padding: 7px 13px;
                font-size: 12px; font-weight: 750; }
            #availabilityPage QLabel#availCaption { color: #708097; font-size: 12px; }
            #availabilityPage QLabel#availCount { color: #2955CE; font-size: 22px; font-weight: 750; }
            #availabilityPage QFrame#availPanel, #availabilityPage QFrame#availItem {
                background: white; border: 1px solid #E4EAF3; border-radius: 13px; }
            #availabilityPage QPushButton#availToggle {
                border: 1px solid #C7D7FA; background: white; color: #2955CE;
                border-radius: 9px; padding: 10px 16px; font-weight: 700; }
            #availabilityPage QPushButton#availRemove {
                background: #FFF0F0; color: #AC4242; border: none; border-radius: 7px;
                padding: 6px 12px; }
            #availabilityPage QTabWidget::pane { border: none; }
            #availabilityPage QTabBar::tab { background: white; color: #52627A;
                min-width: 150px; padding: 12px 20px; margin-right: 8px;
                border-radius: 9px; font-weight: 650; }
            #availabilityPage QTabBar::tab:selected { background: #EBE9FC; color: #4032A3; }
            #availabilityPage QLineEdit, #availabilityPage QComboBox {
                background: white; border: 1px solid #DDE6F4; border-radius: 8px;
                padding: 8px 10px; min-height: 27px; }
        """)
        self.add_header(
            "MODULE 02", "Faculty & Room Availability",
            "See who and what is free for the exact day and time you choose."
        )
        self._build_filters()
        self._build_results()
        self._build_editor()
        self.finish()
        self.refresh()

    @staticmethod
    def _label(value, name="availCaption"):
        widget = QLabel(str(value))
        widget.setObjectName(name)
        return widget

    def _build_filters(self):
        panel = QFrame()
        panel.setObjectName("availPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(21, 17, 21, 19)
        outer.setSpacing(12)
        outer.addWidget(self._label("Check availability", "availHeading"))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.day = Combo()
        for code, name in db.DAYS:
            self.day.addItem(name, code)
        self.start = Combo()
        self.end = Combo()
        for minute, title in logic.TIME_CHOICES:
            self.start.addItem(title, minute)
            self.end.addItem(title, minute)
        self.start.setCurrentIndex(self.start.findData(8 * 60))
        self.end.setCurrentIndex(self.end.findData(9 * 60))
        self.room_type = Combo()
        self.room_type.addItem("All room types", None)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a faculty or room name…")
        for title, control, stretch in (
            ("Day", self.day, 2),
            ("Start time", self.start, 2),
            ("End time", self.end, 2),
            ("Search", self.search, 3),
        ):
            column = QVBoxLayout()
            column.setSpacing(6)
            column.addWidget(self._label(title))
            column.addWidget(control)
            row.addLayout(column, stretch)
        outer.addLayout(row)
        self.day.currentIndexChanged.connect(self.refresh)
        self.start.currentIndexChanged.connect(self.refresh)
        self.end.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.lay.addWidget(panel)

    def _build_results(self):
        self.tabs = QTabWidget()
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.addTab(QWidget(), "Faculty")
        self.tabs.addTab(QWidget(), "Classrooms")
        self.lay.addWidget(self.tabs)
        self.tab_contents = []
        self.grids = []
        self.counts = []
        self.empty_labels = []
        for index in range(2):
            widget = self.tabs.widget(index)
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 8, 0, 12)
            layout.setSpacing(12)
            head = QHBoxLayout()
            headline = self._label("", "availHeading")
            counter = self._label("", "availCount")
            head.addWidget(headline)
            head.addStretch()
            head.addWidget(counter)
            layout.addLayout(head)
            if index == 1:
                filter_row = QHBoxLayout()
                filter_row.addWidget(self._label("Room type"))
                filter_row.addWidget(self.room_type)
                filter_row.addStretch()
                layout.addLayout(filter_row)
            grid = QGridLayout()
            grid.setHorizontalSpacing(13)
            grid.setVerticalSpacing(13)
            layout.addLayout(grid)
            empty = self._label("")
            layout.addWidget(empty)
            layout.addStretch()
            self.tab_contents.append(headline)
            self.grids.append(grid)
            self.counts.append(counter)
            self.empty_labels.append(empty)
        self.room_type.currentIndexChanged.connect(self.refresh)
        self.summary = self._label("")
        self.lay.addWidget(self.summary)

    def _build_editor(self):
        toggle = QPushButton("Manage unavailable times  ▾")
        toggle.setObjectName("availToggle")
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.clicked.connect(self.update_availability)
        self.lay.addWidget(toggle, 0, Qt.AlignLeft)
        self.editor_toggle = toggle
        self.editor = QFrame()
        self.editor.setObjectName("availPanel")
        v = QVBoxLayout(self.editor)
        v.setContentsMargins(21, 18, 21, 20)
        v.setSpacing(12)
        v.addWidget(self._label("Mark a faculty member or room as unavailable", "availHeading"))
        v.addWidget(self._label("This creates an unavailable window, separate from scheduled classes."))
        fields = QHBoxLayout()
        fields.setSpacing(12)
        self.resource = searchable_combo()
        self.resource.addItem("Choose faculty or classroom…", None)
        self.block_day = Combo()
        for code, name in db.DAYS:
            self.block_day.addItem(name, code)
        self.block_start = Combo()
        self.block_end = Combo()
        for minute, title in logic.TIME_CHOICES:
            self.block_start.addItem(title, minute)
            self.block_end.addItem(title, minute)
        self.block_start.setCurrentIndex(self.block_start.findData(8 * 60))
        self.block_end.setCurrentIndex(self.block_end.findData(9 * 60))
        for title, control in (
            ("Faculty / room", self.resource), ("Day", self.block_day),
            ("From", self.block_start), ("Until", self.block_end),
        ):
            col = QVBoxLayout()
            col.setSpacing(5)
            col.addWidget(self._label(title))
            col.addWidget(control)
            fields.addLayout(col, 3 if title == "Faculty / room" else 2)
        v.addLayout(fields)
        save = button("Mark unavailable", "primary", self.save_unavailability)
        v.addWidget(save, 0, Qt.AlignRight)
        v.addWidget(self._label("Saved unavailable windows", "availHeading"))
        self.blocks = QVBoxLayout()
        v.addLayout(self.blocks)
        self.editor.hide()
        self.lay.addWidget(self.editor)

    def update_availability(self):
        opened = self.editor.isHidden()
        self.editor.setVisible(opened)
        self.editor_toggle.setText(
            "Hide unavailable times  ▴" if opened else "Manage unavailable times  ▾"
        )
        if opened:
            self._reload_resources()
            self._reload_blocks()

    def _reload_resources(self):
        current = self.resource.currentData()
        self.resource.blockSignals(True)
        self.resource.clear()
        self.resource.addItem("Choose faculty or classroom…", None)
        for kind, table, prefix in (
            ("faculty", "faculty", "Faculty"), ("room", "classrooms", "Room"),
        ):
            for record in db.rows(f"SELECT id,name FROM {table} ORDER BY name"):
                self.resource.addItem(f"{prefix} · {record['name']}", (kind, record["id"]))
        self.resource.setCurrentIndex(max(0, self.resource.findData(current)))
        self.resource.blockSignals(False)
        if self.resource.currentIndex() == 0:
            self.resource.lineEdit().clear()
            self.resource.lineEdit().setPlaceholderText("Type to find faculty or room…")

    def _reload_blocks(self):
        clear_layout(self.blocks)
        items = db.rows("SELECT * FROM unavailable ORDER BY day,start_min,id")
        if not items:
            self.blocks.addWidget(self._label("No unavailable windows recorded yet."))
        for item in items:
            table = "faculty" if item["kind"] == "faculty" else "classrooms"
            resource = db.row(f"SELECT name FROM {table} WHERE id=?", (item["resource_id"],))
            name = resource["name"] if resource else "Removed record"
            day = dict(db.DAYS).get(item["day"], item["day"])
            row = QHBoxLayout()
            row.addWidget(self._label(
                f"{name}  ·  {day}  ·  {logic.fmt(item['start_min'])}–{logic.fmt(item['end_min'])}",
                "availInfo",
            ))
            row.addStretch()
            remove = QPushButton("Remove")
            remove.setObjectName("availRemove")
            remove.clicked.connect(lambda _=False, rid=item["id"]: self.remove_unavailability(rid))
            row.addWidget(remove)
            self.blocks.addLayout(row)

    def save_unavailability(self):
        typed = self.resource.currentText().strip()
        i = next((i for i in range(1, self.resource.count())
                  if self.resource.itemText(i).casefold() == typed.casefold()), -1)
        resource = self.resource.itemData(i) if i >= 0 else None
        if resource is None:
            self.win.notify("Choose a faculty member or classroom from the suggestions.", "warning")
            return
        start, end = self.block_start.currentData(), self.block_end.currentData()
        if end <= start:
            self.win.notify("End time must be later than start time.", "warning")
            return
        day = self.block_day.currentData()
        if db.row('''SELECT 1 FROM unavailable WHERE kind=? AND resource_id=? AND day=?
                     AND start_min<? AND end_min>? LIMIT 1''',
                  (resource[0], resource[1], day, end, start)):
            self.win.notify("This resource already has an overlapping unavailable window.", "warning")
            return
        with db.conn:
            db.conn.execute(
                "INSERT INTO unavailable(kind,resource_id,day,start_min,end_min) VALUES(?,?,?,?,?)",
                (resource[0], resource[1], day, start, end),
            )
        self.refresh()
        self.win.notify("Unavailable time saved.", "success")

    def remove_unavailability(self, rid):
        if QMessageBox.question(
            self, "Remove unavailable time?", "Remove this blocked time window?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        with db.conn:
            db.conn.execute("DELETE FROM unavailable WHERE id=?", (rid,))
        self.refresh()
        self.win.notify("Unavailable time removed.", "success")

    def _availability(self, kind, rid, day, start, end, schedules):
        blocked = db.row(
            """SELECT 1 FROM unavailable
               WHERE kind=? AND resource_id=? AND day=?
                 AND start_min<? AND end_min>? LIMIT 1""",
            (kind, rid, day, end, start),
        )
        if blocked:
            return "Unavailable", "Marked unavailable for this time", False
        key = "faculty_id" if kind == "faculty" else "room_id"
        busy = [s for s in schedules if s[key] == rid and s["day"] == day
                and logic.overlap(start, end, s["start_min"], s["end_min"])]
        if busy:
            s = busy[0]
            return "Scheduled", f"Class: {s['code']} · {s['section']}", False
        return "Available", "No conflicting class or blocked time", True

    def _resource_card(self, kind, record, status, detail, is_free, loads):
        card = QFrame()
        card.setObjectName("availItem")
        v = QVBoxLayout(card)
        v.setContentsMargins(17, 16, 17, 16)
        v.setSpacing(10)
        top = QHBoxLayout()
        name = self._label(record["name"], "availName")
        name.setWordWrap(True)
        top.addWidget(name, 1)
        tag = self._label(status, "availStatus")
        color = ("#E5F7EE", "#147A50") if is_free else (
            ("#FFF1DF", "#9A5A09") if status in ("Scheduled", "Load full")
            else ("#FDEBED", "#A33E51")
        )
        tag.setStyleSheet(f"background: {color[0]}; color: {color[1]};")
        top.addWidget(tag)
        v.addLayout(top)
        if kind == "faculty":
            v.addWidget(self._label(
                f"{record['department'] or 'Department not set'} · "
                f"{loads.get(record['id'], 0)}/{record['max_units']} assigned units",
                "availInfo",
            ))
        else:
            v.addWidget(self._label(
                f"{record['room_type']} · {record['capacity']} seats · "
                f"{record['floor'] or 'Floor not set'}",
                "availInfo",
            ))
        v.addWidget(self._label(detail, "availInfo"))
        return card

    def refresh(self, *_):
        types = [r[0] for r in db.rows(
            "SELECT DISTINCT room_type FROM classrooms ORDER BY room_type"
        )]
        chosen = self.room_type.currentData()
        self.room_type.blockSignals(True)
        self.room_type.clear()
        self.room_type.addItem("All room types", None)
        for room_type in types:
            self.room_type.addItem(room_type, room_type)
        self.room_type.setCurrentIndex(max(0, self.room_type.findData(chosen)))
        self.room_type.blockSignals(False)
        if self.editor.isVisible():
            self._reload_resources()
            self._reload_blocks()
        for grid in self.grids:
            clear_layout(grid)
        start, end = self.start.currentData(), self.end.currentData()
        if end <= start:
            self.summary.setText("Please choose an end time later than the start time.")
            for counter in self.counts:
                counter.setText("—")
            return
        day = self.day.currentData()
        schedules = logic.schedule_rows(self.win.term_id())
        loads = logic.faculty_loads(self.win.term_id())
        needle = self.search.text().strip().casefold()
        counts = []
        for index, (kind, table) in enumerate((("faculty", "faculty"), ("room", "classrooms"))):
            records = db.rows(f"SELECT * FROM {table} ORDER BY name")
            if kind == "room" and self.room_type.currentData():
                records = [r for r in records if r["room_type"] == self.room_type.currentData()]
            if needle:
                records = [r for r in records if needle in r["name"].casefold()]
            free = 0
            for n, record in enumerate(records):
                status, detail, available = self._availability(
                    kind, record["id"], day, start, end, schedules,
                )
                if kind == "faculty" and available and loads.get(record["id"], 0) >= record["max_units"]:
                    status = "Load full"
                    detail = "This time is open, but teaching load is already full"
                    available = False
                free += int(available)
                self.grids[index].addWidget(
                    self._resource_card(kind, record, status, detail, available, loads),
                    n // 2, n % 2,
                )
            self.counts[index].setText(f"{free} / {len(records)} free")
            self.tab_contents[index].setText(
                "Faculty availability" if kind == "faculty" else "Classroom availability"
            )
            self.empty_labels[index].setText(
                "No matching faculty records." if kind == "faculty" else "No matching classrooms."
            )
            self.empty_labels[index].setVisible(not records)
            counts.append(free)
        self.summary.setText(
            f"Selected time: {dict(db.DAYS).get(day, day)}, "
            f"{logic.fmt(start)}–{logic.fmt(end)}  ·  "
            f"{counts[0]} faculty and {counts[1]} classrooms available"
        )
