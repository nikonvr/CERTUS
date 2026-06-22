from __future__ import annotations
import numpy as np
from numba import njit
from scipy.interpolate import PchipInterpolator, CubicSpline
from certus.utils.certus_re_config import (
    RE_P4_BEAM_N_KNOTS,
    RE_SUB_CAUCHY_BARRIER_SQRT_W,
    RE_SUB_CAUCHY_TUBE_DELTA,
)


def _re_p4_beam_knots_lam_nm_from_wls(wls: np.ndarray, cfg: dict) -> np.ndarray:
    """N knots (nm) for chromatic beam: cfg ``re_p4_beam_ap_knots_nm`` (>=4 values) or linspace on grid."""

    wmin = float(np.min(wls))

    wmax = float(np.max(wls))

    if wmax <= wmin:
        wmax = wmin + 1.0

    nk = int(RE_P4_BEAM_N_KNOTS)

    ck = cfg.get("re_p4_beam_ap_knots_nm")

    if ck is not None:
        k = np.asarray(ck, dtype=np.float64).ravel()

        if k.size >= nk:
            kk = np.sort(
                np.clip(
                    k[:nk],
                    max(1.0, wmin * 0.5),
                    wmax * 1.5 + 1.0,
                )
            )

            return kk

    return np.linspace(wmin, wmax, nk, dtype=np.float64)


def _re_p4_sort_knot_pairs(knots_lam: np.ndarray, knots_ap: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(lambda_nm, ap_deg) sorted by lambda; length n = min(len(lam), len(ap)), n >= 1."""

    lam = np.asarray(knots_lam, dtype=np.float64).ravel()

    ap = np.asarray(knots_ap, dtype=np.float64).ravel()

    n = int(min(lam.size, ap.size))

    n = max(n, 1)

    lam = lam[:n].copy()

    ap = ap[:n].copy()

    order = np.argsort(lam, kind="mergesort")

    return lam[order], ap[order]


def _re_p4_chromatic_band_masks(wls_1d: np.ndarray, knots_lam: np.ndarray) -> list[np.ndarray]:
    """Splits lambda into n contiguous bands (thresholds = midpoints between sorted knot lambda)."""

    k = np.sort(np.asarray(knots_lam, dtype=np.float64).ravel().copy())

    n = int(k.size)

    w = np.asarray(wls_1d, dtype=np.float64)

    if n <= 1:
        return [np.ones(w.shape, dtype=bool)]

    t = np.array([0.5 * (k[i] + k[i + 1]) for i in range(n - 1)], dtype=np.float64)

    masks: list[np.ndarray] = [w <= t[0]]

    for i in range(1, n - 1):
        masks.append((w > t[i - 1]) & (w <= t[i]))

    masks.append(w > t[-1])

    return masks


def _re_p4_band_ap_deg(knots_lam: np.ndarray, knots_ap: np.ndarray, lam_c: float) -> float:
    """Stepwise constant ap: value of the knot associated with the band containing lam_c (sorted lambda)."""

    k, a = _re_p4_sort_knot_pairs(knots_lam, knots_ap)

    n = int(k.size)

    lam = float(lam_c)

    if n <= 1:
        return float(a[0])

    t = [0.5 * (k[i] + k[i + 1]) for i in range(n - 1)]

    if lam <= t[0]:
        return float(a[0])

    for i in range(1, n - 1):
        if lam <= t[i]:
            return float(a[i])

    return float(a[-1])


def _re_p4_ap_staircase_polyline(
    knots_lam: np.ndarray,
    knots_ap: np.ndarray,
    w_lo: float,
    w_hi: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Points (x,y) to plot ap(lambda) in steps (H/V segments) on [w_lo, w_hi]."""

    k, a = _re_p4_sort_knot_pairs(knots_lam, knots_ap)

    n = int(k.size)

    w_lo = float(w_lo)

    w_hi = float(w_hi)

    if n <= 1:
        return (
            np.array([w_lo, w_hi], dtype=np.float64),
            np.array([float(a[0]), float(a[0])], dtype=np.float64),
        )

    t = [0.5 * (k[i] + k[i + 1]) for i in range(n - 1)]

    xs: list[float] = [w_lo, t[0]]

    ys: list[float] = [float(a[0]), float(a[0])]

    for j in range(n - 1):
        xs.append(t[j])

        ys.append(float(a[j + 1]))

        if j < n - 2:
            xs.append(t[j + 1])

            ys.append(float(a[j + 1]))

    xs.append(w_hi)

    ys.append(float(a[-1]))

    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def _re_p4_ap_band_intervals_str(
    knots_lam: np.ndarray,
    knots_ap: np.ndarray,
    w_lo: float,
    w_hi: float,
) -> str:
    """Human-readable spectral intervals for P4 plateaus: [lambda_lo, lambda_hi] -> ap."""

    k, a = _re_p4_sort_knot_pairs(knots_lam, knots_ap)

    n = int(k.size)

    lo = float(min(w_lo, w_hi))

    hi = float(max(w_lo, w_hi))

    if n <= 1:
        return f"[{lo:.1f}, {hi:.1f}] nm -> ap={float(a[0]):.2f}"

    thr = np.array([0.5 * (k[i] + k[i + 1]) for i in range(n - 1)], dtype=np.float64)

    cuts = np.concatenate(([lo], thr, [hi]))

    parts: list[str] = []

    for i in range(n):
        b_lo = float(max(lo, cuts[i]))

        b_hi = float(min(hi, cuts[i + 1]))

        if b_hi < b_lo:
            continue

        parts.append(f"[{b_lo:.1f}, {b_hi:.1f}] nm -> ap={float(a[i]):.2f}")

    return " | ".join(parts) if parts else f"[{lo:.1f}, {hi:.1f}] nm -> ap=na"


def _re_p4_effective_half_width_deg(theta_deg: float, ap_total_deg: float) -> float:
    """Half-width h so theta+/-h stays in (0, 90) deg; reduces h if aperture would exceed physical range."""

    h = 0.5 * float(ap_total_deg)

    if h <= 0.0:
        return 0.0

    eps = 1e-6

    margin_lo = max(0.0, float(theta_deg) - eps)

    margin_hi = max(0.0, 90.0 - eps - float(theta_deg))

    h_lim = min(margin_lo, margin_hi)

    return float(min(h, h_lim))


def _re_deadzone_excess_abs(v: np.ndarray, eps: float) -> np.ndarray:
    """Portion of |v| beyond eps; 0 if |v|<=eps. eps<=0 -> |v| (no dead zone)."""

    va = np.asarray(v, dtype=np.float64)

    e = float(max(eps, 0.0))

    if e <= 0.0:
        return np.abs(va)

    return np.maximum(np.abs(va) - e, 0.0)


def format_re_drift_log_triplet_pct(a: float, b: float, f: float) -> str:
    """Single format for H / L / substrate Re-drift percents in logs and spectrum title."""

    return f"drift_Re[H]={a:+.3f}% drift_Re[L]={b:+.3f}% drift_Re[sub]={f:+.3f}%"




import logging








from dataclasses import dataclass, field


import re


import unicodedata


from typing import Any, Dict




import numpy as np


from numba import njit


# RE front stack table: #, Mat, n@lambda0, QWOT, Thick(nm)


_RE_FT_COL_NUM = 0


_RE_FT_COL_MAT = 1


_RE_FT_COL_N = 2


_RE_FT_COL_QW = 3


_RE_FT_COL_THICK = 4


# RE phase-2 spline: 5 lambda for DeltaRe(H) and DeltaRe(L). Knot index 1 (nm) is optimized in RE_SPLINE_NODE2_BOUNDS_NM.


RE_SPLINE_NODE2_BOUNDS_NM = (1500.0, 2100.0)


RE_SPLINE_NODE2_DEFAULT_NM = 2000.0


RE_SPLINE_KNOTS_BASE_NM = np.array(
    [1100.0, 2600.0, 3600.0, 4800.0], dtype=np.float64
)  # knots at indices 0,2,3,4  index 1 is lam2


RE_SPLINE_N_KNOTS = 5


def re_knots_wavelengths(lam_node2_nm: float) -> np.ndarray:
    """Full knot lambda vector (nm); lam_node2_nm is RE knot #2 (between 1100 and 2600 nm)."""

    lam = float(lam_node2_nm)

    return np.array(
        [
            float(RE_SPLINE_KNOTS_BASE_NM[0]),
            lam,
            float(RE_SPLINE_KNOTS_BASE_NM[1]),
            float(RE_SPLINE_KNOTS_BASE_NM[2]),
            float(RE_SPLINE_KNOTS_BASE_NM[3]),
        ],
        dtype=np.float64,
    )


# Default knot grid (for len(), tests, fallback logs).


RE_SPLINE_KNOTS_NM = re_knots_wavelengths(RE_SPLINE_NODE2_DEFAULT_NM)


# |Delta Re|(lambda) envelope: monotone PCHIP (lazy init in re_envelope_max_delta_n).


_re_envelope_pchip = None


def re_envelope_max_delta_n(wls_nm: np.ndarray, *, scale: float = 1.0) -> np.ndarray:
    """Max |Delta Re|  smooth increasing curve (PCHIP), ~0.05 -> ~0.15 -> ~0.20; ``scale`` (e.g. 0.5) scales amplitude."""

    global _re_envelope_pchip

    if _re_envelope_pchip is None:
        from scipy.interpolate import PchipInterpolator

        # Same shape as legacy visible / mid-IR track; long-wavelength cap ~0.20.

        wx = np.array(
            [280.0, 1000.0, 2200.0, 2800.0, 3600.0, 4000.0, 4800.0, 5200.0, 7500.0],
            dtype=np.float64,
        )

        vx = np.array(
            [0.05, 0.05, 0.05, 0.125, 0.15, 0.15, 0.18, 0.20, 0.21],
            dtype=np.float64,
        )

        _re_envelope_pchip = PchipInterpolator(wx, vx, extrapolate=True)

    w = np.asarray(wls_nm, dtype=np.float64)

    out = np.asarray(_re_envelope_pchip(w), dtype=np.float64)

    out = np.clip(out, 0.03, 0.25)

    s = float(scale)

    if not np.isfinite(s) or s <= 0.0:
        s = 1.0

    return out * s


# S3: LRU cache keyed on (rounded knots ×0.1nm, rounded wls ×1nm)  typically ~5 distinct lam2 values.


_re_bmat_cache: dict = {}


_RE_BMAT_CACHE_MAXSIZE = 12


def re_compute_spline_basis_matrix(
    knot_wl_nm: np.ndarray,
    wls_query_nm: np.ndarray,
) -> np.ndarray:
    """Precompute matrix B_ij such that S(lambda_i) = sum_j B_ij * d_j for a natural CubicSpline.

    Builds the basis by evaluating unit vectors e_j. Constant extrapolation outside knot

    domain, like ``re_interp_delta_knots_clamped``.

    Returns shape (len(wls_query), len(knot_wl)).

    LRU-cached: same knot grid + same wls grid -> O(1) lookup.

    """

    from scipy.interpolate import CubicSpline

    k = np.asarray(knot_wl_nm, dtype=np.float64).ravel()

    wq = np.asarray(wls_query_nm, dtype=np.float64).ravel()

    # Cache key: round knots to 0.1 nm, wls to 1 nm to tolerate float noise.

    _key = (tuple(np.round(k, 1).tolist()), tuple(np.round(wq, 0).tolist()))

    cached = _re_bmat_cache.get(_key)

    if cached is not None:
        return cached

    B = np.zeros((wq.size, k.size), dtype=np.float64)

    if k.size < 4:
        for i in range(k.size):
            ei = np.zeros(k.size, dtype=np.float64)
            ei[i] = 1.0

            B[:, i] = np.interp(wq, k, ei, left=ei[0], right=ei[-1])

    else:
        m_left = wq < k[0]

        m_right = wq > k[-1]

        m_mid = ~(m_left | m_right)

        wq_mid = wq[m_mid]

        for i in range(k.size):
            ei = np.zeros(k.size, dtype=np.float64)
            ei[i] = 1.0

            cs = CubicSpline(k, ei, bc_type="natural", extrapolate=False)

            col = np.empty(wq.shape, dtype=np.float64)

            if np.any(m_left):
                col[m_left] = ei[0]

            if np.any(m_right):
                col[m_right] = ei[-1]

            if np.any(m_mid):
                col[m_mid] = cs(wq_mid)

            B[:, i] = col

    if len(_re_bmat_cache) >= _RE_BMAT_CACHE_MAXSIZE:
        # Evict oldest entry (insertion order in Python 3.7+)

        _re_bmat_cache.pop(next(iter(_re_bmat_cache)))

    _re_bmat_cache[_key] = B

    return B


@njit(cache=True)
def re_compute_tikhonov_weights(knot_wls: np.ndarray, data_wls: np.ndarray) -> np.ndarray:
    """

    Computes adaptive Tikhonov weights for the discrete 2nd derivative penalty of spline knots.

    The penalty on knot i relates to the interval [knot[i-1], knot[i+1]].

    We count how many data points fall into this interval.

    Fewer points -> larger weight (stronger smoothing where no data).

    """

    _nk = len(knot_wls)

    weights = np.ones(_nk - 2, dtype=np.float64)

    if len(data_wls) == 0:
        return weights * 10.0

    for i in range(1, _nk - 1):
        w_min = knot_wls[i - 1]

        w_max = knot_wls[i + 1]

        count = 0.0

        for dw in data_wls:
            if w_min <= dw <= w_max:
                count += 1.0

        # Weight goes to 1.0 (max) if count=0. Drops as count increases (say count=50 -> w=0.09)

        weights[i - 1] = 1.0 / (1.0 + count / 5.0)

    return weights


def re_interp_delta_knots_clamped(
    knot_wl_nm: np.ndarray,
    d_knots: np.ndarray,
    wls_query_nm: np.ndarray,
    *,
    envelope_scale: float = 1.0,
    envelope_max: np.ndarray | None = None,
) -> np.ndarray:
    """Natural cubic (C2) spline of Delta Re at knot lambdas, then clamp to envelope.

    Outside [lambda_min, lambda_max] of knots: constant extrapolation (= end knot values),

    like legacy linear interp. Fewer than 4 knots: fall back to ``np.interp``.

    If ``envelope_max`` is given (same length as ``wls_query``), skip a second PCHIP call

    (shared H/L path in ``re_apply_re_index_model``).

    """

    k = np.asarray(knot_wl_nm, dtype=np.float64).ravel()

    d = np.asarray(d_knots, dtype=np.float64).ravel()

    wq = np.asarray(wls_query_nm, dtype=np.float64).ravel()

    if k.size < 2 or d.size < 2:
        di = np.full(wq.shape, float(d[0]) if d.size else 0.0, dtype=np.float64)

    elif k.size < 4:
        di = np.interp(wq, k, d, left=float(d[0]), right=float(d[-1]))

    else:
        from scipy.interpolate import CubicSpline

        cs = CubicSpline(k, d, bc_type="natural", extrapolate=False)

        di = np.empty(wq.shape, dtype=np.float64)

        m_left = wq < k[0]

        m_right = wq > k[-1]

        m_mid = ~(m_left | m_right)

        if np.any(m_left):
            di[m_left] = float(d[0])

        if np.any(m_right):
            di[m_right] = float(d[-1])

        if np.any(m_mid):
            di[m_mid] = np.asarray(cs(wq[m_mid]), dtype=np.float64)

    if envelope_max is None:
        env = re_envelope_max_delta_n(wq, scale=envelope_scale)

    else:
        env = np.asarray(envelope_max, dtype=np.float64)

    return np.clip(di, -env, env)


def re_apply_re_index_model(
    n_layers_nominal: np.ndarray,
    n_sub_nominal: np.ndarray,
    *,
    is_H: np.ndarray,
    is_L: np.ndarray,
    wls_nm: np.ndarray,
    lambda_ref_nm: float,
    a_pct: float = 0.0,
    b_pct: float = 0.0,
    f_pct: float = 0.0,
    spline_dH: np.ndarray | None = None,
    spline_dL: np.ndarray | None = None,
    spline_lam_node2_nm: float | None = None,
    re_envelope_scale: float = 1.0,
    re_envelope_at_wls: np.ndarray | None = None,
    spline_basis_matrix: np.ndarray | None = None,
    sub_cauchy_theta: tuple[float, float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (n_layers, n_sub) with RE correction  cubic DeltaRe(H/L) splines if valid knot arrays,

    else legacy Re scale via a_pct/b_pct/f_pct and cubic lambda law. Im(n) unchanged.

    ``re_envelope_at_wls``: |DeltaRe| envelope already evaluated on ``wls_nm`` (same length), to avoid

    recomputing PCHIP on every call (RE worker).

    ``sub_cauchy_theta``: if not None, Re(substrate) = a0+a1(lambdaref/lambda)2+a2(lambdaref/lambda)4; tabulated Im(sub) unchanged.

    """

    complex_dtype = np.complex128

    wls = np.asarray(wls_nm, dtype=np.float64).ravel()

    n_layers_nominal = np.asarray(n_layers_nominal, dtype=complex_dtype)

    n_sub_nominal = np.asarray(n_sub_nominal, dtype=complex_dtype)

    lambda_ref = float(lambda_ref_nm)

    wls_drift_denom = max(5200.0 - lambda_ref, 1.0)

    t_arr = np.clip((wls - lambda_ref) / wls_drift_denom, 0.0, None)

    drift_factor = t_arr**3

    _nksp = int(RE_SPLINE_N_KNOTS)

    use_sp = (
        spline_dH is not None
        and spline_dL is not None
        and len(np.asarray(spline_dH).ravel()) == _nksp
        and len(np.asarray(spline_dL).ravel()) == _nksp
    )

    if use_sp:
        lam2 = float(spline_lam_node2_nm) if spline_lam_node2_nm is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

        knot_wl = re_knots_wavelengths(lam2)

        if re_envelope_at_wls is not None:
            _pre = np.asarray(re_envelope_at_wls, dtype=np.float64).ravel()

            _env_wls = _pre if _pre.size == wls.size else re_envelope_max_delta_n(wls, scale=re_envelope_scale)

        else:
            _env_wls = re_envelope_max_delta_n(wls, scale=re_envelope_scale)

        if spline_basis_matrix is not None:
            dHv = spline_basis_matrix @ np.asarray(spline_dH, dtype=np.float64)

            dLv = spline_basis_matrix @ np.asarray(spline_dL, dtype=np.float64)

            np.clip(dHv, -_env_wls, _env_wls, out=dHv)

            np.clip(dLv, -_env_wls, _env_wls, out=dLv)

        else:
            dHv = re_interp_delta_knots_clamped(
                knot_wl, np.asarray(spline_dH, dtype=np.float64), wls, envelope_max=_env_wls
            )

            dLv = re_interp_delta_knots_clamped(
                knot_wl, np.asarray(spline_dL, dtype=np.float64), wls, envelope_max=_env_wls
            )

        n_real = n_layers_nominal.real.copy()

        n_imag = n_layers_nominal.imag.copy()

        for il in range(n_layers_nominal.shape[0]):
            if is_H[il]:
                n_real[il, :] += dHv

            elif is_L[il]:
                n_real[il, :] += dLv

        n_layers_out = n_real + 1j * n_imag

        n_sub_out = np.ascontiguousarray(n_sub_nominal.copy())

    else:
        n_layers_out = n_layers_nominal.copy()

        n_sub_out = n_sub_nominal.copy()

        if abs(a_pct) > 1e-12 or abs(b_pct) > 1e-12:
            n_real = n_layers_out.real.copy()

            n_imag = n_layers_out.imag.copy()

            n_real[is_H] *= 1.0 + (a_pct / 100.0) * drift_factor

            n_real[is_L] *= 1.0 + (b_pct / 100.0) * drift_factor

            n_layers_out = n_real + 1j * n_imag

        if abs(f_pct) > 1e-12:
            n_sub_out = n_sub_out.real * (1.0 + (f_pct / 100.0) * drift_factor) + 1j * n_sub_out.imag

            n_sub_out = np.ascontiguousarray(n_sub_out.astype(complex_dtype, copy=False))

    if sub_cauchy_theta is not None:
        a0, a1, a2 = (
            float(sub_cauchy_theta[0]),
            float(sub_cauchy_theta[1]),
            float(sub_cauchy_theta[2]),
        )

        n_sub_re = re_substrate_cauchy_n_re_from_theta(wls, lambda_ref, np.array([a0, a1, a2], dtype=np.float64))

        _im_sub = np.imag(np.asarray(n_sub_out, dtype=complex_dtype))

        n_sub_out = np.asarray(n_sub_re + 1j * _im_sub, dtype=complex_dtype)

    return (
        np.asarray(n_layers_out, dtype=complex_dtype),
        np.asarray(n_sub_out, dtype=complex_dtype),
    )


def re_substrate_cauchy_phi_matrix(wls_nm: np.ndarray, lambda_ref_nm: float) -> np.ndarray:
    """Columns [1, (lambdaref/lambda)2, (lambdaref/lambda)4] for n_Re(lambda) =  @ ."""

    w = np.asarray(wls_nm, dtype=np.float64).ravel()

    lr = max(float(lambda_ref_nm), 1e-9)

    r = lr / np.maximum(w, 1e-9)

    u2 = r * r

    u4 = u2 * u2

    return np.column_stack((np.ones_like(w), u2, u4))


def re_substrate_cauchy_n_re_from_theta(
    wls_nm: np.ndarray,
    lambda_ref_nm: float,
    theta: np.ndarray,
) -> np.ndarray:
    """Re(substrate) on wls_nm from  = (a0,a1,a2)."""

    Phi = re_substrate_cauchy_phi_matrix(wls_nm, lambda_ref_nm)

    t = np.asarray(theta, dtype=np.float64).ravel()[:3]

    return (Phi @ t).astype(np.float64, copy=False)


def re_substrate_cauchy_initial_theta(
    n_tab: np.ndarray,
    wls_nm: np.ndarray,
    lambda_ref_nm: float,
    *,
    delta: float = RE_SUB_CAUCHY_TUBE_DELTA,
) -> np.ndarray | None:
    """Feasible  (lstsq then linprog if needed) or None if feasible polyhedron is empty."""

    from scipy.optimize import linprog

    y = np.asarray(n_tab, dtype=np.float64).ravel()

    w = np.asarray(wls_nm, dtype=np.float64).ravel()

    if y.size != w.size or y.size < 1:
        return None

    Phi = re_substrate_cauchy_phi_matrix(w, lambda_ref_nm)

    coef, _, rank, _ = np.linalg.lstsq(Phi, y, rcond=None)

    if rank < 1:
        return None

    th = np.asarray(coef, dtype=np.float64).ravel()[:3].copy()

    pred = Phi @ th

    d = float(delta)

    if np.max(np.abs(pred - y)) <= d + 1e-12:
        return th


    A_ub = np.vstack((Phi, -Phi))

    b_ub = np.concatenate((y + d, -y + d))

    res = linprog(
        np.zeros(3, dtype=np.float64),
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=[(None, None)] * 3,
        method="highs",
    )

    if not res.success or res.x is None:
        return None

    th2 = np.asarray(res.x, dtype=np.float64).ravel()[:3]

    pred2 = Phi @ th2

    if np.max(np.abs(pred2 - y)) > d + 1e-8:
        return None

    return th2


def re_substrate_cauchy_barrier_residuals_jac(
    theta: np.ndarray,
    Phi: np.ndarray,
    n_tab: np.ndarray,
    *,
    delta: float = RE_SUB_CAUCHY_TUBE_DELTA,
    sqrt_w: float = RE_SUB_CAUCHY_BARRIER_SQRT_W,
) -> tuple[np.ndarray, np.ndarray]:
    """Hinge residuals √wmax(0,+/-(n)) and Jacobian (2N, 3)."""

    t = np.asarray(theta, dtype=np.float64).ravel()[:3]

    pred = Phi @ t

    y = np.asarray(n_tab, dtype=np.float64).ravel()

    sw = float(sqrt_w)

    d = float(delta)

    eu = np.maximum(0.0, pred - y - d)

    el = np.maximum(0.0, y - d - pred)

    r = np.concatenate((sw * eu, sw * el))

    n = y.size

    J = np.zeros((2 * n, 3), dtype=np.float64)

    for i in range(n):
        if eu[i] > 0.0:
            J[i, :] = sw * Phi[i, :]

        if el[i] > 0.0:
            J[n + i, :] = -sw * Phi[i, :]

    return r, J


