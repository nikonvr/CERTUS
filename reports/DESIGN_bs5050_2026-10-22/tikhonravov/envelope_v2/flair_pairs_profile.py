"""OIC 2016 B1 (cissoid): which pairs of swaps score best at 30 polish iterations, against all 15750 (2026-11-01).

Reads the per-candidate csv of flair_backtest.py (pre-designs E 0.01375, G 0.01316, I 0.01299) and compares the TOP
pairs by sp30 with all pairs on: distance between the two layers, both moves ladder neighbours (F<L<B<M<T<H), same
direction of index change, layers in 10-19 or 40-49, metal neighbour, optical thickness. Prints enrichment = share in
the top / share in all.
usage: python flair_pairs_profile.py DATA_DIR [TOP]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import cissoid_opt as co
import numpy as np

LADDER = "FLBMTH"
PRE = {"E": "cissoid_record_0p01375.csv", "G": "cissoid_record_0p01316.csv", "I": "cissoid_record_0p01299.csv"}


def features(m, d, a, b):
    (i, y), (j, z) = a, b
    si = np.sign(LADDER.index(y) - LADDER.index(m[i]))
    sj = np.sign(LADDER.index(z) - LADDER.index(m[j]))
    lad = abs(LADDER.index(y) - LADDER.index(m[i])) == 1 and abs(LADDER.index(z) - LADDER.index(m[j])) == 1
    hot = lambda k: 10 <= k <= 19 or 40 <= k <= 49  # noqa: E731
    metal_nb = lambda k: any(0 <= q < len(m) and m[q] in "AUN" for q in (k - 1, k + 1))  # noqa: E731
    ot = lambda k: co.MATS[m[k]] * d[k]  # noqa: E731
    return {
        "dist<=3": abs(i - j) <= 3,
        "dist<=1": abs(i - j) <= 1,
        "both ladder": lad,
        "same direction": si == sj,
        "both hot": hot(i) and hot(j),
        "one hot": hot(i) or hot(j),
        "both next to metal": metal_nb(i) and metal_nb(j),
        "both OT<150": ot(i) < 150 and ot(j) < 150,
        "one OT>600": ot(i) > 600 or ot(j) > 600,
    }


def parse(tok, m):
    return [(int(t[:-1]), t[-1]) for t in tok.split()]


def main() -> None:
    data, top = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 50
    for tag, src in PRE.items():
        r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
        m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
        rows = [r for r in csv.DictReader((data / f"flair_{tag}.csv").open(encoding="utf-8")) if " " in r["swaps"]]
        sp30 = np.array([float(r["sp30"]) for r in rows])
        order = np.argsort(sp30)
        feats = [features(m, d, *parse(r["swaps"], m)) for r in rows]
        keys = list(feats[0])
        base = {k: np.mean([f[k] for f in feats]) for k in keys}
        best = {k: np.mean([feats[q][k] for q in order[:top]]) for k in keys}
        print(f"[{tag}] {len(rows)} pairs, best sp30 {sp30[order[0]]:.5f} [{rows[order[0]]['swaps']}], "
              f"top {top} up to {sp30[order[top - 1]]:.5f}")
        for k in keys:
            enr = best[k] / base[k] if base[k] else float("nan")
            print(f"  {k:20s} all {base[k]:.3f}  top {best[k]:.3f}  x{enr:.1f}")
        layers = np.bincount([i for q in order[:top] for i, _ in parse(rows[q]["swaps"], m)], minlength=len(m))
        print("  layers most often in the top: " + " ".join(f"{i}{m[i]}:{c}" for i, c in
                                                           sorted(enumerate(layers), key=lambda t: -t[1])[:10]))


if __name__ == "__main__":
    main()
