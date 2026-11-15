"""PROFILE STRAT'S GROWTH KERNEL BY STAGE (chantier 44, step 1 of the OMS 5100 audit, section 8).

`simulate_growth_kernel` is timed whole, and each of its stages is timed alone, on the same inputs, at several layer
depths of the reference design (the 48-layer dichroic of `example/example_strat/JSON-strat-example.json`):

    matrices   two `_stack_matrix` (real and nominal) and the `_stack_matrix_pair` under the replayed window
    niveau     `_monotonicity_scan` and `_frozen_trigger_level`
    balayage   `_fill_history_signal` + `_fill_current_signal`, reading noise OFF (the trigonometry of the scan)
    bruit      the same with the reading noise ON, minus `balayage`
    detection  `_read_poem_anchors` + `_level_reachability`
    inversion  `_invert_thickness_from_probes` (production) ; `inversion_exacte` = `_invert_thickness_exact` (D97 option)
    ancres     `_exact_poem_anchors` (D96 option, not on the production path)

Each stage runs inside a compiled loop (no Python dispatch per call): the figure is microseconds per call, the best of
`--repeat` timings of `--reps` calls. The sum of the production stages is printed next to the whole kernel: a large gap
means a stage is missing from the list or the loop is not representative. No line of `certus/` is touched.

Production path: coarse grid, smoothing 1, parabolic stop, no exact anchors, `arming` = 2, reading noise at A, threshold
`tp_hysteresis_factor` x A. The plan is synthetic (blocks of `--block` layers, alternately at `--wl` and `--wl2`) unless `--plan`
gives a JSON list of `[start, end, wl]` blocks: the cost per call depends on the depth and on the replayed window (at most
`MAX_LOOKBACK_VAL` layers), not on which plan is good.

The batch (`simulate_stack_robustness_batch`, parallel) is also timed on `--runs` runs at the middle noise level, wall
clock, so the per-call figure can be set against what a search actually pays.

    python scripts/probe_strat_kernel_profile.py [--depths 3,12,24,36,47] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402
from numba import njit  # noqa: E402

from certus.physics.certus_strat_growth import (  # noqa: E402
    _frozen_trigger_level,
    _level_reachability,
    _monotonicity_scan,
    _read_poem_anchors,
    _scan_window,
    simulate_growth_kernel,
)
from certus.physics.certus_strat_readings import (  # noqa: E402
    _exact_poem_anchors,
    _fill_current_signal,
    _fill_history_signal,
    _invert_thickness_exact,
    _invert_thickness_from_probes,
    _stack_matrix,
    _stack_matrix_pair,
)

DEFAULT_CONFIG = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
OUT_DIR = ROOT / "reports" / "audit_oms5100_2026-11-15" / "profil_noyau"


@njit(cache=False)
def _signals(wl, nS, nH, nL, th_r, th_n, i, block_start, noise_on, sig, seed, run):
    j0, n_hist, npts_cur, d_max, n_tot = _scan_window(block_start, i, 0, th_n[i])
    Ts_r = np.zeros(n_tot, dtype=np.float64)
    Ts_n = np.zeros(n_tot, dtype=np.float64)
    R00, R01, R10, R11, Q00, Q01, Q10, Q11 = _stack_matrix_pair(wl, nH, nL, th_r, nH, nL, th_n, 0, j0)
    idx, R00, R01, R10, R11, Q00, Q01, Q10, Q11 = _fill_history_signal(
        wl, nS, nH, nL, nH, nL, th_r, th_n, j0, i, R00, R01, R10, R11, Q00, Q01, Q10, Q11, Ts_r, Ts_n,
        noise_on, sig, seed, run,
    )
    _fill_current_signal(
        wl, nS, nH, nL, nH, nL, i, R00, R01, R10, R11, Q00, Q01, Q10, Q11, d_max, npts_cur, n_hist, idx, Ts_r, Ts_n,
        noise_on, sig, seed, run,
    )
    return Ts_r, Ts_n, j0, n_hist, npts_cur, d_max, n_tot


@njit(cache=False)
def bench_matrices(reps, wl, nH, nL, th_r, th_n, i, block_start):
    acc = 0.0
    for _ in range(reps):
        a00, _a01, _a10, _a11 = _stack_matrix(wl, nH, nL, th_r, 0, i)
        b00, _b01, _b10, _b11 = _stack_matrix(wl, nH, nL, th_n, 0, i)
        j0, _h, _p, _d, _t = _scan_window(block_start, i, 0, th_n[i])
        pair = _stack_matrix_pair(wl, nH, nL, th_r, nH, nL, th_n, 0, j0)
        acc += a00.real + b00.real + pair[0].real
    return acc


@njit(cache=False)
def bench_level(reps, wl, nS, nH, nL, th_r, th_n, i):
    M = _stack_matrix(wl, nH, nL, th_r, 0, i)
    N = _stack_matrix(wl, nH, nL, th_n, 0, i)
    n_cur = nH if i % 2 == 0 else nL
    acc = 0.0
    for _ in range(reps):
        _nm, T_mono = _monotonicity_scan(wl, n_cur, th_n[i], nS, M[0], M[1], M[2], M[3], N[0], N[1], N[2], N[3])
        acc += _frozen_trigger_level(wl, n_cur, th_n[i], nS, N[0], N[1], N[2], N[3], T_mono[4])
    return acc


@njit(cache=False)
def bench_scan(reps, wl, nS, nH, nL, th_r, th_n, i, block_start, noise_on, sig, seed):
    """The two fill passes only: the pair matrix under the window is counted in `matrices`, so it is built once here."""
    j0, n_hist, npts_cur, d_max, n_tot = _scan_window(block_start, i, 0, th_n[i])
    P00, P01, P10, P11, S00, S01, S10, S11 = _stack_matrix_pair(wl, nH, nL, th_r, nH, nL, th_n, 0, j0)
    acc = 0.0
    for r in range(reps):
        Ts_r = np.zeros(n_tot, dtype=np.float64)
        Ts_n = np.zeros(n_tot, dtype=np.float64)
        idx, R00, R01, R10, R11, Q00, Q01, Q10, Q11 = _fill_history_signal(
            wl, nS, nH, nL, nH, nL, th_r, th_n, j0, i, P00, P01, P10, P11, S00, S01, S10, S11, Ts_r, Ts_n,
            noise_on, sig, seed, r,
        )
        _fill_current_signal(
            wl, nS, nH, nL, nH, nL, i, R00, R01, R10, R11, Q00, Q01, Q10, Q11, d_max, npts_cur, n_hist, idx, Ts_r,
            Ts_n, noise_on, sig, seed, r,
        )
        acc += Ts_r[n_tot - 1]
    return acc


@njit(cache=False)
def _target(wl, nS, nH, nL, th_r, th_n, i, Ts_r, Ts_n, j0, n_tot, idx_nom_stop, hyst):
    """The stop level as the kernel computes it (POEM when it holds, the frozen nominal level otherwise)."""
    N = _stack_matrix(wl, nH, nL, th_n, 0, i)
    M = _stack_matrix(wl, nH, nL, th_r, 0, i)
    n_cur = nH if i % 2 == 0 else nL
    _nm, T_mono = _monotonicity_scan(wl, n_cur, th_n[i], nS, M[0], M[1], M[2], M[3], N[0], N[1], N[2], N[3])
    target_nominal = _frozen_trigger_level(wl, n_cur, th_n[i], nS, N[0], N[1], N[2], N[3], T_mono[4])
    res = _read_poem_anchors(i, j0, Ts_r, Ts_n, n_tot, idx_nom_stop, hyst, True, False)
    T_prev_nom, T_last_nom, T_prev_real, T_last_real, poem_ok = res[4], res[5], res[6], res[7], res[8]
    if poem_ok:
        p = (target_nominal - T_prev_nom) / (T_last_nom - T_prev_nom)
        return T_prev_real + p * (T_last_real - T_prev_real), poem_ok, T_prev_real, T_last_real, T_prev_nom, T_last_nom
    return target_nominal, poem_ok, T_prev_real, T_last_real, T_prev_nom, T_last_nom


@njit(cache=False)
def bench_detection(reps, wl, nS, nH, nL, th_r, th_n, i, block_start, sig, seed, hyst):
    Ts_r, Ts_n, j0, n_hist, npts_cur, d_max, n_tot = _signals(wl, nS, nH, nL, th_r, th_n, i, block_start, True, sig, seed, 0)
    idx_nom_stop = n_hist + round((npts_cur - 1) * th_n[i] / d_max)
    target = _target(wl, nS, nH, nL, th_r, th_n, i, Ts_r, Ts_n, j0, n_tot, idx_nom_stop, hyst)[0]
    acc = 0.0
    for _ in range(reps):
        res = _read_poem_anchors(i, j0, Ts_r, Ts_n, n_tot, idx_nom_stop, hyst, True, False)
        m, ok = _level_reachability(Ts_r, n_tot, n_hist, idx_nom_stop, hyst, target)
        acc += res[2] + m + (1.0 if ok else 0.0)
    return acc


@njit(cache=False)
def bench_inversion(reps, wl, nS, nH, nL, th_r, th_n, i, block_start, sig, seed, hyst, probe_offset, exact):
    Ts_r, Ts_n, j0, n_hist, npts_cur, d_max, n_tot = _signals(wl, nS, nH, nL, th_r, th_n, i, block_start, True, sig, seed, 0)
    idx_nom_stop = n_hist + round((npts_cur - 1) * th_n[i] / d_max)
    target = _target(wl, nS, nH, nL, th_r, th_n, i, Ts_r, Ts_n, j0, n_tot, idx_nom_stop, hyst)[0]
    M = _stack_matrix(wl, nH, nL, th_r, 0, i)
    n_cur = nH if i % 2 == 0 else nL
    acc = 0.0
    for _ in range(reps):
        if exact:
            acc += _invert_thickness_exact(wl, n_cur, th_n[i], probe_offset, nS, M[0], M[1], M[2], M[3], 1.0, 0.0, 0.0,
                                           None, i, target)
        else:
            acc += _invert_thickness_from_probes(wl, n_cur, th_n[i], probe_offset, nS, M[0], M[1], M[2], M[3], 1.0, 0.0,
                                                 0.0, None, i, target)
    return acc


@njit(cache=False)
def bench_anchors(reps, wl, nS, nH, nL, th_r, th_n, i, block_start, sig, seed, hyst):
    Ts_r, Ts_n, j0, n_hist, npts_cur, d_max, n_tot = _signals(wl, nS, nH, nL, th_r, th_n, i, block_start, True, sig, seed, 0)
    idx_nom_stop = n_hist + round((npts_cur - 1) * th_n[i] / d_max)
    t = _target(wl, nS, nH, nL, th_r, th_n, i, Ts_r, Ts_n, j0, n_tot, idx_nom_stop, hyst)
    acc = 0.0
    if not t[1]:
        return -1.0  # POEM does not hold at this depth: the option has nothing to read
    for _ in range(reps):
        a = _exact_poem_anchors(wl, nS, nH, nL, nH, nL, 0, j0, i, th_r, th_n, n_hist, npts_cur, d_max, Ts_r, Ts_n, n_tot,
                                1.0, 0.0, None, t[2], t[3], t[4], t[5])
        acc += a[0]
    return acc


@njit(cache=False)
def bench_kernel(reps, th_n, i, th_r, wl, nH, nL, nS, probe_offset, nm_factor, block_start, sig, seed, hyst):
    prev = th_r[:i]
    acc = 0.0
    for r in range(reps):
        val, _dyn, _ml, _mm, _mf = simulate_growth_kernel(
            th_n, i, prev, wl, nH, nL, nS, probe_offset, 0.0, nm_factor, 0, block_start, sig, seed, r, hyst,
            1.0, 0.0, 0.0, True, 1, nH, nL, False, None, 0, 0.0, None, False, False, 2,
        )
        acc += val
    return acc


def best_us(fn, args, reps, repeat):
    fn(1, *args)  # compile
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn(reps, *args)
        best = min(best, time.perf_counter() - t0)
    return 1e6 * best / reps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--depths", default="3,12,24,36,47")
    ap.add_argument("--wl", type=float, default=550.0)
    ap.add_argument("--wl2", type=float, default=600.0)
    ap.add_argument("--block", type=int, default=6)
    ap.add_argument("--plan", default=None, help="JSON list of [start, end, wl] blocks")
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--runs", type=int, default=200, help="runs of the batch timing (0: skip it)")
    ap.add_argument("--json", default=str(OUT_DIR / "profil.json"))
    args = ap.parse_args()

    from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio

    params = seq.load_params(Path(args.config))
    th_n = np.ascontiguousarray(seq.nominal_thicknesses(params), dtype=np.float64)
    n = len(th_n)
    th_r = np.ascontiguousarray(th_n * (1.0 + 0.005 * np.random.default_rng(44).standard_normal(n)))
    A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    h = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    probe_offset = compute_probe_offset_nm_from_ratio(params)
    nm_factor = float(params.get("non_monotonic_error_factor", 2.0))
    # Synthetic plan: blocks of `--block` layers alternating between `--wl` and `--wl2`, since the batch opens a block
    # only where the wavelength changes.
    blocks = json.loads(Path(args.plan).read_text()) if args.plan else [
        [b, min(b + args.block, n), args.wl if k % 2 == 0 else args.wl2] for k, b in enumerate(range(0, n, args.block))]
    lw = np.zeros(n)
    for b0, b1, wl in blocks:
        lw[int(b0):int(b1)] = float(wl)
    # The block starts as `simulate_stack_robustness_batch` derives them (no Rate layer, no witness swap).
    bstart = np.zeros(n, dtype=np.int64)
    for k in range(1, n):
        bstart[k] = k if abs(lw[k] - lw[k - 1]) > 1e-6 else bstart[k - 1]
    seed = 4401
    sig, hyst = A, h * A
    print(f"config={Path(args.config).name} layers={n} A={A:g} h={h:g} probe_offset={probe_offset:.4g} nm "
          f"blocks={len(blocks)} reps={args.reps} repeat={args.repeat} python={sys.version.split()[0]}", flush=True)

    rows = []
    for i in (int(x) for x in args.depths.split(",") if x.strip()):
        i = min(i, n - 1)
        wl = float(lw[i])
        nH = seq.material_index(params, params["nH_id"], wl)
        nL = seq.material_index(params, params["nL_id"], wl)
        nS = seq.material_index(params, params["nSub_id"], wl)
        bs = int(bstart[i])
        common = (wl, nS, nH, nL, th_r, th_n, i, bs)
        row = {"layer": i, "wl": wl, "block_start": bs}
        row["matrices"] = best_us(bench_matrices, (wl, nH, nL, th_r, th_n, i, bs), args.reps, args.repeat)
        row["niveau"] = best_us(bench_level, (wl, nS, nH, nL, th_r, th_n, i), args.reps, args.repeat)
        scan_off = best_us(bench_scan, (*common, False, sig, seed), args.reps, args.repeat)
        scan_on = best_us(bench_scan, (*common, True, sig, seed), args.reps, args.repeat)
        row["balayage"] = scan_off
        row["bruit"] = scan_on - scan_off
        row["detection"] = best_us(bench_detection, (*common, sig, seed, hyst), args.reps, args.repeat)
        row["inversion"] = best_us(bench_inversion, (*common, sig, seed, hyst, probe_offset, False), args.reps, args.repeat)
        row["inversion_exacte"] = best_us(bench_inversion, (*common, sig, seed, hyst, probe_offset, True), args.reps,
                                          args.repeat)
        row["ancres"] = best_us(bench_anchors, (*common, sig, seed, hyst), args.reps, args.repeat)
        row["noyau"] = best_us(bench_kernel, (th_n, i, th_r, wl, nH, nL, nS, probe_offset, nm_factor, bs, sig, seed, hyst),
                               args.reps, args.repeat)
        row["somme_production"] = sum(row[k] for k in ("matrices", "niveau", "balayage", "bruit", "detection", "inversion"))
        rows.append(row)
        print("  " + " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()), flush=True)

    batch = None
    if args.runs:
        from certus.core.certus_strat_robustness import INDEX_CORRIDOR_DEFAULT
        from certus.physics.certus_strat_batch import corridor_wl_range, simulate_stack_robustness_batch
        from certus.physics.certus_strat_growth import PHOTOMETRIC_CURVATURE_AMP

        nH_v = np.array([seq.material_index(params, params["nH_id"], w) for w in lw])
        nL_v = np.array([seq.material_index(params, params["nL_id"], w) for w in lw])
        nS_v = np.array([seq.material_index(params, params["nSub_id"], w) for w in lw])
        lo, hi = (float(x) for x in params["wl_range"])
        wls = np.arange(lo, hi + 0.5, 1.0)
        c_lo, c_hi = corridor_wl_range(wls, lw)
        corridor = float(params.get("index_corridor", INDEX_CORRIDOR_DEFAULT) or 0.0)
        curvature = float(params.get("photometric_curvature_amp", PHOTOMETRIC_CURVATURE_AMP) or 0.0)
        stop = A * np.clip(np.random.default_rng(45).normal(0.0, 1.0 / 3.0, size=(args.runs, n)), -1.0, 1.0)

        def run_batch():
            return simulate_stack_robustness_batch(
                th_n, lw, nH_v, nL_v, nS_v, stop, probe_offset, nm_factor, 0, np.full(n, A), seed, hyst, 0.0, 0.0,
                curvature, seed + 1, True, 1, corridor, seed + 2, c_lo, c_hi, None, None, None, False, False, 2,
            )

        run_batch()  # compile
        walls = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            run_batch()
            walls.append(time.perf_counter() - t0)
        from numba import get_num_threads

        threads = get_num_threads()
        batch = {"runs": args.runs, "layers": n, "wall_s": min(walls), "threads": threads,
                 "us_per_call_wall": 1e6 * min(walls) / (args.runs * n),
                 "us_per_call_cpu": 1e6 * min(walls) * threads / (args.runs * n)}
        print(f"  batch: {args.runs} runs x {n} layers, {min(walls):.3f} s wall on {threads} threads, "
              f"{batch['us_per_call_wall']:.2f} us/call wall, {batch['us_per_call_cpu']:.2f} us/call x threads", flush=True)

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"config": Path(args.config).name, "blocks": blocks, "A": A, "h": h, "rows": rows,
                               "batch": batch}, indent=1), encoding="utf-8")
    print(f"JSON={out}", flush=True)


if __name__ == "__main__":
    main()
