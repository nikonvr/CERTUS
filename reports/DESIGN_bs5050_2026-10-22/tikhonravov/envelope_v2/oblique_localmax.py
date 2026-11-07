"""Code 1's detection with one step per local maximum of the excess phase derivative instead of one per positive run
(oblique_diag_45deg.out: close resonances share a run, and all but one are missed at 45 deg). Same threshold, same
running median, same Newton starts; poles narrower than 0.5 nm above 1 % in 400-700 nm, against the 0.0005-nm scan of
oblique45_check.py, at ANGLE (0: no regression wanted).
usage: python oblique_localmax.py OE_CODE_DIR ANGLE
"""

from __future__ import annotations

import csv

import numpy as np
import oblique45_check as oc  # reads OE_CODE_DIR and ANGLE from the command line

hr = oc.hr


def phase_steps_localmax(n_layers, d, wl_grid, gamma=1.0):
    """Steps of pi of arg t along lambda + i*gamma: every local maximum of the excess derivative above 0.25 / gamma."""
    y, _ = hr.char_y(n_layers, d, wl_grid + 1j * gamma)
    dphi = np.gradient(np.unwrap(-np.angle(y)), wl_grid)
    ex = dphi - np.array([np.median(dphi[max(0, k - 40):k + 41]) for k in range(len(dphi))])
    k = np.where((ex[1:-1] > ex[:-2]) & (ex[1:-1] >= ex[2:]) & (ex[1:-1] > 0.25 / gamma))[0] + 1
    return [float(wl_grid[i]) for i in k]


def find_poles_dense(n_layers, d, bands, target_fn, gamma=1.0, max_fwhm=0.5, min_height=1e-3):
    """Code 1's find_poles from every local maximum, with Newton started every gamma/4 over +-2.5 gamma of each."""
    found = []
    for a, b in bands:
        w = np.arange(float(a), b + 1e-9, 1.0)
        for x0 in phase_steps_localmax(n_layers, d, w, gamma):
            for dx in np.arange(-2.5, 2.51, 0.25) * gamma:
                s = hr.newton_pole(n_layers, d, 1.0 / (x0 + dx))
                lam, fwhm = 1.0 / s.real, 2.0 * s.imag / s.real ** 2
                if not (abs(lam - x0) < 3 * gamma and a <= lam <= b and 0.0 < fwhm < max_fwhm):
                    continue
                h = abs(float(hr.transmittance(n_layers, d, [lam])[0]) - target_fn(lam))
                if h > min_height and all(abs(lam - p[0]) > 1e-6 for p in found):
                    found.append((lam, fwhm, h, s))
    return found


def main() -> None:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    nl, d = [oc.N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
    one_per_run, find_poles = hr.phase_steps, hr.find_poles
    for s_pol, pol in ((True, "s"), (False, "p")):
        hr.char_y = oc.make_char_y(s_pol)
        peaks = [p for p in oc.scan_peaks(nl, d) if oc.background(nl, d, p[0]) < 0.05]
        for name, steps, finder in (("one step per run", one_per_run, find_poles),
                                    ("one step per local maximum", phase_steps_localmax, find_poles),
                                    ("local maxima, starts over +-2.5 nm", phase_steps_localmax, find_poles_dense)):
            hr.phase_steps = steps
            poles = finder(nl, d, [(400, 700)], lambda _x: 0.0, max_fwhm=0.5, min_height=0.01)
            hit = [p for p in peaks if any(abs(p[0] - q[0]) < max(q[1], 0.002) for q in poles)]
            print(f"{oc.ANGLE:g} deg {pol}, {name}: {len(poles)} poles; {len(hit)} of the {len(peaks)} narrow peaks of "
                  f"the scan on a blocked background (median T < 5 % over +-2 nm) found", flush=True)
            for p in peaks:
                if p not in hit:
                    print(f"    missed {p[0]:.4f} nm, T {100 * p[1]:.2f} %, FWHM {p[2]:.4f} nm", flush=True)
        hr.phase_steps = one_per_run


if __name__ == "__main__":
    main()
