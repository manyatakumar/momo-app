"""Turns a brain dump into a ready-to-post LinkedIn draft in your voice.

Two engines, same output:
  * Claude (when ANTHROPIC_API_KEY is set): writes the full post from your voice file, viral hits and the hook
    library, and picks funnel + hook itself.
  * Offline (always available): momo/hooks.py templates. Instant, no internet, leaves [brackets] to fill.
Any API problem (no internet, bad key, refusal) silently falls back to offline so Momo never gets stuck.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from . import config
from .analyzer import LinkedInProfile, fmt_num
from .content import ARCHETYPES, DEFAULT_ARCHETYPE, classify
from .hooks import HOOKS, hooks_for, offline_draft, pick_hook

log = logging.getLogger(__name__)


@dataclass
class Draft:
    funnel: str
    archetype: str
    hook_key: str
    hook_reason: str
    text: str
    engine: str          # "claude" | "offline"
    note: str = ""       # why we fell back, if we did

    @property
    def hook_name(self) -> str:
        return HOOKS[self.hook_key].name


def ai_available() -> bool:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    import importlib.util
    return importlib.util.find_spec("anthropic") is not None


# --------------------------------------------------------------------------- offline

def offline(text: str, force_funnel: str | None = None, note: str = "") -> Draft:
    cls = classify(text)
    funnel = force_funnel or cls.funnel
    archetype = cls.archetype if ARCHETYPES[cls.archetype].funnel == funnel else DEFAULT_ARCHETYPE[funnel]
    hook, reason = pick_hook(text, funnel)
    return Draft(funnel, archetype, hook.key, reason, offline_draft(text, funnel, hook), "offline", note)


# --------------------------------------------------------------------------- claude

SCHEMA = {
    "type": "object",
    "properties": {
        "funnel": {"type": "string", "enum": list(config.FUNNELS)},
        "hook_key": {"type": "string", "enum": list(HOOKS)},
        "why_this_hook": {"type": "string"},
        "draft": {"type": "string"},
    },
    "required": ["funnel", "hook_key", "why_this_hook", "draft"],
    "additionalProperties": False,
}


def _voice_file() -> str:
    path = config.LINKEDIN_DIR / "voice.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "lowercase, conversational, short punchy lines, → arrows, vulnerable + self-deprecating humor."


def system_prompt(profile: LinkedInProfile) -> str:
    hits = "\n".join(
        f"- [{p.funnel} · {p.label}] {fmt_num(p.impressions)} impressions: “{p.text.strip()}”"
        for p in sorted(profile.measured, key=lambda p: p.impressions, reverse=True)[:12]
    ) or "- (no past posts on file yet)"
    library = "\n\n".join(
        f"[{h.key}] {h.name} (funnels: {', '.join(h.funnels)})\nTemplate: {h.template}\nRule: {h.rule}"
        for h in HOOKS.values()
    )
    funnels = "\n".join(f"- {f} ({config.FUNNEL_LABELS[f]}, {config.FUNNEL_TARGETS[f]}x/week): "
                        f"{config.FUNNEL_BLURB[f]}" for f in config.FUNNELS)
    return f"""You are the ghostwriter inside Momo, a desktop companion that turns rough brain dumps into ready-to-post \
LinkedIn drafts for one specific creator. Your drafts must sound exactly like her, not like an AI.

<creator_profile>
{profile.about or "(no About section on file)"}
</creator_profile>

<voice_rules>
{_voice_file()}
</voice_rules>

<viral_hits>
These are her real posts and their real numbers. Study the rhythm, casing and humor.
{hits}
</viral_hits>

<funnels>
{funnels}
</funnels>

<hook_library>
For MoFU ideas, choose the best of Gaurav Sharma's 10 middle-of-funnel hooks (flex_twist, confession, receipt, \
how_did_i, fake_out, withheld, backfire, one_liner, hot_take, mirror) and follow its template and rule closely. \
ToFU ideas use the meme formats (economy, irony, juxtapose) or one_liner / hot_take. BoFU ideas use receipt, \
how_did_i or result.

{library}
</hook_library>

<task>
1. Decide the funnel. Memes, pop-culture and trend jokes are ToFU; vulnerable stories, career lessons and \
identity insights are MoFU; client wins, results and metrics are BoFU.
2. Pick the single best hook_key for that funnel and say in one short, casual sentence why it fits.
3. Write the full post in her voice: lowercase, short punchy lines, → arrows for sequences, generous line breaks. \
ToFU stays 1-4 lines. MoFU runs roughly 120-220 words with a one-line takeaway near the end. BoFU leads with the \
number and walks through the how.
4. Never invent facts, names or numbers that aren't in the brain dump. Where a specific detail is needed and \
missing, leave a short [bracket] placeholder for her to fill.
5. No hashtags, no "thrilled to announce", no motivational-poster lines, no em dashes.
</task>"""


def _claude(text: str, profile: LinkedInProfile, force_funnel: str | None) -> Draft:
    import anthropic

    client = anthropic.Anthropic(timeout=90.0, max_retries=1)
    user = f"<brain_dump>\n{text}\n</brain_dump>"
    if force_funnel:
        user += f"\n\nShe has decided this is a {force_funnel} post. Use funnel = {force_funnel} and a hook that fits it."
    response = client.beta.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=system_prompt(profile),
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this one")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("the draft got cut off")
    raw = next(b.text for b in response.content if b.type == "text")
    data = json.loads(raw)
    funnel = force_funnel or data["funnel"]
    hook_key = data["hook_key"] if funnel in HOOKS[data["hook_key"]].funnels else hooks_for(funnel)[0].key
    cls = classify(text)
    archetype = cls.archetype if ARCHETYPES[cls.archetype].funnel == funnel else DEFAULT_ARCHETYPE[funnel]
    return Draft(funnel, archetype, hook_key, data["why_this_hook"].strip(), data["draft"].strip(), "claude")


def write_draft(text: str, profile: LinkedInProfile, force_funnel: str | None = None) -> Draft:
    if not ai_available():
        return offline(text, force_funnel)
    try:
        return _claude(text, profile, force_funnel)
    except Exception as exc:  # noqa: BLE001 - any failure: fall back, never block the user
        import anthropic

        if isinstance(exc, anthropic.AuthenticationError):
            reason = "your Claude API key was rejected"
        elif isinstance(exc, anthropic.APIConnectionError):
            reason = "no internet connection"
        elif isinstance(exc, anthropic.RateLimitError):
            reason = "Claude is rate-limiting right now"
        elif isinstance(exc, anthropic.APIStatusError):
            reason = f"Claude API error {exc.status_code}"
        else:
            reason = str(exc) or type(exc).__name__
        log.warning("Claude draft failed (%s); using offline writer", reason)
        return offline(text, force_funnel, note=f"offline draft: {reason}")


def save_api_key(key: str) -> None:
    """Write/replace ANTHROPIC_API_KEY in .env and apply it to this process."""
    key = key.strip()
    path = config.ENV_PATH
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [ln for ln in lines if not ln.startswith("ANTHROPIC_API_KEY=")]
    if key:
        lines.append(f"ANTHROPIC_API_KEY={key}")
        os.environ["ANTHROPIC_API_KEY"] = key
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
