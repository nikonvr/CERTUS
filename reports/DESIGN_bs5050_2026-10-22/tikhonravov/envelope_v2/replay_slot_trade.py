"""Replay of the slot trade of 2026-11-01 09:03 on 0.012210 (its run keeps the result in memory until it ends).

needle F@6 (best P-function depth) + merge 35L+36F + delete Ag 9, polished; then the descent steps
8T 28T 23M 22H, 27M 29B 28H 25L, 42F (each applied as cissoid_multiswap.apply, polished on the 301 points).
usage: python replay_slot_trade.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import sys

import cissoid_fixedN as fx
import cissoid_multiswap as ms
import cissoid_opt as co
import cissoid_slot_trade as st
import numpy as np

STEPS = ["8T 28T 23M 22H", "27M 29B 28H 25L", "42F"]


def main() -> None:
    r0 = list(csv.DictReader((co.s.HERE / sys.argv[1]).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    m, d, base = co.polish_full((m, d, co.FLOOR))
    p = sorted(g for c in co.NEEDLE_MATS for g in fx._p_one((m, d, c)))
    z = next(z for g, cand, i, z in p if cand == "F" and i == 6 and g < 0)
    m1, d1 = co.normalize(*co.insert(m, d, "F", 6, z, 10.0), 0.5)
    extra = len(m1) - len(m)
    for op in sorted([("merge", 35), ("del", 9)], key=lambda t: -t[1]):
        m1, d1 = st.apply_free(m1, d1, (op[0], op[1] + (extra if op[1] >= 6 else 0)))
    m1, d1, f = co.polish_full((*co.normalize(m1, d1, 0.0), co.FLOOR))
    print(f"base {base:.6f}; needle F@6 z={z:.1f} + merge 35L+36F + delete 9A: N {len(m1)}, MF {f:.6f}", flush=True)
    for s in STEPS:
        sw = [(int(t[:-1]), t[-1]) for t in s.split()]
        m1, d1, f = co.polish_full((*ms.apply(m1, d1, sw), co.FLOOR, 300))
        print(f"  {s}: N {len(m1)}, MF {f:.6f}", flush=True)
    o = co.oracle_mf(m1, d1)
    st.save(sys.argv[2], m1, d1, f, "needle F@6 + merge 35L+36F + delete 9A + " + " + ".join(STEPS))
    print(f"oracle {o:.6f}, min d {d1.min():.2f} nm, materials {''.join(sorted(set(m1)))}", flush=True)


if __name__ == "__main__":
    main()
