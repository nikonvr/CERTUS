"""OIC 2016 B1 (cissoid): thicken a dielectric layer, then let needles and removals reorganize the stack (2026-10-31,
owner; the gradual-evolution idea of Tikhonravov and Trubetskov). The TOP thickenings of a screen (one layer + DOT nm
of OT, polished) each get up to CYCLES needle-removal cycles and a swap round on the 301 points; judged by the oracle.
usage: python cissoid_thicken_evolve.py IN.csv OUT.csv TOP CYCLES DOT [DOT ...]   (env CISSOID_GRID=full)
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_islands as ci
import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst, top, cycles = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    dots = [float(v) for v in sys.argv[5:]]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m0, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    tries = [(i, t) for i, x in enumerate(m0) if x in "FLBMTH" for t in dots]
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        _m, _d, best = co.polish_full((m0, d0, co.FLOOR))
        tasks = []
        for i, t in tries:
            d2 = d0.copy()
            d2[i] += t / co.MATS[m0[i]]
            tasks.append((m0, d2, co.FLOOR))
        screen = list(pool.map(co.polish_full, tasks))
        order = np.argsort([q[2] for q in screen])[:top]
        print(f"start {best:.5f}; screen of {len(tries)}, kept {top} ({time.time() - t0:.0f} s)", flush=True)
        for k in order:
            m, d, r = screen[k]
            for _ in range(cycles):
                got = fx.cycle(m, d, pool)
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, d, r = got
            m, d, r, _kept = ci.swap_round(m, d, r, pool)
            m, d, f = co.polish_full((m, d, co.FLOOR))
            tag = ""
            if f < best * (1 - 1e-4) and len(m) <= co.N_MAX and d.min() >= co.FLOOR - 1e-9:
                best, o = f, co.oracle_mf(m, d)
                tag = f" NEW BEST oracle {o:.5f}"
                row = {"how": f"thicken {tries[k][0] + 1}+{tries[k][1]:g}", "layers": len(m), "mf_kernel": f,
                       "mf_full": f, "mf_oracle": o, "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}
                with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(row))
                    w.writeheader()
                    w.writerow(row)
            print(f"layer {tries[k][0] + 1}{m0[tries[k][0]]} +{tries[k][1]:g}: screen {screen[k][2]:.5f} -> "
                  f"{f:.5f}{tag} ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
