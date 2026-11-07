"""OIC 2016 B1 (cissoid): swaps restricted to the dielectric layers of low optical thickness (2026-10-31, owner).
Every single swap and every pair of swaps among the dielectric layers whose OT is below OTMAX nm, to the materials of
MATS, each polished on the 301 points and judged by the oracle; the best is written to OUT if it gains.
usage: python cissoid_thin_swaps.py IN.csv OUT.csv OTMAX MATS
"""

from __future__ import annotations

import csv
import itertools
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_multiswap as ms
import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst, otmax, mats = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    thin = [i for i, x in enumerate(m) if x in "FLBMTH" and co.MATS[x] * d[i] < otmax]
    print(f"{len(thin)} thin layers (OT < {otmax} nm): {[(i + 1, m[i], round(co.MATS[m[i]] * d[i])) for i in thin]}", flush=True)
    singles = [(i, y) for i in thin for y in mats if y != m[i]]
    combos = [(s,) for s in singles] + [c for c in itertools.combinations(singles, 2) if c[0][0] != c[1][0]]
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, base = co.polish_full((m, d, co.FLOOR))
        res = list(pool.map(co.polish_full, [(*ms.apply(m, d, c), co.FLOOR) for c in combos], chunksize=8))
    order = np.argsort([q[2] for q in res])
    print(f"start {base:.5f}; {len(combos)} candidates; best: " + "; ".join(
        " ".join(f"{i + 1}{y}" for i, y in combos[k]) + f" {res[k][2]:.5f}" for k in order[:6]), flush=True)
    k = order[0]
    m2, d2, f = res[k]
    if f < base * (1 - 1e-4) and len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9:
        o = co.oracle_mf(m2, d2)
        print(f"NEW BEST oracle {o:.5f}", flush=True)
        row = {"how": " ".join(f"{i + 1}{y}" for i, y in combos[k]), "layers": len(m2), "mf_full": f, "mf_oracle": o,
               "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)}
        with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row))
            w.writeheader()
            w.writerow(row)


if __name__ == "__main__":
    main()
