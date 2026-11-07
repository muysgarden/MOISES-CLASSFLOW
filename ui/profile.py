"""Full workspace account settings, styled like the ClassFlow dashboard."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QButtonGroup,
    QMessageBox, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)
import auth
import db
from ui.theme import gradient
from ui.appearance import current_mode


def caption(value, name=None):
    widget = QLabel(value)
    if name:
        widget.setObjectName(name)
    return widget


def secret(placeholder):
    widget = QLineEdit()
    widget.setEchoMode(QLineEdit.Password)
    widget.setPlaceholderText(placeholder)
    return widget


class AccountSettingsPage(QWidget):
    """A normal page with an account/security sub-navigation."""
    username_changed = pyqtSignal(str)
    appearance_changed = pyqtSignal(str)

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setObjectName("accountSettingsPage")
        self.setStyleSheet(f"""
            #accountSettingsPage {{ background: #F1F5FC; }}
            #settingsSurface {{ background: white; border: 1px solid #E4EAF3; border-radius: 14px; }}
            #settingsMenu {{ background: white; border-right: 1px solid #E4EAF3; }}
            QLabel#settingsHeading {{ color: #19263B; font-size: 26px; font-weight: 750; }}
            QLabel#settingsSubtitle, QLabel#settingsHint {{ color: #708097; font-size: 12px; }}
            QLabel#settingsSectionTitle {{ color: #19263B; font-size: 20px; font-weight: 700; }}
            QLabel#settingsLabel {{ color: #344761; font-size: 12px; font-weight: 600; }}
            QLabel#settingsAvatar {{ background: #E8EEFF; color: #2955CE; border-radius: 26px;
                font-size: 22px; font-weight: 750; }}
            QPushButton#settingsTab {{ text-align: left; background: transparent; color: #52627A;
                border: none; border-radius: 9px; padding: 13px 10px; font-size: 13px; }}
            QPushButton#settingsTab:hover {{ background: #F1F5FC; }}
            QPushButton#settingsTab:checked {{ background: #EBE8FA; color: #423092; font-weight: 700; }}
            QLineEdit {{ background: white; border: 1px solid #DCE4EE; border-radius: 8px;
                min-height: 30px; padding: 6px 11px; color: #19263B; }}
            QLineEdit:focus {{ border: 1px solid #3479E8; }}
            QPushButton#settingsPrimary {{ background: {gradient()}; color: white; border: none;
                border-radius: 9px; padding: 11px 22px; font-weight: 700; }}
            QPushButton#settingsBack {{ background: white; color: #2955CE; border: 1px solid #BACCF6;
                border-radius: 9px; padding: 10px 21px; }}
            QPushButton#settingsDanger {{ background: #FFF1F0; color: #B33B3B;
                border: 1px solid #F0C6C3; border-radius: 9px; padding: 11px 22px; font-weight: 700; }}
            QPushButton#settingsDanger:disabled {{ color: #9FA8B7; background: #F4F6F9; border-color: #E4EAF3; }}
            QLabel#settingsMessage {{ border-radius: 8px; padding: 10px; font-size: 12px; }}
            QScrollArea#settingsScroll {{ background: white; border: none; }}
            QWidget#settingsBody {{ background: white; }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 28)
        outer.setSpacing(18)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        titles.addWidget(caption("Settings", "settingsHeading"))
        titles.addWidget(caption("Manage your ClassFlow administrator account.", "settingsSubtitle"))
        heading.addLayout(titles)
        heading.addStretch()
        back = QPushButton("Back to dashboard")
        back.setObjectName("settingsBack")
        back.clicked.connect(self._go_back)
        heading.addWidget(back)
        outer.addLayout(heading)

        surface = QFrame()
        surface.setObjectName("settingsSurface")
        shell = QHBoxLayout(surface)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        menu = QFrame()
        menu.setObjectName("settingsMenu")
        menu.setFixedWidth(240)
        ml = QVBoxLayout(menu)
        ml.setContentsMargins(14, 24, 14, 20)
        ml.setSpacing(8)
        self.tabs = {}
        for key, title in (("account", "My account"),
                           ("security", "Security"),
                           ("appearance", "Appearance"),
                           ("data", "Data management")):
            button = QPushButton(title)
            button.setObjectName("settingsTab")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, name=key: self.set_tab(name))
            ml.addWidget(button)
            self.tabs[key] = button
        ml.addStretch()
        shell.addWidget(menu)
        self.sections = QStackedWidget()
        self.sections.addWidget(self._account_section())
        self.sections.addWidget(self._security_section())
        self.sections.addWidget(self._appearance_section())
        self.sections.addWidget(self._data_section())
        shell.addWidget(self.sections, 1)
        outer.addWidget(surface, 1)
        self.set_tab("account")

    def _go_back(self):
        window = self.window()
        if hasattr(window, "go"):
            window.go("dashboard")

    def _section(self, heading, description):
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("settingsBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(34, 30, 34, 32)
        layout.setSpacing(12)
        layout.addWidget(caption(heading, "settingsSectionTitle"))
        layout.addWidget(caption(description, "settingsHint"))
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #E4EAF3; margin: 12px 0;")
        layout.addWidget(divider)
        scroll.setWidget(body)
        return scroll, layout

    @staticmethod
    def _field(layout, title, field):
        layout.addWidget(caption(title, "settingsLabel"))
        layout.addWidget(field)
        layout.addSpacing(9)

    def _account_section(self):
        scroll, layout = self._section("Account", "Your sign-in details and account information.")
        identity = QHBoxLayout()
        self.avatar = caption(self.username[:1].upper() or "A", "settingsAvatar")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(52, 52)
        identity.addWidget(self.avatar)
        names = QVBoxLayout()
        self.account_label = caption(self.username, "settingsSectionTitle")
        names.addWidget(self.account_label)
        names.addWidget(caption("Administrator · Local account", "settingsHint"))
        identity.addLayout(names)
        identity.addStretch()
        layout.addLayout(identity)
        layout.addSpacing(18)
        self.new_username = QLineEdit(self.username)
        self.new_username.setMaxLength(80)
        self._field(layout, "Username", self.new_username)
        layout.addWidget(caption("Confirm with your current password to save changes.", "settingsHint"))
        self.username_password = secret("Current password")
        self._field(layout, "Current password", self.username_password)
        save = QPushButton("Save changes")
        save.setObjectName("settingsPrimary")
        save.clicked.connect(self.save_username)
        layout.addWidget(save, 0, Qt.AlignRight)
        self.username_message = caption("", "settingsMessage")
        self.username_message.setWordWrap(True)
        self.username_message.hide()
        layout.addWidget(self.username_message)
        layout.addStretch()
        return scroll

    def _security_section(self):
        scroll, layout = self._section("Security", "Change your password to keep your account secure.")
        self.current_password = secret("Current password")
        self._field(layout, "Current password", self.current_password)
        self.new_password = secret("At least 8 characters")
        self._field(layout, "New password", self.new_password)
        self.confirm_password = secret("Confirm new password")
        self._field(layout, "Confirm new password", self.confirm_password)
        save = QPushButton("Update password")
        save.setObjectName("settingsPrimary")
        save.clicked.connect(self.save_password)
        layout.addWidget(save, 0, Qt.AlignRight)
        self.password_message = caption("", "settingsMessage")
        self.password_message.setWordWrap(True)
        self.password_message.hide()
        layout.addWidget(self.password_message)
        layout.addStretch()
        return scroll

    def _appearance_section(self):
        scroll, layout = self._section(
            "Appearance", "Choose how ClassFlow looks on this device."
        )
        description = caption(
            "Changes apply immediately and are remembered when you reopen the app.",
            "settingsHint"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.appearance_group = QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        self.appearance_buttons = {}
        for name, title, detail in (
            ("light", "☀  Light mode", "Soft blue-white workspace"),
            ("dark", "☾  Dark mode", "Low-glare navy workspace"),
        ):
            choice = QPushButton(f"{title}   ·   {detail}")
            choice.setObjectName("settingsTab")
            choice.setCheckable(True)
            choice.setMinimumHeight(58)
            choice.clicked.connect(
                lambda _=False, selected=name: self._choose_appearance(selected)
            )
            self.appearance_group.addButton(choice)
            self.appearance_buttons[name] = choice
            layout.addWidget(choice)
        layout.addStretch()
        self.refresh_appearance()
        return scroll

    def refresh_appearance(self):
        selected = current_mode()
        if hasattr(self, "appearance_buttons"):
            for name, button in self.appearance_buttons.items():
                button.setChecked(name == selected)

    def _choose_appearance(self, mode):
        self.appearance_changed.emit(mode)
        self.refresh_appearance()

    def _data_section(self):
        scroll, layout = self._section(
            "Data management", "Remove demonstration records when testing is complete."
        )
        self.demo_count = caption("", "settingsSectionTitle")
        layout.addWidget(self.demo_count)
        warning = caption(
            "Only records explicitly marked when ClassFlow created its demo dataset "
            "are eligible. Existing records from older versions are not assumed to be samples. "
            "If you've edited a sample or connected real records to it, cleanup will stop "
            "without deleting anything.",
            "settingsHint",
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addSpacing(14)
        self.clear_samples_button = QPushButton("Clear tracked sample data")
        self.clear_samples_button.setObjectName("settingsDanger")
        self.clear_samples_button.clicked.connect(self.clear_samples)
        layout.addWidget(self.clear_samples_button, 0, Qt.AlignLeft)
        self.data_message = caption("", "settingsMessage")
        self.data_message.setWordWrap(True)
        self.data_message.hide()
        layout.addWidget(self.data_message)
        layout.addStretch()
        return scroll

    def refresh_samples(self):
        count = db.sample_count()
        self.demo_count.setText(f"{count} tracked demonstration records")
        self.clear_samples_button.setEnabled(count > 0)

    def clear_samples(self):
        count = db.sample_count()
        if not count:
            self.refresh_samples()
            return
        answer = QMessageBox.question(
            self, "Remove demonstration records?",
            f"Remove {count} tagged demo records and their original subject-program links?\n"
            "This cannot be undone. Your manually entered records will be protected; "
            "cleanup will stop if any dependencies are unsafe.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            removed = db.clear_sample_data()
        except ValueError as exc:
            self.feedback(self.data_message, str(exc), False)
            return
        self.feedback(self.data_message, f"Removed {removed} tagged demo records.", True)
        self.refresh_samples()
        window = self.window()
        if hasattr(window, "reload_terms"):
            window.reload_terms()

    def set_tab(self, tab):
        for key, button in self.tabs.items():
            button.setChecked(key == tab)
        self.sections.setCurrentIndex({"account": 0, "security": 1, "appearance": 2, "data": 3}[tab])
        if tab == "data":
            self.refresh_samples()
        elif tab == "appearance":
            self.refresh_appearance()

    def prepare(self, username):
        self.username = username
        self.new_username.setText(username)
        self.account_label.setText(username)
        self.avatar.setText(username[:1].upper() or "A")
        for field in (self.username_password, self.current_password,
                      self.new_password, self.confirm_password):
            field.clear()
        self.username_message.hide()
        self.password_message.hide()
        self.set_tab("account")

    @staticmethod
    def feedback(target, message, success):
        target.setText(message)
        target.setStyleSheet("color: #216449; background: #E8F6EE;" if success
                             else "color: #B34943; background: #FFF0EE;")
        target.show()

    def save_username(self):
        try:
            updated = auth.change_username(self.username, self.new_username.text(),
                                           self.username_password.text())
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
            auth.change_password(self.username, self.current_password.text(),
                                 self.new_password.text())
        except ValueError as exc:
            self.feedback(self.password_message, str(exc), False)
            return
        for field in (self.current_password, self.new_password, self.confirm_password):
            field.clear()
        self.feedback(self.password_message, "Password updated successfully.", True)
