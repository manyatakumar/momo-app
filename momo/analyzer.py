"""Reads my_linkedin_data/ and turns past posts + metrics into hype-able insights.

Supported files (any mix):
  about.md            your LinkedIn "About" section
  viral_hooks.md      one hook per line
  posts.md / *.txt    posts separated by lines of ---, with optional metric lines:
                          date: 2026-10-13
                          impressions: 30k
                          comments: 142
                          reactions: 980
                      or one line like:  metrics: 30k impressions, 142 comments
  *.csv               LinkedIn analytics exports (columns are matched loosely)
  *.json              a list of {"text", "impressions", "comments", "reactions", "date"} objects
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .content import ARCHETYPES, detect_archetype

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

_METRIC_FIELD = {
    "impression": "impressions", "impressions": "impressions", "views": "impressions",
    "comment": "comments", "comments": "comments",
    "reactions": "reactions", "like": "reactions", "likes": "reactions",
    "repost": "reposts", "reposts": "reposts", "shares": "reposts",
}
_KV_RE = re.compile(r"^\s*(impressions?|views|comments?|reactions|likes?|reposts?|shares|date|posted|hook|archetype|"
                    r"label|type)\s*[:=]\s*(.+?)\s*$", re.I)
_METRICS_LINE_RE = re.compile(r"^\s*(?:metrics|stats)\s*[:=]\s*(.+)$", re.I)
_INLINE_METRIC_RE = re.compile(r"([\d][\d.,]*\s*[kKmM]?)\s*(impressions?|views|comments?|reactions|likes?|reposts?|shares)", re.I)
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y",
                 "%d %b %Y", "%d %B %Y", "%b %d %Y")


def parse_number(raw: str) -> int:
    s = str(raw).strip().lower().replace(",", "").replace(" ", "")
    m = re.match(r"([\d.]+)([km]?)", s)
    if not m:
        return 0
    try:
        n = float(m.group(1))
    except ValueError:
        return 0
    return int(n * {"k": 1_000, "m": 1_000_000}.get(m.group(2), 1))


def parse_date(raw: str) -> date | None:
    s = str(raw).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def plural(label: str) -> str:
    return label[:-1] + "ies" if label.endswith("y") else label + "s"


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 100_000:
        return f"{round(n / 1000)}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


@dataclass
class PastPost:
    text: str
    impressions: int = 0
    comments: int = 0
    reactions: int = 0
    reposts: int = 0
    date: date | None = None
    hook: str = ""
    archetype: str = ""
    custom_label: str = ""

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.hook:
            first = next((ln.strip() for ln in self.text.splitlines() if ln.strip()), "")
            self.hook = first[:140] + ("…" if len(first) > 140 else "")
        if self.archetype not in ARCHETYPES:
            self.archetype = detect_archetype(self.text)

    @property
    def funnel(self) -> str:
        return ARCHETYPES[self.archetype].funnel

    @property
    def label(self) -> str:
        return self.custom_label or ARCHETYPES[self.archetype].label


@dataclass
class ArchetypeStat:
    archetype: str
    label: str
    count: int
    avg_impressions: int
    lift: float  # vs. overall average


@dataclass
class LinkedInProfile:
    about: str = ""
    posts: list[PastPost] = field(default_factory=list)
    viral_hooks: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.posts or self.about or self.viral_hooks)

    @property
    def measured(self) -> list[PastPost]:
        return [p for p in self.posts if p.impressions > 0]

    @property
    def avg_impressions(self) -> int:
        m = self.measured
        return int(sum(p.impressions for p in m) / len(m)) if m else 0

    def top_posts(self, n: int = 3) -> list[PastPost]:
        return sorted(self.measured, key=lambda p: (p.impressions, p.comments), reverse=True)[:n]

    def archetype_stats(self) -> list[ArchetypeStat]:
        groups: dict[str, list[int]] = defaultdict(list)
        for p in self.measured:
            groups[p.archetype].append(p.impressions)
        avg_all = self.avg_impressions or 1
        stats = [ArchetypeStat(k, ARCHETYPES[k].label, len(v), int(sum(v) / len(v)), sum(v) / len(v) / avg_all)
                 for k, v in groups.items()]
        return sorted(stats, key=lambda s: s.avg_impressions, reverse=True)

    def stat_for(self, archetype: str) -> ArchetypeStat | None:
        return next((s for s in self.archetype_stats() if s.archetype == archetype), None)

    def best_weekday(self) -> tuple[str, int] | None:
        groups: dict[int, list[int]] = defaultdict(list)
        for p in self.measured:
            if p.date:
                groups[p.date.weekday()].append(p.impressions)
        if sum(len(v) for v in groups.values()) < 3:
            return None
        day, vals = max(groups.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        return WEEKDAYS[day], int(sum(vals) / len(vals))


# ---------------------------------------------------------------- parsing

def parse_posts_text(text: str) -> list[PastPost]:
    posts = []
    for chunk in re.split(r"^\s*-{3,}\s*$", text, flags=re.M):
        meta: dict[str, str] = {}
        body: list[str] = []
        for line in chunk.splitlines():
            kv = _KV_RE.match(line)
            ml = _METRICS_LINE_RE.match(line)
            if kv:
                meta[kv.group(1).lower()] = kv.group(2)
            elif ml:
                for num, name in _INLINE_METRIC_RE.findall(ml.group(1)):
                    meta[name.lower()] = num
            else:
                body.append(line)
        body_text = "\n".join(body).strip()
        if not body_text:
            continue
        post = PastPost(text=body_text, hook=meta.get("hook", ""), archetype=meta.get("archetype", "").strip().lower(),
                        custom_label=meta.get("label", meta.get("type", "")).strip())
        for k, v in meta.items():
            if k in _METRIC_FIELD:
                setattr(post, _METRIC_FIELD[k], parse_number(v))
            elif k in ("date", "posted"):
                post.date = parse_date(v)
        posts.append(post)
    return posts


def _match_col(headers: list[str], *needles: str, avoid: tuple[str, ...] = ()) -> int | None:
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(n in hl for n in needles) and not any(a in hl for a in avoid):
            return i
    return None


def parse_csv(raw: str) -> list[PastPost]:
    rows = list(csv.reader(io.StringIO(raw)))
    text_needles = ("commentary", "post text", "content", "text", "body", "post")
    avoid = ("url", "link", "id", "date", "type", "title")
    # LinkedIn exports often have title rows first: the header is the row with a text AND a metric column.
    header_idx = next((i for i, r in enumerate(rows[:15]) if _match_col(r, *text_needles, avoid=avoid) is not None
                       and _match_col(r, "impression", "views", "reaction", "like") is not None), None)
    if header_idx is None:
        return []
    headers = rows[header_idx]
    cols = {
        "text": _match_col(headers, *text_needles, avoid=avoid),
        "impressions": _match_col(headers, "impression", "views"),
        "comments": _match_col(headers, "comment", avoid=("commentary",)),
        "reactions": _match_col(headers, "reaction", "like"),
        "reposts": _match_col(headers, "repost", "share"),
        "date": _match_col(headers, "date", "created", "published"),
    }
    posts = []
    for r in rows[header_idx + 1:]:
        get = lambda k: r[cols[k]] if cols[k] is not None and cols[k] < len(r) else ""  # noqa: E731
        if not get("text").strip():
            continue
        posts.append(PastPost(
            text=get("text"),
            impressions=parse_number(get("impressions")),
            comments=parse_number(get("comments")),
            reactions=parse_number(get("reactions")),
            reposts=parse_number(get("reposts")),
            date=parse_date(get("date")),
        ))
    return posts


def parse_json(raw: str) -> list[PastPost]:
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("posts", [])
    posts = []
    for d in data:
        if not isinstance(d, dict) or not str(d.get("text", "")).strip():
            continue
        posts.append(PastPost(
            text=str(d["text"]),
            impressions=parse_number(d.get("impressions", d.get("views", 0))),
            comments=parse_number(d.get("comments", 0)),
            reactions=parse_number(d.get("reactions", d.get("likes", 0))),
            reposts=parse_number(d.get("reposts", d.get("shares", 0))),
            date=parse_date(d.get("date", "")),
            hook=str(d.get("hook", "")),
        ))
    return posts


def _data_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith(".") and not p.name.lower().startswith("readme")
                  and p.stat().st_size > 0)


def folder_has_data(folder: Path) -> bool:
    return bool(_data_files(folder))


def folder_signature(folder: Path) -> tuple:
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in _data_files(folder))


def load_profile(folder: Path) -> LinkedInProfile:
    profile = LinkedInProfile()
    for path in _data_files(folder):
        stem, suffix = path.stem.lower(), path.suffix.lower()
        try:
            raw = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if "voice" in stem:  # style guide for the draft writer, not posts
            continue
        if "about" in stem:
            profile.about = (profile.about + "\n\n" + raw).strip()
        elif "hook" in stem:
            for line in raw.splitlines():
                line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"“”')
                if line:
                    profile.viral_hooks.append(line)
        elif suffix == ".csv":
            profile.posts.extend(parse_csv(raw))
        elif suffix == ".json":
            try:
                profile.posts.extend(parse_json(raw))
            except (ValueError, TypeError):
                continue
        elif suffix in (".md", ".txt"):
            profile.posts.extend(parse_posts_text(raw))
    return profile


def save_setup(folder: Path, about: str, posts: str, hooks: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in (("about.md", about), ("posts.md", posts), ("viral_hooks.md", hooks)):
        if content.strip():
            (folder / name).write_text(content.strip() + "\n", encoding="utf-8")
