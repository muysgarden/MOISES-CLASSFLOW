"""Small, authenticated administrator-account popup (not a separate page)."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

import auth
from ui.theme import gradient


def label(value, object_name=None):
    result = QLabel(value)
    if object_name:
        result.setObjectName(object_name)
    return result


def password_field(placeholder):
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setPlaceholderText(placeholder)
    return field


class ProfileDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.sign_out_requested = False
        self.setWindowTitle("ClassFlow — Account Profile")
        self.setObjectName("profileDialog")
        self.setModal(True)
        self.setFixedWidth(470)
        self.setMinimumHeight(450)
        self.setStyleSheet(f"""
            QDialog#profileDialog {{ background: #FFFFFF; }}
            #profileHeader {{ background: {gradient()}; border-radius: 13px; }}
            #profileHeader QLabel {{ color: white; background: transparent; }}
            #profileTitle {{ color: white; font-size: 20px; font-weight: 700; }}
            #profileSubtitle {{ color: #EDF0FF; font-size: 11px; }}
            #profileHeader QLabel#profileAvatar {{ background: rgba(255,255,255,0.20);
                border-radius: 22px; color: white; font-size: 20px; font-weight: 700; }}
            #profileLabel {{ color: #35445B; font-size: 12px; font-weight: 650; }}
            #profileHint {{ color: #718096; font-size: 11px; }}
            #profileMessage {{ background: #EFF5FF; border-radius: 9px;
                color: #2653B3; padding: 9px; font-size: 12px; }}
            QTabWidget::pane {{ border: 1px solid #E4EAF3; border-radius: 10px;
                background: white; }}
            QTabBar::tab {{ background: #F3F6FC; color: #63728A;
                border: none; padding: 10px 20px; margin-right: 6px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }}
            QTabBar::tab:selected {{ background: #E9EFFF; color: #2955CE;
                font-weight: 700; }}
            QLineEdit {{ background: #FFFFFF; border: 1px solid #DCE3F0;
                border-radius: 9px; min-height: 29px; padding: 4px 10px; }}
            QLineEdit:focus {{ border-color: #3479E8; }}
            QPushButton#profileSave {{ background: #2955CE; color: white;
                border: none; border-radius: 9px; padding: 10px 15px; }}
            QPushButton#profileSave:hover {{ background: #3479E8; }}
            QPushButton#profileLogout {{ color: #B34943; background: #FFF2F1;
                border: 1px solid #F5D6D4; border-radius: 9px; padding: 8px 15px; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 17)
        root.setSpacing(13)
        header = QFrame()
        header.setObjectName("profileHeader")
        head = QHBoxLayout(header)
        head.setContentsMargins(18, 17, 18, 17)
        head.setSpacing(12)
        self.avatar = label(username[:1].upper() or "A", "profileAvatar")
        self.avatar.setFixedSize(44, 44)
        self.avatar.setAlignment(Qt.AlignCenter)
        head.addWidget(self.avatar)
        detail = QVBoxLayout()
        detail.setSpacing(3)
        detail.addWidget(label("Account Profile", "profileTitle"))
        self.account_label = label(f"{username} · Administrator", "profileSubtitle")
        detail.addWidget(self.account_label)
        head.addLayout(detail, 1)
        root.addWidget(header)

        tabs = QTabWidget()
        tabs.setObjectName("profileTabs")
        tabs.addTab(self._username_tab(), "Username")
        tabs.addTab(self._password_tab(), "Password")
        root.addWidget(tabs)

        self.message = label("", "profileMessage")
        self.message.setWordWrap(True)
        self.message.hide()
        root.addWidget(self.message)

        bottom = QHBoxLayout()
        logout = QPushButton("Log out")
        logout.setObjectName("profileLogout")
        logout.clicked.connect(self.sign_out)
        bottom.addWidget(logout)
        bottom.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)

    def _field(self, layout, title, widget):
        layout.addWidget(label(title, "profileLabel"))
        layout.addWidget(widget)

    def _username_tab(self):
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(17, 17, 17, 17)
        body.setSpacing(9)
        body.addWidget(label("Change your login username.", "profileHint"))
        self.new_username = QLineEdit(self.username)
        self.new_username.setMaxLength(80)
        self._field(body, "New username", self.new_username)
        self.username_password = password_field("Enter your current password")
        self._field(body, "Current password", self.username_password)
        save = QPushButton("Save username")
        save.setObjectName("profileSave")
        save.clicked.connect(self.save_username)
        body.addWidget(save)
        body.addStretch()
        return page

    def _password_tab(self):
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(17, 17, 17, 17)
        body.setSpacing(9)
        body.addWidget(label("Choose a password with at least 8 characters.", "profileHint"))
        self.current_password = password_field("Current password")
        self._field(body, "Current password", self.current_password)
        self.new_password = password_field("New password")
        self._field(body, "New password", self.new_password)
        self.confirm_password = password_field("Repeat new password")
        self._field(body, "Confirm new password", self.confirm_password)
        save = QPushButton("Update password")
        save.setObjectName("profileSave")
        save.clicked.connect(self.save_password)
        body.addWidget(save)
        body.addStretch()
        return page

    def feedback(self, message, success):
        self.message.setText(message)
        self.message.setStyleSheet(
            "color: #216449; background: #E8F6EE;" if success
            else "color: #B34943; background: #FFF0EE;"
        )
        self.message.show()

    def save_username(self):
        try:
            updated = auth.change_username(
                self.username, self.new_username.text(), self.username_password.text()
            )
        except ValueError as exc:
            self.feedback(str(exc), False)
            return
        self.username = updated
        self.username_password.clear()
        self.account_label.setText(f"{updated} · Administrator")
        self.avatar.setText(updated[:1].upper() or "A")
        self.feedback("Username updated. Use it the next time you log in.", True)

    def save_password(self):
        if self.new_password.text() != self.confirm_password.text():
            self.feedback("New passwords do not match.", False)
            return
        try:
            auth.change_password(
                self.username, self.current_password.text(), self.new_password.text()
            )
        except ValueError as exc:
            self.feedback(str(exc), False)
            return
        for field in (self.current_password, self.new_password, self.confirm_password):
            field.clear()
        self.feedback("Password updated successfully.", True)

    def sign_out(self):
        self.sign_out_requested = True
        self.accept()
