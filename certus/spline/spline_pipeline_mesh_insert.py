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



def insert_manual_sigma_nodes(
    cfg: SplineOptConfig,
    base_result: dict,
    stop_event: Event,
    extra_sigma_knots: np.ndarray,
    target_sigma_knots: np.ndarray | None = None,
    force_reopt: bool = False,
    progress_cb=None,
    live_cb=None,
) -> dict:
    """Insert one or more user-defined sigma knots and re-optimize locally.

    Standard mode only (no split sigma_knots_n / sigma_knots_L).
    Insertions remain guarded by RMSE checks. Explicit target-mesh reductions are
    accepted as long as the local polish returns a finite result, so manual knot
    deletions can be re-optimized without being rolled back solely because RMSE rises.
    Returns the updated result dict (or base_result unchanged on skip/rollback/fallback).
    """
    log = logging.getLogger("CERTUS")
    out = dict(base_result)  # shallow copy – keys replaced atomically on accept

    if "sigma_knots_n" in out or "sigma_knots_L" in out:
        _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="split_knot_mode")
        log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: split-knot mode detected.")
        return base_result

    sk = np.asarray(out.get("sigma_knots", []), dtype=np.float64).ravel()
    if sk.size < 2:
        _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="sigma_knots_too_small")
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] Skip: sigma_knots has < 2 elements.")
        return base_result

    target_raw = np.asarray(target_sigma_knots if target_sigma_knots is not None else [], dtype=np.float64).ravel()
    base_offset = float(out.get("substrate_n_offset", 0.0))
    cfg_offset = float(getattr(cfg, "substrate_n_offset", 0.0) or 0.0)
    offset_changed = abs(cfg_offset - base_offset) > 1e-12
    if target_raw.size > 0:
        if not np.all(np.isfinite(target_raw)):
            _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="target_sigma_not_finite")
            log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: target sigma knots contain non-finite values.")
            return base_result
        sk_new = np.unique(np.sort(target_raw))
        if sk_new.size < 2:
            _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="target_sigma_too_small")
            log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: target sigma knot count < 2.")
            return base_result
        sigma_lo = float(np.min(sk))
        sigma_hi = float(np.max(sk))
        tol = max(1e-12, 1e-8 * max(abs(sigma_lo), abs(sigma_hi), 1.0))
        if np.any(sk_new < (sigma_lo - tol)) or np.any(sk_new > (sigma_hi + tol)):
            _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="target_sigma_out_of_range")
            log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: target sigma knots out of base range.")
            return base_result
        if _should_skip_manual_insert_for_equal_mesh(
            sk_new,
            sk,
            offset_changed=offset_changed,
            force_reopt=force_reopt,
        ):
            _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="target_sigma_equals_base")
            log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: target sigma knots equal current mesh.")
            return base_result
        extra_sorted = np.asarray([], dtype=np.float64)
    else:
        extra_sorted = _validated_extra_sigma_knots(sk, extra_sigma_knots)
        if extra_sorted.size == 0:
            _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="no_valid_extra_sigma_knots")
            log.info("INDEX_SPLINE [MANUAL NODE INSERT] Skip: no valid extra sigma knots (duplicates or out of range).")
            return base_result
        sk_new = np.sort(np.concatenate([sk, extra_sorted]))

    mesh_summary = _sigma_mesh_change_summary_for_log(sk, sk_new)

    rmse_ref = float(out.get("rmse", float("inf")))
    # Use the best known RMSE as reference: polished value may be tighter than the solver dict RMSE.
    # This prevents accepting K+n results that regress vs the polished baseline.
    _best_polished_rmse = out.get("spectral_rmse_global_best_value") or out.get("spectral_rmse_polished_value")
    if _best_polished_rmse is not None:
        try:
            _bpr = float(_best_polished_rmse)
            if np.isfinite(_bpr) and _bpr < rmse_ref:
                rmse_ref = _bpr
        except (TypeError, ValueError):
            pass
    if not np.isfinite(rmse_ref):
        _log_spline_pipeline_json(log, "manual_node_insert_skip", seq="05b", reason="rmse_not_finite")
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] Skip: reference RMSE not finite.")
        return base_result

    K_before = int(sk.size)
    K_new = int(sk_new.size)

    # Snap sk_new to base knots when K is identical and positions match at floating-point level.
    # Lambda→sigma conversion in the dialog can shift sigma values by ~1e-12..1e-10.
    # Even a sub-epsilon shift can change n_mono_segment_flags (chain structure), causing
    # project_n_pwl_monotone_chains inside encode_physical_n_to_xi_n to modify the n values
    # and produce a grossly wrong x0 (RMSE×2 or worse).
    if target_raw.size > 0 and K_new == K_before and np.allclose(sk_new, sk, rtol=1e-9, atol=1e-11):
        sk_new = sk.copy()
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] sk_new snapped to base sk (K=%d, fp-level match).",
            K_before,
        )

    xb_sk = build_segment_optimizer_x_vector(out, cfg)
    if xb_sk is None:
        _log_spline_pipeline_json(
            log, "manual_node_insert_fallback", seq="05b", reason="build_segment_optimizer_failed"
        )
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] Fallback: cannot build x vector from result.")
        return base_result
    x_ref, _ = xb_sk

    try:
        n_phys = x_slice_n_to_physical_nodes(x_ref[1 : 1 + K_before], sk, cfg.n_mono_band_nm)
        L_nodes = np.asarray(x_ref[1 + K_before : 1 + 2 * K_before], dtype=np.float64).copy()
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        _log_spline_pipeline_json(log, "manual_node_insert_fallback", seq="05b", reason=f"decode_failed:{ex}")
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] Fallback: node decode failed: %s", ex)
        return base_result

    # ── WARM START: project current n(σ), k(σ) onto the new knot mesh ──────────
    # This is the single most critical step for RMSE stability during knot
    # insertion/removal.  We use PCHIP (Piecewise Cubic Hermite Interpolating
    # Polynomial) instead of CubicSpline because:
    #   • PCHIP is shape-preserving: it never overshoots between data points,
    #     so n_phys_new stays within [min(n_phys), max(n_phys)].
    #   • CubicSpline(bc_type='natural') can produce Runge-like oscillations
    #     that push n far outside the physical range (e.g., n=2.8 → 3.5),
    #     corrupting the initial guess and causing massive RMSE degradation.
    #   • For K=2 (minimum), PCHIP degenerates to linear (same as np.interp).
    # The except-fallback to np.interp handles exotic edge cases (NaN, K<2).
    try:
        n_phys_new = PchipInterpolator(sk, n_phys)(sk_new)
        L_nodes_new = PchipInterpolator(sk, L_nodes)(sk_new)
    except (ValueError, TypeError) as ex:
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] PCHIP warm start failed, fallback to linear: %s", ex)
        n_phys_new = np.interp(sk_new, sk, n_phys)
        L_nodes_new = np.interp(sk_new, sk, L_nodes)

    # Safety clip: even PCHIP can slightly exceed the data range at the edges
    # due to floating-point arithmetic.  Clamp to the original value range so
    # the encoder (physical_nodes_to_x_slice_n) never receives an outlier.
    n_lo, n_hi = float(np.min(n_phys)), float(np.max(n_phys))
    L_lo_data, L_hi_data = float(np.min(L_nodes)), float(np.max(L_nodes))
    n_phys_new = np.clip(n_phys_new, n_lo, n_hi)
    L_nodes_new = np.clip(L_nodes_new, L_lo_data, L_hi_data)

    log.debug(
        "INDEX_SPLINE [MANUAL NODE INSERT] warm-start | K %d -> %d | n_range=[%.4f, %.4f] | L_range=[%.4f, %.4f] | n_new_range=[%.4f, %.4f] | L_new_range=[%.4f, %.4f]",
        K_before,
        K_new,
        n_lo,
        n_hi,
        L_lo_data,
        L_hi_data,
        float(np.min(n_phys_new)),
        float(np.max(n_phys_new)),
        float(np.min(L_nodes_new)),
        float(np.max(L_nodes_new)),
    )

    try:
        bounds_new, x0_new, L_lo, L_hi = _bounds_x0_for_sigma_knots(cfg, sk_new)
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        _log_spline_pipeline_json(log, "manual_node_insert_fallback", seq="05b", reason=f"bounds_failed:{ex}")
        log.warning("INDEX_SPLINE [MANUAL NODE INSERT] Fallback: _bounds_x0_for_sigma_knots failed: %s", ex)
        return base_result

    # ── CONSTRUCT INITIAL GUESS x0 FOR L-BFGS-B ───────────────────────────────
    # x0 layout: [d_nm, ξ_n_0..ξ_n_{K-1}, L_0..L_{K-1}]
    #   • x0[0] = thickness d (nm), clipped to new bounds
    #   • x0[1:1+K] = n nodes encoded as ξ (sigmoid-reparameterized for monotonicity)
    #   • x0[1+K:1+2K] = ln(k) nodes, clipped to [L_lo, L_hi]
    x0_new[0] = float(np.clip(float(x_ref[0]), bounds_new[0, 0], bounds_new[0, 1]))
    x0_new[1 : 1 + K_new] = physical_nodes_to_x_slice_n(n_phys_new, sk_new, cfg.n_mono_band_nm)
    x0_new[1 + K_new : 1 + 2 * K_new] = np.clip(L_nodes_new, L_lo, L_hi)

    # ── ITERATION BUDGET ──────────────────────────────────────────────────────
    # The polish budget determines convergence depth.  For manual operations
    # (user clicking buttons in the dialog), we want deep convergence by default.
    # Workers (auto_add, auto_clean) override via manual_node_insert_polish_maxfun.
    nm_mf = getattr(cfg, "node_model_spectral_polish_maxfun", None)
    mf_base = int(nm_mf) if nm_mf is not None else int(cfg.polish_maxfun)
    # Manual node insertion is an explicit "advanced local polish" action from the UI:
    # use a much larger iteration budget than the standard mesh polish by default.
    mf_override = getattr(cfg, "manual_node_insert_polish_maxfun", None)
    if mf_override is not None:
        mf_ins = int(mf_override)
    else:
        mf_ins = int(max(2000, 4 * max(300, mf_base)))

    op_id = f"05b-{time.time_ns()}"

    _log_manual_insert_decision(
        log,
        event="manual_node_insert_attempt",
        op_id=op_id,
        decision="attempt",
        reason="polish_requested",
        K_before=K_before,
        K_after=K_new,
        rmse_ref=float(rmse_ref),
        rmse_cand=None,
        mesh_summary=mesh_summary,
        extra_sigma_knots=extra_sorted.tolist(),
        explicit_mesh_edit=bool(target_raw.size > 0),
        explicit_k_reduction=bool(target_raw.size > 0 and K_new < K_before),
        force_reopt=bool(force_reopt),
        maxfun=mf_ins,
    )
    delta_ns = float(out.get("substrate_n_offset", 0.0))
    log.debug(
        "INDEX_SPLINE [MANUAL NODE INSERT] attempt=%s | K=%d -> K=%d | extra_sigma=%s | RMSE_ref=%.8f | maxfun=%d | delta_ns=%+.6f | before_lambda=%s | after_lambda=%s | removed=%s | added=%s",
        op_id,
        K_before,
        K_new,
        np.array2string(extra_sorted, precision=6, separator=", "),
        rmse_ref,
        mf_ins,
        delta_ns,
        mesh_summary["mesh_before_lambda_summary"],
        mesh_summary["mesh_after_lambda_summary"],
        mesh_summary["mesh_removed_lambda_summary"],
        mesh_summary["mesh_added_lambda_summary"],
    )

    try:
        pack = _spectral_polish_node_mesh_profile(
            cfg,
            out,
            x0_new,
            sk_new,
            bounds_new,
            stop_event=stop_event,
            maxfun=mf_ins,
            progress_cb=progress_cb,
        )
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        _log_spline_pipeline_json(
            log,
            "manual_node_insert_fallback",
            seq="05b",
            op_id=op_id,
            reason=f"polish_exception:{ex}",
            K_before=K_before,
            K_after=K_new,
        )
        log.warning(
            "INDEX_SPLINE [MANUAL NODE INSERT] attempt=%s | Fallback: polish exception: %s",
            op_id,
            ex,
        )
        return base_result

    if pack is None:
        _log_spline_pipeline_json(
            log,
            "manual_node_insert_fallback",
            seq="05b",
            op_id=op_id,
            reason="polish_returned_None",
            K_before=K_before,
            K_after=K_new,
        )
        log.info(
            "INDEX_SPLINE [MANUAL NODE INSERT] attempt=%s | Fallback: polish returned None.",
            op_id,
        )
        return base_result

    rmse_cand_raw = pack.get("spectral_rmse")
    rmse_cand = float(rmse_cand_raw) if rmse_cand_raw is not None else float("inf")

    is_explicit_mesh_edit = target_raw.size > 0
    is_explicit_k_reduction = bool(is_explicit_mesh_edit and K_new < K_before)

    if not np.isfinite(rmse_cand):
        _log_manual_insert_decision(
            log,
            event="manual_node_insert_rejected",
            op_id=op_id,
            decision="reject",
            reason="rmse_candidate_not_finite",
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=None,
            mesh_summary=mesh_summary,
            extra_sigma_knots=extra_sorted.tolist(),
            explicit_mesh_edit=bool(is_explicit_mesh_edit),
            explicit_k_reduction=bool(is_explicit_k_reduction),
            force_reopt=bool(force_reopt),
        )
        log.warning(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | RMSE candidate non-finite - rollback.",
            op_id,
        )
        return base_result

    if (not is_explicit_k_reduction) and _spl_rmse_regression_exceeds_tolerance(cfg, rmse_ref, rmse_cand):
        _log_manual_insert_decision(
            log,
            event="manual_node_insert_rejected",
            op_id=op_id,
            decision="reject",
            reason="rmse_regression_exceeds_tolerance",
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=float(rmse_cand) if np.isfinite(rmse_cand) else None,
            mesh_summary=mesh_summary,
            extra_sigma_knots=extra_sorted.tolist(),
            explicit_mesh_edit=bool(is_explicit_mesh_edit),
            explicit_k_reduction=bool(is_explicit_k_reduction),
            force_reopt=bool(force_reopt),
            regression_abs=(float(rmse_cand - rmse_ref) if np.isfinite(rmse_cand) else None),
            tolerance_abs=float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5),
            tolerance_rel=float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0),
        )
        log.warning(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | RMSE regression exceeded tolerance - rollback.",
            op_id,
        )
        return base_result

    if is_explicit_k_reduction and rmse_cand > rmse_ref and not force_reopt:
        if _spl_rmse_regression_exceeds_tolerance(cfg, rmse_ref, rmse_cand):
            _log_manual_insert_decision(
                log,
                event="manual_node_insert_rejected",
                op_id=op_id,
                decision="reject",
                reason="explicit_k_reduction_regression_exceeds_tolerance",
                K_before=K_before,
                K_after=K_new,
                rmse_ref=float(rmse_ref),
                rmse_cand=float(rmse_cand) if np.isfinite(rmse_cand) else None,
                mesh_summary=mesh_summary,
                extra_sigma_knots=extra_sorted.tolist(),
                explicit_mesh_edit=bool(is_explicit_mesh_edit),
                explicit_k_reduction=True,
                force_reopt=bool(force_reopt),
                regression_abs=(float(rmse_cand - rmse_ref) if np.isfinite(rmse_cand) else None),
                tolerance_abs=float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5),
                tolerance_rel=float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0),
            )
            log.warning(
                "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | explicit K reduction exceeded RMSE tolerance - rollback.",
                op_id,
            )
            return base_result
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Explicit K reduction accepted within tolerance: attempt=%s | K %d -> %d | RMSE %.8f -> %.8f.",
            op_id,
            K_before,
            K_new,
            rmse_ref,
            rmse_cand,
        )

    if not is_explicit_mesh_edit and not _spl_rmse_improves_meaningfully(rmse_ref, rmse_cand):
        _log_manual_insert_decision(
            log,
            event="manual_node_insert_rejected",
            op_id=op_id,
            decision="reject",
            reason="no_meaningful_gain",
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=float(rmse_cand) if np.isfinite(rmse_cand) else None,
            mesh_summary=mesh_summary,
            extra_sigma_knots=extra_sorted.tolist(),
            explicit_mesh_edit=bool(is_explicit_mesh_edit),
            explicit_k_reduction=bool(is_explicit_k_reduction),
            force_reopt=bool(force_reopt),
        )
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | no meaningful RMSE gain - rollback.",
            op_id,
        )
        return base_result

    x_new = np.asarray(pack["x_best"], dtype=np.float64)
    n_lam_new = np.asarray(pack["n_lam"], dtype=np.float64)
    k_lam_new = np.asarray(pack["k_lam"], dtype=np.float64)
    d_new = float(pack["d_nm"])
    mse_new = float(pack.get("spectral_mse", 0.0))
    rmse_new = float(pack["spectral_rmse"])

    out["sigma_knots"] = sk_new
    out["n_seg"] = K_new - 1
    out["x"] = x_new
    out["n_nodes_physical"] = x_slice_n_to_physical_nodes(x_new[1 : 1 + K_new], sk_new, cfg.n_mono_band_nm)
    out["L_nodes"] = np.asarray(x_new[1 + K_new : 1 + 2 * K_new], dtype=np.float64).copy()
    out["n_lam"] = n_lam_new
    out["k_lam"] = k_lam_new
    out["d_nm"] = d_new
    out["mse"] = mse_new
    out["rmse"] = rmse_new
    out["nk_profile_interp"] = str(pack.get("profile_interp", "smooth"))
    # Clear stale polished RMSE fields: the mesh has changed, old polished values
    # no longer correspond to the current n/k parameterisation.
    for _stale_k in (
        "spectral_rmse_seg_spline_sigma",
        "spectral_rmse_polished_value",
        "spectral_rmse_global_best_value",
        "spectral_rmse_best_value",
        "spectral_rmse_polished_best_value",
        "spectral_rmse_polished_label",
        "spectral_rmse_global_best_label",
        "spectral_rmse_best_label",
        "spectral_rmse_global_best_source",
        "spectral_rmse_polished_source",
        "spectral_rmse_polished_status",
        "spectral_rmse_global_best_status",
        "n_lam_seg_spline_sigma",
        "k_lam_seg_spline_sigma",
        "d_nm_seg_spline_sigma",
    ):
        out.pop(_stale_k, None)
    n_sub_base = (
        np.asarray(
            getattr(cfg, "substrate_n_base", None) if getattr(cfg, "substrate_n_base", None) is not None else cfg.n_sub,
            dtype=np.float64,
        )
        .ravel()
        .copy()
    )
    out["n_sub_base"] = n_sub_base
    out["n_sub_effective"] = np.asarray(cfg.n_sub, dtype=np.float64).ravel().copy()
    out["substrate_n_offset"] = float(getattr(cfg, "substrate_n_offset", out.get("substrate_n_offset", 0.0)) or 0.0)
    _sync_theoretical_tr_from_nk_dict(cfg, out, log=log, reason="manual_sigma_insertion_ok")

    log_index_spline_d_trace(
        log, "manual sigma insertion accepted (+ spectral sync)", d_new, detail=f"RMSE {rmse_ref:.8f}->{rmse_new:.8f}"
    )

    _log_manual_insert_decision(
        log,
        event="manual_node_insert_accepted",
        op_id=op_id,
        decision="accept",
        reason="polish_converged",
        K_before=K_before,
        K_after=K_new,
        rmse_ref=float(rmse_ref),
        rmse_cand=float(rmse_new),
        mesh_summary=mesh_summary,
        extra_sigma_knots=extra_sorted.tolist(),
        explicit_mesh_edit=bool(is_explicit_mesh_edit),
        explicit_k_reduction=bool(is_explicit_k_reduction),
        force_reopt=bool(force_reopt),
        rmse_before=float(rmse_ref),
        rmse_after=rmse_new,
    )
    rmse_delta_final = float(rmse_new - rmse_ref) if np.isfinite(rmse_new) and np.isfinite(rmse_ref) else float("nan")
    acceptance_rule = "explicit_k_reduction_or_rmse_within_tolerance" if is_explicit_k_reduction else "rmse_regression_within_tolerance"
    audit_status = "accepted_worse_rmse" if np.isfinite(rmse_delta_final) and rmse_delta_final > 0.0 else "ok"
    human_status = "ACCEPTED (worse RMSE)" if audit_status == "accepted_worse_rmse" else "ACCEPTED"
    delta_ns_final = float(out.get("substrate_n_offset", 0.0))
    n_sub_eff_avg = float(np.mean(np.asarray(out.get("n_sub_effective", cfg.n_sub), dtype=np.float64).ravel()))
    log.info(
        "INDEX_SPLINE [MANUAL NODE INSERT] %s: attempt=%s | K %d -> %d | RMSE %.8f -> %.8f | d=%.4f nm | delta_ns=%+.6f | n_sub_eff=%.6f | before_lambda=%s | after_lambda=%s | removed=%s | added=%s | policy=%s | audit=%s",
        human_status,
        op_id,
        K_before,
        K_new,
        rmse_ref,
        rmse_new,
        d_new,
        delta_ns_final,
        n_sub_eff_avg,
        mesh_summary["mesh_before_lambda_summary"],
        mesh_summary["mesh_after_lambda_summary"],
        mesh_summary["mesh_removed_lambda_summary"],
        mesh_summary["mesh_added_lambda_summary"],
        acceptance_rule,
        audit_status,
    )

    if live_cb is not None:
        live_cb(out)

    return out

def insert_mwir_mid_sigma_node(
    cfg: SplineOptConfig,
    base_result: dict,
    stop_event: Event,
    progress_cb=None,
    live_cb=None,
) -> dict:
    """Insert one sigma node between sigma_knots[0] and sigma_knots[1] (MWIR refinement).

    Standard mode only (no split sigma_knots_n / sigma_knots_L).
    Accepts the insertion only if RMSE improves meaningfully; strict rollback otherwise.
    Returns the updated result dict (or base_result unchanged on skip/rollback/fallback).
    """
    sk = np.asarray(base_result.get("sigma_knots", []), dtype=np.float64).ravel()
    if sk.size < 2:
        return base_result
    sigma_mid = 0.5 * (float(sk[0]) + float(sk[1]))
    return insert_manual_sigma_nodes(
        cfg,
        base_result,
        stop_event,
        np.asarray([sigma_mid], dtype=np.float64),
        progress_cb=progress_cb,
        live_cb=live_cb,
    )

def worker_spline_mwir_insert_node(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: insert one MWIR sigma node (σ₀+σ₁)/2 and re-optimize.

    Called by the UI dialog after pipeline completion.
    Returns the updated result dict (accepted or rolled back), or None on critical failure.
    """
    log = logging.getLogger("CERTUS")
    try:
        return insert_mwir_mid_sigma_node(cfg, base_result, stop_event, progress_cb=progress_cb, live_cb=live_cb)
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        log.error("INDEX_SPLINE [MWIR NODE INSERT] worker unhandled exception: %s", ex, exc_info=True)
        return None

def worker_spline_manual_sigma_insert(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    extra_sigma_knots: np.ndarray | None = None,
    target_sigma_knots: np.ndarray | None = None,
    force_reopt: bool = False,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: insert user-defined sigma knots and re-optimize."""
    log = logging.getLogger("CERTUS")
    try:
        return insert_manual_sigma_nodes(
            cfg,
            base_result,
            stop_event,
            np.asarray(extra_sigma_knots if extra_sigma_knots is not None else [], dtype=np.float64),
            target_sigma_knots=np.asarray(target_sigma_knots, dtype=np.float64).ravel()
            if target_sigma_knots is not None
            else None,
            force_reopt=bool(force_reopt),
            progress_cb=progress_cb,
            live_cb=live_cb,
        )
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        log.error("INDEX_SPLINE [MANUAL NODE INSERT] worker unhandled exception: %s", ex, exc_info=True)
        return None

def worker_spline_auto_add_one_knot(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    target_sigma_knots: np.ndarray,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: test one insertion in every mid-gap and keep the best candidate."""
    import copy as _copy

    log = logging.getLogger("CERTUS")
    try:
        active_knots = np.unique(np.sort(np.asarray(target_sigma_knots, dtype=np.float64).ravel()))
        if active_knots.size < 2:
            log.info("INDEX_SPLINE [AUTO_ADD_ONE] skip: need at least two knots (K=%d)", int(active_knots.size))
            return _copy.deepcopy(base_result)

        rmse_ref = float(base_result.get("rmse", float("inf")))
        if not np.isfinite(rmse_ref):
            log.warning("INDEX_SPLINE [AUTO_ADD_ONE] abort: reference RMSE is non-finite")
            return _copy.deepcopy(base_result)

        candidate_maxfun = int(max(120, int(getattr(cfg, "auto_add_one_candidate_maxfun", 500) or 500)))
        cfg_eval = cfg.replace(manual_node_insert_polish_maxfun=candidate_maxfun)

        best_result = _copy.deepcopy(base_result)
        best_rmse = float("inf")
        best_gap_idx = -1
        best_kept_insertion = False
        n_gaps = int(max(0, active_knots.size - 1))
        # List all finished scan candidates to allow a top-K promotion during deep polish.
        scan_candidates: list[tuple[float, int, dict]] = []  # (rmse_scan, gap_idx, result_dict)

        log.info(
            "INDEX_SPLINE [AUTO_ADD_ONE] start | K=%d | gaps=%d | RMSE_ref=%.8f | candidate_maxfun=%d",
            int(active_knots.size),
            int(n_gaps),
            float(rmse_ref),
            int(candidate_maxfun),
        )

        # ── SCAN PHASE ─────────────────────────────────────────────────────────
        # For each gap between consecutive knots, insert a new knot at the
        # midpoint and run a fast (500 iter) polish to estimate RMSE gain.
        # Results are collected for top-K deep promotion afterwards.
        for gi in range(n_gaps):
            if stop_event.is_set():
                break

            s_lo = float(active_knots[gi])
            s_hi = float(active_knots[gi + 1])
            s_mid = 0.5 * (s_lo + s_hi)
            cand_knots = np.sort(np.concatenate([active_knots, np.asarray([s_mid], dtype=np.float64)]))

            if progress_cb is not None:
                p = 100.0 * float(gi) / float(max(n_gaps, 1))
                lam_mid_nm = 1.0 / max(s_mid, 1e-30)
                progress_cb(
                    float(np.clip(p, 0.0, 99.0)),
                    f"Auto add one: testing gap {gi + 1}/{n_gaps} (lambda_mid={lam_mid_nm:.2f} nm)",
                )

            # Scan probe: strip polished RMSE fields from the seed so the acceptance
            # test uses the solver RMSE (0.002402) not the tighter polished reference
            # (0.002196).  Suppressing live_cb prevents intermediate scan results
            # (partially converged, 240 iters) from appearing as a degradation in the GUI.
            _scan_seed = _copy.deepcopy(base_result)
            for _pk in (
                "spectral_rmse_global_best_value",
                "spectral_rmse_polished_value",
                "spectral_rmse_best_value",
                "spectral_rmse_polished_best_value",
            ):
                _scan_seed.pop(_pk, None)
            cand = insert_manual_sigma_nodes(
                cfg_eval,
                _scan_seed,
                stop_event,
                np.asarray([], dtype=np.float64),
                target_sigma_knots=cand_knots,
                force_reopt=True,
                progress_cb=None,
                live_cb=None,
            )
            if stop_event.is_set():
                break

            rmse_cand = float(cand.get("rmse", float("inf")))
            lam_mid_nm = 1.0 / max(s_mid, 1e-30)
            log.info(
                "INDEX_SPLINE [AUTO_ADD_ONE] gap=%d/%d | lambda_mid=%.3f nm | RMSE=%.8f | delta_ref=%+.8f",
                int(gi + 1),
                int(n_gaps),
                float(lam_mid_nm),
                float(rmse_cand),
                float(rmse_cand - rmse_ref) if np.isfinite(rmse_cand) else float("nan"),
            )

            if np.isfinite(rmse_cand):
                scan_candidates.append((float(rmse_cand), int(gi), _copy.deepcopy(cand)))
                if (not best_kept_insertion) or rmse_cand < (best_rmse - 1e-12):
                    best_rmse = float(rmse_cand)
                    best_result = _copy.deepcopy(cand)
                    best_gap_idx = int(gi)
                    best_kept_insertion = True

        if not best_kept_insertion:
            best_result = _copy.deepcopy(base_result)
            best_rmse = float(rmse_ref)

        # ── DEEP POLISH PHASE (TOP-K PROMOTION) ──────────────────────────────
        # The scan at 500 iterations may mis-rank candidates: a gap whose
        # true optimum is better may score worse with limited iterations.
        # We promote the top-K scan winners to a full deep polish (8000 iter)
        # and keep the absolute best result.
        top_k_deep = int(max(1, int(getattr(cfg, "auto_add_one_top_k_deep", 3) or 3)))
        if scan_candidates and not stop_event.is_set():
            scan_candidates.sort(key=lambda t: t[0])
            promoted = scan_candidates[:top_k_deep]
            deep_maxfun = int(
                max(
                    candidate_maxfun + 1,
                    int(
                        getattr(cfg, "auto_add_one_deep_polish_maxfun", None)
                        or int(getattr(cfg, "polish_maxfun", 8000) or 8000)
                    ),
                )
            )
            if deep_maxfun > candidate_maxfun and len(promoted) >= 1:
                cfg_deep = cfg.replace(manual_node_insert_polish_maxfun=deep_maxfun)

                deep_best_rmse = float("inf")
                deep_best_result = None
                deep_best_gap = best_gap_idx

                for j_pr, (scan_rmse, gap_idx_pr, cand_pr) in enumerate(promoted):
                    if stop_event.is_set():
                        break
                    if progress_cb is not None:
                        pct = 95.0 + 4.0 * (float(j_pr) / float(max(len(promoted), 1)))
                        progress_cb(
                            float(np.clip(pct, 0.0, 99.0)),
                            f"Auto add one: deep re-polish promoted {j_pr + 1}/{len(promoted)} "
                            f"(gap={gap_idx_pr + 1}, scan_rmse={scan_rmse:.6f})",
                        )
                    winner_knots = np.asarray(cand_pr.get("sigma_knots", []), dtype=np.float64)
                    _deep_seed = _copy.deepcopy(cand_pr)
                    # Strip polished RMSE fields so the deep polish acceptance test
                    # uses the solver RMSE, not an unreachable polished reference
                    # that would cause systematic false rejections.
                    for _pk_deep in (
                        "spectral_rmse_global_best_value",
                        "spectral_rmse_polished_value",
                        "spectral_rmse_best_value",
                        "spectral_rmse_polished_best_value",
                    ):
                        _deep_seed.pop(_pk_deep, None)
                    deep_result = insert_manual_sigma_nodes(
                        cfg_deep,
                        _deep_seed,
                        stop_event,
                        np.asarray([], dtype=np.float64),
                        target_sigma_knots=winner_knots,
                        force_reopt=True,
                        progress_cb=None,
                        live_cb=live_cb,
                    )
                    if stop_event.is_set():
                        break
                    deep_rmse = float(deep_result.get("rmse", float("inf")))
                    log.info(
                        "INDEX_SPLINE [AUTO_ADD_ONE] deep re-polish promoted=%d/%d | gap=%d | scan_rmse=%.8f | deep_rmse=%.8f",
                        int(j_pr + 1),
                        int(len(promoted)),
                        int(gap_idx_pr + 1),
                        float(scan_rmse),
                        float(deep_rmse),
                    )
                    if np.isfinite(deep_rmse) and deep_rmse < deep_best_rmse:
                        deep_best_rmse = deep_rmse
                        deep_best_result = deep_result
                        deep_best_gap = int(gap_idx_pr)

                if deep_best_result is not None and np.isfinite(deep_best_rmse):
                    log.info(
                        "INDEX_SPLINE [AUTO_ADD_ONE] deep top-K winner | gap=%d | RMSE %.8f -> %.8f",
                        int(deep_best_gap + 1),
                        float(best_rmse),
                        float(deep_best_rmse),
                    )
                    best_result = deep_best_result
                    best_rmse = deep_best_rmse
                    best_gap_idx = deep_best_gap

        if progress_cb is not None:
            progress_cb(100.0, f"Auto add one finished | RMSE={best_rmse:.6f}")

        if best_gap_idx >= 0:
            s_mid = 0.5 * float(active_knots[best_gap_idx] + active_knots[best_gap_idx + 1])
            lam_mid_nm = 1.0 / max(s_mid, 1e-30)
            log.info(
                "INDEX_SPLINE [AUTO_ADD_ONE] selected gap=%d/%d | lambda_mid=%.3f nm | RMSE %.8f -> %.8f",
                int(best_gap_idx + 1),
                int(n_gaps),
                float(lam_mid_nm),
                float(rmse_ref),
                float(best_rmse),
            )
            if best_rmse >= (rmse_ref - 1e-12):
                log.info(
                    "INDEX_SPLINE [AUTO_ADD_ONE] retaining best inserted candidate despite non-improving RMSE | delta_ref=%+.8f",
                    float(best_rmse - rmse_ref),
                )
        else:
            log.info(
                "INDEX_SPLINE [AUTO_ADD_ONE] no finite insertion candidate found | RMSE stays %.8f", float(rmse_ref)
            )

        return best_result
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        log.error("INDEX_SPLINE [AUTO_ADD_ONE] worker unhandled exception: %s", ex, exc_info=True)
        return None

def _sensitivity_rank_inner_indices(
    cfg: "SplineOptConfig",
    active_knots: np.ndarray,
    best_result_out: dict,
    K: int,
    inner_indices: list[int],
    top_n_sensitivity: int,
    tolerance: float,
    strict_tol_mode: bool,
    log: logging.Logger,
    step: int,
) -> list[int]:
    """Rank inner knot indices by no-refit RMSE sensitivity and return the top-N shortlist."""
    from certus.spline.spline_objective import nk_from_x_pwlnk

    lam_raw = getattr(cfg, "lam_nm", None)
    lam_full = (
        np.asarray(lam_raw, dtype=np.float64).ravel()
        if lam_raw is not None
        else np.asarray([], dtype=np.float64)
    )
    d_nm_cur = float(best_result_out.get("d_nm", 0.0))
    n_phys_cur = np.asarray(best_result_out.get("n_nodes_physical", []), dtype=np.float64).ravel()
    L_nodes_cur = np.asarray(best_result_out.get("L_nodes", []), dtype=np.float64).ravel()
    can_rank = (
        n_phys_cur.size == K
        and L_nodes_cur.size == K
        and lam_full.size > 2
        and np.isfinite(d_nm_cur)
        and hasattr(cfg, "k_clip_lo")
        and hasattr(cfg, "k_clip_hi")
        and hasattr(cfg, "n_mono_band_nm")
    )
    if not can_rank:
        log.debug(
            "INDEX_SPLINE [AUTO_CLEAN] step=%d sensitivity ranking skipped | can_rank=%s | size_n=%d | size_L=%d | lam=%d | d_finite=%s",
            int(step + 1), str(can_rank), int(n_phys_cur.size), int(L_nodes_cur.size),
            int(lam_full.size), str(np.isfinite(d_nm_cur)),
        )
        return inner_indices

    sensitivity_scores: list[tuple[int, float]] = []
    for i_cand in inner_indices:
        sk_reduced = np.delete(active_knots, i_cand)
        try:
            n_reduced = PchipInterpolator(active_knots, n_phys_cur)(sk_reduced)
            L_reduced = PchipInterpolator(active_knots, L_nodes_cur)(sk_reduced)
        except (ValueError, TypeError):
            n_reduced = np.interp(sk_reduced, active_knots, n_phys_cur)
            L_reduced = np.interp(sk_reduced, active_knots, L_nodes_cur)
        n_slice = physical_nodes_to_x_slice_n(n_reduced, sk_reduced, cfg.n_mono_band_nm)
        x_nodes_red = np.concatenate((n_slice, L_reduced))
        x_full_red = np.concatenate((np.asarray([d_nm_cur], dtype=np.float64), x_nodes_red))
        try:
            n_lam_red, k_lam_red = nk_from_x_pwlnk(
                x_full_red, lam_full, sk_reduced,
                cfg.k_clip_lo, cfg.k_clip_hi, sig_pre=None,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=str(cfg.nk_profile_interp or "smooth"),
            )
            _, rmse_norefit = spectral_mse_rmse_masked_from_nk(
                cfg, best_result_out, lam_full,
                np.asarray(n_lam_red, dtype=np.float64).ravel(),
                np.asarray(k_lam_red, dtype=np.float64).ravel(),
                d_nm_cur,
            )
            sensitivity_scores.append((i_cand, float(rmse_norefit)))
        except NUMERICAL_FAULT_EXCEPTIONS:
            sensitivity_scores.append((i_cand, float("inf")))

    sensitivity_scores.sort(key=lambda t: t[1])
    _strict_default = 2.0e-5
    _loose_default = max(5.0e-5, 1.0 * float(max(tolerance, 0.0)))
    _default_margin = _strict_default if strict_tol_mode else _loose_default
    shortlist_margin_abs = float(
        getattr(cfg, "auto_clean_sensitivity_shortlist_margin_abs", _default_margin) or _default_margin
    )
    finite_scores = [(i, s) for i, s in sensitivity_scores if np.isfinite(s)]
    if finite_scores:
        best_score = float(finite_scores[0][1])
        shortlisted = [i for i, s in finite_scores if float(s) <= (best_score + float(shortlist_margin_abs))]
        if shortlisted:
            result = shortlisted[:top_n_sensitivity]
        else:
            result = [i for i, _ in finite_scores[:top_n_sensitivity]]
    else:
        result = [i for i, _ in sensitivity_scores[:top_n_sensitivity]]
    log.debug(
        "INDEX_SPLINE [AUTO_CLEAN] step=%d sensitivity ranking | K=%d | top_%d=%s | scores=%s",
        int(step + 1), int(K), int(top_n_sensitivity), str(result),
        ", ".join(f"{i}:{s:.6f}" for i, s in sensitivity_scores[:top_n_sensitivity]),
    )
    return result

def _build_local_pull_variants(
    knots: np.ndarray,
    removed_idx: int,
    pull_enabled: bool,
    pull_ratios: list[float],
) -> list[tuple[str, np.ndarray]]:
    """Build candidate knot sets after removal, optionally pulling local neighbors inward.

    Extreme knots are never moved; only non-extreme neighbors around the removed knot
    can be shifted toward the removed position.
    """
    base = np.delete(np.asarray(knots, dtype=np.float64).ravel(), int(removed_idx))
    variants: list[tuple[str, np.ndarray]] = [("baseline", base)]
    if (not pull_enabled) or (not pull_ratios):
        return variants

    K0 = int(knots.size)
    if removed_idx <= 0 or removed_idx >= (K0 - 1):
        return variants

    left = float(knots[removed_idx - 1])
    rem = float(knots[removed_idx])
    right = float(knots[removed_idx + 1])
    can_move_left = (removed_idx - 1) > 0
    can_move_right = (removed_idx + 1) < (K0 - 1)
    if (not can_move_left) and (not can_move_right):
        return variants

    span = max(float(knots[-1] - knots[0]), 1e-12)
    eps = max(1e-12, 1e-6 * span)

    def _apply_pull(base_knots: np.ndarray, r_left: float, r_right: float, tag: str) -> None:
        cand = base_knots.copy()
        l_idx = removed_idx - 1
        r_idx = removed_idx

        if can_move_left and r_left > 0.0:
            left_new = left + float(r_left) * (rem - left)
            left_prev = float(knots[removed_idx - 2]) if (removed_idx - 2) >= 0 else -float("inf")
            left_upper = float(cand[r_idx]) - eps
            left_new = max(left_new, left_prev + eps)
            left_new = min(left_new, left_upper)
            cand[l_idx] = left_new

        if can_move_right and r_right > 0.0:
            right_new = right - float(r_right) * (right - rem)
            right_next = float(knots[removed_idx + 2]) if (removed_idx + 2) < K0 else float("inf")
            right_lower = float(cand[l_idx]) + eps
            right_new = min(right_new, right_next - eps)
            right_new = max(right_new, right_lower)
            cand[r_idx] = right_new

        if not np.all(np.isfinite(cand)):
            return
        if np.any(np.diff(cand) <= 0.0):
            return

        is_dup = any(np.allclose(prev_knots, cand, rtol=0.0, atol=eps) for _, prev_knots in variants)
        if is_dup:
            return
        variants.append((tag, cand.copy()))

    for ratio in pull_ratios:
        _apply_pull(base, float(ratio), float(ratio), f"neighbor_pull_sym_r{ratio:.2f}")
        if can_move_left:
            _apply_pull(base, float(ratio), 0.0, f"neighbor_pull_left_r{ratio:.2f}")
        if can_move_right:
            _apply_pull(base, 0.0, float(ratio), f"neighbor_pull_right_r{ratio:.2f}")

    return variants

def _build_local_refine_variants(
    knots: np.ndarray,
    removed_idx: int,
    seed_knots: np.ndarray,
    pull_enabled: bool,
    local_refine_enabled: bool,
    local_refine_rel_step: float,
) -> list[tuple[str, np.ndarray]]:
    """Small 2D local grid around removed-gap neighbors (conditional, low-cost)."""
    if not (pull_enabled and local_refine_enabled):
        return []

    K0 = int(knots.size)
    if removed_idx <= 0 or removed_idx >= (K0 - 1):
        return []

    can_move_left = (removed_idx - 1) > 0
    can_move_right = (removed_idx + 1) < (K0 - 1)
    if (not can_move_left) and (not can_move_right):
        return []

    base = np.asarray(seed_knots, dtype=np.float64).ravel().copy()
    l_idx = removed_idx - 1
    r_idx = removed_idx
    if base.size <= r_idx:
        return []

    left_prev = float(knots[removed_idx - 2]) if (removed_idx - 2) >= 0 else -float("inf")
    right_next = float(knots[removed_idx + 2]) if (removed_idx + 2) < K0 else float("inf")
    span = max(float(knots[-1] - knots[0]), 1e-12)
    eps = max(1e-12, 1e-6 * span)

    local_gap = float(base[r_idx] - base[l_idx])
    if not np.isfinite(local_gap) or local_gap <= 0.0:
        return []
    step = float(np.clip(local_refine_rel_step * local_gap, eps, 0.25 * local_gap))

    deltas = (-step, 0.0, step)
    out: list[tuple[str, np.ndarray]] = []
    for d_left in deltas:
        for d_right in deltas:
            if abs(d_left) < 0.5 * eps and abs(d_right) < 0.5 * eps:
                continue
            cand = base.copy()
            if can_move_left:
                cand[l_idx] = float(cand[l_idx] + d_left)
            if can_move_right:
                cand[r_idx] = float(cand[r_idx] + d_right)

            if can_move_left:
                cand[l_idx] = max(cand[l_idx], left_prev + eps)
            if can_move_right:
                cand[r_idx] = min(cand[r_idx], right_next - eps)
            cand[l_idx] = min(cand[l_idx], cand[r_idx] - eps)
            cand[r_idx] = max(cand[r_idx], cand[l_idx] + eps)

            if not np.all(np.isfinite(cand)):
                continue
            if np.any(np.diff(cand) <= 0.0):
                continue

            dup = any(np.allclose(prev, cand, rtol=0.0, atol=eps) for _, prev in out)
            if dup:
                continue
            out.append((f"neighbor_pull_refine_dl{d_left:+.3e}_dr{d_right:+.3e}", cand.copy()))

    return out

