#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Spline workers: local L-BFGS-B (SOL2), SOL3/SOL3b stages, chunked polish."""

from __future__ import annotations

import logging

import time

from threading import Event

from typing import Any, Callable

import numpy as np

from scipy.optimize import minimize

from certus_core import N_MIN_LIMIT, N_MAX_LIMIT

from certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _transmittance_absolute_from_nk,
)

from certus_physics import (
    PGlobalConfig,
    PGlobalOptimizer,
    Sample,
    calculate_bare_substrate_RT,
    clip_to_bounds,
)

from certus_index_spline_core import (
    DataType,
    NUMERICAL_FAULT_EXCEPTIONS,
    SplineOptConfig,
    SmartInitPreviewCancelled,
    _log_spline_pipeline_json,
    enforce_k_floor_on_nodes,
    make_bounds_and_x0,
    min_relative_lambda_spacing_ratio,
    nan_nk_outside_rmse_lambda_window,
    physical_nodes_to_x_slice_n,
    rmse_at_spline_stage_x0_init,
    snapshot_result_with_rmse_fit_meta,
    sol3_phase1_maxfun_effective,
    _reflectance_absolute_backside_from_nk,
)

from spline_objective import (
    SplinePWLObjective,
    _spline_objective_lam_mask,
    build_spline_objective_masked_grid,
    decompose_spline_pwl_objective,
    nk_from_x_pwlnk,
    sigma_knots_decode,
    sigma_knots_encode,
    spline_objective_mse_on_masked_grid,
    spline_pwl_analytic_grad_supported,
    spline_spectral_mse_from_xy_nk,
    x_slice_n_to_physical_nodes,
)

def _pglobal_bounds_trust_region(
    bounds_full: np.ndarray,
    x0: np.ndarray,
    k_sigma: int,
    k_lo: int,
    k_hi: int,
    rho_lo: float,
    rho_hi: float,
    sigma_knots: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    """Tightens the bounds passed to PGlobal around ``x0``; decreases as K increases.

    If a knot is outside [600, 3000] nm, the trust box is relaxed (wider box) to account

    for the high uncertainty of the initial local solution (Needle) in the UV / Far-IR.

    """

    b = np.asarray(bounds_full, dtype=np.float64).copy()

    x0v = np.asarray(x0, dtype=np.float64).ravel()

    ks = int(k_sigma)

    k_lo = int(max(3, k_lo))

    k_hi = int(max(k_lo + 1, k_hi))

    rh = float(rho_hi)

    rl = float(rho_lo)

    if ks <= k_lo:
        rho = rh

    elif ks >= k_hi:
        rho = rl

    else:
        t = float(ks - k_lo) / float(k_hi - k_lo)

        rho = rh + t * (rl - rh)

    rho = float(np.clip(rho, 1e-7, 0.5))

    dim = int(b.shape[0])

    for i in range(dim):
        L, U = float(b[i, 0]), float(b[i, 1])

        span = U - L

        if not np.isfinite(span) or span <= 0.0:
            continue

        current_rho = rho

        # Relaxation at the edges because the uncertainty on the Needle probe is high

        if sigma_knots is not None and i > 0:
            idx_knot = (i - 1) % ks

            lam_knot = 1.0 / max(float(sigma_knots[idx_knot]), 1e-12)

            if lam_knot < 600.0 or lam_knot > 3000.0:
                current_rho = min(0.45, current_rho * 2.5)

        hw = current_rho * span

        lo = max(L, float(x0v[i]) - hw)

        hi = min(U, float(x0v[i]) + hw)

        if hi <= lo + 1e-18 * max(1.0, abs(U)):
            lo, hi = L, U

        b[i, 0], b[i, 1] = lo, hi

    return b, rho

def _build_live_dict(
    cfg: SplineOptConfig,
    sigma_knots: np.ndarray,
    xv: np.ndarray,
    mse: float,
    progress_meta: int,
) -> dict:
    """Same spectral grid as file / cfg.lam_nm (not only masked lam_f) for GUI display."""

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    n_sub_full = np.asarray(cfg.n_sub, dtype=np.float64).ravel()

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    xv = np.asarray(xv, dtype=np.float64).ravel()

    sig_full = 1.0 / np.maximum(lam, 1e-9)

    n_l, k_l = nk_from_x_pwlnk(
        xv,
        lam,
        sk,
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=sig_full,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=cfg.nk_profile_interp,
    )

    d_nm = float(xv[0])

    t_is_ratio_val = bool(cfg.t_is_ratio)

    if t_is_ratio_val:
        t_th = _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    else:
        t_th = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    r_th = None

    if cfg.r_exp is not None:
        if t_is_ratio_val:
            r_th = _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

        else:
            r_th = _reflectance_absolute_backside_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    k_nodes = int(sk.size)

    n_nodes_phys = x_slice_n_to_physical_nodes(xv[1 : 1 + k_nodes], sk, cfg.n_mono_band_nm)

    L_nodes = np.asarray(xv[1 + k_nodes : 1 + 2 * k_nodes], dtype=np.float64).copy()

    mse_ui = float(mse)

    if float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0) > 0.0:
        ms_sp = spline_spectral_mse_from_xy_nk(cfg, lam, n_l, k_l, d_nm)

        if ms_sp is not None and np.isfinite(ms_sp):
            mse_ui = float(ms_sp)

    n_l, k_l = nan_nk_outside_rmse_lambda_window(lam, n_l, k_l, cfg.rmse_fit_lambda_nm)

    return {
        "lam_nm": lam,
        "n_lam": n_l,
        "k_lam": k_l,
        "sigma_knots": sk,
        "t_theo": t_th,
        "r_theo": r_th,
        "mse": mse_ui,
        "rmse": float(np.sqrt(max(mse_ui, 0.0))),
        "d_nm": d_nm,
        "live_progress_meta": int(progress_meta),
        "t_is_ratio": t_is_ratio_val,
        "x": xv.copy(),
        "n_nodes_physical": np.asarray(n_nodes_phys, dtype=np.float64).copy(),
        "L_nodes": L_nodes,
        "n_mono_band_nm": cfg.n_mono_band_nm,
        "x_encoding": "xi_n_mono" if cfg.n_mono_band_nm is not None else "n_physical",
    }

def _polish_lbfgsb_chunked(
    obj: SplinePWLObjective,
    x_start: np.ndarray,
    bounds: np.ndarray,
    maxfun_total: int,
    stop_event: Event,
    *,
    progress_cb: Callable[[int, str], None] | None = None,
    live_cb: Callable[[dict], None] | None = None,
    sigma_knots: np.ndarray | None = None,
    progress_lo: int = 85,
    progress_hi: int = 100,
) -> tuple[np.ndarray, float, int]:
    """L-BFGS-B (unbroken) to preserve the Hessian approximation. Stop via StopIteration."""

    x_cur = np.asarray(x_start, dtype=np.float64, order="C").ravel().copy()

    dim = int(bounds.shape[0])

    bds = [(float(bounds[i, 0]), float(bounds[i, 1])) for i in range(dim)]

    # Best iterate seen during L-BFGS-B (the last one returned by SciPy might be worse if maxfun / stop).
    # Tracking wrapper: records (x, f) during normal L-BFGS-B evaluations,
    # eliminating redundant obj() calls in the callback (~50% eval reduction).
    _best_x_seen = [x_cur.copy()]

    _best_fun_seen = [float(obj(x_cur))]

    _tracker_last_x = [x_cur.copy()]
    _tracker_last_f = [_best_fun_seen[0]]

    _orig_obj = obj

    def _tracking_obj(xv):
        f = float(_orig_obj(xv))
        _tracker_last_x[0] = np.asarray(xv, dtype=np.float64).ravel().copy()
        _tracker_last_f[0] = f
        if f < float(_best_fun_seen[0]) - 1e-18:
            _best_fun_seen[0] = f
            _best_x_seen[0] = _tracker_last_x[0].copy()
        return f

    # Replace obj for minimize() so all evaluations are tracked
    obj = _tracking_obj

    state = {
        "x": x_cur.copy(),
        "nfev": 0,
        "nit": 0,
        "last_fun": float(_best_fun_seen[0]),
    }

    last_ui_time = [0.0]

    class LBFGSBStop(Exception):
        pass

    def _cb(xk):

        state["nit"] += 1

        state["x"] = np.asarray(xk, dtype=np.float64).copy()

        # Use tracked best instead of re-evaluating obj (saves ~50% evals)
        state["last_fun"] = float(_best_fun_seen[0])

        now = time.monotonic()

        if now - last_ui_time[0] > 0.35:
            last_ui_time[0] = now

            if progress_cb:
                lo = int(np.clip(int(progress_lo), 0, 99))

                hi = int(np.clip(int(progress_hi), lo + 1, 100))

                span = max(1, hi - lo)

                frac = min(1.0, float(state["nit"]) / max(1.0, float(maxfun_total)))

                pct = float(lo) + float(span) * frac

                progress_cb(
                    pct,
                    f"Polish L-BFGS-B: iterations={state['nit']} | RMSE={float(np.sqrt(max(float(_best_fun_seen[0]), 0.0))):.6f}",
                )

            if live_cb and sigma_knots is not None:
                try:
                    xv = _best_x_seen[0]

                    live_cb(
                        _build_live_dict(_orig_obj.cfg, sigma_knots, xv, float(_best_fun_seen[0]), int(state["nit"]))
                    )

                except NUMERICAL_FAULT_EXCEPTIONS:
                    logging.getLogger("CERTUS").debug("live_cb failed in _polish_lbfgsb_chunked", exc_info=True)

        if stop_event.is_set():
            raise LBFGSBStop()

    # Attempt to combine fun+grad into single call (jac=True) to halve TMM evals.
    _minimize_fn = obj  # already the tracking wrapper
    _minimize_jac = None

    try:
        from spline_objective import spline_pwl_analytic_grad_supported

        if spline_pwl_analytic_grad_supported(_orig_obj.cfg):
            _gt = _orig_obj.analytic_gradient(x_cur)

            if _gt is not None and np.all(np.isfinite(_gt)):
                _grad_fn = _orig_obj.analytic_gradient

                def _combined_fun_and_grad(xv):
                    f = obj(xv)  # goes through tracking wrapper
                    g = _grad_fn(xv)
                    if g is None:
                        return f  # scipy falls back to FD
                    return f, g

                _minimize_fn = _combined_fun_and_grad
                _minimize_jac = True

    except NUMERICAL_FAULT_EXCEPTIONS:
        logging.getLogger("CERTUS").debug("Analytic gradient probe failed, falling back to numerical", exc_info=True)

    try:
        res = minimize(
            _minimize_fn,
            x_cur,
            method="L-BFGS-B",
            jac=_minimize_jac,
            bounds=bds,
            options={"maxfun": int(maxfun_total), "ftol": 1e-12, "gtol": 1e-9},
            callback=_cb,
        )

        _xf = np.asarray(res.x, dtype=np.float64).ravel().copy()

        _ff = float(obj(_xf))

        if _ff < float(_best_fun_seen[0]) - 1e-18:
            _best_fun_seen[0] = _ff

            _best_x_seen[0] = _xf.copy()

        state["x"] = np.asarray(_best_x_seen[0], dtype=np.float64).ravel().copy()

        state["last_fun"] = float(_best_fun_seen[0])

        state["nfev"] = int(getattr(res, "nfev", getattr(res, "nit", state["nit"])))

    except LBFGSBStop:
        # Last callback not necessarily the best: keep the minimal incumbent as done after minimize.

        state["x"] = np.asarray(_best_x_seen[0], dtype=np.float64).ravel().copy()

        state["last_fun"] = float(_best_fun_seen[0])

    except NUMERICAL_FAULT_EXCEPTIONS:
        logging.getLogger("CERTUS").debug(
            "L-BFGS-B minimize raised unexpected exception in _polish_lbfgsb_chunked",
            exc_info=True,
        )

    return state["x"], state["last_fun"], state["nfev"]

def _pack_spline_stage_result(
    cfg: SplineOptConfig,
    sigma_knots: np.ndarray,
    x_best: np.ndarray,
    final_mse: float,
    nfev_pglobal: int,
    nit_polish: int,
    *,
    stage_repli_local: bool = False,
    pglobal_trust_rho: float | None = None,
) -> dict[str, Any]:
    """Build the result dict for one spline stage (PGlobal + polish)."""

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    n_sub_full = np.asarray(cfg.n_sub, dtype=np.float64)

    sig_full = 1.0 / np.maximum(lam, 1e-9)

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    x_best = np.asarray(x_best, dtype=np.float64).ravel().copy()

    k_nodes = int(sk.size)

    L_nodes = np.asarray(x_best[1 + k_nodes : 1 + 2 * k_nodes], dtype=np.float64).copy()

    # Clamp + flat only (same K as x): insertion disabled here

    _, L_nodes_f, k_floor_mod = enforce_k_floor_on_nodes(sk, L_nodes, k_floor=float(cfg.k_clip_lo), allow_insert=False)

    if k_floor_mod:
        x_best[1 + k_nodes : 1 + 2 * k_nodes] = L_nodes_f

        logging.getLogger("CERTUS").info("k_floor enforce: L nodes adjusted (clamp/flat) in _pack_spline_stage_result")

    n_l, k_l = nk_from_x_pwlnk(
        x_best,
        lam,
        sk,
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=sig_full,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=cfg.nk_profile_interp,
    )

    d_nm = float(x_best[0])

    if cfg.t_is_ratio:
        np.asarray(calculate_bare_substrate_RT(lam, n_sub_full), dtype=np.float64)

        t_th = _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    else:
        t_th = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    r_th = None

    if cfg.r_exp is not None:
        if cfg.t_is_ratio:
            r_th = _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

        else:
            r_th = _reflectance_absolute_backside_from_nk(lam, n_l, k_l, d_nm, n_sub_full)

    n_nodes_phys = x_slice_n_to_physical_nodes(x_best[1 : 1 + k_nodes], sk, cfg.n_mono_band_nm)

    L_nodes = np.asarray(x_best[1 + k_nodes : 1 + 2 * k_nodes], dtype=np.float64).copy()

    mse_report = float(final_mse)

    w_pen = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)

    if k_floor_mod or w_pen > 0.0:
        ms_sp = spline_spectral_mse_from_xy_nk(cfg, lam, n_l, k_l, d_nm)

        if ms_sp is not None and np.isfinite(ms_sp):
            mse_report = float(ms_sp)

    return {
        "x": x_best,
        "sigma_knots": sigma_knots,
        "n_seg": int(np.asarray(sigma_knots, dtype=np.float64).size - 1),
        "lam_nm": lam,
        "n_lam": n_l,
        "k_lam": k_l,
        "d_nm": d_nm,
        "mse": float(mse_report),
        "rmse": float(np.sqrt(max(mse_report, 0.0))),
        "t_theo": t_th,
        "r_theo": r_th,
        "nfev_pglobal": int(nfev_pglobal),
        "nit_polish": int(nit_polish),
        "stage_repli_local": bool(stage_repli_local),
        "pglobal_trust_rho": None if pglobal_trust_rho is None else float(pglobal_trust_rho),
        "n_mono_band_nm": cfg.n_mono_band_nm,
        "n_mono_continuous_penalty": float(cfg.n_mono_continuous_penalty),
        "x_encoding": "xi_n_mono" if cfg.n_mono_band_nm is not None else "n_physical",
        "n_nodes_physical": n_nodes_phys,
        "L_nodes": L_nodes,
        "nk_profile_interp": str(cfg.nk_profile_interp),
    }

def _free_knot_warm_state(
    base_result: dict,
    cfg: Any,
    optimize_n: bool,
    seq_label: str,
    stage_name: str,
    ev: str,
    progress_cb: Callable,
    log: Any,
) -> dict | None:
    """Extract and validate warm-start knot/nk state from *base_result*.

    Returns a mapping with keys ``sk0``, ``skn0``, ``skL0``, ``d0``, ``nn0``, ``LL0``,
    ``K``, ``x_sol2_for_check`` on success.  Returns ``None`` when the warm state is
    invalid; *progress_cb* has already been notified in that case.
    """
    sk0 = np.asarray(base_result.get("sigma_knots", []), dtype=np.float64).ravel()
    skn0 = np.asarray(base_result.get("sigma_knots_n", sk0), dtype=np.float64).ravel()
    skL0 = np.asarray(base_result.get("sigma_knots_L", sk0), dtype=np.float64).ravel()
    d0 = float(base_result.get("d_nm", 0.5 * (cfg.d_lo + cfg.d_hi)))
    nn0 = np.asarray(base_result.get("n_nodes_physical", []), dtype=np.float64).ravel()
    LL0 = np.asarray(base_result.get("L_nodes", []), dtype=np.float64).ravel()

    # Vecteur ``x`` du stage SOL2 : source de vérité (d, ξ_n→n physique, L) après polish « best-seen ».
    x_sol2_for_check: np.ndarray | None = None
    _xp = base_result.get("x")
    if _xp is not None:
        _xv = np.asarray(_xp, dtype=np.float64).ravel()
        _k_mesh = int(sk0.size)
        if _k_mesh >= 2 and int(_xv.size) == 1 + 2 * _k_mesh:
            d0 = float(_xv[0])
            nn0 = x_slice_n_to_physical_nodes(_xv[1 : 1 + _k_mesh], sk0, cfg.n_mono_band_nm)
            LL0 = np.asarray(_xv[1 + _k_mesh : 1 + 2 * _k_mesh], dtype=np.float64).ravel()
            x_sol2_for_check = _xv.copy()
            log.info(
                "PIPELINE [%s] %s | warm d, n_phys, L from SOL2 packed ``x`` (best-ever incumbent; len=%d, K=%d).",
                seq_label,
                stage_name,
                int(_xv.size),
                _k_mesh,
            )
        elif (not optimize_n) and _k_mesh >= 2 and int(_xv.size) == 4 * _k_mesh - 1:
            log.info(
                "PIPELINE [%s] %s | ``x`` au format SOL3 scindé (len=%d, K=%d); warm via sigma_knots_* / n_nodes / L_nodes.",
                seq_label,
                stage_name,
                int(_xv.size),
                _k_mesh,
            )
        elif int(_xv.size) > 0:
            log.warning(
                "PIPELINE [%s] %s | SOL2 ``x`` len=%d incompatible with K=%d; using n_nodes_physical / L_nodes.",
                seq_label,
                stage_name,
                int(_xv.size),
                _k_mesh,
            )
    else:
        log.warning(
            "PIPELINE [%s] %s | pas de ``x`` dans base_result; warm depuis d_nm / n_nodes_physical / L_nodes (legacy).",
            seq_label,
            stage_name,
        )

    if optimize_n:
        if sk0.size < 2 or nn0.size != sk0.size or LL0.size != sk0.size:
            log.warning("_run_free_knot_stage (%s): invalid warm state.", stage_name)
            _log_spline_pipeline_json(
                log,
                f"{ev}_abort",
                seq=seq_label,
                reason="invalid_warm_state",
                sk0=int(sk0.size),
                n0=int(nn0.size),
                L0=int(LL0.size),
            )
            progress_cb(100, f"{stage_name}: abort (invalid warm state).")
            return None
        K = int(sk0.size)
    else:
        if skn0.size < 2 or skL0.size < 2 or nn0.size != skn0.size or LL0.size != skL0.size:
            log.warning("_run_free_knot_stage (%s): invalid warm state.", stage_name)
            _log_spline_pipeline_json(
                log,
                f"{ev}_abort",
                seq=seq_label,
                reason="invalid_warm_state",
            )
            progress_cb(100, f"{stage_name}: abort (invalid warm state).")
            return None
        K = int(skL0.size)

    return {
        "sk0": sk0,
        "skn0": skn0,
        "skL0": skL0,
        "d0": d0,
        "nn0": nn0,
        "LL0": LL0,
        "K": K,
        "x_sol2_for_check": x_sol2_for_check,
    }

def _lbfgsb_phase_with_progress(
    z_start: np.ndarray,
    options: dict[str, Any],
    phase_idx: int,
    phase_lo: float,
    phase_hi: float,
    phase_name: str,
    phase_count: int,
    bnds: Any,
    stage_name: str,
    progress_cb: Callable,
    obj_tracked_fn: Callable,
) -> Any:
    """Run one L-BFGS-B phase and emit periodic progress via *progress_cb*.

    Extracted from the inner function previously defined inside
    ``_run_free_knot_stage`` to allow independent testing and reuse.
    """
    maxfun_phase = int(max(1, options.get("maxfun", 1) or 1))
    state: dict[str, Any] = {
        "nfev": 0,
        "nit": 0,
        "t0": time.monotonic(),
        "last_emit": 0.0,
        "last_fun": float("nan"),
    }

    def _emit(force: bool = False) -> None:
        now = time.monotonic()
        frac = min(1.0, float(state["nfev"]) / float(maxfun_phase))
        pct = phase_lo + (phase_hi - phase_lo) * frac
        if force or now - float(state["last_emit"]) >= 5.0:
            state["last_emit"] = now
            progress_cb(
                pct,
                f"{stage_name}: {phase_name} {phase_idx + 1}/{phase_count}"
                f" | evals={int(state['nfev'])}/{maxfun_phase}"
                f" | nit={int(state['nit'])}"
                f" | RMSE={float(np.sqrt(max(float(state['last_fun']), 0.0))):.6f}"
                f" | elapsed={now - float(state['t0']):.0f}s",
            )

    def _obj_phase(z: np.ndarray) -> float:
        state["nfev"] += 1
        val = float(obj_tracked_fn(z))
        state["last_fun"] = val
        _emit(force=False)
        return val

    def _cb_phase(_xk: np.ndarray) -> None:
        state["nit"] += 1
        _emit(force=False)

    progress_cb(
        phase_lo,
        f"{stage_name}: {phase_name} {phase_idx + 1}/{phase_count} started | eval budget={maxfun_phase}",
    )
    res = minimize(_obj_phase, z_start, method="L-BFGS-B", bounds=bnds, options=options, callback=_cb_phase)
    state["nfev"] = max(int(state["nfev"]), int(getattr(res, "nfev", 0) or 0))
    state["nit"] = max(int(state["nit"]), int(getattr(res, "nit", 0) or 0))
    _emit(force=True)
    return res

def _run_free_knot_stage(
    cfg: SplineOptConfig,
    base_result: dict,
    stop_event: Event,
    progress_cb,
    live_cb=None,
    *,
    optimize_n: bool = True,
    seq_label: str = "03",
    stage_name: str = "SOL 3",
    apply_result_finalize: bool = True,
) -> dict | None:
    """L-BFGS-B, free sigma knots: SOL3 (n, L, sigma_n, sigma_L) or SOL3b (fixed n, L and sigma_L)."""


    log = logging.getLogger("CERTUS")

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    sig = 1.0 / np.maximum(lam, 1e-9)

    ev = "sol3" if optimize_n else "sol3b"

    mg = build_spline_objective_masked_grid(cfg)

    if mg is None:
        log.warning("_run_free_knot_stage (%s): empty objective mask.", stage_name)

        _log_spline_pipeline_json(
            log,
            f"{ev}_abort",
            seq=seq_label,
            reason="masked_grid_empty",
        )

        progress_cb(100, f"{stage_name}: Aborted (empty mask).")

        return None

    lam_f, sig_f, n_sub_f_mg, w_f, inv_npix, t_exp_f, r_exp_f = mg

    s_lo = float(np.min(sig))

    s_hi = float(np.max(sig))

    _span_sig = float(max(s_hi - s_lo, 1e-30))

    # sigma_knots_decode(encode(sk)) déplace légèrement les nœuds (~1e-5 en σ, eps_s + cumsum).
    # Les n/L du warm start sont définis sur sigma_knots du résultat SOL2/SOL3 : pour nk_from_x
    # on réutilise ce maillage de référence tant que sk décodé n'a pas réellement bougé.
    _sigma_snap_atol = float(max(2.5e-5, 1e-6 * _span_sig, 1e-12))

    _ws = _free_knot_warm_state(base_result, cfg, optimize_n, seq_label, stage_name, ev, progress_cb, log)

    if _ws is None:
        return None

    sk0 = _ws["sk0"]

    skn0 = _ws["skn0"]

    skL0 = _ws["skL0"]

    d0 = _ws["d0"]

    nn0 = _ws["nn0"]

    LL0 = _ws["LL0"]

    K = _ws["K"]

    x_sol2_for_check = _ws["x_sol2_for_check"]

    M = K - 1

    lo_k = max(float(cfg.k_clip_lo), 1e-12)

    hi_k = max(float(cfg.k_clip_hi), lo_k * 1.0001)

    L_lo = float(np.log(lo_k))

    L_hi = float(np.log(hi_k))

    n_lo = float(N_MIN_LIMIT)

    n_hi = float(N_MAX_LIMIT)

    def _w2s(sk: np.ndarray) -> np.ndarray:

        return sigma_knots_encode(sk, s_lo, s_hi)

    _decode_work: dict[str, np.ndarray] = {}

    def _s2s(raw: np.ndarray) -> np.ndarray:

        return sigma_knots_decode(raw, s_lo, s_hi, work=_decode_work, reuse_output=True)


    if not optimize_n:
        np.interp(sig_f, skn0, nn0)

    float(max(getattr(cfg, "lnk_spline_reg_weight", 1e-3), 0.0))

    min_dlam_ratio_req = float(max(getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.0) or 0.0, 0.0))
    lam_lo = float(np.min(lam)) if lam.size else float("nan")
    lam_hi = float(np.max(lam)) if lam.size else float("nan")

    skn_spacing_ref = np.asarray(skn0, dtype=np.float64).ravel().copy()

    skL_spacing_ref = np.asarray(skL0, dtype=np.float64).ravel().copy()

    if min_dlam_ratio_req > 0.0:
        log.debug(
            "PIPELINE [%s] %s | espacement nœuds libres : cfg min_delta_lambda/lambda_mean=%.5g ; "
            "pénalité si min(Deltaλ)/λ_mean **diminue** vs maillage SOL2 (fichier λ [%.4f, %.4f] nm).",
            seq_label,
            stage_name,
            min_dlam_ratio_req,
            lam_lo,
            lam_hi,
        )

    if optimize_n:
        z0 = np.concatenate(([d0], _w2s(skn0), _w2s(skL0), np.clip(nn0, n_lo, n_hi), np.clip(LL0, L_lo, L_hi)))

        if min_dlam_ratio_req > 0.0 and np.isfinite(lam_lo) and np.isfinite(lam_hi) and lam_hi > lam_lo:
            _r_sp_n = float(min_relative_lambda_spacing_ratio(skn0, lam_lo, lam_hi))

            _r_sp_L = float(min_relative_lambda_spacing_ratio(skL0, lam_lo, lam_hi))

            log.info(
                "PIPELINE [%s] %s | SOL3 init (maille SOL2): min(Deltaλ)/λ_mean  sigma_n=%.6f  sigma_L=%.6f "
                "| cfg construction=%.6f (un pas UV court peut donner un ratio << cfg ; "
                "pénalité SOL3 seulement si ce ratio **baisse** vs ce départ).",
                seq_label,
                stage_name,
                _r_sp_n,
                _r_sp_L,
                min_dlam_ratio_req,
            )

        bnds = (
            [(float(cfg.d_lo), float(cfg.d_hi))]
            + [(-12.0, 12.0)] * M
            + [(-12.0, 12.0)] * M
            + [(n_lo, n_hi)] * K
            + [(L_lo, L_hi)] * K
        )

        def _unpack(z: np.ndarray):

            zz = z.ravel()

            return (
                float(zz[0]),
                _s2s(zz[1 : 1 + M]),
                _s2s(zz[1 + M : 1 + 2 * M]),
                zz[1 + 2 * M : 1 + 2 * M + K],
                zz[1 + 2 * M + K : 1 + 2 * M + 2 * K],
            )

    else:
        z0 = np.concatenate(([d0], _w2s(skL0), np.clip(LL0, L_lo, L_hi)))

        if min_dlam_ratio_req > 0.0 and np.isfinite(lam_lo) and np.isfinite(lam_hi) and lam_hi > lam_lo:
            _r_sp_Lb = float(min_relative_lambda_spacing_ratio(skL0, lam_lo, lam_hi))

            log.info(
                "PIPELINE [%s] %s | SOL3b init: min(Deltaλ)/λ_mean (sigma_L)=%.6f | cfg construction=%.6f "
                "(pénalité seulement si ce ratio **baisse** vs ce départ).",
                seq_label,
                stage_name,
                _r_sp_Lb,
                min_dlam_ratio_req,
            )

        bnds = [(float(cfg.d_lo), float(cfg.d_hi))] + [(-12.0, 12.0)] * M + [(L_lo, L_hi)] * K

        def _unpack(z: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:

            zz = np.asarray(z, dtype=np.float64).ravel()

            d = float(zz[0])

            skL = _s2s(zz[1 : 1 + M])

            LL = zz[1 + M : 1 + M + K]

            return d, skL, LL

    _nk_prof_sol3 = str(getattr(cfg, "nk_profile_interp", "smooth") or "smooth")

    def _sk_max_abs_delta(a: np.ndarray, b: np.ndarray) -> float:

        aa = np.asarray(a, dtype=np.float64).ravel()

        bb = np.asarray(b, dtype=np.float64).ravel()

        if aa.size != bb.size:
            return float("inf")

        return float(np.max(np.abs(aa - bb)))

    def _snap_nk_mesh_sol3_split(
        skn_a: np.ndarray,
        skL_a: np.ndarray,
        nn_a: np.ndarray,
        LL_v: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:

        skn_a = np.asarray(skn_a, dtype=np.float64).ravel()

        skL_a = np.asarray(skL_a, dtype=np.float64).ravel()

        nn_a = np.asarray(nn_a, dtype=np.float64).ravel()

        LL_v = np.asarray(LL_v, dtype=np.float64).ravel()

        if (
            int(sk0.size) == int(skn_a.size)
            and _sk_max_abs_delta(skn_a, sk0) <= _sigma_snap_atol
            and _sk_max_abs_delta(skL_a, sk0) <= _sigma_snap_atol
        ):
            sk_ref = np.asarray(sk0, dtype=np.float64).ravel()

            nn_at = np.asarray(nn_a, dtype=np.float64).ravel().copy()

            LL_at = np.asarray(LL_v, dtype=np.float64).ravel().copy()

        else:
            sk_ref = skn_a

            nn_at = np.interp(sk_ref, skn_a, nn_a)

            LL_at = np.interp(sk_ref, skL_a, LL_v)

        return sk_ref, nn_at, LL_at

    def _snap_nk_mesh_sol3b(skL_a: np.ndarray, LL_v: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:

        skL_a = np.asarray(skL_a, dtype=np.float64).ravel()

        LL_v = np.asarray(LL_v, dtype=np.float64).ravel()

        if int(skL0.size) == int(skL_a.size) and _sk_max_abs_delta(skL_a, skL0) <= _sigma_snap_atol:
            sk_ref = np.asarray(skL0, dtype=np.float64).ravel()

            LL_at = np.asarray(LL_v, dtype=np.float64).ravel().copy()

        else:
            sk_ref = skL_a

            LL_at = np.interp(sk_ref, skL_a, LL_v)

        if int(skn0.size) == int(sk_ref.size) and _sk_max_abs_delta(sk_ref, skn0) <= _sigma_snap_atol:
            n_at = np.asarray(nn0, dtype=np.float64).ravel().copy()

        else:
            n_at = np.interp(sk_ref, skn0, nn0)

        return sk_ref, n_at, LL_at

    def _sol3_split_to_nk_masked(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, np.ndarray, np.ndarray]:

        d, skn, skL, nn, LL = _unpack(z)

        skn_a = np.asarray(skn, dtype=np.float64).ravel()

        skL_a = np.asarray(skL, dtype=np.float64).ravel()

        nn_a = np.asarray(nn, dtype=np.float64).ravel()

        LL_v = np.asarray(LL, dtype=np.float64).ravel()

        sk_ref, nn_at, LL_at = _snap_nk_mesh_sol3_split(skn_a, skL_a, nn_a, LL_v)

        xi_n = physical_nodes_to_x_slice_n(nn_at, sk_ref, cfg.n_mono_band_nm)

        x_pack = np.concatenate(
            (
                np.asarray([float(d)], dtype=np.float64),
                np.asarray(xi_n, dtype=np.float64).ravel(),
                np.asarray(LL_at, dtype=np.float64).ravel(),
            )
        )

        n_l, k_l = nk_from_x_pwlnk(
            x_pack,
            lam_f,
            sk_ref,
            lo_k,
            hi_k,
            sig_pre=sig_f,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=_nk_prof_sol3,
        )

        return n_l, k_l, float(d), skn_a, nn_a

    def _sol3b_to_nk_masked(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:

        d, skL, LL = _unpack(z)

        skL_a = np.asarray(skL, dtype=np.float64).ravel()

        LL_a = np.asarray(LL, dtype=np.float64).ravel()

        sk_ref, n_at, LL_at = _snap_nk_mesh_sol3b(skL_a, LL_a)

        xi = physical_nodes_to_x_slice_n(n_at, sk_ref, cfg.n_mono_band_nm)

        x_pack = np.concatenate(
            (
                np.asarray([float(d)], dtype=np.float64),
                np.asarray(xi, dtype=np.float64).ravel(),
                LL_at,
            )
        )

        n_l, k_l = nk_from_x_pwlnk(
            x_pack,
            lam_f,
            sk_ref,
            lo_k,
            hi_k,
            sig_pre=sig_f,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=_nk_prof_sol3,
        )

        return n_l, k_l, float(d), LL_a

    def _spectral_mse_sol3(z: np.ndarray) -> float:

        if stop_event.is_set():
            return 1e30

        if optimize_n:
            n_l, k_l, d, _, _ = _sol3_split_to_nk_masked(z)

        else:
            n_l, k_l, d, _ = _sol3b_to_nk_masked(z)

        return float(
            spline_objective_mse_on_masked_grid(
                cfg,
                lam_f=lam_f,
                n_sub_f=n_sub_f_mg,
                w=w_f,
                inv_npix=inv_npix,
                t_exp_f=t_exp_f,
                r_exp_f=r_exp_f,
                n_l=n_l,
                k_l=k_l,
                d=d,
            )
        )

    def _obj(z: np.ndarray) -> float:

        if stop_event.is_set():
            return 1e30

        if optimize_n:
            n_l, k_l, d, _skn_a, _nn_a = _sol3_split_to_nk_masked(z)

        else:
            n_l, k_l, d, _LL_a = _sol3b_to_nk_masked(z)

        return float(
            spline_objective_mse_on_masked_grid(
                cfg,
                lam_f=lam_f,
                n_sub_f=n_sub_f_mg,
                w=w_f,
                inv_npix=inv_npix,
                t_exp_f=t_exp_f,
                r_exp_f=r_exp_f,
                n_l=n_l,
                k_l=k_l,
                d=d,
            )
        )

    if optimize_n and x_sol2_for_check is not None:
        try:
            _n2, _k2 = nk_from_x_pwlnk(
                np.asarray(x_sol2_for_check, dtype=np.float64).ravel(),
                lam_f,
                sk0,
                lo_k,
                hi_k,
                sig_pre=sig_f,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=str(cfg.nk_profile_interp),
            )

            _mse_sol2_sp = float(
                spline_objective_mse_on_masked_grid(
                    cfg,
                    lam_f=lam_f,
                    n_sub_f=n_sub_f_mg,
                    w=w_f,
                    inv_npix=inv_npix,
                    t_exp_f=t_exp_f,
                    r_exp_f=r_exp_f,
                    n_l=_n2,
                    k_l=_k2,
                    d=float(x_sol2_for_check[0]),
                )
            )

            _mse_sol3_z0_sp = float(_spectral_mse_sol3(z0))

            _tol_m = 1e-6 * max(1.0, abs(_mse_sol2_sp))

            if abs(_mse_sol2_sp - _mse_sol3_z0_sp) > _tol_m:
                log.warning(
                    "PIPELINE [%s] %s | écart init SOL2 vs SOL3(z0) (MSE spectrale grille masquée): "
                    "%.6e vs %.6e (|Delta|=%.6e). Vérifier clip n/L ou encode sigma.",
                    seq_label,
                    stage_name,
                    _mse_sol2_sp,
                    _mse_sol3_z0_sp,
                    abs(_mse_sol2_sp - _mse_sol3_z0_sp),
                )

            else:
                log.info(
                    "PIPELINE [%s] %s | init alignée: MSE spectrale SOL2 ``x`` == SOL3(z0) (~%.6e).",
                    seq_label,
                    stage_name,
                    _mse_sol2_sp,
                )

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.debug(
                "PIPELINE [%s] %s | contrôle MSE SOL2/SOL3 init impossible",
                seq_label,
                stage_name,
                exc_info=True,
            )

    # Best z by **spectral MSE** (same grid / same nk_from_x as SOL2): display RMSE
    # ne peut pas empirer vs le warm start le long de la trajectoire retenue.
    _best_z: list[np.ndarray] = []

    _best_spec_mse: list[float] = []

    def _reset_obj_tracker(z_init: np.ndarray) -> None:

        zi = np.asarray(z_init, dtype=np.float64).ravel().copy()

        _best_z.clear()

        _best_spec_mse.clear()

        _best_z.append(zi)

        _best_spec_mse.append(float(_obj(zi)))

    def _obj_tracked(z: np.ndarray) -> float:

        v = float(_obj(z))

        if v < float(_best_spec_mse[0]) - 1e-18:
            _best_spec_mse[0] = v

            _best_z[0] = np.asarray(z, dtype=np.float64).ravel().copy()

        return v

    rmse_warm = float(np.sqrt(max(float(_obj(z0)), 0.0)))

    if not optimize_n:
        rmse_ref = float(base_result.get("rmse", float("nan")))

        if np.isfinite(rmse_ref):
            min_gain = max(1e-7, 1e-4 * max(abs(rmse_ref), 1e-12))

            if rmse_warm > rmse_ref + min_gain:
                _log_spline_pipeline_json(
                    log,
                    "sol3b_projection_skip",
                    seq=seq_label,
                    rmse_before=float(rmse_ref),
                    rmse_warm_projected=float(rmse_warm),
                    delta_rmse=float(rmse_warm - rmse_ref),
                )

                log.info(
                    "PIPELINE [%s] %s skipped: projected warm-start RMSE %.6f > incoming %.6f "
                    "(Delta=%+.6f). Keeping previous solution.",
                    seq_label,
                    stage_name,
                    float(rmse_warm),
                    float(rmse_ref),
                    float(rmse_warm - rmse_ref),
                )

                progress_cb(100, f"{stage_name}: skipped (warm projection degrades RMSE).")

                return None

    _mxf1 = int(sol3_phase1_maxfun_effective(cfg))

    _mxf2 = int(max(16000, 2 * _mxf1))

    _mxf3 = int(max(40000, 4 * _mxf1))

    _phase_maxfun_list = [_mxf1, _mxf2] + ([_mxf3] if optimize_n else [])

    _phase_weight_total = float(max(1, sum(max(1, int(v)) for v in _phase_maxfun_list)))

    opt_p1 = {"maxiter": 1200, "maxfun": _mxf1, "ftol": 5e-13, "gtol": 1e-12}

    opt_p2 = {"maxiter": 3000, "maxfun": _mxf2, "ftol": 1e-14, "gtol": 1e-14}

    opt_p3 = {"maxiter": 6000, "maxfun": _mxf3, "ftol": 1e-16, "gtol": 1e-16}

    def _phase_progress_bounds(phase_idx: int) -> tuple[float, float]:

        done_before = float(sum(max(1, int(v)) for v in _phase_maxfun_list[:phase_idx]))

        done_after = done_before + float(max(1, int(_phase_maxfun_list[phase_idx])))

        return 100.0 * done_before / _phase_weight_total, 100.0 * done_after / _phase_weight_total

    def _phase_display_name(phase_idx: int) -> str:

        if optimize_n:
            return ("descent", "polish", "deep polish")[phase_idx]

        return ("descent", "polish")[phase_idx]

    def _run_lbfgsb_phase_with_progress(
        z_start: np.ndarray,
        options: dict[str, Any],
        phase_idx: int,
    ) -> Any:

        ph_lo, ph_hi = _phase_progress_bounds(phase_idx)

        ph_name = _phase_display_name(phase_idx)

        ph_count = 3 if optimize_n else 2

        return _lbfgsb_phase_with_progress(
            z_start,
            options,
            phase_idx,
            ph_lo,
            ph_hi,
            ph_name,
            ph_count,
            bnds,
            stage_name,
            progress_cb,
            _obj_tracked,
        )

    if optimize_n:
        _log_spline_pipeline_json(
            log,
            "sol3_minimize_enter",
            seq=seq_label,
            K_sigma=int(K),
            n_vars=int(z0.size),
            rmse_warm_sol2=rmse_warm,
            d_warm=float(d0),
            phase1_maxfun=int(_mxf1),
            phase2_maxfun=int(_mxf2),
            phase3_maxfun=int(_mxf3),
        )

        log.debug(
            "PIPELINE [%s] %s L-BFGS-B - phase 1/2 | %d variables | RMSE warm (SOL2)~%.6f | phase1 maxfun=%d",
            seq_label,
            stage_name,
            int(z0.size),
            float(rmse_warm),
            int(_mxf1),
        )

        progress_cb(0, f"{stage_name}: L-BFGS-B {int(z0.size)} vars (descent)...")

    else:
        _log_spline_pipeline_json(
            log,
            "sol3b_minimize_enter",
            seq=seq_label,
            K_sigma_L=int(K),
            n_vars=int(z0.size),
            rmse_warm_before=float(rmse_warm),
            phase1_maxfun=int(_mxf1),
            phase2_maxfun=int(_mxf2),
        )

        log.debug(
            "PIPELINE [%s] %s - phase 1/2 | %d vars | RMSE entry=%.6f | phase1 maxfun=%d",
            seq_label,
            stage_name,
            int(z0.size),
            float(rmse_warm),
            int(_mxf1),
        )

        progress_cb(0, f"{stage_name}: ln k spline + free sigma_L (descent)...")

    _reset_obj_tracker(z0)

    r1 = _run_lbfgsb_phase_with_progress(z0, opt_p1, 0)

    z1 = np.asarray(_best_z[0], dtype=np.float64).ravel().copy()

    mse_1_spec = float(_spectral_mse_sol3(z1))

    _x1_ret = np.asarray(getattr(r1, "x", z1), dtype=np.float64).ravel()

    _mse1_ret_spec = float(_spectral_mse_sol3(_x1_ret))

    if _mse1_ret_spec > mse_1_spec + 1e-12 * max(1.0, abs(mse_1_spec)):
        log.info(
            "PIPELINE [%s] %s phase 1: last L-BFGS-B iterate worse (spectral MSE) than best seen; "
            "on garde le meilleur (%.6e -> %.6e).",
            seq_label,
            stage_name,
            _mse1_ret_spec,
            mse_1_spec,
        )

    rmse_1 = float(np.sqrt(max(mse_1_spec, 0.0)))

    if optimize_n:
        _log_spline_pipeline_json(
            log,
            "sol3_minimize_phase1_done",
            seq=seq_label,
            success=bool(getattr(r1, "success", False)),
            message=str(getattr(r1, "message", ""))[:160],
            nit=int(getattr(r1, "nit", 0) or 0),
            nfev=int(getattr(r1, "nfev", 0) or 0),
            status=int(getattr(r1, "status", -1)),
            rmse=float(rmse_1),
        )

        log.info(
            "PIPELINE [%s] %s phase 1 done | success=%s nit=%d | RMSE~%.6f | %s",
            seq_label,
            stage_name,
            getattr(r1, "success", False),
            int(getattr(r1, "nit", 0) or 0),
            rmse_1,
            str(getattr(r1, "message", ""))[:80],
        )

        _m1 = str(getattr(r1, "message", "")).upper()

        if optimize_n and "EXCEEDS" in _m1 and "LIMIT" in _m1:
            log.info(
                "PIPELINE [%s] %s phase 1 hint: L-BFGS-B budget hit (maxfun=%d). "
                "Increase sol3_phase1_maxfun (INDEX-SPLINE advanced panel) or SplineOptConfig.sol3_phase1_maxfun.",
                seq_label,
                stage_name,
                int(opt_p1.get("maxfun", 0) or 0),
            )

        progress_cb(_phase_progress_bounds(1)[0], f"{stage_name}: polish {int(z0.size)} vars...")

    else:
        _log_spline_pipeline_json(
            log,
            "sol3b_minimize_phase1_done",
            seq=seq_label,
            success=bool(getattr(r1, "success", False)),
            message=str(getattr(r1, "message", ""))[:160],
            nit=int(getattr(r1, "nit", 0) or 0),
            nfev=int(getattr(r1, "nfev", 0) or 0),
            rmse=float(rmse_1),
        )

        log.info(
            "PIPELINE [%s] %s phase 1 | success=%s nit=%d | RMSE~%.6f",
            seq_label,
            stage_name,
            getattr(r1, "success", False),
            int(getattr(r1, "nit", 0) or 0),
            rmse_1,
        )

        progress_cb(_phase_progress_bounds(1)[0], f"{stage_name}: ln k spline + free sigma_L (polish)...")

    _reset_obj_tracker(z1)

    r2 = _run_lbfgsb_phase_with_progress(z1, opt_p2, 1)

    zf = np.asarray(_best_z[0], dtype=np.float64).ravel().copy()

    mse_f_spec = float(_spectral_mse_sol3(zf))

    _x2_ret = np.asarray(getattr(r2, "x", zf), dtype=np.float64).ravel()

    _mse2_ret_spec = float(_spectral_mse_sol3(_x2_ret))

    if _mse2_ret_spec > mse_f_spec + 1e-12 * max(1.0, abs(mse_f_spec)):
        log.info(
            "PIPELINE [%s] %s phase 2: last L-BFGS-B iterate worse (spectral MSE) than best seen; "
            "on garde le meilleur (%.6e -> %.6e).",
            seq_label,
            stage_name,
            _mse2_ret_spec,
            mse_f_spec,
        )

    if optimize_n:
        progress_cb(_phase_progress_bounds(2)[0], f"{stage_name}: ultra-fine polish {int(z0.size)} vars...")

        _reset_obj_tracker(zf)

        r3 = _run_lbfgsb_phase_with_progress(zf, opt_p3, 2)

        z3 = np.asarray(_best_z[0], dtype=np.float64).ravel().copy()

        mse_3_spec = float(_spectral_mse_sol3(z3))

        _x3_ret = np.asarray(getattr(r3, "x", z3), dtype=np.float64).ravel()

        _mse3_ret_spec = float(_spectral_mse_sol3(_x3_ret))

        if _mse3_ret_spec > mse_3_spec + 1e-12 * max(1.0, abs(mse_3_spec)):
            log.info(
                "PIPELINE [%s] %s phase 3: last L-BFGS-B iterate worse (spectral MSE) than best seen; "
                "on garde le meilleur (%.6e -> %.6e).",
                seq_label,
                stage_name,
                _mse3_ret_spec,
                mse_3_spec,
            )

        if mse_3_spec < mse_f_spec - 1e-18:
            zf = z3

            mse_f_spec = float(mse_3_spec)

        rmse_3 = float(np.sqrt(max(mse_3_spec, 0.0)))

        _log_spline_pipeline_json(
            log,
            "sol3_minimize_phase3_done",
            seq=seq_label,
            success=bool(getattr(r3, "success", False)),
            message=str(getattr(r3, "message", ""))[:160],
            nit=int(getattr(r3, "nit", 0) or 0),
            nfev=int(getattr(r3, "nfev", 0) or 0),
            status=int(getattr(r3, "status", -1)),
            rmse=float(rmse_3),
            delta_rmse_vs_phase2=float(rmse_3 - float(np.sqrt(max(float(_spectral_mse_sol3(_x2_ret)), 0.0)))),
            delta_rmse_vs_warm=float(rmse_3 - rmse_warm),
        )

        log.info(
            "PIPELINE [%s] %s phase 3 (ultra-fine) | success=%s nit=%d | RMSE~%.6f",
            seq_label,
            stage_name,
            getattr(r3, "success", False),
            int(getattr(r3, "nit", 0) or 0),
            rmse_3,
        )

    if optimize_n:
        d_f, skn_f, skL_f, nn_f, LL_f = _unpack(zf)

        skn_ff = np.asarray(skn_f, dtype=np.float64).ravel()

        skL_ff = np.asarray(skL_f, dtype=np.float64).ravel()

        nn_ff = np.asarray(nn_f, dtype=np.float64).ravel()

        LL_ff = np.asarray(LL_f, dtype=np.float64).ravel()

        sk_rf, nn_rf, LL_rf = _snap_nk_mesh_sol3_split(skn_ff, skL_ff, nn_ff, LL_ff)

        xi_ff = physical_nodes_to_x_slice_n(nn_rf, sk_rf, cfg.n_mono_band_nm)

        x_f = np.concatenate((np.asarray([float(d_f)], dtype=np.float64), xi_ff.ravel(), LL_rf.ravel()))

        n_lf, k_lf = nk_from_x_pwlnk(
            x_f,
            lam,
            sk_rf,
            lo_k,
            hi_k,
            sig_pre=sig,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=_nk_prof_sol3,
        )

        d_f = float(x_f[0])

        if min_dlam_ratio_req > 0.0 and np.isfinite(lam_lo) and np.isfinite(lam_hi) and lam_hi > lam_lo:
            _rf_n = float(min_relative_lambda_spacing_ratio(skn_f, lam_lo, lam_hi))

            _rf_L = float(min_relative_lambda_spacing_ratio(skL_f, lam_lo, lam_hi))

            log.info(
                "PIPELINE [%s] %s | fin: min(Deltaλ)/λ_mean  sigma_n=%.6f  sigma_L=%.6f  (départ SOL2: %.6f / %.6f ; cfg=%.6f)",
                seq_label,
                stage_name,
                _rf_n,
                _rf_L,
                float(min_relative_lambda_spacing_ratio(skn_spacing_ref, lam_lo, lam_hi)),
                float(min_relative_lambda_spacing_ratio(skL_spacing_ref, lam_lo, lam_hi)),
                min_dlam_ratio_req,
            )

        mse_report = float(mse_f_spec)

        rmse_f = float(np.sqrt(max(mse_report, 0.0)))

        _log_spline_pipeline_json(
            log,
            "sol3_minimize_phase2_done",
            seq=seq_label,
            success=bool(getattr(r2, "success", False)),
            message=str(getattr(r2, "message", ""))[:160],
            nit=int(getattr(r2, "nit", 0) or 0),
            nfev=int(getattr(r2, "nfev", 0) or 0),
            status=int(getattr(r2, "status", -1)),
            rmse=float(rmse_f),
            rmse_after_phase1=float(rmse_1),
            delta_rmse_phases=float(rmse_f - rmse_1),
            delta_rmse_vs_warm=float(rmse_f - rmse_warm),
        )

        log.info(
            "PIPELINE [%s] %s phase 2 (polish) | success=%s nit=%d | RMSE %.6f -> %.6f (vs warm Delta=%+.6f)",
            seq_label,
            stage_name,
            getattr(r2, "success", False),
            int(getattr(r2, "nit", 0) or 0),
            rmse_1,
            rmse_f,
            float(rmse_f - rmse_warm),
        )

    else:
        d_f, skL_f, LL_f = _unpack(zf)

        if min_dlam_ratio_req > 0.0 and np.isfinite(lam_lo) and np.isfinite(lam_hi) and lam_hi > lam_lo:
            _rf_L_end = float(min_relative_lambda_spacing_ratio(skL_f, lam_lo, lam_hi))

            log.info(
                "PIPELINE [%s] %s | fin: min(Deltaλ)/λ_mean (sigma_L)=%.6f (départ SOL2: %.6f ; cfg=%.6f)",
                seq_label,
                stage_name,
                _rf_L_end,
                float(min_relative_lambda_spacing_ratio(skL_spacing_ref, lam_lo, lam_hi)),
                min_dlam_ratio_req,
            )

        rmse_fb = float(np.sqrt(max(mse_f_spec, 0.0)))

        _log_spline_pipeline_json(
            log,
            "sol3b_minimize_phase2_done",
            seq=seq_label,
            success=bool(getattr(r2, "success", False)),
            message=str(getattr(r2, "message", ""))[:160],
            nit=int(getattr(r2, "nit", 0) or 0),
            nfev=int(getattr(r2, "nfev", 0) or 0),
            rmse=float(rmse_fb),
            rmse_after_phase1=float(rmse_1),
            delta_rmse_vs_warm=float(rmse_fb - rmse_warm),
        )

        log.info(
            "PIPELINE [%s] %s phase 2 | RMSE %.6f -> %.6f (vs entry Delta=%+.6f)",
            seq_label,
            stage_name,
            rmse_1,
            rmse_fb,
            float(rmse_fb - rmse_warm),
        )

        skL_fb = np.asarray(skL_f, dtype=np.float64).ravel()

        LL_fb = np.asarray(LL_f, dtype=np.float64).ravel()

        sk_rfb, n_at_f, LL_rfb = _snap_nk_mesh_sol3b(skL_fb, LL_fb)

        xi_fb = physical_nodes_to_x_slice_n(n_at_f, sk_rfb, cfg.n_mono_band_nm)

        x_fb = np.concatenate((np.asarray([float(d_f)], dtype=np.float64), xi_fb.ravel(), LL_rfb))

        n_lf, k_lf = nk_from_x_pwlnk(
            x_fb,
            lam,
            sk_rfb,
            lo_k,
            hi_k,
            sig_pre=sig,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=_nk_prof_sol3,
        )

        d_f = float(x_fb[0])

    progress_cb(100, f"{stage_name}: done.")

    t_th = (
        _ratio_theoretical_from_nk(lam, n_lf, k_lf, d_f, cfg.n_sub)
        if cfg.t_is_ratio
        else _transmittance_absolute_from_nk(lam, n_lf, k_lf, d_f, cfg.n_sub)
    )

    r_th = None

    if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and cfg.r_exp is not None:
        r_th = (
            _reflectance_ratio_theoretical_from_nk(lam, n_lf, k_lf, d_f, cfg.n_sub)
            if cfg.t_is_ratio
            else _reflectance_absolute_backside_from_nk(lam, n_lf, k_lf, d_f, cfg.n_sub)
        )

    if optimize_n:
        out = {
            "x": zf,
            "sigma_knots": 0.5 * (skn_f + skL_f),
            "sigma_knots_n": skn_f,
            "sigma_knots_L": skL_f,
            "n_seg": K - 1,
            "lam_nm": lam,
            "n_lam": n_lf,
            "k_lam": k_lf,
            "d_nm": d_f,
            "mse": mse_report,
            "rmse": float(np.sqrt(max(mse_report, 0.0))),
            "t_theo": t_th,
            "r_theo": r_th,
            "nfev_pglobal": 0,
            "nit_polish": int(getattr(r2, "nit", 0)),
            "x_encoding": "split_sigma_free_knots",
            "n_nodes_physical": nn_f,
            "L_nodes": LL_f,
        }

    else:
        out = {
            "x": zf,
            "sigma_knots": 0.5 * (skn0 + skL_f) if skn0.size == skL_f.size else skL_f.copy(),
            "sigma_knots_n": skn0.copy(),
            "sigma_knots_L": skL_f.copy(),
            "n_seg": max(1, int(skL_f.size) - 1),
            "lam_nm": lam,
            "n_lam": n_lf,
            "k_lam": k_lf,
            "d_nm": d_f,
            "mse": float(mse_f_spec),
            "rmse": float(np.sqrt(max(float(mse_f_spec), 0.0))),
            "t_theo": t_th,
            "r_theo": r_th,
            "nfev_pglobal": 0,
            "nit_polish": int(getattr(r2, "nit", 0)),
            "x_encoding": "lnk_spline_free_knots",
            "n_nodes_physical": nn0.copy(),
            "L_nodes": LL_f.copy(),
        }

    if apply_result_finalize:
        out = snapshot_result_with_rmse_fit_meta(cfg, out)

        if live_cb is not None:
            live_cb(out)

    return out

def worker_auto_best_split_knot_refinement(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    progress_cb,
    live_cb=None,
) -> dict | None:
    """Auto-Best pass 2: same stage as SOL3 (free sigma_n/sigma_L), logged sequence ``AB2``."""

    out = _run_free_knot_stage(
        cfg,
        base_result,
        stop_event,
        progress_cb,
        None,
        optimize_n=True,
        seq_label="AB2",
        stage_name="Auto-Best split-knot",
        apply_result_finalize=False,
    )

    if out is None:
        return None

    out["stage_repli_local"] = False

    out["pglobal_trust_rho"] = None

    out["adaptive_mesh"] = False

    out["split_knots_refine"] = True

    out = snapshot_result_with_rmse_fit_meta(cfg, out)

    if live_cb is not None:
        live_cb(out)

    return out


def _run_single_spline_stage(
    cfg: SplineOptConfig,
    stop_event: Event,
    progress_cb,
    live_cb=None,
    *,
    progress_k_ref: list | None = None,
    pipeline_seq: str = "spline_stage",
    fatal_finish: Callable[[str], None] | None = None,
) -> tuple[dict | None, object | None]:
    """One local L-BFGS-B stage. progress_cb(pc:int, msg:str). live_cb(dict) optional.

    If ``progress_k_ref`` is a one-int list, it is updated with real K_sigma after

    ``make_bounds_and_x0`` (e.g. Smart Init -> 10 knots) for progress messages.

    sigma knot abscissas are fixed for this stage (``sigma_knots_override``); only

    ``d``, ``n_j`` and ``L_j`` are optimized until the next adaptive insertion.

    If ``stage_mandatory_local_maxfun`` > 0: mandatory L-BFGS-B on full bounds from

    the seed, then polish ``polish_maxfun`` on full physical bounds.

    """

    try:
        bounds_full, x0, sigma_knots = make_bounds_and_x0(cfg)

    except SmartInitPreviewCancelled:
        if fatal_finish is not None:
            fatal_finish("Stop  Smart Init preview cancelled")

        else:
            progress_cb(100, "Stop  Smart Init preview cancelled")

        return None, None

    # --- FACTUAL ANALYSIS SOL 1 (MANUAL) vs SOL 2 (WORKER) ---

    is_manual = False

    manual_rmse = 0.0

    lgr = logging.getLogger("CERTUS")

    if getattr(cfg, "smart_init_manual_force_restart", False):
        is_manual = True

        manual_rmse = float(getattr(cfg, "smart_preview_accepted_rmse", 0.0) or 0.0)

        # NE PAS re-appeler make_bounds_and_x0 : les attrs dynamiques ont deja ete

        # consommes par le 1er appel (ligne 2514). bounds_full, x0, sigma_knots

        # contiennent deja les values manualles correctes.

        cfg.smart_init_manual_force_restart = False

        lgr.info("=" * 60)

        lgr.info("FACTUAL - SOL 1: VALEURS ISSUES DU DIALOGUE MANUEL")

        lgr.info(
            " -> RMSE mémorisée (maillage worker, même métrique que SOL2 ci-dessous) = %.8f",
            manual_rmse,
        )

        lgr.info(
            " -> Si la fenêtre Smart Init affichait mieux: c'était l'aperçu ; les logs utilisent la valeur ci-dessus.",
        )

        lgr.info(
            " -> Regrille K_dialog → K_worker: voir ``INDEX_SPLINE_smart_init_Ksrc_to_worker_mesh`` (snap / interp / extrap)."
        )

        lgr.info(" -> d (x0 avant clip) = %.6f nm", float(x0[0]))

        lgr.info(
            " -> sigma_knots (nm⁻¹) K=%d : %s",
            int(sigma_knots.size),
            np.array2string(np.asarray(sigma_knots, dtype=np.float64), precision=6, max_line_width=200),
        )

        k_nodes = int(sigma_knots.size)

        n_pre = x_slice_n_to_physical_nodes(x0[1 : 1 + k_nodes], sigma_knots, cfg.n_mono_band_nm)

        L_pre = np.asarray(x0[1 + k_nodes : 1 + 2 * k_nodes], dtype=np.float64).ravel()

        for ii in range(k_nodes):
            sig_ii = float(sigma_knots[ii])

            lam_ii = 1.0 / max(sig_ii, 1e-30)

            lgr.info(
                " -> Node %2d/%2d  sigma=%.6e nm⁻¹  lambda=%10.4f nm  n=%.6f  ln k=%.6f",
                ii + 1,
                k_nodes,
                sig_ii,
                lam_ii,
                float(n_pre[ii]),
                float(L_pre[ii]),
            )

        lgr.info("-" * 60)

    obj = SplinePWLObjective(cfg, sigma_knots)

    x0_pre_clip = np.asarray(x0, dtype=np.float64).ravel().copy()

    x0_init = clip_to_bounds(x0_pre_clip.copy(), bounds_full[:, 0], bounds_full[:, 1])

    delta_clip = np.abs(x0_init - x0_pre_clip)

    if np.any(delta_clip > 1e-15):
        hit = np.where(delta_clip > 1e-15)[0]

        lgr.info(
            "INDEX_SPLINE [x0 clip] %d component(s) changed by bounds clip (max |Delta|=%.6e): %s",
            int(hit.size),
            float(np.max(delta_clip)),
            np.array2string(hit, max_line_width=120),
        )

        for j in hit[: min(12, hit.size)]:
            ji = int(j)

            lgr.info(
                "   [clip] i=%d  before=%.8e  after=%.8e  bounds=[%.8e, %.8e]",
                ji,
                float(x0_pre_clip[ji]),
                float(x0_init[ji]),
                float(bounds_full[ji, 0]),
                float(bounds_full[ji, 1]),
            )

        if hit.size > 12:
            lgr.info("   [clip] … (%d more indices)", int(hit.size - 12))

    mse_init = float(obj(x0_init))

    worker_rmse = float(np.sqrt(max(mse_init, 0.0)))

    factuel_mse_sp: float | None = None

    factuel_pen: float | None = None

    factuel_tot: float | None = None

    factuel_n_pix: int | None = None

    factuel_rmse_pwl_contrast: float | None = None

    if is_manual:
        try:
            factuel_n_pix = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

        except (TypeError, ValueError, AttributeError, KeyError):
            lgr.debug("_spline_objective_lam_mask failed in FACTUAL", exc_info=True)

            factuel_n_pix = -1

        msp_d, pen_d, tot_d = decompose_spline_pwl_objective(cfg, sigma_knots, x0_init)

        factuel_mse_sp, factuel_pen, factuel_tot = float(msp_d), float(pen_d), float(tot_d)

        if not np.isfinite(tot_d) or abs(float(tot_d) - float(mse_init)) > max(1e-9, 1e-9 * abs(float(mse_init))):
            lgr.warning(
                "FACTUAL - decompose vs obj mismatch: total_decompose=%.6e vs mse_obj=%.6e",
                float(tot_d),
                float(mse_init),
            )

        nk_mode = str(getattr(cfg, "nk_profile_interp", "smooth") or "smooth").strip().lower()

        lgr.info("FACTUAL - SOL 2: RECALCUL IMMÉDIAT CÔTÉ WORKER (objectif spline)")

        lgr.info(
            " -> Objective context: nk_profile_interp=%s | lambda pixels (MSE mask)=%s | wT=%.4g wR=%.4g | "
            "t_is_ratio=%s | rmse_fit_lambda_nm=%s | n_mono_band_nm=%s",
            nk_mode,
            str(factuel_n_pix),
            float(getattr(cfg, "weight_t", 0.0)),
            float(getattr(cfg, "weight_r", 0.0)),
            str(bool(getattr(cfg, "t_is_ratio", False))),
            str(getattr(cfg, "rmse_fit_lambda_nm", None)),
            str(getattr(cfg, "n_mono_band_nm", None)),
        )

        lgr.info(
            " -> √MSE decomposition (same clipped x0): MSE_spectral=%.6e | penalties=%.6e | total=%.6e",
            factuel_mse_sp,
            factuel_pen,
            factuel_tot,
        )

        lgr.info(
            " -> Dialog RMSE (stored): √MSE_decl=%.8f | MSE_decl=%.6e vs worker total=%.6e (Delta=%.6e)",
            float(manual_rmse),
            float(manual_rmse) ** 2,
            factuel_tot,
            float(factuel_tot) - float(manual_rmse) ** 2,
        )

        lgr.info(" -> RMSE recomputed (worker, SplinePWLObjective on clipped x0) = %.8f", worker_rmse)

        k_nodes = int(sigma_knots.size)

        n_inj = x_slice_n_to_physical_nodes(x0_init[1 : 1 + k_nodes], sigma_knots, cfg.n_mono_band_nm)

        L_inj = np.asarray(x0_init[1 + k_nodes : 1 + 2 * k_nodes], dtype=np.float64).ravel()

        if abs(float(x0_pre_clip[0]) - float(x0_init[0])) > 1e-9:
            lgr.info(
                " -> Note: d before clip=%.6f nm -> after clip=%.6f nm",
                float(x0_pre_clip[0]),
                float(x0_init[0]),
            )

        try:
            _mr, rmse_like_dialog = rmse_at_spline_stage_x0_init(
                cfg,
                sigma_knots,
                n_inj,
                L_inj,
                float(x0_init[0]),
                relax_n_mono=True,
            )

            _ms, rmse_strict_mono = rmse_at_spline_stage_x0_init(
                cfg,
                sigma_knots,
                n_inj,
                L_inj,
                float(x0_init[0]),
                relax_n_mono=False,
            )

            lgr.info(
                " -> RMSE same (n,L,d) as post-clip, recomputed **like preview** (relax_n_mono=True) = %.8f",
                float(rmse_like_dialog),
            )

            lgr.info(
                " -> RMSE same (n,L,d), **strict worker** objective (relax_n_mono=False / ξ mono) = %.8f",
                float(rmse_strict_mono),
            )

            if cfg.n_mono_band_nm is not None and abs(rmse_like_dialog - rmse_strict_mono) > 1e-6:
                lgr.warning(
                    " => Preview vs strict gap: dialog may show RMSE without penalties / mono "
                    "parametrization identical to worker (see rmse_at_spline_stage_x0_init + cfg n_mono_band_nm)."
                )

        except (TypeError, ValueError, AttributeError, RuntimeError) as exc:
            lgr.warning("FACTUAL: rmse_at_spline_stage_x0_init recompute failed: %s", exc)

        abs_rmse_diff = float(abs(worker_rmse - manual_rmse))

        diff_rel = 100.0 * abs_rmse_diff / max(manual_rmse, 1e-9)

        # Warning threshold: >1% rel. (old 0.1% fired on clip/float noise alone, e.g. 0.04 vs 0.0413).

        if diff_rel > 1.0:
            lgr.warning("!!! SIGNIFICANT GAP (worker vs dialog declared RMSE): %.1f%%", diff_rel)

            lgr.warning(
                " => Leads: dialog vs canonical K sigma (regrid); x0 clip; rmse_fit_lambda_nm; wT/wR; "
                "t_is_ratio; stale stored RMSE (config/spectrum changed between Keep and SOL2); relax_n_mono preview."
            )

        elif diff_rel > 0.25 or abs_rmse_diff > 2e-4:
            lgr.info(
                "  Residual dialog vs first worker cost: %.2f%% rel. (|Delta|=%.2e) - typ. x0 clip or rounding.",
                diff_rel,
                abs_rmse_diff,
            )

        else:
            lgr.info("  SOLUTION VALIDATED: dialog and worker in close agreement.")

        lgr.info(
            "FACTUAL - La ligne suivante ``INDEX_SPLINE stage ... RMSE start`` doit coïncider avec le RMSE SOL2 ici (± bruit clip)."
        )

        lgr.info("=" * 60)

    if progress_k_ref is not None:
        if len(progress_k_ref) < 1:
            progress_k_ref.append(int(np.asarray(sigma_knots).size))

        else:
            progress_k_ref[0] = int(np.asarray(sigma_knots).size)

    dim = int(bounds_full.shape[0])

    local_only = True

    bounds_pg = bounds_full

    trust_rho_val: float | None = None

    if (not local_only) and cfg.pglobal_trust_region_by_k:
        bounds_pg, trust_rho_val = _pglobal_bounds_trust_region(
            bounds_full,
            x0,
            int(sigma_knots.size),
            int(cfg.pglobal_trust_k_lo),
            int(cfg.pglobal_trust_k_hi),
            float(cfg.pglobal_trust_rho_lo),
            float(cfg.pglobal_trust_rho_hi),
            sigma_knots,
        )

        logging.getLogger("CERTUS").info(
            "INDEX_SPLINE PGlobal trust region K_sigma=%s =%.4g (polish -> full bounds)",
            int(sigma_knots.size),
            trust_rho_val,
        )

    smlf = int(max(0, int(getattr(cfg, "stage_mandatory_local_maxfun", 0) or 0)))

    n_loc_pre = 0

    x_local = x0_init.copy()

    mse_local = float(obj(x_local))

    lgr = logging.getLogger("CERTUS")

    rmse_depart_local = float(np.sqrt(max(mse_local, 0.0)))

    lgr.info(
        "INDEX_SPLINE stage K_sigma=%s: RMSE départ (x0 après clip, avant local obligatoire) = %.6f  "
        "| = √total FACTUAL SOL2 si Smart Init manuel vient d'être appliqué",
        int(sigma_knots.size),
        rmse_depart_local,
    )

    _log_spline_pipeline_json(
        lgr,
        "stage_enter",
        seq=pipeline_seq,
        K_sigma=int(sigma_knots.size),
        dim=int(dim),
        spline_local_only=bool(local_only),
        stage_mandatory_local_maxfun=int(smlf),
        polish_maxfun=int(cfg.polish_maxfun),
        rmse_depart_after_clip_x0=rmse_depart_local,
        d_x0=float(x0_init[0]),
        smart_init_manual=bool(is_manual),
        manual_rmse_dialog=float(manual_rmse) if is_manual else None,
        worker_rmse_recalc=float(worker_rmse) if is_manual else None,
        nk_profile_interp=str(getattr(cfg, "nk_profile_interp", "smooth")),
        factuel_mse_spectral=factuel_mse_sp,
        factuel_penalties=factuel_pen,
        factuel_n_pix_lambda=factuel_n_pix,
        factuel_rmse_pwl_contrast=factuel_rmse_pwl_contrast,
    )

    lgr.info(
        "PIPELINE [%s] Stage entry | K_sigma=%d dim=%d local_only=%s smlf=%d -> RMSE start=%.6f",
        pipeline_seq,
        int(sigma_knots.size),
        int(dim),
        local_only,
        int(smlf),
        rmse_depart_local,
    )

    if smlf > 0:
        if stop_event.is_set():
            return None, None

        progress_cb(5, f"Mandatory local descent (maxfun={smlf})...")

        x_local, mse_local, n_loc_pre = _polish_lbfgsb_chunked(
            obj,
            x0_init,
            bounds_full,
            smlf,
            stop_event,
            progress_cb=progress_cb,
            live_cb=live_cb,
            sigma_knots=sigma_knots,
            progress_lo=5,
            progress_hi=15,
        )

        if stop_event.is_set():
            return None, None

        rmse_after_mand = float(np.sqrt(max(mse_local, 0.0)))

        _log_spline_pipeline_json(
            lgr,
            "stage_mandatory_local_done",
            seq=pipeline_seq,
            rmse_before=float(rmse_depart_local),
            rmse_after=rmse_after_mand,
            nfev_local=int(n_loc_pre),
            delta_rmse=float(rmse_after_mand - rmse_depart_local),
        )

        lgr.info(
            "PIPELINE [%s] Mandatory local descent done | RMSE %.6f -> %.6f (nfev~%d)",
            pipeline_seq,
            rmse_depart_local,
            rmse_after_mand,
            int(n_loc_pre),
        )

    if local_only:
        lgr.info(
            "INDEX_SPLINE step K_sigma=%s: local-only optimization | This run stays in local L-BFGS-B mode from the current seed.",
            int(sigma_knots.size),
        )

        if stop_event.is_set():
            return None, None

        progress_cb(2, "L-BFGS-B uniquement (polish)...")

        x_best, final_mse, nitp = _polish_lbfgsb_chunked(
            obj,
            x_local,
            bounds_full,
            int(cfg.polish_maxfun),
            stop_event,
            progress_cb=progress_cb,
            live_cb=live_cb,
            sigma_knots=sigma_knots,
            progress_lo=5,
            progress_hi=100,
        )

        nit_combined = int(n_loc_pre + nitp)

        rmse_fin_loc = float(np.sqrt(max(final_mse, 0.0)))

        rmse_in_polish = float(np.sqrt(max(mse_local, 0.0)))

        _log_spline_pipeline_json(
            lgr,
            "stage_local_only_complete",
            seq=pipeline_seq,
            rmse_after_mandatory_local=rmse_in_polish,
            rmse_after_polish_only=rmse_fin_loc,
            nfev_lbfgsb=int(nitp),
            nit_combined=int(nit_combined),
            pglobal_skipped=True,
        )

        lgr.info(
            "PIPELINE [%s] Stage local-only done | RMSE after polish=%.6f (nfev L-BFGS-B~%d)",
            pipeline_seq,
            rmse_fin_loc,
            int(nitp),
        )

        out = _pack_spline_stage_result(
            cfg,
            sigma_knots,
            x_best,
            final_mse,
            0,
            nit_combined,
            stage_repli_local=False,
            pglobal_trust_rho=None,
        )

        return out, None

    rmse_before_pg = float(np.sqrt(max(mse_local, 0.0)))

    lgr.info(
        "INDEX_SPLINE stage K_sigma=%s: RMSE au départ PGlobal (après local obligatoire) = %.6f  "
        "| même métrique objectif que FACTUAL SOL2",
        int(sigma_knots.size),
        rmse_before_pg,
    )

    progress_cb(15, "PGlobal: start...")

    lgr.info(
        "INDEX_SPLINE PGlobal ACTIVE | seq=%s | K_sigma=%d | dim=%d | trust_region_by_k=%s | rho=%s",
        str(pipeline_seq),
        int(sigma_knots.size),
        int(dim),
        bool(cfg.pglobal_trust_region_by_k),
        (f"{float(trust_rho_val):.4g}" if trust_rho_val is not None else "n/a_full_bounds"),
    )

    pg_conf = PGlobalConfig.for_dimension(dim).with_overrides(
        max_feval=max(50000, 4000 * dim),
        max_time=600.0,
    )

    if cfg.pglobal_max_feval is not None:
        mfe = int(cfg.pglobal_max_feval)

        # mfe = max(mfe, 6000 * dim)  # Suppression de cette contrainte qui ralentissait l'adaptatif

        pg_conf = pg_conf.with_overrides(max_feval=mfe)

        # PGLOBAL ~ triple la taille du 1er batch ; eviter de depasser max_feval des literation 0

        cap_spi = max(32, mfe // 8)

        if cap_spi < pg_conf.n_samples_per_iter:
            pg_conf = pg_conf.with_overrides(n_samples_per_iter=cap_spi)

        # reduire les recherches locales si le budget global est serre

        if cfg.pglobal_local_search_budget is None:
            pg_conf = pg_conf.with_overrides(
                local_search_budget=min(int(pg_conf.local_search_budget), max(1000, mfe // 2))
            )

    if cfg.pglobal_max_time is not None:
        pg_conf = pg_conf.with_overrides(max_time=float(cfg.pglobal_max_time))

    if cfg.pglobal_local_search_budget is not None:
        # Respect explicit user/UI budget (avoid silently inflating eval counts).
        lsb = max(0, int(cfg.pglobal_local_search_budget))

        pg_conf = pg_conf.with_overrides(local_search_budget=lsb)
    pglobal_seed = getattr(cfg, "pglobal_random_seed", None)
    if pglobal_seed is not None:
        pg_conf = pg_conf.with_overrides(random_seed=int(pglobal_seed))

    # Wire analytic gradient into PGlobal's L-BFGS-B local searches
    # so each local search uses the direct Fortran setulb fast path (jac=True)
    # instead of finite-difference gradients (2N+1 → 1 eval per iteration).
    _pg_grad_func = None
    try:

        if spline_pwl_analytic_grad_supported(cfg):
            _gt = obj.analytic_gradient(x_local)
            if _gt is not None and np.all(np.isfinite(_gt)):
                _pg_grad_func = obj.analytic_gradient
    except NUMERICAL_FAULT_EXCEPTIONS:
        logging.getLogger("CERTUS").debug("PGlobal gradient probe failed, using FD fallback", exc_info=True)

    optimizer = PGlobalOptimizer(
        objective=obj,
        bounds=bounds_pg,
        config=pg_conf,
        stop_event=stop_event,
        x0=x_local,
        gradient_func=_pg_grad_func,
    )

    _log_spline_pipeline_json(
        lgr,
        "stage_pglobal_start",
        seq=pipeline_seq,
        rmse_seed_for_pglobal=rmse_before_pg,
        pglobal_max_iter=int(cfg.pglobal_max_iter),
        max_feval=int(pg_conf.max_feval),
        max_time_s=float(pg_conf.max_time),
        n_samples_per_iter=int(pg_conf.n_samples_per_iter),
        local_search_budget=int(pg_conf.local_search_budget),
        pglobal_random_seed=(
            int(getattr(pg_conf, "random_seed")) if getattr(pg_conf, "random_seed", None) is not None else None
        ),
        dim_pglobal_bounds=int(bounds_pg.shape[0]),
        bounds_are_trust_region=bool(trust_rho_val is not None),
    )

    lgr.info(
        "PIPELINE [%s] PGlobal started | feval budget=%d time=%.0fs | RMSE seed=%.6f",
        pipeline_seq,
        int(pg_conf.max_feval),
        float(pg_conf.max_time),
        rmse_before_pg,
    )

    _live_throttle = [0.0]

    _LIVE_INTERVAL = 2.0

    import time as _time_mod

    # Track best RMSE for logging improvements

    best_rmse_ref = [float(np.sqrt(max(mse_local, 0.0)))]

    # GUI live_cb must show the **best-so-far** model (same contract as polish), not the last random

    # sample; otherwise INDEX_SPLINE _on_live_update can treat a bad sample as a "new record" when

    # _best_live_rmse was still inf (early live dicts skipped).

    best_mse_live_ref = [float(mse_local)]

    best_x_live_ref = [np.asarray(x_local, dtype=np.float64).ravel().copy()]

    _pg_snap_last_eval = [0]

    _pg_cb_count = [0]

    _pg_prog_last = [0.0]

    _PG_PROG_INTERVAL = 0.4

    def cb(s: Sample) -> None:

        _pg_cb_count[0] += 1

        _fe = max(1, int(pg_conf.max_feval))

        frac = min(1.0, float(optimizer.n_evals) / float(_fe))

        pc = 15.0 + 70.0 * frac

        rmse = float(np.sqrt(max(s.y, 0.0)))

        # Log improvement with parameters

        if rmse < best_rmse_ref[0] - 1e-12:
            best_rmse_ref[0] = rmse

            best_mse_live_ref[0] = float(s.y)

            best_x_live_ref[0] = np.asarray(s.x, dtype=np.float64).ravel().copy()

            xv = best_x_live_ref[0]

            with np.printoptions(precision=6, suppress=True):
                lgr.info(
                    "PGlobal IMPROVEMENT: evals=%d  RMSE=%.6f  x(d,n,L)=%s",
                    int(optimizer.n_evals),
                    rmse,
                    np.array2string(xv, separator=", "),
                )

        step_pg = max(1, int(pg_conf.max_feval) // 8)

        step_hit = False

        if optimizer.n_evals - _pg_snap_last_eval[0] >= step_pg:
            _pg_snap_last_eval[0] = int(optimizer.n_evals)

            step_hit = True

            _log_spline_pipeline_json(
                lgr,
                "pglobal_progress",
                seq=pipeline_seq,
                n_evals=int(optimizer.n_evals),
                best_rmse_so_far=float(best_rmse_ref[0]),
                last_sample_rmse=rmse,
            )

            lgr.info(
                "PIPELINE [%s] PGlobal … evals=%d | best RMSE=%.6f (current sample=%.6f)",
                pipeline_seq,
                int(optimizer.n_evals),
                float(best_rmse_ref[0]),
                rmse,
            )

        # GUI: éviter une file Qt saturée, tout en restant lisible (pas seulement 1er cb / pas d'éval).

        _now_prog = _time_mod.monotonic()

        _prog_time_hit = (_now_prog - _pg_prog_last[0]) >= _PG_PROG_INTERVAL

        _emit_prog = _pg_cb_count[0] == 1 or step_hit or _prog_time_hit

        if _emit_prog:
            _pg_prog_last[0] = _now_prog

            progress_cb(pc, f"PGlobal: evals={optimizer.n_evals}  RMSE={rmse:.6f}")

        if live_cb is not None:
            now = _time_mod.monotonic()

            if now - _live_throttle[0] >= _LIVE_INTERVAL:
                _live_throttle[0] = now

                try:
                    live_cb(
                        _build_live_dict(
                            cfg,
                            sigma_knots,
                            best_x_live_ref[0],
                            best_mse_live_ref[0],
                            int(optimizer.n_evals),
                        )
                    )

                except NUMERICAL_FAULT_EXCEPTIONS:
                    logging.getLogger("CERTUS").debug("live_cb failed in PGlobal callback", exc_info=True)

    best = optimizer.optimize(max_iter=int(cfg.pglobal_max_iter), callback=cb)

    if stop_event.is_set() and best is None:
        return None, None

    mse_pg_returned = float(best.y) if best is not None else float("nan")

    rmse_pg_returned = float(np.sqrt(max(mse_pg_returned, 0.0))) if np.isfinite(mse_pg_returned) else float("nan")

    # Prefer the best sample observed during callbacks over the optimizer return value.
    # Some optimizers return the last sampled point rather than the incumbent best.
    mse_pg_best_obs = float(best_mse_live_ref[0]) if np.isfinite(float(best_mse_live_ref[0])) else float(mse_local)

    x_pg_best_obs = np.asarray(best_x_live_ref[0], dtype=np.float64).ravel().copy()

    if best is not None and np.isfinite(mse_pg_returned) and mse_pg_returned < mse_pg_best_obs - 1e-15:
        mse_pg_best_obs = float(mse_pg_returned)

        x_pg_best_obs = np.asarray(best.x, dtype=np.float64).ravel().copy()

    rmse_pg_out = float(np.sqrt(max(mse_pg_best_obs, 0.0)))

    _log_spline_pipeline_json(
        lgr,
        "stage_pglobal_done",
        seq=pipeline_seq,
        n_evals_pglobal=int(optimizer.n_evals),
        rmse_before_pglobal=rmse_before_pg,
        rmse_best_pglobal=rmse_pg_out,
        pglobal_returned_sample=bool(best is not None),
        rmse_pglobal_returned_sample=float(rmse_pg_returned) if np.isfinite(rmse_pg_returned) else None,
        delta_rmse_pglobal=float(rmse_pg_out - rmse_before_pg),
        stop_event_set=bool(stop_event.is_set()),
    )

    lgr.info(
        "PIPELINE [%s] PGlobal finished | evals=%d | RMSE %.6f -> %.6f (Delta=%+.6f) | returned_sample=%s",
        pipeline_seq,
        int(optimizer.n_evals),
        rmse_before_pg,
        rmse_pg_out,
        float(rmse_pg_out - rmse_before_pg),
        f"{rmse_pg_returned:.6f}" if np.isfinite(rmse_pg_returned) else "n/a",
    )

    x_start = clip_to_bounds(np.asarray(x_pg_best_obs, dtype=np.float64).copy(), bounds_full[:, 0], bounds_full[:, 1])

    mse_polish_in = float(obj(x_start))

    rmse_polish_in = float(np.sqrt(max(mse_polish_in, 0.0)))

    if stop_event.is_set():
        progress_cb(85, "Stop requested: short polish then save best PGlobal...")

    else:
        progress_cb(85, "Polish L-BFGS-B...")

    x_best, final_mse, nitp = _polish_lbfgsb_chunked(
        obj,
        x_start,
        bounds_full,
        int(cfg.polish_maxfun),
        stop_event,
        progress_cb=progress_cb,
        live_cb=live_cb,
        sigma_knots=sigma_knots,
        progress_lo=85,
        progress_hi=100,
    )

    nit_combined = int(n_loc_pre + nitp)

    rmse_after_polish = float(np.sqrt(max(float(final_mse), 0.0)))

    _log_spline_pipeline_json(
        lgr,
        "stage_polish_done",
        seq=pipeline_seq,
        rmse_start_polish=rmse_polish_in,
        rmse_end_polish=rmse_after_polish,
        nfev_lbfgsb=int(nitp),
        delta_rmse_polish=float(rmse_after_polish - rmse_polish_in),
    )

    lgr.info(
        "PIPELINE [%s] Polish L-BFGS-B done | RMSE %.6f -> %.6f (nfev~%d)",
        pipeline_seq,
        rmse_polish_in,
        rmse_after_polish,
        int(nitp),
    )

    repli_local = False

    # Always guard against PGlobal+polish degradation relative to the pre-PGlobal seed/local state.
    tol_repli = max(1e-14, 1e-9 * max(1.0, abs(float(mse_local))))
    if float(final_mse) > float(mse_local) + float(tol_repli):
        lgr.info(
            "INDEX_SPLINE step: fallback to pre-PGlobal seed/local (MSE %.6e < PGlobal+polish %.6e); K continuation possible",
            mse_local,
            final_mse,
        )

        _log_spline_pipeline_json(
            lgr,
            "stage_repli_mandatory_local",
            seq=pipeline_seq,
            reason="PGlobal_plus_polish_worse_than_seed_or_local",
            mse_mandatory_local=float(mse_local),
            mse_after_pglobal_polish=float(final_mse),
            rmse_kept=float(np.sqrt(max(mse_local, 0.0))),
        )

        lgr.info(
            "PIPELINE [%s] FALLBACK to pre-PGlobal seed/local | RMSE kept=%.6f "
            "(PGlobal+polish worsened the objective - common cause: PGlobal budget too low "
            "or multimodal landscape).",
            pipeline_seq,
            float(np.sqrt(max(mse_local, 0.0))),
        )

        x_best = x_local.copy()

        final_mse = float(mse_local)

        nit_combined = int(n_loc_pre)

        repli_local = True

    rmse_final = float(np.sqrt(max(float(final_mse), 0.0)))

    _log_spline_pipeline_json(
        lgr,
        "stage_complete",
        seq=pipeline_seq,
        rmse_final=rmse_final,
        repli_local=bool(repli_local),
        n_evals_pglobal=int(optimizer.n_evals),
        nit_total=int(nit_combined),
    )

    lgr.info(
        "PIPELINE [%s] Stage done | RMSE final=%.6f | repli_local=%s",
        pipeline_seq,
        rmse_final,
        repli_local,
    )

    out = _pack_spline_stage_result(
        cfg,
        sigma_knots,
        x_best,
        final_mse,
        int(optimizer.n_evals),
        nit_combined,
        stage_repli_local=repli_local,
        pglobal_trust_rho=trust_rho_val,
    )

    return out, None
