"""The convergence guard gives further attempts to the modules whose result varies by design
(accepted by the project owner on 2026-09-27: docs/ETAT.md, section 3), and only to them. The runs are simulated:
these tests take a second, the guard itself several minutes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _guard():
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("convergence_guard_under_test", HERE / "test_convergence_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _simulated(values):
    calls: list[str] = []

    def run(name, script):
        calls.append(name)
        return values[len(calls) - 1], ""

    return run, calls


def test_an_unlucky_draw_of_a_stochastic_module_gets_another_attempt(monkeypatch) -> None:
    guard = _guard()
    reference = guard._baseline()["INDEX"]
    run, calls = _simulated([reference * 2.6, reference * 0.99])
    monkeypatch.setattr(guard, "run_test_and_extract_rmse", run)
    guard.test_convergence_has_not_regressed("INDEX", "test_index.py")
    assert calls == ["INDEX", "INDEX"]


def test_a_deterministic_module_gets_a_single_attempt(monkeypatch) -> None:
    guard = _guard()
    reference = guard._baseline()["SPLINE"]
    run, calls = _simulated([reference * 1.5, reference])
    monkeypatch.setattr(guard, "run_test_and_extract_rmse", run)
    with pytest.raises(AssertionError):
        guard.test_convergence_has_not_regressed("SPLINE", "test_spline.py")
    assert calls == ["SPLINE"]


def test_a_real_regression_still_fails_after_every_attempt(monkeypatch) -> None:
    guard = _guard()
    reference = guard._baseline()["INDEX"]
    run, calls = _simulated([reference * 2.0] * guard.ESSAIS)
    monkeypatch.setattr(guard, "run_test_and_extract_rmse", run)
    with pytest.raises(AssertionError, match="execution"):
        guard.test_convergence_has_not_regressed("INDEX", "test_index.py")
    assert len(calls) == guard.ESSAIS
