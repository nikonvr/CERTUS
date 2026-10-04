"""Thickness uncertainties of a reverse-engineering result, from the Jacobian of the data alone (port of certus_re, Zenodo).

    THE COVARIANCE: on a linear model the closed form s^2 (A^T A)^-1, with s^2 = |r|^2 / (m - n), is what comes out
    A DIRECTION THE DATA DO NOT SEE: two identical columns leave one direction free; the thicknesses it involves get nan,
        never a bar that is too small, and the report says how many directions are free
    THE RESULT'S OWN MODEL: the residuals are evaluated with the data rows only, the result's dispersion corrections, and
        its own beam aperture (phase 4) or none; the shared aperture state is restored after
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from certus.core.certus_re_uncertainty import (
    attach_thickness_uncertainty,
    least_squares_covariance,
    thickness_uncertainty_at,
    thickness_uncertainty_report,
)


def linear_problem(seed: int = 7):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(60, 3))
    x_true = np.array([100.0, 250.0, 80.0])
    y = a @ x_true + rng.normal(scale=0.3, size=60)
    x_hat, *_ = np.linalg.lstsq(a, y, rcond=None)
    return a, y - a @ x_hat


def test_on_a_linear_model_the_covariance_is_the_closed_form():
    a, r = linear_problem()
    covariance, s2, dropped, note = least_squares_covariance(a, r, 3)
    expected_s2 = float(r @ r) / (60 - 3)
    assert s2 == pytest.approx(expected_s2, rel=1e-12)
    assert covariance == pytest.approx(expected_s2 * np.linalg.inv(a.T @ a), rel=1e-9)
    assert dropped == 0
    assert note == ""


def test_a_direction_the_data_do_not_see_gets_no_error_bar():
    a, r = linear_problem()
    twin = np.column_stack([a, a[:, 1]])  # columns 1 and 3 identical: their difference is invisible
    covariance, _, dropped, note = least_squares_covariance(twin, r, 4)
    assert dropped == 1
    assert "rank deficient" in note
    assert np.isnan(covariance[1, 1])
    assert np.isnan(covariance[3, 3])
    assert np.isfinite(covariance[0, 0])
    assert np.isfinite(covariance[2, 2])


def test_the_report_gives_one_sigma_per_thickness_and_the_counts():
    a, r = linear_problem()
    report = thickness_uncertainty_report(a, r, np.array([100.0, 250.0, 80.0]))
    covariance, *_ = least_squares_covariance(a, r, 3)
    assert report["sigma_nm"] == pytest.approx(np.sqrt(np.diag(covariance)).tolist(), rel=1e-12)
    assert report["relative"] == pytest.approx((np.sqrt(np.diag(covariance)) / [100.0, 250.0, 80.0]).tolist(), rel=1e-12)
    assert (report["n_data"], report["n_parameters"]) == (60, 3)
    assert report["data_points_per_parameter"] == pytest.approx(20.0)


class _Recorder:
    """Stands for the RE residual helper: records how it is called and what aperture state it sees."""

    def __init__(self, state: dict):
        self.state = state
        self.calls: list[dict] = []

    def __call__(self, ep, wt, want_grad, correc, return_residuals=False, data_only=False):
        a, r = linear_problem()
        self.calls.append({
            "want_grad": want_grad, "return_residuals": return_residuals, "data_only": data_only, "correc": correc,
            "is_phase4": self.state["is_phase4"], "knots": self.state["re_aperture_knots"].copy(),
        })
        return 0.0, None, r, a


def state() -> dict:
    return {"is_phase4": True, "re_aperture_knots": np.full(4, 2.0), "re_p4_beam_knots_lam_nm": np.linspace(1000, 4000, 4)}


def at(result: dict, st: dict, recorder: _Recorder):
    return thickness_uncertainty_at(
        result, mse_grad=recorder, wt_spectral=np.ones(3), correc_nominal=("nominal",),
        p2_to_correc=lambda r, sub: ("spline", tuple(r["re_dH_knots"]), sub), re_state=st,
    )


def test_the_residuals_are_the_data_rows_with_the_results_own_corrections():
    st = state()
    rec = _Recorder(st)
    report = at({"ep": [100.0, 250.0, 80.0], "re_dH_knots": [0.1], "re_dL_knots": [0.2]}, st, rec)
    assert report is not None
    (call,) = rec.calls
    assert call["data_only"] is True
    assert call["return_residuals"] is True
    assert call["want_grad"] is True
    assert call["correc"] == ("spline", (0.1,), False)


def test_a_phase4_result_is_evaluated_with_its_own_aperture_and_the_state_is_restored():
    st = state()
    rec = _Recorder(st)
    at({"ep": [100.0, 250.0, 80.0], "re_p4_beam_ap_knots_deg": [1.0, 1.5, 2.5, 3.0]}, st, rec)
    (call,) = rec.calls
    assert call["is_phase4"] is True
    assert call["knots"].tolist() == [1.0, 1.5, 2.5, 3.0]
    assert st["is_phase4"] is True
    assert st["re_aperture_knots"].tolist() == [2.0] * 4


def test_a_result_without_aperture_is_evaluated_without_the_cone_average():
    st = state()
    rec = _Recorder(st)
    at({"ep": [100.0, 250.0, 80.0]}, st, rec)
    (call,) = rec.calls
    assert call["is_phase4"] is False
    assert call["correc"] == ("nominal",)
    assert st["is_phase4"] is True


def test_aperture_knots_that_do_not_match_the_context_give_no_report():
    st = state()
    rec = _Recorder(st)
    assert at({"ep": [100.0, 250.0, 80.0], "re_p4_beam_ap_knots_deg": [1.0, 2.0]}, st, rec) is None
    assert rec.calls == []


def test_the_report_is_stored_on_the_result_and_logged_layer_by_layer(caplog):
    top = {"ep": [100.0, 250.0, 80.0]}
    a, r = linear_problem()
    with caplog.at_level(logging.INFO):
        attach_thickness_uncertainty(top, lambda res: thickness_uncertainty_report(a, r, np.asarray(res["ep"])), logging.getLogger("t"))
    assert top["thickness_uncertainty"]["n_parameters"] == 3
    assert sum("RE   layer" in rec.getMessage() for rec in caplog.records) == 3
