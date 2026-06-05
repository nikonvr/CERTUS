#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""Main spline pipeline: JSON logging, RMSE snapshots, worker orchestration."""

from __future__ import annotations
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


def _sync_theoretical_tr_from_nk_dict(
    cfg: SplineOptConfig,
    out: dict[str, Any],
    *,
    log: logging.Logger | None = None,
    reason: str = "generique",
) -> None:
    """Rebuild ``t_theo`` / ``r_theo`` from ``out`` wavelengths, ``n_lam``, ``k_lam``, ``d_nm``.

    Keeps the displayed / exported spectrum model aligned with indices when ``n_lam`` /
    ``k_lam`` / ``d_nm`` change without a prior transfer-matrix refresh (e.g. corridor
    promotion).
    """
    _audit_corridor = reason == "corridor_profile_bloc_fin"
    _warn_skip = log is not None and _audit_corridor

    def _skip(msg: str) -> None:
        if _warn_skip:
            log.warning(
                "PIPELINE [MODELE_SPECTRAL_SYNC] SKIP (audit corridor) | %s | reason=%s",
                msg,
                reason,
            )
        elif log is not None:
            log.debug("PIPELINE: skip t_theo sync | %s | raison=%s", msg, reason)

    lam_src = out.get("lam_nm", getattr(cfg, "lam_nm", None))
    if lam_src is None:
        _skip("pas de lam_nm ni cfg.lam_nm")
        return
    lam_full = np.asarray(lam_src, dtype=np.float64).ravel()
    n_l = np.asarray(out.get("n_lam"), dtype=np.float64).ravel()
    k_l = np.asarray(out.get("k_lam"), dtype=np.float64).ravel()
    if lam_full.size < 2 or n_l.size != lam_full.size or k_l.size != lam_full.size:
        _skip(f"tailles incompatibles lam={lam_full.size} n={n_l.size} k={k_l.size} (attendu n=k=lam)")
        return
    d_raw = out.get("d_nm", float("nan"))
    try:
        d_nm = float(d_raw)
    except (TypeError, ValueError):
        _skip("d_nm non convertible en float")
        return
    if not np.isfinite(d_nm):
        _skip("d_nm non fini")
        return
    if not (np.all(np.isfinite(lam_full)) and np.all(np.isfinite(n_l)) and np.all(np.isfinite(k_l))):
        _skip("lam/n/k contain non-finite values (sync impossible)")
        return
    n_sub_raw = out.get("n_sub_effective", getattr(cfg, "n_sub", None))
    n_sub_full = np.asarray(n_sub_raw, dtype=np.float64).ravel()
    if n_sub_full.size != lam_full.size:
        _skip(f"tailles incompatibles n_sub={n_sub_full.size} lam={lam_full.size} (attendu n_sub=lam)")
        return
    try:
        if cfg.t_is_ratio:
            out["t_theo"] = _ratio_theoretical_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
        else:
            out["t_theo"] = _transmittance_absolute_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
        if cfg.r_exp is not None:
            if cfg.t_is_ratio:
                out["r_theo"] = _reflectance_ratio_theoretical_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
            else:
                out["r_theo"] = _reflectance_absolute_backside_from_nk(lam_full, n_l, k_l, d_nm, n_sub_full)
    except NUMERICAL_FAULT_EXCEPTIONS as ex:
        if log is not None:
            log.warning(
                "PIPELINE [MODELE_SPECTRAL_SYNC] FAILED recalculation (non-blocking) | reason=%s | %s",
                reason,
                ex,
            )
        return

    if log is None:
        return

    tt = np.asarray(out["t_theo"], dtype=np.float64).ravel()
    i1 = int(lam_full.size - 1)
    t0 = float(tt[0]) if tt.size == lam_full.size else float("nan")
    t1 = float(tt[i1]) if tt.size == lam_full.size else float("nan")
    l0 = float(lam_full[0])
    l1 = float(lam_full[i1])
    promoted = bool(out.get("profile_d_promoted"))
    log.info(
        "PIPELINE [MODELE_SPECTRAL_SYNC] OK | reason=%s | T_theo (and R_theo if active) recalculated "
        "from n_lam,k_lam,d_nm — proof that the model spectrum is aligned on the n,k tab "
        "(fix for \"noisy T\" bug after corridor promotion) | lam_pts=%d lambda[0,last]=[%.4f,%.4f] nm "
        "d_nm=%.6f T_substrat_norm=%s R_theo=%s | T_theo(λ_0,λ_last)=(%.6g,%.6g) | "
        "profile_d_promoted=%s",
        reason,
        int(lam_full.size),
        l0,
        l1,
        float(d_nm),
        bool(cfg.t_is_ratio),
        bool(cfg.r_exp is not None),
        t0,
        t1,
        promoted,
    )


def enforce_local_optimization_policy(cfg: SplineOptConfig) -> None:
    """INDEX-SPLINE policy: optimization is local-only (L-BFGS-B)."""
    cfg.spline_local_only = True


class _WorkerProgressCoordinator:
    """

    Monotonic gauge for the UI: maps local sub-phases (0-100) onto global ranges,

    without backtracking (avoids jumps like 93 % -> 5 % between SOL2 and legacy free-knot stage).

    Values sent to ``root_cb`` are **centi-percent** integers in ``0..10000`` (i.e. ``5423``

    means ``54.23 %``), except completion which emits ``10000`` for a full bar.

    """

    __slots__ = ("_root", "_last")

    def __init__(self, root_cb: Callable[[int, str], None]) -> None:

        self._root = root_cb

        self._last = 0.0

    def emit(self, g: float, msg: str) -> None:
        g = float(np.clip(g, 0.0, 99.99))
        if g < self._last:
            g = self._last
        self._last = g
        # Log percentage for linearity analysis (INFO for transitions, DEBUG for iterations)
        _logger = logging.getLogger("CERTUS")
        if "iterations=" in msg or "Polish L-BFGS-B" in msg:
            _logger.debug("[%5.2f%%] %s", g, msg)
        else:
            _logger.info("[%5.2f%%] %s", g, msg)
        self._root(int(min(10000, max(0, round(g * 100.0)))), msg)

    def scoped(self, lo: float, hi: float) -> Callable[[float | int, str], None]:
        lo = float(np.clip(lo, 0.0, 100.0))
        hi = float(max(lo, min(100.0, float(hi))))
        span = max(1e-9, hi - lo)
        coord = self

        def inner(p_local: float | int, msg: str) -> None:
            pl = float(np.clip(float(p_local), 0.0, 100.0))
            g = lo + span * (pl / 100.0)
            coord.emit(g, msg)

        return inner

    def finish(self, msg: str) -> None:
        self._last = 100.0
        logging.getLogger("CERTUS").info("[100.00%%] %s", msg)
        self._root(10000, msg)


def _spl_rmse_improves_meaningfully(rmse_ref: float, rmse_cand: float) -> bool:
    """True if candidate RMSE beats the reference by more than numerical / tie noise."""
    if not (np.isfinite(rmse_cand) and np.isfinite(rmse_ref)):
        return False
    rr = float(rmse_ref)
    rc = float(rmse_cand)
    if rc >= rr:
        return False
    min_gain = max(1e-7, 1e-4 * max(abs(rr), 1e-12))
    return (rr - rc) > min_gain


def _spl_rmse_regression_exceeds_tolerance(
    cfg: SplineOptConfig,
    rmse_ref: float,
    rmse_cand: float,
) -> bool:
    """True when RMSE regression is larger than configured tolerance.

    Tolerances are optional config fields for explicit manual mesh edits:
    - ``manual_node_insert_max_rmse_regression_abs``
    - ``manual_node_insert_max_rmse_regression_rel``

    Default absolute tolerance is 5e-5 to avoid rejecting negligible regressions
    caused by optimizer noise on explicit manual mesh edits.
    """
    if not (np.isfinite(rmse_ref) and np.isfinite(rmse_cand)):
        return True
    rr = float(rmse_ref)
    rc = float(rmse_cand)
    if rc <= rr:
        return False

    abs_tol = float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5)
    rel_tol = float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0)
    allowed = max(abs_tol, rel_tol * max(abs(rr), 1e-12))
    return (rc - rr) > allowed


def _validated_extra_sigma_knots(base_sigma_knots: np.ndarray, extra_sigma_knots: np.ndarray) -> np.ndarray:
    """Return filtered extra sigma knots strictly inside the base range (no duplicates)."""
    sk = np.asarray(base_sigma_knots, dtype=np.float64).ravel()
    extra_raw = np.asarray(extra_sigma_knots, dtype=np.float64).ravel()
    if sk.size < 2 or extra_raw.size == 0:
        return np.empty(0, dtype=np.float64)

    # Filter out non-finite values
    extra_raw = extra_raw[np.isfinite(extra_raw)]
    if extra_raw.size == 0:
        return np.empty(0, dtype=np.float64)

    sigma_lo = float(sk[0])
    sigma_hi = float(sk[-1])
    span = max(abs(sigma_lo), abs(sigma_hi), 1.0)
    tol = max(1e-12, 1e-6 * span)

    valid_list = []
    # Sort to make comparison easier
    extra_sorted = np.sort(extra_raw)

    for val in extra_sorted:
        # 1. Check the boundaries
        if val <= (sigma_lo + tol) or val >= (sigma_hi - tol):
            continue

        # 2. Check distance against existing knots
        if np.any(np.abs(sk - val) <= tol):
            continue

        # 3. Check distance against knots already accepted in this loop
        if valid_list and (val - valid_list[-1]) <= tol:
            continue

        valid_list.append(val)

    return np.array(valid_list, dtype=np.float64)


def _should_skip_manual_insert_for_equal_mesh(
    sk_new: np.ndarray,
    sk: np.ndarray,
    *,
    offset_changed: bool,
    force_reopt: bool,
) -> bool:
    """True when manual insert can be skipped because nothing meaningful changed."""
    if bool(force_reopt):
        return False
    if bool(offset_changed):
        return False
    return bool(sk_new.size == sk.size and np.allclose(sk_new, sk, rtol=1e-10, atol=1e-12))





def _sigma_knot_difference_for_log(
    source_sigma_knots: np.ndarray | None, reference_sigma_knots: np.ndarray | None
) -> np.ndarray:
    src = _sorted_finite_sigma_knots_for_log(source_sigma_knots)
    ref = _sorted_finite_sigma_knots_for_log(reference_sigma_knots)
    if src.size == 0:
        return np.empty(0, dtype=np.float64)
    if ref.size == 0:
        return src.copy()
    used = np.zeros(ref.size, dtype=bool)
    missing: list[float] = []
    for value in src:
        tol = max(1e-12, 1e-8 * max(abs(float(value)), 1.0))
        idx = np.where((~used) & (np.abs(ref - float(value)) <= tol))[0]
        if idx.size:
            used[int(idx[0])] = True
        else:
            missing.append(float(value))
    return np.asarray(missing, dtype=np.float64)


def _sigma_knots_to_lambda_nm_for_log(sigma_knots: np.ndarray | None) -> np.ndarray:
    sig = _sorted_finite_sigma_knots_for_log(sigma_knots)
    if sig.size == 0:
        return np.empty(0, dtype=np.float64)
    return np.sort(1.0 / np.maximum(sig, 1e-30))


def _format_lambda_knots_nm_for_log(
    lambda_knots_nm: np.ndarray | None, *, precision: int = 1, max_items: int = 6
) -> str:
    lam = np.asarray(lambda_knots_nm if lambda_knots_nm is not None else [], dtype=np.float64).ravel()
    lam = lam[np.isfinite(lam) & (lam > 0.0)]
    if lam.size == 0:
        return "[]"
    lam = np.sort(lam)
    if lam.size <= int(max_items):
        return "[" + ", ".join(f"{float(v):.{precision}f}" for v in lam) + "]"
    head = [f"{float(v):.{precision}f}" for v in lam[:3]]
    tail = [f"{float(v):.{precision}f}" for v in lam[-2:]]
    return "[" + ", ".join([*head, "...", *tail]) + "]"


def _sigma_mesh_change_summary_for_log(
    before_sigma_knots: np.ndarray | None, after_sigma_knots: np.ndarray | None
) -> dict[str, Any]:
    before_sigma = _sorted_finite_sigma_knots_for_log(before_sigma_knots)
    after_sigma = _sorted_finite_sigma_knots_for_log(after_sigma_knots)
    removed_sigma = _sigma_knot_difference_for_log(before_sigma, after_sigma)
    added_sigma = _sigma_knot_difference_for_log(after_sigma, before_sigma)
    before_lambda = _sigma_knots_to_lambda_nm_for_log(before_sigma)
    after_lambda = _sigma_knots_to_lambda_nm_for_log(after_sigma)
    removed_lambda = _sigma_knots_to_lambda_nm_for_log(removed_sigma)
    added_lambda = _sigma_knots_to_lambda_nm_for_log(added_sigma)
    return {
        "mesh_delta_k": int(after_sigma.size - before_sigma.size),
        "mesh_removed_count": int(removed_sigma.size),
        "mesh_added_count": int(added_sigma.size),
        "mesh_before_lambda_summary": _format_lambda_knots_nm_for_log(before_lambda),
        "mesh_after_lambda_summary": _format_lambda_knots_nm_for_log(after_lambda),
        "mesh_removed_lambda_summary": _format_lambda_knots_nm_for_log(removed_lambda),
        "mesh_added_lambda_summary": _format_lambda_knots_nm_for_log(added_lambda),
    }


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

    _log_spline_pipeline_json(
        log,
        "manual_node_insert_attempt",
        seq="05b",
        op_id=op_id,
        K_before=K_before,
        K_after=K_new,
        extra_sigma_knots=extra_sorted.tolist(),
        rmse_ref=float(rmse_ref),
        maxfun=mf_ins,
        explicit_mesh_edit=bool(target_raw.size > 0),
        explicit_k_reduction=bool(target_raw.size > 0 and K_new < K_before),
        **mesh_summary,
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
        _log_spline_pipeline_json(
            log,
            "manual_node_insert_rejected",
            seq="05b",
            op_id=op_id,
            reason="rmse_candidate_not_finite",
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=None,
            extra_sigma_knots=extra_sorted.tolist(),
            explicit_mesh_edit=bool(is_explicit_mesh_edit),
            **mesh_summary,
        )
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | RMSE ref=%.8f cand=n/a (candidate RMSE not finite) - rollback.",
            op_id,
            rmse_ref,
        )
        return base_result

    if (not is_explicit_k_reduction) and _spl_rmse_regression_exceeds_tolerance(cfg, rmse_ref, rmse_cand):
        _log_spline_pipeline_json(
            log,
            "manual_node_insert_rejected",
            seq="05b",
            op_id=op_id,
            reason="rmse_regression_exceeds_tolerance",
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=float(rmse_cand) if np.isfinite(rmse_cand) else None,
            extra_sigma_knots=extra_sorted.tolist(),
            explicit_mesh_edit=bool(is_explicit_mesh_edit),
            regression_abs=(float(rmse_cand - rmse_ref) if np.isfinite(rmse_cand) else None),
            tolerance_abs=float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5),
            tolerance_rel=float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0),
            **mesh_summary,
        )
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | RMSE ref=%.8f cand=%s | regression=%+.8f > allowed=%+.8f (tol_abs=%.1e, tol_rel=%.1e) - rollback.",
            op_id,
            rmse_ref,
            f"{rmse_cand:.8f}" if np.isfinite(rmse_cand) else "n/a",
            float(rmse_cand - rmse_ref) if np.isfinite(rmse_cand) else float("nan"),
            float(
                max(
                    float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5),
                    float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0)
                    * max(abs(rmse_ref), 1e-12),
                )
            ),
            float(getattr(cfg, "manual_node_insert_max_rmse_regression_abs", 5e-5) or 5e-5),
            float(getattr(cfg, "manual_node_insert_max_rmse_regression_rel", 0.0) or 0.0),
        )
        return base_result

    if is_explicit_k_reduction and rmse_cand > rmse_ref:
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Explicit K reduction accepted despite RMSE regression: attempt=%s | K %d -> %d | RMSE %.8f -> %.8f.",
            op_id,
            K_before,
            K_new,
            rmse_ref,
            rmse_cand,
        )

    if not is_explicit_mesh_edit and not _spl_rmse_improves_meaningfully(rmse_ref, rmse_cand):
        _log_spline_pipeline_json(
            log,
            "manual_node_insert_rejected",
            seq="05b",
            op_id=op_id,
            K_before=K_before,
            K_after=K_new,
            rmse_ref=float(rmse_ref),
            rmse_cand=float(rmse_cand) if np.isfinite(rmse_cand) else None,
            extra_sigma_knots=extra_sorted.tolist(),
            **mesh_summary,
        )
        log.debug(
            "INDEX_SPLINE [MANUAL NODE INSERT] Rejected: attempt=%s | RMSE ref=%.8f cand=%s (no meaningful gain) - rollback.",
            op_id,
            rmse_ref,
            f"{rmse_cand:.8f}" if np.isfinite(rmse_cand) else "n/a",
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

    _log_spline_pipeline_json(
        log,
        "manual_node_insert_accepted",
        seq="05b",
        op_id=op_id,
        K_before=K_before,
        K_after=K_new,
        rmse_before=float(rmse_ref),
        rmse_after=rmse_new,
        extra_sigma_knots=extra_sorted.tolist(),
        explicit_mesh_edit=bool(is_explicit_mesh_edit),
        explicit_k_reduction=bool(is_explicit_k_reduction),
        **mesh_summary,
    )
    delta_ns_final = float(out.get("substrate_n_offset", 0.0))
    n_sub_eff_avg = float(np.mean(np.asarray(out.get("n_sub_effective", cfg.n_sub), dtype=np.float64).ravel()))
    log.info(
        "INDEX_SPLINE [MANUAL NODE INSERT] ACCEPTED: attempt=%s | K %d -> %d | RMSE %.8f -> %.8f | d=%.4f nm | delta_ns=%+.6f | n_sub_eff=%.6f | before_lambda=%s | after_lambda=%s | removed=%s | added=%s",
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


def _knots_cache_key(knots: np.ndarray) -> tuple[float, ...]:
    """Round knots to 15 decimals and return as hashable tuple."""
    arr = np.asarray(knots, dtype=np.float64).ravel()
    return tuple(float(v) for v in np.round(arr, decimals=15))


def _fmt_d_nm(v) -> str:
    """Format thickness value for log messages."""
    try:
        dv = float(v)
    except (TypeError, ValueError):
        return "n/a"
    return f"{dv:.3f} nm" if np.isfinite(dv) else "n/a"


def _meshes_match(a: np.ndarray, b: np.ndarray) -> bool:
    """Check if two sigma meshes are numerically identical within floating-point tolerance."""
    a1 = np.asarray(a, dtype=np.float64).ravel()
    b1 = np.asarray(b, dtype=np.float64).ravel()
    if a1.size != b1.size or a1.size == 0:
        return False
    span = max(abs(float(b1[-1] - b1[0])), 1.0)
    atol = max(1e-12, 1e-9 * span)
    return bool(np.allclose(a1, b1, rtol=0.0, atol=atol))


def _candidate_mesh_matches_target(cand: dict | None, target_knots: np.ndarray) -> bool:
    """Check if a candidate result dict has the expected sigma mesh."""
    if not isinstance(cand, dict):
        return False
    return _meshes_match(np.asarray(cand.get("sigma_knots", []), dtype=np.float64), target_knots)


def _auto_clean_cache_result(
    cache: dict,
    cache_key: tuple[float, ...],
    cand: dict | None,
    rmse_value: float,
) -> tuple[dict | None, float]:
    payload = (cand, float(rmse_value))
    cache[cache_key] = payload
    return payload


def _auto_clean_prescreen_result(
    *,
    log: "logging.Logger",
    cache: dict,
    cache_key: tuple[float, ...],
    cand: dict,
    rmse_value: float,
    test_knots: np.ndarray,
    nominal_rmse: float,
    tolerance: float,
    prescreen_margin_abs: float,
    candidate_polish_maxfun: int,
    prescreen_maxfun: int,
) -> tuple[dict | None, float] | None:
    k_sz = int(np.asarray(test_knots, dtype=np.float64).size)
    if not np.isfinite(rmse_value):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] prescreen produced non-finite RMSE | K=%d", k_sz)
        return _auto_clean_cache_result(cache, cache_key, None, float("inf"))
    if not _candidate_mesh_matches_target(cand, test_knots):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] prescreen returned inconsistent mesh | K_target=%d | rmse_fast=%.8f", k_sz, float(rmse_value))
        return _auto_clean_cache_result(cache, cache_key, None, rmse_value)
    gate = float(nominal_rmse + tolerance + prescreen_margin_abs)
    if rmse_value > gate:
        log.debug("INDEX_SPLINE [AUTO_CLEAN] prescreen rejected variant | K=%d | rmse_fast=%.8f | gate=%.8f", k_sz, float(rmse_value), float(gate))
        return _auto_clean_cache_result(cache, cache_key, None, rmse_value)
    if int(candidate_polish_maxfun) <= int(prescreen_maxfun):
        return _auto_clean_cache_result(cache, cache_key, cand, rmse_value)
    return None


def _eval_clean_variant(
    test_knots: np.ndarray,
    stop_event,
    step_eval_cache: dict,
    cfg_prescreen,
    cfg_candidate,
    best_result_out: dict,
    nominal_rmse: float,
    tolerance: float,
    prescreen_enabled: bool,
    prescreen_margin_abs: float,
    candidate_polish_maxfun: int,
    prescreen_maxfun: int,
    log: "logging.Logger",
) -> tuple[dict | None, float]:
    """Evaluate a single knot-removal variant with optional prescreen + full polish.

    Returns (result_dict_or_None, rmse).
    """
    if stop_event.is_set():
        return None, float("inf")

    cache_key = _knots_cache_key(test_knots)
    cached = step_eval_cache.get(cache_key)
    if cached is not None:
        return cached

    warm_seed = best_result_out
    if prescreen_enabled:
        cand_fast = insert_manual_sigma_nodes(cfg_prescreen, best_result_out, stop_event, np.asarray([], dtype=np.float64), target_sigma_knots=test_knots, force_reopt=True, live_cb=None)
        rmse_fast = float(cand_fast.get("rmse", float("inf")))
        prescreen_out = _auto_clean_prescreen_result(
            log=log,
            cache=step_eval_cache,
            cache_key=cache_key,
            cand=cand_fast,
            rmse_value=rmse_fast,
            test_knots=test_knots,
            nominal_rmse=nominal_rmse,
            tolerance=tolerance,
            prescreen_margin_abs=prescreen_margin_abs,
            candidate_polish_maxfun=candidate_polish_maxfun,
            prescreen_maxfun=prescreen_maxfun,
        )
        if prescreen_out is not None:
            return prescreen_out
        if int(candidate_polish_maxfun) > int(prescreen_maxfun):
            warm_seed = cand_fast

    cand = insert_manual_sigma_nodes(cfg_candidate, warm_seed, stop_event, np.asarray([], dtype=np.float64), target_sigma_knots=test_knots, force_reopt=True, live_cb=None)
    rmse_cand = float(cand.get("rmse", float("inf")))
    if not np.isfinite(rmse_cand):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] candidate polish produced non-finite RMSE | K=%d", int(np.asarray(test_knots, dtype=np.float64).size))
    if not _candidate_mesh_matches_target(cand, test_knots):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] candidate polish returned inconsistent mesh | K_target=%d | rmse=%.8f", int(np.asarray(test_knots, dtype=np.float64).size), float(rmse_cand))
        return _auto_clean_cache_result(step_eval_cache, cache_key, None, rmse_cand)
    log.debug("INDEX_SPLINE [AUTO_CLEAN] candidate polish done | K=%d | rmse=%.8f | delta_nominal=%+.8f | within_tol=%s", int(np.asarray(test_knots, dtype=np.float64).size), float(rmse_cand), float(rmse_cand - nominal_rmse) if np.isfinite(rmse_cand) else float("nan"), str(rmse_cand <= nominal_rmse + tolerance) if np.isfinite(rmse_cand) else "n/a")
    return _auto_clean_cache_result(step_eval_cache, cache_key, cand, rmse_cand)



@dataclass
class AutoCleanKnotsContext:
    tolerance: float
    nominal_rmse: float
    progress_cb: Any | None
    progress_units_total: int
    progress_units_done: int

    def emit_progress(self, units_inc: int, message: str) -> None:
        if self.progress_cb is None:
            return
        self.progress_units_done = int(min(self.progress_units_total, self.progress_units_done + max(int(units_inc), 0)))
        pct = 99.0 * (float(self.progress_units_done) / float(max(self.progress_units_total, 1)))
        self.progress_cb(float(np.clip(pct, 0.0, 99.0)), str(message))

    def decisive_improvement_margin(self) -> float:
        return float(max(5.0e-6, 0.25 * float(max(self.tolerance, 0.0))))

    def have_decisive_local_candidate(self, rmse_value: float) -> bool:
        return bool(np.isfinite(rmse_value) and rmse_value <= (self.nominal_rmse - self.decisive_improvement_margin()))


def worker_spline_auto_clean_knots(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    target_sigma_knots: np.ndarray,
    tolerance: float,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: iteratively remove the least sensitive knots until RMSE degrades by more than tolerance."""

    log = logging.getLogger("CERTUS")
    step_eval_cache: dict[tuple[float, ...], tuple[dict[str, Any] | None, float]] = {}

    pull_enabled = bool(getattr(cfg, "auto_clean_neighbor_pull_enabled", True))
    pull_ratios_raw = getattr(cfg, "auto_clean_neighbor_pull_ratios", (0.20,))
    pull_ratios: list[float] = []
    if pull_enabled:
        try:
            for rr in np.asarray(pull_ratios_raw, dtype=np.float64).ravel():
                rv = float(rr)
                if np.isfinite(rv) and 0.0 < rv < 0.49:
                    pull_ratios.append(rv)
        except (ValueError, TypeError):
            pull_ratios = [0.20]
        if not pull_ratios:
            pull_ratios = [0.20]

    strict_tol_mode = bool(float(tolerance) <= 1e-12)

    # Conditional local refinement around the best per-removal variant.
    # We exclusively respect the user's choice (GUI checkbox). The
    # forced deactivation in strict mode was masking valid removals.
    local_refine_enabled = bool(getattr(cfg, "auto_clean_neighbor_pull_local_refine_enabled", False))
    local_refine_rel_step = float(getattr(cfg, "auto_clean_neighbor_pull_local_refine_rel_step", 0.05) or 0.05)
    local_refine_rel_step = float(np.clip(local_refine_rel_step, 0.005, 0.20))

    # Performance knobs (absolute acceptance criterion remains unchanged).
    candidate_polish_maxfun = int(max(120, int(getattr(cfg, "auto_clean_candidate_polish_maxfun", 2000) or 2000)))
    prescreen_enabled = bool(getattr(cfg, "auto_clean_candidate_prescreen_enabled", True))
    prescreen_maxfun = int(max(80, int(getattr(cfg, "auto_clean_candidate_prescreen_maxfun", 120) or 120)))
    prescreen_margin_default = 0.0 if strict_tol_mode else max(2.0e-4, 2.0 * float(max(tolerance, 0.0)))
    prescreen_margin_abs = float(
        getattr(cfg, "auto_clean_candidate_prescreen_margin_abs", prescreen_margin_default) or prescreen_margin_default
    )
    if not np.isfinite(prescreen_margin_abs) or prescreen_margin_abs < 0.0:
        prescreen_margin_abs = float(prescreen_margin_default)

    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] start | tolerance=+%.6f | strict_mode=%s | neighbor_pull=%s | pull_ratios=%s | local_refine=%s(step=%.4f) | prescreen=%s(maxfun=%d, margin=+%.6f) | candidate_maxfun=%d",
        float(tolerance),
        "on" if strict_tol_mode else "off",
        "on" if pull_enabled else "off",
        ",".join(f"{r:.3f}" for r in pull_ratios) if pull_enabled else "n/a",
        "on" if (pull_enabled and local_refine_enabled) else "off",
        float(local_refine_rel_step),
        "on" if prescreen_enabled else "off",
        int(prescreen_maxfun),
        float(prescreen_margin_abs),
        int(candidate_polish_maxfun),
    )





    current_result = _copy.deepcopy(base_result)
    current_knots = np.sort(target_sigma_knots)
    if current_knots.size >= 2:
        _diff = np.diff(current_knots)
        if np.any(_diff <= 0.0):
            log.warning(
                "INDEX_SPLINE [AUTO_CLEAN] target mesh has non-strict spacing | K=%d | min_gap=%+.3e",
                int(current_knots.size),
                float(np.min(_diff)) if _diff.size else float("nan"),
            )
        log.info(
            "INDEX_SPLINE [AUTO_CLEAN] target mesh summary | K_target=%d | sigma_min=%.8e | sigma_max=%.8e | span=%.8e",
            int(current_knots.size),
            float(current_knots[0]),
            float(current_knots[-1]),
            float(current_knots[-1] - current_knots[0]),
        )

    if progress_cb:
        progress_cb(0.0, "Cleaning: calculating nominal RMSE...")

    nominal_result = insert_manual_sigma_nodes(
        cfg,
        current_result,
        stop_event,
        np.asarray([], dtype=np.float64),
        target_sigma_knots=current_knots,
        force_reopt=True,
        live_cb=live_cb,
    )
    if stop_event.is_set():
        return None

    nominal_rmse = float(nominal_result.get("rmse", float("inf")))
    if not np.isfinite(nominal_rmse):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] abort: nominal RMSE is non-finite.")
        return None
    _d_nom = nominal_result.get("d_nm", float("nan"))
    try:
        _d_nom_f = float(_d_nom)
    except (TypeError, ValueError):
        _d_nom_f = float("nan")
    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] nominal reference | K=%d | RMSE=%.8f | d=%s",
        int(current_knots.size),
        float(nominal_rmse),
        f"{_d_nom_f:.3f} nm" if np.isfinite(_d_nom_f) else "n/a",
    )

    best_result_out = nominal_result
    active_knots = current_knots.copy()
    cfg_candidate = cfg.replace(manual_node_insert_polish_maxfun=int(candidate_polish_maxfun))
    cfg_prescreen = cfg.replace(manual_node_insert_polish_maxfun=int(min(candidate_polish_maxfun, prescreen_maxfun)))

    # Build a conservative work budget so progress can move during long iterative tests.
    initial_k = int(max(active_knots.size, 0))
    max_pull_variants = 1 + (3 * len(pull_ratios) if pull_enabled else 0)
    max_refine_variants = 8 if (pull_enabled and local_refine_enabled) else 0
    progress_units_total = 1  # nominal RMSE initialization
    for kk in range(initial_k, 2, -1):
        n_removed_candidates = max(0, kk - 2)
        progress_units_total += n_removed_candidates * (max_pull_variants + max_refine_variants)
        progress_units_total += 1  # validation deep polish slot per step

    ctx = AutoCleanKnotsContext(
        tolerance=tolerance,
        nominal_rmse=nominal_rmse,
        progress_cb=progress_cb,
        progress_units_total=progress_units_total,
        progress_units_done=1,
    )











    step = 0
    while True:
        if stop_event.is_set():
            break
        K = active_knots.size
        if K <= 2:
            break
        step_eval_cache.clear()
        log.info(
            "INDEX_SPLINE [AUTO_CLEAN] step=%d start | K=%d | nominal_rmse=%.8f | acceptance_rmse<=%.8f",
            int(step + 1),
            int(K),
            float(nominal_rmse),
            float(nominal_rmse + tolerance),
        )

        best_cand_rmse = float("inf")
        best_cand_result = None
        best_cand_knots = None
        best_cand_variant = "baseline"

        top_n_sensitivity = int(max(1, int(getattr(cfg, "auto_clean_top_n_sensitivity", 4) or 4)))
        inner_indices = list(range(1, K - 1))

        if len(inner_indices) > top_n_sensitivity:
            inner_indices = _sensitivity_rank_inner_indices(
                cfg, active_knots, best_result_out, K, inner_indices,
                top_n_sensitivity, tolerance, strict_tol_mode, log, step,
            )

        for i in inner_indices:
            if stop_event.is_set():
                break

            variants = _build_local_pull_variants(active_knots, i, pull_enabled, pull_ratios)
            log.debug(
                "INDEX_SPLINE [AUTO_CLEAN] step=%d evaluating removal idx=%d/%d | variants=%d",
                int(step + 1),
                int(i),
                int(K - 2),
                int(len(variants)),
            )
            local_best_rmse = float("inf")
            local_best_knots = None
            local_best_variant = "baseline"

            def _update_best_candidate(vname: str, tk: np.ndarray, is_refine: bool = False) -> float:
                nonlocal best_cand_rmse, best_cand_result, best_cand_knots, best_cand_variant
                nonlocal local_best_rmse, local_best_knots, local_best_variant

                cand, cand_rmse = _eval_clean_variant(
                    tk, stop_event, step_eval_cache,
                    cfg_prescreen, cfg_candidate, best_result_out,
                    nominal_rmse, tolerance, prescreen_enabled,
                    prescreen_margin_abs, candidate_polish_maxfun,
                    prescreen_maxfun, log,
                )
                if cand is not None:
                    if cand_rmse < best_cand_rmse:
                        best_cand_rmse = cand_rmse
                        best_cand_result = cand
                        best_cand_knots = tk
                        best_cand_variant = str(vname)
                    if cand_rmse < local_best_rmse:
                        local_best_rmse = cand_rmse
                        local_best_knots = tk
                        local_best_variant = str(vname)
                else:
                    gate = float(nominal_rmse + tolerance + prescreen_margin_abs)
                    if is_refine:
                        kind_str = f"refine_variant={vname}"
                    elif vname == "baseline":
                        kind_str = "baseline"
                    else:
                        kind_str = f"variant={vname}"

                    if np.isfinite(cand_rmse):
                        log.debug(
                            "INDEX_SPLINE [AUTO_CLEAN] step=%d idx=%d %s rejected before polish | rmse_fast=%.8f | gate=%.8f",
                            int(step + 1),
                            int(i),
                            kind_str,
                            float(cand_rmse),
                            float(gate),
                        )
                    else:
                        log.debug(
                            "INDEX_SPLINE [AUTO_CLEAN] step=%d idx=%d %s failed/non-finite",
                            int(step + 1),
                            int(i),
                            kind_str,
                        )
                return cand_rmse

            # 1. Evaluate baseline first (always variants[0])
            baseline_name, baseline_knots = variants[0]
            ctx.emit_progress(1, f"Step {step + 1}: testing knot removal {i}/{K - 2} [{baseline_name}]...")
            baseline_rmse = _update_best_candidate(baseline_name, baseline_knots)

            # Early-exit: if baseline already improves RMSE by more than a full tolerance
            # margin, pull-variants cannot change the final outcome meaningfully.
            if baseline_name == "baseline" and np.isfinite(baseline_rmse) and baseline_rmse < nominal_rmse - tolerance:
                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d knot=%d early-exit (baseline rmse=%.8f << nominal-tol %.8f)",
                    int(step + 1),
                    int(i),
                    float(baseline_rmse),
                    float(nominal_rmse - tolerance),
                )
            else:
                # 2. Evaluate remaining pull-variants sequentially.
                # This avoids a backlog of stale computations that would continue running
                # even after a clearly better candidate has already been found.
                remaining_variants = variants[1:]
                if (
                    remaining_variants
                    and not stop_event.is_set()
                    and not ctx.have_decisive_local_candidate(local_best_rmse)
                ):
                    for vname, tk in remaining_variants:
                        if stop_event.is_set() or ctx.have_decisive_local_candidate(local_best_rmse):
                            break
                        ctx.emit_progress(1, f"Step {step + 1}: testing knot removal {i}/{K - 2} [{vname}]...")
                        try:
                            _update_best_candidate(vname, tk)
                        except (ValueError, TypeError, RuntimeError) as e:
                            log.debug("INDEX_SPLINE [AUTO_CLEAN] variant %s failed: %s", vname, e)

            # Conditional local 2D refinement around local best for this removed index.
            refine_trigger = np.isfinite(local_best_rmse) and (
                (local_best_rmse <= nominal_rmse + tolerance) or (local_best_rmse <= nominal_rmse + 1.25 * tolerance)
            )
            if (
                refine_trigger
                and local_best_knots is not None
                and not stop_event.is_set()
                and not ctx.have_decisive_local_candidate(local_best_rmse)
            ):
                refine_variants = _build_local_refine_variants(
                    active_knots, i, local_best_knots,
                    pull_enabled, local_refine_enabled, local_refine_rel_step,
                )
                if refine_variants:
                    for vname, tk in refine_variants:
                        if stop_event.is_set() or ctx.have_decisive_local_candidate(local_best_rmse):
                            break
                        ctx.emit_progress(1, f"Step {step + 1}: 2D refinement [{vname}]...")
                        try:
                            _update_best_candidate(vname, tk, is_refine=True)
                        except (ValueError, TypeError, RuntimeError) as e:
                            log.debug("INDEX_SPLINE [AUTO_CLEAN] refine variant %s failed: %s", vname, e)

                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] local refine summary | step=%d | removed_idx=%d | best_variant=%s | local_rmse=%.8f",
                    int(step + 1),
                    int(i),
                    str(local_best_variant),
                    float(local_best_rmse),
                )
            else:
                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d removed_idx=%d local refine skipped | trigger=%s | have_seed=%s",
                    int(step + 1),
                    int(i),
                    str(refine_trigger),
                    str(local_best_knots is not None),
                )

        if stop_event.is_set():
            break

        if not np.isfinite(best_cand_rmse):
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] stop: no finite candidate at step=%d | K=%d",
                int(step + 1),
                int(K),
            )
            if progress_cb:
                progress_cb(-1, "Cleaning finished: no finite candidate found for knot removal.")
            break

        if best_cand_rmse <= nominal_rmse + tolerance:
            # The selected candidate is already a fully polished K-1 solution.
            # Re-running the exact same target mesh creates redundant 05b work and stale
            # follow-up jobs without improving the acceptance guarantee meaningfully.
            ctx.emit_progress(1, f"Accepting best removal [{best_cand_variant}]...")
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] step=%d candidate accepted for validation | variant=%s | K_before=%d -> K_after=%d | rmse_candidate=%.8f | nominal=%.8f | delta=%+.8f",
                int(step + 1),
                str(best_cand_variant),
                int(K),
                int(best_cand_knots.size) if best_cand_knots is not None else -1,
                float(best_cand_rmse),
                float(nominal_rmse),
                float(best_cand_rmse - nominal_rmse),
            )
            final_cand = best_cand_result if best_cand_result is not None else None
            final_rmse = float(best_cand_rmse)
            d_prev = _fmt_d_nm(best_result_out.get("d_nm"))
            d_new = _fmt_d_nm(final_cand.get("d_nm")) if isinstance(final_cand, dict) else "n/a"

            final_mesh_ok = _candidate_mesh_matches_target(final_cand, np.asarray(best_cand_knots, dtype=np.float64))

            if final_cand is not None and final_mesh_ok and final_rmse <= nominal_rmse + tolerance:
                active_knots = np.asarray(best_cand_knots, dtype=np.float64).ravel().copy()
                best_result_out = final_cand
                if live_cb is not None:
                    live_cb(best_result_out)
                step += 1
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d accepted | variant=%s | K=%d | RMSE=%.8f | nominal_delta=%+.8f",
                    int(step),
                    str(best_cand_variant),
                    int(active_knots.size),
                    float(final_rmse),
                    float(final_rmse - nominal_rmse),
                )
                if progress_cb:
                    progress_cb(
                        -1,
                        f"Knot removed! [{best_cand_variant}] K={active_knots.size}. RMSE={final_rmse:.6f} (+{final_rmse - nominal_rmse:.6f}) | d: {d_prev} -> {d_new}",
                    )
            else:
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d rejected after final consistency check | variant=%s | mesh_ok=%s | RMSE=%.8f | nominal_delta=%+.8f | tolerance=+%.8f",
                    int(step + 1),
                    str(best_cand_variant),
                    str(final_mesh_ok),
                    float(final_rmse),
                    float(final_rmse - nominal_rmse),
                    float(tolerance),
                )
                if progress_cb:
                    progress_cb(
                        -1,
                        f"Cleaning finished: removal rejected at final consistency check (mesh mismatch or +{final_rmse - nominal_rmse:.6f} > tolerance) | d: {d_prev} -> {d_new}.",
                    )
                break
        else:
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] stop: best candidate exceeds tolerance | step=%d | best_variant=%s | best_delta=%+.8f | tolerance=+%.8f",
                int(step + 1),
                str(best_cand_variant),
                float(best_cand_rmse - nominal_rmse),
                float(tolerance),
            )
            if progress_cb:
                progress_cb(
                    -1, f"Cleaning finished: best candidate exceeds tolerance (+{best_cand_rmse - nominal_rmse:.6f})."
                )
            break

    # --- Final deep re-polish of cleaned mesh (full budget, mirrors local re-opt button) ---
    if step > 0 and not stop_event.is_set():
        final_deep_maxfun = int(
            max(
                candidate_polish_maxfun + 1,
                int(
                    getattr(cfg, "auto_clean_final_polish_maxfun", None)
                    or int(getattr(cfg, "polish_maxfun", 8000) or 8000)
                ),
            )
        )
        if final_deep_maxfun > candidate_polish_maxfun:
            if progress_cb:
                progress_cb(99.0, f"Deep re-polish of final mesh K={active_knots.size} (maxfun={final_deep_maxfun})...")
            cfg_final_deep = cfg.replace(manual_node_insert_polish_maxfun=final_deep_maxfun)
            final_knots = active_knots.copy()
            deep_final = insert_manual_sigma_nodes(
                cfg_final_deep,
                _copy.deepcopy(best_result_out),
                stop_event,
                np.asarray([], dtype=np.float64),
                target_sigma_knots=final_knots,
                force_reopt=True,
                live_cb=live_cb,
            )
            if not stop_event.is_set():
                deep_final_rmse = float(deep_final.get("rmse", float("inf")))
                _rmse_before_deep = float(best_result_out.get("rmse", float("nan")))
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] final deep re-polish | K=%d | RMSE %.8f -> %.8f | delta=%+.8f",
                    int(final_knots.size),
                    float(_rmse_before_deep),
                    float(deep_final_rmse),
                    float(deep_final_rmse - _rmse_before_deep),
                )
                if np.isfinite(deep_final_rmse):
                    best_result_out = deep_final
                    if live_cb is not None:
                        live_cb(best_result_out)

    was_canceled = bool(stop_event.is_set())
    if progress_cb:
        if was_canceled:
            progress_cb(
                -1,
                f"Advanced cleaning canceled. K={active_knots.size} | RMSE={float(best_result_out.get('rmse', 0)):.6f}",
            )
        else:
            progress_cb(
                100.0,
                f"Advanced cleaning finished. K={active_knots.size} | RMSE={float(best_result_out.get('rmse', 0)):.6f}",
            )

    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] done | canceled=%s | steps=%d | K_final=%d | RMSE_final=%.8f | RMSE_nominal=%.8f | delta_nominal=%+.8f",
        str(was_canceled),
        int(step),
        int(active_knots.size),
        float(best_result_out.get("rmse", float("nan"))),
        float(nominal_rmse),
        float(best_result_out.get("rmse", float("nan")) - nominal_rmse)
        if np.isfinite(float(best_result_out.get("rmse", float("nan"))))
        else float("nan"),
    )

    return best_result_out


def worker_spline_autoshift_delta_ns(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    target_sigma_knots: np.ndarray | None = None,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: find optimal delta_ns in [-0.01, 0.01] with Brent search.

    The worker first probes five evenly spaced points to build a valid local
    bracket, then refines the best minimum with ``scipy.optimize.minimize_scalar``
    using ``method=\"brent\"``. Each candidate receives an independent deep copy
    of ``base_result`` so ``insert_manual_sigma_nodes`` cannot corrupt the seed
    for subsequent evaluations.
    """

    log = logging.getLogger("CERTUS")

    n_sub_base = np.asarray(base_result.get("n_sub_base", cfg.n_sub), dtype=np.float64).ravel().copy()

    # --- helpers --------------------------------------------------------
    def _try_shift(d_ns: float, maxfun_override: int | None = None) -> tuple[dict | None, float]:
        """Run a full polish at *d_ns* and return (result, rmse)."""
        seed = _copy.deepcopy(base_result)  # isolation totale

        cfg_args = {
            "substrate_n_offset": d_ns,
            "substrate_n_base": n_sub_base.copy(),
            "n_sub": n_sub_base + d_ns,
        }
        if maxfun_override is not None:
            cfg_args["manual_node_insert_polish_maxfun"] = maxfun_override

        cfg_cand = cfg.replace(**cfg_args)

        try:
            cand = insert_manual_sigma_nodes(
                cfg_cand,
                seed,
                stop_event,
                np.asarray([], dtype=np.float64),
                target_sigma_knots=target_sigma_knots,
                force_reopt=True,
                progress_cb=None,
                live_cb=live_cb,
            )
        except (ValueError, TypeError, RuntimeError) as ex:
            log.warning("INDEX_SPLINE [AUTOSHIFT] cand %+.4f failed: %s", d_ns, ex)
            return None, float("inf")
        r = float(cand.get("rmse", float("inf")))
        return cand, r

    # --- 1D Brent search for optimal delta_ns ---
    from scipy.optimize import minimize_scalar

    best_result_out = _copy.deepcopy(base_result)
    best_rmse = float(best_result_out.get("rmse", float("inf")))
    best_dns = 0.0
    tested: dict[float, tuple[dict | None, float]] = {}
    eval_count = [0]
    max_brent_evals = 18

    def _f_for_brent(d_ns: float) -> float:
        if stop_event.is_set():
            return float("inf")
        d_key = round(float(d_ns), 6)
        if d_key in tested:
            return tested[d_key][1]
        cand, r = _try_shift(d_key, maxfun_override=1000)
        tested[d_key] = (cand, r)
        eval_count[0] += 1
        nonlocal best_result_out, best_rmse, best_dns
        if cand is not None and np.isfinite(r) and r < best_rmse - 1e-8:
            best_rmse = r
            best_result_out = cand
            best_dns = d_key
            log.info("INDEX_SPLINE [AUTOSHIFT] brent improved: dns=%+.6f RMSE=%.8f", d_key, r)
        if progress_cb:
            pct = 90.0 * float(min(eval_count[0], max_brent_evals)) / float(max_brent_evals)
            progress_cb(float(np.clip(pct, 0.0, 89.0)), f"Autoshift Brent eval {eval_count[0]} : delta_ns={d_key:+.6f}")
        return float(r) if np.isfinite(r) else float("inf")

    # Initial bracketing: 5 evenly spaced points to identify (a, b, c) with f(b) = min.
    bracket_pts = np.linspace(-0.01, 0.01, 5)
    for d_ns in bracket_pts:
        if stop_event.is_set():
            break
        _f_for_brent(float(d_ns))

    if not stop_event.is_set():
        finite_pts = sorted(
            ((d, tested[d][1]) for d in tested if np.isfinite(tested[d][1])),
            key=lambda t: t[0],
        )
        # Looks for a triplet bracketing a strict minimum.
        best_triplet = None
        for i in range(1, len(finite_pts) - 1):
            a, fa = finite_pts[i - 1]
            b, fb = finite_pts[i]
            c, fc = finite_pts[i + 1]
            if fb <= fa and fb <= fc:
                best_triplet = (a, b, c)
                break
        if best_triplet is not None:
            try:
                res = minimize_scalar(
                    _f_for_brent,
                    bracket=best_triplet,
                    method="brent",
                    options={"xtol": 5e-4, "maxiter": max_brent_evals},
                )
                log.info(
                    "INDEX_SPLINE [AUTOSHIFT] brent done | x=%+.6f | fun=%.8f | nit=%d",
                    float(res.x),
                    float(res.fun),
                    int(res.nit),
                )
            except (ValueError, RuntimeError) as ex:
                log.warning("INDEX_SPLINE [AUTOSHIFT] brent failed, fallback to grid best: %s", ex)
        else:
            log.info("INDEX_SPLINE [AUTOSHIFT] no strict bracket, keep grid best dns=%+.6f", best_dns)

    # --- Final deep reoptimization at the best delta ns ---
    if progress_cb:
        progress_cb(90.0, f"Autoshift: final deep re-optimization on delta ns = {best_dns:+.6f}...")

    final_cand, final_rmse = _try_shift(best_dns, maxfun_override=40000)
    if final_cand is not None and np.isfinite(final_rmse):
        best_result_out = final_cand
        best_rmse = final_rmse

    if progress_cb:
        progress_cb(100.0, f"Autoshift finished. Best shift: {best_dns:+.6f} | RMSE={best_rmse:.8f}")

    log.info(
        "INDEX_SPLINE [AUTOSHIFT] DONE | best_dns=%+.6f | best_rmse=%.8f",
        best_dns,
        best_rmse,
    )
    return best_result_out


def _pipeline_mesh_dimensions(
    cfg: SplineOptConfig,
) -> tuple[np.ndarray, int, int, int, float | None, float | None]:
    """Compute lambda array, bounds, and canonical mesh-derived SOL2 dimensions."""
    lam_arr = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    lam_min = float(np.min(lam_arr)) if lam_arr.size else None
    lam_max = float(np.max(lam_arr)) if lam_arr.size else None
    if lam_arr.size:
        sk_mesh = canonical_spline_sigma_knots(
            float(lam_min),
            float(lam_max),
            **_canonical_knots_min_lambda_kw(cfg),
        )
        k_mesh = int(np.asarray(sk_mesh).size)
    else:
        k_mesh = 12
    nseg_mesh = max(1, k_mesh - 1)
    dim_sol2 = 1 + 2 * k_mesh
    return lam_arr, k_mesh, nseg_mesh, dim_sol2, lam_min, lam_max


def _stop_with_snapshot_if_requested(
    stop_event: Event,
    coord: _WorkerProgressCoordinator,
    stop_msg: str,
    cfg: SplineOptConfig,
    result: dict,
) -> dict | None:
    """Finish worker and return snapshot when stop is requested."""
    if not stop_event.is_set():
        return None
    coord.finish(stop_msg)
    return snapshot_result_with_rmse_fit_meta(cfg, result)


def _log_worker_start_payload(
    log: logging.Logger,
    cfg: SplineOptConfig,
    *,
    lam_arr: np.ndarray,
    k_mesh: int,
    nseg_mesh: int,
    lam_min: float | None,
    lam_max: float | None,
) -> None:
    """Emit the structured worker-start payload."""
    _log_spline_pipeline_json(
        log,
        "worker_start",
        seq="01",
        n_lambda=int(lam_arr.size),
        lam_nm_min=lam_min,
        lam_nm_max=lam_max,
        d_bounds=(float(cfg.d_lo), float(cfg.d_hi)),
        data_type=str(getattr(cfg.data_type, "name", cfg.data_type)),
        polish_maxfun=int(cfg.polish_maxfun),
        optimization_mode="local_only",
        lnk_spline_stage_enabled=bool(getattr(cfg, "lnk_spline_stage_enabled", True)),
        node_mesh_spectral_polish_enabled=bool(getattr(cfg, "node_mesh_spectral_polish_enabled", True)),
        t_is_ratio=bool(cfg.t_is_ratio),
        weight_t=float(cfg.weight_t),
        weight_r=float(cfg.weight_r),
        K_sigma_mesh=int(k_mesh),
        n_seg_mesh=int(nseg_mesh),
    )


def _log_final_insert_enter(
    log: logging.Logger,
    sol_spline: dict,
    *,
    k_mesh: int,
    nseg_mesh: int,
) -> None:
    """Emit fixed-mesh final-stage entry payload."""
    _log_spline_pipeline_json(
        log,
        "worker_final_insert_enter",
        seq="05",
        rmse_before=float(sol_spline["rmse"]),
        fixed_mesh=True,
        K_nodes=int(k_mesh),
        n_seg_fixed=int(nseg_mesh),
    )


def _log_after_final_insert(
    log: logging.Logger,
    sol_spline: dict,
    out: dict,
    *,
    mwir_insert_accepted: bool = False,
) -> None:
    """Emit payload after fixed-mesh insertion stage."""
    _log_spline_pipeline_json(
        log,
        "worker_after_final_insert",
        seq="06",
        rmse_sol_spline=float(sol_spline["rmse"]),
        rmse_chosen=float(out["rmse"]),
        used_insert_result=bool(mwir_insert_accepted),
        mwir_insert_accepted=bool(mwir_insert_accepted),
    )


def _log_fixed_mesh_stage_summary(
    log: logging.Logger, k_mesh: int, nseg_mesh: int, rmse: float, delta_ns: float = 0.0
) -> None:
    """Emit human-readable fixed-mesh stage summary."""
    log.info(
        "PIPELINE [05/09] Fixed mesh baseline prepared after SOL2 hand-off (K=%d sigma knots, %d segments) | RMSE=%.6f | delta_ns=%+.6f | optional MWIR stage follows before k-floor and corridors",
        int(k_mesh),
        int(nseg_mesh),
        float(rmse),
        float(delta_ns),
    )


def _log_after_final_stage_summary(
    log: logging.Logger,
    rmse: float,
    *,
    mwir_stage_considered: bool,
    mwir_insert_accepted: bool,
) -> None:
    """Emit summary after fixed-mesh stage completion."""
    if mwir_insert_accepted:
        mwir_txt = "MWIR extra-node accepted"
    elif mwir_stage_considered:
        mwir_txt = "MWIR extra-node evaluated but not kept"
    else:
        mwir_txt = "MWIR extra-node not applicable or disabled"
    log.info(
        "PIPELINE [06/09] After fixed-mesh/MWIR stage | kept RMSE=%.6f | %s "
        "(current spline solution before k-floor and before any downstream corridor worker)",
        float(rmse),
        mwir_txt,
    )


def _emit_enter_fixed_mesh_stage(coord: _WorkerProgressCoordinator) -> None:
    """Emit fixed-mesh stage entry progress marker."""
    coord.emit(68, "Final spline: fixed mesh baseline (optional MWIR stage next)...")


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
                        "d_nm_seg_spline=%s d_nm_courant=%s | len(n_lam)=%d vs len(seg_pack)=%s → "
                        "profilage depuis dict nominal.",
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
                from certus.spline.spline_profile_corridors import compute_reg_sensitivity_scan

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
                from certus.spline.spline_profile_corridors import compute_bootstrap_corridors_by_d

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
    if stop_event.is_set():
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
    if stop_event.is_set():
        return out
    log_index_spline_d_trace(
        log,
        "deferred/post-NL corridor: after profiling (dict out, before nk RMSE display mask)",
        out.get("d_nm"),
    )
    apply_rmse_fit_window_nk_nan_to_result(out, cfg.rmse_fit_lambda_nm)
    progress_cb(100, "Corridors: completed.")
    return out


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
    L_lam_out = np.interp(sig_out, _sk_f, _LL_f)
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
