"""Momo's hype-man voice: points at your real past winners when you drop a new idea.

Numbers here always come from my_linkedin_data/, never from the AI, so the receipts are real.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import date

from . import config
from .analyzer import LinkedInProfile, PastPost, fmt_num, plural
from .scheduler import day_phrase, week_start

OPENERS = (
    "OKAY this is a banger. 🔥",
    "Stop it. This is GOOD.",
    "Momo's whiskers are tingling. 🐾",
    "This has viral energy, I can smell it.",
    "Purr-fect raw material right here.",
)
CLOSERS = ("This one's got legs. 🔥", "Post it before the feeling fades!", "I'd double-tap this. Twice.", "")

_STOP = set("""a an and are as at be but by for from has have i i'm in is it its just my of on or so that the this
to was we what when with you your about into than then them they our out how why who will would could should
had make made after being""".split())


# Close cousins: a raw vulnerable story should be modelled on the identity story that worked, etc.
RELATED = {
    "vulnerability": ("identity", "story", "lesson"),
    "identity": ("vulnerability", "story"),
    "story": ("identity", "vulnerability", "lesson"),
    "lesson": ("story", "vulnerability"),
    "trend": ("meme", "contrarian"),
    "contrarian": ("meme", "trend"),
    "question": ("meme", "trend"),
}


@dataclass
class Match:
    post: PastPost
    reason: str  # theme | archetype | funnel | top


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z']{2,}", text.lower()) if w not in _STOP}


def find_match(text: str, funnel: str, archetype: str, profile: LinkedInProfile) -> Match | None:
    measured = profile.measured
    if not measured:
        return None
    toks = _tokens(text)
    same_funnel = [p for p in measured if p.funnel == funnel]
    if toks and same_funnel:  # same theme beats same format: "AI" ideas -> the AI-police post
        def overlap(p: PastPost) -> float:
            pt = _tokens(p.text)
            return len(toks & pt) / (len(toks | pt) or 1)
        best = max(same_funnel, key=overlap)
        if overlap(best) >= 0.08:
            return Match(best, "theme")
    for arch in (archetype, *RELATED.get(archetype, ())):
        same = [p for p in measured if p.archetype == arch]
        if same:
            return Match(max(same, key=lambda p: p.impressions), "archetype")
    if same_funnel:
        return Match(max(same_funnel, key=lambda p: p.impressions), "funnel")
    return Match(max(measured, key=lambda p: p.impressions), "top")


def relative_when(d: date | None, today: date) -> str:
    if not d:
        return ""
    delta = (today - d).days
    if delta < 0:
        return ""
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if week_start(d) == week_start(today):
        return f"on {d.strftime('%A')}"
    if (week_start(today) - week_start(d)).days == 7:
        return f"last {d.strftime('%A')}"
    if delta < 45:
        return f"on {d.strftime('%b')} {d.day}"
    return f"back in {d.strftime('%B')}" + (f" {d.year}" if d.year != today.year else "")


def short_hook(post: PastPost, words: int = 8) -> str:
    parts = post.hook.split()
    return " ".join(parts[:words]).rstrip(".,!?…") + ("…" if len(parts) > words else "")


def hype_line(text: str, funnel: str, archetype: str, profile: LinkedInProfile, today: date | None = None) -> str:
    today = today or date.today()
    match = find_match(text, funnel, archetype, profile)
    if not match:
        if profile.has_data:
            return f"{random.choice(OPENERS)} (Add impressions to your past posts and I'll hype you with receipts.)"
        return f"{random.choice(OPENERS)} Feed me your LinkedIn history (right-click me → LinkedIn setup)."
    p = match.post
    when = relative_when(p.date, today)
    subject = f"your {p.label} (“{short_hook(p)}”)" + (f" {when}" if when else "")
    if match.reason in ("theme", "archetype"):
        line = f"Hey, {subject} hit **{fmt_num(p.impressions)} impressions**—let's frame this one the same way!"
    elif match.reason == "funnel":
        line = (f"{random.choice(OPENERS)} Your biggest {funnel} hit, {subject}, pulled "
                f"**{fmt_num(p.impressions)} impressions**. Bring that energy here!")
    else:
        line = (f"{random.choice(OPENERS)} No {funnel} receipts on file yet, but {subject} pulled "
                f"**{fmt_num(p.impressions)} impressions**. Your audience shows up. Give them a win to cheer for!")
    stat = profile.stat_for(archetype)
    avg = profile.avg_impressions
    if stat and stat.count >= 2 and stat.lift >= 1.2:
        line += f"\nYour {plural(stat.label)} average **{stat.lift:.1f}x** your usual reach. Receipts don't lie. 🧾"
    elif avg and p.impressions >= 1.5 * avg and match.reason != "top":
        line += f"\nThat's **{p.impressions / avg:.1f}x** your average post. Do it again. 🧾"
    closer = random.choice(CLOSERS)
    return line + (f"\n{closer}" if closer else "")


def react(text: str, funnel: str, archetype: str, hook_name: str, hook_reason: str, profile: LinkedInProfile,
          slot: date | None, progress: dict[str, tuple[int, int]], today: date | None = None) -> str:
    today = today or date.today()
    lines = [hype_line(text, funnel, archetype, profile, today)]
    lines.append(f"🪝 Hook: **{hook_name}** ({hook_reason})")
    done, target = progress.get(funnel, (0, config.FUNNEL_TARGETS[funnel]))
    lines.append(f"📌 **{funnel}** · {config.FUNNEL_BLURB[funnel]}: {done}/{target} this week")
    if slot:
        lines.append(f"🗓️ Dropped into **{day_phrase(slot, today)}**'s {funnel} slot.")
    else:
        lines.append(f"🗓️ Every {funnel} slot for the next 3 weeks is full, so it's parked in your backlog. Overachiever.")
    return "\n".join(lines)


def rationale(text: str, funnel: str, archetype: str, profile: LinkedInProfile) -> str:
    """One line tied to her data, e.g. 'similar to your AI-police irony post, which hit 25.8k'."""
    match = find_match(text, funnel, archetype, profile)
    if not match:
        return "no past numbers on file yet, so this is a fresh experiment."
    p = match.post
    if match.reason in ("theme", "archetype", "funnel"):
        return f"similar to your {p.label} (“{short_hook(p, 6)}”), which hit {fmt_num(p.impressions)}."
    return f"no {funnel} winners on file yet; your best post overall is the {p.label} at {fmt_num(p.impressions)}."
