"""No undo state is written into a stack that nothing reads (audit v2, plan S6.2; step 2.13: "do not promise a key that does
nothing").

Five windows carried `undo_stack` and the audit saw five stacks without Ctrl+Z. INDEX, FIELD and the two METAL windows never
wrote into theirs (no `front_table`, so nothing to replay). SPLINE wrote a SplineState before every run, into a stack with
no consumer: measured 2026-09-05 and left in place since. Wiring Ctrl+Z on them would raise, or do nothing; the writer that
had no reader is gone, and this file keeps a new one from arriving without its reader and its key.
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
import ast
import time


def test_no_module_writes_an_undo_state_that_nothing_reads() -> None:
    """SPLINE wrote a SplineState into `undo_stack` before every run, for a stack with no consumer. Not again.

    A file may push onto an undo stack only where something pops it AND a key reaches it: the base app (replay through
    `front_table`, bound by DESIGN and RE) and STRAT (its own stack, Ctrl+Z). A new writer comes with its consumer and its
    key, and with its file in this set.
    """
    allowed = {"certus/ui/certus_base_app.py", "certus/ui/certus_strat_ui_state.py"}
    writers = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "certus").rglob("*.py")
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "undo_stack"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig")))
        )
    }

    assert writers <= allowed, f"a stack is filled with no consumer and no key: {sorted(writers - allowed)}"


def test_every_window_that_can_undo_has_ctrl_z(qapp) -> None:
    from scripts.audit_ux_certus import MODULES, owns_undo_machinery
    from certus.ui.certus_ui_utils import shortcut_owner

    failures = []
    for tag in ("CERTUS_DESIGN", "CERTUS_STRAT", "CERTUS_RE", "CERTUS_INDEX_SPLINE", "CERTUS_INDEX", "CERTUS_FIELD"):
        module, cls = MODULES[tag]
        win = getattr(__import__(module, fromlist=[cls]), cls)()
        try:
            # STRAT binds its Ctrl+Z "after the interface is ready": let the event loop run before judging it.
            deadline = time.monotonic() + 5.0
            while shortcut_owner(win, "Ctrl+Z") is None and time.monotonic() < deadline:
                qapp.processEvents()
                time.sleep(0.05)
            if owns_undo_machinery(win) and shortcut_owner(win, "Ctrl+Z") is None:
                failures.append(f"{tag}: has the machinery to undo and no Ctrl+Z")
        finally:
            win.close()

    assert not failures, failures


@pytest.mark.parametrize("tag", ["CERTUS_INDEX", "CERTUS_INDEX_SPLINE", "CERTUS_FIELD", "CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER"])
def test_the_five_windows_that_only_inherited_a_stack_do_not_claim_to_undo(qapp, tag) -> None:
    """They inherited `undo_stack` and never wrote into it: the audit must not ask them for a key that would do nothing."""
    from scripts.audit_ux_certus import MODULES, owns_undo_machinery

    module, cls = MODULES[tag]
    win = getattr(__import__(module, fromlist=[cls]), cls)()
    try:
        assert not owns_undo_machinery(win), f"{tag} now owns an undo machinery: bind Ctrl+Z, then drop it from this list"
        assert not win.undo_stack, f"{tag} wrote into its undo stack"
    finally:
        win.close()
