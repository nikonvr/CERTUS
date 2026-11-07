"""OIC 2016 B1 (cissoid): every pair of material swaps, and every inversion of two neighbouring layers (2026-10-31).

Pairs: all pairs of single swaps in distinct layers (6 dielectrics, Ag <-> Ni), polished on the search grid; the 10
best go to the 301-point polish and the oracle. Inversions: layers i and i+1 exchanged (materials and thicknesses),
polished on the 301 points. A better design is written to OUT.
usage: python cissoid_exhaustive.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_islands as ci
import cissoid_memetic as mm
import cissoid_multiswap as ms
import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    r0 = next(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, best = co.polish_full((m, d, co.FLOOR))
        # dielectric layers only since 2026-10-31 (owner: the metals are settled; EXH_METALS=1 adds Ag <-> Ni)
        metals = os.environ.get("EXH_METALS", "0") == "1"
        names = [(i, b) for i, a in enumerate(m) if metals or not ci.is_metal(a)
                 for b in (mm.METALS if ci.is_metal(a) else mm.DIELECTRICS) if b != a]
        pairs = [c for c in itertools.combinations(names, 2) if c[0][0] != c[1][0]]
        res = list(pool.map(mm.polish_feasible, [ms.apply(m, d, c) for c in pairs], chunksize=64))
        order = np.argsort([q[2] for q in res])[:10]
        print(f"{len(pairs)} pairs ({time.time() - t0:.0f} s), best search {res[order[0]][2]:.5f}", flush=True)
        cands = [(" ".join(f"{i}{y}" for i, y in pairs[k]), res[k][0], res[k][1]) for k in order]
        for i in range(len(m) - 1):
            m2, d2 = list(m), d.copy()
            m2[i], m2[i + 1], d2[i], d2[i + 1] = m[i + 1], m[i], d[i + 1], d[i]
            cands.append((f"invert {i}-{i + 1}", *co.normalize(m2, d2, 0.0)))
        out = list(pool.map(co.polish_full, [(mm_, dd, co.FLOOR) for _, mm_, dd in cands]))
        inv = [q[2] for (how, _, _), q in zip(cands, out, strict=True) if how.startswith("invert")]
        print(f"inversions: best {min(inv):.5f} ({time.time() - t0:.0f} s)", flush=True)
        k = int(np.argmin([q[2] for q in out]))
        m2, d2, f = out[k]
        ok = len(m2) <= co.N_MAX and d2.min() >= co.FLOOR - 1e-9
        if ok and f < best * (1 - 1e-4):
            o = co.oracle_mf(m2, d2)
            print(f"NEW BEST {cands[k][0]}: 301-point {f:.5f}, oracle {o:.5f}", flush=True)
            row = {"how": cands[k][0], "layers": len(m2), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
                   "metals": "".join(x for x in m2 if x in "AUN"), "physical_nm": float(d2.sum()),
                   "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)}
            with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row))
                w.writeheader()
                w.writerow(row)
        else:
            print(f"no gain: best {f:.5f} ({cands[k][0]}) vs {best:.5f}", flush=True)


if __name__ == "__main__":
    main()
