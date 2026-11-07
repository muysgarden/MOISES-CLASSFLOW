from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QColor, QPainterPath, QIcon, QPen
from PyQt5.QtWidgets import (QDialog, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
                           QLineEdit, QPushButton, QGraphicsScene,
                           QGraphicsPixmapItem, QGraphicsBlurEffect)
import auth
from ui.theme import gradient

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



class FrostedGlass(QFrame):
    """Frosted crop of the existing login background, not a separate image."""

    def __init__(self, background, parent=None):
        super().__init__(parent)
        self.background = background
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._blurred = QPixmap()
        self._cache_key = None

    def _background_crop(self):
        bg = self.background
        if bg.photo.isNull() or self.width() <= 0 or self.height() <= 0:
            return QPixmap()
        scaled = bg.photo.scaled(
            bg.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        position = self.mapTo(bg, QPoint(0, 0))
        x = position.x() + (scaled.width() - bg.width()) // 2
        y = position.y() + (scaled.height() - bg.height()) // 2
        return scaled.copy(x, y, self.width(), self.height())

    def paintEvent(self, event):
        bg = self.background
        position = self.mapTo(bg, QPoint(0, 0))
        key = (self.width(), self.height(), bg.width(), bg.height(),
               position.x(), position.y())
        if key != self._cache_key:
            self._cache_key = key
            source = self._background_crop()
            self._blurred = QPixmap()
            if not source.isNull():
                scene = QGraphicsScene()
                scene.setSceneRect(QRectF(source.rect()))
                item = QGraphicsPixmapItem(source)
                effect = QGraphicsBlurEffect()
                effect.setBlurRadius(18)
                item.setGraphicsEffect(effect)
                scene.addItem(item)
                self._blurred = QPixmap(source.size())
                self._blurred.fill(Qt.transparent)
                output = QPainter(self._blurred)
                scene.render(output, QRectF(self._blurred.rect()),
                             QRectF(source.rect()))
                output.end()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Only OUTER left corners are rounded. The edge touching the login
        # form must remain square and flush; rounding both sides created the
        # visible dark strip in the middle of the login card.
        w, h = float(self.width()), float(self.height())
        radius = min(12.0, w / 4, h / 4)
        clip = QPainterPath()
        clip.moveTo(radius, 0)
        clip.lineTo(w, 0)
        clip.lineTo(w, h)
        clip.lineTo(radius, h)
        clip.quadTo(0, h, 0, h-radius)
        clip.lineTo(0, radius)
        clip.quadTo(0, 0, radius, 0)
        clip.closeSubpath()
        painter.setClipPath(clip)
        if not self._blurred.isNull():
            painter.drawPixmap(self.rect(), self._blurred)
        # Fill the right edge without any transparent rounded gap.
        painter.fillRect(self.rect(), QColor(26, 39, 67, 100))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(243, 249, 255, 105), 1.0))
        painter.setBrush(Qt.NoBrush)
        # Draw borders only around the outer edges, not at the shared join.
        outline = QPainterPath()
        outline.moveTo(w-1, 0.5)
        outline.lineTo(radius, 0.5)
        outline.quadTo(0.5, 0.5, 0.5, radius)
        outline.lineTo(0.5, h-radius)
        outline.quadTo(0.5, h-0.5, radius, h-0.5)
        outline.lineTo(w-1, h-0.5)
        painter.drawPath(outline)
        painter.end()


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ClassFlow')
        # Maximized keeps the normal Windows title bar controls available.
        # True fullscreen/frameless mode hides minimize and maximize buttons.
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )
        self.setWindowState(self.windowState() | Qt.WindowMaximized)
        self.resize(1100, 660)
        self.setMinimumSize(640, 420)
        self.first = not auth.has_users()
        self.failures = 0
        self.setStyleSheet('''
            QDialog { background:#202020; }
            QLabel { color:#fff; background:transparent; font-size:12px; }
            QFrame#loginPanel { background:#202020; border-top-right-radius:12px; border-bottom-right-radius:12px; }
            QLabel#loginTitle { font-size:34px; font-weight:700; }
            QLabel#loginSub { color:#B7B7B7; font-size:12px; }
            QLineEdit { background:#444; color:white; border:1px solid #777; border-radius:12px; min-height:39px; padding:0 14px; }
            QPushButton#loginButton { background:#6021b5; color:white; border:1px solid #8246ca; border-radius:16px; padding:9px; }
            QPushButton#eye { background:transparent; border:0; color:#bbb; padding:0; min-width:26px; }
            QLabel#error { color:#efb8b8; background:#421d20; padding:8px; font-size:10px; }
        ''')
        # Preserve the split-photo login the user prefers, while carrying the
        # same blue-to-purple accent into the new dashboard.
        self.setStyleSheet(self.styleSheet() + f'''
            QPushButton#loginButton {{
                background: {gradient()};
                border: none; border-radius: 15px;
                min-height: 33px; font-weight: 700;
            }}
            QPushButton#loginButton:hover {{
                background: {gradient("#3D86F4", "#AB4CF0")};
            }}
            QLineEdit:focus {{ border: 1px solid #7F6BE5; }}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bg = Photo('background.jpg')
        root.addWidget(bg, 1)
        outer = QVBoxLayout(bg); outer.addStretch()
        center = QHBoxLayout(); center.addStretch()
        # A roomier card on typical desktops, while smaller screens can
        # still shrink the width without clipping the form.
        card = QFrame()
        card.setObjectName('loginCard')
        card.setMinimumHeight(410)
        card.setMaximumWidth(820)
        # A single continuous backing surface prevents any black gap between
        # the glass on the left and the dark form on the right.
        card.setStyleSheet('QFrame#loginCard { background:#202020; border:0; border-radius:12px; }')
        self.login_card = card
        row = QHBoxLayout(card); row.setContentsMargins(0,0,0,0); row.setSpacing(0)
        photo = FrostedGlass(bg)
        self.login_photo = photo
        pl = QVBoxLayout(photo); pl.addStretch()
        logo = QLabel(); logo.setAlignment(Qt.AlignCenter)
        pix = QPixmap(str(ASSETS/'logo.png')) if (ASSETS/'logo.png').exists() else QPixmap()
        if not pix.isNull():
            logo.setPixmap(pix.scaled(152,152,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            logo.setText('CF'); logo.setStyleSheet('font-size:44px; font-weight:700; color:#ddd')
        pl.addWidget(logo); pl.addStretch(); row.addWidget(photo)
        panel = QFrame(); panel.setObjectName('loginPanel'); row.addWidget(panel,1)
        form = QVBoxLayout(panel); form.setContentsMargins(38,34,38,34); form.setSpacing(11)
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
        form.addStretch()
        center.addWidget(card)
        center.addStretch()
        outer.addLayout(center)
        outer.addStretch()
        self._resize_login_card()

    def _resize_login_card(self):
        """Size the *actual* centered card, not only its maximum width."""
        if not hasattr(self, 'login_card'):
            return
        available = max(0, self.width() - 48)
        width = min(820, available)
        if width <= 0:
            return
        if self.login_card.width() != width:
            self.login_card.setFixedWidth(width)
        # Keep the photo around 30% so the input panel has real breathing room.
        photo_width = min(320, max(150, int(width * .30)))
        if self.login_photo.width() != photo_width:
            self.login_photo.setFixedWidth(photo_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_login_card()

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
