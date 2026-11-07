"""OIC 2016 B1 (cissoid): full swap descent from one row of a csv, result in its own file (2026-11-01).

The descent of flair_campaign (N1, metal trades, ADD, N2; up to 6 rounds) from the row whose "step" is STEP ("" = the
last row); the result goes to OUT only, never to cissoid_record_best.csv: take_record.py decides against the record.
Used for plateau moves, e.g. the neutral T -> H steps of cissoid_reduce_T.csv.
usage: python descend_from.py IN.csv STEP OUT.csv
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_opt as co
import cissoid_slot_trade as st
import flair_campaign as fc
import numpy as np


def main() -> None:
    src, step, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    r0 = next(r for r in rows if r["step"] == step) if step else rows[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, co.FLOOR))
        print(f"start {f:.6f}, N {len(m)}", flush=True)
        m, d, f, steps = fc.descend(pool, m, d, f, names=("N1", "MT", "ADD", "N2"), rounds=6)
        o = st.save(dst, m, d, f, f"{src} step {step or 'last'} + " + " + ".join(steps))
        print(f"end {f:.6f} oracle {o:.6f} {steps}", flush=True)


if __name__ == "__main__":
    main()
