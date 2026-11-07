"""OIC 2016 B1 (cissoid): combined material swaps of 2, 3 and 4 layers (2026-10-31, owner).

1. single swaps without cap until none gains; 2. every combination of 2, 3, 4 swaps among the TOP best single swaps
(losing ones included), polished on the search grid; the 10 best go to the 301-point polish and the oracle; a better
design is written to OUT and the loop starts again from it.
usage: python cissoid_multiswap.py IN.csv OUT.csv [TOP]
"""

from __future__ import annotations

import csv
import itertools
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_islands as ci
import cissoid_memetic as mm
import cissoid_opt as co
import numpy as np


def apply(m0, d0, swaps):
    m, d = list(m0), d0.copy()
    for i, y in swaps:
        if not ci.is_metal(m[i]):
            d[i] *= co.MATS[m[i]] / co.MATS[y]
        m[i] = y
    return co.normalize(m, np.maximum(d, co.FLOOR), 0.0)


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    r0 = next(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, best = co.polish_full((m, d, co.FLOOR))
        print(f"start 301-point {best:.5f}", flush=True)
        while True:
            ci.SWAP_MAX = 0
            m, d, r = mm.polish_feasible((m, d))
            m, d, r, kept = ci.swap_round(m, d, r, pool)
            names = [(i, b) for i, a in enumerate(m) for b in (mm.METALS if ci.is_metal(a) else mm.DIELECTRICS) if b != a]
            singles = list(pool.map(mm.polish_feasible, ci.swap_tasks(m, d)))
            tops = [names[k] for k in np.argsort([s[2] for s in singles])[:top]]
            combos = [c for n in (2, 3, 4) for c in itertools.combinations(tops, n) if len({i for i, _ in c}) == n]
            res = list(pool.map(mm.polish_feasible, [apply(m, d, c) for c in combos]))
            order = np.argsort([q[2] for q in res])[:10]
            print(f"{kept} singles kept (search {r:.5f}); {len(combos)} combos, best search {res[order[0]][2]:.5f}",
                  flush=True)
            cands = [("singles", m, d)] + [(" ".join(f"{i}{y}" for i, y in combos[k]), res[k][0], res[k][1])
                                           for k in order]
            out = [(how, *co.polish_full((mm_, dd, co.FLOOR))) for how, mm_, dd in cands]
            how, m2, d2, f = min(out, key=lambda t: t[3])
            if f >= best * (1 - 1e-4) or len(m2) > co.N_MAX or d2.min() < co.FLOOR - 1e-9:
                print(f"stop: best {f:.5f} ({how}) vs {best:.5f}", flush=True)
                break
            best, o = f, co.oracle_mf(m2, d2)
            m, d = m2, d2
            print(f"NEW BEST {how}: 301-point {f:.5f}, oracle {o:.5f}", flush=True)
            row = {"how": how, "layers": len(m), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
                   "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
                   "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}
            with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row))
                w.writeheader()
                w.writerow(row)


if __name__ == "__main__":
    main()
