"""DESIGN's "Clear / Reset" must actually clear (mission order, step 2.17).

The button used to be built on the LayoutManager delegate rather than on the
window:

    create_reset_button(self, use_app_reset=True)     # self is a LayoutManager

CertusResetManager._confirm_reset then called QMessageBox.question(self.app, ...)
with a non-QWidget parent, which raises TypeError inside a Qt slot - where Qt
swallows it.

Both halves of that fix are already in the tree and are locked here, because
these files were reverted to HEAD once on 2026-09-04 and the loss stayed
invisible until a window was opened:

  * the button is wired to the window (certus_design_ui_layout.py:602), so the
    reset runs;
  * create_reset_button refuses a non-QWidget outright, so the same mistake
    cannot come back as silence.

WARNING about how to measure this. Step 2.17 of the mission order declares the
button dead on the strength of "4 rows before the click, 4 rows after". That
measurement cannot support the conclusion: reset RESTORES the factory stack, and
DESIGN's factory stack is 4 rows, so a working reset and a dead one produce the
same number. Measured 2026-09-04: set the table to 9 rows, click, and it comes
back to 4 - the button works. Perturb before measuring, always.
"""

from __future__ import annotations

import pytest


def test_create_reset_button_refuses_a_non_widget(qapp) -> None:
    """A delegate passed where Qt needs a parent must fail loudly, not silently."""
    from certus.utils.certus_reset_framework import create_reset_button

    class _Delegate:  # what LayoutManager is: a plain Python object
        pass

    with pytest.raises(TypeError):
        create_reset_button(_Delegate(), use_app_reset=True)


def test_design_clear_button_actually_clears(qapp, monkeypatch) -> None:
    """Clicking Clear / Reset must empty the stack table."""
    from PyQt6.QtWidgets import QMessageBox

    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.utils import certus_reset_framework as rf

    monkeypatch.setattr(
        rf.QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    win = CertusDesignApp()
    try:
        table = win.front_table
        factory = table.rowCount()
        assert factory > 0, "DESIGN opens with an empty stack: this test would prove nothing"

        # Perturb FIRST. Reset restores the factory stack, so a table left at its
        # default value cannot tell a working reset from a dead one - which is the
        # trap the mission order's own reproduction fell into (step 2.17 reported
        # "4 rows before, 4 after" and concluded the button did nothing).
        table.setRowCount(factory + 5)
        assert table.rowCount() != factory

        win.clear_btn.click()

        assert table.rowCount() == factory, (
            f"Clear / Reset did not restore the factory stack: expected {factory} rows, "
            f"got {table.rowCount()}"
        )
    finally:
        win.close()
