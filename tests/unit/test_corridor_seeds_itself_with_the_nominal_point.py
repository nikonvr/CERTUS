"""`CorridorContextBuilder._seed_corridor_with_the_nominal_point` records the nominal profile as the corridor's first point (audit v2, plan S5.2).

The block was the head of `_process_center_solution`, a 305-line method no unit test reaches. It decides three things, each pinned here on its own:

    whether there is a first point        only with an absolute-delta corridor whose n and k curves have the grid's size, and a finite RMSE to give it
    which RMSE it carries                 the optimiser's RMSE when the nominal comes from a scientific pack, the spectral-curves RMSE otherwise
    which curves the corridor is measured against   the pack's own n and k when there is one, a copy of the first fit's curves when there is not

The returned pair is (reference k, reference n): the helper hands back what it was given, unchanged, when it records nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.spline.certus_corridor_config import CorridorContextBuilder

LAM = np.linspace(400.0, 800.0, 5)
N_B = np.array([1.50, 1.51, 1.52, 1.53, 1.54])
K_B = np.array([0.0, 0.001, 0.002, 0.003, 0.004])
PACK = {"n_lam": np.array([[1.4, 1.41, 1.42, 1.43, 1.44]]), "k_lam": np.array([[0.1, 0.1, 0.1, 0.1, 0.1]])}


def builder():
    pushed: list[tuple] = []
    return SimpleNamespace(
        d_vals=[],
        n_curves=[],
        k_curves=[],
        rmse_vals=[],
        chi2_vals=[],
        fit_nfev_values=[],
        fit_nit_values=[],
        fit_try_values=[],
        fit_fail_values=[],
        live_streamer=SimpleNamespace(push_point=lambda *args: pushed.append(args)),
        pushed=pushed,
    )


def seed(b, *, use_abs_delta=True, scientific=True, pack=PACK, n_b=N_B, k_b=K_B, rmse_curves=0.02, rmse_opt=0.01, ref_n=None, ref_k=None, d0=95.0):
    return CorridorContextBuilder._seed_corridor_with_the_nominal_point(b, LAM, use_abs_delta, d0, scientific, pack, n_b, k_b, rmse_curves, rmse_opt, ref_n, ref_k)


def test_a_scientific_nominal_gives_its_rmse_and_its_own_reference_curves():
    b = builder()
    ref_k, ref_n = seed(b)
    assert b.d_vals == [95.0]
    assert b.rmse_vals == [0.01]
    np.testing.assert_array_equal(ref_n, PACK["n_lam"].ravel())
    np.testing.assert_array_equal(ref_k, PACK["k_lam"].ravel())
    assert ref_n is not PACK["n_lam"]
    assert not np.shares_memory(ref_n, PACK["n_lam"])


def test_without_a_pack_the_reference_is_a_copy_of_the_first_fit_and_the_rmse_is_the_curves_one():
    b = builder()
    ref_k, ref_n = seed(b, scientific=False, pack=None)
    assert b.rmse_vals == [0.02]
    np.testing.assert_array_equal(ref_n, N_B)
    np.testing.assert_array_equal(ref_k, K_B)
    assert not np.shares_memory(ref_n, N_B)
    assert not np.shares_memory(ref_k, K_B)


def test_the_stored_and_streamed_curves_are_copies_so_a_later_edit_cannot_reach_them():
    b = builder()
    seed(b, scientific=False, pack=None)
    assert not np.shares_memory(b.n_curves[0], N_B)
    assert not np.shares_memory(b.k_curves[0], K_B)
    (d, rmse, n_curve, k_curve, chi2) = b.pushed[0]
    assert (d, rmse) == (95.0, 0.02)
    assert not np.shares_memory(n_curve, N_B)
    assert not np.shares_memory(k_curve, K_B)
    assert np.isnan(chi2)


def test_the_first_point_has_no_fit_statistics():
    b = builder()
    seed(b)
    for values in (b.chi2_vals, b.fit_nfev_values, b.fit_nit_values, b.fit_try_values, b.fit_fail_values):
        assert len(values) == 1
        assert np.isnan(values[0])


def test_a_nan_rmse_without_a_pack_records_nothing_and_hands_the_references_back():
    b = builder()
    sentinel_n, sentinel_k = np.array([9.0]), np.array([8.0])
    ref_k, ref_n = seed(b, scientific=False, pack=None, rmse_curves=float("nan"), ref_n=sentinel_n, ref_k=sentinel_k)
    assert (b.d_vals, b.rmse_vals, b.pushed) == ([], [], [])
    assert ref_n is sentinel_n
    assert ref_k is sentinel_k


@pytest.mark.parametrize(
    "change",
    [{"use_abs_delta": False}, {"n_b": N_B[:3]}, {"k_b": K_B[:2]}],
    ids=["not an absolute-delta corridor", "n curve of another size", "k curve of another size"],
)
def test_no_first_point_when_the_corridor_is_not_absolute_or_the_curves_do_not_fit_the_grid(change):
    b = builder()
    ref_k, ref_n = seed(b, **change)
    assert (b.d_vals, b.n_curves, b.pushed) == ([], [], [])
    assert ref_n is None
    assert ref_k is None


def test_the_method_that_builds_the_corridor_calls_the_helper():
    import inspect

    assert "self._seed_corridor_with_the_nominal_point(" in inspect.getsource(CorridorContextBuilder._process_center_solution)
