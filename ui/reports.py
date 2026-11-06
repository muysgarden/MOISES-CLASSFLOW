import html
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

REPORTS=['Class Schedules','Faculty Schedules','Section Schedules','Room Utilization Schedule','Room Utilization','Faculty Teaching Load','Conflict Reports','Available Rooms']
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
        self.add_header('MODULE 05','Timetable Generation and Reports','Generate, review, and export official schedules and academic utilization reports.',[
            button('Print',slot=self.print_report),button('Export PDF',slot=self.export_pdf),self.excel_button])
        card=Card(); self.lay.addWidget(card); row=QHBoxLayout(); card.body(margins=(18,18,18,18)).addLayout(row)
        self.report=Combo(); self.report.addItems(REPORTS); self.report.setCurrentIndex(3)
        self.program=Combo(); self.section=Combo(); self.faculty=Combo(); self.room=Combo()
        for title,w in [('Report Type',self.report),('Program',self.program),('Section',self.section),('Faculty',self.faculty),('Classroom',self.room)]:
            row.addWidget(labeled(title,w),1)
        self.report.currentIndexChanged.connect(self.report_changed); self.program.currentIndexChanged.connect(self.populate_sections)
        for w in [self.section,self.faculty,self.room]: w.currentIndexChanged.connect(self.render)
        columns=QHBoxLayout(); self.lay.addLayout(columns)
        self.main_card=Card('Weekly Timetable','Selected academic term'); columns.addWidget(self.main_card,5)
        body=self.main_card.body(); self.calendar=CalendarWidget(); body.addWidget(self.calendar)
        self.table=make_table(['Subject','Section','Faculty','Room','Day','Time']); body.addWidget(self.table)
        self.resolve_button=button('Resolve conflicts','smallPrimary',lambda: self.win.go('validation'))
        self.resolve_button.setVisible(False)
        self.banner=Banner(right=self.resolve_button); body.addWidget(self.banner)
        right=QVBoxLayout(); columns.addLayout(right,1)
        chart=Card('Room Utilization','Weekly occupancy rate'); self.chart_card=chart; self.chart=BarChart(); chart.body().addWidget(self.chart); right.addWidget(chart)
        summary=Card('Schedule Summary'); self.summary=label('',wrap=True); summary.body().addWidget(self.summary); right.addWidget(summary); right.addStretch(); self.finish()

    def refresh(self):
        if self.report.currentText() == 'Room Utilization Schedule':
            for combo in (self.program, self.section, self.faculty):
                combo.blockSignals(True)
                combo.setCurrentIndex(-1)
                combo.blockSignals(False)
        include_all = self.report.currentText() not in REPORTS[:3]
        self._set_filter_options(
            self.program, db.rows('SELECT id,name FROM programs ORDER BY code'),
            'All programs', include_all,
        )
        self._set_filter_options(
            self.faculty, db.rows('SELECT id,name FROM faculty ORDER BY name'),
            'All faculty', include_all,
        )
        self._set_filter_options(
            self.room, db.rows('SELECT id,name FROM classrooms ORDER BY name'),
            'All rooms', self.report.currentText() != 'Room Utilization Schedule',
        )
        self.populate_sections()

    def _set_filter_options(self, combo, records, all_label, include_all, preferred_text=None):
        selected = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if include_all:
            combo.addItem(all_label, None)
        for record in records:
            combo.addItem(record['name'], record['id'])
        index = combo.findData(selected)
        if index < 0 and preferred_text is not None:
            index = combo.findText(preferred_text)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def report_changed(self):
        room_schedule = self.report.currentText() == 'Room Utilization Schedule'
        if room_schedule:
            for combo in (self.program, self.section, self.faculty):
                combo.blockSignals(True)
                combo.setCurrentIndex(-1)
                combo.blockSignals(False)
        else:
            self.room.blockSignals(True)
            self.room.setCurrentIndex(-1)
            self.room.blockSignals(False)
        include_all = self.report.currentText() not in REPORTS[:3]
        self._set_filter_options(
            self.program, db.rows('SELECT id,name FROM programs ORDER BY code'),
            'All programs', include_all,
        )
        self._set_filter_options(
            self.faculty, db.rows('SELECT id,name FROM faculty ORDER BY name'),
            'All faculty', include_all,
        )
        self._set_filter_options(
            self.room, db.rows('SELECT id,name FROM classrooms ORDER BY name'),
            'All rooms', not room_schedule,
        )
        self.populate_sections()

    def populate_sections(self):
        include_all = self.report.currentText() not in REPORTS[:3]
        pid=self.program.currentData()
        records = db.rows(
            'SELECT id,name FROM sections'+(' WHERE program_id=?' if pid else '')+' ORDER BY name',
            (pid,) if pid else (),
        )
        self._set_filter_options(
            self.section, records, 'All sections', include_all, preferred_text='BSCS 2A',
        )
        self.render()

    def render(self):
        if not hasattr(self,'calendar'): return
        rows=logic.schedule_rows(self.win.term_id()); pid=self.program.currentData()
        sections={r[0] for r in db.rows('SELECT id FROM sections WHERE program_id=?',(pid,))} if pid else None
        mode=self.report.currentText()
        self.excel_button.setEnabled(mode in REPORTS[:4])
        if mode == 'Room Utilization Schedule':
            room_id = self.room.currentData()
            self.report_rows = [r for r in rows if room_id is not None and r['room_id'] == room_id]
        else:
            self.report_rows=[r for r in rows if (sections is None or r['section_id'] in sections) and (self.section.currentData() is None or r['section_id']==self.section.currentData()) and (self.faculty.currentData() is None or r['faculty_id']==self.faculty.currentData()) and (self.room.currentData() is None or r['room_id']==self.room.currentData())]
        self.calendar.set_rows(
            self.report_rows,
            'section' if mode in ['Faculty Schedules','Room Utilization Schedule'] else 'room',
            include_faculty=mode == 'Room Utilization Schedule',
            show_availability=mode == 'Room Utilization Schedule' and self.room.currentData() is not None,
            room_id=self.room.currentData() if mode == 'Room Utilization Schedule' else None,
        )
        for combo in (self.program, self.section, self.faculty):
            combo.setEnabled(mode != 'Room Utilization Schedule')
        self.main_card.title_label.setText(
            mode+' — '+(self.room.currentText() if mode == 'Room Utilization Schedule' else self.section.currentText())
        )
        self.main_card.subtitle.setText(self.win.term_name())
        self.headers=['Subject','Section','Faculty','Room','Day','Time']
        self.output=[[r['code'],r['section'],r['faculty'],r['room'],r['day'],f'{logic.fmt(r["start_min"])} – {logic.fmt(r["end_min"])}'] for r in self.report_rows]
        if mode == 'Room Utilization Schedule':
            self.headers=['Room','Day','From','To','Status','Course','Section','Instructor']
            self.output=[]
            selected_room=self.room.currentData()
            room_record=db.row('SELECT name FROM classrooms WHERE id=?',(selected_room,)) if selected_room is not None else None
            unavailable={}
            if selected_room is not None and db.row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unavailable'"):
                unavailable={d:db.rows(
                    "SELECT start_min,end_min FROM unavailable WHERE kind='room' AND resource_id=? AND day=?",
                    (selected_room,d),
                ) for d,_ in db.DAYS}
            for day,_ in db.DAYS:
                for start in range(logic.CAL_START,logic.CAL_END,30):
                    end=start+30
                    occupants=[r for r in self.report_rows if r['day']==day and logic.overlap(start,end,r['start_min'],r['end_min'])]
                    blocked=any(logic.overlap(start,end,w['start_min'],w['end_min']) for w in unavailable.get(day,[]))
                    status='Occupied' if occupants else 'Unavailable' if blocked else 'Available'
                    self.output.append([
                        room_record['name'] if room_record else '',
                        day,logic.fmt(start),logic.fmt(end),status,
                        '; '.join(r['code'] for r in occupants),
                        '; '.join(r['section'] for r in occupants),
                        '; '.join(r['faculty'] for r in occupants),
                    ])
        utilization_rooms=db.rows('SELECT id FROM classrooms')
        if mode == 'Room Utilization Schedule':
            room_id=self.room.currentData()
            utilization_rooms=[r for r in utilization_rooms if r['id']==room_id] if room_id is not None else []
        room_count=len(utilization_rooms)
        hours=(logic.CAL_END-logic.CAL_START)/60
        utilization=[]
        for d,_ in db.DAYS:
            # Merge occupied intervals per room, so overlaps cannot inflate occupancy.
            total=0
            for room in utilization_rooms:
                intervals=sorted((max(logic.CAL_START,r['start_min']),min(logic.CAL_END,r['end_min'])) for r in rows if r['day']==d and r['room_id']==room['id'])
                end=logic.CAL_START
                for a,b in intervals:
                    total+=max(0,b-max(a,end)); end=max(end,b)
            utilization.append((d,round(100*total/(room_count*hours*60),1) if room_count else 0))
        self.chart.set_data(utilization)
        self.chart_card.title_label.setText(
            'Selected Room Utilization' if mode == 'Room Utilization Schedule' else 'Room Utilization'
        )
        if mode=='Room Utilization':
            self.headers=['Day','Occupancy']; self.output=[[d,str(v)+'%'] for d,v in utilization]
        elif mode=='Faculty Teaching Load':
            loads=logic.faculty_loads(self.win.term_id()); self.headers=['Faculty','Assigned Units','Maximum Units']; self.output=[[r['name'],loads.get(r['id'],0),r['max_units']] for r in db.rows('SELECT * FROM faculty') if self.faculty.currentData() is None or r['id']==self.faculty.currentData()]
        elif mode=='Conflict Reports':
            self.headers=['Issue','Schedule','Description','Severity']; self.output=[[i['type'],i['label'],i['desc'],i['severity']] for i in logic.validate_term(self.win.term_id())['issues']]
        elif mode=='Available Rooms':
            self.headers=['Room','Capacity','Day','From','To']; self.output=[]
            from ui.availability import unavailable
            for room in db.rows('SELECT * FROM classrooms'):
                if self.room.currentData() is not None and room['id']!=self.room.currentData(): continue
                for d,_ in db.DAYS:
                    for a,b,_ in logic.BLOCKS:
                        if not unavailable('room',room['id'],d,a,b) and not any(r['room_id']==room['id'] and r['day']==d and logic.overlap(a,b,r['start_min'],r['end_min']) for r in rows):
                            self.output.append([room['name'],room['capacity'],d,logic.fmt(a),logic.fmt(b)])
        self.table.setColumnCount(len(self.headers)); self.table.setHorizontalHeaderLabels([h.upper() for h in self.headers]); self.table._flex_weights={i:1 for i in range(len(self.headers))}; self.table.setRowCount(len(self.output))
        for n,record in enumerate(self.output):
            for c,value in enumerate(record): self.table.setItem(n,c,text_item(value))
        fit_table(self.table); self.calendar.setVisible(mode in REPORTS[:4]); self.table.setVisible(mode not in REPORTS[:4])
        validation=logic.validate_term(self.win.term_id())
        self.banner.title.setText('Resolve critical conflicts before using final timetables.' if validation['critical'] else 'Timetable validated. No critical conflicts detected.')
        self.banner.text.setText(f'{len(validation["issues"])} issues in this term. Export reflects current saved data.'); self.banner.text.show()
        self.resolve_button.setVisible(validation['critical'] > 0)
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if validation['critical'] else 'good')
        summary_label='Average selected room utilization' if mode == 'Room Utilization Schedule' else 'Average room utilization'
        self.summary.setText(f'Total subjects: {len({r["subject_id"] for r in self.report_rows})}\n\nWeekly class hours: {sum((r["end_min"]-r["start_min"])/60 for r in self.report_rows):g}\n\nRooms assigned: {len({r["room_id"] for r in self.report_rows})}\n\n{summary_label}:\n{sum(v for _,v in utilization)/6:.1f}%')

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
                f'<td><b>Capacity:</b> {esc(room["capacity"])}</td>'
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
        printer.setOrientation(QPrinter.Landscape)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(path))
        document.print_(printer)
        if not path.is_file() or path.stat().st_size == 0:
            raise OSError(f"The schedule PDF could not be written to {path}.")
        return path

    def document(self):
        esc=lambda x:html.escape(str(x))
        doc=QTextDocument()
        if self.report.currentText() == 'Room Utilization Schedule':
            doc.setHtml(self.room_utilization_html())
        elif self.report.currentText() in REPORTS[:4]:
            doc.setHtml(self.schedule_sheet_html())
        else:
            doc.setHtml('<h1>ClassFlow</h1><h2>'+esc(self.report.currentText())+'</h2><p>'+esc(self.win.term_name())+'</p><p>'+esc(self.banner.title.text())+'</p><table border="1" cellspacing="0" cellpadding="6"><tr>'+''.join('<th>'+esc(h)+'</th>' for h in self.headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in self.output)+'</table>')
        return doc

    def print_schedule_pdf(self, printer, document):
        printer.setPaperSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Landscape)
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        page = printer.pageRect(QPrinter.Point)
        document.setTextWidth(page.width())
        frames = [document.rootFrame()]
        while frames:
            frame = frames.pop()
            for child in frame.childFrames():
                if isinstance(child, QTextTable) and child.columns() == len(db.DAYS) + 1:
                    table_format = child.format()
                    table_format.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                    time_column_width = 17
                    table_format.setColumnWidthConstraints(
                        [QTextLength(QTextLength.PercentageLength, time_column_width)]
                        + [
                            QTextLength(
                                QTextLength.PercentageLength,
                                (100 - time_column_width) / len(db.DAYS),
                            )
                            for _ in db.DAYS
                        ]
                    )
                    child.setFormat(table_format)
                frames.append(child)
        size = document.documentLayout().documentSize()
        scale = min(1.0, page.height() / size.height())

        painter = QPainter(printer)
        painter.setWindow(0, 0, round(page.width()), round(page.height()))
        painter.translate(
            (page.width() - size.width() * scale) / 2,
            (page.height() - size.height() * scale) / 2,
        )
        painter.scale(scale, scale)
        document.drawContents(painter, QRectF(0, 0, size.width(), size.height()))
        painter.end()

    def export_pdf(self):
        default_name = "ClassFlow-schedule-sheet.pdf" if self.report.currentText() in REPORTS[:4] else "ClassFlow-report.pdf"
        path,_=QFileDialog.getSaveFileName(self,'Export PDF',default_name,'PDF (*.pdf)')
        if path:
            printer=QPrinter(QPrinter.HighResolution); printer.setOrientation(QPrinter.Landscape); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(path)
            document = self.document()
            if self.report.currentText() in REPORTS[:4]:
                self.print_schedule_pdf(printer, document)
            else:
                document.print_(printer)
            self.win.notify('PDF report exported.')

    def print_report(self):
        printer=QPrinter(QPrinter.HighResolution); printer.setOrientation(QPrinter.Landscape)
        if QPrintDialog(printer,self).exec_(): self.document().print_(printer)

    def export_excel(self):
        if self.report.currentText() not in REPORTS[:4]:
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
