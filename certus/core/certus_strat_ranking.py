"""
CERTUS STRAT RANKING
====================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- _find_k_best_groupings_dp_sequential (sequential Dynamic Programming solver)
- mine_strategies_for_block_count (mining orchestration)
- _convert_solution_to_strategy
- _apply_strategy_ranking (basic strategy ranking)
"""

import concurrent.futures
import logging
import math
from collections.abc import Callable
from typing import Any

import numpy as np

from certus.core.certus_strat_config import (
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    SYM_DEFAULT_WEIGHT,
)
from certus.core.certus_strat_utils import DP_DEFAULT_MIN_WL_SEPARATION_NM
from certus.utils.certus_strat_context import (
    _apply_block_diversity,
    _apply_family_diversity,
    _apply_wl_diversity,
    _augment_solution_cost_with_sym,
    _blocks_signature,
    _extract_rmse_p95_for_noise,
    _origin_family,
    _origin_priority_from_map,
    _strategy_id_sort_token,
    _validate_strategy_blocks_contract,
    _wl_set,
)
from certus.utils.certus_strat_service import select_best_strat_result
from certus_physics import _compute_valid_blocks_kernel, _dp_kernel

#: Offset of the identifier range of the COVERAGE groupings, per origin.
#: The plan is `n_blocks * 1000 + offset + rank`, offsets 0/100/200 for the cost maps and
#: 800 for the structured seeds: 300/400/500 are therefore free.
_COUVERTURE_ID_OFFSET = 300
#: Width of that range -- hence the hard cap of the coverage budget, per origin.
_COUVERTURE_ID_STRIDE = 100


def _solution_wls(sol: dict) -> set:
    """The control wavelengths a DP solution uses. `blocks_info` is `[(start, end, wl), ...]`."""
    return {float(wl) for _s, _e, wl in (sol.get("blocks_info") or [])}


def _couverture_wl_groupings(
    cost_map: dict[int, dict[float, float]],
    solutions: list[dict],
    appel_dp: Callable[..., Any],
    budget: int,
    logger: logging.Logger,
    stats: dict | None = None,
) -> list[dict]:
    """Groupings that USE the admissible wavelengths the k-best never selected.

    🔑 WHY THIS PASS EXISTS, AND IT WAS BORN FROM A MEASUREMENT, NOT AN INTUITION.

    📏 On 2026-08-21, on `r75x2` at 2 nm, seed 42: Phase A declares a MEDIAN of 86
    admissible wavelengths per layer. The search produces **14 to 29** per block count,
    and **65 out of the 301 of the grid** over all of its 1617 strategies. It spends
    104 to 160 strategies per block count, i.e. **five to seven duplicates per λ**.

        The spreading budget is already spent -- on redundancy.

    🔴 And the price of that redundancy is measured: the family of the 72 depositable
    strategies requires 685 nm on the block of layers 33-52, and that λ appears in **ZERO**
    of the 1617 strategies. SIX levers were tried without effect -- ELITE cap at 480, span
    ±2 nm, crash gate with a confidence bound, five seeds at screening, widened profile
    x3-x4, λ diversity of the parent pool. None could work: they widen the search AROUND
    WHAT ALREADY EXISTS, and the required λ exists nowhere.

    🟢 WHAT MAKES THIS PASS POSSIBLE WITHOUT TOUCHING THE DP. `_find_k_best_groupings_dp_sequential`
    takes a `cost_map` -- `{layer: {λ: cost}}`. Restricting ONE layer to a single λ is
    therefore enough to force the block that contains it to use it, and the DP then returns
    the BEST COHERENT grouping under that constraint. That is the difference with a
    mutation: ELITE substitutes a λ in an otherwise unchanged plan, which breaks its
    coherence; here the rest of the plan is RE-OPTIMISED around the constraint.

    ⚠️ THE FORCED LAYER IS THE ONE WHERE THE λ IS CHEAPEST, and that is not a setting:
    it is where Phase A judges it most natural. No threshold, no invented parameter (§19).

    ⚠️ And the processing order is INCREASING COST of the λ, so that the budget, if it
    bites, bites on the least promising ones -- never on the best.

    🔴 A FAILURE IS SAID. Forcing a layer can make the problem infeasible at the requested
    block count: the DP then returns nothing, and it is counted. A silent pruning reads as
    full coverage, and that is the failure mode this repository has been paying for since
    the beginning.

    🔴 AND THE COUNTERS GO UP THROUGH `stats`, NOT ONLY THROUGH THE LOG. 📏 Measured on
    2026-08-21: the `ThinFilm` logger this module then used is MUTE -- its unconditional
    `info` line "Mining: n_blocks=..." appears **zero times** in the campaign logs, while the
    worker's `W{n_blk}` logger gets through without trouble. A first fifty-minute run was
    therefore made UNINTERPRETABLE: impossible to tell "the pass did not run" from
    "every forced λ was infeasible". (Since D3 the miner logs through the logger its caller
    carries; `ThinFilm` is only its fallback.)

        An instrument whose output does not reach the result is not an instrument.

    It is exactly the pattern of §24-37 -- *"the fallback IS logged per layer, but nothing
    goes up to the ranking"*. The log stays, for convenience; `stats` is what counts.
    """
    if budget <= 0:
        return []

    deja = set()
    for sol in solutions:
        deja |= _solution_wls(sol)

    # All the admissible wavelengths, with their best cost and the layer where it is reached.
    meilleur: dict[float, tuple[float, int]] = {}
    for couche, dico in (cost_map or {}).items():
        for w, c in (dico or {}).items():
            w = float(w)
            if w not in meilleur or float(c) < meilleur[w][0]:
                meilleur[w] = (float(c), int(couche))

    absentes = sorted((w for w in meilleur if w not in deja), key=lambda w: meilleur[w][0])
    if not absentes:
        # 🔴 This case is recorded TOO. Without a counter, "no missing λ" and "the pass did
        # not run" read exactly the same in an artefact -- and that is the confusion that
        # cost a fifty-minute run on 2026-08-21.
        if stats is not None:
            stats["deja_employees"] = stats.get("deja_employees", 0) + len(deja)
            stats["absentes"] = stats.get("absentes", 0)
            stats["appels_dp"] = stats.get("appels_dp", 0)
        logger.info("   [WL-COUVERTURE] no admissible λ is missing from the groupings: nothing to do.")
        return []

    ajoutes: list[dict] = []
    infaisables = 0
    for w in absentes:
        # 🔴 THE BUDGET CAPS THE ATTEMPTS, NOT THE ADDITIONS. First version wrong, and
        # measured: it tested `len(ajoutes) >= budget`, so a case where EVERYTHING is
        # infeasible consumed no budget and still paid for every call.
        # 📏 On 2026-08-21, on a configuration where the DP returned no grouping:
        # "903 missing -> 0 added, 903 infeasible, 903 DP calls" -- for a budget
        # of 100, and about two minutes thrown away per block count.
        # The wavelengths being sorted by INCREASING cost, the first `budget` attempts are the
        # most promising: capping the work does not sacrifice the best ones.
        if len(ajoutes) + infaisables >= budget:
            break
        _cout, couche = meilleur[w]
        carte = dict(cost_map)
        carte[couche] = {w: _cout}
        sols = appel_dp(carte, 1)
        if sols:
            ajoutes.append(sols[0])
        else:
            infaisables += 1

    reste = len(absentes) - len(ajoutes) - infaisables
    if stats is not None:
        stats["deja_employees"] = stats.get("deja_employees", 0) + len(deja)
        stats["absentes"] = stats.get("absentes", 0) + len(absentes)
        stats["ajoutees"] = stats.get("ajoutees", 0) + len(ajoutes)
        stats["infaisables"] = stats.get("infaisables", 0) + infaisables
        stats["non_traitees"] = stats.get("non_traitees", 0) + max(0, reste)
        stats["appels_dp"] = stats.get("appels_dp", 0) + len(ajoutes) + infaisables
    logger.info(
        f"   [WL-COUVERTURE] {len(deja)} λ already used, {len(absentes)} missing -> "
        f"{len(ajoutes)} grouping(s) added, {infaisables} infeasible at the requested "
        f"block count" + (f", {reste} NOT PROCESSED for lack of budget ({budget})" if reste > 0 else "")
    )
    return ajoutes


def _convert_solution_to_strategy(sol: dict[str, Any], num_layers: int, n_blocks: int, origin_tag: str, s_id: Any) -> dict:
    blocks_info = sol.get("blocks_info", [])
    blocks_struct = []
    for start, end, wl in blocks_info:
        blocks_struct.append(
            {
                "start": start,
                "end": end,
                "wavelength": float(wl),
                "num_layers": end - start,
            }
        )

    base_total_cost = float(sol.get("base_cost", sol["cost"]))
    ranking_cost = float(sol["cost"])

    return {
        "strategy_id": s_id,
        "n_blocks": n_blocks,
        "avg_cost": float(ranking_cost / num_layers),
        "total_cost": ranking_cost,
        "blocks": blocks_struct,
        "origin": origin_tag,
        "avg_rmse_nominal": base_total_cost,
        "origin_details": origin_tag,
        "symmetry_bonus": float(sol.get("symmetry_bonus", 0.0)),
        "same_wl_kept": int(sol.get("same_wl_kept", 0)),
    }


def _find_k_best_groupings_dp_sequential(
    cost_map: dict[int, dict[float, float]],
    n_blocks: int,
    num_layers: int,
    top_k: int = 100,
    timeout: float = 120.0,
    start_time: float | None = None,
    force_monolayer: bool = False,
    nucleation_wl: float | None = None,
    nucleation_size: int = 0,
    sym_bonus_map: dict[int, dict[float, float]] | None = None,
    layer_importance_map: dict[int, float] | None = None,
    sym_weight: float = 0.0,
    same_wl_bonus: float = 0.0,
    continuity_weight: float = SYM_DEFAULT_CONTINUITY_WEIGHT,
    adaptive_same_wl: bool = True,
    enable_sym_post_ranking: bool = False,
    min_wl_sep_nm: float = 0.0,
) -> list[dict[str, Any]]:
    max_W = max((len(v) for v in cost_map.values() if v), default=0)
    layer_wls = np.full((num_layers, max_W), -1.0, dtype=np.float64)
    layer_costs = np.full((num_layers, max_W), np.inf, dtype=np.float64)
    valid_mask = np.zeros((num_layers, max_W), dtype=np.bool_)

    for layer_idx, layer_dict in cost_map.items():
        if layer_idx >= num_layers or not layer_dict:
            continue
        wls = sorted(layer_dict.keys())
        for w_idx, w in enumerate(wls):
            layer_wls[layer_idx, w_idx] = float(w)
            layer_costs[layer_idx, w_idx] = float(layer_dict[w])
            valid_mask[layer_idx, w_idx] = True

    block_costs, block_wls, block_counts = _compute_valid_blocks_kernel(
        layer_wls, layer_costs, valid_mask, num_layers, top_k, max_W, float(min_wl_sep_nm)
    )

    if nucleation_wl and nucleation_size > 0 and num_layers >= nucleation_size:
        for j in range(1, num_layers + 1):
            if block_counts[0, j] > 0:
                filtered_c = 0
                for b in range(block_counts[0, j]):
                    if j <= nucleation_size:
                        if abs(block_wls[0, j, b] - nucleation_wl) <= 1.0:
                            block_costs[0, j, filtered_c] = block_costs[0, j, b]
                            block_wls[0, j, filtered_c] = block_wls[0, j, b]
                            filtered_c += 1
                    else:
                        if abs(block_wls[0, j, b] - nucleation_wl) <= 1.0:
                            block_costs[0, j, filtered_c] = block_costs[0, j, b]
                            block_wls[0, j, filtered_c] = block_wls[0, j, b]
                            filtered_c += 1
                block_counts[0, j] = filtered_c

    if force_monolayer and block_counts[0, 1] > 0:
        block_counts[0, 1] = 0
        smart_nucl_active = nucleation_wl is not None
        if num_layers >= 2 and not smart_nucl_active and block_counts[0, 2] == 0:
            l2_mask = valid_mask[1]
            l1_mask = valid_mask[0]
            l1_costs = layer_costs[0][l1_mask]
            dynamic_penalty = np.mean(l1_costs) * 2.0 if len(l1_costs) > 0 else 1.0
            l2_valid_idx = np.where(l2_mask)[0]
            if len(l2_valid_idx) > 0:
                l2_costs = layer_costs[1][l2_valid_idx]
                best_clues = np.argsort(l2_costs)[:10]
                cpt = 0
                for idx in best_clues:
                    wl = layer_wls[1, l2_valid_idx[idx]]
                    cost_l2 = l2_costs[idx]
                    block_costs[0, 2, cpt] = cost_l2 + dynamic_penalty
                    block_wls[0, 2, cpt] = wl
                    cpt += 1
                block_counts[0, 2] = cpt
                sort_idx = np.argsort(block_costs[0, 2, :cpt])
                block_costs[0, 2, :cpt] = block_costs[0, 2, :cpt][sort_idx]
                block_wls[0, 2, :cpt] = block_wls[0, 2, :cpt][sort_idx]

    dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts = _dp_kernel(
        block_costs, block_wls, block_counts, n_blocks, num_layers, top_k
    )

    final_count = dp_counts[n_blocks, num_layers]
    if final_count == 0:
        return []

    solutions: list[dict[str, Any]] = []
    for t in range(final_count):
        total_cost = dp_costs[n_blocks, num_layers, t]
        blocks_info = []
        for b in range(n_blocks):
            st = dp_paths_start[n_blocks, num_layers, t, b]
            en = dp_paths_end[n_blocks, num_layers, t, b]
            wl = dp_paths_wl[n_blocks, num_layers, t, b]
            if st != -1:
                blocks_info.append((int(st), int(en), float(wl)))

        assignments = {}
        for start, end, wl in blocks_info:
            for layer_index in range(start, end):
                assignments[layer_index] = wl

        solutions.append(
            {
                "cost": float(total_cost),
                "base_cost": float(total_cost),
                "assignments": assignments,
                "blocks_info": blocks_info,
            }
        )

    if enable_sym_post_ranking and (sym_bonus_map or same_wl_bonus > 0.0):
        for sol in solutions:
            aug_cost, sym_bonus_val, same_wl_kept = _augment_solution_cost_with_sym(
                sol,
                sym_bonus_map,
                layer_importance_map,
                sym_weight,
                same_wl_bonus,
                continuity_weight,
                adaptive_same_wl,
            )
            sol["cost"] = float(aug_cost)
            sol["symmetry_bonus"] = float(sym_bonus_val)
            sol["same_wl_kept"] = int(same_wl_kept)

    solutions.sort(key=lambda x: float(x["cost"]))
    return solutions


def mine_strategies_for_block_count(
    n_blocks: int,
    raw_results_thickness: dict[int, list[dict[str, float]]],
    raw_results_sq: dict[int, list[dict[str, float]]],
    num_layers: int,
    top_k: int = 10,
    force_monolayer: bool = False,
    nucleation_wl: float | None = None,
    nucleation_size: int = 0,
    candidate_limit: int = 3000,
    sym_enable: bool = True,
    sym_bonus_map: dict[int, dict[float, float]] | None = None,
    layer_importance_map: dict[int, float] | None = None,
    sym_weight: float = SYM_DEFAULT_WEIGHT,
    sym_same_wl_bonus: float = SYM_DEFAULT_SAME_WL_BONUS,
    sym_continuity_weight: float = SYM_DEFAULT_CONTINUITY_WEIGHT,
    sym_adaptive_same_wl: bool = True,
    sym_scoring_mode: str = SYM_DEFAULT_SCORING_MODE,
    sym_allow_hybrid: bool = False,
    min_wl_sep_nm: float = DP_DEFAULT_MIN_WL_SEPARATION_NM,
    # 🔑 λ COVERAGE -- inert by default, former path TO THE BIT.
    # `wl_coverage_top_k = 0` falls back on `top_k`: as many groupings for COVERAGE
    # as for OPTIMALITY. It is a symmetry, not an invented number (§19).
    enable_wl_coverage: bool = False,
    wl_coverage_top_k: int = 0,
    # 🔴 Filled in place: a log line is read by a person, the counters by the caller, which
    # must tell "nothing to cover" apart from "did not run" (see `_couverture_wl_groupings`).
    wl_coverage_stats: dict[str, Any] | None = None,
    # The logger the pipeline carries (`params["logger"]`; the worker's `W{n_blk}`). D3:
    # `ThinFilm`, the fallback, has no handler and neither has the root, so Python drops
    # every `info` it gets -- the "Mining: n_blocks=..." line never reached a campaign log.
    logger: logging.Logger | None = None,
) -> list[dict[str, Any]]:
    if n_blocks <= 0 or num_layers <= 0:
        return []
    log = logger if logger is not None else logging.getLogger("ThinFilm")

    strategies_collected = []
    strategy_id_base = n_blocks * 1000
    LIMIT_CANDIDATES = candidate_limit

    def apply_nucleation_constraint(cost_map_in: dict[Any, Any]) -> Any:
        if not nucleation_wl or nucleation_size <= 0:
            return cost_map_in
        n_wl = float(nucleation_wl)
        for i in range(nucleation_size):
            if cost_map_in.get(i):
                if n_wl in cost_map_in[i]:
                    val = cost_map_in[i][n_wl]
                else:
                    available_wls = list(cost_map_in[i].keys())
                    if available_wls:
                        closest_wl = min(available_wls, key=lambda x: abs(x - n_wl))
                        val = cost_map_in[i][closest_wl]
                    else:
                        val = 1.0
                cost_map_in[i] = {n_wl: val}
            else:
                cost_map_in[i] = {n_wl: 1.0}
        return cost_map_in

    cost_map_thick = {}

    def _prune_candidates(cands: list[dict[str, float]], limit: int) -> list[dict[str, float]]:
        if not cands:
            return []
        return sorted(cands, key=lambda x: x["cost"])[:limit]

    for i in range(num_layers):
        candidates = raw_results_thickness.get(i, [])
        if not candidates:
            continue
        candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)
        cost_map_thick[i] = {c["wl"]: c["cost"] for c in candidates_sorted}

    cost_map_sq = {}
    for i in range(num_layers):
        candidates = raw_results_sq.get(i, [])
        if not candidates:
            continue
        candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)
        cost_map_sq[i] = {c["wl"]: c["cost"] for c in candidates_sorted}

    if nucleation_wl:
        cost_map_thick = apply_nucleation_constraint(cost_map_thick)
        cost_map_sq = apply_nucleation_constraint(cost_map_sq)

    scoring_mode = str(sym_scoring_mode or SYM_DEFAULT_SCORING_MODE).strip().lower()
    if scoring_mode not in {"pre", "post", "hybrid"}:
        scoring_mode = SYM_DEFAULT_SCORING_MODE
    if scoring_mode == "hybrid" and not bool(sym_allow_hybrid):
        scoring_mode = "post"

    pre_sym_enabled = scoring_mode in {"pre", "hybrid"}
    post_sym_enabled = scoring_mode in {"post", "hybrid"}

    cost_map_sym = {}
    if sym_enable:
        for i in range(num_layers):
            candidates = raw_results_thickness.get(i, [])
            if not candidates:
                continue
            candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)
            layer_map: dict[float, float] = {}
            for c in candidates_sorted:
                wl = float(c["wl"])
                base_cost = float(c["cost"])
                sym_gain = 0.0
                if sym_bonus_map is not None:
                    sym_gain = float(sym_bonus_map.get(i, {}).get(wl, 0.0))
                if pre_sym_enabled:
                    layer_map[wl] = max(0.0, base_cost - float(sym_weight) * sym_gain)
                else:
                    layer_map[wl] = base_cost
            if layer_map:
                cost_map_sym[i] = layer_map

        if nucleation_wl:
            cost_map_sym = apply_nucleation_constraint(cost_map_sym)

    log.info(
        f"Mining: n_blocks={n_blocks}, CostMapThick Size={len(cost_map_thick)}, CostMapSq Size={len(cost_map_sq)}"
    )

    def run_mining(cost_map: dict[Any, Any], origin_name: str, offset_id: int, apply_sym_post: bool = False) -> Any:
        logger = log
        logger.debug(f"[DEBUG MINING] {origin_name}: Starting DP with {len(cost_map)} layers, n_blocks={n_blocks}")
        
        for layer_idx in list(cost_map.keys())[:3]:
            wls_sample = list(cost_map[layer_idx].keys())[:5]
            logger.debug(
                f"[DEBUG MINING] Layer {layer_idx}: {len(cost_map[layer_idx])} wavelengths, sample: {wls_sample}"
            )

        # 🔒 The DP settings are gathered HERE and nowhere else: the coverage pass
        # calls it again under constraint, and two lists of fourteen arguments that must
        # stay identical would be a scheduled divergence.
        _dp_reglages: dict[str, Any] = dict(
            timeout=30.0,
            force_monolayer=force_monolayer,
            nucleation_wl=nucleation_wl,
            nucleation_size=nucleation_size,
            sym_bonus_map=sym_bonus_map if (apply_sym_post and post_sym_enabled) else None,
            layer_importance_map=layer_importance_map if (apply_sym_post and post_sym_enabled) else None,
            sym_weight=float(sym_weight) if (apply_sym_post and post_sym_enabled) else 0.0,
            same_wl_bonus=float(sym_same_wl_bonus) if (apply_sym_post and post_sym_enabled) else 0.0,
            continuity_weight=float(sym_continuity_weight) if apply_sym_post else SYM_DEFAULT_CONTINUITY_WEIGHT,
            adaptive_same_wl=bool(sym_adaptive_same_wl) if apply_sym_post else False,
            enable_sym_post_ranking=bool(apply_sym_post and post_sym_enabled),
            min_wl_sep_nm=float(min_wl_sep_nm),
        )

        def _appel_dp(carte: dict[Any, Any], k: int) -> Any:
            return _find_k_best_groupings_dp_sequential(
                carte, n_blocks, num_layers, top_k=k, **_dp_reglages
            )

        solutions = _appel_dp(cost_map, top_k)
        logger.debug(f"[DEBUG MINING] {origin_name}: DP returned {len(solutions)} solutions")

        # 🔑 λ COVERAGE -- inert by default, former path TO THE BIT.
        # See `_couverture_wl_groupings` for the measurement that motivates it: Phase A admits
        # a median of 86 λ per layer, the search uses 14 to 29, and the λ the 72 depositable
        # ones need appears in ZERO strategies.
        # 🔴 THE COVERAGE GROUPINGS HAVE THEIR OWN IDENTIFIER RANGE, and it is not
        # cosmetic. The plan is `strategy_id_base + offset_id + rank` with
        # `strategy_id_base = n_blocks * 1000`, and the offsets in use are 0 / 100 / 200 for
        # the three cost maps, 800 for the structured seeds. In DEEP mode `top_k` is
        # **exactly 100**: the plan is SATURATED. Extending `solutions` in place would therefore
        # have given the 101st grouping the identifier of the 1st of the next map -- two
        # different strategies under one id, and everything that indexes by id (the premium
        # cache, the reports, `from 9000000...`) would have gone silent.
        # Offsets 300 / 400 / 500 are free, and 800 bounds the range.
        couverture: list = []
        if enable_wl_coverage:
            _plafond = _COUVERTURE_ID_STRIDE
            _budget = min(int(wl_coverage_top_k or top_k), _plafond)
            if int(wl_coverage_top_k or top_k) > _plafond:
                logger.warning(
                    f"   [WL-COUVERTURE] requested budget {int(wl_coverage_top_k or top_k)} "
                    f"clipped to {_plafond}: it is the width of the identifier range "
                    f"reserved per origin, not a search setting."
                )
            couverture = _couverture_wl_groupings(
                cost_map, solutions, _appel_dp, _budget, logger, wl_coverage_stats
            )

        found = []

        def _convertir(sols: list, base: int, etiquette: str) -> None:
            for rank, sol in enumerate(sols):
                s_id = strategy_id_base + base + rank
                strat = _convert_solution_to_strategy(sol, num_layers, n_blocks, etiquette, s_id)
                is_valid, reason = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=n_blocks)
                if not is_valid:
                    logger.debug(f"[DEBUG MINING] Dropped invalid strategy {s_id} ({etiquette}): {reason}")
                    continue
                strat["rank_in_group"] = rank + 1
                smart_tag = f" (Smart Nucl. L1-L{nucleation_size})" if nucleation_wl else ""
                strat["origin_details"] = f"{etiquette}{smart_tag} (Rank {rank + 1})"
                found.append(strat)

        if solutions:
            _convertir(solutions, offset_id, origin_name)
        if couverture:
            # The origin is DISTINCT: otherwise, reading a ranking, one could not tell
            # whether a winner comes from optimality or from coverage -- and that is precisely
            # the question this pass is meant to settle.
            _convertir(
                couverture,
                offset_id + _COUVERTURE_ID_OFFSET,
                f"{origin_name}-COUVERTURE",
            )
        return found

    max_workers = 3 if sym_enable else 2
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as miner_executor:
        f1 = miner_executor.submit(run_mining, cost_map_thick, "THICKNESS", 0, False)
        f2 = miner_executor.submit(run_mining, cost_map_sq, "THICKNESS²", 100, False)
        strategies_collected.extend(f1.result())
        strategies_collected.extend(f2.result())
        if sym_enable and cost_map_sym:
            f3 = miner_executor.submit(run_mining, cost_map_sym, "SYM", 200, True)
            strategies_collected.extend(f3.result())

    structured_seeds = _generate_structured_seed_strategies(
        n_blocks=n_blocks,
        num_layers=num_layers,
        raw_results_thickness=raw_results_thickness,
        strategy_id_base=strategy_id_base,
    )
    strategies_collected.extend(structured_seeds)

    return strategies_collected


def _generate_structured_seed_strategies(
    n_blocks: int,
    num_layers: int,
    raw_results_thickness: dict[int, list[dict[str, float]]],
    strategy_id_base: int = 9000,
) -> list[dict[str, Any]]:
    """Generate structured reference seed strategies (Action 5.4):
    - Mono-wavelength strategy (all blocks at maximum transmission lambda)
    - 1-block-per-layer strategy (when n_blocks == num_layers)
    - Regular partitions (equal-sized contiguous block partitions)
    """
    if n_blocks <= 0 or num_layers <= 0 or not raw_results_thickness:
        return []

    best_wl_global = 550.0
    min_c = float("inf")
    for cands in raw_results_thickness.values():
        for c in cands:
            cost = float(c.get("cost", float("inf")))
            if cost < min_c:
                min_c = cost
                best_wl_global = float(c.get("wl", 550.0))

    def _best_wl_for_block(start: int, end: int) -> float:
        best_wl = best_wl_global
        best_score = float("inf")
        first_layer_cands = raw_results_thickness.get(start, [])
        for cand in first_layer_cands:
            wl = float(cand.get("wl", 550.0))
            tot_cost = sum(
                next((c["cost"] for c in raw_results_thickness.get(lyr, []) if abs(c["wl"] - wl) < 1e-6), 1.0)
                for lyr in range(start, end)
            )
            if tot_cost < best_score:
                best_score = tot_cost
                best_wl = wl
        return best_wl

    seeds = []
    sid_counter = strategy_id_base + 800

    # 1. Mono-lambda strategy for n_blocks
    if n_blocks == 1 or n_blocks in {2, 3, 4, 6, 8, 12}:
        block_size = num_layers / float(n_blocks)
        mono_blocks = []
        for b_idx in range(n_blocks):
            b_start = round(b_idx * block_size)
            b_end = round((b_idx + 1) * block_size) if b_idx < n_blocks - 1 else num_layers
            if b_end > b_start:
                mono_blocks.append({"start": b_start, "end": b_end, "wavelength": best_wl_global})
        if mono_blocks:
            strat = {
                "strategy_id": sid_counter,
                "n_blocks": len(mono_blocks),
                "avg_cost": 0.0,
                "total_cost": 0.0,
                "blocks": mono_blocks,
                "origin": "STRUCTURED_MONO_WL",
                "origin_details": f"STRUCTURED_MONO_WL(wl={best_wl_global:g}nm, n_blocks={len(mono_blocks)})",
                "same_wl_kept": len(mono_blocks) - 1,
            }
            ok, _ = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=len(mono_blocks))
            if ok:
                seeds.append(strat)
                sid_counter += 1

    # 2. Regular equal partition strategy with per-block best Phase A wavelength
    block_size = num_layers / float(n_blocks)
    reg_blocks = []
    for b_idx in range(n_blocks):
        b_start = round(b_idx * block_size)
        b_end = round((b_idx + 1) * block_size) if b_idx < n_blocks - 1 else num_layers
        if b_end > b_start:
            wl = _best_wl_for_block(b_start, b_end)
            reg_blocks.append({"start": b_start, "end": b_end, "wavelength": wl})
    if reg_blocks:
        same_wl_kept = sum(
            1 for i in range(1, len(reg_blocks))
            if abs(reg_blocks[i]["wavelength"] - reg_blocks[i - 1]["wavelength"]) < 1e-6
        )
        strat = {
            "strategy_id": sid_counter,
            "n_blocks": len(reg_blocks),
            "avg_cost": 0.0,
            "total_cost": 0.0,
            "blocks": reg_blocks,
            "origin": "STRUCTURED_REGULAR_PARTITION",
            "origin_details": f"STRUCTURED_REGULAR_PARTITION(n_blocks={len(reg_blocks)})",
            "same_wl_kept": same_wl_kept,
        }
        ok, _ = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=len(reg_blocks))
        if ok:
            seeds.append(strat)
            sid_counter += 1

    # 3. 1-block-per-layer strategy (when n_blocks == num_layers)
    if n_blocks == num_layers:
        single_blocks = []
        for lyr in range(num_layers):
            cands = raw_results_thickness.get(lyr, [])
            wl = float(cands[0]["wl"]) if cands else best_wl_global
            single_blocks.append({"start": lyr, "end": lyr + 1, "wavelength": wl})
        strat = {
            "strategy_id": sid_counter,
            "n_blocks": num_layers,
            "avg_cost": 0.0,
            "total_cost": 0.0,
            "blocks": single_blocks,
            "origin": "STRUCTURED_1_PER_LAYER",
            "origin_details": f"STRUCTURED_1_PER_LAYER({num_layers} blocks)",
            "same_wl_kept": 0,
        }
        ok, _ = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=num_layers)
        if ok:
            seeds.append(strat)

    return seeds


#: Measurement limit on an equivalent per-layer error. 👤 "SEEL a 0.01 nm pres partout" (2026-08-14). Half-width, hence 0.005.
SEEL_RESOLUTION_NM = 0.005


def rank_key_seel_yield_margin(
    seel_nm: float,
    crash_rate: float,
    critical_margin_in_A: float,
) -> tuple[float, float, float]:
    """The 👤 ranking rule of 14, as a sort key. Lower is better on every component.

        1. SEEL, quantised to its equivalence class   ascending
        2. yield = 1 - crash rate                     descending
        3. margin of the critical layer               descending   <- 2026-08-11

    🔑 WHY QUANTISE AT ALL. `fit_alpha` is 1.0, so SEEL = k . RMSE with k constant:
    sorting on the CONTINUOUS SEEL reproduces exactly the RMSE order -- a sort that
    sorts nothing. 📏 And 17-26 measured that at N = 150 the top eight strategies lie
    within 2 sigma of one another and all read 0.3 nm. The continuous ranking is
    separating noise; the quantised one says "equal", which is true.

    🔑 WHY YIELD SECOND. 👤 decided 2026-08-10, and it is 8: "if 95 % of depositions
    work, it's a win", and a crashed run and an out-of-spec filter are the same
    failure. At indistinguishable spectral performance, take the one that finishes.

    🔑 WHY THE MARGIN THIRD, and why it was impossible before today. On this stack
    every tied strategy reads 0/150 crashes, so the yield cannot separate them either:
    0 out of 150 says p < 2 % and nothing more. The margin is continuous and defined
    at zero crashes -- it is the only one of the three that still discriminates inside
    the equivalence class.

    ⚠️ A margin beyond 2 A means the event CANNOT happen -- the draws are bounded -- so
    ordering by it there is meaningless. It is clamped, not because large margins are
    equal in nature but because nothing distinguishes "impossible" from "impossible".
    """
    # Bin index at strict 0.01 nm resolution (2 * SEEL_RESOLUTION_NM): two SEELs within
    # 0.01 nm land on the same key.
    binned = round(max(seel_nm, 0.0) / (2.0 * SEEL_RESOLUTION_NM))
    margin = min(max(critical_margin_in_A, 0.0), 2.0)
    return (float(binned), float(crash_rate), -margin)


def _apply_strategy_ranking(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    origin_priority_map: dict[str, int],
) -> list[dict[str, Any]]:
    """Rank and sort strategies based on robustness, resolution, and origin priority."""
    use_margin = bool(params.get("use_margin_ranking", False))

    def _advanced_key(item: dict[str, Any]) -> tuple:
        strategy = item.get("strategy", {})
        origin = str(strategy.get("origin", "UNKNOWN"))
        same_wl_kept = int(strategy.get("same_wl_kept", 0))
        try:
            n_blocks_val = int(strategy.get("n_blocks", len(strategy.get("blocks", []))))
        except (TypeError, ValueError):
            n_blocks_val = len(strategy.get("blocks", []))
        min_res = float(item.get("min_resolution", 999.0))

        if use_margin:
            score_val = float(item.get("robustness_score", np.inf))
            seel_nm = 2.0 * math.sqrt(score_val) if (math.isfinite(score_val) and score_val > 0) else np.inf
            crash_rate = float(item.get("crash_rate", 1.0))
            cl = item.get("critical_layer") or {}
            margin_val = float(cl.get("margin_in_A", item.get("critical_margin", 0.0)) or 0.0)
            primary_key: tuple[float, ...] = rank_key_seel_yield_margin(seel_nm, crash_rate, margin_val)
        else:
            primary_key = (float(item.get("robustness_score", np.inf)),)

        return (
            *primary_key,
            min_res,
            -same_wl_kept,
            n_blocks_val,
            _origin_priority_from_map(origin, origin_priority_map),
            _strategy_id_sort_token(strategy.get("strategy_id", "")),
        )

    strategies_results.sort(key=_advanced_key)

    sym_prefer_on_tie = bool(params.get("sym_prefer_on_tie", True))
    sym_tie_epsilon = max(float(params.get("sym_tie_epsilon", SYM_DEFAULT_TIE_EPS_ABS)), 1e-12)
    sym_tie_epsilon_rel = max(float(params.get("sym_tie_epsilon_rel", SYM_DEFAULT_TIE_EPS_REL)), 0.0)

    def _is_tie(s_a: float, s_b: float) -> bool:
        tol = sym_tie_epsilon + sym_tie_epsilon_rel * max(abs(s_a), abs(s_b))
        return abs(s_a - s_b) <= tol

    if sym_prefer_on_tie and len(strategies_results) > 1:
        reordered = []
        i = 0
        while i < len(strategies_results):
            base_score = float(strategies_results[i]["robustness_score"])
            j = i + 1
            while j < len(strategies_results):
                current_score = float(strategies_results[j]["robustness_score"])
                if _is_tie(base_score, current_score):
                    j += 1
                else:
                    break
            tie_group = strategies_results[i:j]
            tie_group.sort(
                key=lambda item: (
                    0 if "SYM" in str(item.get("strategy", {}).get("origin", "")).upper() else 1,
                    *_advanced_key(item),
                )
            )
            reordered.extend(tie_group)
            i = j
        return reordered

    return strategies_results


def _resolve_available_wavelengths(
    clues_at_wl: Any,
    wl_arr: np.ndarray,
) -> list[float]:
    """Resolve candidate wavelengths from clues map, with wl-array fallback."""
    available_wls: list[float] = []
    if hasattr(clues_at_wl, "keys"):
        for key in clues_at_wl.keys():
            try:
                available_wls.append(float(key))
            except (TypeError, ValueError):
                continue
    if not available_wls:
        return [float(w) for w in wl_arr.tolist()]
    return available_wls


def _resolve_monitoring_wavelength_grid(
    params: dict[str, Any],
    clues_at_wl: Any,
    wl_arr: np.ndarray,
) -> list[float]:
    """Admissible CONTROL wavelengths: the scanning grid, not the display one.

    🔴 A CONTROL WAVELENGTH IS CHOSEN AT THE ``scan_wl_step`` STEP.
    👤 The physicist, 2026-08-06: "the wavelengths must be able to be chosen in
    steps of 2 nm" — in wavelength, not in thickness.

    `_resolve_available_wavelengths` returns the KEYS of `clues_at_wl`. But this
    dictionary is built on the UNION of two unrelated grids
    (`_prepare_precompute_wavelength_grid`, certus_strat_config.py:287):

        SCANNING grid   scan_wl_min..scan_wl_max at scan_wl_step step  (2 nm)
        DISPLAY grid    wl_range[0]..wl_range[1] at wl_step step       (1 nm)

    The union is thus at 1 nm over the whole overlap, and the ELITE stage, which mutates
    "towards the neighboring wavelength", mutated by 1 nm — outside the control grid.
    📏 This is the measured origin of the top 5 `551, 552, 553, 554` observed on the benchmark:
    four variations of a single strategy, separated by a quantity that
    makes no physical sense, on which four fifths of the final Monte-Carlo
    budget was spent.

    Fallback to `_resolve_available_wavelengths` if the scanning bounds are missing:
    better to have a grid that is too fine than no candidate at all.
    """
    try:
        lo = float(params["scan_wl_min"])
        hi = float(params["scan_wl_max"])
        step = float(params["scan_wl_step"])
    except KeyError, TypeError, ValueError:
        return _resolve_available_wavelengths(clues_at_wl, wl_arr)
    if not (step > 0.0 and hi > lo):
        return _resolve_available_wavelengths(clues_at_wl, wl_arr)

    from certus_physics import arange_inclusive

    grid = [float(w) for w in arange_inclusive(lo, hi, step).tolist()]

    # Only keep what we really have the indices for: `clues_at_wl` may
    # have been built on a step widened by the cache limit
    # (certus_strat_config.py:272). A matching at 1e-6 is useless here — the
    # scanning grid IS an exact subset of `all_wls`.
    keys = None
    if hasattr(clues_at_wl, "keys"):
        keys = set()
        for k in clues_at_wl.keys():
            try:
                keys.add(round(float(k), 6))
            except (TypeError, ValueError):
                continue
    if keys:
        kept = [w for w in grid if round(w, 6) in keys]
        if kept:
            return kept
    return grid


def _max_strategy_id(strategies_results: list[dict[str, Any]]) -> int:
    """Return maximum integer strategy id found in result rows."""
    max_sid = 0
    for item in strategies_results:
        try:
            max_sid = max(max_sid, int(item.get("strategy", {}).get("strategy_id", 0)))
        except (TypeError, ValueError):
            continue
    return max_sid


def _existing_block_signatures(strategies_results: list[dict[str, Any]]) -> set[tuple]:
    """Build signature set for already present strategies."""
    return {_blocks_signature(item.get("strategy", {}).get("blocks", [])) for item in strategies_results}


def _resolve_elite_nominal_and_target_threshold(
    strategies_results: list[dict[str, Any]],
    *,
    nominal_noise_level: float,
    elite_min_improvement: float,
) -> tuple[float, float] | None:
    """Resolve (rank-10 nominal threshold, target threshold) for ELITE gate."""
    top10_idx = min(9, len(strategies_results) - 1)
    nominal_threshold = _extract_rmse_p95_for_noise(strategies_results[top10_idx], nominal_noise_level)
    if not np.isfinite(nominal_threshold):
        return None
    target_threshold = nominal_threshold - elite_min_improvement
    return float(nominal_threshold), float(target_threshold)


def _resolve_family_diversity_cfg(params: dict[str, Any]) -> tuple[bool, int, int]:
    """Resolve family-diversity feature flags and limits."""
    enable_family_diversity = bool(params.get("enable_family_diversity", True))
    diversity_top_k = int(params.get("diversity_top_k", 12))
    diversity_max_per_family = int(params.get("diversity_max_per_family", 4))
    return enable_family_diversity, diversity_top_k, diversity_max_per_family


def _top_origin_families(
    strategies_results: list[dict[str, Any]],
    diversity_top_k: int,
) -> list[str]:
    """Return origin-family labels for top-K strategies."""
    return [
        _origin_family(r.get("strategy", {}).get("origin", "UNKNOWN"))
        for r in strategies_results[: min(diversity_top_k, len(strategies_results))]
    ]


def _did_family_top_order_change(before_top: list[str], after_top: list[str]) -> bool:
    """Return True when family ordering changed after diversity pass."""
    return before_top != after_top


def _log_family_diversity_reordering(
    *,
    logger,
    diversity_top_k: int,
    diversity_max_per_family: int,
) -> None:
    """Log family-diversity reorder event with active limits."""
    logger.info(
        "[ROBUSTNESS] Family diversity reordering applied "
        f"(top_k={diversity_top_k}, max_per_family={diversity_max_per_family})."
    )


def _apply_family_diversity_if_enabled(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Applies family diversity ranking if enabled in params."""
    (
        enable_family_diversity,
        diversity_top_k,
        diversity_max_per_family,
    ) = _resolve_family_diversity_cfg(params)

    if enable_family_diversity and len(strategies_results) > 1:
        before_top = _top_origin_families(strategies_results, diversity_top_k)
        strategies_results = _apply_family_diversity(strategies_results, diversity_top_k, diversity_max_per_family)
        after_top = _top_origin_families(strategies_results, diversity_top_k)
        if _did_family_top_order_change(before_top, after_top):
            _log_family_diversity_reordering(
                logger=logger,
                diversity_top_k=diversity_top_k,
                diversity_max_per_family=diversity_max_per_family,
            )
    return strategies_results


def _resolve_block_diversity_cfg(params: dict[str, Any]) -> tuple[bool, int, int]:
    """Resolve block-diversity feature flags and limits."""
    enable_block_diversity = bool(params.get("enable_block_diversity", True))
    diversity_top_k = int(params.get("block_diversity_top_k", 10))
    diversity_max_per_partition = int(params.get("diversity_max_per_partition", 1))
    return enable_block_diversity, diversity_top_k, diversity_max_per_partition


def _apply_block_diversity_if_enabled(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Applies block partitioning diversity ranking if enabled in params."""
    (
        enable_block_diversity,
        diversity_top_k,
        diversity_max_per_partition,
    ) = _resolve_block_diversity_cfg(params)

    if enable_block_diversity and len(strategies_results) > 1:
        strategies_results = _apply_block_diversity(
            strategies_results,
            top_k=diversity_top_k,
            max_per_partition=diversity_max_per_partition,
        )
    return strategies_results


def _apply_wl_diversity_if_enabled(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Spread the head over WAVELENGTH space. 🔒 INERT BY DEFAULT, former path to the bit.

    See `_apply_wl_diversity` for the measurement that motivates it: the five ten-block ELITE
    parents carried ONE SINGLE set of λ, and that explains why four widening levers returned
    zero depositable -- they searched harder AROUND THE SAME POINT.
    """
    if not bool(params.get("enable_wl_diversity", False)):
        return strategies_results
    # 🔴 `or` AND NOT `get(key, default)`. A key present with None or 0 must fall back on
    # the block setting, and `get` does not do it: it only falls back if the key is ABSENT.
    # That default would have raised a TypeError only when the pass is ARMED -- hence never
    # in the test suite, where the flag is false by default.
    top_k = int(
        params.get("wl_diversity_top_k") or params.get("block_diversity_top_k") or 10
    )
    avant = len({_wl_set((it.get("strategy") or {}).get("blocks", []))
                 for it in strategies_results[:top_k]})
    out = _apply_wl_diversity(strategies_results, top_k=top_k)
    apres = len({_wl_set((it.get("strategy") or {}).get("blocks", []))
                 for it in out[:top_k]})
    # 🔴 WHAT THE PASS CHANGED IS SAID, NOT ASSUMED. A diversity pass that diversifies
    # nothing is exactly the kind of setting that creates a false explanation.
    logger.info(
        f"   [WL-DIVERSITE] head of {top_k}: {avant} distinct λ set(s) -> {apres}"
    )
    return out


def _filter_valid_robustness_strategies(
    strategies_in: list[dict[str, Any]],
    num_layers: int,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Filters out strategies that violate block constraint contract."""
    valid_strategies = []
    for s in strategies_in:
        ok, reason = _validate_strategy_blocks_contract(s, num_layers)
        if ok:
            valid_strategies.append(s)
        else:
            logger.warning(
                f"[ROBUSTNESS] Dropped invalid strategy ID "
                f"{s.get('strategy_id', '?')} from robustness evaluation: {reason}"
            )
    return valid_strategies


def _select_best_strat_result(strategies_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the best finite-ranked strategy result (compatibility delegate)."""
    return select_best_strat_result(strategies_results)

# --------------------------------------------------------------------------- #
# Strategy identifier ranges -- ONE single declaration
# --------------------------------------------------------------------------- #
#
# 🔴 WHY THIS EXISTS, and what it has already cost. On 2026-08-12 the winner of a run
# carried the identifier 990000320. I read "range 990 = Rate variant" and reported
# it as such; its `origin` said LOCAL_SEARCH. The consensus generator starts from
# `max_sid + 1`, so it CLIMBS into any range as soon as a variant exists -- and two
# generators end up sharing the same numbers.
#
# The wrong reading was then passed on to the user, who believed they saw Rate winning
# where there had never been any. That is exactly the pattern of this repository: it
# does not produce an error, it produces a plausible result.
#
# 🔑 THE RULE, AND IT IS SIMPLE: **the identifier is not data, it is a number.** The
# generator is read in `origin`, which is authoritative. The ranges below only serve
# to guarantee that two distinct strategies never carry the same number.

#: Base of the derived strategies (Phase B local search, `certus_strat_workers`).
STRATEGY_ID_DERIVED_BASE: int = 900_000_000
#: Base of the SLIT variants (A18).
STRATEGY_ID_SLIT_BASE: int = 970_000_000
#: Base of the RATE variants.
STRATEGY_ID_RATE_BASE: int = 990_000_000
#: Cap beyond which an incremental generator must never climb: it would enter
#: the ranges reserved above.
STRATEGY_ID_INCREMENTAL_CEILING: int = STRATEGY_ID_SLIT_BASE


def clamp_incremental_strategy_id(next_id: int) -> int:
    """Prevents a `max_sid + 1` counter from entering a reserved range.

    The incremental generators (consensus, ELITE, local search) start from the largest
    identifier already seen, so as not to collide with what exists. But once variants at
    970M or 990M are in the list, that `max + 1` follows them and the number stops
    meaning anything.

    It is therefore brought back under the cap. The residual risk -- reusing a number
    already taken under the cap -- is ruled out by the strategy signatures, which are what
    really deduplicates (`_existing_block_signatures`).
    """
    return next_id if next_id < STRATEGY_ID_INCREMENTAL_CEILING else STRATEGY_ID_DERIVED_BASE
