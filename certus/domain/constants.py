"""Constants that the physics layer reads, in a file that imports nothing of CERTUS.

They lived in `certus.core.certus_core`, so every kernel file of `certus/physics/` imported the core for one number:
fourteen upward imports on 2026-09-30, twelve of them for `TWO_PI`. Under everything that reads them they cut those
edges. `certus.core.certus_core` re-exports each name, so `from certus.core.certus_core import TWO_PI` still works.

Numba freezes these values into the machine code of the kernels that read them. The cache directory is keyed by the
sources whose text mentions Numba (`numba_cache_key`), and that is why THIS text says so: change a value here with
this file outside the key, and kernels compiled with the old value are read back from the cache.
`tests/unit/test_the_cache_key_covers_what_the_kernels_read.py` fails on a module that gives a kernel a value
without naming Numba.
"""

from functools import lru_cache

import numpy as np

# --- Optical constants ---

PI: float = np.pi

TWO_PI: float = 6.283185307179586

N_SUPERSTRATE: float = 1.0  # Air


# --- Precision ---

WL_DECIMALS: int = 6


# --- Frosted Glass (Infinite Substrate) ---

FROSTED_GLASS_N: float = 1.52  # Average index

FROSTED_GLASS_CAUCHY_A: float = 1.5046

FROSTED_GLASS_CAUCHY_B: float = 4200.0  # nm²


# --- Default dtypes ---
# Double precision. Measured on 2026-08-02 (see `get_precision_config` in certus_core): the mixed f32/c64 policy
# is 1.1 % slower and loses eight orders of magnitude on R.


@lru_cache(maxsize=1)
def get_float_dtype() -> type[np.float64]:
    """Default float dtype: double precision.

    Cached for performance.
    """

    return np.float64


@lru_cache(maxsize=1)
def get_complex_dtype() -> type[np.complex128]:
    """Default complex dtype: double precision.

    Cached for performance.
    """

    return np.complex128
