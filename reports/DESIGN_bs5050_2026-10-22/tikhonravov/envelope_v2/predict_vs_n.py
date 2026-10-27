"""Second-order robust cost of the best nominal design at each N (before choosing the N to study).

sqrt(E[MSE]) ~ sqrt(MSE + sum |J v|^2) for the error models of catalog.py; best design per N over the given curves
(lowest oracle RMSE). These designs were optimised for the nominal MSE only.

usage: python predict_vs_n.py CURVE.csv [CURVE.csv ...]   -> predict_vs_n.txt, predict_vs_n.png
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import search as s
from catalog import models

HERE = Path(__file__).resolve().parent


def main() -> None:
    best: dict[int, tuple[float, str, np.ndarray]] = {}
    for f in sys.argv[1:]:
        for r in csv.DictReader((HERE / f).open(encoding="utf-8")):
            n, v = int(r["layers"]), float(r["rmse_1601_oracle"])
            if v < best.get(n, (np.inf,))[0]:
                best[n] = (v, r["seq"], np.array([float(x) for x in r["d_nm"].split()]))
    names = list(models("H", np.ones(1)))
    out = ["N  nominal   " + "  ".join(f"{m:>10s}" for m in names) + "  thinnest OT (nm)  TOT (QWOT)"]
    curves: dict[str, list[tuple[int, float]]] = {m: [] for m in names}
    for n in sorted(best):
        if n < 8:
            continue
        _v, seq, d = best[n]
        res, jac, _c = s.Stack.of(seq).res_jac(d)
        mse0 = float(np.sum(res * res))
        pred = {m: np.sqrt(mse0 + float(np.sum((jac @ v.T) ** 2))) for m, v in models(seq, d).items()}
        for m in names:
            curves[m].append((n, pred[m]))
        tot = float(np.sum(d * np.array([4 * s.N_IDX[m] for m in seq]) / s.L0))
        out.append(f"{n:2d} {np.sqrt(mse0):.2e} " + "  ".join(f"{pred[m]:10.2e}" for m in names)
                   + f"  {np.min(d * np.array([s.N_IDX[m] for m in seq])):6.1f}  {tot:5.1f}")
    (HERE / "predict_vs_n.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    ns = sorted(n for n in best if n >= 8)
    ax.semilogy(ns, [best[n][0] for n in ns], "ko-", label="nominal (oracle)")
    for m in names:
        ax.semilogy(*zip(*curves[m], strict=True), "o-", ms=3, label=f"predicted, {m}")
    ax.set_xlabel("number of layers N")
    ax.set_ylabel("sqrt(E[MSE]) of T")
    ax.set_title("best nominal design at each N, second-order robust cost")
    ax.grid(True, which="both", alpha=.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "predict_vs_n.png", dpi=130)


if __name__ == "__main__":
    main()
