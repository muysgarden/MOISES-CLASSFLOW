from PyQt5.QtWidgets import QHBoxLayout, QWidget
from ui.widgets import Page, Card, Combo, Banner, button, label, make_table, text_item, fit_table, widget_cell
import logic


class ValidationPage(Page):
    def __init__(self,win):
        super().__init__(win)
        self.add_header('MODULE 04','Conflict Detection and Validation','Automatically identify scheduling conflicts, capacity concerns, and policy violations.',[button('✓  Run Validation','primary',self.refresh)])
        row=QHBoxLayout(); self.lay.addLayout(row); self.counts={}
        for key,title in logic.CARD_TYPES:
            card=Card(); v=card.body(margins=(16,16,16,16)); v.addWidget(label(title,'muted')); count=label('0','big'); self.counts[key]=count; v.addWidget(count); v.addWidget(label('Detected issues','muted')); row.addWidget(card)
        self.severity=Combo(); self.severity.addItems(['All severities','Critical','Warning','Review']); self.severity.currentIndexChanged.connect(self.render)
        self.kind=Combo(); self.kind.addItem('All issue types'); self.kind.addItems([k for k,_ in logic.CARD_TYPES]); self.kind.addItem('Unavailable Resource'); self.kind.currentIndexChanged.connect(self.render)
        card=Card('Validation Results','Live checks across saved assignments',right=[self.severity,self.kind]); self.lay.addWidget(card)
        self.banner=Banner(); card.body().addWidget(self.banner)
        self.table=make_table(['Issue Type','Affected Schedule','Description','Severity','Actions'],flex={0:2,1:2,2:5,3:1,4:1}); card.add(self.table); self.finish()

    def refresh(self):
        self.result=logic.validate_term(self.win.term_id())
        for key,w in self.counts.items(): w.setText(str(self.result['counts'].get(key,0)))
        self.banner.title.setText('Schedule is not ready for publishing' if self.result['critical'] else 'No critical scheduling conflicts')
        self.banner.text.setText(f'{len(self.result["issues"])} issues across {self.result["total"]} assignments · Validation score {self.result["score"]}%'); self.banner.text.show()
        from ui.widgets import set_kind
        set_kind(self.banner,'bad' if self.result['critical'] else 'good')
        self.render()

    def render(self):
        if not hasattr(self,'result'): return
        issues=[i for i in self.result['issues'] if (self.severity.currentIndex()==0 or i['severity']==self.severity.currentText()) and (self.kind.currentIndex()==0 or i['type']==self.kind.currentText())]
        self.table.setRowCount(len(issues))
        for n,i in enumerate(issues):
            for col,text in enumerate([i['type'],i['label'],i['desc'],i['severity']]): self.table.setItem(n,col,text_item(text,bold=col==0))
            widget_cell(self.table,n,4,button('Resolve','smallPrimary',lambda _,issue=i:self.win.go('schedules',edit_ids=issue['edit_ids'])))
        fit_table(self.table)
