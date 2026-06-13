#!/usr/bin/env python


"""test_needle_cached.py - Validates needle_scan_cached against the naive


per-position cost_numba_fast approach.





THIS FILE PROTECTS:


  - _certus_physics_impl.py::needle_scan_cached (LOCKED)


  - CERTUS_DESIGN.py::NeedleWorker.run() (dispatch cached/fallback)





Testing:


  1. Correctness: identical best_layer, best_depth, best_cost (10-layer stack)


  2. Performance: cached vs naive benchmark (26-layer stack, ~55× speedup)


  3. Edge cases: single layer, all-thin-layers





Convention: Macleod (+1d), pre-multiply Air->Sub, index 0 = substrate.


Rerun this test MANDATORY after any modification of needle_scan_cached


or Needle logic in NeedleWorker."""





import numpy as np


import sys, os, time
from pathlib import Path





sys.path.insert(0, str(Path(__file__).resolve().parent))





from certus.core._certus_physics_impl import (


    cost_numba_fast,


    needle_scan_cached,


    prepare_targets_vectorized,


)





PASS = 0


FAIL = 0








def check(name, got, ref, tol=1e-8):


    global PASS, FAIL


    if abs(ref) > 1e-12:


        rel = abs(got - ref) / abs(ref)


        ok = rel < tol


    else:


        ok = abs(got - ref) < tol


    if ok:


        PASS += 1


        print(f"  [PASS] {name}: got={got:.10g}  ref={ref:.10g}")


    else:


        FAIL += 1


        print(


            f"  [FAIL] {name}: got={got:.10g}  ref={ref:.10g}  err={abs(got-ref):.3e}"


        )








def build_test_stack(n_layers=10):


    """Build a simple H/L alternating stack for testing."""


    np.random.seed(42)


    wls = np.linspace(400.0, 800.0, 200, dtype=np.float64)





    # H = 2.35, L = 1.45 (typical TiO2/SiO2)


    nH = np.full(len(wls), 2.35 + 0j, dtype=np.complex128)


    nL = np.full(len(wls), 1.45 + 0j, dtype=np.complex128)


    nSub = np.full(len(wls), 1.52 + 0j, dtype=np.complex128)





    # Build layer clues (H, L, H, L, ...)


    n_layers_list = []


    mat_names = []


    for i in range(n_layers):


        if i % 2 == 0:


            n_layers_list.append(nH)


            mat_names.append("H")


        else:


            n_layers_list.append(nL)


            mat_names.append("L")





    n_layers_T = np.ascontiguousarray(np.array(n_layers_list, dtype=np.complex128).T)





    # Random thicknesses 50-150 nm


    ep = np.array(


        [50.0 + 100.0 * np.random.random() for _ in range(n_layers)], dtype=np.float64


    )





    # Build needle material per layer (alternate)


    n_needle_list = []


    needle_mat_names = []


    for i in range(n_layers):


        if mat_names[i] == "H":


            n_needle_list.append(nL)


            needle_mat_names.append("L")


        else:


            n_needle_list.append(nH)


            needle_mat_names.append("H")


    n_needle_T = np.ascontiguousarray(np.array(n_needle_list, dtype=np.complex128).T)





    # Targets: T = 0.5 over full range


    from certus.core._certus_physics_impl import Target





    tgts = [Target(400.0, 800.0, 0.5, 0.5, 1.0)]


    tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)





    scan_mask = np.ones(n_layers, dtype=np.int64)





    return (


        wls,


        n_layers_T,


        n_needle_T,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        scan_mask,


        mat_names,


        needle_mat_names,


        nH,


        nL,


    )








def naive_needle_scan(


    wls,


    n_layers_T,


    nH,


    nL,


    nSub,


    ep,


    tgt_vals,


    tgt_weights,


    mat_names,


    needle_mat_names,


    step_nm=2.0,


    probe=0.01,


):


    """Original naive approach: full TMM per position via cost_numba_fast."""


    N = len(ep)


    W = len(wls)


    mats_nk = {"H": nH, "L": nL}


    n_back_T = np.zeros((W, 0), dtype=np.complex128)


    d_back = np.zeros(0, dtype=np.float64)





    best_layer = -1


    best_depth = 0.0


    best_cost = 1e30





    for i in range(N):


        d_layer = ep[i]


        if d_layer < step_nm + 0.1:


            continue





        needle_mat = needle_mat_names[i]


        n_needle_col = mats_nk[needle_mat].reshape(-1, 1)


        n_current_col = n_layers_T[:, i : i + 1]





        mat_left = n_layers_T[:, :i]


        mat_right = n_layers_T[:, i + 1 :]





        n_test_T = np.hstack(


            [mat_left, n_current_col, n_needle_col, n_current_col, mat_right]


        )


        n_test_T = np.ascontiguousarray(n_test_T)





        z_positions = np.arange(step_nm, d_layer - 0.1, step_nm)





        ep_test = np.empty(N + 2, dtype=np.float64)


        ep_test[:i] = ep[:i]


        ep_test[i + 3 :] = ep[i + 1 :]


        ep_test[i + 1] = probe





        for z in z_positions:


            ep_test[i] = z


            ep_test[i + 2] = d_layer - z





            c = cost_numba_fast(


                ep_test,


                n_test_T,


                nSub,


                wls,


                tgt_vals,


                tgt_weights,


                0.0,


                False,


                n_back_T,


                d_back,


            )





            if c < best_cost:


                best_cost = c


                best_layer = i


                best_depth = z





    return best_layer, best_depth, best_cost








def test_correctness():


    """Test that cached and naive produce identical results."""


    print("=" * 60)


    print("TEST 1: Correctness - cached vs naive")


    print("=" * 60)





    (


        wls,


        n_layers_T,


        n_needle_T,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        scan_mask,


        mat_names,


        needle_mat_names,


        nH,


        nL,


    ) = build_test_stack(10)





    # Naive


    t0 = time.perf_counter()


    naive_layer, naive_depth, naive_cost = naive_needle_scan(


        wls,


        n_layers_T,


        nH,


        nL,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        mat_names,


        needle_mat_names,


    )


    t_naive = time.perf_counter() - t0





    # Cached


    t0 = time.perf_counter()


    cached_layer, cached_depth, cached_cost = needle_scan_cached(


        wls,


        n_layers_T,


        n_needle_T,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        2.0,


        0.01,


        scan_mask,


    )


    t_cached = time.perf_counter() - t0





    print(


        f"  Naive:  layer={naive_layer}, depth={naive_depth:.2f}, cost={naive_cost:.10g}  [{t_naive*1000:.1f} ms]"


    )


    print(


        f"  Cached: layer={cached_layer}, depth={cached_depth:.2f}, cost={cached_cost:.10g}  [{t_cached*1000:.1f} ms]"


    )





    check("best_layer", float(cached_layer), float(naive_layer), tol=0.5)


    check("best_depth", cached_depth, naive_depth, tol=1e-10)


    check("best_cost", cached_cost, naive_cost, tol=1e-8)








def test_performance():


    """Benchmark cached vs naive on a larger stack."""


    print("\n" + "=" * 60)


    print("TEST 2: Performance - 26-layer stack")


    print("=" * 60)





    (


        wls,


        n_layers_T,


        n_needle_T,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        scan_mask,


        mat_names,


        needle_mat_names,


        nH,


        nL,


    ) = build_test_stack(26)





    # Warmup JIT


    _ = needle_scan_cached(


        wls,


        n_layers_T,


        n_needle_T,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        2.0,


        0.01,


        scan_mask,


    )


    _ = naive_needle_scan(


        wls,


        n_layers_T,


        nH,


        nL,


        nSub,


        ep,


        tgt_vals,


        tgt_weights,


        mat_names,


        needle_mat_names,


    )





    # Benchmark cached (3 runs)


    times_cached = []


    for _ in range(3):


        t0 = time.perf_counter()


        cached_layer, cached_depth, cached_cost = needle_scan_cached(


            wls,


            n_layers_T,


            n_needle_T,


            nSub,


            ep,


            tgt_vals,


            tgt_weights,


            2.0,


            0.01,


            scan_mask,


        )


        times_cached.append(time.perf_counter() - t0)





    # Benchmark naive (3 runs)


    times_naive = []


    for _ in range(3):


        t0 = time.perf_counter()


        naive_layer, naive_depth, naive_cost = naive_needle_scan(


            wls,


            n_layers_T,


            nH,


            nL,


            nSub,


            ep,


            tgt_vals,


            tgt_weights,


            mat_names,


            needle_mat_names,


        )


        times_naive.append(time.perf_counter() - t0)





    avg_cached = np.mean(times_cached) * 1000


    avg_naive = np.mean(times_naive) * 1000


    speedup = avg_naive / avg_cached if avg_cached > 0 else float("inf")





    print(f"  Naive:  {avg_naive:.1f} ms  (best of 3: {min(times_naive)*1000:.1f} ms)")


    print(


        f"  Cached: {avg_cached:.1f} ms  (best of 3: {min(times_cached)*1000:.1f} ms)"


    )


    print(f"  Speedup: {speedup:.1f}×")





    # Verify same result


    check("26-layer best_layer", float(cached_layer), float(naive_layer), tol=0.5)


    check("26-layer best_depth", cached_depth, naive_depth, tol=1e-10)


    check("26-layer best_cost", cached_cost, naive_cost, tol=1e-8)








def test_edge_cases():


    """Test edge cases: single layer, thin layers."""


    print("\n" + "=" * 60)


    print("TEST 3: Edge cases")


    print("=" * 60)





    wls = np.linspace(400.0, 800.0, 100, dtype=np.float64)


    nH = np.full(len(wls), 2.35 + 0j, dtype=np.complex128)


    nL = np.full(len(wls), 1.45 + 0j, dtype=np.complex128)


    nSub = np.full(len(wls), 1.52 + 0j, dtype=np.complex128)


    from certus.core._certus_physics_impl import Target





    tgts = [Target(400.0, 800.0, 0.5, 0.5, 1.0)]


    tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)





    # Single layer


    ep1 = np.array([100.0], dtype=np.float64)


    n_layers_T1 = nH.reshape(-1, 1).copy()


    n_needle_T1 = nL.reshape(-1, 1).copy()


    scan_mask1 = np.array([1], dtype=np.int64)





    layer, depth, cost = needle_scan_cached(


        wls,


        n_layers_T1,


        n_needle_T1,


        nSub,


        ep1,


        tgt_vals,


        tgt_weights,


        2.0,


        0.01,


        scan_mask1,


    )


    print(f"  Single layer: layer={layer}, depth={depth:.2f}, cost={cost:.6f}")


    check("single_layer >= 0", float(layer), 0.0, tol=0.5)





    # All layers too thin to scan


    ep_thin = np.array([1.0, 1.0], dtype=np.float64)


    n_layers_T_thin = np.hstack([nH.reshape(-1, 1), nL.reshape(-1, 1)])


    n_needle_T_thin = np.hstack([nL.reshape(-1, 1), nH.reshape(-1, 1)])


    scan_mask_thin = np.array([1, 1], dtype=np.int64)





    layer, depth, cost = needle_scan_cached(


        wls,


        n_layers_T_thin,


        n_needle_T_thin,


        nSub,


        ep_thin,


        tgt_vals,


        tgt_weights,


        2.0,


        0.01,


        scan_mask_thin,


    )


    print(f"  All thin: layer={layer}, depth={depth:.2f}, cost={cost:.6g}")


    check("thin_layers_no_candidate", float(layer), -1.0, tol=0.5)








if __name__ == "__main__":


    print("Needle Scan Cached - Regression & Performance Test")


    print("=" * 60)





    test_correctness()


    test_performance()


    test_edge_cases()





    print("\n" + "=" * 60)


    print(f"RESULTS:  {PASS} passed,  {FAIL} failed")


    if FAIL == 0:


        print("ALL TESTS PASSED ✓")


    else:


        print("SOME TESTS FAILED ✗")


    print("=" * 60)


