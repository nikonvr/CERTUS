"""OIC 2016 B1 (cissoid): get under a dielectric optical-thickness cap by one interference-order hop (2026-11-01).

A plain polish under the cap squeezes every layer (record 0.009210 at 20 131 nm -> 0.0361 at 19 995 nm). Here one
thick dielectric layer (OT > 400 nm) loses k = 1, 2 or 3 interference orders (k * 550 / (2 n) nm of physical
thickness), which can pass the cap in one move and leave the others in place; each hopped design is polished under the
cap (CISSOID_OTMAX), the best ones descended under the cap (N1, metal trades, ADD, N2), and the best written to OUT.
usage: CISSOID_OTMAX=19995 python cissoid_ot_hops.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import cissoid_ot_cap as oc
import cissoid_slot_trade as st
import flair_campaign as fc
import numpy as np


def main() -> None:
    assert co.OTMAX, "set CISSOID_OTMAX"
    src, dst = sys.argv[1], sys.argv[2]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    cands, hows = [], []
    for i, x in enumerate(m):
        n = float(np.real(co.MATS[x]))
        if np.iscomplex(co.MATS[x]) or n * d[i] < 400.0:
            continue
        for k in (1, 2, 3):
            d2 = d.copy()
            d2[i] -= k * 550.0 / (2.0 * n)
            if d2[i] > co.FLOOR:
                cands.append((list(m), d2, co.FLOOR))
                hows.append(f"hop {i}{x} -{k}")
    with ProcessPoolExecutor(co.WORKERS) as pool:
        res = list(pool.map(co.polish_full, cands))
        orc = [co.oracle_mf(q[0], q[1]) if oc.ot_d(q[0], q[1]) <= co.OTMAX + 1.0 else np.inf for q in res]
        order = np.argsort(orc)
        print(f"{len(cands)} hops polished under the cap ({time.time() - t0:.0f} s); best:", flush=True)
        for k in order[:6]:
            print(f"  {hows[k]}: OT_d {oc.ot_d(res[k][0], res[k][1]):.1f} nm, oracle {orc[k]:.6f}", flush=True)
        best = None
        for k in order[:3]:
            mm, dd, ff, steps = fc.descend(pool, *res[k], names=("N1", "MT", "ADD", "N2"), rounds=8)
            o = co.oracle_mf(mm, dd)
            print(f"  {hows[k]} + descent {steps}: OT_d {oc.ot_d(mm, dd):.1f} nm, oracle {o:.6f} "
                  f"({time.time() - t0:.0f} s)", flush=True)
            if oc.ot_d(mm, dd) <= co.OTMAX + 1.0 and (best is None or o < best[2]):
                best = (mm, dd, o, hows[k] + " + " + " + ".join(steps))
                st.save(dst, mm, dd, ff, best[3])
        print(f"done: best oracle {best[2]:.6f} -> {dst}", flush=True)


if __name__ == "__main__":
    main()
