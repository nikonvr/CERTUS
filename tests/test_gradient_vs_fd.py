#!/usr/bin/env python

"""Test: Analytical Gradients vs Finite Differences

===================================================

Validates ALL analytical gradient kernels against central finite differences,

including absorbing (n-ik) and dispersive clues.



Kernels tested:

  1. _compute_gradient_analytic_kernel (DESIGN) - dCost/d(thickness)

  2. _compute_metal_tmm_gradient_kernel (METAL) - dMSE/d(eM,eL,nM,nL)

  3. _compute_single_layer_sensitivity_kernel (INDEX) - dT/d(n,k,d), dR/d(n,k,d)"""



import numpy as np

import sys
from pathlib import Path



sys.path.insert(0, str(Path(__file__).resolve().parent))

from _certus_physics_impl import (

    _compute_gradient_analytic_kernel,

    compute_oblique_gradient_contrib_analytic,

    compute_oblique_rt_and_grads_analytic,

    calc_spectrum_full_oblique_exact,

    calc_spectrum_full_exact,

    calc_spectrum_oblique_backside_vectorized,

    _compute_metal_tmm_gradient_kernel,

    _compute_single_layer_sensitivity_kernel,

    TWO_PI,

)





def _ref_RT_backside(wl, nr, ni, d, ns):

    """

    Reference R_total, T_total matching the sensitivity kernel's convention.

    Internal convention: (-1j, n+ik) - same as the kernel.

    Includes exact incoherent backside correction.

    """

    k0 = TWO_PI / wl

    n0 = 1.0

    # n+ik convention: n_hat = nr + 1j*ni

    n_hat = complex(nr, ni)

    phi = k0 * n_hat * d

    cp = np.cos(phi)

    sp = np.sin(phi)

    if abs(n_hat) < 1e-14:

        return 0.0, 0.0

    # -1j convention for matrix elements

    M01 = -1j * sp / n_hat

    M10 = -1j * n_hat * sp

    M00 = cp

    M11 = cp



    # Forward: Air -> Film -> Sub  (exit = ns)

    B = M00 + M01 * ns

    C = M10 + M11 * ns

    denom = n0 * B + C

    if abs(denom) < 1e-25:

        return 0.0, 0.0

    num = n0 * B - C

    R_front = abs(num / denom) ** 2

    T_front = 4.0 * n0 * ns / abs(denom) ** 2



    # Reverse: Sub -> Film -> Air  (exit = 1)

    Bp = M00 + M01

    Cp = M10 + M11

    denom_p = ns * Bp + Cp

    if abs(denom_p) < 1e-25:

        R_prime = 0.0

    else:

        num_p = ns * Bp - Cp

        R_prime = abs(num_p / denom_p) ** 2



    # Backside: Sub|Air interface

    r_b = (ns - 1.0) / (ns + 1.0)

    R_sub = r_b * r_b

    T_sub = 1.0 - R_sub



    # Incoherent combination

    D = 1.0 - R_prime * R_sub

    if D < 1e-12:

        D = 1e-12

    T_total = T_front * T_sub / D

    R_total = R_front + T_front**2 * R_sub / D



    return max(0.0, min(1.0, R_total)), max(0.0, min(1.0, T_total))





PASS = 0

FAIL = 0





def check(name, analytic, fd, tol=1e-4):

    global PASS, FAIL

    if abs(fd) > 1e-12:

        rel = abs(analytic - fd) / abs(fd)

        ok = rel < tol

        label = f"rel={rel:.2e}"

    else:

        ok = abs(analytic - fd) < tol

        label = f"abs={abs(analytic-fd):.2e}"

    if ok:

        PASS += 1

        print(f"  ✅ {name}: analytic={analytic:.8e}, fd={fd:.8e}, {label}")

    else:

        FAIL += 1

        print(f"  ❌ {name}: analytic={analytic:.8e}, fd={fd:.8e}, {label}")





# ============================================================

#  TEST 1: DESIGN gradient (_compute_gradient_analytic_kernel)

#          Dispersive + absorbing multilayer

# ============================================================

def test_design_gradient():

    print("\n" + "=" * 60)

    print("  TEST 1: DESIGN gradient - dispersive + absorbing stack")

    print("=" * 60)



    # 5-layer stack: H L H_abs L H  (layer 2 is absorbing)

    n_layers = 5

    ep = np.array([80.0, 120.0, 90.0, 110.0, 70.0], dtype=np.float64)



    # Dispersive wavelengths

    wls = np.array([400.0, 500.0, 550.0, 600.0, 700.0], dtype=np.float64)

    n_wls = len(wls)



    # Dispersive + absorbing clues: n_layers_T shape (n_wls, n_layers)

    # Layer 0,2,4 = "H" with dispersion; Layer 1,3 = "L" with dispersion

    # Layer 2 has absorption (k = 0.05)

    n_layers_T = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i, wl in enumerate(wls):

        nH = 2.3 + 0.02 * (550.0 / wl - 1.0)  # Dispersive H

        nL = 1.45 + 0.01 * (550.0 / wl - 1.0)  # Dispersive L

        # Macleod: n - ik

        n_layers_T[i, 0] = complex(nH, 0.0)

        n_layers_T[i, 1] = complex(nL, 0.0)

        n_layers_T[i, 2] = complex(nH, -0.05)  # Absorbing H layer (Macleod: n - ik)

        n_layers_T[i, 3] = complex(nL, 0.0)

        n_layers_T[i, 4] = complex(nH, 0.0)



    # Dispersive substrate

    n_sub = np.array(

        [complex(1.52 + 0.005 * (550.0 / wl - 1.0)) for wl in wls], dtype=np.complex128

    )



    # Targets (arbitrary)

    tgt_vals = np.array([0.8, 0.5, 0.4, 0.5, 0.7], dtype=np.float64)

    tgt_weights = np.ones(n_wls, dtype=np.float64)



    # All layers variable

    var_idx = np.arange(n_layers, dtype=np.int64)



    # Analytical gradient

    cost_a, grad_a, T_arr = _compute_gradient_analytic_kernel(

        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

    )



    # Finite difference gradient

    h = 1e-6

    grad_fd = np.zeros(n_layers, dtype=np.float64)

    for k in range(n_layers):

        ep_p = ep.copy()

        ep_p[k] += h

        ep_m = ep.copy()

        ep_m[k] -= h

        cost_p, _, _ = _compute_gradient_analytic_kernel(

            ep_p, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

        )

        cost_m, _, _ = _compute_gradient_analytic_kernel(

            ep_m, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

        )

        grad_fd[k] = (cost_p - cost_m) / (2.0 * h)



    for k in range(n_layers):

        absorb = " (absorbing)" if k == 2 else ""

        check(f"dCost/d(ep[{k}]){absorb}", grad_a[k], grad_fd[k], tol=1e-4)





# ============================================================

#  TEST 2: DESIGN gradient - ALL absorbing layers

# ============================================================

def test_design_gradient_all_absorbing():

    print("\n" + "=" * 60)

    print("  TEST 2: DESIGN gradient - ALL absorbing layers")

    print("=" * 60)



    n_layers = 3

    ep = np.array([60.0, 100.0, 80.0], dtype=np.float64)

    wls = np.array([450.0, 550.0, 650.0], dtype=np.float64)

    n_wls = len(wls)



    n_layers_T = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i, wl in enumerate(wls):

        nH = 2.3 + 0.02 * (550.0 / wl - 1.0)

        nL = 1.45 + 0.01 * (550.0 / wl - 1.0)

        # All absorbing (Macleod: n - ik)

        n_layers_T[i, 0] = complex(nH, -0.03)

        n_layers_T[i, 1] = complex(nL, -0.01)

        n_layers_T[i, 2] = complex(nH, -0.05)



    n_sub = np.array([complex(1.52)] * n_wls, dtype=np.complex128)

    tgt_vals = np.array([0.6, 0.4, 0.6], dtype=np.float64)

    tgt_weights = np.ones(n_wls, dtype=np.float64)

    var_idx = np.arange(n_layers, dtype=np.int64)



    cost_a, grad_a, _ = _compute_gradient_analytic_kernel(

        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

    )



    h = 1e-6

    grad_fd = np.zeros(n_layers, dtype=np.float64)

    for k in range(n_layers):

        ep_p = ep.copy()

        ep_p[k] += h

        ep_m = ep.copy()

        ep_m[k] -= h

        cost_p, _, _ = _compute_gradient_analytic_kernel(

            ep_p, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

        )

        cost_m, _, _ = _compute_gradient_analytic_kernel(

            ep_m, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx

        )

        grad_fd[k] = (cost_p - cost_m) / (2.0 * h)



    for k in range(n_layers):

        check(f"dCost/d(ep[{k}]) all-absorbing", grad_a[k], grad_fd[k], tol=1e-4)





# ============================================================

#  TEST 3: METAL gradient (_compute_metal_tmm_gradient_kernel)

#          Absorbing metal + dispersive dielectric

# ============================================================

def test_metal_gradient():

    print("\n" + "=" * 60)

    print("  TEST 3: METAL gradient - absorbing metal + dielectric")

    print("=" * 60)



    wls = np.linspace(400, 700, 20, dtype=np.float64)

    n_pts = len(wls)



    # Metal: Ag-like dispersive absorbing (Macleod: n - ik)

    nM_arr = np.array(

        [

            complex(0.05 + 0.01 * (wl / 550 - 1), -(3.0 + 0.5 * (wl / 550 - 1)))

            for wl in wls

        ],

        dtype=np.complex128,

    )

    # Dielectric: SiO2-like dispersive

    nL_arr = np.array(

        [complex(1.46 + 0.005 * (550 / wl - 1)) for wl in wls], dtype=np.complex128

    )

    # substrate: Si (absorbing)

    nS_arr = np.array(

        [

            complex(3.5 + 0.1 * (550 / wl - 1), -(0.1 + 0.05 * (wl / 550 - 1)))

            for wl in wls

        ],

        dtype=np.complex128,

    )



    eM = 30.0  # nm

    eL = 50.0  # nm



    # Target R (arbitrary)

    r_tgt = np.full(n_pts, 0.5, dtype=np.float64)



    # Analytical

    mse_a, g_eM_a, g_eL_a, dJ_dnM_r, dJ_dnM_i, dJ_dnL_r = (

        _compute_metal_tmm_gradient_kernel(wls, nM_arr, eM, eL, nL_arr, nS_arr, r_tgt)

    )



    h = 1e-6



    # --- grad_eM ---

    mse_p, *_ = _compute_metal_tmm_gradient_kernel(

        wls, nM_arr, eM + h, eL, nL_arr, nS_arr, r_tgt

    )

    mse_m, *_ = _compute_metal_tmm_gradient_kernel(

        wls, nM_arr, eM - h, eL, nL_arr, nS_arr, r_tgt

    )

    g_eM_fd = (mse_p - mse_m) / (2 * h)

    check("dMSE/d(eM) metal", g_eM_a, g_eM_fd, tol=1e-4)



    # --- grad_eL ---

    mse_p, *_ = _compute_metal_tmm_gradient_kernel(

        wls, nM_arr, eM, eL + h, nL_arr, nS_arr, r_tgt

    )

    mse_m, *_ = _compute_metal_tmm_gradient_kernel(

        wls, nM_arr, eM, eL - h, nL_arr, nS_arr, r_tgt

    )

    g_eL_fd = (mse_p - mse_m) / (2 * h)

    check("dMSE/d(eL) dielectric", g_eL_a, g_eL_fd, tol=1e-4)



    # --- grad nM_r, nM_i per wavelength (spot check: 3 wavelengths) ---

    for idx in [0, n_pts // 2, n_pts - 1]:

        wl = wls[idx]



        # dJ/dnM_r

        nM_p = nM_arr.copy()

        nM_p[idx] += h

        nM_m = nM_arr.copy()

        nM_m[idx] -= h

        mse_p, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_p, eM, eL, nL_arr, nS_arr, r_tgt

        )

        mse_m, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_m, eM, eL, nL_arr, nS_arr, r_tgt

        )

        fd_nr = (mse_p - mse_m) / (2 * h)

        check(f"dMSE/d(nM_r) @ {wl:.0f}nm", dJ_dnM_r[idx], fd_nr, tol=1e-3)



        # dJ/dnM_i (perturbation on imaginary part)

        nM_p = nM_arr.copy()

        nM_p[idx] += 1j * h

        nM_m = nM_arr.copy()

        nM_m[idx] -= 1j * h

        mse_p, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_p, eM, eL, nL_arr, nS_arr, r_tgt

        )

        mse_m, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_m, eM, eL, nL_arr, nS_arr, r_tgt

        )

        fd_ni = (mse_p - mse_m) / (2 * h)

        check(f"dMSE/d(nM_i) @ {wl:.0f}nm", dJ_dnM_i[idx], fd_ni, tol=1e-3)



    # --- grad nL_r per wavelength ---

    for idx in [0, n_pts // 2, n_pts - 1]:

        wl = wls[idx]

        nL_p = nL_arr.copy()

        nL_p[idx] += h

        nL_m = nL_arr.copy()

        nL_m[idx] -= h

        mse_p, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_arr, eM, eL, nL_p, nS_arr, r_tgt

        )

        mse_m, *_ = _compute_metal_tmm_gradient_kernel(

            wls, nM_arr, eM, eL, nL_m, nS_arr, r_tgt

        )

        fd_nLr = (mse_p - mse_m) / (2 * h)

        check(f"dMSE/d(nL_r) @ {wl:.0f}nm", dJ_dnL_r[idx], fd_nLr, tol=1e-3)





# ============================================================

#  TEST 4: INDEX gradient (_compute_single_layer_sensitivity_kernel)

#          Lossless film - using n+ik convention reference

# ============================================================

def _run_index_gradient_checks(label, wl, nr, ni, d, ns, tol=1e-4):

    """Run FD checks for the sensitivity kernel using n+ik convention reference."""

    dT_dnr, dT_dni, dR_dnr, dR_dni, dT_dd, dR_dd = (

        _compute_single_layer_sensitivity_kernel(wl, nr, ni, d, ns)

    )



    h = 1e-7



    # FD: perturb nr (same in both conventions)

    R_p, T_p = _ref_RT_backside(wl, nr + h, ni, d, ns)

    R_m, T_m = _ref_RT_backside(wl, nr - h, ni, d, ns)

    check(f"dT/d(nr) {label}", dT_dnr, (T_p - T_m) / (2 * h), tol=tol)

    check(f"dR/d(nr) {label}", dR_dnr, (R_p - R_m) / (2 * h), tol=tol)



    # FD: perturb ni (n+ik convention - same as kernel)

    R_p, T_p = _ref_RT_backside(wl, nr, ni + h, d, ns)

    R_m, T_m = _ref_RT_backside(wl, nr, ni - h, d, ns)

    check(f"dT/d(ni) {label}", dT_dni, (T_p - T_m) / (2 * h), tol=tol)

    check(f"dR/d(ni) {label}", dR_dni, (R_p - R_m) / (2 * h), tol=tol)



    # FD: perturb d

    R_p, T_p = _ref_RT_backside(wl, nr, ni, d + h, ns)

    R_m, T_m = _ref_RT_backside(wl, nr, ni, d - h, ns)

    check(f"dT/d(d) {label}", dT_dd, (T_p - T_m) / (2 * h), tol=tol)

    check(f"dR/d(d) {label}", dR_dd, (R_p - R_m) / (2 * h), tol=tol)





def test_index_gradient_lossless():

    print("\n" + "=" * 60)

    print("  TEST 4: INDEX gradient - lossless film")

    print("=" * 60)

    _run_index_gradient_checks("lossless", 550.0, 2.0, 0.0, 80.0, 1.52)





# ============================================================

#  TEST 5: INDEX gradient - absorbing film

# ============================================================

def test_index_gradient_absorbing():

    print("\n" + "=" * 60)

    print("  TEST 5: INDEX gradient - absorbing film (k > 0)")

    print("=" * 60)

    _run_index_gradient_checks("absorbing", 500.0, 1.8, 0.15, 60.0, 1.52)





# ============================================================

#  TEST 6: INDEX gradient - strongly absorbing (metal-like)

# ============================================================

def test_index_gradient_metal():

    print("\n" + "=" * 60)

    print("  TEST 6: INDEX gradient - strongly absorbing (metal-like)")

    print("=" * 60)

    _run_index_gradient_checks("metal", 600.0, 0.1, 3.5, 30.0, 1.52, tol=1e-3)





# ============================================================

#  TEST 7: INDEX gradient - multiple wavelengths (dispersive)

# ============================================================

def test_index_gradient_dispersive():

    print("\n" + "=" * 60)

    print("  TEST 7: INDEX gradient - dispersive, multiple wavelengths")

    print("=" * 60)



    d = 70.0

    ns = 1.52



    for wl in [400.0, 500.0, 600.0, 700.0]:

        nr = 1.9 + 0.02 * (550.0 / wl - 1.0)

        ni = 0.05 + 0.02 * (550.0 / wl - 1.0)

        _run_index_gradient_checks(f"@ {wl:.0f}nm disp", wl, nr, ni, d, ns)





# ============================================================

#  TEST 8: DESIGN oblique front-only gradient

# ============================================================

def test_design_oblique_gradient_front_only():

    print("\n" + "=" * 60)

    print("  TEST 8: DESIGN oblique front-only gradient (analytic vs FD)")

    print("=" * 60)



    ep = np.array([80.0, 110.0, 70.0], dtype=np.float64)

    wls = np.array([450.0, 500.0, 550.0, 620.0], dtype=np.float64)

    n_wls = len(wls)

    n_layers = len(ep)



    n_layers_T = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i, wl in enumerate(wls):

        nH = 2.2 + 0.02 * (550.0 / wl - 1.0)

        nL = 1.46 + 0.01 * (550.0 / wl - 1.0)

        n_layers_T[i, 0] = complex(nH, -0.01)

        n_layers_T[i, 1] = complex(nL, 0.0)

        n_layers_T[i, 2] = complex(nH, -0.02)



    n_sub = np.array([complex(1.52)] * n_wls, dtype=np.complex128)

    tgt_vals = np.array([0.45, 0.50, 0.55, 0.52], dtype=np.float64)

    tgt_weights = np.ones(n_wls, dtype=np.float64)

    var_idx = np.arange(n_layers, dtype=np.int64)

    angle_deg = 45.0

    is_s_pol = True



    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(

        ep,

        n_layers_T,

        n_sub,

        wls,

        tgt_vals,

        tgt_weights,

        angle_deg,

        is_s_pol,

        False,  # target = T

        var_idx,

    )

    cost_a = err_sum / weight_sum

    grad_a = (2.0 / weight_sum) * grad_raw



    h = 1e-6

    grad_fd = np.zeros(n_layers, dtype=np.float64)

    for k in range(n_layers):

        ep_p = ep.copy()

        ep_p[k] += h

        ep_m = ep.copy()

        ep_m[k] -= h



        err_p, _, w_p = compute_oblique_gradient_contrib_analytic(

            ep_p, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, angle_deg, is_s_pol, False, var_idx

        )

        err_m, _, w_m = compute_oblique_gradient_contrib_analytic(

            ep_m, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, angle_deg, is_s_pol, False, var_idx

        )

        cost_p = err_p / w_p

        cost_m = err_m / w_m

        grad_fd[k] = (cost_p - cost_m) / (2.0 * h)



    print(f"  cost oblique analytic = {cost_a:.8e}")

    for k in range(n_layers):

        check(f"dCost/d(ep[{k}]) oblique-front", grad_a[k], grad_fd[k], tol=5e-4)





# ============================================================

#  TEST 9: Oblique full exact @ 0deg matches normal exact (T)

# ============================================================

def test_oblique_full_exact_zero_degree_matches_normal():

    print("\n" + "=" * 60)

    print("  TEST 9: oblique full exact @0deg vs normal exact")

    print("=" * 60)



    wls = np.array([450.0, 550.0, 650.0], dtype=np.float64)

    d_front = np.array([80.0, 110.0], dtype=np.float64)

    d_back = np.array([40.0], dtype=np.float64)



    n_front = np.zeros((len(wls), len(d_front)), dtype=np.complex128)

    n_back = np.zeros((len(wls), len(d_back)), dtype=np.complex128)

    for i, wl in enumerate(wls):

        n_front[i, 0] = complex(2.25 + 0.01 * (550.0 / wl - 1.0), -0.01)

        n_front[i, 1] = complex(1.46 + 0.005 * (550.0 / wl - 1.0), 0.0)

        n_back[i, 0] = complex(1.38 + 0.003 * (550.0 / wl - 1.0), 0.0)

    n_sub = np.array([complex(1.52)] * len(wls), dtype=np.complex128)



    # Normal exact reference

    Rf, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(

        wls, d_front, n_front, d_back, n_back, n_sub

    )

    denom = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)

    T_ref = (Tf * Tb) / denom



    # Oblique exact at 0° (must reduce to normal case)

    _, T_obl = calc_spectrum_full_oblique_exact(

        wls, d_front, n_front, d_back, n_back, n_sub, 0.0, True

    )



    for i in range(len(wls)):

        check(f"T@{wls[i]:.0f}nm", T_obl[i], T_ref[i], tol=5e-4)





# ============================================================

#  TEST 10: Oblique backside wrapper == full exact (empty back)

# ============================================================

def test_oblique_backside_wrapper_matches_full_exact_empty_back():

    print("\n" + "=" * 60)

    print("  TEST 10: oblique backside wrapper vs full exact empty back")

    print("=" * 60)



    wls = np.array([430.0, 520.0, 610.0], dtype=np.float64)

    d_front = np.array([70.0, 105.0, 62.0], dtype=np.float64)

    n_front = np.zeros((len(wls), len(d_front)), dtype=np.complex128)

    for i, wl in enumerate(wls):

        n_front[i, 0] = complex(2.25 + 0.01 * (550.0 / wl - 1.0), -0.01)

        n_front[i, 1] = complex(1.46 + 0.004 * (550.0 / wl - 1.0), 0.0)

        n_front[i, 2] = complex(2.10 + 0.008 * (550.0 / wl - 1.0), -0.015)

    n_sub = np.array([complex(1.52)] * len(wls), dtype=np.complex128)



    R_w, T_w = calc_spectrum_oblique_backside_vectorized(

        wls, n_front, d_front, n_sub, 35.0, "p"

    )

    R_f, T_f = calc_spectrum_full_oblique_exact(

        wls,

        d_front,

        n_front,

        np.zeros(0, dtype=np.float64),

        np.zeros((len(wls), 0), dtype=np.complex128),

        n_sub,

        35.0,

        False,

    )



    for i in range(len(wls)):

        check(f"R@{wls[i]:.0f}nm", R_w[i], R_f[i], tol=1e-10)

        check(f"T@{wls[i]:.0f}nm", T_w[i], T_f[i], tol=1e-10)





# ============================================================

#  TEST 11: Oblique backside analytic chain gradient vs FD

# ============================================================

def test_oblique_backside_analytic_chain_gradient():

    print("\n" + "=" * 60)

    print("  TEST 11: oblique backside analytic chain gradient vs FD")

    print("=" * 60)



    wls = np.array([460.0, 530.0, 610.0], dtype=np.float64)

    ep_front = np.array([78.0, 102.0], dtype=np.float64)

    ep_back = np.array([42.0], dtype=np.float64)

    n_sub = np.array([complex(1.52)] * len(wls), dtype=np.complex128)

    var_idx = np.arange(len(ep_front), dtype=np.int64)

    angle = 40.0

    is_s = True



    n_front = np.zeros((len(wls), len(ep_front)), dtype=np.complex128)

    n_back = np.zeros((len(wls), len(ep_back)), dtype=np.complex128)

    for i, wl in enumerate(wls):

        n_front[i, 0] = complex(2.20 + 0.01 * (550.0 / wl - 1.0), -0.01)

        n_front[i, 1] = complex(1.46 + 0.005 * (550.0 / wl - 1.0), 0.0)

        n_back[i, 0] = complex(1.38 + 0.003 * (550.0 / wl - 1.0), 0.0)



    tgt_T = np.array([0.55, 0.52, 0.50], dtype=np.float64)

    weights = np.ones(len(wls), dtype=np.float64)



    def cost_and_grad(ep):

        Rf, Tf, _, dTf = compute_oblique_rt_and_grads_analytic(

            ep, n_front, n_sub, wls, var_idx, angle, is_s, False

        )

        Rfp, Tfr, dRfp, _ = compute_oblique_rt_and_grads_analytic(

            ep, n_front, n_sub, wls, var_idx, angle, is_s, True

        )

        Rbp, Tb, _, _ = compute_oblique_rt_and_grads_analytic(

            ep_back, n_back, n_sub, wls, np.zeros(0, dtype=np.int64), angle, is_s, True

        )



        D = np.maximum(1.0 - Rfp * Rbp, 1e-12)

        D2 = D * D

        Ttot = (Tf * Tb) / D

        diff = Ttot - tgt_T

        cost = np.sum(weights * diff * diff) / np.sum(weights)



        dTtot = Tb[:, None] * (

            dTf / D[:, None] + (Tf[:, None] * Rbp[:, None] * dRfp) / D2[:, None]

        )

        grad = (2.0 / np.sum(weights)) * np.sum(weights[:, None] * diff[:, None] * dTtot, axis=0)

        return cost, grad



    c_a, g_a = cost_and_grad(ep_front)

    h = 1e-6

    g_fd = np.zeros_like(g_a)

    for k in range(len(ep_front)):

        ep_p = ep_front.copy()

        ep_m = ep_front.copy()

        ep_p[k] += h

        ep_m[k] -= h

        c_p, _ = cost_and_grad(ep_p)

        c_m, _ = cost_and_grad(ep_m)

        g_fd[k] = (c_p - c_m) / (2.0 * h)



    print(f"  cost analytic-chain = {c_a:.8e}")

    for k in range(len(ep_front)):

        check(f"dCost/d(ep_front[{k}])", g_a[k], g_fd[k], tol=1e-3)





# ============================================================

#  MAIN

# ============================================================

if __name__ == "__main__":

    print("=" * 60)

    print("  GRADIENT VERIFICATION: Analytical vs Finite Differences")

    print("=" * 60)



    test_design_gradient()

    test_design_gradient_all_absorbing()

    test_metal_gradient()

    test_index_gradient_lossless()

    test_index_gradient_absorbing()

    test_index_gradient_metal()

    test_index_gradient_dispersive()

    test_design_oblique_gradient_front_only()

    test_oblique_full_exact_zero_degree_matches_normal()

    test_oblique_backside_wrapper_matches_full_exact_empty_back()

    test_oblique_backside_analytic_chain_gradient()



    print("\n" + "=" * 60)

    print(f"  RESULTS: {PASS} passed, {FAIL} failed")

    print("=" * 60)

    if FAIL == 0:

        print("  ✅ ALL GRADIENT TESTS PASSED")

    else:

        print("  ❌ SOME TESTS FAILED")

    sys.exit(FAIL)

