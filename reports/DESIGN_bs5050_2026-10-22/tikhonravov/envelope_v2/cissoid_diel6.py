"""OIC 2016 B1 (cissoid): material swaps over the six dielectrics F L B M T H (2026-10-31, owner: 4 or 5 dielectric
indices are allowed). Every single swap is scored, then `cissoid_islands.swap_round` keeps the best while it gains;
the result is polished on the 301 points and checked at the oracle.
usage: CISSOID_DIELECTRICS=all python cissoid_diel6.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cissoid_islands as ci
import cissoid_memetic as mm
import cissoid_opt as co
import numpy as np


def main() -> None:
    r0 = next(csv.DictReader((co.s.HERE / sys.argv[1]).open(encoding="utf-8")))
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    print(f"dielectrics {mm.DIELECTRICS}, metals {mm.METALS}", flush=True)
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, r = mm.polish_feasible((m, d))
        names = [(i, b) for i, a in enumerate(m) for b in (mm.METALS if ci.is_metal(a) else mm.DIELECTRICS) if b != a]
        res = list(pool.map(mm.polish_feasible, ci.swap_tasks(m, d)))
        order = sorted(range(len(res)), key=lambda k: res[k][2])
        print(f"start search MF {r:.5f}; best single swaps: " + " ".join(
            f"{names[k][0]}{m[names[k][0]]}->{names[k][1]}:{res[k][2]:.5f}" for k in order[:12]), flush=True)
        m2, d2, r2, kept = ci.swap_round(m, d, r, pool)
        m3, d3, f = co.polish_full((m2, d2, co.FLOOR))
        o = co.oracle_mf(m3, d3)
    print(f"swap round: {kept} kept, search MF {r2:.5f}; 301-point {f:.5f}, oracle {o:.5f}, N {len(m3)}, "
          f"materials {dict(Counter(m3))}", flush=True)
    row = {"layers": len(m3), "mf_kernel": f, "mf_full": f, "mf_oracle": o, "metals": "".join(x for x in m3 if x in "AUN"),
           "physical_nm": float(d3.sum()), "mats": " ".join(m3), "d_nm": " ".join(f"{v:.4f}" for v in d3)}
    with (co.s.HERE / sys.argv[2]).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    main()
