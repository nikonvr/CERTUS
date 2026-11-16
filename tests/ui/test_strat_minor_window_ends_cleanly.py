"""The STRAT window recovers from a failed final table and ends its session on close (audit 2026-11-15, L6-m1, L6-m2)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QCloseEvent


@pytest.fixture
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        yield win
    finally:
        win.close()


def test_l6_m1_a_failed_final_table_leaves_the_window_usable(strat, monkeypatch) -> None:
    import certus.ui.certus_strat_ui_worker as worker_ui

    monkeypatch.setattr(worker_ui.QMessageBox, "critical", lambda *_a, **_k: None)

    def _fail(*_a, **_k):
        raise RuntimeError("table")

    monkeypatch.setattr(strat, "on_show_strategies_table", _fail)
    strat.run_step0_btn.setEnabled(False)
    strat.run_full_btn.setEnabled(False)

    strat.on_workflow_finished({"final_results": {"all_strategies_results": [{"strategy": {}}]}})

    assert strat.run_step0_btn.isEnabled()
    assert strat.run_full_btn.isEnabled()


def test_l6_m2_closing_ends_the_session(strat, monkeypatch) -> None:
    ended: list[bool] = []
    monkeypatch.setattr(strat, "_session_end", lambda: ended.append(True))
    monkeypatch.setattr(strat, "confirm_close_during_run", lambda _event: True)

    strat.closeEvent(QCloseEvent())

    assert ended == [True]
