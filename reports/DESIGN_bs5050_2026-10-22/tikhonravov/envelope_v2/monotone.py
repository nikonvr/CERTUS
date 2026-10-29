"""Repair the free 50/50 envelope where RMSE(N) > RMSE(N-1), which no best design can do.

For free thicknesses the best N-layer RMSE is at most the best (N-1)-layer one: an (N-1)-layer design plus a vanishing
layer at either end has N layers and the same spectrum. Every point above its left neighbour is a search failure.
Candidates for N, all polished with every layer kept at or above DEAD = 1 nm so that the layer count is kept:
  the (N-1)-layer design plus a 1 nm layer of the other material at the substrate end or at the air end;
  the (N-2)-layer design plus a 1 nm needle at each of the 12 best places of its P-function;
  the current N-layer design itself (re-polished).
Passes go up in N and repeat until no point improves (at most PASSES). Every kept RMSE is re-judged by the oracle.

usage: python monotone.py CURVE.csv [CURVE.csv ...]   -> curve_mono_free.csv, monotone.txt
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import search as s

HERE = Path(__file__).resolve().parent
DEAD, PASSES, N_LO, N_HI = 1.0, 6, 10, 40


def polish_keep(seq: str, d: np.ndarray) -> tuple[np.ndarray, float]:
    return s.polish(seq, np.maximum(d, DEAD), DEAD, max_nfev=600)


def main() -> None:
    best: dict[int, tuple[float, str, np.ndarray]] = {}
    for f in sys.argv[1:]:
        for r in csv.DictReader((HERE / f).open(encoding="utf-8")):
            seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
            n = len(seq)
            if N_LO <= n <= N_HI and np.min(d) >= DEAD * 0.999:
                v = s.rmse(seq, d)
                if v < best.get(n, (np.inf,))[0]:
                    best[n] = (v, seq, d)
    before = {n: best[n][0] for n in best}
    out = ["free 50/50: repair of RMSE(N) > RMSE(N-1) (kernel values; oracle in the CSV)"]
    for p in range(1, PASSES + 1):
        changed = 0
        for n in range(N_LO + 1, N_HI + 1):
            cands = []
            if n - 1 in best:
                _r, sq, d = best[n - 1]
                cands.append((s.other(sq[0]) + sq, np.concatenate([[DEAD], d])))
                cands.append((sq + s.other(sq[-1]), np.concatenate([d, [DEAD]])))
            if n - 2 in best:
                _r, sq, d = best[n - 2]
                for s2, d2, j in s.needle_scan(sq, d, keep=12):
                    d2 = d2.copy()
                    d2[j] = DEAD
                    cands.append((s2, d2))
            if n in best:
                cands.append(best[n][1:])
            for sq, d in cands:
                if len(sq) != n:
                    continue
                x, r = polish_keep(sq, d)
                if r < best.get(n, (np.inf,))[0] * (1 - 1e-9):
                    best[n] = (r, sq, x)
                    changed += 1
        bad = [n for n in sorted(best) if n - 1 in best and best[n][0] > best[n - 1][0] * (1 + 1e-9)]
        out.append(f"pass {p}: {changed} improvements; points still above their left neighbour: {bad}")
        print(out[-1], flush=True)
        if changed == 0:
            break
    rows = []
    for n in sorted(best):
        r, seq, d = best[n]
        out.append(f"N={n:2d} {before.get(n, np.nan):.4e} -> {r:.4e}")
        rows.append({"layers": n, "rmse_1601_oracle": s.oracle_rmse(seq, d), "rmse_1601_kernel": r,
                     "old": before.get(n, ""), "first_mat": seq[0], "last_mat": seq[-1],
                     "thinnest_nm": float(np.min(d)),
                     "total_qwot": float(np.sum(d * np.array([4 * s.N_IDX[m] for m in seq]) / s.L0)),
                     "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
    with (HERE / "curve_mono_free.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (HERE / "monotone.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[-len(rows):]))


if __name__ == "__main__":
    main()
