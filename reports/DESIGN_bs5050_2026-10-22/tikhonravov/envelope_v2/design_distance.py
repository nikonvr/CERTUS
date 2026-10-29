"""Structural distance between two-material designs with different numbers of layers (2026-10-29).

A design is a sequence of (material, optical thickness), layer 1 next to the substrate. Two designs are aligned by
dynamic programming (Needleman-Wunsch, semi-global), with the moves that keep the index profile continuous:
  - match: a layer of A with a layer of B of the same material, cost |t_a - t_b|;
  - gap: a layer of one design absent from the other, cost its optical thickness;
  - merge: three layers m, x, m of one design against one layer m of the other (a needle x), cost
    |t1 + t3 - u| + t_x;
  - end gaps (a section at the substrate or at the air side, e.g. an impedance-matching prefix): the first FREE nm
    of optical thickness of each unmatched end are free, the rest costs its optical thickness. FREE caps the
    section, otherwise the whole of A as a prefix and the whole of B as a suffix would cost nothing.
The distance is the cost of the best alignment in nm of optical thickness; it is reported raw and divided by the
mean TOT of the two designs. FREE = 0 is a true metric on profiles up to merges; FREE > 0 measures core similarity.

usage: python design_distance.py CSV1[:ROW] CSV2[:ROW] [FREE]   (rows default 0; columns seq and d_nm; FREE nm)
       python design_distance.py --matrix CSV [FREE]            (all pairs of rows of one csv)
"""

from __future__ import annotations

import csv
import sys

import numpy as np

N_IDX = {"H": 2.35, "L": 1.45}


def layers(seq: str, d) -> list[tuple[str, float]]:
    return [(m, float(x) * N_IDX[m]) for m, x in zip(seq, d, strict=True)]


def align(a: list[tuple[str, float]], b: list[tuple[str, float]], free: float = 0.0):
    """Best alignment cost and its moves; dp[i][j] = cost of aligning a[:i] with b[:j]."""
    na, nb = len(a), len(b)
    inf = float("inf")
    dp = np.full((na + 1, nb + 1), inf)
    back: dict[tuple[int, int], tuple[int, int, str]] = {}
    ca = np.concatenate([[0.0], np.cumsum([t for _m, t in a])])
    cb = np.concatenate([[0.0], np.cumsum([t for _m, t in b])])
    dp[0, :] = np.maximum(0.0, cb - free)  # a prefix of B without counterpart (substrate side)
    dp[:, 0] = np.maximum(0.0, ca - free)
    for i in range(1, na + 1):
        for j in range(1, nb + 1):
            best, how = inf, None
            ma, ta = a[i - 1]
            mb, tb = b[j - 1]
            if ma == mb and dp[i - 1, j - 1] + abs(ta - tb) < best:
                best, how = dp[i - 1, j - 1] + abs(ta - tb), (i - 1, j - 1, "match")
            if dp[i - 1, j] + ta < best:
                best, how = dp[i - 1, j] + ta, (i - 1, j, "gap A")
            if dp[i, j - 1] + tb < best:
                best, how = dp[i, j - 1] + tb, (i, j - 1, "gap B")
            if i >= 3 and a[i - 3][0] == a[i - 1][0] == mb:
                c = dp[i - 3, j - 1] + abs(a[i - 3][1] + ta - tb) + a[i - 2][1]
                if c < best:
                    best, how = c, (i - 3, j - 1, "merge A")
            if j >= 3 and b[j - 3][0] == b[j - 1][0] == ma:
                c = dp[i - 1, j - 3] + abs(b[j - 3][1] + tb - ta) + b[j - 2][1]
                if c < best:
                    best, how = c, (i - 1, j - 3, "merge B")
            dp[i, j] = best
            back[(i, j)] = how
    # unmatched suffix (air side) of either design, its first FREE nm free
    cands = [(dp[i, nb] + max(0.0, ca[na] - ca[i] - free), i, nb) for i in range(na + 1)]
    cands += [(dp[na, j] + max(0.0, cb[nb] - cb[j] - free), na, j) for j in range(nb + 1)]
    cost, i, j = min(cands)
    moves = []
    while i > 0 and j > 0:
        pi, pj, kind = back[(i, j)]
        moves.append((kind, pi, i, pj, j))
        i, j = pi, pj
    return cost, moves[::-1], (i, j)


def load(spec: str):
    path, _, row = spec.partition(":")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    r = rows[int(row or 0)]
    return r["seq"], [float(v) for v in r["d_nm"].split()]


def summary(a, b, free: float) -> str:
    cost, moves, _start = align(a, b, free)
    tot = 0.5 * (sum(t for _m, t in a) + sum(t for _m, t in b))
    kinds = {k: sum(1 for m in moves if m[0] == k) for k in ("match", "gap A", "gap B", "merge A", "merge B")}
    first = moves[0] if moves else None
    off = f"core starts at A{first[1] + 1}/B{first[3] + 1}" if first else "no core"
    return (f"N {len(a)}/{len(b)} TOT {sum(t for _m, t in a):.0f}/{sum(t for _m, t in b):.0f} FREE {free:g} nm: "
            f"distance {cost:.0f} nm ({100 * cost / tot:.1f} % TOT), {off}, " + ", ".join(f"{k} {v}" for k, v in kinds.items() if v))


def main() -> None:
    if sys.argv[1] == "--matrix":
        path, free = sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        ds = [layers(r["seq"], [float(v) for v in r["d_nm"].split()]) for r in rows]
        m = np.zeros((len(ds), len(ds)))
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                c = align(ds[i], ds[j], free)[0]
                m[i, j] = m[j, i] = 100 * c / (0.5 * (sum(t for _m, t in ds[i]) + sum(t for _m, t in ds[j])))
        print(f"distance in % of mean TOT, FREE {free:g} nm")
        for i, row in enumerate(m):
            print(f"{i:2d} " + " ".join(f"{v:5.1f}" for v in row))
        return
    free = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    a, b = (layers(*load(x)) for x in sys.argv[1:3])
    print(summary(a, b, free))


if __name__ == "__main__":
    main()
