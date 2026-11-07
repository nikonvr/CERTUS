"""OIC 2016 B1 (cissoid): the record under a cap on the dielectric optical thickness (2026-11-01, owner: <= 20 000 nm
without losing merit; the record 0.009210 has 20 131 nm).

Run with CISSOID_OTMAX set (cissoid_opt adds one residual for the excess over the cap): the design is polished under the
cap, then descended (N1, metal trades, ADD, N2 of flair_campaign, up to 8 rounds) and beamed (3-5 swaps), every polish
working under the cap; the result goes to OUT only (never to the record files), with its dielectric optical thickness
and the oracle's MF.
usage: CISSOID_OTMAX=19995 python cissoid_ot_cap.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import cissoid_slot_trade as st
import flair_campaign as fc
import numpy as np


def ot_d(m, d) -> float:
    return float(sum(float(np.real(co.MATS[x])) * t for x, t in zip(m, d, strict=True) if not np.iscomplex(co.MATS[x])))


def report(tag, m, d, t0) -> None:
    print(f"{tag}: N {len(m)}, OT_d {ot_d(m, d):.1f} nm, oracle {co.oracle_mf(m, d):.6f} ({time.time() - t0:.0f} s)",
          flush=True)


def main() -> None:
    assert co.OTMAX, "set CISSOID_OTMAX"
    src, dst = sys.argv[1], sys.argv[2]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    report("start", m, d, t0)
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, co.FLOOR))
        report(f"polished under the cap {co.OTMAX:.0f} nm", m, d, t0)
        for rnd in range(3):
            m, d, f, steps = fc.descend(pool, m, d, f, names=("N1", "MT", "ADD", "N2"), rounds=8)
            report(f"round {rnd + 1} descent {steps}", m, d, t0)
            got = fc.stage(pool, "BEAM", m, d, f)
            if not (fc.ok(got[1], got[2]) and got[0] < f * (1 - 1e-4)):
                break
            m, d, f = got[1], got[2], got[0]
            report(f"round {rnd + 1} beam [{got[3]}]", m, d, t0)
        o = st.save(dst, m, d, f, f"cap {co.OTMAX:.0f} nm on {src}")
        print(f"done: OT_d {ot_d(m, d):.1f} nm, oracle {o:.6f}, min d {d.min():.2f} nm -> {dst}", flush=True)


if __name__ == "__main__":
    main()
