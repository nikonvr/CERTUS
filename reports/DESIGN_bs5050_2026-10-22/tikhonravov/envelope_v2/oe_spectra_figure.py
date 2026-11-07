"""Spectral responses of the three arbitrary targets (2026-11-02, owner): for each target, the target, the best design
on the 1-nm grid and the same design after the charge of its poles ({TAG}spectra_designs.csv from spectra_best.py),
T every 0.002 nm (CERTUS kernel, article_spectra.dense_t) with the grid points; middle: zoom on the strongest hidden
resonance of the design on the grid; right: the charged design's index profile against the optical thickness from the
substrate (owner, 2026-11-02: designs are drawn this way), glass on the left and air on the right.
usage: SEARCH_TARGET=threeline python oe_spectra_figure.py OUT_DIR
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import article_spectra as asp
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HL = asp.HL


def target(kind, w):
    t = np.full(len(w), np.nan)
    if kind == "semi":
        t[(w <= 499) | (w >= 601)] = 0.0
        m = (w >= 500) & (w <= 600)
        t[m] = 0.5 * np.sqrt(np.clip(1 - ((w[m] - 550) / 50) ** 2, 0, None))
    elif kind == "mshape":
        t[(w <= 449) | (w >= 651)] = 0.0
        m = (w >= 450) & (w <= 650)
        t[m] = np.interp(w[m], [450, 500, 550, 600, 650], [0, 0.5, 0.25, 0.5, 0])
    else:
        t[w <= 540] = 0.0
        t[w >= 560] = 1.0
    return t


def merge_thin(seq, d, dead=1.0):
    """Layers under `dead` nm dropped and equal neighbours merged, as a designer would list the design."""
    out_s, out_d = [], []
    for m, t in zip(seq, d, strict=True):
        if t < dead:
            continue
        if out_s and out_s[-1] == m:
            out_d[-1] += t
        else:
            out_s.append(m)
            out_d.append(t)
    return "".join(out_s), np.array(out_d)


KINDS = (("semi", "half circle"), ("mshape", "spectral M"), ("highpass", "long-wave pass"))


def main() -> None:
    # 2026-11-03 (figure review of the OE paper): printed width (16.6-cm text width), 8-pt text, panels lettered (a)-(i)
    # row by row, one legend for the colours, the MFs in the titles, narrow peaks drawn as segments (a 0.01-nm peak is
    # thinner than a pixel on 300 nm); the index profile stays (owner, 2026-11-02: designs drawn as n against OT)
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 7.5, "axes.labelsize": 8, "legend.fontsize": 7,
                         "xtick.labelsize": 7, "ytick.labelsize": 7})
    out = Path(sys.argv[1])
    fig, ax = plt.subplots(3, 3, figsize=(6.5, 5.5), gridspec_kw={"width_ratios": [1.8, 0.9, 1.1]})
    w = np.arange(400.0, 700.0001, 0.002)
    letters = "abcdefghi"
    for i, (tag, label) in enumerate(KINDS):
        rows = {r["which"]: r for r in csv.DictReader(open(f"{os.environ.get('SPECTRA_PREFIX', '')}{tag}_spectra_designs.csv", encoding="utf-8"))}
        tg = target(tag, w)
        grid = np.arange(400.0, 701.0)
        tgg = target(tag, grid)
        keep = ~np.isnan(tgg)
        curves = {}
        for which, col in (("grid", "C0"), ("charged", "C2")):
            r = rows[which]
            curves[which] = asp.dense_t([HL[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()]), w)
            ax[i, 0].plot(w, 100 * curves[which], color=col, lw=0.6, rasterized=True)
            exc = np.nan_to_num(curves[which] - tg)
            k = np.where((exc[1:-1] > exc[:-2]) & (exc[1:-1] >= exc[2:]) & (exc[1:-1] > 0.01))[0] + 1
            ax[i, 0].vlines(w[k], 100 * np.nan_to_num(tg[k]), 100 * curves[which][k], color=col, lw=0.8)
        ax[i, 0].plot(w, 100 * tg, color="k", lw=0.9, ls="--")
        r0, rc = rows["grid"], rows["charged"]
        tgrid = asp.dense_t([HL[m] for m in r0["seq"]], np.array([float(v) for v in r0["d_nm"].split()]), grid[keep])
        ax[i, 0].plot(grid[keep], 100 * tgrid, "k.", ms=1.2)
        ax[i, 0].set_ylabel("T (%)")
        ax[i, 0].set_title(f"({letters[3 * i]}) {label}, {r0['layers']} layers; MF grid / resolved:\n"
                           f"{float(r0['mf_nominal']):.3f} / {float(r0['mf_resolved']):.3f} % (blue), "
                           f"{float(rc['mf_nominal']):.3f} / {float(rc['mf_resolved']):.3f} % (green)")
        err = np.abs(curves["grid"] - tg)
        err[np.isnan(err)] = 0.0
        k = int(np.argmax(err))
        z = (w > w[k] - 1.5) & (w < w[k] + 1.5)
        for which, col in (("grid", "C0"), ("charged", "C2")):
            ax[i, 1].plot(w[z], 100 * curves[which][z], color=col, lw=0.8)
        ax[i, 1].plot(w[z], 100 * tg[z], color="k", lw=0.9, ls="--")
        gz = (grid >= w[k] - 1.5) & (grid <= w[k] + 1.5) & keep
        tz = asp.dense_t([HL[m] for m in r0["seq"]], np.array([float(v) for v in r0["d_nm"].split()]), grid[gz])
        ax[i, 1].plot(grid[gz], 100 * tz, "ko", ms=3)
        ax[i, 1].set_title(f"({letters[3 * i + 1]}) near {w[k]:.3f} nm")
        seq_c, dd = merge_thin(rc["seq"], np.array([float(v) for v in rc["d_nm"].split()]))
        # 2026-11-02 (owner): the design as its index profile against the optical thickness from the substrate, with a
        # stretch of glass (left) and air (right); the bars of physical thickness against layer number are gone
        n_c = np.array([HL[m] for m in seq_c])
        edges = np.concatenate([[0.0], np.cumsum(n_c * dd)]) / 1000
        pad = 0.04 * edges[-1]
        ax[i, 2].stairs([1.52, *n_c, 1.0], [-pad, *edges, edges[-1] + pad], baseline=1.0, fill=True, color="C2",
                        alpha=0.25, lw=0)
        ax[i, 2].stairs([1.52, *n_c, 1.0], [-pad, *edges, edges[-1] + pad], baseline=None, color="C2", lw=0.5)
        ax[i, 2].set_xlim(-pad, edges[-1] + pad)
        ax[i, 2].set_ylim(0.9, 2.5)
        ax[i, 2].set_ylabel("index")
        ax[i, 2].set_title(f"({letters[3 * i + 2]}) {len(dd)} layers, OT {edges[-1]:.1f} µm")
    for a in ax[2][:2]:
        a.set_xlabel("wavelength (nm)")
    ax[2][2].set_xlabel("OT from the substrate (µm)")
    handles = [plt.Line2D([], [], color="C0", lw=1), plt.Line2D([], [], color="C2", lw=1),
               plt.Line2D([], [], color="k", lw=0.9, ls="--"), plt.Line2D([], [], color="k", ls="", marker=".")]
    fig.legend(handles, ["optimized on the 1-nm grid", "resonances charged at their poles", "target", "grid points"],
               loc="upper center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "targets_spectra.pdf")
    fig.savefig(out / "targets_spectra.png", dpi=200)


if __name__ == "__main__":
    main()
