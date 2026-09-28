"""Three STRAT actions that stopped on a NameError, each run on a real window.

The STRAT mixins received their names through `from certus.ui.certus_strat_common import *`,
which never provided three of the names they use: PopOutWindow (detaching the stack table),
_validate_strategy_blocks_contract (loading external strategies: a star import never carries a
name that starts with an underscore) and NON_MONOTONIC_MODE_REJECT (the "reject" choice of the
non-monotonic mode). Found on 2026-09-28 by replacing the star imports: ruff then reports them
as F821. The exceptions each path catches do not include NameError.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT actions", main_windows_only=True)


@pytest.fixture
def window(qapp):
    from certus.ui.certus_strat_ui import CertusStratApp

    return CertusStratApp()


def test_the_stack_table_detaches_and_comes_back(window) -> None:
    from certus.ui.certus_strat_popout_ui import PopOutWindow

    window.detach_stack_window()
    floating = window._floating_stack_window
    assert isinstance(floating, PopOutWindow)

    floating.close()
    assert window._floating_stack_window is None
    assert not window.detach_btn.isHidden()


def test_the_reject_mode_reaches_the_parameters(window) -> None:
    from certus_physics import NON_MONOTONIC_MODE_ATTENUATE, NON_MONOTONIC_MODE_REJECT

    combo = window.widgets["non_monotonic_mode"]
    assert window.collect_params()["non_monotonic_mode"] == NON_MONOTONIC_MODE_ATTENUATE
    combo.setCurrentText("reject")
    assert window.collect_params()["non_monotonic_mode"] == NON_MONOTONIC_MODE_REJECT


def test_external_strategies_are_validated_and_handed_to_the_worker(window, tmp_path, monkeypatch) -> None:
    import certus.ui.certus_strat_ui_state as state
    from PyQt6.QtWidgets import QFileDialog

    n_layers = window.widgets["stack_table"].rowCount()
    assert n_layers > 0
    strategy = {
        "strategy_id": "one-block",
        "n_blocks": 1,
        "blocks": [{"start": 0, "end": n_layers, "wavelength": 600.0, "num_layers": n_layers}],
    }
    path = tmp_path / "strategy.json"
    path.write_text(json.dumps([strategy]), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(path)], "")))
    monkeypatch.setattr(state, "set_certus_last_dir", lambda *a, **k: None)
    monkeypatch.setattr(state, "rebuild_visualization_context", lambda params, logger: object())

    handed = []

    class _Worker:
        """Records what the real WorkerThread would have evaluated, and runs nothing."""

        def __init__(self, step, params, opti_results, timing_logger):
            handed.append(params)
            self.signals = _Signals()

        def start(self):
            pass

        def isRunning(self):
            return False

    class _Signal:
        def connect(self, *a):
            pass

        def disconnect(self, *a):
            raise TypeError

    class _Signals:
        def __getattr__(self, name):
            return _Signal()

    monkeypatch.setattr(state, "WorkerThread", _Worker)
    monkeypatch.setattr(window, "_register_worker_thread", lambda *a: None)
    monkeypatch.setattr(window.worker_manager, "register_worker", lambda *a: None)

    window.load_external_strategies()

    assert len(handed) == 1
    assert [s["strategy_id"] for s in handed[0]["loaded_strategies"]] == ["one-block"]
