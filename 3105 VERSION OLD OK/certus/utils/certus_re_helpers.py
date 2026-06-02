from __future__ import annotations








from certus.core.certus_core import create_module_environment, NUMERICAL_FAULT_EXCEPTIONS


from certus.workers.certus_re_worker_utils import (
    re_objective_wls_weight_log_trap,
    re_ranking_combined_rmse,
)


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


env = create_module_environment(__file__, "CERTUS_RE")


script_dir = env["script_dir"]


# =============================================================================


# FURTHER IMPORTS


# =============================================================================


RE_THICKNESS_SEARCH_RADIUS_PCT = 5


# RE TRF stopping tolerances (stricter than SciPy defaults; both phases).


RE_TRF_FTOL = 1e-11


RE_TRF_GTOL = 1e-8


# Legacy aliases (historic name was L-BFGS-B; solver is now TRF).


RE_LBFGSB_FTOL = RE_TRF_FTOL


RE_LBFGSB_GTOL = RE_TRF_GTOL


# Phase 2 (REWorker): FD step on spline-knot amplitudes (not Re %); RE_SPLINE_KNOTS_NM after numpy import.


RE_PHASE2_SPLINE_FD_STEP = 5e-5


# FD step (nm) for the optimizable wavelength of interior knot index 1 (second knot).


RE_PHASE2_LAM2_FD_STEP = 0.25


# RE phase 2a: L-BFGS-B on spline amplitudes only (thicknesses fixed to phase-1 end) before joint phase 2b.


# Set to 0 in cfg key ``re_phase2_spline_prefit_maxiter`` to skip.


RE_PHASE2_SPLINE_PREFIT_MAXITER = 45


# FD on spline / lambda2: if True, forward-difference Jacobian (~half the MSE evals vs centered)  faster phase 2a/2b.


RE_PHASE2_ONESIDED_SPLINE_FD = True


# Parallel FD (ThreadPoolExecutor): MSE blocks are independent  helps unless BLAS already uses all cores.


# If slow or CPU-saturated: set False or RE_PHASE2_FD_MAX_WORKERS=1, or OMP_NUM_THREADS=1.


RE_PHASE2_FD_PARALLEL = True


RE_PHASE2_FD_MAX_WORKERS = 0  # 0 -> min(8, os.cpu_count())


# Max L-BFGS-B iterations for the joint phase-2b optimization (ep + splines + lambda₂).


# Overridable in cfg via key ``re_phase2b_maxiter``.


RE_PHASE2B_MAXITER = 400


# Phase 2a prefit uses looser convergence (good init is enough; exact convergence wastes time).


# FTOL and GTOL for prefit = RE_LBFGSB_FTOL * factor, RE_LBFGSB_GTOL * factor.


RE_PHASE2A_PREFIT_TOL_FACTOR = 50.0


# Phase 4: beam (average +/-h); ap(lambda) in N steps (RE_P4_BEAM_N_KNOTS); 1D scan + joint TRF (expensive).


RE_PHASE4_APERTURE_SCAN_POINTS = 24


# 0 = scan only (fast). >0 = joint TRF polish (each nfev ~= one full FD Jacobian build).


RE_PHASE4_TRF_MAX_NFEV = 48


RE_PHASE4_TRF_TOL_FACTOR = 35.0


# Bounds (deg) on beam width at each wavelength knot (phase 4 chromatic aperture).


# Reduced zone: stepwise search on [1.0, 2.5] (override possible: cfg re_phase4_ap_bounds_deg).


RE_P4_BEAM_AP_BOUNDS_DEG = (1.0, 2.5)


RE_GUI_DEFAULT_BEAM_APERTURE_DEG = 0.5 * (RE_P4_BEAM_AP_BOUNDS_DEG[0] + RE_P4_BEAM_AP_BOUNDS_DEG[1])


# Finite-difference step (deg) on aperture knots for phase-4 TRF Jacobian block.


RE_P4_AP_FD_STEP_DEG = 1.0e-3


# Number of lambda knots (and ap opening steps) in phase 4 - independent ap, non-monotonic.


RE_P4_BEAM_N_KNOTS = 4


RE_RESULT_LABEL_WITH_DRIFT = "Deltaln(lambda) trap + splines Re(H,L)"


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


# Phase 2b: Re(substrate) = a0 + a1(lambdaref/lambda)2 + a2(lambdaref/lambda)4 ; tube |nn_tab| <=  at worker wavelengths.


RE_SUB_CAUCHY_TUBE_DELTA = 0.02


RE_SUB_CAUCHY_BARRIER_SQRT_W = 250.0


RE_PHASE2_SUB_CAUCHY_FD_STEP = 1e-5


# ---------------------------------------------------------------------------


# RE preset base (optimal batch): env ×0.5 or ×1, HL √(w)=4,  QWOT 0.05, Tikhonov 1, Cauchy substrate,


# RMSE _ref 0.05, iterations 85 / 45 / 110. GUI exposes only Slow / Medium / Fast (see RE_SPEED_PRESETS).


# ---------------------------------------------------------------------------


RE_GUI_DEFAULT_RE_ENV_FULL_SCALE = False  # False = low x0.5 envelope, True = full x1


RE_PRESET_ENVELOPE_SCALE = 0.5 if not RE_GUI_DEFAULT_RE_ENV_FULL_SCALE else 1.0


RE_GUI_DEFAULT_RE_QWOT_ALPHA = 0.05


# Fixed alpha for RMSE* = sqrt(RMSE_sp^2 + alpha_ref * RMS(delta Q)^2)  ranking across runs (raw QWOT, no dead zone).


RE_RANKING_ALPHA_REF = 0.05


# Pipeline partial best (stopped batch): p1ms2_p2tk3_p3sh4, RMSE* ~0.012781  see re_pipeline_best_partial.json


RE_GUI_DEFAULT_RE_PHASE1_RESTARTS = 2


RE_GUI_DEFAULT_RE_PHASE2_TOP_K = 3


RE_GUI_DEFAULT_RE_PHASE3_SHAKES = 4


RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV = 1.0


# Max TRF iterations (Medium preset = batch #1).


RE_GUI_DEFAULT_RE_PHASE1_MAXITER = 85


RE_GUI_DEFAULT_RE_PHASE2B_MAXITER = 110


# Regularization on Delta Re splines **H and L only** (not substrate): at each knot,


# r_k = sqrt(w)*(Delta Re_k / env(lambda_k))^2 -> LS cost scales ~ w * sum (Delta Re/env)^4.


# Config stores sqrt(w) directly, not w = (re_hl_delta_re_reg_sqrt_w)^2.


RE_HL_DELTA_RE_REG_SQRT_W = 0.4


# Dead zone: |Delta Re| <= eps -> no H/L penalty; same |Delta QW| <= eps for QWOT term (absolute units).


RE_RE_DEADZONE_DELTA_RE_ABS = 0.01


RE_RE_DEADZONE_QWOT_ABS = 0.01


RE_SPLINE_CORREC_KINDS = frozenset(("spline", "spline_cached", "spline_sub3", "spline_cached_sub3"))


# Substrate: no H/L-style Delta Re penalty; optional Cauchy fit inside the tube only.


RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT = True


# If |RMSE_sum_1 - RMSE_sum_2| <= tol * max(|RMSE_sum_1|, eps), keep only one phase-1 candidate for phase 2.


RE_PHASE2_TOP_K_MERGE_REL_TOL = 1e-6


# Speed presets (RE GUI only). Medium = same budget as optimal batch (RE_GUI_* defaults).


# Slow / Fast: more or less exploration (multistarts, top-K, shakes, maxiter); physics unchanged.


RE_SPEED_PRESETS = {
    "medium": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": int(RE_GUI_DEFAULT_RE_PHASE1_RESTARTS),
        "re_phase2_top_k": int(RE_GUI_DEFAULT_RE_PHASE2_TOP_K),
        "re_phase3_shake_rounds": int(RE_GUI_DEFAULT_RE_PHASE3_SHAKES),
        "re_phase2_spline_prefit_maxiter": int(RE_PHASE2_SPLINE_PREFIT_MAXITER),
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": int(RE_GUI_DEFAULT_RE_PHASE1_MAXITER),
        "re_phase2b_maxiter": int(RE_GUI_DEFAULT_RE_PHASE2B_MAXITER),
        "re_phase4_aperture_scan_points": int(RE_PHASE4_APERTURE_SCAN_POINTS),
        "re_phase4_trf_max_nfev": int(RE_PHASE4_TRF_MAX_NFEV),
    },
    "fast": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": 1,
        "re_phase2_top_k": 1,
        "re_phase3_shake_rounds": 0,
        "re_phase2_spline_prefit_maxiter": 24,
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": 50,
        "re_phase2b_maxiter": 72,
        "re_phase4_aperture_scan_points": 12,
        "re_phase4_trf_max_nfev": 0,
    },
    "slow": {
        "radius": float(RE_THICKNESS_SEARCH_RADIUS_PCT),
        "re_envelope_scale": float(RE_PRESET_ENVELOPE_SCALE),
        "re_qwot_penalty_weight": float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        "re_enable_qwot_penalty": True,
        "re_ranking_alpha_ref": float(RE_RANKING_ALPHA_REF),
        "re_phase2b_substrate_cauchy": bool(RE_GUI_DEFAULT_SUBSTRATE_CAUCHY_OPT),
        "re_refine_h": True,
        "re_refine_l": True,
        "re_phase1_multistarts": 4,
        "re_phase2_top_k": 5,
        "re_phase3_shake_rounds": 8,
        "re_phase2_spline_prefit_maxiter": 60,
        "re_spline_tikhonov_scale": float(RE_GUI_DEFAULT_RE_SPLINE_TIKHONOV),
        "re_hl_delta_re_reg_sqrt_w": float(RE_HL_DELTA_RE_REG_SQRT_W),
        "re_phase2_skip_spline_prefit": False,
        "re_qwot_per_phase_schedule": True,
        "re_qwot_adaptive_init_scale": False,
        "re_phase1_de_maxiter": 0,
        "re_phase1_maxiter": 120,
        "re_phase2b_maxiter": 160,
        "re_phase4_aperture_scan_points": 40,
        "re_phase4_trf_max_nfev": 96,
    },
}


# Wavelength grid for RMSE / EVAL: one point per active measurement target (Excel RE).


RE_OPTIM_POINTS_PER_TARGET = 1


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


# =============================================================================


# RE factored helpers (F1 + F2)  single source of truth for spectrum dispatch


# and correc-tuple -> re_apply_re_index_model mapping.


# =============================================================================


def _re_apply_correc(
    n_layers_nominal: np.ndarray,
    n_sub_nominal: np.ndarray,
    *,
    is_H: np.ndarray,
    is_L: np.ndarray,
    wls: np.ndarray,
    lambda_ref: float,
    correc: tuple,
    re_env_s: float = 1.0,
    env_cache: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Dispatch a correc-tuple to `re_apply_re_index_model`.

    *correc* is either ``("pct", a, b, f)`` for legacy drift-percent model,

    or ``("spline", dH_knots, dL_knots, lam_node2_nm)`` for cubic-spline DeltaRe,

    or ``("spline_cached", dH_knots, dL_knots, lam_node2_nm, B_matrix, env_wls)``

    for zero-allocation vectorised B-spline mapping,

    or ``("spline_cached_sub3", ..., tk_w, a0, a1, a2)`` / ``("spline_sub3", ..., a0, a1, a2)``

    for phase 2b (Cauchy substrate + tube; see RE_SUB_CAUCHY_* constants).

    """

    if correc[0] == "pct":
        return re_apply_re_index_model(
            n_layers_nominal,
            n_sub_nominal,
            is_H=is_H,
            is_L=is_L,
            wls_nm=wls,
            lambda_ref_nm=lambda_ref,
            a_pct=float(correc[1]),
            b_pct=float(correc[2]),
            f_pct=float(correc[3]),
            spline_dH=None,
            spline_dL=None,
            re_envelope_scale=re_env_s,
        )

    # Spline variants

    dh = np.asarray(correc[1], dtype=np.float64).ravel()

    dl = np.asarray(correc[2], dtype=np.float64).ravel()

    lam_spl = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

    B_mat = None

    env_wls_cached = env_cache

    sub_c = None

    if correc[0] in ("spline_cached", "spline_cached_sub3"):
        B_mat = correc[4]

        env_wls_cached = correc[5]

    if correc[0] == "spline_cached_sub3":
        sub_c = (float(correc[7]), float(correc[8]), float(correc[9]))

    elif correc[0] == "spline_sub3":
        if len(correc) >= 8 and isinstance(correc[4], np.ndarray):
            sub_c = (float(correc[5]), float(correc[6]), float(correc[7]))

        else:
            sub_c = (float(correc[4]), float(correc[5]), float(correc[6]))

    return re_apply_re_index_model(
        n_layers_nominal,
        n_sub_nominal,
        is_H=is_H,
        is_L=is_L,
        wls_nm=wls,
        lambda_ref_nm=lambda_ref,
        a_pct=0.0,
        b_pct=0.0,
        f_pct=0.0,
        spline_dH=dh,
        spline_dL=dl,
        spline_lam_node2_nm=lam_spl,
        re_envelope_scale=re_env_s,
        re_envelope_at_wls=env_wls_cached,
        spline_basis_matrix=B_mat,
        sub_cauchy_theta=sub_c,
    )


def _re_correc_to_nk_preview_payload(correc: tuple) -> dict[str, Any]:
    """Extract DeltaRe (knots), lambda₂ and Cauchy substrate from *correc* for the live n(lambda) tab."""

    out: dict[str, Any] = {
        "re_nk_preview_dH": None,
        "re_nk_preview_dL": None,
        "re_nk_preview_lam2": None,
        "re_nk_preview_sub012": None,
    }

    if not correc:
        return out

    tag = correc[0]

    if tag == "pct":
        return out

    if tag not in (
        "spline",
        "spline_cached",
        "spline_sub3",
        "spline_cached_sub3",
    ):
        return out

    dh = np.asarray(correc[1], dtype=np.float64).ravel()

    dl = np.asarray(correc[2], dtype=np.float64).ravel()

    lam = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

    out["re_nk_preview_dH"] = dh.tolist()

    out["re_nk_preview_dL"] = dl.tolist()

    out["re_nk_preview_lam2"] = lam

    if tag == "spline_cached_sub3" and len(correc) >= 10:
        out["re_nk_preview_sub012"] = [
            float(correc[7]),
            float(correc[8]),
            float(correc[9]),
        ]

    elif tag == "spline_sub3":
        if len(correc) >= 8 and isinstance(correc[4], np.ndarray):
            out["re_nk_preview_sub012"] = [
                float(correc[5]),
                float(correc[6]),
                float(correc[7]),
            ]

        elif len(correc) >= 7:
            out["re_nk_preview_sub012"] = [
                float(correc[4]),
                float(correc[5]),
                float(correc[6]),
            ]

    return out


def _re_calc_spectrum_for_config(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    ep: np.ndarray,
    n_sub: np.ndarray,
    angle: float,
    pol: str,
    include_backside: bool,
    phase4_average: bool = False,
    beam_aperture: float = 1.0,
    beam_aperture_knots_deg: np.ndarray | None = None,
    beam_aperture_knots_lam_nm: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute (R, T) for one physical config (angle × pol × backside model).

    RE does not model a rear stack: plate with or without a substrate rear-face

    (Fresnel) model, never an explicit rear coating.

    * ``include_backside``  semi-infinite (front only) vs inconsistent plate,

    * ``pol``  ``"s"`` / ``"p"`` / ``"Avg"`` (mean of s and p).

     * Phase 4 (``phase4_average``) - for incidence >= 10 deg: average of two angles

      ``theta +/- h`` with ``h`` = effective half-width from total beam width ``ap`` (deg);

      ``h`` is reduced so ``theta +/- h`` stays inside (0, 90) deg. If ``beam_aperture_knots_*``

      are set, ``ap(lambda)`` is **stepwise constant** between lambda knots (midpoints between

      consecutive sorted lambda); the ap per knot are independent (no monotonicity enforced).

      The fast path groups lambda by band and takes the knot ap value at the **mean lambda** of the band.

    """

    def _one_w(wl_s: np.ndarray, nlay_s: np.ndarray, nsub_s: np.ndarray, is_s: bool, a: float):

        p = "s" if is_s else "p"

        if not include_backside:
            return calc_spectrum_oblique_vectorized(wl_s, nlay_s, ep, nsub_s, a, p)

        return calc_spectrum_oblique_backside_vectorized(wl_s, nlay_s, ep, nsub_s, a, p)

    def _one(is_s: bool, a: float) -> tuple[np.ndarray, np.ndarray]:

        return _one_w(wls, n_layers_T, n_sub, is_s, a)

    def _eval_angle_w(wl_s, nlay_s, nsub_s, a: float):

        pl = str(pol).lower()

        if pl == "avg":
            Rs, Ts = _one_w(wl_s, nlay_s, nsub_s, True, a)

            Rp, Tp = _one_w(wl_s, nlay_s, nsub_s, False, a)

            return (Rs + Rp) * 0.5, (Ts + Tp) * 0.5

        return _one_w(wl_s, nlay_s, nsub_s, pl == "s", a)

    def _eval_angle(a: float):

        return _eval_angle_w(wls, n_layers_T, n_sub, a)

    if phase4_average and angle >= 10.0:
        ak = None if beam_aperture_knots_deg is None else np.asarray(beam_aperture_knots_deg, dtype=np.float64).ravel()

        lk = (
            None
            if beam_aperture_knots_lam_nm is None
            else np.asarray(beam_aperture_knots_lam_nm, dtype=np.float64).ravel()
        )

        if ak is not None and lk is not None and ak.size >= 2 and lk.size >= 2 and ak.size == lk.size:
            n = int(wls.size)

            R_acc = np.zeros(n, dtype=np.float64)

            T_acc = np.zeros(n, dtype=np.float64)

            masks = _re_p4_chromatic_band_masks(wls, lk)

            for m in masks:
                if not np.any(m):
                    continue

                lam_c = float(np.mean(wls[m]))

                ap_b = _re_p4_band_ap_deg(lk, ak, lam_c)

                h = _re_p4_effective_half_width_deg(angle, ap_b)

                nl = n_layers_T[m, :]

                ns = n_sub[m]

                ws = wls[m]

                if h <= 0.0:
                    R0, T0 = _eval_angle_w(ws, nl, ns, angle)

                    R_acc[m] = R0

                    T_acc[m] = T0

                else:
                    R1, T1 = _eval_angle_w(ws, nl, ns, angle - h)

                    R2, T2 = _eval_angle_w(ws, nl, ns, angle + h)

                    R_acc[m] = 0.5 * (R1 + R2)

                    T_acc[m] = 0.5 * (T1 + T2)

            return R_acc, T_acc

        h = _re_p4_effective_half_width_deg(angle, beam_aperture)

        if h <= 0.0:
            return _eval_angle(angle)

        R1, T1 = _eval_angle(angle - h)

        R2, T2 = _eval_angle(angle + h)

        return 0.5 * (R1 + R2), 0.5 * (T1 + T2)

    return _eval_angle(angle)


def _re_p4_kwargs_from_opt_result(best_r: Dict, cfg: Dict) -> Dict[str, Any]:
    """If *best_r* contains phase-4 knots, returns kwargs to align theory/RMSE with the beam fit."""

    _ak = best_r.get("re_p4_beam_ap_knots_deg")

    _nm = best_r.get("re_p4_beam_ap_knots_nm")

    if _ak is None or _nm is None:
        return {}

    ak = np.asarray(_ak, dtype=np.float64).ravel()

    nm = np.asarray(_nm, dtype=np.float64).ravel()

    n = int(min(ak.size, nm.size))

    if n < 2:
        return {}

    ap = float(
        best_r.get(
            "re_p4_aperture_deg",
            cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG),
        )
    )

    return {
        "phase4_average": True,
        "beam_aperture": ap,
        "beam_aperture_knots_deg": np.ascontiguousarray(ak[:n]),
        "beam_aperture_knots_lam_nm": np.ascontiguousarray(nm[:n]),
    }


def _re_oblique_config_groups(tgts: list) -> dict:

    from collections import defaultdict

    g: dict = defaultdict(list)

    for tgt in tgts:
        if not getattr(tgt, "on", True):
            continue

        g[(tgt.angle, tgt.pol, tgt.include_backside)].append(tgt)

    return g


def _re_rmse_oblique_weighted(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgts: list,
    *,
    phase4_average: bool = False,
    beam_aperture: float = 1.0,
    beam_aperture_knots_deg: np.ndarray | None = None,
    beam_aperture_knots_lam_nm: np.ndarray | None = None,
) -> float:
    """RE RMSE (Deltaln(lambda) trapezoidal weighting, same aggregation as the TRF least-squares objective)."""

    wt_lambda = re_objective_wls_weight_log_trap(wls)

    total_err = 0.0

    total_w = 0.0

    for (angle, pol, include_backside), tgt_list in _re_oblique_config_groups(tgts).items():
        R_c, T_c = _re_calc_spectrum_for_config(
            wls,
            n_layers_T,
            ep,
            n_sub,
            angle,
            pol,
            include_backside,
            phase4_average=phase4_average,
            beam_aperture=beam_aperture,
            beam_aperture_knots_deg=beam_aperture_knots_deg,
            beam_aperture_knots_lam_nm=beam_aperture_knots_lam_nm,
        )

        for tgt in tgt_list:
            mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)

            pos = np.where(mask)[0]

            if pos.size == 0:
                continue

            tgt_val = (tgt.tmin + tgt.tmax) / 2.0

            vals = R_c[pos] if tgt.target_type == "R" else T_c[pos]

            wt = wt_lambda[pos]

            ws = float(tgt.w)

            wt_sum = float(np.sum(wt))

            wy = wt * vals

            wy2_sum = float(np.dot(wy, vals))

            wy_sum = float(np.sum(wy))

            w_tgt_sum = ws * tgt_val

            w_tgt2_sum = ws * tgt_val * tgt_val

            total_err += (ws * wy2_sum) - (2.0 * w_tgt_sum * wy_sum) + (w_tgt2_sum * wt_sum)

            total_w += ws * wt_sum

    if total_w <= 1e-18:
        return float("nan")

    return float(np.sqrt(total_err / total_w))


def _re_rmse_combined_spectral_qwot(rmse_spectral: float, rmse_qwot: float, alpha_qwot: float) -> float:
    """Combined RMSE matching REWorker: √(RMSE_sp2 + RMSE_QWOT2). =0 -> spectral only."""

    return re_ranking_combined_rmse(rmse_spectral, rmse_qwot, alpha_qwot)


def _re_sort_results_best_for_table_and_apply(results: list) -> None:
    """In-place sort: ``results[0]`` = best ``rmse_combined`` (user objective), with spectral RMSE as a tie-break."""

    if len(results) < 2:
        return

    results.sort(
        key=lambda r: (
            float(r.get("rmse_combined", r.get("rmse", float("inf")))),
            float(r.get("rmse", float("inf"))),
        )
    )


def _re_objective_variance_fractions(
    rmse_spectral: float, rmse_qwot: float, alpha_qwot: float
) -> tuple[float, float, float]:
    """Fractions of sp2 and QWOT2 in RMSE2 = sp2 + QWOT2 (same convention as the objective)."""

    sp = max(float(rmse_spectral), 0.0)

    qw = max(float(rmse_qwot), 0.0)

    a = max(float(alpha_qwot), 0.0)

    sp2 = sp * sp

    qw_t = a * qw * qw

    den = sp2 + qw_t

    if den < 1e-30:
        return (0.5, 0.5, 0.0)

    comb = re_ranking_combined_rmse(rmse_spectral, rmse_qwot, alpha_qwot)

    return (sp2 / den, qw_t / den, comb)


def _re_diagnostic_action_hints(
    frac_sp: float,
    frac_qw_weighted: float,
    rmse_sp: float,
    rmse_qw: float,
    alpha: float,
) -> list[str]:
    """Short hints to tune settings (, splines, Excel design) after a real run."""

    hints: list[str] = []

    if frac_qw_weighted > 0.55:
        hints.append(
            "Objective dominated by the QWOT term (weighted by ) -> increase QWOT weight, "
            "or review QWOT / lambda₀ in the Excel design sheet."
        )

    if frac_sp > 0.55:
        hints.append(
            "Objective dominated by spectral error (Deltaln(lambda) trap) -> adjust DeltaRe envelope, splines, "
            "thicknesses (phase 1 radius), or weighting / quality of measurement channels."
        )

    if rmse_sp < 0.03 and rmse_qw > 0.12 and frac_sp > 0.35:
        hints.append(
            "Spectrum already low but QWOT still high -> risk of spectral fit at the expense of "
            "optical thickness at lambda₀; strengthen  in phase 2b or check design consistency."
        )

    if alpha < 0.04 and rmse_qw > 0.1:
        hints.append(
            f"={alpha:g} is modest for RMSE_QWOT{rmse_qw:.3f} -> QWOT penalty may stay secondary "
            "in TRF (residual  √DeltaQ2)."
        )

    if not hints:
        hints.append(
            "Spectral and QWOT terms comparable in RMSE: refine according to metrology priority "
            "(spectrum vs QWOT anchoring)."
        )

    return hints


def _re_log_objective_diagnostic(
    tag: str,
    rmse_spectral: float,
    rmse_qwot: float,
    alpha_qwot: float,
) -> None:
    """Structured log: RMSE breakdown and hints (same log file as a reverse_sample.xlsx run)."""

    fs, fq, comb = _re_objective_variance_fractions(rmse_spectral, rmse_qwot, alpha_qwot)

    hints = _re_diagnostic_action_hints(fs, fq, float(rmse_spectral), float(rmse_qwot), float(alpha_qwot))

    logging.info(
        "RE diag [%s] RMSE_sp=%.6f | RMSE_QWOT=%.6f | =%.4f -> RMSE=%.6f | "
        "shares in RMSE2 (sp2 vs QWOT2): %.0f%% / %.0f%%",
        tag,
        float(rmse_spectral),
        float(rmse_qwot),
        float(alpha_qwot),
        comb,
        100.0 * fs,
        100.0 * fq,
    )

    for h in hints:
        logging.info("RE diag [%s] -> %s", tag, h)


def _parse_re_rmse_combined_from_progress_message(msg: str) -> float | None:
    """Reads RMSE_facade / RMSE_combined / RMSE(curr) from REWorker messages (backup if signal is delayed)."""

    if not msg:
        return None

    #  in RE f-strings is often U+2211 (n-ary summation), not Greek  U+03A3.

    for pat in (
        r"RMSE_facade\(curr\)=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE_facade=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE[\u2211\u03A3]=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE_combined=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE\(curr\)=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"(?<![\w(])RMSE=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
    ):
        m = re.search(pat, msg)

        if m:
            try:
                x = float(m.group(1))

            except ValueError:
                continue

            if np.isfinite(x) and x >= 0.0:
                return x

    return None


def re_n_corr_at_lambda_ref(
    n_ref_nom_per_layer: np.ndarray,
    is_H: np.ndarray,
    is_L: np.ndarray,
    lref_arr: np.ndarray,
    re_envelope_scale: float,
    *,
    correc: tuple | None = None,
    spline_dH: np.ndarray | None = None,
    spline_dL: np.ndarray | None = None,
    spline_lam2_nm: float | None = None,
) -> np.ndarray:
    """Re(n) per layer at lambda_ref: tabulated + DeltaRe H/L - **unique** source for the QWOT term (TRF + RMSE).

    Priority: if ``correc`` is a spline tuple (worker), it takes precedence; otherwise ``spline_dH`` /

    ``spline_dL`` arrays (UI / export).

    """

    out = np.asarray(n_ref_nom_per_layer, dtype=np.float64).ravel().copy()

    _nk = int(RE_SPLINE_N_KNOTS)

    lr = np.asarray(lref_arr, dtype=np.float64).ravel()

    if lr.size == 0:
        lr = np.array([500.0], dtype=np.float64)

    esc = float(re_envelope_scale)

    iH = np.asarray(is_H, dtype=bool)

    iL = np.asarray(is_L, dtype=bool)

    if correc is not None and len(correc) > 0 and correc[0] in RE_SPLINE_CORREC_KINDS:
        dH = np.asarray(correc[1], dtype=np.float64).ravel()

        dL = np.asarray(correc[2], dtype=np.float64).ravel()

        lam2 = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

        kn = re_knots_wavelengths(lam2)

        dn_h = float(re_interp_delta_knots_clamped(kn, dH, lr, envelope_scale=esc)[0])

        dn_l = float(re_interp_delta_knots_clamped(kn, dL, lr, envelope_scale=esc)[0])

        out[iH] += dn_h

        out[iL] += dn_l

        return out

    if spline_dH is not None and spline_dL is not None:
        dh = np.asarray(spline_dH, dtype=np.float64).ravel()

        dl = np.asarray(spline_dL, dtype=np.float64).ravel()

        if dh.size == _nk and dl.size == _nk:
            lam2 = float(spline_lam2_nm) if spline_lam2_nm is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

            kn = re_knots_wavelengths(lam2)

            dn_h = float(re_interp_delta_knots_clamped(kn, dh, lr, envelope_scale=esc)[0])

            dn_l = float(re_interp_delta_knots_clamped(kn, dl, lr, envelope_scale=esc)[0])

            out[iH] += dn_h

            out[iL] += dn_l

    return out


def re_delta_qwot_per_layer(
    ep: np.ndarray,
    ep0: np.ndarray,
    n_ref_nom_per_layer: np.ndarray,
    is_H: np.ndarray,
    is_L: np.ndarray,
    lambda_ref: float,
    re_envelope_scale: float,
    lref_arr: np.ndarray,
    *,
    correc: tuple | None = None,
    spline_dH: np.ndarray | None = None,
    spline_dL: np.ndarray | None = None,
    spline_lam2_nm: float | None = None,
) -> np.ndarray:
    """Q_i = (4/lambda_ref)(n_corr_iep_i - n_tab_iep0_i) - identical to the TRF QWOT residual."""

    ep = np.asarray(ep, dtype=np.float64).ravel()

    ep0 = np.asarray(ep0, dtype=np.float64).ravel()

    nref = np.asarray(n_ref_nom_per_layer, dtype=np.float64).ravel()

    if ep.size != ep0.size or ep.size != nref.size or ep.size == 0:
        return np.zeros(0, dtype=np.float64)

    l0 = float(max(float(lambda_ref), 1e-9))

    kq = 4.0 / l0

    n_corr = re_n_corr_at_lambda_ref(
        nref,
        is_H,
        is_L,
        lref_arr,
        re_envelope_scale,
        correc=correc,
        spline_dH=spline_dH,
        spline_dL=spline_dL,
        spline_lam2_nm=spline_lam2_nm,
    )

    return kq * (n_corr * ep - nref * ep0)


def _re_qwot_rmse_abs_delta_at_l0(
    ep: np.ndarray,
    ep0: np.ndarray,
    stack: list,
    mats: dict,
    lambda_ref: float,
    is_H: np.ndarray,
    is_L: np.ndarray,
    *,
    spline_dH: np.ndarray | None,
    spline_dL: np.ndarray | None,
    spline_lam2_nm: float | None,
    re_envelope_scale: float,
    deadzone_abs: float = 0.0,
) -> float:
    """QWOT-related RMS at lambda₀: if deadzone_abs>0, RMS(max(0,|DeltaQ|)); else RMS(|DeltaQ|). DeltaQ = QQ_init."""

    ep = np.asarray(ep, dtype=np.float64).ravel()

    ep0 = np.asarray(ep0, dtype=np.float64).ravel()

    if ep.size != ep0.size or ep.size == 0:
        return 0.0

    n_lay = int(ep.size)

    l0 = float(max(float(lambda_ref), 1e-9))

    _lref = np.array([float(lambda_ref)], dtype=np.float64)

    n_ref_nom = np.array(
        [float(mats[stack[i].mat].get_nk(_lref).real[0]) for i in range(n_lay)],
        dtype=np.float64,
    )

    delta_q = re_delta_qwot_per_layer(
        ep,
        ep0,
        n_ref_nom,
        is_H,
        is_L,
        l0,
        float(re_envelope_scale),
        _lref,
        spline_dH=spline_dH,
        spline_dL=spline_dL,
        spline_lam2_nm=spline_lam2_nm,
    )

    if delta_q.size == 0:
        return 0.0

    ex = _re_deadzone_excess_abs(delta_q, float(deadzone_abs))

    return float(np.sqrt(np.mean(ex**2)))


def format_re_spline_knots_log(knot_wl: np.ndarray, dh: np.ndarray, dl: np.ndarray) -> str:

    parts = [
        f"lambda{float(knot_wl[i]):.0f}nm DeltaRe[H]={float(dh[i]):+.5f} DeltaRe[L]={float(dl[i]):+.5f}"
        for i in range(min(len(knot_wl), len(dh), len(dl)))
    ]

    return " | ".join(parts)


def re_drift_result_log_suffix(r: dict) -> str:
    """Concatenated optional drift fragments (leading space each) for one RE result dict row."""

    if r.get("re_dH_knots") is not None and r.get("re_dL_knots") is not None:
        try:
            kw = np.asarray(r.get("re_knots_nm", RE_SPLINE_KNOTS_NM), dtype=np.float64)

            dh = np.asarray(r["re_dH_knots"], dtype=np.float64)

            dl = np.asarray(r["re_dL_knots"], dtype=np.float64)

            _s = " " + format_re_spline_knots_log(kw, dh, dl)

            if r.get("re_sub_cauchy_a0") is not None:
                _s += (
                    f" | sub_Cauchy=({float(r['re_sub_cauchy_a0']):.5f},"
                    f"{float(r['re_sub_cauchy_a1']):.5f},{float(r['re_sub_cauchy_a2']):.5f})"
                )

            return _s

        except NUMERICAL_FAULT_EXCEPTIONS :
            pass

    parts: list[str] = []

    if "a" in r:
        parts.append(f" drift_Re[H]={r.get('a', 0):+.3f}%")

    if "b" in r:
        parts.append(f" drift_Re[L]={r.get('b', 0):+.3f}%")

    if "f" in r:
        parts.append(f" drift_Re[sub]={r.get('f', 0):+.3f}%")

    return "".join(parts)


# pyqtgraph configured in certus_ui, imported locally for use








# Conditional SVG Import


# =============================================================================


# IMPORTS MODULAR ARCHITECTURE


# =============================================================================


# Import Modular Architecture


# --- 1. CORE (Config, Constants, Utils) ---




# --- 4. DATA (IO, Reporting) ---




# --- 5. ERRORS (Validation, Messages) ---


# Direct import for warmup


# --- 2. PHYSICS (Models, TMM, Optimization) ---




from certus_physics import (
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
)


# --- 3. UI (Theme, Widgets) ---








# =============================================================================


# TABULAR MATERIAL (Reverse Engineering  bypasses Cauchy model)


# =============================================================================


class TabularMaterial:
    """Material backed by tabulated n(\u03bb) data instead of the Cauchy 2-point model.

    Used exclusively for Reverse Engineering loads.  ``get_nk(wls)`` returns

    values by linear interpolation (constant extrapolation at boundaries).

    The ``n4`` attribute is set to n(\u03bb_ref) so that ``init_thickness`` converts

    QWOT values correctly for the actual working wavelength.

    """

    _is_tabular: bool = True

    def __init__(self, wls_nm: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray | None = None, l0_ref: float = 500.0):

        self.wls_nm = np.asarray(wls_nm, dtype=np.float64)

        self.n_arr = np.asarray(n_arr, dtype=np.float64)

        self.k_arr = np.zeros_like(self.n_arr) if k_arr is None else np.asarray(k_arr, dtype=np.float64)

        # n4 = n(\u03bb_ref): used by init_thickness for correct QWOT\u2192nm conversion

        self.n4 = float(np.interp(l0_ref, self.wls_nm, self.n_arr, left=self.n_arr[0], right=self.n_arr[-1]))

        self.n7 = self.n4  # kept for code that reads n7 (not used in RE calcs)

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        """Returns (n + ik) as a complex array via linear interpolation."""

        wls_f = np.asarray(wls, dtype=np.float64)

        n_i = np.interp(wls_f, self.wls_nm, self.n_arr, left=self.n_arr[0], right=self.n_arr[-1])

        k_i = np.interp(wls_f, self.wls_nm, self.k_arr, left=self.k_arr[0], right=self.k_arr[-1])

        return (n_i + 1j * k_i).astype(np.complex128)


# =============================================================================


# RE measurement column header parser (incidence, pol, R/T, backside)


# =============================================================================


def _re_ascii_fold_lower(s: str) -> str:
    """Lowercase without accents (mixed Excel FR/EN labels)."""

    if not s:
        return ""

    s = unicodedata.normalize("NFD", str(s))

    return "".join(c for c in s.lower() if unicodedata.category(c) != "Mn")


_re_no_back_tokens = frozenset(
    {
        "nobk",
        "no-bk",
        "noback",
        "nobackside",
        "no-backside",
        "nobs",
        "semisub",
        "semi",
        "inf",
        "infinite",
        "frontonly",
        "subinf",
        "semiinf",
        # Acronyms for 1 side / 2 sides (often 1f / 2f in exports)
        "1f",
        "1face",
        "1-face",
        "singleface",
        "1-face-only",
        # FR (single token or abbreviation without space)
        "sansarriere",
        "sansverso",
        "faceavant",
        "recto",
        "monoface",
    }
)


_re_with_back_tokens = frozenset(
    {
        "withback",
        "with-bk",
        "withbk",
        "wbk",
        "plate",
        "finite",
        "backside",
        "wback",
        "2f",
        "2face",
        "2faces",
        "2-face",
        "twoface",
        "twofaces",
        "rear",
        "doubleface",
        # FR ( verso = back / return side)
        "derriere",
        "facedos",
        "verso",
    }
)


@dataclass(frozen=True, slots=True)
class ParsedREColumn:
    """Metadata for a spectral column (RE measurement sheet)."""

    target_type: str  # 'R' ou 'T'

    angle_deg: float

    pol: str  # 's', 'p', ou 'Avg'

    include_backside: bool

    raw_header: str

    #: User-facing messages when interpretation relies on assumptions.

    interpretation_notes: tuple[str, ...] = field(default_factory=tuple)


def _re_header_normalize_for_tokens(raw: str) -> str:
    """Normalize before splitting column titles (mixed Excel FR/EN)."""

    s = _re_cell_str(raw)

    s = re.sub(r",\s*", " ", s)

    # Common FR -> tokens already handled by the parser

    s = re.sub(
        r"sans\s*[-_/]?\s*arri[eee]res?",
        " noBK ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(
        r"face\s*[-_/]?\s*avant(?:\s+seule)?",
        " noBK ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(
        r"avec\s*[-_/]?\s*arri[eee]res?",
        " withback ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(r"\bincidence\b", " aoi ", s, flags=re.IGNORECASE)

    s = re.sub(r"\bmoyenne\b", " Avg ", s, flags=re.IGNORECASE)

    s = re.sub(r"\bnon[\s-]*polaris", " unpol ", s, flags=re.IGNORECASE)

    # Detach 1f / 2f glued after a letter (e.g. ``Rs1f``, ``RnoBKs2f``)

    s = re.sub(r"(?<=[A-Za-z])(1f|2f)\b", r" \1 ", s, flags=re.IGNORECASE)

    return s


def _re_header_tokens(raw_stripped: str) -> list[str]:
    """Split an RE label into tokens (robust: - _ / space, parentheses)."""

    s = _re_header_normalize_for_tokens(raw_stripped)

    parts = [p for p in re.split(r"[\s\-_,/]+", s) if p]

    out: list[str] = []

    for p in parts:
        t = p.strip()

        if len(t) >= 2 and t[0] in "([{" and t[-1] in ")]}":
            t = t[1:-1].strip()

        if t:
            out.append(t)

    return out


def parse_re_column_header(raw: str | None) -> ParsedREColumn:
    """Infer R/T, angle (deg), polarization, and backside model from a column title.

    Accepts **French and/or English** labels (accents normalized), e.g.

    ``Reflection 45 s noBK``, ``Transmission AOI 30 p``,

    ``R-45-s-noBK``, ``T-30-P-BACK``, ``R45s1f``, legacy ``R`` / ``T``.

    * **noBK-type tokens** -> front side only (see ``_re_no_back_tokens``).

    * **with-back tokens** -> inconsistent plate (see ``_re_with_back_tokens``).

    * If both no-back and with-back hints appear, raises ``ValueError``.

    Ambiguous cases are recorded in ``interpretation_notes`` (for logs and optional

    dialog when loading Excel).

    """

    raw_header = "" if raw is None else str(raw).strip()

    if not raw_header:
        raise ValueError("measurement column header is empty")

    legacy_u = _re_ascii_fold_lower(raw_header).upper()

    if legacy_u == "R":
        return ParsedREColumn("R", 0.0, "s", True, raw_header, ())

    if legacy_u == "T":
        return ParsedREColumn("T", 0.0, "s", True, raw_header, ())

    tokens = _re_header_tokens(raw_header)

    if not tokens:
        raise ValueError(f"cannot parse measurement header: {raw_header!r}")

    notes: list[str] = []

    assumed_rt = False

    t0 = tokens[0].upper()

    t0_fold = _re_ascii_fold_lower(tokens[0])

    # Order: transmission (avoids ambiguous "T...") then reflection / R... (excluding "reference").

    if t0_fold.startswith("transm") or (
        t0.startswith("T")
        and not t0_fold.startswith("travail")
        and not t0_fold.startswith("titre")
        and not t0_fold.startswith("taux")
    ):
        target_type = "T"

        rest = tokens[1:]

    elif (
        t0_fold.startswith("refle")
        or t0_fold.startswith("reflex")
        or (t0.startswith("R") and not t0_fold.startswith("reference"))
    ):
        target_type = "R"

        rest = tokens[1:]

    else:
        raw_low = _re_ascii_fold_lower(raw_header)

        if any(_re_ascii_fold_lower(t).startswith("transm") for t in tokens) or (
            "transmission" in raw_low or "transmittance" in raw_low
        ):
            target_type = "T"

            rest = tokens[:]

        elif any(
            _re_ascii_fold_lower(t).startswith("refle") or _re_ascii_fold_lower(t).startswith("reflex") for t in tokens
        ) or ("reflection" in raw_low or "reflectance" in raw_low or "reflexion" in raw_low):
            target_type = "R"

            rest = tokens[:]

        else:
            target_type = "R"

            rest = tokens

            assumed_rt = True

            notes.append(
                "No R/T header or reflection/transmission keyword at the start of the label: "
                "the column is interpreted as **reflectance (R)**."
            )

            logging.warning(
                "RE measurement header %r: no leading R/T; assuming Reflectance (R).",
                raw_header,
            )

    angle_deg = 0.0

    pol = "s"

    no_back = False

    with_back = False

    unknown_tokens: list[str] = []

    for tok in rest:
        tl = _re_ascii_fold_lower(tok)

        if tl in _re_no_back_tokens or (tl.startswith("no") and tl.endswith("bk")):
            no_back = True

            continue

        if tl in _re_with_back_tokens or tl in ("back", "bk"):
            with_back = True

            continue

        if tl in ("s", "pols", "pol-s", "spol", "te"):
            pol = "s"

            continue

        if tl in ("p", "polp", "pol-p", "ppol", "tm"):
            pol = "p"

            continue

        if "avg" in tl or "unpol" in tl or tl == "amb" or "moyen" in tl:
            pol = "Avg"

            continue

        m_ang = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([sp]?)", tl, re.IGNORECASE)

        if m_ang:
            a = float(m_ang.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            suf = (m_ang.group(2) or "").lower()

            if suf == "s":
                pol = "s"

            elif suf == "p":
                pol = "p"

            continue

        m_theta = re.match(r"(?:aoi|th(?:eta)?|deg|angle)\s*[\s_\-:]*(\d+(?:\.\d+)?)", tl, re.IGNORECASE)

        if m_theta:
            a = float(m_theta.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        m_inc_fr = re.fullmatch(r"(?:i|inc|inci)(?:idence)?\s*[\s_\-:]*(\d+(?:\.\d+)?)", tl, re.IGNORECASE)

        if m_inc_fr:
            a = float(m_inc_fr.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        if re.fullmatch(r"\d+(?:\.\d+)?", tl):
            a = float(tl)

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        unknown_tokens.append(tok)

    if unknown_tokens:
        notes.append(
            f"Unrecognized label segments (ignored by the parser): {', '.join(repr(t) for t in unknown_tokens)}."
        )

    if no_back and with_back:
        raise ValueError(f"RE header {raw_header!r}: conflicting backside hints (no back vs with back)")

    if no_back:
        include_backside = False

    elif with_back:
        include_backside = True

    else:
        include_backside = True

        if assumed_rt or unknown_tokens:
            notes.append(
                "No explicit rear-face marker (noBK, 1f, sans arriere, plate, 2f, back...): "
                "model **with** incoherent rear face on substrate (**default behaviour**)."
            )

    return ParsedREColumn(target_type, angle_deg, pol, include_backside, raw_header, tuple(notes))


# --- Robust Excel RE layout helpers (variable column order / count) -------------


_RE_DESIGN_LABEL_SKIP = frozenset(
    {
        "lambda",
        "l0",
        "wl",
        "wave",
        "wavelength",
        "longueur",
        "longueurdonde",
        "design",
        "sub",
        "substrate",
        "substrate",
        "ref",
        "lref",
        "nm",
        "qwot",
        "qwuot",
        "ot",
        "couche",
        "layers",
        "layer",
        "materiau",
        "materiaux",
        "thickness",
        "conception",
        "reference",
        "empilement",
        "pile",
        "multicouche",
    }
)


def _re_cell_str(cell) -> str:

    if cell is None:
        return ""

    s = str(cell).strip().replace("\u00a0", " ").replace("\u202f", " ")

    return " ".join(s.split())


def _re_header_is_wavelength_label(s: str) -> bool:

    s_clean = _re_cell_str(s)

    sl = s_clean.lower()

    fold = _re_ascii_fold_lower(s_clean)

    if "wavelength" in sl or "longueur" in sl or "lambda" in s_clean:
        return True

    if "longueur" in fold and "onde" in fold:
        return True

    t = sl.replace(" ", "").replace("(", "").replace(")", "")

    if not t:
        return False

    if any(
        k in t
        for k in (
            "wavelength",
            "longueurd'onde",
            "longueurdonde",
            "lambda",
            "lambda",
        )
    ):
        return True

    if t in ("wl", "wave", "lenm", "lnm"):
        return True

    if "nm" in t and not t.startswith("r") and not t.startswith("t-") and "r_" not in t[:3]:
        if "n_" in t or "n1" in t or "k_" in t:
            return False

        return True

    return False


def _re_header_looks_like_spectrum_title(s: str) -> bool:

    u = _re_ascii_fold_lower(_re_cell_str(s))

    if not u:
        return False

    if u in ("r", "t"):
        return True

    if u.startswith("r") or u.startswith("t"):
        return True

    if any(k in u for k in ("reflect", "reflex", "transmi", "transmission")):
        return True

    return False


def _re_parse_design_metadata_row(header: tuple) -> tuple[float, str]:
    """First row of ``design``: lambda_ref (nm) + substrate name, any column order."""

    import re as _re

    lambda_ref = 500.0

    for cell in header:
        if cell is None:
            continue

        if isinstance(cell, (int, float)):
            v = float(cell)

            if 200.0 <= v <= 200_000.0:
                lambda_ref = v

                break

        if isinstance(cell, str):
            m = _re.search(r"(\d+\.?\d*)", cell)

            if m:
                v = float(m.group(1))

                if 200.0 <= v <= 200_000.0:
                    lambda_ref = v

                    break

    substrate_name = ""

    for cell in header:
        if cell is None or isinstance(cell, (int, float)):
            continue

        s = _re_cell_str(cell)

        if not s:
            continue

        if "lambda" in s:
            continue

        sl = _re_ascii_fold_lower(s)

        if sl in _RE_DESIGN_LABEL_SKIP:
            continue

        if _re.fullmatch(r"\d+\.?\d*\s*(nm)?", sl):
            continue

        substrate_name = s

        break

    return lambda_ref, substrate_name


def _re_looks_like_layer_index_sequence(seq: list[float]) -> bool:
    """Reject columns that are 1,2,3... (layer row counters)."""

    if len(seq) < 3:
        return False

    arr = np.asarray(seq, dtype=np.float64)

    if not np.allclose(arr, np.round(arr), rtol=0.0, atol=1e-9):
        return False

    arr_i = np.round(arr).astype(int)

    if int(arr_i[0]) != 1:
        return False

    return bool(np.all(np.diff(arr_i) == 1))


def _re_qwot_cell_value(v) -> float | None:
    """Return *v* as QWOT if plausibly a quarter-wave fraction, else None."""

    try:
        fv = float(v)

    except (TypeError, ValueError):
        return None

    if fv <= 0.0 or fv > 1.0e6:
        return None

    return fv


def re_qwot_penalty_weight_from_preset(*, speed_preset: dict[str, Any], default: float) -> float:
    """Return the configured QWOT penalty weight from a speed preset."""
    try:
        return float(speed_preset["re_qwot_penalty_weight"])
    except (KeyError, TypeError, ValueError):
        return float(default)


def _re_row_left_qwot_run(row: tuple) -> list[float]:
    """Consecutive QWOT-like numbers from column 0 until None or invalid (one row)."""

    if not row:
        return []

    out: list[float] = []

    for j in range(len(row)):
        v = row[j]

        if v is None:
            break

        fv = _re_qwot_cell_value(v)

        if fv is None:
            break

        out.append(fv)

    return out


def _re_parse_design_qwot_rows(rows: list[tuple]) -> list[float]:
    """QWOT list below the metadata header.

    Supports **multi-column** rows (e.g. H and L on the same line) by flattening

    row-major, and **single-column** legacy (longest vertical run).

    """

    if len(rows) < 2:
        return []

    data_rows = [r for r in rows[1:] if r and any(c is not None for c in r)]

    if not data_rows:
        return []

    head = min(5, len(data_rows))

    multi = any(len(_re_row_left_qwot_run(r)) >= 2 for r in data_rows[:head])

    if multi:
        flat: list[float] = []

        for row in data_rows:
            flat.extend(_re_row_left_qwot_run(row))

        if flat and not _re_looks_like_layer_index_sequence(flat):
            return flat

    max_w = max((len(r) for r in rows if r), default=0)

    best_seq: list[float] = []

    for j in range(max_w):
        seq: list[float] = []

        for row in rows[1:]:
            if not row or len(row) <= j:
                break

            v = row[j]

            if v is None:
                break

            fv = _re_qwot_cell_value(v)

            if fv is None:
                break

            seq.append(fv)

        if _re_looks_like_layer_index_sequence(seq):
            continue

        if len(seq) > len(best_seq):
            best_seq = seq

    return best_seq


def _re_normalize_sheet_key(name: str) -> str:
    """Normalized key to match sheet names (FR accents ignored)."""

    return _re_ascii_fold_lower(_re_cell_str(name))


_RE_CANONICAL_SHEETS = ("measurement", "design", "index")


_RE_SHEET_SYNONYMS: dict[str, tuple[str, ...]] = {
    "measurement": (
        "measurement",
        "measurment",
        "measure",
        "measures",
        "mesure",
        "mesures",
        "spectrum",
        "spectres",
        "spectrum",
        "data",
        "re data",
        "data",
        "mesuree",
        "results",
    ),
    "design": (
        "design",
        "stack",
        "structure",
        "empilement",
        "conception",
        "pile",
        "multicouche",
    ),
    "index": (
        "index",
        "indices",
        "nk",
        "materials",
        "material clues",
        "clues",
        "materiaux",
        "materiaux",
        "indice",
        "optique",
    ),
}


def _re_resolve_re_workbook_sheets(sheetnames: list[str]) -> dict[str, str]:
    """Map canonical keys *measurement* / *design* / *index* to actual sheet titles."""

    norm_to_actual: dict[str, str] = {}

    for s in sheetnames:
        k = _re_normalize_sheet_key(s)

        if not k:
            continue

        norm_to_actual.setdefault(k, s)

    def resolve_one(canonical: str) -> str | None:

        for syn in _RE_SHEET_SYNONYMS.get(canonical, (canonical,)):
            sk = _re_normalize_sheet_key(syn)

            if sk and sk in norm_to_actual:
                return norm_to_actual[sk]

        for raw in sheetnames:
            rk = _re_normalize_sheet_key(raw).replace("_", " ")

            for syn in _RE_SHEET_SYNONYMS.get(canonical, (canonical,)):
                sk = _re_normalize_sheet_key(syn).replace("_", " ")

                if not sk:
                    continue

                pad = f" {rk} "

                if rk == sk or rk.startswith(sk + " ") or rk.endswith(" " + sk) or f" {sk} " in pad:
                    return raw

        return None

    out: dict[str, str] = {}

    for c in _RE_CANONICAL_SHEETS:
        r = resolve_one(c)

        if r:
            out[c] = r

    return out


def _re_index_split_header_and_data(rows: list[tuple]) -> tuple[tuple | None, list[tuple]]:
    """If row 0 looks like text headers, return (row0, data). Else (None, all)."""

    if not rows:
        return None, []

    r0 = rows[0]

    text_n = sum(1 for c in r0 if c is not None and isinstance(c, str) and _re_cell_str(c))

    num_n = sum(1 for c in r0 if isinstance(c, (int, float)))

    if text_n >= 2 and text_n >= num_n:
        return tuple(r0), list(rows[1:])

    return None, list(rows)


def _re_index_column_map(
    header: tuple | None, _max_cols: int
) -> tuple[int, int | None, int | None, int | None, int | None]:
    """Map wavelength + n1,k1,n2,k2 columns. None = missing column (use defaults).

    Priority:
    1. If header labels explicitly contain n_H/k_H and n_B|n_L/k_B|k_L prefixes,
       use name-based mapping so columns don't have to be in positional order.
    2. Fallback: positional order (col after wavelength = n1,k1,n2,k2).
    """

    if header is None:
        return 0, 1, 2, 3, 4

    # --- wavelength column (unchanged) ---
    wl = 0
    for i, c in enumerate(header):
        if c is not None and _re_header_is_wavelength_label(_re_cell_str(c)):
            wl = i
            break

    # --- name-based detection of H / L columns ---
    # Accept multiple conventions used in Excel exports:
    #   n_H / k_H / n_L / k_L
    #   n_high / k_high / n_low / k_low
    #   n_haut / k_haut / n_bas / k_bas
    #   n1 / k1 / n2 / k2
    col_nH = col_kH = col_nL = col_kL = None
    for i, c in enumerate(header):
        if i == wl or c is None:
            continue
        s = _re_cell_str(c).lower().replace(" ", "_").replace("-", "_")
        if s.startswith(("n_h", "n_high", "n_haut", "n1")):
            col_nH = i
        elif s.startswith(("k_h", "k_high", "k_haut", "k1")):
            col_kH = i
        elif s.startswith(("n_l", "n_low", "n_bas", "n_b", "n2")):
            col_nL = i
        elif s.startswith(("k_l", "k_low", "k_bas", "k_b", "k2")):
            col_kL = i

    # If we identified at least n_H and n_L by name, use name-based mapping
    if col_nH is not None and col_nL is not None:
        return wl, col_nH, col_kH, col_nL, col_kL

    # --- fallback: positional order ---
    rest = [i for i in range(len(header)) if i != wl and header[i] is not None and _re_cell_str(header[i])]
    rest.sort()

    if len(rest) >= 4:
        return wl, rest[0], rest[1], rest[2], rest[3]

    if len(rest) == 3:
        return wl, rest[0], rest[1], rest[2], None

    if len(rest) == 2:
        return wl, rest[0], None, rest[1], None

    if len(rest) == 1:
        return wl, rest[0], None, None, None

    return 0, 1, 2, 3, 4



def _re_find_measurement_wavelength_column(header: tuple, data_rows: list[tuple]) -> tuple[int, str | None]:
    """Find the lambda column; returns (index, user message if ambiguous, else None)."""

    if header:
        for i, h in enumerate(header):
            if h is not None and _re_header_is_wavelength_label(_re_cell_str(h)):
                return i, None

    n = len(data_rows)

    if n < 2:
        return 0, (
            "Few rows in the sheet: the wavelength column is assumed to be the **first column (A)**; check values (nm)."
        )

    max_c = max((len(r) for r in data_rows if r), default=0)

    best_i, best_score = 0, -1.0

    for j in range(max_c):
        vals: list[float] = []

        bad = False

        for r in data_rows:
            if not r or len(r) <= j:
                bad = True

                break

            v = r[j]

            if not isinstance(v, (int, float)):
                bad = True

                break

            vals.append(float(v))

        if bad or len(vals) < 3:
            continue

        med = float(np.median(vals))

        if not (80.0 < med < 55000.0):
            continue

        dif = np.diff(vals)

        inc_ratio = float(np.sum(dif >= 0.0)) / max(len(dif), 1)

        score = inc_ratio * len(vals)

        if score > best_score:
            best_score, best_i = score, j

    if best_score >= 0.55 * n:
        # Heuristic clear enough: no user alert (see business logs if needed).

        return best_i, None

    return 0, (
        "**lambda** column not discriminative enough: falling back to **column A**. "
        "Add a header such as 'wavelength (nm)' on the correct column if needed."
    )


def _re_measurement_values_are_percent(vals: list[float]) -> bool:

    arr = np.asarray(vals, dtype=np.float64)

    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return True

    return float(np.nanmax(np.abs(arr))) > 1.25


from certus.core.certus_re_config import (
    REMseContext,
    REPhase2Context,
    REWorkerRequest,
    REPhase1Result,
    REPhase2Result,
    REPhase3Result,
    REPhase4Result,
    _re_phase23_result_to_legacy_dict,
    _result_dto_at,
    _top_result_dto,
    _set_top_result_dto,
    _prepend_result_dto,
    _replace_all_with_top_dto
)
def _re_trf_residual_rms(residual: np.ndarray | None) -> float:
    """RMS of the residual vector as minimized by least_squares: sqrt(mean(r_i^2))."""

    if residual is None:
        return float("nan")

    v = np.asarray(residual, dtype=np.float64).ravel()

    if v.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(v * v)))


def _re_backside_bundle_fixed(ep_local, n_layers_sel, n_sub_sel, wls_sel, var_idx, angle, is_s_pol) -> Any:

    from certus_physics import compute_oblique_backside_bundle_analytic

    return compute_oblique_backside_bundle_analytic(
        ep_local, n_layers_sel, n_sub_sel, wls_sel, var_idx, angle, is_s_pol, None, None
    )


def _re_eval_angle_physics_for(
    sub, angle, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, var_idx
) -> tuple:

    from certus_physics import compute_oblique_rt_and_grads_analytic

    if sub is None:
        wls_s = wls_all

        n_lay_s = n_layers_all

        n_sub_s = n_sub_all

    else:
        wls_s = wls_all[sub]

        n_lay_s = n_layers_all[sub, :]

        n_sub_s = n_sub_all[sub]

    if pl == "avg":
        if not inc_back:
            Rs, Ts, dRs, dTs = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, True, False
            )

            Rp, Tp, dRp, dTp = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, False, False
            )

            return 0.5 * (Rs + Rp), 0.5 * (dRs + dRp), 0.5 * (Ts + Tp), 0.5 * (dTs + dTp)

        else:
            yRs, dRs, yTs, dTs = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, True)

            yRp, dRp, yTp, dTp = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, False)

            return 0.5 * (yRs + yRp), 0.5 * (dRs + dRp), 0.5 * (yTs + yTp), 0.5 * (dTs + dTp)

    else:
        is_s_pol = pl != "p"

        if not inc_back:
            rR, rT, rdR, rdT = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, is_s_pol, False
            )

            return rR, rdR, rT, rdT

        else:
            rR, rdR, rT, rdT = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, is_s_pol)

            return rR, rdR, rT, rdT
