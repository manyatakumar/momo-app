"""Run slow work (Gemini drafts, DB writes) off the UI thread so Momo never stutters."""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], args: tuple) -> None:
        super().__init__()
        self.fn, self.args = fn, args
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI instead of crashing a thread
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.done.emit(result)


_live: set[_Task] = set()  # keep signal objects alive until their queued signals are delivered


def run_async(fn: Callable[..., Any], *args: Any, on_done: Callable[[Any], None],
              on_error: Callable[[str], None] | None = None) -> None:
    task = _Task(fn, args)
    task.setAutoDelete(False)
    _live.add(task)

    def finish(cb: Callable | None, value: Any) -> None:
        _live.discard(task)
        if cb:
            cb(value)

    task.signals.done.connect(lambda r: finish(on_done, r))
    task.signals.failed.connect(lambda e: finish(on_error, e))
    QThreadPool.globalInstance().start(task)
