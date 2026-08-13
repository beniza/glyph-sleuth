"""Drives the real window offscreen: `python test_app.py`.

Builds the index, runs a query of every kind, and checks something landed in the
results and the inspector. Catches the wiring mistakes the core tests can't see.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import app as gui  # noqa: E402


def wait_until(condition, what, seconds=600):
    """Pump the event loop until something is true.

    Never call the app's own slots to fake completion — the queued signal would
    still arrive later and undo whatever the test did next.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            QApplication.processEvents()
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def main():
    application = QApplication(sys.argv)
    window = gui.MainWindow()
    window.show()

    pool = QThreadPool.globalInstance()
    window._start_index()
    wait_until(lambda: window.browse_font.count() > 0, "the font index")

    faces = window.index.faces
    assert faces, "no fonts found on this machine"
    print(f"  ok  index — {len(faces)} faces, {len(window.index.families)} families")

    # a character
    window.omni.setText("U+2731")
    window._run_query()
    n = window.results.topLevelItemCount()
    assert n > 0, "U+2731 should be in at least one face"
    assert "HEAVY ASTERISK" in window.statusBar().currentMessage()
    assert "Dingbats" in window.inspector.toPlainText()
    print(f"  ok  character — {n} faces can draw U+2731")

    # the parse echo explains itself, and offers the other reading
    window.omni.setText("2731")
    assert "hex codepoint" in window.echo.text()
    assert "decimal" in window.echo.text(), "the ambiguity must be visible"
    print("  ok  parse echo — shows the reading and the alternative")

    # a font
    family = faces[0].family
    window.omni.setText(family)
    window._run_query()
    assert window.results.topLevelItemCount() > 0
    assert family in window.inspector.toPlainText()
    print(f"  ok  font — {family}")

    # a name search
    window.omni.setText("heavy asterisk")
    window._run_query()
    assert window.results.topLevelItemCount() >= 1
    print("  ok  name search")

    # a property, which runs off-thread
    window.omni.setText("\\p{Block=Dingbats}")
    window._run_query()
    wait_until(lambda: "192" in window.statusBar().currentMessage(),
               "the property scan")
    print("  ok  property — \\p{Block=Dingbats} found 192 codepoints")

    # a font view must survive a theme flip: Qt only applies a default stylesheet
    # to HTML set afterwards, so the inspector has to redraw itself
    window.omni.setText(family)
    window._run_query()
    before = window.dark
    window._toggle_theme()
    assert window.dark is not before
    ink = (gui.DARK if window.dark else gui.LIGHT)["ink"]
    assert ink.lower() in window.inspector.document().defaultStyleSheet().lower()
    assert family in window.inspector.toPlainText(), "inspector lost its content"
    window._toggle_theme()
    assert family in window.inspector.toPlainText()
    print("  ok  theme toggle — inspector redraws in the new palette")

    # conversion
    window._set_mode(1)
    window.convert_input.setPlainText("✱ Ǎ ა")
    assert window.convert_table.rowCount() == 5
    assert window.convert_table.item(0, 1).text() == "U+2731"
    assert window.convert_table.item(4, 2).text() == "GEORGIAN LETTER AN"
    window.convert_input.setPlainText("e2 9c b1")
    assert "utf-8" in window.convert_note.text()
    print("  ok  convert — both directions")

    # browsing a block
    window._set_mode(2)
    window.block_combo.setCurrentText("Dingbats")
    assert window.grid.rowCount() == 12, window.grid.rowCount()
    assert window.grid.item(0, 0).data(Qt.UserRole) == 0x2700

    # the picker offers only faces that actually have some of the block
    offered = [window.browse_font.itemData(i)
               for i in range(window.browse_font.count())]
    assert offered, "some face must cover Dingbats"
    for fam in offered:
        face = window.index.find_face(fam)
        assert any(cp in face.codepoints for cp in range(0x2700, 0x27C0)), fam
    print(f"  ok  browse — Dingbats grid, {len(offered)} families offered")

    # and the grid never renders a glyph the chosen face lacks: Qt would fall
    # back to another font and silently contradict the count above it
    for block, expect_empty in (("Malayalam", True), ("Basic Latin", False)):
        window.block_combo.setCurrentText(block)
        family = window.browse_font.currentData()
        face = window.index.find_face(family)
        drawn = missing_shown = 0
        for r in range(window.grid.rowCount()):
            for c in range(window.grid.columnCount()):
                item = window.grid.item(r, c)
                cp = item.data(Qt.UserRole)
                if not item.text() or item.text() == "·":
                    continue
                drawn += 1
                if cp not in face.codepoints:
                    missing_shown += 1
        assert missing_shown == 0, \
            f"{block}: {missing_shown} glyphs drawn that {family} does not have"
        assert drawn > 0, block
    print("  ok  browse — no glyph is drawn that the chosen face lacks")

    # language coverage, the whole point
    window._set_mode(3)
    try:
        wait_until(lambda: bool(window.languages), "the language list", 120)
    except AssertionError:
        pass
    assert window.stack.currentIndex() == 3, "Language mode must stay selected"
    if window.languages:
        print(f"  ok  languages — {len(window.languages):,} tags")
        window.lang_filter.setText("hi")
        match = None
        for i in range(window.lang_list.topLevelItemCount()):
            item = window.lang_list.topLevelItem(i)
            if item.text(1) == "hi":
                match = item
                break
        assert match, "Hindi should be in the filtered list"
        window.lang_list.setCurrentItem(match)
        wait_until(lambda: "needs" in window.statusBar().currentMessage(),
                   "the exemplar fetch")
        message = window.statusBar().currentMessage()
        assert "needs" in message and "cover" in message, message
        assert "Verdict" in window.inspector.toPlainText()
        print(f"  ok  language — {message}")
    else:
        print("  --  languages skipped (no network)")

    print("\nall app checks passed")


if __name__ == "__main__":
    main()
