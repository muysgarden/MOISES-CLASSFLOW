"""Non-modal, sliding account drawer for ClassFlow's main workspace."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
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


class AccountDrawer(QFrame):
    """Account settings that stays over the current page, without blocking it."""

    close_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    username_changed = pyqtSignal(str)

    WIDTH = 390

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setObjectName("accountDrawer")
        self.setFixedWidth(self.WIDTH)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet(f"""
            QFrame#accountDrawer {{ background: white; border-left: 1px solid #DFE6F4; }}
            QFrame#accountHeader {{ background: {gradient()}; border: none; }}
            #accountHeader QLabel {{ color: white; background: transparent; }}
            QLabel#accountEyebrow {{ color: #E9E8FF; font-size: 10px; font-weight: 700; }}
            QLabel#accountTitle {{ color: white; font-size: 23px; font-weight: 700; }}
            QLabel#accountSubtitle {{ color: #F1EEFF; font-size: 11px; }}
            QLabel#accountAvatar {{ background: rgba(255,255,255,0.20);
                border-radius: 23px; font-size: 21px; font-weight: 700; }}
            QPushButton#accountClose {{ background: rgba(255,255,255,0.17);
                color: white; border: none; border-radius: 17px;
                font-size: 21px; padding: 0; }}
            QPushButton#accountClose:hover {{ background: rgba(255,255,255,0.30); }}
            QScrollArea#accountScroll, QWidget#accountContent {{ background: #F7F9FD; border: none; }}
            QFrame#accountSection {{ background: white; border: 1px solid #E3EAF4;
                border-radius: 13px; }}
            QLabel#accountSectionTitle {{ color: #1A2C49; font-size: 15px; font-weight: 700; }}
            QLabel#accountHint {{ color: #6D7C93; font-size: 11px; }}
            QLabel#accountFieldLabel {{ color: #344761; font-size: 11px; font-weight: 650; }}
            QLineEdit {{ background: white; border: 1px solid #DAE3F0;
                border-radius: 9px; min-height: 29px; padding: 4px 11px; }}
            QLineEdit:focus {{ border: 1px solid #3479E8; }}
            QPushButton#accountSave {{ background: #2955CE; color: white;
                border: none; border-radius: 10px; padding: 11px 14px; font-weight: 650; }}
            QPushButton#accountSave:hover {{ background: #3479E8; }}
            QLabel#accountMessage {{ border-radius: 8px; padding: 8px 10px;
                font-size: 11px; }}
            QFrame#accountFooter {{ background: white; border-top: 1px solid #E3EAF4; }}
            QPushButton#accountLogout {{ color: #B34943; background: #FFF2F1;
                border: 1px solid #F5D6D4; border-radius: 9px; padding: 9px 14px; }}
            QPushButton#accountLogout:hover {{ background: #FDE6E4; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("accountHeader")
        hv = QVBoxLayout(header)
        hv.setContentsMargins(22, 19, 20, 22)
        hv.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(label("CLASSFLOW / ACCOUNT", "accountEyebrow"))
        top.addStretch()
        close = QPushButton("×")
        close.setObjectName("accountClose")
        close.setFixedSize(34, 34)
        close.setToolTip("Close account settings")
        close.clicked.connect(self.close_requested.emit)
        top.addWidget(close)
        hv.addLayout(top)
        self.title = label("Account settings", "accountTitle")
        hv.addWidget(self.title)
        profile = QHBoxLayout()
        profile.setSpacing(12)
        self.avatar = label(username[:1].upper() or "A", "accountAvatar")
        self.avatar.setFixedSize(46, 46)
        self.avatar.setAlignment(Qt.AlignCenter)
        profile.addWidget(self.avatar)
        identity = QVBoxLayout()
        identity.setSpacing(3)
        self.account_label = label(username, "accountSubtitle")
        identity.addWidget(self.account_label)
        identity.addWidget(label("Administrator · Local account", "accountSubtitle"))
        profile.addLayout(identity, 1)
        hv.addLayout(profile)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("accountScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("accountContent")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(20, 20, 20, 20)
        cv.setSpacing(16)
        cv.addWidget(self._username_section())
        cv.addWidget(self._security_section())
        cv.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("accountFooter")
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(20, 13, 20, 13)
        logout = QPushButton("Log out")
        logout.setObjectName("accountLogout")
        logout.clicked.connect(self.logout_requested.emit)
        foot.addWidget(logout)
        foot.addStretch()
        foot.addWidget(label("Stored on this device", "accountHint"))
        root.addWidget(footer)

    def _section(self, title, description):
        frame = QFrame()
        frame.setObjectName("accountSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(17, 18, 17, 18)
        layout.setSpacing(9)
        layout.addWidget(label(title, "accountSectionTitle"))
        description_label = label(description, "accountHint")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addSpacing(4)
        return frame, layout

    @staticmethod
    def _field(layout, title, widget):
        layout.addWidget(label(title, "accountFieldLabel"))
        layout.addWidget(widget)

    def _username_section(self):
        frame, layout = self._section("Profile details", "Update the name used to sign in.")
        self.new_username = QLineEdit(self.username)
        self.new_username.setMaxLength(80)
        self._field(layout, "Username", self.new_username)
        self.username_password = password_field("Confirm your current password")
        self._field(layout, "Current password", self.username_password)
        save = QPushButton("Save username")
        save.setObjectName("accountSave")
        save.clicked.connect(self.save_username)
        layout.addWidget(save)
        self.username_message = label("", "accountMessage")
        self.username_message.setWordWrap(True)
        self.username_message.hide()
        layout.addWidget(self.username_message)
        return frame

    def _security_section(self):
        frame, layout = self._section("Password & security", "Use at least 8 characters for your new password.")
        self.current_password = password_field("Current password")
        self._field(layout, "Current password", self.current_password)
        self.new_password = password_field("New password")
        self._field(layout, "New password", self.new_password)
        self.confirm_password = password_field("Confirm new password")
        self._field(layout, "Confirm new password", self.confirm_password)
        save = QPushButton("Update password")
        save.setObjectName("accountSave")
        save.clicked.connect(self.save_password)
        layout.addWidget(save)
        self.password_message = label("", "accountMessage")
        self.password_message.setWordWrap(True)
        self.password_message.hide()
        layout.addWidget(self.password_message)
        return frame

    def prepare(self, username):
        """Clear sensitive input whenever the user opens the drawer."""
        self.username = username
        self.new_username.setText(username)
        self.account_label.setText(username)
        self.avatar.setText(username[:1].upper() or "A")
        for field in (self.username_password, self.current_password,
                      self.new_password, self.confirm_password):
            field.clear()
        self.username_message.hide()
        self.password_message.hide()

    def feedback(self, target, message, success):
        target.setText(message)
        target.setStyleSheet(
            "color: #216449; background: #E8F6EE;" if success
            else "color: #B34943; background: #FFF0EE;"
        )
        target.show()

    def save_username(self):
        try:
            updated = auth.change_username(
                self.username, self.new_username.text(), self.username_password.text()
            )
        except ValueError as exc:
            self.feedback(self.username_message, str(exc), False)
            return
        self.username = updated
        self.username_password.clear()
        self.account_label.setText(updated)
        self.avatar.setText(updated[:1].upper() or "A")
        self.username_changed.emit(updated)
        self.feedback(self.username_message, "Username updated successfully.", True)

    def save_password(self):
        if self.new_password.text() != self.confirm_password.text():
            self.feedback(self.password_message, "New passwords do not match.", False)
            return
        try:
            auth.change_password(
                self.username, self.current_password.text(), self.new_password.text()
            )
        except ValueError as exc:
            self.feedback(self.password_message, str(exc), False)
            return
        for field in (self.current_password, self.new_password, self.confirm_password):
            field.clear()
        self.feedback(self.password_message, "Password updated successfully.", True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
