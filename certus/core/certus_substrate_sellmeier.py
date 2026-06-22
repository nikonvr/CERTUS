import numpy as np
import re
import logging
from typing import Any

logger = logging.getLogger("CERTUS")

import warnings
from scipy.optimize import least_squares, minimize

from certus.core.certus_substrate_helpers import norm_header
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATES,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
)

SELLMEIER_N_ACCEPT_LO = 1.05
SELLMEIER_N_ACCEPT_HI = 6.5
SELLMEIER_MIN_L_SEP_UM = 0.01  # m minimal spacing between Li poles (was 0.004)

SELLMEIER_L_SEP_SOFT_WEIGHT = 2.0e5  # soft residue weight on minimal Li separation


SELLMEIER_DEFAULT_LOG_L1L2 = False  # log-reparam disabled  bounds sufficiently tightened


SELLMEIER_2POLES_PARAM_BOUNDS: tuple[tuple[float, float], ...] = (
    (0.0, 4.0),  # A constant term >= 0 ; standard substrates: A < 3
    (0.0, 12.0),  # B1 UV oscillator; positive for transparents
    (1.0e-3, 1.0),  # L1 m UV pole; effective ceiling via _sellmeier_2poles_param_bounds
    (0.0, 12.0),  # B2
    (1.0e-3, 30.0),  # L2 m can be UV or short IR
    (0.0, 12.0),  # B3
    (1.0e-3, 30.0),  # L3 m typically IR pole
)


SELLMEIER_2POLES_LAM_FRAC_MAX = 0.97


SELLMEIER_3TERM_C_FRAC_MAX = 0.995


# Light multistart: with physical bounds and good seeding, 2 candidates are enough.


SELLMEIER_SEED_POINTS = 5  # grid points for polynomial seed (was 9)


SELLMEIER_MULTISTART_TRIALS = 2  # additional random jitters (was 8)


SELLMEIER_WEIGHT_MODE = "uniform"  # uniform: no UV bias (was inv_sqrt_lambda)


# Selection of best model (beyond raw RMSE).


# score = rmse + w_mono*frac_viol_mono + w_prior*rmse_prior_sellmeier






# Catalog prior (standard Sellmeier 3-term from certus.core.certus_core), by column name heuristic.


_SUBSTRATE_PRIOR_HINTS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(sapphire|saphir|al2o3)\b", re.IGNORECASE), 3),
    (re.compile(r"\b(n[\s\-_]*bk7|bk7)\b", re.IGNORECASE), 1),
    (re.compile(r"\b(sio2|silice|silica|quartz)\b", re.IGNORECASE), 0),
    (re.compile(r"\b(d263t|d263)\b", re.IGNORECASE), 2),
    (re.compile(r"\b(b270i|b270)\b", re.IGNORECASE), 4),
)


def _sellmeier_midpoint_seed(bounds: list[tuple[float, float]], lam_min_um: float) -> np.ndarray:
    """Returns midpoint of Sellmeier parameter bounds."""
    return np.array([0.5 * (b[0] + b[1]) for b in bounds], dtype=np.float64)


def _sellmeier_2poles_param_bounds(lam_min_um: float) -> list[tuple[float, float]]:
    """Box (A, B1, L1, B2, L2, B3, L3).

    L1 remains UV side (below lambda_min) for stability; L2/L3 are free (up to 40 m)

    for capture IR/Cauchy curvature without forcing all poles to UV.

    """

    cap_uv = max(1.0e-9, float(lam_min_um) * float(SELLMEIER_2POLES_LAM_FRAC_MAX))

    l_hi_uv = min(40.0, cap_uv)

    l_hi_ir = 40.0

    a_lo, a_hi = float(SELLMEIER_2POLES_PARAM_BOUNDS[0][0]), float(SELLMEIER_2POLES_PARAM_BOUNDS[0][1])

    b_lo, b_hi = float(SELLMEIER_2POLES_PARAM_BOUNDS[1][0]), float(SELLMEIER_2POLES_PARAM_BOUNDS[1][1])

    l_lo = float(SELLMEIER_2POLES_PARAM_BOUNDS[2][0])

    return [
        (a_lo, a_hi),
        (b_lo, b_hi),
        (l_lo, float(l_hi_uv)),
        (b_lo, b_hi),
        (l_lo, float(l_hi_ir)),
        (b_lo, b_hi),
        (l_lo, float(l_hi_ir)),
    ]


def _sellmeier_l_separation_gap_um(p: np.ndarray) -> float:
    """Missing part for min(|LiLj|) >= SELLMEIER_MIN_L_SEP_UM (m)."""

    pp = np.asarray(p, dtype=np.float64).ravel()

    lvals = []

    for i in (2, 4, 6):
        if i < pp.size:
            lvals.append(float(pp[i]))

    if len(lvals) < 2:
        return 0.0

    larr = np.sort(np.asarray(lvals, dtype=np.float64))

    min_sep = float(np.min(np.diff(larr)))

    return max(0.0, float(SELLMEIER_MIN_L_SEP_UM) - min_sep)


def _sellmeier_weights_from_nm(wl_nm: np.ndarray, mode: str) -> np.ndarray:

    wl = np.maximum(np.asarray(wl_nm, dtype=np.float64), 1.0)

    m = str(mode or "").strip().lower()

    if m == "uniform":
        return np.ones_like(wl, dtype=np.float64)

    if m == "inv_lambda":
        return 1.0 / wl

    # default robust compromise: less UV domination than 1/lambda

    return 1.0 / np.sqrt(wl)


def _sellmeier_param_reparam_helpers(
    bounds: list[tuple[float, float]],
    log_l1l2: bool,
) -> tuple[list[tuple[float, float]], Any, Any, np.ndarray, np.ndarray]:
    bounds_q: list[tuple[float, float]] = [(float(b[0]), float(b[1])) for b in bounds]
    if log_l1l2:
        _ll0 = float(max(bounds[2][0], 1.0e-30))
        _ll1 = float(bounds[2][1])
        _ln_lo = float(np.log(_ll0))
        _ln_hi = float(np.log(_ll1))
        bounds_q[2] = (_ln_lo, _ln_hi)
        bounds_q[4] = (_ln_lo, _ln_hi)
        bounds_q[6] = (_ln_lo, _ln_hi)

    def _p_from_q(q: np.ndarray) -> np.ndarray:
        q = np.asarray(q, dtype=np.float64).ravel()
        if not log_l1l2:
            return q.copy()
        p = q.copy()
        p[2] = float(np.exp(np.minimum(q[2], 700.0)))
        p[4] = float(np.exp(np.minimum(q[4], 700.0)))
        p[6] = float(np.exp(np.minimum(q[6], 700.0)))
        return p

    def _q_from_p(p: np.ndarray) -> np.ndarray:
        p = np.asarray(p, dtype=np.float64).ravel()
        if not log_l1l2:
            return p.copy()
        q = p.copy()
        q[2] = float(np.log(max(float(p[2]), 1.0e-300)))
        q[4] = float(np.log(max(float(p[4]), 1.0e-300)))
        q[6] = float(np.log(max(float(p[6]), 1.0e-300)))
        return q

    return bounds_q, _p_from_q, _q_from_p, np.asarray([b[0] for b in bounds], dtype=np.float64), np.asarray([b[1] for b in bounds], dtype=np.float64)


def _sellmeier_residual_factory(p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, n_lo_acc: float, n_hi_acc: float):
    def _residuals(p: np.ndarray, x_um: np.ndarray, y_n: np.ndarray, w_nm_inv: np.ndarray) -> np.ndarray:
        pred = sellmeier_2poles_const_eval(p, x_um)
        return (pred - y_n) * w_nm_inv * 1000.0

    def _mse_full_q(q: np.ndarray) -> float:
        p = p_from_q(q)
        pred = sellmeier_2poles_const_eval(p, wl_fit_um)
        if not np.all(np.isfinite(pred)):
            return 1.0e30
        if np.any((pred < n_lo_acc) | (pred > n_hi_acc)):
            vio = float(np.mean(np.maximum(n_lo_acc - pred, 0.0) ** 2 + np.maximum(pred - n_hi_acc, 0.0) ** 2))
            return 1.0e12 + 1.0e9 * vio
        r = _residuals(p, wl_fit_um, n_fit, w_fit_sell)
        mse = float(np.dot(r, r))
        g = _sellmeier_l_separation_gap_um(p)
        if g > 0.0:
            mse += 5.0e7 * (g * g)
        return mse

    return _residuals, _mse_full_q


def _sellmeier_seed_from_compact_poly(
    wl: np.ndarray,
    wl_fit_nm: np.ndarray,
    n_vals: np.ndarray,
    mask: np.ndarray,
    p_from_q,
    q_mid: np.ndarray,
    ls_bounds_q: tuple[list[float], list[float]],
) -> tuple[str, np.ndarray]:
    from scipy.optimize import least_squares
    seed_desc = "centre box (q)"
    q0 = q_mid
    poly_seed = _sellmeier_compact_polynomial_seed(wl, n_vals, mask)
    if poly_seed is not None:
        active_terms, p_poly, _ = poly_seed
        lo_nm = float(np.min(wl_fit_nm))
        hi_nm = float(np.max(wl_fit_nm))
        n_seed_pts = int(max(7, SELLMEIER_SEED_POINTS))
        seed_nm = np.linspace(lo_nm, hi_nm, n_seed_pts, dtype=np.float64)
        seed_um = seed_nm / 1000.0
        from certus.core.certus_substrate_index import IndexCore
        feat_s = IndexCore._poly_compact_feature_dict(seed_um)
        phi_s = np.column_stack([feat_s[t] for t in active_terms])
        n_tar = (phi_s @ p_poly).astype(np.float64, copy=False)

        def _res5_q(qv: np.ndarray) -> np.ndarray:
            pv = p_from_q(qv)
            r = sellmeier_2poles_const_eval(pv, seed_um) - n_tar
            g = _sellmeier_l_separation_gap_um(pv)
            return np.append(
                r,
                float(SELLMEIER_L_SEP_SOFT_WEIGHT) * 0.02 * g,
            )

        r5 = least_squares(
            _res5_q,
            q_mid,
            bounds=ls_bounds_q,
            loss="linear",
            max_nfev=2500,
            ftol=1.0e-12,
            xtol=1.0e-12,
            gtol=1.0e-12,
        )
        q0 = np.clip(np.asarray(r5.x, dtype=np.float64), ls_bounds_q[0], ls_bounds_q[1])
        seed_desc = (
            "compact polynomial + LS "
            f"{int(seed_nm.size)} points (lambda_nm={np.array2string(seed_nm, precision=1, separator=', ')})"
        )
    return seed_desc, q0


def _sellmeier_multistart_candidates(q0: np.ndarray, _p_from_q, _q_from_p, bounds, ls_bounds_q, n_trials: int) -> list[np.ndarray]:
    rng = np.random.default_rng(12345)
    q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]
    p_base = _p_from_q(q0)
    l3_grid = (0.1, 0.5, 2.0, 8.0)
    for l3_try in l3_grid:
        p_try = np.asarray(p_base, dtype=np.float64).copy()
        p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
        q_try = _q_from_p(p_try)
        q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(np.asarray(q_try, dtype=np.float64))
    for _ in range(max(0, int(n_trials) - 1)):
        jit = rng.uniform(-0.15, 0.15, size=q0.shape)
        jit[6] = float(rng.uniform(-0.5, 0.5))
        qj = np.asarray(q0 + jit, dtype=np.float64)
        qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(qj)
    return q_candidates


def _sellmeier_polish_helpers(_p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, log_l1l2: bool):
    def _residuals(p: np.ndarray, x_um: np.ndarray, y_n: np.ndarray, w_nm_inv: np.ndarray) -> np.ndarray:
        pred = sellmeier_2poles_const_eval(p, x_um)
        return (pred - y_n) * w_nm_inv * 1000.0

    def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = _p_from_q(qv)
        r = _residuals(pv, wl_fit_um, n_fit, w_fit_sell)
        g = _sellmeier_l_separation_gap_um(pv)
        return np.append(r, float(SELLMEIER_L_SEP_SOFT_WEIGHT) * g)

    def _jac_polish_q(qv: np.ndarray) -> np.ndarray:
        """Analytical Jacobian of polish residual (extended with separation constraint)."""
        pv = _p_from_q(qv)
        J_main = _sellmeier_2poles_jac(pv, wl_fit_um, w_fit_sell, scale=1000.0)
        J_sep = np.zeros((1, 7), dtype=np.float64)
        _L_vals = np.array([pv[2], pv[4], pv[6]], dtype=np.float64)
        _orig_idx = np.array([2, 4, 6])
        _sort_ord = np.argsort(_L_vals)
        _L_s = _L_vals[_sort_ord]
        _diffs = _L_s[1:] - _L_s[:-1]
        _i_min = int(np.argmin(_diffs))
        _gap = float(SELLMEIER_MIN_L_SEP_UM) - float(_diffs[_i_min])
        if _gap > 0.0:
            _pidx_lo = int(_orig_idx[int(_sort_ord[_i_min])])
            _pidx_hi = int(_orig_idx[int(_sort_ord[_i_min + 1])])
            _sc_lo = float(pv[_pidx_lo]) if log_l1l2 else 1.0
            _sc_hi = float(pv[_pidx_hi]) if log_l1l2 else 1.0
            J_sep[0, _pidx_lo] = float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_lo
            J_sep[0, _pidx_hi] = -float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_hi
        return np.vstack([J_main, J_sep])

    return _residuals_polish_q, _jac_polish_q


def _sellmeier_initial_context(
    wl: np.ndarray,
    wl_fit_nm: np.ndarray,
    n_vals: np.ndarray,
    mask: np.ndarray,
    bounds,
    log_l1l2: bool,
):
    """Build bounds and an initial Sellmeier seed in one call."""

    lam_min_um = float(np.min(np.asarray(wl_fit_nm, dtype=np.float64)) / 1000.0)
    bounds_q, _p_from_q, _q_from_p, *_ = _sellmeier_param_reparam_helpers(bounds, log_l1l2)
    p_mid = _sellmeier_midpoint_seed(bounds, lam_min_um)
    q_mid = np.clip(_q_from_p(p_mid), bounds_q[0], bounds_q[1])
    seed_desc, q0 = _sellmeier_seed_from_compact_poly(wl, wl_fit_nm, n_vals, mask, _p_from_q, q_mid, bounds_q)
    q0 = np.clip(np.asarray(q0, dtype=np.float64), bounds_q[0], bounds_q[1])
    q_candidates = _sellmeier_multistart_candidates(q0, _p_from_q, _q_from_p, bounds, bounds_q, int(SELLMEIER_MULTISTART_TRIALS))
    return bounds_q, _p_from_q, _q_from_p, q_mid, q0, q_candidates, seed_desc


def _sellmeier_build_candidates(q0: np.ndarray, p_from_q, _q_from_p, bounds, ls_bounds_q, n_trials: int, rng) -> list[np.ndarray]:
    q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]
    p_base = p_from_q(q0)
    l3_grid = (0.1, 0.5, 2.0, 8.0)
    for l3_try in l3_grid:
        p_try = np.asarray(p_base, dtype=np.float64).copy()
        p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
        q_try = _q_from_p(p_try)
        q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(np.asarray(q_try, dtype=np.float64))
    for _ in range(n_trials - 1):
        jit = rng.uniform(-0.15, 0.15, size=q0.shape)
        jit[6] = float(rng.uniform(-0.5, 0.5))
        qj = np.asarray(q0 + jit, dtype=np.float64)
        qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(qj)
    return q_candidates


def _sellmeier_polish_helpers(p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, log_l1l2: bool):
    def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = p_from_q(qv)
        r = _sellmeier_residual_factory(p_from_q, wl_fit_um, n_fit, w_fit_sell, -np.inf, np.inf)[0](pv, wl_fit_um, n_fit, w_fit_sell)
        g = _sellmeier_l_separation_gap_um(pv)
        return np.append(r, float(SELLMEIER_L_SEP_SOFT_WEIGHT) * g)

    def _jac_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = p_from_q(qv)
        J_main = _sellmeier_2poles_jac(pv, wl_fit_um, w_fit_sell, scale=1000.0)
        J_sep = np.zeros((1, 7), dtype=np.float64)
        _L_vals = np.array([pv[2], pv[4], pv[6]], dtype=np.float64)
        _orig_idx = np.array([2, 4, 6])
        _sort_ord = np.argsort(_L_vals)
        _L_s = _L_vals[_sort_ord]
        _diffs = _L_s[1:] - _L_s[:-1]
        _i_min = int(np.argmin(_diffs))
        _gap = float(SELLMEIER_MIN_L_SEP_UM) - float(_diffs[_i_min])
        if _gap > 0.0:
            _pidx_lo = int(_orig_idx[int(_sort_ord[_i_min])])
            _pidx_hi = int(_orig_idx[int(_sort_ord[_i_min + 1])])
            _sc_lo = float(pv[_pidx_lo]) if log_l1l2 else 1.0
            _sc_hi = float(pv[_pidx_hi]) if log_l1l2 else 1.0
            J_sep[0, _pidx_lo] = float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_lo
            J_sep[0, _pidx_hi] = -float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_hi
        return np.vstack([J_main, J_sep])

    return _residuals_polish_q, _jac_polish_q


def _sellmeier_2poles_jac(
    p: np.ndarray,
    x_um: np.ndarray,
    w: np.ndarray,
    scale: float = 1000.0,
) -> np.ndarray:
    """Analytical Jacobian of _residuals(p, x_um, n_data, w) with respect to p.

    Residue : r_i = (n_pred_i - n_data_i) * w_i * scale

    n2 = A + B1*lambda2/(lambda2-L12) + B2*lambda2/(lambda2-L22) + B3*lambda2/(lambda2-L32)

    n  = sqrt(max(n2, 0))

    Analytical derivatives :

        n2/A  = 1

        n2/Bk = lambda2/(lambda2-Lk2)

        n2/Lk = 2BkLklambda2/(lambda2-Lk2)2

        n/p   = (1/(2n)) * n2/p   (with anti-division-by-0 threshold)

    """

    p = np.asarray(p, dtype=np.float64).ravel()

    x = np.asarray(x_um, dtype=np.float64)

    w = np.asarray(w, dtype=np.float64)

    A, B1, L1, B2, L2, B3, L3 = p

    lam2 = x * x

    d1 = np.maximum(lam2 - L1 * L1, 1.0e-15)

    d2 = np.maximum(lam2 - L2 * L2, 1.0e-15)

    d3 = np.maximum(lam2 - L3 * L3, 1.0e-15)

    t1 = lam2 / d1

    t2 = lam2 / d2

    t3 = lam2 / d3

    n2 = A + B1 * t1 + B2 * t2 + B3 * t3

    n = np.sqrt(np.maximum(n2, 0.0))

    # dn/dn2 = 1/(2n) ; threshold 1e-9 to avoid division by zero

    inv2n = np.where(n > 1.0e-9, 1.0 / (2.0 * n), 0.0)

    # Common factor : w * scale * dn/dn2

    c = w * scale * inv2n

    J = np.empty((len(x), 7), dtype=np.float64)

    J[:, 0] = c * 1.0  # r/A

    J[:, 1] = c * t1  # r/B1

    J[:, 2] = c * (2.0 * B1 * L1 * lam2 / (d1 * d1))  # r/L1

    J[:, 3] = c * t2  # r/B2

    J[:, 4] = c * (2.0 * B2 * L2 * lam2 / (d2 * d2))  # r/L2

    J[:, 5] = c * t3  # r/B3

    J[:, 6] = c * (2.0 * B3 * L3 * lam2 / (d3 * d3))  # r/L3

    return J


def _sellmeier_3term_standard_eval(coeffs: np.ndarray, wl_um: np.ndarray) -> np.ndarray:
    """Sellmeier standard: n2 = 1 + (Bi*lambda2/(lambda2-Ci)), lambda in m."""

    p = np.asarray(coeffs, dtype=np.float64).ravel()

    wl = np.maximum(np.asarray(wl_um, dtype=np.float64), 1.0e-9)

    lam2 = wl * wl

    B1, C1, B2, C2, B3, C3 = p

    d1 = lam2 - C1

    d2 = lam2 - C2

    d3 = lam2 - C3

    d1 = np.where(np.abs(d1) < 1.0e-15, np.sign(d1) * 1.0e-15 + (d1 == 0.0) * 1.0e-15, d1)

    d2 = np.where(np.abs(d2) < 1.0e-15, np.sign(d2) * 1.0e-15 + (d2 == 0.0) * 1.0e-15, d2)

    d3 = np.where(np.abs(d3) < 1.0e-15, np.sign(d3) * 1.0e-15 + (d3 == 0.0) * 1.0e-15, d3)

    n2 = 1.0 + (B1 * lam2) / d1 + (B2 * lam2) / d2 + (B3 * lam2) / d3

    return np.sqrt(np.maximum(n2, 0.0))


def _sellmeier_prior_coeffs_for_column(col_name: str | None) -> tuple[float, ...] | None:

    s = norm_header(col_name or "")

    for pat, mat_id in _SUBSTRATE_PRIOR_HINTS:
        if pat.search(s):
            c = SELLMEIER_COEFFS_BY_ID.get(int(mat_id))

            if c is not None and len(c) == 6:
                return tuple(float(v) for v in c)

    canon = canonicalize_substrate_label(col_name)
    if canon is not None:
        c = substrate_sellmeier_coeffs(canon)
        if c is not None and len(c) == 6:
            return tuple(float(v) for v in c)

    return None










def _resolve_sellmeier_settings(
    auto_enabled: bool,
    timeout_spin_value: float,
    de_iter_value: int,
    ls_nfev_value: int,
    log_l1l2_enabled: bool,
) -> tuple[float | None, int, int, bool]:
    """Normalize UI Sellmeier settings into a single robust config tuple."""

    if auto_enabled:
        timeout_cfg = 8.0
        de_maxiter = 300
        ls_max_nfev = 3000
    else:
        timeout_cfg = None if float(timeout_spin_value) <= 0.0 else float(timeout_spin_value)
        de_maxiter = int(de_iter_value)
        ls_max_nfev = int(ls_nfev_value)

    return timeout_cfg, de_maxiter, ls_max_nfev, bool(log_l1l2_enabled)


def _sellmeier_compact_polynomial_seed(
    wl: np.ndarray,
    n_vals: np.ndarray,
    mask: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray] | None:
    """

    Same compact polynomial model selection as the main branch (weighted IRLS).

    Returns (active terms, p, n_poly on all `wl`) to seed Sellmeier; no RMSE/mono rejection here.

    """

    wl_fit_nm = np.asarray(wl[mask], dtype=np.float64)

    n_fit = np.asarray(n_vals[mask], dtype=np.float64)

    from certus.core.certus_substrate_index import _fit_compact_polynomial_model
    fitted = _fit_compact_polynomial_model(
        wl_fit_nm,
        n_fit,
        np.asarray(wl, dtype=np.float64),
        rmse_target_compact=1.5e-3,
    )

    if fitted is None:
        return None

    active_terms, p, n_out, _rmse_c = fitted

    return active_terms, np.asarray(p, dtype=np.float64), np.asarray(n_out, dtype=np.float64)


def sellmeier_2poles_const_eval(params: np.ndarray, wl_um: np.ndarray) -> np.ndarray:
    """n2 = A + (Bi*lambda2/(lambda2-Li2)) (i=1..3), with lambda in m."""

    p = np.asarray(params, dtype=np.float64).ravel()

    wl = np.maximum(np.asarray(wl_um, dtype=np.float64), 1.0e-9)

    lam2 = wl**2

    A, B1, L1, B2, L2, B3, L3 = p

    # Under constraint L < lambda_min(fit), den > 0; floor only for numerical anti-0 (not 1e-9 which

    # produced ~1e9 terms when lambda2-L2<0 with L out of UV).

    den1 = np.maximum(lam2 - (L1**2), 1.0e-15)

    den2 = np.maximum(lam2 - (L2**2), 1.0e-15)

    den3 = np.maximum(lam2 - (L3**2), 1.0e-15)

    n2 = A + (B1 * lam2) / den1 + (B2 * lam2) / den2 + (B3 * lam2) / den3

    # No clip on n2 towards acceptance band: it produced n=1.05 everywhere (n2<0) while

    # passing band tests. 1e-9 floor gave n~3e-5. Here: n2<=0 -> n=0 -> out-of-band.

    return np.sqrt(np.maximum(np.asarray(n2, dtype=np.float64), 0.0))


def _fit_model_sellmeier3poles(
    n_vals: np.ndarray,
    wl: np.ndarray,
    mask: np.ndarray,
    n_fit: np.ndarray,
    wl_fit_nm: np.ndarray,
    wl_fit_um: np.ndarray,
    progress_cb,
    sellmeier_timeout_s: float | None,
    sellmeier_de_maxiter: int,
    sellmeier_de_popsize: int,
    sellmeier_ls_max_nfev: int,
    sellmeier_log_l1l2: bool | None,
) -> tuple[np.ndarray | None, str, np.ndarray | None, dict]:
    from scipy.optimize import least_squares, minimize

    import time

    log_l1l2 = bool(SELLMEIER_DEFAULT_LOG_L1L2 if sellmeier_log_l1l2 is None else sellmeier_log_l1l2)

    lam_min_um = float(np.min(wl_fit_um))

    bounds = _sellmeier_2poles_param_bounds(lam_min_um)

    logger.info(
        "Sellmeier 3-poles: math domain A[%.1f,%.1f] B[%.0f,%.0f] L[%.1e,%.4f] m "
        "(lambda_min fit=%.4f m; L_max=min(40,%.2f×lambda_min) for lambda2-L2>0 in window).",
        bounds[0][0],
        bounds[0][1],
        bounds[1][0],
        bounds[1][1],
        bounds[2][0],
        bounds[2][1],
        lam_min_um,
        float(SELLMEIER_2POLES_LAM_FRAC_MAX),
    )

    logger.info(
        "Sellmeier: optimization on %s.",
        "ui=ln(Li) (Li=exp(ui), L1/L2/L3 reparam.)" if log_l1l2 else "native parameters Li (linear)",
    )

    logger.info(
        "Sellmeier: weights=%s | seed_points=%d | multistart=%d",
        str(SELLMEIER_WEIGHT_MODE),
        int(max(7, SELLMEIER_SEED_POINTS)),
        int(max(1, SELLMEIER_MULTISTART_TRIALS)),
    )

    ls_max_nfev = int(max(100, sellmeier_ls_max_nfev))

    timeout_s = None if sellmeier_timeout_s is None else float(max(0.0, sellmeier_timeout_s))

    t0 = time.monotonic()

    lbfgs_maxiter = int(max(80, sellmeier_de_maxiter * 4 + sellmeier_de_popsize * 8))

    w_fit_sell = _sellmeier_weights_from_nm(wl_fit_nm, SELLMEIER_WEIGHT_MODE)

    bounds_q, _p_from_q, _q_from_p, _b_lo, _b_hi = _sellmeier_param_reparam_helpers(bounds, log_l1l2)
    n_lo_acc = float(SELLMEIER_N_ACCEPT_LO)
    n_hi_acc = float(SELLMEIER_N_ACCEPT_HI)
    _residuals, _mse_full_q = _sellmeier_residual_factory(_p_from_q, wl_fit_um, n_fit, w_fit_sell, n_lo_acc, n_hi_acc)

    ls_bounds_lin = ([b[0] for b in bounds], [b[1] for b in bounds])

    ls_bounds_q = ([b[0] for b in bounds_q], [b[1] for b in bounds_q])

    p_mid = np.array(
        [
            0.5 * (bounds[0][0] + bounds[0][1]),
            0.5 * (bounds[1][0] + bounds[1][1]),
            0.5 * (bounds[2][0] + bounds[2][1]),
            0.5 * (bounds[3][0] + bounds[3][1]),
            0.5 * (bounds[4][0] + bounds[4][1]),
            0.5 * (bounds[5][0] + bounds[5][1]),
            0.5 * (bounds[6][0] + bounds[6][1]),
        ],
        dtype=np.float64,
    )

    _l_lo1, _l_hi1 = float(bounds[2][0]), float(bounds[2][1])

    _span1 = max(_l_hi1 - _l_lo1, 1.0e-15)

    p_mid[2] = float(_l_lo1 + 0.35 * _span1)

    _l_lo2, _l_hi2 = float(bounds[4][0]), float(bounds[4][1])

    _l_lo3, _l_hi3 = float(bounds[6][0]), float(bounds[6][1])

    p_mid[4] = float(np.clip(max(0.35, 1.6 * lam_min_um), _l_lo2, _l_hi2))

    p_mid[6] = float(np.clip(max(1.2, 4.0 * lam_min_um), _l_lo3, _l_hi3))

    _sep_need = float(SELLMEIER_MIN_L_SEP_UM)

    _ls = np.sort(np.asarray([p_mid[2], p_mid[4], p_mid[6]], dtype=np.float64))

    if float(np.min(np.diff(_ls))) < _sep_need:
        _mid = 0.5 * (_l_lo1 + _l_hi1)

        p_mid[2] = float(max(_l_lo1, _mid - 1.1 * _sep_need))

        p_mid[4] = float(np.clip(max(0.35, 1.6 * lam_min_um), _l_lo2, _l_hi2))

        p_mid[6] = float(np.clip(max(1.2, 4.0 * lam_min_um), _l_lo3, _l_hi3))

    p_mid = np.clip(p_mid, ls_bounds_lin[0], ls_bounds_lin[1])

    q_mid = _q_from_p(p_mid)

    q_mid = np.clip(q_mid, ls_bounds_q[0], ls_bounds_q[1])

    q0 = np.asarray(q_mid, dtype=np.float64, order="C")

    try:
        if callable(progress_cb):
            progress_cb(1, 2)

        seed_desc, q0_seed = _sellmeier_seed_from_compact_poly(wl, wl_fit_nm, n_vals, mask, _p_from_q, q_mid, ls_bounds_q)
        q0 = np.clip(np.asarray(q0_seed, dtype=np.float64), ls_bounds_q[0], ls_bounds_q[1])
        logger.info("Sellmeier 3-poles: seed %s.", seed_desc)
        run_lbfgs = timeout_s is None or timeout_s <= 0.0 or (time.monotonic() - t0) < max(0.5, timeout_s - 0.3)

        if run_lbfgs:
            rng = np.random.default_rng(12345)

            q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]

            # Reduced L3 structured grid (IR pole): 4 values covering UV-short/IR.
            p_base = _p_from_q(q0)
            l3_grid = (0.1, 0.5, 2.0, 8.0)

            for l3_try in l3_grid:
                p_try = np.asarray(p_base, dtype=np.float64).copy()
                p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
                q_try = _q_from_p(p_try)
                q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
                q_candidates.append(np.asarray(q_try, dtype=np.float64))

            n_trials = int(max(1, SELLMEIER_MULTISTART_TRIALS))

            for _ in range(n_trials - 1):
                jit = rng.uniform(-0.15, 0.15, size=q0.shape)
                jit[6] = float(rng.uniform(-0.5, 0.5))
                qj = np.asarray(q0 + jit, dtype=np.float64)
                qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
                q_candidates.append(qj)

            best_q = np.asarray(q0, dtype=np.float64)
            best_f = float("inf")

            for qi in q_candidates:
                if timeout_s is not None and timeout_s > 0.0 and (time.monotonic() - t0) >= timeout_s:
                    break

                rb = minimize(
                    _mse_full_q,
                    qi,
                    method="L-BFGS-B",
                    bounds=bounds_q,
                    options={"maxiter": int(lbfgs_maxiter), "ftol": 1.0e-14, "gtol": 1.0e-10},
                )

                q_try = np.asarray(rb.x, dtype=np.float64)
                f_try = float(_mse_full_q(q_try))

                if f_try < best_f:
                    best_f = f_try
                    best_q = q_try

            q_lbfgs = np.asarray(best_q, dtype=np.float64)

        else:
            logger.warning("Sellmeier 3-poles: timeout before L-BFGS-B - seed alone.")
            q_lbfgs = np.asarray(q0, dtype=np.float64)

        _residuals_polish_q, _jac_polish_q = _sellmeier_polish_helpers(_p_from_q, wl_fit_um, n_fit, w_fit_sell, log_l1l2)
        res_pol = least_squares(
            _residuals_polish_q,
            q_lbfgs,
            jac=_jac_polish_q,
            bounds=ls_bounds_q,
            loss="linear",
            f_scale=1.0,
            max_nfev=ls_max_nfev,
        )

        q_sell = np.asarray(res_pol.x, dtype=np.float64)

        p_sell = _p_from_q(q_sell)

        p_lbfgs = _p_from_q(q_lbfgs)

        # Removal of redundant unweighted polish (canceled pass 1 corrections).

        # The weighted pass with analytical Jacobian is sufficient.

        if callable(progress_cb):
            progress_cb(2, 2)

        wl_full_um = np.asarray(wl / 1000.0, dtype=np.float64)

        def _sellmeier_n_in_accept_band(p: np.ndarray) -> bool:

            n_line = sellmeier_2poles_const_eval(p, wl_full_um)

            if not np.all(np.isfinite(n_line)):
                return False

            ne = np.asarray(n_line[mask], dtype=np.float64)

            return bool(np.all(ne >= n_lo_acc) and np.all(ne <= n_hi_acc))

        def _accept_stats(p: np.ndarray) -> tuple[bool, float, float, float]:
            n_line = sellmeier_2poles_const_eval(p, wl_full_um)
            if not np.all(np.isfinite(n_line)):
                return False, float("nan"), float("nan"), float("nan")
            ne = np.asarray(n_line[mask], dtype=np.float64)
            nmin = float(np.nanmin(ne)) if ne.size else float("nan")
            nmax = float(np.nanmax(ne)) if ne.size else float("nan")
            viol = float(np.max(np.maximum(n_lo_acc - ne, 0.0) + np.maximum(ne - n_hi_acc, 0.0))) if ne.size else float("inf")
            ok = bool(np.all(ne >= n_lo_acc) and np.all(ne <= n_hi_acc))
            return ok, nmin, nmax, viol

        ok_sell, sell_min, sell_max, sell_viol = _accept_stats(p_sell)
        ok_lbfgs, lbfgs_min, lbfgs_max, lbfgs_viol = _accept_stats(p_lbfgs)
        if not ok_sell and ok_lbfgs:
            logger.info(
                "Sellmeier 3-poles: polish candidate out of band n[%.2f,%.2f] (min=%.6f max=%.6f viol=%.3g); keeping L-BFGS-B (min=%.6f max=%.6f viol=%.3g).",
                n_lo_acc,
                n_hi_acc,
                sell_min,
                sell_max,
                sell_viol,
                lbfgs_min,
                lbfgs_max,
                lbfgs_viol,
            )
            p_sell = np.asarray(p_lbfgs, dtype=np.float64)
            ok_sell = ok_lbfgs
            sell_min, sell_max, sell_viol = lbfgs_min, lbfgs_max, lbfgs_viol

        if not ok_sell:
            logger.warning(
                "Sellmeier 3-poles fit out of band but kept for competitiveness: n[%.2f, %.2f] -> min=%.6f max=%.6f viol=%.3g",
                n_lo_acc,
                n_hi_acc,
                sell_min,
                sell_max,
                sell_viol,
            )

        n_out_sell = sellmeier_2poles_const_eval(p_sell, wl_full_um)
        if not np.all(np.isfinite(n_out_sell)):
            raise ValueError("non-finite output")
        n_eval = np.asarray(n_out_sell[mask], dtype=np.float64)

        rmse_unweighted = float(np.sqrt(np.mean((n_eval - n_fit) ** 2)))

        wrmse = float(np.sqrt(np.mean(((n_eval - n_fit) * w_fit_sell) ** 2)))

        logger.info(
            "Sellmeier 3-poles fit stats: wrmse=%.6g | rmse=%.6g | n_range_fit=[%.6f, %.6f] | n@edges=[%.6f, %.6f]",
            wrmse,
            rmse_unweighted,
            float(np.min(n_eval)),
            float(np.max(n_eval)),
            float(n_eval[0]),
            float(n_eval[-1]),
        )

        logger.info(
            "Sellmeier coefficients accepted: A=%.9g | B1=%.9g | L1=%.9g m | B2=%.9g | L2=%.9g m | B3=%.9g | L3=%.9g m",
            float(p_sell[0]),
            float(p_sell[1]),
            float(p_sell[2]),
            float(p_sell[3]),
            float(p_sell[4]),
            float(p_sell[5]),
            float(p_sell[6]),
        )

        if log_l1l2:
            _ln1 = float(np.log(max(float(p_sell[2]), 1.0e-300)))

            _ln2 = float(np.log(max(float(p_sell[4]), 1.0e-300)))

            _ln3 = float(np.log(max(float(p_sell[6]), 1.0e-300)))

            _lg10 = float(np.log(10.0))

            logger.info(
                "Sellmeier (reparam. ln L): u1=ln(L1)=%.9g | u2=ln(L2)=%.9g | u3=ln(L3)=%.9g "
                "| log10(L1)=%.9g | log10(L2)=%.9g | log10(L3)=%.9g",
                _ln1,
                _ln2,
                _ln3,
                _ln1 / _lg10,
                _ln2 / _lg10,
                _ln3 / _lg10,
            )

        # 3-term standard variant (n2=1+Bi*λ2/(λ2-Ci)) for literature/catalog compatibility.
        c_hi = max(1.0e-15, (lam_min_um * float(SELLMEIER_3TERM_C_FRAC_MAX)) ** 2)
        b_bounds = (-200.0, 200.0)
        c_bounds = (1.0e-15, c_hi)
        std_bounds = (
            [b_bounds[0], c_bounds[0], b_bounds[0], c_bounds[0], b_bounds[0], c_bounds[0]],
            [b_bounds[1], c_bounds[1], b_bounds[1], c_bounds[1], b_bounds[1], c_bounds[1]],
        )

        def _std_seed_from_2p(p2: np.ndarray) -> np.ndarray:
            p2 = np.asarray(p2, dtype=np.float64)
            seed = np.asarray(
                [
                    p2[1],
                    min(c_hi, max(1.0e-15, p2[2] ** 2)),
                    p2[3],
                    min(c_hi, max(1.0e-15, p2[4] ** 2)),
                    p2[5],
                    min(c_hi, max(1.0e-15, p2[6] ** 2)),
                ],
                dtype=np.float64,
            )
            return np.clip(seed, std_bounds[0], std_bounds[1])

        def _std_residuals(p_std: np.ndarray) -> np.ndarray:
            pred = _sellmeier_3term_standard_eval(p_std, wl_fit_um)
            r = (pred - n_fit) * w_fit_sell * 1000.0
            return np.asarray(r, dtype=np.float64)

        candidates: list[tuple[str, np.ndarray, np.ndarray, float, dict]] = []
        candidates.append(
            (
                "analytic-sellmeier-3poles-A",
                np.asarray(p_sell, dtype=np.float64),
                np.asarray(n_out_sell, dtype=np.float64),
                float(wrmse),
                {"sellmeier_optim_log_l1l2": log_l1l2},
            )
        )

        try:
            p0_std = _std_seed_from_2p(p_sell)
            res_std = least_squares(
                _std_residuals,
                p0_std,
                bounds=std_bounds,
                loss="linear",
                max_nfev=max(1200, int(ls_max_nfev)),
            )
            p_std = np.asarray(res_std.x, dtype=np.float64)
            n_out_std = _sellmeier_3term_standard_eval(p_std, wl_full_um)
            n_std_fit = np.asarray(n_out_std[mask], dtype=np.float64)

            if np.all(np.isfinite(n_std_fit)) and np.all((n_std_fit >= n_lo_acc) & (n_std_fit <= n_hi_acc)):
                wrmse_std = float(np.sqrt(np.mean(((n_std_fit - n_fit) * w_fit_sell) ** 2)))
                candidates.append(
                    (
                        "analytic-sellmeier-3term-standard",
                        p_std,
                        np.asarray(n_out_std, dtype=np.float64),
                        wrmse_std,
                        {},
                    )
                )
                logger.info(
                    "Sellmeier standard 3-term candidate: wrmse=%.6g | rmse=%.6g",
                    wrmse_std,
                    float(np.sqrt(np.mean((n_std_fit - n_fit) ** 2))),
                )
        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.info("Sellmeier standard 3-term: fit unavailable, keeping 3-poles variant.")

        best_src, best_coeffs, best_curve, _best_wrmse, best_extra = min(
            candidates,
            key=lambda t: float(t[3]),
        )

        if best_src != "analytic-sellmeier-3poles-A":
            logger.info(
                "Sellmeier selection: variante standard 3-termes retenue (plus proche, wrmse=%.6g).",
                float(_best_wrmse),
            )

        return (
            np.asarray(best_curve, dtype=np.float64),
            best_src,
            np.asarray(best_coeffs, dtype=np.float64),
            best_extra,
        )

    except (ValueError, RuntimeError, ArithmeticError) as ex:
        logger.warning("Sellmeier 3-poles fit failed: %s -> fallback to Polynomial.", str(ex))
        return None, "fallback-raw-sell2p-error", None, {}

    except NUMERICAL_FAULT_EXCEPTIONS:
        logger.exception("Sellmeier 3-poles fit unexpected failure -> fallback to Polynomial.")
        return None, "fallback-raw-sell2p-exception", None, {}


