"""RMSE*(N) of the 50/50 splitter: 2026-10-26 envelope (Argon) against envelope_v2, free and >= 5 nm.

usage: python plot.py  (reads curve_*_s*.csv present here; writes rmse_vs_n.png)
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import search  # noqa: E402

HERE = Path(__file__).resolve().parent


def best_of(kind: str) -> dict[int, float]:
    best: dict[int, float] = {}
    for path in sorted(HERE.glob(f"curve_{kind}_s*.csv")):
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                n, v = int(r["layers"]), float(r["rmse_1601_oracle"])
                best[n] = min(v, best.get(n, v))
    return best


def argon(kind: str) -> dict[int, float]:
    return {len(seq): search.oracle_rmse(seq, d) for seq, d in search.load_old(kind)}


def main() -> None:
    fig, ax = plt.subplots(figsize=(8, 5.2))
    styles = {"free": ("C0", "sans limite (d ≥ 0,1 nm)"), "5nm": ("C3", "d ≥ 5 nm")}
    for kind, (color, label) in styles.items():
        old = argon(kind)
        ax.plot(sorted(old), [old[n] for n in sorted(old)], "o--", color=color, alpha=0.4, ms=4,
                label=f"{label}, enveloppe 2026-10-26")
        new = best_of(kind)
        if new:
            ax.plot(sorted(new), [new[n] for n in sorted(new)], "o-", color=color, ms=5, label=f"{label}, envelope_v2")
    ax.plot([34], [1.77e-4], "k*", ms=12, label="Tikhonravov et al. 1996 (34 couches)")
    ax.set_yscale("log")
    ax.set_xlabel("nombre de couches N")
    ax.set_ylabel("RMSE de T − 0,5 (400–1200 nm, 1601 points, oracle)")
    ax.set_title("Séparatrice 50/50 : nH 2,35 / nL 1,45 sur verre 1,52")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "rmse_vs_n.png", dpi=150)


if __name__ == "__main__":
    main()
