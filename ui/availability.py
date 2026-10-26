from PyQt5.QtWidgets import QHBoxLayout, QWidget, QGridLayout, QDialog, QVBoxLayout, QCheckBox, QMessageBox
from ui.widgets import Page, Card, Combo, Banner, Bar, WeekGrid, label, labeled, button, clear_layout
import db
import logic


def init_availability():
    db.conn.execute('''CREATE TABLE IF NOT EXISTS unavailable(
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, resource_id INTEGER NOT NULL,
        day TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER NOT NULL)''')
    db.conn.commit()


def unavailable(kind,rid,day,start,end):
    return any(logic.overlap(start,end,r['start_min'],r['end_min']) for r in db.rows(
        'SELECT * FROM unavailable WHERE kind=? AND resource_id=? AND day=?',(kind,rid,day)))


class AvailabilityPage(Page):
    def __init__(self,win):
        super().__init__(win); init_availability()
        self.add_header('MODULE 02','Faculty and Room Availability','Review teaching loads and find compatible faculty and classroom time slots.',[button('Update Availability','primary',self.update_availability)])
        controls=Card(); self.lay.addWidget(controls); row=QHBoxLayout(); controls.body(margins=(18,18,18,18)).addLayout(row)
        row.addWidget(label('◷  Available Time Slots','cardTitle'))
        self.day=Combo(); self.day.addItems([name for _,name in db.DAYS])
        self.start=Combo(); self.end=Combo()
        for m,t in logic.TIME_CHOICES: self.start.addItem(t,m); self.end.addItem(t,m)
        self.start.setCurrentIndex(2); self.end.setCurrentIndex(6)
        self.room_type=Combo(); self.room_type.addItem('All room types')
        for name,w in [('Day',self.day),('From',self.start),('To',self.end),('Room Type',self.room_type)]: row.addWidget(labeled(name,w),1)
        row.addWidget(button('Find Available','primary',self.refresh))
        self.summary=label(''); self.lay.addWidget(self.summary)
        columns=QHBoxLayout(); self.lay.addLayout(columns)
        faculty=Card('Faculty Availability','Teaching load and weekly time preferences'); rooms=Card('Classroom Availability','Capacity, type, and weekly room schedule'); columns.addWidget(faculty); columns.addWidget(rooms)
        self.faculty_grid=QGridLayout(); faculty.body().addLayout(self.faculty_grid)
        self.room_grid=QGridLayout(); rooms.body().addLayout(self.room_grid)
        self.lay.addWidget(label('■ Available     ▪ Unavailable / Scheduled','muted')); self.finish()

    def refresh(self):
        types=[r[0] for r in db.rows('SELECT DISTINCT room_type FROM classrooms ORDER BY room_type')]
        keep=self.room_type.currentText(); self.room_type.clear(); self.room_type.addItem('All room types'); self.room_type.addItems(types); self.room_type.setCurrentIndex(max(0,self.room_type.findText(keep)))
        clear_layout(self.faculty_grid); clear_layout(self.room_grid)
        start,end=self.start.currentData(),self.end.currentData(); day=db.DAYS[self.day.currentIndex()][0]
        if end<=start: self.summary.setText('Choose an end time after the start time.'); return
        rows=logic.schedule_rows(self.win.term_id()); loads=logic.faculty_loads(self.win.term_id()); counts=[]
        for kind,table,grid,key in [('faculty','faculty',self.faculty_grid,'faculty_id'),('room','classrooms',self.room_grid,'room_id')]:
            n=0
            for r in db.rows('SELECT * FROM '+table+' ORDER BY name'):
                if kind=='room' and self.room_type.currentIndex()>0 and r['room_type']!=self.room_type.currentText(): continue
                available=not unavailable(kind,r['id'],day,start,end) and not any(s[key]==r['id'] and s['day']==day and logic.overlap(start,end,s['start_min'],s['end_min']) for s in rows)
                n+=available
                box=Card(); v=box.body(margins=(14,14,14,14)); v.addWidget(label(r['name'],'cardTitle')); v.addWidget(label(('Available' if available else 'Unavailable')+' · '+(r['department'] if kind=='faculty' else str(r['capacity'])+' seats · '+r['room_type']),'muted',wrap=True))
                if kind=='faculty':
                    load=loads.get(r['id'],0); v.addWidget(label(f'Teaching load: {load}/{r["max_units"]} units','muted')); v.addWidget(Bar(min(100,100*load/max(1,r['max_units']))))
                week=WeekGrid([{
                    "day": d, "blocks": [not unavailable(kind,r["id"],d,a,b) and not any(s[key]==r["id"] and s["day"]==d and logic.overlap(a,b,s["start_min"],s["end_min"]) for s in rows) for a,b,_ in logic.BLOCKS]
                } for d,_ in db.DAYS])
                # Three daily blocks, calculated from actual schedules and preferences.
                week.setMinimumHeight(44)
                v.addWidget(week)
                index=grid.count(); grid.addWidget(box,index//2,index%2)
            counts.append(n)
        self.summary.setText(f'{counts[0]} faculty and {counts[1]} classrooms available on {day}, {logic.fmt(start)} – {logic.fmt(end)}.')

    def update_availability(self):
        dialog=QDialog(self); dialog.setWindowTitle('Resource Availability'); layout=QVBoxLayout(dialog)
        layout.addWidget(label('Mark an unavailable time window. Existing windows can be cleared.'))
        resource=Combo()
        for kind,table in [('faculty','faculty'),('room','classrooms')]:
            for r in db.rows('SELECT id,name FROM '+table+' ORDER BY name'): resource.addItem(r['name'],(kind,r['id']))
        layout.addWidget(labeled('Resource',resource)); layout.addWidget(label('Uses the day and time selected on this page.','muted'))
        def save(clear=False):
            data=resource.currentData()
            if data is None: return
            start,end=self.start.currentData(),self.end.currentData()
            if not clear and end<=start:
                QMessageBox.warning(dialog,'Invalid time','End time must follow start time.'); return
            with db.conn:
                if clear: db.conn.execute('DELETE FROM unavailable WHERE kind=? AND resource_id=?',data)
                else: db.conn.execute('INSERT INTO unavailable(kind,resource_id,day,start_min,end_min) VALUES(?,?,?,?,?)',(*data,db.DAYS[self.day.currentIndex()][0],start,end))
            dialog.accept(); self.refresh()
        layout.addWidget(button('Mark unavailable','primary',lambda:save()))
        layout.addWidget(button('Clear all unavailable windows',slot=lambda:save(True)))
        dialog.exec_()
