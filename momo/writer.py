"""Turns a brain dump into a ready-to-post LinkedIn draft in your voice.

Two engines, same output (post + funnel + hook + format + alternative first lines + first comment + rationale):
  * Gemini  (GEMINI_API_KEY): REST call to Google's Gemini API. The free tier covers light daily use.
  * Offline (always available): momo/hooks.py templates. Instant, no internet, leaves [fill: ...] placeholders.
Any Gemini problem (no internet, bad key, rate limit) silently falls back to offline so Momo never gets stuck.

build_prompt() produces the same brief as plain text, for pasting into any chat AI (Gemini, ChatGPT, Claude.ai…).
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import config
from .analyzer import LinkedInProfile, fmt_num
from .content import ARCHETYPES, DEFAULT_ARCHETYPE, classify
from .hooks import FIRST_COMMENT, HOOKS, alternative_openers, fill_placeholders, hooks_for, offline_draft, pick_hook

log = logging.getLogger(__name__)
ENGINE_LABEL = {"gemini": "Gemini", "offline": "offline"}


@dataclass
class Draft:
    funnel: str
    archetype: str
    hook_key: str
    hook_reason: str
    text: str
    engine: str                       # "gemini" | "offline"
    note: str = ""                    # why we fell back, if we did
    format: str = ""                  # text story / carousel / meme … (set from the calendar slot)
    alt_first_lines: list[str] = field(default_factory=list)
    first_comment: str = ""
    rationale: str = ""

    @property
    def hook_name(self) -> str:
        return HOOKS[self.hook_key].name


# --------------------------------------------------------------------------- provider choice

def _gemini_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def provider() -> str:
    """'gemini' when a Gemini key is saved (unless MOMO_AI_PROVIDER=offline), else 'offline'."""
    if os.environ.get("MOMO_AI_PROVIDER", "").strip().lower() == "offline":
        return "offline"
    return "gemini" if _gemini_key() else "offline"


def ai_available() -> bool:
    return provider() != "offline"


# --------------------------------------------------------------------------- offline

def offline(text: str, force_funnel: str | None = None, note: str = "", avoid: frozenset[str] = frozenset()) -> Draft:
    cls = classify(text)
    funnel = force_funnel or cls.funnel
    archetype = cls.archetype if ARCHETYPES[cls.archetype].funnel == funnel else DEFAULT_ARCHETYPE[funnel]
    hook, reason = pick_hook(text, funnel, avoid)
    return Draft(funnel, archetype, hook.key, reason, offline_draft(text, funnel, hook), "offline", note,
                 alt_first_lines=alternative_openers(text, funnel, hook.key), first_comment=FIRST_COMMENT[funnel])


# --------------------------------------------------------------------------- the brief (shared by every engine)

def _read(name: str) -> str:
    try:
        return (config.LINKEDIN_DIR / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _context(profile: LinkedInProfile) -> str:
    hits = "\n".join(
        f"- [{p.funnel} · {p.label}] {fmt_num(p.impressions)} impressions: “{p.text.strip()}”"
        for p in sorted(profile.measured, key=lambda p: p.impressions, reverse=True)[:12]
    ) or "- (no past posts on file yet)"
    base = ", ".join(f"{k.replace('_', ' ')}: {v:g}" for k, v in profile.baselines.items()) or "(none on file)"
    hooks = "\n".join(f"- {h}" for h in profile.viral_hooks[:20]) or "- (none on file)"
    library = "\n\n".join(
        f"[{h.key}] {h.name} (best funnels: {', '.join(h.funnels)})\nTemplate: {h.template}\nRule: {h.rule}"
        + (f"\nReference example (another person's situation, calibration only): “{h.example}”" if h.example else "")
        for h in HOOKS.values()
    )
    plan = ", ".join(f"{d}: {', '.join(config.WEEKLY_PLAN[i])} ({config.DAY_FORMAT[i]})"
                     for i, d in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")) if config.WEEKLY_PLAN[i])
    return f"""<operating_instructions>
{_read("momo_instructions.md") or "(no instructions file on file)"}
</operating_instructions>

<creator_profile>
{profile.about or "(no About section on file)"}
</creator_profile>

<voice_rules>
{_read("voice.md") or "lowercase, conversational, short punchy lines, → arrows, vulnerable + self-deprecating humor."}
</voice_rules>

<her_viral_hits>
Real posts, real numbers. Study the rhythm, casing and humor.
{hits}
</her_viral_hits>

<account_baselines>
{base}
</account_baselines>

<her_saved_hooks>
Opening lines she has saved. Reuse their energy, not their exact words.
{hooks}
</her_saved_hooks>

<weekly_plan>
{plan}
</weekly_plan>

<hook_library>
MoFU: apply the 10 storytelling hooks as personal openers. ToFU & BoFU: borrow the structure only (tense line 1, \
data-backed specifics, no fluffy conclusion). ToFU can also use her own meme formats (economy, irony, juxtapose); \
BoFU can use receipt, how_did_i, result.

{library}
</hook_library>"""


def _task(text: str, force_funnel: str | None, avoid: frozenset[str]) -> str:
    rest = f" Rotation rule: don't use these hooks this time: {', '.join(sorted(avoid))}." if avoid else ""
    forced = f" She has decided this is a {force_funnel} post: use that funnel." if force_funnel else ""
    return f"""Turn this brain dump into one ready-to-post LinkedIn post in her voice.

<brain_dump>
{text}
</brain_dump>

Rules: pick the funnel (ToFU / MoFU / BoFU) and the single best hook from the library.{forced}{rest} Line 1 under ~15 \
words with tension. Lowercase-leaning, short punchy lines, → arrows for sequences. No links in the body, 0-3 hashtags, \
no zero-value endings ("thoughts?", "agree?", summaries), no em dashes. Never invent facts, numbers, names or \
biography that aren't in the brain dump or her profile: leave a [fill: ...] placeholder instead. Never present the \
reference hook examples as her life."""


def build_prompt(text: str, profile: LinkedInProfile, avoid: frozenset[str] = frozenset()) -> str:
    """Plain-text brief to paste into any chat AI."""
    return (f"You are Momo, Manyata's LinkedIn ghostwriter. Use everything below.\n\n{_context(profile)}\n\n"
            f"{_task(text, None, avoid)}\n\nReply with exactly:\n"
            "1. Funnel + hook type + format (one line)\n2. The post, ready to paste\n"
            "3. Two alternative first lines (different hook types)\n4. A first-comment suggestion\n"
            "5. One-line rationale tied to her data")


# --------------------------------------------------------------------------- structured output

_FIELDS = ("funnel", "hook_key", "format", "why_this_hook", "draft", "alt_first_lines", "first_comment", "rationale")

GEMINI_SCHEMA = {  # OpenAPI-subset schema (Gemini responseSchema)
    "type": "OBJECT",
    "properties": {
        "funnel": {"type": "STRING", "enum": list(config.FUNNELS)},
        "hook_key": {"type": "STRING", "enum": list(HOOKS)},
        "format": {"type": "STRING"},
        "why_this_hook": {"type": "STRING"},
        "draft": {"type": "STRING"},
        "alt_first_lines": {"type": "ARRAY", "items": {"type": "STRING"}},
        "first_comment": {"type": "STRING"},
        "rationale": {"type": "STRING"},
    },
    "required": list(_FIELDS),
    "propertyOrdering": list(_FIELDS),
}

_OUTPUT_NOTE = ("Fill every field: funnel, hook_key, format, why_this_hook (one casual sentence), draft (the full post), "
                "alt_first_lines (two alternative first lines using different hook types), first_comment (links or "
                "extra context go here, never in the post), rationale (one line tied to her data).")


def _to_draft(data: dict, text: str, force_funnel: str | None, engine: str) -> Draft:
    funnel = force_funnel or data["funnel"]
    hook_key = data["hook_key"] if data.get("hook_key") in HOOKS and funnel in HOOKS[data["hook_key"]].funnels \
        else hooks_for(funnel)[0].key
    cls = classify(text)
    archetype = cls.archetype if ARCHETYPES[cls.archetype].funnel == funnel else DEFAULT_ARCHETYPE[funnel]
    return Draft(funnel, archetype, hook_key, str(data.get("why_this_hook", "")).strip(),
                 fill_placeholders(str(data["draft"]).strip()), engine,
                 format=str(data.get("format", "")).strip(),
                 alt_first_lines=[str(x).strip() for x in data.get("alt_first_lines", []) if str(x).strip()][:2],
                 first_comment=str(data.get("first_comment", "")).strip(),
                 rationale=str(data.get("rationale", "")).strip())


# --------------------------------------------------------------------------- gemini

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
_gemini_model_cache: str | None = None


class GeminiError(RuntimeError):
    pass


def _tls() -> ssl.SSLContext:
    """System certificates plus certifi's bundle, so HTTPS works on any Windows setup."""
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except (ImportError, OSError):
        pass
    return ctx


def _gemini_http(method: str, path: str, key: str, body: dict | None = None, timeout: float = 90.0) -> dict:
    req = urllib.request.Request(f"{GEMINI_API}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_tls()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except (ValueError, OSError):
            msg = ""
        if exc.code == 429:
            raise GeminiError("Gemini's rate limit was hit, try again in a minute") from exc
        if exc.code in (401, 403) or "API key" in msg:
            raise GeminiError("your Gemini API key was rejected") from exc
        raise GeminiError(f"Gemini API error {exc.code}" + (f": {msg[:80]}" if msg else "")) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            raise GeminiError(f"secure connection to Google failed ({exc.reason.reason or 'SSL'})") from exc
        raise GeminiError("no internet connection") from exc
    except TimeoutError as exc:
        raise GeminiError("Gemini took too long to answer") from exc


def pick_gemini_model(names: list[str]) -> str:
    """Newest stable flash model (free-tier friendly), else newest stable pro, else any flash."""
    stable = []
    for n in names:
        m = re.fullmatch(r"(?:models/)?gemini-(\d+(?:\.\d+)?)-(flash|pro)", n)
        if m:
            stable.append((m.group(2) == "flash", float(m.group(1)), n.split("/")[-1]))
    if stable:
        return max(stable)[2]
    flash = sorted((n.split("/")[-1] for n in names if "flash" in n and "gemini" in n), reverse=True)
    return flash[0] if flash else "gemini-2.5-flash"


def check_gemini_key(key: str) -> str:
    """Settings "Test" button: returns the model Momo will use, or raises GeminiError with a plain reason."""
    global _gemini_model_cache
    key = key.strip()
    if not key:
        raise GeminiError("paste your Gemini API key first")
    _gemini_model_cache = None
    return _gemini_model(key)


def _gemini_model(key: str) -> str:
    global _gemini_model_cache
    if config.GEMINI_MODEL:
        return config.GEMINI_MODEL
    if _gemini_model_cache is None:
        try:
            data = _gemini_http("GET", "models?pageSize=1000", key, timeout=20)
            names = [m["name"] for m in data.get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
            _gemini_model_cache = pick_gemini_model(names)
        except GeminiError:
            raise
        except Exception:  # noqa: BLE001 - unexpected listing shape: use a sensible default
            _gemini_model_cache = "gemini-2.5-flash"
    return _gemini_model_cache


def _gemini(text: str, profile: LinkedInProfile, force_funnel: str | None, avoid: frozenset[str]) -> Draft:
    key = _gemini_key()
    model = _gemini_model(key)
    body = {
        "system_instruction": {"parts": [{"text": f"You are Momo, Manyata's LinkedIn ghostwriter inside a desktop "
                                                  f"app.\n\n{_context(profile)}"}]},
        "contents": [{"role": "user", "parts": [{"text": f"{_task(text, force_funnel, avoid)}\n\n{_OUTPUT_NOTE}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": GEMINI_SCHEMA},
    }
    data = _gemini_http("POST", f"models/{model}:generateContent", key, body)
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "no answer")
        raise GeminiError(f"Gemini returned nothing ({reason})")
    parts = candidates[0].get("content", {}).get("parts", [])
    raw = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not raw.strip():
        raise GeminiError(f"Gemini returned an empty answer ({candidates[0].get('finishReason', '?')})")
    return _to_draft(json.loads(raw), text, force_funnel, "gemini")


# --------------------------------------------------------------------------- entry point

def write_draft(text: str, profile: LinkedInProfile, force_funnel: str | None = None,
                avoid: frozenset[str] = frozenset()) -> Draft:
    engine = provider()
    if engine == "offline":
        return offline(text, force_funnel, avoid=avoid)
    try:
        return _gemini(text, profile, force_funnel, avoid)
    except Exception as exc:  # noqa: BLE001 - any failure: fall back, never block the user
        reason = _explain(exc)
        log.warning("%s draft failed (%s); using offline writer", ENGINE_LABEL[engine], reason)
        return offline(text, force_funnel, note=f"offline draft: {reason}", avoid=avoid)


def _explain(exc: Exception) -> str:
    if isinstance(exc, GeminiError):
        return str(exc)
    if isinstance(exc, (ValueError, KeyError)):
        return "Gemini's answer couldn't be read"
    return str(exc) or type(exc).__name__


def save_env(values: dict[str, str]) -> None:
    """Write/replace keys in .env and apply them to this process (empty value = remove)."""
    path = config.ENV_PATH
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [ln for ln in lines if ln.split("=", 1)[0].strip() not in values]
    for k, v in values.items():
        v = v.strip()
        if v:
            lines.append(f"{k}={v}")
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
