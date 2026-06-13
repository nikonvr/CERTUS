"""P1-12 Micro-Batch B.5 – Direct tests for calculate_RT_batch_kernel.

Invariants verified:
  1. Single-run batch on a known QW stack agrees with single-point TMM.
  2. Energy conservation: R + T ≈ 1 for each wavelength, each run.
  3. Identical stacks produce identical (R, T) across all runs.
"""
from __future__ import annotations

import numpy as np
import pytest

from certus_physics import calculate_RT_batch_kernel, calculate_RT_vectorized_real_HL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WAVELENGTHS = np.array([400.0, 550.0, 700.0], dtype=np.float64)
N_H = 2.3 + 0j
N_L = 1.45 + 0j
N_SUB = 1.52 + 0j
L0 = 550.0  # reference wavelength (nm)

# QW thicknesses at L0
D_H = L0 / (4.0 * np.real(N_H))   # ≈ 59.78 nm
D_L = L0 / (4.0 * np.real(N_L))   # ≈ 94.83 nm

NH_ARR = np.full(len(WAVELENGTHS), N_H, dtype=np.complex128)
NL_ARR = np.full(len(WAVELENGTHS), N_L, dtype=np.complex128)
NS_ARR = np.full(len(WAVELENGTHS), N_SUB, dtype=np.complex128)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_b5_batch_single_run_agrees_with_vectorized_kernel():
    """Single-run batch R/T agrees with calculate_RT_vectorized_real_HL at each wavelength."""
    stack = np.array([[D_H, D_L]], dtype=np.float64)  # shape (1, 2)
    R_batch, T_batch = calculate_RT_batch_kernel(WAVELENGTHS, NH_ARR, NL_ARR, NS_ARR, stack)

    # Reference: vectorized over wavelengths, single stack
    R_vec, T_vec = calculate_RT_vectorized_real_HL(
        WAVELENGTHS, NH_ARR, NL_ARR, NS_ARR, np.array([D_H, D_L], dtype=np.float64)
    )

    np.testing.assert_allclose(R_batch[0], R_vec, atol=1e-8,
        err_msg="R mismatch: batch[0] vs vectorized")
    np.testing.assert_allclose(T_batch[0], T_vec, atol=1e-8,
        err_msg="T mismatch: batch[0] vs vectorized")


def test_b5_batch_energy_conservation():
    """R + T ≈ 1 for all runs and all wavelengths (lossless stack)."""
    num_runs = 5
    stacks = np.tile([D_H, D_L], (num_runs, 1)).astype(np.float64)
    R_batch, T_batch = calculate_RT_batch_kernel(WAVELENGTHS, NH_ARR, NL_ARR, NS_ARR, stacks)

    sums = R_batch + T_batch
    np.testing.assert_allclose(
        sums, 1.0, atol=1e-6,
        err_msg="Energy not conserved (R+T != 1) in batch kernel"
    )


def test_b5_batch_identical_stacks_produce_identical_results():
    """Identical rows in the batch must yield bit-identical (R, T)."""
    num_runs = 4
    stacks = np.tile([D_H, D_L], (num_runs, 1)).astype(np.float64)
    R_batch, T_batch = calculate_RT_batch_kernel(WAVELENGTHS, NH_ARR, NL_ARR, NS_ARR, stacks)

    for run_i in range(1, num_runs):
        np.testing.assert_array_equal(
            R_batch[run_i], R_batch[0],
            err_msg=f"R differs between run 0 and run {run_i} for identical stacks"
        )
        np.testing.assert_array_equal(
            T_batch[run_i], T_batch[0],
            err_msg=f"T differs between run 0 and run {run_i} for identical stacks"
        )
