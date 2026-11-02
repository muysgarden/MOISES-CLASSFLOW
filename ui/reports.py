import csv
import html
import re
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QFileDialog
from ui.widgets import Page, Card, Combo, CalendarWidget, BarChart, Banner, button, labeled, label, make_table, text_item, fit_table
import db
import logic

REPORTS=['Class Schedules','Faculty Schedules','Section Schedules','Classroom Schedules','Room Utilization','Faculty Teaching Load','Conflict Reports','Available Rooms']


class ReportsPage(Page):
    def __init__(self,win):
        super().__init__(win)
        self.add_header('MODULE 05','Timetable Generation and Reports','Generate, review, and export official schedules and academic utilization reports.',[
            button('Print',slot=self.print_report),button('Export PDF',slot=self.export_pdf),button('Export CSV',slot=self.export_csv)])
        card=Card(); self.lay.addWidget(card); row=QHBoxLayout(); card.body(margins=(18,18,18,18)).addLayout(row)
        self.report=Combo(); self.report.addItems(REPORTS); self.report.setCurrentIndex(2)
        self.program=Combo(); self.section=Combo(); self.faculty=Combo(); self.room=Combo()
        for title,w in [('Report Type',self.report),('Program',self.program),('Section',self.section),('Faculty',self.faculty),('Classroom',self.room)]:
            row.addWidget(labeled(title,w),1)
        self.report.currentIndexChanged.connect(self.render); self.program.currentIndexChanged.connect(self.populate_sections)
        for w in [self.section,self.faculty,self.room]: w.currentIndexChanged.connect(self.render)
        columns=QHBoxLayout(); self.lay.addLayout(columns)
        self.main_card=Card('Weekly Timetable','Selected academic term'); columns.addWidget(self.main_card,5)
        body=self.main_card.body(); self.calendar=CalendarWidget(); body.addWidget(self.calendar)
        self.table=make_table(['Subject','Section','Faculty','Room','Day','Time']); body.addWidget(self.table)
        self.banner=Banner(); body.addWidget(self.banner)
        right=QVBoxLayout(); columns.addLayout(right,1)
        chart=Card('Room Utilization','Weekly occupancy rate'); self.chart=BarChart(); chart.body().addWidget(self.chart); right.addWidget(chart)
        summary=Card('Schedule Summary'); self.summary=label('',wrap=True); summary.body().addWidget(self.summary); right.addWidget(summary); right.addStretch(); self.finish()

    def refresh(self):
        for combo,sql,alltext in [(self.program,'SELECT id,name FROM programs ORDER BY code','All programs'),(self.faculty,'SELECT id,name FROM faculty ORDER BY name','All faculty'),(self.room,'SELECT id,name FROM classrooms ORDER BY name','All classrooms')]:
            keep=combo.currentData(); combo.blockSignals(True); combo.clear(); combo.addItem(alltext,None)
            for r in db.rows(sql): combo.addItem(r[1],r[0])
            combo.setCurrentIndex(max(0,combo.findData(keep))); combo.blockSignals(False)
        self.populate_sections()

    def populate_sections(self):
        keep=self.section.currentData(); self.section.blockSignals(True); self.section.clear(); self.section.addItem('All sections',None)
        pid=self.program.currentData()
        for r in db.rows('SELECT id,name FROM sections'+(' WHERE program_id=?' if pid else '')+' ORDER BY name',(pid,) if pid else ()):
            self.section.addItem(r['name'],r['id'])
        self.section.setCurrentIndex(max(0,self.section.findData(keep)) if keep is not None else max(0,self.section.findText('BSCS 2A'))); self.section.blockSignals(False); self.render()

    def render(self):
        if not hasattr(self,'calendar'): return
        rows=logic.schedule_rows(self.win.term_id()); pid=self.program.currentData()
        sections={r[0] for r in db.rows('SELECT id FROM sections WHERE program_id=?',(pid,))} if pid else None
        mode=self.report.currentText()
        self.report_rows=[r for r in rows if (sections is None or r['section_id'] in sections) and (self.section.currentData() is None or r['section_id']==self.section.currentData()) and (self.faculty.currentData() is None or r['faculty_id']==self.faculty.currentData()) and (self.room.currentData() is None or r['room_id']==self.room.currentData())]
        self.calendar.set_rows(self.report_rows,'section' if mode in ['Faculty Schedules','Classroom Schedules'] else 'room')
        self.main_card.title_label.setText(mode+' — '+self.section.currentText())
        self.main_card.subtitle.setText(self.win.term_name())
        self.headers=['Subject','Section','Faculty','Room','Day','Time']
        self.output=[[r['code'],r['section'],r['faculty'],r['room'],r['day'],f'{logic.fmt(r["start_min"])} – {logic.fmt(r["end_min"])}'] for r in self.report_rows]
        room_count=db.row('SELECT COUNT(*) FROM classrooms')[0]
        hours=(logic.CAL_END-logic.CAL_START)/60
        utilization=[]
        for d,_ in db.DAYS:
            # Merge occupied intervals per room, so overlaps cannot inflate occupancy.
            total=0
            for room in db.rows('SELECT id FROM classrooms'):
                intervals=sorted((max(logic.CAL_START,r['start_min']),min(logic.CAL_END,r['end_min'])) for r in rows if r['day']==d and r['room_id']==room['id'])
                end=logic.CAL_START
                for a,b in intervals:
                    total+=max(0,b-max(a,end)); end=max(end,b)
            utilization.append((d,round(100*total/(room_count*hours*60),1) if room_count else 0))
        self.chart.set_data(utilization)
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
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if validation['critical'] else 'good')
        self.summary.setText(f'Total subjects: {len({r["subject_id"] for r in self.report_rows})}\n\nWeekly class hours: {sum((r["end_min"]-r["start_min"])/60 for r in self.report_rows):g}\n\nRooms assigned: {len({r["room_id"] for r in self.report_rows})}\n\nAverage room utilization:\n{sum(v for _,v in utilization)/6:.1f}%')

    def schedule_sheet_html(self):
        esc = lambda value: html.escape(str(value))
        slot_minutes = 30
        slot_count = (logic.CAL_END - logic.CAL_START) // slot_minutes
        by_day = {day: [] for day in logic.DAY_CODES}
        for row in self.report_rows:
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

        section_ids = {row["section_id"] for row in self.report_rows}
        section_id = self.section.currentData()
        if section_id is None and len(section_ids) == 1:
            section_id = next(iter(section_ids))
        section = db.row(
            "SELECT sec.name, p.name AS program_name FROM sections sec "
            "JOIN programs p ON p.id=sec.program_id WHERE sec.id=?",
            (section_id,),
        ) if section_id is not None else None
        program_name = "All programs"
        program_id = self.program.currentData()
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
            suffix = "th" if 10 <= year_number % 100 <= 20 else {
                1: "st", 2: "nd", 3: "rd"
            }.get(year_number % 10, "th")
            year = f"{year_number}{suffix} year"

        meta = [
            f"<b>Program:</b> {esc(program_name)}",
            f"<b>Year:</b> {esc(year)}",
            f"<b>Section:</b> {esc(section_name)}",
        ]
        if self.report.currentText() == "Faculty Schedules" and self.faculty.currentData() is not None:
            meta.append(f"<b>Faculty:</b> {esc(self.faculty.currentText())}")
        if self.report.currentText() == "Classroom Schedules" and self.room.currentData() is not None:
            meta.append(f"<b>Classroom:</b> {esc(self.room.currentText())}")

        def block_text(rows):
            blocks = []
            for row in rows:
                room_kind = "LAB" if row["room_type"] == "Laboratory" else "LEC"
                blocks.append(
                    f"<b>{esc(row['code'])} · {esc(row['section'])}</b><br>"
                    f"{esc(row['faculty'])}<br>"
                    f"{esc(row['room'])} ({room_kind})"
                )
            return "<hr>".join(blocks)

        head = (
            '<h2 align="center">CLASS SCHEDULE</h2>'
            f'<p align="center">{esc(self.win.term_name())}</p>'
            '<table width="100%" cellspacing="0" cellpadding="4"><tr>'
            + "".join(f"<td>{item}</td>" for item in meta)
            + "</tr></table>"
        )
        table = (
            '<table width="100%" border="1" cellspacing="0" cellpadding="2">'
            '<tr bgcolor="#e9edf3"><th width="12%">PERIOD</th>'
            + "".join(f"<th>{esc(name.upper())}</th>" for _, name in db.DAYS)
            + "</tr>"
        )
        active_until = {day: 0 for day in logic.DAY_CODES}
        for slot in range(slot_count):
            minute = logic.CAL_START + slot * slot_minutes
            next_minute = minute + slot_minutes
            cells = [
                f'<td height="18" align="center">{esc(logic.fmt(minute))}–{esc(logic.fmt(next_minute))}</td>'
            ]
            for day, _ in db.DAYS:
                component = day_cells[day].get(slot)
                if component:
                    span = component["end"] - component["start"]
                    active_until[day] = component["end"]
                    content = block_text(component["rows"])
                    cells.append(
                        f'<td rowspan="{span}" height="{max(18 * span, 36 * len(component["rows"]))}" '
                        f'bgcolor="#fce8d4" align="center" valign="middle">'
                        f'<font size="2">{content}</font></td>'
                    )
                elif slot >= active_until[day]:
                    cells.append("<td></td>")
            table += "<tr>" + "".join(cells) + "</tr>"
        return head + table + "</table>"

    def document(self):
        esc=lambda x:html.escape(str(x))
        doc=QTextDocument()
        if self.report.currentText() in REPORTS[:4]:
            doc.setHtml(self.schedule_sheet_html())
        else:
            doc.setHtml('<h1>ClassFlow</h1><h2>'+esc(self.report.currentText())+'</h2><p>'+esc(self.win.term_name())+'</p><p>'+esc(self.banner.title.text())+'</p><table border="1" cellspacing="0" cellpadding="6"><tr>'+''.join('<th>'+esc(h)+'</th>' for h in self.headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in self.output)+'</table>')
        return doc

    def export_pdf(self):
        default_name = "ClassFlow-schedule-sheet.pdf" if self.report.currentText() in REPORTS[:4] else "ClassFlow-report.pdf"
        path,_=QFileDialog.getSaveFileName(self,'Export PDF',default_name,'PDF (*.pdf)')
        if path:
            printer=QPrinter(QPrinter.HighResolution); printer.setOrientation(QPrinter.Landscape); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(path); self.document().print_(printer); self.win.notify('PDF report exported.')

    def print_report(self):
        printer=QPrinter(QPrinter.HighResolution); printer.setOrientation(QPrinter.Landscape)
        if QPrintDialog(printer,self).exec_(): self.document().print_(printer)

    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,'Export CSV','ClassFlow-report.csv','CSV (*.csv)')
        if path:
            def safe(v):
                text=str(v)
                return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(self.headers); w.writerows([[safe(v) for v in row] for row in self.output])
            self.win.notify('CSV report exported.')
