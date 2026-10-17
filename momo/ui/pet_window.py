"""The transparent, always-on-top window Momo lives in."""
from __future__ import annotations

import random
import sys

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter
from PyQt6.QtWidgets import QWidget

from .sprites import CatSprites

TICK_MS = 140
BOUNCE = (0, -3, -6, -8, -6, -3, 0)


def overlay_flags() -> Qt.WindowType:
    return (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)


def make_overlay(w: QWidget) -> None:
    """Transparent, borderless, never steals focus, never hides when the app loses focus (macOS)."""
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    if sys.platform == "darwin":
        w.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)


class PetWindow(QWidget):
    clicked = pyqtSignal()
    hovered = pyqtSignal()
    moved = pyqtSignal()
    drag_finished = pyqtSignal()
    context_requested = pyqtSignal(QPoint)

    MODES = ("idle", "happy", "stare", "alert", "sleep")

    def __init__(self, scale: int) -> None:
        super().__init__(None, overlay_flags())
        make_overlay(self)
        self.setWindowTitle("Momo")
        screen = QGuiApplication.primaryScreen()
        self.sprites = CatSprites(scale, screen.devicePixelRatio() if screen else 1.0)
        self._head = 10  # headroom for the happy bounce
        self.setFixedSize(self.sprites.logical_w, self.sprites.logical_h + self._head + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.mode = "idle"
        self._tick = 0
        self._tail = 0
        self._blink = 0
        self._bounce_i = -1
        self._mode_ticks = 0  # >0: revert to idle after N ticks
        self._frame_key: tuple | None = None
        self._press: QPoint | None = None
        self._drag_offset = QPoint()
        self._dragging = False

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._advance)
        self._timer.start(TICK_MS)

    # ----------------------------------------------------------- state
    def set_mode(self, mode: str, seconds: float = 0) -> None:
        self.mode = mode
        self._mode_ticks = int(seconds * 1000 / TICK_MS) if seconds else 0
        if mode in ("happy", "alert"):
            self._bounce_i = 0
        self._advance(force=True)

    def _eyes(self) -> str:
        if self.mode == "happy":
            return "happy"
        if self.mode == "sleep" or self._blink:
            return "blink"
        if self.mode == "stare":
            return "stare"
        return "open"

    def _advance(self, force: bool = False) -> None:
        self._tick += 1
        if self._mode_ticks:
            self._mode_ticks -= 1
            if self._mode_ticks == 0:
                self.mode = "idle"

        tail_every = {"alert": 2, "happy": 2, "stare": 14, "sleep": 30}.get(self.mode, 6)
        if self._tick % tail_every == 0:
            self._tail = (self._tail + 1) % 3 if self.mode != "stare" else (0 if self._tail else 1)

        if self._blink:
            self._blink -= 1
        elif self.mode in ("idle", "alert") and random.random() < 0.03:
            self._blink = 1

        offset = 0
        if self._bounce_i >= 0:
            offset = BOUNCE[self._bounce_i]
            self._bounce_i += 1
            if self._bounce_i >= len(BOUNCE):
                self._bounce_i = 0 if (self.mode == "alert" and self._mode_ticks) else -1

        key = (self._eyes(), self._tail, offset)
        if force or key != self._frame_key:  # only repaint when something visibly changed
            self._frame_key = key
            self.update()

    def paintEvent(self, _event) -> None:
        eyes, tail, offset = self._frame_key or ("open", 0, 0)
        p = QPainter(self)
        w = self.sprites.logical_w
        # soft contact shadow under the paws, shrinks while Momo is mid-hop
        shrink = abs(offset) * 1.5
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(40, 48, 38, 45))
        p.drawEllipse(QRectF(w * 0.08 + shrink, self.height() - 12, w * 0.86 - 2 * shrink, 9))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.drawPixmap(0, self._head + offset, self.sprites.frame(eyes, tail))

    # ----------------------------------------------------------- placement
    def snap_to_corner(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        self.move(g.right() - self.width() - 28, g.bottom() - self.height() - 4)
        self.moved.emit()

    def restore_position(self, x: int, y: int) -> bool:
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().adjusted(-20, -20, 20, 20).contains(QPoint(x + self.width() // 2, y + self.height() // 2)):
                self.move(x, y)
                return True
        return False

    # ----------------------------------------------------------- input
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._drag_offset = self._press - self.frameGeometry().topLeft()
            self._dragging = False
        elif e.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e) -> None:
        if self._press is None:
            return
        pos = e.globalPosition().toPoint()
        if not self._dragging and (pos - self._press).manhattanLength() > 4:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        if self._dragging:
            self.move(pos - self._drag_offset)
            self.moved.emit()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        if self._dragging:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.drag_finished.emit()
        else:
            self.clicked.emit()
        self._press = None
        self._dragging = False

    def enterEvent(self, _e) -> None:
        self.hovered.emit()
