"""Regression tests for M1 (TL E==Eg continuity, NaN/Inf in epsilon_to_nk), m5 (Sellmeier pole guard), and M6b (Cauchy cache)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_optical_models import (
    _get_nk_cauchy_cached,
    epsilon1_TL_analytic,
    epsilon1_TL_overdamped_point,
    epsilon_to_nk,
    sellmeier_n_array,
)


@pytest.mark.unit
@pytest.mark.parametrize("c_val", [1.4, 8.5])  # standard (C < 2*E0) and overdamped (C >= 2*E0)
def test_epsilon1_tl_is_continuous_at_exact_bandgap(c_val: float) -> None:
    eg, amp, e0, eps_inf = 2.1, 42.0, 3.6, 2.3
    eps = 1e-5
    energies = np.array([eg - eps, eg, eg + eps], dtype=np.float64)

    vals = epsilon1_TL_analytic(energies, eg, amp, e0, c_val, eps_inf)
    assert np.all(np.isfinite(vals))
    assert vals[1] == pytest.approx(vals[0], rel=0.0, abs=1e-4)
    assert vals[1] == pytest.approx(vals[2], rel=0.0, abs=1e-4)

    point_left = epsilon1_TL_overdamped_point(float(energies[0]), eg, amp, e0, c_val, eps_inf)
    point_mid = epsilon1_TL_overdamped_point(float(energies[1]), eg, amp, e0, c_val, eps_inf)
    point_right = epsilon1_TL_overdamped_point(float(energies[2]), eg, amp, e0, c_val, eps_inf)
    assert np.isfinite(point_mid)
    assert point_mid == pytest.approx(point_left, rel=0.0, abs=1e-4)
    assert point_mid == pytest.approx(point_right, rel=0.0, abs=1e-4)


@pytest.mark.unit
@pytest.mark.parametrize("bad_val", [np.nan, np.inf, -np.inf])
def test_epsilon_to_nk_rejects_non_finite_inputs(bad_val: float) -> None:
    eps1 = np.array([4.0, bad_val, 3.5], dtype=np.float64)
    eps2 = np.array([0.1, 0.2, 0.3], dtype=np.float64)
    _, _, valid1 = epsilon_to_nk(eps1, eps2, 1.0, 6.0, 5.0)
    assert valid1 is False

    eps1_ok = np.array([4.0, 3.8, 3.5], dtype=np.float64)
    eps2_bad = np.array([0.1, bad_val, 0.3], dtype=np.float64)
    _, _, valid2 = epsilon_to_nk(eps1_ok, eps2_bad, 1.0, 6.0, 5.0)
    assert valid2 is False


@pytest.mark.unit
def test_sellmeier_n_array_guards_exact_pole() -> None:
    # C1 = 0.25 um^2 => pole at wl = 500.0 nm (w = 0.5 um, w^2 = 0.25)
    wls = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    n_vals = sellmeier_n_array(wls, 1.1, 0.25, 0.4, 0.02, 0.9, 90.0, 200.0)
    assert np.all(np.isfinite(n_vals))


@pytest.mark.unit
def test_get_nk_cauchy_cached_returns_isolated_copies() -> None:
    wls = (450.0, 550.0, 650.0)
    first = _get_nk_cauchy_cached(1.52, 1.50, wls)
    expected = first.copy()
    first[:] = -999.0

    second = _get_nk_cauchy_cached(1.52, 1.50, wls)
    assert np.allclose(second, expected, rtol=1e-12, atol=1e-12)
