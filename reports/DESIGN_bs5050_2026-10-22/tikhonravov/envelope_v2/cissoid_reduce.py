"""OIC 2016 B1 (cissoid): reduce the dielectrics back to a smaller set, one layer at a time (2026-10-31, owner: converge
back to the quintet). Each step tries every layer made of a material in DROP as each material of KEEP (constant optical
thickness), polishes every candidate on the 301 points, keeps the best (even if it loses), and records the oracle MF.
usage: python cissoid_reduce.py IN.csv OUT.csv DROP KEEP   e.g. LBT FMH
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst, drop, keep = sys.argv[1:5]
    # the last row: an earlier reduction file holds one row per step, the reduced design last
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    out = []
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, co.FLOOR))
        step = 0
        while True:
            o = co.oracle_mf(m, d)
            left = sorted({x for x in m if x in drop})
            print(f"step {step}: oracle {o:.5f}, N {len(m)}, left {left} ({sum(x in drop for x in m)} layers)", flush=True)
            out.append({"step": step, "oracle": o, "left": "".join(left), "layers": len(m), "mf_full": f, "mf_oracle": o,
                        "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)})
            with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(out[0]))
                w.writeheader()
                w.writerows(out)
            tries = [(i, y) for i, x in enumerate(m) if x in drop for y in keep]
            if not tries:
                break
            tasks = []
            for i, y in tries:
                d2 = d.copy()
                d2[i] *= co.MATS[m[i]] / co.MATS[y]
                tasks.append((*co.normalize([*m[:i], y, *m[i + 1:]], d2, 0.0), co.FLOOR))
            res = list(pool.map(co.polish_full, tasks))
            k = int(np.argmin([q[2] for q in res]))
            m, d, f = res[k]
            step += 1
            print(f"  {tries[k][0]}{tries[k][1]}", flush=True)


if __name__ == "__main__":
    main()
