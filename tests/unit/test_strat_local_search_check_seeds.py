"""How many fresh seeds judge the plan of the local search (`strat_local_search_check_seeds`, chantier 7, 2 by default).

On two seeds the check flipped between versions of the code: on 2026-11-20 it kept the 35c plan (stops 338 -> 10) that it
had refused on 2026-10-21 (0 -> 2), and refused a 36c plan 63 % better in P95 (1 -> 6) where it had kept one before; the
benchmarks moved by -29 % and +12 % for that verdict alone (reports/nuit_2026-11-19/bilan_6_ecarts_35c_36c.md). Owner
decision (2026-11-20): a setting for more seeds, off by default: 2 keeps the two seeds of before, to the bit.
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_local_search import (
    CHECK_SEED_OFFSETS,
    check_seed_offsets,
    check_seeds_for,
    check_seeds_setting,
)


def test_two_seeds_are_the_two_of_before() -> None:
    assert check_seed_offsets(2) == CHECK_SEED_OFFSETS == (7_100_003, 7_100_011)


def test_more_seeds_extend_the_same_sequence() -> None:
    assert check_seed_offsets(6) == (7_100_003, 7_100_011, 7_100_019, 7_100_027, 7_100_035, 7_100_043)


def test_one_seed_is_the_first_of_before() -> None:
    assert check_seed_offsets(1) == (7_100_003,)


@pytest.mark.parametrize("count", [0, -3])
def test_a_check_needs_at_least_one_seed(count) -> None:
    with pytest.raises(ValueError, match="at least one"):
        check_seed_offsets(count)


@pytest.mark.parametrize(
    ("params", "expected"),
    [({}, 2), ({"strat_local_search_check_seeds": 6}, 6), ({"strat_local_search_check_seeds": "6"}, 6),
     ({"strat_local_search_check_seeds": 0}, 1), ({"strat_local_search_check_seeds": "invalid"}, 2)],
)
def test_the_setting_reads_the_params(params, expected) -> None:
    assert check_seeds_setting(params) == expected


def test_the_worker_seeds_are_the_offsets_of_the_robustness_seed() -> None:
    assert check_seeds_for({}, 42) == (42 + 7_100_003, 42 + 7_100_011)
    assert check_seeds_for({"strat_local_search_check_seeds": 3}, 101) == (101 + 7_100_003, 101 + 7_100_011, 101 + 7_100_019)


def test_the_worker_takes_its_check_seeds_from_the_setting() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "certus/workers/certus_strat_workers_local_search.py").read_text(
        encoding="utf-8")
    assert "check_seeds = check_seeds_for(params, base_seed)" in source
