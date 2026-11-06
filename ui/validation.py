"""Module 4: explain conflicts and link directly to the affected assignment."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy

import db
import logic
from ui.widgets import (
    Page, Card, Combo, Banner, button, label, make_table, text_item,
    fit_table, widget_cell, set_kind,
)

EXPLANATIONS = {
    "Faculty Conflict": "One faculty member has overlapping classes.",
    "Classroom Conflict": "Two classes need the same room at the same time.",
    "Section Conflict": "One section has overlapping classes.",
    "Unavailable Resource": "A class uses a faculty member or room during a blocked time.",
    "Capacity Problem": "The classroom has fewer seats than enrolled students.",
    "Teaching-Load Issue": "A faculty member is assigned more units than allowed.",
    "Invalid Time": "The class time is invalid or outside the school period.",
    "Course Mismatch": "The subject is not part of the section's course.",
}


class ValidationPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.setObjectName("validationPage")
        self.setStyleSheet("""
            #validationPage QComboBox {
                background: white; border: 1px solid #DDE6F4;
                border-radius: 8px; padding: 8px 10px; min-height: 28px;
            }
        """)
        self.add_header(
            "MODULE 04", "Conflict Checks",
            "See which classes overlap, why they need attention, and where to edit them.",
            [button("↻  Check Schedules", "primary", self.refresh)],
        )
        overview = QHBoxLayout()
        overview.setSpacing(12)
        self.lay.addLayout(overview)
        self.counts = {}
        for severity, title, hint, accent in (
            (logic.CRITICAL, "Needs fixing", "Conflicts that block a valid timetable", "#C53D48"),
            (logic.WARNING, "Warnings", "Capacity and teaching-load concerns", "#D28620"),
            (logic.REVIEW, "Review", "Check exceptions to the school period", "#4264B8"),
        ):
            card = Card()
            body = card.body(margins=(18, 17, 18, 17), spacing=5)
            body.addWidget(label(title, "cardTitle"))
            count = QLabel("0")
            count.setStyleSheet(f"color: {accent}; font-size: 30px; font-weight: 750;")
            self.counts[severity] = count
            body.addWidget(count)
            body.addWidget(label(hint, "muted", wrap=True))
            overview.addWidget(card)

        self.severity = Combo()
        self.severity.addItems(["All priorities", logic.CRITICAL, logic.WARNING, logic.REVIEW])
        self.severity.setMinimumWidth(155)
        self.severity.currentIndexChanged.connect(self.render)
        self.section = Combo()
        self.section.addItem("All sections", None)
        self.section.setMinimumWidth(155)
        self.section.currentIndexChanged.connect(self.render)
        self.kind = Combo()
        self.kind.addItem("All issue types", None)
        for name in EXPLANATIONS:
            self.kind.addItem(name, name)
        self.kind.setMinimumWidth(180)
        self.kind.currentIndexChanged.connect(self.render)
        self.results = Card(
            "Issues to Review", "Filter to find the classes that need attention",
            right=[self.section, self.severity, self.kind],
        )
        self.results.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.lay.addWidget(self.results)
        self.banner = Banner("good", "No scheduling conflicts found.")
        self.results.body(margins=(16, 10, 16, 12)).addWidget(self.banner)
        self.table = make_table(
            ["Priority", "Problem", "Affected Class", "What happened", "Action"],
            row_h=66, fixed={0: 90, 4: 100}, flex={1: 2, 2: 2, 3: 5},
        )
        self.results.add(self.table)
        self.empty = QLabel("No issues match these filters.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color: #64748B; padding: 18px;")
        self.results.add(self.empty)
        self.lay.addStretch()
        self.finish()

    def refresh(self):
        self.result = logic.validate_term(self.win.term_id())
        for severity, count in self.counts.items():
            count.setText(str(sum(
                issue["severity"] == severity for issue in self.result["issues"]
            )))
        selected = self.section.currentData()
        self.section.blockSignals(True)
        self.section.clear()
        self.section.addItem("All sections", None)
        for record in db.rows("SELECT id, name FROM sections ORDER BY name"):
            self.section.addItem(record["name"], record["id"])
        self.section.setCurrentIndex(max(0, self.section.findData(selected)))
        self.section.blockSignals(False)
        self.render()

    def render(self, *_):
        if not hasattr(self, "result"):
            return
        issues = [
            issue for issue in self.result["issues"]
            if (self.section.currentData() is None
                or issue["section_id"] == self.section.currentData())
            and (self.severity.currentIndex() == 0
                 or issue["severity"] == self.severity.currentText())
            and (self.kind.currentData() is None
                 or issue["type"] == self.kind.currentData())
        ]
        if not self.result["issues"]:
            self.banner.title.setText("No scheduling issues detected")
            self.banner.text.setText("Saved assignments passed the current checks.")
            set_kind(self.banner, "good")
        elif self.result["critical"]:
            self.banner.title.setText(f"{self.result['critical']} critical issue(s) need attention")
            self.banner.text.setText(
                "Fix overlapping assignments or blocked resources before finalizing. "
                "Select Edit to review a record."
            )
            set_kind(self.banner, "bad")
        else:
            self.banner.title.setText("No critical conflicts — review remaining warnings")
            self.banner.text.setText(
                "Check capacity, teaching load, and schedule exceptions before finalizing."
            )
            set_kind(self.banner, "warn")
        self.banner.text.show()
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for col, value in enumerate((
                issue["severity"], issue["type"], issue["label"]
            )):
                item = text_item(value, bold=col == 1)
                item.setToolTip(
                    EXPLANATIONS.get(issue["type"], "") if col == 1 else value
                )
                self.table.setItem(row, col, item)
            description = QLabel(issue["desc"])
            description.setWordWrap(True)
            description.setContentsMargins(8, 4, 10, 4)
            description.setStyleSheet("color: #283955; font-size: 12px;")
            self.table.setCellWidget(row, 3, description)
            widget_cell(
                self.table, row, 4,
                button("Edit", "smallPrimary",
                       lambda _=False, ids=issue["edit_ids"]:
                       self.win.go("schedules", edit_ids=ids)),
            )
        fit_table(self.table)
        self.table.setVisible(bool(issues))
        self.empty.setVisible(not issues)
