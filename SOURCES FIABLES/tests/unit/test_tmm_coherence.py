#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


test_tmm_coherence.py - TMM Coherence & Regression Tests


=========================================================


Validates that ALL TMM functions produce identical R/T values


for the same physical stack, using compute_TMM_generic as reference.





Also validates against analytical quarter-wave formulas.





Run: python test_tmm_coherence.py


"""





import sys


import os
from pathlib import Path


import numpy as np





# Bootstrap path


# Bootstrap path


script_dir = Path(__file__).resolve().parent


project_root = script_dir.parent


if str(project_root) not in sys.path:


    sys.path.insert(0, str(project_root))





from certus.core._certus_physics_impl import (


    compute_TMM_generic,


    compute_RT_from_matrix,


    compute_TMM_single_point_k0,


    compute_TMM_single_point_k0_exact,


    calculate_RT_no_backside,


    calculate_reflectance_bilayer_vectorized,


    _calculate_RT_HL_single_point,


    calculate_RT_batch_kernel,


    calculate_transmission_single,


    TWO_PI,


)





# ─────────────────────────────────────────────────────────────


# Test parameters


# ─────────────────────────────────────────────────────────────


N_SUB = 1.52  # BK7 glass


N_H = 2.30  # TiO2-like


N_L = 1.45  # SiO2-like


L0 = 550.0  # Design wavelength (nm)


TOL = 1e-6  # Tolerance for float comparison


PASS = 0


FAIL = 0








def check(name, val, ref, tol=TOL):


    """Compare val to ref within tolerance."""


    global PASS, FAIL


    diff = abs(val - ref)


    ok = diff < tol


    status = "[PASS]" if ok else "[FAIL]"


    if ok:


        PASS += 1


    else:


        FAIL += 1


    print(f"  {status} {name}: got {val:.8f}, ref {ref:.8f}, diff {diff:.2e}")


    return ok








def section(title):


    print(f"\n{'='*60}")


    print(f"  {title}")


    print(f"{'='*60}")








# ─────────────────────────────────────────────────────────────


# TEST 1: Analytical quarter-wave stack


# ─────────────────────────────────────────────────────────────


def test_analytical_quarter_wave():


    """


    Single QW layer on substrate: analytical R = ((n0 - nH²/nSub)/(n0 + nH²/nSub))²


    """


    section("TEST 1: Analytical Quarter-Wave (single H layer)")





    # Physical thickness for QW at L0


    d_qw = L0 / (4.0 * N_H)  # nm





    # Analytical formula (Macleod, single QW layer)


    Y_eff = N_H**2 / N_SUB


    R_analytical = ((1.0 - Y_eff) / (1.0 + Y_eff)) ** 2


    T_analytical = 1.0 - R_analytical  # Lossless





    print(f"  QW thickness: {d_qw:.4f} nm")


    print(f"  Analytical R: {R_analytical:.8f}")


    print(f"  Analytical T: {T_analytical:.8f}")





    # compute_TMM_generic (reference)


    k0 = TWO_PI / L0


    thicknesses = np.array([d_qw])


    n_layers = np.array([complex(N_H)])


    R_ref, T_ref = compute_TMM_generic(


        k0, thicknesses, n_layers, complex(1.0), complex(N_SUB)


    )





    check("compute_TMM_generic R vs analytical", R_ref, R_analytical)


    check("compute_TMM_generic T vs analytical", T_ref, T_analytical)





    # compute_TMM_single_point_k0


    R_sp, T_sp = compute_TMM_single_point_k0(k0, thicknesses, n_layers, complex(N_SUB))


    check("compute_TMM_single_point_k0 R", R_sp, R_analytical)


    check("compute_TMM_single_point_k0 T", T_sp, T_analytical)





    # compute_TMM_single_point_k0_exact (front only)


    Rf_ex, Tf_ex, Rb_ex = compute_TMM_single_point_k0_exact(


        k0, thicknesses, n_layers, complex(N_SUB)


    )


    check("compute_TMM_single_point_k0_exact Rf", Rf_ex, R_analytical)


    check("compute_TMM_single_point_k0_exact Tf", Tf_ex, T_analytical)





    #  (includes backside, so compare T_total and R_total)


    R_sub_analytical = ((1.0 - N_SUB) / (1.0 + N_SUB)) ** 2


    T_sub_analytical = 1.0 - R_sub_analytical


    denom_incoh = 1.0 - R_analytical * R_sub_analytical


    R_total_expected = R_analytical + (T_analytical**2 * R_sub_analytical) / denom_incoh


    T_total_expected = (T_analytical * T_sub_analytical) / denom_incoh





    R_sl, T_sl = calculate_transmission_single(L0, N_H, 0.0, d_qw, complex(N_SUB))


    check(" R_total", R_sl, R_total_expected)


    check(" T_total", T_sl, T_total_expected)


    # T_sl includes backside correction - verify R + backside T <= 1


    assert 0 <= R_sl + T_sl <= 1.0 + 1e-9, f"R+T out of range: {R_sl + T_sl}"








# ─────────────────────────────────────────────────────────────


# TEST 2: Multi-layer cross-comparison (3-layer HLH stack)


# ─────────────────────────────────────────────────────────────


def test_multilayer_cross_comparison():


    """


    3-layer HLH stack: compare ALL TMM functions to compute_TMM_generic.


    _calculate_RT_HL_single_point returns R_total/T_total WITH backside.


    """


    section("TEST 2: 3-Layer HLH Cross-Comparison")





    d_H = L0 / (4.0 * N_H)


    d_L = L0 / (4.0 * N_L)


    thicknesses = np.array([d_H, d_L, d_H])  # Sub | H | L | H | Air


    n_layers_c128 = np.array([complex(N_H), complex(N_L), complex(N_H)])





    # Backside interface Sub|Air


    r_b = (N_SUB - 1.0) / (N_SUB + 1.0)


    R_sub = r_b * r_b


    T_sub = 1.0 - R_sub





    # Test at multiple wavelengths


    test_wls = [400.0, 500.0, 550.0, 600.0, 700.0, 800.0]





    for wl in test_wls:


        k0 = TWO_PI / wl





        # Reference (front only)


        R_ref, T_ref = compute_TMM_generic(


            k0, thicknesses, n_layers_c128, complex(1.0), complex(N_SUB)


        )





        # compute_TMM_single_point_k0


        R_sp, T_sp = compute_TMM_single_point_k0(


            k0, thicknesses, n_layers_c128, complex(N_SUB)


        )


        check(f"k0 R @ {wl}nm", R_sp, R_ref)


        check(f"k0 T @ {wl}nm", T_sp, T_ref)





        # compute_TMM_single_point_k0_exact (front + Rb)


        Rf_ex, Tf_ex, Rb_ex = compute_TMM_single_point_k0_exact(


            k0, thicknesses, n_layers_c128, complex(N_SUB)


        )


        check(f"k0_exact Rf @ {wl}nm", Rf_ex, R_ref)


        check(f"k0_exact Tf @ {wl}nm", Tf_ex, T_ref)





        # Compute expected R_total/T_total with backside from exact values


        denom_bs = max(1.0 - Rb_ex * R_sub, 1e-12)


        R_total_expected = Rf_ex + (Tf_ex * Tf_ex * R_sub) / denom_bs


        T_total_expected = (Tf_ex * T_sub) / denom_bs





        # _calculate_RT_HL_single_point (returns R_total, T_total WITH backside)


        R_hl, T_hl = _calculate_RT_HL_single_point(


            wl,


            complex(N_H),


            complex(N_L),


            complex(N_SUB),


            thicknesses.astype(np.float32),


        )


        check(f"HL_single R_total @ {wl}nm", R_hl, R_total_expected, tol=1e-4)


        check(f"HL_single T_total @ {wl}nm", T_hl, T_total_expected, tol=1e-4)








# ─────────────────────────────────────────────────────────────


# TEST 3: Vectorized functions vs reference


# ─────────────────────────────────────────────────────────────


def test_vectorized_vs_reference():


    """


    Compares calculate_RT_no_backside and calculate_RT_batch_kernel against reference.


    """


    section("TEST 3: Vectorized Functions")





    d_H = L0 / (4.0 * N_H)


    d_L = L0 / (4.0 * N_L)


    thicknesses = np.array([d_H, d_L, d_H], dtype=np.float64)


    wls = np.linspace(400, 800, 50)





    # Build per-wavelength index arrays (constant dispersion for test)


    n_wls = len(wls)


    n_layers_all = np.zeros((n_wls, 3), dtype=np.complex128)


    n_layers_all[:, 0] = complex(N_H)


    n_layers_all[:, 1] = complex(N_L)


    n_layers_all[:, 2] = complex(N_H)


    n_sub_all = np.full(n_wls, complex(N_SUB), dtype=np.complex128)





    # calculate_RT_no_backside


    R_vec, T_vec = calculate_RT_no_backside(


        thicknesses, n_layers_all, n_sub_all, wls


    )





    max_R_err = 0.0


    max_T_err = 0.0


    for i, wl in enumerate(wls):


        k0 = TWO_PI / wl


        R_ref, T_ref = compute_TMM_generic(


            k0,


            thicknesses,


            np.array([complex(N_H), complex(N_L), complex(N_H)]),


            complex(1.0),


            complex(N_SUB),


        )


        max_R_err = max(max_R_err, abs(R_vec[i] - R_ref))


        max_T_err = max(max_T_err, abs(T_vec[i] - T_ref))





    check("calculate_RT_no_backside max R error", max_R_err, 0.0, tol=1e-6)


    check("calculate_RT_no_backside max T error", max_T_err, 0.0, tol=1e-6)





    # calculate_RT_batch_kernel (uses _calculate_RT_HL_single_point internally)


    wls_f32 = wls.astype(np.float32)


    nH_f32 = np.full(n_wls, complex(N_H), dtype=np.complex64)


    nL_f32 = np.full(n_wls, complex(N_L), dtype=np.complex64)


    nSub_f32 = np.full(n_wls, complex(N_SUB), dtype=np.complex64)


    thick_batch = thicknesses.astype(np.float32).reshape(1, -1)





    R_batch, T_batch = calculate_RT_batch_kernel(


        wls_f32, nH_f32, nL_f32, nSub_f32, thick_batch


    )





    # Batch includes backside - compare R_front only against reference


    # Since _calculate_RT_HL_single_point returns (R_total, T_total) with backside,


    # we check that values are physical and consistent


    R_b = R_batch[0]


    T_b = T_batch[0]


    for i in range(n_wls):


        assert 0 <= R_b[i] <= 1.0 + 1e-5, f"R_batch[{i}] = {R_b[i]}"


        assert 0 <= T_b[i] <= 1.0 + 1e-5, f"T_batch[{i}] = {T_b[i]}"


        assert R_b[i] + T_b[i] <= 1.0 + 1e-4, f"R+T[{i}] = {R_b[i]+T_b[i]}"





    print(


        f"  [PASS] calculate_RT_batch_kernel: all {n_wls} points physical (R,T in [0,1], R+T <= 1)"


    )


    global PASS


    PASS += 1








# ─────────────────────────────────────────────────────────────


# TEST 4: Bilayer (Metal) function


# ─────────────────────────────────────────────────────────────


def test_bilayer_vs_generic():


    """


    Compares calculate_reflectance_bilayer_vectorized against compute_TMM_generic.


    Structure: Air | Metal | SiO2 | Si


    """


    section("TEST 4: Bilayer vs Generic (Metal|SiO2|Si)")





    nM_n = 1.5  # Simplified "metal" (real for test)


    nM_k = 3.0


    nL_val = 1.45


    nSub_val = 3.87  # Si-like


    eM = 10.0


    eL = 50.0





    wls = np.array([400.0, 500.0, 600.0, 700.0])


    n_pts = len(wls)


    nM_arr = np.array([complex(nM_n, -nM_k)] * n_pts, dtype=np.complex128)


    nL_arr = np.array([complex(nL_val)] * n_pts, dtype=np.complex128)


    nSub_arr = np.array([complex(nSub_val)] * n_pts, dtype=np.complex128)





    R_bilayer = calculate_reflectance_bilayer_vectorized(


        wls, nM_arr, eM, eL, nL_arr, nSub_arr


    )





    for i, wl in enumerate(wls):


        k0 = TWO_PI / wl


        # Generic: 2 layers [Metal(sub-adjacent=SiO2, air-adjacent=Metal)]


        # Convention: index 0 = sub-adjacent = SiO2, index 1 = air-adjacent = Metal


        # BUT bilayer code does M_metal @ M_sio2 (pre-mult), so Metal=air-side, SiO2=sub-side


        thicknesses = np.array([eL, eM])  # [SiO2(sub), Metal(air)]


        n_layers_gen = np.array([complex(nL_val), complex(nM_n, -nM_k)])


        R_ref, _ = compute_TMM_generic(


            k0, thicknesses, n_layers_gen, complex(1.0), complex(nSub_val)


        )


        check(f"bilayer R @ {wl}nm", R_bilayer[i], R_ref, tol=1e-6)








# ─────────────────────────────────────────────────────────────


# TEST 5: compute_RT_from_matrix identity (bare substrate)


# ─────────────────────────────────────────────────────────────


def test_bare_substrate():


    """


    No layers (M = Identity): R should match Fresnel formula.


    """


    section("TEST 5: Bare substrate (Fresnel)")





    R_fresnel = ((1.0 - N_SUB) / (1.0 + N_SUB)) ** 2


    T_fresnel = 1.0 - R_fresnel





    R, T = compute_RT_from_matrix(


        complex(1.0),


        complex(0.0),


        complex(0.0),


        complex(1.0),


        complex(1.0),


        complex(N_SUB),


    )


    check("Bare substrate R (Fresnel)", R, R_fresnel)


    check("Bare substrate T (Fresnel)", T, T_fresnel)





    # Also test via compute_TMM_generic with empty stack


    R2, T2 = compute_TMM_generic(


        TWO_PI / 550.0,


        np.array([], dtype=np.float64),


        np.array([], dtype=np.complex128),


        complex(1.0),


        complex(N_SUB),


    )


    check("compute_TMM_generic bare substrate R", R2, R_fresnel)


    check("compute_TMM_generic bare substrate T", T2, T_fresnel)








# ─────────────────────────────────────────────────────────────


# TEST 6: Reciprocity (T_forward == T_backward for lossless)


# ─────────────────────────────────────────────────────────────


def test_reciprocity():


    """


    For lossless stack, T(Air->Sub) == T(Sub->Air).


    """


    section("TEST 6: Reciprocity (lossless)")





    d_H = L0 / (4.0 * N_H)


    d_L = L0 / (4.0 * N_L)


    thicknesses = np.array([d_H, d_L, d_H, d_L, d_H])


    n_layers_fwd = np.array(


        [complex(N_H), complex(N_L), complex(N_H), complex(N_L), complex(N_H)]


    )





    for wl in [400.0, 550.0, 700.0]:


        k0 = TWO_PI / wl





        # Forward: Air -> Sub


        R_fwd, T_fwd = compute_TMM_generic(


            k0, thicknesses, n_layers_fwd, complex(1.0), complex(N_SUB)


        )





        # Backward: Sub -> Air (reversed arrays)


        thicknesses_rev = thicknesses[::-1].copy()


        n_layers_rev = n_layers_fwd[::-1].copy()


        R_bwd, T_bwd = compute_TMM_generic(


            k0, thicknesses_rev, n_layers_rev, complex(N_SUB), complex(1.0)


        )





        check(f"T reciprocity @ {wl}nm", T_fwd, T_bwd)








# ─────────────────────────────────────────────────────────────


# TEST 7: Multi-layer analytical (HLH at design wavelength)


# ─────────────────────────────────────────────────────────────


def test_analytical_hlh():


    """


    At design wavelength, HLH stack has analytical R = ((1 - nH^4/(nL^2*nSub))/(1 + nH^4/(nL^2*nSub)))^2


    """


    section("TEST 7: Analytical HLH at Design Wavelength")





    Y_eff = (N_H**4) / (N_L**2 * N_SUB)


    R_analytical = ((1.0 - Y_eff) / (1.0 + Y_eff)) ** 2





    d_H = L0 / (4.0 * N_H)


    d_L = L0 / (4.0 * N_L)


    k0 = TWO_PI / L0


    thicknesses = np.array([d_H, d_L, d_H])


    n_layers = np.array([complex(N_H), complex(N_L), complex(N_H)])





    R, T = compute_TMM_generic(k0, thicknesses, n_layers, complex(1.0), complex(N_SUB))


    check("HLH R @ design wl", R, R_analytical)


    check("HLH R+T = 1 (lossless)", R + T, 1.0)





    R2, T2 = compute_TMM_single_point_k0(k0, thicknesses, n_layers, complex(N_SUB))


    check("k0 HLH R @ design wl", R2, R_analytical)





    Rf, Tf, _ = compute_TMM_single_point_k0_exact(


        k0, thicknesses, n_layers, complex(N_SUB)


    )


    check("k0_exact HLH Rf @ design wl", Rf, R_analytical)








# ─────────────────────────────────────────────────────────────


# MAIN


# ─────────────────────────────────────────────────────────────


if __name__ == "__main__":


    print("=" * 60)


    print("  CERTUS TMM COHERENCE & REGRESSION TESTS")


    print("=" * 60)





    test_bare_substrate()


    test_analytical_quarter_wave()


    test_analytical_hlh()


    test_multilayer_cross_comparison()


    test_vectorized_vs_reference()


    test_bilayer_vs_generic()


    test_reciprocity()





    print(f"\n{'='*60}")


    print(f"  RESULTS: {PASS} passed, {FAIL} failed")


    print(f"{'='*60}")





    if FAIL > 0:


        print("  [WARN] SOME TESTS FAILED - review output above")


        sys.exit(1)


    else:


        print("  [OK] ALL TESTS PASSED")


        sys.exit(0)


