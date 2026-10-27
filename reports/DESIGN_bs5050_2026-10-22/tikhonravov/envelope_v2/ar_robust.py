"""Robust AR of Tikhonravov & Trubetskov, Appl. Opt. 51, 7319 (2012), Sec. 4, redone with their Eq. (5) of SPIE 4829 (2003).

Problem: R = 0 at 380-720 nm (2 nm step), nH 2.35, nL 1.45, substrate 1.52, MF = RMS of R in %. Errors (their Eq. 8):
d~ = d + Delta + (delta / 100 %) d, Delta ~ N(0, 1 nm), delta ~ N(0, 1 %), independent, in physical thickness.
Their Table 3 (10 000 draws): AR-6 MF 0.263 E(MF) 0.343; AR-10 0.135 / 0.295; AR-14 0.129 / 0.372;
AR-robust (cloud of 20 designs, N = 9, TOT 1102.1 nm) 0.169 / 0.277.

For each N: the catalogue ar{N}.csv (`SEARCH_TARGET=ar CAT_N=N CAT_PREFIX=ar{N} CAT_TOT=... python catalog.py build`),
ranked by the second-order E[MF^2] = MF^2 + sum alpha_i^2 |dMF-residual/dd_i|^2 with alpha_i^2 = 1 + (0.01 d_i)^2
(their Eq. 5 with the probabilistic weights); the K best are polished on it (trf, finite-difference Jacobian), and the
best is judged by Monte Carlo (DRAWS draws, kernel; first 3 checked with the oracle): E(MF) as they define it (mean of
MF) and sqrt(E[MF^2]).

usage: SEARCH_TARGET=ar python ar_robust.py N[,N...] K DRAWS   -> ar_robust.txt, ar_robust.csv
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

import numpy as np
import search as s
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
S_ABS, S_REL, FLOOR, SEED, H_FD = 1.0, 0.01, 0.1, 20261031, 1e-4
assert os.environ.get("SEARCH_TARGET") == "ar", "run with SEARCH_TARGET=ar"


def alpha(d: np.ndarray) -> np.ndarray:
    return np.sqrt(S_ABS ** 2 + (S_REL * d) ** 2)


def resid(seq: str, d: np.ndarray) -> np.ndarray:
    """MF-residuals in % (MF = |r|) and the Eq. (5) terms alpha_i dr/dd_i, stacked."""
    r, j, _c = s.Stack.of(seq).res_jac(d)
    return np.concatenate([100 * r, (100 * j * alpha(d)).T.ravel()])


def robust_mf(seq: str, d: np.ndarray) -> float:
    v = resid(seq, d)
    return float(np.sqrt(v @ v))


def polish(seq: str, d: np.ndarray) -> np.ndarray:
    def jac(x):
        cols = []
        for k in range(len(x)):
            e = np.zeros(len(x))
            e[k] = H_FD
            cols.append((resid(seq, x + e) - resid(seq, np.maximum(x - e, 0.0))) / (2 * H_FD))
        return np.column_stack(cols)

    sol = least_squares(lambda x: resid(seq, x), np.maximum(d, FLOOR), jac=jac, bounds=(FLOOR, np.inf), method="trf",
                        x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=200)
    return np.maximum(sol.x, FLOOR)


def main() -> None:
    ns, k, draws = [int(v) for v in sys.argv[1].split(",")], int(sys.argv[2]), int(sys.argv[3])
    out = ["robust AR (Tikhonravov & Trubetskov 2012, Sec. 4): errors 1 nm + 1 % (physical); E(MF) = mean of MF in %",
           "their Table 3: AR-6 0.263/0.343, AR-10 0.135/0.295, AR-14 0.129/0.372, AR-robust (N=9) 0.169/0.277"]
    rows = []
    for n in ns:
        t0 = time.time()
        cat = [(r["seq"], np.array([float(v) for v in r["d_nm"].split()]))
               for r in csv.DictReader((HERE / f"ar{n}.csv").open(encoding="utf-8"))]
        cat.sort(key=lambda c: robust_mf(*c))
        best_nom = min(cat, key=lambda c: s.rmse(*c))
        cands = [(seq, polish(seq, d)) for seq, d in cat[:k]]
        cands = [(seq, d) for seq, d in cands if len(s.normalize(seq, d, 1.0)[0]) == n] or cat[:1]
        for lab, (seq, d) in (("best nominal", best_nom), ("robust", min(cands, key=lambda c: robust_mf(*c)))):
            st = s.Stack.of(seq)
            rng = np.random.default_rng((SEED, n))
            z1, z2 = rng.standard_normal((draws, n)), rng.standard_normal((draws, n))
            mf = []
            for i in range(draws):
                dk = np.maximum(d + S_ABS * z1[i] + S_REL * d * z2[i], 0.0)
                r, _j, _c = st.res_jac(dk)
                mf.append(100 * float(np.sqrt(r @ r)))
                if i < 3 and abs(100 * s.oracle_rmse(seq, dk) - mf[-1]) > 1e-3 * mf[-1]:
                    raise SystemExit(f"oracle disagrees with the kernel, N={n}")
            mf = np.array(mf)
            tot = s.total_ot(seq, d)
            out.append(f"N={n:2d} {lab:12s} MF {100 * s.rmse(seq, d):.3f}  predicted sqrt(E[MF^2]) {robust_mf(seq, d):.3f}"
                       f"  MC: E(MF) {mf.mean():.3f}  sqrt(E[MF^2]) {np.sqrt(np.mean(mf ** 2)):.3f}"
                       f"  ({draws} draws)  TOT {tot:.1f} nm  thinnest {d.min():.1f} nm")
            rows.append({"layers": n, "kind": lab, "mf": 100 * s.rmse(seq, d), "e_mf": mf.mean(),
                         "rms_mf": float(np.sqrt(np.mean(mf ** 2))), "pred": robust_mf(seq, d), "tot_nm": tot,
                         "seq": seq, "d_nm": " ".join(f"{v:.4f}" for v in d)})
        out.append(f"      ({len(cat)} catalogue designs, {len(cands)} polished, {time.time() - t0:.0f} s)")
        print("\n".join(out[-3:]), flush=True)
    (HERE / "ar_robust.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    with (HERE / "ar_robust.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
