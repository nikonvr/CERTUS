"""Hidden resonances seen from the complex plane (2026-11-01, owner: how to see the ultra-narrow peaks without an
ultra-fine grid?).

A lossless stack's transmission amplitude t = 2 n0 / (n0 B + C) has no zeros, and its poles -- the resonances -- lie on
the gain side of the real axis, at a distance Gamma/2 (Gamma: their width). Moved by gamma to the lossy side (complex
wavelength lambda + i gamma: every layer given the same small loss per unit of optical path), t is smooth on the scale
gamma, and by the argument principle its phase still turns by pi across every resonance, however narrow: each one
becomes a phase step of pi about 2 gamma wide, visible on a grid of step gamma / 2. For the three-line designs (ours, 109
layers; Trubetskov's, 101 layers): the derivative of the unwrapped phase of t along lambda + i gamma over 400-440 nm, for
gamma = 0.1 nm every 0.05 nm and gamma = 0.5 nm every 0.25 nm (characteristic matrices of the independent oracle,
tests/oracle/tmm_reference.stack_matrix, at complex wavelength), and the steps of pi counted on it.
usage: python complex_plane_detect.py OUT_DIR
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import cissoid_opt as co
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# 2026-11-03: n_H follows SEARCH_NH as in search.py (it was fixed at 2.35, so the n_H = 2.1 designs were detected with
# the wrong index); unset, unchanged
HL = {"H": float(os.environ.get("SEARCH_NH", "2.35")), "L": 1.45}
#: env TRACK_STEPS=localmax (2026-11-03): one step per local maximum of the excess derivative, not one per positive run,
#: whose argmax hid the other resonances of the run (oblique_diag_45deg.out); unset, unchanged
STEPS = os.environ.get("TRACK_STEPS", "run")
oracle = co.oracle


def phase_t(seq, d, wls_complex) -> np.ndarray:
    """Unwrapped phase of the transmission amplitude t = 2 n0 / (n0 B + C) (air, glass 1.52) at complex wavelengths."""
    ns = [complex(HL[m]) for m in seq]
    y = []
    for w in wls_complex:
        b, c = oracle.stack_matrix(ns, d, w) @ np.array([1.0 + 0.0j, 1.52 + 0.0j])
        y.append(b + c)
    return np.unwrap(-np.angle(np.array(y)))


def steps(wls, dphi, gamma) -> list[tuple[float, float]]:
    """(position, area) of the bumps of the phase derivative above its running median: one resonance each (area ~ pi)."""
    base = np.array([np.median(dphi[max(0, k - 40):k + 41]) for k in range(len(dphi))])
    ex = dphi - base
    if STEPS == "localmax":
        e = np.concatenate([[-np.inf], ex, [-np.inf]])
        out = []
        for k in np.where((e[1:-1] > e[:-2]) & (e[1:-1] >= e[2:]) & (e[1:-1] > 0.25 / gamma))[0]:
            i, j = k, k + 1  # the bump: down to the neighbouring minima, inside the positive run
            while i > 0 and 0.0 < ex[i - 1] < ex[i]:
                i -= 1
            while j < len(ex) and 0.0 < ex[j] < ex[j - 1]:
                j += 1
            out.append((float(wls[k]), float(np.trapezoid(ex[i:j], wls[i:j]))))
        return out
    out, k = [], 0
    while k < len(ex):
        if ex[k] > 0.25 / gamma:
            j = k
            while j < len(ex) and ex[j] > 0.0:
                j += 1
            i = k
            while i > 0 and ex[i - 1] > 0.0:
                i -= 1
            area = float(np.trapezoid(ex[i:j], wls[i:j]))
            out.append((float(wls[i + int(np.argmax(ex[i:j]))]), area))
            k = j
        k += 1
    return out


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    designs = []
    for label, path, col in (("ours, 109 layers", "gradual_deep2_cont_seed89_clean2.csv", "C0"),
                             ("Trubetskov 2020, 101 layers", "fig4_2020_designs.csv", "C1")):
        r = min(csv.DictReader(open(path, encoding="utf-8")), key=lambda r: float(r["mf_oracle"]))
        designs.append((label, r["seq"], np.array([float(v) for v in r["d_nm"].split()]), col))
    fig, ax = plt.subplots(1, 3, figsize=(15.0, 3.8))
    for a, gamma, step in ((ax[0], 0.1, 0.05), (ax[1], 0.5, 0.25), (ax[2], 1.0, 1.0)):
        wls = np.arange(398.0, 442.0 + 1e-9, step)
        for label, seq, d, col in designs:
            phi = phase_t(seq, d, wls + 1j * gamma)
            dphi = np.gradient(phi, wls)
            a.plot(wls, dphi, color=col, lw=0.9, label=label)
            found = [(x, s) for x, s in steps(wls, dphi, gamma) if 400.0 <= x <= 440.0]
            print(f"gamma {gamma} nm, step {step} nm ({len(wls)} points), {label}: "
                  + ", ".join(f"{x:.2f} nm (area {s / np.pi:.2f} pi)" for x, s in found), flush=True)
        a.set_xlim(400.0, 440.0)
        a.set_xlabel("wavelength (nm)")
        a.set_ylabel(r"d arg $t$ / d$\lambda$ (rad/nm)")
        a.set_title(fr"phase of $t$ at $\lambda + i\,{gamma:g}$ nm, every {step:g} nm", fontsize=9)
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "complex_plane.pdf")
    fig.savefig(out / "complex_plane.png", dpi=150)


if __name__ == "__main__":
    main()
