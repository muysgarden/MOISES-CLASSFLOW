"""A calm, data-driven ClassFlow home page.

Dashboard figures are queried from SQLite on refresh; no illustrative numbers,
timestamps, or activity events are presented as live data.
"""

from PyQt5.QtCore import Qt, QDateTime, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import db
import logic


class GradientTitle(QWidget):
    """Paint crisp gradient text without relying on unsupported QSS text gradients."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setMinimumHeight(55)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Segoe UI", 29, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        baseline = (self.height() + metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(0, baseline, font, self.title)
        gradient = QLinearGradient(0, 0, max(300, metrics.horizontalAdvance(self.title)), 0)
        gradient.setColorAt(0, QColor("#2D6DE0"))
        gradient.setColorAt(0.53, QColor("#8F43E5"))
        gradient.setColorAt(1, QColor("#EE8F28"))
        painter.fillPath(path, QBrush(gradient))


def text(value, role=None):
    widget = QLabel(value)
    if role:
        widget.setObjectName(role)
    return widget


class DashboardPage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("dashboardPage")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        canvas = QWidget()
        canvas.setObjectName("dashboardCanvas")
        self.setWidget(canvas)
        body = QVBoxLayout(canvas)
        body.setContentsMargins(30, 25, 30, 32)
        body.setSpacing(21)

        welcome = QHBoxLayout()
        headline = QVBoxLayout()
        headline.setSpacing(2)
        headline.addWidget(GradientTitle("Welcome to ClassFlow"))
        headline.addWidget(text("Your academic scheduling workspace, at a glance.", "dashSub"))
        welcome.addLayout(headline, 1)
        right = QVBoxLayout()
        right.setSpacing(5)
        self.clock = text("", "dashClock")
        self.clock.setAlignment(Qt.AlignRight)
        right.addWidget(self.clock)
        self.term_label = text("", "dashSub")
        self.term_label.setAlignment(Qt.AlignRight)
        right.addWidget(self.term_label)
        welcome.addLayout(right)
        body.addLayout(welcome)

        metrics = QGridLayout()
        metrics.setSpacing(16)
        self.metrics = {}
        specs = [
            ("programs", "Academic programs", "PG", "blue", "Programs in your records"),
            ("sections", "Sections", "SE", "purple", "Student sections"),
            ("faculty", "Faculty members", "FA", "orange", "Teaching personnel"),
            ("rooms", "Classrooms", "RM", "green", "Teaching spaces"),
            ("assignments", "Scheduled classes", "SC", "sky", "This academic term"),
            ("conflicts", "Critical conflicts", "!", "orange", "Need scheduling attention"),
        ]
        for i, (key, title, mark, tone, subtitle) in enumerate(specs):
            card = self._metric(title, mark, tone, subtitle)
            self.metrics[key] = card.findChild(QLabel, "metricValue")
            metrics.addWidget(card, i // 3, i % 3)
            metrics.setColumnStretch(i % 3, 1)
        body.addLayout(metrics)

        lower = QHBoxLayout()
        lower.setSpacing(18)
        actions = QVBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(text("Quick actions", "dashSection"))
        actions.addWidget(text("Jump straight to common tasks.", "dashSub"))
        action_grid = QGridLayout()
        action_grid.setSpacing(12)
        shortcuts = [
            ("Manage records", "Programs, subjects, faculty", "blue", "+", lambda: self.win.go("academic")),
            ("Create schedule", "Assign class times and rooms", "purple", "▦", lambda: self.win.go("schedules")),
            ("Check availability", "Find free rooms and faculty", "green", "◷", lambda: self.win.go("availability")),
            ("Review conflicts", "See issues to resolve", "orange", "!", lambda: self.win.go("validation")),
        ]
        for i, (title, sub, tone, symbol, action) in enumerate(shortcuts):
            button = QPushButton()
            button.setObjectName("quickAction")
            button.setProperty("tone", tone)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(78)
            button.clicked.connect(action)
            inner = QHBoxLayout(button)
            inner.setContentsMargins(13, 10, 12, 10)
            inner.setSpacing(10)
            mark = text(symbol, "quickIcon")
            mark.setProperty("tone", tone)
            mark.setAlignment(Qt.AlignCenter)
            mark.setFixedSize(35, 35)
            inner.addWidget(mark)
            caption = QVBoxLayout()
            caption.setSpacing(2)
            caption.addWidget(text(title, "quickTitle"))
            caption.addWidget(text(sub, "quickSub"))
            inner.addLayout(caption, 1)
            for child in button.findChildren(QLabel):
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
            action_grid.addWidget(button, i // 2, i % 2)
        actions.addLayout(action_grid)
        actions.addStretch()
        lower.addLayout(actions, 1)

        saved = QVBoxLayout()
        saved.setSpacing(12)
        saved.addWidget(text("Saved schedules", "dashSection"))
        saved.addWidget(text("Latest assignments in the selected term.", "dashSub"))
        self.saved_rows = QVBoxLayout()
        self.saved_rows.setSpacing(9)
        saved.addLayout(self.saved_rows)
        saved.addStretch()
        lower.addLayout(saved, 1)
        body.addLayout(lower)

        health = QFrame()
        health.setObjectName("healthBanner")
        health_body = QVBoxLayout(health)
        health_body.setContentsMargins(24, 19, 24, 20)
        health_body.setSpacing(9)
        health_head = QHBoxLayout()
        health_head.addWidget(text("Scheduling overview", "healthTitle"))
        health_head.addStretch()
        self.health_status = text("", "healthStatus")
        health_head.addWidget(self.health_status)
        health_body.addLayout(health_head)
        self.health_summary = text("", "healthSummary")
        self.health_summary.setWordWrap(True)
        health_body.addWidget(self.health_summary)
        self.progress = QProgressBar()
        self.progress.setObjectName("healthProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setRange(0, 100)
        health_body.addWidget(self.progress)
        body.addWidget(health)
        body.addStretch()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(60000)
        self._update_clock()

    def _metric(self, title, mark, tone, subtitle):
        card = QFrame()
        card.setObjectName("metricCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(28, 48, 88, 36))
        card.setGraphicsEffect(shadow)
        card.setMinimumHeight(132)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(19, 16, 18, 16)
        layout.setSpacing(5)
        top = QHBoxLayout()
        top.addWidget(text(title, "metricTitle"))
        top.addStretch()
        chip = text(mark, "metricIcon")
        chip.setProperty("tone", tone)
        chip.setAlignment(Qt.AlignCenter)
        chip.setFixedSize(36, 36)
        top.addWidget(chip)
        layout.addLayout(top)
        value = text("0", "metricValue")
        layout.addWidget(value)
        layout.addWidget(text(subtitle, "metricNote"))
        return card

    def _update_clock(self):
        self.clock.setText(QDateTime.currentDateTime().toString("ddd, MMM d, yyyy · h:mm AP"))

    def refresh(self):
        self._update_clock()
        term_id = self.win.term_id()
        self.term_label.setText(self.win.term_name())
        counts = {
            "programs": db.row("SELECT COUNT(*) FROM programs")[0],
            "sections": db.row("SELECT COUNT(*) FROM sections")[0],
            "faculty": db.row("SELECT COUNT(*) FROM faculty")[0],
            "rooms": db.row("SELECT COUNT(*) FROM classrooms")[0],
        }
        groups = logic.group_rows(logic.schedule_rows(term_id))
        validation = logic.validate_term(term_id)
        counts["assignments"] = len(groups)
        counts["conflicts"] = validation["critical"]
        for key, value in counts.items():
            self.metrics[key].setText(f"{value:,}")

        while self.saved_rows.count():
            item = self.saved_rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        # A schedule has no creation timestamp in this schema. Show the
        # newest saved assignment IDs, not invented "recent activity" events.
        recent = sorted(groups, key=lambda group: max(group["ids"]), reverse=True)[:4]
        if not recent:
            empty = text("No schedules yet. Create one to see it here.", "dashEmpty")
            empty.setWordWrap(True)
            self.saved_rows.addWidget(empty)
        for group in recent:
            row = QPushButton()
            row.setObjectName("recentRow")
            row.setCursor(Qt.PointingHandCursor)
            inside = QHBoxLayout(row)
            inside.setContentsMargins(15, 8, 12, 8)
            inside.setSpacing(9)
            dot = text("●", "recentDot")
            inside.addWidget(dot)
            summary = QVBoxLayout()
            summary.setSpacing(2)
            summary.addWidget(text(f"{group['code']}  ·  {group['section']}", "recentTitle"))
            summary.addWidget(text(f"{group['days_label']}  ·  {group['time_label']}", "recentSub"))
            inside.addLayout(summary, 1)
            inside.addWidget(text("›", "recentArrow"))
            for child in row.findChildren(QLabel):
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
            ids = list(group["ids"])
            row.clicked.connect(lambda _=False, ids=ids: self.win.go("schedules", edit_ids=ids))
            row.setMinimumHeight(56)
            self.saved_rows.addWidget(row)

        pct = logic.progress(term_id)
        self.progress.setValue(pct)
        required = db.row(
            "SELECT COUNT(*) FROM sections sec "
            "JOIN subject_programs sp ON sp.program_id = sec.program_id"
        )[0]
        completed = db.row(
            "SELECT COUNT(*) FROM (SELECT DISTINCT section_id, subject_id "
            "FROM schedules WHERE term_id=?)", (term_id,)
        )[0]
        used_rooms = db.row(
            "SELECT COUNT(DISTINCT room_id) FROM schedules WHERE term_id=?", (term_id,)
        )[0]
        self.health_status.setText(
            "Needs attention" if validation["critical"] else "No critical conflicts"
        )
        self.health_summary.setText(
            f"{completed} of {required} required class assignments scheduled ({pct}%)  ·  "
            f"{used_rooms} of {counts['rooms']} rooms in use  ·  "
            f"{validation['critical']} critical conflicts"
        )
