from typing import *
import numpy as np
from scipy.optimize import minimize
from certus.core.certus_core import *
from certus.spline.certus_index_spline_core import *
from certus.spline.certus_corridor_utils import _robust_sigma_from_mad
from certus.spline.spline_objective import *
from certus.spline.certus_corridor_config import *
import logging
log = logging.getLogger('CERTUS')
_LOG_PREFIX = "INDEX_SPLINE [CORRIDOR FITTER]"

def _fit_local_quadratic_rmse_profile(
    d_s: np.ndarray,
    r_s: np.ndarray,
    i_anchor: int,
    half_window_pts: int,
    delta_rmse: float = 0.0,
) -> dict[str, Any]:

    d_arr = np.asarray(d_s, dtype=np.float64).ravel()

    r_arr = np.asarray(r_s, dtype=np.float64).ravel()

    out: dict[str, Any] = {
        "ok": False,
        "d_center": float("nan"),
        "d_lo": float("nan"),
        "d_hi": float("nan"),
        "slope_at_anchor": float("nan"),
        "curvature": float("nan"),
        "anchor_nm": float("nan"),
        "window_nm": (float("nan"), float("nan")),
        "coeffs": (float("nan"), float("nan"), float("nan")),
        "fit_error": float("nan"),
        "fit_error_tol": float("nan"),
        "n_fit_points": 0,
    }

    if d_arr.size < 5 or r_arr.size != d_arr.size:
        return out

    ia = int(i_anchor)

    if ia < 0 or ia >= int(d_arr.size):
        return out

    half_start = max(1, int(half_window_pts))
    half_max = max(half_start, int(max(1, d_arr.size // 2)))
    d_anchor = float(d_arr[ia])
    min_pts = 5
    # "Substantial but reasonable": wide relative tolerance + absolute safeguard.
    rel_tol = 0.20
    abs_tol = 4.0e-4

    best_candidate: dict[str, Any] | None = None
    best_half = -1
    best_err = float("inf")

    for half in range(half_start, half_max + 1):
        i0 = int(max(0, ia - half))
        i1 = int(min(d_arr.size, ia + half + 1))
        if i1 - i0 < min_pts:
            continue

        d_loc = np.asarray(d_arr[i0:i1], dtype=np.float64)
        r_loc = np.asarray(r_arr[i0:i1], dtype=np.float64)

        if r_loc.size >= 4:
            r_med = float(np.median(r_loc))
            r_mad = float(np.median(np.abs(r_loc - r_med)))
            mask = r_loc <= r_med + max(4.0 * r_mad, 1e-4)
            if np.sum(mask) >= min_pts:
                d_loc = d_loc[mask]
                r_loc = r_loc[mask]
        if d_loc.size < min_pts:
            continue

        x = d_loc - d_anchor
        try:
            c2, c1, c0 = np.polyfit(x, r_loc, 2)
        except NUMERICAL_FAULT_EXCEPTIONS:
            continue
        if (not np.isfinite(c2)) or (not np.isfinite(c1)) or (not np.isfinite(c0)) or c2 <= 0.0:
            continue

        d_center = float(d_anchor - c1 / (2.0 * c2))
        d_lo_win = float(np.min(d_loc))
        d_hi_win = float(np.max(d_loc))
        win_span = float(max(1e-9, d_hi_win - d_lo_win))
        step_ref = float(np.nanmedian(np.abs(np.diff(d_loc)))) if d_loc.size >= 2 else 0.0
        tol_center = float(max(1e-9, step_ref, 0.25 * win_span))
        if (not np.isfinite(d_center)) or d_center < d_lo_win - tol_center or d_center > d_hi_win + tol_center:
            continue

        r_fit = float(c2) * x * x + float(c1) * x + float(c0)
        resid = np.asarray(r_loc - r_fit, dtype=np.float64).ravel()
        sigma_rob = _robust_sigma_from_mad(resid)
        sigma_rms = float(np.sqrt(np.mean(np.square(resid)))) if resid.size else float("nan")
        fit_err = float(np.nanmax(np.asarray([sigma_rob, sigma_rms], dtype=np.float64)))
        r_ref = float(max(np.nanmedian(r_loc), 1e-12))
        err_tol = float(max(abs_tol, rel_tol * r_ref))
        if (not np.isfinite(fit_err)) or fit_err > err_tol:
            continue

        dd_raw = float(np.sqrt(max(float(delta_rmse), 0.0) / c2)) if np.isfinite(float(delta_rmse)) else float("nan")
        min_excursion = float(max(1e-6, 0.002 * abs(d_anchor)))
        max_excursion = float(win_span * 2.5)
        if np.isfinite(dd_raw):
            dd = float(np.clip(dd_raw, min_excursion, max_excursion))
        else:
            dd = min_excursion

        cand = {
            "ok": True,
            "d_center": d_center,
            "d_lo": float(d_center - dd),
            "d_hi": float(d_center + dd),
            "slope_at_anchor": float(c1),
            "curvature": float(c2),
            "anchor_nm": d_anchor,
            "window_nm": (d_lo_win, d_hi_win),
            "coeffs": (float(c2), float(c1), float(c0)),
            "fit_error": float(fit_err),
            "fit_error_tol": float(err_tol),
            "n_fit_points": int(d_loc.size),
        }

        # B6 FIX: Arbitrate between window width and fit quality.
        # Previously we strictly preferred the widest window, which could artificially flatten curvature.
        # Now we only prefer a wider window if its fit error is acceptable and comparable.
        is_better = False
        if best_candidate is None:
            is_better = True
        else:
            if fit_err < best_err * 0.5:
                is_better = True  # significantly better fit
            elif half > best_half and fit_err <= best_err * 1.5 and fit_err <= err_tol:
                is_better = True  # slightly worse fit but wider window, and acceptable
            elif half == best_half and fit_err < best_err:
                is_better = True

        if is_better:
            best_candidate = cand
            best_half = half
            best_err = fit_err

    if best_candidate is None:
        return out
    out.update(best_candidate)
    return out
def _fit_nodes_at_fixed_d(
    cfg: SplineOptConfig,
    sigma_knots: np.ndarray,
    d_target_nm: float,
    x_nodes_init: np.ndarray,
    bounds_nodes: np.ndarray,
    *,
    maxfun: int = 4000,
    keep_nominal_seed_if_refit_worse: bool = True,
    seed_keep_tol_rel: float = 0.0,
    seed_keep_tol_abs: float = 1e-5,
    pure_spectral: bool = False,
    # P0.1 FIX: LR mode objective coherence parameters
    use_lr: bool = False,
    sig_t: float = 1.0,
    sig_r: float = 1.0,
    sigma_t_f: np.ndarray | None = None,
    sigma_r_f: np.ndarray | None = None,
    masked_grid_cache: tuple | None = None,
    cfg_effective: SplineOptConfig | None = None,
    obj_stage_cache: SplinePWLObjective | None = None,
    bds_cache: list[tuple[float, float]] | None = None,
) -> dict[str, Any] | None:
    """Optimize (n_slice, L_slice) at fixed d and return a minimal snapshot.

    Returns None if the masked objective is empty or dimensions are inconsistent.

    """

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    k = int(sk.size)

    if k < 2:
        return None

    b = np.asarray(bounds_nodes, dtype=np.float64)

    x0 = np.asarray(x_nodes_init, dtype=np.float64).ravel().copy()

    if b.shape != (2 * k, 2) or x0.size != 2 * k:
        return None

    # Optionally receive a pre-built effective config/objective for multi-start reuse.
    if cfg_effective is not None:
        cfg = cfg_effective
    elif pure_spectral:
        # Pure-spectral mode: disable n_lambda_rising penalty and lnk regularization so L-BFGS-B
        # genuinely minimises spectral RMSE at the target d instead of fleeing the nominal solution.
        cfg = cfg.replace(spline_pure_spectral_objective=True)
        log.debug(
            "%s _fit_nodes_at_fixed_d d=%.5g nm: pure_spectral=True -> n_lambda_rising penalty disabled for refit.",
            _LOG_PREFIX,
            float(d_target_nm),
        )

    # Masked objective (same weights / RMSE window); if empty, cannot profile.

    obj_stage = obj_stage_cache if obj_stage_cache is not None else SplinePWLObjective(cfg, sk)

    # Build full x vector for obj(x): x = [d, n_slice..., L_slice...]

    def _pack(x_nodes: np.ndarray) -> np.ndarray:

        return np.concatenate((np.asarray([float(d_target_nm)], dtype=np.float64), x_nodes))

    x0 = clip_to_bounds(x0, b[:, 0], b[:, 1])

    # P0.1 FIX: Pre-compute masked grid for chi² if use_lr (avoid recomputing on each eval)
    _masked_grid_cache = masked_grid_cache
    if use_lr and _masked_grid_cache is None:
        from certus.spline.spline_objective import build_spline_objective_masked_grid

        _masked_grid_cache = build_spline_objective_masked_grid(cfg)

    def _mse_nodes(x_nodes: np.ndarray) -> float:

        x_full = _pack(x_nodes)

        mse0 = float(obj_stage(x_full))

        if not np.isfinite(mse0):
            return 1e30

        if bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            return float(mse0)

        # ln(k) regularization consistent with legacy free-knot B (spline_workers._run_free_knot_stage):

        # penalty on discrete curvature d2(L) at sigma knots.

        reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))

        if reg_w > 0.0:
            k_loc = int(sk.size)

            L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]

            if L_nodes.size >= 3:
                d2 = np.diff(L_nodes, n=2)

                mse0 = float(mse0) + reg_w * float(np.mean(d2 * d2))

        return float(mse0)

    # B7 FIX: cache last nk result from _chi2_nodes to avoid redundant recomputation.
    _chi2_nk_cache: dict[str, Any] = {}

    # P0.1 FIX: chi² objective for LR mode (optimizer matches boundary test)
    def _chi2_nodes(x_nodes: np.ndarray) -> float:
        """Compute chi² on masked grid for LR mode optimization."""
        if _masked_grid_cache is None:
            return 1e30
        lam_f, _sig_f, n_sub_f, w, _inv_npix, t_exp_f, r_exp_f = _masked_grid_cache
        lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
        x_full = _pack(x_nodes)
        n_lam, k_lam = nk_from_x_pwlnk(
            x_full,
            lam_full,
            sk,
            cfg.k_clip_lo,
            cfg.k_clip_hi,
            sig_pre=None,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=str(cfg.nk_profile_interp or "smooth"),
        )
        n_f = np.interp(lam_f, lam_full, np.asarray(n_lam, dtype=np.float64).ravel())
        k_f = np.interp(lam_f, lam_full, np.asarray(k_lam, dtype=np.float64).ravel())
        # B7 FIX: cache the last nk for post-minimize reuse
        _chi2_nk_cache["n_lam"] = np.asarray(n_lam, dtype=np.float64).ravel()
        _chi2_nk_cache["k_lam"] = np.asarray(k_lam, dtype=np.float64).ravel()

        from certus.utils.certus_index_utils import (
            _ratio_theoretical_from_nk,
            _reflectance_ratio_theoretical_from_nk,
            _transmittance_absolute_from_nk,
        )
        from certus.spline.certus_index_spline_core import _reflectance_absolute_backside_from_nk
        from certus.spline.spline_objective import DataType

        chi = 0.0
        d_nm = float(d_target_nm)
        if cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and float(cfg.weight_t) > 0:
            if cfg.t_is_ratio:
                t_th = _ratio_theoretical_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            else:
                t_th = _transmittance_absolute_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            e = np.asarray(t_exp_f, dtype=np.float64) - t_th
            if sigma_t_f is not None:
                st = np.asarray(sigma_t_f, dtype=np.float64).ravel()
                if st.size == e.size:
                    chi += float(cfg.weight_t) * float(np.dot(w, (e / st) ** 2))
            else:
                chi += float(cfg.weight_t) * float(np.dot(w, (e / float(sig_t)) ** 2))
        if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and float(cfg.weight_r) > 0:
            if cfg.t_is_ratio:
                r_th = _reflectance_ratio_theoretical_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            else:
                r_th = _reflectance_absolute_backside_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            e = np.asarray(r_exp_f, dtype=np.float64) - r_th
            if sigma_r_f is not None:
                sr = np.asarray(sigma_r_f, dtype=np.float64).ravel()
                if sr.size == e.size:
                    chi += float(cfg.weight_r) * float(np.dot(w, (e / sr) ** 2))
            else:
                chi += float(cfg.weight_r) * float(np.dot(w, (e / float(sig_r)) ** 2))

        # Add regularization if not pure spectral
        if not bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))
            if reg_w > 0.0:
                k_loc = int(sk.size)
                L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]
                if L_nodes.size >= 3:
                    d2 = np.diff(L_nodes, n=2)
                    chi += reg_w * float(np.mean(d2 * d2))

        return float(chi) if np.isfinite(chi) else 1e30

    # Select objective based on mode
    _obj_nodes = _chi2_nodes if use_lr else _mse_nodes

    m0 = float(_obj_nodes(x0))

    if not np.isfinite(m0) or m0 >= 1e29:
        return None

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    # Lazy seed RMSE evaluation: compute only when seed-gate triggers (refit worse than seed).
    # In the common case where the refit is better, this avoids a redundant nk_from_x_pwlnk +
    # spectral_mse_rmse_masked_from_nk call (~15-20% savings per corridor refit).
    _seed_cache: dict[str, Any] = {}

    def _eval_seed_rmse() -> tuple[float, np.ndarray, np.ndarray, float]:
        if "done" not in _seed_cache:
            x_full_seed = _pack(x0)
            n_s, k_s = nk_from_x_pwlnk(
                x_full_seed,
                lam_full,
                sk,
                cfg.k_clip_lo,
                cfg.k_clip_hi,
                sig_pre=None,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=str(cfg.nk_profile_interp or "smooth"),
            )
            mse_s, rmse_s = spectral_mse_rmse_masked_from_nk(
                cfg,
                {},
                lam_full,
                np.asarray(n_s, dtype=np.float64).ravel(),
                np.asarray(k_s, dtype=np.float64).ravel(),
                float(d_target_nm),
            )
            _seed_cache.update(
                done=True,
                n_lam=np.asarray(n_s, dtype=np.float64).ravel(),
                k_lam=np.asarray(k_s, dtype=np.float64).ravel(),
                mse=float(mse_s) if np.isfinite(float(mse_s)) else float("nan"),
                rmse=float(rmse_s) if np.isfinite(float(rmse_s)) else float("nan"),
            )
        return _seed_cache["rmse"], _seed_cache["n_lam"], _seed_cache["k_lam"], _seed_cache["mse"]

    from certus.spline.spline_objective import spline_pwl_analytic_grad_supported

    def _jac_nodes(x_nodes: np.ndarray) -> np.ndarray | None:

        if not spline_pwl_analytic_grad_supported(cfg):
            return None

        x_full = _pack(x_nodes)

        g_full = obj_stage.analytic_gradient(x_full)

        if g_full is None:
            return None

        gn = np.asarray(g_full[1:], dtype=np.float64).ravel().copy()

        if bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            return gn

        reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))

        if reg_w > 0.0:
            k_loc = int(sk.size)

            L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]

            if L_nodes.size >= 3:
                d2 = np.diff(L_nodes, n=2)

                m = int(d2.size)

                if m > 0:
                    fac = (reg_w * 2.0 / float(m)) * d2  # shape (m,)
                    # Stencil: gn[k+j] += fac[j], gn[k+j+1] -= 2*fac[j], gn[k+j+2] += fac[j]
                    idx_base = k_loc + np.arange(m)
                    np.add.at(gn, idx_base, fac)
                    np.add.at(gn, idx_base + 1, -2.0 * fac)
                    np.add.at(gn, idx_base + 2, fac)

        return gn

    _jac_n = None

    _use_fused = False

    if spline_pwl_analytic_grad_supported(cfg):
        _tj = _jac_nodes(x0)

        if _tj is not None and np.all(np.isfinite(_tj)):
            _jac_n = _jac_nodes

            # Fused mode: when _obj_nodes == _mse_nodes (alpha mode) and no
            # lnk regularization, obj_stage.cost_and_grad gives (f, g) in one
            # call, avoiding duplicate nk/T/R evaluations.
            _has_reg = (
                not bool(getattr(cfg, "spline_pure_spectral_objective", False))
                and float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0)) > 0.0
            )
            if not use_lr and not _has_reg:
                _use_fused = True

    bds = bds_cache if bds_cache is not None else [(float(b[i, 0]), float(b[i, 1])) for i in range(int(b.shape[0]))]

    if _use_fused:

        def _fused_nodes(x_nodes) -> tuple:
            x_full = _pack(x_nodes)
            cost, grad_full = obj_stage.cost_and_grad(x_full)
            return cost, np.asarray(grad_full[1:], dtype=np.float64).ravel().copy()

        res = minimize(
            _fused_nodes,
            x0,
            method="L-BFGS-B",
            jac=True,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-11, "gtol": 1e-8},
        )
    else:
        res = minimize(
            _obj_nodes,
            x0,
            method="L-BFGS-B",
            jac=_jac_n,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-11, "gtol": 1e-8},
        )

    x_best = np.asarray(getattr(res, "x", x0), dtype=np.float64).ravel()

    x_best = clip_to_bounds(x_best, b[:, 0], b[:, 1])

    m_best_obj = float(_obj_nodes(x_best))  # P0.1 FIX: Consistent with minimize objective

    if not np.isfinite(m_best_obj) or m_best_obj >= 1e29:
        return None

    # Rebuild n(lambda), k(lambda) on masked / full grid via nk_from_x_pwlnk.
    # B7 FIX: reuse cached nk from the last _chi2_nodes/_mse_nodes call if available,
    # avoiding a redundant ~5ms nk_from_x_pwlnk + physics rebuild.
    x_full_best = np.concatenate((np.asarray([float(d_target_nm)], dtype=np.float64), x_best))

    if use_lr and "n_lam" in _chi2_nk_cache:
        n_lam = _chi2_nk_cache["n_lam"]
        k_lam = _chi2_nk_cache["k_lam"]
    else:
        n_lam, k_lam = nk_from_x_pwlnk(
            x_full_best,
            lam_full,
            sk,
            cfg.k_clip_lo,
            cfg.k_clip_hi,
            sig_pre=None,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=str(cfg.nk_profile_interp or "smooth"),
        )

    mse_spec, rmse_spec = spectral_mse_rmse_masked_from_nk(
        cfg,
        {},
        lam_full,
        np.asarray(n_lam, dtype=np.float64).ravel(),
        np.asarray(k_lam, dtype=np.float64).ravel(),
        float(d_target_nm),
    )

    mse_spec_f = float(mse_spec) if np.isfinite(float(mse_spec)) else float("nan")
    rmse = float(rmse_spec) if np.isfinite(float(rmse_spec)) else float("nan")
    # Guarantee a finite RMSE per requested Δd grid point whenever the objective is finite.
    # Some corner cases can yield NaN from the external spectral recomputation even though the
    # internal masked objective returns a valid MSE (pure_spectral mode).
    if not np.isfinite(rmse):
        m_obj = float(m_best_obj) if np.isfinite(float(m_best_obj)) else float("nan")
        if np.isfinite(m_obj) and m_obj < 1e29:
            rmse = float(np.sqrt(max(m_obj, 0.0)))
            if not np.isfinite(mse_spec_f):
                mse_spec_f = float(m_obj)

    rmse_refit_attempt = float(rmse)

    # B1 FIX (2026-05-07): Seed-gate compares *spectral RMSE* (not composite objective).
    # The composite objective (m0, m_best_obj) includes regularization penalty (reg_w)
    # which can bias the decision: a refit with better spectral RMSE but worse
    # regularization penalty would be incorrectly rejected, narrowing the corridor.
    # We lazily evaluate the seed RMSE only when the gate might trigger.
    keep_seed = False
    if bool(keep_nominal_seed_if_refit_worse) and np.isfinite(rmse):
        rmse_seed_for_gate, _, _, _ = _eval_seed_rmse()
        keep_seed_tol = max(
            float(seed_keep_tol_abs),
            float(seed_keep_tol_rel) * max(float(rmse_seed_for_gate), 1e-12),
        )
        keep_seed = bool(np.isfinite(rmse_seed_for_gate) and rmse > rmse_seed_for_gate + keep_seed_tol)

    if keep_seed:
        # Lazy eval: only now do we compute the seed spectral RMSE.
        rmse_seed, n_lam_seed, k_lam_seed, mse_seed_spec = _eval_seed_rmse()

        log.info(
            "Corridor fixed-d refit d=%.5g nm: kept nominal seed (spectral RMSE refit=%.5g > seed=%.5g + tol=%.5g).",
            float(d_target_nm),
            float(rmse_refit_attempt),
            float(rmse_seed),
            float(keep_seed_tol),
        )

        x_best = x0.copy()

        m_best_obj = float(m0)

        n_lam = np.asarray(n_lam_seed, dtype=np.float64).ravel()

        k_lam = np.asarray(k_lam_seed, dtype=np.float64).ravel()

        mse_spec = float(mse_seed_spec) if np.isfinite(float(mse_seed_spec)) else float("nan")
        mse_spec_f = float(mse_spec) if np.isfinite(float(mse_spec)) else float("nan")

        rmse = rmse_seed

    # For reporting: physical n_nodes (useful for export) when n_mono is active.

    n_slice = x_best[:k]

    n_nodes_phys = (
        np.asarray(n_slice, dtype=np.float64).copy()
        if cfg.n_mono_band_nm is None
        else x_slice_n_to_physical_nodes(n_slice, sk, cfg.n_mono_band_nm)
    )

    L_nodes = x_best[k:].copy()

    _msg = str(getattr(res, "message", ""))[:160]

    if keep_seed:
        _msg = f"{_msg} | seed_kept_over_refit(spectral_RMSE)"[:160]

    return {
        "success": bool(getattr(res, "success", False)),
        "message": _msg,
        "nit": int(getattr(res, "nit", 0) or 0),
        "nfev": int(getattr(res, "nfev", 0) or 0),
        "d_nm": float(d_target_nm),
        "mse": float(mse_spec_f) if np.isfinite(float(mse_spec_f)) else float("nan"),
        "mse_objective": float(m_best_obj),
        "rmse": rmse,
        "rmse_seed_before_refit": float(_eval_seed_rmse()[0]) if keep_seed else None,
        "seed_kept_over_refit": bool(keep_seed),
        "seed_keep_tolerance": float(keep_seed_tol),
        "seed_keep_rule": (
            "spectral_rmse_refit_gt_seed_plus_tol" if bool(keep_nominal_seed_if_refit_worse) else "disabled"
        ),
        "rmse_refit_attempted": float(rmse_refit_attempt) if np.isfinite(rmse_refit_attempt) else None,
        "chi2": None,
        # Exact warm start (same x space as optimizer: n_slice (physical or ξ) + L_nodes)
        "x_nodes_best": x_best,
        "sigma_knots": sk,
        "n_nodes_physical": n_nodes_phys,
        "L_nodes": L_nodes,
        "n_lam": np.asarray(n_lam, dtype=np.float64).ravel(),
        "k_lam": np.asarray(k_lam, dtype=np.float64).ravel(),
    }