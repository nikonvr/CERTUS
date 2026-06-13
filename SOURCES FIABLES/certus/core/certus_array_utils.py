"""Shared numpy array helpers for CERTUS.

Keep these helpers intentionally small and boring: they centralize the most
common coercion / ordering / interpolation idioms without hiding domain logic.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def as_float64_1d(arr: Any, *, copy: bool = False) -> np.ndarray:
    """Return a contiguous 1D float64 array."""
    out = np.asarray(arr, dtype=np.float64).ravel()
    return out.copy() if copy else out


def sorted_float64(arr: Any, *, copy: bool = True) -> np.ndarray:
    """Return a sorted 1D float64 array using the stable default sort semantics."""
    out = np.sort(as_float64_1d(arr, copy=copy))
    return out.copy() if copy else out


def interp_sorted(x: Any, xp: Any, fp: Any, *, left: float | None = None, right: float | None = None) -> np.ndarray:
    """Convenience wrapper around np.interp with standardized float64 coercion."""
    x_f = as_float64_1d(x)
    xp_f = as_float64_1d(xp)
    fp_f = as_float64_1d(fp)
    return np.interp(x_f, xp_f, fp_f, left=left, right=right)
