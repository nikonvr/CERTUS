"""The kernels under STRAT's Monte-Carlo batches agree with the independent TMM and with what they document.

`certus/physics/certus_strat_batch.py` was covered at 7.3 % on 2026-09-30 (the JIT hides it) and no test named it.
Its small kernels feed every robustness run:

* `corridor_wl_range`: ONE definition of the wavelength interval on which the index perturbation is normalised,
  the envelope of the spectral grid and the monitoring wavelengths (defined once so that the three callers cannot
  drift apart, docstring);
* `_calculate_RT_HL_single_point` and `calculate_RT_batch_kernel`: R and T of an alternating H/L stack on a
  substrate whose back face reflects incoherently, one run or a batch of runs, against the oracle's plate;
* `precompute_matrix_cache_kernel`: the matrix of the first i layers, for every layer and wavelength;
* `compute_batch_rmse`: the score of every run against a target transmission, uniform or weighted by zone.

The physics is checked against `tests/oracle/tmm_reference.py`, never against the kernel (prohibition 7).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_plate_incoherent, stack_matrix

from certus.physics.certus_strat_batch import (
    _calculate_RT_HL_single_point,
    calculate_RT_batch_kernel,
    compute_batch_rmse,
    corridor_wl_range,
    precompute_matrix_cache_kernel,
)

pytestmark = pytest.mark.kernels

N_H, N_L, N_SUB = 2.35 + 0j, 1.46 + 0j, 1.52 + 0j


def _hl(n_layers: int, n_h: complex = N_H, n_l: complex = N_L) -> list[complex]:
    """The index of each layer of an H/L stack, layer 0 (first deposited, next to the substrate) = H."""
    return [n_h if j % 2 == 0 else n_l for j in range(n_layers)]


def _oracle_plate(wl: float, thicknesses, n_h=N_H, n_l=N_L, n_sub=N_SUB) -> tuple[float, float]:
    return rt_plate_incoherent(wl, _hl(len(thicknesses), n_h, n_l), thicknesses, [], [], n_sub, 0.0, True, 1.0e6)


# =============================================================================
# The interval of the index perturbation
# =============================================================================


def test_the_interval_is_the_envelope_of_the_spectral_grid_and_the_monitoring_wavelengths() -> None:
    lo, hi = corridor_wl_range(np.array([400.0, 600.0, 800.0]), np.array([500.0, 900.0]))

    assert (lo, hi) == (400.0, 900.0)  # the monitoring wavelength beyond the grid widens it
    assert corridor_wl_range(np.array([400.0, 800.0]), np.array([500.0, 600.0])) == (400.0, 800.0)  # inside: the grid


def test_a_degenerate_interval_is_opened_to_one_hundred_nanometres() -> None:
    assert corridor_wl_range(np.array([550.0]), np.array([550.0])) == (550.0, 650.0)  # never a zero-width division


# =============================================================================
# R and T of an alternating stack
# =============================================================================


@pytest.mark.parametrize("n_layers", [1, 2, 5, 8])
def test_one_run_at_one_wavelength_is_the_oracles_plate(n_layers) -> None:
    rng = np.random.default_rng(n_layers)
    thicknesses = rng.uniform(30.0, 160.0, n_layers)

    for wl in (450.0, 543.0, 632.8):
        r, t = _calculate_RT_HL_single_point(wl, N_H, N_L, N_SUB, thicknesses)

        expected_r, expected_t = _oracle_plate(wl, thicknesses)
        assert r == pytest.approx(expected_r, abs=1e-12)
        assert t == pytest.approx(expected_t, abs=1e-12)


def test_a_batch_is_one_run_per_row_and_one_column_per_wavelength() -> None:
    rng = np.random.default_rng(3)
    wls = np.array([450.0, 500.0, 600.0])
    batch = rng.uniform(30.0, 160.0, (4, 6))
    batch[3] = batch[0]  # a repeated run

    r, t = calculate_RT_batch_kernel(
        wls, np.full(3, N_H), np.full(3, N_L), np.full(3, N_SUB), batch
    )

    assert r.shape == t.shape == (4, 3)
    for run in range(4):
        for col, wl in enumerate(wls):
            expected_r, expected_t = _oracle_plate(wl, batch[run])
            assert r[run, col] == pytest.approx(expected_r, abs=1e-12)
            assert t[run, col] == pytest.approx(expected_t, abs=1e-12)
    np.testing.assert_array_equal(r[3], r[0])  # the same thicknesses give the same row, whatever the thread


def test_each_wavelength_reads_its_own_indices() -> None:
    wls = np.array([450.0, 600.0])
    n_h = np.array([2.40 + 0j, 2.30 + 0j])
    n_l = np.array([1.47 + 0j, 1.45 + 0j])
    thicknesses = np.array([[55.0, 90.0, 55.0, 90.0]])

    r, t = calculate_RT_batch_kernel(wls, n_h, n_l, np.full(2, N_SUB), thicknesses)

    for col in range(2):
        expected_r, expected_t = _oracle_plate(wls[col], thicknesses[0], n_h[col], n_l[col])
        assert (r[0, col], t[0, col]) == pytest.approx((expected_r, expected_t), abs=1e-12)


# =============================================================================
# The matrix cache
# =============================================================================


def test_the_cache_holds_the_matrix_of_the_layers_deposited_so_far_for_every_wavelength() -> None:
    wls = np.array([450.0, 550.0, 650.0])
    thicknesses = np.array([53.19, 85.62, 53.19, 85.62, 53.19])
    n_h, n_l = np.full(3, N_H), np.full(3, N_L)

    cache = precompute_matrix_cache_kernel(wls, n_h, n_l, thicknesses, len(thicknesses))

    assert cache.shape == (5, 3, 2, 2)
    assert cache.dtype == np.complex128
    for i in range(5):
        for col, wl in enumerate(wls):
            expected = stack_matrix(_hl(i + 1), thicknesses[: i + 1], wl)
            np.testing.assert_allclose(cache[i, col], expected, atol=1e-12)


# =============================================================================
# The score of a batch of runs
# =============================================================================

SCORE_WLS = np.array([450.0, 500.0, 550.0, 600.0, 650.0])
SCORE_TARGET = np.array([0.90, 0.10, 0.85, 0.50, 0.95])
SCORE_BATCH = np.random.default_rng(11).uniform(40.0, 150.0, (3, 6))


def _score(weights=None, **kwargs):
    n_wls = len(SCORE_WLS)
    layers = np.tile(np.array(_hl(SCORE_BATCH.shape[1]), dtype=np.complex128), (n_wls, 1))
    return compute_batch_rmse(
        SCORE_BATCH, SCORE_WLS, np.full(n_wls, N_H), np.full(n_wls, N_L), np.full(n_wls, N_SUB), SCORE_TARGET, layers,
        weights, **kwargs
    )  # fmt: skip


def _oracle_differences() -> np.ndarray:
    """(n_runs, n_wls) of T(oracle plate) - target."""
    return np.array(
        [[_oracle_plate(wl, run)[1] - target for wl, target in zip(SCORE_WLS, SCORE_TARGET, strict=True)] for run in SCORE_BATCH]
    )


def test_the_score_of_a_run_is_the_root_mean_square_distance_of_its_transmission_to_the_target() -> None:
    expected = np.sqrt(np.mean(_oracle_differences() ** 2, axis=1))

    np.testing.assert_allclose(_score(), expected, rtol=1e-12)


def test_a_weighted_score_averages_over_the_weights_and_a_zero_weight_leaves_the_denominator() -> None:
    weights = np.array([1.0, 0.0, 3.0, 0.0, 1.0])  # the points outside every zone weigh nothing
    diffs = _oracle_differences()

    expected = np.sqrt((weights * diffs**2).sum(axis=1) / weights.sum())

    np.testing.assert_allclose(_score(weights), expected, rtol=1e-12)


def test_a_grid_that_no_zone_covers_scores_infinity_and_not_a_perfect_zero() -> None:
    assert np.all(np.isinf(_score(np.zeros(len(SCORE_WLS)))))


def test_the_index_corridor_is_reproducible_by_its_seed_and_moves_the_score() -> None:
    off = _score()
    same_off = _score(index_corridor=0.0, index_seed=5, corridor_wl_min=450.0, corridor_wl_max=650.0)
    on_a = _score(index_corridor=0.01, index_seed=5, corridor_wl_min=450.0, corridor_wl_max=650.0)
    on_b = _score(index_corridor=0.01, index_seed=5, corridor_wl_min=450.0, corridor_wl_max=650.0)
    other_seed = _score(index_corridor=0.01, index_seed=6, corridor_wl_min=450.0, corridor_wl_max=650.0)

    np.testing.assert_array_equal(same_off, off)  # corridor 0: the historical path, whatever the seed and bounds
    np.testing.assert_array_equal(on_a, on_b)  # a draw is a function of the seed and the run, nothing else
    assert not np.array_equal(on_a, off)  # an index uncertainty of 1e-2 changes the score
    assert not np.array_equal(on_a, other_seed)  # and another seed is another realisation
