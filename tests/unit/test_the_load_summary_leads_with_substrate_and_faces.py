"""The load summary opens with the substrate and the faces, marks what is suspicious, and escapes what it shows.

`certus/utils/certus_load_summary.py` is the dialog every module opens after loading a file. 9.8 % of it was
covered on 2026-09-30, and no test named it. What a reader relies on: the substrate and the number of faces come
first whatever the order of the lines they were given, a missing one says so instead of staying blank, a suspicious
line is flagged, and text taken from a file is displayed as text, never as markup.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog


@pytest.fixture(autouse=True)
def summary_windows(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "load summary")


def test_the_summary_leads_with_the_substrate_and_the_faces_whatever_the_order() -> None:
    text = build_summary_plain_text(
        "File loaded",
        ["n(lambda) read", "Substrate: BK7", "faces: TWO FACES", ("k is negative below 400 nm", True), "last line"],
    )

    assert text.splitlines() == [
        "File loaded",
        "",
        "SUBSTRATE: BK7",
        "FACES: TWO FACES",
        "",
        "n(lambda) read",
        "!! k is negative below 400 nm",
        "last line",
    ]


def test_a_missing_substrate_and_a_missing_number_of_faces_say_so() -> None:
    text = build_summary_plain_text("File loaded", ["only a line"])

    assert "SUBSTRATE: UNKNOWN" in text
    assert "FACES: ONE FACE (NO BACKSIDE)" in text


def test_the_last_substrate_line_wins_and_only_a_flagged_line_is_marked() -> None:
    text = build_summary_plain_text(
        "T", ["Substrate: first", "Substrate: second", ("fine", False), ("odd", True), "plain"]
    )

    assert "SUBSTRATE: second" in text and "first" not in text
    assert text.splitlines()[-3:] == ["fine", "!! odd", "plain"]


def _bold_fragments(box) -> list[str]:
    """The text of every run of the document that is set in bold."""
    runs = []
    block = box.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().fontWeight() > 400:
                runs.append(fragment.text())
            iterator += 1
        block = block.next()
    return runs


def test_the_dialog_shows_text_as_text_bolds_the_suspicious_lines_and_copies_the_summary(qapp) -> None:
    from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QTextEdit, QWidget

    plain = build_summary_plain_text("Title", [("<b>x</b> & y", True), "<i>note</i> & co"])

    window = QWidget()  # every caller passes its window: without a parent the dialog would go with the call
    show_load_summary_dialog(window, "Title", plain)
    dialog = window.findChild(QDialog)
    assert dialog.windowTitle() == "Title" and dialog.isVisible()
    box = dialog.findChild(QTextEdit)

    shown = box.toPlainText()
    assert "<b>x</b> & y" in shown and "<i>note</i> & co" in shown  # what came from a file is displayed, not read
    bold = _bold_fragments(box)
    assert any("<b>x</b> & y" in text for text in bold)  # the flagged line is in bold...
    assert not any("note" in text for text in bold)  # ...and the ordinary one is not
    buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
    assert set(buttons) == {"Copy summary", "Close"}
    buttons["Copy summary"].click()
    assert QApplication.clipboard().text() == plain
    buttons["Close"].click()
    assert not dialog.isVisible()
