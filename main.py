import sys
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
import auth
import db
from ui.login import LoginDialog
from ui.availability import init_availability
from ui.main_window import MainWindow
from ui.style import build_qss


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('ClassFlow')
    app.setStyleSheet(build_qss())
    db.init(); auth.init(); init_availability()
    # No destructive reset flag: existing records are never silently erased.
    if LoginDialog().exec_()!=QDialog.Accepted:
        return 0
    if db.is_empty():
        if '--seed' in sys.argv or QMessageBox.question(None,'Welcome to ClassFlow','Load sample academic data to explore the system?\nChoose No to start with your own records.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            db.seed()
    win=MainWindow(); win.show()
    return app.exec_()


if __name__=='__main__':
    sys.exit(main())
