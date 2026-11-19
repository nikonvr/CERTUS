"""Three minors of the SPLINE free-knot stage (audit 2026-11-15, L3-m1, L3-m2, L3-m4).

L3-m1: the SOL2/SOL3(z0) check decoded the SOL3 vector with the SOL2 decoder; its warning fired every time.
L3-m2: after a stop the context objective returns 1e30 and the stage reported RMSE 1e15 with a valid n, k.
L3-m4: an exception inside L-BFGS-B returned the last iterate with the best value seen at another point.
"""

from __future__ import annotations

import inspect
import logging
import threading

import numpy as np

from certus.spline import spline_polish_mixed
from certus.spline import spline_workers as sw


def test_l3_m1_the_check_measures_sol3_with_its_own_decoder() -> None:
    source = inspect.getsource(sw._run_free_knot_stage)
    assert "_mse_sol3_z0_sp = float(ctx.spectral_mse(z0v))" in source
    assert "nk_from_x_pwlnk(\n                z0v," not in source


def test_l3_m2_a_stopped_context_still_measures_a_fixed_point() -> None:
    class _Ctx:
        stop_event = threading.Event()
        spectral_mse = sw.FreeKnotStageContext.spectral_mse
        obj = sw.FreeKnotStageContext.obj

    ctx = _Ctx()
    ctx._spectral_value = 0.0004
    _Ctx.spectral_mse = lambda self, z: self._spectral_value
    assert ctx.obj(np.zeros(3)) == 0.0004
    ctx.stop_event.set()
    assert ctx.obj(np.zeros(3)) == 1e30, "the optimiser must still be told to stop"
    assert ctx.spectral_mse(np.zeros(3)) == 0.0004


def test_l3_m2_the_stage_evaluates_its_results_without_the_stop_guard() -> None:
    source = inspect.getsource(sw._run_free_knot_stage)
    assert "ctx.obj(" not in source


def test_l3_m4_an_exception_in_lbfgsb_returns_a_coherent_point(monkeypatch, caplog) -> None:
    class _Obj:
        cfg = None

        def __call__(self, x):
            return float(np.sum((np.asarray(x) - 1.0) ** 2))

    def _raise(fun, x0, **_k):
        fun(np.asarray(x0) * 0.0 + 0.9)  # a good point seen before the failure
        fun(np.asarray(x0) * 0.0 + 5.0)  # the last point evaluated, a bad one
        raise ValueError("line search")

    monkeypatch.setattr(spline_polish_mixed, "minimize", _raise)  # the polish calls L-BFGS-B through minimize_polish
    monkeypatch.setattr(sw, "spline_pwl_analytic_grad_supported", lambda _cfg: False)
    certus_logger = logging.getLogger("CERTUS")  # may not propagate to the root handler of caplog
    certus_logger.addHandler(caplog.handler)
    monkeypatch.setattr(certus_logger, "level", logging.WARNING)
    try:
        x, f, _nfev = sw._polish_lbfgsb_chunked(
            _Obj(), np.zeros(2), np.array([[-10.0, 10.0]] * 2), maxfun_total=10, stop_event=threading.Event()
        )
    finally:
        certus_logger.removeHandler(caplog.handler)
    assert f == float(np.sum((x - 1.0) ** 2)), "f is not the value of the returned x"
    np.testing.assert_allclose(x, [0.9, 0.9])
    assert any(r.levelno >= logging.WARNING for r in caplog.records)
