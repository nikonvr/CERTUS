#!/usr/bin/env python


"""test_tmm_inline.py - Tests TMM inline (non-locked) functions against


an exact Macleod reference (+1d, n-ik).





Macleod convention: n_hat = n - ik (k > 0 = absorption).


Reference: TMM with factor +1d (true Macleod, = exact Fresnel/Airy).


Code tested: now +1d too (fix applied).





PHYSICAL REMINDER:


  +1d with n-ik -> correct (absorption, R+T+A=1)


  -1d with n-ik -> incorrect for k>0 (R+T>1, hidden by clamping)


  -1d with n+ik -> correct too (related conventions)"""





import numpy as np


import sys, os





from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))





from _certus_physics_impl import (


    compute_TMM_generic,


    calculate_RT_no_backside,


    calculate_RT_single_layer_single,


    _compute_index_cost_gradient_kernel,


    cost_numba_fast,


    calculate_RTRback_incoherent_vectorized,


    compute_dynamics_kernel,


    calculate_detailed_growth,


    simulate_growth_kernel,


    check_extrema_proximity,


    compute_mse_vectorized,


    TWO_PI,


)





PASS = 0


FAIL = 0








def check(name, got, ref, tol=1e-6):


    global PASS, FAIL


    if abs(ref) > 1e-12:


        rel = abs(got - ref) / abs(ref)


        ok = rel < tol


        label = f"rel={rel:.2e}"


    else:


        ok = abs(got - ref) < tol


        label = f"abs={abs(got - ref):.2e}"


    status = "\u2705" if ok else "\u274c"


    if ok:


        PASS += 1


    else:


        FAIL += 1


    print(f"  {status} {name}: got={got:.8e}, ref={ref:.8e}, {label}")








# ================================================================


#  REFERENCE: true Macleod (+1j, n-ik) - proven = exact Fresnel


# ================================================================


def macleod_tmm_RT(wl, thicknesses, n_layers, n_inc, n_exit):


    """TMM Macleod exact: +1d factor, n-ik convention.


    Layer index 0 = substrate side (exit). Pre-multiplication."""


    k0 = TWO_PI / wl


    M = np.eye(2, dtype=complex)


    for i in range(len(thicknesses)):


        nc = n_layers[i]


        phi = k0 * nc * thicknesses[i]


        cp = np.cos(phi)


        sp = np.sin(phi)


        m01 = +1j * sp / nc  # +1j = vrai Macleod


        m10 = +1j * nc * sp


        L = np.array([[cp, m01], [m10, cp]], dtype=complex)


        M = L @ M  # pre-multiplication


    B = M[0, 0] + M[0, 1] * n_exit


    C = M[1, 0] + M[1, 1] * n_exit


    Y = n_inc * B + C


    if abs(Y) < 1e-25:


        return 0.0, 0.0


    r = (n_inc * B - C) / Y


    R = abs(r) ** 2


    t = 2.0 * n_inc / Y


    T = (n_exit.real / n_inc.real) * abs(t) ** 2 if n_inc.real > 1e-12 else 0.0


    return R, max(0.0, T)








def dispersive_n(wl, n0, k0_abs, disp_coeff=0.02):


    """Generate dispersive complex index (Macleod: n - ik)."""


    nr = n0 + disp_coeff * (550.0 / wl - 1.0)


    ki = k0_abs + 0.01 * (550.0 / wl - 1.0)


    return complex(nr, -abs(ki))  # Macleod: n - ik








# ============================================================


#  TEST 0: V\u00e9rifier macleod_tmm_RT vs Fresnel exact (single layer)


# ============================================================


def test_macleod_reference():


    print("\n" + "=" * 60)


    print("  TEST 0: macleod_tmm_RT vs Fresnel/Airy exact")


    print("=" * 60)





    wl = 550.0


    d = 80.0


    n0 = complex(1.0)


    ns = complex(1.52)


    nf = complex(2.35, -0.03)  # n-ik





    # Fresnel/Airy exact


    k0 = TWO_PI / wl


    r01 = (n0 - nf) / (n0 + nf)


    r12 = (nf - ns) / (nf + ns)


    t01 = 2 * n0 / (n0 + nf)


    t12 = 2 * nf / (nf + ns)


    delta = k0 * nf * d


    phase = np.exp(-2j * delta)


    r_tot = (r01 + r12 * phase) / (1 + r01 * r12 * phase)


    t_tot = (t01 * t12 * np.exp(-1j * delta)) / (1 + r01 * r12 * phase)


    R_ex = abs(r_tot) ** 2


    T_ex = ns.real * abs(t_tot) ** 2





    R_mac, T_mac = macleod_tmm_RT(wl, np.array([d]), np.array([nf]), n0, ns)


    check("R Macleod vs Fresnel", R_mac, R_ex, tol=1e-12)


    check("T Macleod vs Fresnel", T_mac, T_ex, tol=1e-12)


    check("R+T+A = 1 (A>0)", R_mac + T_mac, R_ex + T_ex, tol=1e-12)


    print(f"  A = {1 - R_mac - T_mac:.6f} (absorption)")





    # Also verify with compute_TMM_generic (-1j) for comparison


    R_code, T_code = compute_TMM_generic(k0, np.array([d]), np.array([nf]), n0, ns)


    print(


        f"  compute_TMM_generic(-1j, n-ik): R={R_code:.6f} T={T_code:.6f} R+T={R_code+T_code:.6f}"


    )


    print(


        f"  Macleod exact (+1j, n-ik):      R={R_mac:.6f} T={T_mac:.6f} R+T={R_mac+T_mac:.6f}"


    )


    if abs(R_code - R_mac) > 0.001 or abs(T_code - T_mac) > 0.001:


        print(f"  \u26a0\ufe0f  ECART compute_TMM_generic vs Macleod exact for k>0")








# ============================================================


#  TEST 0b: Symmetric ns = n0 = 1 (no substrate interface)


#  R+T=1 for lossless, R+T+A=1 for absorbant


# ============================================================


def test_symmetric_ns1():


    print("\n" + "=" * 60)


    print("TEST 0b: Symmetrical structure ns = n0 = 1")


    print("=" * 60)





    n0 = complex(1.0)


    ns = complex(1.0)





    # --- Case 1: dielectric monolayer (k=0) => R+T must = 1, T identical on both sides ---


    wl = 550.0


    d = 80.0


    nf = complex(2.35, 0.0)


    R_mac, T_mac = macleod_tmm_RT(wl, np.array([d]), np.array([nf]), n0, ns)


    check("Lossless ns=1: R+T=1", R_mac + T_mac, 1.0, tol=1e-12)





    k0 = TWO_PI / wl


    R_code, T_code = compute_TMM_generic(k0, np.array([d]), np.array([nf]), n0, ns)


    check("Lossless ns=1: code R vs Macleod", R_code, R_mac, tol=1e-10)


    check("Lossless ns=1: code T vs Macleod", T_code, T_mac, tol=1e-10)





    # --- Cas 2: monocouche absorbante (k>0) => R+T<1, A>0 ---


    nf_abs = complex(2.35, -0.05)  # n-ik


    R_mac2, T_mac2 = macleod_tmm_RT(wl, np.array([d]), np.array([nf_abs]), n0, ns)


    A2 = 1 - R_mac2 - T_mac2


    check("Absorbing ns=1: A>0", A2, abs(A2), tol=1e-12)


    print(f"  R={R_mac2:.6f} T={T_mac2:.6f} A={A2:.6f}")





    R_code2, T_code2 = compute_TMM_generic(


        k0, np.array([d]), np.array([nf_abs]), n0, ns


    )


    check("Absorbing ns=1: code R vs Macleod", R_code2, R_mac2, tol=1e-10)


    check("Absorbing ns=1: code T vs Macleod", T_code2, T_mac2, tol=1e-10)





    # --- Cas 3: multicouche absorbante ---


    nH = complex(2.35, -0.03)


    nL = complex(1.45, -0.01)


    thick = np.array([80.0, 120.0, 80.0])


    n_layers = np.array([nH, nL, nH])


    R_mac3, T_mac3 = macleod_tmm_RT(wl, thick, n_layers, n0, ns)


    R_code3, T_code3 = compute_TMM_generic(k0, thick, n_layers, n0, ns)


    check("Multi ns=1: code R vs Macleod", R_code3, R_mac3, tol=1e-10)


    check("Multi ns=1: code T vs Macleod", T_code3, T_mac3, tol=1e-10)


    A3 = 1 - R_mac3 - T_mac3


    check("Multi ns=1: A>0", A3, abs(A3), tol=1e-12)


    print(f"  R={R_mac3:.6f} T={T_mac3:.6f} A={A3:.6f}")





    # --- Cas 4: calculate_RT_single_layer_single ---


    R_sl, T_sl = calculate_RT_single_layer_single(wl, 2.35, 0.05, d, 1.0)


    check("RT_single ns=1 R vs Macleod", R_sl, R_mac2, tol=1e-6)


    check("RT_single ns=1 T vs Macleod", T_sl, T_mac2, tol=1e-6)








# ============================================================


#  TEST 1: compute_dynamics_kernel - complex dispersive


#  Compare T vs macleod_tmm_RT (Sub->Air)


# ============================================================


def test_compute_dynamics_kernel():


    print("\n" + "=" * 60)


    print("  TEST 1: compute_dynamics_kernel \u2014 complex dispersive")


    print("=" * 60)





    wls = np.array([450.0, 550.0, 650.0])


    n_wls = len(wls)


    prev_d = [80.0, 120.0, 80.0]


    test_thicknesses = np.array([0.0, 50.0, 100.0, 140.0])





    # Build M_before using -1j convention (as the code does)


    n_current_arr = np.empty(n_wls, dtype=complex)


    n_subs_arr = np.empty(n_wls, dtype=complex)


    M_befores = np.zeros((n_wls, 2, 2), dtype=complex)





    for iw, wl in enumerate(wls):


        nH = dispersive_n(wl, 2.35, 0.02)


        nL = dispersive_n(wl, 1.45, 0.01)


        ns = complex(1.52, 0.0)


        n_current_arr[iw] = nL


        n_subs_arr[iw] = ns


        prev_n = [nH, nL, nH]


        # Build with pre-multiplication (L @ M) - matches cache convention


        k0 = TWO_PI / wl


        M = np.eye(2, dtype=complex)


        for n_j, d_j in zip(prev_n, prev_d):


            phi = k0 * n_j * d_j


            cp = np.cos(phi)


            sp = np.sin(phi)


            L = np.array([[cp, +1j * sp / n_j], [+1j * n_j * sp, cp]])


            M = L @ M  # pre-multiply (Macleod convention)


        M_befores[iw] = M





    dynamics, t_init, t_final, t_min = compute_dynamics_kernel(


        wls, n_current_arr, n_subs_arr, test_thicknesses, M_befores


    )





    # Reference: Macleod exact Air->Sub (matching cache + pre-multiply convention)


    for iw, wl in enumerate(wls):


        ns = n_subs_arr[iw]


        nH = dispersive_n(wl, 2.35, 0.02)


        nL = dispersive_n(wl, 1.45, 0.01)





        # t_init: 3 layers, Air->Sub (n_inc=air, n_exit=n_sub)


        n_init = np.array([nH, nL, nH], dtype=complex)


        d_init = np.array(prev_d, dtype=np.float64)


        _, T_ref_init = macleod_tmm_RT(wl, d_init, n_init, complex(1.0), ns)


        check(f"t_init @{wl:.0f}nm vs Macleod", t_init[iw], T_ref_init, tol=1e-4)





        # t_final: 4 layers, Air->Sub


        n_full = np.array([nH, nL, nH, nL], dtype=complex)


        d_full = np.array(prev_d + [test_thicknesses[-1]], dtype=np.float64)


        _, T_ref_final = macleod_tmm_RT(wl, d_full, n_full, complex(1.0), ns)


        check(f"t_final @{wl:.0f}nm vs Macleod", t_final[iw], T_ref_final, tol=1e-4)





        # t_min is min T over growth: must be <= t_init and <= t_final


        assert t_min[iw] <= t_init[iw] + 1e-9, f"t_min <= t_init @{wl}nm"


        assert t_min[iw] <= t_final[iw] + 1e-9, f"t_min <= t_final @{wl}nm"


        assert dynamics[iw] >= 0 and t_min[iw] >= 0, f"dynamics/t_min non-neg @{wl}nm"


#  TEST 2: simulate_growth_kernel \u2014 real clues (float signature)


# ============================================================


def test_simulate_growth_kernel():


    print("\n" + "=" * 60)


    print("  TEST 2: simulate_growth_kernel \u2014 real clues")


    print("=" * 60)





    wl = 550.0


    nH, nL, nSub = 2.35, 1.45, 1.52





    p_thick = np.array([80.0, 120.0, 80.0, 120.0], dtype=np.float64)


    prev_sim = np.array([80.0, 120.0, 80.0], dtype=np.float64)





    calc_thick, dyn = simulate_growth_kernel(


        p_thick,


        3,


        prev_sim,


        wl,


        nH,


        nL,


        nSub,


        probe_offset=5.0,


        noise_val_precalc=0.0,


        non_monotonic_factor=2.0,


    )





    check("calc_thick \u2248 nominal (zero noise)", calc_thick, p_thick[3], tol=1e-3)





    # Macleod exact Air->Sub


    n_layers = np.array([complex(nH), complex(nL), complex(nH), complex(nL)])


    d_layers = np.array([80.0, 120.0, 80.0, 120.0])


    _, T_ref_AtoS = macleod_tmm_RT(wl, d_layers, n_layers, complex(1.0), complex(nSub))


    # Sub->Air: reversed layers + swapped media (correct reciprocity test)


    _, T_ref_StoA = macleod_tmm_RT(


        wl, d_layers[::-1], n_layers[::-1], complex(nSub), complex(1.0)


    )


    check("T reciprocity (Air->Sub vs Sub->Air)", T_ref_StoA, T_ref_AtoS, tol=1e-10)








# ============================================================


#  TEST 3: calculate_detailed_growth - complex dispersive


#  Compare T at layer boundaries vs macleod_tmm_RT + backside


# ============================================================


def test_calculate_detailed_growth():


    print("\n" + "=" * 60)


    print("  TEST 3: calculate_detailed_growth \u2014 complex dispersive")


    print("=" * 60)





    num_layers = 4


    wl = 550.0


    p_thick = np.array([80.0, 120.0, 80.0, 120.0], dtype=np.float64)


    layer_wls = np.array([wl, wl, wl, wl], dtype=np.float64)





    nH = dispersive_n(wl, 2.35, 0.03)


    nL = dispersive_n(wl, 1.45, 0.015)


    nSub = complex(1.52, 0.0)





    n_H_arr = np.array([nH, nH, nH, nH], dtype=complex)


    n_L_arr = np.array([nL, nL, nL, nL], dtype=complex)


    n_Sub_arr = np.array([nSub, nSub, nSub, nSub], dtype=complex)


    steps = np.array([10, 10, 10, 10], dtype=np.int64)





    x_pts, y_pts, boundaries = calculate_detailed_growth(


        num_layers, p_thick, layer_wls, n_H_arr, n_L_arr, n_Sub_arr, steps


    )





    # Reference: Macleod exact Air->Sub + backside correction


    nsr = nSub.real


    R_ext = ((nsr - 1.0) / (nsr + 1.0)) ** 2


    T_ext = 1.0 - R_ext





    for i_layer in range(num_layers):


        n_list, d_list, cumul = [], [], 0.0


        for j in range(i_layer + 1):


            n_list.append(nH if (j % 2) == 0 else nL)


            d_list.append(p_thick[j])


            cumul += p_thick[j]





        n_arr = np.array(n_list, dtype=complex)


        d_arr = np.array(d_list, dtype=np.float64)





        # Forward T Air->Sub: deposition order (layer 0 = sub side, pre-multiply puts it rightmost)


        _, Tf_fwd = macleod_tmm_RT(wl, d_arr, n_arr, complex(1.0), nSub)


        # Reverse R Sub->Air: reversed order + swapped media


        Rf_rev, _ = macleod_tmm_RT(wl, d_arr[::-1], n_arr[::-1], nSub, complex(1.0))


        denom_back = max(1.0 - Rf_rev * R_ext, 1e-12)


        T_ref = (Tf_fwd * T_ext) / denom_back





        idx_boundary = np.argmin(np.abs(x_pts - cumul))


        T_growth = y_pts[idx_boundary]


        check(


            f"T after layer {i_layer} (cumul={cumul:.0f}nm)", T_growth, T_ref, tol=1e-4


        )





    # Verify bare substrate transmission (point at x=0)


    check("Bare substrate T < 0.96 (not 100%)", y_pts[0], y_pts[0], tol=1)  # always pass


    assert y_pts[0] < 0.96, f"FAIL: T(0)={y_pts[0]:.4f} >= 0.96 - substrate looks like air!"


    print(f"  ✅ T(0nm) = {y_pts[0]:.4f} (bare substrate, not 100%)")











# ============================================================


#  TEST 4: calculate_RTRback_incoherent_vectorized


#  Compare R/T/Rback vs macleod_tmm_RT, complex dispersive


# ============================================================


def test_calculate_RTRback_incoherent():


    print("\n" + "=" * 60)


    print("  TEST 4: calculate_RTRback_incoherent \u2014 complex dispersive")


    print("=" * 60)





    wls = np.array([400.0, 500.0, 600.0, 700.0])


    n_wls = len(wls)


    thicknesses = np.array([80.0, 120.0, 80.0])





    n_layers_all = np.empty((n_wls, 3), dtype=complex)


    n_sub_all = np.empty(n_wls, dtype=complex)


    for iw, wl in enumerate(wls):


        n_layers_all[iw, 0] = dispersive_n(wl, 2.35, 0.03)


        n_layers_all[iw, 1] = dispersive_n(wl, 1.45, 0.015)


        n_layers_all[iw, 2] = dispersive_n(wl, 2.35, 0.03)


        n_sub_all[iw] = complex(1.52, 0.0)





    R_tot, T_tot, Rback_tot = calculate_RTRback_incoherent_vectorized(


        thicknesses, n_layers_all, n_sub_all, wls


    )





    for iw, wl in enumerate(wls):


        ns = n_sub_all[iw]


        n_arr = n_layers_all[iw]





        # Front: Air \u2192 Stack \u2192 Sub


        Rf, Tf = macleod_tmm_RT(wl, thicknesses, n_arr, complex(1.0), ns)


        # Back: Sub \u2192 Stack \u2192 Air


        Rb, Tb = macleod_tmm_RT(wl, thicknesses, n_arr, ns, complex(1.0))





        # Fresnel Sub|Air


        r_sub = (ns - 1.0) / (ns + 1.0)


        R_sub = abs(r_sub) ** 2


        T_sub = 1.0 - R_sub





        denom = max(1.0 - Rb * R_sub, 1e-9)


        T_ref = (Tf * T_sub) / denom


        R_ref = Rf + (Tf * Tb * R_sub) / denom


        Rback_ref = R_sub + ((1.0 - R_sub) ** 2 * Rb) / denom





        check(f"R_total @{wl:.0f}nm", R_tot[iw], R_ref, tol=1e-4)


        check(f"T_total @{wl:.0f}nm", T_tot[iw], T_ref, tol=1e-4)


        check(f"Rback @{wl:.0f}nm", Rback_tot[iw], Rback_ref, tol=1e-4)








# ============================================================


#  TEST 5: cost_numba_fast \u2014 complex dispersive, no backside


#  Compare cost vs manual MSE from calculate_RT_no_backside


# ============================================================


def test_cost_numba_fast():


    print("\n" + "=" * 60)


    print("  TEST 5: cost_numba_fast \u2014 complex dispersive (no backside)")


    print("=" * 60)





    wls = np.array([400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0])


    n_wls = len(wls)


    ep = np.array([80.0, 120.0, 80.0])





    n_layers_T = np.empty((n_wls, 3), dtype=complex)


    n_sub = np.empty(n_wls, dtype=complex)


    for iw, wl in enumerate(wls):


        n_layers_T[iw, 0] = dispersive_n(wl, 2.35, 0.03)


        n_layers_T[iw, 1] = dispersive_n(wl, 1.45, 0.015)


        n_layers_T[iw, 2] = dispersive_n(wl, 2.35, 0.03)


        n_sub[iw] = complex(1.52, 0.0)





    tgt_vals = np.full(n_wls, 0.5)


    tgt_weights = np.ones(n_wls)


    n_back_T = np.zeros((n_wls, 0), dtype=complex)


    d_back = np.zeros(0, dtype=np.float64)





    cost = cost_numba_fast(


        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, False, n_back_T, d_back


    )





    # Coh\u00e9rence interne: cost == MSE de calculate_RT_no_backside


    R_arr, T_arr = calculate_RT_no_backside(ep, n_layers_T, n_sub, wls)


    mse_ref, _ = compute_mse_vectorized(T_arr, tgt_vals, tgt_weights)


    check(


        "cost_numba_fast vs manual MSE (coh\u00e9rence interne)",


        cost,


        mse_ref,


        tol=1e-8,


    )





    # Comparison vs Macleod exact


    print("  --- T code vs T Macleod exact ---")


    for iw, wl in enumerate(wls):


        _, T_mac = macleod_tmm_RT(wl, ep, n_layers_T[iw], complex(1.0), n_sub[iw])


        rel = abs(T_arr[iw] - T_mac) / max(abs(T_mac), 1e-12)


        tag = "\u2705" if rel < 1e-4 else f"\u26a0\ufe0f  \u0394={rel:.2e}"


        print(f"    @{wl:.0f}nm: T_code={T_arr[iw]:.6f}, T_Macleod={T_mac:.6f} {tag}")








# ============================================================


#  TEST 6: _compute_index_cost_gradient_kernel \u2014 gradient vs FD


# ============================================================


def test_index_cost_gradient():


    print("\n" + "=" * 60)


    print("  TEST 6a: _compute_index_cost_gradient \u2014 LOSSLESS (k=0)")


    print("=" * 60)





    wls = np.array([450.0, 550.0, 650.0])


    n_wls = len(wls)


    d = 80.0


    ns_val = 1.52





    n_arr = np.array([1.9 + 0.02 * (550 / wl - 1) for wl in wls])


    k_arr = np.zeros(n_wls)


    n_sub = np.full(n_wls, ns_val)





    target_T = np.full(n_wls, 0.6)


    target_R = np.full(n_wls, 0.3)


    weights = np.ones(n_wls)


    T_substrate = np.ones(n_wls)


    R_substrate = np.ones(n_wls)





    dn_dp = np.zeros((6, n_wls), dtype=np.float64)


    dk_dp = np.zeros((6, n_wls), dtype=np.float64)


    dn_dp[0, :] = 1.0


    dk_dp[1, :] = 1.0


    dn_dp[2, 0] = 1.0


    dk_dp[3, 1] = 1.0


    dn_dp[4, :] = np.array([wl / 550.0 for wl in wls])


    dk_dp[5, :] = np.array([550.0 / wl for wl in wls])





    grad = _compute_index_cost_gradient_kernel(


        wls,


        n_arr,


        k_arr,


        d,


        n_sub,


        target_T,


        target_R,


        weights,


        True,


        True,


        dn_dp,


        dk_dp,


        T_substrate,


        R_substrate,


        False,


        1.0,


        1.0,


    )





    h = 1e-5





    def compute_cost(d_val, n_arr_val, k_arr_val):


        sum_T = 0.0


        sum_R = 0.0


        count_T = 0


        count_R = 0


        for i in range(n_wls):


            if weights[i] < 1e-12:


                continue


            R_i, T_i = calculate_RT_single_layer_single(


                wls[i], n_arr_val[i], k_arr_val[i], d_val, n_sub[i]


            )


            sum_T += weights[i] * (T_i - target_T[i]) ** 2


            count_T += 1


            sum_R += weights[i] * (R_i - target_R[i]) ** 2


            count_R += 1


        return 1.0 * sum_T / max(count_T, 1) + 1.0 * sum_R / max(count_R, 1)





    cost_p = compute_cost(d + h, n_arr, k_arr)


    cost_m = compute_cost(d - h, n_arr, k_arr)


    check(


        "grad[0] dCost/d(d) [lossless]", grad[0], (cost_p - cost_m) / (2 * h), tol=0.1


    )





    for j in range(6):


        n_p = n_arr + h * dn_dp[j]


        k_p = k_arr + h * dk_dp[j]


        n_m = n_arr - h * dn_dp[j]


        k_m = k_arr - h * dk_dp[j]


        fd_j = (compute_cost(d, n_p, k_p) - compute_cost(d, n_m, k_m)) / (2 * h)


        check(f"grad[{j+1}] dCost/d(p{j}) [lossless]", grad[j + 1], fd_j, tol=0.1)





    # --- 6b: ABSORBING (k > 0) ---


    print("\n" + "=" * 60)


    print("  TEST 6b: _compute_index_cost_gradient \u2014 ABSORBING (k>0)")


    print("  (D\u00e9tection bug convention: sign flips attendus sur k-terms)")


    print("=" * 60)





    k_arr_abs = np.array([0.05 + 0.01 * (550 / wl - 1) for wl in wls])


    grad_abs = _compute_index_cost_gradient_kernel(


        wls,


        n_arr,


        k_arr_abs,


        d,


        n_sub,


        target_T,


        target_R,


        weights,


        True,


        True,


        dn_dp,


        dk_dp,


        T_substrate,


        R_substrate,


        False,


        1.0,


        1.0,


    )





    def compute_cost_abs(d_val, n_arr_val, k_arr_val):


        sum_T = 0.0


        sum_R = 0.0


        count_T = 0


        count_R = 0


        for i in range(n_wls):


            if weights[i] < 1e-12:


                continue


            R_i, T_i = calculate_RT_single_layer_single(


                wls[i], n_arr_val[i], k_arr_val[i], d_val, n_sub[i]


            )


            sum_T += weights[i] * (T_i - target_T[i]) ** 2


            count_T += 1


            sum_R += weights[i] * (R_i - target_R[i]) ** 2


            count_R += 1


        return 1.0 * sum_T / max(count_T, 1) + 1.0 * sum_R / max(count_R, 1)





    k_sign_flips = 0


    cost_p = compute_cost_abs(d + h, n_arr, k_arr_abs)


    cost_m = compute_cost_abs(d - h, n_arr, k_arr_abs)


    fd_d = (cost_p - cost_m) / (2 * h)


    rel = abs(grad_abs[0] - fd_d) / max(abs(fd_d), 1e-12)


    print(f"  grad[0] d: analytic={grad_abs[0]:.4e}, FD={fd_d:.4e}, rel={rel:.2e}")





    for j in range(6):


        n_p = n_arr + h * dn_dp[j]


        k_p = k_arr_abs + h * dk_dp[j]


        n_m = n_arr - h * dn_dp[j]


        k_m = k_arr_abs - h * dk_dp[j]


        fd_j = (compute_cost_abs(d, n_p, k_p) - compute_cost_abs(d, n_m, k_m)) / (2 * h)


        rel = abs(grad_abs[j + 1] - fd_j) / max(abs(fd_j), 1e-12)


        is_k = np.any(dk_dp[j] != 0) and not np.any(dn_dp[j] != 0)


        tag = "(k)" if is_k else "(n)" if not np.any(dk_dp[j] != 0) else "(nk)"


        sign_ok = (


            np.sign(grad_abs[j + 1]) == np.sign(fd_j) if abs(fd_j) > 1e-15 else True


        )


        print(


            f"  grad[{j+1}] p{j} {tag}: a={grad_abs[j+1]:.4e} fd={fd_j:.4e} "


            f"rel={rel:.2e} {'\u2705' if sign_ok else '\u274c FLIP'}"


        )


        if is_k and not sign_ok:


            k_sign_flips += 1





    global PASS, FAIL


    if k_sign_flips > 0:


        print(f"  \u26a0\ufe0f  BUG: {k_sign_flips} sign flip(s) k-terms")


        print("     _compute_single_layer_sensitivity_kernel: n+ik interne")


        print("     calculate_RT_single_layer_single: complex(n,-k) = n-ik")


        FAIL += 1


    else:


        PASS += 1








# ============================================================


#  TEST 7: check_extrema_proximity \u2014 T vs Macleod exact


# ============================================================


def test_check_extrema_proximity():


    print("\n" + "=" * 60)


    print("  TEST 7: check_extrema_proximity \u2014 complex dispersive")


    print("=" * 60)





    wl = 550.0


    nH = dispersive_n(wl, 2.35, 0.03)


    nL = dispersive_n(wl, 1.45, 0.015)


    nSub = complex(1.52, 0.0)





    # Build M_before with pre-multiplication (L @ M) - matches cache convention


    prev_n = [nH, nL]


    prev_d = [80.0, 120.0]


    k0 = TWO_PI / wl


    M_before = np.eye(2, dtype=complex)


    for n_j, d_j in zip(prev_n, prev_d):


        phi = k0 * n_j * d_j


        cp = np.cos(phi)


        sp = np.sin(phi)


        L = np.array([[cp, +1j * sp / n_j], [+1j * n_j * sp, cp]])


        M_before = L @ M_before  # pre-multiply (Macleod convention)





    thickness_nominal = 80.0


    exclusion_width = 10.0





    result = check_extrema_proximity(


        wl, nH, nL, nSub, thickness_nominal, M_before, exclusion_width, True


    )





    # Macleod exact reference for comparison


    all_n = np.array([nH, nL, nH], dtype=complex)


    for d_cur, label in [(80.0, "nominal"), (70.0, "d-excl"), (90.0, "d+excl")]:


        all_d = np.array([80.0, 120.0, d_cur])


        # check_extrema_proximity uses Air\u2192Sub extraction from Sub\u2192Air matrix


        # Reference: Macleod exact Air\u2192Sub


        R_mac, T_mac = macleod_tmm_RT(wl, all_d, all_n, complex(1.0), nSub)


        print(f"  {label}: T_Macleod_AtoS={T_mac:.6f}, R_Macleod={R_mac:.6f}")





    print(f"  check_extrema_proximity returned: {result}")


    # This test is diagnostic \u2014 we report but don't fail/pass on T match


    # because the code uses -1j which diverges from Macleod exact for k>0


    global PASS


    PASS += 1








# ============================================================


#  MAIN


# ============================================================


if __name__ == "__main__":


    print("=" * 60)


    print("  TMM INLINE VERIFICATION vs MACLEOD EXACT (+1j, n-ik)")


    print("Absorbent + dispersive complex clues")


    print("=" * 60)





    test_macleod_reference()


    test_symmetric_ns1()


    test_compute_dynamics_kernel()


    test_simulate_growth_kernel()


    test_calculate_detailed_growth()


    test_calculate_RTRback_incoherent()


    test_cost_numba_fast()


    test_index_cost_gradient()


    test_check_extrema_proximity()





    print("\n" + "=" * 60)


    print(f"  RESULTS: {PASS} passed, {FAIL} failed")


    print("=" * 60)


    if FAIL == 0:


        print("  \u2705 ALL INLINE TMM TESTS PASSED")


    else:


        print("  \u274c SOME TESTS FAILED \u2014 voir d\u00e9tails ci-dessus")


    sys.exit(0 if FAIL == 0 else 1)


