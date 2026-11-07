import sys
import sqlite3
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
import auth
import db
from ui.login import LoginDialog
from ui.availability import init_availability
from ui.main_window import MainWindow
from ui.style import build_qss
from ui.workspace import active_workspace_path


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('ClassFlow')
    app.setStyleSheet(build_qss())
    try:
        db.init(active_workspace_path())
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        QMessageBox.critical(None, "Cannot open ClassFlow dataset", str(exc))
        return 1
    auth.init()
    init_availability()
    # No destructive reset flag: existing records are never silently erased.
    login = LoginDialog()
    if login.exec_()!=QDialog.Accepted:
        return 0
    # New workspaces stay blank unless the developer explicitly requests demo data.
    if '--seed' in sys.argv and db.is_empty():
        db.seed()
    win=MainWindow(username=login.username.text().strip()); win.showMaximized()
    return app.exec_()


if __name__=='__main__':
    sys.exit(main())
