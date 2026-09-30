"""A spline fit that fails falls back to the raw index: it does not crash the smoothing (found by mypy, plan S4.4).

`IndexCore._fit_model_spline_adaptive` is annotated `-> tuple[...]`, and mypy said "Missing return statement": its two
`except` clauses logged "fallback to Polynomial" and then fell off the end of the function, which returns None. The caller
unpacks a quadruple, so any exception inside the fit (a bad knot set, a singular system) ended in
`TypeError: cannot unpack non-iterable NoneType object`, in the window of the user who had chosen that smoothing.

The fallback is the one the bounds check already uses (`fallback-raw-spline-bounds`): the raw index, flagged by its source.
The message said "Polynomial", which was never what happened: it now says what does.
"""

from __future__ import annotations

import numpy as np
import pytest

import certus.core.certus_substrate_index as csi


def _dispersion() -> tuple[np.ndarray, np.ndarray]:
    wl = np.linspace(400.0, 2400.0, 80, dtype=float)
    return wl, 1.85 - 0.00007 * (wl - 400.0)  # decreasing: the spline is not rejected as non-monotonic


def test_the_fit_works_when_nothing_fails() -> None:
    """Control: the failure tests below fail on the raw fallback, not on a fit that never worked."""
    wl, n = _dispersion()

    _, meta = csi.IndexCore.fit_sellmeier(n, wl, 400.0, 2400.0, model_kind="spline_adaptive", return_meta=True)

    assert str(meta["source"]).startswith("analytic-bspline-lsq")


@pytest.mark.parametrize(
    "error",
    [ValueError("knots"), RuntimeError("solver"), ArithmeticError("overflow"), FloatingPointError("nan"), np.linalg.LinAlgError("singular")],
    ids=lambda e: type(e).__name__,
)
def test_a_spline_fit_that_raises_falls_back_to_the_raw_index(monkeypatch, error) -> None:
    wl, n = _dispersion()

    def fails(*_args, **_kwargs):
        raise error

    # Called after the knot search and outside its own guard: the exception reaches the `except` of the fit.
    monkeypatch.setattr(csi, "_index_eval_bspline_linear_extrap", fails)

    n_fit, meta = csi.IndexCore.fit_sellmeier(n, wl, 400.0, 2400.0, model_kind="spline_adaptive", return_meta=True)

    assert meta["source"] == "fallback-raw-spline-failed"
    assert meta["requested_model_kind"] == "spline_adaptive"
    np.testing.assert_allclose(n_fit, n)


def test_the_fit_reports_why_it_fell_back(monkeypatch) -> None:
    wl, n = _dispersion()
    monkeypatch.setattr(csi, "_index_eval_bspline_linear_extrap", lambda *a, **k: (_ for _ in ()).throw(ValueError("knots")))
    said: list[str] = []
    # The module's logger does not propagate to the root handler `caplog` listens on: read what it is told directly.
    monkeypatch.setattr(csi.logger, "warning", lambda message, *args, **kwargs: said.append(message % args if args else message))

    csi.IndexCore.fit_sellmeier(n, wl, 400.0, 2400.0, model_kind="spline_adaptive")

    text = " ".join(said)
    assert "Spline fit failed: knots" in text
    assert "Polynomial" not in text, "the message promised a polynomial fit that was never made"
