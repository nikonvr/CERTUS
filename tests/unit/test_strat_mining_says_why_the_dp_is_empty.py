"""Below the fewest feasible block count the DP has no grouping, and the miner says so (D9).

    THE FEWEST BLOCKS: contiguous blocks with one wavelength admissible in every layer of each block; greedy is optimal
        because any sub-interval of a feasible block stays feasible; 0 when a layer admits nothing
    THE MINER: under that count only the structured seeds remain, and one log line gives the count, so an empty DP no
        longer reads as an emptied search; above it the DP finds groupings and nothing is said
"""

from __future__ import annotations

import logging

from certus.core.certus_strat_ranking import fewest_feasible_blocks, mine_strategies_for_block_count


def _raw(sets: list[list[float]]) -> dict[int, list[dict[str, float]]]:
    return {i: [{"wl": w, "cost": 0.1 + 0.01 * k} for k, w in enumerate(ws)] for i, ws in enumerate(sets)}


# layers 0-2 share 500, layers 3-5 share 600, layer 6 admits only 700: three blocks at least
SETS = [[500.0, 510.0], [500.0, 520.0], [500.0], [600.0, 500.5], [600.0], [600.0, 610.0], [700.0]]


def test_the_fewest_blocks_is_the_greedy_count():
    cost_map = {i: {w: 1.0 for w in ws} for i, ws in enumerate(SETS)}
    assert fewest_feasible_blocks(cost_map, len(SETS)) == 3


def test_a_layer_without_any_admissible_wavelength_gives_zero():
    cost_map = {0: {500.0: 1.0}, 2: {500.0: 1.0}}
    assert fewest_feasible_blocks(cost_map, 3) == 0


def _mine(n_blocks: int, caplog) -> list:
    raw = _raw(SETS)
    with caplog.at_level(logging.INFO, logger="t"):
        return mine_strategies_for_block_count(
            n_blocks, raw, raw, len(SETS), top_k=5, sym_enable=False, logger=logging.getLogger("t")
        )


def test_under_the_fewest_count_the_miner_says_why_only_seeds_remain(caplog):
    strategies = _mine(2, caplog)
    assert all("STRUCTURED" in str(s.get("origin", "")) for s in strategies)
    assert "the DP found no grouping; the fewest contiguous blocks with one admissible wavelength per block is 3" in caplog.text


def test_at_the_fewest_count_the_dp_finds_groupings_and_nothing_is_said(caplog):
    strategies = _mine(3, caplog)
    assert any("STRUCTURED" not in str(s.get("origin", "")) for s in strategies)
    assert "the DP found no grouping" not in caplog.text
