"""A window opens without saying the same thing twice and without a shortcut it could not install (U5).

Measured on 2026-11-12 (`scripts/audit_ux_certus.py`, 1440x900), DESIGN only:

* two toasts with the same text, "Evaluation OK. RMSE: 0.368035", one above the other: the window evaluates its design
  twice while it starts, and each evaluation announced itself;
* a warning in the log, "shortcut 'Ctrl+S' requested for 'save' but already claimed by QShortcut(Ctrl+S)": the window
  bound Ctrl+S to its save by hand, then asked the standard installer for the same key and the same action.

A message that is already on screen is not shown a second time: the toast stack answers with the toast it has. DESIGN
leaves Ctrl+S to the standard installer.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.audit_ux_certus import MODULES, _run_worker  # noqa: E402


@pytest.mark.parametrize("app", sorted(MODULES))
def test_the_window_opens_without_a_repeated_toast_or_a_refused_shortcut(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["shortcut_conflicts"] == [], f"{app} asked for a key that was taken"
    assert len(set(row["toasts"])) == len(row["toasts"]), f"{app} shows the same toast twice: {row['toasts']}"


def test_design_still_saves_on_ctrl_s() -> None:
    row = _run_worker("CERTUS_DESIGN", 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")
    assert "Ctrl+S" not in row["missing_vital_keys"]


@pytest.fixture
def window(qapp):
    from PyQt6.QtWidgets import QMainWindow

    win = QMainWindow()
    win.resize(900, 600)
    win.show()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()


def test_a_message_already_on_screen_is_not_shown_again(window) -> None:
    from certus.ui.certus_toast_stack import get_toast_stack, show_toast_stack

    first = show_toast_stack(window, "Evaluation OK. RMSE: 0.368035", variant="success", duration_ms=0)
    again = show_toast_stack(window, "Evaluation OK. RMSE: 0.368035", variant="success", duration_ms=0)

    assert again is first
    assert len(get_toast_stack(window)._toasts) == 1


def test_another_message_or_another_kind_is_another_toast(window) -> None:
    from certus.ui.certus_toast_stack import get_toast_stack, show_toast_stack

    show_toast_stack(window, "Evaluation OK. RMSE: 0.368035", variant="success", duration_ms=0)
    show_toast_stack(window, "Evaluation OK. RMSE: 0.401122", variant="success", duration_ms=0)
    show_toast_stack(window, "Evaluation OK. RMSE: 0.368035", variant="warning", duration_ms=0)

    assert len(get_toast_stack(window)._toasts) == 3


def test_a_message_that_went_away_can_be_shown_again(window, qapp) -> None:
    from PyQt6.QtTest import QTest

    from certus.ui.certus_toast_stack import get_toast_stack, show_toast_stack

    first = show_toast_stack(window, "Saved", variant="success", duration_ms=0)
    first._dismiss()
    # The toast leaves the stack when its fade-out ends: wait for that, not for a duration (400 ms were not enough under
    # the load of a full validation).
    deadline = time.monotonic() + 10.0
    while get_toast_stack(window)._toasts and time.monotonic() < deadline:
        QTest.qWait(20)
    assert get_toast_stack(window)._toasts == []

    again = show_toast_stack(window, "Saved", variant="success", duration_ms=0)

    assert again is not first
    assert len(get_toast_stack(window)._toasts) == 1
