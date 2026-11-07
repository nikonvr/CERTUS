"""Why does the charge stall from round 11 with the fixed detector (threeline_track_height_trub101_localmax.out)? On the
design of its last round: the poles found (lambda, FWHM, height, |Y| at the pole, and where Newton goes when started
again from the pole), then one polish burst with them: does it move the design?
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex TRACK_STEPS=localmax TRACK_MULTISTART=dense NUMBA_NUM_THREADS=8 \
       python stall_probe.py
"""

from __future__ import annotations

import csv

import numpy as np
import threeline_track as tt


def main() -> None:
    r = list(csv.DictReader(open("threeline_track_height_trub101_localmax.csv", encoding="utf-8")))[-1]
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    peaks = tt.poles(seq, d)
    ns = [complex(tt.fl.N_IDX[m]) for m in seq]
    for lam, fwhm, h, s in peaks:
        b, c = tt.cp.oracle.stack_matrix(ns, d, 1.0 / s) @ np.array([1.0 + 0.0j, 1.52 + 0.0j])
        s2 = tt.newton(seq, d, s)
        print(f"pole {lam:.5f} nm, FWHM {fwhm:.5f} nm, height {100 * h:.3f} %, |Y| {abs(b + c):.1e}, Newton again "
              f"-> {tt.lam_fwhm(s2)[0]:.5f} nm", flush=True)
    solve = tt.least_squares

    def verbose(*args, **kwargs):
        sol = solve(*args, **kwargs)
        print(f"    least_squares: status {sol.status}, nfev {sol.nfev}, cost {sol.cost:.6e}, optimality "
              f"{sol.optimality:.2e}, active bounds {int(np.sum(sol.active_mask != 0))}; {sol.message}", flush=True)
        return sol

    tt.least_squares = verbose
    for name, sub in (("both poles", peaks), ("first only", peaks[:1]), ("second only", peaks[1:]), ("none", [])):
        d2 = tt.polish("height", seq, d, sub)
        print(f"one burst, {name}: max |change| {np.max(np.abs(d2 - d)):.2e} nm", flush=True)
    print(f"thinnest layer {d.min():.4f} nm (floor {tt.gs.FLOOR})", flush=True)


if __name__ == "__main__":
    main()
