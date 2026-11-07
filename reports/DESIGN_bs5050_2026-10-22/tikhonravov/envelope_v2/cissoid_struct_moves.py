"""OIC 2016 B1 (cissoid): structural moves no swap search contains, on one design (2026-11-01 audit of 0.012210).

The metal -> dielectric trade (Ag 27 -> H) opened the cascade 0.012869 -> 0.012210; this tries the other move types
that keep N: every dielectric layer turned into a thin metal (each allowed metal, start thickness 3, 5 and 8 nm), and
every inversion of two neighbouring layers; each polished on the 301 points (d >= 3 nm). The best 8 are printed; a
design better than the start is written to OUT.
usage: python cissoid_struct_moves.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, base = co.polish_full((m, d, co.FLOOR))
        tasks, hows = [], []
        for i, x in enumerate(m):
            if fx.is_metal(x):
                continue
            for y in fx.METALS:
                for t in (3.0, 5.0, 8.0):
                    d2 = d.copy()
                    d2[i] = t
                    tasks.append((*co.normalize([*m[:i], y, *m[i + 1:]], d2, 0.0), co.FLOOR))
                    hows.append(f"{i}{x}->{y}{t:g}")
        for i in range(len(m) - 1):
            m2, d2 = list(m), d.copy()
            m2[i], m2[i + 1], d2[i], d2[i + 1] = m[i + 1], m[i], d[i + 1], d[i]
            tasks.append((*co.normalize(m2, d2, 0.0), co.FLOOR))
            hows.append(f"invert {i}-{i + 1}")
        res = list(pool.map(co.polish_full, tasks, chunksize=2))
        vals = [q[2] if len(q[0]) <= co.N_MAX and q[1].min() >= co.FLOOR - 1e-9 else np.inf for q in res]
        order = np.argsort(vals)
        print(f"base {base:.6f}; {len(tasks)} moves ({time.time() - t0:.0f} s); best:", flush=True)
        for k in order[:8]:
            print(f"  {hows[k]}: N {len(res[k][0])}, MF {vals[k]:.6f}", flush=True)
        k = order[0]
        if vals[k] < base * (1 - 1e-4):
            m2, d2, f2 = res[k]
            o = co.oracle_mf(m2, d2)
            with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["how", "layers", "mf_full", "mf_oracle", "mats", "d_nm"])
                w.writeheader()
                w.writerow({"how": hows[k], "layers": len(m2), "mf_full": f2, "mf_oracle": o, "mats": " ".join(m2),
                            "d_nm": " ".join(f"{v:.4f}" for v in d2)})
            print(f"GAIN {hows[k]}: oracle {o:.6f} vs {base:.6f} -> {dst}", flush=True)


if __name__ == "__main__":
    main()
