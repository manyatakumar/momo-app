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


class DraftCard(QFrame):
    """The ready-to-post draft with a one-click copy."""

    def __init__(self, draft: writer.Draft) -> None:
        super().__init__()
        self.setObjectName("DraftCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(label("📝 READY TO POST", "Section"))
        head.addStretch(1)
        badge = label("✨ claude" if draft.engine == "claude" else "offline", "Badge")
        badge.setToolTip("Written by Claude in your voice" if draft.engine == "claude"
                         else draft.note or "Offline template draft: fill the [brackets]. Add a Claude API key in "
                                            "LinkedIn setup for full AI drafts.")
        head.addWidget(badge)
        lay.addLayout(head)
        body = QLabel(draft.text)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setObjectName("DraftText")
        lay.addWidget(body)
        foot = QHBoxLayout()
        if draft.note:
            foot.addWidget(label(draft.note, "Muted", wrap=True), 1)
        else:
            foot.addStretch(1)
        self.copy_btn = QPushButton("Copy draft")
        self.copy_btn.setObjectName("SmallGhost")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(lambda: self._copy(draft.text))
        foot.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(foot)

    def _copy(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.copy_btn.setText("Copied ✓")
        QTimer.singleShot(1600, lambda: self.copy_btn.setText("Copy draft"))


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
        send.setFixedHeight(74)
        send.clicked.connect(self.submit)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input, 1)
        row.addWidget(send)
        root.addLayout(row)

        engine = "Claude, in your voice" if writer.ai_available() else "my offline engine (add a Claude key for full AI drafts)"
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
        msg.layout().addWidget(DraftCard(result.draft))
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

    def focus_input(self) -> None:
        self.input.setFocus()
