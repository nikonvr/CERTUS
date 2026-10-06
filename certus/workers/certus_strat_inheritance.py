"""Block-fusion inheritance for STRAT strategies."""
from __future__ import annotations

from typing import Any

from certus.core.certus_strat_ranking import STRATEGY_ID_DERIVED_BASE, strategy_id_for_block


def _estimate_fusion_cost_fast(b1, b2, cost_map_sq) -> Any:

    start, end = b1["start"], b2["end"]

    cost = 0.0

    wl = b1["wavelength"]

    for l_idx in range(start, end):
        if l_idx in cost_map_sq and wl in cost_map_sq[l_idx]:
            cost += cost_map_sq[l_idx][wl]

        else:
            cost += 1e6

    return cost


def _find_best_wl_fast(start_layer, end_layer, cost_map_sq) -> Any:

    if start_layer not in cost_map_sq:
        return None

    candidate_wls = list(cost_map_sq[start_layer].keys())[:10]

    best_wl = None

    min_total_cost = float("inf")

    for wl in candidate_wls:
        total_cost = 0.0

        valid = True

        for l_idx in range(start_layer, end_layer):
            if l_idx in cost_map_sq and wl in cost_map_sq[l_idx]:
                total_cost += cost_map_sq[l_idx][wl]

            else:
                valid = False

                break

        if valid and total_cost < min_total_cost:
            min_total_cost = total_cost

            best_wl = wl

    return best_wl


def derive_strategies_exhaustive(
    high_complexity_results: list[dict[str, Any]],
    cost_map_sq: dict[int, dict[float, float]],
    top_k_parents: int = 15,
    max_fusions_per_parent: int = 5,
) -> list[dict[str, Any]]:

    derived_strategies = []

    _derive_next_id = [0]

    parents = sorted(high_complexity_results, key=lambda x: x["robustness_score"])[:top_k_parents]

    seen_signatures = set()

    for res in parents:
        parent_strat = res["strategy"]

        blocks = parent_strat["blocks"]

        n_blocks = len(blocks)

        if n_blocks <= 1:
            continue

        fusion_candidates = []

        for i in range(n_blocks - 1):
            b1, b2 = blocks[i], blocks[i + 1]

            cost_est = _estimate_fusion_cost_fast(b1, b2, cost_map_sq)

            fusion_candidates.append({"index": i, "cost": cost_est, "b1": b1, "b2": b2})

        fusion_candidates.sort(key=lambda x: x["cost"])

        best_fusions = fusion_candidates[:max_fusions_per_parent]

        for fusion in best_fusions:
            i = fusion["index"]

            b1, b2 = fusion["b1"], fusion["b2"]

            candidate_wls = {float(b1["wavelength"]), float(b2["wavelength"])}

            best_theo = _find_best_wl_fast(b1["start"], b2["end"], cost_map_sq)

            if best_theo:
                candidate_wls.add(float(best_theo))

            for wl in sorted(candidate_wls):
                new_blocks_struct = []

                new_blocks_struct.extend(blocks[:i])

                new_blocks_struct.append(
                    {
                        "start": b1["start"],
                        "end": b2["end"],
                        "wavelength": float(wl),
                        "num_layers": b2["end"] - b1["start"],
                    }
                )

                new_blocks_struct.extend(blocks[i + 2 :])

                sig = tuple((b["start"], b["end"], b["wavelength"]) for b in new_blocks_struct)

                if sig not in seen_signatures:
                    seen_signatures.add(sig)

                    _derive_next_id[0] += 1

                    new_id = strategy_id_for_block(STRATEGY_ID_DERIVED_BASE, n_blocks, _derive_next_id[0])

                    parent_origin = str(parent_strat.get("origin", "UNKNOWN")).upper()

                    if "SYM" in parent_origin:
                        merge_origin = "SMART_MERGE_SYM"

                    elif "THICKNESS²" in parent_origin or "THICKNESS2" in parent_origin:
                        merge_origin = "SMART_MERGE_THICKNESS2"

                    elif "THICKNESS" in parent_origin:
                        merge_origin = "SMART_MERGE_THICKNESS"

                    else:
                        merge_origin = "SMART_MERGE_MIXED"

                    derived_strategies.append(
                        {
                            "strategy_id": new_id,
                            "n_blocks": n_blocks - 1,
                            "blocks": new_blocks_struct,
                            "origin": f"{merge_origin} (from ID {parent_strat['strategy_id']})",
                            "origin_details": (
                                f"{merge_origin} from {parent_origin} (parent ID {parent_strat['strategy_id']})"
                            ),
                            "avg_rmse_nominal": 0.0,
                            "num_unique_wavelengths": len(set(b["wavelength"] for b in new_blocks_struct)),
                        }
                    )

    return derived_strategies


