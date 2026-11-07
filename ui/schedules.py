"""Module 3: readable class assignment editor and schedule views."""

import math
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QCompleter, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
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

SCHEDULES_PER_PAGE = 8


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
        self.page_no = 0
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
        self.add_header('MODULE 03', 'Schedule Management',
                        'Assign classes to faculty, rooms, and time slots, then preview the weekly schedule.',
                        [button('+  New Schedule', 'primary', self.clear)])
        card=Card('Assign Class Schedule', 'All fields are required. Availability is checked automatically.')
        self.lay.addWidget(card)
        body=card.body(); row=QHBoxLayout(); body.addLayout(row)
        self.fields={}
        for key, title in [('subject_id','Subject'),('section_id','Section'),('faculty_id','Faculty'),('room_id','Classroom'),('days','Day'),('start','From'),('end','To')]:
            combo=Combo(); self.fields[key]=combo; row.addWidget(labeled(title,combo),1)
            combo.currentIndexChanged.connect(self.preview)
        for value,text in logic.PATTERNS:
            self.fields['days'].addItem(text,value)
        for value,text in logic.TIME_CHOICES:
            self.fields['start'].addItem(text,value); self.fields['end'].addItem(text,value)
        self.fields['start'].setCurrentIndex(2); self.fields['end'].setCurrentIndex(5)
        row.addWidget(button('Save Schedule','primary',self.save))
        self.status=Banner('good','Select a class assignment to check availability.'); body.addWidget(self.status)
        columns=QHBoxLayout(); self.lay.addLayout(columns)
        self.section=Combo(); self.section.currentIndexChanged.connect(self.render)
        self.section.addItem('All sections',None)
        self.search=QLineEdit(); self.search.setPlaceholderText('Search schedules…'); self.search.textChanged.connect(self.render)
        listing=Card('Existing Schedules','Assignments for the selected term',right=[self.section,self.search]); columns.addWidget(listing,6)
        self.table=make_table(['Subject / Section','Faculty','Room','Schedule','Actions'],flex={0:3,1:3,2:2,3:3,4:3}); listing.add(self.table)
        self.calendar_room=Combo(); self.calendar_room.currentIndexChanged.connect(self.render_calendar)
        self.calendar_room.setMinimumWidth(150)
        cal=Card('Room Utilization Schedule','Select one room to view its Monday–Saturday assignments and availability',right=[self.calendar_room]); columns.addWidget(cal,5)
        self.calendar=CalendarWidget(); cal.body().addWidget(self.calendar)
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
        self.course_hint = QLabel("Course: Choose a section to identify its program")
        self.course_hint.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(self.course_hint)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.fields = {}
        for index, (key, title, _sql) in enumerate(LOOKUPS):
            widget = searchable()
            widget.lineEdit().setPlaceholderText(f"Search {title.lower()}…")
            self.fields[key] = widget
            grid.addWidget(labeled(title, widget), 0, index)
        self.fields["start"] = time_combo()
        self.fields["end"] = time_combo()
        self.fields["start"].lineEdit().setPlaceholderText("e.g. 8:15 AM")
        self.fields["end"].lineEdit().setPlaceholderText("e.g. 10:45 AM")
        days_panel = QWidget()
        day_box = QVBoxLayout(days_panel)
        day_box.setContentsMargins(0, 0, 0, 0)
        day_box.setSpacing(5)
        label_days = QLabel("CLASS DAYS")
        label_days.setObjectName("fieldLabel")
        day_box.addWidget(label_days)
        day_row = QHBoxLayout()
        day_row.setSpacing(5)
        self.day_checks = {}
        for code, _name in db.DAYS:
            check = QCheckBox(code)
            check.toggled.connect(self.preview)
            self.day_checks[code] = check
            day_row.addWidget(check)
        day_box.addLayout(day_row)
        grid.addWidget(days_panel, 1, 0, 1, 2)
        grid.addWidget(labeled("From", self.fields["start"]), 1, 2)
        grid.addWidget(labeled("Until", self.fields["end"]), 1, 3)
        layout.addLayout(grid)
        hint = QLabel(
            "Select multiple days only when their class times are the same. "
            "For different times, save separate assignments for each day."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
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
        self.search.setPlaceholderText("Search schedules…")
        self.search.setFixedWidth(230)
        self.search.textChanged.connect(self._filters_changed)
        self.list_section = Combo()
        self.list_section.setMinimumWidth(170)
        self.list_section.addItem("All sections", None)
        self.list_section.currentIndexChanged.connect(self._filters_changed)
        listing = Card(
            "Saved Schedules", "Filter by section or search records",
            right=[self.list_section, self.search],
        )
        listing.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        listing_layout.addWidget(listing)
        listing_layout.addStretch()
        self.table = make_table(
            ["Course", "Section", "Subject", "Faculty", "Room", "Days & Time", "Actions"],
            row_h=54, fixed={0: 78, 6: 158},
            flex={1: 2, 2: 2, 3: 2, 4: 2, 5: 3},
        )
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        listing.add(self.table)
        footer = QWidget()
        pagination = QHBoxLayout(footer)
        pagination.setContentsMargins(15, 7, 15, 10)
        self.page_info = QLabel("")
        pagination.addWidget(self.page_info)
        pagination.addStretch()
        self.prev_page = button("Previous", "pg", lambda: self._goto_page(self.page_no - 1))
        self.next_page = button("Next", "pg", lambda: self._goto_page(self.page_no + 1))
        self.current_page = QLabel("")
        pagination.addWidget(self.prev_page)
        pagination.addWidget(self.current_page)
        pagination.addWidget(self.next_page)
        listing.add(footer)
        self.views.addTab(listing_page, "Saved Schedules")

        calendar_page = QWidget()
        calendar_layout = QVBoxLayout(calendar_page)
        calendar_layout.setContentsMargins(0, 10, 0, 0)
        self.section = searchable()
        self.section.setMinimumWidth(185)
        self.section.lineEdit().setPlaceholderText("Search section…")
        self.section.currentIndexChanged.connect(self.render_calendar)
        self.section.lineEdit().textEdited.connect(self.render_calendar)
        calendar_card = Card(
            "Weekly Calendar", "Choose a section to see its timetable",
            right=[self.section],
        )
        self.calendar_card = calendar_card
        self.calendar = CalendarWidget(step_minutes=30)
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
        keep = self._lookup_value(self.section)
        self.section.blockSignals(True)
        self.section.clear()
        for record in db.rows("SELECT id,name FROM sections ORDER BY name"):
            self.section.addItem(record["name"], record["id"])
        if keep is not None and self.section.findData(keep) >= 0:
            self.section.setCurrentIndex(self.section.findData(keep))
        else:
            self._clear_combo(self.section)
        self.section.blockSignals(False)
        keep_list = self.list_section.currentData()
        self.list_section.blockSignals(True)
        self.list_section.clear()
        self.list_section.addItem("All sections", None)
        for record in db.rows("SELECT id,name FROM sections ORDER BY name"):
            self.list_section.addItem(record["name"], record["id"])
        self.list_section.setCurrentIndex(max(0, self.list_section.findData(keep_list)))
        self.list_section.blockSignals(False)
        self.render()
        self.preview()
        for key,sql in [('subject_id','SELECT id,code || " — " || title FROM subjects ORDER BY code'),('section_id','SELECT id,name FROM sections ORDER BY name'),('faculty_id','SELECT id,name FROM faculty ORDER BY name'),('room_id','SELECT id,name || " · " || capacity || " seats" FROM classrooms ORDER BY name')]:
            combo=self.fields[key]; keep=combo.currentData(); combo.blockSignals(True); combo.clear()
            for r in db.rows(sql): combo.addItem(r[1],r[0])
            idx=combo.findData(keep); combo.setCurrentIndex(max(0,idx)); combo.blockSignals(False)
        keep_room=self.calendar_room.currentData(); self.calendar_room.blockSignals(True); self.calendar_room.clear()
        for r in db.rows('SELECT id,name FROM classrooms ORDER BY name'): self.calendar_room.addItem(r['name'],r['id'])
        room_index=self.calendar_room.findData(keep_room)
        self.calendar_room.setCurrentIndex(max(0,room_index)); self.calendar_room.blockSignals(False)
        keep=self.section.currentData(); self.section.blockSignals(True); self.section.clear(); self.section.addItem('All sections',None)
        for r in db.rows('SELECT id,name FROM sections ORDER BY name'): self.section.addItem(r['name'],r['id'])
        self.section.setCurrentIndex(max(0,self.section.findData(keep)) if keep is not None else max(0,self.section.findText('BSCS 2A'))); self.section.blockSignals(False)
        self.render(); self.preview()

    def values(self):
        values = {key: self._lookup_value(self.fields[key]) for key, _, _ in LOOKUPS}
        values["days"] = ",".join(
            code for code, _name in db.DAYS if self.day_checks[code].isChecked()
        ) or None
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
        course = db.row(
            """SELECT p.code FROM sections s
               JOIN programs p ON p.id=s.program_id WHERE s.id=?""",
            (values["section_id"],),
        ) if values["section_id"] is not None else None
        self.course_hint.setText(
            f"Course: {course['code']} (based on selected section)"
            if course else "Course: Choose a section to identify its program"
        )
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
        d=self.values()
        if any(v is None for v in d.values()):
            self.win.notify('Create subjects, sections, faculty, and classrooms first.','error'); return
        issues=logic.check_candidate(self.win.term_id(),d['subject_id'],d['section_id'],d['faculty_id'],d['room_id'],d['days'].split(','),d['start'],d['end'],self.replace_ids)
        if any(i['severity']==logic.CRITICAL for i in issues):
            QMessageBox.warning(self,'Cannot save schedule','\n'.join(i['desc'] for i in issues)); return
        if issues and QMessageBox.question(self,'Schedule warnings','\n'.join(i['desc'] for i in issues)+'\n\nSave anyway?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        logic.save_schedule(self.win.term_id(),d['subject_id'],d['section_id'],d['faculty_id'],d['room_id'],d['days'].split(','),d['start'],d['end'],self.replace_ids)
        self.replace_ids=[]; self.win.data_changed(); self.render(); self.preview(); self.save_device_copy()

    def save_device_copy(self):
        try:
            path = self.win.pages['reports'].save_schedule_sheet()
        except (OSError, RuntimeError) as error:
            self.win.notify(f'Schedule data was saved, but the device PDF could not be updated: {error}', 'error')
        else:
            self.win.notify(f'Schedule saved. Device PDF updated in {path.parent}.')

    def clear(self):
        self.replace_ids = []
        for combo in self.fields.values():
            self._clear_combo(combo)
        for check in self.day_checks.values():
            check.setChecked(False)
        self.form_title.setText("New class assignment")
        self.save_button.setText("Save Schedule")
        self.editor.hide()
        self.preview()

    def _filters_changed(self, *_):
        self.page_no = 0
        self.render()

    def _goto_page(self, page):
        self.page_no = page
        self.render()

    def render(self, *_):
        self.groups = logic.group_rows(logic.schedule_rows(self.win.term_id()))
        query = self.search.text().strip().casefold()
        groups = [
            group for group in self.groups
            if query in " ".join(str(value) for value in group.values()).casefold()
            and (self.list_section.currentData() is None
                 or group["section_id"] == self.list_section.currentData())
        ]
        pages = max(1, math.ceil(len(groups) / SCHEDULES_PER_PAGE))
        self.page_no = min(max(0, self.page_no), pages - 1)
        start = self.page_no * SCHEDULES_PER_PAGE
        groups = groups[start:start + SCHEDULES_PER_PAGE]
        sections = {
            record["id"]: record["code"] for record in db.rows(
                "SELECT s.id,p.code FROM sections s JOIN programs p ON p.id=s.program_id"
            )
        }
        self.table.setRowCount(len(groups))
        for index, group in enumerate(groups):
            values = [
                sections.get(group["section_id"], "—"),
                group["section"], group["code"] + " · " + group["title"],
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
            widget_cell(self.table, index, 6, action_host)
        height = self.table.horizontalHeader().height() + len(groups) * 54 + 3
        self.table.setFixedHeight(max(100, height))
        count = sum(
            query in " ".join(str(value) for value in group.values()).casefold()
            and (self.list_section.currentData() is None
                 or group["section_id"] == self.list_section.currentData())
            for group in self.groups
        )
        self.page_info.setText(
            f"Showing {start + 1}–{start + len(groups)} of {count} schedules"
            if count else "No matching schedules"
        )
        self.current_page.setText(f"Page {self.page_no + 1} of {pages}")
        self.prev_page.setEnabled(self.page_no > 0)
        self.next_page.setEnabled(self.page_no < pages - 1)
        self.render_calendar()

    def render_calendar(self, *_):
        selected = self._lookup_value(self.section)
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
        for code, check in self.day_checks.items():
            check.setChecked(code in group["days"])
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
        for i,g in enumerate(groups):
            for j,text in enumerate([g['code']+' · '+g['section'],g['faculty'],g['room'],g['days_label']+'\n'+g['time_label']]): self.table.setItem(i,j,text_item(text,bold=j==0))
            actions=QWidget(); row=QHBoxLayout(actions); row.setContentsMargins(0,0,0,0)
            row.addWidget(button('Edit','linkbtn',lambda _,g=g:self.edit(g)))
            row.addWidget(button('Delete','danger',lambda _,g=g:self.delete(g)))
            widget_cell(self.table,i,4,actions)
        fit_table(self.table); self.render_calendar()

    def render_calendar(self):
        if not hasattr(self,'calendar'): return
        room_id=self.calendar_room.currentData()
        rows=[r for r in logic.schedule_rows(self.win.term_id()) if room_id is not None and r['room_id']==room_id]
        self.calendar.set_rows(
            rows, 'section', include_faculty=True, show_availability=True, room_id=room_id
        )

    def edit(self,g):
        self.replace_ids=g['ids']
        self.section.setCurrentIndex(self.section.findData(g['section_id']))
        for k in ['subject_id','section_id','faculty_id','room_id']:
            self.fields[k].setCurrentIndex(self.fields[k].findData(g[k]))
        for k,v in [('days',g['days_csv']),('start',g['start_min']),('end',g['end_min'])]:
            combo=self.fields[k]; idx=combo.findData(v)
            if idx<0: combo.addItem(str(v),v); idx=combo.count()-1
            combo.setCurrentIndex(idx)
        self.preview(); self.verticalScrollBar().setValue(0)

    def delete(self,g):
        if QMessageBox.question(self,'Delete schedule','Delete '+g['code']+' for '+g['section']+'?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            logic.delete_schedules(self.win.term_id(),g['ids']); self.replace_ids=[]; self.render(); self.preview(); self.win.data_changed(); self.save_device_copy()

    def open(self,edit_ids=None,**kw):
        self.refresh()
        if edit_ids:
            for group in self.groups:
                if set(group["ids"]) & set(edit_ids):
                    self.edit(group)
                    break

    def search_all(self, query):
        self.views.setCurrentIndex(0)
        self.search.setText(query)
