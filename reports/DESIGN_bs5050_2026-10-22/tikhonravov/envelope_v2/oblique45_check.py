"""Is the detection unchanged at a fixed oblique incidence? (2026-11-02 night, method paper, Discussion: "At a fixed angle
of incidence the tilted admittances of non-dispersive layers do not depend on the wavelength, and the detection applies
unchanged" was deduced, not measured.) The re-created 101-layer design (fig4_2020_designs.csv, row deep) at ANGLE deg
from air, s and p: Code 1's detection and Newton (hidden_resonances.find_poles) run with tilted admittances (char_y
replaced by its oblique form) on the 1-nm points of 400-700 nm, against (1) a scan of T every 0.0005 nm of the same
oblique form for every peak narrower than 0.5 nm and above 1 %, and (2) the independent oracle of the repository
(tests/oracle/tmm_reference.rt_stack_oblique) for T at random wavelengths and around every pole.
usage: python oblique45_check.py OE_CODE_DIR [ANGLE]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "oracle"))
import hidden_resonances as hr  # noqa: E402
import tmm_reference as oracle  # noqa: E402

ANGLE = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
BETA = float(np.sin(np.deg2rad(ANGLE)))  # Snell invariant, incidence from air
N_IDX = {"H": 2.35, "L": 1.45}


def make_char_y(s_pol):
    def tilted(n):
        cos_t = np.sqrt(1.0 - (BETA / n) ** 2 + 0j)
        return (n * cos_t if s_pol else n / cos_t), cos_t

    def char_y(n_layers, d, wl, n0=1.0, ns=1.52):
        """Code 1's char_y with tilted admittances and phase thicknesses n d cos(theta) (layers from the substrate)."""
        wl = np.atleast_1d(np.asarray(wl, dtype=complex))
        e_s = tilted(ns)[0]
        b, c = np.ones_like(wl), np.full_like(wl, e_s)
        for n, t in zip(n_layers, d, strict=True):
            e, cos_t = tilted(n)
            delta = 2.0 * np.pi * n * t * cos_t / wl
            cs, sn = np.cos(delta), np.sin(delta)
            b, c = cs * b + 1j * sn / e * c, 1j * e * sn * b + cs * c
        e_0 = tilted(n0)[0]
        y = e_0 * b + c
        return y, 4.0 * e_0.real * e_s.real / np.abs(y) ** 2

    return char_y


def scan_peaks(nl, d, step=0.0005, thr=0.01, wmax=0.5):
    """Peaks of T above thr narrower than wmax nm on a scan of 400-700 nm: (lambda, T, FWHM)."""
    w = np.arange(400.0, 700.0 + step / 2, step)
    t = np.concatenate([hr.transmittance(nl, d, w[k:k + 20000]) for k in range(0, len(w), 20000)])
    out, reach = [], int(wmax / step)
    for k in np.where((t[1:-1] > t[:-2]) & (t[1:-1] >= t[2:]) & (t[1:-1] > thr))[0] + 1:
        lo, hi = k, k
        while lo > max(0, k - reach) and t[lo] > t[k] / 2:
            lo -= 1
        while hi < min(len(t) - 1, k + reach) and t[hi] > t[k] / 2:
            hi += 1
        if t[lo] <= t[k] / 2 and t[hi] <= t[k] / 2:
            out.append((float(w[k]), float(t[k]), float(w[hi] - w[lo])))
    return out


def background(nl, d, lam):
    """Median of T over +-2 nm around lam, 0.5 nm away from it: below a few % on a blocked background (a hidden
    resonance), near 1 on a pass band or a band edge."""
    w = np.concatenate([np.linspace(lam - 2.0, lam - 0.5, 300), np.linspace(lam + 0.5, lam + 2.0, 300)])
    return float(np.median(hr.transmittance(nl, d, w)))


def oracle_peak(nl, d, lam, fwhm, s_pol):
    """Peak and FWHM of T from the oracle, 2001 points over +-6 FWHM."""
    w = np.linspace(lam - 6 * fwhm, lam + 6 * fwhm, 2001)
    t = np.array([oracle.rt_stack_oblique(x, nl, d, ANGLE, s_pol)[1] for x in w])
    k = int(np.argmax(t))
    above = np.where(t >= t[k] / 2)[0]
    return float(w[k]), float(t[k]), float(w[above[-1]] - w[above[0]])


def main() -> None:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    nl, d = [N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
    rng = np.random.default_rng(1)
    for s_pol, pol in ((True, "s"), (False, "p")):
        hr.char_y = make_char_y(s_pol)  # Code 1's detection, Newton and T now use the tilted admittances
        x = rng.uniform(400.0, 700.0, 50)
        dt = max(abs(float(hr.transmittance(nl, d, [v])[0]) - oracle.rt_stack_oblique(v, nl, d, ANGLE, s_pol)[1])
                 for v in x)
        poles = sorted(hr.find_poles(nl, d, [(400, 700)], lambda _x: 0.0, max_fwhm=0.5, min_height=0.01))
        peaks = scan_peaks(nl, d)
        print(f"{ANGLE:g} deg, {pol}: max |T - oracle| at 50 random wavelengths {dt:.1e}; {len(poles)} resonances "
              f"narrower than 0.5 nm and above 1 % found from the 301 points, {len(peaks)} on the 0.0005-nm scan",
              flush=True)
        for lam, fwhm, h, _s in poles:
            near = [p for p in peaks if abs(p[0] - lam) < max(fwhm, 0.002)]
            ox, ot, ofw = oracle_peak(nl, d, lam, fwhm, s_pol)
            print(f"  pole {lam:.4f} nm, FWHM {fwhm:.4f} nm, T {100 * h:.2f} % | oracle {ox:.4f} nm, FWHM {ofw:.4f} nm, "
                  f"T {100 * ot:.2f} % | on the scan: {'yes' if near else 'NO'} | background "
                  f"{100 * background(nl, d, lam):.2f} %", flush=True)
        missed = [p for p in peaks if all(abs(p[0] - q[0]) >= max(q[1], 0.002) for q in poles)]
        for p in missed:
            print(f"  on the scan only: {p[0]:.4f} nm, T {100 * p[1]:.2f} %, FWHM {p[2]:.4f} nm | background "
                  f"{100 * background(nl, d, p[0]):.2f} %", flush=True)


if __name__ == "__main__":
    main()
