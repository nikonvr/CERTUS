#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""n/k corridors by thickness *d* profiling (continuation).

Design intent (local sensitivity around the best spectral fit):

  - The corridor is **not** a new global inversion: it is a **narrow strip** of models obtained by

    **small variations of thickness** *d* around the optimum, re-equilibrating **only** the spline

    nodes (n and L = ln k) at each *d* with the **same** objective / masks / penalties as the main

    spline fit. Think **differential-style sensitivity** or **profile likelihood on *d*** with a

    **fixed RMSE tolerance band** (alpha×RMSE_ref or RMSE_ref+Delta): every accepted point stays inside that

    tube in spectral space.

  - Operationally, the **center** must be the solution that carries the **best (lowest) masked

    spectral RMSE** you export as reference - in the pipeline this is typically

    ``corridor_profile_d_base_source="best_polished"`` (mesh-polished sigma splines) so that *d_opt*,

    ``n_lam``/``k_lam``, ``x``/nodes, and ``RMSE_ref`` all describe the **same** state before any

    corridor refit.

Idea:

  - Start from an existing spline solution (sigma_knots, d_opt, n/L at knots).

  - Fix *d* at d_target and re-optimize only the nodes (n and L=ln k)

    with EXACTLY the same guards / penalties / RMSE convention as the spline objective.

  - Repeat in "continuation" on both sides of d_opt; solutions whose RMSE

    stays below a threshold define a plausible interval [d_min, d_max] and an envelope

    (corridor) on n(lambda) and k(lambda).

This module does not touch the UI; it only produces fields to merge into the result dict.

RMSE reference (alpha mode, and automatic sigma in LR):

  - if ``spectral_rmse_segments`` is present in the pipeline dict (>0, finite), it is **preferred**

    (same convention as the n/k spline « solver » optimization);

  - otherwise ``rmse`` from the dict, then direct spectral RMSE recomputed from extracted nodes.

  The key ``profile_d_rmse_ref_source`` records which was used.

Automatic lift (alpha mode, default): if the refit at ``d_opt`` exceeds ``alpha×RMSE_ref``,

the effective threshold is raised to ``RMSE_center×(1+ε)`` to avoid empty profiling while still

logging ``profile_d_rmse_thresh_nominal`` vs ``profile_d_rmse_thresh`` and ``profile_d_auto_relaxed_threshold``.

**RMSE_ref vs refit RMSE (do not confuse in logs)**:

  - ``RMSE_ref`` (often ``spectral_rmse_segments``) = spectrum for the frozen **solver** solution

    (no corridor re-optimization of nodes).

  - Each « best-of » / refit step = L-BFGS-B on **n and L** only at fixed ``d``, budget

    ``corridor_profile_d_polish_maxfun``, jitter / multi-starts allowed -> RMSE can be

    **much larger** than ``RMSE_ref`` (local minima, insufficient budget) **without a bug**;

    the code then adjusts the threshold (``center_refit`` fallback, automatic lift).

**Scientific nominal mode** (``scientific_nominal_corridor`` + ``abs_delta``):

  ``RMSE_ref = spectral_rmse_best_value``; the nominal polished n(lambda),k(lambda) is the **first** member of the

  accepted family; ``corridor_reference_*`` is a copy of that nominal curve (not the center-d refit).

  No post-hoc widening toward a separate « main » ``n_lam``/``k_lam`` export.

**Legacy UI widening** (when scientific mode is off):

  After min/max over refits, the envelope can be **expanded** so reported ``n_lam``/``k_lam`` lie inside

  ``[corridor_*_lo, corridor_*_hi]`` at each lambda.

"""

from __future__ import annotations
from certus.spline.certus_corridor_config import (
    CorridorProfileContext,
    ProfileCorridorConfig,
    _log_coaching_corridor_failure,
)

# from certus.spline.certus_corridor_fitter import *  # Unused
from certus.spline.certus_corridor_fitter import _fit_nodes_at_fixed_d, _fit_local_quadratic_rmse_profile
from certus.spline.certus_corridor_exploration import _corridor_profile_walk_side, compute_regular_grid_rmse_profile

# from certus.spline.certus_corridor_logger import *  # Unused
from certus.spline.certus_corridor_logger import _log_coaching_corridor_outcome, _log_coaching_bootstrap_outcome, _log_coaching_reg_sensitivity_outcome, _log_corridor_base_geometry, _log_corridor_envelope_diagnostics, _log_corridor_start_config
# from certus.spline.certus_corridor_bootstrap import *  # Unused
from certus.spline.certus_corridor_orchestrator_utils import _setup_corridor_context
from certus.spline.certus_corridor_bootstrap import _bootstrap_single_replicate, _bootstrap_pool_entry, _resample_residuals_block
# from certus.spline.certus_corridor_utils import *  # Unused
from certus.spline.certus_corridor_utils import _expand_corridor_envelope_with_reported_nk, _robust_sigma_from_mad, _estimate_adaptive_rmse_abs_tolerance, _pick_rmse_reference_for_profile, _extract_knots_and_nodes_from_result, _spectral_rmse_at_packed_nodes, _x_nodes0_from_mesh_x_if_consistent, _bounds_for_nodes_only, _hetero_sigma_masked_from_base, _chi2_masked_constant_sigma, _detect_corridor_spike, quick_pwlnk_refit_result_dict
from certus.spline.certus_corridor_orchestrator_utils import enforce_min_k_corridor_half_width

from certus.spline.certus_corridor_orchestrator_utils import (
    _best_fit_at_d,
    _generate_iso_phase_seed,
    _theoretical_TR_from_base_result,
    _manual_grid_tag_base_on_duplicate_discard,
    _detect_breakpoint,
    _run_global_opt_from_breakpoint,
    _build_emergency_fit_record,
    _profile_p0_suspects,
    _profile_manual_grid_coverage_audit,
    _package_profile_grid_result,
    _compute_corridor_rmse_threshold,
    _prep_corridor_base_eff,
    _eval_adaptive_abs_tolerance,
    _eval_corridor_threshold_fallback,
    _package_corridor_results,
)


import logging


import threading

import time

from concurrent.futures import ThreadPoolExecutor, as_completed

from dataclasses import dataclass

from typing import Any

import numpy as np

from scipy.optimize import minimize

from scipy.stats import chi2 as _chi2

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, get_safe_worker_count

from certus_physics import clip_to_bounds

from certus.spline.certus_index_spline_core import (
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    DataType,
    SplineOptConfig,
    corridor_profile_refit_maxfun,
    physical_nodes_to_x_slice_n,
    _reflectance_absolute_backside_from_nk,
)

from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _transmittance_absolute_from_nk,
)

from certus.spline.spline_objective import (
    SplinePWLObjective,
    build_spline_objective_masked_grid,
    nk_from_x_pwlnk,
    spectral_mse_rmse_masked_from_nk,
    spline_pwl_analytic_grad_supported,
    x_slice_n_to_physical_nodes,
)

from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference

log = logging.getLogger("CERTUS")

_LOG_PREFIX = "INDEX_SPLINE [CORRIDORS d]"








from pydantic import BaseModel, ConfigDict




















































































def compute_profiled_corridors_by_d(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig | None = None,
    log_coaching: bool = True,
    profile_polish_maxfun: int | None = None,
    live_cb: Any | None = None,
) -> dict[str, Any]:
    ctx = _setup_corridor_context(
        cfg,
        base_result,
        pconf=pconf,
        log_coaching=log_coaching,
        profile_polish_maxfun=profile_polish_maxfun,
        live_cb=live_cb,
    )
    if isinstance(ctx, dict):
        return ctx

    target_min_span = 0.0
    if (
        hasattr(ctx, "adaptive_abs_meta")
        and isinstance(ctx.adaptive_abs_meta, dict)
        and ctx.adaptive_abs_meta.get("ok", False)
    ):
        _curv = float(ctx.adaptive_abs_meta.get("curvature", float("nan")))
        _dtol = float(ctx.adaptive_abs_meta.get("delta_rmse_tol", float("nan")))
        if np.isfinite(_curv) and _curv > 0.0 and np.isfinite(_dtol) and _dtol > 0.0:
            target_min_span = float(np.sqrt(_dtol / _curv))

    def _run_walks_sequential() -> tuple[dict[str, Any], dict[str, Any]]:

        return (
            _corridor_profile_walk_side(
                1.0,
                ctx.pconf,
                ctx.cfg,
                ctx.sk,
                ctx.d0,
                ctx.x_nodes_center,
                ctx.x0_default,
                ctx.bounds_nodes,
                ctx.maxfun_prof,
                ctx.use_lr,
                ctx.chi2_min,
                ctx.delta_chi2,
                ctx.rmse_thresh_active,
                ctx.rmse_opt,
                ctx.sig_t,
                ctx.sig_r,
                ctx.sigma_t_f_hetero,
                ctx.sigma_r_f_hetero,
                ctx.live_streamer,
                target_min_span=target_min_span,
            ),
            _corridor_profile_walk_side(
                -1.0,
                ctx.pconf,
                ctx.cfg,
                ctx.sk,
                ctx.d0,
                ctx.x_nodes_center,
                ctx.x0_default,
                ctx.bounds_nodes,
                ctx.maxfun_prof,
                ctx.use_lr,
                ctx.chi2_min,
                ctx.delta_chi2,
                ctx.rmse_thresh_active,
                ctx.rmse_opt,
                ctx.sig_t,
                ctx.sig_r,
                ctx.sigma_t_f_hetero,
                ctx.sigma_r_f_hetero,
                ctx.live_streamer,
                target_min_span=target_min_span,
            ),
        )

    parallel_walks = bool(getattr(ctx.cfg, "corridor_profile_d_parallel_walks", True))

    if parallel_walks:
        try:
            p_plus = ctx.pconf.replace(rng_seed=int(ctx.pconf.rng_seed) + 1_000_003)

            p_minus = ctx.pconf.replace(rng_seed=int(ctx.pconf.rng_seed) + 1_000_019)

            with ThreadPoolExecutor(max_workers=2) as _pool:
                _f_plus = _pool.submit(
                    _corridor_profile_walk_side,
                    1.0,
                    p_plus,
                    ctx.cfg,
                    ctx.sk,
                    ctx.d0,
                    ctx.x_nodes_center,
                    ctx.x0_default,
                    ctx.bounds_nodes,
                    ctx.maxfun_prof,
                    ctx.use_lr,
                    ctx.chi2_min,
                    ctx.delta_chi2,
                    ctx.rmse_thresh_active,
                    ctx.rmse_opt,
                    ctx.sig_t,
                    ctx.sig_r,
                    ctx.sigma_t_f_hetero,
                    ctx.sigma_r_f_hetero,
                    ctx.live_streamer,
                    target_min_span=target_min_span,
                )

                _f_minus = _pool.submit(
                    _corridor_profile_walk_side,
                    -1.0,
                    p_minus,
                    ctx.cfg,
                    ctx.sk,
                    ctx.d0,
                    ctx.x_nodes_center,
                    ctx.x0_default,
                    ctx.bounds_nodes,
                    ctx.maxfun_prof,
                    ctx.use_lr,
                    ctx.chi2_min,
                    ctx.delta_chi2,
                    ctx.rmse_thresh_active,
                    ctx.rmse_opt,
                    ctx.sig_t,
                    ctx.sig_r,
                    ctx.sigma_t_f_hetero,
                    ctx.sigma_r_f_hetero,
                    ctx.live_streamer,
                    target_min_span=target_min_span,
                )

                r_plus = _f_plus.result()

                r_minus = _f_minus.result()

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s parallel +/-d walks failed - sequential fallback.", _LOG_PREFIX)

            r_plus, r_minus = _run_walks_sequential()

    else:
        r_plus, r_minus = _run_walks_sequential()

    ctx.d_vals.extend(r_plus["d_vals"])

    ctx.d_vals.extend(r_minus["d_vals"])

    ctx.n_curves.extend(r_plus["n_curves"])

    ctx.n_curves.extend(r_minus["n_curves"])

    ctx.k_curves.extend(r_plus["k_curves"])

    ctx.k_curves.extend(r_minus["k_curves"])

    ctx.x_curves.extend(r_plus["x_curves"])

    ctx.x_curves.extend(r_minus["x_curves"])

    ctx.rmse_vals.extend(r_plus["rmse_vals"])

    ctx.rmse_vals.extend(r_minus["rmse_vals"])

    ctx.chi2_vals.extend(r_plus["chi2_vals"])

    ctx.chi2_vals.extend(r_minus["chi2_vals"])

    ctx.fit_nfev_values.extend(r_plus["fit_nfev_values"])

    ctx.fit_nfev_values.extend(r_minus["fit_nfev_values"])

    ctx.fit_nit_values.extend(r_plus["fit_nit_values"])

    ctx.fit_nit_values.extend(r_minus["fit_nit_values"])

    ctx.fit_try_values.extend(r_plus["fit_try_values"])

    ctx.fit_try_values.extend(r_minus["fit_try_values"])

    ctx.fit_fail_values.extend(r_plus["fit_fail_values"])

    ctx.fit_fail_values.extend(r_minus["fit_fail_values"])

    pos_valid = int(r_plus["n_valid_side"])

    neg_valid = int(r_minus["n_valid_side"])

    ctx.boundary_refine_calls = int(r_plus["n_refines"]) + int(r_minus["n_refines"])
    ctx.seed_gate_eval_count = (
        int(r_plus.get("seed_gate_eval_count", 0))
        + int(r_minus.get("seed_gate_eval_count", 0))
        + int(ctx.center_seed_gate_eval_count)
    )
    ctx.seed_gate_kept_count = (
        int(r_plus.get("seed_gate_kept_count", 0))
        + int(r_minus.get("seed_gate_kept_count", 0))
        + int(ctx.center_seed_gate_kept_count)
    )
    ctx.seed_gate_deltas = np.asarray(
        list(np.asarray(r_plus.get("seed_gate_delta_refit_minus_seed", []), dtype=np.float64).ravel())
        + list(np.asarray(r_minus.get("seed_gate_delta_refit_minus_seed", []), dtype=np.float64).ravel())
        + (
            [float(ctx.center_seed_gate_delta_refit_minus_seed)]
            if np.isfinite(float(ctx.center_seed_gate_delta_refit_minus_seed))
            else []
        ),
        dtype=np.float64,
    )

    # P0.3 FIX: Global seed-gate status for corridor quality assessment
    _sg_global_rate = (
        float(ctx.seed_gate_kept_count) / float(ctx.seed_gate_eval_count)
        if int(ctx.seed_gate_eval_count) > 0
        else float("nan")
    )
    ctx.seed_gate_saturated_global = (
        np.isfinite(_sg_global_rate) and _sg_global_rate > 0.5 and int(ctx.seed_gate_eval_count) >= 5
    )
    if ctx.seed_gate_saturated_global:
        log.warning(
            "%s Corridor seed-gate SATURATED (%.0f%% kept > 50%%). "
            "Result may be non-informative (envelope artificially tight). "
            "Consider increasing corridor_profile_d_polish_maxfun or enabling refit_pure_spectral.",
            _LOG_PREFIX,
            100.0 * _sg_global_rate,
        )
    ctx.seed_gate_auto_escalated_global = bool(
        r_plus.get("seed_gate_auto_escalated", False) or r_minus.get("seed_gate_auto_escalated", False)
    )

    min_req = int(max(1, ctx.pconf.min_valid_points))

    if ctx.scientific_nominal:
        min_req = 1

    ctx.min_side = int(max(0, getattr(ctx.pconf, "min_valid_each_side", 0)))

    if len(ctx.d_vals) < min_req:
        if len(ctx.d_vals) >= 1 and ctx.auto_relaxed_alpha:
            log.warning(
                "%s Continuing with %d valid point(s) (< min_valid_points=%d) after automatic RMSE threshold lift "
                "(envelope may be narrow or degenerate).",
                _LOG_PREFIX,
                int(len(ctx.d_vals)),
                min_req,
            )

        else:
            # P1.2 FIX: Detect plateau scenario (RMSE almost flat -> threshold too strict)
            _is_plateau = False
            if len(ctx.d_vals) >= 2 and len(ctx.rmse_vals) >= 2:
                _rmse_arr = np.asarray(ctx.rmse_vals, dtype=np.float64)
                _rmse_mean = float(np.nanmean(_rmse_arr))
                _rmse_std = float(np.nanstd(_rmse_arr))
                _cv = _rmse_std / _rmse_mean if _rmse_mean > 0 else 0.0  # coefficient of variation
                # Plateau: low CV (< 2%) and all points near threshold
                _all_near_thresh = np.all(np.abs(_rmse_arr - ctx.rmse_thresh_active) < 0.01 * ctx.rmse_thresh_active)
                if _cv < 0.02 and _all_near_thresh:
                    _is_plateau = True

            if _is_plateau:
                log.warning(
                    "%s PLATEAU DETECTED: RMSE nearly flat (CV<2%%) with all points near threshold. "
                    "The tolerance is likely too strict for this data. Suggestions: "
                    "(1) Increase rmse_abs_tolerance by ~2x; "
                    "(2) Switch to mode='alpha' with alpha=1.05; "
                    "(3) Enable use_heteroscedastic_sigma=True if noise varies with wavelength; "
                    "(4) Check if data has sufficient spectral contrast for n/k inference. "
                    "Current: %d valid points (min_req=%d), RMSE_mean=%.6f, thresh=%.6f",
                    _LOG_PREFIX,
                    int(len(ctx.d_vals)),
                    min_req,
                    float(_rmse_mean),
                    float(ctx.rmse_thresh_active),
                )
            else:
                log.warning(
                    "%s Abort: too few valid solutions (%d < %d).",
                    _LOG_PREFIX,
                    int(len(ctx.d_vals)),
                    min_req,
                )

            if ctx.log_coaching:
                _log_coaching_corridor_failure(
                    reason="too_few_valid",
                    pconf=ctx.pconf,
                    use_lr=ctx.use_lr,
                    rmse_opt=ctx.rmse_opt,
                    rmse_thresh=ctx.rmse_thresh_active,
                    d0=float(ctx.d0),
                )

            return {"profile_d_status": "failed"}

    if ctx.min_side > 0 and (pos_valid < ctx.min_side or neg_valid < ctx.min_side):
        log.warning(
            "%s Degenerate corridor: valid_side(+d=%d, -d=%d) < min_valid_each_side=%d.",
            _LOG_PREFIX,
            int(pos_valid),
            int(neg_valid),
            int(ctx.min_side),
        )

    ctx = CorridorProfileContext(
        _use_hetero=ctx._use_hetero,
        _user_mask=ctx._user_mask,
        adaptive_abs_meta=ctx.adaptive_abs_meta,
        auto_relaxed_alpha=ctx.auto_relaxed_alpha,
        base_result=ctx.base_result,
        boundary_refine_calls=ctx.boundary_refine_calls,
        center_seed_kept=ctx.center_seed_kept,
        cfg=ctx.cfg,
        chi2_vals=ctx.chi2_vals,
        d0=ctx.d0,
        d_vals=ctx.d_vals,
        delta_chi2=ctx.delta_chi2,
        fit_fail_values=ctx.fit_fail_values,
        fit_nfev_values=ctx.fit_nfev_values,
        fit_nit_values=ctx.fit_nit_values,
        fit_try_values=ctx.fit_try_values,
        k_curves=ctx.k_curves,
        log_coaching=ctx.log_coaching,
        maxfun_prof=ctx.maxfun_prof,
        min_side=ctx.min_side,
        n_curves=ctx.n_curves,
        nom_pack=ctx.nom_pack,
        pconf=ctx.pconf,
        rmse_opt=ctx.rmse_opt,
        rmse_ref_tag=ctx.rmse_ref_tag,
        rmse_thr_sub=ctx.rmse_thr_sub,
        rmse_thresh=ctx.rmse_thresh,
        rmse_thresh_active=ctx.rmse_thresh_active,
        rmse_vals=ctx.rmse_vals,
        scientific_nominal=ctx.scientific_nominal,
        seed_gate_auto_escalated_global=ctx.seed_gate_auto_escalated_global,
        seed_gate_deltas=ctx.seed_gate_deltas,
        seed_gate_eval_count=ctx.seed_gate_eval_count,
        seed_gate_kept_count=ctx.seed_gate_kept_count,
        seed_gate_saturated_global=ctx.seed_gate_saturated_global,
        sig_r=ctx.sig_r,
        sig_t=ctx.sig_t,
        sigma_r_f_hetero=ctx.sigma_r_f_hetero,
        sigma_t_f_hetero=ctx.sigma_t_f_hetero,
        t0=ctx.t0,
        threshold_basis_eff=ctx.threshold_basis_eff,
        threshold_fallback_reason=ctx.threshold_fallback_reason,
        tol_abs=ctx.tol_abs,
        tol_abs_effective=ctx.tol_abs_effective,
        use_abs_delta=ctx.use_abs_delta,
        use_adaptive_abs_delta=ctx.use_adaptive_abs_delta,
        use_lr=ctx.use_lr,
        sk=ctx.sk,
        x_nodes_center=ctx.x_nodes_center,
        x0_default=ctx.x0_default,
        bounds_nodes=ctx.bounds_nodes,
        chi2_min=ctx.chi2_min,
        x_curves=ctx.x_curves,
        corridor_ref_n_lam=ctx.corridor_ref_n_lam,
        corridor_ref_k_lam=ctx.corridor_ref_k_lam,
        _push_live_point_from_payload=ctx._push_live_point_from_payload,
        live_streamer=ctx.live_streamer,
        center_seed_gate_eval_count=ctx.center_seed_gate_eval_count,
        center_seed_gate_kept_count=ctx.center_seed_gate_kept_count,
        center_seed_gate_delta_refit_minus_seed=ctx.center_seed_gate_delta_refit_minus_seed,
    )
    return _package_corridor_results(ctx)


def _sorted_corridor_stacks(ctx: CorridorProfileContext) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return ordered d/rmse/chi2 and stacked n/k curves."""

    n_stack = np.vstack([np.asarray(c, dtype=np.float64).reshape(1, -1) for c in ctx.n_curves])
    k_stack = np.vstack([np.asarray(c, dtype=np.float64).reshape(1, -1) for c in ctx.k_curves])
    d_arr = np.asarray(ctx.d_vals, dtype=np.float64)
    rm_arr = np.asarray(ctx.rmse_vals, dtype=np.float64)
    c_arr = np.asarray(ctx.chi2_vals, dtype=np.float64)
    order = np.argsort(d_arr)
    d_arr = d_arr[order]
    rm_arr = rm_arr[order]
    c_arr = c_arr[order] if c_arr.size == d_arr.size else np.full(d_arr.shape, np.nan, dtype=np.float64)
    n_stack = n_stack[order, :] if n_stack.shape[0] == order.size else n_stack
    k_stack = k_stack[order, :] if k_stack.shape[0] == order.size else k_stack
    return d_arr, rm_arr, c_arr, n_stack, k_stack


def _derive_symmetric_d_interval(
    ctx: CorridorProfileContext,
    d_arr: np.ndarray,
    rm_arr: np.ndarray,
) -> tuple[float, tuple[float, float], str, dict[str, Any]]:
    """Derive the reported d interval from the accepted samples."""

    d_interval_raw = (float(np.min(d_arr)), float(np.max(d_arr)))
    parab_half_window_pts = int(max(1, int(getattr(ctx.pconf, "parabola_half_window_pts", 3) or 3)))
    parab_fit = _fit_local_quadratic_rmse_profile(d_arr, rm_arr, int(np.argmin(rm_arr)), parab_half_window_pts, 0.0)
    parab_center_nm = float(parab_fit.get("d_center", float("nan"))) if bool(parab_fit.get("ok", False)) else float("nan")
    center_mode = str(getattr(ctx.pconf, "symmetric_interval_center_mode", "parabola") or "parabola").strip().lower()
    if bool(getattr(ctx.pconf, "force_symmetric_interval", True)) and np.isfinite(parab_center_nm) and center_mode == "parabola":
        d_center_sym = float(parab_center_nm)
        center_source = "parabola"
    else:
        d_center_sym = float(parab_center_nm) if np.isfinite(parab_center_nm) else float(ctx.d0)
        center_source = "parabola" if np.isfinite(parab_center_nm) else "nominal"
    if not np.isfinite(d_center_sym):
        d_center_sym = float(ctx.d0)
        center_source = "nominal"

    side_neg = d_center_sym - d_arr[d_arr <= d_center_sym + 1e-12]
    side_pos = d_arr[d_arr >= d_center_sym - 1e-12] - d_center_sym
    half_neg = float(np.max(side_neg)) if side_neg.size else 0.0
    half_pos = float(np.max(side_pos)) if side_pos.size else 0.0
    half_sym = float(max(0.0, min(half_neg, half_pos)))
    min_half_sym = float(max(0.0, float(getattr(ctx.pconf, "symmetric_interval_min_half_width_rel", 0.002) or 0.0))) * max(abs(float(ctx.d0)), 1e-12)
    half_bounds = float(max(0.0, min(float(d_center_sym - float(ctx.cfg.d_lo)), float(ctx.cfg.d_hi - float(d_center_sym)))))
    half_sym = float(min(max(half_sym, min_half_sym), half_bounds)) if half_bounds > 0.0 else 0.0
    if bool(getattr(ctx.pconf, "force_symmetric_interval", False)):
        d_sym_lo, d_sym_hi = float(d_center_sym - half_sym), float(d_center_sym + half_sym)
    else:
        d_sym_lo = max(min(float(d_center_sym - half_neg), float(d_center_sym - min_half_sym)), float(ctx.cfg.d_lo))
        d_sym_hi = min(max(float(d_center_sym + half_pos), float(d_center_sym + min_half_sym)), float(ctx.cfg.d_hi))
    valid_hi = d_arr[d_arr >= d_sym_hi - 1e-9]
    if valid_hi.size > 0:
        d_sym_hi = float(np.min(valid_hi))
    return d_interval_raw, (float(d_sym_lo), float(d_sym_hi)), str(center_source), parab_fit


def _package_corridor_results(ctx: CorridorProfileContext) -> dict[str, Any]:
    """Package the final corridor state into the output dictionary."""

    if not ctx.d_vals or not ctx.n_curves or not ctx.k_curves:
        return {"profile_d_status": "failed"}

    n_stack = np.vstack([np.asarray(c, dtype=np.float64).reshape(1, -1) for c in ctx.n_curves])
    k_stack = np.vstack([np.asarray(c, dtype=np.float64).reshape(1, -1) for c in ctx.k_curves])
    n_lo = np.nanmin(n_stack, axis=0)
    n_hi = np.nanmax(n_stack, axis=0)
    k_lo = np.nanmin(k_stack, axis=0)
    k_hi = np.nanmax(k_stack, axis=0)

    if n_stack.ndim == 2 and k_stack.ndim == 2 and n_stack.shape == k_stack.shape:
        _crossing_mask = np.nanmin(n_stack, axis=0) < np.nanmax(k_stack, axis=0)
        if np.any(_crossing_mask):
            log.warning(
                "%s n/k CROSSING DETECTED: n < k at %d wavelengths (%.1f%%). Consider tightening rmse_alpha or rmse_abs_tolerance.",
                _LOG_PREFIX,
                int(np.sum(_crossing_mask)),
                100.0 * float(np.mean(_crossing_mask)),
            )

    if ctx.scientific_nominal and ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None:
        n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(n_lo, n_hi, k_lo, k_hi, ctx.corridor_ref_n_lam, ctx.corridor_ref_k_lam)
    elif not ctx.scientific_nominal:
        n_nom_r = np.asarray(ctx.base_result.get("n_lam"), dtype=np.float64).ravel()
        k_nom_r = np.asarray(ctx.base_result.get("k_lam"), dtype=np.float64).ravel()
        if int(n_nom_r.size) >= int(n_lo.size) and int(k_nom_r.size) >= int(k_lo.size):
            n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(n_lo, n_hi, k_lo, k_hi, n_nom_r, k_nom_r)

    if not ctx.scientific_nominal and ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None and int(n_stack.shape[0]) > 0:
        ctx.corridor_ref_n_lam = np.asarray(n_stack[0], dtype=np.float64).ravel().copy()
        ctx.corridor_ref_k_lam = np.asarray(k_stack[0], dtype=np.float64).ravel().copy()

    if ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None and int(n_stack.shape[0]) > 0:
        m_chk = np.isfinite(k_lo) & np.isfinite(k_hi) & np.isfinite(ctx.corridor_ref_k_lam) & (ctx.corridor_ref_k_lam > 0.0)
        if np.any(m_chk):
            bad_m = (ctx.corridor_ref_k_lam[m_chk] < k_lo[m_chk] - 1e-12) | (ctx.corridor_ref_k_lam[m_chk] > k_hi[m_chk] + 1e-12)
            if np.any(bad_m):
                idx_full = int(np.flatnonzero(m_chk)[int(np.where(bad_m)[0][0])])
                log.warning(
                    "%s k corridor health: k_ref outside [k_lo,k_hi] at lambda[%d] (min/max inconsistency) - k_ref=%.6e k_lo=%.6e k_hi=%.6e",
                    _LOG_PREFIX,
                    idx_full,
                    float(ctx.corridor_ref_k_lam[idx_full]),
                    float(k_lo[idx_full]),
                    float(k_hi[idx_full]),
                )

    d_arr, rm_arr, c_arr, n_stack, k_stack = _sorted_corridor_stacks(ctx)
    d_interval_raw, d_interval_sym, center_source, parab_fit = _derive_symmetric_d_interval(ctx, d_arr, rm_arr)

    k_ref_for_min = np.asarray(ctx.corridor_ref_k_lam, dtype=np.float64).ravel() if ctx.corridor_ref_k_lam is not None else np.asarray([], dtype=np.float64)
    if k_ref_for_min.size != np.asarray(k_lo, dtype=np.float64).ravel().size:
        k_ref_for_min = 0.5 * (np.asarray(k_lo, dtype=np.float64).ravel() + np.asarray(k_hi, dtype=np.float64).ravel())
    k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
        np.asarray(k_lo, dtype=np.float64),
        np.asarray(k_hi, dtype=np.float64),
        np.asarray(k_ref_for_min, dtype=np.float64),
        min_half_width=1e-4,
    )
    _log_corridor_envelope_diagnostics(
        n_lo=n_lo,
        n_hi=n_hi,
        k_lo=k_lo,
        k_hi=k_hi,
        k_stack=k_stack,
        corridor_ref_k_lam=ctx.corridor_ref_k_lam,
        base_k_lam=np.asarray(ctx.base_result.get("k_lam", []), dtype=np.float64).ravel(),
    )
    if ctx.log_coaching:
        _log_coaching_corridor_outcome(
            pconf=ctx.pconf,
            use_lr=ctx.use_lr,
            use_abs_delta=bool(ctx.use_abs_delta),
            d0=float(ctx.d0),
            d_arr=d_arr,
            rm_arr=rm_arr,
            rmse_opt=ctx.rmse_opt,
            rmse_thresh=ctx.rmse_thresh_active,
            polish_maxfun=int(ctx.maxfun_prof),
            base_result=ctx.base_result,
        )

    out_prof: dict[str, Any] = {
        "profile_d_polish_maxfun_effective": int(ctx.maxfun_prof),
        "profile_d_enabled": True,
        "profile_d_mode": str(ctx.pconf.mode),
        "profile_d_acceptance_mode": "lr" if ctx.use_lr else ("delta_rmse_abs_best_polished" if (ctx.use_abs_delta and ctx.scientific_nominal) else ("delta_rmse_abs" if ctx.use_abs_delta else "alpha_heuristic")),
        "profile_d_scientific_nominal": bool(ctx.scientific_nominal),
        "profile_rmse_best_ref": float(ctx.rmse_opt) if ctx.scientific_nominal else None,
        "profile_d_rmse_ref_source": str(ctx.rmse_ref_tag),
        "profile_d_rmse_thresh": float(ctx.rmse_thresh_active),
        "profile_d_rmse_thresh_nominal": float(ctx.rmse_thresh) if (not ctx.use_lr) else None,
        "profile_d_threshold_basis_effective": str(ctx.threshold_basis_eff),
        "profile_d_threshold_fallback_reason": str(ctx.threshold_fallback_reason),
        "profile_d_auto_relaxed_threshold": bool(ctx.auto_relaxed_alpha),
        "profile_d_lr_conf": float(ctx.pconf.lr_conf_level) if ctx.use_lr else None,
        "profile_d_lr_delta_chi2": float(ctx.delta_chi2) if ctx.use_lr else None,
        "profile_d_sigma_t": float(ctx.sig_t) if ctx.use_lr else None,
        "profile_d_sigma_r": float(ctx.sig_r) if ctx.use_lr else None,
        "profile_d_values_nm": d_arr,
        "profile_d_rmse_values": rm_arr,
        "profile_d_chi2_values": c_arr,
        "profile_d_n_curves": np.asarray(n_stack, dtype=np.float64),
        "profile_d_k_curves": np.asarray(k_stack, dtype=np.float64),
        "profile_d_interval_nm": d_interval_sym,
        "profile_d_interval_raw_nm": d_interval_raw,
        "profile_d_interval_center_nm": float(parab_fit.get("d_center", float("nan"))),
        "profile_d_interval_center_source": str(center_source),
        "profile_d_parabola_ok": bool(parab_fit.get("ok", False)),
        "profile_d_parabola_center_nm": float(parab_fit.get("d_center", float("nan"))),
        "profile_d_parabola_curvature": float(parab_fit.get("curvature", float("nan"))),
        "profile_d_seed_gate_eval_count": int(ctx.seed_gate_eval_count),
        "profile_d_seed_gate_kept_count": int(ctx.seed_gate_kept_count),
        "profile_d_seed_gate_saturated": bool(ctx.seed_gate_saturated_global),
        "profile_d_seed_gate_auto_escalated": bool(ctx.seed_gate_auto_escalated_global),
        "profile_d_user_rmse_mask": np.asarray(ctx._user_mask, dtype=bool).copy() if ctx._user_mask is not None and len(np.asarray(ctx._user_mask)) > 0 else None,
        "profile_d_mean_nfev": float(np.nanmean(np.asarray(ctx.fit_nfev_values, dtype=np.float64))) if ctx.fit_nfev_values else float("nan"),
        "profile_d_mean_nit": float(np.nanmean(np.asarray(ctx.fit_nit_values, dtype=np.float64))) if ctx.fit_nit_values else float("nan"),
        "corridor_n_lo": np.asarray(n_lo, dtype=np.float64),
        "corridor_n_hi": np.asarray(n_hi, dtype=np.float64),
        "corridor_k_lo": np.asarray(k_lo, dtype=np.float64),
        "corridor_k_hi": np.asarray(k_hi, dtype=np.float64),
        "corridor_k_min_half_width": float(1e-4),
        "corridor_k_min_half_width_enforced_points": int(k_min_changed),
        "profile_d_status": "degenerate" if (int(np.count_nonzero(d_arr > ctx.d0 + 1e-12)) < ctx.min_side or int(np.count_nonzero(d_arr < ctx.d0 - 1e-12)) < ctx.min_side) else "ok",
    }
    if ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None:
        out_prof["corridor_reference_n_lam"] = ctx.corridor_ref_n_lam
        out_prof["corridor_reference_k_lam"] = ctx.corridor_ref_k_lam
    out_prof["profile_d_run_id"] = getattr(ctx, "_run_id", None)
    out_prof["profile_d_stage"] = getattr(ctx, "_run_stage", None)
    return out_prof

