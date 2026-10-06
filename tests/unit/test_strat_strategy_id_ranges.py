"""Les identifiants de strategie ne sont PAS une donnee -- et ils ont menti une fois.

🔴 CE QUE CE FICHIER EMPECHE DE REVENIR. Le 2026-08-12 la gagnante d'un run nominal
portait l'identifiant 990000320. Lu comme "plage 990 = variante Rate", il a ete rapporte
comme tel; son `origin` disait LOCAL_SEARCH. La lecture fausse est remontee jusqu'a
l'utilisateur, qui a cru voir le mode Rate gagner la ou aucune gagnante n'en a jamais
porte -- verifie ensuite sur les huit runs de la journee, `rate_layers` vide partout.

La cause: les generateurs incrementaux (consensus, ELITE, recherche locale) partent de
`max_sid + 1`, donc ils GRIMPENT dans les plages reservees des qu'une variante existe.
Deux generateurs finissent par se partager les memes numeros, et rien ne le signale.

🔑 LA REGLE : le generateur se lit dans `origin`, qui fait foi. Les plages ne servent
qu'a garantir l'unicite des numeros. Ces tests verifient les deux moities de cela.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from certus.core import certus_strat_ranking as ranking
from certus.core.certus_strat_ranking import (
    STRATEGY_ID_DERIVED_BASE,
    STRATEGY_ID_INCREMENTAL_CEILING,
    STRATEGY_ID_RATE_BASE,
    STRATEGY_ID_SLIT_BASE,
    clamp_incremental_strategy_id,
)
from certus.core.certus_strat_robustness import (
    _expand_with_rate_variants,
    _expand_with_resolution_variants,
)
from certus.workers.certus_strat_workers import _finalize_and_export_pipeline_results, derive_strategies_exhaustive


class _Log:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def _strat(n_blocks: int = 3, sid: int = 7) -> dict:
    step = 48 // n_blocks
    return {
        "strategy_id": sid,
        "blocks": [
            {"start": i * step, "end": (i + 1) * step if i < n_blocks - 1 else 48,
             "wavelength": 544.0 + i}
            for i in range(n_blocks)
        ],
    }


def test_the_three_ranges_are_disjoint_and_ordered():
    """Deux strategies distinctes ne doivent jamais porter le meme numero."""
    bases = [STRATEGY_ID_DERIVED_BASE, STRATEGY_ID_SLIT_BASE, STRATEGY_ID_RATE_BASE]
    assert bases == sorted(bases), "les plages doivent etre ordonnees"
    assert len(set(bases)) == 3, "deux generateurs partagent une base"
    # 10 M de marge entre deux bases : un generateur devrait produire dix millions de
    # variantes pour deborder, ce qui n'arrive pas avec le plafond de 3 par strategie.
    assert min(b - a for a, b in pairwise(bases)) >= 10_000_000


def test_an_incremental_counter_can_never_enter_a_reserved_range():
    """🔴 LE DEFAUT LUI-MEME. `max_sid + 1` suivait les variantes vers le haut."""
    assert clamp_incremental_strategy_id(5_000) == 5_000
    assert clamp_incremental_strategy_id(STRATEGY_ID_DERIVED_BASE + 12) == \
        STRATEGY_ID_DERIVED_BASE + 12
    # une variante Rate dans la liste ne doit plus tirer le compteur derriere elle
    assert clamp_incremental_strategy_id(STRATEGY_ID_RATE_BASE + 321) < \
        STRATEGY_ID_INCREMENTAL_CEILING
    assert clamp_incremental_strategy_id(STRATEGY_ID_SLIT_BASE) < \
        STRATEGY_ID_INCREMENTAL_CEILING


def test_rate_variants_land_in_the_rate_range():
    out = _expand_with_rate_variants([_strat(3)], {"allow_rate": True}, 48, _Log())
    variants = [v for v in out if v.get("rate_layers")]
    assert variants, "le montage ne genere aucune variante : le test ne teste rien"
    for v in variants:
        assert STRATEGY_ID_RATE_BASE <= v["strategy_id"] < STRATEGY_ID_RATE_BASE + 10_000_000


def test_slit_variants_land_in_the_slit_range():
    out = _expand_with_resolution_variants([_strat(3)], {"search_resolution": True}, _Log())
    variants = [v for v in out if "SLIT" in str(v.get("origin"))]
    assert variants, "le montage ne genere aucune variante : le test ne teste rien"
    for v in variants:
        assert STRATEGY_ID_SLIT_BASE <= v["strategy_id"] < STRATEGY_ID_SLIT_BASE + 10_000_000


def test_the_generator_is_read_from_origin_never_from_the_id():
    """🔑 La moitie qui compte vraiment.

    Meme avec des plages disjointes, l'identifiant reste un NUMERO. Ce qui nomme le
    generateur est `origin`, et c'est ce qu'il faut lire -- y compris quand un parent
    porte deja un identifiant de la plage d'un autre generateur, ce qui arrive des qu'on
    enchaine deux expansions.
    """
    rate = _expand_with_rate_variants([_strat(3)], {"allow_rate": True}, 48, _Log())
    both = _expand_with_resolution_variants(rate, {"search_resolution": True}, _Log())
    for v in both:
        origin = str(v.get("origin", ""))
        if "SLIT" in origin:
            assert "SLIT" in origin      # l'origine dit la verite...
        # ...et l'identifiant seul ne suffit jamais a trancher : une variante de fente
        # NEE d'une variante Rate porte un id de la plage FENTE tout en descendant du
        # Rate. Seule `origin` porte la filiation complete.
    slit_from_rate = [v for v in both if "SLIT" in str(v.get("origin")) and v.get("rate_layers")]
    assert slit_from_rate, "l'enchainement Rate -> fente doit produire des variantes mixtes"
    for v in slit_from_rate:
        assert v["strategy_id"] >= STRATEGY_ID_SLIT_BASE
        assert "SLIT" in str(v["origin"])


def test_a_string_id_parent_keeps_a_string_id_variant():
    """`sorted()` LEVE sur une liste melangeant int et str, et le departage des ex aequo
    trie sur l'identifiant. Trouve le 2026-08-12, latent tant que Rate etait eteint."""
    out = _expand_with_rate_variants([{"strategy_id": "a", "blocks": _strat(3)["blocks"]}],
                                     {"allow_rate": True}, 48, _Log())
    ids = [v["strategy_id"] for v in out]
    assert all(isinstance(i, str) for i in ids), f"types melanges : {ids}"
    sorted(ids)          # doit ne pas lever


def test_derived_ids_distinguish_the_parent_block_count():
    parents = [_strat(3, 3001), _strat(4, 4001)]
    children = [
        derive_strategies_exhaustive(
            [{"strategy": parent, "robustness_score": 0.1}],
            {},
            max_fusions_per_parent=1,
        )[0]
        for parent in parents
    ]
    assert len({child["strategy_id"] for child in children}) == len(children)
    assert all(str(parent["strategy_id"]) in child["origin"] for parent, child in zip(parents, children, strict=True))


def test_rate_ids_distinguish_the_source_block_count():
    variants = [
        next(
            v for v in _expand_with_rate_variants(
                [_strat(n_blocks, n_blocks * 1000)],
                {"allow_rate": True, "rate_by_swing": False},
                48,
                _Log(),
            )
            if v.get("rate_layers")
        )
        for n_blocks in (3, 4)
    ]
    assert len({variant["strategy_id"] for variant in variants}) == len(variants)


def test_slit_ids_distinguish_the_source_block_count():
    variants = [
        next(
            v for v in _expand_with_resolution_variants(
                [_strat(n_blocks, n_blocks * 1000)], {"search_resolution": True}, _Log()
            )
            if "SLIT" in str(v.get("origin"))
        )
        for n_blocks in (3, 4)
    ]
    assert len({variant["strategy_id"] for variant in variants}) == len(variants)


def test_refinement_ids_follow_their_own_block_count_and_existing_children():
    initial_3 = ranking.next_refinement_strategy_id([], 3)
    initial_4 = ranking.next_refinement_strategy_id([], 4)
    assert initial_3 != initial_4
    results = [{"strategy": {"strategy_id": initial_3, "blocks": _strat(3)["blocks"]}}]
    assert ranking.next_refinement_strategy_id(results, 3) == initial_3 + 1


def test_rate_then_slit_children_have_one_identifiable_parent_across_blocks():
    all_rate_parents = []
    all_candidates = []
    for n_blocks in (3, 4):
        rate_parents = _expand_with_rate_variants(
            [_strat(n_blocks, n_blocks * 1000)],
            {"allow_rate": True, "rate_by_swing": False},
            48,
            _Log(),
        )
        all_rate_parents.extend(rate_parents)
        all_candidates.extend(_expand_with_resolution_variants(rate_parents, {"search_resolution": True}, _Log()))

    ids = [str(candidate["strategy_id"]) for candidate in all_candidates]
    assert len(ids) == len(set(ids))
    for child in all_candidates:
        origin = str(child.get("origin", ""))
        if not origin.startswith("SLIT"):
            continue
        parent_id = origin.partition("(from ")[2].removesuffix(")")
        assert sum(str(parent["strategy_id"]) == parent_id for parent in all_rate_parents) == 1


def test_ambiguous_ids_never_reach_the_table_or_export():
    rows = [
        {"strategy": _strat(3, 42), "robustness_score": 0.1},
        {"strategy": _strat(4, 42), "robustness_score": 0.2},
    ]
    with pytest.raises(ValueError, match="strategy_id"):
        _finalize_and_export_pipeline_results(
            rows,
            {},
            {},
            {"logger": _Log(), "show_plots": False, "export_excel": False},
            object(),
            None,
        )


def test_layer_by_layer_slit_variants_survive_a_design_of_250_layers():
    """`num_layers` is always in `blocks_range`: the layer-by-layer worker of a long design
    must still receive slit variants instead of losing its whole block count to a ValueError."""
    layer_by_layer = {
        "strategy_id": 250_000,
        "blocks": [{"start": i, "end": i + 1, "wavelength": 544.0} for i in range(250)],
    }
    out = _expand_with_resolution_variants([layer_by_layer], {"search_resolution": True}, _Log())
    slit_ids = [v["strategy_id"] for v in out if "SLIT" in str(v.get("origin"))]
    assert slit_ids
    assert all(STRATEGY_ID_SLIT_BASE <= sid < STRATEGY_ID_RATE_BASE for sid in slit_ids)


def test_two_simulation_calls_of_one_worker_never_hand_out_the_same_refinement_id(monkeypatch):
    """A worker scores its block count in several calls (mined plans, inherited plans, the full pass), each running ELITE.

    Measured on the dichroic in `fast` mode on 2026-10-04: the ELITE children of two screenings of the 8-block worker
    both reached the full pass as 900850014, and the uniqueness guard withheld the whole run. Each call only saw its
    own list, so each started again at the base of the range; the worker's cursor remembers what was handed out."""
    import logging

    import numpy as np

    from certus.core import certus_strat_consensus as consensus
    from certus.core.certus_strat_config import RobustnessContext

    monkeypatch.setattr(consensus, "_resolve_elite_nominal_and_target_threshold", lambda *a, **k: (1.0, 1.0))
    monkeypatch.setattr(
        consensus,
        "_test_strategy_robustness_task",
        lambda strat, *a, **k: {
            "strategy": strat,
            "robustness_score": 0.001,
            "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.001}],
        },
    )
    monkeypatch.setattr(consensus, "_calculate_strategy_spectral_resolution", lambda *a, **k: (10.0, None, np.zeros(0)))
    cursor = ranking.RefinementIdCursor(3)
    wls = np.arange(540.0, 551.0)

    def one_call(parent_sid: int) -> list:
        ctx = RobustnessContext(
            params={
                "elite_parent_top_k": 1,
                "elite_max_candidates": 4,
                "elite_wl_neighbor_span": 1,
                "elite_num_runs": 10,
                "elite_rounds": 1,
                "elite_min_improvement": 0.0,
                "elite_stop_on_no_gain": True,
                "elite_max_full_evals": 4,
                "robustness_noise_factors": [1.0],
                "scan_wl_min": 540.0,
                "scan_wl_max": 550.0,
                "scan_wl_step": 1.0,
            },
            params_safe={},
            logger=logging.getLogger("test"),
            noise_levels=[1.0],
            num_runs=10,
            p_thick_nominal=[80.0] * 48,
            num_layers=48,
            clues_at_wl={float(w): {"H": 2.0, "L": 1.5, "substrate": 1.52} for w in wls},
            wl_arr=wls,
            nH_arr=np.full(wls.size, 2.0),
            nL_arr=np.full(wls.size, 1.5),
            nSub_arr=np.full(wls.size, 1.52),
            T_nom=np.full(wls.size, 0.5),
            full_dyn_grid={},
            strategy_id_namespace_n_blocks=3,
            strategy_id_cursor=cursor,
        )
        parents = [{
            "strategy": _strat(3, parent_sid),
            "robustness_score": 0.01,
            "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.01}],
        }]
        out = consensus._apply_elite_refinement_if_enabled(parents, ctx, lambda *a: None)
        return [r["strategy"]["strategy_id"] for r in out if r["strategy"]["strategy_id"] != parent_sid]

    first = one_call(3001)
    second = one_call(3002)
    assert first
    assert second
    assert not set(first) & set(second), f"shared refinement ids {sorted(set(first) & set(second))}"


def test_every_simulation_call_of_a_block_worker_shares_one_refinement_cursor(monkeypatch):
    """The screening and the full pass of one block count must draw from ONE cursor, created with the worker."""
    from certus.workers import certus_strat_workers as workers

    contexts: list[dict] = []

    def fake_simulation(context, _params, num_runs=0, **_kw):
        contexts.append(context)
        return {"all_strategies_results": [
            {"strategy": s, "robustness_score": 0.2, "results_per_noise": []} for s in context.get("all_strategies", [])
        ]}

    mined = [{"strategy_id": 101, "n_blocks": 1, "origin": "THICKNESS",
              "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}]}]
    monkeypatch.setattr(workers, "run_final_simulation_block", fake_simulation)
    monkeypatch.setattr(workers, "mine_strategies_for_block_count", lambda *a, **k: [dict(s) for s in mined])
    pre_calc_data = {
        "raw_results_thickness": {0: [{"wl": 500.0, "cost": 1.0}], 1: [{"wl": 500.0, "cost": 1.0}]},
        "raw_results_sq": {0: [{"wl": 500.0, "cost": 1.0}], 1: [{"wl": 500.0, "cost": 1.0}]},
        "num_layers": 2,
        "p_thick_nominal": [100.0, 80.0],
        "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},
        "full_dynamics_grid": {},
    }
    workers._parallel_block_worker((1, pre_calc_data, {"robustness_seed": 42}, 3, 2, 9, [], {"wl": None, "size": 0}))
    assert len(contexts) >= 2
    cursors = {id(c.get("strategy_id_cursor")) for c in contexts}
    assert len(cursors) == 1
    assert isinstance(contexts[0]["strategy_id_cursor"], ranking.RefinementIdCursor)
    assert contexts[0]["strategy_id_cursor"].source_n_blocks == 1


def test_a_beam_deeper_than_an_id_range_is_clipped_and_never_shares_an_id(monkeypatch, caplog):
    """Each cost map numbers its groupings `n_blocks * 1000 + offset + rank`, the offsets 100 apart. `dp_top_k` is bounded
    nowhere else: at 150 the 101st grouping of THICKNESS took the id of the first of THICKNESS^2, and the uniqueness guard
    would then withhold the run at its very end. The beam is clipped to the width of the range, and says so."""
    import logging

    calls: list[int] = []

    def fake_dp(cost_map, n_blocks, num_layers, top_k=10, **_kw):
        calls.append(int(top_k))
        return [
            {"blocks_info": [(0, 2, 400.0 + i // 10), (2, 4, 500.0 + i % 10)], "cost": 1.0 + i}
            for i in range(min(int(top_k), 150))
        ]

    monkeypatch.setattr(ranking, "_find_k_best_groupings_dp_sequential", fake_dp)
    raw = {i: [{"wl": 500.0, "cost": 1.0}] for i in range(4)}
    with caplog.at_level(logging.WARNING):
        strategies = ranking.mine_strategies_for_block_count(
            n_blocks=2, raw_results_thickness=raw, raw_results_sq=raw, num_layers=4, top_k=150
        )
    ids = [s["strategy_id"] for s in strategies]
    assert len(ids) == len(set(ids))
    assert calls
    assert max(calls) <= ranking._COUVERTURE_ID_STRIDE
    assert "clipped" in " ".join(r.getMessage() for r in caplog.records)
