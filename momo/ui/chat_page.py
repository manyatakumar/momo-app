"""Brain-dump chat: drop a rough idea and Momo files it, hypes it, writes the post and drops it into your week."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .. import config, services, writer
from .widgets import label, rich, scroll_area
from .worker import run_async

BUBBLE_MAX_W = 352


class DumpInput(QPlainTextEdit):
    submitted = pyqtSignal()

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(e)


class Message(QFrame):
    def __init__(self, text: str, mine: bool) -> None:
        super().__init__()
        self.setObjectName("UserMsg" if mine else "MomoMsg")
        self.setMaximumWidth(BUBBLE_MAX_W if not mine else 290)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 10)
        lay.setSpacing(8)
        self.text = QLabel(rich(text))
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.text)


def flash(button: QPushButton, done: str = "Copied ✓") -> None:
    original = button.text()
    button.setText(done)
    QTimer.singleShot(1600, lambda: button.setText(original))


class DraftCard(QFrame):
    """The ready-to-post draft + writing-mode extras, with one-click copies."""

    def __init__(self, draft: writer.Draft, idea_text: str) -> None:
        super().__init__()
        self.setObjectName("DraftCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(label("📝 READY TO POST" + (f" · {draft.format.upper()}" if draft.format else ""), "Section"))
        head.addStretch(1)
        ai = draft.engine != "offline"
        badge = label(f"✨ {writer.ENGINE_LABEL[draft.engine].lower()}" if ai else "offline", "Badge")
        badge.setToolTip(f"Written by {writer.ENGINE_LABEL[draft.engine]} in your voice" if ai
                         else draft.note or "Offline template draft: fill the [fill: …] parts. Add a Gemini or Claude "
                                            "key in LinkedIn setup → Voice & AI for full AI drafts.")
        head.addWidget(badge)
        lay.addLayout(head)
        body = QLabel(draft.text)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setObjectName("DraftText")
        lay.addWidget(body)

        extras = []
        if draft.alt_first_lines:
            extras.append("<b>other first lines</b><br>" + "<br>".join(f"↺ {rich(x)}" for x in draft.alt_first_lines))
        if draft.first_comment:
            extras.append(f"<b>first comment</b><br>{rich(draft.first_comment)}")
        if draft.rationale:
            extras.append(f"<b>why</b> {rich(draft.rationale)}")
        if extras:
            more = QLabel("<br><br>".join(extras))
            more.setTextFormat(Qt.TextFormat.RichText)
            more.setWordWrap(True)
            more.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            more.setObjectName("Muted")
            lay.addWidget(more)
        if draft.note:
            lay.addWidget(label(draft.note, "Muted", wrap=True))

        foot = QHBoxLayout()
        prompt_btn = QPushButton("Copy prompt for any AI")
        prompt_btn.setObjectName("Ghost")
        prompt_btn.setToolTip("Copies your full brief (voice, hits, hooks, this idea). Paste it into Gemini, "
                              "ChatGPT, Claude.ai… for free.")
        prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prompt_btn.clicked.connect(lambda: (QGuiApplication.clipboard().setText(services.copy_prompt(idea_text)),
                                            flash(prompt_btn)))
        foot.addWidget(prompt_btn)
        foot.addStretch(1)
        copy_btn = QPushButton("Copy draft")
        copy_btn.setObjectName("SmallGhost")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: (QGuiApplication.clipboard().setText(draft.text), flash(copy_btn)))
        foot.addWidget(copy_btn)
        lay.addLayout(foot)


class Typing(Message):
    def __init__(self, what: str) -> None:
        super().__init__(what, mine=False)
        self._what, self._dots = what, 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(380)

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.text.setText(rich(self._what + "." * self._dots))


class ChatPage(QWidget):
    data_changed = pyqtSignal()
    idea_added = pyqtSignal(object)  # IngestResult
    busy_changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._pending = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._feed = QWidget()
        self._feed_lay = QVBoxLayout(self._feed)
        self._feed_lay.setContentsMargins(0, 4, 4, 4)
        self._feed_lay.setSpacing(10)
        self._feed_lay.addStretch(1)
        self._scroll = scroll_area(self._feed)
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _lo, hi: bar.setValue(hi))  # new message -> follow it
        root.addWidget(self._scroll, 1)

        self.input = DumpInput()
        self.input.setPlaceholderText("dump a rough idea… (Enter to send, Shift+Enter for a new line)")
        self.input.setFixedHeight(74)
        self.input.submitted.connect(self.submit)
        send = QPushButton("Send")
        send.setFixedHeight(44)
        send.clicked.connect(self.submit)
        self.prompt_btn = QPushButton("📋 Prompt")
        self.prompt_btn.setObjectName("Ghost")
        self.prompt_btn.setFixedHeight(26)
        self.prompt_btn.setToolTip("Copy a ready prompt for what you typed. Paste it into any AI (Gemini, ChatGPT, "
                                   "Claude.ai…). Nothing is saved.")
        self.prompt_btn.clicked.connect(self.copy_prompt)
        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(send)
        buttons.addWidget(self.prompt_btn)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input, 1)
        row.addLayout(buttons)
        root.addLayout(row)

        engine = (f"{writer.ENGINE_LABEL[writer.provider()]}, in your voice" if writer.ai_available()
                  else "my offline engine (add a Gemini or Claude key for full AI drafts)")
        self.add_momo("mrrp. drop any half-baked idea here, messy is fine.\n"
                      f"i'll file it into your funnel, hype you with your own receipts, write the post with {engine}, "
                      "and drop it into your week. 🐾")

    # ------------------------------------------------------------------ feed
    def _append(self, widget: QWidget, mine: bool) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if mine:
            row.addStretch(1)
        row.addWidget(widget)
        if not mine:
            row.addStretch(1)
        self._feed_lay.addLayout(row)
        while self._feed_lay.count() > 61:  # trim very long sessions so the feed stays snappy
            self._remove_row(self._feed_lay.takeAt(1))

    @staticmethod
    def _remove_row(item) -> None:
        if item and item.layout():
            while item.layout().count():
                w = item.layout().takeAt(0).widget()
                if w:
                    w.deleteLater()

    def _remove_widget(self, widget: QWidget) -> None:
        for i in range(self._feed_lay.count()):
            item = self._feed_lay.itemAt(i)
            if item.layout() and item.layout().indexOf(widget) >= 0:
                self._remove_row(self._feed_lay.takeAt(i))
                return

    def add_user(self, text: str) -> None:
        self._append(Message(text, mine=True), True)

    def add_momo(self, text: str) -> Message:
        msg = Message(text, mine=False)
        self._append(msg, False)
        return msg

    def add_result(self, result: services.IngestResult) -> None:
        msg = Message(result.message, mine=False)
        msg.layout().addWidget(DraftCard(result.draft, result.idea.text))
        msg.layout().addLayout(self._funnel_chips(result.idea.id, result.idea.funnel))
        self._append(msg, False)

    def _funnel_chips(self, idea_id: int, current: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(label("wrong funnel?", "Muted"))
        group = QButtonGroup(row)
        group.setExclusive(True)
        for f in config.FUNNELS:
            chip = QPushButton(f)
            chip.setObjectName("Chip")
            chip.setCheckable(True)
            chip.setChecked(f == current)
            chip.setToolTip(f"{config.FUNNEL_LABELS[f]}: {config.FUNNEL_BLURB[f]}. Click to rewrite it as {f}.")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, fn=f: self._reclassify(idea_id, fn))
            group.addButton(chip)
            row.addWidget(chip)
        row.addStretch(1)
        return row

    # --------------------------------------------------------------- actions
    def _busy(self, delta: int) -> None:
        was = self._pending > 0
        self._pending += delta
        if (self._pending > 0) != was:
            self.busy_changed.emit(self._pending > 0)

    def submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.add_user(text)
        typing = Typing("✍️ writing your draft")
        self._append(typing, False)
        self._busy(+1)

        def done(result: services.IngestResult) -> None:
            self._busy(-1)
            self._remove_widget(typing)
            self.add_result(result)
            self.idea_added.emit(result)
            self.data_changed.emit()

        def failed(err: str) -> None:
            self._busy(-1)
            self._remove_widget(typing)
            self.add_momo(f"😿 something broke while saving that idea: {err}")

        run_async(services.ingest_idea, text, "desktop", on_done=done, on_error=failed)

    def _reclassify(self, idea_id: int, funnel: str) -> None:
        typing = Typing(f"✍️ rewriting it as a {funnel} post")
        self._append(typing, False)
        self._busy(+1)

        def done(result: services.IngestResult | None) -> None:
            self._busy(-1)
            self._remove_widget(typing)
            if result:
                self.add_result(result)
                self.data_changed.emit()

        def failed(err: str) -> None:
            self._busy(-1)
            self._remove_widget(typing)
            self.add_momo(f"😿 couldn't move it: {err}")

        run_async(services.reclassify, idea_id, funnel, on_done=done, on_error=failed)

    def copy_prompt(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            self.add_momo("type the idea first, then hit 📋 Prompt. i'll copy a brief you can paste into any AI.")
            return
        QGuiApplication.clipboard().setText(services.copy_prompt(text))
        flash(self.prompt_btn, "Copied ✓")
        self.add_momo("📋 copied! paste it into Gemini / ChatGPT / Claude.ai. it has your voice, hits and all 10 hooks. "
                      "(press Enter instead if you want me to write and schedule it.)")

    def focus_input(self) -> None:
        self.input.setFocus()
