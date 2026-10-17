"""SQLite storage shared by the desktop app and the Telegram bot (WAL mode, safe across processes)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    text           TEXT    NOT NULL,
    funnel         TEXT    NOT NULL,
    archetype      TEXT,
    source         TEXT    NOT NULL DEFAULT 'desktop',
    status         TEXT    NOT NULL DEFAULT 'idea',   -- idea | drafted | posted
    scheduled_date TEXT,                               -- ISO date of the funnel slot it fills
    created_at     TEXT    NOT NULL,
    draft          TEXT,                               -- ready-to-post LinkedIn draft
    hook           TEXT                                -- hook key from momo/hooks.py
);
CREATE INDEX IF NOT EXISTS idx_ideas_slot ON ideas(scheduled_date, funnel);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""

STATUSES = ("idea", "drafted", "posted")
_UPDATABLE = {"text", "funnel", "archetype", "status", "scheduled_date", "draft", "hook"}
_ready = False


@dataclass
class Idea:
    id: int
    text: str
    funnel: str
    archetype: str | None
    source: str
    status: str
    scheduled_date: date | None
    created_at: datetime
    draft: str | None = None
    hook: str | None = None

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "Idea":
        return cls(
            id=r["id"],
            text=r["text"],
            funnel=r["funnel"],
            archetype=r["archetype"],
            source=r["source"],
            status=r["status"],
            scheduled_date=date.fromisoformat(r["scheduled_date"]) if r["scheduled_date"] else None,
            created_at=datetime.fromisoformat(r["created_at"]),
            draft=r["draft"],
            hook=r["hook"],
        )


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    global _ready
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        if not _ready:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(ideas)")}
            for col in ("draft", "hook"):  # upgrade databases from v1
                if col not in cols:
                    conn.execute(f"ALTER TABLE ideas ADD COLUMN {col} TEXT")
            conn.execute("INSERT OR IGNORE INTO kv(key, value) VALUES ('installed_on', ?)", (date.today().isoformat(),))
            _ready = True
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect():
        pass


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def add_idea(text: str, funnel: str, archetype: str | None = None, source: str = "desktop",
             scheduled_date: date | None = None, draft: str | None = None, hook: str | None = None) -> Idea:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO ideas(text, funnel, archetype, source, scheduled_date, created_at, draft, hook) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (text, funnel, archetype, source, _iso(scheduled_date), datetime.now().isoformat(timespec="seconds"),
             draft, hook),
        )
        new_id = cur.lastrowid
    return get_idea(new_id)  # type: ignore[return-value]


def get_idea(idea_id: int) -> Idea | None:
    with connect() as c:
        r = c.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
    return Idea.from_row(r) if r else None


def update_idea(idea_id: int, **fields) -> Idea | None:
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if "scheduled_date" in fields and isinstance(fields["scheduled_date"], date):
        fields["scheduled_date"] = fields["scheduled_date"].isoformat()
    if fields:
        cols = ", ".join(f"{k}=?" for k in fields)
        with connect() as c:
            c.execute(f"UPDATE ideas SET {cols} WHERE id=?", (*fields.values(), idea_id))
    return get_idea(idea_id)


def delete_idea(idea_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM ideas WHERE id=?", (idea_id,))


def ideas_in_range(start: date, end: date) -> list[Idea]:
    """Scheduled ideas with start <= scheduled_date <= end."""
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM ideas WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date, id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [Idea.from_row(r) for r in rows]


def idea_in_slot(day: date, funnel: str) -> Idea | None:
    with connect() as c:
        r = c.execute("SELECT * FROM ideas WHERE scheduled_date=? AND funnel=? ORDER BY id LIMIT 1",
                      (day.isoformat(), funnel)).fetchone()
    return Idea.from_row(r) if r else None


def backlog(funnel: str | None = None) -> list[Idea]:
    q = "SELECT * FROM ideas WHERE scheduled_date IS NULL AND status != 'posted'"
    args: tuple = ()
    if funnel:
        q += " AND funnel=?"
        args = (funnel,)
    with connect() as c:
        rows = c.execute(q + " ORDER BY id DESC", args).fetchall()
    return [Idea.from_row(r) for r in rows]


def ideas_after(last_id: int, exclude_source: str = "desktop") -> list[Idea]:
    with connect() as c:
        rows = c.execute("SELECT * FROM ideas WHERE id>? AND source!=? ORDER BY id",
                         (last_id, exclude_source)).fetchall()
    return [Idea.from_row(r) for r in rows]


def max_idea_id() -> int:
    with connect() as c:
        r = c.execute("SELECT COALESCE(MAX(id), 0) FROM ideas").fetchone()
    return int(r[0])


def kv_get(key: str, default: str | None = None) -> str | None:
    with connect() as c:
        r = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def kv_set(key: str, value: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO kv(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, value))
