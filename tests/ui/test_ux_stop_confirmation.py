"""Stopping a run must require a deliberate click (step 2.20).

confirm_stop_with_timeout guards every stop path of the suite - DESIGN, INDEX,
RE, STRAT and both METAL. Measured 2026-09-05, it stopped the run on THREE
different kinds of inaction:

    msg.setDefaultButton(btn_stop)   the destructive button had the focus
    btn_stop.animateClick()          the countdown clicked it after 10 s
    return True                      the fall-through: closing the dialog with
                                     Escape or the X clicks nothing, so
                                     clickedButton() is None - and the old code
                                     read that as "stop"

That matters because Esc is now bound to stop in every module (step 2.20a), and
Esc is a reflex key. Press it once without meaning to, walk away, and a run that
takes 2 h 39 on STRAT is gone - twice over, because a second reflexive Esc
dismisses the confirmation too.

The rule asserted here: inaction never destroys work. True is returned only when
the operator actually clicked "Stop Now".
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


def _spin(seconds: float) -> None:
    from PyQt6.QtWidgets import QApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def test_letting_the_countdown_expire_keeps_the_run(qapp, monkeypatch) -> None:
    """Nobody touches the dialog: the optimisation must survive."""
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from certus.ui.certus_ui_utils import confirm_stop_with_timeout

    # exec() would block on a modal loop; spin the event queue instead so the
    # internal countdown really fires.
    monkeypatch.setattr(QMessageBox, "exec", lambda self: _spin(2.5) or 0)

    parent = QWidget()
    try:
        assert confirm_stop_with_timeout(parent, timeout_sec=1) is False, (
            "an unattended confirmation stopped the run by itself"
        )
    finally:
        parent.deleteLater()


def test_closing_the_dialog_without_clicking_keeps_the_run(qapp, monkeypatch) -> None:
    """Escape or the window's X click no button - that is not a confirmation."""
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from certus.ui.certus_ui_utils import confirm_stop_with_timeout

    # Return immediately, as a rejected dialog does, without clicking anything.
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    parent = QWidget()
    try:
        assert confirm_stop_with_timeout(parent, timeout_sec=30) is False, (
            "dismissing the dialog was read as a confirmation to stop"
        )
    finally:
        parent.deleteLater()


def test_the_destructive_button_is_not_the_default() -> None:
    """The focused button must be the one that loses nothing."""
    src = Path("certus/ui/certus_ui_utils.py").read_text(encoding="utf-8")
    assert "msg.setDefaultButton(btn_stop)" not in src, (
        "the destructive button holds the focus: Enter or Space stops the run"
    )


def test_the_countdown_never_clicks_the_destructive_button() -> None:
    """A countdown may cancel by itself; it may never destroy by itself."""
    src = Path("certus/ui/certus_ui_utils.py").read_text(encoding="utf-8")
    assert "btn_stop.animateClick()" not in src, (
        "the countdown presses Stop on the operator's behalf"
    )
