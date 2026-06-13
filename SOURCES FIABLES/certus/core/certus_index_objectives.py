from pathlib import Path
from certus.core.certus_core import create_module_environment
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import scipy
import scipy.optimize

_env = create_module_environment(__file__, 'CERTUS_INDEX_CORE')
script_dir = _env['script_dir']

from certus.core.certus_index_core import TLU_SOFT_EDGE_MARGIN, TLU_PRIOR_TRANSPARENT_N_MIN_SOFT


from numba import njit, prange
import logging
import numpy as np
import pandas as pd
from enum import Enum, auto
from typing import Any

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    HC_EV_NM,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    OH_BAND_MAX,
    OH_BAND_MIN,
    PI,
    SMALL_EPSILON,
    T_SUB_MIN_R_NORM,
    T_SUB_MIN_T_NORM,
    SUBSTRATE_LIST,
    SUBSTRATES,
    SELLMEIER_COEFFS_BY_ID,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
    substrate_sellmeier_id,
    __version__,
    get_resource_path,
    get_safe_worker_count,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
)
from certus_physics import (
    PGlobalConfig,
    Sample,
    SingleLinkageClusterer,
    TLUParameters,
    _compute_index_cost_gradient_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_phase2_derivatives_kernel,
    _compute_ir_global_cost_gradient_kernel,
    calculate_single_interface_R,
    calculate_reflection_array,
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    calculate_transmission_single,
    clip_to_bounds,
    compute_mse_vectorized,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_n_frosted_glass_array,
    get_n_substrate_array_by_id,
    SplineBasisCache,
)
from certus.utils.certus_index_utils import (
    spectral_rmse_weights,
    sellmeier_2poles_eval_nj,
    sellmeier_2poles_eval,
    k_law_8p_eval,
    _deduce_knots_from_k8p,
    _ensure_strictly_increasing,
    _merge_closest_knot_pair,
    _sellmeier_residuals,
    fit_sellmeier_global,
    fit_k_global_8p,
    DataType,
    _detect_data_type_from_array,
    _detect_type_from_column_name,
    detect_data_type,
    analyze_loaded_data,
    _get_substrate_n_array_index,
    normalize_index_config,
    calculate_index_rmse,
)

from certus_physics import calculate_reflection_array
from certus_physics import _calculate_RT_absorbing_sub_single
from certus_physics import _compute_single_layer_sensitivity_kernel
from certus_physics import calculate_reflection_infinite_substrate_single
from certus_physics import calculate_transmission_single

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _njit_ir_global_gradient_fused(
    lam_nm: np.ndarray,
    lam_um: np.ndarray,
    n_sub: np.ndarray,
    weights: np.ndarray,
    target_T: np.ndarray,
    target_R: np.ndarray,
    p_sell: np.ndarray,
    p_k8: np.ndarray,
    d: float,
    weight_T: float,
    weight_R: float,
    use_T: bool,
    use_R: bool,
    is_frosted: bool,
    abs_sub: bool,
    k_sub_f: np.ndarray,
    D_sub: float,
    use_norm: bool,
    T_substrate: np.ndarray,
    grad_out: np.ndarray
) -> None:
    n_pts = len(lam_um)
    w_sum_T = 0.0
    w_sum_R = 0.0

    for i in range(n_pts):
        if weights[i] > 1e-12:
            if use_T and not np.isnan(target_T[i]): 
                w_sum_T += weights[i]
            if use_R and not np.isnan(target_R[i]): 
                w_sum_R += weights[i]

    if w_sum_T < 1e-12: w_sum_T = 1.0
    if w_sum_R < 1e-12: w_sum_R = 1.0

    DELTA = 1e-7
    _lo, _hi = -25.0, 5.0
    _mid = 0.5 * (_lo + _hi)
    _scale = 2.0
    half_diff = 0.5 * (_hi - _lo)

    for p in range(13):
        grad_out[p] = 0.0

    for i in range(n_pts):
        w = weights[i]
        if w < 1e-12:
            continue

        wl = lam_um[i]
        wl_sq = wl * wl
        
        # 1. Evaluate Sellmeier and derivatives
        A, B1, L1, B2, L2 = p_sell[0], p_sell[1], p_sell[2], p_sell[3], p_sell[4]
        denom1 = wl_sq - L1 * L1
        if abs(denom1) < 1e-15:
            denom1 = 1e-15 if denom1 >= 0 else -1e-15
        denom2 = wl_sq - L2 * L2
        if abs(denom2) < 1e-15:
            denom2 = 1e-15 if denom2 >= 0 else -1e-15
        term1 = (B1 * wl_sq) / denom1
        term2 = (B2 * wl_sq) / denom2
        n_sq = A + term1 + term2
        nr = np.sqrt(max(n_sq, 1e-6))
        
        inv_2n = 0.5 / nr if n_sq > 1e-6 else 0.0
        dn0 = inv_2n * 1.0
        dn1 = inv_2n * (wl_sq / denom1)
        dn2 = inv_2n * (term1 * 2.0 * L1 / denom1)
        dn3 = inv_2n * (wl_sq / denom2)
        dn4 = inv_2n * (term2 * 2.0 * L2 / denom2)

        # 2. Evaluate k-law and derivatives
        amp, center, width, exponent = p_k8[4], p_k8[5], p_k8[6], p_k8[7]
        w_safe = max(width, 1e-9)
        beta = max(min(exponent, 8.0), 1.0)
        
        x1 = p_k8[0] * wl + p_k8[1]
        x2 = p_k8[2] * wl + p_k8[3]
        y1 = (x1 - _mid) / _scale
        y2 = (x2 - _mid) / _scale
        t1 = np.tanh(y1)
        t2 = np.tanh(y2)
        base1 = np.exp(_mid + half_diff * t1)
        base2 = np.exp(_mid + half_diff * t2)
        
        arg = abs((wl - center) / w_safe)
        arg_beta = arg**beta
        gauss = amp * np.exp(-arg_beta)
        ni = 1e-6 + base1 + base2 + gauss
        
        d_e1_dx1 = half_diff * (1.0 - t1 * t1) / _scale
        d_e2_dx2 = half_diff * (1.0 - t2 * t2) / _scale
        
        dk0 = base1 * d_e1_dx1 * wl
        dk1 = base1 * d_e1_dx1 * 1.0
        dk2 = base2 * d_e2_dx2 * wl
        dk3 = base2 * d_e2_dx2 * 1.0
        dk4 = np.exp(-arg_beta)
        
        dk6 = 0.0
        dk7 = 0.0
        if arg > 0:
            sgn = 0.0 if wl == center else (-1.0 if wl > center else 1.0)
            d_arg_dc = sgn / w_safe
            dk5 = -gauss * beta * (arg ** (beta - 1.0)) * d_arg_dc
            d_arg_dw = -arg / w_safe
            dk6 = -gauss * beta * (arg ** (beta - 1.0)) * d_arg_dw
            if arg > 1e-12:
                dk7 = -gauss * arg_beta * np.log(arg)

        ns = n_sub[i]
        dTdn, dTdk, dRdn, dRdk = 0.0, 0.0, 0.0, 0.0
        
        wl_nm = lam_nm[i]

        if is_frosted:
            ns_cmplx = ns + 0j
            val_R = calculate_reflection_infinite_substrate_single(wl_nm, nr, ni, d, ns_cmplx)
            val_T = np.nan
            vR_up_n = calculate_reflection_infinite_substrate_single(wl_nm, nr + DELTA, ni, d, ns_cmplx)
            vR_dn_n = calculate_reflection_infinite_substrate_single(wl_nm, nr - DELTA, ni, d, ns_cmplx)
            dRdn = (vR_up_n - vR_dn_n) / (2.0 * DELTA)
            vR_up_k = calculate_reflection_infinite_substrate_single(wl_nm, nr, ni + DELTA, d, ns_cmplx)
            if ni < DELTA:
                dRdk = (vR_up_k - val_R) / DELTA
            else:
                vR_dn_k = calculate_reflection_infinite_substrate_single(wl_nm, nr, ni - DELTA, d, ns_cmplx)
                dRdk = (vR_up_k - vR_dn_k) / (2.0 * DELTA)

        elif abs_sub:
            ks = k_sub_f[i]
            val_R, val_T = _calculate_RT_absorbing_sub_single(wl_nm, nr, ni, d, ns, ks, D_sub)
            vR_up_n, vT_up_n = _calculate_RT_absorbing_sub_single(wl_nm, nr + DELTA, ni, d, ns, ks, D_sub)
            vR_dn_n, vT_dn_n = _calculate_RT_absorbing_sub_single(wl_nm, nr - DELTA, ni, d, ns, ks, D_sub)
            dRdn = (vR_up_n - vR_dn_n) / (2.0 * DELTA)
            dTdn = (vT_up_n - vT_dn_n) / (2.0 * DELTA)
            vR_up_k, vT_up_k = _calculate_RT_absorbing_sub_single(wl_nm, nr, ni + DELTA, d, ns, ks, D_sub)
            if ni < DELTA:
                dRdk = (vR_up_k - val_R) / DELTA
                dTdk = (vT_up_k - val_T) / DELTA
            else:
                vR_dn_k, vT_dn_k = _calculate_RT_absorbing_sub_single(wl_nm, nr, ni - DELTA, d, ns, ks, D_sub)
                dRdk = (vR_up_k - vR_dn_k) / (2.0 * DELTA)
                dTdk = (vT_up_k - vT_dn_k) / (2.0 * DELTA)

        else:
            ns_cmplx = ns + 0j
            val_R, val_T = calculate_transmission_single(wl_nm, nr, ni, d, ns_cmplx)
            dTdn_corr, dTdk_corr, dRdn_corr, dRdk_corr, _, _ = _compute_single_layer_sensitivity_kernel(
                wl_nm, nr, ni, d, ns
            )
            dTdn = dTdn_corr
            dTdk = dTdk_corr
            dRdn = dRdn_corr
            dRdk = dRdk_corr

        fac_T = 0.0
        fac_R = 0.0

        if use_T and not np.isnan(target_T[i]):
            if use_norm:
                scale_T = 1.0 / max(T_substrate[i], 1e-6)
                diff_T = (val_T * scale_T) - target_T[i]
            else:
                scale_T = 1.0
                diff_T = val_T - target_T[i]
            fac_T = (2.0 * w * diff_T * weight_T / w_sum_T) * scale_T

        if use_R and not np.isnan(target_R[i]):
            if use_norm:
                scale_R = 1.0 / T_substrate[i] if T_substrate[i] >= 0.05 else 0.0
                diff_R = (val_R * scale_R) - target_R[i]
            else:
                scale_R = 1.0
                diff_R = val_R - target_R[i]
            fac_R = (2.0 * w * diff_R * weight_R / w_sum_R) * scale_R

        # Accumulate gradients (Sellmeier)
        grad_out[0] += (fac_T * dTdn * dn0 + fac_R * dRdn * dn0) if (use_T or use_R) else 0.0
        grad_out[1] += (fac_T * dTdn * dn1 + fac_R * dRdn * dn1) if (use_T or use_R) else 0.0
        grad_out[2] += (fac_T * dTdn * dn2 + fac_R * dRdn * dn2) if (use_T or use_R) else 0.0
        grad_out[3] += (fac_T * dTdn * dn3 + fac_R * dRdn * dn3) if (use_T or use_R) else 0.0
        grad_out[4] += (fac_T * dTdn * dn4 + fac_R * dRdn * dn4) if (use_T or use_R) else 0.0

        # Accumulate gradients (k-law)
        grad_out[5] += (fac_T * dTdk * dk0 + fac_R * dRdk * dk0) if (use_T or use_R) else 0.0
        grad_out[6] += (fac_T * dTdk * dk1 + fac_R * dRdk * dk1) if (use_T or use_R) else 0.0
        grad_out[7] += (fac_T * dTdk * dk2 + fac_R * dRdk * dk2) if (use_T or use_R) else 0.0
        grad_out[8] += (fac_T * dTdk * dk3 + fac_R * dRdk * dk3) if (use_T or use_R) else 0.0
        grad_out[9] += (fac_T * dTdk * dk4 + fac_R * dRdk * dk4) if (use_T or use_R) else 0.0
        grad_out[10] += (fac_T * dTdk * dk5 + fac_R * dRdk * dk5) if (use_T or use_R) else 0.0
        grad_out[11] += (fac_T * dTdk * dk6 + fac_R * dRdk * dk6) if (use_T or use_R) else 0.0
        grad_out[12] += (fac_T * dTdk * dk7 + fac_R * dRdk * dk7) if (use_T or use_R) else 0.0

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _njit_check_bounds_ir_global(
    wl_um_vis: np.ndarray,
    n_tlu_ref_vis: np.ndarray,
    n_tol: float,
    wl_um: np.ndarray,
    p_sell: np.ndarray,
    p_k8: np.ndarray,
    k_max_guard: float,
    n_ref_global: np.ndarray,
    n_ref_tol: float,
) -> bool:
    for i in range(len(wl_um_vis)):
        n_vis = sellmeier_2poles_eval_nj(p_sell, wl_um_vis[i])
        if abs(n_vis - n_tlu_ref_vis[i]) > n_tol:
            return False
            
    has_ref = len(n_ref_global) > 0
    for i in range(len(wl_um)):
        n_val = sellmeier_2poles_eval_nj(p_sell, wl_um[i])
        k_val = k_law_8p_eval(wl_um[i], p_k8)
        
        if not np.isfinite(n_val) or n_val < 1.199 or n_val > 4.001 or k_val > k_max_guard + 1e-6:
            return False
            
        if has_ref:
            if abs(n_val - n_ref_global[i]) > n_ref_tol:
                return False
                
    return True

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _njit_ir_global_mse_fused(
    lam_nm: np.ndarray,
    lam_um: np.ndarray,
    n_sub_f: np.ndarray,
    w: np.ndarray,
    t_exp_f: np.ndarray,
    r_exp_f: np.ndarray,
    p_sell: np.ndarray,
    p_k8: np.ndarray,
    d: float,
    wt: float,
    wr: float,
    need_t: bool,
    need_r: bool,
    is_frosted: bool,
    abs_sub: bool,
    k_sub_f: np.ndarray,
    D_sub: float,
    use_norm: bool,
    t_sub_f: np.ndarray,
) -> float:
    n_pix = lam_nm.shape[0]
    
    loss_t = 0.0
    loss_r = 0.0
    w_sum_t = 0.0
    w_sum_r = 0.0
    n_t = 0
    n_r = 0
        
    for j in range(n_pix):
        wj = w[j]
        # Ignore excluded points (where wj == 0) to avoid unnecessary computation
        if wj == 0.0:
            continue
            
        wl_nm = lam_nm[j]
        wl_um_scalar = lam_um[j]
        
        n_val = sellmeier_2poles_eval_nj(p_sell, wl_um_scalar)
        k_val = k_law_8p_eval(wl_um_scalar, p_k8)
        
        # 2. Transmission single point calculation
        if is_frosted:
            # Frosted Glass: calculate reflection only
            r_th, _ = calculate_transmission_single(
                wl_nm, n_val, k_val, d, complex(n_sub_f[j], 0.0)
            )
            t_th = 0.0
        elif abs_sub:
            r_th, t_th = _calculate_RT_absorbing_sub_single(wl_nm, n_val, k_val, d, n_sub_f[j], k_sub_f[j], D_sub)
        else:
            r_th, t_th = calculate_transmission_single(wl_nm, n_val, k_val, d, complex(n_sub_f[j], 0.0))
            
        if use_norm:
            sub_t = t_sub_f[j]
            sub_t_safe = sub_t if sub_t > 1e-12 else 1.0
            if sub_t > 1e-12:
                t_th = t_th / sub_t_safe
                r_th = r_th / sub_t_safe
            else:
                t_th = np.nan
                r_th = np.nan
            
        # 3. Compute loss using exact error values
        if need_t and not np.isnan(t_th) and not np.isnan(t_exp_f[j]):
            e_t = t_exp_f[j] - t_th
            loss_t += wj * e_t * e_t
            w_sum_t += wj
            n_t += 1
            
        if need_r and not np.isnan(r_th) and not np.isnan(r_exp_f[j]):
            e_r = r_exp_f[j] - r_th
            loss_r += wj * e_r * e_r
            w_sum_r += wj
            n_r += 1
            
    cost = 0.0
    total_w = 0.0
    
    if need_t and n_t >= 5:
        w_safe_t = w_sum_t if w_sum_t > 1e-12 else 1.0
        if w_sum_t > 0:
            mse_t = loss_t / w_safe_t
        else:
            mse_t = 0.0
        cost += mse_t * wt
        total_w += wt

    if need_r and n_r >= 5:
        w_safe_r = w_sum_r if w_sum_r > 1e-12 else 1.0
        if w_sum_r > 0:
            mse_r = loss_r / w_safe_r
        else:
            mse_r = 0.0
        cost += mse_r * wr
        total_w += wr

    if total_w > 0:
        total_w_safe = total_w if total_w > 1e-12 else 1.0
        return cost / total_w_safe
    else:
        return 1e9

class IRGlobalObjective:
    """Refinement objective for Phase 2 (>2500nm) using 13-parameter global model."""

    def __init__(self, wls, target_T, target_R, n_sub, T_sub, R_sub, thickness, n_tlu_ref, config) -> None:

        self.wls = wls.astype(np.float64)

        self.wl_um = (wls / 1000.0).astype(np.float64)

        self.target_T = target_T.astype(np.float64) if target_T is not None else None

        self.target_R = target_R.astype(np.float64) if target_R is not None else None

        self.n_sub = n_sub.astype(np.float64)

        self.T_sub = T_sub.astype(np.float64)

        self.R_sub = R_sub.astype(np.float64)

        self.thickness = float(thickness)

        self.n_tlu_ref = n_tlu_ref.astype(np.float64)

        self.is_frosted = config.is_frosted_glass

        self.data_type = config.data_type

        self.use_norm = config.use_normalized

        self.weight_T = config.weight_T

        self.weight_R = config.weight_R

        # Absorbing substrate: required for correct R/T physics in _compute_cost

        _k = getattr(config, "k_sub_data", None)

        _D = getattr(config, "substrate_thickness_nm", None)

        self._k_sub = _k.astype(np.float64) if _k is not None else None

        self._D_sub = float(_D) if _D is not None else None

        self._abs_sub = config.has_absorbing_substrate

        # Use unified Log-Lambda weighting for broadband optimization.

        # This compensates for sampling density and gives equal weights per octave.

        self.spec_w = spectral_rmse_weights(self.wls, weight_space="log")

        self._inv_T_sub = np.where(self.T_sub > SMALL_EPSILON, 1.0 / self.T_sub, np.nan)

        # Apply Exclusion and Range Masks

        mask = np.ones_like(self.wls, dtype=bool)

        # 1. Lambda Range

        mask &= (self.wls >= config.lambda_min) & (self.wls <= config.lambda_max)

        # 2. Exclude Range

        if config.exclude_min is not None and config.exclude_max is not None:
            mask &= ~((self.wls >= config.exclude_min) & (self.wls <= config.exclude_max))

        # 3. Substrate transmission safety mask (only when use_norm is True)

        if self.use_norm:
            if self.data_type == DataType.TRANSMISSION:
                mask &= (self.T_sub > T_SUB_MIN_T_NORM)
            elif self.data_type == DataType.REFLECTION:
                mask &= (self.T_sub > T_SUB_MIN_R_NORM)
            else:  # DataType.BOTH
                mask &= (self.T_sub > T_SUB_MIN_R_NORM)

        self.spec_w[~mask] = 0.0

        # Normalize weights so mean of ACTIVE points is 1

        if np.any(mask):
            self.spec_w /= np.mean(self.spec_w[mask])

        # Fast-rejection constants for guards in __call__

        self.ir_limit = 2500.0

        self._mask_vis = self.wls <= self.ir_limit

        # Relaxed n_tol for global Phase 2 so Sobol can find feasible starting points

        self.n_tol = 0.20

        # k_max: 0.02 for true IR (>=2500 nm); relaxed for VIS/near-IR-only data

        self.k_max_guard = 0.02 if np.max(self.wls) >= 2500.0 else 0.15

        # VIS subset: used for early continuity check before full n/k/RT computation

        self._wl_um_vis = self.wl_um[self._mask_vis]

        self._n_tlu_ref_vis = self.n_tlu_ref[self._mask_vis]

        # Wavelength range (m) for Sellmeier pole singularity pre-check

        self._wl_um_min = float(self.wl_um.min())

        self._wl_um_max = float(self.wl_um.max())

        # Optional constraint for T-only / R-only sub-fits (set after main R+T search)

        self.n_ref_global = None

        self.n_ref_tol = 0.05

        self._cache_version = 0

        self._cache = None

    def invalidate_cache(self) -> None:

        self._cache_version += 1

        self._cache = None

    def _get_cached(self, p: np.ndarray) -> Any:

        c = self._cache

        if c is None:
            return None

        if c["version"] != self._cache_version:
            return None

        if c["x"].shape != p.shape:
            return None

        if not np.array_equal(c["x"], p):
            return None

        return c

    def _set_cached(self, p: np.ndarray, cost=None, grad=None, n=None, k=None) -> None:

        c = self._cache

        if c is None or c["version"] != self._cache_version or c["x"].shape != p.shape or not np.array_equal(c["x"], p):
            c = {
                "version": self._cache_version,
                "x": p.copy(),
                "cost": None,
                "grad": None,
                "n": None,
                "k": None,
            }

        if cost is not None:
            c["cost"] = float(cost)

        if grad is not None:
            c["grad"] = np.asarray(grad, dtype=np.float64).copy()

        if n is not None:
            c["n"] = np.asarray(n, dtype=np.float64).copy()

        if k is not None:
            c["k"] = np.asarray(k, dtype=np.float64).copy()

        self._cache = c

    def __call__(self, p) -> Any:

        cached = self._get_cached(p)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        # p = [sellmeier_5, k_law_8]
        p_sell = p[:5]
        p_k8 = p[5:]

        # 0. Scalar pre-check: Sellmeier pole singularity

        # L1=p[2], L2=p[4] (m). If either pole lies inside the spectral range,

        # n diverges (NaN/Inf). Skip full vectorized call (~34% of random L2 draws rejected).

        L1, L2 = p[2], p[4]

        if (self._wl_um_min < L1 < self._wl_um_max) or (self._wl_um_min < L2 < self._wl_um_max):
            return 1e12

        # 1. VIS-only Sellmeier to check continuity with Phase 1 before full computation
        # 2. Physical bounds: n in [1.2, 4.0], k <= k_max. NaN guard for fastmath edge cases.
        # 3. Optional reference guard for T-only / R-only sub-fits
        
        is_valid = _njit_check_bounds_ir_global(
            self._wl_um_vis,
            self._n_tlu_ref_vis,
            self.n_tol,
            self.wl_um,
            p_sell,
            p_k8,
            self.k_max_guard,
            self.n_ref_global if self.n_ref_global is not None else np.zeros(0),
            self.n_ref_tol,
        )
        use_T = self.target_T is not None and self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
        use_R = self.target_R is not None and self.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.is_frosted:
            use_T = False
            use_R = self.target_R is not None

        tgt_T = self.target_T if self.target_T is not None else np.zeros(0)
        tgt_R = self.target_R if self.target_R is not None else np.zeros(0)
        k_sub_v = self._k_sub if self._k_sub is not None else np.zeros(0)
        D_sub_v = self._D_sub if self._D_sub is not None else 0.0

        # Zero-Allocation Fused Cost Computation
        cost = _njit_ir_global_mse_fused(
            self.wls,
            self.wl_um,
            self.n_sub,
            self.spec_w,
            tgt_T,
            tgt_R,
            p_sell,
            p_k8,
            self.thickness,
            self.weight_T,
            self.weight_R,
            use_T,
            use_R,
            self.is_frosted,
            self._abs_sub,
            k_sub_v,
            D_sub_v,
            self.use_norm,
            self.T_sub,
        )

        self._set_cached(p, cost=cost)

        return cost

    def _compute_cost(self, n, k) -> Any:

        if self.is_frosted:
            R_c = calculate_reflection_array(self.wls, n, k, self.thickness, self.n_sub)

            # Frosted: single-face R (absolute or relative). Never R/Tnu.

            R_val = R_c

            mse_r, n_r = compute_mse_vectorized(R_val, self.target_R, self.spec_w)

            return mse_r if n_r >= 5 else 1e9

        else:
            # substrate: absorbing (k_sub != 0, IR e.g. Sapphire) or transparent.

            # When _abs_sub: T and R use Beer-Lambert in substrate; required for IR > 2500 nm.

            if self._abs_sub:
                R_c, T_c = calculate_RT_single_layer_absorbing_substrate_array(
                    self.wls, n, k, self.thickness, self.n_sub, self._k_sub, self._D_sub
                )

            else:
                R_c, T_c = calculate_RT_single_layer_backside_array(self.wls, n, k, self.thickness, self.n_sub)

            cost = 0.0

            total_w = 0.0

            if self.target_T is not None and self.data_type in (DataType.TRANSMISSION, DataType.BOTH):
                T_val = T_c

                if self.use_norm:
                    T_val = T_val * self._inv_T_sub

                mse_t, n_t = compute_mse_vectorized(T_val, self.target_T, self.spec_w)

                if n_t >= 5:
                    cost += mse_t * self.weight_T

                    total_w += self.weight_T

            if self.target_R is not None and self.data_type in (DataType.REFLECTION, DataType.BOTH):
                R_val = R_c

                if self.use_norm:
                    R_val = R_val * self._inv_T_sub

                mse_r, n_r = compute_mse_vectorized(R_val, self.target_R, self.spec_w)

                if n_r >= 5:
                    cost += mse_r * self.weight_R

                    total_w += self.weight_R

            return cost / total_w if total_w > 0 else 1e9

    def gradient(self, p) -> Any:

        cached = self._get_cached(p)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        p_sell = p[:5]
        p_k8 = p[5:]

        # 0. Pre-check: skip computation if out of bounds/poles

        is_valid = _njit_check_bounds_ir_global(
            self._wl_um_vis,
            self._n_tlu_ref_vis,
            self.n_tol,
            self.wl_um,
            p_sell,
            p_k8,
            self.k_max_guard,
            self.n_ref_global if self.n_ref_global is not None else np.zeros(0),
            self.n_ref_tol,
        )
        if not is_valid:
            raise ValueError("Out of bounds")

        use_T = self.target_T is not None and self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
        use_R = self.target_R is not None and self.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.is_frosted:
            use_T = False
            use_R = self.target_R is not None

        grad_out = np.zeros(13, dtype=np.float64)

        wT_actual = self.weight_T if use_T else 0.0
        wR_actual = self.weight_R if use_R else 0.0
        total_w = wT_actual + wR_actual if (use_T or use_R) else 1e-9
        wT_actual /= total_w
        wR_actual /= total_w

        tgt_T = self.target_T if self.target_T is not None else np.zeros(0)
        tgt_R = self.target_R if self.target_R is not None else np.zeros(0)
        k_sub_v = self._k_sub if self._k_sub is not None else np.zeros(0)
        D_sub_v = self._D_sub if self._D_sub is not None else 0.0

        _njit_ir_global_gradient_fused(
            self.wls,
            self.wl_um,
            self.n_sub,
            self.spec_w,
            tgt_T,
            tgt_R,
            p_sell,
            p_k8,
            self.thickness,
            wT_actual,
            wR_actual,
            use_T,
            use_R,
            self.is_frosted,
            self._abs_sub,
            k_sub_v,
            D_sub_v,
            self.use_norm,
            self.T_sub,
            grad_out
        )

        self._set_cached(p, grad=grad_out)

        return grad_out

def _phase23_cached_get(cache: dict[str, object] | None, x: np.ndarray) -> dict[str, object] | None:
    """Shared cache access for Phase23 objective wrappers."""
    c = cache
    if c is None:
        return None
    if c["x"].shape != x.shape:
        return None
    if not np.array_equal(c["x"], x):
        return None
    return c

def _phase23_cached_set(
    cache: dict[str, object] | None,
    x: np.ndarray,
    *,
    cost: float | None = None,
    grad: np.ndarray | None = None,
) -> dict[str, object]:
    """Shared cache write for Phase23 objective wrappers."""
    c = cache
    if c is None or c["x"].shape != x.shape or not np.array_equal(c["x"], x):
        c = {"x": x.copy(), "cost": None, "grad": None}

    if cost is not None:
        c["cost"] = float(cost)

    if grad is not None:
        c["grad"] = np.asarray(grad, dtype=np.float64).copy()

    return c

class Phase23SplineObjective:
    """Objective Phase 2.3: n (Sellmeier 5p, tight bounds) + k spline in log k.

    x = [p_sell(5), log_k_knot_values(num_knots)].

    k(lambda) = exp(clip(B @ log_k_knots, log(k_min), log(k_max)))."""

    def __init__(self, base_obj: IRGlobalObjective, knot_lambda_um: np.ndarray, k_max: float) -> None:

        self.obj = base_obj

        self.knot_lambda_um = np.asarray(knot_lambda_um, dtype=np.float64)

        self.num_knots = len(self.knot_lambda_um)

        self.k_max = float(k_max)

        self._log_k_lo = np.log(1e-9)

        self._log_k_hi = np.log(max(self.k_max, 1e-9))

        self._B = SplineBasisCache.get(self.knot_lambda_um, base_obj.wl_um)

        self._p_dummy_8 = np.zeros(8, dtype=np.float64)

        self._cache = None

    def _get_cached(self, x: np.ndarray) -> Any:
        return _phase23_cached_get(self._cache, x)

    def _set_cached(self, x: np.ndarray, cost=None, grad=None) -> None:
        self._cache = _phase23_cached_set(self._cache, x, cost=cost, grad=grad)

    def __call__(self, x: np.ndarray) -> float:

        cached = self._get_cached(x)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        L1, L2 = p_sell[2], p_sell[4]

        if (self.obj._wl_um_min < L1 < self.obj._wl_um_max) or (self.obj._wl_um_min < L2 < self.obj._wl_um_max):
            return 1e12

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return 1e12

        n = sellmeier_2poles_eval_nj(p_sell, self.obj.wl_um)

        log_k = self._B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max + 1e-6):
            return 1e12

        if self.obj.n_ref_global is not None and np.any(np.abs(n - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return 1e12

        cost = self.obj._compute_cost(n, k)

        self._set_cached(x, cost=cost)

        return cost

    def gradient(self, x: np.ndarray) -> np.ndarray:

        cached = self._get_cached(x)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        log_k = self._B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        p_full = np.concatenate([p_sell, self._p_dummy_8])

        n_arr, _, dn_dp, _ = _compute_phase2_derivatives_kernel(self.obj.wl_um, p_full)

        dn_dp = dn_dp[:, :]

        dk_dp = (k[:, np.newaxis] * self._B).T

        use_T = self.obj.target_T is not None and self.obj.data_type in (DataType.TRANSMISSION, DataType.BOTH)

        use_R = self.obj.target_R is not None and self.obj.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.obj.is_frosted:
            use_T, use_R = False, self.obj.target_R is not None

        wT = self.obj.weight_T if use_T else 0.0

        wR = self.obj.weight_R if use_R else 0.0

        total_w = wT + wR if (use_T or use_R) else 1e-9

        wT /= total_w

        wR /= total_w

        tgt_T = self.obj.target_T if self.obj.target_T is not None else np.zeros(0)

        tgt_R = self.obj.target_R if self.obj.target_R is not None else np.zeros(0)

        k_sub_v = self.obj._k_sub if self.obj._k_sub is not None else np.zeros(0)

        D_sub_v = self.obj._D_sub if self.obj._D_sub is not None else 0.0

        grad = _compute_ir_global_cost_gradient_kernel(
            self.obj.wls,
            n_arr,
            k,
            self.obj.thickness,
            self.obj.n_sub,
            tgt_T,
            tgt_R,
            self.obj.spec_w,
            use_T,
            use_R,
            dn_dp,
            dk_dp,
            self.obj.T_sub,
            self.obj.use_norm,
            wT,
            wR,
            self.obj.is_frosted,
            self.obj._abs_sub,
            k_sub_v,
            D_sub_v,
        )

        self._set_cached(x, grad=grad)

        return grad

class Phase23Pass2SplineObjective:
    """Objective Phase 2.3 Pass 2: n (Sellmeier 5p) + k spline in log k + internal positions of the nodes.

    x = [p_sell (5), log_k_knot_values (num_knots), internal_lambda (num_knots-2)].

    knot_lam = [wl_min, sort(internal_lambda), wl_max]. Lambda gradient by finite differences."""

    def __init__(
        self,
        base_obj: IRGlobalObjective,
        num_knots: int,
        wl_min_um: float,
        wl_max_um: float,
        k_max: float,
        min_knot_dist_um: float,
    ) -> None:

        self.obj = base_obj

        self.num_knots = num_knots

        self.n_internes = num_knots - 2

        self.wl_min = float(wl_min_um)

        self.wl_max = float(wl_max_um)

        self.k_max = float(k_max)

        self.min_knot_dist = float(min_knot_dist_um)

        self._log_k_lo = np.log(1e-9)

        self._log_k_hi = np.log(max(self.k_max, 1e-9))

        self._p_dummy_8 = np.zeros(8, dtype=np.float64)

        self._fd_eps = max(1e-7 * (wl_max_um - wl_min_um), 1e-8)

        self._cache = None

    def _get_cached(self, x: np.ndarray) -> Any:
        return _phase23_cached_get(self._cache, x)

    def _set_cached(self, x: np.ndarray, cost=None, grad=None) -> None:
        self._cache = _phase23_cached_set(self._cache, x, cost=cost, grad=grad)

    def _knot_lam_from_x(self, x: np.ndarray) -> np.ndarray:

        lam_int = np.sort(x[5 + self.num_knots : 5 + self.num_knots + self.n_internes].copy())

        knot_lam = np.concatenate([[self.wl_min], lam_int, [self.wl_max]])

        knot_lam = _ensure_strictly_increasing(knot_lam, min_gap=1e-9)

        knot_lam[0] = self.wl_min

        knot_lam[-1] = self.wl_max

        if knot_lam[1] <= knot_lam[0]:
            knot_lam[1] = knot_lam[0] + 1e-9

        if len(knot_lam) > 2 and knot_lam[-2] >= knot_lam[-1]:
            knot_lam[-2] = knot_lam[-1] - 1e-9

        return knot_lam

    def __call__(self, x: np.ndarray) -> float:

        cached = self._get_cached(x)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        knot_lam = self._knot_lam_from_x(x)

        L1, L2 = p_sell[2], p_sell[4]

        if (self.obj._wl_um_min < L1 < self.obj._wl_um_max) or (self.obj._wl_um_min < L2 < self.obj._wl_um_max):
            return 1e12

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return 1e12

        n = sellmeier_2poles_eval_nj(p_sell, self.obj.wl_um)

        from scipy.interpolate import CubicSpline
        spline = CubicSpline(knot_lam, log_k_knot, bc_type="natural", extrapolate=True)
        log_k = spline(self.obj.wl_um)

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max + 1e-6):
            return 1e12

        if self.obj.n_ref_global is not None and np.any(np.abs(n - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return 1e12

        cost = self.obj._compute_cost(n, k)

        self._set_cached(x, cost=cost)

        return cost

    def gradient(self, x: np.ndarray) -> np.ndarray:

        cached = self._get_cached(x)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        knot_lam = self._knot_lam_from_x(x)

        # Invariants for all lambda-knot FD probes in this gradient call.

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return np.zeros_like(x, dtype=np.float64)

        B = SplineBasisCache.get(knot_lam, self.obj.wl_um)

        log_k = B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        p_full = np.concatenate([p_sell, self._p_dummy_8])

        n_arr, _, dn_dp, _ = _compute_phase2_derivatives_kernel(self.obj.wl_um, p_full)

        if not np.all(np.isfinite(n_arr)) or np.any(n_arr < 1.199) or np.any(n_arr > 4.001):
            return np.zeros_like(x, dtype=np.float64)

        if self.obj.n_ref_global is not None and np.any(np.abs(n_arr - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return np.zeros_like(x, dtype=np.float64)

        dn_dp = dn_dp[:, :]

        dk_dp = (k[:, np.newaxis] * B).T

        use_T = self.obj.target_T is not None and self.obj.data_type in (DataType.TRANSMISSION, DataType.BOTH)

        use_R = self.obj.target_R is not None and self.obj.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.obj.is_frosted:
            use_T, use_R = False, self.obj.target_R is not None

        wT = self.obj.weight_T if use_T else 0.0

        wR = self.obj.weight_R if use_R else 0.0

        total_w = wT + wR if (use_T or use_R) else 1e-9

        wT /= total_w

        wR /= total_w

        tgt_T = self.obj.target_T if self.obj.target_T is not None else np.zeros(0)

        tgt_R = self.obj.target_R if self.obj.target_R is not None else np.zeros(0)

        k_sub_v = self.obj._k_sub if self.obj._k_sub is not None else np.zeros(0)

        D_sub_v = self.obj._D_sub if self.obj._D_sub is not None else 0.0

        grad_sell_logk = _compute_ir_global_cost_gradient_kernel(
            self.obj.wls,
            n_arr,
            k,
            self.obj.thickness,
            self.obj.n_sub,
            tgt_T,
            tgt_R,
            self.obj.spec_w,
            use_T,
            use_R,
            dn_dp,
            dk_dp,
            self.obj.T_sub,
            self.obj.use_norm,
            wT,
            wR,
            self.obj.is_frosted,
            self.obj._abs_sub,
            k_sub_v,
            D_sub_v,
        )

        grad_lambda = np.zeros(self.n_internes, dtype=np.float64)

        x_plus = x.copy()

        x_minus = x.copy()

        def _cost_fixed_n_for_knot(knot_lam_local: np.ndarray) -> float:

            from scipy.interpolate import CubicSpline
            spline_local = CubicSpline(knot_lam_local, log_k_knot, bc_type="natural", extrapolate=True)
            log_k_local = spline_local(self.obj.wl_um)

            log_k_local_c = np.clip(log_k_local, self._log_k_lo, self._log_k_hi)

            k_local = np.exp(log_k_local_c)

            if np.any(k_local > self.k_max + 1e-6) or not np.all(np.isfinite(k_local)):
                return 1e12

            return self.obj._compute_cost(n_arr, k_local)

        for i in range(self.n_internes):
            idx = 5 + self.num_knots + i

            x_plus[idx] = x[idx] + self._fd_eps

            x_minus[idx] = x[idx] - self._fd_eps

            knot_plus = self._knot_lam_from_x(x_plus)

            knot_minus = self._knot_lam_from_x(x_minus)

            c_plus = _cost_fixed_n_for_knot(knot_plus)

            c_minus = _cost_fixed_n_for_knot(knot_minus)

            if np.isfinite(c_plus) and np.isfinite(c_minus):
                grad_lambda[i] = (c_plus - c_minus) / (2.0 * self._fd_eps)

            x_plus[idx] = x[idx]

            x_minus[idx] = x[idx]

        grad_full = np.concatenate([grad_sell_logk, grad_lambda])
        return grad_full


class TLUObjective:
    """Objective function for TLU optimization - Supports frosted glass"""

    def __init__(
        self,
        wavelengths: np.ndarray,
        target_T: np.ndarray | None,
        target_R: np.ndarray | None,
        n_substrate: np.ndarray,
        data_type: DataType,
        thickness_bounds: tuple,
        use_normalized: bool = True,
        weight_T: float = 1.0,
        weight_R: float = 1.0,
        exclude_range: tuple | None = None,
        is_frosted_glass: bool = False,
        lambda_max_fit: float | None = None,
        has_absorbing_substrate: bool = False,
        k_sub_data: np.ndarray | None = None,
        substrate_thickness_nm: float | None = None,
    ) -> None:

        self.wavelengths = wavelengths.astype(np.float64)

        self.n_substrate = n_substrate.astype(np.float64)

        self.data_type = data_type

        self.thickness_bounds = thickness_bounds

        self.use_normalized = use_normalized

        self.weight_T = weight_T

        self.weight_R = weight_R

        self.is_frosted_glass = is_frosted_glass

        self.E_array = (HC_EV_NM / self.wavelengths).astype(np.float64)

        self.target_T = target_T.astype(np.float64) if target_T is not None else None

        self.target_R = target_R.astype(np.float64) if target_R is not None else None

        self.has_absorbing_substrate = has_absorbing_substrate

        self.k_sub_data = k_sub_data.astype(np.float64) if k_sub_data is not None else None

        self.substrate_thickness_nm = float(substrate_thickness_nm) if substrate_thickness_nm is not None else None

        # References for normalization

        self.T_substrate = calculate_bare_substrate_RT(self.wavelengths, self.n_substrate)

        self._inv_T_sub = np.where(self.T_substrate > SMALL_EPSILON, 1.0 / self.T_substrate, np.nan)

        if is_frosted_glass:
            self.R_substrate = calculate_single_interface_R(self.wavelengths, self.n_substrate)

        else:
            self.R_substrate = (
                calculate_bare_substrate_RT,
                calculate_single_interface_R(self.wavelengths, self.n_substrate),
            )

        # Use unified Log-Lambda weighting for broadband optimization.

        # This compensates for sampling density and gives equal weights per octave.

        self.weights = spectral_rmse_weights(self.wavelengths, weight_space="log")

        if exclude_range:
            ex_min, ex_max = exclude_range

            mask = (self.wavelengths >= ex_min) & (self.wavelengths <= ex_max)

            self.weights[mask] = 0.0

        if lambda_max_fit is not None:
            mask_fit = self.wavelengths > lambda_max_fit

            self.weights[mask_fit] = 0.0

        # Normalize weights so mean of ACTIVE points is 1

        active_mask = self.weights > 1e-12

        if np.any(active_mask):
            self.weights /= np.mean(self.weights[active_mask])

        self.n_evals = 0

        self.best_value = np.inf

        self.best_params = None

        self._cache = None

        # Eg (eV): if Eg << hv over part of the window, the TLU becomes inconsistent (wild n/k).
        # Lower bound = max photon on grid + small margin (sub-gap model usable across the full fit).

        _eg_lo = float(max(0.5, min(9.5, float(np.max(self.E_array)) + 0.05)))

        _e0_lo = float(max(1.5, _eg_lo + 0.35))

        self.param_bounds = np.array(
            [
                [_eg_lo, 10.0],  # Eg
                [10.0, 2000.0],  # A
                [_e0_lo, 10.0],  # E0 > Eg en pratique
                [0.1, 10.0],  # C
                [0.01, 3.0],  # Eu
                [1.4, 10.0],  # eps_inf
            ],
            dtype=np.float64,
        )

        # If T data shows a highly transparent slab (T/Tsub or normalized T), the scan must not
        # start with giant k: soft ceiling on max(k) well below K_MAX_LIMIT.

        self._k_soft_ceiling = float(K_MAX_LIMIT) - float(TLU_SOFT_EDGE_MARGIN)

        self._prior_transparent_low_k = False

        if (
            target_T is not None
            and self.use_normalized
            and self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
            and not self.is_frosted_glass
        ):
            wm = self.weights > 1e-12

            if np.any(wm):
                tt = np.asarray(target_T)[wm]

                ww = self.weights[wm]

                mask = np.isfinite(tt) & (ww > 1e-15)

                if np.any(mask):
                    w_med = float(np.nanmedian(tt[mask]))

                    if w_med >= 0.58:
                        self._prior_transparent_low_k = True

                        self._k_soft_ceiling = min(self._k_soft_ceiling, 3e-3)

        # WARNING log budget in __call__ ("why does k explode" analysis) without flooding 20k evals.

        self._tlu_explode_logs_left = 20

    def format_diag_line(self, params: np.ndarray) -> str:
        """Human-readable line: n, k_max @lambda, k ceilings, TLU (Eg, Eu, ...), eps2, E>Eg fraction."""

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size < 7:
            return "diag: params incomplets"

        d = float(p[0])

        Eg, A, E0, C, Eu, eps_inf = [float(p[i]) for i in range(1, 7)]

        eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        ik = int(np.argmax(k_calc))

        kmax = float(k_calc[ik])

        wl_k = float(self.wavelengths[ik])

        n_lo = float(np.min(n_calc))

        n_hi = float(np.max(n_calc))

        emax = float(np.max(self.E_array))

        eg_frac = float(np.mean(self.E_array > Eg))

        eps2_max = float(np.max(eps2))

        eps2_at_kmax = float(eps2[ik])

        k_ceil = float(getattr(self, "_k_soft_ceiling", float(K_MAX_LIMIT)))

        _pri = bool(getattr(self, "_prior_transparent_low_k", False))

        return (
            f"n∈[{n_lo:.3f},{n_hi:.3f}] k_max={kmax:.4g} @λ={wl_k:.0f}nm "
            f"k_ceiling={k_ceil:.4g}(prior_T={_pri}) "
            f"d={d:.1f}nm Eg={Eg:.4f} Eu={Eu:.4f} E0={E0:.4f} "
            f"frac(E>Eg)={eg_frac:.2f} eps2_max={eps2_max:.4g} eps2@kmax={eps2_at_kmax:.4g} hν_max={emax:.4f}eV"
        )

    def format_k_line(self, params: np.ndarray) -> str:
        """Short string centered on k(lambda) for Phase 1 PGLOBAL logs."""

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size < 7:
            return "k: params incomplets"

        Eg, A, E0, C, Eu, eps_inf = [float(p[i]) for i in range(1, 7)]

        eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        ik = int(np.argmax(k_calc))

        k_min = float(np.min(k_calc))

        k_med = float(np.median(k_calc))

        k_max = float(np.max(k_calc))

        wl_k = float(self.wavelengths[ik])

        ik_lo = int(np.argmin(k_calc))

        wl_lo = float(self.wavelengths[ik_lo])

        k_ceil = float(getattr(self, "_k_soft_ceiling", float(K_MAX_LIMIT)))

        return (
            f"k_min={k_min:.4g} k_med={k_med:.4g} k_max={k_max:.4g} | λ(k_max)={wl_k:.0f} nm λ(k_min)={wl_lo:.0f} nm "
            f"| k_ceiling_soft={k_ceil:.4g}"
        )

    def get_bounds(self) -> np.ndarray:

        thickness_bound = np.array([[self.thickness_bounds[0], self.thickness_bounds[1]]], dtype=np.float64)

        return np.vstack([thickness_bound, self.param_bounds])

    def _get_cached(self, params: np.ndarray) -> Any:

        c = self._cache

        if c is None:
            return None

        if c["x"].shape != params.shape:
            return None

        if not np.array_equal(c["x"], params):
            return None

        return c

    def _set_cached(self, params: np.ndarray, cost=None, grad=None) -> None:

        c = self._cache

        if c is None or c["x"].shape != params.shape or not np.array_equal(c["x"], params):
            c = {"x": params.copy(), "cost": None, "grad": None}

        if cost is not None:
            c["cost"] = float(cost)

        if grad is not None:
            c["grad"] = np.asarray(grad, dtype=np.float64).copy()

        self._cache = c

    def gradient(self, params: np.ndarray) -> np.ndarray:
        """Computes analytic gradient of the objective function."""

        cached = self._get_cached(params)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        # Unpack parameters

        thickness = params[0]

        Eg, A, E0, C, Eu, eps_inf = params[1:7]

        grad = np.zeros(7, dtype=np.float64)

        # --- Penalty Gradients ---

        # Thickness bounds

        if thickness < self.thickness_bounds[0]:
            # P = 1000 * (min - t)^2 -> dP/dt = -2000 * (min - t)

            grad[0] += -2000.0 * (self.thickness_bounds[0] - thickness)

        elif thickness > self.thickness_bounds[1]:
            # P = 1000 * (t - max)^2 -> dP/dt = 2000 * (t - max)

            grad[0] += 2000.0 * (thickness - self.thickness_bounds[1])

        # E0 vs Eg constraint

        # if E0 <= Eg: P = 100 * (Eg - E0 + 0.1)^2

        # dP/dEg = 200 * (Eg - E0 + 0.1)

        # dP/dE0 = -200 * (Eg - E0 + 0.1)

        if E0 <= Eg:
            term = 200.0 * (Eg - E0 + 0.1)

            grad[1] += term  # Eg is params[1]

            grad[3] -= term  # E0 is params[3]

        elif E0 - Eg < 0.3:
            # P = 10 * (0.3 - (E0 - Eg))^2 = 10 * (0.3 - E0 + Eg)^2

            # dP/dEg = 20 * (0.3 - E0 + Eg)

            # dP/dE0 = -20 * (0.3 - E0 + Eg)

            term = 20.0 * (0.3 - E0 + Eg)

            grad[1] += term

            grad[3] -= term

        # Positivity constraints (soft barrier?)

        # TLUObjective returns 1e12 + penalty if invalid.

        # Analytic gradient near 0 might be problematic but we assume valid region for local polish.

        if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
            # Return zero gradient or steep gradient?

            # Zero is safer to avoid exploding optimizers if they step out

            grad0 = np.zeros(7)

            self._set_cached(params, grad=grad0)

            return grad0

        # --- Cost Gradient ---

        # 1. Compute Material Derivatives (dn/dp, dk/dp)

        # Kernel returns dMSE/[Eg, A, E0, C, Eu, eps_inf]

        n_calc, k_calc, dn_dp, dk_dp = _compute_tlu_derivatives_kernel(self.E_array, Eg, A, E0, C, Eu, eps_inf)

        # --- Physical Penalty Gradients ---

        _m = float(TLU_SOFT_EDGE_MARGIN)

        _n_lo = float(N_MIN_LIMIT) + _m

        _n_hi = float(N_MAX_LIMIT) - _m

        _k_hi = float(K_MAX_LIMIT) - _m

        _k_hi_eff = float(min(_k_hi, getattr(self, "_k_soft_ceiling", _k_hi)))

        _pk = float(3500.0 if getattr(self, "_prior_transparent_low_k", False) else 1000.0)

        _n_lo_eff = float(_n_lo)

        if getattr(self, "_prior_transparent_low_k", False):
            _n_lo_eff = max(_n_lo_eff, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

        idx_n_min = np.argmin(n_calc)

        n_min = n_calc[idx_n_min]

        if n_min < _n_lo_eff:
            dPd_n = -2000.0 * (_n_lo_eff - n_min)

            grad[1:7] += dPd_n * dn_dp[:, idx_n_min]

        idx_n_max = np.argmax(n_calc)

        n_max = n_calc[idx_n_max]

        if n_max > _n_hi:
            dPd_n = 2000.0 * (n_max - _n_hi)

            grad[1:7] += dPd_n * dn_dp[:, idx_n_max]

        idx_k_max = np.argmax(k_calc)

        k_peak = k_calc[idx_k_max]

        if k_peak > _k_hi_eff:
            dPd_k = 2.0 * _pk * (k_peak - _k_hi_eff)

            grad[1:7] += dPd_k * dk_dp[:, idx_k_max]

        # 2. Compute Total MSE Gradient (dMSE/d_thickness, dMSE/d_params)

        use_T = (
            self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
            and self.target_T is not None
            and not self.is_frosted_glass
        )

        use_R = self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None

        target_T_arr = self.target_T if self.target_T is not None else np.zeros_like(self.wavelengths)

        target_R_arr = self.target_R if self.target_R is not None else np.zeros_like(self.wavelengths)

        # Normalize data type weights to match __call__ scaling

        total_dt_weight = (self.weight_T if use_T else 0.0) + (self.weight_R if use_R else 0.0)

        wT_norm = self.weight_T / total_dt_weight if total_dt_weight > 0 else 0.0

        wR_norm = self.weight_R / total_dt_weight if total_dt_weight > 0 else 0.0

        # Call kernel with full normalization support

        if self.has_absorbing_substrate:
            # Use the more general IR global gradient kernel which supports absorption.
            # _compute_ir_global_cost_gradient_kernel returns a vector of size
            # (1 + dn_dp.shape[0] + dk_dp.shape[0]) when compute_thickness_gradient=True.
            # For TLU, dn_dp and dk_dp SHARE the same 6 parameters [Eg, A, E0, C, Eu, eps_inf].
            # mse_grad_raw layout: [thickness, dn0..dn5, dk0..dk5] (size 1 + 6 + 6 = 13)
            # We accumulate into grad[0:7] = [thickness, Eg, A, E0, C, Eu, eps_inf].

            mse_grad_raw = _compute_ir_global_cost_gradient_kernel(
                self.wavelengths,
                n_calc,
                k_calc,
                thickness,
                self.n_substrate,
                target_T_arr,
                target_R_arr,
                self.weights,
                use_T,
                use_R,
                dn_dp,
                dk_dp,
                self.T_substrate,
                self.use_normalized,
                wT_norm,
                wR_norm,
                self.is_frosted_glass,
                True,  # has_absorbing_substrate
                self.k_sub_data,
                self.substrate_thickness_nm,
                True,  # compute_thickness_gradient
            )

            # Map result back to (7,) TLU gradient vector.
            mse_grad = np.zeros(7, dtype=np.float64)
            mse_grad[0] = mse_grad_raw[0]
            mse_grad[1:7] += mse_grad_raw[1:7]
            mse_grad[1:7] += mse_grad_raw[7:13]

        else:
            # Use specialized fast kernel for transparent substrates

            mse_grad = _compute_index_cost_gradient_kernel(
                self.wavelengths,
                n_calc,
                k_calc,
                thickness,
                self.n_substrate,
                target_T_arr,
                target_R_arr,
                self.weights,
                use_T,
                use_R,
                dn_dp,
                dk_dp,
                self.T_substrate,
                self.R_substrate,
                self.use_normalized,
                wT_norm,
                wR_norm,
            )

        grad += mse_grad

        self._set_cached(params, grad=grad)

        return grad

    def __call__(self, params: np.ndarray) -> float:

        cached = self._get_cached(params)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        self.n_evals += 1

        try:
            thickness = params[0]

            Eg, A, E0, C, Eu, eps_inf = params[1:7]

            penalty = 0.0

            if thickness < self.thickness_bounds[0]:
                penalty += 1000 * (self.thickness_bounds[0] - thickness) ** 2

            elif thickness > self.thickness_bounds[1]:
                penalty += 1000 * (thickness - self.thickness_bounds[1]) ** 2

            if E0 <= Eg:
                penalty += 100 * (Eg - E0 + 0.1) ** 2

            elif E0 - Eg < 0.3:
                penalty += 10 * (0.3 - (E0 - Eg)) ** 2

            if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
                return 1e12 + penalty

            eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

            eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

            n_calc, k_calc, is_valid = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

            if not is_valid:
                return 1e12 + penalty

            # --- Physical Constraints (Soft Penalty) ---

            # Matches the same global bounds as epsilon_to_nk, with a slight inner margin:

            # compatible with all material types within [N_MIN,N_MAX], k up to K_MAX_LIMIT.

            _m = float(TLU_SOFT_EDGE_MARGIN)

            _n_lo = float(N_MIN_LIMIT) + _m

            _n_hi = float(N_MAX_LIMIT) - _m

            _k_hi = float(K_MAX_LIMIT) - _m

            _k_hi_eff = float(min(_k_hi, getattr(self, "_k_soft_ceiling", _k_hi)))

            _pk = float(3500.0 if getattr(self, "_prior_transparent_low_k", False) else 1000.0)

            _n_lo_eff = float(_n_lo)

            if getattr(self, "_prior_transparent_low_k", False):
                _n_lo_eff = max(_n_lo_eff, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

            n_min = np.min(n_calc)

            n_max = np.max(n_calc)

            k_peak = np.max(k_calc)

            if n_min < _n_lo_eff:
                penalty += 1000.0 * (_n_lo_eff - n_min) ** 2

            if n_max > _n_hi:
                penalty += 1000.0 * (n_max - _n_hi) ** 2

            if k_peak > _k_hi_eff:
                penalty += _pk * (k_peak - _k_hi_eff) ** 2

            _ex_left = int(getattr(self, "_tlu_explode_logs_left", 0))

            if k_peak > _k_hi_eff and _ex_left > 0:
                self._tlu_explode_logs_left = _ex_left - 1

                _ik2 = int(np.argmax(k_calc))

                _egf = float(np.mean(self.E_array > Eg))

                _e2m = float(np.max(eps2))

                _e2k = float(eps2[_ik2])

                logging.getLogger("CERTUS").warning(
                    "[INDEX.tlu_k_penalty] eval=%d remaining_logs=%d k_max=%.6g k_limit=%.4g penalty_power=%.0f Eg=%.4f Eu=%.4f E0=%.4f frac_E_gt_Eg=%.2f eps2_max=%.4g eps2_at_kmax=%.4g penalty=%.4g",
                    int(self.n_evals),
                    int(self._tlu_explode_logs_left),
                    float(k_peak),
                    float(_k_hi_eff),
                    _pk,
                    float(Eg),
                    float(Eu),
                    float(E0),
                    _egf,
                    _e2m,
                    _e2k,
                    float(_pk * (k_peak - _k_hi_eff) ** 2) if k_peak > _k_hi_eff else 0.0,
                )

            total_mse = 0.0

            total_weight = 0.0

            if self.is_frosted_glass:
                if self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None:
                    R_calc = calculate_reflection_array(self.wavelengths, n_calc, k_calc, thickness, self.n_substrate)

                    # Frosted = 1 face: R or Rnu only. Never R/Tnu.

                    R_val = R_calc

                    mse_R, n_valid_R = compute_mse_vectorized(R_val, self.target_R, self.weights)

                    if n_valid_R >= 5:
                        total_mse += mse_R * self.weight_R

                        total_weight += self.weight_R

            else:
                if self.has_absorbing_substrate:
                    R_calc, T_calc = calculate_RT_single_layer_absorbing_substrate_array(
                        self.wavelengths,
                        n_calc,
                        k_calc,
                        thickness,
                        self.n_substrate,
                        self.k_sub_data,
                        self.substrate_thickness_nm,
                    )

                else:
                    R_calc, T_calc = calculate_RT_single_layer_backside_array(
                        self.wavelengths, n_calc, k_calc, thickness, self.n_substrate
                    )

                if self.data_type in (DataType.TRANSMISSION, DataType.BOTH) and self.target_T is not None:
                    if self.use_normalized:
                        T_val = T_calc * self._inv_T_sub

                    else:
                        T_val = T_calc

                    mse_T, n_valid_T = compute_mse_vectorized(T_val, self.target_T, self.weights)

                    if n_valid_T >= 5:
                        total_mse += mse_T * self.weight_T

                        total_weight += self.weight_T

                if self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None:
                    if self.use_normalized:
                        R_val = R_calc * self._inv_T_sub

                    else:
                        R_val = R_calc

                    mse_R, n_valid_R = compute_mse_vectorized(R_val, self.target_R, self.weights)

                    if n_valid_R >= 5:
                        total_mse += mse_R * self.weight_R

                        total_weight += self.weight_R

            if total_weight < SMALL_EPSILON:
                return 1e12 + penalty

            mse = total_mse / total_weight

            total = mse + penalty

            if total < self.best_value:
                self.best_value = total

                self.best_params = params.copy()

            self._set_cached(params, cost=total)

            return total

        except NUMERICAL_FAULT_EXCEPTIONS:
            # Critical: objective function errors fall back to large penalty

            return 1e12

def warmup_index_objectives(silent: bool = True) -> None:
    """Pre-compiles critical Numba kernels for INDEX to eliminate first-call JIT latency."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            n_pix = 10
            wls = np.linspace(400.0, 800.0, n_pix, dtype=np.float64)
            lam_um = wls / 1000.0
            n_sub_f = np.full(n_pix, 1.5, dtype=np.float64)
            w = np.ones(n_pix, dtype=np.float64)
            t_exp_f = np.full(n_pix, 0.9, dtype=np.float64)
            r_exp_f = np.full(n_pix, 0.1, dtype=np.float64)
            p_sell = np.array([1.5, 0.5, 0.2, 0.1, 0.1], dtype=np.float64)
            p_k8 = np.array([-1.0, -10.0, -2.0, -15.0, 0.05, 1.0, 0.2, 2.0], dtype=np.float64)
            k_sub_f = np.zeros(n_pix, dtype=np.float64)
            t_sub_f = np.full(n_pix, 0.92, dtype=np.float64)

            _njit_ir_global_mse_fused(
                wls, lam_um, n_sub_f, w, t_exp_f, r_exp_f,
                p_sell, p_k8, 100.0, 0.5, 0.5,
                True, True, False, False, k_sub_f, 0.0, False, t_sub_f
            )

            grad_out = np.zeros(13, dtype=np.float64)
            _njit_ir_global_gradient_fused(
                wls, lam_um, n_sub_f, w, t_exp_f, r_exp_f,
                p_sell, p_k8, 100.0, 0.5, 0.5,
                True, True, False, False, k_sub_f, 0.0, False, t_sub_f, grad_out
            )

            _njit_check_bounds_ir_global(
                lam_um, np.full(n_pix, 2.0), 100.0, lam_um, p_sell, p_k8, 5.0, np.zeros(0), 0.0
            )
        except Exception:
            pass
