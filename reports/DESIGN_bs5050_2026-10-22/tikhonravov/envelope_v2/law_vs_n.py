"""Does every layer contribute the same sensitivity? Robust selection at several N, random optical-thickness errors.

For each N, the catalogue law{N}.csv (`CAT_N=N CAT_PREFIX=law{N} python catalog.py build ...`) is a sample of nominal
local minima. For every design: S = sum_i |dr/dOT_i|^2 (sensitivity per nm of OT error, squared; second order:
E[MSE] = MSE0 + sigma^2 S). Robust selection: the design minimising MSE0 + sigma^2 S at sigma = 0.5 nm OT, checked by
Monte Carlo (400 draws, kernel, first 3 checked with the oracle). Reported per N:
  s = sqrt(S) of the robust design, min and median of s over the good designs (MSE0 within 4x the best),
  S / N (contribution per layer) and the spread of the per-layer contributions in the robust design (max / mean, and the
  share of the 3 largest).
Law tested: S proportional to N (S / N constant). Fit of log S against log N over the robust designs.

usage: python law_vs_n.py N [N ...]   -> law_vs_n.txt, law_vs_n.png
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import numpy as np
import search as s

HERE = Path(__file__).resolve().parent
SIG, DRAWS, SEED = 0.5, 400, 20261028
PREFIX = os.environ.get("LAW_PREFIX", "law")  # catalogues {PREFIX}{N}.csv; outputs {PREFIX}_vs_n.*


def design_stats(seq: str, d: np.ndarray) -> tuple[float, float, np.ndarray]:
    r, j, _c = s.Stack.of(seq).res_jac(d)
    per_layer = np.sum((j / np.array([s.N_IDX[m] for m in seq])) ** 2, axis=0)
    return float(np.sum(r * r)), float(per_layer.sum()), per_layer


def main() -> None:
    ns = [int(v) for v in sys.argv[1:]]
    out = [f"random OT errors; robust selection at sigma = {SIG} nm; s = sqrt(S), S = sum_i |dr/dOT_i|^2 (per nm^2)",
           " N  designs  robust: nominal    s        MC/pred  S/N       max/mean  top3  | good designs: s min  s median"]
    pts = []
    for n in ns:
        rows = list(csv.DictReader((HERE / f"{PREFIX}{n}.csv").open(encoding="utf-8")))
        st = []
        for r in rows:
            d = np.array([float(v) for v in r["d_nm"].split()])
            mse0, S, per = design_stats(r["seq"], d)
            st.append((mse0 + SIG ** 2 * S, mse0, S, per, r["seq"], d))
        best = min(st, key=lambda t: t[0])
        mse_min = min(t[1] for t in st)
        good = [t for t in st if t[1] <= 4 * mse_min]
        s_good = np.sqrt([t[2] for t in good])
        _cost, mse0, S, per, seq, d = best
        stk = s.Stack.of(seq)
        z = np.random.default_rng((SEED, n)).standard_normal((DRAWS, n)) * SIG / np.array([s.N_IDX[m] for m in seq])
        mse = []
        for k, zk in enumerate(z):
            dk = np.maximum(d + zk, 0.0)
            mse.append(float(np.sum(stk.res_jac(dk)[0] ** 2)))
            if k < 3 and abs(s.oracle_rmse(seq, dk) - np.sqrt(mse[-1])) > 1e-3 * np.sqrt(mse[-1]):
                raise SystemExit(f"oracle disagrees with the kernel at N={n}, draw {k}")
        ratio = np.sqrt(np.mean(mse)) / np.sqrt(mse0 + SIG ** 2 * S)
        top3 = np.sort(per)[::-1][:3].sum() / per.sum()
        out.append(f"{n:2d}  {len(st):6d}   {np.sqrt(mse0):.2e}  {np.sqrt(S):.3e}  {ratio:.2f}     {S / n:.2e}  "
                   f"{per.max() / per.mean():5.2f}    {top3:.2f}  |  {s_good.min():.3e}  {np.median(s_good):.3e}"
                   f"  ({len(good)} good)")
        pts.append((n, S, s_good.min() ** 2, np.sqrt(mse0)))
    n_arr = np.array([p[0] for p in pts], float)
    out.insert(0, f"nH = {s.N_IDX['H']}, nL = {s.N_IDX['L']}, catalogues {PREFIX}<N>.csv")
    if len(pts) < 2:  # one N: no fit, no plot
        (HERE / f"{PREFIX}_vs_n.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
        print("\n".join(out))
        return
    for label, col in (("robust design", 1), ("min over good designs", 2)):
        slope, _icpt = np.polyfit(np.log(n_arr), np.log([p[col] for p in pts]), 1)
        out.append(f"fit S ~ N^a ({label}): a = {slope:.2f}  (a = 1: every layer contributes the same)")
    (HERE / f"{PREFIX}_vs_n.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(n_arr, [np.sqrt(p[1]) for p in pts], "o-", label="s of the robust design (sigma = 0.5 nm OT)")
    ax.loglog(n_arr, [np.sqrt(p[2]) for p in pts], "s--", label="min s over good designs")
    ref = np.sqrt(pts[0][1] / pts[0][0] * n_arr)
    ax.loglog(n_arr, ref, "k:", label="s proportional to sqrt(N)")
    ax.set_xlabel("number of layers N")
    ax.set_ylabel("s = sqrt(sum |dr/dOT_i|^2), per nm of OT error")
    ax.set_title("50/50 splitter: sensitivity to random OT errors against N")
    ax.grid(True, which="both", alpha=.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / f"{PREFIX}_vs_n.png", dpi=130)


if __name__ == "__main__":
    main()
