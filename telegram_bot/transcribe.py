"""Optional, offline voice-note transcription via faster-whisper (pip install -r requirements-voice.txt)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)
_model = None


def available() -> bool:
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


def transcribe(path: Path) -> str | None:
    """Return the transcript, or None if faster-whisper isn't installed or decoding failed."""
    global _model
    if not available():
        return None
    from faster_whisper import WhisperModel

    try:
        if _model is None:
            size = os.environ.get("WHISPER_MODEL", "base")
            log.info("Loading whisper model %r (first run downloads it)…", size)
            _model = WhisperModel(size, device="auto", compute_type="int8")
        segments, _info = _model.transcribe(str(path), vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip() or None
    except Exception:  # noqa: BLE001 - never crash the bot over one bad voice note
        log.exception("Transcription failed for %s", path)
        return None
