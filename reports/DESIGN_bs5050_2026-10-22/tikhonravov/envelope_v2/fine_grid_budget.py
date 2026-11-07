"""Referee audit of the OE paper (2026-11-03): does the 0.001-nm polish catch up with the pole charge when it gets at
least the charge's budget?

Same polish as grid_study.polish (trust region, tolerances 1e-15) on the 270 007 points of 0.001 nm steps, from the
0.005-nm design of threeline_refine_probe_trub101.csv, with max_nfev = BUDGET (default 1200, the 40 x 30 iterations of
the charge) instead of grid_study.NFEV = 300. Judged as threeline_refine_probe.report (1, 0.005, 0.001 and 0.0002 nm,
peaks above 1 % on the 0.0002 nm scan), with the evaluations used, the solver status and |E|^2 at the highest peak.
Design to fine_grid_budget_trub101.csv.
usage: SEARCH_TARGET=threeline NUMBA_NUM_THREADS=8 python fine_grid_budget.py [BUDGET]
"""

from __future__ import annotations

import csv
import sys
import time

import bs5050_grid as bg
import field_grid_link as fl
import grid_study as gs
import numpy as np
import threeline_refine_probe as rp
from scipy.optimize import least_squares

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 1200


def main() -> None:
    r = next(x for x in csv.DictReader(open("threeline_refine_probe_trub101.csv", encoding="utf-8"))
             if float(x["grid_nm"]) == 0.005)
    seq, d0 = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    t0 = time.time()
    rp.report("start (polished on 0.005 nm)", seq, d0, t0)
    g = gs.kernel_grid(*gs.band_grid(0.001))
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = bg.res_jac(seq, x, g)[:2]
        return memo[key]

    t1 = time.time()
    sol = least_squares(lambda x: both(x)[0], np.maximum(d0, gs.FLOOR), jac=lambda x: both(x)[1],
                        bounds=(gs.FLOOR, np.inf), method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15,
                        max_nfev=BUDGET)
    d = np.maximum(sol.x, gs.FLOOR)
    print(f"polish on 0.001 nm: {sol.nfev} evaluations, {sol.njev} Jacobians, status {sol.status} ({sol.message}), "
          f"{time.time() - t1:.0f} s", flush=True)
    rp.report(f"polished on 0.001 nm, budget {BUDGET}", seq, d, t0)
    pk = rp.peaks(seq, d)
    if pk:
        h, x, fw = pk[0]
        e2 = fl.e2max([fl.N_IDX[m] for m in seq], d, x)[0]
        print(f"highest peak {100 * h:.2f} % at {x:.4f} nm, FWHM {fw:.4f} nm, max |E|^2 {e2:.0f}", flush=True)
    with open("fine_grid_budget_trub101.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["grid_nm", "budget", "nfev", "seq", "d_nm"])
        w.writeheader()
        w.writerow({"grid_nm": 0.001, "budget": BUDGET, "nfev": sol.nfev, "seq": seq,
                    "d_nm": " ".join(f"{v:.6f}" for v in d)})


if __name__ == "__main__":
    main()
