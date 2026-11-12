"""The UX audit sees a text that does not fit the room it is given, and tells a cut text from a cramped one (U3).

The audit of 2026-11-11 found sixteen labels and a handful of table headers cut at 1440x900 ("Nominal thickness (nm):"
asked for 138 px and had 84), with a script that was not kept. `scripts/audit_ux_certus.py::clipped_texts` is that
measure, kept: `clipped` when the text itself is wider than what it is drawn in, `tight` when it is whole but eats the
padding its widget asks for. A text the user does not see is not counted, and a label that wraps is not cut by its width.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LONG = "Nominal thickness of the layer (nm):"


def _host(qapp, build):
    """A shown widget that `build` fills; the caller closes it."""
    from PyQt6.QtWidgets import QWidget

    host = QWidget()
    build(host)
    host.resize(600, 200)
    host.show()
    qapp.processEvents()
    return host


def kinds(found: list[str]) -> list[str]:
    return sorted(item.split("|")[0] + "|" + item.split("|")[1] for item in found)


def test_a_label_and_a_button_narrower_than_their_text_are_clipped(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QPushButton

    from scripts.audit_ux_certus import clipped_texts

    def build(host) -> None:
        label = QLabel(LONG, host)
        label.setGeometry(0, 0, 60, 20)
        button = QPushButton("Export the corridor envelope", host)
        button.setGeometry(0, 40, 50, 24)
        fits = QLabel("d (nm)", host)
        fits.setGeometry(0, 80, 300, 20)

    host = _host(qapp, build)
    try:
        found = clipped_texts(host)
    finally:
        host.close()
        host.deleteLater()

    assert kinds(found["clipped"]) == ["button|Export the corridor envelope", f"label|{LONG}"]
    assert found["tight"] == []


def test_a_text_that_is_whole_but_eats_its_padding_is_tight_not_clipped(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from scripts.audit_ux_certus import clipped_texts

    def build(host) -> None:
        button = QPushButton("Run", host)
        text = button.fontMetrics().horizontalAdvance("Run")
        assert button.sizeHint().width() > text + 4, "a push button asks for more than its text"
        button.setGeometry(0, 0, text + 3, 24)

    host = _host(qapp, build)
    try:
        found = clipped_texts(host)
    finally:
        host.close()
        host.deleteLater()

    assert found["clipped"] == []
    assert kinds(found["tight"]) == ["button|Run"]


def test_a_header_narrower_than_its_text_is_clipped_and_a_wide_one_is_not(qapp) -> None:
    from PyQt6.QtWidgets import QTableWidget

    from scripts.audit_ux_certus import clipped_texts

    def build(host) -> None:
        table = QTableWidget(1, 2, host)
        table.setHorizontalHeaderLabels(["Wavelength max (nm)", "n"])
        table.setGeometry(0, 0, 400, 100)
        table.setColumnWidth(0, 30)
        table.setColumnWidth(1, 120)

    host = _host(qapp, build)
    try:
        found = clipped_texts(host)
    finally:
        host.close()
        host.deleteLater()

    assert kinds(found["clipped"]) == ["header|Wavelength max (nm)"]


def test_a_header_of_two_lines_is_measured_line_by_line(qapp) -> None:
    from PyQt6.QtWidgets import QStyle, QTableWidget

    from scripts.audit_ux_certus import clipped_texts

    def build(host) -> None:
        table = QTableWidget(1, 1, host)
        table.setHorizontalHeaderLabels(["Wavelength max\n(nm)"])
        table.setGeometry(0, 0, 400, 100)
        header = table.horizontalHeader()
        margin = header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin, None, header)
        longest_line = header.fontMetrics().horizontalAdvance("Wavelength max")
        table.setColumnWidth(0, longest_line + 2 * margin + 2)  # room for the longest line, not for the two end to end

    host = _host(qapp, build)
    try:
        found = clipped_texts(host)
    finally:
        host.close()
        host.deleteLater()

    assert found["clipped"] == []


def test_what_wraps_and_what_is_hidden_is_not_counted(qapp) -> None:
    from PyQt6.QtWidgets import QLabel

    from scripts.audit_ux_certus import clipped_texts

    def build(host) -> None:
        wrapping = QLabel(LONG, host)
        wrapping.setWordWrap(True)
        wrapping.setGeometry(0, 0, 60, 80)
        hidden = QLabel(LONG, host)
        hidden.setGeometry(0, 100, 60, 20)
        hidden.hide()

    host = _host(qapp, build)
    try:
        found = clipped_texts(host)
    finally:
        host.close()
        host.deleteLater()

    assert found == {"clipped": [], "tight": []}
