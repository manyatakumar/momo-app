"""Momo — the black pixel cat (tail up, white slit eyes, mid-stride).

The silhouette is stored as filled column spans, traced 1:1 from the Momo logo. Frames are rendered
once, nearest-neighbour scaled (crisp pixels) and cached.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap

W, H = 32, 34
_DX, _DY = -12, -11  # logo grid -> sprite canvas

BODY = QColor("#161616")
EYE = QColor("#FFFFFF")
GLOW = QColor(251, 247, 238, 85)  # soft cream halo so Momo never vanishes on dark wallpapers
GLOW_ON = os.environ.get("MOMO_CAT_GLOW", "1") == "1"

# logo column -> list of (top_row, bottom_row) filled spans (inclusive)
SPANS: dict[int, list[tuple[int, int]]] = {
    14: [(35, 39)], 15: [(32, 40)], 16: [(28, 40)], 17: [(26, 39)], 18: [(24, 37)], 19: [(23, 35)],
    20: [(12, 34)], 21: [(12, 35)], 22: [(12, 35)], 23: [(14, 36)],            # tail rises from here
    24: [(18, 42)], 25: [(22, 43)], 26: [(18, 43)], 27: [(16, 43)], 28: [(15, 42)],  # front leg
    29: [(15, 39)], 30: [(15, 37)], 31: [(16, 37)], 32: [(18, 37)],
    33: [(18, 36)], 34: [(18, 36)], 35: [(18, 36)], 36: [(17, 37)],
    37: [(16, 38)], 38: [(16, 39)], 39: [(16, 30), (32, 39)],                  # notch under the cheek
    40: [(23, 29), (34, 40)], 41: [(36, 40)], 42: [(38, 39)],                  # back leg
}
EYE_COLS = (32, 37)

# Tail sway: overrides of the tail columns' top rows, plus extra pixels.
TAILS = [
    ({}, []),
    ({20: 13, 21: 13, 22: 15, 23: 16}, [(19, r) for r in range(13, 18)]),
    ({20: 14, 21: 12, 22: 12, 23: 12, 24: 14}, []),
]


def _eye_pixels(style: str) -> list[tuple[int, int]]:
    px = []
    for c in EYE_COLS:
        if style in ("open", "alert"):
            px += [(c, 23), (c, 24), (c, 25)]
        elif style == "blink":
            px += [(c, 25)]
        elif style == "happy":     # ^ ^
            px += [(c, 23), (c - 1, 24), (c + 1, 24)]
        elif style == "stare":     # — —  deadpan
            px += [(c - 1, 24), (c, 24), (c + 1, 24)]
    return px


def compose(eyes: str = "open", tail: int = 0) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Return (body pixels, eye pixels) in sprite-canvas coordinates."""
    tops, extra = TAILS[tail]
    body: set[tuple[int, int]] = set()
    for col, spans in SPANS.items():
        for i, (top, bottom) in enumerate(spans):
            if i == 0 and col in tops:
                top = tops[col]
            body.update((col, r) for r in range(top, bottom + 1))
    body.update(extra)
    shift = lambda pts: {(c + _DX, r + _DY) for c, r in pts}  # noqa: E731
    return shift(body), shift(_eye_pixels(eyes))


def render(eyes: str, tail: int, px: int, glow: bool = GLOW_ON) -> QImage:
    body, eye = compose(eyes, tail)
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    if glow:
        for c, r in body:
            for nc, nr in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                if (nc, nr) not in body and 0 <= nc < W and 0 <= nr < H:
                    img.setPixelColor(nc, nr, GLOW)
    for c, r in body:
        img.setPixelColor(c, r, EYE if (c, r) in eye else BODY)
    return img.scaled(W * px, H * px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)


class CatSprites:
    def __init__(self, scale: int, dpr: float = 1.0) -> None:
        self.dpr = dpr
        self.px = max(1, round(scale * dpr))  # whole device pixels per art pixel => crisp edges
        self._cache: dict[tuple[str, int], QPixmap] = {}

    @property
    def logical_w(self) -> int:
        return round(W * self.px / self.dpr)

    @property
    def logical_h(self) -> int:
        return round(H * self.px / self.dpr)

    def frame(self, eyes: str, tail: int) -> QPixmap:
        key = (eyes, tail)
        if key not in self._cache:
            pm = QPixmap.fromImage(render(eyes, tail, self.px))
            pm.setDevicePixelRatio(self.dpr)
            self._cache[key] = pm
        return self._cache[key]


def cat_pixmap(px: int, eyes: str = "open", dpr: float = 1.0) -> QPixmap:
    pm = QPixmap.fromImage(render(eyes, 0, max(1, round(px * dpr)), glow=False))
    pm.setDevicePixelRatio(dpr)
    return pm


def cat_icon() -> QIcon:
    icon = QIcon()
    for px in (1, 2, 4, 8):
        icon.addPixmap(QPixmap.fromImage(render("open", 0, px, glow=True)))
    return icon
