"""Minimal benchmarks for the 5 hottest physics kernels — action M2 of CERTUS_MINIMAL_PLAN.md.

Scope:
- One benchmark per kernel listed in M2:
    1. calculate_RT_batch_kernel        (Monte-Carlo MC batch, parallel @njit)
    2. calculate_RT_vectorized_real_HL  (vectorized HL spectral calc, surface wrapper)
    3. precompute_matrix_cache_kernel   (cumulative TMM cache, parallel @njit)
    4. compute_dynamics_kernel          (T(d) range over growth, parallel @njit)
    5. simulate_growth_kernel           (per-wavelength fast TMM growth scoring, @njit)
- Plus one mini-call replicating a small strategy-robustness MC round.

No hard threshold gate: the suite is a "regression visible at PR review" tool.
Run with:
    pytest tests/performance/test_kernel_benchmarks_minimal.py --benchmark-only
Save baseline with:
    pytest tests/performance/test_kernel_benchmarks_minimal.py --benchmark-only --benchmark-save=baseline
Compare against baseline with:
    pytest tests/performance/test_kernel_benchmarks_minimal.py --benchmark-only --benchmark-compare=baseline

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠ OPTIONAL DEPENDENCY: pytest-benchmark (see test_kernel_benchmarks.py)
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import numpy as np
import pytest

# FIREWALL: graceful skip if pytest-benchmark is not installed.
pytest.importorskip("pytest_benchmark")

from certus.core._certus_physics_impl import (
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    compute_dynamics_kernel,
    precompute_matrix_cache_kernel,
    simulate_growth_kernel,
)

# Realistic problem sizes for an optical-monitor pass.
N_WLS = 401          # 320 - 720 nm at 1 nm step.
NUM_LAYERS = 21      # Typical mid-size HL stack.
N_RUNS = 32          # MC batch size (robustness sample).
N_STEPS = 64         # Growth steps for compute_dynamics_kernel.


def _wls() -> np.ndarray:
    return np.linspace(320.0, 720.0, N_WLS, dtype=np.float64)


def _nH(wls: np.ndarray) -> np.ndarray:
    return np.full(wls.shape, 2.35 - 0.020j, dtype=np.complex128)


def _nL(wls: np.ndarray) -> np.ndarray:
    return np.full(wls.shape, 1.46 + 0.0j, dtype=np.complex128)


def _nSub(wls: np.ndarray) -> np.ndarray:
    return np.full(wls.shape, 1.52 + 0.0j, dtype=np.complex128)


def _thicknesses() -> np.ndarray:
    return np.linspace(80.0, 140.0, NUM_LAYERS, dtype=np.float64)


@pytest.mark.performance
def test_bench_calculate_RT_batch_kernel(benchmark) -> None:
    wls = _wls()
    nH, nL, nSub = _nH(wls), _nL(wls), _nSub(wls)
    nominal = _thicknesses()
    rng = np.random.default_rng(42)
    batch = nominal[None, :] * (1.0 + 0.05 * rng.standard_normal((N_RUNS, NUM_LAYERS)))
    batch = np.ascontiguousarray(batch.astype(np.float64))

    # JIT warmup on a 1-row batch.
    calculate_RT_batch_kernel(wls, nH, nL, nSub, batch[:1])
    R, T = benchmark(calculate_RT_batch_kernel, wls, nH, nL, nSub, batch)
    assert R.shape == (N_RUNS, N_WLS)
    assert T.shape == (N_RUNS, N_WLS)
    assert np.all(np.isfinite(R))
    assert np.all(np.isfinite(T))


@pytest.mark.performance
def test_bench_calculate_RT_vectorized_real_HL(benchmark) -> None:
    wls = _wls()
    nH, nL, nSub = _nH(wls), _nL(wls), _nSub(wls)
    thicknesses = _thicknesses()

    # Warmup.
    calculate_RT_vectorized_real_HL(wls, nH, nL, nSub, thicknesses)
    R, T = benchmark(calculate_RT_vectorized_real_HL, wls, nH, nL, nSub, thicknesses)
    assert R.shape == wls.shape
    assert T.shape == wls.shape


@pytest.mark.performance
def test_bench_precompute_matrix_cache_kernel(benchmark) -> None:
    wls = _wls()
    nH, nL = _nH(wls), _nL(wls)
    thicknesses = _thicknesses()

    # Warmup.
    precompute_matrix_cache_kernel(wls, nH, nL, thicknesses, NUM_LAYERS)
    cache = benchmark(precompute_matrix_cache_kernel, wls, nH, nL, thicknesses, NUM_LAYERS)
    assert cache.shape == (NUM_LAYERS, N_WLS, 2, 2)


@pytest.mark.performance
def test_bench_compute_dynamics_kernel(benchmark) -> None:
    wls = _wls()
    n_layer_per_wl = _nH(wls)            # The layer currently being grown (H here).
    n_sub_per_wl = _nSub(wls)            # Substrate, per wavelength.
    thickness_steps = np.linspace(0.0, 100.0, N_STEPS, dtype=np.float64)

    # M_befores is the cumulative pre-layer matrix per wavelength, shape (n_wls, 2, 2).
    # Use identity for the benchmark to exercise the kernel without depending on cache content.
    eye = np.zeros((N_WLS, 2, 2), dtype=np.complex128)
    eye[:, 0, 0] = 1.0
    eye[:, 1, 1] = 1.0

    # Warmup.
    compute_dynamics_kernel(wls, n_layer_per_wl, n_sub_per_wl, thickness_steps, eye)
    out = benchmark(
        compute_dynamics_kernel,
        wls, n_layer_per_wl, n_sub_per_wl, thickness_steps, eye,
    )
    # Kernel returns (dynamics, t_init, t_final, t_min) — all 1D of size n_wls.
    dynamics, t_init, t_final, t_min = out
    assert dynamics.shape == wls.shape
    assert t_init.shape == wls.shape
    assert t_final.shape == wls.shape
    assert t_min.shape == wls.shape


@pytest.mark.performance
def test_bench_simulate_growth_kernel(benchmark) -> None:
    p_thick_nominal = _thicknesses()
    prev_thick = np.zeros(NUM_LAYERS, dtype=np.float64)

    # All scalar wl + complex indices — Numba dispatches a single specialization.
    args = (
        p_thick_nominal,
        0,                     # i_layer
        prev_thick,
        550.0,                 # wl
        complex(2.35, -0.020), # n_H
        complex(1.46, 0.0),    # n_L
        complex(1.52, 0.0),    # n_Sub
        0.0,                   # probe_offset
        0.0,                   # noise_val_precalc
        1.0,                   # non_monotonic_factor
        0,                     # non_monotonic_mode (ATTENUATE)
    )
    # Warmup.
    simulate_growth_kernel(*args)
    out = benchmark(simulate_growth_kernel, *args)
    # Kernel returns (float, float).
    assert len(out) == 2
    assert np.isfinite(out[0])
    assert np.isfinite(out[1])


@pytest.mark.performance
def test_bench_strategy_robustness_minicall(benchmark) -> None:
    """Mini-call replicating one robustness MC round on a 21-layer stack with 8 noise draws."""
    wls = _wls()
    nH, nL, nSub = _nH(wls), _nL(wls), _nSub(wls)
    nominal = _thicknesses()
    rng = np.random.default_rng(0)
    n_mc = 8
    batch = nominal[None, :] * (1.0 + 0.02 * rng.standard_normal((n_mc, NUM_LAYERS)))
    batch = np.ascontiguousarray(batch.astype(np.float64))
    target_T = np.full(N_WLS, 0.5, dtype=np.float64)

    # Warmup.
    calculate_RT_batch_kernel(wls, nH, nL, nSub, batch[:1])

    def _one_mc_round() -> float:
        _R, T = calculate_RT_batch_kernel(wls, nH, nL, nSub, batch)
        rmse_per_run = np.sqrt(np.mean((T - target_T[None, :]) ** 2, axis=1))
        return float(rmse_per_run.mean())

    out = benchmark(_one_mc_round)
    assert np.isfinite(out)
