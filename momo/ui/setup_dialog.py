"""First-launch setup: paste your LinkedIn history so Momo can hype you with receipts."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QTabWidget,
                             QVBoxLayout, QWidget)

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
        lay.addWidget(label("<b>Claude API key (optional).</b> With a key, Claude writes full drafts in your voice. "
                            "Without one, Momo uses its offline engine and leaves [brackets] for you to fill. "
                            "Get a key at console.anthropic.com. It's saved only in Momo's .env file.", "Muted", wrap=True))
        self.api_key = QLineEdit(os.environ.get("ANTHROPIC_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-ant-…  (leave empty for offline mode)")
        lay.addWidget(self.api_key)
        return page

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
        from ..writer import save_api_key
        save_setup(config.LINKEDIN_DIR, self.about.toPlainText(), self.posts.toPlainText(), self.hooks.toPlainText())
        if self.voice.toPlainText().strip():
            (config.LINKEDIN_DIR / "voice.md").write_text(self.voice.toPlainText().strip() + "\n", encoding="utf-8")
        if self.api_key.text().strip() != os.environ.get("ANTHROPIC_API_KEY", ""):
            save_api_key(self.api_key.text())
        self.accept()
