"""The sleek drawer that opens when you click Momo."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout,
                             QWidget)

from .. import scheduler, writer
from . import theme
from .calendar_page import CalendarPage
from .chat_page import ChatPage
from .insights_page import InsightsPage
from .sprites import cat_pixmap
from .widgets import FunnelProgress, label

PAGES = ("chat", "week", "insights")


class Drawer(QWidget):
    focus_requested = pyqtSignal()
    setup_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Momo")
        self.setFixedSize(420, 650)
        self._drag: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

        # header: pixel Momo + name + engine status
        self._header = QFrame()
        self._header.setObjectName("Header")
        head = QHBoxLayout(self._header)
        head.setContentsMargins(12, 8, 10, 8)
        head.setSpacing(12)
        self._cat = QLabel()
        self._cat.setFixedSize(64, 68)
        self.set_cat("open")
        head.addWidget(self._cat)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addStretch(1)
        titles.addWidget(label("momo", "Title"))
        titles.addWidget(label("your content hype-cat", "Subtitle"))
        self.status = label("", "Status")
        titles.addWidget(self.status)
        titles.addStretch(1)
        head.addLayout(titles)
        head.addStretch(1)
        close = QPushButton("✕")
        close.setObjectName("IconButton")
        close.setToolTip("Close (Esc)")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.close_drawer)
        head.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._header)

        self.progress = FunnelProgress()
        root.addWidget(self.progress)

        # nav
        bar = QFrame()
        bar.setObjectName("NavBar")
        nav = QHBoxLayout(bar)
        nav.setContentsMargins(4, 4, 4, 4)
        nav.setSpacing(4)
        self._nav = QButtonGroup(self)
        for i, (key, text) in enumerate((("chat", "💬 Brain dump"), ("week", "🗓 Week"), ("insights", "📈 Insights"))):
            b = QPushButton(text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav.addButton(b, i)
            nav.addWidget(b)
        nav.addStretch(1)
        focus = QPushButton("⏱")
        focus.setObjectName("Nav")
        focus.setToolTip("Focus mode — Momo stares until you finish")
        focus.setCursor(Qt.CursorShape.PointingHandCursor)
        focus.clicked.connect(self.focus_requested.emit)
        nav.addWidget(focus)
        root.addWidget(bar)

        self.stack = QStackedWidget()
        self.chat = ChatPage()
        self.week = CalendarPage()
        self.insights = InsightsPage()
        for page in (self.chat, self.week, self.insights):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        self._nav.idClicked.connect(lambda i: self.show_page(PAGES[i]))
        self.chat.data_changed.connect(self.refresh)
        self.chat.busy_changed.connect(lambda busy: self.set_status("✍️ writing…" if busy else None))
        self.set_status(None)
        self.week.data_changed.connect(self.refresh)
        self.week.request_chat.connect(lambda: self.show_page("chat"))
        self.insights.request_setup.connect(self.setup_requested.emit)
        self.show_page("chat")
        self.refresh_progress()

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_cat(self, eyes: str) -> None:
        self._cat.setPixmap(cat_pixmap(2, eyes, self.devicePixelRatioF()))

    def set_status(self, text: str | None) -> None:
        if text is None:
            text = (f"✨ AI drafts on ({writer.ENGINE_LABEL[writer.provider()]})" if writer.ai_available()
                    else "● offline drafts")
        self.status.setText(text)

    # ------------------------------------------------------------ pages / data
    def show_page(self, name: str) -> None:
        idx = PAGES.index(name)
        self.stack.setCurrentIndex(idx)
        self._nav.button(idx).setChecked(True)
        if name == "week":
            self.week.refresh()
        elif name == "chat":
            self.chat.focus_input()

    def refresh_progress(self) -> None:
        self.progress.set_progress(scheduler.week_progress(scheduler.week_start(date.today())))

    def refresh(self) -> None:
        self.refresh_progress()
        if self.stack.currentWidget() is self.week:
            self.week.refresh()

    def refresh_all(self) -> None:
        self.refresh_progress()
        self.week.refresh()
        self.insights.refresh()

    # ------------------------------------------------------------ show / hide
    def place_near(self, pet: QWidget) -> None:
        g = pet.frameGeometry()
        screen = (pet.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        x = g.left() - self.width() - 10
        if x < screen.left() + 8:
            x = g.right() + 10
        x = max(screen.left() + 8, min(x, screen.right() - self.width() - 8))
        y = max(screen.top() + 8, min(g.bottom() - self.height(), screen.bottom() - self.height() - 8))
        self.move(x, y)

    def open(self, pet: QWidget, page: str | None = None) -> None:
        if page:
            self.show_page(page)
        self.refresh_all()
        if not self.isVisible():
            self.place_near(pet)
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.stop()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        self.raise_()
        self.activateWindow()
        if self.stack.currentWidget() is self.chat:
            self.chat.focus_input()

    def close_drawer(self) -> None:
        self.hide()

    def toggle(self, pet: QWidget) -> None:
        if self.isVisible():
            self.close_drawer()
        else:
            self.open(pet)

    # ------------------------------------------------------------ chrome
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 20, 20)
        p.setPen(QPen(QColor(theme.BORDER), 1.2))
        p.setBrush(QColor(theme.CREAM))
        p.drawPath(path)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.close_drawer()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < self._header.geometry().bottom():
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e) -> None:
        self._drag = None
