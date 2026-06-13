import numpy as np
from numba import njit, prange
from typing import *
from functools import lru_cache
import math
from certus.core.certus_core import SUBSTRATES


# [MONOLITHIC BLOCK] MATERIAL DATABASE


# DO NOT SPLIT - Interpolation kernels required by all modules


# =========================================================================================


# INTERPOLATION UTILS & MATERIAL DATABASE


# =============================================================================


# OPENPYXL_AVAILABLE imported from certus.core.certus_core at top of file


CACHE_SIZE_MATERIAL_INDEX = 1000


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def numba_interp_scalar(x: float, xp: np.ndarray, fp: np.ndarray) -> float:
    """Optimized scalar linear interpolation."""

    n = len(xp)

    if n == 0:
        return np.nan

    if n == 1:
        return fp[0]

    if x <= xp[0]:
        slope = (fp[1] - fp[0]) / (xp[1] - xp[0])

        return fp[0] + slope * (x - xp[0])

    if x >= xp[-1]:
        slope = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])

        return fp[-1] + slope * (x - xp[-1])

    idx = np.searchsorted(xp, x)

    if idx == 0:
        return fp[0]

    x0, x1 = xp[idx - 1], xp[idx]

    y0, y1 = fp[idx - 1], fp[idx]

    t = (x - x0) / (x1 - x0)

    return y0 + t * (y1 - y0)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def numba_interp_vectorized(x_arr: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """Parallel vectorized linear interpolation"""

    n = len(x_arr)

    result = np.empty(n, dtype=np.float64)

    for i in prange(n):
        result[i] = numba_interp_scalar(x_arr[i], xp, fp)

    return result


class MaterialDatabase:
    """Thread-safe material DB with smart cache (Robust wrapper to prevent substrate/material cross-loading)"""

    def __init__(self, filepath: str = "clues.xlsx"):
        from certus.utils.certus_strat_db import RobustMaterialDatabase
        self._db = RobustMaterialDatabase(filepath)
        self._interpolation_cache = {}
        self._substrate_cache = {}
        self._computation_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def data(self) -> dict[str, dict[str, Any]]:
        return self._db.materials

    @property
    def _data(self):
        return self._db.materials

    @_data.setter
    def _data(self, value):
        self._db.materials = value

    def get_index(self, material_name: str, wavelength_nm: float) -> float:
        wl_rounded = round(wavelength_nm, 2)
        cache_key = (material_name, wl_rounded)
        if cache_key in self._interpolation_cache:
            return self._interpolation_cache[cache_key]

        # Standard get_index only returns real part (float) of layer material
        val = self._db.get_refractive_index(material_name, wavelength_nm)
        n_val = float(val.real)
        self._interpolation_cache[cache_key] = n_val
        return n_val

    def get_clues_vectorized(self, material_name: str, wavelengths: np.ndarray) -> np.ndarray:
        # Standard get_clues_vectorized only returns real parts (float) of layer material
        val = self._db.get_refractive_clues_vectorized(material_name, wavelengths)
        return val.real

    def clear_cache(self):
        self._interpolation_cache.clear()

    def get_material_list(self) -> list[str]:
        return list(self._db.materials.keys())

    def get_wavelength_range(self, material_name: str) -> tuple[float, float]:
        if material_name not in self._db.materials:
            raise ValueError(f"Material '{material_name}' not found")
        mat = self._db.materials[material_name]
        return float(mat["wl"][0]), float(mat["wl"][-1])

    @property
    def substrate_cache(self) -> dict:
        return self._substrate_cache

    def get_cached_computation(self, key: str, compute_func: Callable, *args, **kwargs):
        if key in self._computation_cache:
            self._cache_hits += 1
            return self._computation_cache[key]
        result = compute_func(*args, **kwargs)
        self._computation_cache[key] = result
        self._cache_misses += 1
        return result

    def get_cache_stats(self) -> dict:
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._computation_cache),
        }




# =============================================================================
