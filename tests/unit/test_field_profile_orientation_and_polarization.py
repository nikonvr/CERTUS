"""Regression tests for C3 (Substrate->Superstrate field orientation) and C2 (oblique p-pol / unpolarized)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_field_core import calculate_electric_field


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
