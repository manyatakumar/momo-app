"""Wires Momo together: pet window, bubble, drawer, focus/pester controllers, tray and phone sync."""
from __future__ import annotations

import os
import random
import signal
import sys
from typing import Callable

from PyQt6.QtCore import QObject, QPoint, QProcess, QSettings, Qt, QTimer, QUrl
from PyQt6.QtGui import QCursor, QDesktopServices, QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QSystemTrayIcon

from . import analyzer, config, db, services
from .analyzer import fmt_num, plural
from .controllers import FocusController, PesterController
from .ui import theme
from .ui.bubble import SpeechBubble
from .ui.drawer import Drawer
from .ui.pet_window import PetWindow
from .ui.setup_dialog import SetupDialog
from .ui.sprites import cat_icon

GREETINGS = (
    "Mrrp! Momo reporting for hype duty. 🐾",
    "I'm here. Got any ideas worth going viral?",
    "Back on my corner. Click me to brain-dump.",
)
FOCUS_PRESETS = (25, 55, 90)
SYNC_POLL_MS = 4000


class MomoApp(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        db.init()
        self._bubble_action: Callable[[], None] | None = None
        self._bot: QProcess | None = None

        self.pet = PetWindow(config.SCALE)
        self.bubble = SpeechBubble()
        self.drawer = Drawer()
        self.bubble.avoid = self.drawer
        self.focus = FocusController(self)
        self.pester = PesterController(self)

        self.pet.clicked.connect(self.on_pet_clicked)
        self.pet.hovered.connect(self.focus.scold)
        self.pet.moved.connect(self._follow_pet)
        self.pet.drag_finished.connect(self._save_position)
        self.pet.context_requested.connect(self.show_menu)
        self.bubble.clicked.connect(self._on_bubble_clicked)
        self.drawer.focus_requested.connect(lambda: self.focus_menu(QCursor.pos()))
        self.drawer.setup_requested.connect(self.run_setup)
        self.drawer.chat.idea_added.connect(lambda _r: self.pet.set_mode("happy", seconds=2.5))

        self._setup_tray()

        self._last_seen_id = db.max_idea_id()
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._poll_phone_ideas)
        self._sync_timer.start(SYNC_POLL_MS)

        pos = db.kv_get("pet_pos")
        if not (pos and self.pet.restore_position(*map(int, pos.split(",")))):
            self.pet.snap_to_corner()
        self.pet.show()
        self._maybe_start_bot()
        QTimer.singleShot(700, self._first_run_or_greet)

    # ------------------------------------------------------------- speech
    def say(self, text: str, duration_ms: int = 6000, fixed_width: int | None = None,
            on_click: Callable[[], None] | None = None) -> None:
        self._bubble_action = on_click
        self.bubble.say(text, self.pet, duration_ms, fixed_width)

    def notify(self, title: str, message: str) -> None:
        if config.SYSTEM_NOTIFICATIONS and self.tray and self.tray.supportsMessages():
            self.tray.showMessage(title, message, cat_icon(), 7000)

    def _on_bubble_clicked(self) -> None:
        action, self._bubble_action = self._bubble_action, None
        if action:
            action()

    # ------------------------------------------------------------- pet
    def on_pet_clicked(self) -> None:
        if self.focus.active:
            self.focus.scold()
            return
        if self.bubble.isVisible() and self._bubble_action:
            self._on_bubble_clicked()
            self.bubble.hide()
            return
        self.bubble.hide()
        self.drawer.toggle(self.pet)
        self._restack_bubble()

    def open_drawer(self, page: str | None = None) -> None:
        if not self.focus.active:
            self.bubble.hide()
        self.drawer.open(self.pet, page)
        self._restack_bubble()

    def _restack_bubble(self) -> None:
        if self.bubble.isVisible():
            self.bubble.reposition()
            self.bubble.raise_()

    def _follow_pet(self) -> None:
        if self.drawer.isVisible():
            self.drawer.place_near(self.pet)
        if self.bubble.isVisible():
            self.bubble.reposition()

    def _save_position(self) -> None:
        db.kv_set("pet_pos", f"{self.pet.x()},{self.pet.y()}")

    def snap(self) -> None:
        self.pet.snap_to_corner()
        self._save_position()

    def toggle_visible(self) -> None:
        if self.pet.isVisible():
            self.pet.hide()
            self.bubble.hide()
            self.drawer.hide()
        else:
            self.pet.show()
            self.pet.raise_()

    # ------------------------------------------------------------- menus
    def _build_menu(self, menu: QMenu) -> QMenu:
        menu.addAction("💬  Brain dump", lambda: self.open_drawer("chat"))
        menu.addAction("🗓  This week", lambda: self.open_drawer("week"))
        menu.addAction("📈  Insights", lambda: self.open_drawer("insights"))
        menu.addSeparator()
        if self.focus.active:
            menu.addAction("⏹  End focus session", self.focus.stop)
        else:
            focus = menu.addMenu("⏱  Focus mode")
            self._fill_focus_menu(focus)
        menu.addAction("🔔  Check my slots now", lambda: self.pester.check(force=True))
        menu.addSeparator()
        menu.addAction("🧠  LinkedIn setup…", self.run_setup)
        menu.addAction("↘  Snap to corner", self.snap)
        menu.addAction("🙈  Hide Momo" if self.pet.isVisible() else "🐾  Show Momo", self.toggle_visible)
        menu.addAction("📂  Open my Momo folder",
                       lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.ROOT))))
        if sys.platform == "win32" and config.FROZEN:
            auto = menu.addAction("🚀  Start Momo with Windows")
            auto.setCheckable(True)
            auto.setChecked(autostart_enabled())
            auto.toggled.connect(set_autostart)
        menu.addSeparator()
        menu.addAction("Quit Momo", self.quit)
        return menu

    def show_menu(self, pos: QPoint) -> None:
        self._build_menu(QMenu()).exec(pos)

    def _fill_focus_menu(self, menu: QMenu) -> None:
        for m in FOCUS_PRESETS:
            menu.addAction(f"{m} minutes", lambda mm=m: self.focus.start(mm))
        menu.addAction("Custom…", self._custom_focus)

    def focus_menu(self, pos: QPoint) -> None:
        menu = QMenu()
        if self.focus.active:
            menu.addAction("⏹  End focus session", self.focus.stop)
        else:
            self._fill_focus_menu(menu)
        menu.exec(pos)

    def _custom_focus(self) -> None:
        minutes, ok = QInputDialog.getInt(None, "Focus mode", "How many minutes will you focus?", 45, 1, 240)
        if ok:
            self.focus.start(minutes)

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(cat_icon(), self)
        self.tray.setToolTip("Momo — your content hype-cat")
        self._tray_menu = QMenu()
        self._tray_menu.aboutToShow.connect(lambda: (self._tray_menu.clear(), self._build_menu(self._tray_menu)))
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(
            lambda reason: self.open_drawer() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(lambda: self.open_drawer("week"))
        self.tray.show()

    # ------------------------------------------------------------- setup
    def _first_run_or_greet(self) -> None:
        if not analyzer.folder_has_data(config.LINKEDIN_DIR):
            self.say("Hi, I'm Momo! 🐾 Before I can hype you up, I need to study your LinkedIn. "
                     "Paste your past posts & metrics?", 9000)
            QTimer.singleShot(900, self.run_setup)
        else:
            self.pet.set_mode("happy", seconds=2)
            self.say(random.choice(GREETINGS), 4500)

    def run_setup(self) -> None:
        dlg = SetupDialog()
        if dlg.exec():
            profile = services.get_profile(force=True)
            self.drawer.refresh_all()
            self.pet.set_mode("happy", seconds=3)
            stats = profile.archetype_stats()
            if stats:
                best = stats[0]
                self.say(f"Studied {len(profile.posts)} posts! 🧠 Your secret weapon: {plural(best.label)} "
                         f"(avg {fmt_num(best.avg_impressions)} impressions). Let's make more of those.", 10000,
                         on_click=lambda: self.open_drawer("insights"))
            elif profile.has_data:
                self.say("Saved! Add impressions to your posts and I'll find your winning formula. 🐾", 7000)
        elif not analyzer.folder_has_data(config.LINKEDIN_DIR):
            self.say("No worries — right-click me → LinkedIn setup whenever you're ready.", 6000)

    # ------------------------------------------------------------- phone sync
    def _poll_phone_ideas(self) -> None:
        try:
            new = db.ideas_after(self._last_seen_id)
        except Exception:  # DB briefly locked by the bot: try again next tick
            return
        if not new:
            return
        self._last_seen_id = max(i.id for i in new)
        self.drawer.refresh()
        if self.focus.active:
            return
        latest = new[-1]
        snippet = latest.text if len(latest.text) < 70 else latest.text[:69] + "…"
        extra = f" (+{len(new) - 1} more)" if len(new) > 1 else ""
        self.pet.set_mode("happy", seconds=2.5)
        self.say(f"📱 New idea from your phone{extra} → {latest.funnel}\n“{snippet}”", 8000,
                 on_click=lambda: self.open_drawer("week"))

    def _maybe_start_bot(self) -> None:
        if not (config.TELEGRAM_AUTOSTART and config.TELEGRAM_BOT_TOKEN):
            return
        self._bot = QProcess(self)
        self._bot.setWorkingDirectory(str(config.ROOT))
        self._bot.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        if config.FROZEN:  # Momo.exe doubles as the bot: Momo.exe --telegram-bot
            self._bot.start(sys.executable, ["--telegram-bot"])
        else:
            self._bot.start(sys.executable, ["-m", "telegram_bot.bot"])

    def quit(self) -> None:
        if self._bot and self._bot.state() != QProcess.ProcessState.NotRunning:
            self._bot.terminate()
            if not self._bot.waitForFinished(3000):
                self._bot.kill()
        if self.tray:
            self.tray.hide()
        self.qapp.quit()


_RUN_KEY = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"
_INSTANCE = "momo-desktop-pet"


def autostart_enabled() -> bool:
    return QSettings(_RUN_KEY, QSettings.Format.NativeFormat).contains("Momo")


def set_autostart(on: bool) -> None:
    s = QSettings(_RUN_KEY, QSettings.Format.NativeFormat)
    if on:
        s.setValue("Momo", f'"{sys.executable}"')
    else:
        s.remove("Momo")


def _already_running() -> bool:
    """If Momo is already open, ask it to pop its drawer and report True."""
    sock = QLocalSocket()
    sock.connectToServer(_INSTANCE)
    if sock.waitForConnected(400):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return True
    return False


def main(selftest: bool = False) -> None:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    if not selftest and _already_running():
        return
    qapp.setApplicationName("Momo")
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(cat_icon())
    font = QFont()
    font.setFamilies(theme.FONT_FAMILIES)
    font.setPointSizeF(10.5 if sys.platform != "darwin" else 13)
    qapp.setFont(font)
    qapp.setStyle("Fusion")  # consistent look on macOS + Windows; QSS does the rest
    qapp.setStyleSheet(theme.STYLESHEET)

    momo = MomoApp(qapp)
    server = QLocalServer()
    if not selftest:  # one Momo at a time: opening it again just shows the drawer
        QLocalServer.removeServer(_INSTANCE)
        server.listen(_INSTANCE)
        server.newConnection.connect(lambda: (server.nextPendingConnection(), momo.pet.show(), momo.open_drawer()))
    if selftest:
        _run_selftest(qapp, momo)
    signal.signal(signal.SIGINT, lambda *_: momo.quit())
    # Let Python handle Ctrl+C while the Qt loop runs.
    ping = QTimer()
    ping.start(500)
    ping.timeout.connect(lambda: None)
    sys.exit(qapp.exec())


def _run_selftest(qapp: QApplication, momo: MomoApp) -> None:
    """Momo.exe --selftest: boot the real UI, write one draft, exit 0 (used by the build to catch packaging bugs)."""
    def check() -> None:
        try:
            result = services.ingest_idea("my mom cried when i left for bangalore. i learned strong isn't silent.")
            assert result.draft.text and result.idea.scheduled_date
            momo.open_drawer("week")
            momo.focus.start(1)
            momo.focus.stop()
            assert momo.pet.isVisible()
        except Exception as exc:  # noqa: BLE001
            (config.ROOT / "selftest.log").write_text(repr(exc), encoding="utf-8")
            qapp.exit(1)
            return
        (config.ROOT / "selftest.log").write_text("ok", encoding="utf-8")
        qapp.exit(0)
    QTimer.singleShot(2500, check)
