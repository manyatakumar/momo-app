"""Small reusable widgets."""
from __future__ import annotations

import html
import re

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QWidget

from .. import config
from . import theme


def rich(text: str) -> str:
    """Escape, then render **bold** and line breaks."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return out.replace("\n", "<br>")


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def divider() -> QFrame:
    f = QFrame()
    f.setObjectName("Divider")
    return f


def scroll_area(inner: QWidget) -> QScrollArea:
    inner.setObjectName("Transparent")
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    area.setWidget(inner)
    return area


class FunnelProgress(QWidget):
    """Three mini bars: ToFU 2/4 · MoFU 1/3 · BoFU 0/1."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(34)
        self._data = {f: (0, t) for f, t in config.FUNNEL_TARGETS.items()}
        self.setToolTip("This week's funnel slots filled")

    def set_progress(self, data: dict[str, tuple[int, int]]) -> None:
        if data != self._data:
            self._data = data
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = 10
        seg_w = (self.width() - gap * 2) / 3
        small = QFont(self.font())
        small.setPixelSize(11)
        bold = QFont(small)
        bold.setBold(True)
        for i, f in enumerate(config.FUNNELS):
            done, target = self._data.get(f, (0, config.FUNNEL_TARGETS[f]))
            x = i * (seg_w + gap)
            p.setFont(bold)
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(x, 0, seg_w, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f)
            p.setFont(small)
            p.setPen(QColor(theme.SAGE_DARK if done >= target else theme.INK_SOFT))
            p.drawText(QRectF(x, 0, seg_w, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{done}/{target}" + (" ✓" if done >= target else ""))
            bar = QRectF(x, 21, seg_w, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.SAGE_MIST))
            p.drawRoundedRect(bar, 3.5, 3.5)
            if done:
                p.setBrush(QColor(theme.FUNNEL_COLORS[f]))
                p.drawRoundedRect(QRectF(x, 21, seg_w * min(1.0, done / target), 7), 3.5, 3.5)


class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
