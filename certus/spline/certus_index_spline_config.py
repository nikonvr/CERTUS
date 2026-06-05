#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Dataclasses for CERTUS-INDEX-SPLINE.
Extracted from certus_index_spline_core.py for Single Responsibility Principle.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Callable
from certus.utils.certus_index_utils import DataType

# Constants required by config defaults
from certus.spline.certus_index_spline_core import (
    SPLINE_PWL_N_SEG,
    SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,
    K_MIN_PHYS,
    L_LNK_MIN_PHYS,
    K_FLOOR_DEFAULT,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
)

class SplinePGlobalConfig:
    """PGlobal optimizer + SOL3 phase 1 + local-only fallback settings."""

    pglobal_max_iter: int = 35
    polish_maxfun: int = 8000
    sol3_phase1_maxfun: int | None = None
    pglobal_max_feval: int | None = None
    pglobal_max_time: float | None = None
    pglobal_local_search_budget: int | None = None
    pglobal_random_seed: int | None = None
    pglobal_trust_region_by_k: bool = False
    pglobal_trust_k_lo: int = 4
    pglobal_trust_k_hi: int = 14
    pglobal_trust_rho_lo: float = 0.12
    pglobal_trust_rho_hi: float = 0.5
    auto_knot_dual_seed: bool = True
    auto_knot_recovery_perturb: bool = True
    auto_knot_recovery_rel_tol: float = 0.02
    spline_local_only: bool = False
    stage_mandatory_local_maxfun: int = 0


@dataclass
class SplineSmartInitConfig:
    """Smart-Init preview hook + post-preview overrides."""

    smart_init_preview_hook: Callable[[dict], bool] | None = None
    smart_init_preview_shown: bool = False
    smart_preview_node_override: tuple[np.ndarray, np.ndarray] | None = None
    smart_preview_d_nm_override: float | None = None
    smart_preview_accepted_rmse: float | None = None
    smart_init_manual_force_restart: bool = False
    smart_preview_exact_sigma_knots: np.ndarray | None = None
    smart_preview_exact_n_L: tuple[np.ndarray, np.ndarray] | None = None
    fixed_sigma_knots_count: int | None = None
    spline_smart_init_deep_two_phase: bool = True


@dataclass
class SplineCorridorConfig:
    """d-profiling corridor parameters (without bootstrap, see SplineBootstrapConfig)."""

    corridor_profile_d_enabled: bool = False
    corridor_profile_d_mode: str = "abs_delta_adaptive"
    corridor_profile_d_rmse_alpha: float = 1.05
    corridor_profile_d_rmse_abs_tolerance: float = 2.5e-4
    corridor_profile_d_base_source: str = "best_polished"
    corridor_profile_d_threshold_basis: str = "max"
    corridor_profile_d_threshold_ratio_guard: float = 1.25
    corridor_profile_d_auto_relax_max_factor: float = 1.5
    # Modified: force symmetry and automatic calculation every 0.5nm
    corridor_profile_d_step_nm: float = 0.5
    corridor_profile_d_step_nm_initial: float = 0.5
    corridor_profile_d_step_growth: float = 1.0
    corridor_profile_d_step_nm_max: float = 0.5
    corridor_profile_d_max_span_nm: float = 15.0
    corridor_profile_d_min_valid_each_side: int = 1
    corridor_profile_d_lr_conf_level: float = 0.95
    corridor_profile_d_sigma_t: float | None = None
    corridor_profile_d_sigma_r: float | None = None
    corridor_profile_d_sigma_hetero: bool = False
    corridor_profile_d_sigma_hetero_scale: float = 1.0
    corridor_profile_d_n_starts: int = 1
    corridor_profile_d_jitter_n: float = 0.02
    corridor_profile_d_jitter_L: float = 0.15
    corridor_profile_d_rng_seed: int = 0
    corridor_profile_d_fit_auto_n_starts: bool = False
    corridor_profile_d_fit_max_n_starts: int = 2
    corridor_profile_d_fit_retry_maxfun_scale: float = 1.5
    corridor_profile_d_seed_gate_keep_nominal_if_refit_worse: bool = True
    corridor_profile_d_seed_gate_tol_rel: float = 0.0
    corridor_profile_d_seed_gate_tol_abs: float = 1e-5
    corridor_profile_d_polish_maxfun: int | None = None
    corridor_profile_d_parallel_walks: bool = True
    corridor_profile_d_auto_relax_threshold: bool = True
    corridor_profile_d_auto_relax_epsilon: float = 0.002
    corridor_scientific_nominal_enabled: bool = True
    corridor_profile_d_parabola_half_window_pts: int = 4
    # Modified: Force interval to be symmetric around the parabola (USER request)
    corridor_profile_d_force_symmetric_interval: bool = True
    corridor_profile_d_symmetric_center_mode: str = "parabola"
    corridor_profile_d_adaptive_rmse_ref_half_width_nm: float = 1.5
    corridor_profile_d_adaptive_rmse_probe_steps_each_side: int = 3
    corridor_profile_d_adaptive_rmse_noise_factor: float = 3.0
    corridor_profile_d_adaptive_rmse_min: float = 2.5e-5
    corridor_reg_sensitivity_enabled: bool = False
    corridor_reg_sensitivity_points: int = 5
    corridor_reg_sensitivity_decades: int = 2
    corridor_reg_sensitivity_n_workers: int = 1
    # If a new minimum is found, we repeat the calculation
    corridor_profile_d_rerun_after_promotion: bool = True
    corridor_profile_d_rerun_max_extra_passes: int = 6


@dataclass
class SplineBootstrapConfig:
    """Parametric / residual bootstrap for corridor confidence bands."""

    corridor_bootstrap_enabled: bool = False
    corridor_bootstrap_n: int = 40
    corridor_bootstrap_seed: int = 0
    corridor_bootstrap_percentile: float = 0.95
    corridor_bootstrap_sigma_t: float | None = None
    corridor_bootstrap_sigma_r: float | None = None
    corridor_bootstrap_mode: str = "parametric"
    corridor_bootstrap_block_len: int = 1
    corridor_bootstrap_quick_refit: bool = False
    corridor_bootstrap_quick_refit_maxfun: int = 4000
    corridor_bootstrap_n_workers: int = 1


@dataclass
class SplineNonlinearAlphaConfig:
    """Post-pass alpha refinement (linear scale factor on T/R)."""

    nonlinear_alpha_refinement_enabled: bool = True
    nonlinear_alpha_budget_mode: str = "slow"
    nonlinear_alpha_second_pass_enabled: bool = True
    nonlinear_alpha_second_pass_maxfun: int | None = None
    nl_alpha_adaptive_early_stop: bool = True
    nl_alpha_pure_spectral: bool = True
    nl_alpha_bisection_refine: bool = True
    nl_alpha_bisection_max_iter: int = 8


@dataclass(init=False)
class SplineOptConfig:
    lam_nm: np.ndarray
    t_exp: np.ndarray | None
    r_exp: np.ndarray | None
    n_sub: np.ndarray
    data_type: DataType
    n_seg: int
    d_lo: float
    d_hi: float
    weight_t: float
    weight_r: float
    substrate_name: str
    t_is_ratio: bool = False
    x0_warm: np.ndarray | None = None
    k_clip_lo: float = 1e-5
    k_clip_hi: float = min(0.99, float(K_MAX_LIMIT))
    sigma_knots_override: np.ndarray | None = None
    n_mono_band_nm: tuple[float, float] | None = None
    n_mono_continuous_penalty: float = 0.0
    n_lambda_rising_penalty_band_nm: tuple[float, float] | None = (400.0, 1500.0)
    n_lambda_rising_penalty_weight: float = 3000.0
    n_lambda_rising_penalty_slack: float = 0.001
    x0_warm_encoding: str | None = None
    x0_warm_n_mono_band_for_decode: tuple[float, float] | None = None
    lnk_spline_stage_enabled: bool = True
    lnk_spline_reg_weight: float = 1e-3
    spline_pure_spectral_objective: bool = False
    lnk_spline_min_sep_rel: float = 0.01
    node_mesh_spectral_polish_enabled: bool = True
    node_model_spectral_polish_maxfun: int | None = None
    rmse_fit_lambda_nm: tuple[float, float] | None = None
    nk_profile_interp: str = "smooth"
    spline_min_delta_lambda_over_lambda_mean: float = 0.02

    # --- Composed configs ---
    pglobal: SplinePGlobalConfig = field(default_factory=SplinePGlobalConfig)
    smart_init: SplineSmartInitConfig = field(default_factory=SplineSmartInitConfig)
    corridor: SplineCorridorConfig = field(default_factory=SplineCorridorConfig)
    bootstrap: SplineBootstrapConfig = field(default_factory=SplineBootstrapConfig)
    nonlinear_alpha: SplineNonlinearAlphaConfig = field(default_factory=SplineNonlinearAlphaConfig)

    def __init__(
        self,
        substrate_name,
        weight_r,
        weight_t,
        d_hi,
        d_lo,
        n_seg,
        data_type,
        n_sub,
        r_exp,
        t_exp,
        lam_nm,
        t_is_ratio=False,
        x0_warm=None,
        k_clip_lo=1e-5,
        k_clip_hi=min(0.99, float(K_MAX_LIMIT)),
        sigma_knots_override=None,
        n_mono_band_nm=None,
        n_mono_continuous_penalty=0.0,
        n_lambda_rising_penalty_band_nm=(400.0, 1500.0),
        n_lambda_rising_penalty_weight=3000.0,
        n_lambda_rising_penalty_slack=0.001,
        x0_warm_encoding=None,
        x0_warm_n_mono_band_for_decode=None,
        lnk_spline_stage_enabled=True,
        lnk_spline_reg_weight=1e-3,
        spline_pure_spectral_objective=False,
        lnk_spline_min_sep_rel=0.01,
        node_mesh_spectral_polish_enabled=True,
        node_model_spectral_polish_maxfun=None,
        rmse_fit_lambda_nm=None,
        nk_profile_interp="smooth",
        spline_min_delta_lambda_over_lambda_mean=0.02,
        **kwargs,
    ):
        self.lam_nm = lam_nm
        self.t_exp = t_exp
        self.r_exp = r_exp
        self.n_sub = n_sub
        self.data_type = data_type
        self.n_seg = n_seg
        self.d_lo = d_lo
        self.d_hi = d_hi
        self.weight_t = weight_t
        self.weight_r = weight_r
        self.substrate_name = substrate_name
        self.t_is_ratio = t_is_ratio
        self.x0_warm = x0_warm
        self.k_clip_lo = k_clip_lo
        self.k_clip_hi = k_clip_hi
        self.sigma_knots_override = sigma_knots_override
        self.n_mono_band_nm = n_mono_band_nm
        self.n_mono_continuous_penalty = n_mono_continuous_penalty
        self.n_lambda_rising_penalty_band_nm = n_lambda_rising_penalty_band_nm
        self.n_lambda_rising_penalty_weight = n_lambda_rising_penalty_weight
        self.n_lambda_rising_penalty_slack = n_lambda_rising_penalty_slack
        self.x0_warm_encoding = x0_warm_encoding
        self.x0_warm_n_mono_band_for_decode = x0_warm_n_mono_band_for_decode
        self.lnk_spline_stage_enabled = lnk_spline_stage_enabled
        self.lnk_spline_reg_weight = lnk_spline_reg_weight
        self.spline_pure_spectral_objective = spline_pure_spectral_objective
        self.lnk_spline_min_sep_rel = lnk_spline_min_sep_rel
        self.node_mesh_spectral_polish_enabled = node_mesh_spectral_polish_enabled
        self.node_model_spectral_polish_maxfun = node_model_spectral_polish_maxfun
        self.rmse_fit_lambda_nm = rmse_fit_lambda_nm
        self.nk_profile_interp = nk_profile_interp
        self.spline_min_delta_lambda_over_lambda_mean = spline_min_delta_lambda_over_lambda_mean
        self.pglobal = SplinePGlobalConfig()
        self.smart_init = SplineSmartInitConfig()
        self.corridor = SplineCorridorConfig()
        self.bootstrap = SplineBootstrapConfig()
        self.nonlinear_alpha = SplineNonlinearAlphaConfig()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def replace(self, **changes):
        import copy

        new_obj = copy.copy(self)
        new_obj.pglobal = copy.copy(self.pglobal)
        new_obj.smart_init = copy.copy(self.smart_init)
        new_obj.corridor = copy.copy(self.corridor)
        new_obj.bootstrap = copy.copy(self.bootstrap)
        new_obj.nonlinear_alpha = copy.copy(self.nonlinear_alpha)
        for k, v in changes.items():
            setattr(new_obj, k, v)
        return new_obj

    # --- Metaprogramming Router (Top 1% refactor) ---
    def __getattr__(self, name: str):
        for sub_name in ('pglobal', 'smart_init', 'corridor', 'bootstrap', 'nonlinear_alpha'):
            sub_cfg = self.__dict__.get(sub_name)
            if sub_cfg and hasattr(sub_cfg, name):
                return getattr(sub_cfg, name)
        raise AttributeError(f"'SplineOptConfig' object has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        if name in self.__class__.__dict__ or name in self.__dict__ or name in ('pglobal', 'smart_init', 'corridor', 'bootstrap', 'nonlinear_alpha'):
            super().__setattr__(name, value)
            return
        for sub_name in ('pglobal', 'smart_init', 'corridor', 'bootstrap', 'nonlinear_alpha'):
            sub_cfg = self.__dict__.get(sub_name)
            if sub_cfg and hasattr(sub_cfg, name):
                setattr(sub_cfg, name, value)
                return
        super().__setattr__(name, value)


    # --- Legacy Composition & View Methods (P4 Scaffold Compatibility) ---

    def pglobal_view(self):
        return self.pglobal

    def corridor_view(self):
        return self.corridor

    def nonlinear_alpha_view(self):
        return self.nonlinear_alpha


def sol3_phase1_maxfun_effective_from_view(view: SplinePGlobalConfig) -> int:
    """View-based core of :func:`sol3_phase1_maxfun_effective` (Lot B2).

    Takes the read-only :class:`SplinePGlobalConfig`; all information needed
    comes from the pglobal sub-domain.
    """

    v = view.sol3_phase1_maxfun
    if v is None:
        return 10000
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return 10000
    if iv <= 0:
        return 10000
    return int(max(300, iv))


def sol3_phase1_maxfun_effective(cfg: SplineOptConfig) -> int:
    """L-BFGS-B ``maxfun`` for SOL3 / SOL3b phase 1 (descent). Legacy default 10000 if unset or non-positive."""

    return sol3_phase1_maxfun_effective_from_view(cfg.pglobal_view())


def corridor_profile_refit_maxfun_from_views(
    corridor: SplineCorridorConfig,
    pglobal: SplinePGlobalConfig,
    override: int | None = None,
) -> int:
    """View-based core of :func:`corridor_profile_refit_maxfun` (Lot B2).

    Uses ``corridor.corridor_profile_d_polish_maxfun`` and falls back to
    ``pglobal.polish_maxfun`` when unset/non-positive.
    """

    if override is not None:
        return int(max(300, int(override)))
    v = corridor.corridor_profile_d_polish_maxfun
    if v is not None:
        try:
            iv = int(v)
            if iv > 0:
                return int(max(300, iv))
        except (TypeError, ValueError):
            pass
    pm = int(pglobal.polish_maxfun or 4000)
    return int(max(300, pm))


def corridor_profile_refit_maxfun(cfg: SplineOptConfig, override: int | None = None) -> int:
    """Effective L-BFGS-B budget for each d profiling refit (floor 300)."""

    return corridor_profile_refit_maxfun_from_views(
        cfg.corridor_view(),
        cfg.pglobal_view(),
        override=override,
    )


# Minimum number of spectral points in the objective mask (after RMSE window if active).


SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS: int = 3


class SmartInitPreviewCancelled(Exception):
    """User cancellation after Smart Init preview."""


