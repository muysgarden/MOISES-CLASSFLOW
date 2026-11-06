"""Module 4: explain conflicts and link directly to the affected assignment."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QSizePolicy

import logic
from ui.widgets import (
    Page, Card, button, label, make_table, text_item, fit_table,
)

PRIORITY_COLORS = {
    logic.CRITICAL: ("#B42336", "#FFF0F2", "#F4B1BC"),
    logic.WARNING: ("#AA6206", "#FFF5E5", "#F5D39B"),
    logic.REVIEW: ("#3157AE", "#EDF4FF", "#B7CEF8"),
}

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

NEXT_STEPS = {
    "Faculty Conflict": "Change the time or assigned faculty in Class Schedules.",
    "Classroom Conflict": "Move one class to an available room or time.",
    "Section Conflict": "Move one class to a different time for this section.",
    "Unavailable Resource": "Choose another time, room, or faculty member.",
    "Capacity Problem": "Assign a room that can accommodate the section.",
    "Teaching-Load Issue": "Reassign a class to a faculty member with available load.",
    "Invalid Time": "Adjust the class start or end time.",
    "Course Mismatch": "Select a subject offered by the section's course.",
}


class PriorityCard(Card):
    clicked = pyqtSignal(str)

    def __init__(self, severity):
        super().__init__()
        self.severity = severity
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("priorityCard")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.severity)
        super().mouseReleaseEvent(event)


class ValidationPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.setObjectName("validationPage")
        self.active_priority = None
        self.add_header(
            "MODULE 04", "Conflict Checks",
            "See which classes overlap, why they need attention, and where to edit them.",
            [button("↻  Check Schedules", "primary", self.refresh)],
        )
        overview = QHBoxLayout()
        overview.setSpacing(12)
        self.lay.addLayout(overview)
        self.counts = {}
        self.priority_cards = {}
        for severity, title, hint, accent in (
            (logic.CRITICAL, "Critical", "Overlaps and blocked resources", "#B42336"),
            (logic.WARNING, "Warning", "Capacity and teaching-load concerns", "#AA6206"),
            (logic.REVIEW, "Review", "Time-window exceptions", "#3157AE"),
        ):
            card = PriorityCard(severity)
            card.clicked.connect(self.toggle_priority)
            self.priority_cards[severity] = card
            body = card.body(margins=(18, 17, 18, 17), spacing=5)
            heading = label(title, "cardTitle")
            heading.setAttribute(Qt.WA_TransparentForMouseEvents)
            body.addWidget(heading)
            count = QLabel("0")
            count.setStyleSheet(f"color: {accent}; font-size: 30px; font-weight: 750;")
            count.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.counts[severity] = count
            body.addWidget(count)
            subtitle = label(hint, "muted", wrap=True)
            subtitle.setAttribute(Qt.WA_TransparentForMouseEvents)
            body.addWidget(subtitle)
            body.parentWidget().setAttribute(Qt.WA_TransparentForMouseEvents)
            overview.addWidget(card)

        self.results = Card(
            "Issues to Review", "Click a colored card above to filter by priority",
        )
        self.results.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.lay.addWidget(self.results)
        self.table = make_table(
            ["Priority", "Problem", "Affected Class", "What happened"],
            row_h=60, fixed={0: 90}, flex={1: 2, 2: 2, 3: 5},
        )
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellClicked.connect(self.select_issue)
        self.results.add(self.table)
        self.empty = QLabel("No issues match these filters.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color: #64748B; padding: 18px;")
        self.results.add(self.empty)
        self.detail = Card("Selected Conflict", "Choose an issue above to view its details")
        self.detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.detail_body = self.detail.body(margins=(18, 8, 18, 16), spacing=7)
        self.detail_title = QLabel("No conflict selected")
        self.detail_title.setStyleSheet("font-size: 15px; font-weight: 750; color: #1B3155;")
        self.detail_body.addWidget(self.detail_title)
        self.detail_description = QLabel()
        self.detail_description.setWordWrap(True)
        self.detail_description.setStyleSheet("color: #334765; font-size: 13px;")
        self.detail_body.addWidget(self.detail_description)
        self.detail_hint = QLabel()
        self.detail_hint.setWordWrap(True)
        self.detail_hint.setStyleSheet("color: #64748B; font-size: 12px;")
        self.detail_body.addWidget(self.detail_hint)
        self.view_button = button("View in Schedules", "primary", self.view_selected)
        self.detail_body.addWidget(self.view_button, alignment=Qt.AlignRight)
        self.lay.addWidget(self.detail)
        self.selected_issue = None
        self.lay.addStretch()
        self.finish()

    def toggle_priority(self, severity):
        self.active_priority = None if self.active_priority == severity else severity
        self.render()

    def select_issue(self, row, _col=0):
        if not 0 <= row < len(self.visible_issues):
            return
        issue = self.visible_issues[row]
        self.selected_issue = issue
        self.table.selectRow(row)
        self.detail_title.setText(f"{issue['type']} · {issue['label']}")
        self.detail_description.setText(issue["desc"])
        self.detail_hint.setText(NEXT_STEPS.get(issue["type"], "Review the assignment in Class Schedules."))
        self.detail.subtitle.setText("Review what happened and decide whether to edit the assignment")
        self.detail.show()

    def view_selected(self):
        if self.selected_issue:
            self.win.go("schedules", edit_ids=self.selected_issue["edit_ids"])

    def refresh(self):
        self.result = logic.validate_term(self.win.term_id())
        for severity, count in self.counts.items():
            count.setText(str(sum(
                issue["severity"] == severity for issue in self.result["issues"]
            )))
        self.render()

    def render(self, *_):
        if not hasattr(self, "result"):
            return
        issues = [
            issue for issue in self.result["issues"]
            if self.active_priority is None or issue["severity"] == self.active_priority
        ]
        self.visible_issues = issues
        for severity, card in self.priority_cards.items():
            active = self.active_priority == severity
            foreground, background, outline = PRIORITY_COLORS[severity]
            card.setStyleSheet(
                f"QFrame#priorityCard {{border: {2 if active else 1}px solid {outline}; "
                f"background: {background if active else '#FFFFFF'}; border-radius: 12px;}}"
            )
        self.results.subtitle.setText(
            f"Showing {len(issues)} of {len(self.result['issues'])} issues · Click a row for details"
        )
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for col, value in enumerate((issue["severity"], issue["type"], issue["label"])):
                item = text_item(value, bold=col == 1)
                if col == 0:
                    foreground, background, _ = PRIORITY_COLORS[issue["severity"]]
                    item.setForeground(QColor(foreground))
                    item.setBackground(QColor(background))
                item.setToolTip(
                    EXPLANATIONS.get(issue["type"], "") if col == 1 else value
                )
                self.table.setItem(row, col, item)
            description = QLabel(issue["desc"])
            description.setWordWrap(True)
            description.setContentsMargins(8, 4, 10, 4)
            description.setStyleSheet("color: #283955; font-size: 12px;")
            description.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.table.setCellWidget(row, 3, description)
        fit_table(self.table)
        self.table.setVisible(bool(issues))
        self.empty.setVisible(not issues)
        self.selected_issue = None
        self.detail.hide()
        if issues:
            self.select_issue(0)
