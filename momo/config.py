"""Paths, funnel targets and tunables. Everything can be overridden from .env."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Running as the packaged Momo.exe / Momo.app (PyInstaller) instead of from source?
FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))  # read-only app files


def _home() -> Path:
    if os.environ.get("MOMO_HOME"):
        return Path(os.environ["MOMO_HOME"])
    if not FROZEN:
        return Path(__file__).resolve().parent.parent
    # The packaged app can't write next to itself: keep your data in your user folder.
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "Momo"


# Shipped defaults that were later improved: replace them only if the user never edited them.
_OLD_DEFAULTS = {"voice.md": {"7ccb6d83e2dd779d19ea675ead8a0aa3af37b478ade5ea3177feb792d45df0bb"}}


def _seed_profile(src: Path, dst: Path) -> None:
    """First launch: copy the bundled profile. Updates: add new files, never overwrite your edits."""
    import hashlib

    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        target = dst / f.name
        if not f.is_file():
            continue
        if not target.exists():
            shutil.copy2(f, target)
        elif f.name in _OLD_DEFAULTS and hashlib.sha256(target.read_bytes()).hexdigest() in _OLD_DEFAULTS[f.name]:
            shutil.copy2(f, target)


ROOT = _home()
ROOT.mkdir(parents=True, exist_ok=True)
if FROZEN and (BUNDLE / "my_linkedin_data").exists():
    _seed_profile(BUNDLE / "my_linkedin_data", ROOT / "my_linkedin_data")

try:  # python-dotenv is optional at import time so the core stays dependency-free
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "momo.db"
VOICE_DIR = DATA_DIR / "voice"
LINKEDIN_DIR = ROOT / "my_linkedin_data"

FUNNELS = ("ToFU", "MoFU", "BoFU")
FUNNEL_TARGETS = {"ToFU": 3, "MoFU": 3, "BoFU": 1}
FUNNEL_LABELS = {
    "ToFU": "Top of Funnel",
    "MoFU": "Middle of Funnel",
    "BoFU": "Bottom of Funnel",
}
FUNNEL_HUMAN = {"ToFU": "top\u2011of\u2011funnel", "MoFU": "middle\u2011funnel", "BoFU": "bottom\u2011funnel"}  # no-break hyphens
FUNNEL_BLURB = {
    "ToFU": "memes, pop culture, LinkedIn/work-life humor, viral visuals",
    "MoFU": "vulnerable stories, career lessons, identity insights, contrarian takes",
    "BoFU": "case studies, exact metrics, client wins, teardowns",
}

# Weekly template from momo_instructions.md: one post a day max, 3 ToFU / 3 MoFU / 1 BoFU.
# weekday (0 = Monday) -> funnel slots
WEEKLY_PLAN: dict[int, list[str]] = {
    0: ["MoFU"],
    1: ["ToFU"],
    2: ["BoFU"],
    3: ["MoFU"],
    4: ["ToFU"],
    5: ["MoFU"],
    6: ["ToFU"],
}
DAY_FORMAT: dict[int, str] = {
    0: "text story",
    1: "short text",
    2: "carousel",
    3: "text story",
    4: "meme / visual",
    5: "text or short video",
    6: "light one-liner",
}

PESTER_INTERVAL_MIN = _int("MOMO_PESTER_INTERVAL_MIN", 45)
PESTER_LOOKAHEAD_DAYS = _int("MOMO_PESTER_LOOKAHEAD_DAYS", 3)
PESTER_COOLDOWN_MIN = 180  # don't nag about the same slot more often than this
QUIET_START = _int("MOMO_QUIET_START", 22)
QUIET_END = _int("MOMO_QUIET_END", 8)
SYSTEM_NOTIFICATIONS = os.environ.get("MOMO_SYSTEM_NOTIFICATIONS", "1") == "1"

SCALE = max(2, min(10, _int("MOMO_SCALE", 4)))

ENV_PATH = ROOT / ".env"
# AI drafts (optional): Gemini when GEMINI_API_KEY is set, else offline. MOMO_AI_PROVIDER=offline forces offline.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")  # empty = pick the newest stable flash model your key can use

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_AUTOSTART = os.environ.get("MOMO_TELEGRAM_AUTOSTART", "0") == "1"
