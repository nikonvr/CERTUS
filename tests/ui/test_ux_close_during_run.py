"""Closing a window mid-run must ask first (step 2.20c).

Measured 2026-09-05:

    CertusBaseApp.closeEvent (certus_base_app.py:2277) called _stop_all_workers()
    and never asked anything;
    CERTUS_STRAT overrides closeEvent and ends with `finally: event.accept()`,
    so it accepted the close whatever happened - and its own comment says the
    override never chains to the base one.

A STRAT run takes up to 2 h 39. Clicking the window's X by accident threw it
away with no question and no undo. This is the same family as the stop dialog:
an irreversible loss reachable without a decision.

The guard must be PRECISE, not merely safe: worker_manager.active_count()
counts REGISTRATIONS, and a worker that has finished may still be registered.
Blocking on that would freeze a window with nothing to lose - and
tests/unit/test_gui_apps_smoke.py closes eleven of them.
"""

from __future__ import annotations

import pytest

MODULES_UNDER_TEST = [
    ("certus.ui.certus_field_ui", "CertusFieldApp"),  # inherits CertusBaseApp.closeEvent
    ("certus.ui.certus_strat_ui", "CertusStratApp"),  # overrides it, never chains
]


class _FakeRunningWorker:
    """Duck-types the one method the guard is allowed to trust."""

    def isRunning(self) -> bool:
        return True


@pytest.mark.parametrize("mod_path,cls_name", MODULES_UNDER_TEST)
def test_close_is_refused_when_the_operator_declines(qapp, monkeypatch, mod_path, cls_name) -> None:
    """A running worker plus a declined confirmation must leave the window open."""
    from PyQt6.QtGui import QCloseEvent

    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    try:
        win.worker_manager._active_workers = [_FakeRunningWorker()]
        asked = []
        monkeypatch.setattr(
            type(win), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False
        )

        event = QCloseEvent()
        win.closeEvent(event)

        assert asked, f"{cls_name} closed during a run without asking"
        assert not event.isAccepted(), f"{cls_name} closed anyway after the operator declined"
    finally:
        win.worker_manager._active_workers = []
        win.close()


@pytest.mark.parametrize("mod_path,cls_name", MODULES_UNDER_TEST)
def test_close_is_silent_when_nothing_is_running(qapp, monkeypatch, mod_path, cls_name) -> None:
    """No run, no question: a false positive would block a harmless close."""
    from PyQt6.QtGui import QCloseEvent

    cls = getattr(__import__(mod_path, fromlist=[cls_name]), cls_name)
    win = cls()
    try:
        win.worker_manager._active_workers = []
        asked = []
        monkeypatch.setattr(
            type(win), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False
        )

        event = QCloseEvent()
        win.closeEvent(event)

        assert not asked, f"{cls_name} asked for confirmation with no worker running"
        assert event.isAccepted(), f"{cls_name} refused to close with nothing running"
    finally:
        win.close()
