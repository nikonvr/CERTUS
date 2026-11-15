"""Nested parallelism in STRAT's robustness pool: 8 Python threads, each calling parallel Numba kernels.

`_run_robustness_tests_parallel` runs `cpu_count() // 2` Python threads; each calls `simulate_stack_robustness_batch`
and `compute_batch_rmse` (prange over runs) with Numba's default thread count. This probe times one batch of tasks
(growth + scoring of the real ELITE plan, 150 runs) on the same pool, with `numba.set_num_threads(k)` set in every pool
thread for k in `--inner`, and checks that the results are bit-identical whatever k.

    python reports/audit_oms5100_2026-11-15/profil_strat_complet/probe_threads.py [--tasks 32] [--inner 16,4,2,1]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.environ.get("NUMBA_THREADING_LAYER") == "tbb":  # pip's tbb puts its DLLs in <prefix>/Library/bin, off the search path
    _tbb = Path(sys.prefix) / "Library" / "bin"
    os.add_dll_directory(str(_tbb))
    os.environ["PATH"] = str(_tbb) + os.pathsep + os.environ["PATH"]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import numba  # noqa: E402
import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402

from certus.physics.certus_strat_batch import (  # noqa: E402
    calculate_RT_batch_kernel,
    compute_batch_rmse,
    corridor_wl_range,
    simulate_stack_robustness_batch,
)

ap = argparse.ArgumentParser()
ap.add_argument("--tasks", type=int, default=32)
ap.add_argument("--runs", type=int, default=150)
ap.add_argument("--inner", default="16,4,2,1")
ap.add_argument("--job", default=str(ROOT / "reports/ANALYSE_claude_2026-10-22/resultats/brut/diag_plancher_panel/"
                                     "48c_premium_s42/jobs.json") + ":0")
args = ap.parse_args()

params = seq.load_params(ROOT / "example" / "example_strat" / "JSON-strat-example.json")
th = np.ascontiguousarray(seq.nominal_thicknesses(params), dtype=np.float64)
n = len(th)
path, _, index = args.job.rpartition(":")
plan = json.loads(Path(path).read_text(encoding="utf-8"))[int(index)]["plan"]
lw = np.zeros(n)
for b in plan["blocks"]:
    lw[b["start"]:b["end"]] = b["wavelength"]
rate = np.zeros(n, dtype=np.bool_)
rate[[int(k) for k in plan.get("rate_layers", [])]] = True
nH = np.array([seq.material_index(params, params["nH_id"], w) for w in lw])
nL = np.array([seq.material_index(params, params["nL_id"], w) for w in lw])
nS = np.array([seq.material_index(params, params["nSub_id"], w) for w in lw])
lo, hi = (float(x) for x in params["wl_range"])
wls = np.arange(lo, hi + 0.5, 1.0)
nH_w = np.array([seq.material_index(params, params["nH_id"], w) for w in wls])
nL_w = np.array([seq.material_index(params, params["nL_id"], w) for w in wls])
nS_w = np.array([seq.material_index(params, params["nSub_id"], w) for w in wls])
flat = np.where((np.arange(n) % 2 == 0)[None, :], nH_w[:, None], nL_w[:, None]).astype(np.complex128)
T_nom = calculate_RT_batch_kernel(wls, nH_w, nL_w, nS_w, th.reshape(1, -1))[1][0]
c_lo, c_hi = corridor_wl_range(wls, lw)
A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
h = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio  # noqa: E402

probe_offset = compute_probe_offset_nm_from_ratio(params)


def task(seed: int) -> np.ndarray:
    stop = A * np.clip(np.random.default_rng(seed).normal(0.0, 1.0 / 3.0, size=(args.runs, n)), -1.0, 1.0)
    res = simulate_stack_robustness_batch(
        th, lw, nH, nL, nS, stop, probe_offset, 2.0, 0, np.full(n, A), seed, h * A, 0.0, 0.0, 0.00375, seed + 1, True,
        1, 0.005, seed + 2, c_lo, c_hi, rate, None, None, False, False, 2,
    )[0]
    rm = compute_batch_rmse(np.ascontiguousarray(res), wls, nH_w, nL_w, nS_w, T_nom, flat, None, 0.005, seed + 2, c_lo,
                            c_hi)
    return np.concatenate([res.ravel(), rm])


workers = max(1, multiprocessing.cpu_count() // 2)
print(f"cpu={multiprocessing.cpu_count()} pool={workers} tasks={args.tasks} runs={args.runs} "
      f"layer={numba.config.THREADING_LAYER} default_threads={numba.get_num_threads()}", flush=True)
task(0)  # compile
reference = None
for k in (int(x) for x in args.inner.split(",")):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers, initializer=numba.set_num_threads,
                                               initargs=(k,)) as ex:
        t0 = time.perf_counter()
        outs = list(ex.map(task, range(100, 100 + args.tasks)))
        wall = time.perf_counter() - t0
    stacked = np.stack(outs)
    same = reference is None or np.array_equal(stacked.view(np.int64), reference.view(np.int64))
    reference = stacked if reference is None else reference
    import hashlib

    digest = hashlib.sha256(stacked.tobytes()).hexdigest()[:16]
    print(f"inner={k:2d}: {wall:.2f} s for {args.tasks} tasks, bit-identical to the first: {same}, sha256 {digest}",
          flush=True)
