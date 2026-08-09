"""Kernel-level benchmarks for physics hot paths (#38).

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠ OPTIONAL DEPENDENCY: pytest-benchmark

   Ces tests utilisent la fixture  benchmark  fournie par  pytest-benchmark.
   This package is NOT in the base CI dependencies.

   Le  pytest.importorskip  ci-dessous assure un skip gracieux (pas un ERROR)
   quand pytest-benchmark est absent.  NE PAS le supprimer.

   Installation for local execution:
       pip install pytest-benchmark
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import numpy as np
import pytest

# FIREWALL: graceful skip if pytest-benchmark is not installed.
pytest.importorskip("pytest_benchmark")

from certus.core._certus_physics_impl import (
    calculate_RT_no_backside,
    calculate_bare_substrate_RT,
    calculate_reflection_array,
    calculate_transmission_array,
    calculate_RT_single_layer_single,
)


def _sample_inputs(n_pts: int = 1024) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    wavelengths = np.linspace(320.0, 2200.0, n_pts, dtype=np.float64)
    n_film = np.full(n_pts, 2.05, dtype=np.float64)
    k_film = np.full(n_pts, 0.018, dtype=np.float64)
    n_sub_real = np.full(n_pts, 1.52, dtype=np.float64)
    n_sub_complex = n_sub_real.astype(np.complex128)
    n_layers_all_wls = np.ascontiguousarray(
        np.column_stack(
            (
                np.full(n_pts, 2.35 - 0.020j, dtype=np.complex128),
                np.full(n_pts, 1.46 - 0.000j, dtype=np.complex128),
                np.full(n_pts, 2.10 - 0.015j, dtype=np.complex128),
            )
        )
    )
    return wavelengths, n_film, k_film, n_sub_real, n_sub_complex, n_layers_all_wls


@pytest.mark.performance
def test_bench_calculate_t_substrate_array(benchmark) -> None:
    wavelengths, _n_film, _k_film, n_sub_real, _n_sub_complex, _layers = _sample_inputs()
    calculate_bare_substrate_RT(wavelengths, n_sub_real)  # JIT warmup
    out = benchmark(calculate_bare_substrate_RT, wavelengths, n_sub_real)
    assert out.shape == wavelengths.shape


@pytest.mark.performance
def test_bench_calculate_reflection_array(benchmark) -> None:
    wavelengths, n_film, k_film, n_sub_real, _n_sub_complex, _layers = _sample_inputs()
    calculate_reflection_array(wavelengths, n_film, k_film, 120.0, n_sub_real)  # JIT warmup
    out = benchmark(calculate_reflection_array, wavelengths, n_film, k_film, 120.0, n_sub_real)
    assert out.shape == wavelengths.shape


@pytest.mark.performance
def test_bench_calculate_transmission_array(benchmark) -> None:
    wavelengths, n_film, k_film, n_sub_real, _n_sub_complex, _layers = _sample_inputs()
    calculate_transmission_array(wavelengths, n_film, k_film, 120.0, n_sub_real)  # JIT warmup
    out = benchmark(calculate_transmission_array, wavelengths, n_film, k_film, 120.0, n_sub_real)
    assert out.shape == wavelengths.shape


@pytest.mark.performance
def test_bench_calculate_rt_single_layer_single(benchmark) -> None:
    # calculate_RT_single_layer_single has Numba signature n_sub: float64.
    # Do NOT pass complex here (TypingError). Use calculate_transmission_single for complex n_sub.
    n_sub = 1.52  # float64
    calculate_RT_single_layer_single(550.0, 2.05, 0.018, 120.0, n_sub)  # JIT warmup
    r_val = benchmark(calculate_RT_single_layer_single, 550.0, 2.05, 0.018, 120.0, n_sub)
    assert np.isfinite(r_val)


@pytest.mark.performance
def test_bench_calculate_rt_no_backside(benchmark) -> None:
    wavelengths, _n_film, _k_film, _n_sub_real, n_sub_complex, n_layers_all_wls = _sample_inputs()
    thicknesses = np.asarray([85.0, 112.0, 95.0], dtype=np.float64)
    calculate_RT_no_backside(thicknesses, n_layers_all_wls, n_sub_complex, wavelengths)  # JIT warmup
    r_arr, t_arr = benchmark(
        calculate_RT_no_backside,
        thicknesses,
        n_layers_all_wls,
        n_sub_complex,
        wavelengths,
    )
    assert r_arr.shape == wavelengths.shape
    assert t_arr.shape == wavelengths.shape
