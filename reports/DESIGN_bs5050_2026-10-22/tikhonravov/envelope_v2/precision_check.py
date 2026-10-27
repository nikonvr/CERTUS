"""Is the ~1.5e-5 plateau a float64 limit? T in 50-digit arithmetic (mpmath) against float64, and cond(J) of the polish.

usage: python precision_check.py  (designs N = 30 and 36 of curve_free_s1.csv; 200 wavelengths for mpmath)
"""

from __future__ import annotations

import csv
from pathlib import Path

import mpmath as mp
import numpy as np
import search as s

HERE = Path(__file__).resolve().parent
mp.mp.dps = 50


def t_mp(seq: str, d: np.ndarray, wl: float):
    """Characteristic-matrix T at normal incidence (Macleod, chap. 2), layer 0 on the substrate side as in the oracle."""
    m = mp.matrix([[1, 0], [0, 1]])
    for mat, thick in zip(reversed(seq), reversed(d), strict=True):  # incident side first
        n = mp.mpf(s.N_IDX[mat])
        phi = 2 * mp.pi * n * mp.mpf(float(thick)) / mp.mpf(float(wl))
        m = m * mp.matrix([[mp.cos(phi), 1j * mp.sin(phi) / n], [1j * n * mp.sin(phi), mp.cos(phi)]])
    ns = mp.mpf(s.N_SUB)
    b, c = m[0, 0] + m[0, 1] * ns, m[1, 0] + m[1, 1] * ns
    return 4 * ns / abs(b + c) ** 2


def main() -> None:
    rows = {int(r["layers"]): r for r in csv.DictReader((HERE / "curve_free_s1.csv").open(encoding="utf-8"))}
    wls = np.linspace(400.0, 1200.0, 200)
    for n in (30, 36):
        seq, d = rows[n]["seq"], np.array([float(v) for v in rows[n]["d_nm"].split()])
        t64 = np.array([s.oracle.rt_stack(w, [complex(s.N_IDX[m]) for m in seq], d, complex(1.0), complex(s.N_SUB))[1] for w in wls])
        tmp = np.array([float(t_mp(seq, d, w)) for w in wls])
        _r, jac, _c = s.Stack.of(seq).res_jac(d)
        sv = np.linalg.svd(jac, compute_uv=False)
        print(f"N={n}: max|T64 - T50digits| = {np.max(np.abs(t64 - tmp)):.2e}  RMSE(200 wl) float64 {np.sqrt(np.mean((t64 - .5) ** 2)):.6e}"
              f" mp {np.sqrt(np.mean((tmp - .5) ** 2)):.6e}  cond(J) = {sv[0] / sv[-1]:.2e}  sigma_min = {sv[-1]:.2e}")


if __name__ == "__main__":
    main()
