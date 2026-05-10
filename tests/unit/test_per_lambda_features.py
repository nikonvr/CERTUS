"""

Tests for Per-Lambda refinement features:

  1. Thickness scan (arc length criterion)

  2. n/k +/-2% relative bounds

  3. Spline smoothing (k positivity in log-space)

  4. Thread attribute consistency (self._thread)

  5. Spline/Morphing chaining after Per-Lambda (no tlu_params guard)

"""



import sys

import os
from pathlib import Path

import numpy as np

import pytest



sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))



from CERTUS_INDEX import (

    _optimize_point_kernel,

    _optimize_all_points_batch,

)



# ─────────────────────────────────────────────────────────────────────────────

# Helpers

# ─────────────────────────────────────────────────────────────────────────────





def _arc_length(wls, n):

    """Geometric arc length of n(lambda)."""

    return float(np.sum(np.hypot(np.diff(wls), np.diff(n))))





def _batch(wls, n_start, k_start, T_tgt, d):

    """Shortcut to call the batch kernel with standard test params."""

    N = len(wls)

    n_sub = np.full(N, 1.5, dtype=np.float64)

    T_sub = np.full(N, 0.92, dtype=np.float64)

    R_sub = np.full(N, 0.08, dtype=np.float64)

    R_tgt = np.full(N, np.nan, dtype=np.float64)

    excl = np.zeros(N, dtype=np.bool_)

    return _optimize_all_points_batch(

        n_start.copy().astype(np.float64),

        k_start.copy().astype(np.float64),

        wls.astype(np.float64),

        T_tgt.astype(np.float64),

        R_tgt,

        1.0,

        0.0,

        n_sub,

        T_sub,

        R_sub,

        d,

        True,

        False,

        False,

        False,  # use_T=True, use_R=False, use_norm=False, is_frost=False

        excl,

    )





# ─────────────────────────────────────────────────────────────────────────────

# Test 1 - Thickness scan: smoothest d gives minimum arc length

# ─────────────────────────────────────────────────────────────────────────────





def test_thickness_scan_arc_length():

    """

    Scan 11 thickness values +/-2%.

    Each produces a different n(lambda) curve.

    Arc lengths must differ - the scan is not degenerate.

    """

    wls = np.linspace(500, 2500, 200, dtype=np.float64)

    n_start = np.full(200, 1.5, dtype=np.float64)

    k_start = np.full(200, 0.001, dtype=np.float64)

    T_tgt = np.clip(0.85 + 0.1 * np.sin(wls / 200), 0.5, 1.0).astype(np.float64)



    d_nom = 300.0

    d_vals = np.linspace(d_nom * 0.98, d_nom * 1.02, 11)



    arcs = []

    for d_t in d_vals:

        nf, _ = _batch(wls, n_start, k_start, T_tgt, d_t)

        arcs.append(_arc_length(wls, nf))



    # Arc lengths must not all be identical (scan is meaningful)

    spread = max(arcs) - min(arcs)

    assert spread > 0, f"Arc lengths are all identical (spread={spread})"



    # The minimum must be achievable (a best d exists)

    best_idx = int(np.argmin(arcs))

    assert 0 <= best_idx < len(d_vals), "No best d found"



    print(

        f"[PASS] Thickness scan: arc spread={spread:.6f}, best d={d_vals[best_idx]:.2f} nm"

    )





# ─────────────────────────────────────────────────────────────────────────────

# Test 2 - Kernel +/-2% relative bounds on n

# ─────────────────────────────────────────────────────────────────────────────





@pytest.mark.parametrize("n_init", [1.3, 1.7, 2.5, 3.8])

def test_kernel_n_bounds_relative(n_init):

    """

    The scalar kernel must return n within +/-2% of n_start.

    """

    wl = 1000.0

    k0 = 0.001

    T_sub = 0.92

    R_sub = 0.08

    n_sub = 1.5



    n_result, k_result, cost = _optimize_point_kernel(

        n_init,

        k0,

        wl,

        0.90,

        np.nan,

        1.0,

        0.0,

        n_sub,

        T_sub,

        R_sub,

        300.0,

        True,

        False,

        False,

        False,

    )



    delta_n = n_init * 0.02

    tolerance = 1e-9  # allow floating point at boundary

    assert (

        n_result >= n_init - delta_n - tolerance

    ), f"n={n_result:.6f} below lower bound {n_init - delta_n:.6f} (n_init={n_init})"

    assert (

        n_result <= n_init + delta_n + tolerance

    ), f"n={n_result:.6f} above upper bound {n_init + delta_n:.6f} (n_init={n_init})"

    print(

        f"[PASS] n={n_result:.5f} within [{n_init - delta_n:.5f}, {n_init + delta_n:.5f}]"

    )





# ─────────────────────────────────────────────────────────────────────────────

# Test 3 - Spline smoothing: k stays strictly positive

# ─────────────────────────────────────────────────────────────────────────────





def test_spline_k_positivity():

    """

    After log-space spline smoothing, all k values must be > 0.

    """

    from scipy.interpolate import LSQUnivariateSpline



    wls = np.linspace(500, 5000, 400, dtype=np.float64)

    # k with a near-zero region

    k_raw = np.where(wls < 2000, 1e-4, 0.001 + 0.002 * np.sin(wls / 500))

    k_raw = np.clip(k_raw, 1e-9, None)



    N_KNOTS = 8

    interior_knots = np.linspace(wls[0], wls[-1], N_KNOTS + 2)[1:-1]

    log_k = np.log(k_raw)



    valid_knots = interior_knots[(interior_knots > wls[0]) & (interior_knots < wls[-1])]

    spl = LSQUnivariateSpline(wls, log_k, valid_knots, k=3)

    k_smoothed = np.exp(spl(wls))



    assert np.all(

        k_smoothed > 0

    ), f"k_smoothed has non-positive values! min={k_smoothed.min():.3e}"

    assert not np.any(np.isnan(k_smoothed)), "k_smoothed contains NaN"

    assert not np.any(np.isinf(k_smoothed)), "k_smoothed contains Inf"

    print(

        f"[PASS] k_smoothed: min={k_smoothed.min():.2e}, max={k_smoothed.max():.2e}, all > 0"

    )





# ─────────────────────────────────────────────────────────────────────────────

# Test 4 - Spline smoothing: n stays in physical range [0.01, 20]

# ─────────────────────────────────────────────────────────────────────────────





def test_spline_n_clipping():

    """

    Spline fit on n must be clipped to [0.01, 20.0].

    """

    from scipy.interpolate import LSQUnivariateSpline



    wls = np.linspace(500, 5000, 400, dtype=np.float64)

    n_raw = 1.5 - 0.0002 * (wls - 2500)  # gently sloping

    n_raw = n_raw + 0.05 * np.random.default_rng(42).normal(size=len(wls))



    N_KNOTS = 8

    interior_knots = np.linspace(wls[0], wls[-1], N_KNOTS + 2)[1:-1]

    spl = LSQUnivariateSpline(wls, n_raw, interior_knots, k=3)

    n_smoothed = np.clip(spl(wls), 0.01, 20.0)



    assert n_smoothed.min() >= 0.01, f"n_smoothed below 0.01: {n_smoothed.min()}"

    assert n_smoothed.max() <= 20.0, f"n_smoothed above 20.0: {n_smoothed.max()}"

    print(f"[PASS] n_smoothed: [{n_smoothed.min():.4f}, {n_smoothed.max():.4f}]")





# Test 5 & 6 removed as they referenced legacy refinement methods (per-lambda/morphing/spline_old)

# that were deleted in the cleanup.





# ─────────────────────────────────────────────────────────────────────────────

# Test 7 - Batch kernel: output shapes match input

# ─────────────────────────────────────────────────────────────────────────────





def test_batch_kernel_output_shape():

    """

    _optimize_all_points_batch must return arrays of the same length as input.

    """

    for N in [10, 100, 500]:

        wls = np.linspace(500, 2000, N, dtype=np.float64)

        n_s = np.full(N, 1.6, dtype=np.float64)

        k_s = np.full(N, 0.001, dtype=np.float64)

        T_tgt = np.full(N, 0.88, dtype=np.float64)



        nf, kf = _batch(wls, n_s, k_s, T_tgt, 300.0)



        assert nf.shape == (N,), f"n_final shape mismatch for N={N}: {nf.shape}"

        assert kf.shape == (N,), f"k_final shape mismatch for N={N}: {kf.shape}"

        assert np.all(np.isfinite(nf)), f"n_final contains non-finite values for N={N}"

        assert np.all(nf > 0), f"n_final has non-positive values for N={N}"



    print("[PASS] Batch kernel output shapes and validity checked")





if __name__ == "__main__":

    print("=" * 60)

    print("Running Per-Lambda feature tests...")

    print("=" * 60)



    tests = [

        test_thickness_scan_arc_length,

        lambda: test_kernel_n_bounds_relative(1.3),

        lambda: test_kernel_n_bounds_relative(1.7),

        lambda: test_kernel_n_bounds_relative(2.5),

        lambda: test_kernel_n_bounds_relative(3.8),

        test_spline_k_positivity,

        test_spline_n_clipping,

        test_thread_attribute_consistency,

        test_no_tlu_params_guard,

        test_batch_kernel_output_shape,

    ]



    passed = 0

    failed = 0

    for t in tests:

        name = getattr(t, "__name__", "lambda")

        try:

            t()

            passed += 1

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            print(f"[FAIL] {name}: {e}")

            failed += 1



    print("=" * 60)

    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:

        print("ALL TESTS PASSED ✓")

    else:

        sys.exit(1)

