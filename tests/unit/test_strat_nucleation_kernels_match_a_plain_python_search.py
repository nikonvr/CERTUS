"""The two nucleation kernels do what their loops say (audit v2, plan S3.2: the STRAT kernels had no test of their own).

`rank_nucleation_candidates_kernel` and `find_nucleation_adaptive_kernel` (`certus/physics/certus_strat_nucleation.py`, 16 % covered before this file) grow a
stack layer by layer with `simulate_growth_kernel` under seeded noise, once per Monte Carlo run, and score a candidate wavelength by the root mean square
of the thickness errors. They are parallel, fast-math, and their noise is generated inside the kernel. What is pinned here is what a plain Python rewrite of
the same loops, written from the docstrings and calling the same growth kernel and the same noise generator, gives:

    the scores of the ranking, for both noise laws and both modes of the non-monotonic rule
    the sizes and errors of the adaptive search, for a sweep of thresholds that makes it stop at each size in turn
    the three ways the search stops: the error of a size above the limit, a degradation ratio above the threshold, the largest size reached
    what must not depend on anything: the same seed gives the same numbers, a noise-free ranking does not depend on where a candidate stands in the list
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_growth import simulate_growth_kernel
from certus.physics.certus_strat_math import _seeded_noise_sample
from certus.physics.certus_strat_nucleation import (
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    find_nucleation_adaptive_kernel,
    rank_nucleation_candidates_kernel,
)

pytestmark = pytest.mark.kernels

# A quarter-wave stack of 2.35 / 1.46 at 540 nm, four pairs, monitored at three wavelengths around it. The growth kernel ends a layer either on its nominal
# thickness or, when the noisy signal never reaches its target, on the nominal plus the sentinel of a failed layer (1e6 nm): the errors are not graded, they
# are counted in sentinels, and at a transmittance noise of 0.02 the number of sentinels depends on the candidate, the size and the seed.
N_HIGH, N_LOW, N_SUBSTRATE = 2.35, 1.46, 1.52
NOMINAL = np.array([540.0 / (4 * (N_HIGH if i % 2 == 0 else N_LOW)) for i in range(8)], dtype=np.float64)
CANDIDATES = np.array([500.0, 540.0, 580.0], dtype=np.float64)
N_H = np.full(3, N_HIGH + 0.0j, dtype=np.complex128)
N_L = np.full(3, N_LOW + 0.0j, dtype=np.complex128)
N_SUB = np.full(3, N_SUBSTRATE + 0.0j, dtype=np.complex128)
NOISE, OFFSET, FACTOR = 0.02, 0.0, 1.0
SMALLEST, LARGEST = 3, 7
#: With this seed several sizes of a candidate end exactly on their nominal thickness (an error of 0) and the next one meets a sentinel: the only way the
#: floor of the degradation ratio (a previous error under 0.05 is counted as 0.05) can matter. With most seeds every size is already saturated.
SEED_WITH_CLEAN_SIZES = 13


def thickness_of(wl, n_h, n_l, n_sub, index, stack, noise, mode):
    """One layer grown by the growth kernel, as both nucleation kernels call it."""
    return simulate_growth_kernel(NOMINAL, index, stack[:index], wl, n_h, n_l, n_sub, OFFSET, noise, FACTOR, mode)[0]


def noise_vector(seed, group, run, size, gaussian):
    return np.array([_seeded_noise_sample(seed, group, run, j, gaussian) * NOISE for j in range(size)])


def plain_scores(candidates, min_size, mc_runs, gaussian, mode, seed):
    scores = np.zeros(len(candidates))
    for i, wl in enumerate(candidates):
        total = 0.0
        for run in range(mc_runs):
            noise = noise_vector(seed, i, run, min_size, gaussian)
            stack = np.zeros(min_size)
            for j in range(min_size):
                stack[j] = thickness_of(wl, N_H[i], N_L[i], N_SUB[i], j, stack, noise[j], mode)
                total += (stack[j] - NOMINAL[j]) ** 2
        scores[i] = np.sqrt(total / (mc_runs * min_size))
    return scores


def rmse_by_size(i_cand, wl, min_size, max_size, mc_runs, gaussian, mode, seed):
    """The error of each size the adaptive search tries, from the same loops (the group of the noise is `i_cand + size`)."""
    out = {}
    for size in range(min_size, max_size + 1):
        total = 0.0
        for run in range(mc_runs):
            noise = noise_vector(seed, i_cand + size, run, size, gaussian)
            stack = np.zeros(size)
            for i in range(size):
                stack[i] = thickness_of(wl, N_H[i_cand], N_L[i_cand], N_SUB[i_cand], i, stack, noise[i], mode)
                total += (stack[i] - NOMINAL[i]) ** 2
        out[size] = float(np.sqrt(total / (mc_runs * size)))
    return out


def plain_search(rmse, min_size, max_size, degradation_threshold, max_rmse):
    """The stopping rule of the adaptive search, applied to the errors of the sizes: (last valid size, its error)."""
    previous, last_valid, final = 0.0, 0, 0.0
    for size in range(min_size, max_size + 1):
        value = rmse[size]
        if value > max_rmse:
            break
        if size > min_size and value / max(previous, 0.05) > degradation_threshold:
            break
        last_valid, previous, final = size, value, value
    return last_valid, final


def rank(**overrides):
    args = {"min_size": 6, "mc_runs": 4, "gaussian": True, "mode": NON_MONOTONIC_MODE_ATTENUATE, "seed": 11}
    args.update(overrides)
    return rank_nucleation_candidates_kernel(
        CANDIDATES, NOMINAL, N_H, N_L, N_SUB, args.get("noise", NOISE), OFFSET, FACTOR, args["min_size"], args["mc_runs"], args["gaussian"], args["mode"], args["seed"]
    )


def search(min_size=SMALLEST, max_size=LARGEST, mc_runs=3, degradation=1.5, max_rmse=1e9, gaussian=True, mode=NON_MONOTONIC_MODE_ATTENUATE, seed=11):
    return find_nucleation_adaptive_kernel(
        CANDIDATES, NOMINAL, N_H, N_L, N_SUB, NOISE, OFFSET, FACTOR, min_size, max_size, mc_runs, degradation, max_rmse, gaussian, mode, seed
    )


# --- the ranking ---------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("gaussian", [True, False])
@pytest.mark.parametrize("mode", [NON_MONOTONIC_MODE_ATTENUATE, NON_MONOTONIC_MODE_REJECT])
def test_the_scores_are_those_of_a_plain_python_ranking(gaussian, mode):
    expected = plain_scores(CANDIDATES, 6, 4, gaussian, mode, 11)
    np.testing.assert_allclose(rank(gaussian=gaussian, mode=mode), expected, rtol=1e-9, atol=1e-12)


def test_there_is_one_finite_non_negative_score_per_candidate():
    scores = rank()
    assert scores.shape == (len(CANDIDATES),)
    assert np.all(np.isfinite(scores))
    assert np.all(scores >= 0.0)


def test_the_same_seed_gives_the_same_scores_and_another_seed_gives_others():
    first, again, other = rank(seed=11), rank(seed=11), rank(seed=12)
    np.testing.assert_array_equal(first, again)
    assert not np.allclose(first, other)


def test_the_two_noise_laws_give_different_scores():
    assert not np.allclose(rank(gaussian=True), rank(gaussian=False))


def test_without_noise_a_candidate_scores_the_same_wherever_it_stands_in_the_list():
    kept = rank_nucleation_candidates_kernel(CANDIDATES, NOMINAL, N_H, N_L, N_SUB, 0.0, OFFSET, FACTOR, 6, 2, True, NON_MONOTONIC_MODE_ATTENUATE, 3)
    order = [2, 0, 1]
    moved = rank_nucleation_candidates_kernel(
        CANDIDATES[order], NOMINAL, N_H[order], N_L[order], N_SUB[order], 0.0, OFFSET, FACTOR, 6, 2, True, NON_MONOTONIC_MODE_ATTENUATE, 3
    )
    np.testing.assert_allclose(moved, kept[order], rtol=1e-12)


def test_more_noise_costs_more_error():
    quiet = rank_nucleation_candidates_kernel(CANDIDATES, NOMINAL, N_H, N_L, N_SUB, 0.0, OFFSET, FACTOR, 6, 4, True, NON_MONOTONIC_MODE_ATTENUATE, 5)
    loud = rank_nucleation_candidates_kernel(CANDIDATES, NOMINAL, N_H, N_L, N_SUB, 0.08, OFFSET, FACTOR, 6, 4, True, NON_MONOTONIC_MODE_ATTENUATE, 5)
    assert np.all(loud >= quiet)
    assert np.any(loud > quiet)


# --- the adaptive search -------------------------------------------------------------------------------------------------------------------


def expected_search(degradation, max_rmse, **kw):
    sizes, errors = [], []
    for i, wl in enumerate(CANDIDATES):
        values = rmse_by_size(i, wl, SMALLEST, LARGEST, 3, kw.get("gaussian", True), kw.get("mode", NON_MONOTONIC_MODE_ATTENUATE), kw.get("seed", 11))
        size, error = plain_search(values, SMALLEST, LARGEST, degradation, max_rmse)
        sizes.append(size)
        errors.append(error)
    return np.array(sizes), np.array(errors)


@pytest.mark.parametrize("seed", [11, SEED_WITH_CLEAN_SIZES])
@pytest.mark.parametrize("gaussian", [True, False])
@pytest.mark.parametrize("mode", [NON_MONOTONIC_MODE_ATTENUATE, NON_MONOTONIC_MODE_REJECT])
def test_the_search_is_that_of_a_plain_python_search(gaussian, mode, seed):
    sizes, errors = search(gaussian=gaussian, mode=mode, seed=seed)
    want_sizes, want_errors = expected_search(1.5, 1e9, gaussian=gaussian, mode=mode, seed=seed)
    np.testing.assert_array_equal(sizes, want_sizes)
    np.testing.assert_allclose(errors, want_errors, rtol=1e-9, atol=1e-12)


def test_with_no_limit_the_search_reaches_the_largest_size_and_reports_its_error():
    sizes, errors = search(degradation=1e9, max_rmse=1e9)
    np.testing.assert_array_equal(sizes, [LARGEST] * 3)
    want = [rmse_by_size(i, wl, SMALLEST, LARGEST, 3, True, NON_MONOTONIC_MODE_ATTENUATE, 11)[LARGEST] for i, wl in enumerate(CANDIDATES)]
    np.testing.assert_allclose(errors, want, rtol=1e-9, atol=1e-12)


def test_an_error_limit_below_every_size_leaves_no_valid_size():
    sizes, errors = search(max_rmse=-1.0)
    np.testing.assert_array_equal(sizes, [0, 0, 0])
    np.testing.assert_array_equal(errors, [0.0, 0.0, 0.0])


def test_the_smallest_size_is_never_judged_on_degradation():
    # a threshold of zero rejects every size after the first, but the first is kept
    sizes, _ = search(degradation=0.0, max_rmse=1e9)
    np.testing.assert_array_equal(sizes, [SMALLEST] * 3)


def test_the_search_stops_at_each_size_in_turn_as_the_threshold_comes_down():
    """Thresholds just under the ratio that stops each candidate at size k-1: the kernel and the plain search agree on every one."""
    values = [rmse_by_size(i, wl, SMALLEST, LARGEST, 3, True, NON_MONOTONIC_MODE_ATTENUATE, SEED_WITH_CLEAN_SIZES) for i, wl in enumerate(CANDIDATES)]
    ratios = sorted({values[i][s] / max(values[i][s - 1], 0.05) for i in range(len(CANDIDATES)) for s in range(SMALLEST + 1, LARGEST + 1)})
    assert max(ratios) > 1e5  # a size that ends on its nominal, then one that does not: the ratio is a sentinel over the floor
    for threshold in [*(r * 0.999 for r in ratios), *(r * 1.001 for r in ratios)]:
        sizes, _ = search(degradation=threshold, seed=SEED_WITH_CLEAN_SIZES)
        want_sizes, _ = expected_search(threshold, 1e9, seed=SEED_WITH_CLEAN_SIZES)
        np.testing.assert_array_equal(sizes, want_sizes, err_msg=f"threshold {threshold}")


def test_the_search_stops_when_the_error_of_a_size_passes_the_limit():
    values = [rmse_by_size(i, wl, SMALLEST, LARGEST, 3, True, NON_MONOTONIC_MODE_ATTENUATE, 11) for i, wl in enumerate(CANDIDATES)]
    limit = float(np.median([values[i][5] for i in range(len(CANDIDATES))]))
    sizes, _ = search(degradation=1e9, max_rmse=limit)
    want_sizes, _ = expected_search(1e9, limit)
    np.testing.assert_array_equal(sizes, want_sizes)
    assert set(sizes) != {LARGEST}  # the limit did stop at least one candidate before the largest size


def test_the_same_seed_gives_the_same_search_and_another_changes_the_errors():
    first, again, other = search(seed=11), search(seed=11), search(seed=12)
    np.testing.assert_array_equal(first[0], again[0])
    np.testing.assert_array_equal(first[1], again[1])
    assert not np.allclose(first[1], other[1])
