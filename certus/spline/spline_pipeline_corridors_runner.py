from __future__ import annotations
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
from certus.spline.certus_corridor_config import ProfileCorridorConfig
from certus.spline.spline_profile_corridors import compute_profiled_corridors_by_d
from certus.spline.certus_corridor_utils import widen_corridor_envelope_to_include_nk_in_result
from certus.spline.certus_corridor_logger import (
    log_coaching_corridor_pipeline_skip_empty,
    log_coaching_uncertainty_parameter_guide,
)



def _corridor_seg_spline_sigma_pack_matches_nominal(out: dict) -> bool:
    """Whether ``n_lam_seg_spline_sigma`` / ``d_nm_seg_spline_sigma`` still describe ``out``'s nominal n,k,d.

    After manual node insert (or any step that changes ``d_nm`` / ``n_lam`` without regenerating
    the mesh-polish archive), the seg-sigma pack is stale: using it for corridors would center
    profiling on the old thickness (see logs: ``seed_d_nm`` correct but ``d_opt`` wrong).
    """
    rs = out.get("spectral_rmse_seg_spline_sigma")
    if not isinstance(rs, (int, float)) or not np.isfinite(float(rs)):
        return False
    if "n_lam_seg_spline_sigma" not in out or "k_lam_seg_spline_sigma" not in out:
        return False
    raw_n = out.get("n_lam")
    raw_k = out.get("k_lam")
    if raw_n is None or raw_k is None:
        return True
    n_seg = np.asarray(out["n_lam_seg_spline_sigma"], dtype=np.float64).ravel()
    k_seg = np.asarray(out["k_lam_seg_spline_sigma"], dtype=np.float64).ravel()
    n_cur = np.asarray(raw_n, dtype=np.float64).ravel()
    k_cur = np.asarray(raw_k, dtype=np.float64).ravel()
    if n_cur.size == 0 or k_cur.size == 0:
        return True
    if n_seg.size != n_cur.size or k_seg.size != k_cur.size:
        return False
    try:
        d_seg = float(out.get("d_nm_seg_spline_sigma", float("nan")))
        d_cur = float(out.get("d_nm", float("nan")))
    except (TypeError, ValueError):
        return False
    if not (np.isfinite(d_seg) and np.isfinite(d_cur)):
        return False
    tol_nm = 5.0e-3
    return abs(d_seg - d_cur) <= tol_nm

def _select_corridor_base_result_for_profile(
    cfg: SplineOptConfig,
    out: dict,
    solver_snapshot: dict,
) -> tuple[dict, str]:
    """Selects the "base" dict for corridor profiling (starting n,k + consistent RMSE).

    The corridor is a **local sensitivity**: small steps in *d* around optimum, refit
    n/L only, with an **RMSE tolerance** (alpha or Delta). Starting point must be the
    **same model** as the one providing the **best spectral RMSE** reference: with
    ``best_polished``, we copy polished curves **and**, if available,
    ``x_seg_spline_sigma`` -> ``x`` / ``n_nodes_physical`` / ``L_nodes`` so that the
    central refit seed is aligned with this model (otherwise threshold and refit mismatch).

    If ``corridor_profile_d_base_source`` attribute is missing (minimal cfg), default =
    ``best_polished`` comme ``SplineOptConfig``.
    """
    mode = str(getattr(cfg, "corridor_profile_d_base_source", "best_polished") or "best_polished").strip().lower()
    out["post_s3_scientific_corridor_seed_candidate_id"] = None
    out["post_s3_scientific_corridor_fallback_reason"] = None
    if mode == "best_global":
        selected_candidate = out.get("post_s3_scientific_candidate")
        ledger = out.get("post_s3_candidate_ledger")

        def _candidate_to_base(candidate: dict | None) -> tuple[dict | None, str | None]:
            if not isinstance(candidate, dict):
                return None, None
            base_mode = str(candidate.get("corridor_base_mode", "")).strip().lower()
            if base_mode == "solver":
                return dict(solver_snapshot), "best_global_solver"
            if base_mode == "best_polished":
                return None, "best_polished"
            return None, None

        def _best_compatible_candidate() -> dict | None:
            if not isinstance(ledger, list):
                return None
            compatible = [
                cand
                for cand in ledger
                if isinstance(cand, dict)
                and bool(cand.get("selection_eligible"))
                and bool(cand.get("corridor_seed_compatible"))
                and cand.get("rmse") is not None
            ]
            if not compatible:
                return None
            return min(compatible, key=lambda cand: float(cand["rmse"]))

        if isinstance(selected_candidate, dict):
            out["post_s3_scientific_corridor_seed_candidate_id"] = selected_candidate.get("id")
            if bool(selected_candidate.get("corridor_seed_compatible")):
                direct_base, direct_mode = _candidate_to_base(selected_candidate)
                if direct_mode == "best_global_solver":
                    return direct_base if direct_base is not None else dict(solver_snapshot), direct_mode
                if direct_mode == "best_polished":
                    mode = "best_polished"
                else:
                    out["post_s3_scientific_corridor_fallback_reason"] = (
                        f"scientific candidate {selected_candidate.get('id')} has no usable corridor base mode"
                    )
            else:
                fallback_candidate = _best_compatible_candidate()
                if isinstance(fallback_candidate, dict):
                    out["post_s3_scientific_corridor_seed_candidate_id"] = fallback_candidate.get("id")
                    out["post_s3_scientific_corridor_fallback_reason"] = (
                        f"scientific candidate {selected_candidate.get('id')} is not corridor compatible; "
                        f"fallback to {fallback_candidate.get('id')}"
                    )
                    fallback_base, fallback_mode = _candidate_to_base(fallback_candidate)
                    if fallback_mode == "best_global_solver":
                        return fallback_base if fallback_base is not None else dict(solver_snapshot), fallback_mode
                    if fallback_mode == "best_polished":
                        mode = "best_polished"
                else:
                    out["post_s3_scientific_corridor_fallback_reason"] = (
                        f"scientific candidate {selected_candidate.get('id')} is not corridor compatible and no compatible fallback exists"
                    )
        if mode == "best_global":
            global_source = str(out.get("spectral_rmse_global_best_source", "")).strip().lower()
            global_label = str(out.get("spectral_rmse_global_best_label", "")).strip()
            if global_source == "solver" or global_label == "Solver_segments":
                return dict(solver_snapshot), "best_global_solver"
            if global_source == "polished":
                mode = "best_polished"
    if mode == "dict":
        return out, "dict"
    if mode == "best_polished":
        rs = out.get("spectral_rmse_seg_spline_sigma")
        if isinstance(rs, (int, float)) and np.isfinite(float(rs)):
            if "n_lam_seg_spline_sigma" in out and "k_lam_seg_spline_sigma" in out:
                if not _corridor_seg_spline_sigma_pack_matches_nominal(out):
                    try:
                        d_seg = float(out.get("d_nm_seg_spline_sigma", float("nan")))
                        d_cur = float(out.get("d_nm", float("nan")))
                    except (TypeError, ValueError):
                        d_seg = float("nan")
                        d_cur = float("nan")
                    n_sz = int(np.asarray(out.get("n_lam"), dtype=np.float64).size)
                    nseg_sz = int(np.asarray(out["n_lam_seg_spline_sigma"], dtype=np.float64).size)
                    logging.getLogger("CERTUS").info(
                        "PIPELINE [CORRIDORS d] Base best_polished ignored: archived spline-sigma pack "
                        "out of sync with the current result (e.g. manual node insertion). "
                        "d_nm_seg_spline=%s d_nm_current=%s | len(n_lam)=%d vs len(seg_pack)=%s → "
                        "profiling from nominal dict.",
                        f"{d_seg:.6f}" if np.isfinite(d_seg) else "n/a",
                        f"{d_cur:.6f}" if np.isfinite(d_cur) else "n/a",
                        n_sz,
                        nseg_sz,
                    )
                    return dict(out), "dict_stale_seg_sigma_pack"
                b = dict(solver_snapshot)
                b["n_lam"] = np.asarray(out["n_lam_seg_spline_sigma"], dtype=np.float64).copy()
                b["k_lam"] = np.asarray(out["k_lam_seg_spline_sigma"], dtype=np.float64).copy()
                b["d_nm"] = float(out.get("d_nm_seg_spline_sigma", b.get("d_nm", float("nan"))))
                b["rmse"] = float(rs)
                b["x_encoding"] = "corridor_base_best_polished_spline_sigma"
                best_label = out.get("spectral_rmse_best_label")
                best_val = out.get("spectral_rmse_best_value")
                if best_label is not None:
                    b["spectral_rmse_best_label"] = best_label
                if isinstance(best_val, (int, float)) and np.isfinite(float(best_val)):
                    b["spectral_rmse_best_value"] = float(best_val)
                b["spectral_rmse_seg_spline_sigma"] = float(rs)
                if "n_lam_seg_spline_sigma" in out:
                    b["n_lam_seg_spline_sigma"] = np.asarray(out["n_lam_seg_spline_sigma"], dtype=np.float64).copy()
                if "k_lam_seg_spline_sigma" in out:
                    b["k_lam_seg_spline_sigma"] = np.asarray(out["k_lam_seg_spline_sigma"], dtype=np.float64).copy()
                if "d_nm_seg_spline_sigma" in out and np.isfinite(float(out.get("d_nm_seg_spline_sigma"))):
                    b["d_nm_seg_spline_sigma"] = float(out["d_nm_seg_spline_sigma"])
                # Corridor seed: same nodes / x as sigma-mesh polish (otherwise RMSE_ref vs refit inconsistent).
                sk_b = np.asarray(
                    out.get("sigma_knots", b.get("sigma_knots")),
                    dtype=np.float64,
                ).ravel()
                if sk_b.size < 2:
                    lam_cfg = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
                    if lam_cfg.size:
                        sk_b = np.asarray(
                            canonical_spline_sigma_knots(
                                float(np.min(lam_cfg)),
                                float(np.max(lam_cfg)),
                                **_canonical_knots_min_lambda_kw(cfg),
                            ),
                            dtype=np.float64,
                        ).ravel()
                if sk_b.size >= 2:
                    b["sigma_knots"] = sk_b.copy()
                x_seg = out.get("x_seg_spline_sigma")
                if x_seg is not None and sk_b.size >= 2:
                    xa = np.asarray(x_seg, dtype=np.float64).ravel()
                    k_sig = int(sk_b.size)
                    if xa.size == 1 + 2 * k_sig:
                        b["x_seg_spline_sigma"] = xa.copy()
                        b["x"] = xa.copy()
                        n_slice = xa[1 : 1 + k_sig]
                        L_slice = xa[1 + k_sig : 1 + 2 * k_sig]
                        b["L_nodes"] = np.asarray(L_slice, dtype=np.float64).copy()
                        if cfg.n_mono_band_nm is None:
                            b["n_nodes_physical"] = np.asarray(n_slice, dtype=np.float64).copy()
                        else:
                            from certus.spline.spline_objective import x_slice_n_to_physical_nodes

                            b["n_nodes_physical"] = x_slice_n_to_physical_nodes(
                                np.asarray(n_slice, dtype=np.float64),
                                sk_b,
                                cfg.n_mono_band_nm,
                            )
                        return b, "best_polished"
                return b, "best_polished"
        return dict(solver_snapshot), "solver"

    return dict(solver_snapshot), "solver"

def _resolve_corridor_mode(cfg: SplineOptConfig) -> tuple[str, str, float]:
    """Map ``corridor_profile_d_mode`` to ``(walk_mode, threshold_mode, tol_abs)``."""
    raw = str(getattr(cfg, "corridor_profile_d_mode", "abs_delta_adaptive") or "abs_delta_adaptive").strip().lower()
    tol = float(getattr(cfg, "corridor_profile_d_rmse_abs_tolerance", 2.5e-4) or 2.5e-4)
    if raw == "lr":
        return "lr", "alpha", tol
    if raw == "abs_delta":
        return "alpha", "abs_delta", tol
    if raw == "abs_delta_adaptive":
        return "alpha", "abs_delta_adaptive", tol
    if raw == "alpha_plus_delta":
        return "alpha", "alpha_plus_delta", tol
    if raw == "alpha_plus_adaptive_delta":
        return "alpha", "alpha_plus_adaptive_delta", tol
    return "alpha", "alpha", tol

def _build_profile_corridor_config(
    cfg: SplineOptConfig,
    p_mode: str,
    rm_thr_mode: str,
    tol_abs: float,
) -> ProfileCorridorConfig:
    """Build a :class:`ProfileCorridorConfig` from ``SplineOptConfig`` corridor fields."""
    return ProfileCorridorConfig(
        enabled=True,
        rmse_alpha=float(getattr(cfg, "corridor_profile_d_rmse_alpha", 1.05) or 1.05),
        mode=str(p_mode),
        step_nm=float(getattr(cfg, "corridor_profile_d_step_nm", 1.0) or 1.0),
        step_nm_initial=float(getattr(cfg, "corridor_profile_d_step_nm_initial", 1.0) or 1.0),
        step_growth=float(getattr(cfg, "corridor_profile_d_step_growth", 1.4) or 1.4),
        step_nm_max=float(getattr(cfg, "corridor_profile_d_step_nm_max", 4.0) or 4.0),
        max_span_nm=float(getattr(cfg, "corridor_profile_d_max_span_nm", 15.0) or 15.0),
        min_valid_each_side=int(getattr(cfg, "corridor_profile_d_min_valid_each_side", 1) or 1),
        lr_conf_level=float(getattr(cfg, "corridor_profile_d_lr_conf_level", 0.95) or 0.95),
        sigma_t=getattr(cfg, "corridor_profile_d_sigma_t", None),
        sigma_r=getattr(cfg, "corridor_profile_d_sigma_r", None),
        n_starts=int(getattr(cfg, "corridor_profile_d_n_starts", 1) or 1),
        fit_auto_n_starts=bool(getattr(cfg, "corridor_profile_d_fit_auto_n_starts", False)),
        fit_max_n_starts=int(getattr(cfg, "corridor_profile_d_fit_max_n_starts", 2) or 2),
        fit_retry_maxfun_scale=float(getattr(cfg, "corridor_profile_d_fit_retry_maxfun_scale", 1.5) or 1.5),
        jitter_n=float(getattr(cfg, "corridor_profile_d_jitter_n", 0.02) or 0.02),
        jitter_L=float(getattr(cfg, "corridor_profile_d_jitter_L", 0.15) or 0.15),
        seed_gate_keep_nominal_if_refit_worse=bool(
            getattr(cfg, "corridor_profile_d_seed_gate_keep_nominal_if_refit_worse", True)
        ),
        seed_gate_tol_rel=float(getattr(cfg, "corridor_profile_d_seed_gate_tol_rel", 0.0)),
        seed_gate_tol_abs=float(getattr(cfg, "corridor_profile_d_seed_gate_tol_abs", 1e-5)),
        rng_seed=int(getattr(cfg, "corridor_profile_d_rng_seed", 0) or 0),
        sigma_hetero_residual=bool(getattr(cfg, "corridor_profile_d_sigma_hetero", False)),
        sigma_hetero_scale=float(getattr(cfg, "corridor_profile_d_sigma_hetero_scale", 1.0) or 1.0),
        threshold_basis=str(getattr(cfg, "corridor_profile_d_threshold_basis", "max") or "max"),
        threshold_ratio_guard=float(getattr(cfg, "corridor_profile_d_threshold_ratio_guard", 1.25) or 1.25),
        auto_relax_threshold_to_include_center=bool(getattr(cfg, "corridor_profile_d_auto_relax_threshold", True)),
        auto_relax_epsilon=float(getattr(cfg, "corridor_profile_d_auto_relax_epsilon", 0.002) or 0.002),
        auto_relax_max_factor=float(getattr(cfg, "corridor_profile_d_auto_relax_max_factor", 1.5) or 1.5),
        parabola_half_window_pts=int(getattr(cfg, "corridor_profile_d_parabola_half_window_pts", 4) or 4),
        force_symmetric_interval=bool(getattr(cfg, "corridor_profile_d_force_symmetric_interval", True)),
        symmetric_interval_center_mode=str(
            getattr(cfg, "corridor_profile_d_symmetric_center_mode", "parabola") or "parabola"
        ),
        adaptive_rmse_abs_ref_half_width_nm=float(
            getattr(cfg, "corridor_profile_d_adaptive_rmse_ref_half_width_nm", 1.5) or 1.5
        ),
        adaptive_rmse_abs_probe_steps_each_side=int(
            getattr(cfg, "corridor_profile_d_adaptive_rmse_probe_steps_each_side", 3) or 3
        ),
        adaptive_rmse_abs_noise_factor=float(getattr(cfg, "corridor_profile_d_adaptive_rmse_noise_factor", 3.0) or 3.0),
        adaptive_rmse_abs_min=float(getattr(cfg, "corridor_profile_d_adaptive_rmse_min", 2.5e-5) or 2.5e-5),
        rmse_threshold_mode=str(rm_thr_mode),
        rmse_abs_tolerance=float(tol_abs),
        scientific_nominal_corridor=bool(getattr(cfg, "corridor_scientific_nominal_enabled", True)),
    )

def _run_corridor_profile_block(
    cfg: SplineOptConfig,
    out: dict,
    solver_snapshot: dict,
    log: logging.Logger,
    live_cb=None,
) -> None:
    """Run d-profiling corridors if enabled; modifies ``out`` in-place.

    Guard: returns immediately if ``corridor_profile_d_enabled`` is False.
    """
    if not bool(getattr(cfg, "corridor_profile_d_enabled", False)):
        return
    try:
        cfg_eff = cfg
        base_corridor_result, base_source_effective = _select_corridor_base_result_for_profile(
            cfg_eff, out, solver_snapshot
        )
        try:
            _d_out_nom = float(out.get("d_nm", float("nan")))
            _d_out_txt = f"{_d_out_nom:.6f} nm" if np.isfinite(_d_out_nom) else "n/a"
        except (TypeError, ValueError):
            _d_out_txt = "n/a"
        try:
            _d_seg_a = float(out.get("d_nm_seg_spline_sigma", float("nan")))
            _d_seg_txt = f"{_d_seg_a:.6f} nm" if np.isfinite(_d_seg_a) else "—"
        except (TypeError, ValueError):
            _d_seg_txt = "—"
        log_index_spline_d_trace(
            log,
            f"corridor: base profilage ({base_source_effective})",
            base_corridor_result.get("d_nm"),
            detail=f"d_dict_out avant merge={_d_out_txt} d_nm_seg_spline_sigma(archive)={_d_seg_txt}",
        )
        fallback_reason = str(out.get("post_s3_scientific_corridor_fallback_reason", "")).strip()
        if fallback_reason:
            log.info(
                "PIPELINE [CORRIDORS d] best_global fallback | %s",
                fallback_reason,
            )
        log_coaching_uncertainty_parameter_guide()
        _pmf = int(corridor_profile_refit_maxfun(cfg_eff))
        _raw_corr = (
            str(getattr(cfg_eff, "corridor_profile_d_mode", "abs_delta_adaptive") or "abs_delta_adaptive")
            .strip()
            .lower()
        )
        _p_mode, _rm_thr_mode, _tol_abs = _resolve_corridor_mode(cfg_eff)
        log.info(
            "PIPELINE [CORRIDORS d] Corridor profiling (acceptance envelope) | base_source=%s | mode=%s (walk=%s thr=%s) "
            "alpha=%.3f Delta_rmse=%.6f conf=%.3f sigma=%s | step=%.4g nm span=%.4g nm | refit_maxfun=%d (polish run=%d) | starts=%d jitter_n=%.4g jitter_L=%.4g seed=%d",
            str(base_source_effective),
            str(_raw_corr),
            str(_p_mode),
            str(_rm_thr_mode),
            float(getattr(cfg_eff, "corridor_profile_d_rmse_alpha", 1.05) or 1.05),
            float(_tol_abs),
            float(getattr(cfg_eff, "corridor_profile_d_lr_conf_level", 0.95) or 0.95),
            str(getattr(cfg_eff, "corridor_profile_d_sigma_t", None)),
            float(getattr(cfg_eff, "corridor_profile_d_step_nm", 1.0) or 1.0),
            float(getattr(cfg_eff, "corridor_profile_d_max_span_nm", 15.0) or 15.0),
            int(_pmf),
            int(getattr(cfg_eff, "polish_maxfun", 0) or 0),
            int(getattr(cfg_eff, "corridor_profile_d_n_starts", 1) or 1),
            float(getattr(cfg_eff, "corridor_profile_d_jitter_n", 0.02) or 0.02),
            float(getattr(cfg_eff, "corridor_profile_d_jitter_L", 0.15) or 0.15),
            int(getattr(cfg_eff, "corridor_profile_d_rng_seed", 0) or 0),
        )
        if _rm_thr_mode == "alpha_plus_delta":
            log.info(
                "PIPELINE [CORRIDORS d] Scientific corridor (alpha_plus_delta): threshold = %.3f × RMSE_ref + %.4f; nominal included natively.",
                float(getattr(cfg_eff, "corridor_profile_d_rmse_alpha", 1.05) or 1.05),
                float(_tol_abs),
            )
        elif _rm_thr_mode == "alpha_plus_adaptive_delta":
            log.info(
                "PIPELINE [CORRIDORS d] Scientific corridor (alpha_plus_adaptive_delta): threshold = %.3f × RMSE_ref + Delta_adaptive(local) ; nominal included natively.",
                float(getattr(cfg_eff, "corridor_profile_d_rmse_alpha", 1.05) or 1.05),
            )
        elif _rm_thr_mode == "abs_delta_adaptive":
            if bool(getattr(cfg, "corridor_scientific_nominal_enabled", True)):
                log.info(
                    "PIPELINE [CORRIDORS d] Scientific corridor: RMSE_ref = best polished RMSE (spectral_rmse_best_value); threshold = RMSE_ref + Delta_adaptive(local); nominal included natively.",
                )
            else:
                log.info(
                    "PIPELINE [CORRIDORS d] Corridor threshold (adaptive abs_delta): RMSE <= RMSE_ref (base curves) + Delta_adaptive(local).",
                )
        elif _rm_thr_mode == "abs_delta":
            if bool(getattr(cfg, "corridor_scientific_nominal_enabled", True)):
                log.info(
                    "PIPELINE [CORRIDORS d] Scientific corridor: RMSE_ref = best polished RMSE "
                    "(spectral_rmse_best_value); threshold = RMSE_ref + Delta; nominal included natively.",
                )
            else:
                log.info(
                    "PIPELINE [CORRIDORS d] Corridor threshold (legacy abs_delta): RMSE <= RMSE_ref (base curves) + Delta.",
                )
        else:
            log.info(
                "PIPELINE [CORRIDORS d] Reminder: RMSE for refits at fixed d can exceed spectral_rmse_segments "
                "(local n,L re-optimization, corridor budget) - compare to INDEX_SPLINE [CORRIDORS d] logs "
                "('Reminder', 'Center: OK', 'RMSE threshold fallback').",
            )
        pconf = _build_profile_corridor_config(cfg_eff, _p_mode, _rm_thr_mode, _tol_abs)
        cfg_prof = cfg_eff.replace(
            nk_profile_interp="smooth",
            k_clip_lo=1e-6,
            k_clip_hi=1e-1,
        )
        if str(getattr(cfg_eff, "nk_profile_interp", "smooth") or "smooth").strip().lower() != "smooth":
            log.info(
                "PIPELINE [CORRIDORS d] nk_profile_interp forced to 'smooth' for profiling refits.",
            )
        log.info(
            "PIPELINE [CORRIDORS d] k bounds forced for corridor refits | k_min=%.1e | k_max=%.1e",
            float(cfg_prof.k_clip_lo),
            float(cfg_prof.k_clip_hi),
        )
        extra = compute_profiled_corridors_by_d(
            cfg_prof,
            base_corridor_result,
            pconf=pconf,
            live_cb=live_cb,
        )
        extra["profile_d_base_source_effective"] = str(base_source_effective)
        extra["profile_d_base_x_encoding"] = str(base_corridor_result.get("x_encoding", ""))
        try:
            extra["profile_d_base_rmse_seed"] = float(base_corridor_result.get("rmse", float("nan")))
        except (TypeError, ValueError):
            extra["profile_d_base_rmse_seed"] = float("nan")
        out.update(extra)
        _maybe_promote_best_corridor_refit(cfg_eff, out, extra, log)
        if not bool(extra.get("profile_d_scientific_nominal", False)):
            widen_corridor_envelope_to_include_nk_in_result(
                out,
                np.asarray(out.get("n_lam", []), dtype=np.float64),
                np.asarray(out.get("k_lam", []), dtype=np.float64),
            )
        # V2.3: ln(k) regularization weight sensitivity scan.
        if bool(getattr(cfg, "corridor_reg_sensitivity_enabled", False)):
            try:
                from certus.spline.certus_corridor_orchestrator_utils import compute_reg_sensitivity_scan

                base_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))
                decades = int(max(0, getattr(cfg, "corridor_reg_sensitivity_decades", 2) or 2))
                npt = int(max(2, getattr(cfg, "corridor_reg_sensitivity_points", 5) or 5))
                if base_w <= 0.0:
                    base_w = 1e-3
                exps = np.linspace(-decades, decades, npt, dtype=np.float64)
                w_grid = base_w * (10.0**exps)
                log.info(
                    "PIPELINE [CORRIDORS d] REG-SENS start | base=%.6g decades=%d points=%d | grid=%s",
                    float(base_w),
                    int(decades),
                    int(npt),
                    np.array2string(np.asarray(w_grid), precision=3),
                )
                extra2 = compute_reg_sensitivity_scan(cfg_prof, out, pconf=pconf, weights=w_grid)
                out.update(extra2)
            except NUMERICAL_FAULT_EXCEPTIONS:
                log.exception("PIPELINE [CORRIDORS d] REG-SENS failed (ignored).")
        # V2.4: parametric bootstrap (bands).
        if bool(getattr(cfg, "corridor_bootstrap_enabled", False)):
            try:
                from certus.spline.certus_corridor_exploration import compute_bootstrap_corridors_by_d

                B = int(max(0, getattr(cfg, "corridor_bootstrap_n", 40) or 40))
                p = float(getattr(cfg, "corridor_bootstrap_percentile", 0.95) or 0.95)
                seedB = int(getattr(cfg, "corridor_bootstrap_seed", 0) or 0)
                sigT = getattr(cfg, "corridor_bootstrap_sigma_t", None)
                sigR = getattr(cfg, "corridor_bootstrap_sigma_r", None)
                modeB = str(getattr(cfg, "corridor_bootstrap_mode", "parametric") or "parametric")
                blkB = int(max(1, getattr(cfg, "corridor_bootstrap_block_len", 1) or 1))
                qref = (
                    int(max(0, getattr(cfg, "corridor_bootstrap_quick_refit_maxfun", 0) or 0))
                    if bool(getattr(cfg, "corridor_bootstrap_quick_refit", False))
                    else None
                )
                log.info(
                    "PIPELINE [CORRIDORS d] BOOT start | mode=%s blk=%d | B=%d p=%.3f seed=%d sigma_T=%s sigma_R=%s | quick_refit_maxfun=%s",
                    str(modeB),
                    int(blkB),
                    int(B),
                    float(p),
                    int(seedB),
                    str(sigT),
                    str(sigR),
                    str(qref),
                )
                # Solver snapshot after mesh polish: align n/k, sigma, spectral_rmse_segments with seed.
                extra3 = compute_bootstrap_corridors_by_d(
                    cfg_prof,
                    solver_snapshot,
                    pconf=pconf,
                    n_boot=B,
                    percentile=p,
                    seed=seedB,
                    sigma_t=sigT,
                    sigma_r=sigR,
                    mode=modeB,
                    block_len=int(blkB),
                    quick_refit_maxfun=qref,
                )
                out.update(extra3)
            except NUMERICAL_FAULT_EXCEPTIONS:
                log.exception("PIPELINE [CORRIDORS d] BOOT failed (ignored).")
        _sync_theoretical_tr_from_nk_dict(cfg_eff, out, log=log, reason="corridor_profile_bloc_fin")
        if "profile_d_interval_nm" in extra:
            try:
                a0, a1 = extra["profile_d_interval_nm"]
                log.info(
                    "PIPELINE [CORRIDORS d] OK | d_interval=[%.6f, %.6f] nm | n_valid=%d",
                    float(a0),
                    float(a1),
                    int(np.asarray(extra.get("profile_d_values_nm", [])).size),
                )
            except (TypeError, ValueError, KeyError):
                log.info("PIPELINE [CORRIDORS d] OK (interval not parsable)")
        else:
            log.info("PIPELINE [CORRIDORS d] SKIP/EMPTY (no corridor returned).")
            log_coaching_corridor_pipeline_skip_empty()
    except NUMERICAL_FAULT_EXCEPTIONS:
        log.exception("Profiled d-corridors: failed (ignored).")

def _run_corridor_profile_with_optional_rerun(
    cfg: SplineOptConfig,
    out: dict,
    solver_snapshot: dict,
    log: logging.Logger,
    live_cb=None,
) -> None:
    """Run corridor profiling; optionally rerun from promoted optimum until stable (capped).

    Each pass calls ``_run_corridor_profile_block`` then ``_maybe_promote_best_corridor_refit``:

    if a point in the RMSE(d) profile beats the exported ``rmse``, ``out`` is promoted (``d_nm``, ``n_lam``,
    ``k_lam``, etc.) and the previous interval can be invalidated. As long as a promotion occurs and
    ``corridor_profile_d_rerun_after_promotion`` is true, the corridor is rerun with
    ``corridor_profile_d_base_source="dict"`` and the current snapshot as seed, until there
    is no more gain on the profile or ``corridor_profile_d_rerun_max_extra_passes`` is reached.

    Metadata: ``profile_d_promoted_pass1`` / ``profile_d_promoted_pass2`` preserve the historical
    semantics (1st and 2nd pass); ``profile_d_promoted_corridor_blocks`` gives the total number of
    corridor blocks executed in this sequence.
    """
    out.pop("profile_d_promoted", None)
    out.pop("profile_d_promoted_corridor_blocks", None)
    rerun_enabled = bool(getattr(cfg, "corridor_profile_d_rerun_after_promotion", True))
    max_extra = int(getattr(cfg, "corridor_profile_d_rerun_max_extra_passes", 6) or 0)
    max_extra = max(0, min(max_extra, 25))
    max_blocks = 1 + max_extra

    cfg_loop = cfg
    snap_loop = solver_snapshot
    block_index = 0
    promoted_second_block = False

    while True:
        if block_index > 0:
            out.pop("profile_d_promoted", None)
            out["profile_d_promoted_rerun_done"] = True
            out["profile_d_promoted_rerun_base_source"] = "dict"
            log.info(
                "PIPELINE [CORRIDORS d] Re-run after promotion (block %d/%d): corridor from promoted "
                "optimum (seed=d/rmse/n_lam/k_lam).",
                int(block_index + 1),
                int(max_blocks),
            )
            cfg_loop = cfg.replace(corridor_profile_d_base_source="dict")
            snap_loop = dict(out)

        _run_corridor_profile_block(cfg_loop, out, snap_loop, log, live_cb=live_cb)
        promoted = bool(out.get("profile_d_promoted", False))

        if block_index == 0:
            out["profile_d_promoted_pass1"] = promoted
            if promoted:
                try:
                    out["profile_d_promoted_pass1_d_nm"] = float(out.get("d_nm", float("nan")))
                except (TypeError, ValueError):
                    out["profile_d_promoted_pass1_d_nm"] = float("nan")
                try:
                    out["profile_d_promoted_pass1_rmse"] = float(out.get("rmse", float("nan")))
                except (TypeError, ValueError):
                    out["profile_d_promoted_pass1_rmse"] = float("nan")
        elif block_index == 1:
            promoted_second_block = promoted

        block_index += 1
        out["profile_d_promoted_corridor_blocks"] = int(block_index)

        need_rerun = promoted and rerun_enabled and block_index < max_blocks
        if not need_rerun:
            break

    out["profile_d_promoted_pass2"] = bool(promoted_second_block)

def _sync_promoted_corridor_seed_state(
    cfg: SplineOptConfig,
    out: dict,
    *,
    log: logging.Logger,
) -> None:
    """Rebuild minimal node/x state from promoted n(lambda), k(lambda), d.

    This keeps the rerun seed coherent after corridor promotion, even when the
    promoted point only provides spectral curves (no packed node vector).
    """
    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    n_lam = np.asarray(out.get("n_lam", []), dtype=np.float64).ravel()
    k_lam = np.asarray(out.get("k_lam", []), dtype=np.float64).ravel()
    d_nm = float(out.get("d_nm", float("nan")))
    if (
        lam.size < 2
        or n_lam.size != lam.size
        or k_lam.size != lam.size
        or not np.isfinite(d_nm)
        or (not np.all(np.isfinite(n_lam)))
    ):
        return
    sk = np.asarray(out.get("sigma_knots_L", out.get("sigma_knots", [])), dtype=np.float64).ravel()
    if sk.size < 2:
        return

    if "x" in out and isinstance(out["x"], (list, np.ndarray)):
        x_pack = np.asarray(out["x"], dtype=np.float64).ravel()
        if x_pack.size == 1 + 2 * sk.size:
            n_slice = x_pack[1 : 1 + sk.size]
            L_nodes = x_pack[1 + sk.size :]
            if getattr(cfg, "n_mono_band_nm", None) is None:
                n_nodes = n_slice.copy()
            else:
                try:
                    n_nodes = x_slice_n_to_physical_nodes(n_slice, sk, cfg.n_mono_band_nm)
                except NUMERICAL_FAULT_EXCEPTIONS:
                    n_nodes = n_slice.copy()
            out["n_nodes_physical"] = np.asarray(n_nodes, dtype=np.float64).ravel()
            out["L_nodes"] = np.asarray(L_nodes, dtype=np.float64).ravel()
            out["profile_d_promoted_seed_state"] = "exact_from_x_nodes"
            if "d_nm_seg_spline_sigma" in out:
                out["d_nm_seg_spline_sigma"] = float(out.get("d_nm", float("nan")))
            if "n_lam_seg_spline_sigma" in out:
                out["n_lam_seg_spline_sigma"] = np.asarray(out.get("n_lam", []), dtype=np.float64).ravel().copy()
            if "k_lam_seg_spline_sigma" in out:
                out["k_lam_seg_spline_sigma"] = np.asarray(out.get("k_lam", []), dtype=np.float64).ravel().copy()
            if "x_seg_spline_sigma" in out and isinstance(out.get("x_seg_spline_sigma"), np.ndarray):
                xa_old = np.asarray(out.get("x_seg_spline_sigma"), dtype=np.float64).ravel()
                if xa_old.size == x_pack.size:
                    out["x_seg_spline_sigma"] = x_pack.copy()
            log.info(
                "PIPELINE [CORRIDORS d] Promotion seed synchronized exactly from promoted x vector | K=%d | x_size=%d",
                int(sk.size),
                int(x_pack.size),
            )
            return

    sig = 1.0 / np.maximum(lam, 1e-30)
    ord_sig = np.argsort(sig)
    sig_sorted = np.asarray(sig[ord_sig], dtype=np.float64)
    n_sorted = np.asarray(n_lam[ord_sig], dtype=np.float64)
    k_sorted = np.asarray(k_lam[ord_sig], dtype=np.float64)
    if (
        sig_sorted.size < 2
        or (not np.all(np.isfinite(sig_sorted)))
        or (not np.all(np.isfinite(n_sorted)))
        or (not np.all(np.isfinite(k_sorted)))
    ):
        return

    n_nodes = np.interp(sk, sig_sorted, n_sorted)
    k_nodes = np.interp(sk, sig_sorted, k_sorted)
    k_nodes = np.maximum(np.asarray(k_nodes, dtype=np.float64), 1e-30)
    L_nodes = np.log(k_nodes)

    try:
        if cfg.n_mono_band_nm is None:
            n_slice = np.asarray(n_nodes, dtype=np.float64).copy()
        else:
            n_slice = physical_nodes_to_x_slice_n(
                np.asarray(n_nodes, dtype=np.float64),
                sk,
                cfg.n_mono_band_nm,
            )
    except NUMERICAL_FAULT_EXCEPTIONS:
        n_slice = np.asarray(n_nodes, dtype=np.float64).copy()

    x_pack = np.concatenate(
        (
            np.asarray([float(d_nm)], dtype=np.float64),
            np.asarray(n_slice, dtype=np.float64).ravel(),
            np.asarray(L_nodes, dtype=np.float64).ravel(),
        )
    )

    out["n_nodes_physical"] = np.asarray(n_nodes, dtype=np.float64).ravel()
    out["L_nodes"] = np.asarray(L_nodes, dtype=np.float64).ravel()
    out["x"] = np.asarray(x_pack, dtype=np.float64).ravel()
    out["profile_d_promoted_seed_state"] = "reconstructed_from_promoted_nk"
    if "d_nm_seg_spline_sigma" in out:
        out["d_nm_seg_spline_sigma"] = float(out.get("d_nm", float("nan")))
    if "n_lam_seg_spline_sigma" in out:
        out["n_lam_seg_spline_sigma"] = np.asarray(out.get("n_lam", []), dtype=np.float64).ravel().copy()
    if "k_lam_seg_spline_sigma" in out:
        out["k_lam_seg_spline_sigma"] = np.asarray(out.get("k_lam", []), dtype=np.float64).ravel().copy()
    if "x_seg_spline_sigma" in out and isinstance(out.get("x_seg_spline_sigma"), np.ndarray):
        xa_old = np.asarray(out.get("x_seg_spline_sigma"), dtype=np.float64).ravel()
        if xa_old.size == x_pack.size:
            out["x_seg_spline_sigma"] = np.asarray(x_pack, dtype=np.float64).ravel()
    log.info(
        "PIPELINE [CORRIDORS d] Promotion seed synchronized from promoted curves | K=%d | x_size=%d",
        int(sk.size),
        int(x_pack.size),
    )

def _maybe_promote_best_corridor_refit(
    cfg: SplineOptConfig,
    out: dict,
    extra: dict,
    log: logging.Logger,
) -> None:
    """Promote the best corridor refit to final output when strictly better.

    This keeps the original values in ``profile_d_promoted_from_*`` fields and
    only promotes when the gain is significant enough.
    """
    if not bool(getattr(cfg, "corridor_profile_d_promote_best_refit", True)):
        return
    status = str(extra.get("profile_d_status", "")).strip().lower()
    if status in {"", "failed", "manual_grid_empty"}:
        return

    d_vals = np.asarray(extra.get("profile_d_values_nm", []), dtype=np.float64).ravel()
    rm_vals = np.asarray(extra.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
    n_curves = np.asarray(extra.get("profile_d_n_curves", []), dtype=np.float64)
    k_curves = np.asarray(extra.get("profile_d_k_curves", []), dtype=np.float64)
    if d_vals.size == 0 or rm_vals.size != d_vals.size:
        return
    if n_curves.ndim != 2 or k_curves.ndim != 2:
        return
    if n_curves.shape[0] != d_vals.size or k_curves.shape[0] != d_vals.size:
        return

    finite_mask = np.isfinite(d_vals) & np.isfinite(rm_vals)
    if not np.any(finite_mask):
        return
    idx_valid = np.flatnonzero(finite_mask)
    idx_local = int(np.argmin(rm_vals[finite_mask]))
    idx_best = int(idx_valid[idx_local])
    best_d = float(d_vals[idx_best])
    best_rmse = float(rm_vals[idx_best])

    curr_rmse = float(out.get("rmse", float("nan")))
    min_gain = float(getattr(cfg, "corridor_profile_d_promote_min_rmse_gain", 1e-6) or 1e-6)
    if np.isfinite(curr_rmse):
        if not np.isfinite(best_rmse) or best_rmse >= (curr_rmse - min_gain):
            return

    best_n = np.asarray(n_curves[idx_best], dtype=np.float64).ravel()
    best_k = np.asarray(k_curves[idx_best], dtype=np.float64).ravel()
    if best_n.size == 0 or best_k.size == 0 or best_n.size != best_k.size:
        return
    if not (np.all(np.isfinite(best_n)) and np.all(np.isfinite(best_k))):
        return

    x_curves = extra.get("profile_d_x_curves", [])
    best_x = None
    if isinstance(x_curves, list) and len(x_curves) == d_vals.size:
        best_x = np.asarray(x_curves[idx_best], dtype=np.float64).ravel()

    out["profile_d_promoted"] = True
    out["profile_d_promoted_from_d_nm"] = float(out.get("d_nm", float("nan")))
    out["profile_d_promoted_from_rmse"] = curr_rmse if np.isfinite(curr_rmse) else None
    out["profile_d_promoted_to_d_nm"] = best_d
    out["profile_d_promoted_to_rmse"] = best_rmse
    out["profile_d_promoted_index"] = int(idx_best)

    out["d_nm"] = best_d
    out["rmse"] = best_rmse
    out["mse"] = float(max(best_rmse, 0.0) ** 2)
    out["n_lam"] = best_n
    out["k_lam"] = best_k
    out["x_encoding"] = "corridor_refit_fixed_d"

    if best_x is not None:
        out["x"] = np.concatenate(([float(best_d)], best_x))

    # Keep the scientific-corridor reference coherent after promotion.  The next
    # rerun uses ``corridor_profile_d_base_source='dict'``; if these fields keep
    # the pre-promotion polished values, the next block logs a huge seed/ref
    # mismatch and thresholds the new profile against the obsolete nominal RMSE.
    out["spectral_rmse_best_value"] = float(best_rmse)
    out["spectral_rmse_best_label"] = "Corridor_refit_fixed_d"
    out["spectral_rmse_best_source"] = "corridor_promotion"
    out["spectral_rmse_segments"] = float(best_rmse)
    out["spectral_rmse_seg_spline_sigma"] = float(best_rmse)
    out["d_nm_seg_spline_sigma"] = float(best_d)
    out["n_lam_seg_spline_sigma"] = np.asarray(best_n, dtype=np.float64).ravel().copy()
    out["k_lam_seg_spline_sigma"] = np.asarray(best_k, dtype=np.float64).ravel().copy()
    if best_x is not None:
        out["x_seg_spline_sigma"] = np.concatenate(([float(best_d)], best_x))

    out["profile_d_promoted_from_status"] = str(status)
    # The symmetrized interval centered on the old parabola is now mathematically invalid.
    # Remove it: a "rerun" will be required to report a valid uncertainty around the new value.
    out.pop("profile_d_interval_nm", None)
    _sync_promoted_corridor_seed_state(cfg, out, log=log)

    log.info(
        "PIPELINE [CORRIDORS d] Promotion: final output switched to best corridor refit | "
        "d %.6f -> %.6f nm | RMSE %s -> %.8f | idx=%d | "
        "AUDIT BUGFIX: after this corridor block, seek obligatorily "
        "« PIPELINE [MODELE_SPECTRAL_SYNC] OK » reason=corridor_profile_block_end "
        "(T_theo realigned on promoted n,k,d; absence = possible inconsistency between spectrum and n,k tab).",
        float(out.get("profile_d_promoted_from_d_nm", float("nan"))),
        float(best_d),
        (
            f"{float(out['profile_d_promoted_from_rmse']):.8f}"
            if out.get("profile_d_promoted_from_rmse") is not None
            else "n/a"
        ),
        float(best_rmse),
        int(idx_best),
    )

    log_index_spline_d_trace(
        log,
        "corridor: after promotion (d dict updated)",
        best_d,
        detail=(
            "d_before="
            + (
                f"{float(out['profile_d_promoted_from_d_nm']):.6f} nm"
                if out.get("profile_d_promoted_from_d_nm") is not None
                and np.isfinite(float(out["profile_d_promoted_from_d_nm"]))
                else "n/a"
            )
            + f" profile_idx={idx_best}"
        ),
    )

def worker_run_corridor_profile_after_nl_choice(
    cfg: SplineOptConfig,
    result: dict,
    stop_event: Event,
    progress_cb,
    live_cb=None,
) -> dict | None:
    log = logging.getLogger("CERTUS")
    if not isinstance(result, dict):
        return None
    out = dict(result)
    solver_snapshot = out.get("gui_solver_snapshot_for_corridors")
    if not isinstance(solver_snapshot, dict):
        solver_snapshot = dict(out)
    if stop_event and stop_event.is_set():
        return out
    progress_cb(5, "Corridors: preparing post-NL profiling...")
    log_index_spline_d_trace(
        log,
        "deferred/post-NL corridor: before d profiling",
        out.get("d_nm"),
        detail="Corridor snapshot used for rerun (can differ from profiling base if best_polished)",
    )
    _run_corridor_profile_with_optional_rerun(
        cfg,
        out,
        dict(solver_snapshot),
        log,
        live_cb=live_cb,
    )
    if stop_event and stop_event.is_set():
        return out
    log_index_spline_d_trace(
        log,
        "deferred/post-NL corridor: after profiling (dict out, before nk RMSE display mask)",
        out.get("d_nm"),
    )
    apply_rmse_fit_window_nk_nan_to_result(out, cfg.rmse_fit_lambda_nm)
    progress_cb(100, "Corridors: completed.")
    return out

