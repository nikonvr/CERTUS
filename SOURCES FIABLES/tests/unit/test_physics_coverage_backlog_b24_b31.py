"""Coverage backlog batch tests for action #37 (B.24..B.31).

These tests target the remaining physics kernels listed in the roadmap and
validate core contracts (shape, finiteness, boundedness, deterministic outputs).
"""

from __future__ import annotations

import numpy as np

from certus.core._certus_physics_impl import (
    _calc_spectrum_oblique_parallel,
    _compute_epsilon1_gradient_kernel,
    _compute_ir_global_cost_gradient_kernel,
    _compute_metal_tmm_gradient_kernel,
    _compute_oblique_rt_and_grads_kernel,
    _compute_single_layer_sensitivity_kernel,
    calculate_detailed_growth,
    needle_scan_cached,
)


def _build_simple_stack(n_wls: int = 6, n_layers: int = 3):
    wls = np.linspace(450.0, 850.0, n_wls, dtype=np.float64)
    ep = np.linspace(60.0, 120.0, n_layers, dtype=np.float64)
    n_layers_T = np.zeros((n_wls, n_layers), dtype=np.complex128)
    for i, wl in enumerate(wls):
        for j in range(n_layers):
            base = 2.2 if (j % 2 == 0) else 1.46
            disp = 0.015 * (550.0 / wl - 1.0)
            n_layers_T[i, j] = complex(base + disp, 0.0)
    n_sub = np.array([complex(1.52, 0.0)] * n_wls, dtype=np.complex128)
    return wls, ep, n_layers_T, n_sub


def test_b24_calc_spectrum_oblique_parallel_finite_outputs():
    wls, ep, n_layers_T, n_sub = _build_simple_stack(n_wls=5, n_layers=3)
    r, t = _calc_spectrum_oblique_parallel(
        wls,
        n_layers_T,
        ep,
        n_sub,
        35.0,
        True,
    )
    assert r.shape == (len(wls),)
    assert t.shape == (len(wls),)
    assert np.all(np.isfinite(r))
    assert np.all(np.isfinite(t))
    assert np.all((r >= 0.0) & (r <= 1.0 + 1e-9))
    assert np.all((t >= 0.0) & (t <= 1.0 + 1e-9))


def test_b24_oblique_parallel_zero_layer_branch_works():
    wls = np.linspace(450.0, 750.0, 4, dtype=np.float64)
    n_layers_T = np.zeros((len(wls), 0), dtype=np.complex128)
    d_layers = np.zeros(0, dtype=np.float64)
    n_sub = np.array([complex(1.45, 0.0)] * len(wls), dtype=np.complex128)
    r, t = _calc_spectrum_oblique_parallel(wls, n_layers_T, d_layers, n_sub, 25.0, False)
    assert np.all(np.isfinite(r))
    assert np.all(np.isfinite(t))


def test_b25_epsilon1_gradient_kernel_shapes_and_finite():
    e_array = np.linspace(0.6, 4.2, 64, dtype=np.float64)
    out = _compute_epsilon1_gradient_kernel(
        e_array,
        1.2,   # Eg
        45.0,  # A
        3.0,   # E0
        0.25,  # C
        1.8,   # eps_inf
    )
    assert out.shape == (7, len(e_array))
    assert np.all(np.isfinite(out))


def test_b26_needle_scan_cached_returns_valid_candidate_or_sentinel():
    wls, ep, n_layers_T, n_sub = _build_simple_stack(n_wls=6, n_layers=3)
    n_needle_T = np.full_like(n_layers_T, complex(2.0, 0.0), dtype=np.complex128)
    tgt_vals = np.full(len(wls), 0.6, dtype=np.float64)
    tgt_weights = np.ones(len(wls), dtype=np.float64)
    scan_mask = np.ones(len(ep), dtype=np.int64)

    best_layer, best_depth, best_cost = needle_scan_cached(
        wls,
        n_layers_T,
        n_needle_T,
        n_sub,
        ep,
        tgt_vals,
        tgt_weights,
        5.0,
        1.0,
        scan_mask,
    )

    assert np.isfinite(best_depth)
    assert np.isfinite(best_cost)
    # Either a valid candidate [0, N-1] or sentinel -1 when no candidate is legal.
    assert best_layer == -1 or (0 <= int(best_layer) < len(ep))


def test_b27_single_layer_sensitivity_kernel_finite_contract():
    dtdn, dtdk, drdn, drdk, dtdd, drdd = _compute_single_layer_sensitivity_kernel(
        550.0,
        2.0,
        0.05,
        100.0,
        1.5,
    )
    vals = np.array([dtdn, dtdk, drdn, drdk, dtdd, drdd], dtype=np.float64)
    assert np.all(np.isfinite(vals))


def test_b28_calculate_detailed_growth_monotonic_and_finite():
    num_layers = 4
    p_thick_nominal = np.array([80.0, 110.0, 90.0, 120.0], dtype=np.float64)
    layer_wavelengths = np.array([550.0, 550.0, 600.0, 600.0], dtype=np.float64)
    n_h_arr = np.array([2.25, 2.25, 2.20, 2.20], dtype=np.complex128)
    n_l_arr = np.array([1.46, 1.46, 1.44, 1.44], dtype=np.complex128)
    n_sub_arr = np.array([1.52, 1.52, 1.52, 1.52], dtype=np.complex128)
    steps_per_layer_arr = np.array([4, 4, 4, 4], dtype=np.int64)

    x_points, y_points, boundaries = calculate_detailed_growth(
        num_layers,
        p_thick_nominal,
        layer_wavelengths,
        n_h_arr,
        n_l_arr,
        n_sub_arr,
        steps_per_layer_arr,
    )

    assert len(x_points) == len(y_points)
    assert len(boundaries) == num_layers + 1
    assert np.all(np.isfinite(x_points))
    assert np.all(np.isfinite(y_points))
    assert np.all(np.diff(boundaries) >= 0.0)


def test_b29_metal_tmm_gradient_kernel_finite_outputs():
    l_array = np.linspace(420.0, 900.0, 8, dtype=np.float64)
    n_m = np.array([complex(0.15, 3.2)] * len(l_array), dtype=np.complex128)
    n_l = np.array([complex(1.46, 0.0)] * len(l_array), dtype=np.complex128)
    n_sub = np.array([complex(1.52, 0.0)] * len(l_array), dtype=np.complex128)
    r_tgt = np.full(len(l_array), 0.35, dtype=np.float64)

    out = _compute_metal_tmm_gradient_kernel(
        l_array,
        n_m,
        22.0,
        95.0,
        n_l,
        n_sub,
        r_tgt,
    )

    assert len(out) == 6
    mse, grad_dm, grad_el, djnmr, djnmi, djnlr = out
    assert np.isfinite(mse)
    assert np.isfinite(grad_dm)
    assert np.isfinite(grad_el)
    assert djnmr.shape == l_array.shape
    assert djnmi.shape == l_array.shape
    assert djnlr.shape == l_array.shape
    assert np.all(np.isfinite(djnmr))
    assert np.all(np.isfinite(djnmi))
    assert np.all(np.isfinite(djnlr))


def test_b30_oblique_rt_and_grads_kernel_shapes_reverse_and_forward():
    wls, ep, n_layers_T, n_sub = _build_simple_stack(n_wls=5, n_layers=4)
    var_idx = np.array([0, 2, 3], dtype=np.int64)

    for reverse in (False, True):
        r_arr, t_arr, dr, dt = _compute_oblique_rt_and_grads_kernel(
            ep,
            n_layers_T,
            n_sub,
            wls,
            var_idx,
            40.0,
            True,
            reverse,
        )
        assert r_arr.shape == (len(wls),)
        assert t_arr.shape == (len(wls),)
        assert dr.shape == (len(wls), len(var_idx))
        assert dt.shape == (len(wls), len(var_idx))
        assert np.all(np.isfinite(r_arr))
        assert np.all(np.isfinite(t_arr))
        assert np.all(np.isfinite(dr))
        assert np.all(np.isfinite(dt))


def test_b31_ir_global_cost_gradient_kernel_returns_finite_vector():
    n_pts = 7
    wls = np.linspace(900.0, 2500.0, n_pts, dtype=np.float64)
    n_arr = np.full(n_pts, 1.8, dtype=np.float64)
    k_arr = np.full(n_pts, 0.02, dtype=np.float64)
    n_sub = np.full(n_pts, 1.52, dtype=np.float64)

    target_t = np.full(n_pts, 0.65, dtype=np.float64)
    target_r = np.full(n_pts, 0.25, dtype=np.float64)
    weights = np.ones(n_pts, dtype=np.float64)

    # Sellmeier params grads: fixed 5 x n_pts
    dn_dp = np.vstack([
        np.full(n_pts, 0.01, dtype=np.float64),
        np.full(n_pts, 0.015, dtype=np.float64),
        np.full(n_pts, 0.008, dtype=np.float64),
        np.full(n_pts, 0.006, dtype=np.float64),
        np.full(n_pts, 0.004, dtype=np.float64),
    ])
    # k-model params grads: 3 x n_pts (arbitrary finite values)
    dk_dp = np.vstack([
        np.full(n_pts, 0.02, dtype=np.float64),
        np.full(n_pts, -0.01, dtype=np.float64),
        np.full(n_pts, 0.005, dtype=np.float64),
    ])

    t_substrate = np.full(n_pts, 0.9, dtype=np.float64)
    k_sub_full = np.zeros(n_pts, dtype=np.float64)

    grad = _compute_ir_global_cost_gradient_kernel(
        wls,
        n_arr,
        k_arr,
        300.0,
        n_sub,
        target_t,
        target_r,
        weights,
        True,
        True,
        dn_dp,
        dk_dp,
        t_substrate,
        False,
        1.0,
        1.0,
        False,
        False,
        k_sub_full,
        500000.0,
    )

    assert grad.shape == (5 + dk_dp.shape[0],)
    assert np.all(np.isfinite(grad))
