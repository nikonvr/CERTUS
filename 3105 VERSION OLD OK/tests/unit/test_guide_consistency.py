"""
TEST DE CONSISTANCE : GUIDE HTML vs KERNEL CERTUS
This test verifies that the optimized implementation (Numba) in _certus_physics_impl.py
yields EXACTLY the same results as the theoretical formulas from the HTML Guide.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pytest
from certus.core._certus_physics_impl import (
    compute_TMM_single_point_k0_exact,
    calculate_RT_vectorized_real,
    calc_spectrum_oblique_vectorized,
)


# =====================================================================
# 1. “STUDENT” LOGIC (GUIDE FORMULAS)
# =====================================================================
def guide_formulas_front(WL, n0, theta0_deg, n_layers, d_layers, n_sub, pol):
    """Literal implementation of Guide §1-§4 (Front)."""
    theta0 = np.radians(theta0_deg)
    k0 = 2 * np.pi / WL
    S0 = n0 * np.sin(theta0)  # Invariant Snell

    def cos_theta(n):
        return np.sqrt(n**2 - S0**2) / n

    def get_eta(n, p):
        ct = cos_theta(n)
        return n * ct if p == "s" else n / ct

    eta_inc = get_eta(n0, pol)
    eta_exit = get_eta(n_sub, pol)

    M = np.eye(2, dtype=complex)
    for i in range(len(n_layers)):  # 0=Sub, N-1=Air
        n, d = n_layers[i], d_layers[i]
        ct = cos_theta(n)
        eta = get_eta(n, pol)
        delta = k0 * n * d * ct
        cos_d, sin_d = np.cos(delta), np.sin(delta)
        M_j = np.array([[cos_d, 1j * sin_d / eta], [1j * eta * sin_d, cos_d]])
        M = M_j @ M  # Pre-mult (M_N ... M_1)

    BC = M @ np.array([1.0, eta_exit])
    B, C = BC[0], BC[1]
    denom = eta_inc * B + C
    r = (eta_inc * B - C) / denom
    t = 2.0 * eta_inc / denom

    R = abs(r) ** 2
    T = (eta_exit.real / eta_inc.real) * abs(t) ** 2 if eta_inc.real > 0 else 0
    return R, T


def guide_formulas_back(WL, n0, theta0_deg, n_layers, d_layers, n_sub, pol):
    """Literal implementation of Guide §5.3 (Back -> R'_front)."""
    # Incidence = substrate, Output = Air
    theta0 = np.radians(theta0_deg)
    S0 = n0 * np.sin(theta0)  # Invariant Snell
    k0 = 2 * np.pi / WL

    def cos_theta(n):
        return np.sqrt(n**2 - S0**2) / n

    def get_eta(n, p):
        ct = cos_theta(n)
        return n * ct if p == "s" else n / ct

    # Attention : Incident = Sub, Sortie = Air
    eta_inc = get_eta(n_sub, pol)
    eta_exit = get_eta(n0, pol)

    # Matrice M_back = M_1 * ... * M_N (L1=Sub side, LN=Air side)
    # L1 applies last on the output vector (Air).
    # Donc on applique d'abord M_N, puis M_{N-1}...
    M = np.eye(2, dtype=complex)
    for i in range(len(n_layers) - 1, -1, -1):  # N-1 ... 0
        n, d = n_layers[i], d_layers[i]
        ct = cos_theta(n)
        eta = get_eta(n, pol)
        delta = k0 * n * d * ct
        cos_d, sin_d = np.cos(delta), np.sin(delta)
        M_j = np.array([[cos_d, 1j * sin_d / eta], [1j * eta * sin_d, cos_d]])
        M = M_j @ M

    BC = M @ np.array([1.0, eta_exit])
    B, C = BC[0], BC[1]
    denom = eta_inc * B + C
    r = (eta_inc * B - C) / denom
    R_prime = abs(r) ** 2
    return R_prime


def guide_formulas_finite(R_front, T_front, R_prime_front, n_sub, n0, theta0_deg, pol):
    """Literal implementation of Guide §6 (Finite substrate)."""
    S0 = n0 * np.sin(np.radians(theta0_deg))

    def cos_theta(n):
        return np.sqrt(n**2 - S0**2) / n

    def get_eta(n, p):
        ct = cos_theta(n)
        return n * ct if p == "s" else n / ct

    eta_sub = get_eta(n_sub, pol)
    eta_air = get_eta(n0, pol)

    # Back Interface (Sub -> Air)
    r_back = (eta_sub - eta_air) / (eta_sub + eta_air)
    R_back = abs(r_back) ** 2
    T_back = 1.0 - R_back  # Sans perte

    # Substrate transparent (alpha=0)
    denom = 1.0 - R_back * R_prime_front
    R_tot = R_front + (T_front**2 * R_back) / denom
    T_tot = (T_front * T_back) / denom
    return R_tot, T_tot


# =====================================================================
# 2. COMPATIBILITY TESTS
# =====================================================================

# Guide test case (§9)
CASES = [
    (0.0, "s", 0.4970852791, 0.4182563055, 0.5047125703, 0.4100385830),  # 0°
    (45.0, "s", 0.6635212081, 0.2571915993, 0.6703965370, 0.2496188562),  # 45s
    (45.0, "p", 0.5656411291, 0.3676514534, 0.5669131072, 0.3662770124),  # 45p
]

# Material Data
WL = 550.0
n0 = 1.0
n_sub = 1.52
n_layers = np.array([2.35, 1.46, 0.12 - 3.45j, 2.35, 1.46], dtype=complex)
d_layers = np.array([85.0, 90.0, 15.0, 85.0, 90.0])


@pytest.mark.parametrize(
    "angle, pol, R_inf_ref, T_inf_ref, R_fin_ref, _T_fin_ref", CASES
)
def test_guide_vs_code_consistency(
    angle, pol, R_inf_ref, T_inf_ref, R_fin_ref, _T_fin_ref
):
    """Check that:
    1. The local 'Guide' logic reproduces the reference values (§9).
    2. The CERTUS kernel (compute_TMM...) reproduces EXACTLY the 'Guide' logic."""

    # --- 1. GUIDE LOCAL vs REFERENCE ---
    Rf_g, Tf_g = guide_formulas_front(WL, n0, angle, n_layers, d_layers, n_sub, pol)
    Rp_g = guide_formulas_back(WL, n0, angle, n_layers, d_layers, n_sub, pol)
    Rtot_g, Ttot_g = guide_formulas_finite(Rf_g, Tf_g, Rp_g, n_sub, n0, angle, pol)

    assert abs(Rf_g - R_inf_ref) < 1e-9, "Guide Local Front mismatch Reference"
    assert abs(Tf_g - T_inf_ref) < 1e-9, "Guide Local Front mismatch Reference"
    assert abs(Rtot_g - R_fin_ref) < 1e-9, "Guide Local Finite mismatch Reference"

    # --- 2. CODE CERTUS vs GUIDE LOCAL ---
    # A) Normal Incidence (Using optimized kernels)
    if angle == 0:
        k0 = 2 * np.pi / WL
        # Exact point-by-point kernel test
        Rf_c, Tf_c, Rb_c = compute_TMM_single_point_k0_exact(
            k0, d_layers, n_layers, complex(n_sub)
        )

        assert abs(Rf_c - Rf_g) < 1e-12, "CERTUS Kernel Front R mismatch"
        assert abs(Tf_c - Tf_g) < 1e-12, "CERTUS Kernel Front T mismatch"
        assert abs(Rb_c - Rp_g) < 1e-12, "CERTUS Kernel Back R mismatch"

        # COMPLETE calculation test with Backside (Vectorized)
        # Note: calculate_RT_vectorized_real expects 2D arrays for n_layers
        wls = np.array([WL])
        n_layers_2d = n_layers.reshape(1, -1)
        n_sub_arr = np.array([n_sub], dtype=complex)

        R_fin_c, T_fin_c = calculate_RT_vectorized_real(
            d_layers, n_layers_2d, n_sub_arr, wls, with_backside=True
        )

        assert abs(R_fin_c[0] - Rtot_g) < 1e-12, "CERTUS Finite R mismatch"
        assert abs(T_fin_c[0] - Ttot_g) < 1e-12, "CERTUS Finite T mismatch"

    # B) Oblique Incidence (Using the oblique kernel)
    else:
        wls = np.array([WL])
        n_layers_2d = n_layers.reshape(1, -1)
        n_sub_arr = np.array([n_sub], dtype=complex)

        # The oblique kernel computes only Front (no Backside integrated for now in this wrapper)
        # We therefore check R_front and T_front
        R_arr, T_arr = calc_spectrum_oblique_vectorized(
            wls, n_layers_2d, d_layers, n_sub_arr, float(angle), pol
        )
        # Comparison avec Guide Valeurs Reference
        print(f"\n[DEBUG] Angle={angle} Pol={pol}")
        print(f"  Guide Ref R: {Rf_g:.10f}, T: {Tf_g:.10f}")
        print(f"  Code  Cal R: {R_arr[0]:.10f}, T: {T_arr[0]:.10f}")
        print(f"  Delta     R: {abs(R_arr[0] - Rf_g):.10e}")

        assert (
            abs(R_arr[0] - Rf_g) < 1e-9
        ), f"Oblique Code R mismatch {angle}{pol} | G:{Rf_g} C:{R_arr[0]}"
        assert (
            abs(T_arr[0] - Tf_g) < 1e-9
        ), f"Oblique Code T mismatch {angle}{pol} | G:{Tf_g} C:{T_arr[0]}"
