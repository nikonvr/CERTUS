import numpy as np
import pytest

from certus.core.certus_array_utils import (
    as_float64_1d,
    sorted_float64,
    interp_sorted,
)

def test_as_float64_1d():
    # Test simple list
    arr = [1, 2, 3]
    res = as_float64_1d(arr)
    assert isinstance(res, np.ndarray)
    assert res.dtype == np.float64
    assert res.ndim == 1
    np.testing.assert_array_equal(res, np.array([1.0, 2.0, 3.0]))

    # Test 2D array flattening
    arr2d = np.array([[1, 2], [3, 4]])
    res2d = as_float64_1d(arr2d)
    assert res2d.ndim == 1
    np.testing.assert_array_equal(res2d, np.array([1.0, 2.0, 3.0, 4.0]))

    # Test copy flag
    orig = np.array([1.0, 2.0], dtype=np.float64)
    res_no_copy = as_float64_1d(orig, copy=False)
    assert np.shares_memory(res_no_copy, orig)  # Same memory

    res_copy = as_float64_1d(orig, copy=True)
    assert res_copy is not orig
    np.testing.assert_array_equal(res_copy, orig)


def test_sorted_float64():
    arr = [3.0, 1.0, 2.0]
    res = sorted_float64(arr)
    assert isinstance(res, np.ndarray)
    assert res.dtype == np.float64
    np.testing.assert_array_equal(res, np.array([1.0, 2.0, 3.0]))

    # Test copy flag
    arr_np = np.array([3.0, 1.0, 2.0], dtype=np.float64)
    res_no_copy = sorted_float64(arr_np, copy=False)
    assert res_no_copy is not arr_np # np.sort always returns a new array anyway for unsorted, but let's test if already sorted
    
    sorted_np = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    res_sorted_no_copy = sorted_float64(sorted_np, copy=False)
    # np.sort returns a copy even if sorted, so out is a new array.
    # The copy=False in sorted_float64 only prevents an ADDITIONAL copy at the end.
    np.testing.assert_array_equal(res_sorted_no_copy, sorted_np)


def test_interp_sorted():
    x = [1.5, 2.5]
    xp = [1.0, 2.0, 3.0]
    fp = [10.0, 20.0, 30.0]

    res = interp_sorted(x, xp, fp)
    assert res.dtype == np.float64
    np.testing.assert_array_equal(res, np.array([15.0, 25.0]))

    # Test left and right bounds
    x_bounds = [0.0, 4.0]
    res_bounds = interp_sorted(x_bounds, xp, fp, left=0.0, right=40.0)
    np.testing.assert_array_equal(res_bounds, np.array([0.0, 40.0]))
