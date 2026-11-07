"""Threshold figure of the method paper (2026-11-01 evening, owner: integrate the half circle into the question of the
title; counter-analysis: the three-line envelope designs belong to the optimality paper, which shows them on both
grids, so the method paper uses only designs made for it and the two published designs of Trubetskov 2020).
Reads {semi,mshape,highpass}_threshold.csv when present (semi_threshold.py) and adds the two re-created designs of
Trubetskov's Fig. 4 (variants_fig4_2020.out: deep N101 0.0128 -> 0.3483 %, classical N104 0.0129 -> 0.0320 % on 0.001 nm;
OT 14171 and 14101 nm). Resolved / nominal MF against optical thickness and number of layers; shaded: the range of the
estimate OT_c over the designs (column ot_c).
usage: python threshold_figure.py OUT_DIR
"""

from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# 2026-11-03 (figure review of the OE paper): drawn at the printed width (0.62 of a 16.6-cm text width), 8-pt text
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 6.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7})

TARGETS = (("semi", "half circle", "o"), ("mshape", "spectral M", "D"), ("highpass", "long-wave pass", "v"))
_DG = 2 / math.pi * math.asin(0.9 / 3.8)  # quarter-wave stop band of 2.35/1.45
M_THREE_LINE = math.log(700 / 400) / math.log((1 + _DG) / (1 - _DG))
C_FP = 2 * 2.52 * 0.9 / (math.pi * 2.35 * 1.45)


def ot_c(r, m=M_THREE_LINE):
    return m * 200 * math.log(C_FP * 400 / math.sqrt(r / 0.5)) / math.log(2.35 / 1.45)


# 2026-11-02 (owner): the classical design without its L layer on the substrate (classical_nolsub.py, N103), resolved
# on 0.0002 nm (classical_nolsub.out); it was N104 at 0.0320 % on 0.001 nm, which misses its 0.0009-nm resonance
TRUB = ((14171.0, 101, 0.3483 / 0.0128, ot_c(0.000128), "three-line, deep search (re-created)"),
        (13968.4, 103, 0.0354 / 0.0133, ot_c(0.000133), "three-line, classical (re-created)"))


def main() -> None:
    out = Path(sys.argv[1])
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    for tag, label, mk in TARGETS:
        rows = []
        files = ((f"nolsub_{tag}_threshold_s5.csv", f"nolsub_{tag}_threshold_s6.csv")  # 2026-11-02: no dead L layer
                 if os.environ.get("THRESH_SET") == "nolsub" else (f"{tag}_threshold.csv", f"{tag}_threshold_s2.csv"))
        for f in files:
            if os.path.exists(f):
                rows += [r for r in csv.DictReader(open(f, encoding="utf-8")) if float(r["mf_nominal"]) < 5.0]
        # 2026-11-03: a design can be both the best of its number of layers and on the front; count and draw it once
        seen: set = set()
        rows = [r for r in rows if not ((k := (r["layers"], r["ot_nm"], r["mf_nominal"], r["mf_resolved"])) in seen
                                        or seen.add(k))]
        if not rows:
            continue
        x = [float(r["ot_nm"]) for r in rows]
        c = [float(r["ot_c"]) for r in rows]
        y = [float(r["mf_resolved"]) / float(r["mf_nominal"]) for r in rows]
        below = [b for a, b, k in zip(x, y, c, strict=True) if a < k]
        above = [b for a, b, k in zip(x, y, c, strict=True) if a >= k]
        print(f"{label}: {len(rows)} designs; below OT_c {len(below)} (ratio > 1.2: {sum(b > 1.2 for b in below)}); "
              f"above {len(above)} (ratio > 1.2: {sum(b > 1.2 for b in above)})", flush=True)
        ax[0].semilogy(x, y, mk, ms=3.2, alpha=0.6, label=f"{label} ({len(rows)} designs)")
        ax[1].semilogy([a / k for a, k in zip(x, c, strict=True)], y, mk, ms=3.2, alpha=0.6, label=label)
    for ot, _n, ratio, oc, label in TRUB:
        ax[0].semilogy(ot, ratio, "*", ms=13, label=label)
        ax[1].semilogy(ot / oc, ratio, "*", ms=13, label=label)
    ax[1].axvline(1.0, color="C3", lw=1.2, ls="--")
    for a in ax:
        a.axhline(1.2, color="0.6", lw=0.8)  # 2026-11-03: the criterion of the paper, F_inf > 1.2 F_G
        a.set_ylabel("resolved MF / nominal MF")
        a.legend(fontsize=7)
    ax[0].set_xlabel("optical thickness OT (nm)")
    ax[1].set_xlabel(r"OT / OT$_c$ (estimated critical thickness of each design)")
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "threshold.pdf")
    fig.savefig(out / "threshold.png", dpi=150)
    for k, name in ((0, "threshold_ot"), (1, "threshold_norm")):  # 2026-11-02: one panel per section of the paper
        f2, a2 = plt.subplots(figsize=(4.05, 2.7))
        for line in ax[k].get_lines():
            if line.get_label().startswith("_"):
                continue
            a2.semilogy(line.get_xdata(), line.get_ydata(), line.get_marker(), ms=0.75 * line.get_markersize(),
                        alpha=line.get_alpha(), color=line.get_color(), label=line.get_label())
        a2.axhline(1.2, color="0.6", lw=0.8)
        a2.text(0.99, 1.2, "1.2", transform=a2.get_yaxis_transform(), ha="right", va="bottom", fontsize=7, color="0.4")
        if k == 1:
            a2.axvline(1.0, color="C3", lw=1.2, ls="--")
        a2.set_xlabel(ax[k].get_xlabel())
        a2.set_ylabel(ax[k].get_ylabel())
        a2.legend(fontsize=6, loc="upper left" if k == 0 else "upper right", framealpha=0.9)  # keep the stars visible
        f2.tight_layout()
        f2.savefig(out / f"{name}.pdf")
        f2.savefig(out / f"{name}.png", dpi=150)


if __name__ == "__main__":
    main()
