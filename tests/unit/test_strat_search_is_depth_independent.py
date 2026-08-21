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


def test_the_inherited_screening_call_does_not_receive_the_scoring_depth():
    """The inherited screening runs at `n_screen`. If it ever took `num_runs`, the
    population would become depth-dependent again through a different door."""
    src = inspect.getsource(W)
    i = src.index("screen_context_inh, params")
    call = src[i : src.index(")", i)]
    assert "num_runs=n_screen" in call, "screen_context_inh doit cribler a n_screen"
    assert "expand_variants=False" in call, (
        "screen_context_inh ne doit pas etendre les variantes : le criblage choisit des "
        "strategies, pas des variantes"
    )


def test_every_screening_inside_the_multiseed_helper_runs_at_the_screening_depth():
    """🔴 THE GUARD MOVED WITH THE CODE IT GUARDS, ON 2026-08-21, AND IT GOT STRICTER.

    The DP screening used to be a single inline call anchored on `screen_context_dp, params`.
    It now lives in `_screen_with_seeds`, which runs it once per seed of `screen_seed_list` and
    unions the survivors by plan signature -- the multiseed repair, placed at the one stage
    upstream where the two seeds' populations were measured to diverge.

    ⚠️ Moving a guard is exactly where an invariant gets lost in silence, so this version is
    STRONGER than the one it replaces: instead of checking one call, it checks that EVERY
    `run_final_simulation_block` inside the helper screens at `n_screen`. The helper has two
    such calls -- the historical single-seed path and the per-seed loop -- and a future third
    one would be caught too.

    🔒 And the depth reaching the helper is checked at the call site below, because a helper
    that screens at `n_screen` is worthless if the caller hands it `num_runs`.
    """
    src = inspect.getsource(W)
    debut = src.index("def _screen_with_seeds(")
    corps = src[debut : src.index("\ndef ", debut + 10)]

    appels = corps.count("run_final_simulation_block(")
    assert appels >= 2, (
        f"attendu au moins deux appels de criblage dans _screen_with_seeds, vu {appels} -- "
        "si le chemin mono-graine a disparu, la regle d'or n'est plus garantie au bit"
    )
    assert corps.count("num_runs=n_screen") == appels, (
        "CHAQUE criblage de _screen_with_seeds doit tourner a n_screen : "
        f"{appels} appels, {corps.count('num_runs=n_screen')} a la bonne profondeur"
    )
    assert corps.count("expand_variants=False") == appels, (
        "CHAQUE criblage doit refuser l'expansion de variantes : le criblage choisit des "
        "strategies, pas des variantes"
    )
    assert "num_runs=num_runs" not in corps and "robustness_num_runs" not in corps, (
        "la profondeur de NOTATION ne doit jamais apparaitre dans le criblage"
    )


def test_the_multiseed_helper_is_called_with_the_screening_depth_not_the_scoring_one():
    """🔒 L'autre moitie de l'invariant : ce que l'appelant passe reellement."""
    src = inspect.getsource(W)
    i = src.index("survivors_dp = _screen_with_seeds(")
    call = src[i : src.index(")", i)]
    assert "n_screen" in call, "le criblage DP doit recevoir n_screen"
    assert "n_full" not in call and "num_runs" not in call, (
        "le criblage DP ne doit JAMAIS recevoir la profondeur de notation"
    )


def test_the_multiseed_union_never_reranks_across_seeds():
    """The union carries PLANS, and the full pass rescores them on the run's own seed.

    🔴 Why this must be pinned. The screening scores returned by `_screen_with_seeds` come
    from DIFFERENT seeds and are NOT comparable to one another. If anything downstream ever
    sorted the union by `robustness_score`, the realisation would be CHOOSING candidates --
    the exact inversion of the project invariant that the realisation serves to SCORE, never
    to CHOOSE. The full pass must therefore be the only ranking authority.
    """
    src = inspect.getsource(W)
    debut = src.index("final_context = pre_calc_data.copy()")
    corps = src[debut : src.index("final_results = final_run", debut)]
    assert 'final_context["all_strategies"] = [r["strategy"] for r in unique_survivors]' in corps, (
        "la passe complete doit recevoir les PLANS seuls, jamais les scores de criblage"
    )
