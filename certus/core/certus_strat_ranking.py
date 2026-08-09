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

import logging
import concurrent.futures
import math
import numpy as np
from typing import Any

from certus_physics import _compute_valid_blocks_kernel, _dp_kernel

from certus.core.certus_strat_config import (
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
)

from certus.core.certus_strat_utils import DP_DEFAULT_MIN_WL_SEPARATION_NM

from certus.utils.certus_strat_service import select_best_strat_result

from certus.utils.certus_strat_context import (
    _validate_strategy_blocks_contract,
    _origin_priority_from_map,
    _strategy_id_sort_token,
    _augment_solution_cost_with_sym,
    _origin_family,
    _apply_family_diversity,
    _apply_block_diversity,
    _blocks_signature,
    _extract_rmse_p95_for_noise,
)



def _convert_solution_to_strategy(sol, num_layers, n_blocks, origin_tag, s_id) -> dict:
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


#: Ceiling on `p` before the logarithm. `-log(1 - 1)` is infinity, which would EXCLUDE the
#: candidate instead of ranking it last — and if all candidates of a layer
#: were 1, the DP would have no path left. So we cap at 1 - 1e-9, giving a
#: cost of ~20.7 nats: huge, but finite, so the order among bad options survives.
_YIELD_P_MAX: float = 1.0 - 1e-9


def build_yield_cost_map(
    raw_results: dict[int, list[dict[str, Any]]],
) -> dict[int, dict[float, float]]:
    """Map `[layer][lambda] -> -log(1 - p)`, LOGARITHM OF YIELD.

    Phase A calculates `results_fast[idx, 2]`, the non-terminating deposition rate
    per layer and wavelength. Phase B constructs the map given to DP by taking `-log(1 - p)`.

    Why logarithm: A deposition terminates if EVERY layer terminates:
    `yield = prod(1 - p_i)`. Its logarithm is ADDITIVE — exactly the form that Bellman DP
    optimizes without approximation. `-log(1 - p)` is a direct component of `P(conforming)`.

    `p` is estimated over `num_runs` Monte-Carlo draws. Below `1/num_runs`, this map equals ZERO.
    That is why it ADDS to the thickness error cost rather than replacing it (see `dp_yield_weight`).
    """
    out: dict[int, dict[float, float]] = {}
    for layer_idx, items in (raw_results or {}).items():
        layer_map: dict[float, float] = {}
        for entry in items or []:
            try:
                p = float(entry.get("crash_rate", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if p < 0.0:
                p = 0.0
            elif p > _YIELD_P_MAX:
                p = _YIELD_P_MAX
            layer_map[float(entry["wl"])] = -math.log1p(-p)
        if layer_map:
            out[int(layer_idx)] = layer_map
    return out


def combine_cost_and_yield(
    cost_map: dict[int, dict[float, float]],
    yield_map: dict[int, dict[float, float]],
    yield_weight: float,
) -> dict[int, dict[float, float]]:
    """`cost_nm + w x (-log(1 - p))`, the DP objective when `w > 0`.

    `yield_weight = 0` (default) returns the input map AS IS — therefore the
    previous behavior, bit for bit.

    🔴 WHY A SUM AND NOT A REPLACEMENT. The plan proposed to replace the cost
    in nanometers by the yield alone. Two measurements oppose this:

      1. 📏 On the benchmark, the BEST lambda of each of the 47 layers has a
         NULL crash rate. A pure yield objective would thus be zero on almost
         all paths and the DP would become DEGENERATE — it would no longer rank anything.
      2. The plan itself points out: "a DP that optimizes only yield can
         propose safe but spectrally mediocre strategies".

    In summary, the yield REORDERS where it is measurable and lets the cost in
    nanometers decide elsewhere. This is strictly more information, never less.

    ⚠️ `w` is in nanometers per nat, and it cannot be guessed. Benchmark to calibrate it:
    at a per-layer tolerance of 0.107%, `-log(1-p)` is 1.07e-3 nat; for this
    crash to weigh as much as 0.2 nm of error — the order of magnitude of the median measured cost
    — `w` needs to be around 200. **To be scanned, not to be set.**
    """
    if yield_weight <= 0.0 or not yield_map:
        return cost_map
    out: dict[int, dict[float, float]] = {}
    for layer_idx, layer_dict in cost_map.items():
        y = yield_map.get(layer_idx, {})
        out[layer_idx] = {wl: c + yield_weight * y.get(wl, 0.0) for wl, c in layer_dict.items()}
    return out


def _find_k_best_groupings_dp_sequential(
    cost_map: dict[int, dict[float, float]],
    n_blocks: int,
    num_layers: int,
    top_k: int = 100,
    timeout: float = 120.0,
    start_time: float = None,
    force_monolayer: bool = False,
    nucleation_wl: float = None,
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

    solutions = []
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
            for l in range(start, end):
                assignments[l] = wl

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
    nucleation_wl: float = None,
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
) -> list[dict[str, Any]]:
    if n_blocks <= 0 or num_layers <= 0:
        return []

    strategies_collected = []
    strategy_id_base = n_blocks * 1000
    LIMIT_CANDIDATES = candidate_limit

    def apply_nucleation_constraint(cost_map_in) -> Any:
        if not nucleation_wl or nucleation_size <= 0:
            return cost_map_in
        n_wl = float(nucleation_wl)
        for i in range(nucleation_size):
            if i in cost_map_in and cost_map_in[i]:
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

    logging.getLogger("ThinFilm").info(
        f"Mining: n_blocks={n_blocks}, CostMapThick Size={len(cost_map_thick)}, CostMapSq Size={len(cost_map_sq)}"
    )

    def run_mining(cost_map, origin_name, offset_id, apply_sym_post=False) -> Any:
        logger = logging.getLogger("ThinFilm")
        logger.debug(f"[DEBUG MINING] {origin_name}: Starting DP with {len(cost_map)} layers, n_blocks={n_blocks}")
        
        for layer_idx in list(cost_map.keys())[:3]:
            wls_sample = list(cost_map[layer_idx].keys())[:5]
            logger.debug(
                f"[DEBUG MINING] Layer {layer_idx}: {len(cost_map[layer_idx])} wavelengths, sample: {wls_sample}"
            )

        solutions = _find_k_best_groupings_dp_sequential(
            cost_map,
            n_blocks,
            num_layers,
            top_k=top_k,
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
        logger.debug(f"[DEBUG MINING] {origin_name}: DP returned {len(solutions)} solutions")

        found = []
        if solutions:
            for rank, sol in enumerate(solutions):
                s_id = strategy_id_base + offset_id + rank
                strat = _convert_solution_to_strategy(sol, num_layers, n_blocks, origin_name, s_id)
                is_valid, reason = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=n_blocks)
                if not is_valid:
                    logger.debug(f"[DEBUG MINING] Dropped invalid strategy {s_id} ({origin_name}): {reason}")
                    continue
                strat["rank_in_group"] = rank + 1
                smart_tag = f" (Smart Nucl. L1-L{nucleation_size})" if nucleation_wl else ""
                strat["origin_details"] = f"{origin_name}{smart_tag} (Rank {rank + 1})"
                found.append(strat)
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
    for _layer_idx, cands in raw_results_thickness.items():
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
            b_start = int(round(b_idx * block_size))
            b_end = int(round((b_idx + 1) * block_size)) if b_idx < n_blocks - 1 else num_layers
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
        b_start = int(round(b_idx * block_size))
        b_end = int(round((b_idx + 1) * block_size)) if b_idx < n_blocks - 1 else num_layers
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


def _apply_strategy_ranking(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    origin_priority_map: dict[str, int],
) -> list[dict[str, Any]]:
    """Rank and sort strategies based on robustness, resolution, and origin priority."""

    def _advanced_key(item: dict[str, Any]) -> tuple:
        strategy = item.get("strategy", {})
        origin = str(strategy.get("origin", "UNKNOWN"))
        same_wl_kept = int(strategy.get("same_wl_kept", 0))
        try:
            n_blocks_val = int(strategy.get("n_blocks", len(strategy.get("blocks", []))))
        except (TypeError, ValueError):
            n_blocks_val = len(strategy.get("blocks", []))
        min_res = float(item.get("min_resolution", 999.0))
        return (
            float(item.get("robustness_score", np.inf)),
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



