"""`_run_mesh_polish_minimizer` runs the L-BFGS-B polish of the spline mesh and keeps the starting vector unless the polish really improved it (audit v2, plan S5.2).

It was the middle of `_spectral_polish_node_mesh_profile` (305 lines). Three outcomes, each reported by the label it returns:

    "lbfgsb"              the polish ended at a cost no worse than the start (to 1e-14)
    "x0_fallback"         the polish ended worse: the start is kept
    "exception_fallback"  the optimiser raised a numerical fault: the start is kept and a warning is logged

The tolerances depend on whether an analytic gradient is used (1e-11 / 1e-8) or not (1e-9 / 1e-6), the counters of the progress dictionary take the largest of what they held and what the optimiser
reports, and the progress is flushed once at the end.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import numpy as np
import pytest

from certus.spline import spline_finalize
from certus.spline.spline_finalize import _run_mesh_polish_minimizer

CENTRE = np.array([1.0, 2.0])
BOUNDS = [(-5.0, 5.0), (-5.0, 5.0)]


def bowl(x) -> float:
    return float(np.sum((np.asarray(x) - CENTRE) ** 2))


def run(x0, *, objective=bowl, minimize_jac=None, prog=None, minimizer=None):
    x0 = np.asarray(x0, dtype=np.float64)
    emitted: list[bool] = []
    prog = prog if prog is not None else {"nfev": 0, "nit": 0}
    m0 = objective(x0)
    out = _run_mesh_polish_minimizer(
        x0,
        lambda _xk: None,
        lambda force=False: emitted.append(force),
        objective,
        logging.getLogger("test_mesh_polish"),
        BOUNDS,
        500,
        m0,
        prog,
        float(np.sqrt(m0)),
        minimizer or objective,
        minimize_jac,
    )
    return out, emitted, prog


def test_a_start_off_the_minimum_is_improved_and_labelled_lbfgsb():
    (m_best, used, x_best), emitted, prog = run([3.0, -1.0])
    assert used == "lbfgsb"
    assert m_best < 1e-8
    np.testing.assert_allclose(x_best, CENTRE, atol=1e-4)
    assert emitted == [True]
    assert prog["nfev"] > 0
    assert prog["nit"] > 0


def test_a_polish_that_ends_worse_than_the_start_keeps_the_start(monkeypatch):
    monkeypatch.setattr(spline_finalize, "minimize", lambda fun, x0, **kw: SimpleNamespace(x=np.asarray(x0) + 1.0, nfev=3, nit=1, message="stopped"))
    (m_best, used, x_best), _, _ = run([1.0, 2.0])
    assert used == "x0_fallback"
    assert m_best == 0.0
    np.testing.assert_array_equal(x_best, [1.0, 2.0])


def test_a_polish_that_ends_equal_to_the_start_counts_as_a_success(monkeypatch):
    monkeypatch.setattr(spline_finalize, "minimize", lambda fun, x0, **kw: SimpleNamespace(x=np.asarray(x0), nfev=1, nit=1, message="no move"))
    (_, used, _), _, _ = run([3.0, -1.0])
    assert used == "lbfgsb"


def test_a_numerical_fault_keeps_the_start_and_warns(monkeypatch, caplog):
    def boom(fun, x0, **kw):
        raise ValueError("singular")

    monkeypatch.setattr(spline_finalize, "minimize", boom)
    with caplog.at_level(logging.WARNING, logger="test_mesh_polish"):
        (m_best, used, x_best), _, _ = run([3.0, -1.0])
    assert used == "exception_fallback"
    assert m_best == bowl([3.0, -1.0])
    np.testing.assert_array_equal(x_best, [3.0, -1.0])
    assert any("full fallback to x0" in record.getMessage() for record in caplog.records)


def test_an_error_that_is_not_numerical_is_not_swallowed(monkeypatch):
    def boom(fun, x0, **kw):
        raise KeyError("a bug, not a numerical fault")

    monkeypatch.setattr(spline_finalize, "minimize", boom)
    with pytest.raises(KeyError):
        run([3.0, -1.0])


@pytest.mark.parametrize(("jac", "ftol", "gtol"), [(True, 1e-11, 1e-8), (None, 1e-9, 1e-6)], ids=["analytic gradient", "finite differences"])
def test_the_tolerances_follow_the_gradient(monkeypatch, jac, ftol, gtol):
    seen: dict = {}

    def recorder(fun, x0, **kw):
        seen.update(kw)
        return SimpleNamespace(x=np.asarray(x0), nfev=1, nit=1, message="")

    monkeypatch.setattr(spline_finalize, "minimize", recorder)
    run([3.0, -1.0], minimize_jac=jac)
    assert seen["method"] == "L-BFGS-B"
    assert seen["jac"] is jac
    assert seen["options"] == {"maxfun": 500, "ftol": ftol, "gtol": gtol}


def test_the_counters_only_ever_grow(monkeypatch):
    monkeypatch.setattr(spline_finalize, "minimize", lambda fun, x0, **kw: SimpleNamespace(x=np.asarray(x0), nfev=3, nit=2, message=""))
    _, _, prog = run([3.0, -1.0], prog={"nfev": 10, "nit": 1})
    assert prog == {"nfev": 10, "nit": 2}


def test_the_polish_function_calls_the_helper():
    import inspect

    assert "m_best, used, x_best = _run_mesh_polish_minimizer(" in inspect.getsource(spline_finalize._spectral_polish_node_mesh_profile)
