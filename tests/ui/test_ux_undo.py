"""Undo must work where the machinery exists, and stay away where it does not.

RE owns the whole undo machinery - front_table, _get_front_stack, _add_front_row
and even the _trigger_post_undo_action hook - and one guard neutralised all of
it: _save_undo_state returned early unless the window also had an `undo_btn`,
which RE does not. Nothing was ever pushed, so there was nothing to pop.

The symmetrical trap, which the mission order itself first got wrong: FIELD
inherits undo_stack from CertusBaseApp without owning a front_table, so wiring
Ctrl+Z there would raise AttributeError on the first press. An earlier version of
step 2.13 recommended exactly that.

Hence a guard on the CAPABILITY rather than on the presence of a button, and a
test in both directions.
"""

from __future__ import annotations

import pytest


def test_re_records_and_restores_its_stack(qapp) -> None:
    """RE has every collaborator undo needs; it must actually undo."""
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    try:
        win.undo_stack.clear()
        while win.front_table.rowCount() > 0:
            win.front_table.removeRow(win.front_table.rowCount() - 1)
        win._add_front_row("H", 1.0, True)
        win._add_front_row("L", 1.0, True)
        before = win.front_table.rowCount()
        assert before == 2

        win._save_undo_state(force=True)
        assert win.undo_stack, "RE pushed nothing: the undo stack stayed empty"

        win._add_front_row("H", 1.0, True)
        assert win.front_table.rowCount() == before + 1

        win._undo()

        assert win.front_table.rowCount() == before, (
            f"undo did not restore the stack: {win.front_table.rowCount()} rows instead of {before}"
        )
    finally:
        win.close()


def test_re_binds_ctrl_z(qapp) -> None:
    """A working undo the keyboard cannot reach is not an undo."""
    from CERTUS_RE import CertusREApp
    from certus.ui.certus_ui_utils import shortcut_owner

    win = CertusREApp()
    try:
        assert shortcut_owner(win, "Ctrl+Z") is not None, "RE has no Ctrl+Z"
    finally:
        win.close()


@pytest.mark.parametrize(
    "mod_path,cls_name",
    [
        ("certus.ui.certus_field_ui", "CertusFieldApp"),
        ("certus.ui.certus_index_ui", "CertusIndexApp"),
    ],
)
def test_saving_undo_is_inert_without_the_machinery(qapp, mod_path, cls_name) -> None:
    """A module that inherited undo_stack but owns no front_table must not push.

    Pushing there would build a stack whose replay raises on the first press.
    """
    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    try:
        # front_table is the real discriminator: undo_stack, _get_front_stack,
        # _add_front_row and _undo are inherited by ALL six modules and tell
        # nothing apart. Measured 2026-09-05.
        if hasattr(win, "front_table"):
            pytest.skip(f"{cls_name} owns a front_table after all")
        win.undo_stack.clear()

        win._save_undo_state(force=True)

        assert not win.undo_stack, (
            f"{cls_name} pushed an undo state it cannot replay: {len(win.undo_stack)} entries"
        )
    finally:
        win.close()
