"""Admittance diagrams at real and complex wavelengths (2026-11-01 evening, owner: can poles and complex wavelengths be
drawn as admittance circles, spirals...?). The running admittance Y (in units of free space) from the substrate (1.52)
to the air, layer by layer, each layer cut in 40 sublayers, by the independent judge (tests/oracle stack_matrix:
[B; C] = M [1; Y], Y <- C / B). At a real wavelength each layer turns Y on a circle (an elliptic Moebius map); at
lambda + i gamma (the lossy side) on a contracting spiral; at a pole (the gain side) on an opening spiral, and the locus
ends on Y = -n0 = -1, the zero of n0 B + C. Prints the final admittance of each locus (check: -1 at the poles).
(a) Fabry-Perot (HL)^4 H 2L H (LH)^4 at 500 nm: on its line (real), at its line + 1.5i FWHM, at its pole.
(b) Trubetskov's 101-layer design (re-created): at 402 nm (a grid point), at 402.525 nm (its hidden resonance, real),
and at its pole.
usage: python admittance_poles.py OUT_DIR
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import complex_plane_detect as cp
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SUB = 40


def locus(seq, d, lam):
    y, pts = 1.52 + 0j, [1.52 + 0j]
    for m, t in zip(seq, d, strict=True):
        n = complex(cp.HL[m])
        for _ in range(SUB):
            b, c = cp.oracle.stack_matrix([n], [t / SUB], lam) @ np.array([1.0 + 0j, y])
            y = c / b
            pts.append(y)
    return np.array(pts)


def pole(seq, d, lam0):
    ns = [complex(cp.HL[m]) for m in seq]

    def f(s):
        b, c = cp.oracle.stack_matrix(ns, d, 1 / s) @ np.array([1.0 + 0j, 1.52 + 0j])
        return b + c

    s = 1 / lam0 + 1e-9j
    for _ in range(80):
        h = 1e-9 * abs(s)
        step = f(s) * 2 * h / (f(s + h) - f(s - h))
        s -= step
        if abs(step) < 1e-16:
            break
    return 1 / s


def panel(ax, seq, d, cases, title, lim):
    for lam, label, col in cases:
        p = locus(seq, d, lam)
        ax.plot(p.real, p.imag, color=col, lw=0.7, label=label)
        ax.plot(p[-1].real, p[-1].imag, "o", color=col, ms=6, mfc="none", mew=1.5)
        print(f"{title} | {label}: final Y = {p[-1].real:+.6f} {p[-1].imag:+.6f}i", flush=True)
    for x, lab in ((1.0, r"$+n_0$"), (-1.0, r"$-n_0$")):
        ax.plot(x, 0, "k+", ms=12, mew=1.5)
        ax.annotate(lab, (x, 0), textcoords="offset points", xytext=(4, -14), fontsize=9)
    ax.axhline(0, color="0.8", lw=0.6)
    ax.axvline(0, color="0.8", lw=0.6)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Re Y")
    ax.set_ylabel("Im Y")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, loc="upper right")


def main() -> None:
    out = Path(sys.argv[1])
    fpq = "HL" * 4 + "H" + "LL" + "H" + "LH" * 4
    fpd = np.array([500.0 / (4 * cp.HL[m]) for m in fpq])
    lp = pole(fpq, fpd, 500.0)
    fw = -2 * lp.imag
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    tp = pole(seq, d, 402.525)
    print(f"Fabry-Perot pole {lp:.6f}; 101-layer pole {tp:.6f}", flush=True)
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    panel(ax[0], fpq, fpd, [(complex(lp.real), f"real, {lp.real:.3f} nm: circles", "C0"),
                            (lp.real + 1.5j * fw, rf"$\lambda+i\gamma$, $\gamma$ = {1.5 * fw:.2f} nm: closing spirals",
                             "C2"),
                            (lp, f"pole {lp.real:.3f}{lp.imag:+.3f}i nm: opening spirals", "C3")],
          "(a) Fabry-Perot (HL)$^4$H 2L H(LH)$^4$", 4.0)
    panel(ax[1], seq, d, [(402.0 + 0j, "402 nm, a grid point", "0.5"),
                          (complex(tp.real), f"{tp.real:.4f} nm, the hidden resonance", "C0"),
                          (tp, f"pole {tp.real:.4f}{tp.imag:+.4f}i nm", "C3")],
          "(b) the 101-layer design", 4.0)
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "admittance.pdf")
    fig.savefig(out / "admittance.png", dpi=150)


if __name__ == "__main__":
    main()
