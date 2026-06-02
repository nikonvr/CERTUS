"""Noyaux d'optimisation / coût sur `_certus_physics_impl` (P1-12)."""

from __future__ import annotations

import numpy as np
import numpy.testing as npt
import pytest

from certus.core._certus_physics_impl import compute_mse_vectorized


def test_compute_mse_vectorized_five_equal_weights_is_mean_squared_error() -> None:
    calc = np.array([0.0, 1.0, 2.0, 0.0, 3.0], dtype=np.float64)
    tgt = np.array([0.0, 2.0, 2.0, 0.0, 5.0], dtype=np.float64)
    w = np.ones(5, dtype=np.float64)
    diffs = (calc - tgt) ** 2
    mse, count = compute_mse_vectorized(calc, tgt, w)
    assert count == 5
    npt.assert_allclose(mse, float(np.mean(diffs)))


def test_compute_mse_vectorized_too_few_valid_points_returns_penalty() -> None:
    calc = np.zeros(4, dtype=np.float64)
    tgt = np.ones(4, dtype=np.float64)
    w = np.ones(4, dtype=np.float64)
    mse, count = compute_mse_vectorized(calc, tgt, w)
    assert count == 4
    assert mse == pytest.approx(1e12, rel=0.0, abs=0.0)


def test_compute_mse_vectorized_skips_zero_weight() -> None:
    # Cinq points valides, erreur^2=1 chacun ; seul poids nul en i1.
    calc = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    tgt = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    w = np.array([1.0, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    mse, count = compute_mse_vectorized(calc, tgt, w)
    assert count == 5
    npt.assert_allclose(mse, 1.0)
