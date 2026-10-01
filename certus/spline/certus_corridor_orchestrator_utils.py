from __future__ import annotations

import logging
import time
import typing
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    Any,
    dataclass,
    get_safe_worker_count,
)
from certus.spline.certus_index_spline_config import SplineOptConfig
from certus.spline.certus_index_spline_core import (
    _reflectance_absolute_backside_from_nk,
    physical_nodes_to_x_slice_n,
    x_slice_n_to_physical_nodes,
)
from certus_physics import clip_to_bounds

if typing.TYPE_CHECKING:
    from certus.spline.certus_corridor_config import CorridorLiveStreamer, ProfileCorridorConfig



from certus.spline.certus_corridor_logger import (
    _log_coaching_reg_sensitivity_outcome,
)
from certus.spline.certus_corridor_utils import (
    _bounds_for_nodes_only,
    _chi2_masked_constant_sigma,
    _estimate_adaptive_rmse_abs_tolerance,
    _extract_knots_and_nodes_from_result,
    _spectral_rmse_at_packed_nodes,
    _x_nodes0_from_mesh_x_if_consistent,
    enforce_min_k_corridor_half_width,
    quick_pwlnk_refit_result_dict,
)
from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference
from certus.spline.spline_objective import (
    SplinePWLObjective,
    build_spline_objective_masked_grid,
)
from certus.utils.certus_index_utils import (
    DataType,
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _transmittance_absolute_from_nk,
)

log = logging.getLogger('CERTUS')
_LOG_PREFIX = "INDEX_SPLINE [CORRIDOR ORCHESTRATOR]"

def _best_fit_at_d(
    cfg: SplineOptConfig,
    *,
    sk: np.ndarray,
    d_nm: float,
    x_seed_primary: np.ndarray,
    x_seed_secondary: np.ndarray | None,
    x_seed_default: np.ndarray,
    bounds_nodes: np.ndarray,
    maxfun: int,
    use_lr: bool,
    sig_t: float,
    sig_r: float,
    chi2_min_ref: float | None,
    delta_chi2: float,
    pconf: ProfileCorridorConfig,
    stage_label: str,
    sigma_t_f: np.ndarray | None = None,
    sigma_r_f: np.ndarray | None = None,
) -> tuple[dict[str, Any] | None, bool, float]:
    """Multi-start: returns (best_fit, ok, metric_value_for_ok_check).

    - ok follows the mode rule (alpha or lr) using chi2_min_ref on the LR side.

    - metric_value_for_ok_check = RMSE (alpha) or χ² (lr) of best_fit.

    """

    from certus.spline.certus_corridor_fitter import _fit_nodes_at_fixed_d
    rng = np.random.default_rng(int(pconf.rng_seed))

    seeds: list[np.ndarray] = []

    x1 = np.asarray(x_seed_primary, dtype=np.float64).ravel()

    seeds.append(x1)

    if x_seed_secondary is not None:
        seeds.append(np.asarray(x_seed_secondary, dtype=np.float64).ravel())

    seeds.append(np.asarray(x_seed_default, dtype=np.float64).ravel())

    # Jitter on seeds (when n_starts > len(seeds))

    k = int(np.asarray(sk).size)

    n_starts_eff = int(max(1, pconf.n_starts))

    while len(seeds) < n_starts_eff:
        base = seeds[0].copy() if seeds else x1.copy()

        j = base.copy()

        j[:k] += rng.normal(0.0, float(pconf.jitter_n), size=k)

        j[k:] += rng.normal(0.0, float(pconf.jitter_L), size=k)

        seeds.append(j)

    best_fit: dict[str, Any] | None = None

    best_metric = float("inf")

    best_rmse = float("inf")

    best_chi2 = float("nan")

    n_try = 0

    n_ok_fit = 0

    n_failed_fit = 0

    n_exceeds_limit = 0

    n_starts_cap = int(max(n_starts_eff, pconf.fit_max_n_starts))

    pure_spectral_refit = bool(getattr(pconf, "refit_pure_spectral", True))
    cfg_fit = cfg.replace(spline_pure_spectral_objective=True) if pure_spectral_refit else cfg
    obj_stage_cache = SplinePWLObjective(cfg_fit, np.asarray(sk, dtype=np.float64).ravel())
    b_arr = np.asarray(bounds_nodes, dtype=np.float64)
    bds_cache = [(float(b_arr[i, 0]), float(b_arr[i, 1])) for i in range(int(b_arr.shape[0]))]

    _mg_cache: tuple | None = None

    if use_lr:
        _mg_cache = build_spline_objective_masked_grid(cfg_fit)

    idx = 0

    def _do_fit(x_in: np.ndarray) -> tuple[dict[str, Any] | None, int]:
        _exceeds = 0
        _f = _fit_nodes_at_fixed_d(
            cfg,
            sk,
            float(d_nm),
            x_in,
            bounds_nodes,
            maxfun=int(maxfun),
            keep_nominal_seed_if_refit_worse=bool(getattr(pconf, "seed_gate_keep_nominal_if_refit_worse", True)),
            seed_keep_tol_rel=float(getattr(pconf, "seed_gate_tol_rel", 0.0)),
            seed_keep_tol_abs=float(getattr(pconf, "seed_gate_tol_abs", 1e-5)),
            pure_spectral=pure_spectral_refit,
            use_lr=bool(use_lr),
            sig_t=float(sig_t),
            sig_r=float(sig_r),
            sigma_t_f=sigma_t_f,
            sigma_r_f=sigma_r_f,
            masked_grid_cache=_mg_cache,
            cfg_effective=cfg_fit,
            obj_stage_cache=obj_stage_cache,
            bds_cache=bds_cache,
        )

        if _f is not None and str(_f.get("message", "")).upper().find("EXCEEDS LIMIT") >= 0:
            _exceeds += 1
            scale = float(max(getattr(pconf, "fit_retry_maxfun_scale", 1.0) or 1.0, 1.0))
            if scale > 1.0:
                _f_retry = _fit_nodes_at_fixed_d(
                    cfg,
                    sk,
                    float(d_nm),
                    np.asarray(_f.get("x_nodes_best", x_in), dtype=np.float64).ravel(),
                    bounds_nodes,
                    maxfun=int(max(maxfun + 1, round(float(maxfun) * scale))),
                    keep_nominal_seed_if_refit_worse=bool(
                        getattr(pconf, "seed_gate_keep_nominal_if_refit_worse", True)
                    ),
                    seed_keep_tol_rel=float(getattr(pconf, "seed_gate_tol_rel", 0.0)),
                    seed_keep_tol_abs=float(getattr(pconf, "seed_gate_tol_abs", 1e-5)),
                    pure_spectral=pure_spectral_refit,
                    use_lr=bool(use_lr),
                    sig_t=float(sig_t),
                    sig_r=float(sig_r),
                    sigma_t_f=sigma_t_f,
                    sigma_r_f=sigma_r_f,
                    masked_grid_cache=_mg_cache,
                    cfg_effective=cfg_fit,
                    obj_stage_cache=obj_stage_cache,
                    bds_cache=bds_cache,
                )
                if _f_retry is not None and np.isfinite(float(_f_retry.get("rmse", float("nan")))):
                    _f = _f_retry
        return _f, _exceeds

    # B2 FIX: Avoid ThreadPoolExecutor overhead for single fit
    if n_starts_cap <= 1:
        while idx < int(min(len(seeds), n_starts_cap)):
            n_try += 1
            try:
                fit, exceeds_count = _do_fit(seeds[idx])
            except ValueError, TypeError, RuntimeError:
                fit, exceeds_count = None, 0

            n_exceeds_limit += exceeds_count

            if fit is None or not np.isfinite(float(fit.get("rmse", float("nan")))):
                n_failed_fit += 1
            else:
                n_ok_fit += 1
                rm = float(fit["rmse"])
                if use_lr:
                    chi = _chi2_masked_constant_sigma(
                        cfg,
                        sigma_t=sig_t,
                        sigma_r=sig_r,
                        n_lam_full=fit["n_lam"],
                        k_lam_full=fit["k_lam"],
                        d_nm=float(d_nm),
                        sigma_t_f=sigma_t_f,
                        sigma_r_f=sigma_r_f,
                        masked_grid=_mg_cache,
                    )
                    metric = float(chi) if np.isfinite(chi) else float("inf")
                else:
                    metric = rm

                if metric < best_metric:
                    best_metric = metric
                    best_fit = fit
                    best_rmse = rm
                    best_chi2 = float(best_metric) if use_lr else float("nan")

            idx += 1
    else:
        # Evaluate seeds in batches to handle parallelization + dynamic additions
        # C2 FIX: Use ThreadPoolExecutor from top-level imports instead of inline
        from certus.core.certus_core import get_safe_worker_count

        with ThreadPoolExecutor(max_workers=min(get_safe_worker_count(), n_starts_cap)) as executor:
            while idx < int(min(len(seeds), n_starts_cap)):
                batch_seeds = seeds[idx:n_starts_cap]
                futures = [executor.submit(_do_fit, s) for s in batch_seeds]

                for future in as_completed(futures):
                    n_try += 1
                    try:
                        fit, exceeds_count = future.result()
                    except ValueError, TypeError, RuntimeError:
                        fit, exceeds_count = None, 0

                    n_exceeds_limit += exceeds_count

                    if fit is None or not np.isfinite(float(fit.get("rmse", float("nan")))):
                        n_failed_fit += 1
                        if bool(getattr(pconf, "fit_auto_n_starts", True)) and len(seeds) < n_starts_cap:
                            jb = x1.copy()
                            jb[:k] += rng.normal(0.0, float(pconf.jitter_n), size=k)
                            jb[k:] += rng.normal(0.0, float(pconf.jitter_L), size=k)
                            seeds.append(jb)
                        continue

                    n_ok_fit += 1
                    rm = float(fit["rmse"])
                    if use_lr:
                        chi = _chi2_masked_constant_sigma(
                            cfg,
                            sigma_t=sig_t,
                            sigma_r=sig_r,
                            n_lam_full=fit["n_lam"],
                            k_lam_full=fit["k_lam"],
                            d_nm=float(d_nm),
                            sigma_t_f=sigma_t_f,
                            sigma_r_f=sigma_r_f,
                            masked_grid=_mg_cache,
                        )
                        metric = float(chi) if np.isfinite(chi) else float("inf")
                    else:
                        metric = rm

                    if metric < best_metric:
                        best_metric = metric
                        best_fit = fit
                        best_rmse = rm
                        best_chi2 = float(best_metric) if use_lr else float("nan")

                idx += len(batch_seeds)

    if best_fit is None:
        log.info(
            "%s %s: multi-start failed | d=%.6f nm | n_starts=%d",
            _LOG_PREFIX,
            stage_label,
            float(d_nm),
            int(pconf.n_starts),
        )

        return None, False, float("nan")

    best_fit["n_try"] = int(n_try)

    best_fit["n_ok_fit"] = int(n_ok_fit)

    best_fit["n_failed_fit"] = int(n_failed_fit)

    best_fit["n_exceeds_limit"] = int(n_exceeds_limit)

    # Determine ok from mode.

    if use_lr:
        if chi2_min_ref is None or not np.isfinite(float(chi2_min_ref)):
            ok = False

        else:
            ok = np.isfinite(best_chi2) and best_chi2 <= float(chi2_min_ref) + float(delta_chi2)

        log.info(
            "%s %s: best-of-%d | d=%.6f nm | chi2=%.8f | rmse=%.8f (refit n,L at fixed d) | ok=%s | okfits=%d",
            _LOG_PREFIX,
            stage_label,
            int(n_try),
            float(d_nm),
            float(best_chi2),
            float(best_rmse),
            bool(ok),
            int(n_ok_fit),
        )

        return best_fit, ok, float(best_chi2)

    else:
        ok = True  # alpha filtering is done by caller with rmse_thresh

        log.info(
            '%s %s: best-of-%d | d=%.6f nm | rmse=%.8f (refit n,L at fixed d; not solver "segments" RMSE) | okfits=%d',
            _LOG_PREFIX,
            stage_label,
            int(n_try),
            float(d_nm),
            float(best_rmse),
            int(n_ok_fit),
        )

        return best_fit, ok, float(best_rmse)
def _generate_iso_phase_seed(
    x_prev: np.ndarray,
    sk: np.ndarray,
    d_prev: float,
    d_try: float,
    cfg: SplineOptConfig,
) -> np.ndarray:
    """Optical path invariant warm-start: projects n such that n * d ~ constant."""
    x_smart_seed = x_prev.copy()
    try:
        from certus.core.certus_core import N_MAX_LIMIT, N_MIN_LIMIT
        from certus.spline.certus_index_spline_core import physical_nodes_to_x_slice_n
        from certus.spline.spline_objective import x_slice_n_to_physical_nodes

        ratio_d = float(d_prev / d_try) if d_try >= 1.0 else 1.0
        k = int(np.asarray(sk, dtype=np.float64).size)
        _n_old = x_slice_n_to_physical_nodes(x_prev[:k], sk, cfg.n_mono_band_nm)
        _n_new = np.clip(_n_old * ratio_d, N_MIN_LIMIT, N_MAX_LIMIT)
        x_smart_seed[:k] = physical_nodes_to_x_slice_n(_n_new, sk, cfg.n_mono_band_nm)
    except (ValueError, TypeError, RuntimeError) as e:
        log.debug("Iso-Phase warm-start projection failed: %s", e)
        x_smart_seed = x_prev
    return x_smart_seed
def compute_reg_sensitivity_scan(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig,
    weights: np.ndarray,
) -> dict[str, Any]:
    """V2.3: sensitivity scan by varying ``cfg.lnk_spline_reg_weight``.

    For each weight, rerun ``compute_profiled_corridors_by_d`` (same thresholds / mode),

    then summarize:

      - admissible d interval

      - mean corridor width for n and k on lambda grid (mean(corridor_hi - corridor_lo)).

    Parallelism: ``cfg.corridor_reg_sensitivity_n_workers`` (default 1). Use ``<= 0`` for

    ``min(8, max(1, get_safe_worker_count()))`` when more than one weight.

    """

    w_arr = np.asarray(weights, dtype=np.float64).ravel()

    w_arr = w_arr[np.isfinite(w_arr) & (w_arr >= 0.0)]

    if w_arr.size == 0:
        return {}

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    out_weights: list[float] = []

    out_d_lo: list[float] = []

    out_d_hi: list[float] = []

    out_nw: list[float] = []

    out_kw: list[float] = []

    out_n_valid: list[int] = []

    def _reg_sens_one(iw: tuple[int, float]) -> tuple[int, float, float, float, float, float, int]:

        _idx, w = iw

        cfg_w = cfg.replace(lnk_spline_reg_weight=float(w))

        try:
            from certus.spline.spline_profile_corridors import compute_profiled_corridors_by_d
            extra = compute_profiled_corridors_by_d(cfg_w, base_result, pconf=pconf, log_coaching=False)

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s [REG-SENS] failed | reg_w=%.6g", _LOG_PREFIX, float(w))

            extra = {}

        d_int = extra.get("profile_d_interval_nm", None)

        dlo = float("nan")

        dhi = float("nan")

        if isinstance(d_int, (tuple, list)) and len(d_int) == 2:
            try:
                dlo = float(d_int[0])

                dhi = float(d_int[1])

            except TypeError, ValueError:
                dlo, dhi = float("nan"), float("nan")

        n_lo = np.asarray(extra.get("corridor_n_lo", []), dtype=np.float64).ravel()

        n_hi = np.asarray(extra.get("corridor_n_hi", []), dtype=np.float64).ravel()

        k_lo = np.asarray(extra.get("corridor_k_lo", []), dtype=np.float64).ravel()

        k_hi = np.asarray(extra.get("corridor_k_hi", []), dtype=np.float64).ravel()

        n_width = float("nan")

        k_width = float("nan")

        if n_lo.size == lam_full.size and n_hi.size == lam_full.size:
            dn = n_hi - n_lo

            dn = dn[np.isfinite(dn)]

            if dn.size:
                n_width = float(np.mean(dn))

        if k_lo.size == lam_full.size and k_hi.size == lam_full.size:
            dk = k_hi - k_lo

            dk = dk[np.isfinite(dk)]

            if dk.size:
                k_width = float(np.mean(dk))

        n_valid = int(np.asarray(extra.get("profile_d_values_nm", [])).size)

        return (_idx, float(w), float(dlo), float(dhi), float(n_width), float(k_width), int(n_valid))

    nw = int(getattr(cfg, "corridor_reg_sensitivity_n_workers", 1) or 1)

    if nw <= 0:
        nw = get_safe_worker_count()

    w_jobs = list(enumerate(w_arr.tolist()))

    log.info(
        "%s [REG-SENS] Scan start | n=%d | workers=%d | weights=%s",
        _LOG_PREFIX,
        int(w_arr.size),
        int(min(nw, len(w_jobs)) if len(w_jobs) > 1 else 1),
        np.array2string(w_arr, precision=3),
    )

    if nw > 1 and len(w_jobs) > 1:
        try:
            with ThreadPoolExecutor(max_workers=min(nw, len(w_jobs))) as _pool:
                rows = list(_pool.map(_reg_sens_one, w_jobs))

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s [REG-SENS] parallel failed - sequential fallback.", _LOG_PREFIX)

            rows = [_reg_sens_one(j) for j in w_jobs]

    else:
        rows = [_reg_sens_one(j) for j in w_jobs]

    rows.sort(key=lambda r: int(r[0]))

    for _idx, w, dlo, dhi, n_width, k_width, n_valid in rows:
        out_weights.append(float(w))

        out_d_lo.append(float(dlo))

        out_d_hi.append(float(dhi))

        out_nw.append(float(n_width))

        out_kw.append(float(k_width))

        out_n_valid.append(int(n_valid))

        log.info(
            "%s [REG-SENS] reg_w=%.6g | d=[%s,%s] nm | mean_width_n=%s mean_width_k=%s | n_valid=%d",
            _LOG_PREFIX,
            float(w),
            f"{dlo:.4f}" if np.isfinite(dlo) else "n/a",
            f"{dhi:.4f}" if np.isfinite(dhi) else "n/a",
            f"{n_width:.6g}" if np.isfinite(n_width) else "n/a",
            f"{k_width:.6g}" if np.isfinite(k_width) else "n/a",
            int(n_valid),
        )

    _log_coaching_reg_sensitivity_outcome(
        weights=np.asarray(out_weights, dtype=np.float64),
        d_lo=np.asarray(out_d_lo, dtype=np.float64),
        d_hi=np.asarray(out_d_hi, dtype=np.float64),
        nw=np.asarray(out_nw, dtype=np.float64),
        kw=np.asarray(out_kw, dtype=np.float64),
    )

    return {
        "reg_sens_enabled": True,
        "reg_sens_weights": np.asarray(out_weights, dtype=np.float64),
        "reg_sens_d_lo_nm": np.asarray(out_d_lo, dtype=np.float64),
        "reg_sens_d_hi_nm": np.asarray(out_d_hi, dtype=np.float64),
        "reg_sens_mean_width_n": np.asarray(out_nw, dtype=np.float64),
        "reg_sens_mean_width_k": np.asarray(out_kw, dtype=np.float64),
        "reg_sens_n_valid": np.asarray(out_n_valid, dtype=np.int64),
    }
def _theoretical_TR_from_base_result(
    cfg: SplineOptConfig,
    base_result: dict,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Compute theoretical T/R from the base result n/k model."""

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    n_lam = np.asarray(base_result.get("n_lam", []), dtype=np.float64).ravel()
    k_lam = np.asarray(base_result.get("k_lam", []), dtype=np.float64).ravel()
    d_nm = float(base_result.get("d_nm", float("nan")))

    if lam.size == 0 or n_lam.size != lam.size or k_lam.size != lam.size or not np.isfinite(d_nm):
        return None, None

    n_sub = np.asarray(cfg.n_sub, dtype=np.float64).ravel()
    if n_sub.size != lam.size:
        return None, None

    t_th: np.ndarray | None = None
    r_th: np.ndarray | None = None

    if cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and cfg.t_exp is not None and float(cfg.weight_t) > 0:
        if cfg.t_is_ratio:
            t_th = _ratio_theoretical_from_nk(lam, n_lam, k_lam, float(d_nm), n_sub)
        else:
            t_th = _transmittance_absolute_from_nk(lam, n_lam, k_lam, float(d_nm), n_sub)

    if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and cfg.r_exp is not None and float(cfg.weight_r) > 0:
        if cfg.t_is_ratio:
            r_th = _reflectance_ratio_theoretical_from_nk(lam, n_lam, k_lam, float(d_nm), n_sub)
        else:
            r_th = _reflectance_absolute_backside_from_nk(lam, n_lam, k_lam, float(d_nm), n_sub)

    return t_th, r_th
def _manual_grid_tag_base_on_duplicate_discard(
    point_kind_list: list[int],
    i_same: int,
    *,
    incoming_point_kind: int,
) -> None:
    """When a chained base-grid refit hits duplicate *d* with worse RMSE, keep coverage semantics.

    Reverse exploration may fill the slot first with ``point_kind!=0`` while a subsequent base-grid
    visit discovers the duplicate and is discarded. Coverage audits still treat ``kind==0`` rows as
    ``returned_base``; tag the occupied slot accordingly.
    """
    if int(incoming_point_kind) != 0:
        return
    i = int(i_same)
    if 0 <= i < len(point_kind_list):
        point_kind_list[i] = 0
def _detect_breakpoint(
    side: int,
    d_now: float,
    rmse_now: float,
    side_last_rmse: dict[int, float],
    side_recent_rmse: dict[int, list[float]],
    side_recent_d: dict[int, list[float]],
    lookback_points: int,
    min_gain_abs_prevn: float,
    min_gain_rel_prevn: float,
    min_gain_abs_parab: float,
) -> tuple[bool, float, float, float, float, bool, float, float, bool, float, float, float]:
    prev = float(side_last_rmse.get(side, float("nan")))
    recent = [float(v) for v in side_recent_rmse.get(side, []) if np.isfinite(v)]
    recent_d = [float(v) for v in side_recent_d.get(side, []) if np.isfinite(v)]

    if not np.isfinite(prev) or not np.isfinite(rmse_now):
        return (
            False,
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            False,
            float("nan"),
            float("nan"),
            False,
            float("nan"),
            float("nan"),
            float("nan"),
        )

    gain_abs = float(prev - rmse_now)
    gain_rel = float(gain_abs / max(abs(prev), 1e-12))
    abs_thr = float(max(8e-5, 0.04 * max(abs(prev), abs(rmse_now), 1e-12)))
    rel_thr = 0.035
    trigger_legacy = bool(gain_abs > abs_thr and gain_rel > rel_thr)

    best_prev5 = (
        float(np.nanmin(np.asarray(recent[-lookback_points:], dtype=np.float64)))
        if len(recent) >= lookback_points
        else float("nan")
    )
    gain_vs_prev5 = float(best_prev5 - rmse_now) if np.isfinite(best_prev5) else float("nan")
    trigger_prev5 = bool(
        np.isfinite(best_prev5)
        and (rmse_now < (best_prev5 - 1e-12))
        and np.isfinite(gain_vs_prev5)
        and (gain_vs_prev5 >= float(min_gain_abs_prevn))
        and ((gain_vs_prev5 / max(abs(best_prev5), 1e-12)) >= float(min_gain_rel_prevn))
    )

    trigger_parabola = False
    parab_pred = float("nan")
    parab_gain = float("nan")
    parab_thr = float("nan")
    n_fit = int(min(max(5, lookback_points), len(recent)))

    if n_fit >= 4 and len(recent_d) >= n_fit:
        d_prev = np.asarray(recent_d[-n_fit:], dtype=np.float64)
        r_prev = np.asarray(recent[-n_fit:], dtype=np.float64)
        if np.all(np.isfinite(d_prev)) and np.all(np.isfinite(r_prev)) and np.ptp(d_prev) > 1e-12:
            d_ref = float(np.mean(d_prev))
            x_prev = d_prev - d_ref
            x_now = float(d_now - d_ref)
            try:
                coefs = np.polyfit(x_prev, r_prev, deg=2)
                parab_pred = float(np.polyval(coefs, x_now))
                parab_gain = float(parab_pred - rmse_now)
                prev_pred = np.polyval(coefs, x_prev)
                resid_std = float(np.nanstd(r_prev - prev_pred))
                parab_thr = float(max(2.5e-6, 3.0 * max(resid_std, 1e-12)))
                trigger_parabola = bool(
                    np.isfinite(parab_gain) and (parab_gain > parab_thr) and (parab_gain >= float(min_gain_abs_parab))
                )
            except ValueError, TypeError, RuntimeError:
                trigger_parabola = False

    return (
        bool(trigger_legacy or trigger_prev5 or trigger_parabola),
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
    )
def _run_global_opt_from_breakpoint(
    d_break: float,
    fit_break: dict[str, Any],
    side_origin: int,
    k: int,
    base_eff: dict[str, Any],
    sk: np.ndarray,
    cfg: SplineOptConfig,
    maxfun_global: int,
) -> dict[str, Any] | None:
    # quick_pwlnk_refit_result_dict is defined in this module (line ~3816)
    seed_x_nodes = np.asarray(fit_break.get("x_nodes_best", []), dtype=np.float64).ravel()
    if seed_x_nodes.size != 2 * int(k):
        return None
    seed_x_full = np.concatenate(([float(d_break)], seed_x_nodes))
    seed_result = dict(base_eff)
    seed_result.update(
        {
            "d_nm": float(d_break),
            "x": np.asarray(seed_x_full, dtype=np.float64).ravel().copy(),
            "x_seg_spline_sigma": np.asarray(seed_x_full, dtype=np.float64).ravel().copy(),
            "sigma_knots": np.asarray(sk, dtype=np.float64).ravel().copy(),
            "sigma_knots_L": np.asarray(sk, dtype=np.float64).ravel().copy(),
            "n_nodes_physical": np.asarray(fit_break.get("n_nodes_physical", []), dtype=np.float64).ravel().copy(),
            "L_nodes": np.asarray(fit_break.get("L_nodes", []), dtype=np.float64).ravel().copy(),
            "n_lam": np.asarray(fit_break.get("n_lam", []), dtype=np.float64).ravel().copy(),
            "k_lam": np.asarray(fit_break.get("k_lam", []), dtype=np.float64).ravel().copy(),
            "rmse": float(fit_break.get("rmse", float("nan"))),
        }
    )
    out_global = quick_pwlnk_refit_result_dict(cfg, seed_result, maxfun=maxfun_global)
    if isinstance(out_global, dict):
        out_global["profile_d_manual_grid_global_opt_seed_d_nm"] = float(d_break)
        out_global["profile_d_manual_grid_global_opt_side_origin"] = int(side_origin)
        out_global["x_encoding"] = "corridor_refit_fixed_d"
    return out_global
def _build_emergency_fit_record(
    d_nm: float,
    x_seed_in: np.ndarray,
    k: int,
    bounds_nodes: np.ndarray,
    x_nodes0: np.ndarray,
    lam_full: np.ndarray,
    sk: np.ndarray,
    cfg: SplineOptConfig,
    base_eff: dict,
    r_list: list[float],
    rmse_abs_ref: float,
) -> dict[str, Any] | None:
    """Last-resort record so each requested base-grid d has one sample."""
    try:
        from certus.spline.spline_objective import (
            SplinePWLObjective,
            nk_from_x_pwlnk,
            spectral_mse_rmse_masked_from_nk,
            x_slice_n_to_physical_nodes,
        )
        from certus.spline.spline_profile_corridors import clip_to_bounds

        x_seed = clip_to_bounds(
            np.asarray(x_seed_in, dtype=np.float64).ravel().copy(),
            bounds_nodes[:, 0],
            bounds_nodes[:, 1],
        )
        if x_seed.size != 2 * int(k):
            x_seed = clip_to_bounds(
                np.asarray(x_nodes0, dtype=np.float64).ravel().copy(),
                bounds_nodes[:, 0],
                bounds_nodes[:, 1],
            )
        if x_seed.size != 2 * int(k):
            return None

        x_full_seed = np.concatenate((np.asarray([float(d_nm)], dtype=np.float64), x_seed))
        n_lam_seed = np.asarray([], dtype=np.float64)
        k_lam_seed = np.asarray([], dtype=np.float64)
        mse_seed = float("nan")
        rmse_seed_f = float("nan")

        try:
            n_tmp, k_tmp = nk_from_x_pwlnk(
                x_full_seed,
                lam_full,
                sk,
                cfg.k_clip_lo,
                cfg.k_clip_hi,
                sig_pre=None,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=str(cfg.nk_profile_interp or "smooth"),
            )
            n_lam_seed = np.asarray(n_tmp, dtype=np.float64).ravel()
            k_lam_seed = np.asarray(k_tmp, dtype=np.float64).ravel()
            if n_lam_seed.size == lam_full.size and k_lam_seed.size == lam_full.size:
                mse_seed, rmse_seed = spectral_mse_rmse_masked_from_nk(
                    cfg,
                    {},
                    lam_full,
                    n_lam_seed,
                    k_lam_seed,
                    float(d_nm),
                )
                rmse_seed_f = float(rmse_seed)
        except TypeError, ValueError, RuntimeError:
            log.debug("%s Initial seed evaluation failed for manual grid (non-critical)", _LOG_PREFIX, exc_info=True)

        if n_lam_seed.size != lam_full.size or k_lam_seed.size != lam_full.size:
            n_base = np.asarray(base_eff.get("n_lam", []), dtype=np.float64).ravel()
            k_base = np.asarray(base_eff.get("k_lam", []), dtype=np.float64).ravel()
            if n_base.size == lam_full.size and k_base.size == lam_full.size:
                n_lam_seed = n_base.copy()
                k_lam_seed = k_base.copy()
            else:
                return None

        if not np.isfinite(rmse_seed_f):
            try:
                obj_seed = SplinePWLObjective(cfg, sk)
                m_obj_seed = float(obj_seed(x_full_seed))
            except TypeError, ValueError, RuntimeError:
                m_obj_seed = float("nan")
            if np.isfinite(m_obj_seed) and m_obj_seed < 1e29:
                rmse_seed_f = float(np.sqrt(max(m_obj_seed, 0.0)))
                mse_seed = float(m_obj_seed)

        if not np.isfinite(rmse_seed_f):
            r_hist = np.asarray(r_list, dtype=np.float64)
            if np.any(np.isfinite(r_hist)):
                r_ref = float(np.nanmax(r_hist))
            elif np.isfinite(rmse_abs_ref):
                r_ref = float(rmse_abs_ref)
            else:
                r_ref = 1e-3
            rmse_seed_f = float(max(1e-6, 5.0 * abs(r_ref)))
            mse_seed = float(rmse_seed_f * rmse_seed_f)

        if not np.isfinite(float(mse_seed)):
            mse_seed = float(rmse_seed_f * rmse_seed_f)

        n_slice_seed = x_seed[:k]
        n_nodes_phys_seed = (
            np.asarray(n_slice_seed, dtype=np.float64).copy()
            if cfg.n_mono_band_nm is None
            else x_slice_n_to_physical_nodes(n_slice_seed, sk, cfg.n_mono_band_nm)
        )
        L_nodes_seed = np.asarray(x_seed[k:], dtype=np.float64).copy()
        return {
            "success": False,
            "message": "fallback_emergency_point_recovery",
            "nit": 0,
            "nfev": 0,
            "d_nm": float(d_nm),
            "rmse": float(rmse_seed_f),
            "mse": float(mse_seed),
            "x_nodes_best": x_seed.copy(),
            "n_nodes_physical": n_nodes_phys_seed,
            "L_nodes": L_nodes_seed,
            "n_lam": np.asarray(n_lam_seed, dtype=np.float64).ravel().copy(),
            "k_lam": np.asarray(k_lam_seed, dtype=np.float64).ravel().copy(),
            "fallback_from_seed": False,
            "fallback_from_objective": False,
            "fallback_from_emergency": True,
        }
    except TypeError, ValueError, RuntimeError:
        return None
def _profile_p0_suspects(
    d_list: list[float],
    r_list: list[float],
    x_nodes_best_list: list[np.ndarray],
    n_list: list[np.ndarray],
    k_list: list[np.ndarray],
    nfev_list: list[float],
    k: int,
    lam_full: np.ndarray,
    stop_check: Any | None,
    fit_point_fn: Any,
    touch_best_fn: Any,
) -> None:
    """Re-fit suspect corridor points using the global optimum seed to escape local minima."""
    if not (d_list and r_list and (len(x_nodes_best_list) == len(d_list))):
        return

    _p0_order = np.argsort(np.asarray(d_list, dtype=np.float64))
    _p0_r = np.asarray([r_list[j] for j in _p0_order], dtype=np.float64)
    _p0_n = int(_p0_r.size)
    finite_mask_p0 = np.isfinite(_p0_r)
    if not np.any(finite_mask_p0):
        return

    rmse_min_p0 = float(np.min(_p0_r[finite_mask_p0]))
    i_best_p0_sorted = int(np.argmin(np.where(finite_mask_p0, _p0_r, np.inf)))
    i_best_p0_orig = int(_p0_order[i_best_p0_sorted])
    x_seed_gb = np.asarray(x_nodes_best_list[i_best_p0_orig], dtype=np.float64).ravel().copy()

    if not (np.isfinite(rmse_min_p0) and int(x_seed_gb.size) == 2 * int(k)):
        return

    p0_margin = float(max(5e-5, 0.01 * rmse_min_p0))
    p0_global_thr = float(max(5e-4, 0.15 * rmse_min_p0))

    _fin = np.isfinite(_p0_r)
    _left_fin = np.empty(_p0_n, dtype=bool)
    _left_fin[0] = False
    _left_fin[1:] = _fin[:-1]
    _right_fin = np.empty(_p0_n, dtype=bool)
    _right_fin[-1] = False
    _right_fin[:-1] = _fin[1:]
    _has_both = _left_fin & _right_fin
    _has_one = (_left_fin | _right_fin) & ~_has_both

    _left_r = np.empty(_p0_n, dtype=np.float64)
    _left_r[0] = np.inf
    _left_r[1:] = _p0_r[:-1]
    _right_r = np.empty(_p0_n, dtype=np.float64)
    _right_r[-1] = np.inf
    _right_r[:-1] = _p0_r[1:]
    _ref_neigh = np.maximum(_left_r, _right_r)

    _interior_suspect = _fin & _has_both & (_p0_r > _ref_neigh + p0_margin)
    _edge_suspect = _fin & _has_one & (_p0_r > rmse_min_p0 + p0_global_thr)
    suspect_sorted = list(np.where(_interior_suspect | _edge_suspect)[0])
    suspect = [int(_p0_order[si]) for si in suspect_sorted]

    log.info(
        "%s P0 re-pass | rmse_min=%.8f | neighbour_margin=%.2e | global_edge_thr=%.2e | suspect=%d/%d pts",
        _LOG_PREFIX,
        rmse_min_p0,
        p0_margin,
        p0_global_thr,
        len(suspect),
        len(d_list),
    )
    n_p0_improved = 0
    for ii in suspect:
        if stop_check is not None and bool(stop_check()):
            break
        fit_rp = fit_point_fn(float(d_list[ii]), x_seed_gb.copy())
        if fit_rp is None:
            continue
        rmse_rp = float(fit_rp.get("rmse", float("nan")))
        if np.isfinite(rmse_rp) and rmse_rp < float(r_list[ii]) - 1e-12:
            log.info(
                "%s P0 re-pass improved | d=%.6f nm | rmse %.8f -> %.8f (gain=%.2e)",
                _LOG_PREFIX,
                float(d_list[ii]),
                float(r_list[ii]),
                rmse_rp,
                float(r_list[ii]) - rmse_rp,
            )
            r_list[ii] = rmse_rp
            n_rp = np.asarray(fit_rp.get("n_lam", []), dtype=np.float64).ravel()
            k_rp = np.asarray(fit_rp.get("k_lam", []), dtype=np.float64).ravel()
            if int(n_rp.size) == int(lam_full.size):
                n_list[ii] = n_rp
            if int(k_rp.size) == int(lam_full.size):
                k_list[ii] = k_rp
            nfev_list[ii] += float(fit_rp.get("nfev", 0))
            x_nodes_best_list[ii] = np.asarray(fit_rp.get("x_nodes_best", x_seed_gb), dtype=np.float64).ravel().copy()
            n_p0_improved += 1
            touch_best_fn(float(d_list[ii]), float(rmse_rp), tag="P0_repass")

    log.info(
        "%s P0 re-pass done | improved=%d/%d suspect pts",
        _LOG_PREFIX,
        n_p0_improved,
        len(suspect),
    )
def _profile_manual_grid_coverage_audit(
    d_arr: np.ndarray,
    d_list: list[float],
    point_kind_list: list[int],
    x_seed_center: np.ndarray,
    x_nodes0: np.ndarray,
    bounds_nodes: tuple[np.ndarray, np.ndarray],
    lam_full: np.ndarray,
    sk: np.ndarray,
    cfg: SplineOptConfig,
    base_eff: dict,
    r_list: list[float],
    rmse_abs_ref: float,
    k: int,
    build_emergency_fn: Any,
    append_fit_fn: Any,
    emit_live_fn: Any,
) -> bool:
    """Enforce strict coverage of the requested base grid: one sample per d target.
    This runs after branch explorations / rescue passes and only fills missing
    requested points, never replacing valid ones.
    """
    _d_req_arr = np.asarray(d_arr, dtype=np.float64).ravel()
    _d_done_arr = np.asarray(d_list, dtype=np.float64)
    if _d_done_arr.size > 0 and _d_req_arr.size > 0:
        _covered = np.any(np.abs(_d_req_arr[:, None] - _d_done_arr[None, :]) <= 1e-9, axis=1)
        missing_base_targets = [float(v) for v in _d_req_arr[~_covered]]
    else:
        missing_base_targets = [float(v) for v in _d_req_arr]

    if missing_base_targets:
        log.warning(
            "%s manual RMSE(d) grid coverage | missing requested base points=%d -> emergency recovery",
            _LOG_PREFIX,
            len(missing_base_targets),
        )
        x_seed_emergency = np.asarray(x_seed_center, dtype=np.float64).ravel().copy()
        if x_seed_emergency.size != 2 * int(k):
            x_seed_emergency = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()
        for d_miss in missing_base_targets:
            fit_e = build_emergency_fn(
                float(d_miss),
                x_seed_emergency,
                k,
                bounds_nodes,
                x_nodes0,
                lam_full,
                sk,
                cfg,
                base_eff,
                r_list,
                rmse_abs_ref,
            )
            if fit_e is None:
                log.warning(
                    "%s manual RMSE(d) grid coverage | emergency recovery failed at d=%.6f nm",
                    _LOG_PREFIX,
                    float(d_miss),
                )
                continue
            append_fit_fn(
                float(d_miss),
                fit_e,
                point_kind=0,
                point_status_code=3,
            )
            x_seed_emergency = (
                np.asarray(
                    fit_e.get("x_nodes_best", x_seed_emergency),
                    dtype=np.float64,
                )
                .ravel()
                .copy()
            )
            emit_live_fn(float(d_miss), 1.0)

    # Paranoid coverage audit
    requested_base_points = int(np.asarray(d_arr, dtype=np.float64).size)
    returned_base_points = int(np.sum(np.asarray(point_kind_list, dtype=np.int32) == 0))
    missing_after_emergency = int(max(0, requested_base_points - returned_base_points))
    coverage_complete = bool(missing_after_emergency == 0)

    if coverage_complete:
        log.info(
            "%s manual RMSE(d) grid coverage audit | requested_base=%d | returned_base=%d | missing_after_emergency=%d | status=OK",
            _LOG_PREFIX,
            int(requested_base_points),
            int(returned_base_points),
            int(missing_after_emergency),
        )
    else:
        log.warning(
            "%s manual RMSE(d) grid coverage audit | requested_base=%d | returned_base=%d | missing_after_emergency=%d | status=INCOMPLETE (CRITICAL)",
            _LOG_PREFIX,
            int(requested_base_points),
            int(returned_base_points),
            int(missing_after_emergency),
        )
    return coverage_complete
def _package_profile_grid_result(
    *,
    d_list: list[float],
    r_list: list[float],
    n_list: list[np.ndarray],
    k_list: list[np.ndarray],
    nit_list: list[float],
    nfev_list: list[float],
    point_kind_list: list[int],
    point_status_code_list: list[int],
    x_nodes_best_list: list[np.ndarray],
    t0: float,
    d_arr: np.ndarray,
    d0: float,
    i_center: int,
    nom_pack_present: bool,
    n_branch_trigger: int,
    n_branch_extra_points: int,
    n_global_opt_runs: int,
    n_global_opt_improved: int,
    branch_events: list[dict],
    global_opt_events: list[dict],
    best_global_rmse: float,
    best_global_result: dict | None,
    rmse_nominal_baseline_for_grid: float,
    rmse_abs_ref: float,
    sk: np.ndarray,
    cfg: SplineOptConfig,
    base_eff: dict,
    k: int,
    coverage_complete: bool,
) -> dict[str, Any]:
    """Package accumulated RMSE(d) profile data into the final result dict."""

    if not d_list:
        return {"profile_d_status": "manual_grid_empty", "profile_d_manual_grid_note": "all refits failed"}

    order = np.argsort(np.asarray(d_list, dtype=np.float64))

    d_out = np.asarray([d_list[i] for i in order], dtype=np.float64)

    r_out = np.asarray([r_list[i] for i in order], dtype=np.float64)

    n_stack = np.vstack([n_list[i] for i in order])

    k_stack = np.vstack([k_list[i] for i in order])

    nit_out = np.asarray([nit_list[i] for i in order], dtype=np.float64)

    nfev_out = np.asarray([nfev_list[i] for i in order], dtype=np.float64)

    point_kind_out = np.asarray([point_kind_list[i] for i in order], dtype=np.int32)
    point_status_out = np.asarray([point_status_code_list[i] for i in order], dtype=np.int32)

    chi_out = np.full(d_out.shape, float("nan"), dtype=np.float64)

    dt_ms = (time.perf_counter() - t0) * 1000.0

    log.info(
        "%s manual RMSE(d) grid | n_ok=%d | d in [%.4f, %.4f] nm | breakpoints=%d | extra_points=%d | global_opt_runs=%d | global_opt_improved=%d | elapsed=%.1f ms",
        _LOG_PREFIX,
        int(d_out.size),
        float(np.min(d_out)),
        float(np.max(d_out)),
        int(n_branch_trigger),
        int(n_branch_extra_points),
        int(n_global_opt_runs),
        int(n_global_opt_improved),
        float(dt_ms),
    )
    n_nan_d_out = int(np.sum(~np.isfinite(d_out)))
    n_nan_r_out = int(np.sum(~np.isfinite(r_out)))
    n_fb_seed = int(np.sum(point_status_out == 1))
    n_fb_obj = int(np.sum(point_status_out == 2))
    n_fb_emg = int(np.sum(point_status_out == 3))
    requested_base_points = int(d_arr.size)
    returned_base_points = int(np.sum(point_kind_out == 0))
    missing_after_emergency = int(max(0, requested_base_points - returned_base_points))
    coverage_complete = bool(missing_after_emergency == 0)
    log.info(
        "%s manual RMSE(d) grid diagnostics | nan(d/rmse)=%d/%d | fallback(seed/objective/emergency)=%d/%d/%d | coverage requested/returned/missing=%d/%d/%d",
        _LOG_PREFIX,
        int(n_nan_d_out),
        int(n_nan_r_out),
        int(n_fb_seed),
        int(n_fb_obj),
        int(n_fb_emg),
        int(requested_base_points),
        int(returned_base_points),
        int(missing_after_emergency),
    )
    fg_curve = np.isfinite(d_out) & np.isfinite(r_out)
    if np.any(fg_curve):
        dc = d_out[fg_curve]
        rc = r_out[fg_curve]
        jm = int(np.argmin(rc))
        jM = int(np.argmax(rc))
        log.info(
            "%s manual RMSE(d) grid curve summary | rmse_min=%.8f @ d=%.6f nm | rmse_max=%.8f @ d=%.6f nm",
            _LOG_PREFIX,
            float(rc[jm]),
            float(dc[jm]),
            float(rc[jM]),
            float(dc[jM]),
        )

    curve_minimum_result: dict[str, Any] | None = None
    curve_beats_nominal = False
    curve_vs_nominal_delta_rmse = float("nan")
    fg_min = np.isfinite(d_out) & np.isfinite(r_out)
    if np.any(fg_min):
        j_curve = int(np.argmin(np.where(fg_min, r_out, np.inf)))
        r_cb = float(r_out[j_curve])
        d_cb = float(d_out[j_curve])
        nom_b = float(rmse_nominal_baseline_for_grid)
        delta_nom = float(nom_b - r_cb)
        rel_gate = max(1e-12, 1e-7 * max(abs(nom_b), abs(r_cb), 1e-30))
        if np.isfinite(nom_b) and np.isfinite(r_cb) and (r_cb + rel_gate < nom_b) and (abs(d_cb - float(d0)) > 1e-3):
            orig_i = int(order[j_curve])
            x_nodes_cb = np.asarray(x_nodes_best_list[orig_i], dtype=np.float64).ravel().copy()
            if int(x_nodes_cb.size) == 2 * int(k):
                n_slice_cb = x_nodes_cb[: int(k)]
                L_slice_cb = x_nodes_cb[int(k) :]
                if cfg.n_mono_band_nm is None:
                    n_phys_cb = np.asarray(n_slice_cb, dtype=np.float64).copy()
                else:
                    n_phys_cb = x_slice_n_to_physical_nodes(
                        np.asarray(n_slice_cb, dtype=np.float64),
                        sk,
                        cfg.n_mono_band_nm,
                    )
                x_full_cb = np.concatenate((np.asarray([d_cb], dtype=np.float64), x_nodes_cb))
                curve_minimum_result = dict(base_eff)
                curve_minimum_result.update(
                    {
                        "d_nm": float(d_cb),
                        "x": x_full_cb.copy(),
                        "x_seg_spline_sigma": x_full_cb.copy(),
                        "sigma_knots": np.asarray(sk, dtype=np.float64).ravel().copy(),
                        "sigma_knots_L": np.asarray(sk, dtype=np.float64).ravel().copy(),
                        "n_nodes_physical": np.asarray(n_phys_cb, dtype=np.float64).ravel().copy(),
                        "L_nodes": np.asarray(L_slice_cb, dtype=np.float64).ravel().copy(),
                        "n_lam": np.asarray(n_stack[j_curve], dtype=np.float64).ravel().copy(),
                        "k_lam": np.asarray(k_stack[j_curve], dtype=np.float64).ravel().copy(),
                        "rmse": float(r_cb),
                        "mse": float(r_cb * r_cb),
                        "x_encoding": "corridor_refit_fixed_d",
                        "profile_d_manual_grid_curve_minimum": True,
                    }
                )
                curve_beats_nominal = True
                curve_vs_nominal_delta_rmse = float(delta_nom)
                log.info(
                    "%s manual RMSE(d) grid | curve min beats nominal (refit@fixed d) | d_nom=%.6f rmse_nom=%.8f "
                    "-> d_curve=%.6f rmse_curve=%.8f | Delta_rmse=%.3e",
                    _LOG_PREFIX,
                    float(d0),
                    float(nom_b),
                    float(d_cb),
                    float(r_cb),
                    float(delta_nom),
                )

    curve_min_rmse_syn = float("nan")
    curve_min_d_syn = float("nan")
    if np.any(fg_min):
        j_syn = int(np.argmin(np.where(fg_min, r_out, np.inf)))
        curve_min_rmse_syn = float(r_out[j_syn])
        curve_min_d_syn = float(d_out[j_syn])
    if (
        int(n_global_opt_improved) > 0
        and np.isfinite(best_global_rmse)
        and np.isfinite(curve_min_rmse_syn)
        and float(curve_min_rmse_syn) + 1e-15 < float(best_global_rmse)
    ):
        d_glob_syn = float("nan")
        if isinstance(best_global_result, dict):
            dg0 = best_global_result.get("d_nm")
            if isinstance(dg0, (int, float)) and np.isfinite(float(dg0)):
                d_glob_syn = float(dg0)
        log.info(
            "%s manual RMSE(d) grid | Synthesis: discrete curve minimum RMSE=%.8f @ d=%.6f nm < RMSE adoption "
            "global_opt=%.8f @ d=%.6f nm \u2014 the GUI flow can merge the global minimum; a deep polish "
            "from the curve minimum remains possible.",
            _LOG_PREFIX,
            float(curve_min_rmse_syn),
            float(curve_min_d_syn),
            float(best_global_rmse),
            float(d_glob_syn),
        )

    return {
        "profile_d_values_nm": d_out,
        "profile_d_rmse_values": r_out,
        "profile_d_manual_grid_point_kind": point_kind_out,
        "profile_d_manual_grid_point_status_code": point_status_out,
        "profile_d_chi2_values": chi_out,
        "profile_d_n_curves": n_stack,
        "profile_d_k_curves": k_stack,
        "profile_d_fit_nit_values": nit_out,
        "profile_d_fit_nfev_values": nfev_out,
        "profile_d_status": "manual_grid",
        "profile_d_manual_grid_elapsed_ms": float(dt_ms),
        "profile_d_manual_grid_d0_seed_nm": float(d_arr[i_center]),
        "profile_d_manual_grid_nominal_pack_d_nm": float(d0),
        "profile_d_manual_grid_nominal_pack": bool(nom_pack_present),
        "profile_d_manual_grid_total_points": int(d_arr.size),
        "profile_d_manual_grid_done_points": int(d_out.size),
        "profile_d_manual_grid_base_done_points": int(np.sum(point_kind_out == 0)),
        "profile_d_manual_grid_extra_done_points": int(np.sum(point_kind_out == 1)),
        "profile_d_manual_grid_fallback_seed_points": int(np.sum(point_status_out == 1)),
        "profile_d_manual_grid_fallback_objective_points": int(np.sum(point_status_out == 2)),
        "profile_d_manual_grid_fallback_emergency_points": int(np.sum(point_status_out == 3)),
        "profile_d_manual_grid_requested_base_points": int(requested_base_points),
        "profile_d_manual_grid_returned_base_points": int(returned_base_points),
        "profile_d_manual_grid_missing_after_emergency": int(missing_after_emergency),
        "profile_d_manual_grid_coverage_complete": bool(coverage_complete),
        "profile_d_manual_grid_breakpoint_count": int(n_branch_trigger),
        "profile_d_manual_grid_extra_points": int(n_branch_extra_points),
        "profile_d_manual_grid_breakpoint_events": branch_events,
        "profile_d_manual_grid_global_opt_runs": int(n_global_opt_runs),
        "profile_d_manual_grid_global_opt_improved": int(n_global_opt_improved),
        "profile_d_manual_grid_global_opt_events": global_opt_events,
        "profile_d_manual_grid_best_global_rmse": float(best_global_rmse)
        if np.isfinite(best_global_rmse)
        else float("nan"),
        "profile_d_manual_grid_best_global_result": dict(best_global_result)
        if isinstance(best_global_result, dict)
        else None,
        "profile_d_manual_grid_curve_beats_nominal": bool(curve_beats_nominal),
        "profile_d_manual_grid_curve_vs_nominal_delta_rmse": float(curve_vs_nominal_delta_rmse),
        "profile_d_manual_grid_curve_minimum_result": (
            dict(curve_minimum_result) if isinstance(curve_minimum_result, dict) else None
        ),
    }
@dataclass
class CorridorProfileContext:
    _use_hetero: Any
    _user_mask: Any
    adaptive_abs_meta: Any
    auto_relaxed_alpha: Any
    base_result: Any
    boundary_refine_calls: Any
    center_seed_kept: Any
    cfg: Any
    chi2_vals: Any
    d0: Any
    d_vals: Any
    delta_chi2: Any
    fit_fail_values: Any
    fit_nfev_values: Any
    fit_nit_values: Any
    fit_try_values: Any
    k_curves: Any
    log_coaching: Any
    maxfun_prof: Any
    min_side: Any
    n_curves: Any
    nom_pack: Any
    pconf: Any
    rmse_opt: Any
    rmse_ref_tag: Any
    rmse_thr_sub: Any
    rmse_thresh: Any
    rmse_thresh_active: Any
    rmse_vals: Any
    scientific_nominal: Any
    seed_gate_auto_escalated_global: Any
    seed_gate_deltas: Any
    seed_gate_eval_count: Any
    seed_gate_kept_count: Any
    seed_gate_saturated_global: Any
    sig_r: Any
    sig_t: Any
    sigma_r_f_hetero: Any
    sigma_t_f_hetero: Any
    t0: Any
    threshold_basis_eff: Any
    threshold_fallback_reason: Any
    tol_abs: Any
    tol_abs_effective: Any
    use_abs_delta: Any
    use_adaptive_abs_delta: Any
    use_lr: Any
    live_streamer: Any = None
    # Walk-side state (set by _setup_corridor_context, consumed by compute_profiled_corridors_by_d)
    sk: Any = None
    x_nodes_center: Any = None
    x0_default: Any = None
    bounds_nodes: Any = None
    chi2_min: Any = float("nan")
    x_curves: Any = None
    corridor_ref_n_lam: Any = None
    corridor_ref_k_lam: Any = None
    _push_live_point_from_payload: Any = None
    center_seed_gate_eval_count: int = 0
    center_seed_gate_kept_count: int = 0
    center_seed_gate_delta_refit_minus_seed: float = float("nan")
def _compute_corridor_rmse_threshold(
    cfg: SplineOptConfig,
    pconf,
    rmse_opt: float,
    rmse_seed0: float,
    sk: np.ndarray | None,
    use_lr: bool,
    use_abs_delta: bool,
    use_alpha_factor: bool,
    tol_abs: float,
    rmse_ref_tag: str,
    corridor_seed_x_source: str,
    scientific_nominal: bool,
    nom_pack: dict | None,
    log: logging.Logger,
    _LOG_PREFIX: str,
) -> float:
    """Compute the RMSE threshold for corridor profiling and validate the seed alignment."""
    # N_eff for intelligent statistical threshold
    _N_data = 0
    if cfg.t_exp is not None:
        _N_data += len(cfg.t_exp)
    if cfg.r_exp is not None:
        _N_data += len(cfg.r_exp)
    _N_params = 1 + 2 * sk.size if sk is not None else 25
    _N_eff = max(5, _N_data - _N_params)

    alpha_intelligent = float(np.sqrt(1.0 + 3.84 / _N_eff))

    use_explicit_auto_flag = (
        str(getattr(pconf, "rmse_threshold_mode", "")).strip().lower() == "auto"
        or str(getattr(pconf, "mode", "")).strip().lower() == "auto"
    )
    _alpha_user = float(pconf.rmse_alpha) if np.isfinite(float(pconf.rmse_alpha)) else 1.05

    _use_intelligent_alpha = (
        not use_lr
        and not use_abs_delta
        and np.isfinite(rmse_opt)
        and (use_explicit_auto_flag or abs(_alpha_user - 1.05) < 1e-4)
    )

    if _use_intelligent_alpha:
        rmse_thresh = alpha_intelligent * float(rmse_opt)
        if _alpha_user > alpha_intelligent * 1.1 and not use_explicit_auto_flag:
            log.warning(
                "%s User alpha=%.3f > intelligent_alpha=%.3f (N_eff=%d). Using intelligent to avoid over-widening. "
                "Set rmse_threshold_mode='auto' explicitly to silence this warning.",
                _LOG_PREFIX,
                _alpha_user,
                alpha_intelligent,
                _N_eff,
            )
        else:
            log.info(
                "%s Corridor intelligent threshold | N_eff=%d (N_obs=%d, N_params=%d) => alpha=%.5f",
                _LOG_PREFIX,
                _N_eff,
                _N_data,
                _N_params,
                alpha_intelligent,
            )
    elif use_lr:
        rmse_thresh = float(pconf.rmse_alpha) * float(rmse_opt) if np.isfinite(rmse_opt) else float("nan")
    elif use_abs_delta and np.isfinite(rmse_opt):
        _alpha_f = float(pconf.rmse_alpha) if use_alpha_factor else 1.0
        rmse_thresh = _alpha_f * float(rmse_opt) + tol_abs
    elif np.isfinite(rmse_opt):
        rmse_thresh = _alpha_user * float(rmse_opt)
        log.info(
            "%s Corridor user alpha threshold | alpha=%.5f (intelligent would be %.5f)",
            _LOG_PREFIX,
            _alpha_user,
            alpha_intelligent,
        )
    else:
        rmse_thresh = float("nan")

    # Seed alignment validation
    if scientific_nominal and nom_pack is not None and np.isfinite(float(rmse_opt)) and np.isfinite(float(rmse_seed0)):
        dv = abs(float(rmse_seed0) - float(rmse_opt))
        tol_rm = max(
            1e-12, abs(float(rmse_opt)) * 1e-9, float(np.sqrt(np.finfo(np.float64).eps)) * abs(float(rmse_opt))
        )
        log.info(
            "%s Corridor seed alignment | x_source=%s | RMSE(packed nodes @ d_opt)=%.12g | RMSE_ref(%s)=%.12g | |Delta|=%.3e (warn if >%.3e)",
            _LOG_PREFIX,
            str(corridor_seed_x_source),
            float(rmse_seed0),
            str(rmse_ref_tag),
            float(rmse_opt),
            float(dv),
            float(tol_rm),
        )
        if float(dv) > float(tol_rm):
            xref = str(corridor_seed_x_source)
            if "roundtrip" in xref.lower():
                log.info(
                    "%s Corridor seed vs %s: |Delta|=%.3e > tol=%.3e (x_source=%s). "
                    "Often expected when the packed seed differs from the polished nominal pack; "
                    "investigate only if envelopes look inconsistent (mono ξ / export mismatch otherwise).",
                    _LOG_PREFIX,
                    str(rmse_ref_tag),
                    float(dv),
                    float(tol_rm),
                    xref,
                )
            else:
                log.warning(
                    "%s Corridor seed vs spectral_rmse_best_value: |Delta|=%.3e exceeds tol=%.3e — "
                    "check x_seg_spline_sigma vs n_lam_seg_spline_sigma export, bounds clip, or mono ξ round-trip.",
                    _LOG_PREFIX,
                    float(dv),
                    float(tol_rm),
                )

    return rmse_thresh
def _prep_corridor_base_eff(cfg, base_result, pconf, use_abs_delta, use_lr):
    scientific_nominal = bool(getattr(pconf, "scientific_nominal_corridor", True)) and use_abs_delta and (not use_lr)

    nom_pack: dict[str, Any] | None = None

    if scientific_nominal:
        nom_pack = extract_nominal_best_polished_corridor_reference(base_result)

        if nom_pack is None:
            scientific_nominal = False

            log.info(
                "%s Scientific corridor (best RMSE) unavailable - fallback to base curves from dict.",
                _LOG_PREFIX,
            )

        elif nom_pack is not None:
            sk_chk = np.asarray(nom_pack["sigma_knots"], dtype=np.float64).ravel()

            xsg_chk = nom_pack.get("x_seg_spline_sigma")

            xa_chk = (
                np.asarray(xsg_chk, dtype=np.float64).ravel() if xsg_chk is not None else np.zeros(0, dtype=np.float64)
            )

            if sk_chk.size < 2 or xa_chk.size != 1 + 2 * int(sk_chk.size):
                log.info(
                    "%s Scientific corridor: ``x_seg_spline_sigma`` missing or inconsistent K - fallback.",
                    _LOG_PREFIX,
                )

                scientific_nominal = False

                nom_pack = None

    base_eff: dict[str, Any] = dict(base_result)

    if scientific_nominal and nom_pack is not None:
        skn = np.asarray(nom_pack["sigma_knots"], dtype=np.float64).ravel()

        xsg = nom_pack.get("x_seg_spline_sigma")

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

    sk, n_nodes_phys0, L_nodes0, d0, _prof_geom = _extract_knots_and_nodes_from_result(base_eff)

    k = int(sk.size)

    sk_n_log = (
        np.asarray(base_eff.get("sigma_knots_n"), dtype=np.float64).ravel()
        if base_eff.get("sigma_knots_n") is not None
        else None
    )

    # Initial x_nodes: prefer canonical worker/polish vector x = [d, n_slice…, L…] (no n_phys↔ξ drift).

    x_nodes0 = _x_nodes0_from_mesh_x_if_consistent(base_eff, sk=sk, d0_nm=float(d0))

    corridor_seed_x_source = "mesh_x"

    if x_nodes0 is None:
        corridor_seed_x_source = "roundtrip_n_phys"

        # Build initial x_nodes consistent with pipeline parameterization:

        # n_slice = physical if no monotonicity; else encode n_phys as ξ.

        if cfg.n_mono_band_nm is None:
            n_slice0 = np.asarray(n_nodes_phys0, dtype=np.float64).copy()

        else:
            n_slice0 = physical_nodes_to_x_slice_n(n_nodes_phys0, sk, cfg.n_mono_band_nm)

        x_nodes0 = np.concatenate((n_slice0, np.asarray(L_nodes0, dtype=np.float64).copy()))

    # P1.3 FIX: Pass k_hard_lower_bound from pconf to enforce physical constraint
    _k_bound = float(getattr(pconf, "k_hard_lower_bound", 0.0))
    bounds_nodes, x0_default = _bounds_for_nodes_only(cfg, k, k_hard_lower_bound=_k_bound)

    x_nodes0_pre_clip = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    x_nodes0 = clip_to_bounds(x_nodes0, bounds_nodes[:, 0], bounds_nodes[:, 1])

    if corridor_seed_x_source == "mesh_x" and not np.array_equal(x_nodes0, x_nodes0_pre_clip):
        log.warning(
            "%s Corridor seed: mesh *x* nodes were clipped to bounds (max |Delta|=%.3e) — "
            "spectral RMSE at seed may diverge from spectral_rmse_best_value.",
            _LOG_PREFIX,
            float(np.max(np.abs(x_nodes0 - x_nodes0_pre_clip))),
        )

    mse_seed0, rmse_seed0 = _spectral_rmse_at_packed_nodes(cfg, base_eff, sk, float(d0), x_nodes0)
    return (
        base_eff,
        sk,
        n_nodes_phys0,
        L_nodes0,
        d0,
        _prof_geom,
        x_nodes0,
        corridor_seed_x_source,
        bounds_nodes,
        x0_default,
        mse_seed0,
        rmse_seed0,
        scientific_nominal,
        nom_pack,
        sk_n_log,
    )
def _eval_adaptive_abs_tolerance(
    cfg: SplineOptConfig,
    *,
    pconf: ProfileCorridorConfig,
    sk: np.ndarray,
    d0: float,
    center_fit: dict[str, Any] | None,
    x_nodes0: np.ndarray,
    x0_default: np.ndarray,
    bounds_nodes: np.ndarray,
    maxfun_prof: int,
    sig_t: float,
    sig_r: float,
    sigma_t_f_hetero: np.ndarray | None,
    sigma_r_f_hetero: np.ndarray | None,
    tol_abs: float,
    rmse_opt: float,
    rmse_thresh: float,
    use_alpha_factor: bool,
    live_streamer: CorridorLiveStreamer | None = None,
) -> tuple[dict[str, Any], float]:
    adaptive_abs_meta: dict[str, Any] = {
        "ok": False,
        "delta_rmse_tol": float("nan"),
        "delta_rmse_geom": float("nan"),
        "delta_rmse_noise": float("nan"),
        "profile_sigma": float("nan"),
        "curvature": float("nan"),
        "center_nm": float("nan"),
        "anchor_nm": float("nan"),
        "h_ref_nm": float("nan"),
        "sample_count": 0,
        "sample_d_nm": np.asarray([], dtype=np.float64),
        "sample_rmse": np.asarray([], dtype=np.float64),
        "sample_n_curves": [],
        "sample_k_curves": [],
        "window_nm": (float("nan"), float("nan")),
    }
    tol_abs_effective = float(tol_abs)
    if not (
        bool(
            getattr(pconf, "rmse_threshold_mode", "").strip().lower()
            in ("abs_delta_adaptive", "alpha_plus_adaptive_delta")
        )
        and np.isfinite(rmse_opt)
        and center_fit is not None
    ):
        return adaptive_abs_meta, tol_abs_effective
    adaptive_abs_meta = _estimate_adaptive_rmse_abs_tolerance(
        cfg,
        sk=sk,
        d0=float(d0),
        center_fit=center_fit,
        x_seed_primary=x_nodes0,
        x_seed_default=x0_default,
        bounds_nodes=bounds_nodes,
        maxfun=maxfun_prof,
        pconf=pconf,
        sig_t=sig_t,
        sig_r=sig_r,
        sigma_t_f=sigma_t_f_hetero,
        sigma_r_f=sigma_r_f_hetero,
    )
    if bool(adaptive_abs_meta.get("ok", False)) and np.isfinite(
        float(adaptive_abs_meta.get("delta_rmse_tol", float("nan")))
    ):
        tol_abs_effective = float(adaptive_abs_meta.get("delta_rmse_tol", float(tol_abs)))
        _alpha_f = float(pconf.rmse_alpha) if use_alpha_factor else 1.0
        _s_d = adaptive_abs_meta.get("sample_d_nm", np.asarray([]))
        _s_r = adaptive_abs_meta.get("sample_rmse", np.asarray([]))
        _s_n = adaptive_abs_meta.get("sample_n_curves", [])
        _s_k = adaptive_abs_meta.get("sample_k_curves", [])
        if live_streamer is not None:
            for i_smp in range(len(_s_d)):
                if abs(float(_s_d[i_smp]) - float(d0)) < 1e-8:
                    continue
                live_streamer.push_point(float(_s_d[i_smp]), float(_s_r[i_smp]), _s_n[i_smp], _s_k[i_smp], float("nan"))
        return adaptive_abs_meta, tol_abs_effective
    return adaptive_abs_meta, tol_abs_effective
def _eval_corridor_threshold_fallback(
    pconf, use_lr, use_abs_delta, rm_c, rmse_thresh_active, rmse_opt, threshold_basis_eff, rmse_thresh
):
    auto_relaxed_alpha = False
    threshold_fallback_reason = ""
    if (
        (not use_lr)
        and (not use_abs_delta)
        and bool(getattr(pconf, "auto_relax_threshold_to_include_center", True))
        and np.isfinite(rm_c)
        and np.isfinite(rmse_thresh_active)
    ):
        basis = threshold_basis_eff

        rmse_nom = float(rmse_opt)

        rmse_ctr = float(rm_c)

        rmse_basis = rmse_nom

        if basis == "center_refit":
            rmse_basis = rmse_ctr

        elif basis == "max":
            rmse_basis = max(rmse_nom, rmse_ctr)

        else:
            basis = "nominal"

            rmse_basis = rmse_nom

        rmse_thresh_active = float(pconf.rmse_alpha) * float(rmse_basis)

        ratio_guard = float(max(getattr(pconf, "threshold_ratio_guard", 1.25) or 1.25, 1.0))

        ratio_ctr = float(rmse_ctr / max(rmse_nom, 1e-30)) if np.isfinite(rmse_nom) and rmse_nom > 0 else float("inf")

        if ratio_ctr > ratio_guard and basis != "center_refit":
            rmse_thresh_active = float(pconf.rmse_alpha) * float(rmse_ctr)

            threshold_fallback_reason = f"center_refit_ratio_guard({ratio_ctr:.3f}>{ratio_guard:.3f})"

            basis = "center_refit"

            log.info(
                "%s RMSE threshold fallback: RMSE_refit_center/RMSE_ref=%.3f > guard=%.3f -> basis forced to **center_refit**: "
                "alpha×RMSE is now based on the **center refit** (not RMSE_ref alone), so d_opt is not rejected when only the "
                "nodes-only subproblem is worse than the full solver run.",
                _LOG_PREFIX,
                ratio_ctr,
                ratio_guard,
            )

        threshold_basis_eff = basis

        eps_ar = float(max(getattr(pconf, "auto_relax_epsilon", 0.002) or 0.0, 1e-12))

        relax_fac_cap = float(max(getattr(pconf, "auto_relax_max_factor", 1.5) or 1.5, 1.0))

        need = float(rm_c) * (1.0 + eps_ar)

        max_allowed = float(rmse_thresh) * relax_fac_cap if np.isfinite(rmse_thresh) else need

        if need > rmse_thresh_active:
            rmse_thresh_active = min(need, max_allowed)

            auto_relaxed_alpha = True

            log.info(
                "%s RMSE threshold auto-lifted: nominal alpha×RMSE_ref=%.8f -> effective=%.8f "
                '(center refit RMSE=%.8f; n,L refit at fixed d ≠ solver "segments" RMSE; threshold adjusted to include center).',
                _LOG_PREFIX,
                float(rmse_thresh),
                float(rmse_thresh_active),
                float(rm_c),
            )
    return rmse_thresh_active, auto_relaxed_alpha, threshold_basis_eff, threshold_fallback_reason
def _setup_corridor_context(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig | None = None,
    log_coaching: bool = True,
    profile_polish_maxfun: int | None = None,
    live_cb: Any | None = None,
) -> CorridorProfileContext | dict[str, Any]:
    """Compute d interval and n/k corridors by profiling (refit nodes at fixed d).

    Returns a dict of fields to merge into the pipeline result (or empty dict if disabled / impossible).

    """
    from certus.spline.certus_corridor_config import CorridorContextBuilder
    builder = CorridorContextBuilder(
        cfg=cfg,
        base_result=base_result,
        pconf=pconf,
        log_coaching=log_coaching,
        profile_polish_maxfun=profile_polish_maxfun,
        live_cb=live_cb,
    )
    return builder.build()