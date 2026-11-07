"""Teaser and cure figures of the method paper with Trubetskov's 101-layer design alone (2026-11-01 evening, owner: the
paper uses no design of ours). Same drawing as article_spectra.teaser and article_grid_figures.cure.
teaser: T of the re-created design every 0.002 nm (CERTUS kernel) and on the 277 points, whole band and 400-430 nm.
cure: the design as re-created, polished on 0.005 then 0.001 nm (threeline_refine_probe_trub101.csv), and with its
resonances charged at their poles (threeline_track_height_trub101.csv, round 40): T over 400-430 nm every 0.0005 nm, and
|E|^2 in the stack at each one's highest stop-band peak.
usage: SEARCH_TARGET=threeline python oe_figures_trub101.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import article_grid_figures as agf
import article_spectra as asp
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HL = asp.HL


def main() -> None:
    out = Path(sys.argv[1])
    r0 = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d0 = r0["seq"], agf.arr(r0["d_nm"])
    ns = [HL[m] for m in seq]
    wl = np.arange(400.0, 700.0001, 0.002)
    t = asp.dense_t(ns, d0, wl)
    grid = np.concatenate([np.arange(a, b + 1.0) for a, b in asp.BANDS])
    tg = asp.dense_t(ns, d0, grid)
    fig, ax = plt.subplots(1, 2, figsize=(13.0, 3.9), gridspec_kw={"width_ratios": [1.7, 1.0]})
    for a, lo, hi in ((ax[0], 400.0, 700.0), (ax[1], 400.0, 430.0)):
        for p, q in asp.PASS:
            a.axvspan(p, q, color="0.9", lw=0)
        m = (wl >= lo) & (wl <= hi)
        a.plot(wl[m], 100 * t[m], color="C1", lw=0.6, rasterized=True,
               label="101 layers, re-created from Trubetskov 2020: MF 0.0128 % on the points")
        g = (grid >= lo) & (grid <= hi)
        a.plot(grid[g], 100 * tg[g], "k.", ms=2.5 if a is ax[1] else 1.2, label="the 277 points of the problem")
        a.set_xlim(lo, hi)
        a.set_xlabel("wavelength (nm)")
        a.set_ylabel("T (%)")
    ax[0].set_title("(a) the whole band: target T = 1 in the grey passbands, 0 elsewhere", fontsize=9)
    ax[1].set_title("(b) 400-430 nm: resonances between the points", fontsize=9)
    ax[0].legend(fontsize=7, loc="center right")
    fig.tight_layout()
    fig.savefig(out / "teaser.pdf")
    fig.savefig(out / "teaser.png", dpi=150)

    # 2026-11-03 (referee audit): the 0.001-nm polish with the charge's 1200 iterations (fine_grid_budget.py), was 300
    p1 = agf.rows("fine_grid_budget_trub101.csv")[0]
    tr = agf.rows("threeline_track_height_trub101.csv")[-1]
    cases = [("as re-created: 0.0128 % on the 1 nm grid, 0.348 % resolved", r0, "C0"),
             ("polished on 0.005 then 0.001 nm steps (270 007 points, 1200 iterations): 0.0231 %", p1, "C1"),
             (f"resonances charged at their poles (277 + 2 points): {float(tr['mf_resolved']):.4f} %", tr, "C2")]
    w = np.arange(400.0, 430.0001, 0.0005)
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 3.9), gridspec_kw={"width_ratios": [1.25, 1.0]})
    for label, r, col in cases:
        sq, d = r["seq"], agf.arr(r["d_nm"])
        tt = asp.dense_t([HL[m] for m in sq], d, w)
        ax[0].plot(w, 100 * tt, color=col, lw=0.7, rasterized=True, label=label)
        lam = float(w[int(np.argmax(tt))])
        x, e2 = agf.field_profile(sq, d, lam)
        ax[1].semilogy(x, e2, color=col, lw=0.7, label=f"at {lam:.3f} nm: max {e2.max():.0f}")
    g = np.arange(400.0, 431.0)
    ax[0].plot(g, 100 * asp.dense_t(ns, d0, g), "k.", ms=3, label="the nominal points")
    ax[0].set_xlabel("wavelength (nm)")
    ax[0].set_ylabel("T (%)  (target 0)")
    ax[0].set_title("(a) the stop band 400-430 nm of the 101-layer design", fontsize=9)
    ax[0].legend(fontsize=7)
    ax[1].set_xlabel("optical thickness from the substrate (nm)")
    ax[1].set_ylabel(r"$|E|^2$ (incident wave = 1)")
    ax[1].set_title("(b) the field at each design's highest peak", fontsize=9)
    ax[1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "cure.pdf")
    fig.savefig(out / "cure.png", dpi=150)


if __name__ == "__main__":
    main()
