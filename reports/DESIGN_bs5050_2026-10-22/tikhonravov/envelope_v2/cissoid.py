"""OIC 2016 problem B1 (cissoid of Diocles), Kruschwitz et al., Appl. Opt. 56, C151 (2017): target reconstruction.

The target (their Fig. 7) is not tabulated. Each 50 nm half-segment is a branch of the cissoid u^3 = t^2 (2a - u) with
u the reflectance distance to the cusp, normalised to 1 at R = 0.5, and t = |lambda - cusp| / 50 nm; cusps at
450 nm (R = 0.2), 550 nm (0.8) and 650 nm (0.2), R = 0.5 at 400, 500, 600 and 700 nm. The scale `a` is not given:
it is fixed by their published example design (Table 8, 43 layers H/L, MF = 0.89721320429466 on 301 points,
400-700 nm, tolerance 0.01, H = 2.45, L = 1.45, substrate 1.52, air), which `check` reproduces.

usage: python cissoid.py check
"""

from __future__ import annotations

import sys

import numpy as np
import search as s
from scipy.optimize import brentq

WLS = np.arange(400.0, 701.0)
EXAMPLE = [15.728, 33.305, 54.117, 24.623, 39.768, 34.341, 137.469, 28.016, 126.42, 76.769, 15.849, 56.657, 47.913,
           55.883, 16.767, 67.774, 71.09, 32.307, 23.759, 78.289, 39.858, 40.247, 34.807, 77.806, 37.148, 42.366, 35.54,
           69.135, 30.279, 48.709, 38.139, 53.423, 24.563, 65.741, 43.56, 47.229, 24.489, 70.099, 41.384, 51.08,
           34.124, 146.383, 60.075]
EXAMPLE_MF = 0.89721320429466
N_B1 = {"H": 2.45, "L": 1.45}


def cissoid_u(t: float, a: float) -> float:
    """u in [0, 1] with u^3 = t^2 (2a - u), t in [0, 1]."""
    if t == 0.0:
        return 0.0
    return brentq(lambda u: u ** 3 - t * t * (2 * a - u), 0.0, 2 * a)


def target(a: float) -> np.ndarray:
    cusps = [(450.0, 0.2, +1), (550.0, 0.8, -1), (650.0, 0.2, +1)]
    out = np.empty(len(WLS))
    for k, wl in enumerate(WLS):
        c, rc, sgn = min(cusps, key=lambda q: abs(wl - q[0]))
        t = min(abs(wl - c) / 50.0, 1.0)
        out[k] = rc + sgn * 0.3 * cissoid_u(t, a) / cissoid_u(1.0, a)
    return out


def mf(d: list[float], tgt: np.ndarray, flip: bool) -> float:
    seq = "".join("H" if i % 2 == 0 else "L" for i in range(len(d)))
    n = [complex(N_B1[m]) for m in seq]
    dd = np.array(d)
    if flip:
        n, dd = n[::-1], dd[::-1]
    r = np.array([s.oracle.rt_stack(w, n, dd, complex(1.0), complex(1.52))[0] for w in WLS])
    return float(np.sqrt(np.mean(((r - tgt) / 0.01) ** 2)))


def check() -> None:
    for flip in (False, True):
        for a in (0.5, 0.6, 0.75, 1.0, 1.5, 2.0, 5.0, 50.0):
            print(f"flip={flip} a={a:6.2f} MF {mf(EXAMPLE, target(a), flip):.6f} (paper {EXAMPLE_MF})", flush=True)


if __name__ == "__main__" and sys.argv[1] == "check":
    check()
