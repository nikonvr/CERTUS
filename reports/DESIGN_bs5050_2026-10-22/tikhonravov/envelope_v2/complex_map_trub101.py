"""The key illustration of the method paper (2026-11-01 evening, owner: "go avec illustration a la cle"): the transmission
in the complex wavelength plane, by the independent judge (tests/oracle/tmm_reference.stack_matrix, Y = n0 B + C, air,
glass 1.52, n_hat = n - ik so the poles lie below the real lambda axis and lambda + i gamma is the lossy side).
(a) A Fabry-Perot, (HL)^4 H 2L H (LH)^4 at 500 nm: log10 |t|^2 around its line, its pole by Newton, the real axis and
the line lambda + i gamma. (b) Trubetskov's 101-layer design (re-created), 400-426 nm: the same map, the grid points on
the real axis, the line gamma = 1 nm, the poles found from the nominal points (threeline_track.poles). (c) Zoom on the
402.5-nm pole. (d) The derivative of the phase of t: on the real axis finely and at the grid points, and along
lambda + 1i nm at the grid points. Also prints the pole count of 400-700 nm (phase along lambda + 0.5i / pi) against
2 OT (1/400 - 1/700), the mean density of poles of a stack of optical thickness OT.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex python complex_map_trub101.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import complex_plane_detect as cp
import matplotlib
import numpy as np
import threeline_track as tt

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

V = np.array([1.0 + 0.0j, 1.52 + 0.0j])


def y_of(ns, d, w):
    b, c = cp.oracle.stack_matrix(ns, d, w) @ V
    return b + c


def logt2(ns, d, re, im):
    z = np.empty((len(im), len(re)))
    for i, b in enumerate(im):
        for j, a in enumerate(re):
            t = 2.0 / y_of(ns, d, a + 1j * b)
            z[i, j] = np.log10(max(1.52 * abs(t) ** 2, 1e-12))
    return z


def newton(ns, d, s):
    for _ in range(50):
        h = 1e-9 * abs(s)
        f = y_of(ns, d, 1.0 / s)
        step = f * 2 * h / (y_of(ns, d, 1.0 / (s + h)) - y_of(ns, d, 1.0 / (s - h)))
        s -= step
        if abs(step) < 1e-15:
            break
    return s


def main() -> None:
    out = Path(sys.argv[1])
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    ns = [complex(cp.HL[m]) for m in seq]
    ot = float(sum(cp.HL[m] * x for m, x in zip(seq, d, strict=True)))
    w = np.arange(400.0, 700.0, 0.05)
    ph = cp.phase_t(seq, d, w + 0.5j)
    print(f"poles in 400-700 nm: phase / pi {abs(ph[-1] - ph[0]) / np.pi:.1f}, 2 OT dsigma "
          f"{2 * ot * (1 / 400 - 1 / 700):.1f} (OT {ot:.0f} nm)", flush=True)

    fpq = "HL" * 4 + "H" + "LL" + "H" + "LH" * 4
    fpd = np.array([500.0 / (4 * cp.HL[m]) for m in fpq])
    fpn = [complex(cp.HL[m]) for m in fpq]
    sp = newton(fpn, fpd, 1.0 / 500.0 + 1e-7j)
    lam_fp, fw_fp = tt.lam_fwhm(sp)
    print(f"Fabry-Perot pole: {lam_fp:.4f} nm, FWHM {fw_fp:.4f} nm, complex wavelength {1 / sp:.5f}", flush=True)
    poles = tt.poles(seq, d)
    for p in poles:
        print(f"pole {p[0]:.4f} nm FWHM {p[1]:.4f} nm height {100 * p[2]:.2f} %", flush=True)

    fig = plt.figure(figsize=(11, 7.2), layout="constrained")
    gsx = fig.add_gridspec(2, 2)
    kw = {"cmap": "magma", "vmin": -9, "vmax": 1, "shading": "auto", "rasterized": True}
    a = fig.add_subplot(gsx[0, 0])
    re, im = np.linspace(lam_fp - 8 * fw_fp, lam_fp + 8 * fw_fp, 240), np.linspace(-3 * fw_fp, 3 * fw_fp, 120)
    m = a.pcolormesh(re, im, logt2(fpn, fpd, re, im), **kw)
    a.axhline(0, color="w", lw=0.8)
    a.axhline(1.5 * fw_fp, color="c", ls="--", lw=1)
    a.plot(lam_fp, (1 / sp).imag, "x", color="c", ms=9, mew=2)
    a.set_title("(a) a Fabry-Perot", fontsize=10)
    a.set_ylabel(r"Im $\lambda$ (nm)")

    b = fig.add_subplot(gsx[0, 1])
    re, im = np.linspace(400.0, 426.0, 520), np.linspace(-0.4, 1.4, 90)
    b.pcolormesh(re, im, logt2(ns, d, re, im), **kw)
    b.axhline(0, color="w", lw=0.8)
    b.plot(np.arange(400, 427), np.zeros(27), "o", color="w", ms=3)
    b.axhline(1.0, color="c", ls="--", lw=1)
    for p in poles:
        b.plot(p[0], -p[1] / 2, "x", color="c", ms=8, mew=2)
    b.set_title("(b) the 101-layer design", fontsize=10)

    c = fig.add_subplot(gsx[1, 0])
    p0 = min(poles, key=lambda p: abs(p[0] - 402.525))
    re, im = np.linspace(p0[0] - 0.12, p0[0] + 0.12, 240), np.linspace(-4 * p0[1], 4 * p0[1], 120)
    c.pcolormesh(re, im, logt2(ns, d, re, im), **kw)
    c.axhline(0, color="w", lw=0.8)
    c.plot(p0[0], -p0[1] / 2, "x", color="c", ms=9, mew=2)
    c.set_title("(c) zoom on its 402.5-nm pole", fontsize=10)
    c.set_xlabel(r"Re $\lambda$ (nm)")
    c.set_ylabel(r"Im $\lambda$ (nm)")
    fig.colorbar(m, ax=[a, c], label=r"$\log_{10}\,(n_s|t|^2)$", location="left", shrink=0.8)

    e = fig.add_subplot(gsx[1, 1])
    wf = np.arange(400.0, 426.0, 0.0005)
    e.plot(wf, np.gradient(cp.phase_t(seq, d, wf), wf), lw=0.6, color="0.6", label="real axis, every 0.0005 nm")
    wg = np.arange(400.0, 427.0, 1.0)
    e.plot(wg, np.gradient(cp.phase_t(seq, d, wg), wg), "o-", ms=3, label="real axis, grid points")
    e.plot(wg, np.gradient(cp.phase_t(seq, d, wg + 1j), wg), "s-", ms=3, label=r"$\lambda+1i$ nm, grid points")
    e.set_yscale("symlog", linthresh=1)
    e.set_xlabel(r"$\lambda$ (nm)")
    e.set_ylabel(r"d arg $t$ / d$\lambda$ (rad/nm)")
    e.legend(fontsize=7)
    e.set_title("(d) derivative of the phase of $t$", fontsize=10)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "complex_map.pdf", bbox_inches="tight")
    fig.savefig(out / "complex_map.png", dpi=140, bbox_inches="tight")


if __name__ == "__main__":
    main()
