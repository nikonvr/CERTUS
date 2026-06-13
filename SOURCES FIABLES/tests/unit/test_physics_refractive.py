"""P1-12 Micro-Batch B.8 – Direct tests for get_refractive_clues_vectorized and get_refractive_index.

Invariants verified:
  1. Constant float ID → all wavelengths return that constant (real-valued).
  2. Output is a 1D array of same length as wavelength input.
  3. get_refractive_index(float_id, wl) agrees with vectorized at same point.
  4. All returned values have positive real part (physical requirement).
"""
from __future__ import annotations

import numpy as np
import pytest

from certus_physics import get_refractive_clues_vectorized, get_refractive_index


WAVELENGTHS = np.array([400.0, 500.0, 550.0, 700.0, 900.0], dtype=np.float64)
N_CONST = 2.3  # constant refractive index (acts as a "material ID" for fixed-n material)


def test_b8_float_id_returns_constant():
    """A scalar float material ID should return that constant at all wavelengths."""
    result = get_refractive_clues_vectorized(N_CONST, WAVELENGTHS)
    np.testing.assert_allclose(np.real(result), N_CONST, atol=1e-9,
        err_msg="Float material ID did not return constant refractive index")


def test_b8_output_shape_matches_wavelengths():
    """Output array length must equal the number of input wavelengths."""
    result = get_refractive_clues_vectorized(1.45, WAVELENGTHS)
    assert len(result) == len(WAVELENGTHS), (
        f"Shape mismatch: got {len(result)}, expected {len(WAVELENGTHS)}"
    )


def test_b8_single_vs_vectorized_agreement():
    """get_refractive_index(id, wl) must agree with vectorized at each point."""
    mat_id = 1.52  # glass-like constant
    vec_result = get_refractive_clues_vectorized(mat_id, WAVELENGTHS)
    for i, wl in enumerate(WAVELENGTHS):
        single = get_refractive_index(mat_id, float(wl))
        assert abs(np.real(vec_result[i]) - np.real(single)) < 1e-9, (
            f"Mismatch at {wl} nm: vectorized={vec_result[i]:.6f}, single={single:.6f}"
        )


def test_b8_positive_real_part():
    """All refractive indices must have a physically meaningful positive real part."""
    for mat_id in [1.0, 1.45, 2.3, 3.5]:
        result = get_refractive_clues_vectorized(mat_id, WAVELENGTHS)
        assert np.all(np.real(result) > 0), (
            f"Non-positive real part found for material id={mat_id}: {result}"
        )
