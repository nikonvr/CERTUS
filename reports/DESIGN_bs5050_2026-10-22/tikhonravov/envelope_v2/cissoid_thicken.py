"""OIC 2016 B1 (cissoid): thicken one dielectric layer sensibly, then repolish (2026-10-31, owner). Each dielectric
layer gets + DOT nm of optical thickness for every DOT given (half-wave orders at 500 nm are 250, 500, ...), then the
design is polished on the 301 points and judged by the oracle; the best is written to OUT if it gains.
Close to the gradual-evolution step of Tikhonravov and Trubetskov (one layer thickened, then all refined).
usage: python cissoid_thicken.py IN.csv OUT.csv DOT [DOT ...]
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst, dots = sys.argv[1], sys.argv[2], [float(v) for v in sys.argv[3:]]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    tries = [(i, t) for i, x in enumerate(m) if x in "FLBMTH" for t in dots]
    tasks = []
    for i, t in tries:
        d2 = d.copy()
        d2[i] += t / co.MATS[m[i]]
        tasks.append((m, d2, co.FLOOR))
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, base = co.polish_full((m, d, co.FLOOR))
        res = list(pool.map(co.polish_full, tasks))
    order = np.argsort([q[2] for q in res])
    print(f"start {base:.5f}; {len(tries)} tries; best: " + "; ".join(
        f"{tries[k][0] + 1}{m[tries[k][0]]}+{tries[k][1]:g}:{res[k][2]:.5f}" for k in order[:8]), flush=True)
    m2, d2, f = res[order[0]]
    if f < base * (1 - 1e-4) and len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9:
        o = co.oracle_mf(m2, d2)
        print(f"NEW BEST oracle {o:.5f}", flush=True)
        row = {"layers": len(m2), "mf_full": f, "mf_oracle": o, "mats": " ".join(m2),
               "d_nm": " ".join(f"{v:.4f}" for v in d2)}
        with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row))
            w.writeheader()
            w.writerow(row)


if __name__ == "__main__":
    main()
