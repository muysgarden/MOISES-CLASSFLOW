import os
import tempfile

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QPalette, QPixmap, QPolygonF
from PyQt5.QtWidgets import QApplication

QSS = """
* { font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif; font-size: 13px; color: #1c2b4a; }
QMainWindow, #pagebody, QScrollArea { background: #f4f5f9; }
QScrollArea { border: none; }
QToolTip { background: #14264a; color: white; border: none; padding: 4px 6px; }

/* ---------- sidebar ---------- */
#sidebar { background: #14264a; }
#sidebar QLabel { color: #cfd8ec; background: transparent; }
#brandName { color: white; font-size: 16px; font-weight: 700; }
#brandSub { color: #8fa0c4; font-size: 11px; }
#logo { background: #14b8a6; border-radius: 9px; color: white; font-size: 17px; }
#navLabel { color: #6f82aa; font-size: 10px; font-weight: 600; }
QPushButton#nav { background: transparent; border: none; border-left: 3px solid transparent;
    border-radius: 12px; padding: 0; text-align: left; }
QPushButton#nav:hover { background: rgba(255,255,255,0.05); }
QPushButton#nav:checked { background: rgba(255,255,255,0.10); border-left: 3px solid #14b8a6; }
#sidebar QPushButton#nav QLabel { color: #aebbd8; font-weight: 400; }
#sidebar QPushButton#nav:checked QLabel { color: white; font-weight: 600; }
#sidebar QPushButton#nav QLabel#navNum { color: #5f7298; font-size: 10px; font-weight: 600; }
#sidebar QPushButton#nav:checked QLabel#navNum { color: #14b8a6; }
#progressCard { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10); border-radius: 10px; }
#progressPct { color: #14b8a6; font-weight: 700; }
#helpTitle { color: white; font-weight: 700; }
#helpSub { color: #8fa0c4; font-size: 11px; }

/* ---------- top bar ---------- */
#topbar { background: white; border-bottom: 1px solid #e6e9f0; }
#topTitle { font-weight: 700; font-size: 17px; color: #14264a; }
#avatar, #avatarTop { background: #e8ebf3; border-radius: 14px; font-size: 10px; font-weight: 700; color: #1c2b4a; }
#avatarTop { border-radius: 16px; font-size: 11px; }
#avatarSq { background: #e8ebf3; border-radius: 7px; font-size: 12px; }
#userName { font-weight: 600; font-size: 12px; }

/* ---------- typography ---------- */
#eyebrow { color: #14b8a6; font-size: 10px; font-weight: 700; }
#h2 { font-size: 24px; font-weight: 700; }
#muted { color: #7b869c; font-size: 11px; }
#cardTitle { font-size: 14px; font-weight: 700; }
#fieldLabel { color: #55627f; font-size: 10px; font-weight: 700; }
#err { color: #dc4b4b; font-size: 11px; }
#big { font-size: 22px; font-weight: 700; }

/* ---------- cards ---------- */
#card { background: white; border: 1px solid #e6e9f0; border-radius: 16px; }
QFrame#recordPanel { background: white; border: 1px solid #e6e9f0; border-radius: 16px; }
QFrame#recordPanelSurface { background: transparent; border: none; }
#tabbar { background: white; border: 1px solid #e6e9f0; border-radius: 16px; }
#formHead { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14264a, stop:1 #27487f);
    border-top-left-radius: 15px; border-top-right-radius: 15px; }
#formHead QLabel { background: transparent; }
#formTitle { color: white; font-size: 14px; font-weight: 700; }
#formSub { color: #b9c7e6; font-size: 11px; }

/* ---------- buttons ---------- */
QPushButton { background: white; border: 1px solid #e6e9f0; border-radius: 10px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #f3f5fa; }
QPushButton:pressed { background: #e9edf7; }
QPushButton#primary { background: #1b2f55; border: 1px solid #1b2f55; color: white; }
QPushButton#primary:hover { background: #27487f; }
QPushButton#small { padding: 4px 12px; font-size: 12px; }
QPushButton#smallPrimary { padding: 4px 12px; font-size: 12px; background: #1b2f55; border: 1px solid #1b2f55; color: white; }
QPushButton#smallPrimary:hover { background: #27487f; }
QPushButton#linkbtn { border: none; background: transparent; padding: 4px 6px; font-size: 12px; }
QPushButton#linkbtn:hover { color: #14b8a6; background: transparent; }
QPushButton#danger { border: none; background: transparent; padding: 4px 6px; font-size: 12px; color: #55627f; }
QPushButton#danger:hover { color: #dc4b4b; background: transparent; }
QPushButton#tab { background: transparent; border: none; border-radius: 12px; padding: 10px 12px; color: #7b869c; font-size: 12px; }
QPushButton#tab:hover { background: #f3f5fa; }
QPushButton#tab:checked { background: #e9edf7; color: #14264a; border-bottom: 2px solid #14b8a6; border-radius: 12px; }
QPushButton#chip { background: #eceff6; border: none; border-radius: 7px; padding: 6px 10px; font-size: 11px; color: #55627f; }
QPushButton#chip:hover { background: #e2e7f1; }
QPushButton#chip:checked { background: #1b2f55; color: white; }
QPushButton#pg { padding: 4px 10px; font-size: 11px; border-radius: 12px; }
QPushButton#pg:checked { background: #1b2f55; color: white; border-color: #1b2f55; }

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QTimeEdit { background: white; border: 1px solid #e6e9f0; border-radius: 10px;
    padding: 6px 10px; min-height: 22px; selection-background-color: #14b8a6; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus { border: 1px solid #14b8a6; }
QComboBox QAbstractItemView { background: white; border: 1px solid #e6e9f0; outline: 0;
    selection-background-color: #e0f5f2; selection-color: #1c2b4a; }
QCheckBox { spacing: 6px; background: transparent; }

/* ---------- tables ---------- */
QTableWidget { background: white; border: none; gridline-color: transparent; outline: 0; }
QTableWidget::item { border-bottom: 1px solid #e6e9f0; padding: 4px 12px; }
QHeaderView::section { background: #fafbfd; color: #7b869c; font-size: 10px; font-weight: 700; border: none;
    border-top: 1px solid #e6e9f0; border-bottom: 1px solid #e6e9f0; padding: 6px 12px; }
#cell { background: transparent; }
QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active { background-color: #fff4d6; color: #1c2b4a; }

/* ---------- badges / pills ---------- */
QLabel#badge { border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600; background: #eceff6; color: #55627f; }
QLabel#badge[kind="ok"] { background: #e4f6ec; color: #2f9e6b; }
QLabel#badge[kind="teal"] { background: #e0f5f2; color: #0f8a7c; }
QLabel#badge[kind="warn"] { background: #fdf3dc; color: #d98a1a; }
QLabel#badge[kind="bad"] { background: #fdecec; color: #dc4b4b; }
QLabel#badge[kind="muted"] { background: #eceff6; color: #55627f; }
QLabel#pill { background: #e8ecf5; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600; }

/* ---------- resource cards (Module 2) ---------- */
#res { background: white; border: 1px solid #eef0f6; }
#res[hit="true"] { background: #f1faf8; border-left: 3px solid #14b8a6; }

/* ---------- stat cards (Module 4) ---------- */
#stat { background: white; border: 1px solid #e6e9f0; border-top: 3px solid #e6e9f0; border-radius: 12px; }
#stat[tone="red"] { border-top: 3px solid #dc4b4b; }
#stat[tone="amber"] { border-top: 3px solid #d98a1a; }
#stat[tone="green"] { border-top: 3px solid #2f9e6b; }
#statNum { font-size: 26px; font-weight: 700; }

/* ---------- banners & messages ---------- */
#banner { border-radius: 10px; border: 1px solid; }
#banner[kind="bad"] { background: #fdecec; border-color: #f4c3c3; }
#banner[kind="bad"] QLabel { color: #b13a3a; background: transparent; }
#banner[kind="good"] { background: #e4f6ec; border-color: #bfe6d0; }
#banner[kind="good"] QLabel { color: #217a52; background: transparent; }
#check { background: #f3f5fa; border-radius: 9px; padding: 10px 14px; color: #7b869c; }
#check[kind="ok"] { background: #e4f6ec; color: #217a52; }
#check[kind="warning"] { background: #fdf3dc; color: #9a6410; }
#check[kind="conflict"] { background: #fdecec; color: #b13a3a; }
#msg { border-radius: 9px; padding: 10px 14px; font-weight: 500; border: 1px solid; }
#msg[kind="success"] { background: #e4f6ec; border-color: #bfe6d0; color: #217a52; }
#msg[kind="error"] { background: #fdecec; border-color: #f4c3c3; color: #b13a3a; }
#msg[kind="warning"] { background: #fdf3dc; border-color: #f2dba3; color: #9a6410; }
QLabel#sev { border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#sev[kind="Critical"] { background: #fdecec; color: #dc4b4b; }
QLabel#sev[kind="Warning"] { background: #fdf3dc; color: #d98a1a; }
QLabel#sev[kind="Review"] { background: #eaeef6; color: #5a6a8c; }
QLabel#sev[kind="OK"] { background: #e4f6ec; color: #2f9e6b; }

QFrame#cardFoot { border: none; border-top: 1px solid #e6e9f0; border-radius: 0; background: transparent; }
#hint { background: #e4f6ec; border: 1px solid #bfe6d0; border-radius: 8px; padding: 8px 10px; color: #217a52; font-size: 11px; }
QLabel#editing { background: #fdf3dc; color: #9a6410; border-radius: 8px; padding: 6px 10px; font-size: 11px; }

/* ---------- scrollbars ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cfd6e4; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cfd6e4; border-radius: 4px; min-width: 30px; }
"""


def _arrow(path, up=False):
    pm = QPixmap(10, 6)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#7b869c"))
    pts = [QPointF(0.5, 5.5), QPointF(9.5, 5.5), QPointF(5, 0.5)] if up else \
          [QPointF(0.5, 0.5), QPointF(9.5, 0.5), QPointF(5, 5.5)]
    p.drawPolygon(QPolygonF(pts))
    p.end()
    pm.save(path)


POLISH_QSS = """
* { color: #263b59; }
QMainWindow, #pagebody, QScrollArea { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #f6f8fc, stop:1 #eaf0f7); }
QToolTip { background: #14264a; color: #ffffff; border: 1px solid #334e77; padding: 6px 8px; }
#sidebar { background: #14264a; }
#sidebar QLabel { color: #ccd6e7; background: transparent; }
#brandName { color: #ffffff; font-size: 20px; font-weight: 700; }
#brandSub { color: #9aaaca; font-size: 11px; }
#logo { background: #28a4c4; border-radius: 9px; color: #ffffff; font-size: 17px; }
#navLabel { color: #8393b2; font-size: 12px; font-weight: 700; }
#sidebarDivider { background: rgba(221,232,246,0.14); border: none; }
QPushButton#nav { border-radius: 12px; }
QPushButton#nav:hover { background: rgba(255,255,255,0.07); }
QPushButton#nav:checked { background: #213c69; border-left: 3px solid #35b5cb; }
#sidebar QPushButton#nav QLabel { color: #bac7df; font-size: 12px; }
#sidebar QPushButton#nav:checked QLabel { color: #ffffff; font-weight: 600; }
#sidebar QPushButton#nav QLabel#navNum { color: #7589af; font-size: 10px; font-weight: 700; }
#sidebar QPushButton#nav:checked QLabel#navNum { color: #35b5cb; }
#sidebar QPushButton#nav QLabel#navChevron { color: #d6e0ee; font-size: 19px; }
#progressCard { background: #1b345d; border: 1px solid #344d73; border-radius: 8px; }
#progressPct { color: #35b5cb; font-weight: 700; }
#helpTitle { color: #ffffff; font-weight: 700; }
#helpSub { color: #9aaaca; }
#topbar { background: #ffffff; border-bottom: 1px solid #dce4ee; }
#topTitle { color: #172e55; }
#avatar, #avatarTop, #avatarSq { background: #e9eef7; color: #294b78; }
#userName { color: #263f65; }
#eyebrow { color: #1689b4; }
#h2 { color: #1b335a; }
#muted { color: #7786a0; }
#cardTitle { color: #20385f; }
#fieldLabel { color: #526482; }
#err { color: #b9453f; }
#big, #statNum { color: #1b335a; }
QFrame#card, QFrame#recordPanel { background: #ffffff; border: 1px solid #dce4ee; border-radius: 16px; }
QFrame#recordPanelSurface { background: transparent; border: none; }
#tabbar { background: #ffffff; border: 1px solid #dce4ee; border-radius: 16px; }
#formHead { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14264a, stop:1 #31558a);
    border-top-left-radius: 15px; border-top-right-radius: 15px; }
#formHead QLabel { background: transparent; }
#formTitle { color: #ffffff; }
#formSub { color: #c3cfe4; }
QPushButton { background: #ffffff; border: 1px solid #d6e0ec; border-radius: 12px; color: #2e4568; }
QPushButton:hover { background: #f2f6fc; border-color: #b9cbe0; }
QPushButton:pressed { background: #e7eef8; }
QPushButton:disabled { background: #f1f4f8; border-color: #e2e8f0; color: #a0adbf; }
QPushButton#primary, QPushButton#smallPrimary { background: #214777; border-color: #214777; color: #ffffff; }
QPushButton#primary:hover, QPushButton#smallPrimary:hover { background: #2b568b; border-color: #2b568b; }
QPushButton#linkbtn { color: #236995; }
QPushButton#linkbtn:hover { color: #167fa8; background: #eef5fb; }
QPushButton#danger { color: #667872; }
QPushButton#danger:hover { color: #b9453f; background: #fff1ef; }
QPushButton#tab { border-radius: 12px; color: #7786a0; }
QPushButton#tab:hover { background: #f1f5fb; color: #294b78; }
QPushButton#tab:checked { background: #e8eff9; color: #203b68; border-bottom: 2px solid #35a6c5; border-radius: 12px; }
QPushButton#chip { background: #edf2f8; color: #526482; }
QPushButton#chip:hover { background: #e0e9f3; }
QPushButton#chip:checked, QPushButton#pg:checked { background: #214777; color: #ffffff; border-color: #214777; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit { background: #ffffff; border: 1px solid #d6e0ec; border-radius: 12px; padding: 8px 10px; min-height: 24px; selection-background-color: #268db7; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QTimeEdit:hover { border-color: #b5c8df; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus { border: 1px solid #268db7; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #d6e0ec; selection-background-color: #e4eff9; selection-color: #1b335a; }
QCheckBox { spacing: 7px; color: #2e4568; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #bdcadd; border-radius: 4px; background: #ffffff; }
QCheckBox::indicator:checked { background: #268db7; border-color: #268db7; }
QTableWidget { background: #ffffff; alternate-background-color: #f8fafd; }
QTableWidget::item { border-bottom: 1px solid #edf1f6; padding: 5px 12px; }
QHeaderView::section { background: #f7f9fc; color: #71819b; border-top: 1px solid #e6ecf3; border-bottom: 1px solid #dfe7f0; }
QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active { background-color: #e7f0fb; color: #1b335a; }
QLabel#badge, QLabel#pill { background: #e8eff8; color: #294b78; border-radius: 6px; }
QLabel#badge[kind="ok"], QLabel#sev[kind="OK"] { background: #e4f3e9; color: #26734f; }
QLabel#badge[kind="teal"] { background: #e0f2f7; color: #137b98; }
QLabel#badge[kind="warn"], QLabel#sev[kind="Warning"] { background: #fff4df; color: #966318; }
QLabel#badge[kind="bad"], QLabel#sev[kind="Critical"] { background: #ffefed; color: #b9453f; }
QLabel#badge[kind="muted"], QLabel#sev[kind="Review"] { background: #edf3f0; color: #5c706b; }
#res[hit="true"] { background: #eff6fb; border-left: 3px solid #35a6c5; }
#stat { background: #ffffff; border-color: #dce4ee; border-top-color: #c8d5e5; border-radius: 8px; }
#stat[tone="red"] { border-top-color: #c9524c; }
#stat[tone="amber"] { border-top-color: #d89b3b; }
#stat[tone="green"] { border-top-color: #168f73; }
#banner { border-radius: 7px; }
#banner[kind="bad"], #check[kind="conflict"], #msg[kind="error"] { background: #ffefed; border-color: #f1c7c2; color: #a83e38; }
#banner[kind="good"], #check[kind="ok"], #msg[kind="success"] { background: #e8f5ed; border-color: #c2e2cf; color: #286b4c; }
#check[kind="warning"], #msg[kind="warning"], QLabel#editing { background: #fff4df; color: #916018; }
#msg { border-radius: 7px; font-weight: 600; }
QFrame#cardFoot { border-top: 1px solid #e7edf4; }
#hint { background: #e8f5ed; border: 1px solid #c2e2cf; border-radius: 6px; color: #286b4c; }
QLabel#editing { border-radius: 6px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 3px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #c6d2e1; border-radius: 4px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #91a7c3; }
"""


def build_qss():
    """QSS plus generated arrow images (call after QApplication exists)."""
    app = QApplication.instance()
    if app is not None:
        palette = app.palette()
        palette.setColor(QPalette.PlaceholderText, QColor("#8998ad"))
        palette.setColor(QPalette.Highlight, QColor("#268db7"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(palette)
    d = tempfile.gettempdir()
    down, up = os.path.join(d, "classflow_down.png"), os.path.join(d, "classflow_up.png")
    _arrow(down)
    _arrow(up, up=True)
    down, up = down.replace("\\", "/"), up.replace("\\", "/")
    return QSS + POLISH_QSS + REFERENCE_QSS + f"""
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 10px; height: 6px; }}
QSpinBox::up-button, QTimeEdit::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 22px; border: none; }}
QSpinBox::down-button, QTimeEdit::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; border: none; }}
QSpinBox::up-arrow, QTimeEdit::up-arrow {{ image: url("{up}"); width: 8px; height: 5px; }}
QSpinBox::down-arrow, QTimeEdit::down-arrow {{ image: url("{down}"); width: 8px; height: 5px; }}
"""


REFERENCE_QSS = """
* { font-size: 12px; }
#sidebar { background:#152b45; }
#logo { background:#14b8a6; }
#brandName { color:white; }
#topTitle { font-size:12px; font-weight:500; }
#h2 { font-size:23px; }
#eyebrow { color:#0caa9c; }
QFrame#card, QFrame#recordPanel, #tabbar { border-radius:7px; }
QPushButton, QLineEdit, QComboBox, QSpinBox, QTimeEdit { border-radius:5px; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit { padding:5px 8px; min-height:22px; }
QPushButton#primary, QPushButton#smallPrimary { background:#203c61; border-color:#203c61; border-radius:5px; }
QPushButton#nav { border-radius:6px; }
QPushButton#nav:checked { background:#263e57; border-left:3px solid #14b8a6; }
QPushButton#tab, QPushButton#tab:checked { border-radius:5px; }
QPushButton#tab:checked { border-bottom:2px solid #14b8a6; }
#progressPct { color:#14b8a6; }
#banner[kind="bad"] QLabel { color:#d8414b; }
#banner[kind="good"] QLabel { color:#118563; }
#banner[kind="warn"] { background:#fff4df; border-color:#f4d7a0; }
#banner[kind="warn"] QLabel { color:#916018; }
#formHead { border-top-left-radius:6px; border-top-right-radius:6px; }
"""
