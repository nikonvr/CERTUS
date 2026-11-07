"""Complex-plane figures of the method paper split into theory and application (2026-11-01 late evening, owner: "one
starts from a theory, then goes to the illustration; the three-band example should come much later").
fp_theory: the Fabry-Perot (HL)^4 H 2L H (LH)^4 at 500 nm alone: (a) log10(n_s |t|^2) in the complex wavelength plane,
its pole, the real axis, the line lambda + i gamma; (b) derivative of the phase of t on the real axis and on
lambda + i gamma (gamma = 1.5 FWHM): a bump of area pi each; (c) admittance loci: circles (real, on the line), closing
spirals (lambda + i gamma), opening spirals ending on -n0 (the pole).
benchmark_poles: Trubetskov's 101-layer design (re-created): (a) the map 400-426 nm with grid points, poles from the
nominal points and the line gamma = 1 nm; (b) zoom on the 402.5-nm pole; (c) derivative of the phase on the real axis
(fine and at the grid points) and on lambda + 1i nm at the grid points; (d) admittance loci at 402 nm, at the hidden
resonance and at its pole. Independent judge (tests/oracle via complex_plane_detect); functions of
complex_map_trub101.py and admittance_poles.py.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex python oe_complex_figures.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import admittance_poles as ap
import complex_map_trub101 as cm
import complex_plane_detect as cp
import matplotlib
import numpy as np
import threeline_track as tt

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

KW = {"cmap": "magma", "vmin": -9, "vmax": 1, "shading": "auto", "rasterized": True}


def fp_theory(out) -> None:
    q = "HL" * 4 + "H" + "LL" + "H" + "LH" * 4
    d = np.array([500.0 / (4 * cp.HL[m]) for m in q])
    ns = [complex(cp.HL[m]) for m in q]
    lp = ap.pole(q, d, 500.0)
    fw = -2 * lp.imag
    g = 1.5 * fw
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4), gridspec_kw={"width_ratios": [1.15, 1.0, 1.0]})
    re, im = np.linspace(lp.real - 8 * fw, lp.real + 8 * fw, 240), np.linspace(-3 * fw, 3 * fw, 120)
    m = ax[0].pcolormesh(re, im, cm.logt2(ns, d, re, im), **KW)
    ax[0].axhline(0, color="w", lw=0.8)
    ax[0].axhline(g, color="c", ls="--", lw=1)
    ax[0].plot(lp.real, lp.imag, "x", color="c", ms=9, mew=2)
    ax[0].set_xlabel(r"Re $\lambda$ (nm)")
    ax[0].set_ylabel(r"Im $\lambda$ (nm)")
    ax[0].set_title("(a) the line is a pole, half its width below the axis", fontsize=9)
    fig.colorbar(m, ax=ax[0], label=r"$\log_{10}(n_s|t|^2)$")
    w = np.linspace(lp.real - 8 * fw, lp.real + 8 * fw, 1601)
    ax[1].plot(w, np.gradient(cp.phase_t(q, d, w), w), label="real axis")
    ax[1].plot(w, np.gradient(cp.phase_t(q, d, w + 1j * g), w), label=rf"$\lambda+i\gamma$, $\gamma$ = {g:.2f} nm")
    ax[1].set_xlabel(r"$\lambda$ (nm)")
    ax[1].set_ylabel(r"d arg $t$ / d$\lambda$ (rad/nm)")
    ax[1].set_title(r"(b) the phase turns by $\pi$ at the pole, seen from either line", fontsize=9)
    ax[1].legend(fontsize=7)
    ap.panel(ax[2], q, d, [(complex(lp.real), "real: circles", "C0"),
                           (lp.real + 1j * g, r"$\lambda+i\gamma$: closing spirals", "C2"),
                           (lp, "pole: opening spirals", "C3")], "(c) admittance loci", 4.0)
    fig.tight_layout()
    fig.savefig(out / "fp_theory.pdf")
    fig.savefig(out / "fp_theory.png", dpi=140)


def benchmark(out) -> None:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    ns = [complex(cp.HL[m]) for m in seq]
    poles = tt.poles(seq, d)
    p0 = min(poles, key=lambda p: abs(p[0] - 402.525))
    tp = ap.pole(seq, d, 402.525)
    fig = plt.figure(figsize=(12, 8.2), layout="constrained")
    gs = fig.add_gridspec(2, 2)
    a = fig.add_subplot(gs[0, 0])
    re, im = np.linspace(400.0, 426.0, 520), np.linspace(-0.4, 1.4, 90)
    m = a.pcolormesh(re, im, cm.logt2(ns, d, re, im), **KW)
    a.axhline(0, color="w", lw=0.8)
    a.plot(np.arange(400, 427), np.zeros(27), "o", color="w", ms=3)
    a.axhline(1.0, color="c", ls="--", lw=1)
    for p in poles:
        a.plot(p[0], -p[1] / 2, "x", color="c", ms=8, mew=2)
    a.set_title("(a) grid points (dots), poles found from them (x), line $\lambda+i$ nm (dashed)", fontsize=9)
    a.set_xlabel(r"Re $\lambda$ (nm)")
    a.set_ylabel(r"Im $\lambda$ (nm)")
    b = fig.add_subplot(gs[0, 1])
    re, im = np.linspace(p0[0] - 0.12, p0[0] + 0.12, 240), np.linspace(-4 * p0[1], 4 * p0[1], 120)
    b.pcolormesh(re, im, cm.logt2(ns, d, re, im), **KW)
    b.axhline(0, color="w", lw=0.8)
    b.plot(p0[0], -p0[1] / 2, "x", color="c", ms=9, mew=2)
    b.set_title(f"(b) zoom on the pole of {p0[0]:.3f} nm (FWHM {p0[1]:.4f} nm)", fontsize=9)
    b.set_xlabel(r"Re $\lambda$ (nm)")
    fig.colorbar(m, ax=[a, b], label=r"$\log_{10}(n_s|t|^2)$", shrink=0.8)
    c = fig.add_subplot(gs[1, 0])
    wf = np.arange(400.0, 426.0, 0.0005)
    c.plot(wf, np.gradient(cp.phase_t(seq, d, wf), wf), lw=0.6, color="0.6", label="real axis, every 0.0005 nm")
    wg = np.arange(400.0, 427.0, 1.0)
    c.plot(wg, np.gradient(cp.phase_t(seq, d, wg), wg), "o-", ms=3, label="real axis, grid points")
    c.plot(wg, np.gradient(cp.phase_t(seq, d, wg + 1j), wg), "s-", ms=3, label=r"$\lambda+1i$ nm, grid points")
    c.set_yscale("symlog", linthresh=1)
    c.set_xlabel(r"$\lambda$ (nm)")
    c.set_ylabel(r"d arg $t$ / d$\lambda$ (rad/nm)")
    c.legend(fontsize=7)
    c.set_title("(c) derivative of the phase of $t$", fontsize=9)
    e = fig.add_subplot(gs[1, 1])
    ap.panel(e, seq, d, [(402.0 + 0j, "402 nm, a grid point", "0.5"),
                         (complex(tp.real), f"{tp.real:.4f} nm, the hidden resonance", "C0"),
                         (tp, "its pole", "C3")], "(d) admittance loci", 4.0)
    fig.savefig(out / "benchmark_poles.pdf")
    fig.savefig(out / "benchmark_poles.png", dpi=140)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    fp_theory(out)
    benchmark(out)


if __name__ == "__main__":
    main()
