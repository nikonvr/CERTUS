"""Three-line filter: TOT descent from the 0.065 % basin (2026-10-28, user request).

The fixed-N search found MF ~0.065 % only at TOT ~11600 nm with 92-100 layers; squeezing those designs to 11000 nm in
one step shifts the three lines by ~30 nm and fails, and at imposed TOT 11000 nm the search stays at ~0.144 %.
Here the basin is followed step by step: TOT is lowered by STEP nm, every design of the beam is stretched to the new
TOT and settled (polish at imposed TOT, layers under 0.3 nm dropped, gradual.settle), then layer removals (each of the
REMOVE thinnest layers, neighbours merged) are tried and settled. The beam keeps the BEAM best designs and the best
design of every N <= N_TARGET; the best design of every N is recorded at every TOT.

usage: python descent.py MINUTES TOT_MIN   (env DESCENT_WORKERS, default 7)
inputs: curve_3line_none_foc70-100_free_s1.csv and front_3line_none_foc70-100_free_s1.csv (arm A), designs with
        MF < 0.08 % are the seeds
outputs: descent.csv (TOT, N, MF kernel, MF oracle on the best per N at multiples of 200 nm, design), descent.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import gradual as g
import numpy as np
import search as s

STEP = 50.0
BEAM = 6
N_TARGET = 90
REMOVE = 10
WORKERS = int(os.environ.get("DESCENT_WORKERS", "7"))


def settle_at(task):
    seq, d, tot = task
    d = d * (tot / s.total_ot(seq, d))
    return g.settle(seq, d, tot)


def removals(seq: str, d: np.ndarray, tot: float):
    for i in np.argsort(d)[:REMOVE]:
        s2, d2 = s.normalize(seq[:i] + seq[i + 1:], np.delete(d, i), 0.0)
        yield s2, d2, tot


def load_seeds() -> list[tuple[str, np.ndarray]]:
    seeds = []
    for name in ("curve_3line_none_foc70-100_free_s1.csv", "front_3line_none_foc70-100_free_s1.csv"):
        for r in csv.DictReader((s.HERE / name).open(encoding="utf-8")):
            mf = float(r["rmse_1601_oracle"]) if "rmse_1601_oracle" in r else float(r["mf_oracle"]) / 100
            if mf < 8e-4:
                seeds.append((r["seq"], np.array([float(v) for v in r["d_nm"].split()])))
    return seeds


def main() -> None:
    minutes, tot_min = float(sys.argv[1]), float(sys.argv[2])
    deadline = time.time() + 60 * minutes
    pool = ProcessPoolExecutor(WORKERS)
    log = (s.HERE / "descent.log").open("w", encoding="utf-8")
    seeds = load_seeds()
    tot = STEP * np.floor(min(s.total_ot(q, x) for q, x in seeds) / STEP)
    beam = list(pool.map(settle_at, [(q, x, tot) for q, x in seeds]))
    rows = []
    while time.time() < deadline and tot >= tot_min:
        tasks = [(q, x, tot) for q, x, _r in beam]
        tasks += [t for q, x, _r in beam for t in removals(q, x, tot)]
        found = list(pool.map(settle_at, tasks))
        best_n: dict[int, tuple[str, np.ndarray, float]] = {}
        for q, x, r in found:
            if np.isfinite(r) and abs(s.total_ot(q, x) - tot) < 1.0 and (len(q) not in best_n or r < best_n[len(q)][2]):
                best_n[len(q)] = (q, x, r)
        for n, (q, x, r) in sorted(best_n.items()):
            rows.append({"total_ot_nm": tot, "layers": n, "mf_kernel": 100 * r, "mf_oracle": "", "seq": q,
                         "d_nm": " ".join(f"{v:.6f}" for v in x)})
        ranked = sorted(best_n.values(), key=lambda t: t[2])
        beam = ranked[:BEAM] + [best_n[n] for n in sorted(best_n) if n <= N_TARGET and best_n[n] not in ranked[:BEAM]]
        low = [f"{n}:{100 * best_n[n][2]:.3f}" for n in sorted(best_n) if n <= N_TARGET][-4:]
        log.write(f"{time.strftime('%H:%M:%S')} TOT {tot:7.0f} best N {len(ranked[0][0])} MF {100 * ranked[0][2]:.4f}"
                  f" | N <= {N_TARGET}: {' '.join(low)}\n")
        log.flush()
        tot -= STEP
    for row in rows:
        if row["total_ot_nm"] % 200 == 0:
            row["mf_oracle"] = 100 * s.oracle_rmse(row["seq"], np.array([float(v) for v in row["d_nm"].split()]))
    with (s.HERE / "descent.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log.write("written\n")
    pool.shutdown()


if __name__ == "__main__":
    main()
