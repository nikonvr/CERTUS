"""Arm A of the synthesis comparison (2026-11-01 late evening, owner: "A against B"): the best design of each number of
layers of a nominal search (curve_{TAG}free_s1.csv) cured afterwards -- ROUNDS rounds of threeline_track (resonances
from the complex plane, each charged by its height at its pole, 30 trust-region iterations), the round of least tracked
MF kept -- and judged on the nominal grid and on 0.001 nm steps. Arm B is the search with SEARCH_POLES. Rows to
{TAG}cure_archive.csv with the time spent.
env CURE_SEED=S (2026-11-02, Sec. 7.3 redone without the substrate-side L layer): the curve of seed S, rows to
{TAG}cure_archive_sS.csv; unset: seed 1, unchanged.
usage: SEARCH_TARGET=mshape TRACK_DETECT=complex python cure_archive.py ROUNDS WORKERS
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import search as s
import threeline_track as tt

ROUNDS, WORKERS = int(sys.argv[1]), int(sys.argv[2])


def cure(row) -> dict:
    t0 = time.time()
    seq, d = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
    rows = tt.track("height", seq, d, rounds=ROUNDS)
    b = min(rows, key=lambda q: float(q["mf_tracked"]))
    return {"layers": len(seq), "ot_nm": s.total_ot(seq, np.array([float(v) for v in b["d_nm"].split()])),
            "nominal_before": float(rows[0]["mf_nominal"]), "resolved_before": float(rows[0]["mf_resolved"]),
            "nominal_after": float(b["mf_nominal"]), "resolved_after": float(b["mf_resolved"]),
            "highest_after": float(b["highest"]), "round": int(b["round"]), "t_s": round(time.time() - t0, 1),
            "seq": seq, "d_nm": b["d_nm"]}


def main() -> None:
    seed = os.environ.get("CURE_SEED")
    src = list(csv.DictReader(open(f"curve_{s.TAG}free_s{seed or 1}.csv", encoding="utf-8")))
    out = []
    t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as pool:
        for r in pool.map(cure, src):
            out.append(r)
            print(f"N {r['layers']:3d}: resolved {r['resolved_before']:.4f} -> {r['resolved_after']:.4f} %, nominal "
                  f"{r['nominal_before']:.4f} -> {r['nominal_after']:.4f} %, highest {100 * r['highest_after']:.2f} % "
                  f"({r['t_s']} s)", flush=True)
    print(f"total {time.time() - t0:.0f} s", flush=True)
    with open(f"{s.TAG}cure_archive{f'_s{seed}' if seed else ''}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
