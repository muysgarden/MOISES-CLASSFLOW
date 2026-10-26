from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget, QFrame,
)

import db
import logic
import importlib

from ui.placeholder import PlaceholderPage
from ui.academic import ENTITIES
from ui.widgets import Bar, label, set_kind

PAGE_CLASSES = {
    "academic": "AcademicPage", "availability": "AvailabilityPage", "schedules": "SchedulesPage",
    "validation": "ValidationPage", "reports": "ReportsPage",
}

NAV = [
    ("academic", "01", "Academic Data Management", "book"),
    ("availability", "02", "Faculty and Room Availability", "clock"),
    ("schedules", "03", "Schedule Management", "calendar"),
    ("validation", "04", "Conflict Detection and Validation", "check"),
    ("reports", "05", "Timetable Generation and Reports", "document"),
]


class SidebarIcon(QWidget):
    def __init__(self, kind, active=False, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.active = active
        self.setFixedSize(18, 18)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_active(self, active):
        if self.active != active:
            self.active = active
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#ffffff" if self.active else "#9aacca")
        pen = QPen(color, 1.45, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self.kind == "book":
            left = QPainterPath()
            left.moveTo(8.5, 4)
            left.cubicTo(6, 2.7, 3.6, 3.1, 2.5, 4.2)
            left.lineTo(2.5, 14.5)
            left.cubicTo(4.8, 13.4, 6.8, 13.6, 8.5, 15)
            right = QPainterPath()
            right.moveTo(9.5, 4)
            right.cubicTo(12, 2.7, 14.4, 3.1, 15.5, 4.2)
            right.lineTo(15.5, 14.5)
            right.cubicTo(13.2, 13.4, 11.2, 13.6, 9.5, 15)
            painter.drawPath(left)
            painter.drawPath(right)
            painter.drawLine(QPointF(9, 4), QPointF(9, 15))
        elif self.kind == "clock":
            painter.drawEllipse(QRectF(2.5, 2.5, 13, 13))
            painter.drawLine(QPointF(9, 5.2), QPointF(9, 9))
            painter.drawLine(QPointF(9, 9), QPointF(12, 10.7))
        elif self.kind == "calendar":
            painter.drawRoundedRect(QRectF(2.5, 4, 13, 11.5), 1.5, 1.5)
            painter.drawLine(QPointF(2.8, 7), QPointF(15.2, 7))
            painter.drawLine(QPointF(6, 2.5), QPointF(6, 5.5))
            painter.drawLine(QPointF(12, 2.5), QPointF(12, 5.5))
            painter.drawPoint(QPointF(6, 10))
            painter.drawPoint(QPointF(9, 10))
            painter.drawPoint(QPointF(12, 10))
        elif self.kind == "check":
            painter.drawEllipse(QRectF(2.5, 2.5, 13, 13))
            painter.drawPolyline(QPolygonF([QPointF(5.5, 9), QPointF(8, 11.5), QPointF(12.5, 6.8)]))
        else:
            page = QPainterPath()
            page.moveTo(4, 2.5)
            page.lineTo(10.8, 2.5)
            page.lineTo(14.5, 6.2)
            page.lineTo(14.5, 15.5)
            page.lineTo(4, 15.5)
            page.closeSubpath()
            painter.drawPath(page)
            painter.drawLine(QPointF(10.5, 2.8), QPointF(10.5, 6.5))
            painter.drawLine(QPointF(10.5, 6.5), QPointF(14.2, 6.5))
            painter.drawLine(QPointF(6.5, 9.5), QPointF(12, 9.5))
            painter.drawLine(QPointF(6.5, 12), QPointF(12, 12))


class BrandMark(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logo")
        self.setFixedSize(42, 42)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#ffffff"), 1.55, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        center = self.width() / 2
        painter.drawPolyline(QPolygonF([
            QPointF(center, 14), QPointF(center + 8, 18), QPointF(center, 22),
            QPointF(center - 8, 18), QPointF(center, 14),
        ]))
        painter.drawPolyline(QPolygonF([
            QPointF(center - 8, 21), QPointF(center, 25), QPointF(center + 8, 21),
        ]))
        painter.drawPolyline(QPolygonF([
            QPointF(center - 8, 25), QPointF(center, 29), QPointF(center + 8, 25),
        ]))


class NavButton(QPushButton):

    def __init__(self, num, text, icon):
        super().__init__()
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(58)
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 6, 9, 6)
        h.setSpacing(8)
        n = label(num, "navNum")
        n.setFixedWidth(20)
        self.icon = SidebarIcon(icon)
        t = label(text, wrap=True)
        self.chevron = label("›", "navChevron", align=Qt.AlignCenter)
        self.chevron.setFixedWidth(12)
        for w in (n, self.icon, t, self.chevron):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text = t
        self.toggled.connect(self._restyle)
        self._restyle(False)
        h.addWidget(n)
        h.addWidget(self.icon)
        h.addWidget(t, 1)
        h.addWidget(self.chevron)

    def _restyle(self, checked):
        f = self._text.font()
        f.setBold(bool(checked))
        self._text.setFont(f)
        self.icon.set_active(checked)
        self.chevron.setVisible(checked)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClassFlow — College of Computer Studies Scheduler")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 640)
        self._msg_token = 0

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self._build_topbar())
        self.msg = QLabel()
        self.msg.setObjectName("msg")
        self.msg.setWordWrap(True)
        self.msg.hide()
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(26, 12, 26, 0)
        wl.addWidget(self.msg)
        right.addWidget(wrap)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)
        self.setCentralWidget(central)

        self.pages = {}
        for key, num, title, _icon in NAV:
            self.pages[key] = self._make_page(key, num, title)
            self.stack.addWidget(self.pages[key])
        self.go("academic")

    def _make_page(self, key, num, title):
        try:
            module = importlib.import_module(f"ui.{key}")
        except ModuleNotFoundError as e:
            if e.name != f"ui.{key}":
                raise
            return PlaceholderPage(self, f"MODULE {num}", title)
        return getattr(module, PAGE_CLASSES[key])(self)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(214)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 30, 12, 14)
        v.setSpacing(7)

        brand = QHBoxLayout()
        brand.setContentsMargins(8, 2, 2, 25)
        brand.setSpacing(16)
        logo = BrandMark()
        brand.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("ClassFlow", "brandName"))
        col.addWidget(label("Academic Scheduler", "brandSub"))
        brand.addLayout(col)
        brand.addStretch()
        v.addLayout(brand)
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        v.addWidget(divider)
        v.addSpacing(22)
        lab = label("WORKSPACE MODULES", "navLabel")
        lab.setContentsMargins(10, 0, 0, 3)
        v.addWidget(lab)

        self.nav_group = QButtonGroup(self)
        self.nav_btns = {}
        for key, num, text, icon in NAV:
            b = NavButton(num, text, icon)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_btns[key] = b
            v.addWidget(b)
        v.addStretch()

        card = QFrame()
        card.setObjectName("progressCard")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(12, 10, 12, 10)
        cv.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(label("Scheduling progress"))
        self.progress_pct = label("0%", "progressPct")
        top.addStretch()
        top.addWidget(self.progress_pct)
        cv.addLayout(top)
        self.progress_bar = Bar(0)
        cv.addWidget(self.progress_bar)
        self.progress_term = label("", "brandSub")
        cv.addWidget(self.progress_term)
        v.addWidget(card)
        v.addSpacing(8)
        v.addWidget(label("Need help?", "helpTitle"))
        v.addWidget(label("View scheduling guide", "helpSub"))
        return side

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(0)
        left.addWidget(label("Classroom Scheduling & Academic Timetabling System", "topTitle"))
        h.addLayout(left)
        h.addStretch()
        self.term_combo = QComboBox()
        self.term_combo.setMinimumWidth(220)
        self.term_combo.currentIndexChanged.connect(self._term_changed)
        h.addWidget(self.term_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search schedules, faculty, rooms…")
        self.search.setFixedWidth(260)
        self.search.returnPressed.connect(self._global_search)
        h.addWidget(self.search)
        av = label("CS", "avatarTop", align=Qt.AlignCenter)
        av.setFixedSize(32, 32)
        h.addWidget(av)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addStretch()
        col.addWidget(label("College Secretary", "userName"))
        col.addWidget(label("Academic Office", "muted"))
        col.addStretch()
        h.addLayout(col)
        logout = QPushButton("Log out")
        logout.clicked.connect(self.logout)
        h.addWidget(logout)
        self.reload_terms()
        return bar

    def reload_terms(self, keep=None):
        keep = keep if keep is not None else self.term_combo.currentData()
        self.term_combo.blockSignals(True)
        self.term_combo.clear()
        for r in db.rows("SELECT id, name, is_current FROM terms ORDER BY id"):
            self.term_combo.addItem(r["name"], r["id"])
        idx = self.term_combo.findData(keep)
        if idx < 0:
            cur = db.row("SELECT id FROM terms WHERE is_current=1")
            idx = self.term_combo.findData(cur["id"]) if cur else 0
        self.term_combo.setCurrentIndex(max(idx, 0))
        self.term_combo.blockSignals(False)

    def term_id(self):
        tid = self.term_combo.currentData()
        if tid is None:  # brand-new empty database
            with db.conn:
                db.conn.execute("INSERT OR IGNORE INTO terms(name, is_current) VALUES('1st Semester, A.Y. 2025–2026', 1)")
            self.reload_terms()
            tid = self.term_combo.currentData()
        return tid

    def term_name(self):
        return self.term_combo.currentText()

    def _term_changed(self):
        self.refresh_current()

    def go(self, key, **kw):
        self.nav_btns[key].setChecked(True)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        if kw and hasattr(page, "open"):
            page.open(**kw)
        else:
            page.refresh()
        self.update_progress()

    def refresh_current(self):
        page = self.stack.currentWidget()
        if page is not None:
            page.refresh()
        self.update_progress()

    def data_changed(self):
        self.reload_terms()
        self.update_progress()

    def update_progress(self):
        if self.term_combo.currentData() is None:
            return
        pct = logic.progress(self.term_combo.currentData())
        self.progress_pct.setText(f"{pct}%")
        self.progress_bar.value = pct
        self.progress_bar.update()
        self.progress_term.setText(self.term_name())

    def _global_search(self):
        query = self.search.text().strip()
        if not query:
            return

        schedules = self.pages["schedules"]
        if hasattr(schedules, "search_all"):
            self.go("schedules")
            schedules.search_all(query)
            return

        normalized = query.casefold()
        search_order = ("classrooms", "faculty", "sections", "subjects", "programs", "terms", "periods")
        target = "subjects"
        for key in search_order:
            ent = ENTITIES[key]
            if any(
                normalized in str(value).casefold()
                for row in db.rows(ent["sql"])
                for value in tuple(row)[1:]
            ):
                target = key
                break

        self.go("academic")
        page = self.pages["academic"]
        page.set_tab(target)
        page.search.setText(query)

    def notify(self, text, kind="success"):
        self.msg.setText(text)
        set_kind(self.msg, kind)
        self.msg.show()
        self._msg_token += 1
        token = self._msg_token
        QTimer.singleShot(6000, lambda: self.msg.hide() if token == self._msg_token else None)

    def logout(self):
        from ui.login import LoginDialog
        from PyQt5.QtWidgets import QDialog
        self.hide()
        if LoginDialog().exec_() == QDialog.Accepted:
            self.show()
        else:
            self.close()
