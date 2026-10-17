"""Weekly content calendar: one row per day, one card per funnel slot."""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .. import config, db, scheduler
from . import theme
from .widgets import ClickableFrame, label, scroll_area

STATUS_ICON = {"idea": "💡", "drafted": "✎", "posted": "✓"}


def _snip(text: str, n: int = 58) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[: n - 1] + "…"


class SlotCard(ClickableFrame):
    def __init__(self, day: date, funnel: str, idea: db.Idea | None, today: date, since: date) -> None:
        super().__init__()
        self.day, self.funnel, self.idea = day, funnel, idea
        color = theme.FUNNEL_COLORS[funnel]
        missed = idea is None and since <= day < today
        if idea is None:
            style = (f"background: #FBEFE9; border: 1px solid {theme.CLAY};" if missed else
                     f"background: transparent; border: 1px solid {theme.BORDER};") + " border-radius: 10px;"
        elif idea.status == "posted":
            style = f"background: {theme.SAGE}; border: 1px solid {theme.SAGE}; border-radius: 10px;"
        else:
            style = f"background: {theme.SAGE_MIST}; border: 1px solid {theme.SAGE_LIGHT}; border-radius: 10px;"
        self.setObjectName("Slot")
        self.setStyleSheet(f"QFrame#Slot {{ {style} }} QFrame#Slot QLabel {{ background: transparent; border: none; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 6, 9, 6)
        lay.setSpacing(8)
        tag = QLabel(funnel)
        tag.setFixedWidth(40)
        on_sage = idea is not None and idea.status == "posted"
        tag.setStyleSheet(f"font-weight: 700; font-size: 11px; color: {'white' if on_sage else color};")
        lay.addWidget(tag)
        if idea:
            text = f"{STATUS_ICON[idea.status]}  {_snip(idea.text)}"
            body = QLabel(text)
            body.setStyleSheet(f"color: {'white' if on_sage else theme.INK}; font-size: 12px;")
            body.setToolTip(idea.draft or idea.text)
        else:
            body = QLabel("missed — fill it anyway?" if missed else "+ empty slot")
            body.setStyleSheet(f"color: {theme.CLAY if missed else theme.INK_SOFT}; font-size: 12px; font-style: italic;")
        body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # never widen the drawer
        lay.addWidget(body, 1)


class CalendarPage(QWidget):
    data_changed = pyqtSignal()
    request_chat = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.week = scheduler.week_start(date.today())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        nav = QHBoxLayout()
        prev_btn, next_btn = QPushButton("‹"), QPushButton("›")
        for b in (prev_btn, next_btn):
            b.setObjectName("IconButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(lambda: self.shift(-7))
        next_btn.clicked.connect(lambda: self.shift(7))
        self.range_label = label("", "Section")
        today_btn = QPushButton("This week")
        today_btn.setObjectName("Ghost")
        today_btn.clicked.connect(self.go_today)
        nav.addWidget(prev_btn)
        nav.addWidget(self.range_label)
        nav.addWidget(next_btn)
        nav.addStretch(1)
        nav.addWidget(today_btn)
        root.addLayout(nav)

        self._days = QWidget()
        self._days_lay = QVBoxLayout(self._days)
        self._days_lay.setContentsMargins(0, 0, 4, 0)
        self._days_lay.setSpacing(6)
        root.addWidget(scroll_area(self._days), 1)

        self.backlog_label = label("", "Muted", wrap=True)
        root.addWidget(self.backlog_label)
        self.refresh()

    def shift(self, days: int) -> None:
        self.week += timedelta(days=days)
        self.refresh()

    def go_today(self) -> None:
        self.week = scheduler.week_start(date.today())
        self.refresh()

    def refresh(self) -> None:
        today = date.today()
        end = self.week + timedelta(days=6)
        self.range_label.setText(f"{self.week.strftime('%b')} {self.week.day} – {end.strftime('%b')} {end.day}")
        ideas = {(i.scheduled_date, i.funnel): i for i in db.ideas_in_range(self.week, end)}
        since = date.fromisoformat(db.kv_get("installed_on") or today.isoformat())

        self.setUpdatesEnabled(False)
        while self._days_lay.count():
            item = self._days_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(7):
            d = self.week + timedelta(days=i)
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
            day_lbl = label(f"{d.strftime('%a')}\n{d.day}", "DayLabelToday" if d == today else "DayLabel")
            day_lbl.setFixedWidth(34)
            day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(day_lbl, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(4)
            funnels = config.WEEKLY_PLAN.get(d.weekday(), [])
            for f in funnels:
                card = SlotCard(d, f, ideas.get((d, f)), today, since)
                card.clicked.connect(lambda c=card: self._slot_menu(c))
                col.addWidget(card)
            if not funnels:
                rest = label("rest day — touch grass 🌿", "Muted")
                rest.setContentsMargins(4, 8, 0, 8)
                col.addWidget(rest)
            lay.addLayout(col, 1)
            self._days_lay.addWidget(row)
        self._days_lay.addStretch(1)
        self.setUpdatesEnabled(True)

        counts = {f: len(db.backlog(f)) for f in config.FUNNELS}
        self.backlog_label.setText("Backlog: " + " · ".join(f"{n} {f}" for f, n in counts.items()))

    # ------------------------------------------------------------ menus
    def _slot_menu(self, card: SlotCard) -> None:
        menu = QMenu(self)
        if card.idea is None:
            backlog = db.backlog(card.funnel)
            title = menu.addAction(f"Fill {card.day.strftime('%A')}'s {card.funnel} slot with…")
            title.setEnabled(False)
            for idea in backlog[:8]:
                menu.addAction(f"{STATUS_ICON[idea.status]}  {_snip(idea.text, 48)}",
                               lambda i=idea: self._assign(i, card.day))
            if not backlog:
                none = menu.addAction(f"(no {card.funnel} ideas in the backlog)")
                none.setEnabled(False)
            menu.addSeparator()
            menu.addAction("✏️  Brain-dump a new idea", self.request_chat.emit)
        else:
            idea = card.idea
            for status, text in (("idea", "💡  Mark as idea"), ("drafted", "✎  Mark as drafted"),
                                 ("posted", "✓  Mark as posted")):
                act = menu.addAction(text, lambda s=status: self._set_status(idea, s))
                act.setEnabled(idea.status != status)
            menu.addSeparator()
            if idea.draft:
                menu.addAction("📋  Copy ready-to-post draft", lambda: QGuiApplication.clipboard().setText(idea.draft))
            menu.addAction("📋  Copy raw idea", lambda: QGuiApplication.clipboard().setText(idea.text))
            menu.addAction("↩  Move back to backlog", lambda: self._unschedule(idea))
            menu.addAction("🗑  Delete idea", lambda: self._delete(idea))
        menu.exec(QCursor.pos())

    def _assign(self, idea: db.Idea, day: date) -> None:
        db.update_idea(idea.id, scheduled_date=day)
        self._changed()

    def _set_status(self, idea: db.Idea, status: str) -> None:
        db.update_idea(idea.id, status=status)
        self._changed()

    def _unschedule(self, idea: db.Idea) -> None:
        db.update_idea(idea.id, scheduled_date=None)
        self._changed()

    def _delete(self, idea: db.Idea) -> None:
        db.delete_idea(idea.id)
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        self.data_changed.emit()
