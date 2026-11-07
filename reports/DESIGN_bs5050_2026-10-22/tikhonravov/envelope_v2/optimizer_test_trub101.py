"""Do the hidden resonances hold the optimization? (2026-11-01 evening, owner's hypothesis for the method paper; the
landscape, landscape_trub101.py, shows a wall of the nominal MF wherever a resonance crosses a grid point.)
From the same starts -- Trubetskov's 101-layer design (re-created, fig4_2020_designs.csv row 'deep') with every
thickness multiplied by 1 + SIGMA N(0, 1), seeds 1..SEEDS -- two optimizations of equal budget, ROUNDS bursts of 30
trust-region iterations: 'nominal' on the 277 points only (threeline_track.polish with no peak), 'pole' with each
resonance found from the complex plane and charged by its height at its pole (TRACK_DETECT=complex). Every round is
judged on the nominal and on the resolved (0.001 nm) grid, with the number and the highest of the resonances found from
the complex plane. Rows to optimizer_test_trub101.csv.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex python optimizer_test_trub101.py SIGMA SEEDS ROUNDS WORKERS
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import grid_study as gs
import numpy as np
import threeline_track as tt

SIGMA, SEEDS, ROUNDS, WORKERS = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
#: env OPTTEST_OUT (2026-11-03, the detector redo): the output file; unset, as before
OUT = os.environ.get("OPTTEST_OUT", "optimizer_test_trub101.csv")


def run(task) -> list[dict]:
    method, seed = task
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d0 = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    d = np.maximum(d0 * (1.0 + SIGMA * np.random.default_rng(seed).normal(size=len(d0))), gs.FLOOR)
    t0, out = time.time(), []
    for rnd in range(ROUNDS + 1):
        peaks = tt.poles(seq, d)
        nom, res = gs.mf(seq, d, gs.GRIDS["nominal"]), gs.mf(seq, d, gs.GRIDS["resolved"])
        out.append({"method": method, "seed": seed, "round": rnd, "mf_nominal": f"{nom:.6e}", "mf_resolved": f"{res:.6e}",
                    "poles": len(peaks), "highest": f"{max((p[2] for p in peaks), default=0.0):.5f}",
                    "t_s": f"{time.time() - t0:.0f}", "d_nm": " ".join(f"{v:.6f}" for v in d)})
        if rnd < ROUNDS:
            d = tt.polish("height", seq, d, peaks if method == "pole" else [])
    return out


def main() -> None:
    tasks = [(m, s) for s in range(1, SEEDS + 1) for m in ("nominal", "pole")]
    rows = []
    with ProcessPoolExecutor(WORKERS) as pool:
        for res in pool.map(run, tasks):
            rows += res
            a, b = res[0], res[-1]
            print(f"seed {a['seed']} {a['method']:7s}: nominal {float(a['mf_nominal']):.4f} -> {float(b['mf_nominal']):.4f} %,"
                  f" resolved {float(a['mf_resolved']):.4f} -> {float(b['mf_resolved']):.4f} %, poles {b['poles']},"
                  f" highest {100 * float(b['highest']):.2f} % ({b['t_s']} s)", flush=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
