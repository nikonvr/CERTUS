"""The two hidden resonances of the re-created 101-layer design with absorption (2026-11-01 evening, counter-analysis of
the method paper: does a realistic k flatten them?). Independent judge tests/oracle/tmm_reference.py (path in argv[1]),
n_hat = n - ik, k_H in (0, 1e-5, 1e-4, 5e-4), k_L = 0; scan every 0.0002 nm around each resonance: peak T, its
wavelength, FWHM of T, and A = 1 - R - T at the peak.
usage: python absorption_trub101.py PATH_TO_tests/oracle
"""

from __future__ import annotations

import csv
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
import tmm_reference as tr  # noqa: E402

r = next(x for x in csv.DictReader(open("fig4_2020_designs.csv", encoding="utf-8")) if x["design"] == "deep")
seq, d = r["seq"], np.array([float(v) for v in r["d_nm"].split()])
for kh in (0.0, 1e-5, 1e-4, 5e-4):
    n = [tr.n_hat(2.35, kh) if m == "H" else tr.n_hat(1.45, 0.0) for m in seq]
    for lo, hi in ((402.45, 402.60), (422.33, 422.48)):
        w = np.arange(lo, hi, 0.0002)
        rt = np.array([tr.rt_from_assembly(tr.stack_matrix(n, d, x), 1.0, 1.52) for x in w])
        t = rt[:, 1]
        k = int(np.argmax(t))
        above = w[t >= t[k] / 2]
        print(f"k_H {kh:g}: peak {w[k]:.4f} nm T {100 * t[k]:6.2f} %  FWHM {above[-1] - above[0]:.4f} nm  "
              f"A {100 * (1 - rt[k, 0] - t[k]):6.2f} %", flush=True)
