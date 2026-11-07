import html
import csv
import re
from pathlib import Path
from PyQt5.QtCore import QStandardPaths, QRectF
from PyQt5.QtGui import QPainter, QTextDocument, QTextLength, QTextTable
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QFileDialog
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from ui.widgets import Page, Card, Combo, CalendarWidget, BarChart, Banner, button, labeled, label, make_table, text_item, fit_table
import db
import logic

REPORTS=['Class Schedules','Faculty Schedules','Section Schedules','Classroom Schedules','Room Utilization Schedule','Room Utilization','Faculty Teaching Load','Conflict Reports','Available Rooms']
TIMETABLE_REPORTS=('Class Schedules','Faculty Schedules','Section Schedules','Classroom Schedules')
EXPORTABLE_SCHEDULES=TIMETABLE_REPORTS+('Room Utilization Schedule',)
YEAR_LEVEL_COLORS = {
    1: 'FCE4D6',
    2: 'FFF2CC',
    3: 'E2F0D9',
    4: 'DDEBF7',
    5: 'E4DFEC',
    6: 'FCE4EC',
}
MULTI_YEAR_COLOR = 'D9D2E9'


def section_year_level(section_name):
    match = re.search(r'\b(\d+)\s*[A-Za-z]?$', section_name)
    return int(match.group(1)) if match else None


def year_level_label(number):
    suffix = 'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
    return f'{number}{suffix} year'


class ReportsPage(Page):
    def __init__(self,win):
        super().__init__(win)
        self.excel_button=button('Export Excel',slot=self.export_excel)
        self.add_header('MODULE 05','Reports & Timetables',
                        'Review saved schedules and export official reports.',[
            button('Print',slot=self.print_report),
            button('Export PDF',slot=self.export_pdf),
            button('Export CSV',slot=self.export_csv),
            self.excel_button,
        ])
        filter_card=Card()
        self.lay.addWidget(filter_card)
        row=QHBoxLayout()
        row.setSpacing(14)
        filter_card.body(margins=(18,12,18,12)).addLayout(row)
        self.report=Combo()
        self.report.addItems(REPORTS)
        self.report.setCurrentText('Section Schedules')
        row.addWidget(labeled('Report Type',self.report),1)
        self.program=Combo()
        self.section=Combo()
        self.faculty=Combo()
        self.room=Combo()
        self.filter_card=QWidget()
        filters=QHBoxLayout(self.filter_card)
        filters.setContentsMargins(0,0,0,0)
        filters.setSpacing(14)
        self.filter_widgets={}
        for key,title,combo in [
            ('program','Program',self.program),
            ('section','Section',self.section),
            ('faculty','Faculty',self.faculty),
            ('room','Classroom',self.room),
        ]:
            host=labeled(title,combo)
            filters.addWidget(host,1)
            self.filter_widgets[key]=host
        row.addWidget(self.filter_card,2)
        self.report.currentIndexChanged.connect(self._report_changed)
        self.program.currentIndexChanged.connect(self.populate_sections)
        for combo in (self.section,self.faculty,self.room):
            combo.currentIndexChanged.connect(self.render)

        self.main_card=Card('Report Preview','Selected academic term')
        self.lay.addWidget(self.main_card)
        body=self.main_card.body()
        self.calendar=CalendarWidget(step_minutes=30)
        body.addWidget(self.calendar)
        self.table=make_table(['Subject','Section','Faculty','Room','Day','Time'])
        body.addWidget(self.table)
        self.resolve_button=button('Resolve conflicts',slot=lambda: self.win.go('validation'))
        self.resolve_button.hide()
        self.banner=Banner(right=self.resolve_button)
        body.addWidget(self.banner)
        self.chart_card=Card('Room Utilization','Weekly occupancy rate')
        self.chart=BarChart()
        self.chart_card.body().addWidget(self.chart)
        self.lay.addWidget(self.chart_card)
        self.summary_card=Card('Schedule Summary')
        self.summary=label('',wrap=True)
        self.summary_card.body().addWidget(self.summary)
        self.lay.addWidget(self.summary_card)
        self.finish()

    def _report_changed(self, *_):
        # Report changes show the full scope by default, with optional filtering.
        room_mode=self.report.currentText()=='Room Utilization Schedule'
        chosen_room=self.room.currentData()
        for combo in (self.program,self.section,self.faculty,self.room):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        if room_mode:
            self._set_filter_options(
                self.room,db.rows('SELECT id,name FROM classrooms ORDER BY name'),
                'All rooms',False,preferred_id=chosen_room
            )
        else:
            self._set_filter_options(
                self.room,db.rows('SELECT id,name FROM classrooms ORDER BY name'),
                'All rooms',True
            )
        self.populate_sections()

    def _show_relevant_filters(self,mode):
        active={
            'Class Schedules': {'program','section','faculty','room'},
            'Faculty Schedules': {'faculty'},
            'Section Schedules': {'program','section'},
            'Classroom Schedules': {'room'},
            'Room Utilization Schedule': {'room'},
            'Room Utilization': set(),
            'Faculty Teaching Load': {'faculty'},
            'Conflict Reports': set(),
            'Available Rooms': {'room'},
        }.get(mode,set())
        self.filter_card.setVisible(bool(active))
        for key,host in self.filter_widgets.items():
            host.setVisible(key in active)
        return active

    def refresh(self):
        self._set_filter_options(self.program,
            db.rows('SELECT id,name FROM programs ORDER BY code'),'All programs',True)
        self._set_filter_options(self.faculty,
            db.rows('SELECT id,name FROM faculty ORDER BY name'),'All faculty',True)
        self._set_filter_options(self.room,
            db.rows('SELECT id,name FROM classrooms ORDER BY name'),'All rooms',
            self.report.currentText()!='Room Utilization Schedule')
        self.populate_sections()

    def _set_filter_options(self, combo, records, all_label, include_all, preferred_id=None):
        selection=combo.currentData() if preferred_id is None else preferred_id
        combo.blockSignals(True)
        combo.clear()
        if include_all:
            combo.addItem(all_label,None)
        for record in records:
            combo.addItem(record['name'],record['id'])
        index=combo.findData(selection)
        if index<0:
            index=0 if combo.count() else -1
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def report_changed(self):
        self._report_changed()

    def populate_sections(self, *_):
        chosen=self.section.currentData()
        pid=self.program.currentData()
        query=('SELECT id,name FROM sections WHERE program_id=? ORDER BY name'
               if pid is not None else 'SELECT id,name FROM sections ORDER BY name')
        records=db.rows(query,(pid,) if pid is not None else ())
        self._set_filter_options(self.section,records,'All sections',True,
                                 preferred_id=chosen)
        self.render()

    def render(self):
        if not hasattr(self,'calendar'):
            return
        rows=logic.schedule_rows(self.win.term_id())
        mode=self.report.currentText()
        active=self._show_relevant_filters(mode)
        pid=self.program.currentData() if 'program' in active else None
        section_ids=({r['id'] for r in db.rows(
            'SELECT id FROM sections WHERE program_id=?',(pid,))}
            if pid is not None else None)
        sid=self.section.currentData() if 'section' in active else None
        fid=self.faculty.currentData() if 'faculty' in active else None
        rid=self.room.currentData() if 'room' in active else None
        self.report_rows=[
            r for r in rows
            if (section_ids is None or r['section_id'] in section_ids)
            and (sid is None or r['section_id']==sid)
            and (fid is None or r['faculty_id']==fid)
            and (rid is None or r['room_id']==rid)
        ]
        room_mode=mode=='Room Utilization Schedule'
        if room_mode:
            # This report always includes every section and faculty using
            # the selected room, regardless of hidden filter values.
            self.report_rows=[
                r for r in rows if rid is not None and r['room_id']==rid
            ]
        grid_mode=(
            (mode=='Section Schedules' and sid is not None)
            or (mode=='Classroom Schedules' and rid is not None)
            or (mode=='Faculty Schedules' and fid is not None)
            or (room_mode and rid is not None)
        )
        self.calendar.set_rows(
            self.report_rows,
            'section' if mode in ('Faculty Schedules','Classroom Schedules','Room Utilization Schedule') else 'room',
            include_faculty=room_mode,
            show_availability=room_mode and rid is not None,
            room_id=rid if room_mode else None
        )
        for combo in (self.program,self.section,self.faculty):
            combo.setEnabled(not room_mode)
        selected=(
            self.faculty.currentText() if mode=='Faculty Schedules' and fid is not None
            else self.section.currentText() if mode=='Section Schedules' and sid is not None
            else self.room.currentText() if mode in ('Classroom Schedules','Room Utilization Schedule') and rid is not None
            else 'All records'
        )
        self.main_card.title_label.setText(mode)
        self.main_card.subtitle.setText(self.win.term_name()+' · '+selected)
        self.excel_button.setEnabled(mode in EXPORTABLE_SCHEDULES)
        self.headers=['Subject','Section','Faculty','Room','Day','Time']
        self.output=[
            [r['code'],r['section'],r['faculty'],r['room'],r['day'],
             f'{logic.fmt(r["start_min"])} – {logic.fmt(r["end_min"])}']
            for r in self.report_rows
        ]
        if room_mode:
            self.headers=['Room','Day','From','To','Status','Course','Section','Instructor']
            self.output=[]
            room_record=(db.row('SELECT name FROM classrooms WHERE id=?',(rid,))
                         if rid is not None else None)
            blocked={}
            if rid is not None and db.row(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"
            ):
                blocked={
                    day:db.rows(
                        "SELECT start_min,end_min FROM unavailable "
                        "WHERE kind='room' AND resource_id=? AND day=?",(rid,day)
                    ) for day,_ in db.DAYS
                }
            if rid is not None:
                for day,_ in db.DAYS:
                    for start in range(logic.CAL_START,logic.CAL_END,30):
                        finish=start+30
                        occupants=[
                            r for r in self.report_rows
                            if r['day']==day and logic.overlap(
                                start,finish,r['start_min'],r['end_min'])
                        ]
                        unavailable=any(
                            logic.overlap(start,finish,w['start_min'],w['end_min'])
                            for w in blocked.get(day,[])
                        )
                        status=('Occupied' if occupants else
                                'Unavailable' if unavailable else 'Available')
                        self.output.append([
                            room_record['name'] if room_record else '',day,
                            logic.fmt(start),logic.fmt(finish),status,
                            '; '.join(r['code'] for r in occupants),
                            '; '.join(r['section'] for r in occupants),
                            '; '.join(r['faculty'] for r in occupants)
                        ])
        available_rooms=(
            [r for r in db.rows('SELECT id FROM classrooms') if r['id']==rid]
            if room_mode and rid is not None
            else db.rows('SELECT id FROM classrooms') if not room_mode
            else []
        )
        hours=(logic.CAL_END-logic.CAL_START)/60
        utilization=[]
        for day,_ in db.DAYS:
            total=0
            for room in available_rooms:
                intervals=sorted(
                    (max(logic.CAL_START,r['start_min']),min(logic.CAL_END,r['end_min']))
                    for r in rows if r['day']==day and r['room_id']==room['id']
                )
                last=logic.CAL_START
                for start,finish in intervals:
                    total+=max(0,finish-max(start,last))
                    last=max(last,finish)
            percentage=(round(100*total/(len(available_rooms)*hours*60),1)
                        if available_rooms else 0)
            utilization.append((day,percentage))
        self.chart.set_data(utilization)
        self.chart_card.title_label.setText(
            'Selected Room Utilization' if room_mode else 'Room Utilization'
        )
        if mode=='Room Utilization':
            self.headers=['Day','Occupancy']
            self.output=[[day,str(pct)+'%'] for day,pct in utilization]
        elif mode=='Faculty Teaching Load':
            loads=logic.faculty_loads(self.win.term_id())
            self.headers=['Faculty','Assigned Units','Maximum Units']
            self.output=[
                [r['name'],loads.get(r['id'],0),r['max_units']]
                for r in db.rows('SELECT * FROM faculty')
                if fid is None or r['id']==fid
            ]
        elif mode=='Conflict Reports':
            self.headers=['Issue','Schedule','Description','Severity']
            self.output=[
                [issue['type'],issue['label'],issue['desc'],issue['severity']]
                for issue in logic.validate_term(self.win.term_id())['issues']
            ]
        elif mode=='Available Rooms':
            from ui.availability import unavailable
            self.headers=['Room','Capacity','Day','From','To']
            self.output=[]
            for room in db.rows('SELECT * FROM classrooms'):
                if rid is not None and room['id']!=rid:
                    continue
                for day,_ in db.DAYS:
                    for start,finish,_label in logic.BLOCKS:
                        if (not unavailable('room',room['id'],day,start,finish)
                            and not any(
                                r['room_id']==room['id'] and r['day']==day
                                and logic.overlap(start,finish,r['start_min'],r['end_min'])
                                for r in rows
                            )):
                            self.output.append([
                                room['name'],room['capacity'],day,
                                logic.fmt(start),logic.fmt(finish)
                            ])
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels([h.upper() for h in self.headers])
        self.table._flex_weights={i:1 for i in range(len(self.headers))}
        self.table.setRowCount(len(self.output))
        for index,record in enumerate(self.output):
            for col,value in enumerate(record):
                self.table.setItem(index,col,text_item(value))
        fit_table(self.table)
        self.calendar.setVisible(grid_mode)
        self.table.setVisible(not grid_mode)
        self.chart_card.setVisible(mode=='Room Utilization')
        self.summary_card.setVisible(mode in EXPORTABLE_SCHEDULES)
        validation=logic.validate_term(self.win.term_id())
        self.banner.title.setText(
            'Resolve critical conflicts before using final timetables.'
            if validation['critical'] else
            'Timetable validated. No critical conflicts detected.'
        )
        self.banner.text.setText(
            f'{len(validation["issues"])} issues in this term. Export reflects current saved data.'
        )
        self.banner.text.show()
        self.resolve_button.setVisible(validation['critical']>0)
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if validation['critical'] else 'good')
        self.summary.setText(
            f'Total subjects: {len({r["subject_id"] for r in self.report_rows})}\n\n'
            f'Weekly class hours: {sum((r["end_min"]-r["start_min"])/60 for r in self.report_rows):g}\n\n'
            f'Rooms assigned: {len({r["room_id"] for r in self.report_rows})}\n\n'
            f'Average room utilization: {sum(v for _,v in utilization)/6:.1f}%'
        )

    def schedule_sheet_html(self, all_schedules=False):
        esc = lambda value: html.escape(str(value))
        slot_minutes = 30
        slot_count = (logic.CAL_END - logic.CAL_START) // slot_minutes
        by_day = {day: [] for day in logic.DAY_CODES}
        report_rows = logic.schedule_rows(self.win.term_id()) if all_schedules else self.report_rows
        for row in report_rows:
            if row["day"] not in by_day:
                continue
            start = max(logic.CAL_START, row["start_min"])
            end = min(logic.CAL_END, row["end_min"])
            if end <= start:
                continue
            start_slot = max(0, (start - logic.CAL_START) // slot_minutes)
            end_slot = min(slot_count, (end - logic.CAL_START + slot_minutes - 1) // slot_minutes)
            if end_slot > start_slot:
                by_day[row["day"]].append((start_slot, end_slot, row))

        day_cells = {}
        for day, entries in by_day.items():
            entries.sort(key=lambda item: (item[0], item[1], item[2]["code"]))
            components = []
            for start_slot, end_slot, row in entries:
                if components and start_slot < components[-1]["end"]:
                    components[-1]["end"] = max(components[-1]["end"], end_slot)
                    components[-1]["rows"].append(row)
                else:
                    components.append({"start": start_slot, "end": end_slot, "rows": [row]})
            day_cells[day] = {component["start"]: component for component in components}

        section_ids = {row["section_id"] for row in report_rows}
        section_id = None if all_schedules else self.section.currentData()
        if section_id is None and len(section_ids) == 1:
            section_id = next(iter(section_ids))
        section = db.row(
            "SELECT sec.name, p.name AS program_name FROM sections sec "
            "JOIN programs p ON p.id=sec.program_id WHERE sec.id=?",
            (section_id,),
        ) if section_id is not None else None
        program_name = "All programs"
        program_id = None if all_schedules else self.program.currentData()
        if section is not None:
            program_name = section["program_name"]
        elif program_id is not None:
            program = db.row("SELECT name FROM programs WHERE id=?", (program_id,))
            if program:
                program_name = program["name"]

        section_name = section["name"] if section else "All sections"
        year = "—"
        match = re.search(r"\b(\d+)\s*[A-Za-z]?$", section_name)
        if match:
            year_number = int(match.group(1))
            year = year_level_label(year_number)

        meta = [
            f"<b>Program:</b> {esc(program_name)}",
            f"<b>Year:</b> {esc(year)}",
            f"<b>Section:</b> {esc(section_name)}",
        ]
        report_name = "Class Schedules" if all_schedules else self.report.currentText()
        if report_name == "Faculty Schedules" and self.faculty.currentData() is not None:
            meta.append(f"<b>Faculty:</b> {esc(self.faculty.currentText())}")
        if report_name == "Classroom Schedules" and self.room.currentData() is not None:
            meta.append(f"<b>Classroom:</b> {esc(self.room.currentText())}")

        def block_text(rows):
            blocks = []
            for row in rows:
                room_kind = "LAB" if row["room_type"] == "Laboratory" else "LEC"
                blocks.append(
                    f"<b>{esc(row['code'])} · {esc(row['section'])}</b><br>"
                    f"{esc(row['faculty'])} · {esc(row['room'])} ({room_kind})"
                )
            return "<br>".join(blocks)

        head = (
            '<table width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse; margin-bottom:8px;">'
            '<tr><td style="background-color:#17365D; color:#FFFFFF; font-size:18pt; font-weight:bold; text-align:center; padding:8px 0;">CLASS SCHEDULE</td></tr>'
            f'<tr><td style="text-align:center; font-size:11pt; color:#17365D; padding:4px 0;">{esc(self.win.term_name())}</td></tr>'
            '<tr>'
            + "".join(
                f'<td style="border:1px solid #D0D7E2; background-color:#F4F8FC; padding:6px 8px; font-size:10pt;">{item}</td>'
                for item in meta
            )
            + '</tr></table>'
        )
        table = (
            '<table width="100%" border="1" cellspacing="0" cellpadding="2" style="border-collapse:collapse; table-layout:fixed;">'
            '<tr style="background-color:#D9EAF7;"><th width="17%" nowrap="nowrap" style="padding:6px; text-align:center;">PERIOD</th>'
            + "".join(f'<th nowrap="nowrap" style="padding:6px; text-align:center;">{esc(name.upper())}</th>' for _, name in db.DAYS)
            + "</tr>"
        )
        active_until = {day: 0 for day in logic.DAY_CODES}
        for slot in range(slot_count):
            minute = logic.CAL_START + slot * slot_minutes
            next_minute = minute + slot_minutes
            cells = [
                f'<td height="20" align="center" nowrap="nowrap">{esc(logic.fmt(minute))} - {esc(logic.fmt(next_minute))}</td>'
            ]
            for day, _ in db.DAYS:
                component = day_cells[day].get(slot)
                if component:
                    span = component["end"] - component["start"]
                    active_until[day] = component["end"]
                    content = block_text(component["rows"])
                    cells.append(
                        f'<td rowspan="{span}" height="{20 * span}" '
                        f'bgcolor="#ffffff" align="center" valign="middle">'
                        f'<font size="1" color="#000000">{content}</font></td>'
                    )
                elif slot >= active_until[day]:
                    cells.append("<td></td>")
            table += '<tr height="20">' + "".join(cells) + "</tr>"
        return head + table + "</table>"

    def room_utilization_html(self, all_rooms=False):
        esc = lambda value: html.escape(str(value))
        rooms = db.rows('SELECT * FROM classrooms ORDER BY name') if all_rooms else (
            [db.row('SELECT * FROM classrooms WHERE id=?', (self.room.currentData(),))]
            if self.room.currentData() is not None else []
        )
        rooms = [room for room in rooms if room is not None]
        pages = []
        slot_minutes = 30
        slot_count = (logic.CAL_END - logic.CAL_START) // slot_minutes
        rows = logic.schedule_rows(self.win.term_id())
        unavailable = {day: [] for day in logic.DAY_CODES}
        if db.row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"):
            for window in db.rows("SELECT resource_id,day,start_min,end_min FROM unavailable WHERE kind='room'"):
                unavailable.setdefault(window['day'], []).append(window)

        for room_index, room in enumerate(rooms):
            room_rows = [r for r in rows if r['room_id'] == room['id']]
            by_day = {day: [] for day in logic.DAY_CODES}
            for day in logic.DAY_CODES:
                for slot in range(slot_count):
                    start = logic.CAL_START + slot * slot_minutes
                    end = start + slot_minutes
                    occupants = sorted(
                        (r for r in room_rows if r['day'] == day and logic.overlap(
                            start, end, r['start_min'], r['end_min']
                        )),
                        key=lambda r: (r['start_min'], r['code'], r['section']),
                    )
                    blocked = any(
                        logic.overlap(start, end, window['start_min'], window['end_min'])
                        for window in unavailable.get(day, [])
                        if window['resource_id'] == room['id']
                    )
                    status = 'occupied' if occupants else 'unavailable' if blocked else 'available'
                    signature = (status, tuple(r['id'] for r in occupants))
                    if status != 'available' and by_day[day] and by_day[day][-1]['signature'] == signature:
                        by_day[day][-1]['end'] = slot + 1
                    else:
                        by_day[day].append({
                            'start': slot, 'end': slot + 1, 'signature': signature, 'rows': occupants,
                            'status': status,
                        })

            sections = ', '.join(sorted({row['section'] for row in room_rows})) or 'None'
            kind = 'Laboratory' if room['room_type'] == 'Laboratory' else 'Lecture room'
            day_width = 90 / len(db.DAYS)
            table = (
                '<table width="100%" border="1" cellspacing="0" cellpadding="2">'
                '<tr bgcolor="#e9edf3"><th width="10%">TIME</th>'
                + ''.join(
                    f'<th width="{day_width:.2f}%" nowrap="nowrap">{esc(name.upper())}</th>'
                    for _, name in db.DAYS
                )
                + '</tr>'
            )
            active_until = {day: 0 for day in logic.DAY_CODES}
            components = {
                day: {component['start']: component for component in day_components}
                for day, day_components in by_day.items()
            }
            for slot in range(slot_count):
                start = logic.CAL_START + slot * slot_minutes
                finish = start + slot_minutes
                cells = [f'<td height="18" align="center" nowrap="nowrap">{esc(logic.fmt(start))}–{esc(logic.fmt(finish))}</td>']
                for day in logic.DAY_CODES:
                    component = components[day].get(slot)
                    if component:
                        span = component['end'] - component['start']
                        active_until[day] = component['end']
                        if component['rows']:
                            content = '<hr>'.join(
                                f"<b>{esc(r['code'])} · {esc(r['section'])}</b><br>{esc(r['faculty'])}"
                                for r in component['rows']
                            )
                            color = '#ffffff'
                        elif component['status'] == 'unavailable':
                            content = '<b>UNAVAILABLE</b>'
                            color = '#ffffff'
                        else:
                            content = ''
                            color = '#ffffff'
                        cells.append(
                            f'<td rowspan="{span}" height="{max(18 * span, 36 * len(component["rows"]))}" '
                            f'bgcolor="{color}" align="center" valign="middle">'
                            f'<font size="2" color="#000000">{content}</font></td>'
                        )
                    elif slot >= active_until[day]:
                        cells.append('<td></td>')
                table += '<tr>' + ''.join(cells) + '</tr>'
            table += '</table>'
            page_break = ' style="page-break-after: always"' if room_index < len(rooms) - 1 else ''
            pages.append(
                f'<div{page_break}>'
                '<h2 align="center">ROOM UTILIZATION SCHEDULE</h2>'
                f'<p align="center">{esc(self.win.term_name())}</p>'
                '<table width="100%" cellspacing="0" cellpadding="4"><tr>'
                f'<td><b>Room:</b> {esc(room["name"])}</td>'
                f'<td><b>Type:</b> {esc(kind)}</td>'

                f'<td><b>Sections:</b> {esc(sections)}</td>'
                '</tr></table>'
                + table
                + '</div>'
            )
        if not pages:
            return '<h2 align="center">ROOM UTILIZATION SCHEDULE</h2><p>Select a room to view its schedule.</p>'
        return ''.join(pages)

    def save_schedule_sheet(self):
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if not documents:
            raise OSError("The device Documents folder is not available.")
        directory = Path(documents) / "ClassFlow" / "Schedules"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"ClassFlow-schedule-sheet-term-{self.win.term_id()}.pdf"

        document = QTextDocument()
        document.setHtml(self.room_utilization_html(all_rooms=True))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPaperSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(path))
        document.print_(printer)
        if not path.is_file() or path.stat().st_size == 0:
            raise OSError(f"The schedule PDF could not be written to {path}.")
        return path

    def _print_styles(self):
        # Simple tables print more reliably through QTextDocument than screen-only cards.
        return (
            'body{font-family:Arial,sans-serif;color:#202633;font-size:8pt;}'
            '.center{text-align:center;}'
            '.university{font-size:11pt;font-weight:bold;}'
            '.college{font-size:10pt;font-weight:bold;margin-top:8px;}'
            '.heading{font-size:13pt;font-weight:bold;margin-top:7px;}'
            '.meta{margin:13px 0 8px 0;font-size:9pt;}'
            '.report-name{margin:14px 0 6px 0;font-size:10pt;font-weight:bold;}'
            'table{border-collapse:collapse;width:100%;table-layout:fixed;}'
            'th,td{border:1px solid #788292;padding:4px;vertical-align:middle;}'
            'th{background-color:#e7ecf4;font-size:8pt;text-align:center;}'
            'td{font-size:7pt;}'
            '.period{text-align:center;width:18%;background-color:#f5f7fa;white-space:nowrap;}'
            '.signature{margin-top:20px;font-size:9pt;}'
            '.notice{font-size:8pt;color:#586174;}'
        )

    def _official_heading(self, title):
        esc=lambda value: html.escape(str(value))
        return (
            '<div class="center">Republic of the Philippines<br/>'
            '<span class="university">Laguna State Polytechnic University</span><br/>'
            'Province of Laguna<br/>'
            '<div class="college">COLLEGE OF COMPUTER STUDIES</div>'
            f'<div class="heading">{esc(title)}</div>'
            f'<div>{esc(self.win.term_name())}</div></div>'
        )

    def _print_footer(self):
        return ('<div class="signature">Prepared by:<br/><br/>'
                '________________________________</div>')

    def _schedule_groups(self):
        """Separate distinct timetable subjects so 'All' doesn't mix sections."""
        mode=self.report.currentText()
        if mode in ('Class Schedules','Section Schedules'):
            key='section_id'
            name='section'
        elif mode=='Faculty Schedules':
            key='faculty_id'
            name='faculty'
        else:
            key='room_id'
            name='room'
        groups={}
        for row in self.report_rows:
            groups.setdefault(row[key],[]).append(row)
        return [(rows[0][name],rows) for _,rows in sorted(
            groups.items(),key=lambda pair: pair[1][0][name].lower())]

    def _group_details(self, name, rows):
        esc=lambda value: html.escape(str(value))
        if not rows:
            return '<b>No matching saved classes for the selected term.</b>'
        mode=self.report.currentText()
        if mode in ('Class Schedules','Section Schedules'):
            # The program belongs to this particular section, not the filter that
            # may have been hidden or left at another report's selection.
            section=db.row('SELECT p.name, s.name AS section FROM sections s '
                           'JOIN programs p ON p.id=s.program_id WHERE s.id=?',
                           (rows[0]['section_id'],))
            program=section['name'] if section else 'Program not specified'
            import re
            match=re.search(r'(?<![0-9])([1-4])(?:st|nd|rd|th)?(?=\s*[A-Za-z]|$)',name)
            ordinal={'1':'1st','2':'2nd','3':'3rd','4':'4th'}
            year=ordinal[match.group(1)]+' Year' if match else 'Not specified'
            return (f'<b>Program:</b> {esc(program)} &nbsp;&nbsp;'
                    f'<b>Year:</b> {esc(year)} &nbsp;&nbsp;'
                    f'<b>Section:</b> {esc(name)}')
        if mode=='Faculty Schedules':
            return f'<b>Faculty:</b> {esc(name)}'
        return f'<b>Classroom:</b> {esc(name)}'

    def _timetable_html(self):
        """Official weekly sheet: one distinct schedule per section/faculty/room."""
        esc=lambda value: html.escape(str(value))
        days=[('Mon','MONDAY'),('Tue','TUESDAY'),('Wed','WEDNESDAY'),
              ('Thu','THURSDAY'),('Fri','FRIDAY'),('Sat','SATURDAY')]
        colors={'major':'#edf2fb','ged':'#e8f6f7','lab':'#fff3df'}
        start=7*60
        groups=self._schedule_groups()
        if not groups:
            groups=[('No matching schedule',[])]
        pages=[]
        for group_name,rows in groups:
            end_of_day=max([17*60]+[r['end_min'] for r in rows])
            stop=logic.CAL_END
            # A real class occupies its entire time interval. Build individual
            # day columns with rowspans to avoid repeating the class at every
            # 30-minute marker.
            by_day={}
            for day,_ in days:
                meetings=sorted((r for r in rows if r['day']==day),
                                key=lambda r:(r['start_min'],r['end_min']))
                starts={}
                occupied=set()
                for meeting in meetings:
                    first=max(start,(meeting['start_min']//30)*30)
                    last=min(stop,((meeting['end_min']+29)//30)*30)
                    if last<=first:
                        continue
                    # In unusual conflicting schedules, preserve all meeting
                    # labels rather than silently dropping a second meeting.
                    slots=list(range(first,last,30))
                    if any(t in occupied for t in slots):
                        # Overlaps cannot be expressed as independent merged
                        # cells in the same column; attach a warning to the
                        # initial occupied block instead of hiding the meeting.
                        anchor=next((k for k,v in starts.items()
                                     if k < last and k+v[1]*30 > first),None)
                        if anchor is not None:
                            starts[anchor][2].append(meeting)
                        continue
                    starts[first]=[meeting,len(slots),[meeting]]
                    occupied.update(slots)
                by_day[day]=(starts,occupied)
            cells=[]
            for t in range(start,stop,30):
                cols=[f'<td class="period">{esc(logic.fmt(t))}–{esc(logic.fmt(t+30))}</td>']
                for day,_ in days:
                    starts,occupied=by_day[day]
                    if t in starts:
                        meeting,count,conflicts=starts[t]
                        blocks=[]
                        for r in conflicts:
                            blocks.append(
                                f'<b>{esc(r["code"])}</b><br/>'
                                f'Section: {esc(r["section"])}<br/>'
                                f'{esc(r["faculty"])}<br/>'
                                f'{esc(r["room"])}<br/>'
                                f'({esc(r["subject_type"])})'
                            )
                        if len(blocks)>1:
                            blocks.insert(0,'<b>OVERLAPPING CLASSES</b>')
                        color=colors.get(meeting['category'],'#edf2fb')
                        cols.append(
                            f'<td rowspan="{count}" style="background-color:{color};'
                            'text-align:center;">'+'<br/>'.join(blocks)+'</td>'
                        )
                    elif t not in occupied:
                        cols.append('<td></td>')
                cells.append('<tr>'+''.join(cols)+'</tr>')
            table=(
                '<table width="100%"><thead><tr><th width="19%">PERIOD</th>'
                +''.join(f'<th width="13.5%">{name}</th>' for _,name in days)
                +'</tr></thead><tbody>'+''.join(cells)+'</tbody></table>'
            )
            pages.append(
                self._official_heading('CLASS SCHEDULE')
                +'<div class="report-name">'+esc(self.report.currentText())+'</div>'
                +f'<div class="meta">{self._group_details(group_name,rows)}</div>'
                +table+self._print_footer()
            )
        return (
            '<html><head><style>'+self._print_styles()+'</style></head><body>'
            +'<p style="page-break-before:always;"></p>'.join(pages)
            +'</body></html>'
        )

    def _table_report_html(self):
        """Apply the same official heading and ruled-table style to non-grid reports."""
        esc=lambda value: html.escape(str(value))
        mode=self.report.currentText()
        columns=''.join(f'<th>{esc(h.upper())}</th>' for h in self.headers)
        entries=''.join(
            '<tr>'+''.join(f'<td>{esc(value)}</td>' for value in record)+'</tr>'
            for record in self.output
        )
        if not self.output:
            entries=f'<tr><td colspan="{len(self.headers)}" class="center">No matching records</td></tr>'
        return (
            '<html><head><style>'+self._print_styles()+'</style></head><body>'
            +self._official_heading(mode.upper())
            +'<div class="meta">Report based on saved records for the selected academic term.</div>'
            +'<table><thead><tr>'+columns+'</tr></thead><tbody>'+entries+'</tbody></table>'
            +self._print_footer()+'</body></html>'
        )

    def document(self):
        doc=QTextDocument()
        mode=self.report.currentText()
        if mode=='Room Utilization Schedule':
            content=(self._official_heading('ROOM UTILIZATION SCHEDULE')
                     +self.room_utilization_html()+self._print_footer())
            doc.setHtml('<html><head><style>'+self._print_styles()+'</style></head><body>'+content+'</body></html>')
        else:
            doc.setHtml(self._timetable_html() if mode in TIMETABLE_REPORTS
                        else self._table_report_html())
        return doc

    def export_pdf(self):
        default_name = "ClassFlow-schedule-sheet.pdf" if self.report.currentText() in EXPORTABLE_SCHEDULES else "ClassFlow-report.pdf"
        path,_=QFileDialog.getSaveFileName(self,'Export PDF',default_name,'PDF (*.pdf)')
        if path:
            printer=QPrinter(QPrinter.HighResolution)
            printer.setPaperSize(QPrinter.A4)
            printer.setOrientation(QPrinter.Portrait)
            printer.setPageMargins(8, 8, 8, 8, QPrinter.Millimeter)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            document = self.document()
            if self.report.currentText() in EXPORTABLE_SCHEDULES:
                self.print_schedule_pdf(printer, document)
            else:
                document.print_(printer)
            self.win.notify('PDF report exported.')

    def print_report(self):
        printer=QPrinter(QPrinter.HighResolution)
        printer.setPaperSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)
        printer.setPageMargins(8, 8, 8, 8, QPrinter.Millimeter)
        if QPrintDialog(printer,self).exec_():
            document=self.document()
            if self.report.currentText() in EXPORTABLE_SCHEDULES:
                self.print_schedule_pdf(printer,document)
            else:
                document.print_(printer)

    def print_schedule_pdf(self, printer, document):
        # The same document is used for printing and saving PDF.
        document.setTextWidth(printer.pageRect().width())
        document.print_(printer)

    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(
            self,'Export CSV','ClassFlow-report.csv','CSV (*.csv)')
        if not path:
            return
        def safe(value):
            text=str(value)
            return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as handle:
                writer=csv.writer(handle)
                writer.writerow(self.headers)
                writer.writerows([[safe(v) for v in row] for row in self.output])
        except OSError as exc:
            self.win.notify(f'CSV export failed: {exc}','error')
            return
        self.win.notify('CSV report exported.')

    def export_excel(self):
        if self.report.currentText() not in EXPORTABLE_SCHEDULES:
            self.win.notify('Excel schedule export is available for schedule reports.','error')
            return
        default_name = "ClassFlow-schedule-sheet.xlsx"
        path,_=QFileDialog.getSaveFileName(self,'Export Excel',default_name,'Excel Workbook (*.xlsx)')
        if not path:
            return
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Class Schedule'
        sheet.sheet_view.showGridLines = True
        sheet.page_setup.orientation = 'landscape'
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_margins.left = 0.25
        sheet.page_margins.right = 0.25
        sheet.page_margins.top = 0.4
        sheet.page_margins.bottom = 0.4
        sheet.column_dimensions['A'].width = 18
        for column in range(2, 8):
            sheet.column_dimensions[get_column_letter(column)].width = 25

        navy = '17365D'
        blue = 'D9EAF7'
        border_side = Side(style='thin', color='202020')
        cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        title_fill = PatternFill('solid', fgColor=navy)
        header_fill = PatternFill('solid', fgColor=blue)
        title = 'ROOM UTILIZATION SCHEDULE' if self.report.currentText() == 'Room Utilization Schedule' else 'CLASS SCHEDULE'
        sheet.merge_cells('A1:G1')
        sheet['A1'] = title
        sheet['A1'].font = Font(name='Arial', size=16, bold=True, color='FFFFFF')
        sheet['A1'].fill = title_fill
        sheet['A1'].alignment = center
        sheet.row_dimensions[1].height = 30
        sheet.merge_cells('A2:G2')
        sheet['A2'] = self.win.term_name()
        sheet['A2'].font = Font(name='Arial', size=11, italic=True, color=navy)
        sheet['A2'].alignment = center
        sheet.row_dimensions[2].height = 22

        section_ids = {row['section_id'] for row in self.report_rows}
        section_id = self.section.currentData()
        if section_id is None and len(section_ids) == 1:
            section_id = next(iter(section_ids))
        section = db.row(
            'SELECT sec.name, p.name AS program_name FROM sections sec '
            'JOIN programs p ON p.id=sec.program_id WHERE sec.id=?',
            (section_id,),
        ) if section_id is not None else None
        program_name = section['program_name'] if section else (
            self.program.currentText() if self.program.currentData() is not None else 'All programs'
        )
        section_name = section['name'] if section else 'All sections'
        match = re.search(r'\b(\d+)\s*[A-Za-z]?$', section_name)
        year = ''
        if match:
            number = int(match.group(1))
            year = year_level_label(number)
        if self.report.currentText() == 'Room Utilization Schedule':
            meta = [
                f'Room: {self.room.currentText()}',
                f'Type: {db.row("SELECT room_type FROM classrooms WHERE id=?", (self.room.currentData(),))["room_type"] if self.room.currentData() is not None else ""}',
                f'Sections: {", ".join(sorted({row["section"] for row in self.report_rows})) or "None"}',
            ]
        else:
            meta = [f'Program: {program_name}', f'Year: {year}', f'Section: {section_name}']
        for start_column, end_column, value in ((1, 2, meta[0]), (3, 4, meta[1]), (5, 7, meta[2])):
            sheet.merge_cells(start_row=4, start_column=start_column, end_row=4, end_column=end_column)
            cell = sheet.cell(4, start_column, value)
            cell.font = Font(name='Arial', size=10, bold=True)
            cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        sheet.row_dimensions[4].height = 30

        headers = ['PERIOD'] + [name.upper() for _, name in db.DAYS]
        for column, value in enumerate(headers, 1):
            cell = sheet.cell(6, column, value)
            cell.font = Font(name='Arial', size=10, bold=True, color=navy)
            cell.fill = header_fill
            cell.alignment = center
            cell.border = cell_border
        sheet.row_dimensions[6].height = 24

        slot_minutes = 30
        slot_count = (logic.CAL_END - logic.CAL_START) // slot_minutes
        day_entries = {day: [] for day in logic.DAY_CODES}
        for row in self.report_rows:
            if row['day'] not in day_entries:
                continue
            start = max(logic.CAL_START, row['start_min'])
            end = min(logic.CAL_END, row['end_min'])
            if end <= start:
                continue
            start_slot = max(0, (start - logic.CAL_START) // slot_minutes)
            end_slot = min(slot_count, (end - logic.CAL_START + slot_minutes - 1) // slot_minutes)
            if end_slot > start_slot:
                day_entries[row['day']].append((start_slot, end_slot, row))

        components_by_day = {}
        for day, entries in day_entries.items():
            components = []
            for start_slot, end_slot, row in sorted(entries, key=lambda item: (item[0], item[1], item[2]['code'])):
                if components and start_slot < components[-1]['end']:
                    components[-1]['end'] = max(components[-1]['end'], end_slot)
                    components[-1]['rows'].append(row)
                else:
                    components.append({'start': start_slot, 'end': end_slot, 'rows': [row]})
            components_by_day[day] = components

        year_levels = sorted({
            level for row in self.report_rows
            if (level := section_year_level(row['section'])) is not None
        })
        has_multi_year_component = any(
            len({
                level for row in component['rows']
                if (level := section_year_level(row['section'])) is not None
            }) > 1
            for components in components_by_day.values()
            for component in components
        )
        sheet['A5'] = 'YEAR LEVEL'
        sheet['A5'].font = Font(name='Arial', size=9, bold=True, color=navy)
        sheet['A5'].alignment = center
        sheet['A5'].border = cell_border
        legend = [
            (year_level_label(number), YEAR_LEVEL_COLORS.get(number, 'E7E6E6'))
            for number in year_levels
        ]
        if has_multi_year_component:
            legend.append(('Multiple years', MULTI_YEAR_COLOR))
        for column, (text, color) in enumerate(legend, 2):
            cell = sheet.cell(5, column, text)
            cell.font = Font(name='Arial', size=9, bold=True)
            cell.fill = PatternFill('solid', fgColor=color)
            cell.alignment = center
            cell.border = cell_border
        sheet.row_dimensions[5].height = 22

        component_cells = {
            day: {component['start']: component for component in components_by_day[day]}
            for day, _ in db.DAYS
        }
        room_unavailable = {}
        room_id = self.room.currentData()
        if self.report.currentText() == 'Room Utilization Schedule' and room_id is not None:
            if db.row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"):
                room_unavailable = {
                    day: db.rows(
                        "SELECT start_min,end_min FROM unavailable WHERE kind='room' AND resource_id=? AND day=?",
                        (room_id, day),
                    )
                    for day in logic.DAY_CODES
                }
        unavailable_cells = {}
        for day in logic.DAY_CODES:
            components = []
            run_start = None
            for slot in range(slot_count + 1):
                blocked = False
                if slot < slot_count:
                    start = logic.CAL_START + slot * slot_minutes
                    end = start + slot_minutes
                    occupied = any(
                        item['start'] <= slot < item['end']
                        for item in components_by_day[day]
                    )
                    blocked = not occupied and any(
                        logic.overlap(start, end, window['start_min'], window['end_min'])
                        for window in room_unavailable.get(day, [])
                    )
                if blocked and run_start is None:
                    run_start = slot
                elif not blocked and run_start is not None:
                    components.append({'start': run_start, 'end': slot})
                    run_start = None
            unavailable_cells[day] = {item['start']: item for item in components}

        active_until = {day: 0 for day in logic.DAY_CODES}
        for slot in range(slot_count):
            worksheet_row = 7 + slot
            start = logic.CAL_START + slot * slot_minutes
            end = start + slot_minutes
            time_cell = sheet.cell(worksheet_row, 1, f'{logic.fmt(start)}–{logic.fmt(end)}')
            time_cell.font = Font(name='Arial', size=9)
            time_cell.alignment = center
            time_cell.border = cell_border
            sheet.row_dimensions[worksheet_row].height = 27
            for day, _ in db.DAYS:
                column = logic.DAY_CODES.index(day) + 2
                cell = sheet.cell(worksheet_row, column)
                cell.alignment = center
                cell.border = cell_border
                component = component_cells[day].get(slot)
                if component:
                    span = component['end'] - component['start']
                    active_until[day] = component['end']
                    blocks = []
                    for row in component['rows']:
                        room_kind = 'LAB' if row['room_type'] == 'Laboratory' else 'LEC'
                        blocks.append(f"{row['code']} · {row['section']}\n{row['faculty']}\n{row['room']} ({room_kind})")
                    cell.value = '\n\n'.join(blocks)
                    cell.font = Font(name='Arial', size=9, bold=True, color='000000')
                    levels = {
                        level for row in component['rows']
                        if (level := section_year_level(row['section'])) is not None
                    }
                    if len(levels) > 1:
                        cell.fill = PatternFill('solid', fgColor=MULTI_YEAR_COLOR)
                    elif levels:
                        cell.fill = PatternFill(
                            'solid',
                            fgColor=YEAR_LEVEL_COLORS.get(next(iter(levels)), 'E7E6E6'),
                        )
                    if span > 1:
                        sheet.merge_cells(start_row=worksheet_row, start_column=column, end_row=worksheet_row + span - 1, end_column=column)
                    sheet.row_dimensions[worksheet_row].height = max(
                        sheet.row_dimensions[worksheet_row].height or 27,
                        27,
                        42 * len(blocks) / span,
                    )
                elif slot >= active_until[day]:
                    unavailable_component = unavailable_cells[day].get(slot)
                    if unavailable_component:
                        span = unavailable_component['end'] - unavailable_component['start']
                        active_until[day] = unavailable_component['end']
                        cell.value = 'UNAVAILABLE'
                        cell.font = Font(name='Arial', size=9, bold=True, color='9C0006')
                        if span > 1:
                            sheet.merge_cells(start_row=worksheet_row, start_column=column, end_row=worksheet_row + span - 1, end_column=column)

        sheet.print_title_rows = '1:6'
        sheet.print_area = f'A1:G{6 + slot_count}'
        try:
            workbook.save(path)
        except OSError as error:
            self.win.notify(f'Excel schedule could not be exported: {error}', 'error')
            return
        self.win.notify('Excel schedule exported.')
