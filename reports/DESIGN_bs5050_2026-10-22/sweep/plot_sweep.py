"""Best fixed-grid RMSE against the real layer count, over every result of the campaign.

    python reports/DESIGN_bs5050_2026-10-22/sweep/plot_sweep.py

Real layers: zero-thickness layers removed, then neighbours of the same material merged.
Writes best_by_layers.csv and best_by_layers.png next to this file.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
N4 = {"H": 2.35, "L": 1.46}
L0 = 500.0


def real_stack(materials: str, ep: list[float]) -> tuple[str, list[float]]:
    mats, out = [], []
    for m, d in zip(materials, ep, strict=False):
        if d <= 1e-9:
            continue
        if mats and mats[-1] == m:
            out[-1] += d
        else:
            mats.append(m)
            out.append(d)
    return "".join(mats), out


def rows():
    for name in ("probe.jsonl", "sweep/sweep.jsonl", "runs.jsonl", "eval_best.jsonl", "window_sweep/window_sweep.jsonl"):
        path = CAMPAIGN / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if "rmse_grid" not in d or "ep" not in d:
                continue
            mats = d["materials"]
            ep = d["ep"] if len(d["ep"]) == len(mats) else [x for x in d["ep"] if x > 1e-9]
            m, e = real_stack(mats, ep)
            if d.get("mode") == "run":
                kw, attrs = d.get("kwargs") or {}, d.get("window_attrs") or {}
                record = (kw.get("memetic_children", 0) >= 1000 and kw.get("memetic_qwot_max") == 30
                          and attrs.get("_pareto_champion_respects_5nm") and "memetic_pair_move_rate" not in kw)
                if kw.get("memetic_children") and not record:
                    continue  # development runs of the memetic stage, before its settings were fixed
                source = "memetic" if record else "workflow"
            else:
                source = "probe"
            if source == "memetic" and (d.get("total_qwot_at_l0") or 0) > 30.0:
                continue  # above the 30 QWOT ceiling of the owner for this case
            yield {
                "source": source,
                "label": d.get("label") or d.get("file", ""),
                "layers": len(m),
                "rmse": float(d["rmse_grid"]),
                "qwot": sum(4.0 * N4[x] * t / L0 for x, t in zip(m, e, strict=True)),
            }


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    all_rows = list(rows())
    best: dict[int, dict] = {}
    best_mem: dict[int, dict] = {}
    for r in all_rows:
        table = best if r["source"] == "probe" else best_mem if r["source"] == "memetic" else None
        if table is not None and (r["layers"] not in table or r["rmse"] < table[r["layers"]]["rmse"]):
            table[r["layers"]] = r
    with (HERE / "best_by_layers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "layers", "best_rmse", "total_qwot", "label"])
        for name, table in (("probe", best), ("design_memetic", best_mem)):
            for n in sorted(table):
                w.writerow([name, n, f"{table[n]['rmse']:.7f}", f"{table[n]['qwot']:.2f}", table[n]["label"]])

    ink, muted, grid = "#2b2b29", "#6b6a63", "#e4e3dd"
    fig, ax = plt.subplots(figsize=(8.0, 4.6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ns = sorted(best)
    ax.plot(ns, [best[n]["rmse"] for n in ns], color="#2a78d6", lw=2, marker="o", ms=5,
            markeredgecolor="#fcfcfb", markeredgewidth=1.5, label="probe outside the window (no 5 nm floor)", zorder=3)
    nm = sorted(best_mem)
    if nm:
        ax.plot(nm, [best_mem[n]["rmse"] for n in nm], color="#1baf7a", lw=2, marker="s", ms=5,
                markeredgecolor="#fcfcfb", markeredgewidth=1.5, label="DESIGN with the memetic stage (window)", zorder=3)
        ax.annotate("DESIGN memetic", (nm[-1], best_mem[nm[-1]]["rmse"]), textcoords="offset points", xytext=(6, -2),
                    fontsize=8, color=ink)
    wf = [r for r in all_rows if r["source"] == "workflow"]
    ax.plot([r["layers"] for r in wf], [r["rmse"] for r in wf], ls="none", marker="D", ms=6, color="#eb6834",
            markeredgecolor="#fcfcfb", markeredgewidth=1.5, label="DESIGN with PGLOBAL (current default)", zorder=4)
    ax.axhline(1e-3, color=muted, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(ns[0] if ns else 10, 1.08e-3, "goal 0.001", color=muted, fontsize=8, va="bottom")
    if ns:
        n_best = min(best, key=lambda n: best[n]["rmse"])
        ax.annotate(f"{best[n_best]['rmse']:.6f}\n{n_best} layers, {best[n_best]['qwot']:.1f} QWOT",
                    (n_best, best[n_best]["rmse"]), textcoords="offset points", xytext=(-12, 4),
                    ha="right", fontsize=8, color=ink)
    ax.set_yscale("log")
    ax.set_xlim(7.5, 36.5)
    ax.set_xlabel("real layers (H/L, zero layers removed)", color=ink, fontsize=9)
    ax.set_ylabel("RMSE of T on 400-1200 nm (0.5 nm grid)", color=ink, fontsize=9)
    ax.set_title("50/50 splitter 400-1200 nm: best RMSE vs layer count (total <= 30 QWOT)", color=ink, fontsize=10,
                 loc="left")
    ax.grid(True, which="major", color=grid, lw=0.8)
    ax.tick_params(colors=muted, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(frameon=False, fontsize=8, labelcolor=ink, loc="upper right")
    fig.tight_layout()
    fig.savefig(HERE / "best_by_layers.png", facecolor=fig.get_facecolor())
    for name, table in (("probe", best), ("memetic", best_mem)):
        for n in sorted(table):
            print(f"{name:8s} {n:3d}  {table[n]['rmse']:.7f}  {table[n]['qwot']:5.2f} QWOT  {table[n]['label']}")


if __name__ == "__main__":
    main()
