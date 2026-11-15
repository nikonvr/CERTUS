"""Chantier 44: STRAT's production batch with and without `stack_carry`, on the 48-layer reference.

Same inputs on both sides (the probe's synthetic plan, reading noise at A, index corridor and photometric curvature as in
production, `arming` = 2). Reports, per noise level: the largest gap in ulp and in relative terms over the five returned
arrays, the number of entries that differ, the runs whose crash status flips, and the wall time of each side
(best of `--repeat`, `--threads` Numba threads).

    python reports/audit_oms5100_2026-11-15/portage_matrices/compare_carry.py [--runs 2000] [--threads 1]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument("--runs", type=int, default=2000)
ap.add_argument("--repeat", type=int, default=3)
ap.add_argument("--threads", type=int, default=1)
ap.add_argument("--plan", default=None)
ap.add_argument("--job", default=None, help="FILE:INDEX of a jobs.json entry (blocks and Rate layers of a real plan)")
args = ap.parse_args()
os.environ["NUMBA_NUM_THREADS"] = str(args.threads)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import json  # noqa: E402

import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402

from certus.core.certus_strat_robustness import INDEX_CORRIDOR_DEFAULT  # noqa: E402
from certus.physics.certus_strat_batch import corridor_wl_range, simulate_stack_robustness_batch  # noqa: E402
from certus.physics.certus_strat_growth import PHOTOMETRIC_CURVATURE_AMP  # noqa: E402
from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio  # noqa: E402


def ulp_gap(a: np.ndarray, b: np.ndarray) -> tuple[int, float, int]:
    """Largest gap in ulp, largest relative gap, number of entries whose bits differ (NaN on both sides counts equal)."""
    a = np.ascontiguousarray(a, dtype=np.float64).ravel()
    b = np.ascontiguousarray(b, dtype=np.float64).ravel()
    diff = a.view(np.int64) != b.view(np.int64)
    both_nan = np.isnan(a) & np.isnan(b)
    diff &= ~both_nan
    if not diff.any():
        return 0, 0.0, 0
    ia, ib = a.view(np.int64)[diff], b.view(np.int64)[diff]
    # map to a monotonic integer line so that the distance counts representable doubles
    ia = np.where(ia < 0, np.iinfo(np.int64).min - ia, ia)
    ib = np.where(ib < 0, np.iinfo(np.int64).min - ib, ib)
    ulp = int(np.max(np.abs(ia.astype(object) - ib.astype(object))))
    rel = float(np.max(np.abs(a[diff] - b[diff]) / np.maximum(np.abs(a[diff]), 1e-300)))
    return ulp, rel, int(diff.sum())


params = seq.load_params(ROOT / "example" / "example_strat" / "JSON-strat-example.json")
th = np.ascontiguousarray(seq.nominal_thicknesses(params), dtype=np.float64)
n = len(th)
blocks = json.loads(Path(args.plan).read_text()) if args.plan else [
    [b, min(b + 6, n), 550.0 if k % 2 == 0 else 600.0] for k, b in enumerate(range(0, n, 6))]
rate = None
if args.job:
    path, _, index = args.job.rpartition(":")
    plan = json.loads(Path(path).read_text(encoding="utf-8"))[int(index)]["plan"]
    blocks = [[b["start"], b["end"], b["wavelength"]] for b in plan["blocks"]]
    rate = np.zeros(n, dtype=np.bool_)
    rate[[int(k) for k in plan.get("rate_layers", [])]] = True
lw = np.zeros(n)
for b0, b1, wl in blocks:
    lw[int(b0):int(b1)] = float(wl)
nH = np.array([seq.material_index(params, params["nH_id"], w) for w in lw])
nL = np.array([seq.material_index(params, params["nL_id"], w) for w in lw])
nS = np.array([seq.material_index(params, params["nSub_id"], w) for w in lw])
A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
h = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
lo, hi = (float(x) for x in params["wl_range"])
c_lo, c_hi = corridor_wl_range(np.arange(lo, hi + 0.5, 1.0), lw)
corridor = float(params.get("index_corridor", INDEX_CORRIDOR_DEFAULT) or 0.0)
curv = float(params.get("photometric_curvature_amp", PHOTOMETRIC_CURVATURE_AMP) or 0.0)
probe_offset = compute_probe_offset_nm_from_ratio(params)
print(f"layers={n} runs={args.runs} threads={args.threads} A={A:g} h={h:g} corridor={corridor:g} curvature={curv:g}",
      flush=True)

for level, f in enumerate((0.5, 1.0, 2.0)):
    stop = A * f * np.clip(np.random.default_rng([42, level]).normal(0.0, 1.0 / 3.0, size=(args.runs, n)), -1.0, 1.0)

    def run(carry: bool, stop=stop, f=f, level=level):
        return simulate_stack_robustness_batch(
            th, lw, nH, nL, nS, stop, probe_offset, 2.0, 0, np.full(n, A * f), 7919 + level, h * A * f, 0.0, 0.0, curv,
            31 + level, True, 1, corridor, 53 + level, c_lo, c_hi, rate, None, None, False, False, 2, carry,
        )

    out = {}
    for carry in (False, True):
        out[carry] = run(carry)  # compile on the first level
        best = float("inf")
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            run(carry)
            best = min(best, time.perf_counter() - t0)
        out[(carry, "s")] = best
    gaps = [ulp_gap(a, b) for a, b in zip(out[False], out[True], strict=True)]
    crash_off = (out[False][0] > 1e5).any(axis=1)
    crash_on = (out[True][0] > 1e5).any(axis=1)
    print(f"level {f:g}: carry off {out[(False, 's')]:.3f} s, on {out[(True, 's')]:.3f} s, "
          f"x{out[(False, 's')] / out[(True, 's')]:.2f} | crash off {crash_off.mean():.4f} on {crash_on.mean():.4f}, "
          f"flipped runs {int((crash_off != crash_on).sum())}", flush=True)
    for name, (ulp, rel, count) in zip(("thick", "dyn", "m_level", "m_missed", "m_fab"), gaps, strict=True):
        print(f"    {name:9s} differing={count:7d} max_ulp={ulp} max_rel={rel:.3g}", flush=True)
