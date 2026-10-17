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


ROOT = _home()
ROOT.mkdir(parents=True, exist_ok=True)
if FROZEN and not (ROOT / "my_linkedin_data").exists() and (BUNDLE / "my_linkedin_data").exists():
    shutil.copytree(BUNDLE / "my_linkedin_data", ROOT / "my_linkedin_data")  # first launch: seed your profile

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
FUNNEL_TARGETS = {"ToFU": 4, "MoFU": 3, "BoFU": 1}
FUNNEL_LABELS = {
    "ToFU": "Top of Funnel",
    "MoFU": "Middle of Funnel",
    "BoFU": "Bottom of Funnel",
}
FUNNEL_HUMAN = {"ToFU": "top\u2011of\u2011funnel", "MoFU": "middle\u2011funnel", "BoFU": "bottom\u2011funnel"}  # no-break hyphens
FUNNEL_BLURB = {
    "ToFU": "memes, pop-culture observations, viral trends",
    "MoFU": "vulnerable personal stories, career lessons, identity insights",
    "BoFU": "results, client wins, case studies, metrics",
}

# weekday (0 = Monday) -> funnel slots. 4x ToFU, 3x MoFU, 1x BoFU per week.
WEEKLY_PLAN: dict[int, list[str]] = {
    0: ["ToFU"],
    1: ["MoFU"],
    2: ["ToFU", "MoFU"],
    3: ["BoFU"],
    4: ["ToFU", "MoFU"],
    5: ["ToFU"],
    6: [],
}

PESTER_INTERVAL_MIN = _int("MOMO_PESTER_INTERVAL_MIN", 45)
PESTER_LOOKAHEAD_DAYS = _int("MOMO_PESTER_LOOKAHEAD_DAYS", 3)
PESTER_COOLDOWN_MIN = 180  # don't nag about the same slot more often than this
QUIET_START = _int("MOMO_QUIET_START", 22)
QUIET_END = _int("MOMO_QUIET_END", 8)
SYSTEM_NOTIFICATIONS = os.environ.get("MOMO_SYSTEM_NOTIFICATIONS", "1") == "1"

SCALE = max(2, min(10, _int("MOMO_SCALE", 4)))

ENV_PATH = ROOT / ".env"
# AI drafts (optional). Without a key Momo writes drafts with its offline engine.
CLAUDE_MODEL = os.environ.get("MOMO_CLAUDE_MODEL", "claude-opus-5-5")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_AUTOSTART = os.environ.get("MOMO_TELEGRAM_AUTOSTART", "0") == "1"
