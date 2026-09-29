# =============================================================================
# CERTUS STRAT - Core numerical and physics logic
# =============================================================================
# The names other modules take from this one, each imported from the module that defines it.
# It used to copy the whole namespace of eight STRAT modules into its globals (an import * in
# disguise, D44): ruff saw neither what it offered nor what others took from it.

from certus.core.certus_strat_config import _emit_stat, _flush_sp_stats, _worker_init, precompute_clues_and_matrices
from certus.core.certus_strat_objectives import (
    _compute_strategy_symmetry_score_percent,
    _compute_theoretical_layer_profile,
    _extract_local_extrema_points,
)
from certus.core.certus_strat_solvers import generate_excel_report
from certus.core.certus_strat_robustness import _get_best_noise_results, run_final_simulation_block
from certus.core.certus_strat_ranking import _find_k_best_groupings_dp_sequential, mine_strategies_for_block_count
from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
from certus.core.certus_strat_consensus import _generate_elite_candidate_strategies, _test_strategy_robustness_task
from certus.core.certus_strat_utils import (
    APP_CONTEXT,
    DYNAMICS_METRIC_NAME,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    SYM_DEFAULT_WEIGHT,
    _IdxWrapper,
    get_refractive_clues_vectorized,
    set_robust_material_db,
)
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter

