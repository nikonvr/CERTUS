"""Sensitivity of the best free designs (N = 28..38) to random thickness errors.

Prediction (second order, Gauss-Newton Hessian H ~ 2 J^T J, valid because the residuals are ~1e-5):
    E[MSE(d + e)] ~ MSE(d) + sum_i sigma_i^2 |J_i|^2      (J_i: column i of the residual Jacobian)
Monte Carlo: DRAWS independent draws per design and error model, MSE from the CERTUS kernel (`search.mse_only`);
the first CHECK draws of each design are recomputed with the independent oracle (tests/oracle/tmm_reference.py).
Error models: absolute (sigma = 0.5 nm per layer) and relative (sigma = 1 % of each thickness), Gaussian, clipped at 0.
Draw k of layer i comes from default_rng((SEED, N, k)): the same draws for every model up to the scale.

usage: python robust.py CURVE.csv [CURVE.csv ...]   -> robust_check.txt, robust_vs_n.png
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import search as s

HERE = Path(__file__).resolve().parent
SEED, DRAWS, CHECK = 20261027, 400, 5
MODELS = (("abs 0.5 nm", lambda d: np.full(len(d), 0.5)), ("rel 1 %", lambda d: 0.01 * d))


def best_designs(files: list[str]) -> dict[int, tuple[float, str, str, np.ndarray]]:
    best: dict[int, tuple[float, str, str, np.ndarray]] = {}
    for f in files:
        for r in csv.DictReader((HERE / f).open(encoding="utf-8")):
            n, v = int(r["layers"]), float(r["rmse_1601_oracle"])
            if 28 <= n <= 38 and v < best.get(n, (np.inf,))[0]:
                best[n] = (v, f, r["seq"], np.array([float(x) for x in r["d_nm"].split()]))
    return best


def main() -> None:
    best = best_designs(sys.argv[1:])
    out = []

    def say(msg: str) -> None:
        print(msg, flush=True)
        out.append(msg)

    curves: dict[str, list[tuple[int, float, float]]] = {m: [] for m, _f in MODELS}
    nominal = []
    for n in sorted(best):
        r0, src, seq, d = best[n]
        res, jac, _c = s.Stack.of(seq).res_jac(d)
        mse0 = float(np.sum(res * res))
        col2 = np.sum(jac * jac, axis=0)
        z = np.array([np.random.default_rng((SEED, n, k)).standard_normal(n) for k in range(DRAWS)])
        nominal.append((n, r0))
        say(f"N={n} nominal oracle {r0:.3e} kernel {np.sqrt(mse0):.3e}  ({src}, thinnest {d.min():.2f} nm)")
        for name, sig_of in MODELS:
            sig = sig_of(d)
            pred = np.sqrt(mse0 + np.sum(sig ** 2 * col2))
            mses = np.array([s.mse_only(seq, np.maximum(d + sig * zk, 0.0)) for zk in z])
            mc = np.sqrt(np.mean(mses))
            lo, hi = np.sqrt(np.percentile(mses, [10, 90]))
            orc = [s.oracle_rmse(seq, np.maximum(d + sig * zk, 0.0)) for zk in z[:CHECK]]
            dev = max(abs(o - np.sqrt(m)) / o for o, m in zip(orc, mses[:CHECK], strict=True))
            share = sig ** 2 * col2 / np.sum(sig ** 2 * col2)
            top = np.argsort(share)[::-1][:3]
            worst = " ".join(f"#{i}({seq[i]},{d[i]:.1f}nm,{100 * share[i]:.0f}%)" for i in top)
            say(f"   {name:10s} predicted {pred:.3e}  MC {mc:.3e} [p10 {lo:.2e}, p90 {hi:.2e}]  pred/MC {pred / mc:.2f}"
                f"  oracle-vs-kernel {dev:.1e}  most sensitive {worst}")
            curves[name].append((n, pred, mc))
    (HERE / "robust_check.txt").write_text("\n".join(out) + "\n", encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogy(*zip(*nominal, strict=True), "o-", color="0.3", label="nominal (oracle)")
    for (name, pts), col in zip(curves.items(), ("C0", "C3"), strict=True):
        ns, pred, mc = zip(*pts, strict=True)
        ax.semilogy(ns, mc, "o-", color=col, label=f"Monte Carlo, {name}")
        ax.semilogy(ns, pred, "x", color=col, ms=9, label=f"J^T J prediction, {name}")
    ax.set_xlabel("number of layers N")
    ax.set_ylabel("RMSE of T (400-1200 nm), sqrt of mean MSE")
    ax.set_title("50/50 splitter: best free designs under thickness errors")
    ax.grid(True, which="both", alpha=.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "robust_vs_n.png", dpi=130)


if __name__ == "__main__":
    main()
