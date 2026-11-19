"""Regression tests for M4 (TMM overflow on thick opaque layers) and m1 (frosted-glass int dtype)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_opt_tmm import (
    calculate_reflectance_bilayer_vectorized,
    compute_TMM_generic,
    get_n_frosted_glass_array,
)
from certus.physics.certus_tmm_matrix import compute_TMM_single_point_k0


def _bulk_fresnel_r(n_inc: complex, n_mat: complex) -> float:
    return float(abs((n_inc - n_mat) / (n_inc + n_mat)) ** 2)


def test_tmm_thick_opaque_layer_does_not_overflow() -> None:
    wl = 500.0
    k0 = 2.0 * np.pi / wl
    n_layer = complex(0.2, -4.0)
    # phi_i = k0 * 4.0 * 20000 ~ 1005 > 709.78 (float64 cosh/sinh overflow threshold)
    thicknesses = np.array([20000.0], dtype=np.float64)
    indices = np.array([n_layer], dtype=np.complex128)
    expected_r = _bulk_fresnel_r(1.0 + 0j, n_layer)

    r_gen, t_gen = compute_TMM_generic(k0, thicknesses, indices, 1.0 + 0j, 1.52 + 0j)
    r_k0, t_k0 = compute_TMM_single_point_k0(k0, thicknesses, indices, 1.52 + 0j)

    assert np.isfinite(r_gen)
    assert r_gen == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert t_gen == 0.0
    assert np.isfinite(r_k0)
    assert r_k0 == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert t_k0 == 0.0

    r_bi = calculate_reflectance_bilayer_vectorized(
        np.array([wl], dtype=np.float64),
        np.array([n_layer], dtype=np.complex128),
        20000.0,
        100.0,
        np.array([1.46 + 0j], dtype=np.complex128),
        np.array([1.52 + 0j], dtype=np.complex128),
    )
    assert np.isfinite(r_bi[0])
    assert r_bi[0] == pytest.approx(expected_r, rel=1e-12, abs=1e-12)


def test_tmm_thick_absorbing_slab_preserves_exact_non_zero_transmittance() -> None:
    wl = 500.0
    k0 = 2.0 * np.pi / wl
    d = 18000.0
    n_layer = complex(1.5, -1.0)  # |phi_i| = k0 * 1.0 * 18000 ~ 226.2 > 200, exp(-2*|phi_i|) ~ 1.4e-197 > 0
    n0 = 1.0 + 0j
    ns = 1.52 + 0j
    thicknesses = np.array([d], dtype=np.float64)
    indices = np.array([n_layer], dtype=np.complex128)

    # Single-pass analytical limit (neglecting internal roundtrip ~ exp(-150))
    t01 = 2.0 * n0 / (n0 + n_layer)
    t1s = 2.0 * n_layer / (n_layer + ns)
    expected_t = float((ns.real / n0.real) * abs(t01 * t1s) ** 2 * np.exp(-2.0 * k0 * 1.0 * d))
    expected_r = _bulk_fresnel_r(n0, n_layer)

    r_gen, t_gen = compute_TMM_generic(k0, thicknesses, indices, n0, ns)
    r_k0, t_k0 = compute_TMM_single_point_k0(k0, thicknesses, indices, ns)

    assert r_gen == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert r_k0 == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert t_gen > 0.0
    assert t_gen == pytest.approx(expected_t, rel=1e-10, abs=0.0)
    assert t_k0 > 0.0
    assert t_k0 == pytest.approx(expected_t, rel=1e-10, abs=0.0)


def test_tmm_multilayer_cumulative_absorption_does_not_overflow() -> None:
    wl = 500.0
    k0 = 2.0 * np.pi / wl
    # 32 layers with |phi_i| ~ 25.13 each (per-layer <= 50, cumulative M ~ exp(804) overflows float64 without rescaling)
    thicknesses = np.full(32, 2000.0, dtype=np.float64)
    indices = np.full(32, complex(1.8, -1.0), dtype=np.complex128)
    expected_r = _bulk_fresnel_r(1.0 + 0j, indices[-1])

    r_gen, t_gen = compute_TMM_generic(k0, thicknesses, indices, 1.0 + 0j, 1.52 + 0j)
    r_k0, t_k0 = compute_TMM_single_point_k0(k0, thicknesses, indices, 1.52 + 0j)

    assert np.isfinite(r_gen)
    assert r_gen == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert np.isfinite(t_gen)
    assert t_gen >= 0.0
    assert np.isfinite(r_k0)
    assert r_k0 == pytest.approx(expected_r, rel=1e-12, abs=1e-12)
    assert np.isfinite(t_k0)
    assert t_k0 >= 0.0


def test_get_n_frosted_glass_array_returns_float64_for_integer_wavelengths() -> None:
    wls_int = np.array([400, 500, 600], dtype=np.int64)
    n_int = get_n_frosted_glass_array(wls_int)
    n_float = get_n_frosted_glass_array(wls_int.astype(np.float64))

    assert n_int.dtype == np.float64
    assert np.allclose(n_int, n_float, rtol=1e-12, atol=1e-12)
    assert np.all((n_int > 1.45) & (n_int < 1.65))
