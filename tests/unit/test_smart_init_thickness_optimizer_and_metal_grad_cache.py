"""Regression tests for M6 (smart-init thickness optimization moved out of UI) and m6 (cached spline basis)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from certus.metal.certus_metal_single_physics import gradient_function_fixed_eM, objective_function_fixed_eM


@pytest.mark.unit
def test_smart_init_ui_mixin_does_not_import_scipy_optimize() -> None:
    mixin_path = Path(__file__).resolve().parents[2] / "certus" / "ui" / "certus_index_spline_smartinit_mixin.py"
    source = mixin_path.read_text(encoding="utf-8")
    assert "scipy.optimize" not in source
    assert "optimize_smart_init_thickness" in source


@pytest.mark.unit
def test_optimize_smart_init_thickness_exists_in_spline_smart_init() -> None:
    from certus.spline.spline_smart_init import optimize_smart_init_thickness

    assert callable(optimize_smart_init_thickness)


@pytest.mark.unit
def test_gradient_function_fixed_em_caches_basis_and_matches_fd() -> None:
    from certus.metal.certus_metal_single_physics import _natural_spline_basis_cached

    _natural_spline_basis_cached.cache_clear()
    l_array = np.linspace(450.0, 750.0, 15, dtype=np.float64)
    n_sub = np.full_like(l_array, 1.52 + 0j, dtype=np.complex128)
    num_knots = 4
    lambda_fixed = np.array([550.0, 650.0], dtype=np.float64)
    r_tgt = np.full_like(l_array, 0.45)
    precomputed = {
        "min_lambda": float(l_array[0]),
        "max_lambda": float(l_array[-1]),
        "nSub_complex_array": n_sub,
    }
    x1 = np.array([0.25, 0.22, 0.20, 0.18, 2.4, 2.8, 3.2, 3.6], dtype=np.float64)
    x2 = x1 + 0.03

    grad1 = gradient_function_fixed_eM(x1, 25.0, num_knots, l_array, r_tgt, 10.0, precomputed, lambda_fixed)
    _ = gradient_function_fixed_eM(x2, 25.0, num_knots, l_array, r_tgt, 10.0, precomputed, lambda_fixed)
    info = _natural_spline_basis_cached.cache_info()
    assert info.hits >= 1
    assert info.misses >= 1

    eps = 1e-6
    fd = np.zeros_like(x1)
    for idx in range(len(x1)):
        up = x1.copy()
        dn = x1.copy()
        up[idx] += eps
        dn[idx] -= eps
        c_up = objective_function_fixed_eM(up, 25.0, num_knots, l_array, r_tgt, 10.0, precomputed, lambda_fixed)
        c_dn = objective_function_fixed_eM(dn, 25.0, num_knots, l_array, r_tgt, 10.0, precomputed, lambda_fixed)
        fd[idx] = (c_up - c_dn) / (2.0 * eps)

    assert np.allclose(grad1, fd, rtol=1e-4, atol=1e-6)
