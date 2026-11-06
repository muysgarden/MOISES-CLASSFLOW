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
        self.report.currentIndexChanged.connect(self._report_changed); self.program.currentIndexChanged.connect(self.populate_sections)
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

    def _report_changed(self, *_):
        # Default to all records when changing report types; filters remain optional.
        for combo in (self.program,self.section,self.faculty,self.room):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.render()

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
        # All-class and all-faculty views contain overlapping unrelated groups;
        # display the assignment list until a specific faculty member is chosen.
        grid_mode=mode in ('Section Schedules','Classroom Schedules') or (mode=='Faculty Schedules' and fid is not None)
        self.calendar.set_rows(self.report_rows,'section' if mode in ['Faculty Schedules','Classroom Schedules'] else 'room')
        self.main_card.title_label.setText(mode)
        selected=(self.faculty.currentText() if mode=='Faculty Schedules' and fid is not None
                  else self.section.currentText() if mode=='Section Schedules' and sid is not None
                  else self.room.currentText() if mode=='Classroom Schedules' and rid is not None
                  else 'All records')
        self.main_card.subtitle.setText(self.win.term_name()+' · '+selected)
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
        fit_table(self.table); self.calendar.setVisible(grid_mode); self.table.setVisible(not grid_mode)
        self.chart_card.setVisible(mode=='Room Utilization')
        self.summary_card.setVisible(mode in REPORTS[:4])
        validation=logic.validate_term(self.win.term_id())
        self.banner.title.setText('Resolve critical conflicts before using final timetables.' if validation['critical'] else 'Timetable validated. No critical conflicts detected.')
        self.banner.text.setText(f'{len(validation["issues"])} issues in this term. Export reflects current saved data.'); self.banner.text.show()
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if validation['critical'] else 'good')
        self.summary.setText(f'Total subjects: {len({r["subject_id"] for r in self.report_rows})}\n\nWeekly class hours: {sum((r["end_min"]-r["start_min"])/60 for r in self.report_rows):g}\n\nRooms assigned: {len({r["room_id"] for r in self.report_rows})}\n\nAverage room utilization:\n{sum(v for _,v in utilization)/6:.1f}%')

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
            'table{border-collapse:collapse;width:100%;}'
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
        # Signatory names must be supplied/approved, not copied from the reference.
        return ('<div class="signature">Prepared by:<br/><br/>'
                '________________________________<br/>Name / Signature / Designation</div>')

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
            stop=min(20*60,((end_of_day+29)//30)*30)
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
                        anchor=next((k for k,v in starts.items() if k<=first and
                                     k+v[1]*30>first),first)
                        if anchor in starts:
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
                '<table><thead><tr><th>PERIOD</th>'
                +''.join(f'<th>{name}</th>' for _,name in days)
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
            +'<div style="page-break-after:always;"></div>'.join(pages)
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
        doc.setHtml(self._timetable_html() if self.report.currentText() in REPORTS[:4]
                    else self._table_report_html())
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
