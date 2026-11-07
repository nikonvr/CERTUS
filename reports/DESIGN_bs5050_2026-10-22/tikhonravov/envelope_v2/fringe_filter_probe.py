"""Referee audit of the OE paper, point 4 (2026-11-03): do fringes and band edges give false detections?

Code 1 on the re-created 101-layer design, band by band as find_poles does: every local maximum of the excess phase
derivative on lambda + i*gamma (its value against the 0.25/gamma threshold), the poles Newton reaches from the flagged
ones and the filter that rejects each, then all the poles of the band (Newton started every 0.25 nm on the real axis)
with their FWHM, to show how far the fringe poles lie from the axis.
"""

import csv
import sys
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parents[6] / "OE_resonances" / "code"
sys.path.insert(0, str(CODE))
import hidden_resonances as hr  # noqa: E402

rows = list(csv.DictReader(open(CODE / "three_line_101_recreated.csv")))
NL = [{"H": 2.35, "L": 1.45}[r["material"]] for r in rows]
D = np.array([float(r["thickness_nm"]) for r in rows])
BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
         (650, 700, 0.0)]
G = 1.0


def target_fn(lam):
    return next((t for a, b, t in BANDS if a <= lam <= b), 0.0)


def distinct(poles, tol=1e-6):
    out = []
    for s in poles:
        if all(abs(s - q) > tol * abs(s) for q in out):
            out.append(s)
    return out


for a, b, t in sorted(BANDS):
    w = np.arange(float(a), b + 1e-9, 1.0)
    y, _ = hr.char_y(NL, D, w + 1j * G)
    dphi = np.gradient(np.unwrap(-np.angle(y)), w)
    base = np.array([np.median(dphi[max(0, k - 40):k + 41]) for k in range(len(dphi))])
    ex = np.concatenate([[-np.inf], dphi - base, [-np.inf]])
    kmax = np.where((ex[1:-1] > ex[:-2]) & (ex[1:-1] >= ex[2:]))[0]
    flagged = [k for k in kmax if ex[k + 1] > 0.25 / G]
    quiet = [ex[k + 1] for k in kmax if ex[k + 1] <= 0.25 / G]
    print(f"band {a}-{b} nm (target {t:g}): {len(kmax)} local maxima, {len(flagged)} above 0.25/gamma"
          f" (excess {', '.join(f'{ex[k + 1]:.2f} at {w[k]:.0f}' for k in flagged) or '-'});"
          f" highest of the others {max(quiet, default=float('nan')):.3f} rad/nm")
    for k in flagged:
        x0 = float(w[k])
        for s in distinct([hr.newton_pole(NL, D, 1.0 / (x0 + dx)) for dx in np.arange(-2.5, 2.51, 0.25) * G]):
            lam, fwhm = 1.0 / s.real, 2.0 * s.imag / s.real ** 2
            h = abs(float(hr.transmittance(NL, D, [lam])[0]) - target_fn(lam))
            why = [m for m, ok in (("farther than 3 gamma", abs(lam - x0) < 3 * G), ("outside the band", a <= lam <= b),
                                   ("FWHM >= 0.5 nm", 0.0 < fwhm < 0.5), ("|T - target| <= 1e-3", h > 1e-3)) if not ok]
            print(f"    from {x0:.0f}: pole {lam:9.4f} nm, FWHM {fwhm:8.4f} nm, |T - target| {h:.4f}"
                  f" -> {'kept' if not why else 'rejected: ' + ', '.join(why)}")
    allp = distinct([hr.newton_pole(NL, D, 1.0 / x) for x in np.arange(a - 1.0, b + 1.0 + 1e-9, 0.25)])
    inb = sorted((1.0 / s.real, 2.0 * s.imag / s.real ** 2) for s in allp if a <= 1.0 / s.real <= b)
    print(f"  poles of the band: {len(inb)}, FWHM (nm) " + ", ".join(f"{f:.3g} at {lam:.1f}" for lam, f in inb))
