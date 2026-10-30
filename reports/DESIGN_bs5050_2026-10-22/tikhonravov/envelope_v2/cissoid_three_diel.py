"""OIC 2016 B1 (cissoid): reduce a design to the two extreme dielectrics F, H and one third (2026-10-30, owner).

L layers become F, T layers H, and B and M layers the third, one layer at a time at constant optical thickness, the
design being repolished at each step (replacing them all at once gave MF 0.21-1.08 from 0.0269).
usage: python cissoid_three_diel.py FILE.csv [K [OUT.csv]]; output: OUT.csv (default cissoid_three_diel.csv), one design per third dielectric.
"""

from __future__ import annotations

import csv
import sys

import cissoid_opt as co
import numpy as np

NAME = sys.argv[1]
rows = sorted(csv.DictReader((co.s.HERE / NAME).open(encoding="utf-8")),
              key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))
r0 = rows[int(sys.argv[2]) if len(sys.argv) > 2 else 0]
m0, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
out = []
for third in "BM":  # the owner: the third dielectric is B or M
    m, d, r = list(m0), d0.copy(), co.mf(m0, d0)
    swap = {"L": "F", "T": "H", "B": third, "M": third}  # the owner: L goes to F, T to H, B and M to the third
    while True:
        todo = [i for i, x in enumerate(m) if swap.get(x, x) != x]
        if not todo:
            break
        i, y = todo[0], swap[m[todo[0]]]
        d2 = d.copy()
        d2[i] *= co.MATS[m[i]] / co.MATS[y]
        m, d = co.normalize([*m[:i], y, *m[i + 1:]], d2, 0.0)
        m, d, r = co.polish((m, d, co.FLOOR))
        print(f"{third}: {len(todo) - 1} left, N {len(m)}, MF {r:.5f}", flush=True)
    out.append({"third": third, "layers": len(m), "mf_kernel": r, "mf_oracle": co.oracle_mf(m, d),
                "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()), "mats": " ".join(m),
                "d_nm": " ".join(f"{v:.4f}" for v in d)})
    with (co.s.HERE / (sys.argv[3] if len(sys.argv) > 3 else "cissoid_three_diel.csv")).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
