from __future__ import annotations
# from typing import *  # Unused
import typing
import logging
import numpy as np
from certus.core.certus_core import Any

if typing.TYPE_CHECKING:
    from certus.spline.certus_corridor_config import ProfileCorridorConfig

# from certus.spline.certus_index_spline_core import *  # Unused

log = logging.getLogger('CERTUS')

_LOG_PREFIX = "INDEX_SPLINE [CORRIDORS d]"


def log_coaching_uncertainty_parameter_guide() -> None:
    from certus.spline.spline_corridor_log_coaching import log_coaching_uncertainty_parameter_guide as _impl

    _impl()
def log_coaching_corridor_pipeline_skip_empty() -> None:
    from certus.spline.spline_corridor_log_coaching import log_coaching_corridor_pipeline_skip_empty as _impl

    _impl()
def _log_coaching_corridor_outcome(
    *,
    pconf: ProfileCorridorConfig,
    use_lr: bool,
    use_abs_delta: bool = False,
    d0: float,
    d_arr: np.ndarray,
    rm_arr: np.ndarray,
    rmse_opt: float,
    rmse_thresh: float,
    polish_maxfun: int,
    base_result: dict,
) -> None:
    from certus.spline.spline_corridor_log_coaching import _log_coaching_corridor_outcome as _impl

    _impl(
        pconf=pconf,
        use_lr=use_lr,
        use_abs_delta=use_abs_delta,
        d0=d0,
        d_arr=d_arr,
        rm_arr=rm_arr,
        rmse_opt=rmse_opt,
        rmse_thresh=rmse_thresh,
        polish_maxfun=polish_maxfun,
        base_result=base_result,
    )
def _log_coaching_corridor_failure(
    *,
    reason: str,
    pconf: ProfileCorridorConfig,
    use_lr: bool,
    rmse_opt: float,
    rmse_thresh: float,
    d0: float,
) -> None:
    from certus.spline.spline_corridor_log_coaching import _log_coaching_corridor_failure as _impl

    _impl(
        reason=reason,
        pconf=pconf,
        use_lr=use_lr,
        rmse_opt=rmse_opt,
        rmse_thresh=rmse_thresh,
        d0=d0,
    )
def _log_coaching_bootstrap_outcome(
    *,
    B: int,
    n_ok: int,
    p: float,
    mode: str,
    qref: int,
    d_lo_q: float,
    d_hi_q: float,
) -> None:
    from certus.spline.spline_corridor_log_coaching import _log_coaching_bootstrap_outcome as _impl

    _impl(B=B, n_ok=n_ok, p=p, mode=mode, qref=qref, d_lo_q=d_lo_q, d_hi_q=d_hi_q)
def _log_coaching_reg_sensitivity_outcome(
    *,
    weights: np.ndarray,
    d_lo: np.ndarray,
    d_hi: np.ndarray,
    nw: np.ndarray,
    kw: np.ndarray,
) -> None:
    from certus.spline.spline_corridor_log_coaching import _log_coaching_reg_sensitivity_outcome as _impl

    _impl(weights=weights, d_lo=d_lo, d_hi=d_hi, nw=nw, kw=kw)
def _log_corridor_base_geometry(
    *,
    sk: np.ndarray,
    n_phys: np.ndarray,
    L_nodes: np.ndarray,
    d0: float,
    sk_n_stored: np.ndarray | None,
    diag: dict[str, Any],
    rmse_ref_pipeline: float,
    rmse_seed_no_refit: float,
    mse_seed_no_refit: float,
    use_abs_delta: bool = False,
) -> None:
    """INFO logs: sigma grids, knots, seed RMSE vs pipeline ref."""

    k = int(sk.size)

    log.info(
        "%s ━━━ Profiling base (geometry) ━━━ x_encoding=%s | sigma_knots_n key=%s | "
        "n remesh (sigma_n->sigma_L)=%s | max|sigma_n-sigma_L|=%s mean|…|=%s (atol=%.3e) | sigma_grids_match=%s",
        _LOG_PREFIX,
        str(diag.get("x_encoding", "-")),
        "yes" if diag.get("sigma_knots_n_key_present") else "no",
        "yes" if diag.get("remeshed_n_sigma_n_to_sigma_L") else "no",
        f"{float(diag.get('max_abs_sigma_n_minus_L', float('nan'))):.6e}"
        if np.isfinite(float(diag.get("max_abs_sigma_n_minus_L", float("nan"))))
        else "n/a",
        f"{float(diag.get('mean_abs_sigma_n_minus_L', float('nan'))):.6e}"
        if np.isfinite(float(diag.get("mean_abs_sigma_n_minus_L", float("nan"))))
        else "n/a",
        float(diag.get("sigma_atol_nm_inv", 0.0)),
        str(diag.get("sigma_grids_coincide", False)),
    )

    log.info(
        "%s sigma_L (nm⁻¹) K=%d : %s",
        _LOG_PREFIX,
        k,
        np.array2string(np.asarray(sk, dtype=np.float64), precision=6, max_line_width=200),
    )

    if sk_n_stored is not None and sk_n_stored.size:
        log.info(
            "%s sigma_n (nm⁻¹) K=%d : %s",
            _LOG_PREFIX,
            int(sk_n_stored.size),
            np.array2string(np.asarray(sk_n_stored, dtype=np.float64), precision=6, max_line_width=200),
        )

    for i in range(k):
        sig = float(sk[i])

        lam_nm = 1.0 / max(sig, 1e-30)

        log.info(
            "%s   knot %2d/%d  sigma=%.6e nm⁻¹  lambda~%.2f nm  n=%.6f  ln_k=%.7f  k=%.6e",
            _LOG_PREFIX,
            i + 1,
            k,
            sig,
            lam_nm,
            float(n_phys[i]),
            float(L_nodes[i]),
            float(np.exp(np.clip(L_nodes[i], -80.0, 80.0))),
        )

    if use_abs_delta:
        log.info(
            "%s Spectral RMSE **without refit** (bounded seed, d=d_opt) = %.8f (MSE=%.6e) | "
            "RMSE **threshold** (nominal base n_lam/k_lam curves, same mask) = %.8f | seed-threshold gap=%+.6e. "
            "If the seed ≫ threshold, check sigma_n/sigma_L, mono ξ, clips. The +/-d walks re-optimize n,L at fixed d.",
            _LOG_PREFIX,
            float(rmse_seed_no_refit),
            float(mse_seed_no_refit),
            float(rmse_ref_pipeline),
            float(rmse_seed_no_refit - rmse_ref_pipeline),
        )

    else:
        log.info(
            "%s Spectral RMSE **without refit** (clipped seed, d=d_opt) = %.8f (MSE=%.6e) | pipeline RMSE_ref=%.8f "
            "(spectral_rmse_segments / dict). seed-ref gap=%+.6e - if seed ≫ ref, check sigma_n/sigma_L grids, mono ξ, bound clips. "
            "Following corridor **refits** re-optimize n,L: their RMSE can be **> RMSE_ref** (expected).",
            _LOG_PREFIX,
            float(rmse_seed_no_refit),
            float(mse_seed_no_refit),
            float(rmse_ref_pipeline),
            float(rmse_seed_no_refit - rmse_ref_pipeline),
        )
def _log_corridor_envelope_diagnostics(
    n_lo: np.ndarray,
    n_hi: np.ndarray,
    k_lo: np.ndarray,
    k_hi: np.ndarray,
    k_stack: np.ndarray,
    corridor_ref_k_lam: np.ndarray | None,
    base_k_lam: np.ndarray,
) -> None:
    """Compute and log corridor envelope statistics (spans, logk, k-vs-ref)."""

    n_span = np.asarray(n_hi, dtype=np.float64) - np.asarray(n_lo, dtype=np.float64)
    k_span = np.asarray(k_hi, dtype=np.float64) - np.asarray(k_lo, dtype=np.float64)
    m_n_span = np.isfinite(n_span)
    m_k_span = np.isfinite(k_span) & np.isfinite(k_lo) & np.isfinite(k_hi) & (np.asarray(k_lo, dtype=np.float64) >= 0.0)
    logk_span = np.full(np.asarray(k_span, dtype=np.float64).shape, np.nan, dtype=np.float64)
    m_logk_span = (
        np.isfinite(k_lo)
        & np.isfinite(k_hi)
        & (np.asarray(k_lo, dtype=np.float64) > 0.0)
        & (np.asarray(k_hi, dtype=np.float64) > 0.0)
    )
    logk_span[m_logk_span] = np.log10(np.maximum(np.asarray(k_hi, dtype=np.float64)[m_logk_span], 1e-30)) - np.log10(
        np.maximum(np.asarray(k_lo, dtype=np.float64)[m_logk_span], 1e-30)
    )

    k_ref_diag = (
        np.asarray(corridor_ref_k_lam, dtype=np.float64).ravel()
        if corridor_ref_k_lam is not None
        else np.asarray(base_k_lam, dtype=np.float64).ravel()
    )
    k_ref_rel = np.full(np.asarray(k_span, dtype=np.float64).shape, np.nan, dtype=np.float64)
    if k_ref_diag.size >= k_span.size and k_span.size > 0:
        k_ref_diag = k_ref_diag[: k_span.size]
        m_k_rel = np.isfinite(k_span) & np.isfinite(k_ref_diag) & (np.abs(k_ref_diag) > 1e-30)
        k_ref_rel[m_k_rel] = k_span[m_k_rel] / np.abs(k_ref_diag[m_k_rel])
        m_ref_inside = np.isfinite(k_lo) & np.isfinite(k_hi) & np.isfinite(k_ref_diag)
        n_ref_inside = int(
            np.count_nonzero(
                m_ref_inside
                & (k_ref_diag >= np.asarray(k_lo, dtype=np.float64))
                & (k_ref_diag <= np.asarray(k_hi, dtype=np.float64))
            )
        )
        n_ref_eval = int(np.count_nonzero(m_ref_inside))
    else:
        n_ref_inside = 0
        n_ref_eval = 0

    log.info(
        "%s Corridor envelope stats | n_span median=%s max=%s | k_span median=%s max=%s | log10(k)_span median=%s max=%s | k_rel_span median=%s max=%s | k_ref_inside=%d/%d",
        _LOG_PREFIX,
        f"{float(np.nanmedian(n_span[m_n_span])):.6e}" if np.any(m_n_span) else "n/a",
        f"{float(np.nanmax(n_span[m_n_span])):.6e}" if np.any(m_n_span) else "n/a",
        f"{float(np.nanmedian(k_span[m_k_span])):.6e}" if np.any(m_k_span) else "n/a",
        f"{float(np.nanmax(k_span[m_k_span])):.6e}" if np.any(m_k_span) else "n/a",
        f"{float(np.nanmedian(logk_span[m_logk_span])):.6e}" if np.any(m_logk_span) else "n/a",
        f"{float(np.nanmax(logk_span[m_logk_span])):.6e}" if np.any(m_logk_span) else "n/a",
        f"{float(np.nanmedian(k_ref_rel[np.isfinite(k_ref_rel)])):.6e}" if np.any(np.isfinite(k_ref_rel)) else "n/a",
        f"{float(np.nanmax(k_ref_rel[np.isfinite(k_ref_rel)])):.6e}" if np.any(np.isfinite(k_ref_rel)) else "n/a",
        int(n_ref_inside),
        int(n_ref_eval),
    )

    if k_stack.ndim == 2 and k_stack.shape[0] >= 2 and k_stack.shape[1] > 0:
        k_ref_curve = None
        if k_ref_diag.size >= k_stack.shape[1]:
            k_ref_curve = np.asarray(k_ref_diag[: k_stack.shape[1]], dtype=np.float64)
        elif k_stack.shape[0] > 0:
            k_ref_curve = np.asarray(k_stack[0, :], dtype=np.float64)
        if k_ref_curve is not None:
            delta_logk = np.full((int(k_stack.shape[0]), int(k_stack.shape[1])), np.nan, dtype=np.float64)
            m_ref_curve = np.isfinite(k_ref_curve) & (k_ref_curve > 0.0)
            for _i in range(int(k_stack.shape[0])):
                kr = np.asarray(k_stack[_i, :], dtype=np.float64)
                m_row = np.isfinite(kr) & (kr > 0.0) & m_ref_curve
                if np.any(m_row):
                    delta_logk[_i, m_row] = np.log10(np.maximum(kr[m_row], 1e-30)) - np.log10(
                        np.maximum(k_ref_curve[m_row], 1e-30)
                    )
            row_max_abs = np.nanmax(np.abs(delta_logk), axis=1)
            row_med_abs = np.nanmedian(np.abs(delta_logk), axis=1)
            log.info(
                "%s Corridor k-vs-ref diagnostics | accepted_curves=%d | max|\u0394log10(k)| across curves: median=%s max=%s | median|\u0394log10(k)| across curves: median=%s max=%s",
                _LOG_PREFIX,
                int(k_stack.shape[0]),
                f"{float(np.nanmedian(row_max_abs[np.isfinite(row_max_abs)])):.6e}"
                if np.any(np.isfinite(row_max_abs))
                else "n/a",
                f"{float(np.nanmax(row_max_abs[np.isfinite(row_max_abs)])):.6e}"
                if np.any(np.isfinite(row_max_abs))
                else "n/a",
                f"{float(np.nanmedian(row_med_abs[np.isfinite(row_med_abs)])):.6e}"
                if np.any(np.isfinite(row_med_abs))
                else "n/a",
                f"{float(np.nanmax(row_med_abs[np.isfinite(row_med_abs)])):.6e}"
                if np.any(np.isfinite(row_med_abs))
                else "n/a",
            )
def _log_corridor_start_config(
    cfg,
    pconf,
    use_abs_delta,
    k,
    d0,
    rmse_opt,
    rmse_ref_tag,
    rmse_thr_sub,
    use_adaptive_abs_delta,
    tol_abs,
    rmse_thresh,
    maxfun_prof,
    scientific_nominal,
    use_lr,
    delta_chi2,
    sig_t,
    sig_r,
    sigma_t_f_hetero,
    sigma_r_f_hetero,
):
    if use_abs_delta:
        log.info(
            "%s Start | K_sigma=%d | d_opt=%.6f nm | RMSE_ref=%.8f (%s) | threshold_mode=%s | Delta_mode=%s | absolute threshold RMSE <= %.8f + Delta=%.6f -> %.8f | "
            "step=%.4g nm | span=%.4g nm | max_steps/side=%d | refine=%s tol=%.4g nm it=%d | nk_profile=%s | mono=%s | "
            "wT=%.4g wR=%.4g | rmse_fit_lambda_nm=%s",
            _LOG_PREFIX,
            int(k),
            float(d0),
            float(rmse_opt),
            str(rmse_ref_tag),
            str(rmse_thr_sub),
            "adaptive(local; effective Delta logged after center refit)" if use_adaptive_abs_delta else "fixed",
            float(rmse_opt),
            float(tol_abs),
            float(rmse_thresh),
            float(pconf.step_nm),
            float(pconf.max_span_nm),
            int(pconf.max_steps_each_side),
            bool(pconf.refine_boundary),
            float(pconf.refine_tol_nm),
            int(pconf.refine_max_iter),
            str(getattr(cfg, "nk_profile_interp", "smooth")),
            str(getattr(cfg, "n_mono_band_nm", None)),
            float(getattr(cfg, "weight_t", 0.0)),
            float(getattr(cfg, "weight_r", 0.0)),
            str(getattr(cfg, "rmse_fit_lambda_nm", None)),
        )

    else:
        log.info(
            "%s Start | K_sigma=%d | d_opt=%.6f nm | RMSE_ref=%.8f (%s) | alpha×RMSE threshold (alpha=%.3f -> %.8f) | "
            "step=%.4g nm | span=%.4g nm | max_steps/side=%d | refine=%s tol=%.4g nm it=%d | nk_profile=%s | mono=%s | "
            "wT=%.4g wR=%.4g | rmse_fit_lambda_nm=%s",
            _LOG_PREFIX,
            int(k),
            float(d0),
            float(rmse_opt),
            str(rmse_ref_tag),
            float(pconf.rmse_alpha),
            float(rmse_thresh),
            float(pconf.step_nm),
            float(pconf.max_span_nm),
            int(pconf.max_steps_each_side),
            bool(pconf.refine_boundary),
            float(pconf.refine_tol_nm),
            int(pconf.refine_max_iter),
            str(getattr(cfg, "nk_profile_interp", "smooth")),
            str(getattr(cfg, "n_mono_band_nm", None)),
            float(getattr(cfg, "weight_t", 0.0)),
            float(getattr(cfg, "weight_r", 0.0)),
            str(getattr(cfg, "rmse_fit_lambda_nm", None)),
        )

    log.info(
        "%s L-BFGS-B budget per refit (profiling): maxfun=%d (main run polish=%d)",
        _LOG_PREFIX,
        maxfun_prof,
        int(cfg.polish_maxfun),
    )

    if maxfun_prof < 300:
        log.warning(
            "%s Corridor profiling uses a very small refit budget (maxfun=%d). Profiling robustness may degrade because fixed-d refits can stop before fully relaxing n,L.",
            _LOG_PREFIX,
            int(maxfun_prof),
        )

    if use_abs_delta:
        if scientific_nominal:
            log.info(
                "%s Reminder (scientific corridor): RMSE_ref = **spectral_rmse_best_value** (best polished model); "
                "threshold = RMSE_ref + Delta; nominal curve included **without** corrective envelope widening.",
                _LOG_PREFIX,
            )

        else:
            log.info(
                "%s Reminder (absolute threshold): RMSE_ref = masked spectrum for **n_lam/k_lam** curves from corridor base. "
                "No automatic threshold lift; refits must stay <= RMSE_ref + Delta.",
                _LOG_PREFIX,
            )

    else:
        log.info(
            "%s Reminder: RMSE_ref (above) = spectrum for the **solver** solution (fixed nodes). "
            "Each « best-of » / refit RMSE = **n,L** re-optimization at fixed d (budget/jitter) -> can be **> RMSE_ref**; "
            "the alpha×RMSE threshold may then track the **center refit** (center_refit fallback or automatic lift).",
            _LOG_PREFIX,
        )

    if use_lr:
        log.info(
            "%s Mode LR | conf=%.4f -> Deltaχ²=%.6f | sigma_T=%.6g sigma_R=%.6g %s",
            _LOG_PREFIX,
            float(pconf.lr_conf_level),
            float(delta_chi2),
            float(sig_t),
            float(sig_r),
            "(+sigma_i residual)" if (sigma_t_f_hetero is not None or sigma_r_f_hetero is not None) else "(constants)",
        )