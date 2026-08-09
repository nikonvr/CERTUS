from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from certus.spline.certus_corridor_config import ProfileCorridorConfig
import logging
from scipy.optimize import minimize
from certus.core.certus_core import Any, NUMERICAL_FAULT_EXCEPTIONS, N_MAX_LIMIT, N_MIN_LIMIT
from certus.spline.certus_index_spline_config import SplineOptConfig
from certus_physics import clip_to_bounds
from certus.spline.certus_index_spline_core import (
    _reflectance_absolute_backside_from_nk,
    x_slice_n_to_physical_nodes,
)
from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _transmittance_absolute_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    DataType,
)

from certus.spline.spline_objective import build_spline_objective_masked_grid, nk_from_x_pwlnk, spline_pwl_analytic_grad_supported, spectral_mse_rmse_masked_from_nk
# _fit_local_quadratic_rmse_profile: lazy import to avoid circular dependency with certus_corridor_fitter

log = logging.getLogger('CERTUS')
_LOG_PREFIX = "INDEX_SPLINE [CORRIDOR EXPLORE]"

def _expand_corridor_envelope_with_reported_nk(
    n_lo: np.ndarray,
    n_hi: np.ndarray,
    k_lo: np.ndarray,
    k_hi: np.ndarray,
    n_nom: np.ndarray,
    k_nom: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Widen [lo, hi] so reported ``n_lam`` / ``k_lam`` lie inside the envelope (per lambda)."""

    n_lo = np.asarray(n_lo, dtype=np.float64).copy()

    n_hi = np.asarray(n_hi, dtype=np.float64).copy()

    k_lo = np.asarray(k_lo, dtype=np.float64).copy()

    k_hi = np.asarray(k_hi, dtype=np.float64).copy()

    nn = np.asarray(n_nom, dtype=np.float64).ravel()

    kn = np.asarray(k_nom, dtype=np.float64).ravel()

    sz = int(n_lo.size)

    if sz == 0 or nn.size < sz or kn.size < sz:
        return n_lo, n_hi, k_lo, k_hi

    nn = nn[:sz]

    kn = kn[:sz]

    m_n = np.isfinite(n_lo) & np.isfinite(n_hi) & np.isfinite(nn)

    n_lo[m_n] = np.minimum(n_lo[m_n], nn[m_n])

    n_hi[m_n] = np.maximum(n_hi[m_n], nn[m_n])

    m_k = np.isfinite(k_lo) & np.isfinite(k_hi) & np.isfinite(kn) & (kn >= 0.0)

    k_lo[m_k] = np.minimum(k_lo[m_k], kn[m_k])

    k_hi[m_k] = np.maximum(k_hi[m_k], kn[m_k])

    return n_lo, n_hi, k_lo, k_hi
def _robust_sigma_from_mad(values: np.ndarray) -> float:

    arr = np.asarray(values, dtype=np.float64).ravel()

    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return float("nan")

    med = float(np.median(arr))

    mad = float(np.median(np.abs(arr - med)))

    return float(1.4826 * mad)
def _estimate_adaptive_rmse_abs_tolerance(
    cfg: SplineOptConfig,
    *,
    sk: np.ndarray,
    d0: float,
    center_fit: dict[str, Any] | None,
    x_seed_primary: np.ndarray,
    x_seed_default: np.ndarray,
    bounds_nodes: np.ndarray,
    maxfun: int,
    pconf: "ProfileCorridorConfig",
    sig_t: float,
    sig_r: float,
    sigma_t_f: np.ndarray | None,
    sigma_r_f: np.ndarray | None,
) -> dict[str, Any]:
    from certus.spline.certus_corridor_orchestrator_utils import _best_fit_at_d
    from certus.spline.certus_corridor_fitter import _fit_local_quadratic_rmse_profile  # lazy: avoids circular import
    out: dict[str, Any] = {
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

    if center_fit is None or not np.isfinite(float(center_fit.get("rmse", float("nan")))):
        return out

    h_ref = float(max(getattr(pconf, "adaptive_rmse_abs_ref_half_width_nm", 0.5) or 0.0, 1e-6))

    probe_steps = int(max(2, getattr(pconf, "adaptive_rmse_abs_probe_steps_each_side", 2) or 2))

    noise_factor = float(max(getattr(pconf, "adaptive_rmse_abs_noise_factor", 2.0) or 0.0, 0.0))

    delta_min = float(max(getattr(pconf, "adaptive_rmse_abs_min", 0.0) or 0.0, 0.0))

    d_samples: list[float] = [float(d0)]
    rm_samples: list[float] = [float(center_fit.get("rmse", float("nan")))]
    n_samples: list[np.ndarray] = [np.asarray(center_fit.get("n_lam", []), dtype=np.float64).ravel().copy()]
    k_samples: list[np.ndarray] = [np.asarray(center_fit.get("k_lam", []), dtype=np.float64).ravel().copy()]

    x_center = np.asarray(center_fit.get("x_nodes_best", x_seed_primary), dtype=np.float64).ravel().copy()

    for i_step in range(1, probe_steps + 1):
        delta_nm = float(i_step) * float(h_ref)

        for sign in (-1.0, 1.0):
            d_try = float(d0 + sign * delta_nm)

            fit_i, _ok_i, _metric_i = _best_fit_at_d(
                cfg,
                sk=sk,
                d_nm=float(d_try),
                x_seed_primary=x_center,
                x_seed_secondary=np.asarray(x_seed_primary, dtype=np.float64).ravel().copy(),
                x_seed_default=x_seed_default,
                bounds_nodes=bounds_nodes,
                maxfun=maxfun,
                use_lr=False,
                sig_t=sig_t,
                sig_r=sig_r,
                chi2_min_ref=None,
                delta_chi2=0.0,
                pconf=pconf,
                stage_label=f"AdaptiveTol {sign:+.0f}{i_step}",
                sigma_t_f=sigma_t_f,
                sigma_r_f=sigma_r_f,
            )

            if fit_i is not None and np.isfinite(float(fit_i.get("rmse", float("nan")))):
                d_samples.append(float(d_try))
                rm_samples.append(float(fit_i.get("rmse", float("nan"))))
                n_samples.append(np.asarray(fit_i.get("n_lam", []), dtype=np.float64).ravel().copy())
                k_samples.append(np.asarray(fit_i.get("k_lam", []), dtype=np.float64).ravel().copy())

    d_arr = np.asarray(d_samples, dtype=np.float64)
    rm_arr = np.asarray(rm_samples, dtype=np.float64)

    if d_arr.size < 5 or rm_arr.size != d_arr.size:
        return out

    order = np.argsort(d_arr)
    d_arr = d_arr[order]
    rm_arr = rm_arr[order]
    n_arr = [n_samples[i] for i in order]
    k_arr = [k_samples[i] for i in order]

    i_anchor = int(np.argmin(np.abs(d_arr - float(d0))))

    fit_q = _fit_local_quadratic_rmse_profile(
        d_arr,
        rm_arr,
        i_anchor,
        max(2, int(getattr(pconf, "parabola_half_window_pts", 3) or 3)),
        0.0,
    )

    if not bool(fit_q.get("ok", False)):
        return out

    c2, c1, c0 = fit_q.get("coeffs", (float("nan"), float("nan"), float("nan")))

    x_rel = d_arr - float(fit_q.get("anchor_nm", float(d0)))

    rm_fit = float(c2) * x_rel * x_rel + float(c1) * x_rel + float(c0)

    sigma_prof = _robust_sigma_from_mad(rm_arr - rm_fit)

    delta_noise = float(noise_factor * sigma_prof) if np.isfinite(sigma_prof) else 0.0

    # B5 FIX: removed computation of unused delta_geom which was confusing in logs.
    delta_eff = float(max(delta_noise, delta_min))

    out.update(
        {
            "ok": np.isfinite(delta_eff),
            "delta_rmse_tol": delta_eff,
            "delta_rmse_geom": float("nan"),
            "delta_rmse_noise": float(delta_noise),
            "profile_sigma": float(sigma_prof),
            "curvature": float(fit_q.get("curvature", float("nan"))),
            "center_nm": float(fit_q.get("d_center", float("nan"))),
            "anchor_nm": float(fit_q.get("anchor_nm", float("nan"))),
            "h_ref_nm": float(h_ref),
            "sample_count": int(d_arr.size),
            "sample_d_nm": d_arr,
            "sample_rmse": rm_arr,
            "sample_n_curves": n_arr,
            "sample_k_curves": k_arr,
            "window_nm": (float(np.min(d_arr)), float(np.max(d_arr))),
        }
    )

    return out
def widen_corridor_envelope_to_include_nk_in_result(
    out: dict[str, Any],
    n_nom: np.ndarray,
    k_nom: np.ndarray,
) -> None:
    """In-place widen corridor_* lo/hi so ``n_nom``/``k_nom`` lie inside (per lambda)."""

    lam = np.asarray(out.get("lam_nm"), dtype=np.float64).ravel()

    if lam.size == 0:
        return

    keys = (
        "corridor_n_lo",
        "corridor_n_hi",
        "corridor_k_lo",
        "corridor_k_hi",
    )

    if not all(k in out and out[k] is not None for k in keys):
        return

    n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
        np.asarray(out["corridor_n_lo"], dtype=np.float64),
        np.asarray(out["corridor_n_hi"], dtype=np.float64),
        np.asarray(out["corridor_k_lo"], dtype=np.float64),
        np.asarray(out["corridor_k_hi"], dtype=np.float64),
        np.asarray(n_nom, dtype=np.float64),
        np.asarray(k_nom, dtype=np.float64),
    )

    out["corridor_n_lo"] = n_lo

    out["corridor_n_hi"] = n_hi

    out["corridor_k_lo"] = k_lo

    out["corridor_k_hi"] = k_hi
def enforce_min_k_corridor_half_width(
    k_lo: np.ndarray,
    k_hi: np.ndarray,
    k_ref: np.ndarray,
    *,
    min_half_width: float = 1e-4,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Guarantee a minimum linear-k corridor half-width around ``k_ref``.

    Real corridor:
      k_lo_real = max(min(k_lo_existing, max(k_ref - min_half_width, 1e-6)), 1e-6)
      k_hi_real = max(k_hi_existing, k_ref + min_half_width)

    k is an extinction coefficient and is physically bounded below by 1e-6
    (never zero or negative in this context).
    """

    lo = np.asarray(k_lo, dtype=np.float64).ravel().copy()

    hi = np.asarray(k_hi, dtype=np.float64).ravel().copy()

    ref = np.asarray(k_ref, dtype=np.float64).ravel().copy()

    if lo.size == 0 or hi.size != lo.size:
        return lo, hi, 0

    if ref.size != lo.size:
        mid = 0.5 * (lo + hi)

        if ref.size == 0:
            ref = mid

        else:
            if ref.size < lo.size:
                ref_pad = np.full(lo.shape, np.nan, dtype=np.float64)

                ref_pad[: ref.size] = ref

                ref = ref_pad

            else:
                ref = ref[: lo.size]

    #The sanitization of non-finite values ​​was locked in the branch
    #`ref.size != lo.size`: in the NORMAL case where the sizes match, a k_ref
    #containing a NaN or an inf passed without filter and contaminated the entire corridor k
    #(any comparison with NaN being false, the limits became inconsistent).
    #It now applies in all cases.
    bad_ref = ~np.isfinite(ref)

    if np.any(bad_ref):
        ref[bad_ref] = (0.5 * (lo + hi))[bad_ref]

    min_hw = float(max(min_half_width, 0.0))

    if min_hw <= 0.0:
        return lo, hi, 0

    bad_lo = ~np.isfinite(lo)

    bad_hi = ~np.isfinite(hi)

    if np.any(bad_lo):
        lo[bad_lo] = np.where(np.isfinite(ref[bad_lo]), np.maximum(ref[bad_lo] - min_hw, 1e-6), 1e-6)

    if np.any(bad_hi):
        hi[bad_hi] = np.where(np.isfinite(ref[bad_hi]), ref[bad_hi] + min_hw, min_hw)

    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)

    lo_min = np.maximum(ref - min_hw, 1e-6)

    hi_min = np.maximum(ref + min_hw, lo_min)

    lo_real = np.maximum(np.minimum(lo, lo_min), 1e-6)  # k >= 1e-6 always

    hi_real = np.maximum(hi, hi_min)

    changed = int(np.sum((np.abs(lo_real - lo) > 1e-15) | (np.abs(hi_real - hi) > 1e-15)))

    return lo_real, hi_real, changed
def _pick_rmse_reference_for_profile(
    cfg: SplineOptConfig,
    base_result: dict,
    sk: np.ndarray,
    d0: float,
    x_nodes0: np.ndarray,
) -> tuple[float, str]:
    """Pick reference RMSE for alpha×RMSE threshold and auto sigma (LR).

    Order: ``spectral_rmse_segments`` (solver-consistent) -> dict ``rmse`` -> recomputed spectral RMSE.

    """

    rs = base_result.get("spectral_rmse_segments")

    try:
        rsv = float(rs) if rs is not None else float("nan")

    except TypeError, ValueError:
        rsv = float("nan")

    if np.isfinite(rsv) and rsv > 0:
        return rsv, "spectral_rmse_segments"

    rm = float(base_result.get("rmse", float("nan")))

    if np.isfinite(rm):
        return rm, "dict_rmse"

    ska = np.asarray(sk, dtype=np.float64).ravel()

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    x_full0 = np.concatenate(
        (np.asarray([float(d0)], dtype=np.float64), np.asarray(x_nodes0, dtype=np.float64).ravel())
    )

    n0, k0 = nk_from_x_pwlnk(
        x_full0,
        lam_full,
        ska,
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=None,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=str(cfg.nk_profile_interp or "smooth"),
    )

    _m0, rr = spectral_mse_rmse_masked_from_nk(cfg, base_result, lam_full, n0, k0, float(d0))

    return rr, "recalc_objective"
def _extract_knots_and_nodes_from_result(
    result: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, dict[str, Any]]:
    """Fetch sigma_knots_L, n and L on that grid, d_nm, and a diagnostic dict (logs / traceability).

    If ``sigma_knots_n`` is present and differs from ``sigma_knots_L`` (sizes or sigma values),

    ``n_nodes_physical`` is interpolated onto the sigma_L grid (same convention as L_nodes / nk PWL).

    """

    sk_L = np.asarray(result.get("sigma_knots_L", result.get("sigma_knots", [])), dtype=np.float64).ravel()

    has_sk_n_key = "sigma_knots_n" in result and result.get("sigma_knots_n") is not None

    sk_n = np.asarray(result.get("sigma_knots_n"), dtype=np.float64).ravel() if has_sk_n_key else sk_L.copy()

    n_nodes = np.asarray(result.get("n_nodes_physical", []), dtype=np.float64).ravel()

    L_nodes = np.asarray(result.get("L_nodes", []), dtype=np.float64).ravel()

    d_nm = float(result.get("d_nm", float("nan")))

    meta: dict[str, Any] = {
        "x_encoding": str(result.get("x_encoding", "")),
        "sigma_knots_n_key_present": bool(has_sk_n_key),
        "recovered_L_nodes_from_x": False,
        "x_recovery_source": "",
        "recovered_L_nodes_from_sigma_source": False,
        "sigma_source_for_L_recovery": "",
        "recovered_n_nodes_from_x": False,
        "recovered_n_nodes_from_sigma_source": False,
        "sigma_source_for_n_recovery": "",
        "fallback_degraded_payload": False,
    }

    if sk_L.size < 2 or not np.isfinite(d_nm):
        raise ValueError("profile corridors: incomplete result (sigma_knots_L / d_nm).")

    if sk_n.size < 2:
        sk_n = sk_L.copy()
        meta["fallback_degraded_payload"] = True

    if L_nodes.size != sk_L.size:
        # Recovery path: some promoted/reconstructed dicts may carry a stale L_nodes vector
        # while keeping a consistent packed x = [d, n_slice..., L_slice...] on the target mesh.
        k = int(sk_L.size)
        want = 1 + 2 * k
        d_atol = float(np.finfo(np.float64).eps) * max(64.0, abs(float(d_nm)), 1.0)
        recovered = False
        for key in ("x_seg_spline_sigma", "x"):
            raw = result.get(key)
            if raw is None:
                continue
            xa = np.asarray(raw, dtype=np.float64).ravel()
            if xa.size != want:
                continue
            if not np.isfinite(float(xa[0])):
                continue
            if not np.isclose(float(xa[0]), float(d_nm), rtol=0.0, atol=d_atol):
                continue
            L_nodes = np.asarray(xa[1 + k : 1 + 2 * k], dtype=np.float64).ravel().copy()
            recovered = True
            meta["recovered_L_nodes_from_x"] = True
            meta["x_recovery_source"] = str(key)
            break
        if (not recovered) or L_nodes.size != sk_L.size:
            # Second recovery path: remesh L_nodes from any sigma source matching its current length.
            sigma_candidates: list[tuple[str, np.ndarray]] = [
                ("sigma_knots", np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()),
                ("sigma_knots_n", np.asarray(result.get("sigma_knots_n", []), dtype=np.float64).ravel()),
            ]
            recovered_sig = False
            for src_name, sk_src_raw in sigma_candidates:
                if int(sk_src_raw.size) != int(L_nodes.size) or sk_src_raw.size < 2:
                    continue
                if not np.all(np.isfinite(sk_src_raw)):
                    continue
                order_src = np.argsort(sk_src_raw)
                sk_src = np.asarray(sk_src_raw[order_src], dtype=np.float64).ravel()
                L_src = np.asarray(L_nodes[order_src], dtype=np.float64).ravel()
                if not np.all(np.isfinite(L_src)):
                    continue
                # Prevent zero-span / duplicate-knot interpolation faults.
                uniq_mask = np.concatenate(([True], np.diff(sk_src) > 0.0))
                sk_u = sk_src[uniq_mask]
                L_u = L_src[uniq_mask]
                if sk_u.size < 2:
                    continue
                try:
                    L_nodes = np.interp(sk_L, sk_u, L_u).astype(np.float64, copy=False)
                    recovered_sig = True
                    meta["recovered_L_nodes_from_sigma_source"] = True
                    meta["sigma_source_for_L_recovery"] = str(src_name)
                    break
                except TypeError, ValueError:
                    continue
            if (not recovered_sig) or L_nodes.size != sk_L.size:
                # Last-resort fallback: monotone index-space remap (keeps pipeline alive on stale payloads).
                if L_nodes.size >= 2:
                    log.warning(
                        "%s L_nodes fallback triggered: using index-space interpolation for L_nodes.", _LOG_PREFIX
                    )
                    t_src = np.linspace(0.0, 1.0, int(L_nodes.size), dtype=np.float64)
                    t_dst = np.linspace(0.0, 1.0, int(sk_L.size), dtype=np.float64)
                    L_nodes = np.interp(t_dst, t_src, np.asarray(L_nodes, dtype=np.float64).ravel())
                    meta["recovered_L_nodes_from_sigma_source"] = True
                    meta["sigma_source_for_L_recovery"] = "index_space_fallback"
                if L_nodes.size != sk_L.size:
                    log.warning("%s Degraded L_nodes fallback triggered: constant L profile applied.", _LOG_PREFIX)
                    # Degraded last fallback: constant L profile from available k_lam or safe default.
                    k_lam_seed = np.asarray(result.get("k_lam", []), dtype=np.float64).ravel()
                    k_f = k_lam_seed[np.isfinite(k_lam_seed) & (k_lam_seed > 0.0)]
                    if k_f.size > 0:
                        l_seed = float(np.log(np.median(k_f)))
                    else:
                        l_seed = float(np.log(1e-5))
                    L_nodes = np.full(int(sk_L.size), l_seed, dtype=np.float64)
                    meta["fallback_degraded_payload"] = True

    if n_nodes.size != sk_n.size:
        # Try to recover n-slice from packed x on either sigma_n or sigma_L mesh.
        d_atol = float(np.finfo(np.float64).eps) * max(64.0, abs(float(d_nm)), 1.0)
        recovered_n = False
        for key in ("x_seg_spline_sigma", "x"):
            raw = result.get(key)
            if raw is None:
                continue
            xa = np.asarray(raw, dtype=np.float64).ravel()
            if not np.isfinite(float(xa[0])) or not np.isclose(float(xa[0]), float(d_nm), rtol=0.0, atol=d_atol):
                continue
            # Prefer sigma_n layout if dimensions match.
            want_n = 1 + 2 * int(sk_n.size)
            want_L = 1 + 2 * int(sk_L.size)
            if xa.size == want_n and sk_n.size >= 2:
                n_slice = np.asarray(xa[1 : 1 + int(sk_n.size)], dtype=np.float64).ravel()
                try:
                    n_nodes = x_slice_n_to_physical_nodes(n_slice, sk_n, None)
                except ValueError, TypeError:
                    n_nodes = n_slice.copy()
                recovered_n = True
                meta["recovered_n_nodes_from_x"] = True
                break
            if xa.size == want_L and sk_L.size >= 2:
                n_slice = np.asarray(xa[1 : 1 + int(sk_L.size)], dtype=np.float64).ravel()
                try:
                    nL_nodes = x_slice_n_to_physical_nodes(n_slice, sk_L, None)
                except ValueError, TypeError:
                    nL_nodes = n_slice.copy()
                if sk_n.size == sk_L.size:
                    n_nodes = np.asarray(nL_nodes, dtype=np.float64).ravel().copy()
                else:
                    n_nodes = np.interp(sk_n, sk_L, np.asarray(nL_nodes, dtype=np.float64).ravel())
                recovered_n = True
                meta["recovered_n_nodes_from_x"] = True
                break
        if (not recovered_n) or n_nodes.size != sk_n.size:
            # Last-resort fallback for stale payloads without usable mesh metadata.
            if n_nodes.size >= 2:
                log.warning("%s n_nodes fallback triggered: using index-space interpolation for n_nodes.", _LOG_PREFIX)
                t_src = np.linspace(0.0, 1.0, int(n_nodes.size), dtype=np.float64)
                t_dst = np.linspace(0.0, 1.0, int(sk_n.size), dtype=np.float64)
                n_nodes = np.interp(t_dst, t_src, np.asarray(n_nodes, dtype=np.float64).ravel())
                meta["recovered_n_nodes_from_sigma_source"] = True
                meta["sigma_source_for_n_recovery"] = "index_space_fallback"
            if n_nodes.size != sk_n.size:
                log.warning("%s Degraded n_nodes fallback triggered: constant n profile applied.", _LOG_PREFIX)
                # Degraded last fallback: constant n profile from available n_lam or safe default.
                n_lam_seed = np.asarray(result.get("n_lam", []), dtype=np.float64).ravel()
                n_f = n_lam_seed[np.isfinite(n_lam_seed)]
                n_seed = float(np.median(n_f)) if n_f.size > 0 else 1.7
                n_nodes = np.full(int(sk_n.size), n_seed, dtype=np.float64)
                meta["fallback_degraded_payload"] = True

    sig_span = float(np.ptp(sk_L)) if sk_L.size else 0.0

    atol_sig = max(1e-14, 1e-9 * sig_span) if np.isfinite(sig_span) and sig_span > 0 else 1e-14

    same_len = sk_n.size == sk_L.size

    grids_coincide = same_len and bool(np.allclose(sk_L, sk_n, rtol=0.0, atol=atol_sig))

    meta["sigma_grids_coincide"] = bool(grids_coincide)

    meta["max_abs_sigma_n_minus_L"] = float(np.max(np.abs(sk_L - sk_n))) if same_len else float("nan")

    meta["mean_abs_sigma_n_minus_L"] = float(np.mean(np.abs(sk_L - sk_n))) if same_len else float("nan")

    meta["sigma_atol_nm_inv"] = float(atol_sig)

    remeshed = False

    if not grids_coincide:
        try:
            n_nodes = np.interp(sk_L, sk_n, n_nodes)

            remeshed = True

        except (TypeError, ValueError) as exc:
            raise ValueError("profile corridors: n_nodes remesh failed (sigma_knots_n -> sigma_knots_L).") from exc

    meta["remeshed_n_sigma_n_to_sigma_L"] = bool(remeshed)

    if n_nodes.size != sk_L.size:
        # Ultimate guard: coerce by index-space remap so corridor path never crashes.
        if n_nodes.size >= 2:
            t_src = np.linspace(0.0, 1.0, int(n_nodes.size), dtype=np.float64)
            t_dst = np.linspace(0.0, 1.0, int(sk_L.size), dtype=np.float64)
            n_nodes = np.interp(t_dst, t_src, np.asarray(n_nodes, dtype=np.float64).ravel())
            log.warning(
                "%s Ultimate n_nodes coerce: index-space remap (%d -> %d nodes).", _LOG_PREFIX, n_nodes.size, sk_L.size
            )
            meta["fallback_degraded_payload"] = True
        elif n_nodes.size == 1:
            n_nodes = np.full(int(sk_L.size), float(n_nodes[0]), dtype=np.float64)
            log.warning("%s Ultimate n_nodes coerce: single value broadcast.", _LOG_PREFIX)
            meta["fallback_degraded_payload"] = True
        else:
            n_nodes = np.full(int(sk_L.size), 1.7, dtype=np.float64)
            log.warning("%s Ultimate n_nodes coerce: hardcoded n=1.7 fallback.", _LOG_PREFIX)
            meta["fallback_degraded_payload"] = True

    return sk_L, n_nodes, L_nodes, d_nm, meta
def _spectral_rmse_at_packed_nodes(
    cfg: SplineOptConfig,
    base_result: dict,
    sk: np.ndarray,
    d_nm: float,
    x_nodes: np.ndarray,
) -> tuple[float, float]:
    """Masked spectral RMSE for fixed [d, x_nodes] (no refit)."""

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    x_full = np.concatenate(
        (np.asarray([float(d_nm)], dtype=np.float64), np.asarray(x_nodes, dtype=np.float64).ravel())
    )

    n_lam, k_lam = nk_from_x_pwlnk(
        x_full,
        lam_full,
        np.asarray(sk, dtype=np.float64).ravel(),
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=None,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=str(cfg.nk_profile_interp or "smooth"),
    )

    mse, rmse = spectral_mse_rmse_masked_from_nk(
        cfg,
        base_result,
        lam_full,
        np.asarray(n_lam, dtype=np.float64).ravel(),
        np.asarray(k_lam, dtype=np.float64).ravel(),
        float(d_nm),
    )

    return float(mse), float(rmse)
def _x_nodes0_from_mesh_x_if_consistent(
    base_eff: dict[str, Any],
    *,
    sk: np.ndarray,
    d0_nm: float,
) -> np.ndarray | None:
    """Extract ``x_nodes`` (size 2K) from ``x_seg_spline_sigma`` or ``x`` when dimensions and *d* match.

    Same layout as the spline worker / mesh polish: ``x = [d, n_slice…, L_slice…]``. Using this path

    avoids ``n_phys → ξ → n_phys`` round-trip drift so packed-node spectral RMSE matches

    ``spectral_rmse_best_value`` at ``d0`` to near machine precision (when the dict *x* is authoritative).

    """

    sk_a = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk_a.size)

    if k < 2:
        return None

    want = 1 + 2 * k

    d_ref = float(d0_nm)

    if not np.isfinite(d_ref):
        return None

    # ULP-tight *d* check: same float pipeline should reproduce bit-identical *d* in x[0] and d_nm.

    d_atol = float(np.finfo(np.float64).eps) * max(64.0, abs(d_ref), 1.0)

    for key in ("x_seg_spline_sigma", "x"):
        raw = base_eff.get(key)

        if raw is None:
            continue

        xa = np.asarray(raw, dtype=np.float64).ravel()

        if xa.size != want:
            continue

        if not np.isfinite(float(xa[0])):
            continue

        if not np.isclose(float(xa[0]), d_ref, rtol=0.0, atol=d_atol):
            continue

        return np.concatenate(
            (xa[1 : 1 + k].astype(np.float64, copy=True), xa[1 + k : 1 + 2 * k].astype(np.float64, copy=True))
        )

    return None
def _bounds_for_nodes_only(
    cfg: SplineOptConfig,
    k: int,
    *,
    k_hard_lower_bound: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Bounds (n-slice, L-slice) and default x0 (size 2K).

    P1.3 FIX: k_hard_lower_bound enforces physical constraint k >= bound via optimizer bounds.
    """

    k = int(k)

    # n bounds: physical or ξ (then N_MONO_XI_BOUNDS apply via cfg/objective);

    # for profiling we reuse the same layout as the optimizer: optimize components

    # exactly as in x = [d, n_slice..., L_slice...].

    if cfg.n_mono_band_nm is None:
        n_lo, n_hi = float(N_MIN_LIMIT), float(N_MAX_LIMIT)

    else:
        # ξ bounds identical to pipeline (see certus_index_spline_core.N_MONO_XI_BOUNDS).

        # Local import to avoid a heavy cyclic import.

        from certus.spline.certus_index_spline_core import N_MONO_XI_BOUNDS

        n_lo, n_hi = map(float, N_MONO_XI_BOUNDS)

    # P1.3 FIX: Apply hard lower bound for k (physical constraint)
    _k_lo_phys = float(max(k_hard_lower_bound, 0.0))
    lo_k = float(max(cfg.k_clip_lo, _k_lo_phys, 1e-30))

    hi_k = float(max(cfg.k_clip_hi, lo_k * 1.0001))

    L_lo = float(np.log(lo_k))

    L_hi = float(np.log(hi_k))

    bounds = np.zeros((2 * k, 2), dtype=np.float64)

    bounds[:k] = [n_lo, n_hi]

    bounds[k:] = [L_lo, L_hi]

    x0 = 0.5 * (bounds[:, 0] + bounds[:, 1])

    # Neutral values (consistent with make_bounds_and_x0):

    if cfg.n_mono_band_nm is None:
        x0[:k] = np.clip(1.65, n_lo, n_hi)

    else:
        x0[:k] = np.clip(0.0, n_lo, n_hi)

    x0[k:] = np.clip(np.log(1e-3), L_lo, L_hi)

    return bounds, x0
def _hetero_sigma_masked_from_base(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    scale: float,
    floor_abs: float,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """sigma_T(lambda), sigma_R(lambda) on masked grid: max(floor, scale×|y_exp-y_th|) like base_result model."""

    from certus.utils.certus_index_utils import _ratio_theoretical_from_nk, _reflectance_ratio_theoretical_from_nk

    mg = build_spline_objective_masked_grid(cfg)

    if mg is None:
        return None, None

    lam_f, _sig_f, n_sub_f, _w, _inv_npix, t_exp_f, r_exp_f = mg

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    n_lam = np.asarray(base_result.get("n_lam", []), dtype=np.float64).ravel()

    k_lam = np.asarray(base_result.get("k_lam", []), dtype=np.float64).ravel()

    d_nm = float(base_result.get("d_nm", float("nan")))

    if n_lam.size != lam_full.size or k_lam.size != lam_full.size or not np.isfinite(d_nm):
        return None, None

    n_f = np.interp(lam_f, lam_full, n_lam)

    k_f = np.interp(lam_f, lam_full, k_lam)

    fl = float(max(floor_abs, 1e-12))

    sc = float(max(scale, 0.0))

    sigma_t_f: np.ndarray | None = None

    sigma_r_f: np.ndarray | None = None

    if cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and float(cfg.weight_t) > 0:
        if cfg.t_is_ratio:
            t_th = _ratio_theoretical_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        else:
            t_th = _transmittance_absolute_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        e = np.asarray(t_exp_f, dtype=np.float64) - np.asarray(t_th, dtype=np.float64)

        sigma_t_f = np.maximum(fl, sc * np.abs(e))

    if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and float(cfg.weight_r) > 0:
        if cfg.t_is_ratio:
            r_th = _reflectance_ratio_theoretical_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        else:
            r_th = _reflectance_absolute_backside_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        e = np.asarray(r_exp_f, dtype=np.float64) - np.asarray(r_th, dtype=np.float64)

        sigma_r_f = np.maximum(fl, sc * np.abs(e))

    return sigma_t_f, sigma_r_f
def _chi2_masked_constant_sigma(
    cfg: SplineOptConfig,
    *,
    sigma_t: float,
    sigma_r: float,
    n_lam_full: np.ndarray,
    k_lam_full: np.ndarray,
    d_nm: float,
    sigma_t_f: np.ndarray | None = None,
    sigma_r_f: np.ndarray | None = None,
    masked_grid: tuple | None = None,
) -> float:
    """χ² on objective mask: constant sigma or sigma_i (vectors aligned with lam_f / exp_f).

    Pass *masked_grid* (pre-built via ``build_spline_objective_masked_grid``) to avoid
    rebuilding it on every call when used inside a multi-start loop.
    """

    if masked_grid is None:
        masked_grid = build_spline_objective_masked_grid(cfg)

    mg = masked_grid

    if mg is None:
        return float("nan")

    lam_f, _sig_f, n_sub_f, w, _inv_npix, t_exp_f, r_exp_f = mg

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    n_full = np.asarray(n_lam_full, dtype=np.float64).ravel()

    k_full = np.asarray(k_lam_full, dtype=np.float64).ravel()

    if n_full.size != lam_full.size or k_full.size != lam_full.size:
        return float("nan")

    n_f = np.interp(lam_f, lam_full, n_full)

    k_f = np.interp(lam_f, lam_full, k_full)

    chi = 0.0

    if cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and float(cfg.weight_t) > 0:
        if cfg.t_is_ratio:
            t_th = _ratio_theoretical_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        else:
            t_th = _transmittance_absolute_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        e = np.asarray(t_exp_f, dtype=np.float64) - t_th

        if sigma_t_f is not None:
            st = np.asarray(sigma_t_f, dtype=np.float64).ravel()

            if st.size != e.size:
                return float("nan")

            chi += float(cfg.weight_t) * float(np.dot(w, (e / st) ** 2))

        else:
            chi += float(cfg.weight_t) * float(np.dot(w, (e / float(sigma_t)) ** 2))

    if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and float(cfg.weight_r) > 0:
        if cfg.t_is_ratio:
            r_th = _reflectance_ratio_theoretical_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        else:
            # Consistent with objective: absolute backside reflection in non-ratio mode.

            r_th = _reflectance_absolute_backside_from_nk(lam_f, n_f, k_f, float(d_nm), n_sub_f)

        e = np.asarray(r_exp_f, dtype=np.float64) - r_th

        if sigma_r_f is not None:
            sr = np.asarray(sigma_r_f, dtype=np.float64).ravel()

            if sr.size != e.size:
                return float("nan")

            chi += float(cfg.weight_r) * float(np.dot(w, (e / sr) ** 2))

        else:
            chi += float(cfg.weight_r) * float(np.dot(w, (e / float(sigma_r)) ** 2))

    return float(chi) if np.isfinite(chi) else float("nan")
def _detect_corridor_spike(
    d_vals: list[float],
    rmse_vals: list[float],
    d_try: float,
    rm: float,
    d0: float,
    parab_tol_abs: float,
) -> tuple[bool, float, float, float]:
    """Detects if an RMSE point is an abnormal spike using local parabolic fit + discontinuity check."""
    is_spike = False
    rm_pred = float("nan")
    _tol_eff = float("nan")
    _sigma = float("nan")

    if len(d_vals) >= 5:
        try:
            _ds = np.asarray(d_vals[-12:], dtype=np.float64)
            _rs = np.asarray(rmse_vals[-12:], dtype=np.float64)
            _coeffs = np.polyfit(_ds - d0, _rs, 2)
            rm_pred = float(np.polyval(_coeffs, d_try - d0))

            _pred_hist = np.polyval(_coeffs, _ds - d0)
            _resid = _rs - _pred_hist
            _sigma = float(1.4826 * np.median(np.abs(_resid - np.median(_resid))))
            _tol_eff = max(parab_tol_abs, 3.0 * _sigma)

            parab_exceeds = bool(rm > rm_pred + _tol_eff)

            if parab_exceeds and len(rmse_vals) >= 2:
                rm_prev_step = float(rmse_vals[-1])
                delta_prev = abs(rm - rm_prev_step)
                if len(rmse_vals) >= 3:
                    _recent_deltas = np.abs(np.diff(np.asarray(rmse_vals[-6:], dtype=np.float64)))
                    _median_delta = float(np.median(_recent_deltas)) if _recent_deltas.size else 0.0
                else:
                    _median_delta = 0.0
                jump_ratio = delta_prev / max(_median_delta, 1e-12) if _median_delta > 1e-12 else float("inf")
                is_spike = bool(jump_ratio >= 2.5 or rm > rm_pred + max(parab_tol_abs * 2.0, 4.0 * _sigma))
            elif parab_exceeds:
                is_spike = True
        except (ValueError, TypeError, IndexError):
            import logging
            log = logging.getLogger('CERTUS')
            log.debug("INDEX_SPLINE [CORRIDOR ORCHESTRATOR] _detect_breakpoint: validation check failed (non-critical)")

    return is_spike, rm_pred, _tol_eff, _sigma
def quick_pwlnk_refit_result_dict(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    maxfun: int,
) -> dict[str, Any] | None:
    """V2.5: one L-BFGS-B polish on (d, nodes) - same objective as ``SplinePWLObjective`` (canonical mesh).

    Warm-start from ``base_result`` (segment vector) without rerunning Smart Init / Swanepoel.

    """

    from certus.spline.certus_index_spline_core import _bounds_x0_for_sigma_knots, make_bounds_and_x0

    from certus.spline.spline_objective import (
        SplinePWLObjective,
        build_segment_optimizer_x_vector,
        nk_from_x_pwlnk,
        spectral_mse_rmse_masked_from_nk,
    )

    try:
        pair = build_segment_optimizer_x_vector(base_result, cfg)

        if pair is not None:
            x0_vec, sk = pair

            sk = np.asarray(sk, dtype=np.float64).ravel()

            bounds, _x0_def, _L_lo, _L_hi = _bounds_x0_for_sigma_knots(cfg, sk)

            x0 = clip_to_bounds(np.asarray(x0_vec, dtype=np.float64).ravel(), bounds[:, 0], bounds[:, 1])

        else:
            bounds, x0_def, sk = make_bounds_and_x0(cfg, skip_smart_init=True)

            sk = np.asarray(sk, dtype=np.float64).ravel()

            x0 = clip_to_bounds(np.asarray(x0_def, dtype=np.float64).ravel(), bounds[:, 0], bounds[:, 1])

    except NUMERICAL_FAULT_EXCEPTIONS:
        log.debug("Bounds/x0 construction failed in quick_pwlnk_refit_result_dict", exc_info=True)

        return None

    obj = SplinePWLObjective(cfg, sk)

    bds = [(float(bounds[i, 0]), float(bounds[i, 1])) for i in range(int(bounds.shape[0]))]

    _use_fused = False

    if spline_pwl_analytic_grad_supported(cfg):
        _gt = obj.analytic_gradient(x0)

        if _gt is not None and np.all(np.isfinite(_gt)):
            _use_fused = True

    if _use_fused:
        res = minimize(
            obj.cost_and_grad,
            x0,
            method="L-BFGS-B",
            jac=True,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-10, "gtol": 1e-7},
        )
    else:
        res = minimize(
            obj,
            x0,
            method="L-BFGS-B",
            jac=None,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-10, "gtol": 1e-7},
        )

    xb = clip_to_bounds(np.asarray(res.x, dtype=np.float64).ravel(), bounds[:, 0], bounds[:, 1])

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    d_nm = float(xb[0])

    n_lam, k_lam = nk_from_x_pwlnk(
        xb,
        lam_full,
        sk,
        cfg.k_clip_lo,
        cfg.k_clip_hi,
        sig_pre=None,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=str(cfg.nk_profile_interp or "smooth"),
    )

    _mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, lam_full, n_lam, k_lam, d_nm)

    k_nodes = int(sk.size)

    n_slice = xb[1 : 1 + k_nodes]

    L_nodes = xb[1 + k_nodes : 1 + 2 * k_nodes]

    n_nodes_phys = (
        np.asarray(n_slice, dtype=np.float64).copy()
        if cfg.n_mono_band_nm is None
        else x_slice_n_to_physical_nodes(n_slice, sk, cfg.n_mono_band_nm)
    )

    out = dict(base_result)

    out.update(
        {
            "sigma_knots": sk,
            "sigma_knots_L": sk,
            "d_nm": d_nm,
            "n_lam": np.asarray(n_lam, dtype=np.float64).ravel(),
            "k_lam": np.asarray(k_lam, dtype=np.float64).ravel(),
            "n_nodes_physical": n_nodes_phys,
            "L_nodes": np.asarray(L_nodes, dtype=np.float64).ravel(),
            "rmse": float(rmse) if np.isfinite(rmse) else float(out.get("rmse", float("nan"))),
            "x": xb,
        }
    )

    return out