"""The Needle's stagnation gate and predicted-gain thresholds are the ones tuned on the window.

`CertusDesignApp.__init__` sets `_needle_gate_no_improve_rounds = 3`, `_needle_pred_gain_rel_threshold
= 0.003` and `_needle_pred_gain_abs_threshold = 2e-5`, and the optimization manager keeps
`_needle_no_improve_rounds` there. `DesignOrchestrator` read all four on itself
(`getattr(self, ...)`), which holds none of them: the counter always read 0 against a gate of 2, so
the stagnation branch of the deep Needle (exploration beyond the target, then pruning) never
opened; the thresholds of the predicted gain were the orchestrator's defaults (1e-5, 0.002),
never the tuned values. The owner accepted the change of behaviour on 2026-09-29.

The orchestrator only stores its window, so a namespace stands for it here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _window(**extra):
    attributes = {
        "front_table": SimpleNamespace(rowCount=lambda: 10),
        "allow_growth_check": SimpleNamespace(isChecked=lambda: True),
        "log": lambda *a, **k: None,
        "_set_busy": lambda *a, **k: None,
        "ep_current": None,
        "_save_table_state": lambda: [],
    }
    return SimpleNamespace(**{**attributes, **extra})


def _orchestrator(window, monkeypatch):
    from certus.core.certus_design_orchestrator import DesignOrchestrator

    orchestrator = DesignOrchestrator(window)
    orchestrator._target_layer_count = 10  # no deficit: only the stagnation can start the Needle
    started = []
    monkeypatch.setattr(orchestrator, "_start_needle_process", lambda: started.append(1))
    return orchestrator, started


def test_the_needle_explores_once_the_window_counts_as_many_rounds_as_its_gate(monkeypatch) -> None:
    window = _window(_needle_no_improve_rounds=3, _needle_gate_no_improve_rounds=3)
    orchestrator, started = _orchestrator(window, monkeypatch)

    assert orchestrator._maybe_start_needle_growth() is True

    assert started == [1]
    assert orchestrator._overshoot_active is True


def test_the_needle_waits_while_the_window_counts_fewer_rounds_than_its_gate(monkeypatch) -> None:
    window = _window(_needle_no_improve_rounds=2, _needle_gate_no_improve_rounds=3)
    orchestrator, started = _orchestrator(window, monkeypatch)

    assert orchestrator._maybe_start_needle_growth() is False

    assert started == []


def test_a_window_without_a_gate_falls_back_on_two_rounds(monkeypatch) -> None:
    window = _window(_needle_no_improve_rounds=2)
    orchestrator, started = _orchestrator(window, monkeypatch)

    assert orchestrator._maybe_start_needle_growth() is True

    assert started == [1]


def _split_result(gain_abs: float, best_rmse: float = 0.010) -> dict:
    return {"action": "split", "cost": (best_rmse - gain_abs) ** 2, "layer_idx": 2}


def _needle_found(monkeypatch, *, growth: bool, gain_abs: float, **tuning):
    window = _window(
        _workflow_best_rmse=0.010,
        allow_growth_check=SimpleNamespace(isChecked=lambda: growth),
        **tuning,
    )
    from certus.core.certus_design_orchestrator import DesignOrchestrator

    orchestrator = DesignOrchestrator(window)
    handled, applied = [], []
    monkeypatch.setattr(
        orchestrator, "_handle_needle_no_candidate", lambda action, res: (handled.append(action), (action, res, True))[1]
    )
    monkeypatch.setattr(orchestrator, "_apply_needle_split_insertion", lambda res: applied.append(res) or False)

    orchestrator._on_needle_found(_split_result(gain_abs))
    return handled, applied


def test_a_gain_under_the_window_thresholds_is_skipped_when_the_growth_is_off(monkeypatch) -> None:
    # 1.5e-5 (0.15 %) is above the orchestrator's defaults (1e-5) and under the tuned ones (2e-5, 0.3 %).
    handled, applied = _needle_found(
        monkeypatch,
        growth=False,
        gain_abs=1.5e-5,
        _needle_pred_gain_abs_threshold=2e-5,
        _needle_pred_gain_rel_threshold=0.003,
    )

    assert handled == ["none"]
    assert applied == []


def test_a_gain_over_the_window_thresholds_is_applied(monkeypatch) -> None:
    handled, applied = _needle_found(
        monkeypatch,
        growth=False,
        gain_abs=5e-5,
        _needle_pred_gain_abs_threshold=2e-5,
        _needle_pred_gain_rel_threshold=0.003,
    )

    assert handled == []
    assert len(applied) == 1


def test_with_the_growth_on_the_predicted_gain_never_stops_an_insertion(monkeypatch) -> None:
    handled, applied = _needle_found(
        monkeypatch,
        growth=True,
        gain_abs=1.5e-5,
        _needle_pred_gain_abs_threshold=2e-5,
        _needle_pred_gain_rel_threshold=0.003,
    )

    assert handled == []
    assert len(applied) == 1


@pytest.mark.parametrize("missing", ["_needle_pred_gain_abs_threshold", "_needle_pred_gain_rel_threshold"])
def test_a_window_without_thresholds_falls_back_on_the_defaults(monkeypatch, missing) -> None:
    tuning = {"_needle_pred_gain_abs_threshold": 2e-5, "_needle_pred_gain_rel_threshold": 0.003}
    del tuning[missing]
    # 5e-6 (0.05 %) is under the defaults whichever threshold the window lacks.
    handled, applied = _needle_found(monkeypatch, growth=False, gain_abs=5e-6, **tuning)

    assert handled == ["none"]
    assert applied == []
