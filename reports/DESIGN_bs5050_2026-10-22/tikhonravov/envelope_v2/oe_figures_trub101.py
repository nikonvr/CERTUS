"""Teaser and cure figures of the method paper with Trubetskov's 101-layer design alone (2026-11-01 evening, owner: the
paper uses no design of ours). Same drawing as article_spectra.teaser and article_grid_figures.cure.
teaser: T of the re-created design every 0.002 nm (CERTUS kernel) and on the 277 points, whole band and 400-430 nm.
cure: the design as re-created, polished on 0.005 then 0.001 nm (fine_grid_budget_trub101.csv, 1200 iterations), and
with its resonances charged at their poles (threeline_track_height_trub101.csv, round 40): T over 400-430 nm every
0.0005 nm, with an inset on 420-424 nm, and |E|^2 in the stack at each one's highest stop-band peak, light from the air.
2026-11-03 (figure review): drawn at the printed width (16.6-cm text width) with 8-pt text; one colour per design across
the paper (blue: as re-created, orange: fine grid, green: charged); the narrow peaks of the whole band drawn explicitly,
since a 0.01-nm peak is thinner than a pixel there.
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
WIDTH = 6.5  # inches, the text width of the paper
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 6.5,
                     "xtick.labelsize": 7, "ytick.labelsize": 7})


def stop_band_peaks(wl, t, thr=0.01):
    """Local maxima of T above thr where the target is 0 (the bands minus the passbands)."""
    stop = np.zeros(len(wl), bool)
    for a, b in asp.BANDS:
        stop |= (wl >= a) & (wl <= b)
    for p, q in asp.PASS:
        stop &= ~((wl >= p) & (wl <= q))
    k = np.where(stop[1:-1] & (t[1:-1] > t[:-2]) & (t[1:-1] >= t[2:]) & (t[1:-1] > thr))[0] + 1
    return wl[k], t[k]


def main() -> None:
    out = Path(sys.argv[1])
    r0 = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d0 = r0["seq"], agf.arr(r0["d_nm"])
    ns = [HL[m] for m in seq]
    wl = np.arange(400.0, 700.0001, 0.002)
    t = asp.dense_t(ns, d0, wl)
    grid = np.concatenate([np.arange(a, b + 1.0) for a, b in asp.BANDS])
    tg = asp.dense_t(ns, d0, grid)
    fig, ax = plt.subplots(1, 2, figsize=(WIDTH, 2.2), gridspec_kw={"width_ratios": [1.7, 1.0]})
    for a, lo, hi in ((ax[0], 400.0, 700.0), (ax[1], 400.0, 430.0)):
        for p, q in asp.PASS:
            a.axvspan(p, q, color="0.9", lw=0)
        m = (wl >= lo) & (wl <= hi)
        a.plot(wl[m], 100 * t[m], color="C0", lw=0.6, rasterized=True,
               label="101 layers, re-created: MF 0.0128 % on the points")
        g = (grid >= lo) & (grid <= hi)
        a.plot(grid[g], 100 * tg[g], "k.", ms=2.5 if a is ax[1] else 1.2, label="the 277 points of the problem")
        a.set_xlim(lo, hi)
        a.set_xlabel("wavelength (nm)")
        a.set_ylabel("T (%)")
    xp, tp = stop_band_peaks(wl, t)
    ax[0].vlines(xp, 0, 100 * tp, color="C0", lw=0.9)  # thinner than a pixel on 300 nm: drawn as segments
    ax[0].set_title("(a) 400-700 nm; grey: T = 1 wanted, 0 elsewhere")
    ax[1].set_title("(b) 400-430 nm, between the points")
    fig.tight_layout()
    fig.savefig(out / "teaser.pdf")
    fig.savefig(out / "teaser.png", dpi=200)

    # 2026-11-03 (referee audit): the 0.001-nm polish with the charge's 1200 iterations (fine_grid_budget.py), was 300
    p1 = agf.rows("fine_grid_budget_trub101.csv")[0]
    tr = agf.rows("threeline_track_height_trub101.csv")[-1]
    cases = [("as re-created, 0.348 %", r0, "C0"),
             ("fine grid, 1200 iterations, 0.0231 %", p1, "C1"),
             (f"charged at the poles, {float(tr['mf_resolved']):.4f} %", tr, "C2")]
    w = np.arange(400.0, 430.0001, 0.0005)
    fig, ax = plt.subplots(1, 2, figsize=(WIDTH, 2.4), gridspec_kw={"width_ratios": [1.25, 1.0]})
    ins = ax[0].inset_axes([0.36, 0.22, 0.28, 0.38])  # its tick labels clear of the baseline
    zoom = (w >= 420.0) & (w <= 424.0)
    for label, r, col in cases:
        sq, d = r["seq"], agf.arr(r["d_nm"])
        tt = asp.dense_t([HL[m] for m in sq], d, w)
        ax[0].plot(w, 100 * tt, color=col, lw=0.7, rasterized=True, label=label)
        ins.plot(w[zoom], 100 * tt[zoom], color=col, lw=0.8)
        lam = float(w[int(np.argmax(tt))])
        x, e2 = agf.field_profile(sq, d, lam)
        ax[1].semilogy(x, e2, color=col, lw=0.6, label=f"at {lam:.3f} nm: max {e2.max():.0f}")
    g = np.arange(400.0, 431.0)
    ax[0].plot(g, 100 * asp.dense_t(ns, d0, g), "k.", ms=2.5, label="nominal points")
    ins.set_xlim(420.0, 424.0)
    ins.set_ylim(0.0, 1.5)
    ins.set_title("420-424 nm", fontsize=6.5)
    ins.tick_params(labelsize=6)
    ax[0].set_xlabel("wavelength (nm)")
    ax[0].set_ylabel("T (%), target 0")
    ax[0].set_title("(a) the stop band 400-430 nm")
    ax[0].legend(loc="upper right")
    ax[1].set_xlabel("optical thickness from the substrate (nm)")
    ax[1].set_ylabel(r"$|E|^2$ (incident wave = 1)")
    ax[1].set_title("(b) the field at each design's highest peak")
    ax[1].text(0.02, 0.96, "substrate", transform=ax[1].transAxes, ha="left", va="top", fontsize=6.5)
    ax[1].text(0.98, 0.96, "air", transform=ax[1].transAxes, ha="right", va="top", fontsize=6.5)
    ax[1].legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "cure.pdf")
    fig.savefig(out / "cure.png", dpi=200)


if __name__ == "__main__":
    main()
