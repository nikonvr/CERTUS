"""OIC 2016 B1 (cissoid): polish on an oversampled grid, judged on the contest's 301 points (2026-10-31, owner: see
what oversampling does). The target between the 1 nm points is linear interpolation of cissoid_target_b1.csv.
For each FACTOR (points per nm), the record is polished (thicknesses, d >= 3 nm) on 400-700 nm with FACTOR*300+1
points, then judged by the oracle on the 301 points, and finally repolished on the 301 points.
usage: python cissoid_oversample.py IN.csv FACTOR [FACTOR ...]
"""

from __future__ import annotations

import csv
import sys

import cissoid_opt as co
import numpy as np
from scipy.optimize import least_squares


def main() -> None:
    r0 = list(csv.DictReader((co.s.HERE / sys.argv[1]).open(encoding="utf-8")))[-1]
    mats, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    print(f"start oracle {co.oracle_mf(mats, d0):.5f}", flush=True)
    hi = np.array([co.HI_METAL if np.iscomplex(co.MATS[m]) else co.HI_DIEL for m in mats])
    for factor in (int(v) for v in sys.argv[2:]):
        w = np.linspace(400.0, 700.0, 300 * factor + 1)
        tgt = np.interp(w, co.W_FULL, co.TGT_FULL)
        nm = np.column_stack([np.full(len(w), co.MATS[m], dtype=complex) for m in mats])
        nsub = np.full(len(w), 1.52 + 0j)
        scale = 1.0 / (0.01 * np.sqrt(len(w)))

        def res(x, nm=nm, nsub=nsub, w=w, tgt=tgt, scale=scale):
            r, _t, dr, _dt = co.compute_oblique_rt_and_grads_analytic(x, nm, nsub, w, np.arange(len(x)), 0.0, True)
            return (r - tgt) * scale, dr * scale

        sol = least_squares(lambda x: res(x)[0], np.clip(d0, co.FLOOR, hi), jac=lambda x: res(x)[1],
                            bounds=(co.FLOOR, hi), max_nfev=2000)
        o = co.oracle_mf(mats, sol.x)
        _m, d2, _f = co.polish_full((mats, sol.x, co.FLOOR, 2000))
        print(f"x{factor} ({len(w)} points): own MF {np.linalg.norm(sol.fun):.5f}, oracle on 301 {o:.5f}, "
              f"repolished on 301 {co.oracle_mf(mats, d2):.5f}, max |dd| {np.abs(sol.x - d0).max():.2f} nm", flush=True)


if __name__ == "__main__":
    main()
