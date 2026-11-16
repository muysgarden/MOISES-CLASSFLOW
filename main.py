import sys
import sqlite3
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog
import auth
import db
from ui.login import LoginDialog
from ui.availability import init_availability
from ui.main_window import MainWindow
from ui.style import build_qss
from ui.workspace import active_workspace_path, validate_workspace, select_workspace


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('ClassFlow')
    app.setStyleSheet(build_qss())
    # A saved dataset may have been moved or deleted since last launch.
    # Offer recovery without removing or overwriting any existing database.
    while True:
        try:
            db.init(active_workspace_path())
            auth.init()
            init_availability()
            break
        except (OSError, ValueError, sqlite3.DatabaseError) as exc:
            if db.conn is not None:
                try:
                    db.conn.close()
                except sqlite3.Error:
                    pass
                db.conn = None
            box = QMessageBox()
            box.setWindowTitle("ClassFlow — Dataset unavailable")
            box.setIcon(QMessageBox.Warning)
            box.setText("ClassFlow could not open the selected dataset.")
            box.setInformativeText(
                f"{exc}\n\nChoose another dataset, use the original local "
                "database, or cancel. No existing records will be deleted."
            )
            choose = box.addButton("Choose Dataset…", QMessageBox.ActionRole)
            original = box.addButton("Use Original Dataset", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Cancel)
            box.exec_()
            selected = box.clickedButton()
            if selected is choose:
                path, _ = QFileDialog.getOpenFileName(
                    None, "Select ClassFlow Dataset", "",
                    "ClassFlow Databases (*.db);;All Files (*)"
                )
                if not path:
                    continue
                try:
                    select_workspace(validate_workspace(path))
                except (OSError, ValueError) as err:
                    QMessageBox.warning(None, "Invalid dataset", str(err))
            elif selected is original:
                # Restore default selection only; do not alter any database.
                from ui.workspace import SETTINGS_APP, SETTINGS_ORG, WORKSPACE_KEY
                from PyQt5.QtCore import QSettings
                QSettings(SETTINGS_ORG, SETTINGS_APP).remove(WORKSPACE_KEY)
                # Explicit CLASSFLOW_DB is never silently overridden.
                import os
                if os.environ.get("CLASSFLOW_DB"):
                    QMessageBox.warning(
                        None, "Dataset override active",
                        "Remove the CLASSFLOW_DB environment variable before "
                        "using the original dataset."
                    )
                    return 1
            else:
                return 1
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
