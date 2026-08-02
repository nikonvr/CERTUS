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
    _interpolate_along_sigma,
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



def _apply_k_floor_to_result(
    cfg: "SplineOptConfig",
    out: dict,
    log: logging.Logger,
) -> None:
    """Enforce k >= k_clip_lo on result dict, with optional knot insertion and RMSE recomputation."""
    _rmse_before_kfloor = float(out.get("rmse", float("nan")))
    _sk_out = np.asarray(out.get("sigma_knots_L", out.get("sigma_knots", [])), dtype=np.float64).ravel()
    _LL_out = np.asarray(out.get("L_nodes", []), dtype=np.float64).ravel()

    if _sk_out.size < 2 or _LL_out.size != _sk_out.size:
        return

    _sk_f, _LL_f, _kf_mod = enforce_k_floor_on_nodes(_sk_out, _LL_out, k_floor=float(cfg.k_clip_lo))
    if not _kf_mod:
        return

    log.info(
        "k_floor enforce (final): %d nodes -> %d nodes (k_floor=%.1e)",
        int(_sk_out.size), int(_sk_f.size), float(cfg.k_clip_lo),
    )
    out["L_nodes"] = _LL_f
    out["post_s3_k_floor_applied"] = True
    out["post_s3_k_floor_nodes_before"] = int(_sk_out.size)
    out["post_s3_k_floor_nodes_after"] = int(_sk_f.size)
    out["post_s3_k_floor_rmse_before"] = (
        float(_rmse_before_kfloor) if np.isfinite(_rmse_before_kfloor) else None
    )

    if _sk_f.size != _sk_out.size:
        _n_phys_old = np.asarray(out.get("n_nodes_physical", []), dtype=np.float64).ravel()
        _skn_src = np.asarray(
            out.get("sigma_knots_n", out.get("sigma_knots", _sk_out)), dtype=np.float64,
        ).ravel()
        if _n_phys_old.size == _skn_src.size:
            out["n_nodes_physical"] = np.interp(_sk_f, _skn_src, _n_phys_old)
        else:
            log.warning(
                "k_floor insert: n_nodes_physical size (%d) != sigma_knots_n (%d) - n not re-sampled",
                int(_n_phys_old.size), int(_skn_src.size),
            )
        if "sigma_knots_L" in out:
            out["sigma_knots_L"] = _sk_f
        else:
            out["sigma_knots"] = _sk_f
        out.pop("x", None)

    # Recompute k_lam and spectra
    lam_out = np.asarray(out.get("lam_nm", cfg.lam_nm), dtype=np.float64).ravel()
    sig_out = 1.0 / np.maximum(lam_out, 1e-30)
    # Reconstruire k_lam avec L'INTERPOLATION DU MODELE, pas systematiquement en
    # lineaire par morceaux. np.interp etait code en dur ici, alors que le mode par
    # defaut est "smooth" des K >= 4 : le k_lam reecrit dans le resultat differait de
    # celui que l'objectif avait reellement utilise pour l'ajustement.
    L_lam_out = _interpolate_along_sigma(
        sig_out, _sk_f, _LL_f, str(getattr(cfg, "nk_profile_interp", "smooth") or "smooth")
    )
    k_lam_out = np.exp(L_lam_out)
    lo_k = max(float(cfg.k_clip_lo), K_MIN_PHYS)
    np.clip(k_lam_out, lo_k, float(cfg.k_clip_hi), out=k_lam_out)
    out["k_lam"] = k_lam_out

    n_lam_out = np.asarray(out.get("n_lam", []), dtype=np.float64).ravel()
    if n_lam_out.size == lam_out.size:
        d_o = float(out.get("d_nm", float("nan")))
        n_sub_o = np.asarray(cfg.n_sub, dtype=np.float64).ravel()
        if n_sub_o.size == lam_out.size and np.isfinite(d_o):
            if cfg.t_is_ratio:
                out["t_theo"] = _ratio_theoretical_from_nk(lam_out, n_lam_out, k_lam_out, d_o, n_sub_o)
            else:
                out["t_theo"] = _transmittance_absolute_from_nk(lam_out, n_lam_out, k_lam_out, d_o, n_sub_o)
            if cfg.r_exp is not None:
                if cfg.t_is_ratio:
                    out["r_theo"] = _reflectance_ratio_theoretical_from_nk(
                        lam_out, n_lam_out, k_lam_out, d_o, n_sub_o)
                else:
                    out["r_theo"] = _reflectance_absolute_backside_from_nk(
                        lam_out, n_lam_out, k_lam_out, d_o, n_sub_o)
            mgf = build_spline_objective_masked_grid(cfg)
            if mgf is not None:
                lam_f, _, n_sub_f_mg, w_f, inv_npix, t_exp_f, r_exp_f = mgf
                n_sub_eff_mg = np.asarray(n_sub_f_mg, dtype=np.float64)
                nlf = np.interp(lam_f, lam_out, n_lam_out)
                klf = np.interp(lam_f, lam_out, k_lam_out)
                m_new = spline_objective_mse_on_masked_grid(
                    cfg, lam_f=lam_f, n_sub_f=n_sub_eff_mg, w=w_f,
                    inv_npix=inv_npix, t_exp_f=t_exp_f, r_exp_f=r_exp_f,
                    n_l=nlf, k_l=klf, d=d_o,
                )
                out["mse"] = float(m_new)
                out["rmse"] = float(np.sqrt(max(m_new, 0.0)))

    out["post_s3_k_floor_rmse_after"] = float(out.get("rmse", float("nan")))
    _log_spline_pipeline_json(
        log, "worker_k_floor_enforced", seq="07b",
        K_nodes_before=int(_sk_out.size), K_nodes_after=int(_sk_f.size),
        k_floor=float(cfg.k_clip_lo),
        rmse_before_kfloor=_rmse_before_kfloor if np.isfinite(_rmse_before_kfloor) else None,
        rmse_after=float(out["rmse"]),
    )
    log.info(
        "PIPELINE [07b] k_floor enforce | nodes %d->%d | RMSE %.6f -> %.6f",
        int(_sk_out.size), int(_sk_f.size),
        _rmse_before_kfloor if np.isfinite(_rmse_before_kfloor) else float("nan"),
        float(out["rmse"]),
    )

def _run_sigma_mesh_polish(
    cfg: "SplineOptConfig",
    out: dict,
    log: logging.Logger,
    coord: "_WorkerProgressCoordinator",
    stop_event: "Event | None",
) -> None:
    """Run sigma-mesh cubic spline polish (step 07c) on the result dict in-place."""
    # Clear stale polish keys
    for _k in (
        "spectral_rmse_seg_spline_sigma", "n_lam_seg_spline_sigma",
        "k_lam_seg_spline_sigma", "d_nm_seg_spline_sigma", "x_seg_spline_sigma",
        "spectral_rmse_seg_pwl", "n_lam_seg_pwl", "k_lam_seg_pwl",
        "d_nm_seg_pwl", "x_seg_pwl",
    ):
        out.pop(_k, None)

    log.info("PIPELINE [07c] sigma-mesh polish - single cubic sigma-spline pass (same x0 as segmented solver).")

    if not bool(getattr(cfg, "node_mesh_spectral_polish_enabled", True)):
        log.info(
            "PIPELINE [07c] SKIP: node_mesh_spectral_polish_enabled=False. "
            "SMART COACHING: The final mesh polish (L-BFGS-B cubic smoothing) was skipped. "
            "If your final metric (RMSE) is poor but intermediate models were good, enable 'node_mesh_spectral_polish_enabled' for a final holistic optimization."
        )
        coord.emit(82, "sigma mesh polish disabled - continuing.")
        return

    xb_sk = build_segment_optimizer_x_vector(out, cfg)
    if xb_sk is None:
        log.warning(
            "PIPELINE [07c] POLISH FAILED: Unable to build [d, n nodes, ln k nodes] optimization vector. "
            "SMART COACHING: Your intermediate spline failed to resolve physically valid 'n_nodes_physical'. "
            "Check for extremely restrictive d bounds or divergent thickness targets."
        )
        coord.emit(82, "Mesh polish impossible (x vector) - continuing.")
        return

    if stop_event is not None and stop_event.is_set():
        log.info("PIPELINE [07c] SKIP: mesh polish aborted because UI cancel event was triggered.")
        coord.emit(82, "Stop before mesh polish - continuing.")
        return

    xb, sk_pol = xb_sk
    xa_dbg = out.get("x")
    if xa_dbg is not None:
        xa_a = np.asarray(xa_dbg, dtype=np.float64).ravel()
        if xa_a.size == 1 + 2 * int(sk_pol.size):
            _src_x0 = "x vector from segmental solver (direct reuse)"
        else:
            _src_x0 = "reconstruction from d_nm, n_nodes_physical, L_nodes (x solver size != 1+2K)"
    else:
        _src_x0 = "reconstruction from d_nm, n_nodes_physical, L_nodes (no x output)"

    bounds_b, _, _, _ = _bounds_x0_for_sigma_knots(cfg, sk_pol)
    x0c = clip_to_bounds(
        np.asarray(xb, dtype=np.float64).copy(), bounds_b[:, 0], bounds_b[:, 1],
    )
    nm_mf = getattr(cfg, "node_model_spectral_polish_maxfun", None)
    mf_pol = int(nm_mf) if nm_mf is not None else int(cfg.polish_maxfun)
    mf_pol = max(300, mf_pol)

    log.info(
        "PIPELINE [07c] Common start | K=%d sigma knots | source=%s | d(started)=%.6f nm | "
        "node_model_spectral_polish_maxfun->effective maxfun=%d (floor 300) | stop_event=%s",
        int(sk_pol.size), _src_x0, float(x0c[0]), mf_pol,
        "active" if (stop_event is not None and stop_event.is_set()) else "inactive",
    )
    coord.emit(76, "Spectral mesh polish: cubic spline sigma...")
    suf = "seg_spline_sigma"
    x_polish = np.asarray(x0c, dtype=np.float64).copy()

    pack = _spectral_polish_node_mesh_profile(
        cfg, out, x_polish, sk_pol, bounds_b,
        stop_event=stop_event, maxfun=mf_pol, progress_cb=coord.scoped(76, 92),
    )
    if pack is not None:
        out[f"n_lam_{suf}"] = pack["n_lam"]
        out[f"k_lam_{suf}"] = pack["k_lam"]
        out[f"d_nm_{suf}"] = float(pack["d_nm"])
        out[f"x_{suf}"] = pack["x_best"]
        out[f"spectral_rmse_{suf}"] = pack["spectral_rmse"]
        log.info(
            "PIPELINE [07c] Storing result %s | spectral_rmse_%s=%s | d_nm_%s=%.6f nm",
            suf, suf,
            f"{float(pack['spectral_rmse']):.8f}"
            if pack.get("spectral_rmse") is not None and np.isfinite(float(pack["spectral_rmse"]))
            else "n/a",
            suf, float(pack["d_nm"]),
        )
    else:
        log.info(
            "PIPELINE [07c] Spline sigma pass: no packets returned (empty mask, stop or internal error).",
        )
    coord.emit(92, "sigma mesh polish completed - RMSE synthesis.")

def worker_spline_optimization(cfg: SplineOptConfig, stop_event: Event, progress_cb, live_cb=None) -> dict | None:
    """Orchestrates the full spline pipeline (SOL2 -> post-processing).

    **Inputs**

        ``cfg``: spectral configuration and budgets (see ``SplineOptConfig``); ``x0`` / Smart Init

        already integrated by ``make_bounds_and_x0`` during internal worker steps.

        ``stop_event``: cooperative cancellation (threading ``Event``).

        ``progress_cb``: ``Callable[[int, str], None]`` - global progress in **centi-percent**

        ``0..10000`` (``10000`` = 100 %) and UI label (see ``_WorkerProgressCoordinator``).

        ``live_cb``: optional; receives ``dict`` snapshots (see ``snapshot_result_with_rmse_fit_meta``)

        for real-time curves / metrics refresh.

    **Output**

        Final result ``dict`` (``rmse``, ``mse``, ``n_lam``, ``k_lam``, ``d_nm``,

        cubic sigma-spline mesh polish ``*_seg_spline_sigma``, ``log10k_*`` corridor, etc.) or ``None``.

    **Steps** (summary): SOL2 (local L-BFGS-B), fixed mesh,

    ``k`` floor, sigma-mesh polish (cubic spline), spectral RMSE synthesis.

    """

    from certus.spline.spline_workers import _run_single_spline_stage

    log = logging.getLogger("CERTUS")

    enforce_local_optimization_policy(cfg)

    coord = _WorkerProgressCoordinator(progress_cb)

    t_worker = time.perf_counter()

    # Watermark: tracked the best observed RMSE across all pipeline stages.

    _wm_best_rmse = float("inf")

    _wm_best_stage = "init"

    def _wm_update(rmse_val: float, stage_name: str) -> None:

        nonlocal _wm_best_rmse, _wm_best_stage

        if np.isfinite(rmse_val) and rmse_val < _wm_best_rmse:
            _wm_best_rmse = float(rmse_val)

            _wm_best_stage = str(stage_name)

    (
        lam_arr,
        _k_mesh,
        _nseg_mesh,
        _dim_sol2,
        _lam_min,
        _lam_max,
    ) = _pipeline_mesh_dimensions(cfg)

    _log_worker_start_payload(
        log,
        cfg,
        lam_arr=lam_arr,
        k_mesh=_k_mesh,
        nseg_mesh=_nseg_mesh,
        lam_min=_lam_min,
        lam_max=_lam_max,
    )

    log.info(
        "PIPELINE [01/09] Starting INDEX_SPLINE worker | %d points lambda | d in [%.4f, %.4f] | %s | delta_ns=%+.6f",
        int(lam_arr.size),
        float(cfg.d_lo),
        float(cfg.d_hi),
        str(getattr(cfg.data_type, "name", cfg.data_type)),
        float(getattr(cfg, "substrate_n_offset", 0.0) or 0.0),
    )

    # SOL 2: local L-BFGS-B fixed knots (dim = d + K*n + K*L)

    coord.emit(0, f"SOL 2: local optimization ({_dim_sol2} vars, fixed knots, K_sigma={_k_mesh})...")

    # Do not clear ``smart_init_manual_force_restart`` here: ``_run_single_spline_stage`` reads it

    # for FACTUAL tracing (dialog RMSE vs first worker cost) and resets it to False after use.

    if getattr(cfg, "smart_init_manual_force_restart", False):
        log.info(
            "PIPELINE [02/09] Manual Smart Init: SOL2 - FACTUAL tracing on worker side (comparison of declared / recalculated RMSE)."
        )

    res2, _ = _run_single_spline_stage(
        cfg,
        stop_event,
        coord.scoped(0, 26),
        live_cb=live_cb,
        pipeline_seq="02_SOL2",
        fatal_finish=coord.finish,
    )

    if res2 is None:
        coord.finish("Stop  no usable sample")

        return None

    _wm_update(float(res2["rmse"]), "SOL2")

    # Log summary concisely with substrate info
    delta_ns_sol2 = float(res2.get("substrate_n_offset", 0.0))
    n_sub_eff_sol2 = float(np.mean(np.asarray(res2.get("n_sub_effective", cfg.n_sub), dtype=np.float64).ravel()))
    log.info(
        "PIPELINE [02/09] SOL2 (Fixed Knots, %d vars, K=%d) finished | RMSE=%.6f | d=%.4f nm | delta_ns=%+.6f | n_sub_eff=%.6f",
        _dim_sol2,
        _k_mesh,
        float(res2["rmse"]),
        float(res2["d_nm"]),
        delta_ns_sol2,
        n_sub_eff_sol2,
    )

    log_index_spline_d_trace(log, "pipeline: after SOL2 (fixed mesh solution)", res2.get("d_nm"))

    _log_spline_pipeline_json(
        log,
        "worker_after_sol2",
        seq="02",
        rmse=float(res2["rmse"]),
        d_nm=float(res2["d_nm"]),
        x_encoding=str(res2.get("x_encoding", "")),
        stage_repli_local=bool(res2.get("stage_repli_local", False)),
        nfev_local=int(res2.get("nit_polish", 0)),
    )

    _log_index_spline_best_config(log, res2, res2["rmse"], title="SOL 2 (Fixed Knots)")

    if live_cb is not None:
        live_cb(snapshot_result_with_rmse_fit_meta(cfg, res2))

    _stop_snapshot = _stop_with_snapshot_if_requested(
        stop_event,
        coord,
        "User stop after SOL 2.",
        cfg,
        res2,
    )
    if _stop_snapshot is not None:
        return _stop_snapshot

    # Visual pause: live_cb already refreshed the plot; UI pacing is handled in _on_live_update.

    # Worker continues without blocking here.

    sol_spline = res2
    log.info("PIPELINE [03/09] Legacy free-knot stage removed from pipeline; continuing from SOL2 baseline.")

    if live_cb is not None:
        live_cb(snapshot_result_with_rmse_fit_meta(cfg, sol_spline))

    _stop_snapshot = _stop_with_snapshot_if_requested(
        stop_event,
        coord,
        "User stop after SOL2 hand-off.",
        cfg,
        sol_spline,
    )
    if _stop_snapshot is not None:
        return _stop_snapshot

    coord.emit(68, "SOL 2 completed - continuing with fixed mesh finalization.")

    _log_spline_pipeline_json(
        log,
        "worker_after_sol2_handoff",
        seq="04",
        rmse_before=float(sol_spline["rmse"]),
    )

    # Final SOL: fixed sigma mesh (no knot insertion)

    _log_final_insert_enter(log, sol_spline, k_mesh=int(_k_mesh), nseg_mesh=int(_nseg_mesh))

    _delta_ns_fixed_mesh = float(sol_spline.get("substrate_n_offset", 0.0))
    _log_fixed_mesh_stage_summary(log, int(_k_mesh), int(_nseg_mesh), float(sol_spline["rmse"]), _delta_ns_fixed_mesh)

    _emit_enter_fixed_mesh_stage(coord)

    _log_skipped_knot_insertion_fixed_mesh(cfg, sol_spline, stop_event, coord.scoped(68, 72), live_cb=live_cb)

    # --- Optional MWIR mid-sigma node insertion (post-SOL2 hand-off, standard mode only) ---
    _mwir_stage_considered = False
    _mwir_insert_accepted = False
    _mwir_flag = bool(getattr(cfg, "post_sol2_insert_mwir_mid_sigma_enabled", False))
    _mwir_lam_max = float(np.max(np.asarray(cfg.lam_nm, dtype=np.float64).ravel()))
    _mwir_split_mode = "sigma_knots_n" in sol_spline or "sigma_knots_L" in sol_spline
    _mwir_stage_eligible = _mwir_flag and _mwir_lam_max > 2500.0 and not _mwir_split_mode
    if _mwir_stage_eligible:
        _mwir_stage_considered = True
        log.info(
            "PIPELINE [05b/09] Optional MWIR extra-node stage enabled | lambda_max=%.1f nm | running before k-floor and before any downstream corridor worker.",
            _mwir_lam_max,
        )
        _sol_before = sol_spline
        sol_spline = insert_mwir_mid_sigma_node(
            cfg,
            sol_spline,
            stop_event,
            progress_cb=coord.scoped(68, 72),
            live_cb=live_cb,
        )
        _mwir_insert_accepted = sol_spline is not _sol_before
    else:
        if not _mwir_flag:
            _mwir_skip_reason = "feature disabled"
        elif _mwir_lam_max <= 2500.0:
            _mwir_skip_reason = f"lambda_max={_mwir_lam_max:.1f} nm <= 2500"
        else:
            _mwir_skip_reason = "split-knot mode"
        log.info(
            "PIPELINE [05b/09] Optional MWIR extra-node stage skipped | reason=%s | continuing with fixed-mesh result before k-floor/corridors.",
            _mwir_skip_reason,
        )

    coord.emit(72, "Final fixed mesh - k floor / sigma mesh polish...")

    out = sol_spline
    out["post_s3_mwir_stage_considered"] = bool(_mwir_stage_considered)
    out["post_s3_mwir_insert_accepted"] = bool(_mwir_insert_accepted)
    out["post_s3_k_floor_applied"] = False

    _log_after_final_insert(log, sol_spline, out, mwir_insert_accepted=_mwir_insert_accepted)

    _log_after_final_stage_summary(
        log,
        float(out["rmse"]),
        mwir_stage_considered=_mwir_stage_considered,
        mwir_insert_accepted=_mwir_insert_accepted,
    )

    coord.emit(76, "k floor and spectral polish...")

    _apply_k_floor_to_result(cfg, out, log)

    _run_sigma_mesh_polish(cfg, out, log, coord, stop_event)

    lam_seg = np.asarray(out.get("lam_nm", cfg.lam_nm), dtype=np.float64).ravel()

    n_seg_arr = np.asarray(out.get("n_lam", []), dtype=np.float64).ravel()

    k_seg_arr = np.asarray(out.get("k_lam", []), dtype=np.float64).ravel()

    d_seg = float(out.get("d_nm", float("nan")))

    mse_seg_ref, rmse_seg_ref = spectral_mse_rmse_masked_from_nk(cfg, out, lam_seg, n_seg_arr, k_seg_arr, d_seg)

    if np.isfinite(rmse_seg_ref):
        out["spectral_rmse_segments"] = float(rmse_seg_ref)

        out["spectral_mse_segments"] = float(mse_seg_ref)

    else:
        out["spectral_rmse_segments"] = None

        out["spectral_mse_segments"] = None

    log.info(
        "PIPELINE [07c->reference] spectral_rmse_segments = masked RMSE on current n(lambda),k(lambda) 'solver' "
        "(out.n_lam / out.k_lam / out.d_nm), without sigma mesh polish - value = %s. "
        "Compare with spectral_rmse_seg_spline_sigma after cubic spline polish.",
        f"{float(rmse_seg_ref):.8f}" if np.isfinite(rmse_seg_ref) else "n/a",
    )

    _log_spline_pipeline_json(
        log,
        "worker_mesh_polish_summary_enter",
        seq="08",
        rmse_dict_before=float(out.get("rmse", float("nan")))
        if np.isfinite(float(out.get("rmse", float("nan"))))
        else None,
        spectral_rmse_segments=out.get("spectral_rmse_segments"),
        spectral_rmse_seg_spline_sigma=out.get("spectral_rmse_seg_spline_sigma"),
    )

    coord.emit(93, "Spectral sigma mesh polish RMSE synthesis...")

    log.info(
        "PIPELINE [08/09] After sigma mesh polish | dict RMSE=%s | reference solver RMSE (mesh)=%s",
        f"{float(out['rmse']):.6f}" if np.isfinite(float(out.get("rmse", float("nan")))) else "n/a",
        f"{float(rmse_seg_ref):.8f}" if np.isfinite(rmse_seg_ref) else "n/a",
    )

    # Shallow copy of ``out`` after sigma-mesh polish and spectral_rmse_segments recalculation,

    # before best_* synthesis - used if corridor base = solver (main curves).

    solver_snapshot = dict(out)

    _finalize_spectral_rmse_mesh_polish_and_best(out)

    out["gui_solver_snapshot_for_corridors"] = dict(solver_snapshot)
    try:
        _d_snap = float(solver_snapshot.get("d_nm", float("nan")))
        _d_snap_s = f"{_d_snap:.6f}" if np.isfinite(_d_snap) else "n/a"
        _d_nom = float(out.get("d_nm", float("nan")))
        _d_nom_s = f"{_d_nom:.6f}" if np.isfinite(_d_nom) else "n/a"
    except (TypeError, ValueError):
        _d_snap_s = _d_nom_s = "n/a"
    log_index_spline_d_trace(
        log,
        "worker: gui_solver_snapshot_for_corridors snapshot saved",
        solver_snapshot.get("d_nm"),
        detail=f"d_out_nominal={_d_nom_s} nm (snapshot.d={_d_snap_s})",
    )
    post_s3_candidates = _collect_post_s3_candidates(out, solver_snapshot=solver_snapshot)
    out["post_s3_candidate_ledger"] = post_s3_candidates
    scientific_candidate = _select_final_scientific_candidate(post_s3_candidates)
    out["post_s3_scientific_candidate"] = scientific_candidate
    if scientific_candidate is None:
        out["post_s3_scientific_candidate_id"] = None
        out["post_s3_scientific_candidate_label"] = None
        out["post_s3_scientific_candidate_origin"] = None
        out["post_s3_scientific_candidate_rmse"] = None
        log.info(
            "INDEX_SPLINE [POST-S3 SCIENTIFIC] No eligible scientific candidate selected.",
        )
    else:
        out["post_s3_scientific_candidate_id"] = str(scientific_candidate.get("id"))
        out["post_s3_scientific_candidate_label"] = str(scientific_candidate.get("label"))
        out["post_s3_scientific_candidate_origin"] = str(scientific_candidate.get("origin"))
        out["post_s3_scientific_candidate_rmse"] = float(scientific_candidate.get("rmse"))
        log.info(
            "INDEX_SPLINE [POST-S3 SCIENTIFIC] Final candidate -> %s (%s) RMSE=%.8f | corridor_compatible=%s | export_compatible=%s",
            str(scientific_candidate.get("label")),
            str(scientific_candidate.get("origin")),
            float(scientific_candidate.get("rmse")),
            bool(scientific_candidate.get("corridor_seed_compatible")),
            bool(scientific_candidate.get("export_compatible")),
        )

    out["rmse_fit_lambda_nm"] = cfg.rmse_fit_lambda_nm

    # n/k corridors + d interval via d profiling (optional, off by default).
    if not bool(getattr(cfg, "gui_defer_corridor_profile_after_nl", False)):
        _run_corridor_profile_with_optional_rerun(cfg, out, solver_snapshot, log)

    apply_rmse_fit_window_nk_nan_to_result(out, cfg.rmse_fit_lambda_nm)

    # --- Watermark RMSE: final check ---

    _wm_update(float(out.get("rmse", float("inf"))), "final")

    out["pipeline_best_rmse_watermark"] = float(_wm_best_rmse) if np.isfinite(_wm_best_rmse) else None

    out["pipeline_best_rmse_stage"] = _wm_best_stage

    _rmse_final = float(out.get("rmse", float("nan")))

    if np.isfinite(_rmse_final) and np.isfinite(_wm_best_rmse) and _rmse_final > _wm_best_rmse + 1e-8:
        wm_expected = False

        out["pipeline_watermark_degradation_expected"] = False

        log_fn = log.warning

        tag = ""

        log_fn(
            "PIPELINE [WATERMARK] SMART COACHING: Final returned RMSE (%.8f) is worse than "
            "the mathematical best RMSE found earlier (%.8f at stage '%s', loss = %+.8f). "
            "ACTION: This indicates a post-processing step (like Nonlinear Alpha smoothing or k_floor enforcement) "
            "overrode the solver's raw optimum to enforce physical constraints. "
            "If you prefer pure mathematical fidelity over physical smoothness, disable those post-processes.%s",
            _rmse_final,
            _wm_best_rmse,
            _wm_best_stage,
            _rmse_final - _wm_best_rmse,
            tag,
        )

        log_fn(
            "PIPELINE [WATERMARK] Mesh polish: spectral_rmse_seg_spline_sigma, "
            "spectral_rmse_best_label / spectral_rmse_best_value."
        )

        _log_spline_pipeline_json(
            log,
            "watermark_degradation",
            seq="09",
            rmse_final=_rmse_final,
            watermark_best_rmse=_wm_best_rmse,
            watermark_best_stage=_wm_best_stage,
            delta=float(_rmse_final - _wm_best_rmse),
            degradation_expected=bool(wm_expected),
        )

    log_index_spline_d_trace(
        log,
        "worker principal: dict final avant worker_complete JSON",
        out.get("d_nm"),
        detail=(
            "RMSE dict="
            + (
                f"{float(out.get('rmse', float('nan'))):.8f}"
                if np.isfinite(float(out.get("rmse", float("nan"))))
                else "n/a"
            )
        ),
    )

    _log_spline_pipeline_json(
        log,
        "worker_complete",
        seq="09",
        rmse_final=float(out.get("rmse", float("nan"))) if np.isfinite(float(out.get("rmse", float("nan")))) else None,
        x_encoding=str(out.get("x_encoding", "")),
        elapsed_worker_s=float(time.perf_counter() - t_worker),
    )

    log.info(
        "PIPELINE [09/09] Worker completed | dict RMSE (final n/k vs masked spectrum) = %s | duration %.2fs | x_encoding=%s",
        f"{float(out['rmse']):.6f}" if np.isfinite(float(out.get("rmse", float("nan")))) else "n/a",
        float(time.perf_counter() - t_worker),
        str(out.get("x_encoding", "?")),
    )

    if np.isfinite(float(_wm_best_rmse)):
        log.info(
            "PIPELINE [09/09] Watermark reminder: best RMSE observed during run = %.8f (stage %s) - "
            "pipeline_best_rmse_watermark / pipeline_best_rmse_stage dict fields.",
            float(_wm_best_rmse),
            _wm_best_stage,
        )

    log.info(
        "PIPELINE [09/09] UI delivery: a result dict is returned to the GUI (rmse, mse, n_lam, k_lam, d_nm, "
        "polish metadata). Curve display uses these n_lam/k_lam."
    )

    coord.finish(f"Completed | RMSE={out.get('rmse', float('nan')):.6f}")

    return snapshot_result_with_rmse_fit_meta(cfg, out)

