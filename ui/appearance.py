"""Persisted, application-wide ClassFlow appearance settings.

The light theme is untouched. Dark theme is an additive QSS layer so it can
be switched at runtime without rebuilding any pages or losing form data.
"""
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QDialog
from ui.style import build_qss

DARK_QSS = """
QMainWindow, QWidget#workspace, QWidget#pagebody, QScrollArea,
QWidget#dashboardPage, QWidget#dashboardCanvas,
QWidget#availabilityPage, QWidget#schedulesPage, QWidget#validationPage,
QWidget#accountSettingsPage { background: #121B2B; color: #DEE7F5; }
QWidget { selection-background-color: #385B9C; selection-color: #FFFFFF; }
QLabel { color: #DCE5F3; }
QFrame#sidebar, QFrame#topbar { background: #19253A; border-color: #34445D; }
QFrame#sidebar QLabel, #brandName, #userName, #topTitle, #topContext {
    color: #E5EDFA;
}
QPushButton#nav, QPushButton#sidebarLogout { color: #DCE5F3; }
QPushButton#nav:hover { background: #253A55; }
QPushButton#profileTrigger { background: #253449; border-color: #3A4B65; }
QPushButton#profileTrigger QLabel { color: #E1E8F5; }
QFrame#card, QFrame#recordPanel, QFrame#recordPanelSurface,
QFrame#metricCard, QFrame#availPanel, QFrame#availItem,
QFrame#scheduleEditor, QFrame#settingsSurface, QFrame#settingsMenu,
QWidget#settingsBody, QScrollArea#settingsScroll, QFrame#dashEmpty {
    background: #202D42; border: 1px solid #3B4D68; color: #E1E9F5;
}
QFrame#card QLabel, QFrame#recordPanel QLabel, QFrame#metricCard QLabel,
QFrame#availPanel QLabel, QFrame#availItem QLabel, QFrame#settingsSurface QLabel,
QFrame#scheduleEditor QLabel { color: #E1E9F5; }
QLabel#muted, QLabel#dashSub, QLabel#settingsHint,
QLabel#settingsSubtitle, QLabel#availInfo, QLabel#availCaption,
QLabel#topContext, QLabel#fieldLabel { color: #A9B9CF; }
QLabel#h2, QLabel#cardTitle, QLabel#dashSection,
QLabel#settingsHeading, QLabel#settingsSectionTitle,
QLabel#availHeading, QLabel#availName, QLabel#formTitle {
    color: #F2F6FE;
}
QLineEdit, QComboBox, QSpinBox, QTimeEdit, QTextEdit, QPlainTextEdit,
QComboBox QAbstractItemView, QListView {
    background: #26364C; color: #EDF4FF; border: 1px solid #49607D;
    selection-background-color: #375F9D; selection-color: white;
}
QLineEdit#globalSearch, QComboBox#termSelector {
    background: #26364C; color: #EDF4FF; border-color: #49607D;
}
QPushButton { background: #28394F; color: #E7EFFB; border: 1px solid #465B78; }
QPushButton:hover { background: #344A65; }
QPushButton:disabled { color: #8797AD; background: #243044; }
QPushButton#primary, QPushButton#smallPrimary,
QPushButton#settingsPrimary, QPushButton#availToggle {
    background: #416AD3; color: white; border: 1px solid #416AD3;
}
QPushButton#tab, QPushButton#settingsTab { color: #AFC1DA; }
QPushButton#tab:checked, QPushButton#settingsTab:checked {
    background: #34436A; color: #EDF4FF; border-color: #627BCE;
}
QTableWidget, QTableView {
    background: #202D42; alternate-background-color: #24344B;
    color: #E4ECF8; gridline-color: #40516D;
    border: 1px solid #40516D;
}
QTableWidget::item { color: #E4ECF8; border-bottom: 1px solid #394961; }
QTableWidget::item:selected { color: #FFFFFF; background: #355586; }
QHeaderView::section {
    background: #2B3A52; color: #D8E4F5;
    border-bottom: 1px solid #49607D;
}
QTabWidget::pane { background: #202D42; border-color: #40516D; }
QTabBar::tab { background: #26364C; color: #C4D3E7; }
QTabBar::tab:selected { background: #3A426B; color: white; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #566782; }
QFrame#healthBanner { background: #2B427D; }
QFrame#healthBanner QLabel { color: #FFFFFF; }
QPushButton#quickAction, QPushButton#recentRow {
    background: #202D42; color: #E2EDFC; border-color: #3C4F6B;
}
QPushButton#quickAction QLabel, QPushButton#recentRow QLabel {
    color: #E2EDFC;
}
QLabel#settingsAvatar { background: #34436A; color: #D5E5FF; }
QPushButton#settingsBack { background: #28394F; color: #C9DBFF; }
QPushButton#settingsDanger { background: #482F3D; color: #FFC0C8; }
QPushButton#availRemove { background: #28394F; color: #CFDAEB; border-color: #52627B; }
QPushButton#availRemove:hover { background: #563742; color: #FFE2E6; }
QLabel#sev, QLabel#badge { color: #E5EDFA; }
"""

# Pages with local stylesheets need equally specific rules; otherwise their
# original widget-level light QSS overrides QApplication's global stylesheet.
LOCAL_DARK_QSS = """
#accountSettingsPage, #availabilityPage, #schedulesPage {
    background: #121B2B;
}
#accountSettingsPage QFrame#settingsSurface,
#accountSettingsPage QFrame#settingsMenu,
#accountSettingsPage QWidget#settingsBody,
#accountSettingsPage QScrollArea#settingsScroll,
#availabilityPage QFrame#availPanel,
#availabilityPage QFrame#availItem,
#schedulesPage QFrame#scheduleEditor {
    background: #202D42; border-color: #40516D;
}
#accountSettingsPage QLabel, #availabilityPage QLabel, #schedulesPage QLabel {
    color: #DDE8F7;
}
#accountSettingsPage QLabel#settingsHint,
#accountSettingsPage QLabel#settingsSubtitle,
#availabilityPage QLabel#availInfo,
#availabilityPage QLabel#availCaption,
#schedulesPage QLabel#muted { color: #A8BAD3; }
#accountSettingsPage QLineEdit,
#availabilityPage QLineEdit, #availabilityPage QComboBox,
#schedulesPage QLineEdit, #schedulesPage QComboBox {
    background: #27364C; color: #F0F5FF; border-color: #4B5E79;
}
#accountSettingsPage QPushButton#settingsTab,
#availabilityPage QTabBar::tab,
#schedulesPage QTabBar::tab { background: #27364C; color: #CDDBED; }
#accountSettingsPage QPushButton#settingsTab:checked,
#availabilityPage QTabBar::tab:selected,
#schedulesPage QTabBar::tab:selected {
    background: #36466D; color: white;
}
#availabilityPage QTableWidget#blockedRecords {
    background: #202D42; color: #E6EEFB; border-color: #40516D;
}
#availabilityPage QTableWidget#blockedRecords QHeaderView::section {
    background: #2B3A52; color: #DAE5F5;
}
#availabilityPage QPushButton#availRemove {
    background: #2C3A50; color: #C9D9EB; border-color: #52637E;
}
#availabilityPage QPushButton#availRemove:hover {
    background: #543644; color: #FFE2E7;
}
#schedulesPage QPushButton#scheduleCancel {
    background: #2C3A50; color: #D4E2F3; border-color: #52637E;
}
"""

def current_mode():
    value=QSettings("ClassFlow","ClassFlow").value("appearance","light")
    return value if value in ("light","dark") else "light"

def save_mode(mode):
    if mode not in ("light","dark"):
        raise ValueError("Unsupported appearance mode")
    QSettings("ClassFlow","ClassFlow").setValue("appearance",mode)

def apply_mode(mode=None):
    """Apply immediately to already-created widgets; never alter database data."""
    mode=mode or current_mode()
    app=QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(build_qss()+(DARK_QSS if mode=="dark" else ""))
    for widget in app.allWidgets():
        if isinstance(widget,QDialog):
            # The sign-in window intentionally keeps its existing photo design.
            continue
        original=widget.property("_classflow_light_qss")
        if original is None:
            original=widget.styleSheet()
            if not original:
                continue
            widget.setProperty("_classflow_light_qss", original)
        desired=original+(LOCAL_DARK_QSS if mode=="dark" else "")
        if widget.styleSheet()!=desired:
            widget.setStyleSheet(desired)
