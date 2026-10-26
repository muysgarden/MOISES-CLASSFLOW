from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QMessageBox
from ui.widgets import Page, Card, Combo, CalendarWidget, button, labeled, make_table, text_item, fit_table, widget_cell, Banner
import db
import logic


class SchedulesPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.replace_ids = []
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
        self.search=QLineEdit(); self.search.setPlaceholderText('Search schedules…'); self.search.textChanged.connect(self.render)
        listing=Card('Existing Schedules','Assignments for the selected term',right=[self.search]); columns.addWidget(listing,6)
        self.table=make_table(['Subject / Section','Faculty','Room','Schedule','Actions'],flex={0:3,1:3,2:2,3:3,4:3}); listing.add(self.table)
        self.section=Combo(); self.section.currentIndexChanged.connect(self.render)
        cal=Card('Weekly Calendar Preview','Selected section',right=[self.section]); columns.addWidget(cal,5)
        self.calendar=CalendarWidget(); cal.body().addWidget(self.calendar)
        self.finish()

    def refresh(self):
        for key,sql in [('subject_id','SELECT id,code || " — " || title FROM subjects ORDER BY code'),('section_id','SELECT id,name FROM sections ORDER BY name'),('faculty_id','SELECT id,name FROM faculty ORDER BY name'),('room_id','SELECT id,name || " · " || capacity || " seats" FROM classrooms ORDER BY name')]:
            combo=self.fields[key]; keep=combo.currentData(); combo.blockSignals(True); combo.clear()
            for r in db.rows(sql): combo.addItem(r[1],r[0])
            idx=combo.findData(keep); combo.setCurrentIndex(max(0,idx)); combo.blockSignals(False)
        keep=self.section.currentData(); self.section.blockSignals(True); self.section.clear(); self.section.addItem('All sections',None)
        for r in db.rows('SELECT id,name FROM sections ORDER BY name'): self.section.addItem(r['name'],r['id'])
        self.section.setCurrentIndex(max(0,self.section.findData(keep)) if keep is not None else max(0,self.section.findText('BSCS 2A'))); self.section.blockSignals(False)
        self.render(); self.preview()

    def values(self):
        return {k:v.currentData() for k,v in self.fields.items()}

    def preview(self):
        if not hasattr(self,'status'): return
        d=self.values()
        if any(v is None for v in d.values()): return
        issues=logic.check_candidate(self.win.term_id(),d['subject_id'],d['section_id'],d['faculty_id'],d['room_id'],d['days'].split(','),d['start'],d['end'],self.replace_ids)
        self.status.title.setText('Time slot available' if not issues else issues[0]['type'])
        self.status.text.setText('Faculty, classroom, and section have no conflicts.' if not issues else '\n'.join(i['desc'] for i in issues))
        self.status.text.show()
        from ui.widgets import set_kind
        set_kind(self.status,'bad' if any(i['severity']==logic.CRITICAL for i in issues) else 'good' if not issues else 'warn')

    def save(self):
        d=self.values()
        if any(v is None for v in d.values()):
            self.win.notify('Create subjects, sections, faculty, and classrooms first.','error'); return
        issues=logic.check_candidate(self.win.term_id(),d['subject_id'],d['section_id'],d['faculty_id'],d['room_id'],d['days'].split(','),d['start'],d['end'],self.replace_ids)
        if any(i['severity']==logic.CRITICAL for i in issues):
            QMessageBox.warning(self,'Cannot save schedule','\n'.join(i['desc'] for i in issues)); return
        if issues and QMessageBox.question(self,'Schedule warnings','\n'.join(i['desc'] for i in issues)+'\n\nSave anyway?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        logic.save_schedule(self.win.term_id(),d['subject_id'],d['section_id'],d['faculty_id'],d['room_id'],d['days'].split(','),d['start'],d['end'],self.replace_ids)
        self.replace_ids=[]; self.win.data_changed(); self.render(); self.preview(); self.win.notify('Schedule saved.')

    def clear(self):
        self.replace_ids=[]; self.refresh()

    def render(self):
        if not hasattr(self,'table'): return
        self.groups=logic.group_rows(logic.schedule_rows(self.win.term_id()))
        query=self.search.text().casefold()
        groups=[g for g in self.groups if query in ' '.join(str(v) for v in g.values()).casefold() and (self.section.currentData() is None or g['section_id']==self.section.currentData())]
        self.table.setRowCount(len(groups))
        for i,g in enumerate(groups):
            for j,text in enumerate([g['code']+' · '+g['section'],g['faculty'],g['room'],g['days_label']+'\n'+g['time_label']]): self.table.setItem(i,j,text_item(text,bold=j==0))
            actions=QWidget(); row=QHBoxLayout(actions); row.setContentsMargins(0,0,0,0)
            row.addWidget(button('Edit','linkbtn',lambda _,g=g:self.edit(g)))
            row.addWidget(button('Delete','danger',lambda _,g=g:self.delete(g)))
            widget_cell(self.table,i,4,actions)
        fit_table(self.table); self.render_calendar()

    def render_calendar(self):
        if not hasattr(self,'calendar'): return
        sid=self.section.currentData()
        self.calendar.set_rows([r for r in logic.schedule_rows(self.win.term_id()) if sid is None or r['section_id']==sid])

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
            logic.delete_schedules(self.win.term_id(),g['ids']); self.replace_ids=[]; self.render(); self.preview(); self.win.data_changed()

    def open(self,edit_ids=None,**kw):
        self.refresh()
        if edit_ids:
            for g in self.groups:
                if set(g['ids']) & set(edit_ids): self.edit(g); break

    def search_all(self,query):
        self.section.setCurrentIndex(0)
        self.search.setText(query)
