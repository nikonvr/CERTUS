"""Phase B of STRAT: which wavelengths can serve a block of layers, and how the layers are split into blocks.

`certus/physics/certus_strat_dp.py` holds the two kernels of the dynamic programme that turns phase A's per-layer
candidates into strategies. It was covered at 5.5 % on 2026-09-30 (the JIT hides it from `coverage`, and the
oracle does not reach it) and no test named it. Each test builds a case small enough to solve by hand, so the
expected numbers come from the definition and not from the kernel:

* `_compute_valid_blocks_kernel`: a block of layers [i, j) can be monitored at a wavelength only if that wavelength
  is valid in EVERY layer of the block; its cost is the sum of the layers' costs there; the `top_k` cheapest are
  kept, and `min_wl_sep` spreads them over distinct regions of the spectrum without ever sacrificing the best;
* `_dp_kernel`: the cheapest way to cut `num_layers` layers into `n_blocks` blocks, block after block.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_dp import _compute_valid_blocks_kernel, _dp_kernel

pytestmark = pytest.mark.kernels

WLS = np.tile([500.0, 600.0, 700.0], (3, 1))
COSTS = np.array([[1.0, 2.0, 3.0], [1.5, 0.5, 4.0], [2.0, 2.0, 0.1]])


def _blocks(valid=None, top_k=3, min_wl_sep=0.0, wls=WLS, costs=COSTS):
    num_layers, max_w = wls.shape
    valid = np.ones((num_layers, max_w), dtype=np.bool_) if valid is None else valid
    return _compute_valid_blocks_kernel(wls, costs, valid, num_layers, top_k, max_w, min_wl_sep)


def test_a_block_costs_the_sum_of_its_layers_at_a_common_wavelength_cheapest_first() -> None:
    costs, wls, counts = _blocks()

    assert counts[0, 1] == 3
    assert costs[0, 1, :3].tolist() == [1.0, 2.0, 3.0] and wls[0, 1, :3].tolist() == [500.0, 600.0, 700.0]
    # layers 0 and 1: 500 -> 1 + 1.5, 600 -> 2 + 0.5, 700 -> 3 + 4 ; the tie keeps the grid order
    assert costs[0, 2, :3].tolist() == [2.5, 2.5, 7.0] and wls[0, 2, :3].tolist() == [500.0, 600.0, 700.0]
    # layers 1 and 2: 500 -> 1.5 + 2, 600 -> 0.5 + 2, 700 -> 4 + 0.1
    assert costs[1, 3, :3].tolist() == [2.5, 3.5, 4.1] and wls[1, 3, :3].tolist() == [600.0, 500.0, 700.0]
    assert costs[0, 3, :3] == pytest.approx([4.5, 4.5, 7.1])  # all three layers


def test_a_wavelength_invalid_in_one_layer_is_out_of_every_block_that_contains_that_layer() -> None:
    valid = np.ones((3, 3), dtype=np.bool_)
    valid[1, 0] = False  # 500 nm is not usable in layer 1

    costs, wls, counts = _blocks(valid=valid)

    assert counts[0, 1] == 3  # layer 0 alone is untouched
    assert counts[0, 2] == 2 and wls[0, 2, :2].tolist() == [600.0, 700.0]  # 500 is gone from [0, 2)
    assert counts[1, 2] == 2 and counts[2, 3] == 3
    assert costs[0, 2, :2].tolist() == [2.5, 7.0]


def test_a_wavelength_masked_in_another_layer_of_the_block_is_not_borrowed_from_it() -> None:
    """Two layers with two valid wavelengths each, not the same two: only the common one can serve the block.
    The mask must count in the layer where the wavelength is looked for, not only where it was proposed."""
    valid = np.array([[True, True, False], [False, True, True], [True, True, True]])

    costs, wls, counts = _blocks(valid=valid)

    assert counts[0, 2] == 1  # 500 is valid in layer 0 and masked in layer 1; 700 the other way round
    assert wls[0, 2, 0] == 600.0 and costs[0, 2, 0] == pytest.approx(2.0 + 0.5)


def test_a_layer_with_no_valid_wavelength_empties_every_block_around_it() -> None:
    valid = np.ones((3, 3), dtype=np.bool_)
    valid[1, :] = False

    _, _, counts = _blocks(valid=valid)

    assert counts[0, 1] == 3 and counts[2, 3] == 3
    assert counts[1, 2] == counts[0, 2] == counts[1, 3] == counts[0, 3] == 0


def test_only_the_top_k_cheapest_wavelengths_are_kept() -> None:
    costs, wls, counts = _blocks(top_k=2)

    assert counts[0, 1] == 2
    assert costs[0, 1, :2].tolist() == [1.0, 2.0] and wls[0, 1, :2].tolist() == [500.0, 600.0]


def _clustered(costs=(1.0, 1.1, 1.2, 3.0), wls=(500.0, 501.0, 502.0, 700.0)):
    return np.array([wls]), np.array([costs])


def test_a_minimum_separation_spreads_the_candidates_and_keeps_the_best() -> None:
    layer_wls, layer_costs = _clustered()

    without = _blocks(top_k=2, wls=layer_wls, costs=layer_costs)
    spread = _blocks(top_k=2, min_wl_sep=50.0, wls=layer_wls, costs=layer_costs)

    assert without[1][0, 1, :2].tolist() == [500.0, 501.0]  # legacy: the two cheapest, side by side
    assert spread[1][0, 1, :2].tolist() == [500.0, 700.0]  # the best is kept, the next is another region
    assert spread[0][0, 1, :2].tolist() == [1.0, 3.0]


def test_when_the_spectrum_offers_too_few_regions_the_remaining_cheapest_complete_the_block() -> None:
    layer_wls, layer_costs = _clustered(costs=(1.0, 1.1, 1.2, 9.0), wls=(500.0, 501.0, 502.0, 503.0))

    costs, wls, counts = _blocks(top_k=3, min_wl_sep=50.0, wls=layer_wls, costs=layer_costs)

    assert counts[0, 1] == 3  # one region only, and the block is not left short
    assert wls[0, 1, :3].tolist() == [500.0, 501.0, 502.0] and costs[0, 1, :3].tolist() == [1.0, 1.1, 1.2]


def test_the_programme_cuts_the_layers_where_the_total_is_cheapest_and_keeps_the_runners_up() -> None:
    block_costs, block_wls, block_counts = _blocks()

    dp_costs, starts, ends, wls, counts = _dp_kernel(block_costs, block_wls, block_counts, 2, 3, 3)

    # two blocks over three layers: cut after layer 2 costs 2.5 + 0.1 = 2.6 (500 or 600 nm for the first block, the
    # tie kept in grid order), cut after layer 1 costs 1.0 + 2.5 = 3.5
    assert counts[2, 3] == 6  # 2 * top_k candidates, sorted by cost
    assert dp_costs[2, 3, :3] == pytest.approx([2.6, 2.6, 3.5])
    assert starts[2, 3, 0].tolist() == [0, 2] and ends[2, 3, 0].tolist() == [2, 3]
    assert wls[2, 3, 0].tolist() == [500.0, 700.0]  # the last layer is monitored where it is cheap: 0.1 at 700 nm
    assert wls[2, 3, 1].tolist() == [600.0, 700.0]
    assert starts[2, 3, 2].tolist() == [0, 1] and ends[2, 3, 2].tolist() == [1, 3]  # the other cut comes third
    assert list(dp_costs[2, 3, :6]) == sorted(dp_costs[2, 3, :6])


def test_one_block_over_all_the_layers_is_the_cheapest_common_wavelength() -> None:
    block_costs, block_wls, block_counts = _blocks()

    dp_costs, starts, ends, wls, counts = _dp_kernel(block_costs, block_wls, block_counts, 1, 3, 3)

    assert dp_costs[1, 3, 0] == pytest.approx(4.5)
    assert (starts[1, 3, 0, 0], ends[1, 3, 0, 0]) == (0, 3) and wls[1, 3, 0, 0] == 500.0
    assert counts[1, 3] == 3  # the three wavelengths can all serve the whole stack


def test_no_way_to_cut_the_layers_leaves_no_candidate() -> None:
    valid = np.ones((3, 3), dtype=np.bool_)
    valid[1, :] = False  # the middle layer cannot be monitored: no cut into blocks can cover it
    block_costs, block_wls, block_counts = _blocks(valid=valid)

    dp_costs, _, _, _, counts = _dp_kernel(block_costs, block_wls, block_counts, 2, 3, 3)

    assert counts[2, 3] == 0
    assert np.isinf(dp_costs[2, 3, 0])
