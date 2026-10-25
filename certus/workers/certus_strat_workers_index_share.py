"""Index share of the best strategies at the end of a STRAT run (`strat_index_share_top_k`, off by default).

The measurement lives in `certus/core/certus_strat_index_share.py`; this module gives it the worker's shared clues and writes
`index_share`, `rmse2_index_on` and `rmse2_index_off` on the first K rows of the final ranking.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from certus.core.certus_strat_index_share import INDEX_SHARE_SEED_OFFSET, index_share
from certus.utils.certus_data import SharedIndicesWorker

Ranker = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def attach_index_share(
    rows: list[dict[str, Any]],
    pre_calc_data: dict[str, Any],
    params: dict[str, Any],
    shared_clues_info: dict[str, Any],
    ranker: Ranker,
    k: int,
) -> list[dict[str, Any]]:
    """Write the index share on the first `k` rows of `ranker(rows)`; the rows and their order are otherwise untouched."""
    from certus.core.certus_strat_local_search import native_evaluator, nominal_level_index

    nominal = list(pre_calc_data["p_thick_nominal"])
    base_seed = int(params.get("robustness_seed", 42)) if params.get("robustness_seed") is not None else 42
    seed = base_seed + INDEX_SHARE_SEED_OFFSET
    runs = int(params.get("robustness_num_runs", 150))
    level = nominal_level_index(params)
    grid = pre_calc_data.get("full_dynamics_grid", {})
    with SharedIndicesWorker(shared_clues_info) as clues:
        evaluate_on = native_evaluator(params, nominal, clues, grid)
        evaluate_off = native_evaluator({**params, "index_corridor": 0.0}, nominal, clues, grid)
        for row in ranker(list(rows))[:k]:
            plan = row["strategy"]
            row.update(index_share(evaluate_on(plan, seed, runs), evaluate_off(plan, seed, runs), level))
    params["logger"].info(f"[INDEX-SHARE] index share of the first {k} strategies, {runs} draws, seed {seed}")
    return rows
