"""OIC 2016 B1 (cissoid): replace a dielectric layer by a stack of two kept dielectrics (2026-11-01, owner).

Three replacements of a layer (index n, thickness t) by p periods of the two kept materials lo < n < hi that bracket it:
  asym  p pairs (lo, hi), effective-medium fraction n^2 = f lo^2 + (1 - f) hi^2 (error first order in period/lambda);
  herp  p symmetric Herpin cells lo/2 hi lo/2 (merged: lo/2 hi lo hi ... lo/2), same fraction (second order);
  fit   the herp stack of uniform cells whose two thicknesses (lo, hi per cell) are fitted so that its
        characteristic matrix matches the layer's on the 301 points (least squares on the four entries).
usage: python cissoid_herpin.py IN.csv KEPT [PERIOD]   prints the 301-point MF and N of each conversion, unpolished
"""

from __future__ import annotations

import csv
import sys

import cissoid_opt as co
import numpy as np
from scipy.optimize import least_squares

W = co.W_FULL


def char(ns, ts):
    """Characteristic matrices (301, 2, 2) of dielectric sub-layers, normal incidence, n - ik convention (k = 0)."""
    m = np.broadcast_to(np.eye(2, dtype=complex), (len(W), 2, 2)).copy()
    for n, t in zip(ns, ts, strict=True):
        dl = 2 * np.pi * n * t / W
        c, s = np.cos(dl), np.sin(dl)
        layer = np.empty((len(W), 2, 2), dtype=complex)
        layer[:, 0, 0], layer[:, 0, 1], layer[:, 1, 0], layer[:, 1, 1] = c, 1j * s / n, 1j * n * s, c
        m = m @ layer
    return m


def bracket(x, keep):
    n = co.MATS[x].real
    lo = max((k for k in keep if co.MATS[k].real <= n), key=lambda k: co.MATS[k].real)
    hi = min((k for k in keep if co.MATS[k].real >= n), key=lambda k: co.MATS[k].real)
    nl, nh = co.MATS[lo].real, co.MATS[hi].real
    return lo, hi, (nh ** 2 - n ** 2) / (nh ** 2 - nl ** 2)


def replace(x, t, keep, mode, period):
    lo, hi, f = bracket(x, keep)
    p = max(1, round(t / period))
    if mode == "asym":
        return [lo, hi] * p, [f * t / p, (1 - f) * t / p] * p
    mats = [lo] + [hi, lo] * p
    ts = np.array([f * t / p / 2] + [(1 - f) * t / p, f * t / p] * p)
    ts[-1] = f * t / p / 2
    if mode == "fit":
        target = char([co.MATS[x].real], [t])
        ns = [co.MATS[k].real for k in mats]

        def res(v):
            dm = char(ns, v) - target
            return np.concatenate([dm.real.ravel(), dm.imag.ravel()])

        # uniform cells: two free thicknesses (lo per cell, hi per cell), the stack lo/2 hi lo ... hi lo/2
        def stack(v):
            a, b = v
            seq = [a / 2, *([b, a] * p)]
            seq[-1] = a / 2
            return seq

        v = least_squares(lambda v: res(stack(v)), [f * t / p, (1 - f) * t / p], bounds=(0.0, np.inf)).x
        ts = np.array(stack(v))
    return mats, list(ts)


def convert(m, d, keep, mode, period):
    om, od = [], []
    for x, t in zip(m, d, strict=True):
        if x in keep or np.iscomplex(co.MATS[x]):
            om.append(x)
            od.append(t)
        else:
            a, b = replace(x, t, keep, mode, period)
            om += a
            od += b
    return co.normalize(om, np.array(od), 0.0)


def main() -> None:
    r0 = list(csv.DictReader((co.s.HERE / sys.argv[1]).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    keep = sys.argv[2]
    for period in [float(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "60").split(",")]:
        for mode in ("asym", "herp", "fit"):
            m2, d2 = convert(m, d, keep, mode, period)
            print(f"{keep} period {period:g} {mode}: N {len(m2)}, MF {co.mf_full(m2, d2):.5f}, min {d2.min():.2f} nm",
                  flush=True)


if __name__ == "__main__":
    main()
