"""Speech bubble that floats above (or below) Momo."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import theme
from .pet_window import make_overlay, overlay_flags

TAIL = 9
MAX_W = 250


class SpeechBubble(QWidget):
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None, overlay_flags() | Qt.WindowType.WindowDoesNotAcceptFocus)
        make_overlay(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setStyleSheet(f"color: {theme.INK}; font-size: 13px; background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.label)
        self._below = False
        self._tail_x = 40.0
        self._anchor: QWidget | None = None
        self.avoid: QWidget | None = None  # e.g. the drawer: never cover it
        self._req_width = 0
        self._hide_timer = QTimer(self, singleShot=True)
        self._hide_timer.timeout.connect(self.hide)

    def say(self, text: str, anchor: QWidget, duration_ms: int = 6000, fixed_width: int | None = None) -> None:
        """duration_ms <= 0 keeps the bubble up until hidden or replaced."""
        self._anchor = anchor
        if fixed_width:
            width = fixed_width
        else:
            fm = QFontMetrics(self.label.font())
            width = min(MAX_W, max(fm.horizontalAdvance(line) for line in text.splitlines() or [""]) + 4)
        same_size = self.label.text().count("\n") == text.count("\n") and self._req_width == width
        self.label.setText(text)
        if not (same_size and self.isVisible()):  # countdown ticks keep their geometry: no jitter
            self._req_width = width
            self.label.setFixedWidth(width)
            self.adjustSize()
            self.reposition()
        if not self.isVisible():
            self.show()
        self.raise_()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)
        else:
            self._hide_timer.stop()

    def reposition(self) -> None:
        if not self._anchor:
            return
        a = self._anchor.frameGeometry()
        screen = (self._anchor.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        if self._req_width and self.label.width() != self._req_width:
            self.label.setFixedWidth(self._req_width)
        self._below = a.top() - self.sizeHint().height() < screen.top() + 4
        self._layout.setContentsMargins(14, 10 + (TAIL if self._below else 0), 14, 10 + (0 if self._below else TAIL))
        self.adjustSize()
        x = a.center().x() - self.width() // 2
        x = max(screen.left() + 6, min(x, screen.right() - self.width() - 6))
        d = self.avoid.frameGeometry() if self.avoid and self.avoid.isVisible() else None
        if d and d.left() < x + self.width() and x < d.right():  # would cover the drawer
            room_right = screen.right() - 6 - (d.right() + 6)
            room_left = (d.left() - 6) - (screen.left() + 6)
            if room_right >= 130 or room_right >= room_left:
                self.label.setFixedWidth(max(100, min(self._req_width or 250, room_right - 30)))
                self.adjustSize()
                x = d.right() + 6
            else:
                self.label.setFixedWidth(max(100, min(self._req_width or 250, room_left - 30)))
                self.adjustSize()
                x = d.left() - 6 - self.width()
        y = a.bottom() - 6 if self._below else a.top() - self.height() + 14
        self._tail_x = max(22.0, min(float(a.center().x() - x), self.width() - 22.0))
        self.move(x, y)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        body = r.adjusted(0, TAIL, 0, 0) if self._below else r.adjusted(0, 0, 0, -TAIL)
        path = QPainterPath()
        path.addRoundedRect(body, 14, 14)
        tail = QPainterPath()
        if self._below:
            tail.moveTo(QPointF(self._tail_x - 8, body.top() + 1))
            tail.lineTo(QPointF(self._tail_x, r.top()))
            tail.lineTo(QPointF(self._tail_x + 8, body.top() + 1))
        else:
            tail.moveTo(QPointF(self._tail_x - 8, body.bottom() - 1))
            tail.lineTo(QPointF(self._tail_x, r.bottom()))
            tail.lineTo(QPointF(self._tail_x + 8, body.bottom() - 1))
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(QColor(theme.SAGE), 1.5))
        p.setBrush(QColor(theme.CREAM))
        p.drawPath(path)

    def mousePressEvent(self, _e) -> None:
        self.hide()
        self.clicked.emit()
