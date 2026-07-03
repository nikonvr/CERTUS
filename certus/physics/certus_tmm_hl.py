import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import calculate_bare_substrate_R, calculate_bare_substrate_RT


# --- LOCKED --- Validated by test_tmm_coherence.py (test_analytical_hlh, test_vectorized_vs_reference) ───


# Macleod convention (+1j). Delegates to calculate_RT_no_backside. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _calculate_RT_HL_core(
    wls: np.ndarray,
    nH: np.ndarray,
    nL: np.ndarray,
    nSub: np.ndarray,
    thicknesses: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Core TMM calculationation for alternating H/L stacks (front surface only).

    Index array dtype matches input nH dtype (f32 -> c64, f64 -> c128)."""

    n_wls = len(wls)

    n_layers = len(thicknesses)

    # Always use double precision (complex128)

    n_layers_complex = np.empty((n_wls, n_layers), dtype=np.complex128)

    # Parallel index array construction

    for i in prange(n_wls):
        valH = nH[i]

        valL = nL[i]

        for j in range(n_layers):
            if j % 2 == 0:
                n_layers_complex[i, j] = valH

            else:
                n_layers_complex[i, j] = valL

    return calculate_RT_no_backside(thicknesses, n_layers_complex, nSub, wls)


# --- LOCKED --- Validated by test_tmm_coherence.py (test_vectorized_vs_reference) ───


# Macleod convention (+1j). HL wrapper with backside. DO NOT MODIFY without running tests.


def calculate_RT_vectorized_real_HL(
    wls: np.ndarray,
    nH: np.ndarray,
    nL: np.ndarray,
    nSub: np.ndarray,
    thicknesses: np.ndarray,
    with_backside: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Wrapper for alternating H/L stacks with optional backside correction.

    Assumes layer 0 is H, layer 1 is L, etc.

    Args:

        wls: Wavelength array

        nH: High index material n(lambda)

        nL: Low index material n(lambda)

        nSub: substrate n(lambda)

        thicknesses: Layer thicknesses

                     IMPORTANT: Index 0 is the layer AGAINST THE SUBSTRATE.

                     This function assumes alternating H/L layers starting with H at index 0 (sub-side).

        with_backside: If True, apply incoherent backside correction (default True)

    Returns:

        R, T arrays

    CRITICAL PHYSICS NOTE:

    This function controls the Strategy Engines view of the world.

    - with_backside=True: Standard mode (Glass Plate). Uses exact incoherent sum.

    - with_backside=False: Optimized mode or Special substrates. Front only.

    DO NOT CHANGE THE DEFAULT OR LOGIC BRANCHING.

    """

    if with_backside:
        n_layers = len(thicknesses)
        n_layers_all_wls = np.empty((len(wls), n_layers), dtype=np.complex128)
        for i in range(n_layers):
            if i % 2 == 0:
                n_layers_all_wls[:, i] = nH
            else:
                n_layers_all_wls[:, i] = nL
        nSub_f = np.asarray(nSub, dtype=np.complex128)
        return calculate_RT_with_backside_fused(thicknesses, n_layers_all_wls, nSub_f, wls)

    else:
        # Front surface calculationation only

        Rf, Tf = _calculate_RT_HL_core(wls, nH, nL, nSub, thicknesses)

        return Rf, Tf


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Incoherent HL backside. DO NOT MODIFY without running tests.


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). index 0 = substrate. DO NOT MODIFY without running tests.


# =============================================================================


# =========================================================================================

