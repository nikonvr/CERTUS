"""The shared widgets of the suite keep their text whole in a narrow panel (U3).

At 1366x768 the left panel of INDEX SPLINE is 360 px wide, and three shared widgets cut their text there, measured on
2026-11-12 with `scripts/audit_ux_certus.py::clipped_texts`:

* `CertusCard`: a title longer than the card ("3 — What to fit on the spectrum (T, T/Tsub, R)", 341 px for 294) ran
  past its edge. It now wraps.
* `EnhancedProgressWidget`: a row made for a wide slot (two bars 220 px wide, then two labels and a button, 509 px in
  all) was squeezed into 308 px: "Overall progress" had 75 px for 99, the status line 99 for 178. A panel can now ask
  for the stacked form, the bars above the texts; the row stays the default, unchanged.

Each case puts the widget in a panel narrower than what it asks for, the way a splitter does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

#: Longer than the one that was cut in the window: the test does not depend on the font of the machine.
LONG_TITLE = "3 — What to fit on the spectrum: transmittance, relative transmittance, reflectance"


def _in_a_narrow_panel(qapp, widget, width: int):
    """`widget` in a panel `width` px wide that may be narrower than its content, as under a splitter."""
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    panel = QWidget()
    panel.setMinimumWidth(100)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    layout.addStretch(1)
    panel.resize(width, 400)
    panel.show()
    for _ in range(5):
        qapp.processEvents()
    assert panel.width() == width
    return panel


def _clipped(qapp, widget, width: int) -> list[str]:
    from scripts.audit_ux_certus import clipped_texts

    panel = _in_a_narrow_panel(qapp, widget, width)
    try:
        return clipped_texts(panel)["clipped"]
    finally:
        panel.close()
        panel.deleteLater()


def test_a_card_title_longer_than_its_card_wraps(qapp) -> None:
    from certus.ui.certus_ui import CertusCard

    assert _clipped(qapp, CertusCard(LONG_TITLE), 318) == []


def test_a_short_card_title_stays_on_one_line(qapp) -> None:
    from PyQt6.QtWidgets import QLabel

    from certus.ui.certus_ui import CertusCard

    card = CertusCard("1 — Spectrum")
    title = card.findChild(QLabel, "CertusCardTitle")
    panel = _in_a_narrow_panel(qapp, card, 318)
    try:
        assert title.height() < 2 * title.fontMetrics().lineSpacing()
    finally:
        panel.close()
        panel.deleteLater()


def test_the_stacked_progress_widget_keeps_its_texts_whole_in_a_narrow_panel(qapp) -> None:
    from certus.ui.certus_ui import EnhancedProgressWidget

    assert _clipped(qapp, EnhancedProgressWidget(main_label="Optimization", stacked=True), 308) == []


def test_the_progress_widget_is_a_row_unless_asked_otherwise(qapp) -> None:
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout

    from certus.ui.certus_ui import EnhancedProgressWidget

    row, stacked = EnhancedProgressWidget(main_label="Optimization"), EnhancedProgressWidget(stacked=True)
    try:
        assert type(row.layout()) is QHBoxLayout
        assert type(stacked.layout()) is QVBoxLayout
        assert not row.detail_label.wordWrap()
    finally:
        row.deleteLater()
        stacked.deleteLater()
