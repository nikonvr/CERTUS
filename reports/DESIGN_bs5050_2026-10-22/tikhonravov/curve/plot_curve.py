"""RMSE vs layer count on the problem of Tikhonravov et al. (Appl. Opt. 35, 5493, 1996), against their design.

    python reports/DESIGN_bs5050_2026-10-22/tikhonravov/curve/plot_curve.py

For each best_N.json of the sweep, placed at N, the layer count the run was allowed (start and max_layers; a hollow
point when DESIGN kept fewer), DESIGN default setting of 2026-10-23, no QWOT ceiling: RMSE of T against 0.5 on the
fixed 1601-point grid of 400-1200 nm (point), and the mean +/- 2 sigma of the RMSE over 200 seeded draws where
every layer gets a Gaussian thickness error whose 2 sigma is 0.1 % of it plus 0.2 nm, evaluated on the article's
80 points (bar). Their 34-layer design: published RMSE 1.277e-4 (MF 1.2767e-2 on 80 points). T comes from the
independent oracle tests/oracle/tmm_reference.py (indices constant: 1.45, 2.35, glass 1.52).
Writes curve.png and curve.csv.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

from tmm_reference import rt_stack  # noqa: E402

from certus.core.certus_design_tolerance import rmse_band  # noqa: E402

ARTICLE_PUBLISHED_RMSE = 1.276685e-4
ARTICLE_RECOMPUTED_1601 = 1.765396e-4


def stack_of(path: Path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in cfg["front"] if float(r["qw"]) > 0.0]
    n = [float(cfg["materials"][r["mat"]]["n4"]) for r in rows]
    d = np.array([float(r["qw"]) * float(cfg["l0"]) / (4.0 * k) for r, k in zip(rows, n, strict=True)])
    return n, d, float(cfg["materials"]["Substrate"]["n4"])


def mse(n, d, n_sub, wls) -> float:
    t = np.array([rt_stack(w, n, d, n_sub=n_sub)[1] for w in wls])
    return float(np.mean((t - 0.5) ** 2))


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fine, article = np.linspace(400.0, 1200.0, 1601), np.linspace(400.0, 1200.0, 80)
    rows = []
    for path in sorted(HERE.glob("best_*.json"), key=lambda p: int(p.stem.split("_")[1])):
        n, d, n_sub = stack_of(path)
        nominal = np.sqrt(mse(n, d, n_sub, fine))
        band = rmse_band(lambda ep, n=n, n_sub=n_sub: mse(n, ep, n_sub, article), d, draws=200)
        rows.append({"start_layers": int(path.stem.split("_")[1]), "layers": len(d), "rmse_1601": float(nominal),
                     "mean_80": band.mean, "two_sigma_80": band.two_sigma,
                     "total_qwot": float(sum(4.0 * k * t / 500.0 for k, t in zip(n, d, strict=True))), "thinnest_nm": float(d.min()),
                     "design_file": path.name, "run_row": f"curve.jsonl, label tcurve{path.stem.split('_')[1]}"})
        print(json.dumps(rows[-1]), flush=True)
    with (HERE / "curve.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    ink, muted, grid, surface, blue, orange = "#2b2b29", "#6b6a63", "#e4e3dd", "#fcfcfb", "#2a78d6", "#eb6834"
    fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    x = [r["start_layers"] for r in rows]
    ax.plot(x, [r["rmse_1601"] for r in rows], color=blue, lw=2, marker="o", ms=6, markeredgecolor=surface,
            markeredgewidth=1.2, label="CERTUS DESIGN: RMSE (1601-point grid)", zorder=4)
    lo = [min(r["two_sigma_80"], r["mean_80"] * 0.999) for r in rows]
    ax.errorbar(x, [r["mean_80"] for r in rows], yerr=[lo, [r["two_sigma_80"] for r in rows]], fmt="_", ms=10,
                color=blue, alpha=0.55, elinewidth=1.2, capsize=3, label="with thickness errors 0.1 % + 0.2 nm: mean ± 2σ",
                zorder=3)
    ax.plot([34], [ARTICLE_PUBLISHED_RMSE], ls="none", marker="D", ms=8, color=orange, markeredgecolor=surface,
            label="Tikhonravov et al. 1996, 34 layers (published)", zorder=5)
    ax.plot([34], [ARTICLE_RECOMPUTED_1601], ls="none", marker="D", ms=8, mfc=surface, mec=orange, mew=1.5,
            label="same design, recomputed on 1601 points", zorder=5)
    ax.set_yscale("log")
    fewer = [r for r in rows if r["layers"] < r["start_layers"]]
    if fewer:
        ax.plot([r["start_layers"] for r in fewer], [r["rmse_1601"] for r in fewer], ls="none", marker="o", ms=6,
                mfc=surface, mec=blue, mew=1.5, label="DESIGN kept fewer layers than allowed", zorder=5)
    ax.set_xlabel("layers allowed (max_layers of the run)", color=ink, fontsize=9)
    ax.set_ylabel("RMSE of T against 0.5, 400-1200 nm", color=ink, fontsize=9)
    ax.set_title("50/50 splitter, n 1.45 / 2.35 on glass 1.52: RMSE vs layers", color=ink, fontsize=10, loc="left")
    ax.grid(True, which="major", color=grid, lw=0.8)
    ax.tick_params(colors=muted, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(frameon=False, fontsize=8, labelcolor=ink, loc="upper right")
    fig.tight_layout()
    fig.savefig(HERE / "curve.png", facecolor=surface)
    print("written", HERE / "curve.png")


if __name__ == "__main__":
    main()
