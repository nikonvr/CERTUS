#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Post-pass: joint local polish of alpha≈1 together with thickness and spline nodes."""

from __future__ import annotations

import logging
from threading import Event
from typing import Any

import numpy as np

from certus_index_spline_core import (
    SplineNonlinearAlphaConfig,
    SplineOptConfig,
    SplinePGlobalConfig,
    canonical_spline_sigma_knots,
    n_lambda_rising_with_wavelength_penalty,
    physical_nodes_to_x_slice_n,
)
from spline_objective import (
    nk_from_x_pwlnk,
    spline_objective_mse_on_masked_grid,
    x_slice_n_to_physical_nodes,
)

log = logging.getLogger("CERTUS")

ALPHA_NL_LO: float = 0.995
ALPHA_NL_HI: float = 1.005
ALPHA_NL_STEP: float = 0.0005
ALPHA_NL_SIGMA_PRIOR: float = 0.0015

_NL_KEYS_CLEAR: tuple[str, ...] = (
    "nl_alpha_opt",
    "nl_lam_nm",
    "n_lam_nl",
    "k_lam_nl",
    "d_nm_nl",
    "nl_rmse_vs_meas_orig",
    "nl_rmse_vs_meas_scaled",
    "nl_rmse_reference_best",
    "nl_profile_mode",
    "nl_optim_ok",
    "nl_optim_message",
    "nl_objective_final",
    "nl_second_pass_applied",
    "nl_alpha_grid_n",
    "nl_alpha_grid_step",
    "nl_alpha_budget_mode",
    "nl_second_pass_maxfun",
    "nl_alpha_identifiable",
    "nl_alpha_identifiability_note",
    "nl_alpha_budget_maxfun_hits",
    "nl_alpha_raw_rmse_span",
    "nl_alpha_steps_evaluated",
    "nl_alpha_scan_early_stopped",
    "nl_alpha_adaptive_applied",
    "nl_alpha_selection_criterion",
    "nl_alpha_best_by_objective",
    "nl_alpha_best_by_raw_rmse",
    "nl_alpha_best_by_scaled_rmse",
    "nl_alpha_selection_diverges_from_raw_rmse",
    "nl_alpha_identifiability_thr_flat",
    "nl_alpha_identifiability_thr_budget_hits",
    "nl_alpha_sigma_prior_used",
    "nl_alpha_prior_weight",
    "nl_alpha_objective_mse_component",
    "nl_alpha_objective_prior_component",
)


def clear_nl_result_fields(out: dict[str, Any]) -> None:
    """Remove all NL-alpha result keys from *out* to reset state."""
    for k in _NL_KEYS_CLEAR:
        out.pop(k, None)


def _cfg_get_first(cfg: Any, *names: str, default: Any) -> Any:
    for name in names:
        v = getattr(cfg, name, None)
        if v is not None:
            return v
    return default


def _interp_on_sigma_knots(lam_nm: np.ndarray, y_lam: np.ndarray, sk: np.ndarray) -> np.ndarray:
    lam = np.asarray(lam_nm, dtype=np.float64).ravel()
    yv = np.asarray(y_lam, dtype=np.float64).ravel()
    skv = np.asarray(sk, dtype=np.float64).ravel()
    if lam.size < 2 or yv.size != lam.size or skv.size < 2:
        return np.array([], dtype=np.float64)
    sig_src = 1.0 / np.maximum(lam, 1e-12)
    order = np.argsort(sig_src)
    return np.interp(skv, sig_src[order], yv[order]).astype(np.float64, copy=False)


def _pick_nl_start_x_and_mode(
    cfg: SplineOptConfig,
    out: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, str] | None:
    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    if lam_full.size < 2:
        return None
    profile = str(getattr(cfg, "nk_profile_interp", "smooth") or "smooth").strip().lower()
    sk_out = np.asarray(out.get("sigma_knots", []), dtype=np.float64).ravel()
    sk_canon = canonical_spline_sigma_knots(float(np.min(lam_full)), float(np.max(lam_full)))
    x0_raw = out.get("x_seg_spline_sigma", out.get("x"))
    x0 = np.asarray(x0_raw, dtype=np.float64).ravel() if x0_raw is not None else np.array([], dtype=np.float64)

    candidates: list[np.ndarray] = []
    if sk_out.size >= 2:
        candidates.append(sk_out)
    if sk_canon.size >= 2 and (not candidates or int(sk_canon.size) != int(candidates[0].size)):
        candidates.append(sk_canon)

    for sk in candidates:
        k = int(np.asarray(sk, dtype=np.float64).size)
        if x0.size == 1 + 2 * k:
            return np.asarray(x0, dtype=np.float64).copy(), np.asarray(sk, dtype=np.float64).copy(), profile

    d0_raw = out.get("d_nm_seg_spline_sigma", out.get("d_nm"))
    n_lam_raw = out.get("n_lam_seg_spline_sigma", out.get("n_lam"))
    k_lam_raw = out.get("k_lam_seg_spline_sigma", out.get("k_lam"))
    if d0_raw is None or n_lam_raw is None or k_lam_raw is None:
        return None
    try:
        d0 = float(d0_raw)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(d0):
        return None

    sk = np.asarray(candidates[0] if candidates else sk_canon, dtype=np.float64).ravel()
    if sk.size < 2:
        return None
    n_phys = _interp_on_sigma_knots(lam_full, np.asarray(n_lam_raw, dtype=np.float64).ravel(), sk)
    k_nodes = _interp_on_sigma_knots(lam_full, np.asarray(k_lam_raw, dtype=np.float64).ravel(), sk)
    if n_phys.size != int(sk.size) or k_nodes.size != int(sk.size):
        return None
    if cfg.n_mono_band_nm is None:
        n_slice = np.asarray(n_phys, dtype=np.float64).copy()
    else:
        n_slice = physical_nodes_to_x_slice_n(n_phys, sk, cfg.n_mono_band_nm)
    k_floor = max(float(getattr(cfg, "k_clip_lo", 1e-8) or 1e-8), 1e-12)
    k_ceil = max(float(getattr(cfg, "k_clip_hi", 10.0) or 10.0), k_floor)
    L_slice = np.log(np.clip(k_nodes, k_floor, k_ceil))
    x_init = np.concatenate((np.asarray([d0], dtype=np.float64), n_slice.ravel(), L_slice.ravel()))
    return np.asarray(x_init, dtype=np.float64), np.asarray(sk, dtype=np.float64).copy(), profile


def nl_alpha_grid_values() -> np.ndarray:
    n = int(round((ALPHA_NL_HI - ALPHA_NL_LO) / ALPHA_NL_STEP)) + 1
    return np.linspace(ALPHA_NL_LO, ALPHA_NL_HI, max(2, n), dtype=np.float64)


def nl_alpha_scan_order_values() -> np.ndarray:
    alphas = nl_alpha_grid_values()
    if alphas.size <= 1:
        return alphas.copy()
    idx0 = int(np.argmin(np.abs(alphas - 1.0)))
    hi = int(alphas.size - 1)
    order_idx: list[int] = [idx0]
    j = 1
    while True:
        got = False
        li, ri = idx0 - j, idx0 + j
        if li >= 0:
            order_idx.append(li)
            got = True
        if ri <= hi:
            order_idx.append(ri)
            got = True
        if not got:
            break
        j += 1
    return np.asarray(alphas[np.array(order_idx, dtype=np.intp)], dtype=np.float64)


def nonlinear_alpha_lbfgs_maxfun_per_step_from_views(
    alpha_view: SplineNonlinearAlphaConfig,
    pglobal_view: SplinePGlobalConfig,
) -> tuple[int, str]:
    """View-based core of :func:`nonlinear_alpha_lbfgs_maxfun_per_step` (Lot B2)."""
    mode = str(alpha_view.nonlinear_alpha_budget_mode or "slow").strip().lower()
    p_max = int(pglobal_view.polish_maxfun or 8000)
    if mode == "fast":
        n_a = int(max(1, nl_alpha_scan_order_values().size))
        return int(max(400, min((2 * max(p_max, 1)) // n_a, 10000))), "fast"
    return int(max(800, min(max(p_max, int(round(1.35 * p_max))), 50000))), "slow"


def nonlinear_alpha_lbfgs_maxfun_per_step(cfg: Any) -> tuple[int, str]:
    # Legacy alias preserved for backward compat with SplineOptConfig-only callers
    # (nl_alpha_budget_mode / nl_alpha_second_pass_maxfun fallbacks).
    if isinstance(cfg, SplineOptConfig):
        return nonlinear_alpha_lbfgs_maxfun_per_step_from_views(cfg.nonlinear_alpha_view(), cfg.pglobal_view())
    mode = (
        str(_cfg_get_first(cfg, "nonlinear_alpha_budget_mode", "nl_alpha_budget_mode", default="slow") or "slow")
        .strip()
        .lower()
    )
    p_max = int(getattr(cfg, "polish_maxfun", 8000) or 8000)
    if mode == "fast":
        n_a = int(max(1, nl_alpha_scan_order_values().size))
        return int(max(400, min((2 * max(p_max, 1)) // n_a, 10000))), "fast"
    return int(max(800, min(max(p_max, int(round(1.35 * p_max))), 50000))), "slow"


def nonlinear_alpha_second_pass_maxfun_effective_from_views(
    alpha_view: SplineNonlinearAlphaConfig,
    pglobal_view: SplinePGlobalConfig,
    mf_per: int,
) -> int:
    """View-based core of :func:`nonlinear_alpha_second_pass_maxfun_effective` (Lot B2)."""
    v = alpha_view.nonlinear_alpha_second_pass_maxfun
    if v is not None and int(v) > 0:
        return int(v)
    p_max = int(pglobal_view.polish_maxfun or 8000)
    return int(max(mf_per, 5000, int(round(1.85 * p_max))))


def nonlinear_alpha_second_pass_maxfun_effective(cfg: Any, mf_per: int) -> int:
    if isinstance(cfg, SplineOptConfig):
        return nonlinear_alpha_second_pass_maxfun_effective_from_views(
            cfg.nonlinear_alpha_view(), cfg.pglobal_view(), mf_per
        )
    v = _cfg_get_first(cfg, "nonlinear_alpha_second_pass_maxfun", "nl_alpha_second_pass_maxfun", default=None)
    if v is not None and int(v) > 0:
        return int(v)
    p_max = int(getattr(cfg, "polish_maxfun", 8000) or 8000)
    return int(max(mf_per, 5000, int(round(1.85 * p_max))))


def _lbfgsb_exit_kind(success: bool, msg: str) -> str:
    m = str(msg).upper()
    if "TOTAL NO. OF F" in m or "MAXFUN" in m:
        return "budget_maxfun"
    if success or "CONVERGED" in m:
        return "converged"
    return "other_error"


class _NLJointObjective:
    def __init__(
        self,
        cfg: SplineOptConfig,
        sk: np.ndarray,
        lam_f: np.ndarray,
        sig_f: np.ndarray,
        n_sub_f: np.ndarray,
        w: np.ndarray,
        inv_npix: float,
        t_exp_f: np.ndarray | None,
        r_exp_f: np.ndarray | None,
        profile: str,
        stop_event: Event | None,
        *,
        alpha_sigma_prior: float,
        alpha_prior_weight: float,
    ) -> None:
        self.cfg = cfg
        self.sk = np.asarray(sk, dtype=np.float64).ravel()
        self.lam_f = np.asarray(lam_f, dtype=np.float64).ravel()
        self.sig_f = np.asarray(sig_f, dtype=np.float64).ravel()
        self.n_sub_f = np.asarray(n_sub_f, dtype=np.float64).ravel()
        self.w = np.asarray(w, dtype=np.float64).ravel()
        self.inv_npix = float(inv_npix)
        self.t_exp_f = None if t_exp_f is None else np.asarray(t_exp_f, dtype=np.float64).ravel()
        self.r_exp_f = None if r_exp_f is None else np.asarray(r_exp_f, dtype=np.float64).ravel()
        self.profile = str(profile)
        self.stop_event = stop_event
        self.alpha_sigma_prior = float(max(alpha_sigma_prior, 1e-9))
        self.alpha_prior_weight = float(max(alpha_prior_weight, 1e-12))

    def unpack(self, z: np.ndarray) -> tuple[float, np.ndarray]:
        zv = np.asarray(z, dtype=np.float64).ravel()
        alpha = float(np.clip(float(zv[0]), ALPHA_NL_LO, ALPHA_NL_HI))
        return alpha, np.asarray(zv[1:], dtype=np.float64).ravel()

    def __call__(self, z: np.ndarray) -> float:
        if self.stop_event is not None and self.stop_event.is_set():
            return 1e30
        alpha, x = self.unpack(z)
        n_l, k_l = nk_from_x_pwlnk(
            x,
            self.lam_f,
            self.sk,
            float(self.cfg.k_clip_lo),
            float(self.cfg.k_clip_hi),
            sig_pre=self.sig_f,
            n_mono_band_nm=self.cfg.n_mono_band_nm,
            profile_interp=self.profile,
        )
        t_s = None if self.t_exp_f is None else (self.t_exp_f * alpha)
        r_s = None if self.r_exp_f is None else (self.r_exp_f * alpha)
        mse = spline_objective_mse_on_masked_grid(
            self.cfg,
            lam_f=self.lam_f,
            n_sub_f=self.n_sub_f,
            w=self.w,
            inv_npix=self.inv_npix,
            t_exp_f=t_s,
            r_exp_f=r_s,
            n_l=n_l,
            k_l=k_l,
            d=float(x[0]),
        )
        k_nodes = int(self.sk.size)
        n_n = x_slice_n_to_physical_nodes(x[1 : 1 + k_nodes], self.sk, self.cfg.n_mono_band_nm)
        pen_n = (
            0.0
            if bool(getattr(self.cfg, "spline_pure_spectral_objective", False))
            else n_lambda_rising_with_wavelength_penalty(self.cfg, self.sk, n_n)
        )
        pen_alpha = self.alpha_prior_weight * (((float(alpha) - 1.0) / self.alpha_sigma_prior) ** 2)
        return float(mse + pen_n + pen_alpha)


