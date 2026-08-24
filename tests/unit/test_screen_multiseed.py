"""MULTISEED AU CRIBLAGE -- l'etage ou les graines divergent.

WHY THIS EXISTS. Measured 2026-08-21 on `r75x2` at 2 nm, `deep`: the populations of seeds 42
and 77 share NO common prefix. Comparing by exact plan signature, block count by block count --

    n_blocks      1      2-6     7-10    11-15
    in common  46.7 %   7.4 %   ~1 %      0 %

At block count 1, where nothing is inherited yet, half the population already differs. The only
stochastic stage upstream is the screening, and its survivors become the next block count's
`inherited_strategies` and ELITE's parents. So the union of K screenings is the repair, and
these tests pin the three properties that make it defensible:

    1. with no seed list, the historical single call runs -- unchanged, one call, same slice;
    2. the union deduplicates by PLAN SIGNATURE, never by `strategy_id` (24-51: 21 ids out of
       79 carry two or three DIFFERENT strategies, so dedup by id would merge distinct plans);
    3. `robustness_seed` is RESTORED afterwards, even when a screening raises -- the full pass
       that follows must score on the run's seed, never on the last screening seed.
"""

from __future__ import annotations

import logging

import pytest

from certus.workers.certus_strat_workers import (
    _resolve_screen_seeds,
    _screen_with_seeds,
)

LOGGER = logging.getLogger("test_screen_multiseed")


def _plan(*wls: float) -> dict:
    """A strategy whose plan signature is determined by the wavelengths given."""
    return {
        "strategy_id": 1,  # deliberately CONSTANT: dedup must not depend on the id
        "n_blocks": len(wls),
        "blocks": [
            {"start": i * 5, "end": (i + 1) * 5, "wavelength": float(w)}
            for i, w in enumerate(wls)
        ],
    }


def _res(strategy: dict, score: float) -> dict:
    return {"strategy": strategy, "robustness_score": float(score)}


class TestResolveScreenSeeds:
    @pytest.mark.parametrize(
        "params,attendu",
        [
            ({}, []),
            ({"screen_seed_list": None}, []),
            ({"screen_seed_list": ""}, []),
            ({"screen_seed_list": []}, []),
            ({"screen_seed_list": "42"}, [42]),
            ({"screen_seed_list": "42,77,101"}, [42, 77, 101]),
            ({"screen_seed_list": "42;77"}, [42, 77]),
            ({"screen_seed_list": [42, 77, 42, 101]}, [42, 77, 101]),
            ({"screen_seed_list": "42.0, 77.9"}, [42, 77]),
            ({"screen_seed_list": "42,,abc,77"}, [42, 77]),
            ({"screen_seed_list": 42}, [42]),
        ],
    )
    def test_parsing(self, params, attendu):
        assert _resolve_screen_seeds(params) == attendu

    def test_order_is_preserved(self):
        """The log reports the seeds in this order; a reader must be able to follow it."""
        assert _resolve_screen_seeds({"screen_seed_list": "101,42,77"}) == [101, 42, 77]

    def test_an_object_without_get_is_not_a_crash(self):
        assert _resolve_screen_seeds(object()) == []


class TestScreenWithSeedsSingle:
    """The historical path. It must stay ONE call, with params untouched."""

    def test_no_seed_list_runs_exactly_one_screening(self, monkeypatch):
        appels = []

        def faux(ctx, params, num_runs=None, expand_variants=None):
            appels.append({
                "num_runs": num_runs,
                "expand_variants": expand_variants,
                "seed": params.get("robustness_seed"),
                "n_strats": len(ctx["all_strategies"]),
            })
            return {"all_strategies_results": [
                _res(_plan(600.0), 0.30), _res(_plan(610.0), 0.10), _res(_plan(620.0), 0.20),
            ]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        params = {"robustness_seed": 42}
        out = _screen_with_seeds(
            [_plan(600.0)], {"num_layers": 5}, params, 50, 2, LOGGER, "T"
        )

        assert len(appels) == 1
        assert appels[0] == {"num_runs": 50, "expand_variants": False, "seed": 42, "n_strats": 1}
        assert params == {"robustness_seed": 42}, "params must come back untouched"
        # sorted by score, sliced to k_keep
        assert [r["robustness_score"] for r in out] == [0.10, 0.20]

    def test_a_single_seed_in_the_list_is_still_the_single_path(self, monkeypatch):
        """One seed is not a union: it must not pay the multiseed machinery."""
        appels = []

        def faux(ctx, params, num_runs=None, expand_variants=None):
            appels.append(params.get("robustness_seed"))
            return {"all_strategies_results": [_res(_plan(600.0), 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        params = {"robustness_seed": 42, "screen_seed_list": "77"}
        _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")
        # The single path does NOT override the seed -- it is the run's seed that applies.
        assert appels == [42]

    def test_empty_results_do_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block",
            lambda *a, **k: {},
        )
        assert _screen_with_seeds([_plan(600.0)], {}, {}, 50, 5, LOGGER, "T") == []


class TestScreenWithSeedsUnion:
    def test_each_seed_is_screened_and_the_seed_is_restored(self, monkeypatch):
        vues = []

        def faux(ctx, params, num_runs=None, expand_variants=None):
            vues.append(params.get("robustness_seed"))
            # each seed prefers a different plan
            return {"all_strategies_results": [_res(_plan(600.0 + 10 * len(vues)), 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        params = {"robustness_seed": 42, "screen_seed_list": "42,77,101"}
        out = _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")

        assert vues == [42, 77, 101]
        assert params["robustness_seed"] == 42, "the run's seed must be restored"
        assert len(out) == 3, "three distinct plans -> three kept"

    def test_union_deduplicates_by_plan_never_by_id(self, monkeypatch):
        """Every result carries strategy_id == 1. Dedup by id would keep ONE.

        24-51: 21 ids out of 79 carry two or three DIFFERENT strategies. Deduplicating by id
        would MERGE distinct plans, which is exactly the loss this union exists to prevent.
        """
        plans = [_plan(600.0), _plan(610.0), _plan(600.0)]
        etat = {"i": 0}

        def faux(ctx, params, num_runs=None, expand_variants=None):
            p = plans[etat["i"]]
            etat["i"] += 1
            return {"all_strategies_results": [_res(p, 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        out = _screen_with_seeds(
            [_plan(600.0)], {}, {"robustness_seed": 42, "screen_seed_list": "1,2,3"},
            50, 5, LOGGER, "T",
        )
        assert all(r["strategy"]["strategy_id"] == 1 for r in out)
        assert len(out) == 2, "the repeated PLAN is dropped, the distinct one is kept"

    def test_the_seed_is_restored_even_when_a_screening_raises(self, monkeypatch):
        def faux(ctx, params, num_runs=None, expand_variants=None):
            if params.get("robustness_seed") == 77:
                raise RuntimeError("criblage en echec")
            return {"all_strategies_results": [_res(_plan(600.0), 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        params = {"robustness_seed": 42, "screen_seed_list": "42,77"}
        with pytest.raises(RuntimeError):
            _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")
        assert params["robustness_seed"] == 42, "restored by the finally clause"

    def test_k_keep_applies_PER_SEED_so_the_union_can_exceed_it(self, monkeypatch):
        """k_keep bounds each screening; the union is bounded by K * k_keep, and that is wanted.

        The point of the union is to widen the parent pool. Applying k_keep to the union would
        undo the diversity it was paid for.
        """
        etat = {"i": 0}

        def faux(ctx, params, num_runs=None, expand_variants=None):
            etat["i"] += 1
            base = 600.0 + 100 * etat["i"]
            return {"all_strategies_results": [
                _res(_plan(base), 0.1), _res(_plan(base + 1), 0.2), _res(_plan(base + 2), 0.3),
            ]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        out = _screen_with_seeds(
            [_plan(600.0)], {}, {"robustness_seed": 42, "screen_seed_list": "1,2"},
            50, 2, LOGGER, "T",
        )
        assert len(out) == 4, "2 seeds x k_keep 2, all plans distinct"

    def test_the_context_is_copied_per_seed_and_never_mutated(self, monkeypatch):
        pre_calc = {"num_layers": 5}

        def faux(ctx, params, num_runs=None, expand_variants=None):
            ctx["pollution"] = True          # a worker mutating its own copy must not leak
            return {"all_strategies_results": [_res(_plan(600.0), 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        _screen_with_seeds(
            [_plan(600.0)], pre_calc, {"robustness_seed": 42, "screen_seed_list": "1,2"},
            50, 5, LOGGER, "T",
        )
        assert pre_calc == {"num_layers": 5}


class TestPiege2ParamsNotADict:
    """CLAUDE.md piege 2: on some paths `params` is a DTO, not a dict.

    `params["k"] = v` and `params.get("k")` must both work; `setdefault` would raise.
    """

    def test_a_mapping_like_object_works(self, monkeypatch):
        class FauxDTO:
            def __init__(self, d):
                self._d = dict(d)

            def get(self, k, default=None):
                return self._d.get(k, default)

            def __setitem__(self, k, v):
                self._d[k] = v

            def __getitem__(self, k):
                return self._d[k]

        vues = []

        def faux(ctx, params, num_runs=None, expand_variants=None):
            vues.append(params.get("robustness_seed"))
            return {"all_strategies_results": [_res(_plan(600.0 + len(vues)), 0.1)]}

        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", faux
        )
        dto = FauxDTO({"robustness_seed": 42, "screen_seed_list": "42,77"})
        out = _screen_with_seeds([_plan(600.0)], {}, dto, 50, 5, LOGGER, "T")
        assert vues == [42, 77]
        assert dto.get("robustness_seed") == 42
        assert len(out) == 2


class TestTheScoringSeedInsideTheGenerationSeeds:
    """THE WINNER'S CURSE CHANNEL MUST NOT PASS IN SILENCE.

    Generating on K seeds and then SCORING on one of those same K means the plans that reach
    the full pass were partly selected on the realisation that grades them. The cost of that
    channel is MEASURED and it is not a constant -- +12.9 % (2026-08-15), +0.55 % (2026-08-22),
    -0.03 % (2026-08-23). A run may legitimately pay it, deliberately; what it may not do is
    pay it without saying so. The night run of 2026-08-21 generated on 42;77;101;202;303 and
    scored on 42, and the overlap was found months later by rereading a command line.

    These tests pin the three properties that make the guard trustworthy: it fires when it
    must, it stays QUIET when it must not (a guard that cries wolf gets ignored), and it
    changes NOTHING to what the function returns.
    """

    @staticmethod
    def _faux(vues):
        def faux(ctx, params, num_runs=None, expand_variants=None):
            vues.append(params.get("robustness_seed"))
            return {"all_strategies_results": [_res(_plan(600.0 + len(vues)), 0.1)]}
        return faux

    def test_it_says_so_when_the_scoring_seed_generates_too(self, monkeypatch, caplog):
        vues = []
        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", self._faux(vues)
        )
        params = {"robustness_seed": 42, "screen_seed_list": "42,77,101"}
        with caplog.at_level(logging.ERROR, logger=LOGGER.name):
            _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")

        fautifs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(fautifs) == 1, "exactly one alert, never a stream"
        message = fautifs[0].getMessage()
        # BOTH numbers must be in the line: a reader who greps the journal must not have to
        # go and fetch the other half of the fact somewhere else.
        assert "42" in message and "77" in message
        assert "malediction" in message.lower()

    def test_it_stays_quiet_when_the_seeds_are_disjoint(self, monkeypatch, caplog):
        """A guard that fires on the CORRECT case is a guard that gets ignored."""
        vues = []
        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", self._faux(vues)
        )
        params = {"robustness_seed": 42, "screen_seed_list": "77,101,202"}
        with caplog.at_level(logging.ERROR, logger=LOGGER.name):
            _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")

        assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []

    def test_it_changes_nothing_to_the_result(self, monkeypatch):
        """The guard is an INSTRUMENT. It observes; it must not touch the union."""
        sorties = []
        for liste in ("42,77", "77,42"):
            vues = []
            monkeypatch.setattr(
                "certus.workers.certus_strat_workers.run_final_simulation_block",
                self._faux(vues),
            )
            params = {"robustness_seed": 42, "screen_seed_list": liste}
            out = _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")
            sorties.append(([r["robustness_score"] for r in out], vues))
            assert params["robustness_seed"] == 42, "the run's seed comes back untouched"

        # Same plans, same scores, whatever the order -- the alert has no side effect.
        assert sorties[0][0] == sorties[1][0]

    @pytest.mark.parametrize("graine", [None, "quarante-deux", float("nan")])
    def test_an_unusable_scoring_seed_never_raises(self, monkeypatch, graine):
        """A guard that crashes the run it protects is worse than no guard at all."""
        vues = []
        monkeypatch.setattr(
            "certus.workers.certus_strat_workers.run_final_simulation_block", self._faux(vues)
        )
        params = {"robustness_seed": graine, "screen_seed_list": "42,77"}
        out = _screen_with_seeds([_plan(600.0)], {}, params, 50, 5, LOGGER, "T")
        assert len(out) == 2
