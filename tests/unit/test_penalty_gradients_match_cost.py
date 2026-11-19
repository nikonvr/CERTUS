"""Regression tests for M5: penalty derivatives align with cost in DESIGN front-only and METAL BILAYER."""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.gradient_metal import compute_metal_bilayer_gradient_analytic
from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic


@pytest.mark.unit
def test_front_only_min_thickness_penalty_gradient_matches_cost_fd() -> None:
    wls = np.linspace(500.0, 900.0, 11, dtype=np.float64)
    ep = np.array([19.9, 80.0, 100.0], dtype=np.float64)  # ep[0] < min_d=20.0 (avoid ULP masking on large penalty)
    n_layers = np.broadcast_to(np.array([2.2 + 0j, 1.46 + 0j, 2.2 + 0j], dtype=np.complex128), (len(wls), 3)).copy()
    n_sub = np.full(len(wls), 1.52 + 0j, dtype=np.complex128)
    tgt_vals = np.full(len(wls), 0.85, dtype=np.float64)
    tgt_weights = np.ones(len(wls), dtype=np.float64)

    _, grad = compute_gradient_all_layers_analytic(
        ep, n_layers, n_sub, wls, tgt_vals, tgt_weights, 20.0, False,
        np.zeros((len(wls), 0), dtype=np.complex128), np.zeros(0, dtype=np.float64),
    )

    eps = 1e-3
    fd = np.zeros_like(ep)
    for i in range(len(ep)):
        ep_up = ep.copy()
        ep_dn = ep.copy()
        ep_up[i] += eps
        ep_dn[i] -= eps
        c_up, _ = compute_gradient_all_layers_analytic(
            ep_up, n_layers, n_sub, wls, tgt_vals, tgt_weights, 20.0, False,
            np.zeros((len(wls), 0), dtype=np.complex128), np.zeros(0, dtype=np.float64),
        )
        c_dn, _ = compute_gradient_all_layers_analytic(
            ep_dn, n_layers, n_sub, wls, tgt_vals, tgt_weights, 20.0, False,
            np.zeros((len(wls), 0), dtype=np.complex128), np.zeros(0, dtype=np.float64),
        )
        fd[i] = (c_up - c_dn) / (2.0 * eps)

    assert np.allclose(grad, fd, rtol=1e-4, atol=1e-4)


@pytest.mark.unit
@pytest.mark.parametrize(("e_m", "e_l"), [(0.5, 45.0), (25.0, 0.5)])
def test_metal_bilayer_thin_film_gradient_matches_mse_fd(e_m: float, e_l: float) -> None:
    wls = np.linspace(450.0, 750.0, 15, dtype=np.float64)
    num_knots = 4
    r_tgt = np.full_like(wls, 0.4)
    n_sub = np.full_like(wls, 4.0 - 0.05j, dtype=np.complex128)
    x = np.array([e_m, e_l, 1.46, 3000.0, 0.25, 0.22, 0.20, 0.18, 2.5, 2.8, 3.1, 3.4, 550.0, 650.0], dtype=np.float64)

    _, grad = compute_metal_bilayer_gradient_analytic(x, num_knots, wls, r_tgt, 10.0, n_sub)

    eps = 1e-6
    for idx in (0, 1):
        x_up = x.copy()
        x_dn = x.copy()
        x_up[idx] += eps
        x_dn[idx] -= eps
        mse_up, _ = compute_metal_bilayer_gradient_analytic(x_up, num_knots, wls, r_tgt, 10.0, n_sub)
        mse_dn, _ = compute_metal_bilayer_gradient_analytic(x_dn, num_knots, wls, r_tgt, 10.0, n_sub)
        fd_i = (mse_up - mse_dn) / (2.0 * eps)
        assert grad[idx] == pytest.approx(fd_i, rel=1e-4, abs=1e-6)
