from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QGraphicsDropShadowEffect, QSpinBox, QTimeEdit, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import logic


class _NoWheel:

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class Combo(_NoWheel, QComboBox):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)


class Spin(_NoWheel, QSpinBox):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)


class TimeEdit(_NoWheel, QTimeEdit):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setDisplayFormat("h:mm AP")


def set_kind(widget, kind, prop="kind"):
    widget.setProperty(prop, kind)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    for child in widget.findChildren(QLabel):
        child.style().unpolish(child)
        child.style().polish(child)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            w = item.widget()
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def set_combo(combo, value):
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def labeled(text, widget):
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(5)
    lab = QLabel(text.upper())
    lab.setObjectName("fieldLabel")
    v.addWidget(lab)
    v.addWidget(widget)
    return box


def label(text="", name=None, wrap=False, align=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if align:
        lab.setAlignment(align)
    return lab


def button(text, kind=None, slot=None):
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def action_icon(kind, color):
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if kind == "pencil":
        painter.drawLine(QPointF(3, 12.5), QPointF(11.2, 4.3))
        painter.drawLine(QPointF(9.8, 3.7), QPointF(11.8, 5.7))
        painter.drawLine(QPointF(2.5, 13.5), QPointF(6, 12.5))
        painter.drawLine(QPointF(11, 4), QPointF(12.2, 2.8))
    else:
        painter.drawLine(QPointF(3, 4.5), QPointF(13, 4.5))
        painter.drawLine(QPointF(6, 3), QPointF(10, 3))
        painter.drawLine(QPointF(4.5, 6), QPointF(5.2, 13))
        painter.drawLine(QPointF(11.5, 6), QPointF(10.8, 13))
        painter.drawLine(QPointF(5.2, 13), QPointF(10.8, 13))
        painter.drawLine(QPointF(7, 6.5), QPointF(7.2, 11.5))
        painter.drawLine(QPointF(9, 6.5), QPointF(8.8, 11.5))
    painter.end()
    return QIcon(pixmap)


class Badge(QLabel):
    def __init__(self, text="", kind="muted"):
        super().__init__(text)
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        set_kind(self, kind)

    def set(self, text, kind):
        self.setText(text)
        set_kind(self, kind)
        self.adjustSize()


def sev_label(text, kind=None):
    lab = QLabel(text)
    lab.setObjectName("sev")
    lab.setAlignment(Qt.AlignCenter)
    lab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    set_kind(lab, kind or text)
    return lab


class Card(QFrame):
    def __init__(self, title=None, subtitle=None, right=None):
        super().__init__()
        self.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setColor(QColor(18, 39, 82, 28))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(0)
        self.v.setAlignment(Qt.AlignTop)
        self.title_label = self.subtitle = None
        if title:
            head = QWidget()
            head.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            h = QHBoxLayout(head)
            h.setContentsMargins(18, 14, 18, 12)
            col = QVBoxLayout()
            col.setSpacing(1)
            self.title_label = label(title, "cardTitle")
            col.addWidget(self.title_label)
            if subtitle is not None:
                self.subtitle = label(subtitle, "muted", wrap=True)
                col.addWidget(self.subtitle)
            h.addLayout(col, 1)
            for w in right or []:
                h.addWidget(w)
            self.v.addWidget(head)

    def add(self, widget):
        self.v.addWidget(widget)
        return widget

    def body(self, margins=(18, 0, 18, 18), spacing=10):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(*margins)
        lay.setSpacing(spacing)
        lay.setAlignment(Qt.AlignTop)
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.v.addWidget(w)
        return lay


class Banner(QFrame):
    def __init__(self, kind="good", title="", text="", right=None, slim=False):
        super().__init__()
        self.setObjectName("banner")
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 8 if slim else 14, 18, 8 if slim else 14)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = label(title)
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        self.text = label(text)
        self.text.setStyleSheet("font-size: 11px;")
        col.addWidget(self.title)
        col.addWidget(self.text)
        self.text.setVisible(bool(text))
        h.addLayout(col)
        h.addStretch()
        if right is not None:
            h.addWidget(right)
        set_kind(self, kind)


class Page(QScrollArea):

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("pagebody")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(24, 20, 24, 28)
        self.lay.setSpacing(16)
        self.setWidget(body)

    def add_header(self, eyebrow, title, subtitle, actions=()):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(label(eyebrow, "eyebrow"))
        v.addWidget(label(title, "h2"))
        v.addWidget(label(subtitle, "muted", wrap=True))
        h.addLayout(v, 1)
        for a in actions:
            h.addWidget(a, 0, Qt.AlignBottom)
        self.lay.addWidget(w)

    def finish(self):
        self.lay.addStretch()

    def refresh(self):
        pass


class _WeightedTable(QTableWidget):
    def __init__(self, headers, row_h, fixed, flex):
        super().__init__(0, len(headers))
        self._fixed_widths = fixed
        self._flex_weights = (
            {col: 1 for col in range(len(headers)) if col not in fixed} if flex is None else flex
        )
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for col, width in fixed.items():
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.setColumnWidth(col, width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_columns()

    def _fit_columns(self):
        if not self._flex_weights:
            return
        free_width = max(0, self.viewport().width() - sum(self._fixed_widths.values()))
        total_weight = sum(self._flex_weights.values())
        assigned = 0
        columns = list(self._flex_weights)
        for index, col in enumerate(columns):
            width = free_width - assigned if index == len(columns) - 1 else free_width * self._flex_weights[col] // total_weight
            self.setColumnWidth(col, width)
            assigned += width


def make_table(headers, row_h=50, stretch=True, fixed=None, flex=None):
    fixed = fixed or {}
    if flex is None and not stretch:
        flex = {}
    t = _WeightedTable(headers, row_h, fixed, flex)
    t.setHorizontalHeaderLabels([h.upper() for h in headers])
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(row_h)
    hh = t.horizontalHeader()
    hh.setFixedHeight(34)
    hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    hh.setHighlightSections(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.NoFocus)
    t.setFrameShape(QFrame.NoFrame)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setWordWrap(False)
    t.setTextElideMode(Qt.ElideRight)
    return t


def fit_table(t):
    h = t.horizontalHeader().height() + sum(t.rowHeight(i) for i in range(t.rowCount())) + 2
    t.setFixedHeight(h)


def text_item(text, bold=False, muted=False):
    it = QTableWidgetItem(str(text))
    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if muted:
        it.setForeground(QColor("#7b869c"))
    return it


def rich_cell(table, row, col, html):
    lab = QLabel(html)
    lab.setObjectName("cell")
    lab.setWordWrap(True)
    lab.setContentsMargins(12, 0, 8, 0)
    table.setCellWidget(row, col, lab)
    return lab


def two_line(top, bottom, bold_top=True):
    t = f"<b>{top}</b>" if bold_top else top
    return f"{t}<br><span style='color:#7b869c;font-size:11px'>{bottom}</span>"


def widget_cell(table, row, col, widget, alignment=Qt.AlignVCenter):
    host = QWidget()
    host.setObjectName("cell")
    h = QHBoxLayout(host)
    h.setContentsMargins(12, 0, 12, 0)
    h.addWidget(widget, 0, alignment)
    table.setCellWidget(row, col, host)


def empty_row(table, text):
    table.setRowCount(1)
    table.setSpan(0, 0, 1, table.columnCount())
    it = QTableWidgetItem(text)
    it.setFlags(Qt.ItemIsEnabled)
    it.setTextAlignment(Qt.AlignCenter)
    it.setForeground(QColor("#7b869c"))
    table.setItem(0, 0, it)
    table.setRowHeight(0, 70)


class Bar(QWidget):

    def __init__(self, value=0, color="#268db7"):
        super().__init__()
        self.value, self.color = value, color
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#e2eaf3"))
        p.drawRoundedRect(r, 3, 3)
        p.setBrush(QColor(self.color))
        p.drawRoundedRect(QRectF(0, 0, self.width() * max(0, min(100, self.value)) / 100, self.height()), 3, 3)


class WeekGrid(QWidget):

    def __init__(self, cells):
        super().__init__()
        self.cells = cells
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.cells)
        gap = 6
        w = (self.width() - gap * (n - 1)) / n
        f = QFont(self.font())
        f.setPixelSize(9)
        p.setFont(f)
        for i, c in enumerate(self.cells):
            x = i * (w + gap)
            p.setPen(QColor("#71819b"))
            p.drawText(QRectF(x, 0, w, 12), Qt.AlignCenter, c["day"])
            p.setPen(Qt.NoPen)
            for j, free in enumerate(c["blocks"]):
                p.setBrush(QColor("#b8e7d2" if free else "#e7edf4"))
                p.drawRoundedRect(QRectF(x, 15 + j * 11, w, 8), 3, 3)


class BarChart(QWidget):

    def __init__(self):
        super().__init__()
        self.data = []
        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, _):
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        top, bottom = 22, 22
        plot_h = H - top - bottom
        n = len(self.data)
        gap = 14
        bw = (W - gap * (n + 1)) / n
        f = QFont(self.font())
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(QPen(QColor("#e1e8f1"), 1))
        p.drawLine(0, H - bottom, W, H - bottom)
        for i, (lab, pct) in enumerate(self.data):
            x = gap + i * (bw + gap)
            h = max(2.0, plot_h * pct / 100)
            grad = QLinearGradient(0, H - bottom - h, 0, H - bottom)
            grad.setColorAt(0, QColor("#14b8a6"))
            grad.setColorAt(1, QColor("#214777"))
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x, H - bottom - h, bw, h), 4, 4)
            p.setPen(QColor("#71819b"))
            p.drawText(QRectF(x - 6, H - bottom - h - 16, bw + 12, 14), Qt.AlignCenter, f"{pct}%")
            p.drawText(QRectF(x - 6, H - bottom + 4, bw + 12, 14), Qt.AlignCenter, lab)


class CalendarWidget(QWidget):

    HEADER, TIMECOL, ROW_H = 30, 66, 44
    COLORS = {  # background, accent, text
        "major": ("#e8eff8", "#214777", "#203b68"),
        "ged": ("#e0f2f7", "#268db7", "#137b98"),
        "lab": ("#fff4df", "#d89b3b", "#916018"),
    }

    def __init__(self):
        super().__init__()
        self.rows, self.sub_key = [], "room"
        self.hours = (logic.CAL_END - logic.CAL_START) // 60
        self.setFixedHeight(self.HEADER + self.hours * self.ROW_H + 2)
        self.setMinimumWidth(480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_rows(self, rows, sub_key="room"):
        self.rows, self.sub_key = rows, sub_key
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        colw = (W - self.TIMECOL - 1) / 6
        p.fillRect(0, 0, W, H, QColor("white"))
        p.fillRect(0, 0, W, self.HEADER, QColor("#f4f8f9"))

        f = QFont(self.font())
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#55627f"))
        p.drawText(QRectF(0, 0, self.TIMECOL, self.HEADER), Qt.AlignCenter, "TIME")
        for i, code in enumerate(logic.DAY_CODES):
            p.drawText(QRectF(self.TIMECOL + i * colw, 0, colw, self.HEADER), Qt.AlignCenter, code.upper())

        f.setBold(False)
        p.setFont(f)
        for h in range(self.hours):
            y = self.HEADER + h * self.ROW_H
            p.setPen(QPen(QColor("#eef0f6"), 1))
            p.drawLine(self.TIMECOL, y, W, y)
            p.setPen(QColor("#7b869c"))
            p.drawText(QRectF(0, y + (2 if h == 0 else -7), self.TIMECOL - 8, 14),
                       Qt.AlignRight | Qt.AlignVCenter, logic.fmt(logic.CAL_START + h * 60))
        p.setPen(QPen(QColor("#e6e9f0"), 1))
        for i in range(7):
            x = self.TIMECOL + i * colw
            p.drawLine(int(x), 0, int(x), H)

        for r in self.rows:
            s, e = max(r["start_min"], logic.CAL_START), min(r["end_min"], logic.CAL_END)
            if e <= s:
                continue
            x = self.TIMECOL + logic.DAY_CODES.index(r["day"]) * colw + 3
            y = self.HEADER + (s - logic.CAL_START) / 60 * self.ROW_H + 1
            h = max((e - s) / 60 * self.ROW_H - 3, 18)
            bg, accent, fg = self.COLORS[r["category"]]
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(bg))
            p.drawRoundedRect(QRectF(x, y, colw - 6, h), 6, 6)
            p.setBrush(QColor(accent))
            p.drawRoundedRect(QRectF(x, y, 4, h), 2, 2)
            p.setPen(QColor(fg))
            tw = int(colw - 6 - 14)
            lines = [(r["code"], True), (str(r[self.sub_key]), False),
                     (f"{logic.fmt(r['start_min'])} – {logic.fmt(r['end_min'])}", False)]
            ty = y + 4
            for text, bold in lines:
                f.setBold(bold)
                f.setPixelSize(11 if bold else 10)
                p.setFont(f)
                fm = QFontMetrics(f)
                if ty + fm.height() > y + h + 1:
                    break
                p.drawText(QRectF(x + 9, ty, tw, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                           fm.elidedText(text, Qt.ElideRight, tw))
                ty += fm.height() + 1
        p.setPen(QPen(QColor("#e6e9f0"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, W - 1, H - 1)
