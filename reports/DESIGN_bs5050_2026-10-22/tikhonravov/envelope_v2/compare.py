"""Greedy against deep-search gradual evolution (Trubetskov, Appl. Opt. 59, A75, 2020, §2-3) on the 50/50 problem.

Same problem, refinement (`search.polish`: trf with exact CERTUS Jacobian) and judge as `search.py`; free thicknesses.
Both start from one 106 nm H layer (A75 §4E) and loop:
  needle step:   P-function sampled every 3 nm with 0.3 nm needles of the other material (`search.p_scan`);
                 greedy inserts at the global minimum, deep inserts at every local minimum, refines each, keeps the best.
  TOT step:      when no needle lowers the MF, each layer in turn is thickened to its next one-parameter MF minimum;
                 greedy keeps the smallest unrefined degradation, deep refines every variant and keeps the best.
Every refined design is written as (seconds, N, QWOT, RMSE) to traj_{mode}.csv.

usage: python compare.py {greedy,deep} MINUTES
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
import search as s

HERE = Path(__file__).resolve().parent
FLOOR, DEAD, N_STOP = 0.1, 1.0, 44
DEBUG = False


def qwot(seq: str, d: np.ndarray) -> float:
    return float(np.sum(d * np.array([4 * s.N_IDX[m] for m in seq]) / s.L0))


def refine(seq: str, d: np.ndarray) -> tuple[str, np.ndarray, float]:
    x, r = s.polish(seq, d, FLOOR, max_nfev=600)
    s2, x2 = s.normalize(seq, x, DEAD)
    if s2 != seq:
        x2, r = s.polish(s2, x2, FLOOR, max_nfev=600)
    return s2, x2, r


def next_minimum(seq: str, d: np.ndarray, k: int, step: float = 1.0, span: float = 400.0):
    """Thicken layer k up to the next local minimum of the one-parameter MF (A75 §2); None if there is none."""
    vals = []
    for t in np.arange(step, span, step):
        d2 = d.copy()
        d2[k] += t
        vals.append(s.mse_only(seq, d2))
        if len(vals) >= 3 and vals[-2] < vals[-3] and vals[-2] <= vals[-1]:
            d2[k] -= step
            return d2
    return None


def needle_candidates(seq: str, d: np.ndarray, deep: bool):
    base = s.mse_only(seq, d)
    scan = [(s.mse_only(s.other(seq[0]) + seq, np.concatenate([[0.3], d])) - base, s.other(seq[0]) + seq,
             np.concatenate([[0.3], d]), 0)]
    scan += s.p_scan(seq, d)
    end = seq + s.other(seq[-1]), np.concatenate([d, [0.3]])
    scan.append((s.mse_only(*end) - base, end[0], end[1], len(seq)))
    neg = [c for c in scan if c[0] < 0.0]
    if not neg:
        return []
    if not deep:
        return [min(neg, key=lambda c: c[0])]
    out = []
    for k, c in enumerate(scan):  # local minima along z inside each layer
        g, i = c[0], c[3]
        left = scan[k - 1] if k > 0 and scan[k - 1][3] == i else None
        right = scan[k + 1] if k + 1 < len(scan) and scan[k + 1][3] == i else None
        if g < 0.0 and (left is None or left[0] >= g) and (right is None or right[0] > g):
            out.append(c)
    return out


def main() -> None:
    mode, minutes = sys.argv[1], float(sys.argv[2])
    deep = mode == "deep"
    t0 = time.time()
    seq, d = "H", np.array([106.0])
    seq, d, r = refine(seq, d)
    rows = []

    def record(sq: str, x: np.ndarray, rr: float, step: str) -> None:
        rows.append({"seconds": round(time.time() - t0, 1), "step": step, "layers": len(sq), "qwot": qwot(sq, x),
                     "rmse": rr, "seq": sq, "d_nm": " ".join(f"{v:.6f}" for v in x)})
        print(f"{rows[-1]['seconds']:8.1f}s {step:6s} N={len(sq):2d} QWOT={rows[-1]['qwot']:6.2f} RMSE={rr:.4e}", flush=True)

    record(seq, d, r, "seed")
    while time.time() - t0 < 60.0 * minutes and len(seq) <= N_STOP:
        best = None
        for _g, s2, d2, j in needle_candidates(seq, d, deep):
            d2 = d2.copy()
            d2[j] = 1.0
            cand = refine(s2, d2)
            if cand[2] < r * (1 - 1e-6) and (best is None or cand[2] < best[2]):
                best = cand
        step = "needle"
        if best is None:  # forced increase of the total optical thickness
            step, raw = "tot", []
            for k in range(len(seq)):
                d2 = next_minimum(seq, d, k)
                if d2 is not None:
                    raw.append((s.rmse(seq, d2), d2))
            raw.sort(key=lambda t: t[0])
            q0, kept = qwot(seq, d), []
            for _r, d2 in raw:  # a refinement that falls back to the old design is not an increase
                cand = refine(seq, d2)
                if DEBUG:
                    print(f"   tot try q0={q0:.3f} raw={qwot(seq, d2):.3f} refined={qwot(cand[0], cand[1]):.3f} N={len(cand[0])}")
                if qwot(cand[0], cand[1]) > q0 + 0.05:
                    kept.append(cand)
                    if not deep:
                        break
            if not kept:
                break
            best = min(kept, key=lambda t: t[2])
        seq, d, r = best
        record(seq, d, r, step)

    with (HERE / f"traj_{mode}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
