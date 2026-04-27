"""ANTI-REGRESSION TEST: Energy conservation R + T <= 1

===============================================================================

This test protects the T formula in compute_RT_from_matrix.



Macleod formula 4th ed., eq. 2.96 (semi-infinite substrate):

    T = Re(η_exit) / Re(η_inc) · |t|²

    t = 2·η_inc / (η_inc·B + C)



CRITICAL CONVENTION: n̂ = n - ik (k >= 0 for absorption).

With n + ik, the formula gives R+T > 1 (non-physical gain).



THIS TEST MUST ALWAYS PASS. If it fails, it is because the T formula

or the sign convention has been changed incorrectly."""



import sys

import os
from pathlib import Path



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



import numpy as np

import pytest

from certus_core import TWO_PI

from _certus_physics_impl import (

    compute_TMM_generic,

    compute_TMM_single_point_k0,

    calculate_RT_no_backside,

)



# ═══════════════════════════════════════════════════════════════

# HELPER

# ═══════════════════════════════════════════════════════════════





def _build_matrix(k0, thicknesses, n_layers):

    """Pure-Python TMM matrix build (reference, no numba)."""

    M00 = 1.0 + 0.0j

    M01 = 0.0 + 0.0j

    M10 = 0.0 + 0.0j

    M11 = 1.0 + 0.0j

    for i in range(len(thicknesses)):

        n_c = n_layers[i]

        phi = k0 * n_c * thicknesses[i]

        cp = np.cos(phi)

        isp = 1j * np.sin(phi)

        m01 = isp / n_c

        m10 = isp * n_c

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    return M00, M01, M10, M11





# ═══════════════════════════════════════════════════════════════

# TEST 1: R + T <= 1 for empilements absorbants

# ═══════════════════════════════════════════════════════════════





class TestEnergyConservation:

    """Checks R + T <= 1 for various absorbent stacks."""



    # Macleod convention: n̂ = n - ik (NEGATIVE imag for absorption)

    ABSORBING_CASES = [

        # 3 weakly absorbing layers

        (

            np.array([80.0, 120.0, 90.0]),

            np.array([2.3 - 0.02j, 1.45 - 0.01j, 1.8 - 0.015j]),

            1.52,

            "3 layers k=0.01-0.02",

        ),

        # Highly absorbent single layer (metal)

        (np.array([10.0]), np.array([0.5 - 3.0j]), 1.52, "metallic monolayer k=3"),

        # Bilayer metal + dielectric

        (

            np.array([50.0, 8.0]),

            np.array([1.45 - 0.001j, 1.0 - 4.0j]),

            1.52,

            "bilayer dielectrique+metal",

        ),

        # 5 mixed layers

        (

            np.array([60.0, 95.0, 55.0, 90.0, 70.0]),

            np.array(

                [2.3 - 0.05j, 1.45 - 0.02j, 1.8 - 0.03j, 2.1 - 0.01j, 1.6 - 0.04j]

            ),

            1.52,

            "5 layers k=0.01-0.05",

        ),

        # BK7 glass substrate

        (

            np.array([100.0, 80.0]),

            np.array([2.3 + 0.0j, 1.38 + 0.0j]),  # pure dielectrics

            1.52,

            "2 pure layers (control)",

        ),

    ]



    @pytest.mark.parametrize("d,n_layers,n_sub,label", ABSORBING_CASES)

    def test_RT_sum_leq_1_compute_TMM_generic(self, d, n_layers, n_sub, label):

        """compute_TMM_generic doit donner R+T <= 1 for tout empilement."""

        wls = np.linspace(380, 780, 50)

        for wl in wls:

            k0 = TWO_PI / wl

            R, T = compute_TMM_generic(k0, d, n_layers, complex(1.0), complex(n_sub))

            assert R >= 0, f"{label} @ {wl}nm: R={R} < 0"

            assert T >= 0, f"{label} @ {wl}nm: T={T} < 0"

            assert R + T <= 1.0 + 1e-10, (

                f"{label} @ {wl}nm: R+T = {R+T:.10f} > 1 "

                f"(R={R:.8f}, T={T:.8f}). "

                f"RÉGRESSION: formule T ou convention n-ik violée."

            )



    @pytest.mark.parametrize("d,n_layers,n_sub,label", ABSORBING_CASES)

    def test_RT_sum_leq_1_single_point_k0(self, d, n_layers, n_sub, label):

        """compute_TMM_single_point_k0 doit donner R+T <= 1."""

        wls = np.linspace(380, 780, 50)

        for wl in wls:

            k0 = TWO_PI / wl

            R, T = compute_TMM_single_point_k0(k0, d, n_layers, complex(n_sub))

            assert R + T <= 1.0 + 1e-10, (

                f"{label} @ {wl}nm: R+T = {R+T:.10f} > 1. "

                f"RÉGRESSION compute_TMM_single_point_k0."

            )





# ═══════════════════════════════════════════════════════════════

# TEST 2: Macleod reciprocity - T identical in both directions

# ═══════════════════════════════════════════════════════════════





class TestMacleodReciprocity:

    """T must be identical Air->Sub and Sub->Air (Macleod, even with absorption)."""



    # Macleod convention : n̂ = n - ik

    CASES = [

        (

            np.array([80.0, 120.0, 90.0]),

            np.array([2.3 - 0.02j, 1.45 - 0.01j, 1.8 - 0.015j]),

            1.52,

            "3 absorbing layers",

        ),

        (np.array([10.0]), np.array([0.5 - 3.0j]), 1.52, "metallic monolayer"),

        (

            np.array([100.0, 80.0]),

            np.array([2.3, 1.38]),

            1.52,

            "dielectrique pur (controle)",

        ),

    ]



    @pytest.mark.parametrize("d,n_layers,n_sub,label", CASES)

    def test_T_reciprocity(self, d, n_layers, n_sub, label):

        """T_forward == T_backward for tout empilement (Macleod reciprocity)."""

        n_layers_c = np.array(n_layers, dtype=np.complex128)

        wls = np.linspace(400, 700, 20)

        for wl in wls:

            k0 = TWO_PI / wl

            # Forward: Air -> Stack -> Sub

            _, T_fwd = compute_TMM_generic(

                k0, d, n_layers_c, complex(1.0), complex(n_sub)

            )

            # Backward: Sub -> Stack -> Air (reversed)

            d_rev = d[::-1].copy()

            n_rev = n_layers_c[::-1].copy()

            _, T_bwd = compute_TMM_generic(

                k0, d_rev, n_rev, complex(n_sub), complex(1.0)

            )

            assert abs(T_fwd - T_bwd) < 1e-10, (

                f"{label} @ {wl}nm: T_fwd={T_fwd:.10f} != T_bwd={T_bwd:.10f} "

                f"(diff={abs(T_fwd-T_bwd):.2e}). "

                f"RÉGRESSION: réciprocité de Macleod violée."

            )





# ═══════════════════════════════════════════════════════════════

# TEST 3: Pure dielectric - R + T = 1 exactly

# ═══════════════════════════════════════════════════════════════





class TestLosslessConservation:

    """Pour un empilement sans absorption, R + T = 1 exactement."""



    def test_RT_equals_1_lossless(self):

        d = np.array([100.0, 80.0, 60.0])

        n_layers = np.array([2.35 + 0j, 1.38 + 0j, 1.8 + 0j], dtype=np.complex128)

        n_sub = complex(1.52)

        wls = np.linspace(380, 780, 100)

        for wl in wls:

            k0 = TWO_PI / wl

            R, T = compute_TMM_generic(k0, d, n_layers, complex(1.0), n_sub)

            assert abs(R + T - 1.0) < 1e-10, (

                f"Lossless @ {wl}nm: R+T={R+T:.12f} != 1.0 "

                f"(diff={abs(R+T-1):.2e}). "

                f"RÉGRESSION: la formule T doit donner R+T=1 for k=0."

            )





# ═══════════════════════════════════════════════════════════════

# TEST 4: Vectorized paths coherent with generic

# ═══════════════════════════════════════════════════════════════





class TestVectorizedConsistency:

    """Vectorized functions must give the same R/T as compute_TMM_generic."""



    def test_vectorized_vs_generic_absorbing(self):

        """calculate_RT_no_backside vs compute_TMM_generic point par point."""

        d = np.array([80.0, 120.0, 90.0])

        n_sub_val = 1.52

        # Macleod convention : n - ik

        n_layers_1d = np.array([2.3 - 0.02j, 1.45 - 0.01j, 1.8 - 0.015j])

        wls = np.linspace(400, 700, 20).astype(np.float64)

        n_wls = len(wls)



        n_layers_2d = np.tile(n_layers_1d, (n_wls, 1)).astype(np.complex128)

        n_sub_arr = np.full(n_wls, complex(n_sub_val), dtype=np.complex128)



        R_vec, T_vec = calculate_RT_no_backside(d, n_layers_2d, n_sub_arr, wls)



        for i, wl in enumerate(wls):

            k0 = TWO_PI / wl

            R_gen, T_gen = compute_TMM_generic(

                k0, d, n_layers_1d, complex(1.0), complex(n_sub_val)

            )

            assert (

                abs(R_vec[i] - R_gen) < 1e-8

            ), f"R mismatch @ {wl}nm: vec={R_vec[i]:.10f}, gen={R_gen:.10f}"

            assert (

                abs(T_vec[i] - T_gen) < 1e-8

            ), f"T mismatch @ {wl}nm: vec={T_vec[i]:.10f}, gen={T_gen:.10f}"





if __name__ == "__main__":

    pytest.main([__file__, "-v", "--tb=short"])

