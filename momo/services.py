"""High-level actions shared by the desktop app and the Telegram bot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import analyzer, config, db, hype, scheduler, writer

_profile_cache: tuple[tuple, analyzer.LinkedInProfile] | None = None


def get_profile(force: bool = False) -> analyzer.LinkedInProfile:
    """LinkedIn profile from my_linkedin_data/, re-parsed only when the files change."""
    global _profile_cache
    sig = analyzer.folder_signature(config.LINKEDIN_DIR)
    if force or _profile_cache is None or _profile_cache[0] != sig:
        _profile_cache = (sig, analyzer.load_profile(config.LINKEDIN_DIR))
    return _profile_cache[1]


@dataclass
class IngestResult:
    idea: db.Idea
    draft: writer.Draft
    slot: date | None
    message: str


def _message(text: str, d: writer.Draft, slot: date | None) -> str:
    progress = scheduler.week_progress(scheduler.week_start(date.today()))
    return hype.react(text, d.funnel, d.archetype, d.hook_name, d.hook_reason, get_profile(), slot, progress)


def ingest_idea(text: str, source: str = "desktop", auto_schedule: bool = True) -> IngestResult:
    """Classify, write the draft, store it and drop it into the next open funnel slot.

    May take a few seconds when Claude is writing: call it off the UI thread.
    """
    text = text.strip()
    d = writer.write_draft(text, get_profile())
    idea = db.add_idea(text, d.funnel, d.archetype, source, draft=d.text, hook=d.hook_key)
    slot = scheduler.auto_schedule(idea) if auto_schedule else None
    return IngestResult(db.get_idea(idea.id) or idea, d, slot, _message(text, d, slot))


def reclassify(idea_id: int, funnel: str) -> IngestResult | None:
    """Move an idea to another funnel and rewrite its draft in that funnel's style."""
    idea = db.get_idea(idea_id)
    if not idea or idea.funnel == funnel:
        return None
    d = writer.write_draft(idea.text, get_profile(), force_funnel=funnel)
    db.update_idea(idea_id, funnel=funnel, archetype=d.archetype, scheduled_date=None, draft=d.text, hook=d.hook_key)
    idea = db.get_idea(idea_id)
    slot = scheduler.auto_schedule(idea) if idea and idea.status != "posted" else None
    return IngestResult(db.get_idea(idea_id) or idea, d, slot, _message(idea.text, d, slot))
