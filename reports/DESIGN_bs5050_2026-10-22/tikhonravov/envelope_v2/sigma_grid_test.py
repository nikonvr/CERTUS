"""Does a grid uniform in wavenumber prevent the hidden resonances? (2026-11-02 night, method paper, "Wavenumber grids")
Same test as optimizer_test_trub101.py, 'nominal' arm only: Trubetskov's 101-layer design (re-created) with every
thickness multiplied by 1 + 0.03 N(0, 1), seeds 1..6, 40 bursts of 30 trust-region iterations on the 277 points of the
three-line bands -- here spread evenly in sigma = 1/lambda inside each band (same count per band) instead of every 1 nm.
Judged on the 1-nm grid, on 0.001 nm steps, and by the resonances found from the complex plane.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex python sigma_grid_test.py WORKERS
"""

from __future__ import annotations

import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import grid_study as gs
import numpy as np
import search as s
import threeline_track as tt


def sigma_grid():
    w, t = [], []
    for a, b, v in s._bands:
        n = b - a + 1
        x = 1.0 / np.linspace(1.0 / b, 1.0 / a, n)[::-1]
        w.append(x)
        t.append(s.band_values(x, v))
    return gs.kernel_grid(np.concatenate(w), np.concatenate(t))


def run(seed) -> tuple[str, dict]:
    tt.NOM = sigma_grid()
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d0 = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    d = np.maximum(d0 * (1.0 + 0.03 * np.random.default_rng(seed).normal(size=len(d0))), gs.FLOOR)
    for _ in range(40):
        d = tt.polish("height", seq, d, [])
    p = tt.poles(seq, d)
    vals = (gs.mf(seq, d, tt.NOM), gs.mf(seq, d, gs.GRIDS["nominal"]), gs.mf(seq, d, gs.GRIDS["resolved"]))
    hi = 100 * max((q[2] for q in p), default=0.0)
    row = {"start": seed, "mf_sigma_grid_pct": f"{vals[0]:.6g}", "mf_nominal_pct": f"{vals[1]:.6g}",
           "mf_resolved_pct": f"{vals[2]:.6g}", "highest_peak_pct": f"{hi:.4f}", "seq": seq,
           "d_nm": " ".join(f"{v:.6f}" for v in d)}
    return (f"seed {seed}: sigma-grid MF {vals[0]:.4f} %, 1-nm grid {vals[1]:.4f} %, resolved {vals[2]:.4f} %, "
            f"poles {len(p)}, highest {hi:.2f} %"), row


if __name__ == "__main__":
    #: 2026-11-03 (referee audit of the OE paper): SIGMA_OUT=file.csv also writes the six designs; unset, nothing more
    out = os.environ.get("SIGMA_OUT", "")
    rows = []
    with ProcessPoolExecutor(int(sys.argv[1])) as pool:
        for line, row in pool.map(run, range(1, 7)):
            print(line, flush=True)
            rows.append(row)
    if out:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
