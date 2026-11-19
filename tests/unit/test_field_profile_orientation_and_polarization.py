"""Regression tests for C3 (Substrate->Superstrate field orientation) and C2 (oblique p-pol / unpolarized)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_field_core import calculate_electric_field, calculate_opt_metrics
from certus.core.certus_field_gradient import field_metric_gradients


@pytest.mark.unit
def test_calculate_electric_field_returns_substrate_to_superstrate_order() -> None:
    n1, n2, n_sub, l0 = 2.3, 1.45, 1.52, 1064.0
    layer_types = [0, 1] * 4
    pts = 50
    z_coords, e2_vals, ep_c1_cn, integrals, averages = calculate_electric_field(
        n1_r=n1,
        n2_r=n2,
        nSub_r=n_sub,
        l0=l0,
        lambda_calc=l0,
        emp_factors=[1.0] * 8,
        layer_types=layer_types,
        n_superstrate_real=1.0,
        integral_points=pts,
        theta_inc=0.0,
        pol_flag=0,
    )
    assert ep_c1_cn[0] == pytest.approx(l0 / (4.0 * n1), rel=1e-12)
    assert ep_c1_cn[-1] == pytest.approx(l0 / (4.0 * n2), rel=1e-12)
    assert z_coords[0] == pytest.approx(0.0, abs=1e-12)
    assert z_coords[-1] == pytest.approx(sum(ep_c1_cn), rel=1e-12)
    assert np.all(np.diff(z_coords) >= 0.0)
    # HR mirror blocks incident light: high |E|^2 on superstrate side (right), low on substrate side (left)
    assert e2_vals[-1] > 3.0
    assert e2_vals[0] < 0.2

    for i in range(len(ep_c1_cn)):
        s = slice(i * pts, (i + 1) * pts)
        layer_int = float(np.trapezoid(e2_vals[s], z_coords[s]))
        assert layer_int == pytest.approx(integrals[i], rel=1e-10, abs=1e-10)
        assert layer_int / ep_c1_cn[i] == pytest.approx(averages[i], rel=1e-10, abs=1e-10)


@pytest.mark.unit
@pytest.mark.parametrize("pol_flag", [0, 1])
def test_oblique_matched_substrate_field_conserves_poynting_flux(pol_flag: int) -> None:
    n0 = 1.0
    n1 = 1.52
    theta = float(np.deg2rad(45.0))
    cos0 = float(np.cos(theta))
    cos1 = float(np.sqrt(1.0 - (n0 * np.sin(theta) / n1) ** 2))

    metrics = calculate_opt_metrics(
        n1_r=n1,
        n2_r=n1,
        nSub_r=n1,
        l0=1000.0,
        emp_factors_list=[1.0],
        layer_types=[0],
        n_super=n0,
        integral_points=50,
        theta_inc=theta,
        pol_flag=pol_flag,
        lambda_calc=1000.0,
    )
    _, e2_vals, _, _, averages = calculate_electric_field(
        n1_r=n1,
        n2_r=n1,
        nSub_r=n1,
        l0=1000.0,
        lambda_calc=1000.0,
        emp_factors=[1.0],
        layer_types=[0],
        n_superstrate_real=n0,
        integral_points=50,
        theta_inc=theta,
        pol_flag=pol_flag,
    )
    expected_e2 = (1.0 - metrics["R"]) * (n0 * cos0) / (n1 * cos1)
    assert np.allclose(e2_vals, expected_e2, rtol=1e-10, atol=1e-10)
    assert averages[0] == pytest.approx(expected_e2, rel=1e-10, abs=1e-10)
    assert metrics["max_peak_1"] == pytest.approx(expected_e2, rel=1e-10, abs=1e-10)


@pytest.mark.unit
def test_unpolarized_oblique_profile_averages_s_and_p_and_matches_integrals() -> None:
    kwargs = {
        "n1_r": 2.25,
        "n2_r": 1.46,
        "nSub_r": 1.52,
        "l0": 1000.0,
        "lambda_calc": 950.0,
        "emp_factors": [1.1, 0.9, 1.2, 0.8],
        "layer_types": [0, 1, 0, 1],
        "n_superstrate_real": 1.0,
        "integral_points": 60,
        "theta_inc": float(np.deg2rad(55.0)),
    }
    _, e2_s, _, _, _ = calculate_electric_field(**kwargs, pol_flag=0)
    _, e2_p, _, _, _ = calculate_electric_field(**kwargs, pol_flag=1)
    z_u, e2_u, ep_u, integrals_u, averages_u = calculate_electric_field(**kwargs, pol_flag=2)

    assert np.allclose(e2_u, 0.5 * (e2_s + e2_p), rtol=1e-12, atol=1e-12)
    pts = 60
    for i in range(len(ep_u)):
        s = slice(i * pts, (i + 1) * pts)
        layer_int = float(np.trapezoid(e2_u[s], z_u[s]))
        assert layer_int == pytest.approx(integrals_u[i], rel=1e-10, abs=1e-10)
        assert layer_int / ep_u[i] == pytest.approx(averages_u[i], rel=1e-10, abs=1e-10)


@pytest.mark.unit
@pytest.mark.parametrize("factors_list", [[0.6, 0.7, 0.6, 0.7], [3.5, 2.8, 3.5, 2.8]])
def test_oblique_p_pol_field_metric_gradients_high_internal_angle_vs_fd(factors_list: list[float]) -> None:
    # With n_super=1.5, theta=50 deg, n1=1.45: theta_1 ~ 52.4 deg > 45 deg, so |cx|^2 - |cz|^2 < 0
    n1, n2, n_sub, l0, wl, n_super = 1.45, 2.15, 1.5, 1000.0, 980.0, 1.5
    theta = float(np.deg2rad(50.0))
    types = [0, 1, 0, 1]
    points = 120
    factors = np.asarray(factors_list, dtype=np.float64)

    grad_r, grad_p1, grad_p2 = field_metric_gradients(
        n1, n2, n_sub, l0, factors, types, n_super, points, theta, 1, wl
    )

    eps = 1e-6
    fd_r = np.zeros_like(factors)
    fd_p1 = np.zeros_like(factors)
    fd_p2 = np.zeros_like(factors)
    for i in range(len(factors)):
        f_plus = factors.copy()
        f_minus = factors.copy()
        f_plus[i] += eps
        f_minus[i] -= eps
        m_plus = calculate_opt_metrics(n1, n2, n_sub, l0, f_plus.tolist(), types, n_super, points, theta, 1, wl)
        m_minus = calculate_opt_metrics(n1, n2, n_sub, l0, f_minus.tolist(), types, n_super, points, theta, 1, wl)
        fd_r[i] = (m_plus["R"] - m_minus["R"]) / (2.0 * eps)
        fd_p1[i] = (m_plus["max_peak_1"] - m_minus["max_peak_1"]) / (2.0 * eps)
        fd_p2[i] = (m_plus["max_peak_2"] - m_minus["max_peak_2"]) / (2.0 * eps)

    assert np.allclose(grad_r, fd_r, rtol=1e-5, atol=1e-6)
    assert np.allclose(grad_p1, fd_p1, rtol=1e-4, atol=1e-5)
    assert np.allclose(grad_p2, fd_p2, rtol=1e-4, atol=1e-5)
