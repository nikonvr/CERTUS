"""MF barrier between two designs along their alignment path, refined by the string method (2026-10-29).

1. `design_distance.align` pairs the layers of A and B (match, gap, merge, capped free ends).
2. Both designs are written in one common superset sequence: a matched pair is one layer going from t_a to t_b; a
   gap layer shrinks to (or grows from) zero; a merge m x m -> m keeps the two m layers (their sum going to u, in
   proportion) and shrinks the needle x to zero. At s = 0 the superset profile is A, at s = 1 it is B (zero-thickness
   layers and adjacent layers of one material change nothing optically).
3. The straight path in that space gives an upper bound of the barrier; the simplified string method (E, Ren,
   Vanden-Eijnden, J. Chem. Phys. 126, 164103, 2007) relaxes it towards the minimum energy path: every interior image
   takes a gradient step on MF^2, then the images are redistributed at equal arc length; endpoints fixed. Physical
   thicknesses stay >= 0; with BOX the layers matched in both designs also stay within the 100-350 nm OT box.

Reported: MF at A and B, highest MF on the straight path and on the relaxed string (barrier = highest MF minus the
higher endpoint), and the total variation of MF along the string (sum of climbs and descents, the Agmon length of
the path for a gradient-like path).

usage: python barrier.py CSV1[:ROW] CSV2[:ROW] [FREE] [ITERS]   (env SEARCH_TARGET, BARRIER_BOX=1, BARRIER_IMAGES)
outputs: barrier_<name1>_<name2>.csv (MF along the straight path and the string)
"""

from __future__ import annotations

import csv
import os
import sys

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from design_distance import align, layers, load  # noqa: E402

IMAGES = int(os.environ.get("BARRIER_IMAGES", "33"))
BOX = os.environ.get("BARRIER_BOX", "") == "1"
OT_LO, OT_HI = 100.0, 350.0


def superset(a, b, free: float):
    """(seq, d at s=0, d at s=1, boxed flags) in physical nm, from the alignment of a and b (optical nm)."""
    _cost, moves, (i0, j0) = align(a, b, free)
    seq, x0, x1, boxed = [], [], [], []

    def put(m, ta, tb, bx=False):
        seq.append(m)
        x0.append(ta / s.N_IDX[m])
        x1.append(tb / s.N_IDX[m])
        boxed.append(bx)

    for m, t in a[:i0]:  # unmatched substrate-side layers of A, then of B
        put(m, t, 0.0)
    for m, t in b[:j0]:
        put(m, 0.0, t)
    i, j = i0, j0
    for kind, pi, ci, pj, cj in moves:
        for m, t in a[i:pi]:  # layers skipped between moves (none expected, kept for safety)
            put(m, t, 0.0)
        for m, t in b[j:pj]:
            put(m, 0.0, t)
        if kind == "match":
            put(a[pi][0], a[pi][1], b[pj][1], True)
        elif kind == "gap A":
            put(a[pi][0], a[pi][1], 0.0)
        elif kind == "gap B":
            put(b[pj][0], 0.0, b[pj][1])
        elif kind == "merge A":
            (m, t1), (x, tx), (_m, t3) = a[pi:ci]
            u = b[pj][1]
            put(m, t1, u * t1 / (t1 + t3))
            put(x, tx, 0.0)
            put(m, t3, u * t3 / (t1 + t3))
        else:
            (m, u1), (x, ux), (_m, u3) = b[pj:cj]
            t = a[pi][1]
            put(m, t * u1 / (u1 + u3), u1)
            put(x, 0.0, ux)
            put(m, t * u3 / (u1 + u3), u3)
        i, j = ci, cj
    for m, t in a[i:]:  # unmatched air-side layers
        put(m, t, 0.0)
    for m, t in b[j:]:
        put(m, 0.0, t)
    return "".join(seq), np.array(x0), np.array(x1), np.array(boxed)


def mf(st, x) -> float:
    r = st.res_jac(x)[0]
    return 100.0 * float(np.sqrt(r @ r))


def grad(st, x) -> np.ndarray:
    r, j, _c = st.res_jac(x)
    return 2.0 * j.T @ r


def reparam(path: np.ndarray) -> np.ndarray:
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    sc = np.concatenate([[0.0], np.cumsum(seg)])
    sc /= sc[-1]
    tgt = np.linspace(0.0, 1.0, len(path))
    return np.array([np.interp(tgt, sc, path[:, k]) for k in range(path.shape[1])]).T


def profile(st, path: np.ndarray, fine: int = 8) -> np.ndarray:
    """MF on the path, `fine` points per segment (piecewise linear between images)."""
    out = [mf(st, np.maximum(0.0, (1 - f) * path[k] + f * path[k + 1]))
           for k in range(len(path) - 1) for f in np.linspace(0.0, 1.0, fine, endpoint=False)]
    out.append(mf(st, path[-1]))
    return np.array(out)


def main() -> None:
    spec_a, spec_b = sys.argv[1], sys.argv[2]
    free = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    iters = int(sys.argv[4]) if len(sys.argv) > 4 else 3000
    a, b = layers(*load(spec_a)), layers(*load(spec_b))
    seq, x0, x1, boxed = superset(a, b, free)
    st = s.Stack.of(seq)
    n = np.array([s.N_IDX[m] for m in seq])
    lo = np.where(boxed & BOX, OT_LO / n, 0.0)
    hi = np.where(boxed & BOX, OT_HI / n, np.inf)
    ma, mb = mf(st, x0), mf(st, x1)
    print(f"superset N {len(seq)} (A {len(a)}, B {len(b)}), MF A {ma:.4f} B {mb:.4f} (check: designs alone "
          f"{100 * s.rmse(*_alone(spec_a)):.4f} {100 * s.rmse(*_alone(spec_b)):.4f})", flush=True)
    path = np.linspace(x0, x1, IMAGES)
    straight = profile(st, path)
    print(f"straight path: max MF {straight.max():.4f}, barrier {straight.max() - max(ma, mb):.4f}", flush=True)
    h = 0.5  # nm, largest move of one image per iteration
    for it in range(iters):
        g = np.array([grad(st, x) for x in path[1:-1]])
        step = h / max(1e-30, np.abs(g).max())
        path[1:-1] = np.clip(path[1:-1] - step * g, lo, hi)
        path = reparam(path)
        if it % 500 == 499 or it == iters - 1:
            vals = np.array([mf(st, x) for x in path])
            print(f"iter {it + 1}: images max MF {vals.max():.4f} at s {vals.argmax() / (len(path) - 1):.2f}",
                  flush=True)
            h = max(0.05, 0.7 * h)
    relaxed = profile(st, path)
    tv = float(np.abs(np.diff(relaxed)).sum())
    k = int(relaxed.argmax())
    print(f"string: max MF {relaxed.max():.4f} at s {k / (len(relaxed) - 1):.3f}, barrier "
          f"{relaxed.max() - max(ma, mb):.4f} (from A {relaxed.max() - ma:.4f}, from B {relaxed.max() - mb:.4f}); "
          f"total variation {tv:.4f}; local minima on the string "
          f"{int(np.sum((relaxed[1:-1] < relaxed[:-2]) & (relaxed[1:-1] < relaxed[2:])))}", flush=True)
    tag = "_".join(x.replace(".csv", "").replace(":", "r").replace("/", "_").replace("\\", "_")[-24:]
                   for x in (spec_a, spec_b))
    with (s.HERE / f"barrier_{tag}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["s", "mf_straight", "mf_string"])
        for q, (u, v) in enumerate(zip(straight, relaxed, strict=True)):
            w.writerow([f"{q / (len(relaxed) - 1):.5f}", f"{u:.6f}", f"{v:.6f}"])


def _alone(spec: str):
    seq, d = load(spec)
    return seq, np.array(d)


if __name__ == "__main__":
    main()
