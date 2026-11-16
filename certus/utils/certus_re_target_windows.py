"""The wavelength window of each RE target built from a measured point."""

from __future__ import annotations

import numpy as np


def re_target_windows(wls: np.ndarray) -> list[tuple[float, float]]:
    """(lmin, lmax) of each measured point: from the midpoint with its lower neighbour to the midpoint with its upper one.

    The half-width was (wls[1] - wls[0]) / 2 for every point: on a non-uniform grid the windows overlapped or left gaps,
    and on a decreasing grid (an export from 2500 to 250 nm) it was negative, so lmax < lmin and every target was
    rejected (audit 2026-11-15, L6-m5). The two end points take half of their only gap; a single point keeps +-5 nm.
    """
    w = np.asarray(wls, dtype=np.float64).ravel()
    if w.size < 2:
        return [(float(x) - 5.0, float(x) + 5.0) for x in w]
    order = np.argsort(w, kind="mergesort")
    s = w[order]
    mid = 0.5 * (s[1:] + s[:-1])
    lo = np.concatenate(([s[0] - 0.5 * (s[1] - s[0])], mid))
    hi = np.concatenate((mid, [s[-1] + 0.5 * (s[-1] - s[-2])]))
    out = [(0.0, 0.0)] * int(w.size)
    for rank, i in enumerate(order):
        out[int(i)] = (float(lo[rank]), float(hi[rank]))
    return out
