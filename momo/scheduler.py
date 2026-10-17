"""Weekly funnel slots: which days need which funnel, what's filled, what's missing."""
from __future__ import annotations

from datetime import date, timedelta

from . import config, db


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_slots(start: date) -> list[tuple[date, str]]:
    return [(start + timedelta(days=i), f) for i in range(7) for f in config.WEEKLY_PLAN.get(i, [])]


def _filled(start: date, end: date) -> set[tuple[date, str]]:
    return {(i.scheduled_date, i.funnel) for i in db.ideas_in_range(start, end)}


def week_progress(start: date) -> dict[str, tuple[int, int]]:
    filled = _filled(start, start + timedelta(days=6))
    return {f: (sum(1 for d, ff in week_slots(start) if ff == f and (d, f) in filled), config.FUNNEL_TARGETS[f])
            for f in config.FUNNELS}


def open_slots(start_day: date, days: int) -> list[tuple[date, str]]:
    end = start_day + timedelta(days=days - 1)
    filled = _filled(start_day, end)
    out = []
    for i in range(days):
        d = start_day + timedelta(days=i)
        out.extend((d, f) for f in config.WEEKLY_PLAN.get(d.weekday(), []) if (d, f) not in filled)
    return out


def next_open_slot(funnel: str, start: date | None = None, horizon: int = 21) -> date | None:
    start = start or date.today()
    return next((d for d, f in open_slots(start, horizon) if f == funnel), None)


def auto_schedule(idea: db.Idea) -> date | None:
    slot = next_open_slot(idea.funnel)
    if slot:
        db.update_idea(idea.id, scheduled_date=slot)
    return slot


def day_phrase(d: date, today: date | None = None) -> str:
    today = today or date.today()
    delta = (d - today).days
    name = d.strftime("%A")
    if delta == 0:
        return "today"
    if delta == 1:
        return f"tomorrow ({name})"
    if 1 < delta < 7:
        return name
    return f"{name}, {d.strftime('%b')} {d.day}"
