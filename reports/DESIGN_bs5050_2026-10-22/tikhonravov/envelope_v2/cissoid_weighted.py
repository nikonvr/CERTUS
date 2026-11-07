"""OIC 2016 B1 (cissoid): one phase of the weighted-target test (2026-10-31, owner).

The owner: weigh much more the few spectral points that cause the most error, reoptimize, then put the normal target
back. A polish alone would slide back into the same minimum: the weighted phase also makes structural moves
(needle-removal cycles, `cissoid_fixedN.cycle`), which the weights steer.
One phase = a polish and CYCLES needle-removal cycles under the current MF (weighted if CISSOID_WEIGHT is set), the
best feasible design kept by that MF. The test chains a weighted phase then a normal one; the control, two normal
phases from the same start.
usage: python cissoid_weighted.py IN.csv OUT.csv CYCLES LABEL  (IN row 0 after sorting by MF; OUT gets one row)
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_opt as co
import numpy as np

WALK = os.environ.get("WEIGHTED_WALK", "0") == "1"


def main() -> None:
    src, dst, cycles, label = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    r0 = sorted(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")),
                key=lambda r: float(r.get("mf_full") or r["mf_kernel"]))[0]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, r = co.polish((m, d, co.FLOOR))
        print(f"{label} start: MF {r:.5f} (weight '{co.WEIGHT}'), oracle {co.oracle_mf(m, d):.5f}", flush=True)
        # A cycle is deterministic: rejecting a cycle that does not gain repeats the same cycle (first run of 2026-10-31,
        # 9 identical cycles). Each round is an overshoot (needle cycles up to 55-60 layers, removals back to 50,
        # CISSOID_OVERSHOOT) then needle-removal cycles while they gain; WALK=1 keeps the overshoot even when it loses,
        # so the design changes, and the phase returns the best design visited after the start.
        best = None
        for k in range(cycles):
            if fx.OVERSHOOT:
                m2, d2, r2 = fx.overshoot(m, d, pool)
                if WALK or r2 < r:
                    m, d, r = m2, d2, r2
            for _ in range(3):
                got = fx.cycle(m, d, pool)
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, d, r = got
            if best is None or r < best[2]:
                best = (m, d, r)
            print(f"{label} round {k + 1}: MF {r:.5f}, oracle {co.oracle_mf(m, d):.5f}, N {len(m)}, M {m.count('M')}",
                  flush=True)
        if best is not None:
            m, d, r = best
    row = {"label": label, "weight": co.WEIGHT, "cycles": cycles, "layers": len(m), "mf_kernel": r,
           "mf_oracle": co.oracle_mf(m, d), "m_count": m.count("M"), "metals": "".join(x for x in m if x in "AUN"),
           "physical_nm": float(d.sum()), "seconds": round(time.time() - t0), "mats": " ".join(m),
           "d_nm": " ".join(f"{v:.4f}" for v in d)}
    with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)
    print(f"{label} end: MF {r:.5f}, oracle {row['mf_oracle']:.5f}, N {len(m)}, {row['seconds']} s", flush=True)


if __name__ == "__main__":
    main()
