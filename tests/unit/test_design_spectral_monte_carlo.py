"""Spectral Monte Carlo of DESIGN (certus.core.certus_design_tolerance.spectral_monte_carlo)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_tolerance import rmse_band, spectral_monte_carlo


def _quadratic(c: np.ndarray, a: np.ndarray):
    return lambda d: float(np.sum(a * (d - c) ** 2))


def test_zero_sigma_gives_the_nominal_rmse_on_every_draw():
    cost = _quadratic(np.array([100.0, 50.0]), np.array([1e-4, 2e-4]))
    ep = np.array([101.0, 49.0])
    mc = spectral_monte_carlo(cost, ep, draws=20, rmse_threshold=1.0)
    assert np.all(mc.samples == mc.nominal)
    assert mc.mean == pytest.approx(mc.nominal, rel=1e-14)  # the mean of 20 equal floats can differ by one ulp
    assert mc.yield_fraction == 1.0


def test_mean_squared_error_matches_the_exact_expectation_of_a_quadratic_cost():
    # E[sum a_i (d_i + e_i - c_i)^2] = sum a_i ((d_i - c_i)^2 + var_i), var_i = abs^2 + (rel d_i)^2 + (ot / n_i)^2
    c, a = np.array([120.0, 80.0, 200.0]), np.array([1e-4, 3e-4, 2e-4])
    ep, n = np.array([118.0, 83.0, 199.0]), np.array([2.35, 1.45, 2.35])
    s_abs, s_rel, s_ot = 0.4, 0.01, 0.5
    mc = spectral_monte_carlo(_quadratic(c, a), ep, n_real=n, sigma_abs_nm=s_abs, sigma_rel=s_rel, sigma_ot_nm=s_ot,
                              draws=40000, seed=3)
    var = s_abs ** 2 + (s_rel * ep) ** 2 + (s_ot / n) ** 2
    exact = float(np.sum(a * ((ep - c) ** 2 + var)))
    assert abs(mc.rms ** 2 - exact) < 0.02 * exact


def test_draws_of_a_layer_do_not_depend_on_the_rest_of_the_stack():
    # C2: the error of layer i is a function of (seed, draw, i) only
    seen = {}

    def record(tag):
        def cost(d):
            seen.setdefault(tag, []).append(d[0])
            return 0.0
        return cost

    spectral_monte_carlo(record("short"), np.array([100.0, 50.0]), sigma_abs_nm=1.0, draws=5, seed=7)
    spectral_monte_carlo(record("long"), np.array([100.0, 50.0, 70.0, 90.0]), sigma_abs_nm=1.0, draws=5, seed=7)
    assert seen["short"][:5] == seen["long"][:5]


def test_cvar_is_the_mean_of_the_worst_five_percent_and_not_below_the_percentile():
    cost = _quadratic(np.array([100.0]), np.array([1e-3]))
    mc = spectral_monte_carlo(cost, np.array([100.0]), sigma_abs_nm=1.0, draws=2000, seed=1)
    worst = np.sort(mc.samples)[::-1][:100]
    assert mc.cvar95 == pytest.approx(worst.mean())
    assert mc.cvar95 >= mc.p95


def test_optical_thickness_errors_need_the_indices():
    with pytest.raises(ValueError, match="real index"):
        spectral_monte_carlo(lambda d: 0.0, np.array([10.0, 20.0]), sigma_ot_nm=0.5, draws=3)


def test_rmse_band_is_unchanged():
    # C1: the existing band keeps its draws (sequential generator seeded by `seed`)
    cost = _quadratic(np.array([100.0, 50.0]), np.array([1e-4, 2e-4]))
    band = rmse_band(cost, np.array([101.0, 49.0]), draws=50, seed=0)
    ep = np.array([101.0, 49.0])
    sigma = 0.5 * (0.001 * ep + 0.2)
    rng = np.random.default_rng(0)
    ref = [np.sqrt(cost(np.maximum(ep + sigma * rng.standard_normal(2), 0.0))) for _ in range(50)]
    assert band.mean == float(np.mean(ref))
