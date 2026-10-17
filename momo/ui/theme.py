"""Cream + sage palette and the global Qt stylesheet."""
CREAM = "#FBF7EE"
CREAM_DEEP = "#F4EDDF"
BEIGE = "#EADFCB"
PAPER = "#FFFDF8"
SAGE = "#7FA07A"
SAGE_DARK = "#5C7D59"
SAGE_LIGHT = "#DCE8D5"
SAGE_MIST = "#EDF3E9"
INK = "#3B4739"
INK_SOFT = "#7D8779"
BORDER = "#D6DFCE"
CLAY = "#CF9C84"

FUNNEL_COLORS = {"ToFU": "#A6C29E", "MoFU": SAGE, "BoFU": SAGE_DARK}
FONT_FAMILIES = ["SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]

STYLESHEET = f"""
* {{ color: {INK}; font-size: 13px; }}
QWidget#Transparent, QScrollArea, QScrollArea > QWidget > QWidget#Transparent {{ background: transparent; border: none; }}

QLabel#Title {{ font-size: 18px; font-weight: 700; color: {SAGE_DARK}; }}
QLabel#Subtitle, QLabel#Muted {{ color: {INK_SOFT}; font-size: 12px; }}
QLabel#Section {{ font-size: 12px; font-weight: 700; color: {SAGE_DARK}; letter-spacing: 0.5px; }}
QLabel#DayLabel {{ font-weight: 700; color: {INK}; }}
QLabel#DayLabelToday {{ font-weight: 700; color: {SAGE_DARK}; }}

QPushButton {{
    background: {SAGE}; color: white; border: none; border-radius: 10px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {SAGE_DARK}; }}
QPushButton:pressed {{ background: #4E6C4B; }}
QPushButton:disabled {{ background: {BEIGE}; color: {INK_SOFT}; }}
QPushButton#Ghost {{ background: transparent; color: {SAGE_DARK}; border: 1px solid {BORDER}; }}
QPushButton#Ghost:hover {{ background: {SAGE_MIST}; border-color: {SAGE}; }}
QPushButton#IconButton {{ background: transparent; color: {INK_SOFT}; border-radius: 8px; padding: 2px 8px; font-size: 16px; }}
QPushButton#IconButton:hover {{ background: {SAGE_MIST}; color: {SAGE_DARK}; }}
QPushButton#Nav {{ background: transparent; color: {INK_SOFT}; border-radius: 9px; padding: 6px 10px; }}
QPushButton#Nav:hover {{ color: {SAGE_DARK}; background: {SAGE_MIST}; }}
QPushButton#Nav:checked {{ background: {SAGE}; color: white; }}
QPushButton#Chip {{
    background: {PAPER}; color: {INK_SOFT}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 2px 9px; font-size: 11px; font-weight: 600;
}}
QPushButton#Chip:hover {{ border-color: {SAGE}; color: {SAGE_DARK}; }}
QPushButton#Chip:checked {{ background: {SAGE}; border-color: {SAGE}; color: white; }}

QFrame#NavBar {{ background: {CREAM_DEEP}; border-radius: 11px; }}
QFrame#Card {{ background: {PAPER}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#MomoMsg {{ background: {CREAM_DEEP}; border: 1px solid {BORDER}; border-radius: 14px; border-top-left-radius: 4px; }}
QFrame#UserMsg {{ background: {SAGE}; border-radius: 14px; border-top-right-radius: 4px; }}
QFrame#UserMsg QLabel {{ color: white; }}
QFrame#DraftCard {{ background: {PAPER}; border: 1px solid {BORDER}; border-left: 3px solid {SAGE}; border-radius: 10px; }}
QFrame#DraftCard QLabel#DraftText {{ color: {INK}; font-size: 13px; }}
QLabel#Badge {{ background: {SAGE_LIGHT}; color: {SAGE_DARK}; border-radius: 8px; padding: 1px 7px; font-size: 10px; font-weight: 700; }}
QPushButton#SmallGhost {{ background: {SAGE}; color: white; border-radius: 8px; padding: 4px 11px; font-size: 12px; }}
QPushButton#SmallGhost:hover {{ background: {SAGE_DARK}; }}
QFrame#Header {{ background: {SAGE_MIST}; border: 1px solid {SAGE_LIGHT}; border-radius: 14px; }}
QLabel#Status {{ color: {SAGE_DARK}; font-size: 11px; font-weight: 600; }}
QFrame#Divider {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

QPlainTextEdit, QTextEdit, QLineEdit, QSpinBox {{
    background: {PAPER}; border: 1px solid {BORDER}; border-radius: 12px; padding: 8px;
    selection-background-color: {SAGE_LIGHT}; selection-color: {INK};
}}
QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {SAGE}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {SAGE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}

QMenu {{ background: {CREAM}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SAGE_LIGHT}; color: {INK}; }}
QMenu::item:disabled {{ color: {INK_SOFT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}

QToolTip {{ background: {CREAM}; color: {INK}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}

QDialog {{ background: {CREAM}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 12px; background: {CREAM}; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {INK_SOFT}; padding: 7px 14px; margin-right: 4px;
    border-top-left-radius: 9px; border-top-right-radius: 9px; font-weight: 600;
}}
QTabBar::tab:selected {{ background: {SAGE}; color: white; }}
QTabBar::tab:hover:!selected {{ background: {SAGE_MIST}; color: {SAGE_DARK}; }}
"""
