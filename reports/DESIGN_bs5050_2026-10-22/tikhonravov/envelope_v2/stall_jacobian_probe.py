"""Is the Jacobian of the charged residuals right at the stalled design (stall_probe.py)? The polish differentiates
T(lambda_p) - T' at a fixed lambda_p = 1/Re(sigma_p) (top of the peak: dT/dlambda = 0); the true derivative also moves
lambda_p with the thicknesses. For each pole: dT/dlambda at lambda_p, the distance from lambda_p to the top of the peak,
and the relative difference between the analytic row and central differences with lambda_p tracked by Newton.
usage: SEARCH_TARGET=threeline TRACK_DETECT=complex TRACK_STEPS=localmax TRACK_MULTISTART=dense NUMBA_NUM_THREADS=8 \
       python stall_jacobian_probe.py
"""

from __future__ import annotations

import csv

import numpy as np
import threeline_track as tt


def main() -> None:
    r = list(csv.DictReader(open("threeline_track_height_trub101_localmax.csv", encoding="utf-8")))[-1]
    seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
    for lam, fwhm, _h, s in tt.poles(seq, d):
        e = lambda w: float(tt.err(seq, d, [w])[0])  # noqa: E731
        slope = (e(lam + 1e-5) - e(lam - 1e-5)) / 2e-5
        w = np.linspace(lam - fwhm, lam + fwhm, 4001)
        top = float(w[np.argmax(np.abs(tt.err(seq, d, w)))])
        jp = tt.err(seq, d, [lam], jac=True)[1][0]
        fd = np.zeros(len(d))
        for i in range(len(d)):
            h = 1e-6
            vals = []
            for sgn in (1.0, -1.0):
                x = d.copy()
                x[i] += sgn * h
                vals.append(float(tt.err(seq, x, [tt.lam_fwhm(tt.newton(seq, x, s))[0]])[0]))
            fd[i] = (vals[0] - vals[1]) / (2 * h)
        print(f"pole {lam:.5f} nm, FWHM {fwhm:.5f}: dT/dlambda there {slope:.3e} /nm, top of the peak {top - lam:+.5f} nm "
              f"away; |analytic - tracked| / |tracked| = {np.linalg.norm(jp - fd) / np.linalg.norm(fd):.3f}", flush=True)


if __name__ == "__main__":
    main()
