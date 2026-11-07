"""Why does Code 1's detection miss resonances at 45 deg (oblique_check_45deg.out)? For each narrow peak of the scan: its
pole (Newton from the scan peak), the nearest phase step found by Code 1, the excess phase (above Code 1's running
median) over +-3 nm, in units of pi, and the poles reached by Newton from starts every 0.25 nm over +-3 nm of each step.
usage: python oblique_diag.py OE_CODE_DIR ANGLE
"""

from __future__ import annotations

import csv

import numpy as np
import oblique45_check as oc  # reads OE_CODE_DIR and ANGLE from the command line

hr = oc.hr
PEAKS = {"s": [402.8605, 457.1675, 459.3540, 592.8559, 595.2020, 599.1675, 694.3525], "p": [659.4930, 672.3540]}


def main() -> None:
    r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
    nl, d = [oc.N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
    w = np.arange(400.0, 701.0)
    for s_pol, pol in ((True, "s"), (False, "p")):
        hr.char_y = oc.make_char_y(s_pol)
        y, _ = hr.char_y(nl, d, w + 1j)
        dphi = np.gradient(np.unwrap(-np.angle(y)), w)
        ex = dphi - np.array([np.median(dphi[max(0, k - 40):k + 41]) for k in range(len(dphi))])
        steps = hr.phase_steps(nl, d, w, 1.0)
        print(f"{oc.ANGLE:g} deg {pol}: steps at {[round(x, 1) for x in steps]}", flush=True)
        for lam in PEAKS[pol]:
            s = hr.newton_pole(nl, d, 1.0 / lam)
            lp, fw = 1.0 / s.real, 2.0 * s.imag / s.real ** 2
            k = round(lp - 400.0)
            win = ex[max(0, k - 3):k + 4]
            near = min(steps, key=lambda x: abs(x - lp))
            print(f"  peak {lam:.4f}: pole {lp:.4f} nm, FWHM {fw:.4f} nm; nearest step {near:.1f} ({abs(near - lp):.2f} nm "
                  f"away); excess phase over +-3 nm {np.sum(win) / np.pi:.2f} pi, its maximum {win.max():.3f} rad/nm "
                  f"(threshold 0.25)", flush=True)
        dense = set()
        for x0 in steps:
            for dx in np.arange(-3.0, 3.01, 0.25):
                s = hr.newton_pole(nl, d, 1.0 / (x0 + dx))
                lp, fw = 1.0 / s.real, 2.0 * s.imag / s.real ** 2
                if 400.0 <= lp <= 700.0 and 0.0 < fw < 0.5:
                    dense.add(round(lp, 3))
        print(f"  poles narrower than 0.5 nm from starts every 0.25 nm over +-3 nm of each step: {sorted(dense)}",
              flush=True)


if __name__ == "__main__":
    main()
