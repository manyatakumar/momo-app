"""Focus mode (the deadpan stare) and pester mode (missing-slot nags)."""
from __future__ import annotations

import math
import time
from datetime import date, datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import config, db, scheduler

if TYPE_CHECKING:
    from .app import MomoApp

FOCUS_LINES = (
    "{m} minutes left, stop looking at me and finish this draft!",
    "{m} minutes. I'm not blinking until that draft exists.",
    "Still {m} minutes. The cursor misses you.",
    "{m} minutes. LinkedIn will still be there. Your draft won't write itself.",
    "{m} minutes. I can hear you thinking about your phone.",
    "{m} minutes. Write the ugly first draft. Pretty comes later.",
)
SCOLDS = (
    "Eyes on the draft, not on me.",
    "Nope. Back to work.",
    "I'm a cat, not a distraction. Well. I'm both. Go.",
    "Staring contest? You'll lose. Write.",
)


class FocusController(QObject):
    changed = pyqtSignal(bool)

    def __init__(self, app: "MomoApp") -> None:
        super().__init__()
        self.app = app
        self._end = 0.0
        self._total = 0
        self._scold_until = 0.0
        self._scold_i = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def remaining(self) -> int:
        return max(0, int(round(self._end - time.monotonic())))

    def start(self, minutes: int) -> None:
        self._total = minutes * 60
        self._end = time.monotonic() + self._total
        self._scold_until = 0
        self.app.pet.set_mode("stare")
        self.app.drawer.set_cat("stare")
        self._timer.start()
        self._tick()
        self.changed.emit(True)

    def stop(self, completed: bool = False) -> None:
        if not self.active:
            return
        self._timer.stop()
        self.app.drawer.set_cat("open")
        self.app.drawer.set_status(None)
        self.changed.emit(False)
        if completed:
            self.app.pet.set_mode("happy", seconds=6)
            msg = "🎉 TIME! You did it. Paste the draft in and mark it drafted in your Week view."
            self.app.say(msg, 10000)
            self.app.notify("Focus session done", msg)
        else:
            self.app.pet.set_mode("idle")
            self.app.say("Fine. Focus ended. I'll pretend I didn't see that. 😼", 4000)

    def scold(self) -> None:
        if not self.active:
            return
        self._scold_until = time.monotonic() + 3
        self._scold_i = (self._scold_i + 1) % len(SCOLDS)
        self._tick()

    def _tick(self) -> None:
        rem = self.remaining()
        if rem <= 0:
            self.stop(completed=True)
            return
        clock = f"⏱ {rem // 60:02d}:{rem % 60:02d}"
        if time.monotonic() < self._scold_until:
            line = SCOLDS[self._scold_i]
        else:
            elapsed_min = (self._total - rem) // 60
            line = FOCUS_LINES[elapsed_min % len(FOCUS_LINES)].format(m=math.ceil(rem / 60))
        self.app.say(f"{clock}\n{line}", 0, fixed_width=230)
        self.app.drawer.set_status(f"{clock} · focus mode")
        if self.app.pet.mode != "stare":
            self.app.pet.set_mode("stare")


class PesterController(QObject):
    def __init__(self, app: "MomoApp") -> None:
        super().__init__()
        self.app = app
        self._last_nag: dict[str, float] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, config.PESTER_INTERVAL_MIN) * 60_000)
        self._timer.timeout.connect(self.check)
        self._timer.start()
        QTimer.singleShot(90_000, self.check)  # first check shortly after launch

    @staticmethod
    def quiet_now() -> bool:
        h = datetime.now().hour
        s, e = config.QUIET_START, config.QUIET_END
        return (h >= s or h < e) if s > e else (s <= h < e)

    def check(self, force: bool = False) -> bool:
        if not force and (self.app.focus.active or self.quiet_now()):
            return False
        today = date.today()
        slots = scheduler.open_slots(today, config.PESTER_LOOKAHEAD_DAYS)
        now = time.monotonic()
        if not force:
            slots = [s for s in slots if now - self._last_nag.get(f"{s[0]}:{s[1]}", -1e9) > config.PESTER_COOLDOWN_MIN * 60]
        if not slots:
            if force:
                self.app.pet.set_mode("happy", seconds=3)
                self.app.say(f"All slots for the next {config.PESTER_LOOKAHEAD_DAYS} days are filled. "
                             "Who's a good creator? You are. 😽", 6000)
            return False
        day, funnel = slots[0]
        self._last_nag[f"{day}:{funnel}"] = now
        msg = f"Meow meow! 🐾 You're missing a {config.FUNNEL_HUMAN[funnel]} post for {scheduler.day_phrase(day, today)}."
        waiting = db.backlog(funnel)
        if waiting:
            msg += f"\nYou've got {len(waiting)} {funnel} idea{'s' if len(waiting) > 1 else ''} in the backlog — tap me to slot one in."
        else:
            msg += f"\nDump a {funnel} idea ({config.FUNNEL_BLURB[funnel]}) and I'll slot it in."
        self.app.pet.set_mode("alert", seconds=3)
        self.app.say(msg, 14000, on_click=lambda: self.app.open_drawer("week" if waiting else "chat"))
        self.app.notify("Momo", msg)
        return True
