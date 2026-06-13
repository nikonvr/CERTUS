"""Unit tests for the new non-regressive METAL optimizations."""

from __future__ import annotations

import numpy as np
import pytest
from certus.core._certus_physics_impl import compute_metal_bilayer_gradient_analytic, SplineBasisCache
from certus.core.certus_core import canonicalize_substrate_label, substrate_sellmeier_id
from CERTUS_METAL_SINGLE import objective_function_fixed_eM, gradient_function_fixed_eM, _resolve_single_substrate_id


@pytest.mark.unit
def test_compute_metal_bilayer_gradient_analytic_non_regression() -> None:
    # Setup parameters
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)
    
    # x = [eM, eL, n_infini, A, n_knots (5), k_knots (5), lambda_internes (3)]
    # lambda_internes must be inside (400, 800) and sorted
    x = np.concatenate((
        [50.0, 100.0, 1.43, 100.0],
        [1.5, 1.6, 1.7, 1.8, 1.9],  # n_knots
        [0.1, 0.2, 0.3, 0.4, 0.5],  # k_knots
        [500.0, 600.0, 700.0]       # lambda_internes
    ))
    
    # Warm up / Clear cache
    SplineBasisCache.clear()
    
    # Run
    cost1, grad1 = compute_metal_bilayer_gradient_analytic(
        x, num_knots, l_array, r_tgt_array, min_knot_dist, nSub_complex_array=nSub
    )
    
    # Second run should hit cache
    cost2, grad2 = compute_metal_bilayer_gradient_analytic(
        x, num_knots, l_array, r_tgt_array, min_knot_dist, nSub_complex_array=nSub
    )
    
    assert np.allclose(cost1, cost2)
    assert np.allclose(grad1, grad2)


@pytest.mark.unit
def test_objective_function_fixed_eM_with_and_without_buffer() -> None:
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)
    
    precomputed_without = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
    }
    
    precomputed_with = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
        "x_full_buffer": np.zeros(2 * num_knots + 3, dtype=np.float64)
    }
    
    lambda_internes_fixed = np.array([500.0, 600.0, 700.0])
    precomputed_with["x_full_buffer"][2*num_knots:] = lambda_internes_fixed
    
    # x is [n_knots (5) | k_knots (5)]
    x = np.concatenate(([1.5, 1.6, 1.7, 1.8, 1.9], [0.1, 0.2, 0.3, 0.4, 0.5]))
    
    val_without = objective_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed_without, lambda_internes_fixed
    )
    
    val_with = objective_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed_with, lambda_internes_fixed
    )
    
    assert np.allclose(val_without, val_with)


@pytest.mark.unit
def test_gradient_function_fixed_eM_with_and_without_cache() -> None:
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)
    
    precomputed_without = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
    }
    
    lambda_internes_fixed = np.array([500.0, 600.0, 700.0])
    
    precomputed_with = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "knot_l_scan": np.concatenate(([400.0], np.sort(lambda_internes_fixed), [800.0]))
    }
    
    x = np.concatenate(([1.5, 1.6, 1.7, 1.8, 1.9], [0.1, 0.2, 0.3, 0.4, 0.5]))
    
    grad_without = gradient_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed_without, lambda_internes_fixed
    )
    
    grad_with = gradient_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed_with, lambda_internes_fixed
    )
    
    assert np.allclose(grad_without, grad_with)


@pytest.mark.unit
def test_gradient_and_objective_under_constraint_violation() -> None:
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 100.0  # Big min distance to force spacing violation
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)
    
    precomputed = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
    }
    
    lambda_internes_fixed = np.array([450.0, 460.0, 470.0])  # Spacing is only 10, < 100
    x = np.concatenate(([1.5, 1.6, 1.7, 1.8, 1.9], [0.1, 0.2, 0.3, 0.4, 0.5]))
    
    # Should trigger constraint checks and return fallbacks
    val = objective_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed, lambda_internes_fixed
    )
    assert val == 1e12 or np.isinf(val)
    
    grad = gradient_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed, lambda_internes_fixed
    )
    assert np.all(grad == 0.0)


@pytest.mark.unit
def test_edge_case_no_internal_knots() -> None:
    num_knots = 2  # Only endpoints, 0 internal knots
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)
    
    precomputed = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
    }
    
    lambda_internes_fixed = np.empty(0)
    x = np.array([1.5, 1.9, 0.1, 0.5])  # n_knots (2), k_knots (2)
    
    val = objective_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed, lambda_internes_fixed
    )
    assert np.isfinite(val)
    
    grad = gradient_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed, lambda_internes_fixed
    )
    assert grad.shape == (4,)
    assert np.all(np.isfinite(grad))


@pytest.mark.unit
def test_spline_basis_cache_eviction_and_lock() -> None:
    # Clear and verify cache sizes/eviction limits
    SplineBasisCache.clear()
    assert len(SplineBasisCache._cache) == 0
    
    # Generate 510 unique cache keys to trigger eviction limit (>500)
    l_array = np.linspace(400, 800, 10)
    for i in range(510):
        # vary the knots slightly
        knot_l = np.array([400.0, 500.0 + i * 1e-4, 800.0])
        SplineBasisCache.get(knot_l, l_array)
        
    # The cache should have evicted/cleared itself to avoid memory leaks
    assert len(SplineBasisCache._cache) < 500


# ---------------------------------------------------------------------------
# SplineBasisCache correctness
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_spline_basis_cache_matrix_matches_cubicspline() -> None:
    """B @ knot_vals must equal CubicSpline(knots, vals)(targets)."""
    from scipy.interpolate import CubicSpline

    knot_l = np.array([400.0, 500.0, 600.0, 700.0, 800.0])
    target_l = np.linspace(410.0, 790.0, 25)
    n_knot_vals = np.array([1.2, 1.4, 1.6, 1.5, 1.3])

    B = SplineBasisCache.get(knot_l, target_l)
    result_cache = B @ n_knot_vals

    ref = CubicSpline(knot_l, n_knot_vals, bc_type="natural", extrapolate=True)(target_l)

    assert np.allclose(result_cache, ref, atol=1e-12)


@pytest.mark.unit
def test_spline_basis_cache_idempotent() -> None:
    """Two calls with the same keys must return the same array object (cache hit)."""
    knot_l = np.array([400.0, 550.0, 800.0])
    target_l = np.linspace(400.0, 800.0, 20)

    SplineBasisCache.clear()
    B1 = SplineBasisCache.get(knot_l, target_l)
    B2 = SplineBasisCache.get(knot_l, target_l)

    assert B1 is B2  # exact same object in memory = cache hit


@pytest.mark.unit
def test_spline_basis_cache_returns_correct_shape() -> None:
    num_knots = 6
    n_targets = 40
    knot_l = np.linspace(400.0, 800.0, num_knots)
    target_l = np.linspace(400.0, 800.0, n_targets)

    B = SplineBasisCache.get(knot_l, target_l)
    assert B.shape == (n_targets, num_knots)


@pytest.mark.unit
def test_metal_single_substrate_resolution_supports_sapphire_aliases() -> None:
    assert canonicalize_substrate_label("Sapphire") == "Sapphire (Al2O3)"
    assert substrate_sellmeier_id("Sapphire") == 3
    assert _resolve_single_substrate_id("Sapphire") == 3
    assert _resolve_single_substrate_id("Fused Silica") == 0


# ---------------------------------------------------------------------------
# Non-finite x guards
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_objective_function_fixed_eM_returns_inf_for_non_finite_x() -> None:
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)

    precomputed = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
    }

    x_nan = np.full(2 * num_knots, np.nan)
    val = objective_function_fixed_eM(
        x_nan, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist, precomputed
    )
    assert np.isinf(val)

    x_inf = np.full(2 * num_knots, np.inf)
    val2 = objective_function_fixed_eM(
        x_inf, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist, precomputed
    )
    assert np.isinf(val2)


@pytest.mark.unit
def test_gradient_function_fixed_eM_returns_zeros_for_non_finite_x() -> None:
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)

    precomputed = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
    }

    x_nan = np.full(2 * num_knots, np.nan)
    grad = gradient_function_fixed_eM(
        x_nan, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist, precomputed
    )
    assert np.all(grad == 0.0)
    assert grad.shape == (2 * num_knots,)


# ---------------------------------------------------------------------------
# Finite-difference gradient check on bilayer analytic gradient
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bilayer_analytic_gradient_agrees_with_finite_differences() -> None:
    """Analytic gradient must match finite-difference approximation on eM and eL."""
    num_knots = 3
    l_array = np.linspace(400, 800, 20)
    r_tgt_array = np.ones(20) * 0.4
    min_knot_dist = 10.0
    nSub = np.ones(20, dtype=np.complex128) * (1.5 + 0j)

    # x = [eM, eL, n_infini, A, n_knots(3), k_knots(3), lambda_internes(1)]
    x0 = np.concatenate((
        [50.0, 100.0, 1.43, 50.0],
        [1.5, 1.6, 1.7],
        [0.2, 0.3, 0.4],
        [600.0]
    ))

    cost0, grad_analytic = compute_metal_bilayer_gradient_analytic(
        x0, num_knots, l_array, r_tgt_array, min_knot_dist, nSub_complex_array=nSub
    )

    h = 1e-5
    # Only check first 4 scalar parameters (eM, eL, n_infini, A)
    for i in range(4):
        x_p = x0.copy()
        x_p[i] += h
        cost_p, _ = compute_metal_bilayer_gradient_analytic(
            x_p, num_knots, l_array, r_tgt_array, min_knot_dist, nSub_complex_array=nSub
        )
        fd = (cost_p - cost0) / h
        assert abs(grad_analytic[i] - fd) < 1e-3 * (1.0 + abs(fd)), (
            f"Gradient mismatch at index {i}: analytic={grad_analytic[i]:.6e}, fd={fd:.6e}"
        )


# ---------------------------------------------------------------------------
# x_full_buffer content correctness
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_x_full_buffer_written_correctly() -> None:
    """The x_full_buffer in precomputed must contain lambda_internes in its tail."""
    num_knots = 5
    l_array = np.linspace(400, 800, 30)
    r_tgt_array = np.ones(30) * 0.5
    min_knot_dist = 10.0
    nSub = np.ones(30, dtype=np.complex128) * (1.5 + 0j)

    lambda_internes_fixed = np.array([500.0, 600.0, 700.0])
    x_full_buffer = np.zeros(2 * num_knots + len(lambda_internes_fixed), dtype=np.float64)
    x_full_buffer[2 * num_knots:] = lambda_internes_fixed

    precomputed = {
        "min_lambda": 400.0,
        "max_lambda": 800.0,
        "nSub_complex_array": nSub,
        "eM_buffer": np.empty(1, dtype=np.float64),
        "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
        "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
        "x_full_buffer": x_full_buffer,
    }

    x = np.array([1.5, 1.6, 1.7, 1.8, 1.9, 0.1, 0.2, 0.3, 0.4, 0.5])
    objective_function_fixed_eM(
        x, 50.0, num_knots, l_array, r_tgt_array, min_knot_dist,
        precomputed, lambda_internes_fixed
    )

    # After call, the first 2*num_knots elements of buffer must equal x
    assert np.allclose(x_full_buffer[:2 * num_knots], x)
    # And the tail must still hold lambda_internes
    assert np.allclose(x_full_buffer[2 * num_knots:], lambda_internes_fixed)
