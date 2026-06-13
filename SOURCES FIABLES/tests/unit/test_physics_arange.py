"""P1-12 Micro-Batch B.7 – Direct tests for arange_inclusive.

Invariants verified:
  1. Endpoints always included (unlike np.arange which may exclude stop).
  2. Step size is respected within floating-point tolerance.
  3. Result is monotonically increasing.
  4. Single-point degenerate range returns exactly one element.
"""
from __future__ import annotations

import numpy as np
import pytest

from certus_physics import arange_inclusive


def test_b7_endpoints_included():
    """Both start and stop must be present in the output."""
    arr = arange_inclusive(400.0, 700.0, 5.0)
    assert arr[0] == pytest.approx(400.0, abs=1e-9)
    assert arr[-1] == pytest.approx(700.0, abs=1e-9)


def test_b7_step_uniformity():
    """All consecutive differences must equal the requested step."""
    arr = arange_inclusive(400.0, 700.0, 10.0)
    diffs = np.diff(arr)
    np.testing.assert_allclose(diffs, 10.0, atol=1e-9,
        err_msg="Non-uniform step in arange_inclusive output")


def test_b7_monotonically_increasing():
    """Output must be strictly monotonically increasing."""
    arr = arange_inclusive(300.0, 1000.0, 2.0)
    assert np.all(np.diff(arr) > 0), "Array is not strictly increasing"


def test_b7_degenerate_single_point():
    """start == stop should return a single-element array."""
    arr = arange_inclusive(550.0, 550.0, 1.0)
    assert len(arr) == 1
    assert arr[0] == pytest.approx(550.0, abs=1e-9)


def test_b7_length_matches_expected():
    """Number of points = (stop - start) / step + 1 when evenly divisible."""
    arr = arange_inclusive(400.0, 700.0, 1.0)
    assert len(arr) == 301  # (700-400)/1 + 1
