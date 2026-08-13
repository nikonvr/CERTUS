"""The SEARCH must not depend on the SCORING DEPTH -- the invariant, and its guard.

🔴 WHY THIS FILE EXISTS. Until 2026-08-13 the inherited parents of block count `n+1`
were derived from the FULL pass of block count `n`, which runs at `robustness_num_runs`.
Depth therefore reached the candidate population, silently.

📏 What that produced, measured on four depths of the same run, same seed, same config.
The screening was IDENTICAL throughout -- 905 strategies, same per-block split -- yet:

    strategies retained per block count
      N= 50 | 1:13  2:54  3:76  4:31 ...        ranked total 343
      N=150 | 1:16  2:50  3:61  4:26 ...                      376
      N=300 | 1: 9  2:10  3: 0  4:52 ...                      229     <- block 3 -> ZERO
      N=500 | 1: 9  2:10  3: 0  4:59 ...                      284

The mechanism is the crash gate: `crash_rate_max >= 0.05 -> score = inf -> dropped`
compares a rate ESTIMATED on N draws to a FIXED threshold, so its sensitivity is a
function of N. At N = 50 it rejects 18.9 % of strategies whose true rate is 3 % (good,
under the threshold) and lets 31 % of those at 7 % (bad) through, where at N = 500 the
same figures are 1.0 % and 2.8 %.

    Two runs at different depths did not compare two precisions on one search.
    They compared two different searches.

🔑 THE INVARIANT THIS FILE GUARDS is an EQUALITY, not a statistic: the set of inherited
parents depends only on the screening pass, which no depth setting touches. A test that
merely compared distributions would pass on the broken code often enough to be useless.
"""

from __future__ import annotations

import inspect

from certus.workers import certus_strat_workers as W


def test_the_block_worker_publishes_its_screening_survivors():
    """They must leave the block function, or the caller cannot derive parents from them."""
    src = inspect.getsource(W)
    assert '"screening_survivors": list(unique_survivors)' in src, (
        "le worker de bloc doit remonter les survivantes du CRIBLAGE"
    )


def test_the_parents_come_from_the_screening_pass_and_not_from_the_full_one():
    """🔴 The regression this whole file exists for.

    `derive_strategies_exhaustive` must be fed the screening survivors. Feeding it
    `strategies_this_step` -- the full pass at `robustness_num_runs` -- is what made the
    search depend on the scoring depth, and it did so without any error.

    This test FAILS on the pre-2026-08-13 code.
    """
    src = inspect.getsource(W)
    call = src[src.index("inherited_strategies = derive_strategies_exhaustive("):]
    call = call[: call.index(")")]
    assert "strategies_this_step" not in call, (
        "les parents NE doivent PAS venir de la passe complete : sa profondeur est "
        "`robustness_num_runs`, donc la recherche dependrait du reglage de notation"
    )
    assert "parents" in call, "les parents viennent des survivantes du criblage"


def test_the_screening_survivors_are_still_contract_checked_as_parents():
    """`strategies_this_step` was contract-filtered and these are not, so the check moves
    with them -- otherwise a malformed payload would newly slip through."""
    src = inspect.getsource(W)
    head = src[src.index('parents_raw = result_batch.get("screening_survivors")'):]
    head = head[: head.index("inherited_strategies = derive_strategies_exhaustive(")]
    assert "_validate_strategy_blocks_contract" in head
    assert "expected_n_blocks=n_blk" in head


def test_the_screening_call_does_not_receive_the_scoring_depth():
    """Both screening passes run at `n_screen`. If either ever took `num_runs`, the
    population would become depth-dependent again through a different door."""
    src = inspect.getsource(W)
    for marker in ("screen_context_dp", "screen_context_inh"):
        i = src.index(marker + ", params")
        call = src[i : src.index(")", i)]
        assert "num_runs=n_screen" in call, f"{marker} doit cribler a n_screen"
        assert "expand_variants=False" in call, (
            f"{marker} ne doit pas etendre les variantes : le criblage choisit des "
            "strategies, pas des variantes"
        )
