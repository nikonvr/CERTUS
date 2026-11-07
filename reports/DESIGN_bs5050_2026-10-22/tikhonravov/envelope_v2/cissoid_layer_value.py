"""OIC 2016 B1 (cissoid): what each slot of a 50-layer design is worth (2026-11-01 audit of 0.012210).

Cost of freeing one slot: delete each layer, or merge each pair of neighbouring dielectrics into one of the six fitted
to their characteristic matrix (cissoid_collapse.single_for); each polished on the 301 points. Gain of one more slot:
each of the K best needles (P-function), polished. A fixed-N exchange can only gain if the cheapest freeing costs less
than the best needle gains.
usage: python cissoid_layer_value.py IN.csv
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ProcessPoolExecutor

import cissoid_collapse as cc
import cissoid_fixedN as fx
import cissoid_opt as co
import numpy as np


def main() -> None:
    r0 = list(csv.DictReader((co.s.HERE / sys.argv[1]).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, base = co.polish_full((m, d, co.FLOOR))
        cands = [(f"delete {i}{m[i]}", *co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0)) for i in range(len(m))]
        for i in range(len(m) - 1):
            if m[i] in cc.DIEL and m[i + 1] in cc.DIEL:
                y, t, _e = cc.single_for(m[i:i + 2], d[i:i + 2])
                cands.append((f"merge {i}{m[i]}+{i + 1}{m[i + 1]}->{y}",
                              *co.normalize([*m[:i], y, *m[i + 2:]], np.concatenate([d[:i], [t], d[i + 2:]]), 0.0)))
        res = list(pool.map(co.polish_full, [(cm, cd, co.FLOOR) for _h, cm, cd in cands], chunksize=2))
        cost = sorted(((q[2] / base - 1) * 100, h, len(q[0])) for (h, _a, _b), q in zip(cands, res, strict=True))
        print(f"base {base:.6f}; cheapest ways to free a slot (MF change):", flush=True)
        for c, h, n in cost[:10]:
            print(f"  {h}: N {n}, {c:+.2f} %", flush=True)
        p = sorted(g for part in pool.map(fx._p_one, [(m, d, c) for c in co.NEEDLE_MATS]) for g in part)
        needles, used = [], set()
        for g, cand, i, z in p:
            if g >= 0 or len(needles) >= 2 * co.K:
                break
            if (cand, i, z == 0.0) not in used:
                used.add((cand, i, z == 0.0))
                needles.append((cand, i, z))
        grown = list(pool.map(co.polish_full, [(*co.insert(m, d, c, i, z), co.FLOOR) for c, i, z in needles]))
        gain = sorted(((q[2] / base - 1) * 100, f"needle {c}@{i} z={z:.1f}", len(q[0]))
                      for (c, i, z), q in zip(needles, grown, strict=True))
        print("best needles (MF change, d >= 3 nm):", flush=True)
        for c, h, n in gain[:10]:
            print(f"  {h}: N {n}, {c:+.2f} %", flush=True)


if __name__ == "__main__":
    main()
