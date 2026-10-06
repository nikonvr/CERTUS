"""DESIGN's needle scan finds the same best position as trying every one against the independent TMM.

`needle_scan_cached` (certus/physics/certus_opt_needle.py) is the heart of the needle method: for every layer and
every depth on a grid it asks what would happen to the merit if a thin needle of another material were inserted
there, and returns the best (layer, depth, cost). It was covered at 3.5 % on 2026-09-30 (the JIT hides it) and no
test named it. It is fast because it caches the matrix products from both ends of the stack; the way to know that
the cache changes nothing is to do the slow thing, once, with a TMM that shares no code with it: build the stack
with the needle in place at each candidate, read T, score it, take the best.

The rules the scan documents, tested one by one: candidates are the depths step, 2 step, ... strictly inside a layer
(the ends are the interfaces), a layer thinner than a step has none, `scan_mask` excludes layers, a point of zero
weight or without a finite target does not score, fewer than five scored points give no valid cost, and with no
candidate the answer is `(-1, 0.0, 1e30)`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack

from certus.physics.certus_opt_needle import needle_scan_cached

pytestmark = pytest.mark.kernels

WLS = np.linspace(450.0, 700.0, 9)
N_H, N_L, N_SUB = 2.35, 1.46, 1.52
EP = np.array([80.0, 120.0, 12.0, 95.0])  # layer 2 is only 12 nm thick: two candidate depths, 5 and 10 nm
STEP, PROBE = 5.0, 1.0


def _arrays(ep=EP):
    n_layers = np.array([[N_H if j % 2 == 0 else N_L for j in range(len(ep))]] * len(WLS), dtype=np.complex128)
    n_needle = np.array([[N_L if j % 2 == 0 else N_H for j in range(len(ep))]] * len(WLS), dtype=np.complex128)
    return n_layers, n_needle, np.full(len(WLS), N_SUB, dtype=np.complex128)


def _scan(target, weights, mask, ep=EP, step=STEP):
    n_layers, n_needle, n_sub = _arrays(ep)
    return needle_scan_cached(WLS, n_layers, n_needle, n_sub, ep, target, weights, step, PROBE, mask)


def _candidates(ep, mask, step):
    """The (layer, depth) pairs the scan documents: depths step, 2 step, ... strictly inside a scanned layer."""
    for j, d in enumerate(ep):
        if mask[j] == 0 or d < step + 0.1:
            continue
        z = step
        while z < d - 0.1:
            yield j, z
            z += step


def _brute_force(target, weights, mask, ep=EP, step=STEP):
    """(layer, depth, cost) of the best candidate, each one scored by the independent TMM with the needle in place."""
    n_layers, n_needle, _ = _arrays(ep)
    best = (-1, 0.0, 1e30)
    scored = np.isfinite(target) & (weights > 0.0)
    for j, z in _candidates(ep, mask, step):
        cost = 0.0
        for w, wl in enumerate(WLS):
            if not scored[w]:
                continue
            n = [*n_layers[w, :j], n_layers[w, j], n_needle[w, j], n_layers[w, j], *n_layers[w, j + 1 :]]
            d = [*ep[:j], z, PROBE, ep[j] - z, *ep[j + 1 :]]
            transmission = rt_stack(wl, n, d, 1.0, N_SUB + 0j)[1]
            cost += weights[w] * (transmission - target[w]) ** 2
        cost = cost / scored.sum() if scored.sum() >= 5 else 1e30
        if best[0] == -1 or cost < best[2]:
            best = (j, z, cost)
    return best


TARGET = np.array([0.95, 0.95, 0.20, 0.10, 0.20, 0.95, 0.95, 0.95, 0.95])
WEIGHTS = np.array([1.0, 1.0, 2.0, 3.0, 2.0, 1.0, 1.0, 1.0, 1.0])
ALL = np.ones(len(EP), dtype=np.int64)


def test_the_best_needle_is_the_one_a_full_recomputation_finds() -> None:
    layer, depth, cost = _scan(TARGET, WEIGHTS, ALL)

    expected_layer, expected_depth, expected_cost = _brute_force(TARGET, WEIGHTS, ALL)
    assert (layer, depth) == (expected_layer, expected_depth)
    assert cost == pytest.approx(expected_cost, rel=1e-10)


def test_a_layer_left_out_of_the_mask_is_never_chosen_and_the_next_best_wins() -> None:
    mask = np.array([1, 0, 1, 1], dtype=np.int64)  # the scan is not allowed into layer 1
    expected = _brute_force(TARGET, WEIGHTS, mask)

    layer, depth, cost = _scan(TARGET, WEIGHTS, mask)

    assert layer != 1
    assert (layer, depth) == expected[:2]
    assert cost == pytest.approx(expected[2], rel=1e-10)


def test_a_layer_barely_thicker_than_a_step_offers_no_candidate_and_a_little_thicker_offers_one() -> None:
    """A depth must sit at least 0.1 nm inside the layer: `z < d - 0.1` and `d >= step + 0.1`."""
    only_the_third = np.array([0, 0, 1, 0], dtype=np.int64)

    for thickness, expected in ((5.05, (-1, 0.0)), (5.1, (-1, 0.0)), (5.2, (2, 5.0))):
        ep = np.array([80.0, 120.0, thickness, 95.0])
        layer, depth, _ = _scan(TARGET, WEIGHTS, only_the_third, ep=ep)

        assert (layer, depth) == expected, thickness
    assert _scan(TARGET, WEIGHTS, only_the_third, ep=np.array([80.0, 120.0, 5.05, 95.0])) == (-1, 0.0, 1e30)


def test_a_point_of_zero_weight_does_not_score() -> None:
    weights = WEIGHTS.copy()
    weights[3] = 0.0  # the deepest point of the notch no longer counts
    expected = _brute_force(TARGET, weights, ALL)

    layer, depth, cost = _scan(TARGET, weights, ALL)

    assert (layer, depth) == expected[:2]
    assert cost == pytest.approx(expected[2], rel=1e-10)


def test_a_point_without_a_finite_target_does_not_score() -> None:
    target = TARGET.copy()
    target[0] = np.nan  # a target that is missing, with a weight that says it counts
    expected = _brute_force(target, WEIGHTS, ALL)

    layer, depth, cost = _scan(target, WEIGHTS, ALL)

    assert np.isfinite(cost)
    assert (layer, depth) == expected[:2]
    assert cost == pytest.approx(expected[2], rel=1e-10)


def test_fewer_than_five_scored_points_give_no_valid_cost() -> None:
    weights = np.array([1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0, 0])  # four points: not enough to score a candidate

    layer, depth, cost = _scan(TARGET, weights, ALL)

    assert cost == 1e30  # every candidate is refused, the first is reported with the refusal
    assert (layer, depth) == (0, 5.0)
