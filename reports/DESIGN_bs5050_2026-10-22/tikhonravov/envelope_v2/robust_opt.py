"""Direct robust optimisation: minimise R^2 = MSE0 + sigma^2 S, S = sum_i |dr/dOT_i|^2, random OT errors.

R^2 is the second-order E[MSE] under independent Gaussian errors of standard deviation sigma on every optical thickness.
It is a sum of squares: the stacked residual [r ; sigma vec(J / n)], minimised by trf. The derivatives of J (second
derivatives of r) are central finite differences of the CERTUS Jacobian (step H_FD nm).

check                      gradient of the stacked residual against finite differences of R^2, on one design
run SIGMA N[,N...] K       for each N: starts = the K best catalogue designs by R (law{N}.csv), plus K perturbed copies;
                           robust polish, then Monte Carlo (MC draws, kernel; first 3 oracle-checked) of the best;
                           -> robust_opt.txt, robust_opt.csv (best design per N)
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
import search as s
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
H_FD, FLOOR, MC, SEED = 1e-4, 0.1, 2000, 20261029


def inv_n(seq: str) -> np.ndarray:
    return 1.0 / np.array([s.N_IDX[m] for m in seq])


def stacked(seq: str, d: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """Residual [r ; sigma vec(J_ot)] and its Jacobian."""
    st, w = s.Stack.of(seq), inv_n(seq)
    r, j, _c = st.res_jac(d)
    j_ot = j * w
    dj = np.empty((j.shape[0], len(d), len(d)))  # dj[:, i, k] = d J_ot[:, i] / d d_k
    for k in range(len(d)):
        e = np.zeros(len(d))
        e[k] = H_FD
        jp = st.res_jac(d + e)[1]
        jm = st.res_jac(np.maximum(d - e, 0.0))[1]
        dj[:, :, k] = (jp - jm) / (2 * H_FD) * w
    res = np.concatenate([r, sigma * j_ot.T.ravel()])
    jac = np.vstack([j, sigma * dj.transpose(1, 0, 2).reshape(-1, len(d))])
    return res, jac


def r2(seq: str, d: np.ndarray, sigma: float) -> tuple[float, float, float]:
    r, j, _c = s.Stack.of(seq).res_jac(d)
    mse0, S = float(np.sum(r * r)), float(np.sum((j * inv_n(seq)) ** 2))
    return mse0 + sigma ** 2 * S, mse0, S


def polish(seq: str, d: np.ndarray, sigma: float, max_nfev: int = 300) -> np.ndarray:
    memo: dict = {}

    def get(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = stacked(seq, x, sigma)
        return memo[key]

    sol = least_squares(lambda x: get(x)[0], np.maximum(d, FLOOR), jac=lambda x: get(x)[1], bounds=(FLOOR, np.inf),
                        method="trf", x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=max_nfev)
    return np.maximum(sol.x, FLOOR)


def check() -> None:
    rows = list(csv.DictReader((HERE / "law20.csv").open(encoding="utf-8")))
    seq, d = rows[0]["seq"], np.array([float(v) for v in rows[0]["d_nm"].split()])
    sigma = 0.5
    res, jac = stacked(seq, d, sigma)
    assert abs(float(res @ res) - r2(seq, d, sigma)[0]) < 1e-12 * float(res @ res)
    g = 2 * jac.T @ res
    worst = 0.0
    for k in range(len(d)):
        e = np.zeros(len(d))
        e[k] = 1e-3
        fd = (r2(seq, d + e, sigma)[0] - r2(seq, d - e, sigma)[0]) / 2e-3
        worst = max(worst, abs(fd - g[k]) / max(np.max(np.abs(g)), 1e-300))
    print(f"|R^2 stacked - R^2| ok; max relative gradient error {worst:.2e}")
    if worst > 1e-3:
        raise SystemExit("CHECK=FAIL")
    print("CHECK=OK")


def run(sigma: float, ns: list[int], k: int) -> None:
    rng = np.random.default_rng(SEED)
    out, best_rows = [f"direct robust optimisation, sigma = {sigma} nm OT; R = sqrt(MSE0 + sigma^2 S)"], []
    for n in ns:
        t0 = time.time()
        rows = list(csv.DictReader((HERE / f"law{n}.csv").open(encoding="utf-8")))
        cat = [(r["seq"], np.array([float(v) for v in r["d_nm"].split()])) for r in rows]
        cat.sort(key=lambda c: r2(c[0], c[1], sigma)[0])
        start_best = np.sqrt(r2(*cat[0], sigma)[0])
        starts = cat[:k] + [(sq, dd * (1 + 0.1 * rng.standard_normal(n))) for sq, dd in cat[:k]]
        found = []
        for sq, dd in starts:
            x = polish(sq, dd, sigma)
            sq2, x2 = s.normalize(sq, x, 1.0)
            if len(sq2) != n:
                continue
            found.append((r2(sq2, x2, sigma), sq2, x2))
        (rr, mse0, S), seq, d = min(found, key=lambda t: t[0][0])
        st = s.Stack.of(seq)
        z = np.random.default_rng((SEED, n)).standard_normal((MC, n)) * sigma * inv_n(seq)
        mse = []
        for i, zk in enumerate(z):
            dk = np.maximum(d + zk, 0.0)
            mse.append(float(np.sum(st.res_jac(dk)[0] ** 2)))
            if i < 3 and abs(s.oracle_rmse(seq, dk) - np.sqrt(mse[-1])) > 1e-3 * np.sqrt(mse[-1]):
                raise SystemExit(f"oracle disagrees with the kernel at N={n}")
        mse = np.array(mse)
        dev = np.array([np.max(np.abs(st.res_jac(np.maximum(d + zk, 0.0))[0])) * np.sqrt(len(s.WLS)) for zk in z[:500]])
        ot = d / inv_n(seq)
        out.append(f"N={n:2d}: catalogue best R {start_best:.4e} -> robust {np.sqrt(rr):.4e}  (nominal {np.sqrt(mse0):.2e},"
                   f" sigma*s {sigma * np.sqrt(S):.2e}); MC {np.sqrt(mse.mean()):.4e}; yield(+-1%, 500 draws)"
                   f" {np.mean(dev < 0.01):.2f}; thinnest OT {ot.min():.1f} nm; TOT {ot.sum() * 4 / s.L0:.1f} QWOT;"
                   f" {len(found)} polished, {time.time() - t0:.0f} s")
        print(out[-1], flush=True)
        best_rows.append({"layers": n, "R": np.sqrt(rr), "mc": np.sqrt(mse.mean()), "nominal": np.sqrt(mse0),
                          "s": np.sqrt(S), "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
    (HERE / "robust_opt.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    with (HERE / "robust_opt.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(best_rows[0]))
        w.writeheader()
        w.writerows(best_rows)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check()
    else:
        run(float(sys.argv[2]), [int(v) for v in sys.argv[3].split(",")], int(sys.argv[4]))
