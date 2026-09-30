"""The UX audit measures what a user sees, not what an inherited attribute suggests (audit v2, plan S6.2).

`scripts/audit_ux_certus.py` reported, on all eleven windows, gaps that were MEASUREMENT errors. Measured on 2026-10-01:

* "inputs without a tooltip" (14, on INDEX, SPLINE and SUBSTRATE): the QLineEdit INSIDE a QDoubleSpinBox. The spin box has
  its tooltip, and Qt shows it over its own field (a help event sent to the inner line edit shows the spin box's text).
* "undo_stack present but no Ctrl+Z" (five windows): `undo_stack` is inherited from CertusBaseApp by every window, and
  only a window that can REPLAY (`front_table`) or has its own writer (STRAT) can undo.
* "missing keys" F5 (run) and Esc (stop) on a launcher and on two file utilities: windows that run nothing long do not owe
  them; a key that does nothing is worse than no key.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_the_line_edit_inside_a_spin_box_is_part_of_it_not_an_input(qapp) -> None:
    from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit

    from scripts.audit_ux_certus import is_inner_line_edit

    spin = QDoubleSpinBox()
    combo = QComboBox()
    combo.setEditable(True)

    assert is_inner_line_edit(spin.lineEdit())
    assert is_inner_line_edit(combo.lineEdit())
    assert not is_inner_line_edit(QLineEdit()), "a free QLineEdit IS an input"


def test_qt_shows_the_spin_box_tooltip_over_its_inner_field(qapp) -> None:
    """The claim behind the audit change, measured: a help event on the inner line edit shows the spin box's text."""
    from PyQt6.QtCore import QEvent, QPoint
    from PyQt6.QtGui import QHelpEvent
    from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QToolTip, QVBoxLayout, QWidget

    host = QWidget()
    layout = QVBoxLayout(host)
    spin = QDoubleSpinBox()
    spin.setToolTip("the spin box tip")
    layout.addWidget(spin)
    host.resize(300, 100)
    host.show()
    qapp.processEvents()
    inner = spin.lineEdit()
    assert inner.toolTip() == "", "the inner line edit has no tooltip of its own: that is what the audit counted"

    QToolTip.hideText()
    position = QPoint(10, inner.height() // 2)
    QApplication.sendEvent(inner, QHelpEvent(QEvent.Type.ToolTip, position, inner.mapToGlobal(position)))
    qapp.processEvents()

    try:
        assert QToolTip.text() == "the spin box tip"
    finally:
        QToolTip.hideText()
        host.close()


def test_a_window_can_undo_when_it_can_replay_or_writes_its_own_state(qapp) -> None:
    from scripts.audit_ux_certus import owns_undo_machinery

    class Inherited:  # `undo_stack` alone, as CertusBaseApp gives it to every window
        def __init__(self) -> None:
            self.undo_stack: list = []

    class CanReplay(Inherited):
        def __init__(self) -> None:
            super().__init__()
            self.front_table = object()

    class WritesItsOwn(Inherited):
        def _save_undo_state(self) -> None: ...

    class NoStack:
        def __init__(self) -> None:
            self.front_table = object()

    assert not owns_undo_machinery(Inherited())
    assert owns_undo_machinery(CanReplay())
    assert owns_undo_machinery(WritesItsOwn())
    assert not owns_undo_machinery(NoStack())


def test_a_launcher_and_two_file_utilities_do_not_owe_run_and_stop_keys() -> None:
    from scripts.audit_ux_certus import VITAL_KEYS, vital_keys_for

    for tag in ("CERTUS_HUB", "CERTUS_SMOOTHER", "CERTUS_SUBSTRATE_INDEX"):
        assert "F5" not in vital_keys_for(tag) and "Esc" not in vital_keys_for(tag)
    assert vital_keys_for("CERTUS_DESIGN") == VITAL_KEYS, "the windows that compute owe the whole set"
