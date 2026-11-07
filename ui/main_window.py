from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, QStringListModel
from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QButtonGroup, QComboBox, QCompleter, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget, QFrame, QSizePolicy, QShortcut,
)

import db
import logic
import importlib

from ui.placeholder import PlaceholderPage
from ui.academic import ENTITIES
from ui.widgets import label, set_kind
from ui.dashboard import DashboardPage
from ui.profile import AccountSettingsPage

PAGE_CLASSES = {
    "academic": "AcademicPage", "availability": "AvailabilityPage", "schedules": "SchedulesPage",
    "validation": "ValidationPage", "reports": "ReportsPage",
}

NAV = [
    ("dashboard", "", "Dashboard", "home"),
    ("academic", "01", "Academic Records", "book"),
    ("availability", "02", "Availability", "clock"),
    ("schedules", "03", "Class Schedules", "calendar"),
    ("validation", "04", "Conflict Checks", "check"),
    ("reports", "05", "Reports & Timetables", "document"),
]

PAGE_DESCRIPTIONS = {
    "dashboard": "Your scheduling workspace at a glance",
    "academic": "Manage the school's academic records",
    "availability": "Faculty and classroom availability",
    "schedules": "Assign classes to rooms and time slots",
    "validation": "Review and resolve scheduling conflicts",
    "reports": "View and export academic timetables",
    "settings": "Manage your administrator account",
}


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
        color = QColor("#ffffff" if self.active else "#5F6D83")
        pen = QPen(color, 1.45, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self.kind == "home":
            roof = QPainterPath()
            roof.moveTo(2.5, 8)
            roof.lineTo(9, 2.8)
            roof.lineTo(15.5, 8)
            painter.drawPath(roof)
            painter.drawRoundedRect(QRectF(4.6, 7.5, 8.8, 8), 1.2, 1.2)
            painter.drawLine(QPointF(9, 15), QPointF(9, 11))
        elif self.kind == "book":
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
        self.setMinimumHeight(48)
        h = QHBoxLayout(self)
        h.setContentsMargins(15, 5, 11, 5)
        h.setSpacing(12)
        self.icon = SidebarIcon(icon)
        t = label(text)
        for w in (self.icon, t):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text = t
        self.toggled.connect(self._restyle)
        self._restyle(False)
        h.addWidget(self.icon)
        h.addWidget(t, 1)

    def _restyle(self, checked):
        f = self._text.font()
        f.setBold(bool(checked))
        self._text.setFont(f)
        # In Qt, descendant labels inside a checkable QPushButton can retain
        # the checked-state QSS palette even after their parent is unchecked.
        self._text.setStyleSheet("color: #FFFFFF;" if checked else "color: #52627A;")
        self.icon.set_active(checked)


class MainWindow(QMainWindow):
    def __init__(self, username="Administrator"):
        super().__init__()
        self.username = username
        self.setWindowTitle("ClassFlow — College of Computer Studies Scheduler")
        self.resize(1440, 860)
        self.setMinimumSize(860, 560)
        self._msg_token = 0

        central = QWidget()
        central.setObjectName("workspace")
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
        self.pages["settings"] = AccountSettingsPage(self.username, self)
        self.pages["settings"].username_changed.connect(self._update_account_name)
        self.stack.addWidget(self.pages["settings"])
        self.go("dashboard")

    def _make_page(self, key, num, title):
        if key == "dashboard":
            return DashboardPage(self)
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
        side.setFixedWidth(218)
        v = QVBoxLayout(side)
        v.setContentsMargins(15, 22, 15, 16)
        v.setSpacing(9)

        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 2, 19)
        brand.setSpacing(12)
        logo = BrandMark()
        brand.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("ClassFlow", "brandName"))
        col.addWidget(label("ACADEMIC SCHEDULING", "brandSub"))
        brand.addLayout(col)
        brand.addStretch()
        v.addLayout(brand)
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        v.addWidget(divider)
        v.addSpacing(13)

        self.nav_group = QButtonGroup(self)
        # Settings is a workspace page but not one of the six module tabs.
        # Allow all module buttons to be unselected while it is open.
        self.nav_group.setExclusive(False)
        self.nav_btns = {}
        for key, num, text, icon in NAV:
            if key == "dashboard":
                lab = label("OVERVIEW", "navLabel")
                lab.setContentsMargins(13, 0, 0, 1)
                v.addWidget(lab)
            elif key == "academic":
                v.addSpacing(16)
                lab = label("WORKSPACE", "navLabel")
                lab.setContentsMargins(13, 0, 0, 1)
                v.addWidget(lab)
            b = NavButton(num, text, icon)
            b.setToolTip(PAGE_DESCRIPTIONS[key])
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_btns[key] = b
            v.addWidget(b)
        v.addStretch()

        self.profile_trigger = QPushButton()
        self.profile_trigger.setObjectName("profileTrigger")
        self.profile_trigger.setToolTip("Open administrator profile and settings")
        self.profile_trigger.setCursor(Qt.PointingHandCursor)
        self.profile_trigger.setFixedHeight(64)
        self.profile_trigger.clicked.connect(self.open_profile)
        profile = QHBoxLayout(self.profile_trigger)
        profile.setContentsMargins(9, 10, 9, 10)
        profile.setSpacing(10)
        self.profile_initial = label(self.username[:1].upper() or "A", "avatarTop", align=Qt.AlignCenter)
        self.profile_initial.setFixedSize(35, 35)
        profile.addWidget(self.profile_initial)
        who = QVBoxLayout()
        who.setSpacing(0)
        self.profile_name = label(self.username, "userName")
        who.addWidget(self.profile_name)
        who.addWidget(label("Administrator", "muted"))
        profile.addLayout(who, 1)
        profile.addWidget(label("›", "profileChevron"))
        for child in self.profile_trigger.findChildren(QLabel):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)
        v.addWidget(self.profile_trigger)
        self.logout_button = QPushButton("↪   Log out")
        self.logout_button.setObjectName("sidebarLogout")
        self.logout_button.setCursor(Qt.PointingHandCursor)
        self.logout_button.setMinimumHeight(39)
        self.logout_button.clicked.connect(self.logout)
        v.addWidget(self.logout_button)
        return side

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        # The active page already has its own title: leave the left side
        # intentionally open and keep only useful global controls here.
        bar.setFixedHeight(66)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(12)
        self.page_title = label("Dashboard", "topTitle")
        self.page_context = label(PAGE_DESCRIPTIONS["dashboard"], "topContext")
        self.page_title.hide()
        self.page_context.hide()
        h.addStretch(1)
        self.search = QLineEdit()
        self.search.setObjectName("globalSearch")
        self.search.setPlaceholderText("⌕  Search subjects, faculty, rooms, schedules…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(160)
        self.search.setMaximumWidth(365)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search.returnPressed.connect(self._global_search)
        self.search_model = QStringListModel(self)
        self.search_completer = QCompleter(self.search_model, self)
        self.search_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_completer.setFilterMode(Qt.MatchContains)
        self.search_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.search_completer.setMaxVisibleItems(9)
        self.search_completer.activated[str].connect(self._open_suggestion)
        self.search.setCompleter(self.search_completer)
        self.search.textEdited.connect(self._update_suggestions)
        self._suggestion_targets = {}
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.search_shortcut.activated.connect(self._focus_search)
        h.addWidget(self.search)
        self.term_combo = QComboBox()
        self.term_combo.setObjectName("termSelector")
        self.term_combo.setMinimumWidth(155)
        self.term_combo.setMaximumWidth(240)
        self.term_combo.setToolTip("Active academic term")
        self.term_combo.currentIndexChanged.connect(self._term_changed)
        h.addWidget(self.term_combo)
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
        for name, button in self.nav_btns.items():
            button.setChecked(name == key)
        self.page_title.setText(next((title for k, _, title, _ in NAV if k == key), "Settings" if key == "settings" else "ClassFlow"))
        self.page_context.setText(PAGE_DESCRIPTIONS[key])
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        if key == "settings":
            page.prepare(self.username)
        elif kw and hasattr(page, "open"):
            page.open(**kw)
        else:
            page.refresh()

    def refresh_current(self):
        page = self.stack.currentWidget()
        if page is not None:
            page.refresh()

    def data_changed(self):
        self.reload_terms()
        self.pages["dashboard"].refresh()

    def _global_search(self):
        query = self.search.text().strip()
        if not query:
            return
        # Enter opens the best matching result; selecting from the suggestion
        # list opens that exact record. Never default to an unrelated page.
        matches = self._search_results(query)
        if matches:
            self._route_target(matches[0][1])
        else:
            self.notify(f"No records found for “{query}”. Try another search.", "warning")

    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _search_results(self, query):
        needle = query.strip().casefold()
        if not needle:
            return []
        matches = []

        for group in logic.group_rows(logic.schedule_rows(self.term_id())):
            values = (group["code"], group["section"], group["faculty"],
                      group["room"], group["days_label"], group["time_label"])
            if any(needle in str(value).casefold() for value in values):
                title = f"Schedule · {group['code']} — {group['section']} ({group['days_label']})"
                matches.append((title, ("schedule", tuple(group["ids"]))))

        for key in ("subjects", "faculty", "classrooms", "sections", "programs", "terms", "periods"):
            entity = ENTITIES[key]
            for record in db.rows(entity["sql"]):
                values = tuple(record)[1:]
                if any(needle in str(value).casefold() for value in values):
                    title = str(values[0])
                    if key == "subjects" and len(values) > 1:
                        title += f" — {values[1]}"
                    matches.append((f"{entity['singular']} · {title}", ("academic", key, record["id"])))
        return matches[:18]

    def _update_suggestions(self, query):
        matches = self._search_results(query) if query.strip() else []
        self._suggestion_targets = {text: target for text, target in matches}
        self.search_model.setStringList([text for text, _ in matches])
        if matches and self.search.hasFocus():
            self.search_completer.setCompletionPrefix(query)
            self.search_completer.complete()
        else:
            self.search_completer.popup().hide()

    def _open_suggestion(self, text):
        target = self._suggestion_targets.get(text)
        if target:
            self._route_target(target)

    def _route_target(self, target):
        if target[0] == "schedule":
            self.go("schedules", edit_ids=list(target[1]))
        else:
            _, tab, record_id = target
            self.go("academic", tab=tab, edit_id=record_id)
        self.search_completer.popup().hide()
        self.search.clear()

    def notify(self, text, kind="success"):
        self.msg.setText(text)
        set_kind(self.msg, kind)
        self.msg.show()
        self._msg_token += 1
        token = self._msg_token
        QTimer.singleShot(6000, lambda: self.msg.hide() if token == self._msg_token else None)

    def open_profile(self):
        self.go("settings")

    def _update_account_name(self, username):
        self.username = username
        self.profile_name.setText(self.username)
        self.profile_initial.setText(self.username[:1].upper() or "A")

    def logout(self):
        from ui.login import LoginDialog
        from PyQt5.QtWidgets import QDialog
        self.hide()
        dialog = LoginDialog()
        if dialog.exec_() == QDialog.Accepted:
            self._update_account_name(dialog.username.text().strip())
            self.show()
        else:
            self.close()
