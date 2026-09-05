"""Destructive table actions must ask first (step 2.21).

confirm_destructive exists, is tested, and had NO production caller - the
"fast_auto_blocks" pattern of CLAUDE.md section 24-50 transposed to ergonomics:
the facility exists, someone tested it, nobody uses it. An AST sweep of the
methods that really mutate something found 24 destructive methods and 0
confirmations.

Two of them destroy an optical stack outright, and neither module can undo:

  * RE - pasting from Excel with NO row selected replaces the whole stack
    (certus_re_table_mixin.py), and RE's undo stack was never filled (step 2.13);
  * FIELD - safe_clear() calls setRowCount(0) on table_layers
    (certus_field_common.py), and FIELD owns no undo machinery at all.

Both tests decline the confirmation and check the rows are still there. A test
that only checked "the dialog appeared" would pass on a dialog whose answer is
ignored.
"""

from __future__ import annotations

import pytest


def test_re_paste_over_a_full_stack_can_be_refused(qapp, monkeypatch) -> None:
    """Declining must leave the layers untouched."""
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    try:
        while win.front_table.rowCount() > 0:
            win.front_table.removeRow(win.front_table.rowCount() - 1)
        win._add_front_row("H", 1.0, True)
        win._add_front_row("L", 1.0, True)
        before = win.front_table.rowCount()
        assert before == 2

        asked = []
        monkeypatch.setattr(
            type(win), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False
        )
        win.front_table.setCurrentCell(-1, -1)

        monkeypatch.setattr(
            "certus.ui.certus_re_table_mixin.QApplication.clipboard",
            staticmethod(lambda: _FakeClipboard("H\t1.0\nL\t1.0\nH\t1.0")),
        )
        win._paste_from_excel()

        assert asked, "RE replaced the whole stack without asking"
        assert win.front_table.rowCount() == before, (
            f"the stack was replaced anyway: {win.front_table.rowCount()} rows instead of {before}"
        )
    finally:
        win.close()


class _FakeClipboard:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


def test_field_clear_can_be_refused(qapp, monkeypatch) -> None:
    """FIELD has no undo: emptying its stack must be a decision."""
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    try:
        panel = None
        for child in win.findChildren(object):
            if type(child).__name__ == "StackPanelWidget":
                panel = child
                break
        if panel is None:
            pytest.skip("no StackPanelWidget in this build")

        panel.table_layers.setRowCount(3)
        before = panel.table_layers.rowCount()

        asked = []
        monkeypatch.setattr(
            type(win), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False
        )

        # safe_clear is a closure; reach it through the button that triggers it.
        from PyQt6.QtWidgets import QPushButton

        cleared = [b for b in panel.findChildren(QPushButton) if "clear" in b.text().lower()]
        if not cleared:
            pytest.skip("no Clear button on the stack panel")
        cleared[0].click()

        assert asked, "FIELD emptied its stack without asking"
        assert panel.table_layers.rowCount() == before, (
            f"the stack was cleared anyway: {panel.table_layers.rowCount()} rows instead of {before}"
        )
    finally:
        win.close()
