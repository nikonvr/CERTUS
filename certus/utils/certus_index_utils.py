from __future__ import annotations


import json

import logging

import time

from enum import Enum, auto

from typing import Any


import numpy as np

import pandas as pd


from certus.utils.errors import NUMERICAL_FAULT_EXCEPTIONS
from certus_physics import calculate_RT_vectorized_real, calculate_bare_substrate_RT


def log_structured_json_event(
    log: logging.Logger | None,
    channel: str,
    event: str,
    *,
    seq: str | None = None,
    **fields: Any,
) -> None:
    """Emit a single-line structured JSON log entry for machine parsing.

    Parameters
    ----------
    log : logging.Logger or None
        Target logger. No-op if None.
    channel : str
        Log channel prefix (e.g. ``SPLINE_PIPELINE_JSON``).
    event : str
        Event name embedded in the JSON payload.
    seq : str, optional
        Sequence tag for ordering in multi-phase pipelines.
    **fields
        Arbitrary key-value pairs added to the JSON payload.
    """

    if log is None:
        return

    payload: dict[str, Any] = {"event": str(event), "ts_epoch_s": float(time.time())}

    if seq is not None:
        payload["seq"] = str(seq)

    payload.update(fields)

    try:
        log.info("%s %s", channel, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))

    except (TypeError, *NUMERICAL_FAULT_EXCEPTIONS):
        # Silently ignore non-serializable fields (e.g. np.ndarray) or other encoding errors
        pass


def _ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute transmittance ratio T_film / T_bare_substrate (with backside).

    Parameters
    ----------
    lam : array_like
        Wavelengths in nm.
    n_l, k_l : array_like
        Film refractive index (n) and extinction coefficient (k), same size as *lam*.
    d_nm : float
        Film thickness in nm.
    n_sub : array_like
        Substrate refractive index, same size as *lam*.

    Returns
    -------
    np.ndarray
        T_film_total / T_substrate_bare, element-wise.
    """

    n_pts = len(lam)

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    # Exact R and T calculation (with backside)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    # Bare substrate T (with backside) - 1e-7 safety bound to prevent NaN

    t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam, n_sub), 1e-7)

    return t_film_tot / t_sub_nu


_THICK_BUF = np.empty(1, dtype=np.float64)  # Pre-allocated, rewritten in-place


def _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute absolute transmittance T_film_total (with backside correction).

    Same TMM call as :func:`_ratio_theoretical_from_nk` but without
    dividing by the bare substrate transmittance.

    Parameters
    ----------
    lam, n_l, k_l, d_nm, n_sub
        See :func:`_ratio_theoretical_from_nk`.

    Returns
    -------
    np.ndarray
        Absolute film transmittance, element-wise.
    """

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(len(lam), 1)

    # Exact R and T calculation (with backside)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    return t_film_tot


def _reflectance_ratio_theoretical_from_nk(lam, n_l, k_l, d_nm, n_sub):
    """Compute reflectance ratio R_film / T_bare_substrate.

    Used in the R/T_nu experimental protocol where both R and T are
    normalized by the bare substrate transmittance.

    Parameters
    ----------
    lam, n_l, k_l, d_nm, n_sub
        See :func:`_ratio_theoretical_from_nk`.

    Returns
    -------
    np.ndarray
        R_film_total / T_substrate_bare, element-wise.
    """

    n_pts = len(lam)

    _THICK_BUF[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    r_film_tot, t_film_tot = calculate_RT_vectorized_real(_THICK_BUF, n_layers_all, n_sub, lam, with_backside=True)

    t_sub_nu = np.maximum(calculate_bare_substrate_RT(lam, n_sub), 1e-7)

    return r_film_tot / t_sub_nu


def spectral_rmse_weights(lam, weight_space="log"):
    """Trapezoidal quadrature weights on ln(lambda) for spectral RMSE.

    Compensates non-uniform sampling density so that RMSE is not biased
    toward densely sampled spectral regions.

    Parameters
    ----------
    lam : array_like
        Wavelengths in nm (any order).
    weight_space : str, optional
        Reserved for future use. Currently always ``"log"``.

    Returns
    -------
    np.ndarray
        Weight array (same size as *lam*), normalized so that ``sum(w) == len(lam)``.
    """

    lam = np.asarray(lam, dtype=np.float64).ravel()

    n = lam.size

    if n < 2:
        return np.ones_like(lam)

    # Compute log(lambda) inter-distances

    log_lam = np.log(np.maximum(lam, 1e-9))

    # Gradient central (schema trapezoidal)

    w = np.zeros_like(log_lam)

    w[1:-1] = 0.5 * (log_lam[2:] - log_lam[:-2])

    w[0] = log_lam[1] - log_lam[0]

    w[-1] = log_lam[-1] - log_lam[-2]

    # Work with absolute values to handle decreasing grids

    w = np.abs(w)

    # Normalization: the sum of weights is equal to the number of points

    # to keep the RMSE consistent with the usual physical scale.

    sw = np.sum(w)

    if sw > 0:
        w = w * (float(n) / sw)

    else:
        w = np.ones_like(lam)

    return w


def _lam_uniform_grid(lo_h: float, hi_h: float, step: float) -> np.ndarray:
    """Generate a uniform wavelength grid snapped to multiples of *step*.

    Parameters
    ----------
    lo_h, hi_h : float
        Wavelength range bounds in nm.
    step : float
        Grid step in nm (e.g. 2.0, 5.0, 10.0).

    Returns
    -------
    np.ndarray
        Sorted grid points in [ceil(lo/step)*step, floor(hi/step)*step].
        Empty array if *lo_h* >= *hi_h* or non-finite.
    """

    if not (np.isfinite(lo_h) and np.isfinite(hi_h) and hi_h > lo_h):
        return np.array([], dtype=np.float64)

    st = float(np.ceil(lo_h / step) * step)

    en = float(np.floor(hi_h / step) * step)

    if en < st - 1e-9:
        return np.array([0.5 * (lo_h + hi_h)], dtype=np.float64)

    if abs(en - st) < 1e-9:
        return np.array([st], dtype=np.float64)

    return np.arange(st, en + 1e-9, step, dtype=np.float64)


def _sorted_finite_sigma_knots(sigma_knots) -> np.ndarray:
    """Clean and sort sigma knots: keep only finite, strictly positive values.

    Parameters
    ----------
    sigma_knots : array_like or None
        Raw knot positions in sigma space (1/nm).

    Returns
    -------
    np.ndarray
        Sorted unique finite knots (empty array if none valid).
    """

    arr = np.asarray(sigma_knots if sigma_knots is not None else [], dtype=np.float64).ravel()

    arr = arr[np.isfinite(arr) & (arr > 0.0)]

    if arr.size == 0:
        return np.empty(0, dtype=np.float64)

    return np.unique(np.sort(arr))


# --- Extracted helper functions from CERTUS_INDEX_SPLINE ---

from typing import Mapping

_D_SLIDER_STEPS_DEFAULT = 5000

def _get_substrate_n_array_spline(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Return substrate n(lambda), forcing Sapphire (id=3) to equation-based Sellmeier."""
    from certus_physics import get_n_substrate_array_by_id
    from certus.core.certus_core import SELLMEIER_COEFFS_BY_ID

    sid = int(substrate_id)
    wl_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    if sid != 3:
        return get_n_substrate_array_by_id(sid, wl_nm)

    coeffs = SELLMEIER_COEFFS_BY_ID.get(3)
    if coeffs is None or len(coeffs) != 6:
        raise KeyError("Missing Sellmeier coefficients for Sapphire (id=3).")

    B1, C1, B2, C2, B3, C3 = (float(v) for v in coeffs)
    wl_um = wl_nm / 1000.0
    wl_sq = wl_um * wl_um

    with np.errstate(divide="ignore", invalid="ignore"):
        n_sq = 1.0 + (B1 * wl_sq) / (wl_sq - C1) + (B2 * wl_sq) / (wl_sq - C2) + (B3 * wl_sq) / (wl_sq - C3)

    n = np.sqrt(np.maximum(n_sq, 1.0e-6))
    n = np.where(wl_nm < 230.0, np.nan, n)
    return n.astype(np.float64)


def _spectral_display_align(lam_nm: np.ndarray, *series: np.ndarray) -> tuple[np.ndarray, list[np.ndarray], np.ndarray]:
    """Truncates all series to the same length as lam_nm, then sorts by increasing lambda.

    Without this, a non-monotonic lambda file results in PyQtGraph lines that "smear"
    the spectrum (phantom oscillations) even if the experimental points remain correct in the scatter plot.
    Also returns ``order`` (indices) to reorder other arrays of the same pre-truncation.
    """
    lam = np.asarray(lam_nm, dtype=np.float64).ravel()
    if lam.size == 0:
        z = np.array([], dtype=np.int64)
        return lam, [np.asarray(s, dtype=np.float64).ravel()[:0] for s in series], z

    n_use = lam.size
    arrs: list[np.ndarray] = []
    for s in series:
        a = np.asarray(s, dtype=np.float64).ravel()
        n_use = min(n_use, a.size)
        arrs.append(a)

    if n_use <= 0:
        zf = np.array([], dtype=np.float64)
        zi = np.array([], dtype=np.int64)
        return zf, [zf.copy() for _ in series], zi

    if n_use != lam.size:
        logging.getLogger("CERTUS").warning(
            "Spectral display: inconsistent lengths (lambda=%d, truncation to %d).",
            lam.size,
            n_use,
        )

    lam_u = lam[:n_use]
    trimmed = [a[:n_use] for a in arrs]
    order = np.argsort(lam_u, kind="mergesort")
    lam_s = lam_u[order]
    out = [np.asarray(t)[order] for t in trimmed]
    return lam_s, out, order


def _d_from_slider_int(iv: int, d_lo_nm: float, d_hi_nm: float, steps: int = _D_SLIDER_STEPS_DEFAULT) -> float:
    """Convert slider integer position to thickness (nm)."""
    if d_hi_nm <= d_lo_nm + 1e-30:
        return float(d_lo_nm)
    t = float(iv) / float(steps)
    return float(d_lo_nm + t * (d_hi_nm - d_lo_nm))


def _slider_int_from_d_nm(dv: float, d_lo_nm: float, d_hi_nm: float, steps: int = _D_SLIDER_STEPS_DEFAULT) -> int:
    """Convert thickness (nm) to slider integer position."""
    if d_hi_nm <= d_lo_nm + 1e-30:
        return 0
    dv = float(np.clip(dv, d_lo_nm, d_hi_nm))
    t = (dv - d_lo_nm) / (d_hi_nm - d_lo_nm)
    return int(round(t * steps))


def _get_xv_spectral_coord(sx: float, mode: str) -> float:
    """Utility for spectral coordinate conversion (lambda / sigma / sigma2)."""
    if mode == "Sigma (nm?1)":
        return float(sx)
    elif mode == "Sigma2 (nm?2)":
        return float(sx) ** 2
    else:
        return 1.0 / float(sx) if sx != 0 else 0.0


def _stretch_sig_to_px(delta: float, span_sig2: float) -> int:
    """Calculate pixel stretch for sigma-based UI elements."""
    return max(1, int(max(0.0, float(delta)) / max(span_sig2, 1e-30) * 28000.0))


def _compute_study_lambda_window_nm(lam_m: np.ndarray, cfg: Any) -> tuple[float, float]:
    """Calculate the useful lambda band for display and RMSE calculation."""
    lam = np.asarray(lam_m, dtype=np.float64).ravel()
    ok = np.isfinite(lam) & (lam > 0)
    if not np.any(ok):
        return 400.0, 1200.0
    lo_d = float(np.min(lam[ok]))
    hi_d = float(np.max(lam[ok]))
    rw = getattr(cfg, "rmse_fit_lambda_nm", None)
    if rw is None:
        return lo_d, hi_d
    lo_w = float(min(rw[0], rw[1]))
    hi_w = float(max(rw[0], rw[1]))
    lo = max(lo_d, lo_w)
    hi = min(hi_d, hi_w)
    if hi <= lo:
        return lo_d, hi_d
    return lo, hi


def _rmse_d_lower_envelope_mask(d_nm: np.ndarray, rmse: np.ndarray, tol_nm: float) -> np.ndarray:
    """Boolean mask: point on the local lower thickness envelope (d +/- tol)."""
    d_a = np.asarray(d_nm, dtype=np.float64).ravel()
    r_a = np.asarray(rmse, dtype=np.float64).ravel()
    n = int(d_a.size)
    if n == 0 or r_a.size != n:
        return np.zeros(max(n, 0), dtype=bool)
    if not np.isfinite(tol_nm) or tol_nm <= 0.0:
        du = np.unique(d_a)
        if du.size >= 2:
            sp = float(np.median(np.diff(np.sort(du))))
        else:
            sp = 1.0
        tol_nm = max(1e-9, 0.55 * sp)
    keep = np.zeros(n, dtype=bool)
    for i in range(n):
        m = np.abs(d_a - d_a[i]) <= tol_nm
        keep[i] = float(r_a[i]) <= float(np.min(r_a[m])) + 1e-15
    return keep


def _filter_rmse_peaks_iteratively(
    d: np.ndarray,
    r: np.ndarray,
    *sidecars: np.ndarray,
) -> tuple[np.ndarray, ...]:
    """Remove points whose RMSE exceeds both neighbors; optional *sidecars stay row-aligned with (d, r)."""
    if d.size < 3:
        if sidecars:
            return (d, r) + tuple(np.asarray(s).copy() for s in sidecars)
        return d, r

    d_curr = d.copy()
    r_curr = r.copy()
    sc = [np.asarray(s).copy() for s in sidecars]
    changed = True
    while changed:
        changed = False
        n = d_curr.size
        if n < 3:
            break
        mask = np.ones(n, dtype=bool)
        for i in range(1, n - 1):
            if r_curr[i] > r_curr[i - 1] + 1e-15 and r_curr[i] > r_curr[i + 1] + 1e-15:
                mask[i] = False
                changed = True
        if changed:
            d_curr = d_curr[mask]
            r_curr = r_curr[mask]
            sc = [a[mask] for a in sc]
    if sidecars:
        return (d_curr, r_curr) + tuple(sc)
    return d_curr, r_curr


def _safe_int_from_mapping(m: Mapping[str, Any], key: str, default: int = -1) -> int:
    v = m.get(key, None)
    if v is None:
        return int(default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)


# --- Extracted helper functions from CERTUS_INDEX ---

from numba import njit

@njit(cache=True, fastmath=True, error_model="numpy")
def sellmeier_2poles_eval_nj(params, wl_um) -> np.ndarray:
    """Numba-compatible Sellmeier 2-poles model with constant A.
    params = [A, B1, L1, B2, L2] where Ci = Li^2
    n^2 = A + sum [ (Bi * wl^2) / (wl^2 - Ci) ]
    """
    A, B1, L1, B2, L2 = params
    term1_den = wl_um**2 - L1**2
    cond1 = np.abs(term1_den) < 1e-15
    sign1 = np.where(term1_den >= 0, 1.0, -1.0)
    term1_den = np.where(cond1, sign1 * 1e-15, term1_den)
    
    term2_den = wl_um**2 - L2**2
    cond2 = np.abs(term2_den) < 1e-15
    sign2 = np.where(term2_den >= 0, 1.0, -1.0)
    term2_den = np.where(cond2, sign2 * 1e-15, term2_den)
    
    term1 = (B1 * wl_um**2) / term1_den
    term2 = (B2 * wl_um**2) / term2_den
    val = A + term1 + term2
    return np.sqrt(np.maximum(val, 1e-6))


@njit(cache=True, fastmath=True, error_model="numpy")
def k_law_8p_eval(L_um, p) -> Any:
    """Numba-compatible 8-parameter empirical model for extinction coefficient k(lambda).
    k(L) = 1e-6 + exp(p[0]*L + p[1]) + exp(p[2]*L + p[3]) + p[4]*exp(-|(L-p[5])/p[6]|^p[7])
    """
    _lo, _hi = -25.0, 5.0
    _mid = 0.5 * (_lo + _hi)
    _scale = 2.0
    x1 = p[0] * L_um + p[1]
    x2 = p[2] * L_um + p[3]
    e1_arg = _mid + (0.5 * (_hi - _lo)) * np.tanh((x1 - _mid) / _scale)
    e2_arg = _mid + (0.5 * (_hi - _lo)) * np.tanh((x2 - _mid) / _scale)
    base1 = np.exp(e1_arg)
    base2 = np.exp(e2_arg)

    amp, center, width, exponent = p[4], p[5], p[6], p[7]
    w_safe = max(width, 1e-9)
    beta = max(min(exponent, 8.0), 1.0)
    arg = np.abs((L_um - center) / w_safe)
    gauss = amp * np.exp(-(arg**beta))
    return 1e-6 + base1 + base2 + gauss


def _deduce_knots_from_k8p(wl_um, p_k8, num_knots=8, min_knot_dist_um=0.05) -> Any:
    """Deduce the positions of the knots for the spline k from the curve k 8p."""
    from certus.core.certus_core import SMALL_EPSILON
    k_ref = k_law_8p_eval(wl_um, p_k8)
    log_k_ref = np.log(np.maximum(k_ref, SMALL_EPSILON))
    n_pts = len(wl_um)

    if n_pts < 4 or num_knots < 3:
        return np.linspace(wl_um.min(), wl_um.max(), max(3, num_knots))

    dlam = np.diff(wl_um)
    dlogk = np.diff(log_k_ref)
    dlogk_dlam = np.zeros_like(wl_um, dtype=np.float64)

    dlogk_dlam[0] = dlogk[0] / dlam[0] if dlam[0] > 1e-10 else 0.0
    dlogk_dlam[-1] = dlogk[-1] / dlam[-1] if dlam[-1] > 1e-10 else 0.0
    dlogk_dlam[1:-1] = (log_k_ref[2:] - log_k_ref[:-2]) / (wl_um[2:] - wl_um[:-2])

    curv = np.zeros(n_pts, dtype=np.float64)
    curv[1:-1] = np.abs((dlogk_dlam[2:] - dlogk_dlam[:-2]) / (wl_um[2:] - wl_um[:-2] + 1e-20))

    cum = np.zeros(n_pts + 1, dtype=np.float64)
    cum[1:] = np.cumsum(np.maximum(curv, 0.0))
    total = cum[-1]

    if total < 1e-20:
        return np.linspace(wl_um.min(), wl_um.max(), num_knots)

    knot_lam = np.empty(num_knots, dtype=np.float64)
    knot_lam[0] = wl_um.min()
    knot_lam[-1] = wl_um.max()

    t_vals = np.arange(1, num_knots - 1, dtype=np.float64) / float(num_knots - 1)
    targets = t_vals * total

    idx = np.searchsorted(cum[1:], targets)
    idx = np.clip(idx, 0, n_pts - 1)
    knot_lam[1 : num_knots - 1] = wl_um[idx]
    knot_lam = np.sort(knot_lam)

    for _ in range(10):
        bad = np.where(np.diff(knot_lam) < min_knot_dist_um)[0]
        if len(bad) == 0:
            break
        for i in bad:
            mid = (knot_lam[i] + knot_lam[i + 1]) * 0.5
            knot_lam[i] = mid - min_knot_dist_um * 0.5
            knot_lam[i + 1] = mid + min_knot_dist_um * 0.5
        knot_lam[0] = wl_um.min()
        knot_lam[-1] = wl_um.max()
        knot_lam = np.sort(knot_lam)

    return _ensure_strictly_increasing(knot_lam, min_gap=min_knot_dist_um * 0.5)


def _ensure_strictly_increasing(knot_lam: np.ndarray, min_gap: float = 1e-10) -> np.ndarray:
    """Guarantee a knot array is strictly increasing."""
    out = np.asarray(knot_lam, dtype=np.float64).copy()
    if out.size < 2:
        return out
    floor = np.arange(out.size, dtype=np.float64) * min_gap
    shifted = out - floor
    shifted = np.maximum.accumulate(shifted)
    out = shifted + floor
    return out


def _merge_closest_knot_pair(knot_lam_um: np.ndarray, log_k_values: np.ndarray) -> tuple:
    """Reduced by one node by merging the closest pair of consecutive nodes."""
    n = len(knot_lam_um)
    if n <= 2:
        return knot_lam_um.copy(), log_k_values.copy()
    gaps = np.diff(knot_lam_um)
    i_merge = int(np.argmin(gaps))
    lam_new = np.concatenate(
        [
            knot_lam_um[:i_merge],
            [(knot_lam_um[i_merge] + knot_lam_um[i_merge + 1]) * 0.5],
            knot_lam_um[i_merge + 2 :],
        ]
    )
    log_k_new = np.concatenate(
        [
            log_k_values[:i_merge],
            [(log_k_values[i_merge] + log_k_values[i_merge + 1]) * 0.5],
            log_k_values[i_merge + 2 :],
        ]
    )
    return lam_new, log_k_new


def sellmeier_2poles_eval(params, wl_um) -> Any:
    return sellmeier_2poles_eval_nj(params, wl_um)


def _sellmeier_residuals(params, wl_um, n_exp) -> Any:
    return (sellmeier_2poles_eval(params, wl_um) - n_exp) * 1000


def fit_sellmeier_global(
    wls_nm: np.ndarray, n_exp: np.ndarray, material: str = "other", valid_mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Robust 3-pole Sellmeier fit using differential_evolution to find the global minimum."""
    from scipy.optimize import differential_evolution, least_squares
    from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

    wl_um = wls_nm / 1000.0
    wl_fit = wl_um
    n_fit = n_exp
    if valid_mask is not None:
        wl_fit = wl_um[valid_mask]
        n_fit = n_exp[valid_mask]

    b_bounds = [(1.0, 16.0), (0.0, 20.0), (0.001, 1.0), (0.0, 20.0), (0.01, 20.0)]
    if str(material).lower() == "sio2":
        b_bounds = [(1.4, 1.5), (0.0, 2.0), (0.01, 0.15), (0.0, 2.0), (0.05, 0.25)]

    wl_min = float(wl_fit.min())
    wl_max = float(wl_fit.max())

    def cost_func(p) -> float:
        L1, L2 = p[2], p[4]
        if (wl_min < L1 < wl_max) or (wl_min < L2 < wl_max):
            return 1e9
        res = _sellmeier_residuals(p, wl_fit, n_fit)
        return float(np.sum(np.log1p(res**2)))

    try:
        res_global = differential_evolution(
            cost_func,
            bounds=b_bounds,
            strategy="best1bin",
            maxiter=1000,
            popsize=15,
            mutation=(0.5, 1.0),
            recombination=0.7,
            seed=42,
            polish=False,
        )

        ls_bounds_lo = [b[0] for b in b_bounds]
        ls_bounds_hi = [b[1] for b in b_bounds]

        L1_opt, L2_opt = res_global.x[2], res_global.x[4]
        if L1_opt <= wl_min:
            ls_bounds_hi[2] = min(ls_bounds_hi[2], wl_min - 1e-4)
        else:
            ls_bounds_lo[2] = max(ls_bounds_lo[2], wl_max + 1e-4)

        if L2_opt <= wl_min:
            ls_bounds_hi[4] = min(ls_bounds_hi[4], wl_min - 1e-4)
        else:
            ls_bounds_lo[4] = max(ls_bounds_lo[4], wl_max + 1e-4)

        res_local = least_squares(
            _sellmeier_residuals, res_global.x, bounds=(ls_bounds_lo, ls_bounds_hi), args=(wl_fit, n_fit), loss="soft_l1", f_scale=0.1
        )
        return sellmeier_2poles_eval(res_local.x, wl_um), res_local.x

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logging.getLogger("CERTUS").warning(f"Sellmeier fit failed: {e}. Falling back to raw spline n.")
        return n_exp, None


def fit_k_global_8p(
    wls_nm: np.ndarray, k_exp: np.ndarray, valid_mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray | None]:
    """Fit k with a robust 8-parameter empirical law."""
    from scipy.optimize import least_squares

    L_um = wls_nm / 1000.0
    mask = (k_exp > 1e-8) & (L_um >= 0.8)
    if valid_mask is not None:
        mask &= valid_mask

    if np.sum(mask) < 8:
        return k_exp, None

    L_fit = L_um[mask]
    k_fit = k_exp[mask]

    def obj_func(p, L, k_target) -> Any:
        fit = k_law_8p_eval(L, p)
        return np.log10(fit + 1e-9) - np.log10(k_target + 1e-9)

    p0 = [1.0, -10.0, 0.1, -15.0, 1e-4, 2.8, 0.2, 2.0]
    bounds = ([-20.0, -40.0, -20.0, -40.0, 0.0, 1.0, 0.01, 1.0], [20.0, 5.0, 20.0, 5.0, 1.0, 20.0, 5.0, 6.0])

    try:
        res = least_squares(obj_func, p0, bounds=bounds, args=(L_fit, k_fit), loss="soft_l1")
        k_smooth = k_law_8p_eval(L_um, res.x)
        k_smooth = np.where(L_um <= 1.0, k_exp, k_smooth)
        return k_smooth, res.x
    except Exception as e:
        logging.getLogger("CERTUS").warning(f"fit_k_global_8p failed: {e}")
        return k_exp, None


class DataType(Enum):
    """Spectral data type"""

    TRANSMISSION = auto()

    REFLECTION = auto()

    BOTH = auto()


def _detect_data_type_from_array(data: np.ndarray, threshold: float = 0.80) -> str:
    """Pure heuristic for spectral array detection."""
    data_copy = np.asarray(data, dtype=np.float64).copy()

    if data_copy.size == 0:
        return "T"

    if np.nanmax(data_copy) > 1.5:
        data_copy = data_copy / 100.0

    valid_data = data_copy[np.isfinite(data_copy)]

    if len(valid_data) == 0:
        return "T"

    mean_val = np.nanmean(valid_data)
    max_val = np.nanmax(valid_data)

    if mean_val > 0.50:
        return "T"

    if mean_val < 0.20 and max_val < 0.30:
        return "R"

    n_above_threshold = np.sum(valid_data > threshold)
    ratio_above = n_above_threshold / len(valid_data)

    if ratio_above > 0.10:
        return "T"

    if max_val > 0.95:
        return "T"

    return "R"


def _detect_type_from_column_name(col_name: str) -> str:
    """Detect data type from column header name.

    Returns 'T', 'R', or 'unknown'."""

    if col_name is None:
        return "unknown"

    name_lower = str(col_name).lower().strip()

    # Transmission patterns (incl. Tnu, T_nu = normalized T)

    t_patterns = ["t", "trans", "transmission", "%t", "t%", "t(%)", "tnu", "t_nu"]

    for pat in t_patterns:
        if name_lower == pat or name_lower.startswith(pat + " ") or name_lower.startswith(pat + "("):
            return "T"

    # Reflection patterns (incl. Rnu, R_nu = normalized R)

    r_patterns = ["r", "refl", "reflection", "%r", "r%", "r(%)", "rnu", "r_nu"]

    for pat in r_patterns:
        if name_lower == pat or name_lower.startswith(pat + " ") or name_lower.startswith(pat + "("):
            return "R"

    return "unknown"


def detect_data_type(data: np.ndarray, threshold: float = 0.80) -> str:
    """Detect if data represents transmission or reflection via statistical analysis.

    Heuristics:

    - Transmission typically has high values (>80% for most of spectrum)

    - Reflection typically has low values (<20% for uncoated substrates)

    - High-reflectance mirrors can have R > 95% - use physical constraints

    Returns 'T' or 'R'"""
    return _detect_data_type_from_array(data, threshold=threshold)


def analyze_loaded_data(df: pd.DataFrame) -> tuple[DataType, dict[str, np.ndarray]]:
    """Analyze a loaded DataFrame to detect data type.

    Detection priority:

    1. Column header names (if present: 'T', 'R', 'Trans', 'Refl', etc.)

    2. Statistical analysis of data distribution

    Returns (DataType, {'lambda': array, 'T': array or None, 'R': array or None})"""

    result = {
        "lambda": df.iloc[:, 0].to_numpy().astype(np.float64),
        "T": None,
        "R": None,
    }

    n_cols = len(df.columns)

    col_names = list(df.columns)

    if n_cols == 2:
        col2_data = df.iloc[:, 1].to_numpy().astype(np.float64)

        # Try column name first

        col2_header_type = _detect_type_from_column_name(col_names[1])

        if col2_header_type != "unknown":
            col2_type = col2_header_type

        else:
            col2_type = detect_data_type(col2_data)

        if col2_type == "T":
            result["T"] = col2_data

            return DataType.TRANSMISSION, result

        else:
            result["R"] = col2_data

            return DataType.REFLECTION, result

    elif n_cols >= 3:
        col2_data = df.iloc[:, 1].to_numpy().astype(np.float64)

        col3_data = df.iloc[:, 2].to_numpy().astype(np.float64)

        # Try column names first

        col2_header_type = _detect_type_from_column_name(col_names[1])

        col3_header_type = _detect_type_from_column_name(col_names[2])

        # If both headers detected, use them

        if col2_header_type != "unknown" and col3_header_type != "unknown":
            if col2_header_type == "T":
                result["T"] = col2_data

            else:
                result["R"] = col2_data

            if col3_header_type == "T":
                result["T"] = col3_data

            else:
                result["R"] = col3_data

            t_val = result.get("T")
            r_val = result.get("R")

            if t_val is not None and r_val is not None:
                return DataType.BOTH, result

            elif t_val is not None:
                return DataType.TRANSMISSION, result

            else:
                return DataType.REFLECTION, result

        # Fall back to statistical detection

        col2_type = col2_header_type if col2_header_type != "unknown" else detect_data_type(col2_data)

        col3_type = col3_header_type if col3_header_type != "unknown" else detect_data_type(col3_data)

        # Conflict or Ambiguity Resolution

        if col2_type == col3_type:
            # Both look like T or both look like R

            # User Rule: "The column with larger values corresponds to T"

            # User Hint: "Zoom towards IR" -> substrate usually transparent in IR

            # Use 95th percentile to robustly estimate "Max" without noise

            val2 = np.nanpercentile(col2_data, 95)

            val3 = np.nanpercentile(col3_data, 95)

            # If values are extremely close (e.g. difference < 5%), look at the IR/End of spectrum

            if abs(val2 - val3) < 0.05:
                # Assume sorted wavelengths? usually yes. Take last 20% points

                n_pts = len(col2_data)

                start_idx = int(0.8 * n_pts)

                val2_ir = np.nanmean(col2_data[start_idx:])

                val3_ir = np.nanmean(col3_data[start_idx:])

                # If IR distinct, use that

                if abs(val2_ir - val3_ir) > 0.02:
                    val2 = val2_ir

                    val3 = val3_ir

            if val2 > val3:
                result["T"] = col2_data

                result["R"] = col3_data

            else:
                result["R"] = col2_data

                result["T"] = col3_data

            return DataType.BOTH, result

        if col2_type == "T":
            result["T"] = col2_data

            result["R"] = col3_data

        else:
            result["R"] = col2_data

            result["T"] = col3_data

        return DataType.BOTH, result

    result["T"] = df.iloc[:, 1].to_numpy().astype(np.float64) if n_cols > 1 else np.array([])

    return DataType.TRANSMISSION, result


def _get_substrate_n_array_index(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Return substrate n(lambda), forcing Sapphire (id=3) to equation-based Sellmeier."""
    from certus_physics import get_n_substrate_array_by_id
    from certus.core.certus_core import SELLMEIER_COEFFS_BY_ID, SUBSTRATES

    sid = int(substrate_id)

    wl_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    if sid != 3:
        return get_n_substrate_array_by_id(sid, wl_nm)

    coeffs = SELLMEIER_COEFFS_BY_ID.get(3)

    if coeffs is None or len(coeffs) != 6:
        raise KeyError("Missing Sellmeier coefficients for Sapphire (id=3).")

    B1, C1, B2, C2, B3, C3 = (float(v) for v in coeffs)

    wl_um = wl_nm / 1000.0

    wl_sq = wl_um * wl_um

    with np.errstate(divide="ignore", invalid="ignore"):
        n_sq = 1.0 + (B1 * wl_sq) / (wl_sq - C1) + (B2 * wl_sq) / (wl_sq - C2) + (B3 * wl_sq) / (wl_sq - C3)

    n = np.sqrt(np.maximum(n_sq, 1.0e-6))

    min_lambda_nm = float(SUBSTRATES.get("Sapphire (Al2O3)", {}).get("min_lambda", 230.0))

    n = np.where(wl_nm < min_lambda_nm, np.nan, n)

    return n.astype(np.float64)


def normalize_index_config(cfg: dict) -> dict:
    """Normalize legacy/new CERTUS_INDEX JSON payloads for first-launch compatibility."""
    if not isinstance(cfg, dict):
        return {}
    out = dict(cfg)
    aliases = {
        # Substrate-only fields. Keep them separate from thin-film material fields.
        "substratee": "substrate",
        "substratee_choice": "substrate",
        "substrate_choice": "substrate",
        "file": "file_loaded",
        "source_file": "file_loaded",
        "data_mode": "data_type",
        "normalize": "normalized",
        "weight_t": "weight_T",
        "weight_r": "weight_R",
    }

    film_field_aliases = {
        # Thin-film material fields are intentionally NOT normalized from substrate keys.
        "h_material": "h_material_file",
        "l_material": "l_material_file",
        "h_file": "h_material_file",
        "l_file": "l_material_file",
    }
    for src, dst in film_field_aliases.items():
        if src in out and dst not in out:
            out[dst] = out[src]
    for src, dst in aliases.items():
        if src in out and dst not in out:
            out[dst] = out[src]
    sub_map = {
        "Sapphire (Al2O3)": "Al2O3",
        "Sapphire": "Al2O3",
        "Silicon (Si)": "Si",
        "Silicon": "Si",
        "Si-substrate": "Si",
        "D263T eco": "D263T",
        "Silice": "SiO2",
    }
    if out.get("substrate") in sub_map:
        out["substrate"] = sub_map[out["substrate"]]

    # Do not infer thin-film material fields from substrate fields.
    # `h_material_file` and `l_material_file` belong to film materials only.
    if "stack_multipliers" in out and isinstance(out["stack_multipliers"], list):
        out["stack_multipliers"] = [float(x) if str(x).strip() else 1.0 for x in out["stack_multipliers"]]
    if "stack_string" in out and not out.get("stack_multipliers"):
        try:
            out["stack_multipliers"] = [float(x.strip()) for x in str(out["stack_string"]).split(",") if x.strip()]
        except Exception:
            pass
    for key in ("thickness_min", "thickness_max", "exclude_min", "exclude_max", "weight_T", "weight_R", "l0", "wl_range_start", "wl_range_end", "wl_step", "scan_wl_min", "scan_wl_max", "scan_wl_step", "dynamics_threshold", "min_transmission_floor", "min_spectral_resolution", "mc_runs_block", "iter_divider_start", "iter_divider_end", "strategy_phase_timeout", "screening_mc_runs", "screening_keep_top_k", "trigger_tolerance", "sim_thickness_probe_offset_ratio", "non_monotonic_error_factor", "wavelength_change_penalty", "extrema_exclusion_ratio", "robustness_num_runs", "nucleation_mc_runs", "mining_candidates_limit", "n_screen_runs", "k_keep_survivors", "top_k_parents", "max_fusions_per_parent", "phase_a_scan_limit", "phase_a_keep_limit", "nucleation_max_rmse", "nucleation_degradation", "step0_sigma", "keep_full_mc_top_k", "sym_weight", "sym_same_wl_bonus", "sym_extrema_window", "sym_continuity_weight", "consensus_num_seeds", "consensus_seed_stride", "consensus_top_k", "consensus_num_runs", "consensus_std_weight"):
        if key in out and isinstance(out[key], str):
            try:
                out[key] = float(str(out[key]).replace(",", "."))
            except Exception:
                pass
    for key in ("frosted", "normalized", "exclude_oh", "strict_min_transmission_floor", "enforce_best_strategy_tmin_check", "sym_enable", "sym_adaptive_same_wl", "sym_allow_hybrid", "sym_prefer_on_tie", "enable_consensus_ranking", "show_plots", "export_excel", "force_first_layer_same_wl"):
        if key in out and isinstance(out[key], str):
            out[key] = str(out[key]).strip().lower() in {"1", "true", "yes", "on", "oui"}
    for key in ("robustness_noise_factors", "consensus_seed_list"):
        if key in out and isinstance(out[key], str):
            raw = str(out[key]).strip()
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    out[key] = json.loads(raw)
                except Exception:
                    pass
    return out


def calculate_index_rmse(mse: float) -> float:
    """Formalized index RMSE calculation from Mean Squared Error."""
    if mse < 0:
        return 0.0
    return float(np.sqrt(mse))


def calculate_rmse_from_arrays(calc: np.ndarray, target: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Compute Root Mean Squared Error (RMSE) between calculated and target arrays with optional weights."""
    from certus_physics import compute_mse_vectorized
    mse, _ = compute_mse_vectorized(calc, target, weights)
    return float(np.sqrt(np.maximum(mse, 0.0)))


