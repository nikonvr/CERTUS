"""Direct TMM smoke tests on `_certus_physics_impl` (P1-12).

Aligned with `tests/test_tmm_coherence.py`:
- TEST 1: single QW — `compute_TMM_generic` vs analytique ; `calculate_RT_single_layer_single` (dos incohérent).
- TEST 2 (HLH) : `compute_TMM_single_point_k0` et `compute_TMM_single_point_k0_exact` (Rf, Tf) vs `compute_TMM_generic`, plusieurs λ.
"""

from __future__ import annotations

import numpy as np
import numpy.testing as npt
import pytest

from _certus_physics_impl import (
    TWO_PI,
    calculate_RT_single_layer_single,
    compute_TMM_generic,
    compute_TMM_single_point_k0,
    compute_TMM_single_point_k0_exact,
)


def test_compute_TMM_generic_quarter_wave_matches_vector_admittance_analytics() -> None:
    n_h = 2.30
    n_sub = 1.52
    l0 = 550.0
    d_qw = l0 / (4.0 * n_h)
    k0 = TWO_PI / l0
    thicknesses = np.array([d_qw], dtype=np.float64)
    n_layers = np.array([complex(n_h)], dtype=np.complex128)

    r_tmm, t_tmm = compute_TMM_generic(
        k0, thicknesses, n_layers, complex(1.0), complex(n_sub)
    )

    y_eff = n_h**2 / n_sub
    r_ana = ((1.0 - y_eff) / (1.0 + y_eff)) ** 2
    t_ana = 1.0 - r_ana

    npt.assert_allclose(r_tmm, r_ana, rtol=0.0, atol=1e-9)
    npt.assert_allclose(t_tmm, t_ana, rtol=0.0, atol=1e-9)


@pytest.mark.parametrize("wl_nm", (400.0, 550.0, 700.0))
def test_compute_TMM_single_point_k0_agrees_with_generic_hlh(wl_nm: float) -> None:
    n_h, n_l, n_sub, l0_design = 2.30, 1.45, 1.52, 550.0
    d_h = l0_design / (4.0 * n_h)
    d_l = l0_design / (4.0 * n_l)
    thicknesses = np.array([d_h, d_l, d_h], dtype=np.float64)
    n_layers = np.array([complex(n_h), complex(n_l), complex(n_h)], dtype=np.complex128)
    k0 = TWO_PI / wl_nm

    r_g, t_g = compute_TMM_generic(
        k0, thicknesses, n_layers, complex(1.0), complex(n_sub)
    )
    r_k, t_k = compute_TMM_single_point_k0(
        k0, thicknesses, n_layers, complex(n_sub)
    )

    npt.assert_allclose(r_k, r_g, rtol=0.0, atol=1e-9)
    npt.assert_allclose(t_k, t_g, rtol=0.0, atol=1e-9)


@pytest.mark.parametrize("wl_nm", (400.0, 550.0, 700.0))
def test_compute_TMM_single_point_k0_exact_front_matches_generic_hlh(wl_nm: float) -> None:
    n_h, n_l, n_sub, l0_design = 2.30, 1.45, 1.52, 550.0
    d_h = l0_design / (4.0 * n_h)
    d_l = l0_design / (4.0 * n_l)
    thicknesses = np.array([d_h, d_l, d_h], dtype=np.float64)
    n_layers = np.array([complex(n_h), complex(n_l), complex(n_h)], dtype=np.complex128)
    k0 = TWO_PI / wl_nm

    r_g, t_g = compute_TMM_generic(
        k0, thicknesses, n_layers, complex(1.0), complex(n_sub)
    )
    r_f, t_f, r_b = compute_TMM_single_point_k0_exact(
        k0, thicknesses, n_layers, complex(n_sub)
    )

    npt.assert_allclose(r_f, r_g, rtol=0.0, atol=1e-9)
    npt.assert_allclose(t_f, t_g, rtol=0.0, atol=1e-9)
    assert 0.0 <= r_b <= 1.0 + 1e-9


def test_calculate_RT_single_layer_single_quarter_wave_matches_incoherent_analytics() -> None:
    n_h = 2.30
    n_sub = 1.52
    l0 = 550.0
    d_qw = l0 / (4.0 * n_h)

    r_sl, t_sl = calculate_RT_single_layer_single(l0, n_h, 0.0, d_qw, n_sub)

    y_eff = n_h**2 / n_sub
    r_ana = ((1.0 - y_eff) / (1.0 + y_eff)) ** 2
    t_ana = 1.0 - r_ana
    r_sub = ((1.0 - n_sub) / (1.0 + n_sub)) ** 2
    t_sub = 1.0 - r_sub
    denom = 1.0 - r_ana * r_sub
    r_total_exp = r_ana + (t_ana**2 * r_sub) / denom
    t_total_exp = (t_ana * t_sub) / denom

    npt.assert_allclose(r_sl, r_total_exp, rtol=0.0, atol=1e-9)
    npt.assert_allclose(t_sl, t_total_exp, rtol=0.0, atol=1e-9)
    assert 0.0 <= r_sl + t_sl <= 1.0 + 1e-9
