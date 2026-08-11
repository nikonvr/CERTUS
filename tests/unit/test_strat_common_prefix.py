"""Ranking must use the margin where strategies DIFFER -- measured 2026-08-11.

Nine of the ten strategies tied at SEEL 0.3 nm returned the very same critical layer and
the very same margin: 0.83 A at layer 6. That is not a bug. All ten open with a 544 nm
block, so layer 6 is literally the same physics in all nine, and an identical margin is
the correct answer.

🔴 But a quantity that describes what strategies SHARE cannot rank them. The tenth had
its critical layer at 42 -- in the second block, where the wavelengths diverge -- with a
margin four times worse, and that one the margin did separate.

Hence two readings of the same data, for two different users:

  * the OPERATOR wants the weakest layer of all, shared prefix included: that is what
    will give way in the chamber;
  * the RANKING wants the weakest layer beyond the prefix, because the prefix is a floor
    every candidate stands on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from probe_anchor_noise_pipeline import (  # noqa: E402
    _layer_wavelengths,
    common_prefix_length,
    discriminating_margin,
)


def _row(bounds, wls, margins=None):
    return {
        "block_bounds": bounds,
        "wavelengths": wls,
        "margin_by_layer": margins or {},
    }


def test_layer_wavelengths_expands_blocks_to_layers():
    row = _row([[0, 3], [3, 5]], [544.0, 531.0])
    assert _layer_wavelengths(row) == [544.0, 544.0, 544.0, 531.0, 531.0]


def test_the_prefix_is_where_every_strategy_still_agrees():
    """The measured case: all open at 544, they diverge at their block boundary."""
    rows = [
        _row([[0, 24], [24, 48]], [544.0, 531.0]),
        _row([[0, 24], [24, 48]], [544.0, 545.0]),
        _row([[0, 24], [24, 48]], [544.0, 506.0]),
    ]
    assert common_prefix_length(rows) == 24


def test_a_differing_block_boundary_shortens_the_prefix():
    """Same wavelengths, different boundary: they part company at the earlier one."""
    rows = [
        _row([[0, 24], [24, 48]], [544.0, 531.0]),
        _row([[0, 10], [10, 48]], [544.0, 531.0]),
    ]
    assert common_prefix_length(rows) == 10


def test_identical_strategies_have_no_discriminating_region():
    rows = [_row([[0, 48]], [544.0])] * 3
    assert common_prefix_length(rows) == 48


def test_a_single_strategy_has_no_prefix_to_speak_of():
    """A prefix is a relation between strategies; one strategy has none."""
    assert common_prefix_length([_row([[0, 48]], [544.0])]) == 0


def test_the_shared_weak_layer_is_excluded_from_the_ranking_margin():
    """The whole point, on the measured numbers.

    Layer 6 at 0.83 A is inside the shared prefix -- every candidate carries it, so it
    ranks nothing. Layer 42 at 0.21 A is beyond it and does.
    """
    row = _row(
        [[0, 24], [24, 48]],
        [544.0, 531.0],
        {"fabricated": {"6": 0.83}, "level": {"42": 0.21}},
    )
    margin, layer, cause = discriminating_margin(row, prefix=24)
    assert layer == 42
    assert margin == 0.21
    assert cause == "level"


def test_nothing_beyond_the_prefix_is_reported_as_absent_not_as_safe():
    """🔴 A sentinel means 'no constraint found there', never 'this one is safe'."""
    row = _row([[0, 24], [24, 48]], [544.0, 531.0], {"fabricated": {"6": 0.83}})
    margin, layer, cause = discriminating_margin(row, prefix=24)
    assert layer == -1
    assert cause == ""
    assert margin >= 1e8, "doit rester une sentinelle, pas une marge confortable"


def test_the_operator_margin_still_sees_the_shared_layer():
    """Excluding the prefix is a RANKING device, not a redefinition of the risk.

    With prefix 0 -- the operator's view -- the weakest layer of all comes back, and it
    is the shared one. Both readings must remain available from the same data.
    """
    row = _row(
        [[0, 24], [24, 48]],
        [544.0, 531.0],
        {"fabricated": {"6": 0.83}, "level": {"42": 0.21}},
    )
    assert discriminating_margin(row, prefix=0)[0] == 0.21
    row_worse_shared = _row(
        [[0, 24], [24, 48]],
        [544.0, 531.0],
        {"fabricated": {"6": 0.10}, "level": {"42": 0.21}},
    )
    assert discriminating_margin(row_worse_shared, prefix=0)[1] == 6
    assert discriminating_margin(row_worse_shared, prefix=24)[1] == 42
