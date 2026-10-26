from pathlib import Path
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPixmap, QColor, QPainterPath, QIcon, QPen
from PyQt5.QtWidgets import QDialog, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton
import auth

ASSETS = Path(__file__).resolve().parent.parent / 'assets'


class Photo(QFrame):
    def __init__(self, filename, shade=0, parent=None):
        super().__init__(parent)
        self.photo = QPixmap(str(ASSETS / filename)) if (ASSETS / filename).exists() else QPixmap()
        self.shade = shade

    def paintEvent(self, event):
        p = QPainter(self)
        if self.property('rounded'):
            clip=QPainterPath(); clip.addRoundedRect(0,0,self.width()+12,self.height(),12,12); p.setClipPath(clip)
        p.fillRect(self.rect(), QColor('#3c424d'))
        if not self.photo.isNull():
            pix = self.photo.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width()-pix.width())//2, (self.height()-pix.height())//2, pix)
        if self.shade:
            p.fillRect(self.rect(), QColor(20, 23, 30, self.shade))


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ClassFlow — Login')
        self.resize(1100, 660)
        self.setMinimumSize(760, 480)
        self.first = not auth.has_users()
        self.failures = 0
        self.setStyleSheet('''
            QDialog { background:#202020; }
            QLabel { color:#fff; background:transparent; font-size:11px; }
            QFrame#loginPanel { background:#202020; border-top-right-radius:12px; border-bottom-right-radius:12px; }
            QLabel#loginTitle { font-size:29px; font-weight:700; }
            QLabel#loginSub { color:#999; font-size:11px; }
            QLineEdit { background:#444; color:white; border:1px solid #777; border-radius:14px; min-height:32px; padding:0 12px; }
            QPushButton#loginButton { background:#6021b5; color:white; border:1px solid #8246ca; border-radius:16px; padding:9px; }
            QPushButton#eye { background:transparent; border:0; color:#bbb; padding:0; min-width:26px; }
            QLabel#error { color:#efb8b8; background:#421d20; padding:8px; font-size:10px; }
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 10, 20, 20)
        cap = QLabel('Login'); cap.setStyleSheet('color:#888; font-size:14px')
        root.addWidget(cap)
        bg = Photo('background.jpg')
        root.addWidget(bg, 1)
        outer = QVBoxLayout(bg); outer.addStretch()
        center = QHBoxLayout(); center.addStretch()
        card = QFrame(); card.setFixedSize(610, 360)
        row = QHBoxLayout(card); row.setContentsMargins(0,0,0,0); row.setSpacing(0)
        photo = Photo('building.jpg', 95); photo.setFixedWidth(248); photo.setProperty('rounded',True)
        pl = QVBoxLayout(photo); pl.addStretch()
        logo = QLabel(); logo.setAlignment(Qt.AlignCenter)
        pix = QPixmap(str(ASSETS/'logo.png')) if (ASSETS/'logo.png').exists() else QPixmap()
        if not pix.isNull():
            logo.setPixmap(pix.scaled(128,128,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            logo.setText('CF'); logo.setStyleSheet('font-size:44px; font-weight:700; color:#ddd')
        pl.addWidget(logo); pl.addStretch(); row.addWidget(photo)
        panel = QFrame(); panel.setObjectName('loginPanel'); row.addWidget(panel,1)
        form = QVBoxLayout(panel); form.setContentsMargins(28,24,28,24); form.setSpacing(8)
        title = QLabel('ClassFlow'); title.setObjectName('loginTitle'); form.addWidget(title)
        sub = QLabel('Classroom Scheduling & Academic Timetabling'); sub.setObjectName('loginSub'); form.addWidget(sub)
        hint = QLabel('Create your administrator account.' if self.first else 'Sign in to manage academic records and schedules.')
        hint.setObjectName('loginSub'); hint.setWordWrap(True); form.addWidget(hint)
        line=QFrame(); line.setFixedHeight(1); line.setStyleSheet('background:#444'); form.addWidget(line)
        self.error = QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True); self.error.hide(); form.addWidget(self.error)
        form.addWidget(QLabel('USERNAME'))
        self.username=QLineEdit(); self.username.setAccessibleName('Username'); form.addWidget(self.username)
        form.addWidget(QLabel('PASSWORD'))
        self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setAccessibleName('Password')
        icon=QPixmap(20,20); icon.fill(Qt.transparent)
        painter=QPainter(icon); painter.setRenderHint(QPainter.Antialiasing); painter.setPen(QPen(QColor('#aaa'),1.2)); painter.drawEllipse(2,6,16,8); painter.drawEllipse(8,8,4,4); painter.end()
        eye=self.password.addAction(QIcon(icon),QLineEdit.TrailingPosition); eye.setToolTip('Show / hide password'); eye.triggered.connect(self.toggle_password); form.addWidget(self.password)
        self.submit=QPushButton('CREATE ACCOUNT' if self.first else 'LOGIN'); self.submit.setObjectName('loginButton'); self.submit.clicked.connect(self.login); form.addWidget(self.submit)
        self.password.returnPressed.connect(self.login); self.username.returnPressed.connect(self.password.setFocus)
        form.addStretch(); center.addWidget(card); center.addStretch(); outer.addLayout(center); outer.addStretch()

    def toggle_password(self):
        self.password.setEchoMode(QLineEdit.Normal if self.password.echoMode()==QLineEdit.Password else QLineEdit.Password)

    def login(self):
        if not self.submit.isEnabled():
            return
        try:
            if self.first:
                auth.create(self.username.text(), self.password.text())
            elif not auth.verify(self.username.text(), self.password.text()):
                raise ValueError('Incorrect username or password. Please try again.')
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc)); self.error.show()
            self.failures += 1
            if self.failures >= 5:
                self.submit.setEnabled(False)
                QTimer.singleShot(30000, lambda: self.submit.setEnabled(True))
