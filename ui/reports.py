import csv
import html
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QFileDialog
from ui.widgets import Page, Card, Combo, CalendarWidget, BarChart, Banner, button, labeled, label, make_table, text_item, fit_table
import db
import logic

REPORTS=['Class Schedules','Faculty Schedules','Section Schedules','Classroom Schedules','Room Utilization','Faculty Teaching Load','Conflict Reports','Available Rooms']


class ReportsPage(Page):
    def __init__(self,win):
        super().__init__(win)
        self.add_header('MODULE 05','Reports & Timetables','Choose a report, review the saved records, and export what you need.',[
            button('Print',slot=self.print_report),button('Export PDF',slot=self.export_pdf),button('Export CSV','primary',self.export_csv)])
        # One compact filter bar keeps the timetable near the top of the page.
        card=Card(); self.lay.addWidget(card)
        self.report=Combo(); self.report.addItems(REPORTS); self.report.setCurrentIndex(2)
        self.program=Combo(); self.section=Combo(); self.faculty=Combo(); self.room=Combo()
        report_row=QHBoxLayout(); report_row.setSpacing(14)
        report_row.addWidget(labeled('Report Type',self.report),1)
        self.filter_card=QWidget()
        filter_row=QHBoxLayout(self.filter_card)
        filter_row.setContentsMargins(0,0,0,0)
        filter_row.setSpacing(14)
        self.filter_widgets={}
        for key,title,w in [('program','Program',self.program),('section','Section',self.section),('faculty','Faculty',self.faculty),('room','Classroom',self.room)]:
            host=labeled(title,w)
            filter_row.addWidget(host,1)
            self.filter_widgets[key]=host
        report_row.addWidget(self.filter_card,2)
        card.body(margins=(18,12,18,12)).addLayout(report_row)
        self.report.currentIndexChanged.connect(self.render); self.program.currentIndexChanged.connect(self.populate_sections)
        for w in [self.section,self.faculty,self.room]: w.currentIndexChanged.connect(self.render)
        self.main_card=Card('Report Preview','Selected academic term'); self.lay.addWidget(self.main_card)
        body=self.main_card.body(); self.calendar=CalendarWidget(step_minutes=30); body.addWidget(self.calendar)
        self.table=make_table(['Subject','Section','Faculty','Room','Day','Time']); body.addWidget(self.table)
        self.banner=Banner(); body.addWidget(self.banner)
        self.chart_card=Card('Room Utilization','Weekly occupancy rate across all classrooms')
        self.chart=BarChart(); self.chart_card.body().addWidget(self.chart); self.lay.addWidget(self.chart_card)
        self.summary_card=Card('Schedule Summary')
        self.summary=label('',wrap=True); self.summary_card.body().addWidget(self.summary)
        self.lay.addWidget(self.summary_card)
        self.finish()

    def _show_relevant_filters(self,mode):
        relevant={
            'Class Schedules': {'program','section','faculty','room'},
            'Faculty Schedules': {'faculty'},
            'Section Schedules': {'program','section'},
            'Classroom Schedules': {'room'},
            'Room Utilization': set(),
            'Faculty Teaching Load': {'faculty'},
            'Conflict Reports': set(),
            'Available Rooms': {'room'},
        }.get(mode,set())
        self.filter_card.setVisible(bool(relevant))
        for key,host in self.filter_widgets.items():
            host.setVisible(key in relevant)
        return relevant

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
        self.section.setCurrentIndex(max(0,self.section.findData(keep))); self.section.blockSignals(False); self.render()

    def render(self):
        if not hasattr(self,'calendar'): return
        rows=logic.schedule_rows(self.win.term_id())
        mode=self.report.currentText()
        active=self._show_relevant_filters(mode)
        pid=self.program.currentData() if 'program' in active else None
        sections={r[0] for r in db.rows('SELECT id FROM sections WHERE program_id=?',(pid,))} if pid else None
        sid=self.section.currentData() if 'section' in active else None
        fid=self.faculty.currentData() if 'faculty' in active else None
        rid=self.room.currentData() if 'room' in active else None
        self.report_rows=[r for r in rows if (sections is None or r['section_id'] in sections) and (sid is None or r['section_id']==sid) and (fid is None or r['faculty_id']==fid) and (rid is None or r['room_id']==rid)]
        self.calendar.set_rows(self.report_rows,'section' if mode in ['Faculty Schedules','Classroom Schedules'] else 'room')
        self.main_card.title_label.setText(mode)
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
            loads=logic.faculty_loads(self.win.term_id()); self.headers=['Faculty','Assigned Units','Maximum Units']; self.output=[[r['name'],loads.get(r['id'],0),r['max_units']] for r in db.rows('SELECT * FROM faculty') if fid is None or r['id']==fid]
        elif mode=='Conflict Reports':
            self.headers=['Issue','Schedule','Description','Severity']; self.output=[[i['type'],i['label'],i['desc'],i['severity']] for i in logic.validate_term(self.win.term_id())['issues']]
        elif mode=='Available Rooms':
            self.headers=['Room','Capacity','Day','From','To']; self.output=[]
            from ui.availability import unavailable
            for room in db.rows('SELECT * FROM classrooms'):
                if rid is not None and room['id']!=rid: continue
                for d,_ in db.DAYS:
                    for a,b,_ in logic.BLOCKS:
                        if not unavailable('room',room['id'],d,a,b) and not any(r['room_id']==room['id'] and r['day']==d and logic.overlap(a,b,r['start_min'],r['end_min']) for r in rows):
                            self.output.append([room['name'],room['capacity'],d,logic.fmt(a),logic.fmt(b)])
        self.table.setColumnCount(len(self.headers)); self.table.setHorizontalHeaderLabels([h.upper() for h in self.headers]); self.table._flex_weights={i:1 for i in range(len(self.headers))}; self.table.setRowCount(len(self.output))
        for n,record in enumerate(self.output):
            for c,value in enumerate(record): self.table.setItem(n,c,text_item(value))
        fit_table(self.table); self.calendar.setVisible(mode in REPORTS[:4]); self.table.setVisible(mode not in REPORTS[:4])
        self.chart_card.setVisible(mode=='Room Utilization')
        self.summary_card.setVisible(mode in REPORTS[:4])
        validation=logic.validate_term(self.win.term_id())
        self.banner.title.setText('Resolve critical conflicts before using final timetables.' if validation['critical'] else 'Timetable validated. No critical conflicts detected.')
        self.banner.text.setText(f'{len(validation["issues"])} issues in this term. Export reflects current saved data.'); self.banner.text.show()
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if validation['critical'] else 'good')
        self.summary.setText(f'Total subjects: {len({r["subject_id"] for r in self.report_rows})}\n\nWeekly class hours: {sum((r["end_min"]-r["start_min"])/60 for r in self.report_rows):g}\n\nRooms assigned: {len({r["room_id"] for r in self.report_rows})}\n\nAverage room utilization:\n{sum(v for _,v in utilization)/6:.1f}%')

    def _timetable_html(self):
        """Print-friendly 30-minute weekly grid based on the CCS class-schedule sheet.

        The exported grid intentionally differs from the dashboard preview: official
        paper documents need a clear heading, schedule metadata and signature area.
        """
        import re
        esc=lambda value: html.escape(str(value))
        term=self.win.term_name()
        mode=self.report.currentText()
        sections=sorted({r['section'] for r in self.report_rows})
        section_text=self.section.currentText() if self.section.currentData() is not None else ', '.join(sections)
        if not section_text:
            section_text='All sections'
        program_row=None
        if self.section.currentData() is not None:
            program_row=db.row(
                'SELECT p.name, p.code FROM sections s JOIN programs p ON p.id=s.program_id WHERE s.id=?',
                (self.section.currentData(),))
        elif self.program.currentData() is not None:
            program_row=db.row('SELECT name, code FROM programs WHERE id=?',(self.program.currentData(),))
        program_name=program_row['name'] if program_row else 'All programs'
        year_match=re.search(r'\\b([1-4])(?:st|nd|rd|th)?\\b',section_text,flags=re.IGNORECASE)
        year=f"{year_match.group(1)}{'st' if year_match.group(1)=='1' else 'nd' if year_match.group(1)=='2' else 'rd' if year_match.group(1)=='3' else 'th'} Year" if year_match else '—'
        detail=(
            f'<b>Program:</b> {esc(program_name)} &nbsp;&nbsp; '
            f'<b>Year:</b> {esc(year)} &nbsp;&nbsp; '
            f'<b>Section:</b> {esc(section_text)}'
        )
        if mode=='Faculty Schedules':
            detail=f'<b>Faculty:</b> {esc(self.faculty.currentText())}'
        elif mode=='Classroom Schedules':
            detail=f'<b>Classroom:</b> {esc(self.room.currentText())}'
        # The source timetable runs 7 AM–5 PM; extend later when saved classes require it.
        beginning=7*60
        latest=max([17*60]+[r['end_min'] for r in self.report_rows])
        finish=min(20*60,((latest+29)//30)*30)
        colors={'major':'#edf2fb','ged':'#e8f6f7','lab':'#fff3df'}
        day_names=[('Mon','MONDAY'),('Tue','TUESDAY'),('Wed','WEDNESDAY'),
                   ('Thu','THURSDAY'),('Fri','FRIDAY'),('Sat','SATURDAY')]
        body=[]
        for t in range(beginning,finish,30):
            cells=[f'<td class="period">{esc(logic.fmt(t))}–{esc(logic.fmt(t+30))}</td>']
            for day,_ in day_names:
                active=[r for r in self.report_rows if r['day']==day and
                        r['start_min']<t+30 and r['end_min']>t]
                if not active:
                    cells.append('<td></td>')
                    continue
                entries=[]
                for r in active:
                    starts_here=r['start_min']>=t or (t==beginning and r['start_min']<beginning)
                    if starts_here:
                        label=(f'<b>{esc(r["code"])}</b><br/>'
                               f'{esc(r["faculty"])}<br/>'
                               f'{esc(r["room"])}<br/>'
                               f'({esc(r["subject_type"])})')
                        entries.append(label)
                color=colors.get(active[0]['category'],'#edf2fb')
                cells.append(f'<td style="background-color:{color};text-align:center;">'
                             +'<hr/>'.join(entries)+'</td>')
            body.append('<tr>'+''.join(cells)+'</tr>')
        css=(
            'body{font-family:Arial,sans-serif;color:#171c29;font-size:8pt;}'
            '.center{text-align:center;}'
            '.school{font-size:10pt;font-weight:bold;}'
            '.college{font-size:10pt;font-weight:bold;margin-top:6px;}'
            '.heading{font-size:14pt;font-weight:bold;margin-top:8px;}'
            '.meta{margin:12px 0 7px 0;font-size:9pt;}'
            'table{border-collapse:collapse;width:100%;table-layout:fixed;}'
            'th,td{border:1px solid #778195;padding:3px;vertical-align:middle;}'
            'th{background-color:#e7edf7;font-size:8pt;}'
            'td{font-size:7pt;height:19px;}'
            '.period{white-space:nowrap;text-align:center;width:18%;background:#f5f7fa;}'
            '.signature{margin-top:18px;font-size:9pt;}'
        )
        return (
            '<html><head><style>'+css+'</style></head><body>'
            '<div class="center">Republic of the Philippines<br/>'
            '<span class="school">Laguna State Polytechnic University</span><br/>'
            'Province of Laguna<br/>'
            '<div class="college">COLLEGE OF COMPUTER STUDIES</div>'
            '<div class="heading">CLASS SCHEDULE</div>'
            f'<div>{esc(term)}</div></div>'
            f'<div class="meta">{detail}</div>'
            '<table><thead><tr><th>PERIOD</th>'
            +''.join(f'<th>{name}</th>' for _,name in day_names)
            +'</tr></thead><tbody>'+''.join(body)+'</tbody></table>'
            '<div class="signature">Prepared by:'
            '<br/><br/>________________________________<br/>Name / Signature / Designation'
            '</div></body></html>'
        )

    def document(self):
        doc=QTextDocument()
        if self.report.currentText() in REPORTS[:4]:
            doc.setHtml(self._timetable_html())
            return doc
        esc=lambda x:html.escape(str(x))
        doc.setHtml('<h1>ClassFlow</h1><h2>'+esc(self.report.currentText())+'</h2><p>'+esc(self.win.term_name())+'</p><p>'+esc(self.banner.title.text())+'</p><table border="1" cellspacing="0" cellpadding="6"><tr>'+''.join('<th>'+esc(h)+'</th>' for h in self.headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in self.output)+'</table>')
        return doc

    def export_pdf(self):
        path,_=QFileDialog.getSaveFileName(self,'Export PDF','ClassFlow-report.pdf','PDF (*.pdf)')
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
