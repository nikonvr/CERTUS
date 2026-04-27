"""Regression tests for the Sapphire Fresnel dataset cache helper.

Locks the contract of `_certus_physics_impl._get_sapphire_n_dataset` before the
P1-13 refactor that replaces the three module-level globals
(`_SAPPHIRE_FRESNEL_LOADED`, `_SAPPHIRE_FRESNEL_WLS`, `_SAPPHIRE_FRESNEL_N`)
with a single `@functools.lru_cache(maxsize=1)`.

Acceptance: the helper must
1. Return identical objects on consecutive calls (caching).
2. Either return `(None, None)` if the dataset is unavailable, or two finite
   ndarrays of equal length with `wl.size >= 2`.
3. Never raise.
"""

from __future__ import annotations

import numpy as np
import pytest

import _certus_physics_impl as phy


@pytest.fixture(scope="module")
def first_call_result():
    return phy._get_sapphire_n_dataset()


def test_sapphire_dataset_consecutive_calls_return_same_arrays(first_call_result):
    wl1, n1 = first_call_result
    wl2, n2 = phy._get_sapphire_n_dataset()
    if wl1 is None:
        assert wl2 is None
        assert n2 is None
    else:
        # Must be the SAME object reference (cache hit) or at least equal arrays.
        np.testing.assert_array_equal(wl1, wl2)
        np.testing.assert_array_equal(n1, n2)


def test_sapphire_dataset_shape_invariants(first_call_result):
    wl, n = first_call_result
    if wl is None:
        # Acceptable contract: dataset missing -> (None, None).
        assert n is None
        return
    assert isinstance(wl, np.ndarray)
    assert isinstance(n, np.ndarray)
    assert wl.size == n.size
    assert wl.size >= 2
    assert wl.dtype == np.float64
    assert n.dtype == np.float64


def test_sapphire_dataset_finite_when_loaded(first_call_result):
    wl, n = first_call_result
    if wl is None:
        return
    assert np.all(np.isfinite(wl))
    assert np.all(np.isfinite(n))


def test_sapphire_dataset_is_sorted_when_loaded(first_call_result):
    wl, _ = first_call_result
    if wl is None:
        return
    diffs = np.diff(wl)
    assert np.all(diffs >= 0.0), "Sapphire dataset wavelengths must be non-decreasing"


def test_sapphire_dataset_no_raise_on_repeated_calls():
    for _ in range(5):
        wl, n = phy._get_sapphire_n_dataset()
        # Either both None or both ndarrays — never mixed.
        assert (wl is None) == (n is None)
