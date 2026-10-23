"""RMSE vs layer count of DESIGN runs, with the +/- 2 sigma tolerance bars of the window's "RMSE vs layers" tab.

    python reports/DESIGN_bs5050_2026-10-22/final_runs/plot_rmse_vs_layers.py LABEL[=NAME] [LABEL[=NAME] ...]

Reads final_runs/runs.jsonl (design_bench.py rows, field rmse_vs_layers): for each Pareto record, the nominal RMSE
(point) and the mean +/- 2 sigma of the RMSE when every layer gets a Gaussian thickness error whose 2 sigma is
0.1 % of it plus 0.2 nm (bar). RMSE on the window's optimization grid. Writes rmse_vs_layers.png and .csv.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]  # validated categorical slots 1-3 (dataviz palette)
MARKERS = ["o", "s", "D"]


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = {json.loads(line)["label"]: json.loads(line) for line in (HERE / "runs.jsonl").read_text(encoding="utf-8").splitlines()}
    series = []
    for arg in sys.argv[1:]:
        label, _, name = arg.partition("=")
        series.append((name or label, rows[label]["rmse_vs_layers"]))

    ink, muted, grid, surface = "#2b2b29", "#6b6a63", "#e4e3dd", "#fcfcfb"
    fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    with (HERE / "rmse_vs_layers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "layers", "rmse_nominal", "rmse_mean_with_errors", "two_sigma"])
        for k, (name, pts) in enumerate(series):
            pts = sorted(pts, key=lambda p: p["layers"])
            dx = (k - (len(series) - 1) / 2) * 0.18
            x = [p["layers"] + dx for p in pts]
            mean = [p["mean"] for p in pts]
            lo = [min(p["two_sigma"], p["mean"]) for p in pts]  # two_sigma is already 2 sigma; an RMSE stops at 0
            hi = [p["two_sigma"] for p in pts]
            ax.errorbar(x, mean, yerr=[lo, hi], fmt="none", ecolor=COLORS[k], elinewidth=1.2, capsize=3, alpha=0.8,
                        zorder=2)
            ax.plot(x, mean, ls="none", marker="_", ms=10, color=COLORS[k], zorder=3)
            ax.plot(x, [p["rmse"] for p in pts], ls="none", marker=MARKERS[k], ms=6, color=COLORS[k],
                    markeredgecolor=surface, markeredgewidth=1.2, label=f"{name}: nominal (point), mean ± 2σ (bar)",
                    zorder=4)
            for p in pts:
                w.writerow([name, p["layers"], f"{p['rmse']:.7f}", f"{p['mean']:.7f}", f"{p['two_sigma']:.7f}"])
    ax.axhline(1e-3, color=muted, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(ax.get_xlim()[0], 1.08e-3, " goal 0.001", color=muted, fontsize=8, va="bottom")
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("layers (Pareto records of the run)", color=ink, fontsize=9)
    ax.set_ylabel("RMSE of T, 400-1200 nm (window grid)", color=ink, fontsize=9)
    ax.set_title("50/50 splitter: RMSE vs layers; bars: thickness errors 0.1 % + 0.2 nm at 2σ", color=ink,
                 fontsize=10, loc="left")
    ax.grid(True, which="major", color=grid, lw=0.8)
    ax.tick_params(colors=muted, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(frameon=False, fontsize=8, labelcolor=ink, loc="upper right")
    fig.tight_layout()
    fig.savefig(HERE / "rmse_vs_layers.png", facecolor=surface)
    print("written", HERE / "rmse_vs_layers.png")


if __name__ == "__main__":
    main()
