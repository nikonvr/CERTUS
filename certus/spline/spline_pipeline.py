from __future__ import annotations
"""Main spline pipeline: JSON logging, RMSE snapshots, worker orchestration."""
import copy as _copy
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
import logging
from dataclasses import dataclass
import time
from threading import Event
from typing import Any, Callable
import numpy as np
from scipy.interpolate import PchipInterpolator
from certus.spline.certus_index_spline_core import (
    K_MIN_PHYS,
    SplineOptConfig,
    _canonical_knots_min_lambda_kw,
    canonical_spline_sigma_knots,
    corridor_profile_refit_maxfun,
    _bounds_x0_for_sigma_knots,
    _log_index_spline_best_config,
    log_index_spline_d_trace,
    _log_spline_pipeline_json,
    _reflectance_absolute_backside_from_nk,
    apply_rmse_fit_window_nk_nan_to_result,
    enforce_k_floor_on_nodes,
    snapshot_result_with_rmse_fit_meta,
    x_slice_n_to_physical_nodes,
    physical_nodes_to_x_slice_n,
)
from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _sorted_finite_sigma_knots as _sorted_finite_sigma_knots_for_log,
    _transmittance_absolute_from_nk,
)
from certus_physics import (
    clip_to_bounds,
)
from certus.spline.spline_objective import (
    build_segment_optimizer_x_vector,
    build_spline_objective_masked_grid,
    spectral_mse_rmse_masked_from_nk,
    spline_objective_mse_on_masked_grid,
)
from certus.spline.spline_finalize import (
    _collect_post_s3_candidates,
    _finalize_spectral_rmse_mesh_polish_and_best,
    _log_skipped_knot_insertion_fixed_mesh,
    _select_final_scientific_candidate,
    _spectral_polish_node_mesh_profile,
)
from certus.spline.spline_profile_corridors import (
    ProfileCorridorConfig,
    compute_profiled_corridors_by_d,
    widen_corridor_envelope_to_include_nk_in_result,
    log_coaching_corridor_pipeline_skip_empty,
    log_coaching_uncertainty_parameter_guide,
)

from .spline_pipeline_utils import (
    _WorkerProgressCoordinator,
    _log_manual_insert_decision,
    _spl_rmse_improves_meaningfully,
    _spl_rmse_regression_exceeds_tolerance,
    _validated_extra_sigma_knots,
    _should_skip_manual_insert_for_equal_mesh,
    _sigma_knot_difference_for_log,
    _sigma_knots_to_lambda_nm_for_log,
    _format_lambda_knots_nm_for_log,
    _sigma_mesh_change_summary_for_log,
    _knots_cache_key,
    _fmt_d_nm,
    _meshes_match,
    _candidate_mesh_matches_target,
    _pipeline_mesh_dimensions,
    _log_worker_start_payload,
    _log_final_insert_enter,
    _log_after_final_insert,
    _log_fixed_mesh_stage_summary,
    _log_after_final_stage_summary,
    _emit_enter_fixed_mesh_stage,
    _sync_theoretical_tr_from_nk_dict,
    _stop_with_snapshot_if_requested,
    enforce_local_optimization_policy,
)
from .spline_pipeline_mesh_insert import (
    insert_manual_sigma_nodes,
    insert_mwir_mid_sigma_node,
    worker_spline_mwir_insert_node,
    worker_spline_manual_sigma_insert,
    worker_spline_auto_add_one_knot,
    _sensitivity_rank_inner_indices,
    _build_local_pull_variants,
    _build_local_refine_variants,
)
from .spline_pipeline_mesh_clean import (
    AutoCleanKnotsContext,
    _auto_clean_cache_result,
    _auto_clean_prescreen_result,
    _eval_clean_variant,
    worker_spline_auto_clean_knots,
    worker_spline_autoshift_delta_ns,
)
from .spline_pipeline_corridors_runner import (
    _corridor_seg_spline_sigma_pack_matches_nominal,
    _select_corridor_base_result_for_profile,
    _resolve_corridor_mode,
    _build_profile_corridor_config,
    _run_corridor_profile_block,
    _run_corridor_profile_with_optional_rerun,
    _sync_promoted_corridor_seed_state,
    _maybe_promote_best_corridor_refit,
    worker_run_corridor_profile_after_nl_choice,
)
from .spline_pipeline_orchestrator import (
    _apply_k_floor_to_result,
    _run_sigma_mesh_polish,
    worker_spline_optimization,
)

__all__ = [
    '_WorkerProgressCoordinator',
    '_log_manual_insert_decision',
    '_spl_rmse_improves_meaningfully',
    '_spl_rmse_regression_exceeds_tolerance',
    '_validated_extra_sigma_knots',
    '_should_skip_manual_insert_for_equal_mesh',
    '_sigma_knot_difference_for_log',
    '_sigma_knots_to_lambda_nm_for_log',
    '_format_lambda_knots_nm_for_log',
    '_sigma_mesh_change_summary_for_log',
    '_knots_cache_key',
    '_fmt_d_nm',
    '_meshes_match',
    '_candidate_mesh_matches_target',
    '_pipeline_mesh_dimensions',
    '_log_worker_start_payload',
    '_log_final_insert_enter',
    '_log_after_final_insert',
    '_log_fixed_mesh_stage_summary',
    '_log_after_final_stage_summary',
    '_emit_enter_fixed_mesh_stage',
    '_sync_theoretical_tr_from_nk_dict',
    '_stop_with_snapshot_if_requested',
    'enforce_local_optimization_policy',
    'insert_manual_sigma_nodes',
    'insert_mwir_mid_sigma_node',
    'worker_spline_mwir_insert_node',
    'worker_spline_manual_sigma_insert',
    'worker_spline_auto_add_one_knot',
    '_sensitivity_rank_inner_indices',
    '_build_local_pull_variants',
    '_build_local_refine_variants',
    'AutoCleanKnotsContext',
    '_auto_clean_cache_result',
    '_auto_clean_prescreen_result',
    '_eval_clean_variant',
    'worker_spline_auto_clean_knots',
    'worker_spline_autoshift_delta_ns',
    '_corridor_seg_spline_sigma_pack_matches_nominal',
    '_select_corridor_base_result_for_profile',
    '_resolve_corridor_mode',
    '_build_profile_corridor_config',
    '_run_corridor_profile_block',
    '_run_corridor_profile_with_optional_rerun',
    '_sync_promoted_corridor_seed_state',
    '_maybe_promote_best_corridor_refit',
    'worker_run_corridor_profile_after_nl_choice',
    '_apply_k_floor_to_result',
    '_run_sigma_mesh_polish',
    'worker_spline_optimization',
]
