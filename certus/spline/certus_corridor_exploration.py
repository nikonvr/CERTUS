# from typing import *  # Unused
import numpy as np
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from certus.core.certus_core import Any, NUMERICAL_FAULT_EXCEPTIONS

# from certus.spline.certus_index_spline_core import *  # Unused
from certus.spline.certus_corridor_config import (
    CorridorLiveStreamer,
    CorridorWalkSideContext,
    ProfileCorridorConfig,
    RegularGridProfileContext,
    SplineOptConfig,
    _hetero_sigma_masked_from_base,
    clip_to_bounds,
    corridor_profile_refit_maxfun,
    x_slice_n_to_physical_nodes,
)

# from certus.spline.certus_corridor_fitter import *  # Unused
from certus.spline.certus_corridor_utils import (
    _extract_knots_and_nodes_from_result,
    _x_nodes0_from_mesh_x_if_consistent,
    _bounds_for_nodes_only,
    _detect_corridor_spike,
)
from certus.spline.certus_corridor_bootstrap import (
    _resample_residuals_block,
    _bootstrap_pool_entry,
    _bootstrap_single_replicate,
)
from certus.spline.certus_corridor_logger import _log_coaching_bootstrap_outcome
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
from certus.spline.spline_objective import build_spline_objective_masked_grid, nk_from_x_pwlnk
log = logging.getLogger('CERTUS')
_LOG_PREFIX = "INDEX_SPLINE [CORRIDOR EXPLORE]"
def _corridor_profile_walk_side(
    walk_sign: float,
    pconf: ProfileCorridorConfig,
    cfg: SplineOptConfig,
    sk: np.ndarray,
    d0: float,
    x_nodes_center: np.ndarray,
    x0_default: np.ndarray,
    bounds_nodes: np.ndarray,
    maxfun_prof: int,
    use_lr: bool,
    chi2_min: float,
    delta_chi2: float,
    rmse_thresh_active: float,
    rmse_opt: float,
    sig_t: float,
    sig_r: float,
    sigma_t_f_hetero: np.ndarray | None,
    sigma_r_f_hetero: np.ndarray | None,
    live_streamer: CorridorLiveStreamer | None = None,
    target_min_span: float = 0.0,
) -> dict[str, Any]:
    """One-sided d continuation (+d or -d). Use distinct ``pconf.rng_seed`` per thread when running in parallel."""

    d_vals: list[float] = []

    n_curves: list[np.ndarray] = []

    k_curves: list[np.ndarray] = []

    x_curves: list[np.ndarray] = []

    rmse_vals: list[float] = []

    chi2_vals: list[float] = []

    fit_nfev_values: list[float] = []

    fit_nit_values: list[float] = []

    fit_try_values: list[float] = []

    fit_fail_values: list[float] = []

    n_refines = 0
    seed_gate_eval_count = 0
    seed_gate_kept_count = 0
    seed_gate_delta_refit_minus_seed: list[float] = []

    # --- For local parabola tracking ---
    clean_d_vals: list[float] = [float(d0)]
    clean_rmse_vals: list[float] = [float(rmse_opt)]
    # B4 FIX: unbiased spike detection — track ALL evaluated points (ok or not)
    # so the parabola reflects the true RMSE(d) trend, not just accepted points.
    all_d_vals: list[float] = [float(d0)]
    all_rmse_vals: list[float] = [float(rmse_opt)]

    ctx = CorridorWalkSideContext(
        pconf=pconf,
        cfg=cfg,
        sk=sk,
        x_nodes_center=x_nodes_center,
        x0_default=x0_default,
        bounds_nodes=bounds_nodes,
        maxfun_prof=maxfun_prof,
        use_lr=use_lr,
        sig_t=sig_t,
        sig_r=sig_r,
        chi2_min=chi2_min,
        delta_chi2=delta_chi2,
        sigma_t_f_hetero=sigma_t_f_hetero,
        sigma_r_f_hetero=sigma_r_f_hetero,
        rmse_thresh_active=rmse_thresh_active,
        live_point_cb=live_streamer,
        d_vals=d_vals,
        n_curves=n_curves,
        k_curves=k_curves,
        rmse_vals=rmse_vals,
        chi2_vals=chi2_vals,
    )


    d_prev = float(d0)

    x_prev = np.asarray(x_nodes_center, dtype=np.float64).copy()

    step = float(max(1e-6, getattr(pconf, "step_nm_initial", pconf.step_nm)))

    step_growth = float(max(getattr(pconf, "step_growth", 1.4) or 1.4, 1.0))

    step_cap = float(max(getattr(pconf, "step_nm_max", pconf.step_nm), 1e-6))

    span = 0.0

    nsteps = 0

    effective_max_span = float(pconf.max_span_nm)
    _d_range = float(abs(max(cfg.d_lo, cfg.d_hi) - min(cfg.d_lo, cfg.d_hi)))
    _max_span_safety = min(_d_range * 0.45, max(effective_max_span * 30.0, 300.0))
    _span_hist: list[float] = [0.0]
    _rmse_hist: list[float] = [float(rmse_opt) if np.isfinite(float(rmse_opt)) else float("nan")]

    last_good_d: float | None = None

    last_good_x: np.ndarray | None = None
    last_good_y: float = -delta_chi2 if use_lr else (rmse_opt - rmse_thresh_active)

    dir_lbl = "+d" if float(walk_sign) > 0 else "-d"

    n_valid_side = 0
    _auto_escalated: bool = False  # P0.3: tracks if seed-gate escalation triggered

    log.info(
        "%s Walk %s: start d=%.6f nm | step=%.4g nm | span_max=%.4g nm",
        _LOG_PREFIX,
        dir_lbl,
        d_prev,
        step,
        float(pconf.max_span_nm),
    )

    while nsteps < int(pconf.max_steps_each_side) and span < effective_max_span:
        d_try = float(d_prev + walk_sign * step)

        if d_try < float(min(cfg.d_lo, cfg.d_hi)) - 1e-9 or d_try > float(max(cfg.d_lo, cfg.d_hi)) + 1e-9:
            log.info(
                "%s Walk %s: stop (d bound) | d_try=%.6f nm not in [%.6f, %.6f]",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                float(min(cfg.d_lo, cfg.d_hi)),
                float(max(cfg.d_lo, cfg.d_hi)),
            )

            break

        # --- Iso-Phase Warm-Start (Physics scaling) ---
        # Optical path invariant: n * d ~ constant. To stay exactly in the interference
        # valley without forcing the optimizer to slide down the gradient, we project n.
        x_smart_seed = _generate_iso_phase_seed(x_prev, sk, d_prev, d_try, cfg)

        fit, _, metricv = _best_fit_at_d(
            cfg,
            sk=sk,
            d_nm=float(d_try),
            x_seed_primary=x_smart_seed,
            x_seed_secondary=x_nodes_center,
            x_seed_default=x0_default,
            bounds_nodes=bounds_nodes,
            maxfun=maxfun_prof,
            use_lr=use_lr,
            sig_t=sig_t,
            sig_r=sig_r,
            chi2_min_ref=float(chi2_min) if (use_lr and np.isfinite(chi2_min)) else None,
            delta_chi2=float(delta_chi2) if np.isfinite(delta_chi2) else 0.0,
            pconf=pconf,
            stage_label=f"Step {dir_lbl}",
            sigma_t_f=sigma_t_f_hetero,
            sigma_r_f=sigma_r_f_hetero,
        )

        if fit is None or not np.isfinite(float(fit.get("rmse", float("nan")))):
            log.info("%s Walk %s: stop (fit invalid) | d=%.6f nm", _LOG_PREFIX, dir_lbl, d_try)

            break

        rm = float(fit["rmse"])
        rmse_seed_fit = fit.get("rmse_seed_before_refit")
        rmse_refit_fit = fit.get("rmse_refit_attempted")
        has_seed_gate = (
            rmse_seed_fit is not None
            and rmse_refit_fit is not None
            and np.isfinite(float(rmse_seed_fit))
            and np.isfinite(float(rmse_refit_fit))
        )
        if has_seed_gate:
            seed_gate_eval_count += 1
            if bool(fit.get("seed_kept_over_refit", False)):
                seed_gate_kept_count += 1
            seed_gate_delta_refit_minus_seed.append(float(rmse_refit_fit) - float(rmse_seed_fit))

        # P0.3 FIX: Auto-escalation if seed-gate saturating (>50% kept on first 3 evals)
        if seed_gate_eval_count >= 3 and nsteps <= 5:
            _kept_rate = float(seed_gate_kept_count) / float(seed_gate_eval_count)
            if _kept_rate > 0.5 and not _auto_escalated:
                _auto_escalated = True
                _old_maxfun = maxfun_prof
                maxfun_prof = int(maxfun_prof * 2.0)
                log.warning(
                    "%s Walk %s: seed-gate saturation detected (%.0f%% kept). "
                    "Auto-escalating maxfun %d -> %d. Consider increasing polish budget or enabling refit_pure_spectral.",
                    _LOG_PREFIX,
                    dir_lbl,
                    100.0 * _kept_rate,
                    _old_maxfun,
                    maxfun_prof,
                )

        ok = False
        chi_v = float("nan")
        y_v = float("nan")

        if use_lr:
            chi_v = float(metricv)
            y_v = chi_v - (chi2_min + delta_chi2)
            ok = np.isfinite(chi_v) and np.isfinite(chi2_min) and (y_v <= 0)
        else:
            y_v = rm - rmse_thresh_active
            ok = rm <= rmse_thresh_active

        if use_lr:
            log.info(
                "%s Walk %s: d=%.6f nm | chi2=%.8f | Deltachi2=%+.8f | RMSE=%.8f | nit=%d nfev=%d",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(chi_v),
                float(chi_v - chi2_min) if np.isfinite(chi2_min) else float("nan"),
                float(rm),
                int(fit.get("nit", 0)),
                int(fit.get("nfev", 0)),
            )

        else:
            log.info(
                "%s Walk %s: d=%.6f nm | RMSE=%.8f | DeltaRMSE(vs_ref_best)=%+.8f | seed_gate=%s | DeltaRMSE(refit-seed)=%s | nit=%d nfev=%d",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(rm),
                float(rm - rmse_opt) if np.isfinite(rmse_opt) else float("nan"),
                "kept" if bool(fit.get("seed_kept_over_refit", False)) else "refit",
                (f"{(float(rmse_refit_fit) - float(rmse_seed_fit)):+.8f}" if has_seed_gate else "n/a"),
                int(fit.get("nit", 0)),
                int(fit.get("nfev", 0)),
            )

        # --- Spike detection vs local parabola ---
        # B4 FIX: use all_d_vals/all_rmse_vals (every evaluated point) instead of
        # d_vals/rmse_vals (accepted-only). This prevents the parabola from being
        # biased toward low-RMSE points and incorrectly flagging natural RMSE rises.
        all_d_vals.append(float(d_try))
        all_rmse_vals.append(float(rm))
        parab_tol_abs = float(getattr(pconf, "parabola_spike_tolerance_abs", 2e-5))
        is_spike, rm_pred, _tol_eff, _sigma = _detect_corridor_spike(
            all_d_vals, all_rmse_vals, d_try, rm, float(d0), parab_tol_abs
        )

        # Smart escalation: if the points are too dispersed vs parabola, the optimizations
        # are insufficiently pushed. Increase rigor globally for this corridor side.
        if np.isfinite(_sigma) and _sigma > max(parab_tol_abs, 2e-5) * 1.5:
            if maxfun_prof < 2000:
                _old_maxfun = maxfun_prof
                maxfun_prof = int(maxfun_prof * 1.5)
                pconf = pconf.replace(n_starts=max(4, int(pconf.n_starts) + 1))
                log.warning(
                    "%s Walk %s: high dispersion vs parabola (sigma=%.6f > tol). "
                    "Intelligently pushing optimizations further: maxfun %d -> %d, n_starts -> %d.",
                    _LOG_PREFIX, dir_lbl, _sigma, _old_maxfun, maxfun_prof, pconf.n_starts
                )
                if not is_spike and rm > rm_pred:
                    # Point might be slightly off but not a massive spike, still force a retry
                    # to clean it up under the new rigorous settings.
                    is_spike = True

        if is_spike:
            log.info(
                "%s Walk %s: spike/noise detected at d=%.6f nm (RMSE=%.8f vs pred=%.8f). Retrying with jitter...",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                rm,
                rm_pred,
            )
            pconf_retry = pconf.replace(n_starts=max(4, int(pconf.n_starts) + 2))

            fit_retry, _, _ = _best_fit_at_d(
                cfg,
                sk=sk,
                d_nm=float(d_try),
                x_seed_primary=x_smart_seed,
                x_seed_secondary=x_nodes_center,
                x_seed_default=x0_default,
                bounds_nodes=bounds_nodes,
                maxfun=maxfun_prof * 2,
                use_lr=use_lr,
                sig_t=sig_t,
                sig_r=sig_r,
                chi2_min_ref=chi2_min if use_lr else None,
                delta_chi2=delta_chi2,
                pconf=pconf_retry,
                stage_label=f"Retry {dir_lbl}",
                sigma_t_f=sigma_t_f_hetero,
                sigma_r_f=sigma_r_f_hetero,
            )

            if fit_retry is not None:
                rm_retry = float(fit_retry.get("rmse", float("inf")))
                if rm_retry < rm:
                    log.info("%s Walk %s: retry improved RMSE %.8f -> %.8f", _LOG_PREFIX, dir_lbl, rm, rm_retry)
                    fit = fit_retry
                    rm = rm_retry
                    all_rmse_vals[-1] = rm  # P0.3 FIX: Update the tracked history with the improved value
                    # Re-check after retry
                    if rm <= rm_pred + _tol_eff:
                        is_spike = False
                        log.info("%s Walk %s: retry recovered point at d=%.6f nm", _LOG_PREFIX, dir_lbl, d_try)

        if is_spike:
            log.warning(
                "%s Walk %s: rejecting point at d=%.6f nm (persistent spike RMSE=%.8f vs pred=%.8f).",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                rm,
                rm_pred,
            )
            # Remove the rejected point from the history so it doesn't corrupt future parabola fits
            all_d_vals.pop()
            all_rmse_vals.pop()
            
            # Advance thickness to avoid looping, but do not add the point to results
            # and do not validate the step.
            d_prev = float(d_try)
            span = abs(float(d_try) - float(d0))
            nsteps += 1
            # x_prev remains the last stable point, favouring a good seed at the next step.
            continue

        force_points = (
            nsteps < max(3, int(getattr(pconf, "min_valid_each_side", 0)))
            or (target_min_span > 0.0 and span < target_min_span)
        )

        if ok or force_points:
            d_vals.append(float(d_try))

            n_curves.append(np.asarray(fit["n_lam"], dtype=np.float64))

            k_curves.append(np.asarray(fit["k_lam"], dtype=np.float64))

            x_curves.append(np.asarray(fit["x_nodes_best"], dtype=np.float64).ravel().copy())

            rmse_vals.append(rm)

            chi2_vals.append(float(chi_v) if np.isfinite(chi_v) else float("nan"))
            if live_streamer is not None:
                live_streamer.push_point(
                    float(d_try),
                    float(rm),
                    np.asarray(fit["n_lam"], dtype=np.float64).ravel(),
                    np.asarray(fit["k_lam"], dtype=np.float64).ravel(),
                    float(chi_v) if np.isfinite(chi_v) else float("nan"),
                )

            fit_nfev_values.append(float(fit.get("nfev", float("nan"))))

            fit_nit_values.append(float(fit.get("nit", float("nan"))))

            fit_try_values.append(float(fit.get("n_try", float("nan"))))

            fit_fail_values.append(float(fit.get("n_failed_fit", float("nan"))))

            x_prev = np.asarray(fit["x_nodes_best"], dtype=np.float64).ravel().copy()

            d_prev = float(d_try)

            span = abs(d_prev - float(d0))
            if ok:
                last_good_d = float(d_prev)
                last_good_x = x_prev.copy()
                last_good_y = float(y_v)
                # Update the "clean" history for the parabola
                clean_d_vals.append(float(d_prev))
                clean_rmse_vals.append(float(rm))

            nsteps += 1

            step = min(step_cap, step * step_growth)

            _span_hist.append(span)
            _rmse_hist.append(rm)
            if len(_span_hist) >= 3 and rm < rmse_thresh_active and np.isfinite(rmse_thresh_active) and np.isfinite(rm):
                _slope = float("nan")
                _nm_remaining = float("nan")
                _ds = _span_hist[-1] - _span_hist[-2]
                _dr = _rmse_hist[-1] - _rmse_hist[-2]
                if _ds > 1e-10 and _dr > 1e-15:
                    _slope = _dr / _ds
                    _nm_remaining = (rmse_thresh_active - rm) / _slope
                    secant_step = float(np.clip(_nm_remaining, step, step_cap * 2.0))
                    if secant_step > step:
                        step = secant_step

                # Parabolic prediction: fit quadratic on last 3 clean points to estimate
                # distance to threshold more accurately than the linear secant.
                if len(clean_d_vals) >= 3 and not use_lr:
                    try:
                        _cd = np.asarray(clean_d_vals[-3:], dtype=np.float64) - float(d0)
                        _cr = np.asarray(clean_rmse_vals[-3:], dtype=np.float64)
                        _pa, _pb, _pc = np.polyfit(_cd, _cr, 2)
                        if np.isfinite(_pa) and _pa > 0.0:
                            _disc = _pb**2 - 4.0 * _pa * (_pc - float(rmse_thresh_active))
                            if _disc >= 0.0:
                                _root = (-_pb + float(walk_sign) * np.sqrt(_disc)) / (2.0 * _pa)
                                _d_pred = float(d0) + float(_root)
                                _para_step = abs(_d_pred - float(d_prev)) * 0.85
                                if np.isfinite(_para_step) and _para_step > step:
                                    step = float(np.clip(_para_step, step, step_cap * 3.0))
                                    log.debug(
                                        "%s Walk %s: parabolic step prediction d_boundary~%.4f nm -> step %.4g nm",
                                        _LOG_PREFIX,
                                        dir_lbl,
                                        float(_d_pred),
                                        float(step),
                                    )
                    except (np.linalg.LinAlgError, ValueError):
                        log.debug("%s parabola fit failed at d=%.6f nm (non-critical)", _LOG_PREFIX, float(d0))

                if np.isfinite(_slope) and np.isfinite(_nm_remaining) and _nm_remaining > 0.0:
                    _projected = span + _nm_remaining * 1.15
                    if _projected > effective_max_span:
                        _new_span = min(_projected, _max_span_safety)
                        if _new_span > effective_max_span + 0.5:
                            log.info(
                                "%s Walk %s: auto-extend span %.1f -> %.1f nm "
                                "(RMSE slope=%.3g /nm, ~%.1f nm to threshold)",
                                _LOG_PREFIX,
                                dir_lbl,
                                effective_max_span,
                                _new_span,
                                _slope,
                                _nm_remaining,
                            )
                        effective_max_span = max(effective_max_span, _new_span)

            if ok:
                n_valid_side += 1

            continue

        if not ok and not force_points and last_good_d is not None and last_good_x is not None:
            rb = ctx.refine_bracket(last_good_d, last_good_x, last_good_y, float(d_try), y_v, walk_sign)

            if rb is not None:
                n_refines += 1

                log.info(
                    "%s Walk %s: refined boundary on admissible side ~ d=%.6f nm",
                    _LOG_PREFIX,
                    dir_lbl,
                    float(rb[0]),
                )

        if use_lr and np.isfinite(chi_v) and np.isfinite(chi2_min):
            chi_lim = float(chi2_min) + float(delta_chi2)

            log.info(
                "%s Walk %s: stop (LR Deltaχ²) | d=%.6f nm χ²=%.6g > χ²_center+Delta=%.6g "
                "(Deltaχ² vs center=%+.6g | RMSE=%.8f; the alpha×RMSE threshold logged above does not apply to the LR criterion)",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(chi_v),
                float(chi_lim),
                float(chi_v - chi2_min),
                float(rm),
            )

        else:
            log.info(
                "%s Walk %s: stop (RMSE > threshold) | d=%.6f nm RMSE=%.8f > %.8f",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(rm),
                float(rmse_thresh_active),
            )

        break

    return {
        "d_vals": d_vals,
        "n_curves": n_curves,
        "k_curves": k_curves,
        "x_curves": x_curves,
        "rmse_vals": rmse_vals,
        "chi2_vals": chi2_vals,
        "fit_nfev_values": fit_nfev_values,
        "fit_nit_values": fit_nit_values,
        "fit_try_values": fit_try_values,
        "fit_fail_values": fit_fail_values,
        "n_valid_side": int(n_valid_side),
        "n_refines": int(n_refines),
        "seed_gate_eval_count": int(seed_gate_eval_count),
        "seed_gate_kept_count": int(seed_gate_kept_count),
        "seed_gate_delta_refit_minus_seed": seed_gate_delta_refit_minus_seed,
        "seed_gate_auto_escalated": bool(_auto_escalated),
    }
def compute_bootstrap_corridors_by_d(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig,
    n_boot: int,
    percentile: float = 0.95,
    seed: int = 0,
    sigma_t: float | None = None,
    sigma_r: float | None = None,
    mode: str = "parametric",
    block_len: int = 1,
    quick_refit_maxfun: int | None = None,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """V2.4: parametric bootstrap for bands.

    Builds B synthetic (T/R) datasets by adding Gaussian noise (sigma_T, sigma_R),

    reruns ``compute_profiled_corridors_by_d`` and aggregates:

      - n/k corridor percentiles (on lambda)

      - distribution of d_interval bounds.

    ``n_workers``: parallelism for replicates (``ProcessPoolExecutor``). Default: ``cfg.corridor_bootstrap_n_workers`` or 1.

    On failure (pickle, worker), falls back to sequential.

    """

    B = int(max(0, n_boot))

    if B <= 0:
        return {}

    p = float(np.clip(percentile, 0.5, 0.999999))

    q_lo = 0.5 * (1.0 - p)

    q_hi = 1.0 - q_lo

    rng = np.random.default_rng(int(seed))

    mode = str(mode or "parametric").strip().lower()

    if mode not in ("parametric", "residual"):
        mode = "parametric"

    blk = int(max(1, block_len))

    # Default sigma: consistent with LR mode (auto := RMSE_opt) when not provided.

    rmse_opt = float(base_result.get("rmse", float("nan")))

    sigma_auto = float(rmse_opt) if np.isfinite(rmse_opt) and rmse_opt > 0 else 1.0

    sig_t = float(sigma_t) if (sigma_t is not None and float(sigma_t) > 0) else sigma_auto

    sig_r = float(sigma_r) if (sigma_r is not None and float(sigma_r) > 0) else sigma_auto

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    t0 = np.asarray(cfg.t_exp, dtype=np.float64).ravel() if cfg.t_exp is not None else None

    r0 = np.asarray(cfg.r_exp, dtype=np.float64).ravel() if cfg.r_exp is not None else None

    if lam.size < 3:
        return {}

    if t0 is not None and t0.size != lam.size:
        return {}

    if r0 is not None and r0.size != lam.size:
        return {}

    from certus.spline.spline_objective import _spline_objective_lam_mask

    qref = int(quick_refit_maxfun) if quick_refit_maxfun is not None else 0

    hetero_param = bool(getattr(cfg, "corridor_profile_d_sigma_hetero", False)) and mode == "parametric"

    floor_abs = max(1e-8, 0.01 * float(sigma_auto))

    h_scale = float(max(getattr(cfg, "corridor_profile_d_sigma_hetero_scale", 1.0) or 0.0, 0.0))

    st_hetero, sr_hetero = _hetero_sigma_masked_from_base(cfg, base_result, scale=h_scale, floor_abs=floor_abs)

    sigma_T_full: np.ndarray | None = None

    sigma_R_full: np.ndarray | None = None

    if hetero_param:
        mobj = _spline_objective_lam_mask(cfg)

        if st_hetero is not None and t0 is not None:
            sigma_T_full = np.full(lam.size, float(sig_t), dtype=np.float64)

            sigma_T_full[mobj] = np.asarray(st_hetero, dtype=np.float64).ravel()

        if sr_hetero is not None and r0 is not None:
            sigma_R_full = np.full(lam.size, float(sig_r), dtype=np.float64)

            sigma_R_full[mobj] = np.asarray(sr_hetero, dtype=np.float64).ravel()

    d_lo_list: list[float] = []

    d_hi_list: list[float] = []

    n_lo_list: list[np.ndarray] = []

    n_hi_list: list[np.ndarray] = []

    k_lo_list: list[np.ndarray] = []

    k_hi_list: list[np.ndarray] = []

    n_ok = 0

    run_b: list[int] = []

    run_ok: list[int] = []

    run_dlo: list[float] = []

    run_dhi: list[float] = []

    run_nvalid: list[int] = []

    log.info(
        "%s [BOOT] start | mode=%s blk=%d | B=%d | p=%.3f (q=[%.4f,%.4f]) | sigma_T=%.6g sigma_R=%.6g | prof_mode=%s | "
        "hetero_sigma(lambda)=%s | quick_refit_maxfun=%d",
        _LOG_PREFIX,
        str(mode),
        int(blk),
        int(B),
        float(p),
        float(q_lo),
        float(q_hi),
        float(sig_t),
        float(sig_r),
        str(getattr(pconf, "mode", "alpha")),
        bool(hetero_param),
        int(qref),
    )

    # Residual mode: needs T_th / R_th and residuals.

    t_th0, r_th0 = (None, None)

    eT0, eR0 = (None, None)

    if mode == "residual":
        t_th0, r_th0 = _theoretical_TR_from_base_result(cfg, base_result)

        if t0 is not None and t_th0 is not None:
            m = np.isfinite(t0) & np.isfinite(t_th0)

            eT0 = (t0[m] - t_th0[m]).astype(np.float64, copy=False)

        if r0 is not None and r_th0 is not None:
            m = np.isfinite(r0) & np.isfinite(r_th0)

            eR0 = (r0[m] - r_th0[m]).astype(np.float64, copy=False)

        if (t0 is not None and (t_th0 is None or eT0 is None or eT0.size < 3)) and (r0 is None):
            return {}

        if (r0 is not None and (r_th0 is None or eR0 is None or eR0.size < 3)) and (t0 is None):
            return {}

    nw = int(n_workers) if n_workers is not None else int(getattr(cfg, "corridor_bootstrap_n_workers", 1) or 1)

    nw = max(1, nw)

    boot_workers_effective = 1

    replicates: list[tuple[int, SplineOptConfig]] = []

    for b in range(B):
        t_b = None

        r_b = None

        if mode == "parametric":
            mobj = _spline_objective_lam_mask(cfg)

            if t0 is not None:
                t_b = t0.copy()

                if hetero_param:
                    idx_t = mobj & np.isfinite(t_b)

                    if np.any(idx_t):
                        stv = (
                            sigma_T_full[idx_t]
                            if sigma_T_full is not None
                            else np.full(int(np.count_nonzero(idx_t)), float(sig_t), dtype=np.float64)
                        )

                        t_b[idx_t] = t_b[idx_t] + rng.normal(0.0, stv, size=int(np.count_nonzero(idx_t)))

                else:
                    m = np.isfinite(t_b)

                    if np.any(m):
                        t_b[m] = t_b[m] + rng.normal(0.0, float(sig_t), size=int(np.count_nonzero(m)))

            if r0 is not None:
                r_b = r0.copy()

                if hetero_param:
                    idx_r = mobj & np.isfinite(r_b)

                    if np.any(idx_r):
                        srv = (
                            sigma_R_full[idx_r]
                            if sigma_R_full is not None
                            else np.full(int(np.count_nonzero(idx_r)), float(sig_r), dtype=np.float64)
                        )

                        r_b[idx_r] = r_b[idx_r] + rng.normal(0.0, srv, size=int(np.count_nonzero(idx_r)))

                else:
                    m = np.isfinite(r_b)

                    if np.any(m):
                        r_b[m] = r_b[m] + rng.normal(0.0, float(sig_r), size=int(np.count_nonzero(m)))

        else:
            if t0 is not None and t_th0 is not None and eT0 is not None:
                t_b = t0.copy()

                m = np.isfinite(t_b) & np.isfinite(t_th0)

                e_star = _resample_residuals_block(eT0, blk, rng)

                t_b[m] = t_th0[m] + e_star[: int(np.count_nonzero(m))]

            if r0 is not None and r_th0 is not None and eR0 is not None:
                r_b = r0.copy()

                m = np.isfinite(r_b) & np.isfinite(r_th0)

                e_star = _resample_residuals_block(eR0, blk, rng)

                r_b[m] = r_th0[m] + e_star[: int(np.count_nonzero(m))]

        cfg_b = cfg.replace(t_exp=t_b, r_exp=r_b)

        replicates.append((int(b), cfg_b))

    batch_out: dict[int, dict[str, Any]] = {}

    use_parallel = nw > 1 and B > 1

    if use_parallel:
        try:
            from concurrent.futures import ProcessPoolExecutor, as_completed

            n_proc = int(min(nw, B))

            with ProcessPoolExecutor(max_workers=n_proc) as ex:
                futs = {
                    ex.submit(
                        _bootstrap_pool_entry,
                        (b, cfg_b, base_result, pconf, qref, lam),
                    ): int(b)
                    for b, cfg_b in replicates
                }

                for fut in as_completed(futs):
                    bi, r = fut.result()

                    batch_out[int(bi)] = r

            boot_workers_effective = n_proc

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s [BOOT] parallel failed - sequential fallback.", _LOG_PREFIX)

            use_parallel = False

            batch_out.clear()

    if not use_parallel or len(batch_out) != B:
        if use_parallel and len(batch_out) != B:
            log.warning("%s [BOOT] incomplete parallel results - sequential fallback.", _LOG_PREFIX)

        batch_out = {}

        for b, cfg_b in replicates:
            batch_out[int(b)] = _bootstrap_single_replicate(
                cfg_b,
                base_result,
                pconf=pconf,
                qref=qref,
                lam=lam,
                log_run_1based=int(b) + 1,
            )

        boot_workers_effective = 1

    for b in range(B):
        r = batch_out[int(b)]

        st = str(r.get("status", "exception"))

        run_b.append(int(b))

        if st == "ok":
            d_lo_list.append(float(r["dlo"]))

            d_hi_list.append(float(r["dhi"]))

            n_lo_list.append(np.asarray(r["n_lo"], dtype=np.float64).ravel())

            n_hi_list.append(np.asarray(r["n_hi"], dtype=np.float64).ravel())

            k_lo_list.append(np.asarray(r["k_lo"], dtype=np.float64).ravel())

            k_hi_list.append(np.asarray(r["k_hi"], dtype=np.float64).ravel())

            n_ok += 1

            run_ok.append(1)

            run_dlo.append(float(r["dlo"]))

            run_dhi.append(float(r["dhi"]))

            run_nvalid.append(int(r.get("nvalid", 0)))

        else:
            run_ok.append(0)

            run_dlo.append(float("nan"))

            run_dhi.append(float("nan"))

            run_nvalid.append(int(r.get("nvalid", 0)))

        if (b + 1) % max(1, B // 10) == 0:
            log.info("%s [BOOT] progress %d/%d | ok=%d", _LOG_PREFIX, int(b + 1), int(B), int(n_ok))

    if n_ok < 3:
        log.warning("%s [BOOT] stop | too few valid runs (%d/%d)", _LOG_PREFIX, int(n_ok), int(B))

        _log_coaching_bootstrap_outcome(
            B=int(B),
            n_ok=int(n_ok),
            p=float(p),
            mode=str(mode),
            qref=int(qref),
            d_lo_q=float("nan"),
            d_hi_q=float("nan"),
        )

        return {}

    d_lo_a = np.asarray(d_lo_list, dtype=np.float64)

    d_hi_a = np.asarray(d_hi_list, dtype=np.float64)

    n_lo_a = np.stack(n_lo_list, axis=0)

    n_hi_a = np.stack(n_hi_list, axis=0)

    k_lo_a = np.stack(k_lo_list, axis=0)

    k_hi_a = np.stack(k_hi_list, axis=0)

    # Percentile bands: aggregate envelopes (lo/hi) from each run.

    # For k, compute quantiles in ln(k) space (better numerical stability), then map back to k.

    boot_n_lo = np.nanquantile(n_lo_a, q_lo, axis=0)

    boot_n_hi = np.nanquantile(n_hi_a, q_hi, axis=0)

    L_lo_a = np.log(np.maximum(k_lo_a, 1e-300))

    L_hi_a = np.log(np.maximum(k_hi_a, 1e-300))

    boot_L_lo = np.nanquantile(L_lo_a, q_lo, axis=0)

    boot_L_hi = np.nanquantile(L_hi_a, q_hi, axis=0)

    boot_k_lo = np.exp(boot_L_lo)

    boot_k_hi = np.exp(boot_L_hi)

    out = {
        "boot_enabled": True,
        "boot_n": int(B),
        "boot_n_ok": int(n_ok),
        "boot_seed": int(seed),
        "boot_percentile": float(p),
        "boot_q_lo": float(q_lo),
        "boot_q_hi": float(q_hi),
        "boot_sigma_t": float(sig_t),
        "boot_sigma_r": float(sig_r),
        "boot_mode": str(mode),
        "boot_block_len": int(blk),
        "boot_runs_b": np.asarray(run_b, dtype=np.int64),
        "boot_runs_ok": np.asarray(run_ok, dtype=np.int64),
        "boot_runs_d_lo_nm": np.asarray(run_dlo, dtype=np.float64),
        "boot_runs_d_hi_nm": np.asarray(run_dhi, dtype=np.float64),
        "boot_runs_n_valid": np.asarray(run_nvalid, dtype=np.int64),
        "boot_d_lo_samples_nm": d_lo_a,
        "boot_d_hi_samples_nm": d_hi_a,
        "boot_d_lo_q_nm": float(np.nanquantile(d_lo_a, q_lo)),
        "boot_d_hi_q_nm": float(np.nanquantile(d_hi_a, q_hi)),
        "boot_corridor_n_lo": np.asarray(boot_n_lo, dtype=np.float64),
        "boot_corridor_n_hi": np.asarray(boot_n_hi, dtype=np.float64),
        "boot_corridor_k_lo": np.asarray(boot_k_lo, dtype=np.float64),
        "boot_corridor_k_hi": np.asarray(boot_k_hi, dtype=np.float64),
        "boot_corridor_L_lo": np.asarray(boot_L_lo, dtype=np.float64),
        "boot_corridor_L_hi": np.asarray(boot_L_hi, dtype=np.float64),
        "boot_quick_refit_maxfun": int(qref),
        "boot_sigma_hetero_parametric": bool(hetero_param),
        "boot_n_workers_effective": int(boot_workers_effective),
    }

    log.info(
        "%s [BOOT] done | ok=%d/%d | d_lo q=%.4f | d_hi q=%.4f",
        _LOG_PREFIX,
        int(n_ok),
        int(B),
        float(out["boot_d_lo_q_nm"]),
        float(out["boot_d_hi_q_nm"]),
    )

    _log_coaching_bootstrap_outcome(
        B=int(B),
        n_ok=int(n_ok),
        p=float(p),
        mode=str(mode),
        qref=int(qref),
        d_lo_q=float(out["boot_d_lo_q_nm"]),
        d_hi_q=float(out["boot_d_hi_q_nm"]),
    )

    return out
def compute_regular_grid_rmse_profile(
    cfg: SplineOptConfig,
    base_result: dict,
    d_targets_nm: np.ndarray,
    *,
    profile_polish_maxfun: int | None = None,
    breakpoint_lookback_points: int = 5,
    visit_anchor_nm: float | None = None,
    progress_cb: Any | None = None,
    stop_check: Any | None = None,
    live_cb: Any | None = None,
) -> dict[str, Any]:
    """Recompute RMSE(d) on an imposed thickness grid (refit n,L at fixed d).

    Same convention as corridor profiling ("scientific nominal" base if available,

    otherwise ``base_result`` as-is). Returns ``profile_d_*`` keys to merge into the GUI result dict.

    """

    from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference

    t0 = time.perf_counter()

    nom_pack = extract_nominal_best_polished_corridor_reference(base_result)

    base_eff: dict[str, Any]

    if nom_pack is not None:
        skn = np.asarray(nom_pack["sigma_knots"], dtype=np.float64).ravel()

        xsg = nom_pack.get("x_seg_spline_sigma")

        base_eff = dict(base_result)

        base_eff["n_lam"] = np.asarray(nom_pack["n_lam"], dtype=np.float64).copy()

        base_eff["k_lam"] = np.asarray(nom_pack["k_lam"], dtype=np.float64).copy()

        base_eff["d_nm"] = float(nom_pack["d_nm"])

        if skn.size >= 2:
            base_eff["sigma_knots"] = skn.copy()

        if xsg is not None:
            xa = np.asarray(xsg, dtype=np.float64).ravel()

            k_sig = int(skn.size)

            if xa.size == 1 + 2 * k_sig:
                base_eff["x_seg_spline_sigma"] = xa.copy()

                base_eff["x"] = xa.copy()

                n_slice_x = xa[1 : 1 + k_sig]

                L_slice_x = xa[1 + k_sig : 1 + 2 * k_sig]

                base_eff["L_nodes"] = np.asarray(L_slice_x, dtype=np.float64).copy()

                if cfg.n_mono_band_nm is None:
                    base_eff["n_nodes_physical"] = np.asarray(n_slice_x, dtype=np.float64).copy()

                else:
                    base_eff["n_nodes_physical"] = x_slice_n_to_physical_nodes(n_slice_x, skn, cfg.n_mono_band_nm)

    else:
        base_eff = dict(base_result)

    sk, _n_phys0, _L0, d0, _ = _extract_knots_and_nodes_from_result(base_eff)

    k = int(sk.size)

    x_nodes0 = _x_nodes0_from_mesh_x_if_consistent(base_eff, sk=sk, d0_nm=float(d0))

    if x_nodes0 is None:
        if cfg.n_mono_band_nm is None:
            n_slice0 = np.asarray(_n_phys0, dtype=np.float64).copy()

        else:
            from certus.spline.spline_objective import physical_nodes_to_x_slice_n

            n_slice0 = physical_nodes_to_x_slice_n(_n_phys0, sk, cfg.n_mono_band_nm)

        x_nodes0 = np.concatenate((n_slice0, np.asarray(_L0, dtype=np.float64).copy()))

    # P1.3 FIX: Pass k_hard_lower_bound to enforce physical k >= 0 constraint
    bounds_nodes, _ = _bounds_for_nodes_only(cfg, k, k_hard_lower_bound=0.0)

    x_nodes0 = clip_to_bounds(np.asarray(x_nodes0, dtype=np.float64).ravel(), bounds_nodes[:, 0], bounds_nodes[:, 1])

    raw = np.asarray(d_targets_nm, dtype=np.float64).ravel()

    raw = raw[np.isfinite(raw)]

    if raw.size == 0:
        return {"profile_d_status": "manual_grid_empty", "profile_d_manual_grid_note": "no finite d targets"}

    d_unique: list[float] = []

    for v in sorted(set(float(x) for x in raw.tolist())):
        if not d_unique or abs(v - d_unique[-1]) > 1e-9:
            d_unique.append(v)

    d_arr = np.asarray(d_unique, dtype=np.float64)

    if d_arr.size == 0:
        return {"profile_d_status": "manual_grid_empty", "profile_d_manual_grid_note": "empty after dedup"}

    # Sweep center: requested grid (visit_anchor_nm or target median), not the nominal pack d.
    # Otherwise the "first/last" order remains anchored on the old thickness after GUI recentering.
    if visit_anchor_nm is not None and np.isfinite(float(visit_anchor_nm)):
        d_visit_anchor = float(visit_anchor_nm)

    else:
        d_visit_anchor = float(np.median(d_arr)) if d_arr.size else float(d0)

    i_center = int(np.argmin(np.abs(d_arr - float(d_visit_anchor))))

    visit_indices: list[int] = [i_center]

    for ofs in range(1, int(d_arr.size)):
        i_r = i_center + ofs

        if i_r < int(d_arr.size):
            visit_indices.append(int(i_r))

        i_l = i_center - ofs

        if i_l >= 0:
            visit_indices.append(int(i_l))

    if visit_indices:
        order_dbg = np.asarray([float(d_arr[i]) for i in visit_indices], dtype=np.float64)
        log.info(
            "%s manual RMSE(d) grid strategy | visit_start_d=%.6f nm (anchor=%.6f) | nominal_pack_d=%.6f nm | "
            "visit_order=%d pts | first=%s | last=%s",
            _LOG_PREFIX,
            float(d_arr[i_center]),
            float(d_visit_anchor),
            float(d0),
            int(order_dbg.size),
            (", ".join(f"{v:.4f}" for v in order_dbg[: min(5, int(order_dbg.size))]) if order_dbg.size > 0 else "-"),
            (
                ", ".join(f"{v:.4f}" for v in order_dbg[max(0, int(order_dbg.size) - 5) :])
                if order_dbg.size > 0
                else "-"
            ),
        )

    maxfun_base = int(corridor_profile_refit_maxfun(cfg, profile_polish_maxfun))

    # User request: push per-point refit/polish further for RMSE(d) grid.
    maxfun = int(max(maxfun_base, round(1.8 * float(maxfun_base))))

    maxfun_polish = int(max(maxfun + 1, round(1.35 * float(maxfun))))

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    d_list: list[float] = []

    r_list: list[float] = []

    n_list: list[np.ndarray] = []

    k_list: list[np.ndarray] = []

    nit_list: list[float] = []

    nfev_list: list[float] = []

    point_kind_list: list[int] = []
    # 0=fit, 1=fallback_seed, 2=fallback_objective, 3=fallback_emergency
    point_status_code_list: list[int] = []
    # x_nodes_best per point — used by P0 re-pass to identify the global-best seed.
    x_nodes_best_list: list[np.ndarray] = []

    x_seed_center = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    x_seed_right = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    x_seed_left = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    n_tot = int(len(visit_indices))

    step_ref = float(np.nanmedian(np.abs(np.diff(d_arr)))) if d_arr.size >= 2 else 1.0

    step_ref = float(max(step_ref, 1e-4))

    side_last_rmse: dict[int, float] = {+1: float("nan"), -1: float("nan")}


    side_recent_rmse: dict[int, list[float]] = {+1: [], -1: []}

    side_recent_d: dict[int, list[float]] = {+1: [], -1: []}

    side_last_break_index: dict[int, int] = {+1: -10_000_000, -1: -10_000_000}

    branch_events: list[dict[str, float]] = []

    global_opt_events: list[dict[str, float]] = []

    n_branch_trigger = 0

    n_branch_extra_points = 0

    n_global_opt_runs = 0

    n_global_opt_improved = 0

    max_branch_events = 6

    max_extra_per_event = 30

    d_lo_grid = float(np.min(d_arr))

    d_hi_grid = float(np.max(d_arr))

    # Important: do NOT constrain manual grid exploration by the initial stage-2 d bounds.
    # We keep a local envelope around the user-requested RMSE(d) grid and allow reverse extras.
    d_lo_b = float(d_lo_grid - float(max_extra_per_event) * 0.5 * float(step_ref))

    d_hi_b = float(d_hi_grid + float(max_extra_per_event) * 0.5 * float(step_ref))

    rmse_abs_candidates = [
        float(base_result.get("rmse", float("nan"))),
        float(base_result.get("spectral_rmse_best_value", float("nan"))),
        float(base_result.get("spectral_rmse_segments", float("nan"))),
        float(base_eff.get("rmse", float("nan"))),
        float(base_eff.get("spectral_rmse_best_value", float("nan"))),
        float(base_eff.get("spectral_rmse_segments", float("nan"))),
    ]
    rmse_abs_ref = float(min([v for v in rmse_abs_candidates if np.isfinite(v)], default=float("nan")))
    # Baseline nominal RMSE (before any global-opt update) to compare against the discrete grid minimum.
    rmse_nominal_baseline_for_grid = float(rmse_abs_ref)
    best_global_result: dict[str, Any] | None = None
    best_global_rmse = float("nan")

    abs_best_seen_rmse = float("inf")


    lookback_points = int(max(2, breakpoint_lookback_points))
    min_gain_abs_prevn = 2e-6
    min_gain_rel_prevn = 5e-4
    min_gain_abs_parab = 2e-6
    min_breakpoint_spacing_points = max(6, int(lookback_points))

    log.info(
        "%s manual RMSE(d) grid budgets | base_maxfun=%d | point_maxfun=%d | polish_maxfun=%d | break_lookback=%d | explore_bounds=[%.6f, %.6f] nm",
        _LOG_PREFIX,
        int(maxfun_base),
        int(maxfun),
        int(maxfun_polish),
        int(lookback_points),
        float(d_lo_b),
        float(d_hi_b),
    )

    ctx = RegularGridProfileContext(
        cfg=cfg, sk=sk, bounds_nodes=bounds_nodes, lam_full=lam_full,
        maxfun=maxfun, maxfun_polish=maxfun_polish, live_cb=live_cb,
        d_arr=d_arr, n_tot=n_tot, step_ref=step_ref, d_lo_b=d_lo_b, d_hi_b=d_hi_b,
        stop_check=stop_check, max_extra_per_event=max_extra_per_event, k=k,
        abs_best_seen_rmse=abs_best_seen_rmse,
        d_list=d_list, r_list=r_list, n_list=n_list, k_list=k_list,
        nit_list=nit_list, nfev_list=nfev_list,
        point_kind_list=point_kind_list, point_status_code_list=point_status_code_list,
        x_nodes_best_list=x_nodes_best_list, branch_events=branch_events
    )

    for step_i, ji in enumerate(visit_indices):
        if stop_check is not None and bool(stop_check()):
            log.info("%s manual grid: stop requested after %d/%d points", _LOG_PREFIX, step_i, n_tot)

            break

        d_t = float(d_arr[int(ji)])

        if progress_cb is not None:
            try:
                progress_cb(float(step_i) / float(max(1, n_tot)), f"RMSE grid: d={d_t:.4f} nm ({step_i + 1}/{n_tot})")

            except (TypeError, ValueError, RuntimeError, AttributeError):
                log.debug("%s failed to invoke progress_cb in _execute_manual_grid (non-critical)", _LOG_PREFIX)

        if int(ji) == i_center:
            x_seed_in = x_seed_center

            side = 0

        elif int(ji) > i_center:
            x_seed_in = x_seed_right

            side = +1

        else:
            x_seed_in = x_seed_left

            side = -1

        fit = ctx._fit_point_with_extra_polish(float(d_t), x_seed_in)

        if fit is None:
            log.info("%s manual grid: refit failed at d=%.6f nm", _LOG_PREFIX, d_t)

            continue

        point_status_code = 0
        if bool(fit.get("fallback_from_objective", False)):
            point_status_code = 2
        elif bool(fit.get("fallback_from_seed", False)):
            point_status_code = 1
        if not ctx._append_fit_record(
            d_t,
            fit,
            point_kind=0,
            point_status_code=int(point_status_code),
        ):
            continue

        x_seed_new = np.asarray(fit.get("x_nodes_best", x_seed_in), dtype=np.float64).ravel().copy()

        if int(ji) == i_center:
            x_seed_center = x_seed_new

            x_seed_right = x_seed_new.copy()

            x_seed_left = x_seed_new.copy()

        elif int(ji) > i_center:
            x_seed_right = x_seed_new

        else:
            x_seed_left = x_seed_new

        ctx._emit_live(float(d_t), float(step_i + 1) / float(max(1, n_tot)))

        if side != 0:
            rm_now = float(fit.get("rmse", float("nan")))

            (
                is_break,
                gain_abs,
                gain_rel,
                abs_thr,
                rel_thr,
                trigger_prev5,
                best_prev5,
                gain_vs_prev5,
                trigger_parabola,
                parab_pred,
                parab_gain,
                parab_thr,
            ) = _detect_breakpoint(
                side,
                float(d_t),
                rm_now,
                side_last_rmse,
                side_recent_rmse,
                side_recent_d,
                lookback_points,
                float(min_gain_abs_prevn),
                float(min_gain_rel_prevn),
                float(min_gain_abs_parab),
            )

            if bool(is_break):
                if int(abs(int(ji) - int(side_last_break_index.get(side, -10_000_000)))) < int(
                    min_breakpoint_spacing_points
                ):
                    is_break = False

            side_last_rmse[side] = rm_now


            side_recent_rmse.setdefault(side, []).append(float(rm_now))

            side_recent_d.setdefault(side, []).append(float(d_t))

            if np.isfinite(gain_abs) and np.isfinite(gain_rel):
                should_trace = bool(is_break or step_i <= 10 or step_i % 10 == 0 or gain_abs > 0.0)

                if should_trace:
                    log.info(
                        "%s manual grid break-check | side=%s | d=%.6f nm | rmse_now=%.8f | gain_abs=%+.6e vs thr_abs=%.6e | gain_rel=%+.3f%% vs thr_rel=%.3f%% | best_prevN=%.8f (N=%d) | gain_vs_prevN=%+.6e | parab_pred=%.8f | gain_vs_parab=%+.6e vs thr_parab=%.6e | trigger_prevN=%s | trigger_parab=%s | trigger=%s",
                        _LOG_PREFIX,
                        ("right" if side > 0 else "left"),
                        float(d_t),
                        float(rm_now),
                        float(gain_abs),
                        float(abs_thr),
                        100.0 * float(gain_rel),
                        100.0 * float(rel_thr),
                        float(best_prev5) if np.isfinite(best_prev5) else float("nan"),
                        int(lookback_points),
                        float(gain_vs_prev5) if np.isfinite(gain_vs_prev5) else float("nan"),
                        float(parab_pred) if np.isfinite(parab_pred) else float("nan"),
                        float(parab_gain) if np.isfinite(parab_gain) else float("nan"),
                        float(parab_thr) if np.isfinite(parab_thr) else float("nan"),
                        ("yes" if trigger_prev5 else "no"),
                        ("yes" if trigger_parabola else "no"),
                        ("yes" if is_break else "no"),
                    )

            if is_break and n_branch_trigger < int(max_branch_events):
                n_branch_trigger += 1
                side_last_break_index[side] = int(ji)

                log.info(
                    "%s manual grid breakpoint detected | side=%s | d=%.6f nm | DeltaRMSE=%+.6e (%.2f%%) -> reverse exploration",
                    _LOG_PREFIX,
                    ("right" if side > 0 else "left"),
                    float(d_t),
                    float(gain_abs),
                    100.0 * float(gain_rel),
                )

                n_global_opt_runs += 1
                maxfun_global = int(max(300, maxfun_polish, maxfun, maxfun_base))
                cand_global = _run_global_opt_from_breakpoint(
                    d_break=float(d_t),
                    fit_break=fit,
                    side_origin=int(side),
                    k=k,
                    base_eff=base_eff,
                    sk=sk,
                    cfg=cfg,
                    maxfun_global=maxfun_global,
                )
                rmse_global = (
                    float(cand_global.get("rmse", float("nan"))) if isinstance(cand_global, dict) else float("nan")
                )
                d_global_eval = float(d_t)
                if isinstance(cand_global, dict):
                    dg_ev = cand_global.get("d_nm")
                    if isinstance(dg_ev, (int, float)) and np.isfinite(float(dg_ev)):
                        d_global_eval = float(dg_ev)
                if np.isfinite(rmse_global):
                    ctx._touch_absolute_best(d_global_eval, float(rmse_global), tag="global_opt_eval")
                beat_abs = bool(
                    np.isfinite(rmse_global)
                    and (
                        (
                            not np.isfinite(rmse_abs_ref)
                            and (not np.isfinite(best_global_rmse) or rmse_global < best_global_rmse)
                        )
                        or (np.isfinite(rmse_abs_ref) and rmse_global + 1e-12 < rmse_abs_ref)
                        or (np.isfinite(best_global_rmse) and rmse_global + 1e-12 < best_global_rmse)
                    )
                )
                if beat_abs and isinstance(cand_global, dict):
                    n_global_opt_improved += 1
                    best_global_rmse = float(rmse_global)
                    best_global_result = dict(cand_global)
                    if np.isfinite(rmse_abs_ref):
                        rmse_abs_ref = float(min(rmse_abs_ref, rmse_global))
                    else:
                        rmse_abs_ref = float(rmse_global)
                global_opt_events.append(
                    {
                        "d_break_nm": float(d_t),
                        "side": float(side),
                        "rmse_global": float(rmse_global),
                        "beat_absolute_best": float(1.0 if beat_abs else 0.0),
                    }
                )
                if np.isfinite(rmse_global):
                    log.info(
                        "%s manual grid breakpoint global-opt | d_break=%.6f nm | side_origin=%s | rmse_global=%.8f | rmse_abs_ref=%.8f | beat_abs=%s",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                        float(rmse_global),
                        float(rmse_abs_ref) if np.isfinite(rmse_abs_ref) else float("nan"),
                        ("yes" if beat_abs else "no"),
                    )
                else:
                    log.info(
                        "%s manual grid breakpoint global-opt | d_break=%.6f nm | side_origin=%s | rmse_global=n/a | beat_abs=no",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                    )

                branch_sign = ctx._choose_branch_direction_sign(
                    d_break=float(d_t),
                    x_seed_start=x_seed_new.copy(),
                    side_origin=int(side),
                    rmse_break=float(rm_now),
                )
                if int(branch_sign) == 0:
                    log.info(
                        "%s manual grid breakpoint branch-sense | d_break=%.6f nm | side_origin=%s | no viable direction",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                    )
                    n_extra, x_seed_rev_end = 0, x_seed_new.copy()
                else:
                    log.info(
                        "%s manual grid breakpoint branch-sense | d_break=%.6f nm | side_origin=%s | chosen=%s",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                        ("right" if int(branch_sign) > 0 else "left"),
                    )
                    n_extra, x_seed_rev_end = ctx._branch_reverse_from_breakpoint(
                        d_break=float(d_t),
                        x_seed_start=x_seed_new.copy(),
                        side_origin=int(side),
                        branch_sign=int(branch_sign),
                        primary_step_idx=int(step_i),
                    )

                n_branch_extra_points += int(n_extra)
                if np.asarray(x_seed_rev_end, dtype=np.float64).size == np.asarray(x_seed_new, dtype=np.float64).size:
                    if side > 0:
                        x_seed_left = np.asarray(x_seed_rev_end, dtype=np.float64).ravel().copy()
                    else:
                        x_seed_right = np.asarray(x_seed_rev_end, dtype=np.float64).ravel().copy()

                log.info(
                    "%s manual grid reverse-explore done | d_break=%.6f nm | side_origin=%s | n_extra=%d | opposite_seed_updated=%s",
                    _LOG_PREFIX,
                    float(d_t),
                    ("right" if side > 0 else "left"),
                    int(n_extra),
                    ("yes" if int(n_extra) > 0 else "no"),
                )

                branch_events.append(
                    {
                        "d_break_nm": float(d_t),
                        "gain_abs_rmse": float(gain_abs),
                        "gain_rel_frac": float(gain_rel),
                        "side": float(side),
                        "n_extra_points": float(n_extra),
                        "trigger_prevN": float(1.0 if bool(trigger_prev5) else 0.0),
                        "trigger_parabola": float(1.0 if bool(trigger_parabola) else 0.0),
                        "branch_dir_sign": float(branch_sign) if "branch_sign" in locals() else float("nan"),
                    }
                )
            elif is_break:
                log.info(
                    "%s manual grid breakpoint skipped | side=%s | d=%.6f nm | reason=max_branch_events reached (%d/%d)",
                    _LOG_PREFIX,
                    ("right" if side > 0 else "left"),
                    float(d_t),
                    int(n_branch_trigger),
                    int(max_branch_events),
                )

    # -- P0 re-pass: rescue points trapped in a local (n,k) minimum ----------
    # Problem: chained warm-start (each point seeded from its neighbor)
    # can propagate a bad local minimum across an entire exploration arm.
    # Solution: after the main loop, re-fit each "suspect" point once
    # using the seed from the global optimum.
    _profile_p0_suspects(
        d_list,
        r_list,
        x_nodes_best_list,
        n_list,
        k_list,
        nfev_list,
        k,
        lam_full,
        stop_check,
        ctx._fit_point_with_extra_polish,
        ctx._touch_absolute_best,
    )
    # ─────────────────────────────────────────────────────────────────────────────

    coverage_complete = _profile_manual_grid_coverage_audit(
        d_arr,
        d_list,
        point_kind_list,
        x_seed_center,
        x_nodes0,
        bounds_nodes,
        lam_full,
        sk,
        cfg,
        base_eff,
        r_list,
        rmse_abs_ref,
        k,
        _build_emergency_fit_record,
        ctx._append_fit_record,
        ctx._emit_live,
    )

    return _package_profile_grid_result(
        d_list=d_list,
        r_list=r_list,
        n_list=n_list,
        k_list=k_list,
        nit_list=nit_list,
        nfev_list=nfev_list,
        point_kind_list=point_kind_list,
        point_status_code_list=point_status_code_list,
        x_nodes_best_list=x_nodes_best_list,
        t0=t0,
        d_arr=d_arr,
        d0=d0,
        i_center=i_center,
        nom_pack_present=bool(nom_pack is not None),
        n_branch_trigger=n_branch_trigger,
        n_branch_extra_points=n_branch_extra_points,
        n_global_opt_runs=n_global_opt_runs,
        n_global_opt_improved=n_global_opt_improved,
        branch_events=branch_events,
        global_opt_events=global_opt_events,
        best_global_rmse=best_global_rmse,
        best_global_result=best_global_result,
        rmse_nominal_baseline_for_grid=rmse_nominal_baseline_for_grid,
        rmse_abs_ref=rmse_abs_ref,
        sk=sk,
        cfg=cfg,
        base_eff=base_eff,
        k=k,
        coverage_complete=coverage_complete,
    )