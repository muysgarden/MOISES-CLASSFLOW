"""Module 3: readable class assignment editor and schedule views."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QCompleter, QFrame, QGridLayout, QHBoxLayout,
    QLineEdit, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

import db
import logic
from ui.availability import parse_time, time_combo
from ui.widgets import (
    Page, Card, Combo, CalendarWidget, Banner, button, fit_table, labeled,
    make_table, text_item, widget_cell, set_kind,
)


LOOKUPS = (
    ("subject_id", "Subject", "SELECT id, code || ' — ' || title FROM subjects ORDER BY code"),
    ("section_id", "Section", "SELECT id, name FROM sections ORDER BY name"),
    ("faculty_id", "Faculty", "SELECT id, name FROM faculty ORDER BY name"),
    ("room_id", "Classroom", "SELECT id, name || ' · ' || capacity || ' seats' FROM classrooms ORDER BY name"),
)


def searchable():
    combo = Combo()
    combo.setEditable(True)
    combo.setInsertPolicy(Combo.NoInsert)
    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)
    return combo


class SchedulesPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.replace_ids = []
        self.setObjectName("schedulesPage")
        self.setStyleSheet("""
            #schedulesPage QFrame#scheduleEditor {
                background: white; border: 1px solid #E4EAF3; border-radius: 13px; }
            #schedulesPage QLineEdit, #schedulesPage QComboBox {
                background: white; border: 1px solid #DDE6F4;
                border-radius: 8px; padding: 8px 10px; min-height: 28px; }
            #schedulesPage QTabWidget::pane { border: none; }
            #schedulesPage QTabBar::tab {
                background: white; color: #52627A; border-radius: 9px;
                padding: 12px 23px; margin-right: 7px;
                min-width: 155px; font-weight: 650; }
            #schedulesPage QTabBar::tab:selected {
                background: #EBE9FC; color: #4032A3; }
            #schedulesPage QPushButton#scheduleCancel {
                background: white; border: 1px solid #D1DCEE; border-radius: 8px;
                padding: 10px 15px; color: #546785; }
            #schedulesPage QFrame#scheduleEditor QLabel#formTitle {
                color: #19263B; font-size: 17px; font-weight: 750; }
        """)
        self.add_header(
            "MODULE 03", "Class Schedules",
            "Create assignments, check conflicts, and review the weekly timetable.",
            [button("+  New Schedule", "primary", self.new_schedule)],
        )
        self._build_form()
        self._build_views()
        self.finish()

    def _build_form(self):
        self.editor = QFrame()
        self.editor.setObjectName("scheduleEditor")
        layout = QVBoxLayout(self.editor)
        layout.setContentsMargins(20, 17, 20, 19)
        layout.setSpacing(13)
        self.form_title = QPushButton("New class assignment")
        self.form_title.setObjectName("formTitle")
        self.form_title.setEnabled(False)
        self.form_title.setStyleSheet(
            "border: none; background: transparent; color: #19263B;"
            "font-size: 16px; font-weight: 750; text-align: left; padding: 0;"
        )
        layout.addWidget(self.form_title)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.fields = {}
        for index, (key, title, _sql) in enumerate(LOOKUPS):
            widget = searchable()
            widget.lineEdit().setPlaceholderText(f"Search {title.lower()}…")
            self.fields[key] = widget
            grid.addWidget(labeled(title, widget), 0, index)
        self.fields["days"] = searchable()
        self.fields["days"].lineEdit().setPlaceholderText("Choose class days…")
        for value, title in logic.PATTERNS:
            self.fields["days"].addItem(title, value)
        self.fields["start"] = time_combo()
        self.fields["end"] = time_combo()
        self.fields["start"].lineEdit().setPlaceholderText("e.g. 8:15 AM")
        self.fields["end"].lineEdit().setPlaceholderText("e.g. 10:45 AM")
        for col, (key, title) in enumerate(
            (("days", "Class days"), ("start", "From"), ("end", "Until"))
        ):
            grid.addWidget(labeled(title, self.fields[key]), 1, col)
        layout.addLayout(grid)
        self.status = Banner("good", "Choose the class details to check availability.")
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("scheduleCancel")
        self.cancel_button.clicked.connect(self.clear)
        actions.addWidget(self.cancel_button)
        self.save_button = button("Save Schedule", "primary", self.save)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.lay.addWidget(self.editor)
        for combo in self.fields.values():
            combo.currentIndexChanged.connect(self.preview)
            if combo.isEditable():
                combo.lineEdit().textEdited.connect(self.preview)
        self.editor.hide()

    def _build_views(self):
        self.views = QTabWidget()
        self.views.tabBar().setUsesScrollButtons(False)
        listing_page = QWidget()
        listing_layout = QVBoxLayout(listing_page)
        listing_layout.setContentsMargins(0, 10, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search schedules by subject, section, faculty, or room…")
        self.search.setMinimumWidth(280)
        self.search.textChanged.connect(self.render)
        listing = Card("Saved Schedules", "Assignments for the selected academic term", right=[self.search])
        listing_layout.addWidget(listing)
        self.table = make_table(
            ["Subject / Section", "Faculty", "Room", "Days & Time", "Actions"],
            row_h=54, fixed={4: 165}, flex={0: 3, 1: 3, 2: 2, 3: 3},
        )
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        listing.add(self.table)
        self.views.addTab(listing_page, "Saved Schedules")

        calendar_page = QWidget()
        calendar_layout = QVBoxLayout(calendar_page)
        calendar_layout.setContentsMargins(0, 10, 0, 0)
        self.section = Combo()
        self.section.addItem("Choose section…", None)
        self.section.currentIndexChanged.connect(self.render_calendar)
        calendar_card = Card(
            "Weekly Calendar", "Choose a section to see its timetable",
            right=[self.section],
        )
        self.calendar_card = calendar_card
        self.calendar = CalendarWidget()
        calendar_card.body().addWidget(self.calendar)
        calendar_layout.addWidget(calendar_card)
        self.views.addTab(calendar_page, "Weekly Calendar")
        self.lay.addWidget(self.views)

    @staticmethod
    def _clear_combo(combo):
        combo.setCurrentIndex(-1)
        if combo.isEditable():
            combo.lineEdit().clear()

    @staticmethod
    def _lookup_value(combo):
        # Typing does not authorize a record unless its text matches a real
        # option. Avoid stale currentData after manual edits.
        typed = combo.currentText().strip().casefold()
        for index in range(combo.count()):
            if typed and combo.itemText(index).casefold() == typed:
                return combo.itemData(index)
        return None

    def refresh(self):
        for key, title, sql in LOOKUPS:
            combo = self.fields[key]
            keep = self._lookup_value(combo)
            combo.blockSignals(True)
            combo.clear()
            for record in db.rows(sql):
                combo.addItem(record[1], record[0])
            if keep is not None and combo.findData(keep) >= 0:
                combo.setCurrentIndex(combo.findData(keep))
            else:
                self._clear_combo(combo)
            combo.blockSignals(False)
        keep = self.section.currentData()
        self.section.blockSignals(True)
        self.section.clear()
        self.section.addItem("Choose section…", None)
        for record in db.rows("SELECT id,name FROM sections ORDER BY name"):
            self.section.addItem(record["name"], record["id"])
        self.section.setCurrentIndex(max(0, self.section.findData(keep)))
        self.section.blockSignals(False)
        self.render()
        self.preview()

    def values(self):
        values = {key: self._lookup_value(self.fields[key]) for key, _, _ in LOOKUPS}
        values["days"] = self._lookup_value(self.fields["days"])
        for key in ("start", "end"):
            try:
                values[key] = parse_time(self.fields[key].currentText())
            except ValueError:
                values[key] = None
        return values

    def _missing(self, values):
        return [label for key, label in (
            ("subject_id", "subject"), ("section_id", "section"),
            ("faculty_id", "faculty"), ("room_id", "classroom"),
            ("days", "class days"), ("start", "start time"), ("end", "end time"),
        ) if values.get(key) is None]

    def preview(self, *_):
        if not hasattr(self, "status"):
            return
        values = self.values()
        missing = self._missing(values)
        if missing:
            self.status.title.setText("Complete the assignment details")
            self.status.text.setText("Select or enter: " + ", ".join(missing) + ".")
            self.status.text.show()
            set_kind(self.status, "warn")
            return
        issues = logic.check_candidate(
            self.win.term_id(), values["subject_id"], values["section_id"],
            values["faculty_id"], values["room_id"], values["days"].split(","),
            values["start"], values["end"], self.replace_ids,
        )
        self.status.title.setText("Time slot available" if not issues else issues[0]["type"])
        self.status.text.setText(
            "No faculty, classroom, or section conflicts found."
            if not issues else "\n".join(issue["desc"] for issue in issues)
        )
        self.status.text.show()
        set_kind(self.status, "bad" if any(
            issue["severity"] == logic.CRITICAL for issue in issues
        ) else "good" if not issues else "warn")

    def save(self):
        values = self.values()
        missing = self._missing(values)
        if missing:
            self.win.notify(
                "Complete these fields with valid selections: " + ", ".join(missing) + ".",
                "warning",
            )
            return
        issues = logic.check_candidate(
            self.win.term_id(), values["subject_id"], values["section_id"],
            values["faculty_id"], values["room_id"], values["days"].split(","),
            values["start"], values["end"], self.replace_ids,
        )
        critical = [issue for issue in issues if issue["severity"] == logic.CRITICAL]
        if critical:
            QMessageBox.warning(
                self, "Cannot save schedule",
                "\n".join(issue["desc"] for issue in critical),
            )
            return
        if issues and QMessageBox.question(
            self, "Schedule warnings",
            "\n".join(issue["desc"] for issue in issues) + "\n\nSave anyway?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        logic.save_schedule(
            self.win.term_id(), values["subject_id"], values["section_id"],
            values["faculty_id"], values["room_id"], values["days"].split(","),
            values["start"], values["end"], self.replace_ids,
        )
        self.clear()
        self.win.data_changed()
        self.refresh()
        self.win.notify("Class schedule saved.", "success")

    def new_schedule(self):
        self.clear()
        self.editor.show()
        self.fields["subject_id"].setFocus()
        self.verticalScrollBar().setValue(0)

    def clear(self):
        self.replace_ids = []
        for combo in self.fields.values():
            self._clear_combo(combo)
        self.form_title.setText("New class assignment")
        self.save_button.setText("Save Schedule")
        self.editor.hide()
        self.preview()

    def render(self, *_):
        self.groups = logic.group_rows(logic.schedule_rows(self.win.term_id()))
        query = self.search.text().strip().casefold()
        groups = [
            group for group in self.groups
            if query in " ".join(str(value) for value in group.values()).casefold()
        ]
        self.table.setRowCount(len(groups))
        for index, group in enumerate(groups):
            values = [
                group["code"] + " · " + group["section"],
                group["faculty"], group["room"],
                group["days_label"] + "\n" + group["time_label"],
            ]
            for col, value in enumerate(values):
                cell = text_item(value, bold=(col == 0))
                cell.setToolTip(value)
                self.table.setItem(index, col, cell)
            action_host = QWidget()
            actions = QHBoxLayout(action_host)
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(3)
            actions.addWidget(button("Edit", "linkbtn", lambda _=False, g=group: self.edit(g)))
            actions.addWidget(button("Delete", "danger", lambda _=False, g=group: self.delete(g)))
            widget_cell(self.table, index, 4, action_host)
        height = self.table.horizontalHeader().height() + min(len(groups), 8) * 54 + 3
        self.table.setFixedHeight(max(100, height))
        self.render_calendar()

    def render_calendar(self, *_):
        selected = self.section.currentData()
        self.calendar_card.subtitle.setText(
            "Choose a section to see its timetable" if selected is None
            else f"Weekly timetable for {self.section.currentText()}"
        )
        self.calendar.set_rows([
            record for record in logic.schedule_rows(self.win.term_id())
            if selected is not None and record["section_id"] == selected
        ])

    def edit(self, group):
        self.refresh()
        self.replace_ids = list(group["ids"])
        for key, _, _ in LOOKUPS:
            combo = self.fields[key]
            combo.setCurrentIndex(combo.findData(group[key]))
        days = self.fields["days"]
        index = days.findData(group["days_csv"])
        if index < 0:
            days.addItem(group["days_label"], group["days_csv"])
            index = days.count() - 1
        days.setCurrentIndex(index)
        self.fields["start"].setEditText(logic.fmt(group["start_min"]))
        self.fields["end"].setEditText(logic.fmt(group["end_min"]))
        self.form_title.setText(f"Editing {group['code']} · {group['section']}")
        self.save_button.setText("Save Changes")
        self.editor.show()
        self.preview()
        self.verticalScrollBar().setValue(0)

    def delete(self, group):
        if QMessageBox.question(
            self, "Delete schedule",
            f"Delete {group['code']} for {group['section']}? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        logic.delete_schedules(self.win.term_id(), group["ids"])
        self.clear()
        self.win.data_changed()
        self.render()
        self.win.notify("Schedule deleted.", "success")

    def open(self, edit_ids=None, **_kwargs):
        self.refresh()
        if edit_ids:
            for group in self.groups:
                if set(group["ids"]) & set(edit_ids):
                    self.edit(group)
                    break

    def search_all(self, query):
        self.views.setCurrentIndex(0)
        self.search.setText(query)
