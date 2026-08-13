"""Glyph Sleuth — which of your fonts can draw this, and what is this character.

Run with:  python app.py
"""
import html
import os
import sys
import time
import unicodedata

# Windows ships legacy .fon bitmap fonts (8514oem, Fixedsys) that DirectWrite
# cannot open, and Qt logs a line every time a UI font lacks OpenType tables for
# some script and falls back. A tool that touches every script on the machine
# triggers hundreds of both. Neither affects rendering.
# Set GLYPH_SLEUTH_FONT_LOG=1 to see them again when debugging a missing glyph.
if not os.environ.get("GLYPH_SLEUTH_FONT_LOG"):
    os.environ.setdefault(
        "QT_LOGGING_RULES", "qt.qpa.fonts=false;qt.text.font.db=false"
    )

from PySide6.QtCore import (QObject, QRunnable, Qt, QThreadPool, QTimer, Signal,  # noqa: E402
                            Slot)
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMainWindow, QPlainTextEdit,
                               QProgressBar, QPushButton, QSplitter,
                               QStackedWidget, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

import chars
import index as fontindex
import langs

APP_NAME = "Glyph Sleuth"

# ---------------------------------------------------------------- appearance

LIGHT = dict(
    vellum="#EAE7DD", panel="#F7F5EF", sunk="#E2DED2", rail="#DFDACB",
    line="#CBC5B2", hair="#DCD7C7", ink="#191A22", ink2="#4B4C58", faint="#7E7C79",
    lapis="#2B3E9B", lapisink="#F2F4FF", lapiswash="#DCE0F6",
    gold="#8A6410", goldwash="#EFE3C4", madder="#9C2B22", madderwash="#F0DCD6",
)
DARK = dict(
    vellum="#14141A", panel="#1B1B23", sunk="#101015", rail="#0E0E13",
    line="#32323F", hair="#26262F", ink="#EDEBE3", ink2="#B7B5AE", faint="#83817C",
    lapis="#8C9BF2", lapisink="#0F1024", lapiswash="#1E2144",
    gold="#D2A238", goldwash="#33280F", madder="#DE7264", madderwash="#3A1A16",
)

DISPLAY_FONT = "Sitka Display, Sitka Heading, Constantia, Georgia, serif"
CHROME_FONT = "Bahnschrift, Segoe UI, system-ui, sans-serif"
DATA_FONT = "Cascadia Mono, Consolas, DejaVu Sans Mono, monospace"

QSS = """
QMainWindow, QWidget {{ background: {panel}; color: {ink};
    font-family: {chrome}; font-size: 13px; }}
QSplitter::handle {{ background: {hair}; width: 1px; }}

#CommandBar {{ background: {panel}; border-bottom: 1px solid {hair}; }}
#Omni {{ background: {sunk}; border: 1px solid {line}; border-radius: 7px;
    padding: 9px 13px; font-family: {data}; font-size: 15px;
    selection-background-color: {lapiswash}; selection-color: {ink}; }}
#Omni:focus {{ border-color: {lapis}; }}
#ParseEcho {{ color: {faint}; font-size: 12px; padding: 2px 3px 0; }}

QPushButton#Mode {{ background: {sunk}; border: 1px solid {line};
    border-radius: 6px; padding: 8px 15px; color: {ink2}; }}
QPushButton#Mode:hover {{ background: {panel}; color: {ink}; }}
QPushButton#Mode:checked {{ background: {lapis}; color: {lapisink};
    border-color: {lapis}; font-weight: 600; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {line};
    border-radius: 6px; padding: 7px 12px; color: {ink2}; }}
QPushButton#Ghost:hover {{ border-color: {lapis}; color: {lapis}; }}

QTreeWidget, QTableWidget {{ background: {panel}; border: 0;
    alternate-background-color: {sunk}; gridline-color: {hair};
    selection-background-color: {lapiswash}; selection-color: {ink}; outline: 0; }}
QTreeWidget::item, QTableWidget::item {{ padding: 5px 4px; border: 0; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{
    background: {lapiswash}; color: {ink}; }}
QHeaderView::section {{ background: {sunk}; color: {faint}; border: 0;
    border-bottom: 1px solid {hair}; padding: 7px 8px;
    font-size: 10px; font-weight: 600; }}
QTableCornerButton::section {{ background: {sunk}; border: 0; }}

QTextBrowser {{ background: {sunk}; border: 0; }}
QPlainTextEdit {{ background: {sunk}; border: 1px solid {line}; border-radius: 7px;
    padding: 8px 10px; font-family: {data}; font-size: 14px;
    selection-background-color: {lapiswash}; selection-color: {ink}; }}
QLineEdit {{ background: {sunk}; border: 1px solid {line}; border-radius: 6px;
    padding: 6px 10px; color: {ink}; }}
QComboBox {{ background: {sunk}; border: 1px solid {line}; border-radius: 6px;
    padding: 6px 10px; color: {ink}; min-width: 150px; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{ background: {panel}; border: 1px solid {line};
    selection-background-color: {lapiswash}; selection-color: {ink}; }}

QStatusBar {{ background: {rail}; border-top: 1px solid {line};
    color: {faint}; font-family: {data}; font-size: 11px; }}
QStatusBar::item {{ border: 0; }}
QProgressBar {{ background: {sunk}; border: 1px solid {line}; border-radius: 4px;
    height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {lapis}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {line}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {line}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {panel}; color: {ink}; border: 1px solid {line}; padding: 5px; }}
"""

DOC_CSS = """
body {{ color: {ink}; font-family: {chrome}; font-size: 13px; }}
a {{ color: {lapis}; text-decoration: none; }}
h3 {{ font-size: 10px; color: {faint}; letter-spacing: 1px;
     text-transform: uppercase; margin: 0 0 6px; }}
.cp {{ font-family: {data}; font-size: 17px; color: {lapis}; font-weight: bold; }}
.nm {{ font-family: {display}; font-size: 17px; color: {ink}; }}
.where {{ color: {faint}; font-size: 12px; }}
.big {{ font-size: 62px; color: {ink}; }}
.k {{ color: {faint}; font-size: 11px; }}
.v {{ font-family: {data}; font-size: 12px; color: {ink}; }}
.chip {{ background: {lapiswash}; color: {lapis}; font-family: {data};
        font-size: 11px; }}
.chipno {{ color: {faint}; font-family: {data}; font-size: 11px; }}
.gold {{ background: {goldwash}; color: {gold}; font-family: {data}; font-size: 11px; }}
.miss {{ background: {madderwash}; color: {madder}; font-family: {data}; font-size: 12px; }}
.rare {{ color: {madder}; font-family: {data}; font-size: 10px; }}
.count {{ color: {faint}; font-family: {data}; font-size: 10px; }}
.cap {{ color: {faint}; font-size: 10px; }}
.glyph {{ color: {ink}; }}
.track {{ background: {hair}; }}
.gap {{ font-size: 6px; }}
"""


# ---------------------------------------------------------------- background work

class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float, str)


class Task(QRunnable):
    """Run a callable off the UI thread. `fn` may accept a progress callback."""

    def __init__(self, fn, wants_progress=False):
        super().__init__()
        self.fn = fn
        self.wants_progress = wants_progress
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            if self.wants_progress:
                result = self.fn(lambda f, m="": self._emit(self.signals.progress, f, m))
            else:
                result = self.fn()
        except Exception as exc:  # surfaced in the status bar, never silent
            self._emit(self.signals.failed, f"{type(exc).__name__}: {exc}")
            return
        self._emit(self.signals.done, result)

    @staticmethod
    def _emit(signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:
            # The window went away mid-task, usually because the app is quitting.
            # There is no one left to tell, and that is not an error.
            pass


# ---------------------------------------------------------------- html helpers

def esc(text):
    return html.escape(str(text), quote=True)


def font_span(family, text, size=34):
    # class="glyph" pins the ink colour so glyphs inside links don't turn blue.
    return (f'<span class="glyph" style="font-family:\'{esc(family)}\'; '
            f'font-size:{size}px">{esc(text)}</span>')


def glyph_or_standin(cp, family=None, size=34):
    label = chars.standin(cp)
    if label:
        return f'<span class="cap">{esc(label)}</span>'
    if family:
        return font_span(family, chr(cp), size)
    return f'<span class="glyph" style="font-size:{size}px">{esc(chr(cp))}</span>'


def kv_table(pairs):
    rows = "".join(
        f'<tr><td class="k" width="86">{esc(k)}</td>'
        f'<td class="v">{v if isinstance(v, str) and v.startswith("<") else esc(v)}</td></tr>'
        for k, v in pairs if v not in (None, "")
    )
    return f'<table cellpadding="2" cellspacing="0" width="100%">{rows}</table>'


def section(title, body):
    return f'<div class="gap">&nbsp;</div><h3>{esc(title)}</h3>{body}<hr>'


def bar(fraction, css):
    """A coverage bar with a visible track behind it."""
    width = max(int(fraction * 100), 1)
    return (
        f'<table cellspacing="0" cellpadding="0" width="100%"><tr>'
        f'<td class="{css}" width="{width}%" height="6"></td>'
        f'<td class="track" width="{100 - width}%" height="6"></td>'
        f"</tr></table>"
    )


def chip_row(labels, css="chip", href=None):
    cells = []
    for label in labels:
        text = f'<span class="{css}">&nbsp;{esc(label)}&nbsp;</span>'
        if href:
            text = f'<a href="{esc(href(label))}">{text}</a>'
        cells.append(text)
    return " ".join(cells)


# ---------------------------------------------------------------- inspector

class Inspector(QTextBrowser):
    """The right-hand pane. Everything it shows is HTML, so links do navigation."""

    navigate = Signal(str, object)  # kind, value

    def __init__(self, palette):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDefaultStyleSheet(
            DOC_CSS.format(display=DISPLAY_FONT, chrome=CHROME_FONT,
                           data=DATA_FONT, **palette)
        )
        self.anchorClicked.connect(self._clicked)
        self.index = None
        self._last = None

    def restyle(self, palette):
        """Qt applies a default stylesheet only to HTML set afterwards, so the
        current view has to be drawn again or it keeps the old theme's colours."""
        self.document().setDefaultStyleSheet(
            DOC_CSS.format(display=DISPLAY_FONT, chrome=CHROME_FONT,
                           data=DATA_FONT, **palette)
        )
        if self._last:
            method, args = self._last
            getattr(self, method)(*args)

    def _clicked(self, url):
        raw = url.toString()
        kind, _, value = raw.partition(":")
        if kind == "cp":
            self.navigate.emit("char", int(value))
        elif kind in ("font", "prop", "block", "lang", "text"):
            self.navigate.emit(kind, value)

    # ---------------------------------------------------------- character view

    def show_char(self, cp, faces):
        self._last = ("show_char", (cp, faces))
        info = chars.describe(cp)
        ch = chr(cp)
        parts = []

        preview = faces[0].family if faces else None
        plate = (
            f'<table cellspacing="0" cellpadding="0" width="100%"><tr>'
            f'<td width="118" align="center">{glyph_or_standin(cp, preview, 62)}</td>'
            f'<td valign="middle">'
            f'<div class="cp">U+{cp:04X}</div>'
            f'<div class="nm">{esc(info.name.title() if info.name.isupper() else info.name)}</div>'
            f'<div class="where">{esc(info.block or "—")} &middot; '
            f'{esc(info.script or "—")} script<br>'
            f'{esc(chars.CATEGORY_NAMES.get(info.category, info.category))} '
            f'({esc(info.category)}) &middot; {info.decimal}</div>'
            f"</td></tr></table>"
        )
        parts.append(plate + '<table cellpadding="6"><tr><td></td></tr></table>')

        if faces:
            cells = "".join(
                f'<td align="center" width="{100 // min(len(faces), 4)}%">'
                f'<a href="font:{esc(f.family)}">{glyph_or_standin(cp, f.family, 34)}</a>'
                f'<div class="cap">{esc(f.family)}</div></td>'
                for f in faces[:4]
            )
            parts.append(section(
                f"Drawn side by side · {len(faces)} of {len(self.index.faces)} faces"
                if self.index else "Drawn side by side",
                f'<table width="100%" cellspacing="4"><tr>{cells}</tr></table>',
            ))
        else:
            parts.append(section(
                "No installed font can draw it",
                '<div class="where">Every face on this machine would fall back '
                "for this character.</div>",
            ))

        parts.append(section("Encodings", kv_table([
            ("UTF-8", info.utf8),
            ("UTF-16", info.utf16),
            ("HTML", info.html),
            ("Escape", info.escape),
            ("Bidi", chars.BIDI_NAMES.get(info.bidi, info.bidi)),
            ("Combining", info.combining or None),
            ("Numeric", info.numeric),
            ("Decomposes", info.decomposition),
        ])))

        matched, unmatched = chars.properties_of(ch)
        parts.append(section(
            f"Matches {len(matched)} of {len(matched) + len(unmatched)} properties",
            chip_row(matched, "chip", lambda p: f"prop:{p}")
            + " " + chip_row(unmatched[:10], "chipno"),
        ))

        try:
            variants = chars.variants(cp, limit=47)
        except Exception:
            variants = []
        if len(variants) > 1:
            cells = []
            for other in variants[:48]:
                n = self.index.count_faces_with(other) if self.index else 0
                # red means "nothing you have can draw this", not merely uncommon
                css = "rare" if n == 0 else "count"
                cells.append(
                    f'<td align="center" width="52">'
                    f'<a href="cp:{other}">{glyph_or_standin(other, None, 20)}</a>'
                    f'<div class="{css}">{n}</div></td>'
                )
            rows = "".join(
                "<tr>" + "".join(cells[i:i + 7]) + "</tr>"
                for i in range(0, len(cells), 7)
            )
            keys = ", ".join(sorted(chars.keywords(info.name))[:3])
            parts.append(section(
                f"{len(variants) - 1} share the name {keys}",
                f'<table cellspacing="3">{rows}</table>'
                '<div class="cap">number below each glyph = installed faces that have it</div>',
            ))

        self.setHtml("".join(parts))

    # ---------------------------------------------------------- font view

    def show_face(self, face):
        self._last = ("show_face", (face,))
        coverage = self.index.block_coverage(face) if self.index else []

        sample = "".join(chr(cp) for cp in (0x41, 0x67, 0x51) if cp in face.codepoints)
        if not sample:
            sample = chr(min(face.codepoints)) if face.codepoints else "?"

        plate = (
            f'<table cellspacing="0" cellpadding="0" width="100%"><tr>'
            f'<td width="118" align="center">{font_span(face.family, sample, 46)}</td>'
            f'<td valign="middle">'
            f'<div class="cp">{esc(face.family)}</div>'
            f'<div class="nm">{esc(face.style or "Regular")}</div>'
            f'<div class="where">{esc(face.format)} &middot; '
            f'{face.glyphs:,} mapped codepoints<br>'
            f'{len(coverage)} blocks touched, '
            f'{sum(1 for _n, h, t in coverage if h == t)} complete</div>'
            f"</td></tr></table>"
        )
        parts = [plate + '<table cellpadding="6"><tr><td></td></tr></table>']
        parts.append(section("File", f'<div class="v">{esc(face.path)}</div>'))

        rows = []
        for name, have, total in coverage[:24]:
            pct = have / total
            colour = "gold" if have == total else ("miss" if pct < 0.15 else "chip")
            rows.append(
                f'<tr><td width="46%"><a href="block:{esc(name)}">{esc(name)}</a></td>'
                f'<td width="38%">{bar(pct, colour)}</td>'
                f'<td align="right" class="v">{have}/{total}</td></tr>'
            )
        parts.append(section(
            "Block coverage",
            f'<table width="100%" cellspacing="2">{"".join(rows)}</table>',
        ))
        self.setHtml("".join(parts))

    # ---------------------------------------------------------- language view

    def show_language(self, lang, needed, rows):
        self._last = ("show_language", (lang, needed, rows))
        families = fontindex.best_per_family(rows)
        best, missing = families[0] if families else (None, needed)
        able = [f for f, m in families if not m]

        plate = (
            f'<div class="cp">{esc(lang.tag)}</div>'
            f'<div class="nm">{esc(lang.name)}</div>'
            f'<div class="where">{esc(lang.full)} &middot; '
            f'{len(needed)} characters needed</div>'
        )
        parts = [plate]

        if able:
            names = ", ".join(f.family for f, _m in families if not _m)
            body = (
                f'<div class="v">{len(able)} of {len(families)} families cover '
                f"it completely.</div>"
                f'<div class="cap">{esc(names[:180])}</div>'
            )
        else:
            body = ('<div class="miss">&nbsp;No installed family covers this '
                    "language completely.&nbsp;</div>")
        parts.append(section("Verdict", body))

        # Combining marks get a dotted circle to sit on, the way a specimen
        # sheet shows them — otherwise they stack onto whatever precedes them.
        sample = "".join(
            ("◌" + c if unicodedata.combining(c) else c)
            for c in sorted(needed)
        )[:200]
        if best and not missing:
            parts.append(section(
                f"Set in {best.family}",
                f'<div>{font_span(best.family, sample, 22)}</div>',
            ))

        if missing:
            parts.append(section(
                f"{best.family if best else 'Best face'} is missing {len(missing)}",
                chip_row(sorted(missing)[:60], "miss", lambda c: f"cp:{ord(c)}"),
            ))

        rows_html = []
        for face, gone in families[:20]:
            have = len(needed) - len(gone)
            pct = have / max(len(needed), 1)
            colour = "gold" if not gone else ("miss" if pct < 0.15 else "chip")
            rows_html.append(
                f'<tr><td width="46%"><a href="font:{esc(face.family)}">'
                f'{esc(face.family)}</a></td>'
                f'<td width="38%">{bar(pct, colour)}</td>'
                f'<td align="right" class="v">{have}/{len(needed)}</td></tr>'
            )
        parts.append(section(
            "Coverage by family",
            f'<table width="100%" cellspacing="2">{"".join(rows_html)}</table>',
        ))
        self.setHtml("".join(parts))

    def show_message(self, title, body):
        self._last = ("show_message", (title, body))
        self.setHtml(f'<h3>{esc(title)}</h3><div class="where">{esc(body)}</div>')


# ---------------------------------------------------------------- main window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 820)
        self.pool = QThreadPool.globalInstance()
        self._running = []  # keeps Tasks alive; the pool only borrows them
        self.index = fontindex.FontIndex()
        self.languages = []
        self.dark = (
            QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        self.current_cp = None
        self.results_kind = "faces"

        self._build()
        self._apply_theme()
        QTimer.singleShot(50, self._start_index)

    # ---------------------------------------------------------- construction

    def _build(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._command_bar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._search_pane())
        self.stack.addWidget(self._convert_pane())
        self.stack.addWidget(self._browse_pane())
        self.stack.addWidget(self._language_pane())

        self.inspector = Inspector(LIGHT)
        self.inspector.navigate.connect(self._navigate)

        self.split = QSplitter(Qt.Horizontal)
        self.split.addWidget(self.stack)
        self.split.addWidget(self.inspector)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        self.split.setSizes([740, 460])
        outer.addWidget(self.split, 1)

        self.setCentralWidget(root)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(150)
        self.progress.setRange(0, 100)
        self.statusBar().addPermanentWidget(self.progress)
        self.progress.hide()
        self.statusBar().showMessage("Starting…")

        for i, key in enumerate("1234"):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{key}"))
            action.triggered.connect(lambda _=False, n=i: self._set_mode(n))
            self.addAction(action)
        focus = QAction(self)
        focus.setShortcut(QKeySequence.Find)
        focus.triggered.connect(lambda: (self.omni.setFocus(), self.omni.selectAll()))
        self.addAction(focus)

    def _command_bar(self):
        bar = QWidget()
        bar.setObjectName("CommandBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.mode_buttons = []
        for i, name in enumerate(("Search", "Convert", "Browse", "Language")):
            button = QPushButton(name)
            button.setObjectName("Mode")
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.clicked.connect(lambda _=False, n=i: self._set_mode(n))
            self.mode_buttons.append(button)
            row.addWidget(button)

        self.omni = QLineEdit()
        self.omni.setObjectName("Omni")
        self.omni.setPlaceholderText(
            "a character, U+2731, 10033, heavy asterisk, \\p{Script=Devanagari}, Quivira…"
        )
        self.omni.returnPressed.connect(self._run_query)
        self.omni.textChanged.connect(self._echo_parse)
        row.addWidget(self.omni, 1)

        self.theme_button = QPushButton("◐")
        self.theme_button.setObjectName("Ghost")
        self.theme_button.setToolTip("Switch between light and dark")
        self.theme_button.clicked.connect(self._toggle_theme)
        row.addWidget(self.theme_button)

        layout.addLayout(row)
        self.echo = QLabel("")
        self.echo.setObjectName("ParseEcho")
        self.echo.setTextFormat(Qt.RichText)
        self.echo.linkActivated.connect(self._echo_link)
        layout.addWidget(self.echo)
        return bar

    def _search_pane(self):
        self.results = QTreeWidget()
        self.results.setColumnCount(5)
        self.results.setHeaderLabels(["", "Family", "Style", "Mapped", "File"])
        self.results.setRootIsDecorated(False)
        self.results.setAlternatingRowColors(True)
        self.results.setSortingEnabled(False)
        self.results.itemSelectionChanged.connect(self._result_selected)
        header = self.results.header()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 56)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        return self.results

    def _convert_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        self.convert_input = QPlainTextEdit()
        self.convert_input.setPlaceholderText(
            "Paste text to break into codepoints — or paste codepoints "
            "(U+0041, 0x41, 65, \\u0041, or raw utf-8 bytes) to turn back into text."
        )
        self.convert_input.setFixedHeight(84)
        self.convert_input.textChanged.connect(self._convert)
        layout.addWidget(self.convert_input)

        self.convert_note = QLabel("")
        self.convert_note.setTextFormat(Qt.RichText)
        layout.addWidget(self.convert_note)

        self.convert_table = QTableWidget(0, 8)
        self.convert_table.setHorizontalHeaderLabels(
            ["", "Codepoint", "Name", "Dec", "Cat", "Script", "UTF-8", "Escape"]
        )
        self.convert_table.verticalHeader().hide()
        self.convert_table.setAlternatingRowColors(True)
        self.convert_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.convert_table.itemSelectionChanged.connect(self._convert_selected)
        layout.addWidget(self.convert_table, 1)
        return pane

    def _browse_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        row = QHBoxLayout()
        self.block_combo = QComboBox()
        self.block_combo.addItems(chars.BLOCKS)
        self.block_combo.setMinimumWidth(240)
        self.block_combo.currentTextChanged.connect(lambda _: self._draw_block())
        row.addWidget(QLabel("Block"))
        row.addWidget(self.block_combo, 1)

        self.browse_font = QComboBox()
        self.browse_font.currentTextChanged.connect(lambda _: self._draw_block())
        row.addWidget(QLabel("drawn in"))
        row.addWidget(self.browse_font, 1)
        layout.addLayout(row)

        self.browse_note = QLabel("")
        layout.addWidget(self.browse_note)

        self.grid = QTableWidget(0, 16)
        self.grid.horizontalHeader().hide()
        self.grid.verticalHeader().hide()
        self.grid.setShowGrid(True)
        self.grid.itemSelectionChanged.connect(self._grid_selected)
        layout.addWidget(self.grid, 1)
        return pane

    def _language_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        row = QHBoxLayout()
        self.lang_filter = QLineEdit()
        self.lang_filter.setPlaceholderText("Filter 9,600 languages by name or tag…")
        self.lang_filter.textChanged.connect(self._filter_languages)
        row.addWidget(self.lang_filter, 1)
        self.aux_button = QPushButton("Include auxiliary")
        self.aux_button.setObjectName("Ghost")
        self.aux_button.setCheckable(True)
        self.aux_button.setToolTip(
            "Auxiliary characters appear in loanwords and older spellings"
        )
        self.aux_button.clicked.connect(lambda: self._language_selected())
        row.addWidget(self.aux_button)
        layout.addLayout(row)

        self.lang_note = QLabel("")
        layout.addWidget(self.lang_note)

        self.lang_list = QTreeWidget()
        self.lang_list.setColumnCount(4)
        self.lang_list.setHeaderLabels(["Language", "Tag", "Script", "SLDR"])
        self.lang_list.setRootIsDecorated(False)
        self.lang_list.setAlternatingRowColors(True)
        self.lang_list.itemSelectionChanged.connect(self._language_selected)
        self.lang_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.lang_list, 1)
        return pane

    # ---------------------------------------------------------- theme

    def _apply_theme(self):
        palette = DARK if self.dark else LIGHT
        self.setStyleSheet(QSS.format(chrome=CHROME_FONT, data=DATA_FONT, **palette))
        self.inspector.restyle(palette)
        self.echo.setStyleSheet(f"color: {palette['faint']};")
        self._echo_parse(self.omni.text())

    def _toggle_theme(self):
        self.dark = not self.dark
        self._apply_theme()

    # ---------------------------------------------------------- startup

    def _start_index(self):
        self.progress.show()
        self.started = time.perf_counter()
        task = Task(self.index.build, wants_progress=True)
        task.signals.progress.connect(self._index_progress)
        task.signals.done.connect(self._index_ready)
        task.signals.failed.connect(self._failed)
        self._start(task)

    def _index_progress(self, fraction, message):
        self.progress.setValue(int(fraction * 100))
        self.statusBar().showMessage(f"Reading fonts…  {message}")

    def _index_ready(self, _result):
        self.progress.hide()
        elapsed = time.perf_counter() - self.started
        families = sorted(self.index.families)
        self.inspector.index = self.index
        self.browse_font.blockSignals(True)
        self.browse_font.addItems(families)
        default = next(
            (f for f in ("Segoe UI Symbol", "Quivira", "DejaVu Sans", "Arial Unicode MS")
             if f in self.index.families),
            families[0] if families else "",
        )
        self.browse_font.setCurrentText(default)
        self.browse_font.blockSignals(False)

        note = f"{len(self.index.faces)} faces · {len(families)} families · {elapsed:.1f} s"
        if self.index.errors:
            note += f" · {len(self.index.errors)} unreadable"
        self.statusBar().showMessage(note)

        if not self.omni.text():
            self.omni.setText("U+2731")
        self._run_query()
        # The name index powers variants and name search; build it quietly.
        task = Task(chars.name_index)
        task.signals.failed.connect(self._failed)
        self._start(task)

    def _start(self, task):
        """Hand a Task to the pool, holding a reference so it outlives the call."""
        self._running.append(task)
        task.signals.done.connect(lambda _=None, t=task: self._finished(t))
        task.signals.failed.connect(lambda _=None, t=task: self._finished(t))
        self.pool.start(task)

    def _finished(self, task):
        if task in self._running:
            self._running.remove(task)

    def _failed(self, message):
        self.progress.hide()
        self.statusBar().showMessage(message, 15000)

    # ---------------------------------------------------------- query

    def _lang_names(self):
        return [(l.tag, l.name) for l in self.languages]

    def _parse(self, text):
        return chars.parse(
            text,
            font_families=list(self.index.families) if self.index.faces else (),
            lang_names=self._lang_names(),
        )

    def _echo_parse(self, text):
        query = self._parse(text)
        palette = DARK if self.dark else LIGHT
        if query.kind == "empty":
            self.echo.setText(
                f"<span style='color:{palette['faint']}'>"
                "Type a character, a codepoint, a name, a property, or a font.</span>"
            )
            return
        bits = [
            "<span style='letter-spacing:1px'>READ AS</span> ",
            f"<span style='color:{palette['lapis']};font-family:{DATA_FONT}'>"
            f"<b>{esc(query.label)}</b></span>",
        ]
        if query.alternates:
            alts = " &middot; ".join(
                f"<a href='alt:{i}' style='color:{palette['ink2']};"
                f"text-decoration:none'>{esc(a.label)}</a>"
                for i, a in enumerate(query.alternates)
            )
            bits.append(f"<span style='color:{palette['hair']}'> — or </span>{alts}")
        self.echo.setText("".join(bits))

    def _echo_link(self, href):
        if not href.startswith("alt:"):
            return
        query = self._parse(self.omni.text())
        try:
            chosen = query.alternates[int(href[4:])]
        except (ValueError, IndexError):
            return
        self._dispatch(chosen)

    def _run_query(self):
        self._dispatch(self._parse(self.omni.text()))

    def _dispatch(self, query):
        if query.kind == "empty":
            return
        if query.kind == "char":
            self._set_mode(0, quiet=True)
            self._show_char(query.value)
        elif query.kind == "prop":
            self._set_mode(0, quiet=True)
            self._show_property(query.value)
        elif query.kind == "name":
            self._set_mode(0, quiet=True)
            self._show_name_search(query.value)
        elif query.kind == "font":
            self._set_mode(0, quiet=True)
            self._show_font(query.value)
        elif query.kind == "block":
            self._set_mode(2, quiet=True)
            self.block_combo.setCurrentText(query.value)
        elif query.kind == "range":
            self._set_mode(0, quiet=True)
            self._show_codepoints(list(range(query.value[0], query.value[1] + 1)))
        elif query.kind == "codepoints":
            self._set_mode(1, quiet=True)
            self.convert_input.setPlainText(self.omni.text())
        elif query.kind == "lang":
            self._set_mode(3, quiet=True)
            self.lang_filter.setText(query.value)
        elif query.kind == "text":
            self._set_mode(0, quiet=True)
            self._show_text_coverage(query.value)

    # ---------------------------------------------------------- search results

    def _fill_results(self, faces, headline, glyph_cp=None):
        self.results_kind = "faces_for_char" if glyph_cp else "faces"
        self.results.clear()
        self.results.setHeaderLabels(["", "Family", "Style", "Mapped", "File"])
        for face in faces:
            item = QTreeWidgetItem([
                chr(glyph_cp) if glyph_cp and not chars.standin(glyph_cp) else "",
                face.family,
                face.style or "Regular",
                f"{face.glyphs:,}",
                face.filename,
            ])
            if glyph_cp:
                preview = QFont(face.family)
                preview.setPointSize(19)
                if face.style:
                    preview.setStyleName(face.style)
                item.setFont(0, preview)
            item.setTextAlignment(0, Qt.AlignCenter)
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            item.setToolTip(4, face.path)
            item.setData(0, Qt.UserRole, face)
            self.results.addTopLevelItem(item)
        self.statusBar().showMessage(headline)
        if faces:
            self.results.setCurrentItem(self.results.topLevelItem(0))

    def _show_char(self, cp):
        self.current_cp = cp
        faces = self.index.with_codepoint(cp) if self.index.faces else []
        info = chars.describe(cp)
        self._fill_results(
            faces,
            f"U+{cp:04X} {info.name} — {len(faces)} of {len(self.index.faces)} faces",
            glyph_cp=cp,
        )
        self.inspector.show_char(cp, faces)

    def _show_font(self, family):
        face = self.index.find_face(family)
        if not face:
            self.statusBar().showMessage(f"No installed family called {family}")
            return
        styles = self.index.styles_of(family)
        self._fill_results(styles, f"{family} — {len(styles)} styles installed")
        self.inspector.show_face(face)

    def _show_codepoints(self, cps, title=None):
        """Rank faces by how much of a codepoint set they cover."""
        if not self.index.faces:
            return
        rows = fontindex.best_per_family(self.index.coverage(cps))
        self.results_kind = "faces"
        self.results.clear()
        self.results.setHeaderLabels(["", "Family", "Style", "Covers", "Missing"])
        for face, have, missing in rows[:200]:
            item = QTreeWidgetItem([
                "", face.family, face.style or "Regular",
                f"{have}/{len(cps)}",
                "—" if not missing else "".join(chr(c) for c in missing[:14]),
            ])
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            if missing:
                preview = QFont(face.family)
                preview.setPointSize(13)
                item.setFont(4, preview)
            item.setData(0, Qt.UserRole, face)
            self.results.addTopLevelItem(item)
        complete = sum(1 for _f, have, _m in rows if have == len(cps))
        self.statusBar().showMessage(
            title or f"{len(cps)} codepoints — {complete} families cover all of them"
        )
        if rows:
            self.results.setCurrentItem(self.results.topLevelItem(0))

    def _show_text_coverage(self, text):
        cps = sorted({ord(c) for c in text if not c.isspace()})
        self._show_codepoints(
            cps, f"“{text[:30]}” needs {len(cps)} distinct characters"
        )
        self.inspector.show_message(
            "Covering a passage",
            "Faces are ranked by how many of these characters they map. "
            "Pick one to inspect it.",
        )

    def _show_property(self, expr):
        self.statusBar().showMessage(f"Scanning Unicode for \\p{{{expr}}}…")
        self.progress.show()
        self.progress.setRange(0, 0)

        def work():
            return expr, chars.property_members(expr)

        task = Task(work)
        task.signals.done.connect(self._property_ready)
        task.signals.failed.connect(self._failed)
        self._start(task)

    def _property_ready(self, result):
        expr, members = result
        self.progress.setRange(0, 100)
        self.progress.hide()
        if members is None:
            self.statusBar().showMessage(f"\\p{{{expr}}} is not a property regex knows")
            self.inspector.show_message(
                "Unknown property",
                f"The regex engine rejected \\p{{{expr}}}. "
                "Try Script=…, Block=…, a category like Lu, or a name like Alphabetic.",
            )
            return
        self._show_codepoints(
            members, f"\\p{{{expr}}} — {len(members)} codepoints"
        )
        self.inspector.show_message(
            f"\\p{{{expr}}}",
            f"{len(members)} codepoints match. Faces are ranked by how many they cover.",
        )

    def _show_name_search(self, needle):
        hits = chars.search_names(needle)
        if not hits:
            self.statusBar().showMessage(f"No character name contains “{needle}”")
            self.inspector.show_message("No match", f"Nothing named “{needle}”.")
            return
        if len(hits) == 1:
            self._show_char(hits[0])
            return
        self.results_kind = "codepoints"
        self.results.clear()
        self.results.setHeaderLabels(["", "Codepoint", "Name", "Faces", ""])
        for cp in hits[:400]:
            n = self.index.count_faces_with(cp)
            item = QTreeWidgetItem(
                ["" if chars.standin(cp) else chr(cp), f"U+{cp:04X}",
                 chars.char_name(chr(cp)), str(n), ""]
            )
            preview = QFont()
            preview.setPointSize(19)
            item.setFont(0, preview)
            item.setTextAlignment(0, Qt.AlignCenter)
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            item.setData(0, Qt.UserRole, cp)
            self.results.addTopLevelItem(item)
        self.statusBar().showMessage(f"{len(hits)} characters named like “{needle}”")
        self.results.setCurrentItem(self.results.topLevelItem(0))

    def _result_selected(self):
        items = self.results.selectedItems()
        if not items:
            return
        payload = items[0].data(0, Qt.UserRole)
        if payload is None:
            return
        if self.results_kind == "codepoints":
            self.current_cp = payload
            self.inspector.show_char(payload, self.index.with_codepoint(payload))
        elif self.results_kind == "faces_for_char" and self.current_cp is not None:
            # Keep the character in view, but preview it in the face just picked.
            faces = self.index.with_codepoint(self.current_cp)
            faces.sort(key=lambda f: f is not payload)
            self.inspector.show_char(self.current_cp, faces)
        else:
            self.inspector.show_face(payload)

    # ---------------------------------------------------------- convert

    def _convert(self):
        text = self.convert_input.toPlainText()
        if not text.strip():
            self.convert_table.setRowCount(0)
            self.convert_note.setText("")
            return

        decoded, how = chars.text_from_codepoints(text)
        if decoded is not None:
            palette = DARK if self.dark else LIGHT
            self.convert_note.setText(
                f"<span style='color:{palette['faint']}'>read as {how} → </span>"
                f"<span style='font-size:19px'>{esc(decoded)}</span>"
            )
            text = decoded
        else:
            self.convert_note.setText("")

        self.convert_table.setRowCount(len(text))
        for row, ch in enumerate(text):
            info = chars.describe(ord(ch))
            label = chars.standin(info.cp)
            cells = [
                label or ch, f"U+{info.cp:04X}", info.name, str(info.decimal),
                info.category, info.script or "", info.utf8, info.escape,
            ]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if column == 0 and not label:
                    big = QFont()
                    big.setPointSize(17)
                    item.setFont(big)
                    item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, info.cp)
                self.convert_table.setItem(row, column, item)
        self.convert_table.resizeColumnsToContents()
        self.convert_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )

        forms = chars.normalization_variants(text)
        differing = [f"{name} differs" for name, value in forms if value != text]
        self.statusBar().showMessage(
            f"{len(text)} characters · "
            f"{len(text.encode('utf-8'))} bytes utf-8"
            + (f" · {', '.join(differing)}" if differing else " · all normal forms equal")
        )

    def _convert_selected(self):
        items = self.convert_table.selectedItems()
        if not items:
            return
        cp = items[0].data(Qt.UserRole)
        if cp is not None:
            self.current_cp = cp
            self.inspector.show_char(cp, self.index.with_codepoint(cp))

    # ---------------------------------------------------------- browse

    def _draw_block(self):
        name = self.block_combo.currentText()
        bounds = chars.block_range(name)
        if not bounds:
            return
        lo, hi = bounds
        family = self.browse_font.currentText()
        face = self.index.find_face(family) if family else None
        codepoints = list(range(lo, hi + 1))

        columns = 16
        rows = (len(codepoints) + columns - 1) // columns
        self.grid.setRowCount(rows)
        self.grid.setColumnCount(columns)
        cell = QFont(family) if family else QFont()
        cell.setPointSize(17)

        assigned = covered = 0
        for i, cp in enumerate(codepoints):
            item = QTableWidgetItem(chr(cp) if not chars.standin(cp) else "")
            item.setFont(cell)
            item.setTextAlignment(Qt.AlignCenter)
            item.setData(Qt.UserRole, cp)
            item.setToolTip(f"U+{cp:04X}  {chars.char_name(chr(cp))}")
            is_assigned = unicodedata.category(chr(cp)) != "Cn"
            has = face and cp in face.codepoints
            assigned += is_assigned
            covered += bool(has)
            if not is_assigned or not has:
                item.setForeground(Qt.gray)
            self.grid.setItem(i // columns, i % columns, item)
        self.grid.resizeColumnsToContents()
        self.grid.resizeRowsToContents()

        palette = DARK if self.dark else LIGHT
        self.browse_note.setText(
            f"<span style='color:{palette['faint']}'>U+{lo:04X}…U+{hi:04X} · "
            f"{assigned} assigned · </span>"
            f"<span style='color:{palette['lapis']}'>{covered} drawn by "
            f"{esc(family)}</span>"
        )
        if face:
            self.inspector.show_face(face)

    def _grid_selected(self):
        items = self.grid.selectedItems()
        if not items:
            return
        cp = items[0].data(Qt.UserRole)
        if cp is not None:
            self.current_cp = cp
            self.inspector.show_char(cp, self.index.with_codepoint(cp))

    # ---------------------------------------------------------- language

    def _ensure_languages(self):
        if self.languages:
            return True
        self.statusBar().showMessage("Fetching the SIL language list…")
        self.progress.show()
        self.progress.setRange(0, 0)
        task = Task(langs.languages)
        task.signals.done.connect(self._languages_ready)
        task.signals.failed.connect(self._languages_failed)
        self._start(task)
        return False

    def _languages_ready(self, languages):
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.languages = languages
        with_data = sum(1 for l in languages if l.has_sldr)
        self.lang_filter.setPlaceholderText(
            f"Filter {len(languages):,} languages by name or tag…"
        )
        self.statusBar().showMessage(
            f"{len(languages):,} language tags · {with_data:,} with SLDR character data"
        )
        self._filter_languages(self.lang_filter.text())

    def _languages_failed(self, message):
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.statusBar().showMessage(f"Language list unavailable — {message}")
        self.inspector.show_message(
            "Can't reach the language data",
            f"{message}\n\nlangtags.json is fetched once from ldml.api.sil.org "
            "and then cached. Everything else works offline.",
        )

    def _filter_languages(self, needle=""):
        if not self.languages:
            return
        needle = needle.strip().lower()
        self.lang_list.clear()

        def rank(lang):
            """Exact tag beats exact name beats a prefix beats a substring."""
            tag, name = lang.tag.lower(), lang.name.lower()
            if tag == needle:
                return 0
            if name == needle:
                return 1
            if tag.startswith(needle):
                return 2
            if name.startswith(needle):
                return 3
            return 4

        matches = [
            l for l in self.languages
            if not needle or needle in l.name.lower() or needle in l.tag.lower()
        ]
        if needle:
            matches.sort(key=lambda l: (rank(l), l.name.lower()))

        for lang in matches[:500]:
            item = QTreeWidgetItem(
                [lang.name, lang.tag, lang.script, "yes" if lang.has_sldr else "—"]
            )
            item.setData(0, Qt.UserRole, lang)
            self.lang_list.addTopLevelItem(item)

        total = len(matches)
        self.lang_note.setText(
            f"{total:,} match" + ("" if total == 1 else "es")
            + (" · showing the closest 500" if total > 500 else "")
        )

    def _language_selected(self):
        items = self.lang_list.selectedItems()
        if not items:
            return
        lang = items[0].data(0, Qt.UserRole)
        aux = self.aux_button.isChecked()
        self.statusBar().showMessage(f"Fetching exemplar characters for {lang.name}…")
        self.progress.show()
        self.progress.setRange(0, 0)

        def work():
            return lang, langs.required(lang.tag, include_auxiliary=aux)

        task = Task(work)
        task.signals.done.connect(self._language_ready)
        task.signals.failed.connect(self._failed)
        self._start(task)

    def _language_ready(self, result):
        lang, needed = result
        self.progress.setRange(0, 100)
        self.progress.hide()
        if not needed:
            self.statusBar().showMessage(f"SLDR has no exemplar characters for {lang.tag}")
            self.inspector.show_message(
                f"No character data for {lang.name}",
                "SLDR lists this tag but has no exemplarCharacters for it.",
            )
            return
        rows = langs.rank_faces(self.index.faces, needed)
        families = fontindex.best_per_family(rows)
        able = sum(1 for _f, missing in families if not missing)
        self.statusBar().showMessage(
            f"{lang.name} ({lang.tag}) needs {len(needed)} characters — "
            f"{able} of {len(families)} families cover all of them"
        )
        self.inspector.show_language(lang, needed, rows)
        self.current_cp = None

    # ---------------------------------------------------------- navigation

    def _set_mode(self, n, quiet=False):
        self.stack.setCurrentIndex(n)
        for i, button in enumerate(self.mode_buttons):
            button.setChecked(i == n)
        if n == 3 and not quiet:
            self._ensure_languages()
        if n == 2 and self.grid.rowCount() == 0 and self.index.faces:
            self._draw_block()
        if n == 1 and not self.convert_input.toPlainText():
            self.convert_input.setPlainText(self.omni.text())

    def _navigate(self, kind, value):
        if kind == "char":
            self.omni.setText(f"U+{value:04X}")
            self._set_mode(0, quiet=True)
            self._show_char(value)
        elif kind == "font":
            self.omni.setText(value)
            self._show_font(value)
        elif kind == "prop":
            self.omni.setText(f"\\p{{{value}}}")
            self._show_property(value)
        elif kind == "block":
            self.omni.setText(value)
            self._set_mode(2, quiet=True)
            self.block_combo.setCurrentText(value)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
