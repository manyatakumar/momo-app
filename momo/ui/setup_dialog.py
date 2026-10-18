"""First-launch setup: paste your LinkedIn history so Momo can hype you with receipts."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton,
                             QTabWidget, QVBoxLayout, QWidget)

from .. import config
from .sprites import cat_icon
from .widgets import label

POSTS_PLACEHOLDER = """Paste past posts separated by a line with three dashes.
Metric lines are optional but make Momo much smarter:

date: 2026-10-06
impressions: 30k
comments: 214
I got laid off on a Tuesday. By Friday I had a plan…
---
date: 2026-09-29
metrics: 12.4k impressions, 96 comments
Unpopular opinion: "post every day" is the worst advice…"""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


class SetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("momo · your LinkedIn brain")
        self.setWindowIcon(cat_icon())
        self.resize(640, 680)
        folder = config.LINKEDIN_DIR

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(10)
        root.addWidget(label("Teach Momo what makes you go viral 🐾", "Title"))
        root.addWidget(label(
            f"Everything stays on your computer in <b>{folder.name}/</b>. Paste as much or as little as you like; "
            "you can update it any time from the Insights tab.", "Muted", wrap=True))

        tabs = QTabWidget()
        self.posts = self._editor(POSTS_PLACEHOLDER, _read(folder / "posts.md"))
        self.about = self._editor("Paste your LinkedIn “About” section…", _read(folder / "about.md"))
        self.hooks = self._editor("One hook per line — the opening lines that pulled people in.\n\n"
                                  "I got laid off on a Tuesday.\nUnpopular opinion: …", _read(folder / "viral_hooks.md"))
        posts_tab = QWidget()
        pl = QVBoxLayout(posts_tab)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.addWidget(self.posts, 1)
        csv_row = QHBoxLayout()
        self.csv_status = label("Have a LinkedIn analytics export? Import the CSV directly.", "Muted", wrap=True)
        csv_btn = QPushButton("Import CSV…")
        csv_btn.setObjectName("Ghost")
        csv_btn.clicked.connect(self._import_csv)
        csv_row.addWidget(self.csv_status, 1)
        csv_row.addWidget(csv_btn)
        pl.addLayout(csv_row)
        tabs.addTab(posts_tab, "Past posts && metrics")
        tabs.addTab(self._wrap(self.about), "About section")
        tabs.addTab(self._wrap(self.hooks), "Viral hooks")
        tabs.addTab(self._voice_tab(folder), "Voice && AI")
        root.addWidget(tabs, 1)

        buttons = QHBoxLayout()
        later = QPushButton("Cancel")
        later.setObjectName("Ghost")
        later.clicked.connect(self.reject)
        save = QPushButton("Save && analyze")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addStretch(1)
        buttons.addWidget(later)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _voice_tab(self, folder: Path) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(label("<b>How you write.</b> Momo follows these rules for every draft.", wrap=True))
        self.voice = self._editor("- lowercase, conversational\n- short punchy lines\n- → arrows for sequences…",
                                  _read(folder / "voice.md"))
        lay.addWidget(self.voice, 1)

        lay.addWidget(label("<b>Gemini API key.</b> With it, Gemini writes your drafts. Without it, Momo uses its "
                            "offline engine and leaves [fill: …] spots. Get a free key at aistudio.google.com/apikey. "
                            "It's saved only on this computer.", wrap=True))
        row = QHBoxLayout()
        self.gemini_key = self._key_field("GEMINI_API_KEY", "paste your Gemini API key (starts with AIza…)")
        row.addWidget(self.gemini_key, 1)
        self.test_btn = QPushButton("Test")
        self.test_btn.setObjectName("Ghost")
        self.test_btn.clicked.connect(self._test_key)
        row.addWidget(self.test_btn)
        lay.addLayout(row)
        self.key_status = label("", "Muted", wrap=True)
        lay.addWidget(self.key_status)
        return page

    def _test_key(self) -> None:
        from ..writer import check_gemini_key
        from .worker import run_async

        self.test_btn.setEnabled(False)
        self.key_status.setText("checking with Google…")

        def ok(model: str) -> None:
            self.test_btn.setEnabled(True)
            self.key_status.setText(f"✅ connected! Momo will write with {model}. Click Save & analyze to keep it.")

        def bad(err: str) -> None:
            self.test_btn.setEnabled(True)
            self.key_status.setText("❌ " + err.split(": ", 1)[-1])

        run_async(check_gemini_key, self.gemini_key.text(), on_done=ok, on_error=bad)

    @staticmethod
    def _key_field(env: str, placeholder: str) -> QLineEdit:
        field = QLineEdit(os.environ.get(env, ""))
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(placeholder)
        field.setToolTip(placeholder)
        return field

    @staticmethod
    def _editor(placeholder: str, text: str) -> QPlainTextEdit:
        ed = QPlainTextEdit()
        ed.setPlaceholderText(placeholder)
        ed.setPlainText(text)
        return ed

    @staticmethod
    def _wrap(w: QWidget) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(w)
        return page

    def _import_csv(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import LinkedIn export", str(Path.home()),
                                                "Data files (*.csv *.json *.md *.txt)")
        if not paths:
            return
        config.LINKEDIN_DIR.mkdir(parents=True, exist_ok=True)
        for p in paths:
            shutil.copy2(p, config.LINKEDIN_DIR / Path(p).name)
        self.csv_status.setText("Imported: " + ", ".join(Path(p).name for p in paths))

    def _save(self) -> None:
        from ..analyzer import save_setup
        from ..writer import save_env
        save_setup(config.LINKEDIN_DIR, self.about.toPlainText(), self.posts.toPlainText(), self.hooks.toPlainText())
        if self.voice.toPlainText().strip():
            (config.LINKEDIN_DIR / "voice.md").write_text(self.voice.toPlainText().strip() + "\n", encoding="utf-8")
        # Gemini only: clear provider/Claude settings left over from older versions.
        save_env({"GEMINI_API_KEY": self.gemini_key.text(), "MOMO_AI_PROVIDER": "", "ANTHROPIC_API_KEY": ""})
        self.accept()
