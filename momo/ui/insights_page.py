"""What Momo learned from my_linkedin_data/."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .. import services
from ..analyzer import fmt_num
from . import theme
from .widgets import label, scroll_area


def card(*widgets: QWidget, spacing: int = 6) -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w)
    return f


class InsightsPage(QWidget):
    request_setup = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._inner = QWidget()
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(0, 0, 4, 0)
        self._lay.setSpacing(10)
        root.addWidget(scroll_area(self._inner))
        self.refresh()

    def _clear(self) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        self._clear()
        prof = services.get_profile()
        setup_btn = QPushButton("Update my LinkedIn data" if prof.has_data else "Set up my LinkedIn data")
        setup_btn.setObjectName("Ghost" if prof.has_data else "")
        setup_btn.clicked.connect(self.request_setup.emit)

        if not prof.measured:
            msg = ("I can see your profile, but no post metrics yet. Add impressions/comments to your past posts "
                   "so I can hype you with receipts." if prof.has_data else
                   "I haven't studied your LinkedIn yet. Paste your past posts, About section and metrics, and "
                   "I'll learn which hooks make your audience stop scrolling.")
            self._lay.addWidget(card(label("🐾  Nothing to analyze (yet)", "Section"), label(msg, "Muted", wrap=True), setup_btn))
            self._lay.addStretch(1)
            return

        best_day = prof.best_weekday()
        b = prof.baselines
        if b.get("total_posts"):
            line = (f"<b>{int(b['total_posts'])}</b> posts · avg <b>{fmt_num(prof.avg_impressions)}</b> · median "
                    f"<b>{fmt_num(int(b.get('median_impressions', 0)))}</b> impressions"
                    + (f"<br>engagement rate <b>{b['engagement_rate']:g}%</b>" if b.get("engagement_rate") else "")
                    + "".join(f"<br>{f} median <b>{fmt_num(int(b[f.lower() + '_median']))}</b>"
                              for f in ("ToFU", "MoFU", "BoFU") if b.get(f.lower() + "_median")))
        else:
            line = f"<b>{len(prof.posts)}</b> posts studied · avg <b>{fmt_num(prof.avg_impressions)}</b> impressions"
        summary = label(line + (f"<br>Best day: <b>{best_day[0]}</b> ({fmt_num(best_day[1])} avg)" if best_day else ""),
                        wrap=True)
        summary.setTextFormat(Qt.TextFormat.RichText)
        self._lay.addWidget(card(label("YOUR NUMBERS", "Section"), summary))

        stats = prof.archetype_stats()
        rows = [label("WHAT WORKS FOR YOU", "Section")]
        top_avg = stats[0].avg_impressions if stats else 1
        for s in stats[:6]:
            line = QWidget()
            lay = QVBoxLayout(line)
            lay.setContentsMargins(0, 2, 0, 2)
            lay.setSpacing(3)
            head = QHBoxLayout()
            head.addWidget(label(s.label.capitalize()))
            head.addStretch(1)
            head.addWidget(label(f"{fmt_num(s.avg_impressions)} · {s.lift:.1f}x", "Muted"))
            lay.addLayout(head)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setRange(0, 100)
            bar.setValue(int(100 * s.avg_impressions / top_avg))
            bar.setStyleSheet(f"QProgressBar {{ background: {theme.SAGE_MIST}; border: none; border-radius: 3px; }}"
                              f"QProgressBar::chunk {{ background: {theme.SAGE}; border-radius: 3px; }}")
            lay.addWidget(bar)
            rows.append(line)
        self._lay.addWidget(card(*rows))

        winners = [label("HALL OF FAME", "Section")]
        for p in prof.top_posts(3):
            hook = QLabel(f"“{p.hook}”")
            hook.setWordWrap(True)
            meta = label(f"{fmt_num(p.impressions)} impressions · {p.comments} comments · {p.label}"
                         + (f" · {p.date.strftime('%b')} {p.date.day}" if p.date else ""), "Muted", wrap=True)
            winners += [hook, meta]
        self._lay.addWidget(card(*winners))

        if prof.viral_hooks:
            hooks = [label("VIRAL HOOKS ON FILE", "Section")]
            hooks += [label(f"• {h}", wrap=True) for h in prof.viral_hooks[:6]]
            self._lay.addWidget(card(*hooks, spacing=4))

        self._lay.addWidget(setup_btn)
        self._lay.addStretch(1)
