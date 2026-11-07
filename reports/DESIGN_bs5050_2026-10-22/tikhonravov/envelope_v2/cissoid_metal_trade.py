"""OIC 2016 B1 (cissoid): trade a metal layer of the record for a dielectric slot (2026-11-01, night analysis).

Why: the F+H pseudo-rugates that beat the record above 60 layers kept 11 metal layers, the record 14; each metal layer
takes one of the 50 slots. For each metal layer: delete it, or turn it into each of the six dielectrics (same physical
thickness); polish on the 301 points. The 3 best then get up to 5 needle-removal cycles (all dielectrics), which can
spend the freed slot.
usage: python cissoid_metal_trade.py IN.csv OUT.csv
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
            if not fx.is_metal(x):
                continue
            tasks.append((*co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0), co.FLOOR))
            hows.append(f"delete {i}{x} ({d[i]:.1f} nm)")
            for y in "FLBMTH":
                tasks.append((*co.normalize([*m[:i], y, *m[i + 1:]], d.copy(), 0.0), co.FLOOR))
                hows.append(f"{i}{x}->{y} ({d[i]:.1f} nm)")
        res = list(pool.map(co.polish_full, tasks))
        order = np.argsort([q[2] for q in res])
        print(f"base {base:.5f}; {len(tasks)} trades ({time.time() - t0:.0f} s); best:", flush=True)
        for k in order[:8]:
            print(f"  {hows[k]}: N {len(res[k][0])}, MF {res[k][2]:.5f}", flush=True)
        best = None
        for k in order[:3]:
            m2, d2, f2 = res[k]
            for _ in range(5):
                got = fx.cycle(m2, d2, pool)
                if got is None or got[2] >= f2 * (1 - 1e-4):
                    break
                m2, d2, f2 = got
            m2, d2, f2 = co.polish_full((m2, d2, co.FLOOR))
            print(f"  {hows[k]} + cycles: N {len(m2)}, metals {sum(map(fx.is_metal, m2))}, MF {f2:.5f} "
                  f"({time.time() - t0:.0f} s)", flush=True)
            if best is None or f2 < best[2]:
                best = (m2, d2, f2, hows[k])
        m2, d2, f2, how = best
        o = co.oracle_mf(m2, d2)
        with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["how", "layers", "mf_full", "mf_oracle", "mats", "d_nm"])
            w.writeheader()
            w.writerow({"how": how + " + cycles", "layers": len(m2), "mf_full": f2, "mf_oracle": o,
                        "mats": " ".join(m2), "d_nm": " ".join(f"{v:.4f}" for v in d2)})
        print(f"best: {how} + cycles, oracle {o:.6f} vs record {base:.6f}", flush=True)


if __name__ == "__main__":
    main()
