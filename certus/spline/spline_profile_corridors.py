#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""n/k corridors by thickness *d* profiling (continuation).

Design intent (local sensitivity around the best spectral fit):

  - The corridor is **not** a new global inversion: it is a **narrow strip** of models obtained by

    **small variations of thickness** *d* around the optimum, re-equilibrating **only** the spline

    nodes (n and L = ln k) at each *d* with the **same** objective / masks / penalties as the main

    spline fit. Think **differential-style sensitivity** or **profile likelihood on *d*** with a

    **fixed RMSE tolerance band** (alpha×RMSE_ref or RMSE_ref+Delta): every accepted point stays inside that

    tube in spectral space.

  - Operationally, the **center** must be the solution that carries the **best (lowest) masked

    spectral RMSE** you export as reference - in the pipeline this is typically

    ``corridor_profile_d_base_source="best_polished"`` (mesh-polished sigma splines) so that *d_opt*,

    ``n_lam``/``k_lam``, ``x``/nodes, and ``RMSE_ref`` all describe the **same** state before any

    corridor refit.

Idea:

  - Start from an existing spline solution (sigma_knots, d_opt, n/L at knots).

  - Fix *d* at d_target and re-optimize only the nodes (n and L=ln k)

    with EXACTLY the same guards / penalties / RMSE convention as the spline objective.

  - Repeat in "continuation" on both sides of d_opt; solutions whose RMSE

    stays below a threshold define a plausible interval [d_min, d_max] and an envelope

    (corridor) on n(lambda) and k(lambda).

This module does not touch the UI; it only produces fields to merge into the result dict.

RMSE reference (alpha mode, and automatic sigma in LR):

  - if ``spectral_rmse_segments`` is present in the pipeline dict (>0, finite), it is **preferred**

    (same convention as the n/k spline « solver » optimization);

  - otherwise ``rmse`` from the dict, then direct spectral RMSE recomputed from extracted nodes.

  The key ``profile_d_rmse_ref_source`` records which was used.

Automatic lift (alpha mode, default): if the refit at ``d_opt`` exceeds ``alpha×RMSE_ref``,

the effective threshold is raised to ``RMSE_center×(1+ε)`` to avoid empty profiling while still

logging ``profile_d_rmse_thresh_nominal`` vs ``profile_d_rmse_thresh`` and ``profile_d_auto_relaxed_threshold``.

**RMSE_ref vs refit RMSE (do not confuse in logs)**:

  - ``RMSE_ref`` (often ``spectral_rmse_segments``) = spectrum for the frozen **solver** solution

    (no corridor re-optimization of nodes).

  - Each « best-of » / refit step = L-BFGS-B on **n and L** only at fixed ``d``, budget

    ``corridor_profile_d_polish_maxfun``, jitter / multi-starts allowed -> RMSE can be

    **much larger** than ``RMSE_ref`` (local minima, insufficient budget) **without a bug**;

    the code then adjusts the threshold (``center_refit`` fallback, automatic lift).

**Scientific nominal mode** (``scientific_nominal_corridor`` + ``abs_delta``):

  ``RMSE_ref = spectral_rmse_best_value``; the nominal polished n(lambda),k(lambda) is the **first** member of the

  accepted family; ``corridor_reference_*`` is a copy of that nominal curve (not the center-d refit).

  No post-hoc widening toward a separate « main » ``n_lam``/``k_lam`` export.

**Legacy UI widening** (when scientific mode is off):

  After min/max over refits, the envelope can be **expanded** so reported ``n_lam``/``k_lam`` lie inside

  ``[corridor_*_lo, corridor_*_hi]`` at each lambda.

"""

from __future__ import annotations

import logging


import threading

import time

from concurrent.futures import ThreadPoolExecutor, as_completed

from dataclasses import dataclass

from typing import Any

import numpy as np

from scipy.optimize import minimize

from scipy.stats import chi2 as _chi2

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, get_safe_worker_count

from certus_physics import clip_to_bounds

from certus.spline.certus_index_spline_core import (
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    DataType,
    SplineOptConfig,
    corridor_profile_refit_maxfun,
    physical_nodes_to_x_slice_n,
    _reflectance_absolute_backside_from_nk,
)

from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _transmittance_absolute_from_nk,
)

from certus.spline.spline_objective import (
    SplinePWLObjective,
    build_spline_objective_masked_grid,
    nk_from_x_pwlnk,
    spectral_mse_rmse_masked_from_nk,
    spline_pwl_analytic_grad_supported,
    x_slice_n_to_physical_nodes,
)

from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference

log = logging.getLogger("CERTUS")

_LOG_PREFIX = "INDEX_SPLINE [CORRIDORS d]"

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

def _fit_local_quadratic_rmse_profile(
    d_s: np.ndarray,
    r_s: np.ndarray,
    i_anchor: int,
    half_window_pts: int,
    delta_rmse: float = 0.0,
) -> dict[str, Any]:

    d_arr = np.asarray(d_s, dtype=np.float64).ravel()

    r_arr = np.asarray(r_s, dtype=np.float64).ravel()

    out: dict[str, Any] = {
        "ok": False,
        "d_center": float("nan"),
        "d_lo": float("nan"),
        "d_hi": float("nan"),
        "slope_at_anchor": float("nan"),
        "curvature": float("nan"),
        "anchor_nm": float("nan"),
        "window_nm": (float("nan"), float("nan")),
        "coeffs": (float("nan"), float("nan"), float("nan")),
        "fit_error": float("nan"),
        "fit_error_tol": float("nan"),
        "n_fit_points": 0,
    }

    if d_arr.size < 5 or r_arr.size != d_arr.size:
        return out

    ia = int(i_anchor)

    if ia < 0 or ia >= int(d_arr.size):
        return out

    half_start = max(1, int(half_window_pts))
    half_max = max(half_start, int(max(1, d_arr.size // 2)))
    d_anchor = float(d_arr[ia])
    min_pts = 5
    # "Substantial but reasonable": wide relative tolerance + absolute safeguard.
    rel_tol = 0.20
    abs_tol = 4.0e-4

    best_candidate: dict[str, Any] | None = None
    best_half = -1
    best_err = float("inf")

    for half in range(half_start, half_max + 1):
        i0 = int(max(0, ia - half))
        i1 = int(min(d_arr.size, ia + half + 1))
        if i1 - i0 < min_pts:
            continue

        d_loc = np.asarray(d_arr[i0:i1], dtype=np.float64)
        r_loc = np.asarray(r_arr[i0:i1], dtype=np.float64)

        if r_loc.size >= 4:
            r_med = float(np.median(r_loc))
            r_mad = float(np.median(np.abs(r_loc - r_med)))
            mask = r_loc <= r_med + max(4.0 * r_mad, 1e-4)
            if np.sum(mask) >= min_pts:
                d_loc = d_loc[mask]
                r_loc = r_loc[mask]
        if d_loc.size < min_pts:
            continue

        x = d_loc - d_anchor
        try:
            c2, c1, c0 = np.polyfit(x, r_loc, 2)
        except NUMERICAL_FAULT_EXCEPTIONS:
            continue
        if (not np.isfinite(c2)) or (not np.isfinite(c1)) or (not np.isfinite(c0)) or c2 <= 0.0:
            continue

        d_center = float(d_anchor - c1 / (2.0 * c2))
        d_lo_win = float(np.min(d_loc))
        d_hi_win = float(np.max(d_loc))
        win_span = float(max(1e-9, d_hi_win - d_lo_win))
        step_ref = float(np.nanmedian(np.abs(np.diff(d_loc)))) if d_loc.size >= 2 else 0.0
        tol_center = float(max(1e-9, step_ref, 0.25 * win_span))
        if (not np.isfinite(d_center)) or d_center < d_lo_win - tol_center or d_center > d_hi_win + tol_center:
            continue

        r_fit = float(c2) * x * x + float(c1) * x + float(c0)
        resid = np.asarray(r_loc - r_fit, dtype=np.float64).ravel()
        sigma_rob = _robust_sigma_from_mad(resid)
        sigma_rms = float(np.sqrt(np.mean(np.square(resid)))) if resid.size else float("nan")
        fit_err = float(np.nanmax(np.asarray([sigma_rob, sigma_rms], dtype=np.float64)))
        r_ref = float(max(np.nanmedian(r_loc), 1e-12))
        err_tol = float(max(abs_tol, rel_tol * r_ref))
        if (not np.isfinite(fit_err)) or fit_err > err_tol:
            continue

        dd_raw = float(np.sqrt(max(float(delta_rmse), 0.0) / c2)) if np.isfinite(float(delta_rmse)) else float("nan")
        min_excursion = float(max(1e-6, 0.002 * abs(d_anchor)))
        max_excursion = float(win_span * 2.5)
        if np.isfinite(dd_raw):
            dd = float(np.clip(dd_raw, min_excursion, max_excursion))
        else:
            dd = min_excursion

        cand = {
            "ok": True,
            "d_center": d_center,
            "d_lo": float(d_center - dd),
            "d_hi": float(d_center + dd),
            "slope_at_anchor": float(c1),
            "curvature": float(c2),
            "anchor_nm": d_anchor,
            "window_nm": (d_lo_win, d_hi_win),
            "coeffs": (float(c2), float(c1), float(c0)),
            "fit_error": float(fit_err),
            "fit_error_tol": float(err_tol),
            "n_fit_points": int(d_loc.size),
        }

        # B6 FIX: Arbitrate between window width and fit quality.
        # Previously we strictly preferred the widest window, which could artificially flatten curvature.
        # Now we only prefer a wider window if its fit error is acceptable and comparable.
        is_better = False
        if best_candidate is None:
            is_better = True
        else:
            if fit_err < best_err * 0.5:
                is_better = True  # significantly better fit
            elif half > best_half and fit_err <= best_err * 1.5 and fit_err <= err_tol:
                is_better = True  # slightly worse fit but wider window, and acceptable
            elif half == best_half and fit_err < best_err:
                is_better = True

        if is_better:
            best_candidate = cand
            best_half = half
            best_err = fit_err

    if best_candidate is None:
        return out
    out.update(best_candidate)
    return out

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

from pydantic import BaseModel, ConfigDict

class ProfileCorridorConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    """Parameters for profiling on *d*.

    rmse_alpha:

      - threshold = rmse_alpha * rmse_opt (heuristic, non-probabilistic).

      - keep low (typically 1.02-1.08) to avoid overly permissive profiles.

    """

    enabled: bool = True

    # "alpha" mode: RMSE threshold <= alpha * RMSE_opt (heuristic).

    rmse_alpha: float = 1.05

    # "lr" (Likelihood Ratio): Deltaχ² threshold <= χ²_{1,conf}. Constant sigma_T, sigma_R.

    mode: str = "alpha"  # "alpha" | "lr"

    lr_conf_level: float = 0.95

    # Constant sigma (same units as data: T as fraction, R as fraction).

    # None => auto = rmse_opt (same value for T and R).

    sigma_t: float | None = None

    sigma_r: float | None = None

    # Alpha-mode threshold policy: "nominal" | "center_refit" | "max"

    threshold_basis: str = "max"

    # Guard: if RMSE_refit_center / RMSE_ref exceeds this ratio, explicit threshold fallback.

    threshold_ratio_guard: float = 1.25

    # Continuation step (nm). The code may shrink automatically on convergence failure.

    step_nm: float = 1.0

    # Adaptive march: initial step, growth factor, step cap.

    step_nm_initial: float = 1.0

    step_growth: float = 1.0

    step_nm_max: float = 4.0

    parabola_half_window_pts: int = 4

    # Force a symmetric reported d-interval even when the accepted sampled points are imbalanced.

    force_symmetric_interval: bool = False

    # Center used for the final symmetric reported d-interval: "nominal" | "parabola".
    # Default = parabola so the excursion is centered on the local RMSE minimum.

    symmetric_interval_center_mode: str = "parabola"

    # Minimum half-width of the reported d-interval, relative to d_opt.

    symmetric_interval_min_half_width_rel: float = 0.002

    # Max exploration span around d_opt (runtime safety), in nm.

    max_span_nm: float = 15.0

    # Max fits (safety) per direction.

    max_steps_each_side: int = 250

    # Stop tolerance: if not enough valid points.

    min_valid_points: int = 3

    # Require valid points on both sides of d_opt for a usable corridor.

    min_valid_each_side: int = 0

    # If True: include d_opt solution in "valid" list even if rmse_opt is NaN (rare).

    include_center_even_if_nan: bool = True

    # Boundary refinement (bisection) around first *d* that exceeds the threshold.

    refine_boundary: bool = True

    refine_max_iter: int = 10

    refine_tol_nm: float = 0.35

    # Multi-start (robustness to local minima):

    # - 1 => continuation only (fast)

    # - >1 => try several initializations per *d*, keep best metric (RMSE or χ²).

    n_starts: int = 1

    # If True, auto-increase n_starts when a fit fails (up to fit_max_n_starts).

    fit_auto_n_starts: bool = False

    fit_max_n_starts: int = 2

    # On STOP maxfun, optional retry with maxfun*scale.

    fit_retry_maxfun_scale: float = 1.5

    # Gaussian jitter (std dev) on x0 (in x space: n_slice or ξ, and L=ln k).

    # Jitters are in parameter units (n or ξ; and ln k).

    jitter_n: float = 0.02

    jitter_L: float = 0.15

    # Seed gate for fixed-d refits:
    # keep incoming seed if refit RMSE worsens beyond the dedicated refit tolerance.
    # This tolerance is intentionally distinct from corridor acceptance slack (rmse_abs_tolerance).
    seed_gate_keep_nominal_if_refit_worse: bool = True
    seed_gate_tol_rel: float = 0.0
    seed_gate_tol_abs: float = 1e-5

    # RNG seed for reproducibility.

    rng_seed: int = 0

    # V2.5 LR: heteroscedastic spectral sigma on masked grid (sigma_i = max(floor, scale×|residual_i|)).

    sigma_hetero_residual: bool = False

    sigma_hetero_scale: float = 1.0

    # Alpha mode: if refit at d_opt exceeds alpha×RMSE_ref (e.g. segments << "nodes-only" error),

    # raise threshold to RMSE_center×(1+ε) to keep center admissible and continue the march.

    auto_relax_threshold_to_include_center: bool = True

    auto_relax_epsilon: float = 0.002

    auto_relax_max_factor: float = 1.5

    # When ``mode`` is "alpha" (not LR): "alpha" = alpha×RMSE_ref (legacy) ;

    # "abs_delta" = accept refit iff RMSE <= RMSE_ref(base n,k on mask) + ``rmse_abs_tolerance``.
    # "abs_delta_adaptive" derives DeltaRMSE from the local quadratic RMSE(d) valley and local roughness.

    rmse_threshold_mode: str = "abs_delta_adaptive"  # "alpha" | "abs_delta" | "alpha_plus_delta" | "abs_delta_adaptive" | "alpha_plus_adaptive_delta"

    # Absolute RMSE slack on the same masked spectral objective as refits (T/R fractions).

    rmse_abs_tolerance: float = 2.5e-4

    adaptive_rmse_abs_ref_half_width_nm: float = 0.5

    adaptive_rmse_abs_probe_steps_each_side: int = 2

    adaptive_rmse_abs_noise_factor: float = 2.0

    adaptive_rmse_abs_min: float = 2.5e-5

    # If True with ``abs_delta``: RMSE_ref = ``spectral_rmse_best_value``, nominal = best polish;

    # no corrective envelope widening; ``corridor_reference_*`` = nominal (not the central refit).

    scientific_nominal_corridor: bool = True

    # When True (default): corridor refits use a **pure spectral objective** (spline_pure_spectral_objective=True),
    # disabling the n_lambda_rising penalty (weight ~3000) and lnk curvature regularization during fixed-d refits.
    # These penalties cause L-BFGS-B to flee the nominal solution, always returning higher spectral RMSE than
    # the seed -> seed-gate keeps nominal n,k for every d -> zero-width corridor.
    # Setting True ensures refits genuinely explore n,k space at each target d.
    refit_pure_spectral: bool = True

    # Optional user-provided RMSE mask for manual spectral exclusion (e.g., absorption bands, detector artifacts).
    # If provided, this boolean mask (same length as lam_nm) excludes masked wavelengths from RMSE/chi² computation.
    # Saved to output as "corridor_user_rmse_mask" for traceability.
    user_rmse_mask: np.ndarray | None = None

    # Hard lower bound for k spline (physical constraint: k >= 0 for passive media).
    # Enforced via optimizer bounds, not just post-hoc clipping, to ensure physically valid corridors.
    k_hard_lower_bound: float = 0.0

    # Unified heteroscedastic sigma for both LR and alpha modes.
    # If True, sigma_i = max(floor, scale × |residual_i|) on the masked grid, consistent across all threshold modes.
    # Replaces legacy sigma_hetero_residual (now aliased for backward compatibility).
    use_heteroscedastic_sigma: bool = False
    heteroscedastic_sigma_floor: float = 1e-6
    heteroscedastic_sigma_scale: float = 1.0

    # P2.4 FIX: Use smoothstep blending for boundary refinement continuity.
    # If True, applies smoothstep interpolation between accepted and rejected boundary points for C¹ continuity.
    smoothstep_boundary_blend: bool = False
    smoothstep_blend_width_nm: float = 0.5

    def replace(self, **changes: Any) -> "ProfileCorridorConfig":
        """Return a copy with selected fields updated (immutable dataclass helper)."""
        return self.model_copy(update=changes)

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

            bad_ref = ~np.isfinite(ref)

            if np.any(bad_ref):
                ref[bad_ref] = mid[bad_ref]

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

    except (TypeError, ValueError):
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
                except (TypeError, ValueError):
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
                except (ValueError, TypeError):
                    n_nodes = n_slice.copy()
                recovered_n = True
                meta["recovered_n_nodes_from_x"] = True
                break
            if xa.size == want_L and sk_L.size >= 2:
                n_slice = np.asarray(xa[1 : 1 + int(sk_L.size)], dtype=np.float64).ravel()
                try:
                    nL_nodes = x_slice_n_to_physical_nodes(n_slice, sk_L, None)
                except (ValueError, TypeError):
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
            "%s Spectral RMSE **without refit** (graine bornée, d=d_opt) = %.8f (MSE=%.6e) | "
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

def _fit_nodes_at_fixed_d(
    cfg: SplineOptConfig,
    sigma_knots: np.ndarray,
    d_target_nm: float,
    x_nodes_init: np.ndarray,
    bounds_nodes: np.ndarray,
    *,
    maxfun: int = 4000,
    keep_nominal_seed_if_refit_worse: bool = True,
    seed_keep_tol_rel: float = 0.0,
    seed_keep_tol_abs: float = 1e-5,
    pure_spectral: bool = False,
    # P0.1 FIX: LR mode objective coherence parameters
    use_lr: bool = False,
    sig_t: float = 1.0,
    sig_r: float = 1.0,
    sigma_t_f: np.ndarray | None = None,
    sigma_r_f: np.ndarray | None = None,
    masked_grid_cache: tuple | None = None,
    cfg_effective: SplineOptConfig | None = None,
    obj_stage_cache: SplinePWLObjective | None = None,
    bds_cache: list[tuple[float, float]] | None = None,
) -> dict[str, Any] | None:
    """Optimize (n_slice, L_slice) at fixed d and return a minimal snapshot.

    Returns None if the masked objective is empty or dimensions are inconsistent.

    """

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    k = int(sk.size)

    if k < 2:
        return None

    b = np.asarray(bounds_nodes, dtype=np.float64)

    x0 = np.asarray(x_nodes_init, dtype=np.float64).ravel().copy()

    if b.shape != (2 * k, 2) or x0.size != 2 * k:
        return None

    # Optionally receive a pre-built effective config/objective for multi-start reuse.
    if cfg_effective is not None:
        cfg = cfg_effective
    elif pure_spectral:
        # Pure-spectral mode: disable n_lambda_rising penalty and lnk regularization so L-BFGS-B
        # genuinely minimises spectral RMSE at the target d instead of fleeing the nominal solution.
        cfg = cfg.replace(spline_pure_spectral_objective=True)
        log.debug(
            "%s _fit_nodes_at_fixed_d d=%.5g nm: pure_spectral=True -> n_lambda_rising penalty disabled for refit.",
            _LOG_PREFIX,
            float(d_target_nm),
        )

    # Masked objective (same weights / RMSE window); if empty, cannot profile.

    obj_stage = obj_stage_cache if obj_stage_cache is not None else SplinePWLObjective(cfg, sk)

    # Build full x vector for obj(x): x = [d, n_slice..., L_slice...]

    def _pack(x_nodes: np.ndarray) -> np.ndarray:

        return np.concatenate((np.asarray([float(d_target_nm)], dtype=np.float64), x_nodes))

    x0 = clip_to_bounds(x0, b[:, 0], b[:, 1])

    # P0.1 FIX: Pre-compute masked grid for chi² if use_lr (avoid recomputing on each eval)
    _masked_grid_cache = masked_grid_cache
    if use_lr and _masked_grid_cache is None:
        from certus.spline.spline_objective import build_spline_objective_masked_grid

        _masked_grid_cache = build_spline_objective_masked_grid(cfg)

    def _mse_nodes(x_nodes: np.ndarray) -> float:

        x_full = _pack(x_nodes)

        mse0 = float(obj_stage(x_full))

        if not np.isfinite(mse0):
            return 1e30

        if bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            return float(mse0)

        # ln(k) regularization consistent with legacy free-knot B (spline_workers._run_free_knot_stage):

        # penalty on discrete curvature d2(L) at sigma knots.

        reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))

        if reg_w > 0.0:
            k_loc = int(sk.size)

            L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]

            if L_nodes.size >= 3:
                d2 = np.diff(L_nodes, n=2)

                mse0 = float(mse0) + reg_w * float(np.mean(d2 * d2))

        return float(mse0)

    # B7 FIX: cache last nk result from _chi2_nodes to avoid redundant recomputation.
    _chi2_nk_cache: dict[str, Any] = {}

    # P0.1 FIX: chi² objective for LR mode (optimizer matches boundary test)
    def _chi2_nodes(x_nodes: np.ndarray) -> float:
        """Compute chi² on masked grid for LR mode optimization."""
        if _masked_grid_cache is None:
            return 1e30
        lam_f, _sig_f, n_sub_f, w, _inv_npix, t_exp_f, r_exp_f = _masked_grid_cache
        lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
        x_full = _pack(x_nodes)
        n_lam, k_lam = nk_from_x_pwlnk(
            x_full,
            lam_full,
            sk,
            cfg.k_clip_lo,
            cfg.k_clip_hi,
            sig_pre=None,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=str(cfg.nk_profile_interp or "smooth"),
        )
        n_f = np.interp(lam_f, lam_full, np.asarray(n_lam, dtype=np.float64).ravel())
        k_f = np.interp(lam_f, lam_full, np.asarray(k_lam, dtype=np.float64).ravel())
        # B7 FIX: cache the last nk for post-minimize reuse
        _chi2_nk_cache["n_lam"] = np.asarray(n_lam, dtype=np.float64).ravel()
        _chi2_nk_cache["k_lam"] = np.asarray(k_lam, dtype=np.float64).ravel()

        from certus.utils.certus_index_utils import (
            _ratio_theoretical_from_nk,
            _reflectance_ratio_theoretical_from_nk,
            _transmittance_absolute_from_nk,
        )
        from certus.spline.certus_index_spline_core import _reflectance_absolute_backside_from_nk
        from certus.spline.spline_objective import DataType

        chi = 0.0
        d_nm = float(d_target_nm)
        if cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH) and t_exp_f is not None and float(cfg.weight_t) > 0:
            if cfg.t_is_ratio:
                t_th = _ratio_theoretical_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            else:
                t_th = _transmittance_absolute_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            e = np.asarray(t_exp_f, dtype=np.float64) - t_th
            if sigma_t_f is not None:
                st = np.asarray(sigma_t_f, dtype=np.float64).ravel()
                if st.size == e.size:
                    chi += float(cfg.weight_t) * float(np.dot(w, (e / st) ** 2))
            else:
                chi += float(cfg.weight_t) * float(np.dot(w, (e / float(sig_t)) ** 2))
        if cfg.data_type in (DataType.REFLECTION, DataType.BOTH) and r_exp_f is not None and float(cfg.weight_r) > 0:
            if cfg.t_is_ratio:
                r_th = _reflectance_ratio_theoretical_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            else:
                r_th = _reflectance_absolute_backside_from_nk(lam_f, n_f, k_f, d_nm, n_sub_f)
            e = np.asarray(r_exp_f, dtype=np.float64) - r_th
            if sigma_r_f is not None:
                sr = np.asarray(sigma_r_f, dtype=np.float64).ravel()
                if sr.size == e.size:
                    chi += float(cfg.weight_r) * float(np.dot(w, (e / sr) ** 2))
            else:
                chi += float(cfg.weight_r) * float(np.dot(w, (e / float(sig_r)) ** 2))

        # Add regularization if not pure spectral
        if not bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))
            if reg_w > 0.0:
                k_loc = int(sk.size)
                L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]
                if L_nodes.size >= 3:
                    d2 = np.diff(L_nodes, n=2)
                    chi += reg_w * float(np.mean(d2 * d2))

        return float(chi) if np.isfinite(chi) else 1e30

    # Select objective based on mode
    _obj_nodes = _chi2_nodes if use_lr else _mse_nodes

    m0 = float(_obj_nodes(x0))

    if not np.isfinite(m0) or m0 >= 1e29:
        return None

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    # Lazy seed RMSE evaluation: compute only when seed-gate triggers (refit worse than seed).
    # In the common case where the refit is better, this avoids a redundant nk_from_x_pwlnk +
    # spectral_mse_rmse_masked_from_nk call (~15-20% savings per corridor refit).
    _seed_cache: dict[str, Any] = {}

    def _eval_seed_rmse() -> tuple[float, np.ndarray, np.ndarray, float]:
        if "done" not in _seed_cache:
            x_full_seed = _pack(x0)
            n_s, k_s = nk_from_x_pwlnk(
                x_full_seed,
                lam_full,
                sk,
                cfg.k_clip_lo,
                cfg.k_clip_hi,
                sig_pre=None,
                n_mono_band_nm=cfg.n_mono_band_nm,
                profile_interp=str(cfg.nk_profile_interp or "smooth"),
            )
            mse_s, rmse_s = spectral_mse_rmse_masked_from_nk(
                cfg,
                {},
                lam_full,
                np.asarray(n_s, dtype=np.float64).ravel(),
                np.asarray(k_s, dtype=np.float64).ravel(),
                float(d_target_nm),
            )
            _seed_cache.update(
                done=True,
                n_lam=np.asarray(n_s, dtype=np.float64).ravel(),
                k_lam=np.asarray(k_s, dtype=np.float64).ravel(),
                mse=float(mse_s) if np.isfinite(float(mse_s)) else float("nan"),
                rmse=float(rmse_s) if np.isfinite(float(rmse_s)) else float("nan"),
            )
        return _seed_cache["rmse"], _seed_cache["n_lam"], _seed_cache["k_lam"], _seed_cache["mse"]

    from certus.spline.spline_objective import spline_pwl_analytic_grad_supported

    def _jac_nodes(x_nodes: np.ndarray) -> np.ndarray | None:

        if not spline_pwl_analytic_grad_supported(cfg):
            return None

        x_full = _pack(x_nodes)

        g_full = obj_stage.analytic_gradient(x_full)

        if g_full is None:
            return None

        gn = np.asarray(g_full[1:], dtype=np.float64).ravel().copy()

        if bool(getattr(cfg, "spline_pure_spectral_objective", False)):
            return gn

        reg_w = float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0))

        if reg_w > 0.0:
            k_loc = int(sk.size)

            L_nodes = np.asarray(x_nodes, dtype=np.float64).ravel()[k_loc:]

            if L_nodes.size >= 3:
                d2 = np.diff(L_nodes, n=2)

                m = int(d2.size)

                if m > 0:
                    fac = (reg_w * 2.0 / float(m)) * d2  # shape (m,)
                    # Stencil: gn[k+j] += fac[j], gn[k+j+1] -= 2*fac[j], gn[k+j+2] += fac[j]
                    idx_base = k_loc + np.arange(m)
                    np.add.at(gn, idx_base, fac)
                    np.add.at(gn, idx_base + 1, -2.0 * fac)
                    np.add.at(gn, idx_base + 2, fac)

        return gn

    _jac_n = None

    _use_fused = False

    if spline_pwl_analytic_grad_supported(cfg):
        _tj = _jac_nodes(x0)

        if _tj is not None and np.all(np.isfinite(_tj)):
            _jac_n = _jac_nodes

            # Fused mode: when _obj_nodes == _mse_nodes (alpha mode) and no
            # lnk regularization, obj_stage.cost_and_grad gives (f, g) in one
            # call, avoiding duplicate nk/T/R evaluations.
            _has_reg = (
                not bool(getattr(cfg, "spline_pure_spectral_objective", False))
                and float(max(getattr(cfg, "lnk_spline_reg_weight", 0.0) or 0.0, 0.0)) > 0.0
            )
            if not use_lr and not _has_reg:
                _use_fused = True

    bds = bds_cache if bds_cache is not None else [(float(b[i, 0]), float(b[i, 1])) for i in range(int(b.shape[0]))]

    if _use_fused:

        def _fused_nodes(x_nodes) -> tuple:
            x_full = _pack(x_nodes)
            cost, grad_full = obj_stage.cost_and_grad(x_full)
            return cost, np.asarray(grad_full[1:], dtype=np.float64).ravel().copy()

        res = minimize(
            _fused_nodes,
            x0,
            method="L-BFGS-B",
            jac=True,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-11, "gtol": 1e-8},
        )
    else:
        res = minimize(
            _obj_nodes,
            x0,
            method="L-BFGS-B",
            jac=_jac_n,
            bounds=bds,
            options={"maxfun": int(max(300, maxfun)), "ftol": 1e-11, "gtol": 1e-8},
        )

    x_best = np.asarray(getattr(res, "x", x0), dtype=np.float64).ravel()

    x_best = clip_to_bounds(x_best, b[:, 0], b[:, 1])

    m_best_obj = float(_obj_nodes(x_best))  # P0.1 FIX: Consistent with minimize objective

    if not np.isfinite(m_best_obj) or m_best_obj >= 1e29:
        return None

    # Rebuild n(lambda), k(lambda) on masked / full grid via nk_from_x_pwlnk.
    # B7 FIX: reuse cached nk from the last _chi2_nodes/_mse_nodes call if available,
    # avoiding a redundant ~5ms nk_from_x_pwlnk + physics rebuild.
    x_full_best = np.concatenate((np.asarray([float(d_target_nm)], dtype=np.float64), x_best))

    if use_lr and "n_lam" in _chi2_nk_cache:
        n_lam = _chi2_nk_cache["n_lam"]
        k_lam = _chi2_nk_cache["k_lam"]
    else:
        n_lam, k_lam = nk_from_x_pwlnk(
            x_full_best,
            lam_full,
            sk,
            cfg.k_clip_lo,
            cfg.k_clip_hi,
            sig_pre=None,
            n_mono_band_nm=cfg.n_mono_band_nm,
            profile_interp=str(cfg.nk_profile_interp or "smooth"),
        )

    mse_spec, rmse_spec = spectral_mse_rmse_masked_from_nk(
        cfg,
        {},
        lam_full,
        np.asarray(n_lam, dtype=np.float64).ravel(),
        np.asarray(k_lam, dtype=np.float64).ravel(),
        float(d_target_nm),
    )

    mse_spec_f = float(mse_spec) if np.isfinite(float(mse_spec)) else float("nan")
    rmse = float(rmse_spec) if np.isfinite(float(rmse_spec)) else float("nan")
    # Guarantee a finite RMSE per requested Δd grid point whenever the objective is finite.
    # Some corner cases can yield NaN from the external spectral recomputation even though the
    # internal masked objective returns a valid MSE (pure_spectral mode).
    if not np.isfinite(rmse):
        m_obj = float(m_best_obj) if np.isfinite(float(m_best_obj)) else float("nan")
        if np.isfinite(m_obj) and m_obj < 1e29:
            rmse = float(np.sqrt(max(m_obj, 0.0)))
            if not np.isfinite(mse_spec_f):
                mse_spec_f = float(m_obj)

    rmse_refit_attempt = float(rmse)

    # B1 FIX (2026-05-07): Seed-gate compares *spectral RMSE* (not composite objective).
    # The composite objective (m0, m_best_obj) includes regularization penalty (reg_w)
    # which can bias the decision: a refit with better spectral RMSE but worse
    # regularization penalty would be incorrectly rejected, narrowing the corridor.
    # We lazily evaluate the seed RMSE only when the gate might trigger.
    keep_seed = False
    if bool(keep_nominal_seed_if_refit_worse) and np.isfinite(rmse):
        rmse_seed_for_gate, _, _, _ = _eval_seed_rmse()
        keep_seed_tol = max(
            float(seed_keep_tol_abs),
            float(seed_keep_tol_rel) * max(float(rmse_seed_for_gate), 1e-12),
        )
        keep_seed = bool(np.isfinite(rmse_seed_for_gate) and rmse > rmse_seed_for_gate + keep_seed_tol)

    if keep_seed:
        # Lazy eval: only now do we compute the seed spectral RMSE.
        rmse_seed, n_lam_seed, k_lam_seed, mse_seed_spec = _eval_seed_rmse()

        log.info(
            "Corridor fixed-d refit d=%.5g nm: kept nominal seed (spectral RMSE refit=%.5g > seed=%.5g + tol=%.5g).",
            float(d_target_nm),
            float(rmse_refit_attempt),
            float(rmse_seed),
            float(keep_seed_tol),
        )

        x_best = x0.copy()

        m_best_obj = float(m0)

        n_lam = np.asarray(n_lam_seed, dtype=np.float64).ravel()

        k_lam = np.asarray(k_lam_seed, dtype=np.float64).ravel()

        mse_spec = float(mse_seed_spec) if np.isfinite(float(mse_seed_spec)) else float("nan")
        mse_spec_f = float(mse_spec) if np.isfinite(float(mse_spec)) else float("nan")

        rmse = rmse_seed

    # For reporting: physical n_nodes (useful for export) when n_mono is active.

    n_slice = x_best[:k]

    n_nodes_phys = (
        np.asarray(n_slice, dtype=np.float64).copy()
        if cfg.n_mono_band_nm is None
        else x_slice_n_to_physical_nodes(n_slice, sk, cfg.n_mono_band_nm)
    )

    L_nodes = x_best[k:].copy()

    _msg = str(getattr(res, "message", ""))[:160]

    if keep_seed:
        _msg = f"{_msg} | seed_kept_over_refit(spectral_RMSE)"[:160]

    return {
        "success": bool(getattr(res, "success", False)),
        "message": _msg,
        "nit": int(getattr(res, "nit", 0) or 0),
        "nfev": int(getattr(res, "nfev", 0) or 0),
        "d_nm": float(d_target_nm),
        "mse": float(mse_spec_f) if np.isfinite(float(mse_spec_f)) else float("nan"),
        "mse_objective": float(m_best_obj),
        "rmse": rmse,
        "rmse_seed_before_refit": float(_eval_seed_rmse()[0]) if keep_seed else None,
        "seed_kept_over_refit": bool(keep_seed),
        "seed_keep_tolerance": float(keep_seed_tol),
        "seed_keep_rule": (
            "spectral_rmse_refit_gt_seed_plus_tol" if bool(keep_nominal_seed_if_refit_worse) else "disabled"
        ),
        "rmse_refit_attempted": float(rmse_refit_attempt) if np.isfinite(rmse_refit_attempt) else None,
        "chi2": None,
        # Exact warm start (same x space as optimizer: n_slice (physical or ξ) + L_nodes)
        "x_nodes_best": x_best,
        "sigma_knots": sk,
        "n_nodes_physical": n_nodes_phys,
        "L_nodes": L_nodes,
        "n_lam": np.asarray(n_lam, dtype=np.float64).ravel(),
        "k_lam": np.asarray(k_lam, dtype=np.float64).ravel(),
    }

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
            except (ValueError, TypeError, RuntimeError):
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
                    except (ValueError, TypeError, RuntimeError):
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
        from certus.spline.spline_objective import x_slice_n_to_physical_nodes
        from certus.spline.certus_index_spline_core import physical_nodes_to_x_slice_n
        from certus.core.certus_core import N_MIN_LIMIT, N_MAX_LIMIT

        ratio_d = float(d_prev / d_try) if d_try >= 1.0 else 1.0
        k = int(np.asarray(sk, dtype=np.float64).size)
        _n_old = x_slice_n_to_physical_nodes(x_prev[:k], sk, cfg.n_mono_band_nm)
        _n_new = np.clip(_n_old * ratio_d, N_MIN_LIMIT, N_MAX_LIMIT)
        x_smart_seed[:k] = physical_nodes_to_x_slice_n(_n_new, sk, cfg.n_mono_band_nm)
    except (ValueError, TypeError, RuntimeError) as e:
        log.debug("Iso-Phase warm-start projection failed: %s", e)
        x_smart_seed = x_prev
    return x_smart_seed

def _detect_corridor_spike(
    d_vals: list[float],
    rmse_vals: list[float],
    d_try: float,
    rm: float,
    d0: float,
    parab_tol_abs: float,
) -> tuple[bool, float, float]:
    """Detects if an RMSE point is an abnormal spike using local parabolic fit + discontinuity check."""
    is_spike = False
    rm_pred = float("nan")
    _tol_eff = float("nan")

    if len(d_vals) >= 5:
        try:
            _ds = np.asarray(d_vals[-12:], dtype=np.float64)
            _rs = np.asarray(rmse_vals[-12:], dtype=np.float64)
            _coeffs = np.polyfit(_ds - d0, _rs, 2)
            rm_pred = float(np.polyval(_coeffs, d_try - d0))

            _pred_hist = np.polyval(_coeffs, _ds - d0)
            _resid = _rs - _pred_hist
            _sigma = float(1.4826 * np.median(np.abs(_resid - np.median(_resid))))
            _tol_eff = max(parab_tol_abs, 4.0 * _sigma)

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
                is_spike = bool(jump_ratio >= 3.0)
            elif parab_exceeds:
                is_spike = True
        except (ValueError, TypeError, IndexError):
            log.debug("%s _detect_breakpoint: validation check failed (non-critical)", _LOG_PREFIX)

    return is_spike, rm_pred, _tol_eff


@dataclass
class CorridorLiveStreamer:
    live_cb: Any | None
    live_stream_lock: threading.Lock
    live_d_vals: list[float]
    live_rmse_vals: list[float]
    live_n_curves: list[np.ndarray]
    live_k_curves: list[np.ndarray]
    live_chi2_vals: list[float]

    def emit_profile(self, current_d_nm=None) -> None:
        if not callable(self.live_cb):
            return
        if not self.live_d_vals or len(self.live_rmse_vals) != len(self.live_d_vals):
            return
        d_a = np.asarray(self.live_d_vals, dtype=np.float64).ravel()
        r_a = np.asarray(self.live_rmse_vals, dtype=np.float64).ravel()
        m = np.isfinite(d_a) & np.isfinite(r_a)
        if not np.any(m):
            return
        d_a = d_a[m]
        r_a = r_a[m]
        order = np.argsort(d_a, kind="mergesort")
        payload = {
            "profile_d_status": "manual_grid_live",
            "profile_d_values_nm": np.asarray(d_a[order], dtype=np.float64),
            "profile_d_rmse_values": np.asarray(r_a[order], dtype=np.float64),
            "profile_d_manual_grid_done_points": int(order.size),
            "profile_d_manual_grid_total_points": int(max(1, order.size)),
            "profile_d_manual_grid_base_done_points": int(order.size),
            "profile_d_manual_grid_extra_done_points": 0,
            "profile_d_manual_grid_progress": 1.0,
            "profile_d_manual_grid_current_d_nm": (
                float(current_d_nm)
                if (current_d_nm is not None and np.isfinite(float(current_d_nm)))
                else float(d_a[order][-1])
            ),
        }
        if len(self.live_n_curves) == len(self.live_d_vals):
            payload["profile_d_n_curves"] = np.asarray([self.live_n_curves[i] for i in np.flatnonzero(m)], dtype=np.float64)[order]
        if len(self.live_k_curves) == len(self.live_d_vals):
            payload["profile_d_k_curves"] = np.asarray([self.live_k_curves[i] for i in np.flatnonzero(m)], dtype=np.float64)[order]
        if len(self.live_chi2_vals) == len(self.live_d_vals):
            payload["profile_d_chi2_values"] = np.asarray([self.live_chi2_vals[i] for i in np.flatnonzero(m)], dtype=np.float64)[order]
        try:
            self.live_cb(payload)
        except (RuntimeError, TypeError):
            log.debug("%s failed to invoke live_cb in async loop (non-critical)", _LOG_PREFIX, exc_info=True)

    def push_point(self, d_nm: float, rmse: float, n_lam=None, k_lam=None, chi2=None) -> None:
        if not callable(self.live_cb):
            return
        with self.live_stream_lock:
            self.live_d_vals.append(float(d_nm))
            self.live_rmse_vals.append(float(rmse))
            self.live_n_curves.append(np.asarray(n_lam, dtype=np.float64).ravel() if n_lam is not None else np.asarray([], dtype=np.float64))
            self.live_k_curves.append(np.asarray(k_lam, dtype=np.float64).ravel() if k_lam is not None else np.asarray([], dtype=np.float64))
            self.live_chi2_vals.append(float(chi2) if (chi2 is not None and np.isfinite(float(chi2))) else float("nan"))
            self.emit_profile(current_d_nm=float(d_nm))

    def push_payload(self, payload):
        self.push_point(
            float(payload.get("d_nm", float("nan"))),
            float(payload.get("rmse", float("nan"))),
            np.asarray(payload.get("n_lam", []), dtype=np.float64).ravel(),
            np.asarray(payload.get("k_lam", []), dtype=np.float64).ravel(),
            float(payload.get("chi2", float("nan"))),
        )


@dataclass
class CorridorWalkSideContext:
    pconf: ProfileCorridorConfig
    cfg: SplineOptConfig
    sk: np.ndarray
    x_nodes_center: np.ndarray
    x0_default: np.ndarray
    bounds_nodes: np.ndarray
    maxfun_prof: int
    use_lr: bool
    sig_t: float
    sig_r: float
    chi2_min: float
    delta_chi2: float
    sigma_t_f_hetero: np.ndarray | None
    sigma_r_f_hetero: np.ndarray | None
    rmse_thresh_active: float
    live_point_cb: Any | None
    d_vals: list[float]
    n_curves: list[np.ndarray]
    k_curves: list[np.ndarray]
    rmse_vals: list[float]
    chi2_vals: list[float]

    def refine_bracket(
        self,
        a_d: float,
        a_x: np.ndarray,
        y_a: float,
        b_d: float,
        y_b: float,
        br_sign: float,
    ) -> tuple[float, np.ndarray] | None:

        if not bool(self.pconf.refine_boundary):
            return None

        if not (a_d < b_d if br_sign > 0 else a_d > b_d):
            return None

        for _ in range(int(max(1, self.pconf.refine_max_iter))):
            if abs(b_d - a_d) <= float(max(1e-6, self.pconf.refine_tol_nm)):
                break

            if y_b - y_a > 1e-12:
                frac = -y_a / (y_b - y_a)
                frac = min(max(frac, 0.2), 0.8)
            else:
                frac = 0.5
            m_d = a_d + frac * (b_d - a_d)
            m_x0 = a_x

            fitm, _, metricm = _best_fit_at_d(
                self.cfg,
                sk=self.sk,
                d_nm=float(m_d),
                x_seed_primary=m_x0,
                x_seed_secondary=self.x_nodes_center,
                x_seed_default=self.x0_default,
                bounds_nodes=self.bounds_nodes,
                maxfun=self.maxfun_prof,
                use_lr=self.use_lr,
                sig_t=self.sig_t,
                sig_r=self.sig_r,
                chi2_min_ref=float(self.chi2_min) if (self.use_lr and np.isfinite(self.chi2_min)) else None,
                delta_chi2=float(self.delta_chi2) if np.isfinite(self.delta_chi2) else 0.0,
                pconf=self.pconf,
                stage_label="Refine",
                sigma_t_f=self.sigma_t_f_hetero,
                sigma_r_f=self.sigma_r_f_hetero,
            )

            if fitm is None or not np.isfinite(float(fitm.get("rmse", float("nan")))):
                b_d = float(m_d)

                continue

            rm = float(fitm["rmse"])

            ok_rb = False
            chi_m = float("nan")
            y_m = 0.0
            if self.use_lr:
                chi_m = float(metricm)
                ok_rb = np.isfinite(chi_m) and np.isfinite(self.chi2_min) and (chi_m <= self.chi2_min + self.delta_chi2)
                y_m = chi_m - (self.chi2_min + self.delta_chi2)
            else:
                ok_rb = rm <= self.rmse_thresh_active
                y_m = rm - self.rmse_thresh_active

            if ok_rb:
                a_d = float(m_d)
                y_a = y_m

                a_x = np.asarray(fitm["x_nodes_best"], dtype=np.float64).ravel().copy()

                self.d_vals.append(float(m_d))

                self.n_curves.append(np.asarray(fitm["n_lam"], dtype=np.float64))

                self.k_curves.append(np.asarray(fitm["k_lam"], dtype=np.float64))

                self.rmse_vals.append(rm)

                self.chi2_vals.append(float(chi_m) if np.isfinite(chi_m) else float("nan"))
                if isinstance(self.live_point_cb, CorridorLiveStreamer):
                    self.live_point_cb.push_payload(
                        {
                            "d_nm": float(m_d),
                            "rmse": float(rm),
                            "n_lam": np.asarray(fitm["n_lam"], dtype=np.float64).ravel(),
                            "k_lam": np.asarray(fitm["k_lam"], dtype=np.float64).ravel(),
                            "chi2": float(chi_m) if np.isfinite(chi_m) else float("nan"),
                        }
                    )

            else:
                b_d = float(m_d)
                y_b = y_m

        return float(a_d), np.asarray(a_x, dtype=np.float64).ravel().copy()


def _corridor_profile_walk_side(
    walk_sign: float,
    pconf: ProfileCorridorConfig,
    cfg: SplineOptConfig,
    sk: np.ndarray,
    d0: float,
    x_nodes_center: np.ndarray,
    x0_default: np.ndarray,
    bounds_nodes: np.ndarray,
    maxfun_prof: int,
    use_lr: bool,
    chi2_min: float,
    delta_chi2: float,
    rmse_thresh_active: float,
    rmse_opt: float,
    sig_t: float,
    sig_r: float,
    sigma_t_f_hetero: np.ndarray | None,
    sigma_r_f_hetero: np.ndarray | None,
    live_streamer: CorridorLiveStreamer | None = None,
    target_min_span: float = 0.0,
) -> dict[str, Any]:
    """One-sided d continuation (+d or -d). Use distinct ``pconf.rng_seed`` per thread when running in parallel."""

    d_vals: list[float] = []

    n_curves: list[np.ndarray] = []

    k_curves: list[np.ndarray] = []

    x_curves: list[np.ndarray] = []

    rmse_vals: list[float] = []

    chi2_vals: list[float] = []

    fit_nfev_values: list[float] = []

    fit_nit_values: list[float] = []

    fit_try_values: list[float] = []

    fit_fail_values: list[float] = []

    n_refines = 0
    seed_gate_eval_count = 0
    seed_gate_kept_count = 0
    seed_gate_delta_refit_minus_seed: list[float] = []

    # --- For local parabola tracking ---
    clean_d_vals: list[float] = [float(d0)]
    clean_rmse_vals: list[float] = [float(rmse_opt)]
    # B4 FIX: unbiased spike detection — track ALL evaluated points (ok or not)
    # so the parabola reflects the true RMSE(d) trend, not just accepted points.
    all_d_vals: list[float] = [float(d0)]
    all_rmse_vals: list[float] = [float(rmse_opt)]

    ctx = CorridorWalkSideContext(
        pconf=pconf,
        cfg=cfg,
        sk=sk,
        x_nodes_center=x_nodes_center,
        x0_default=x0_default,
        bounds_nodes=bounds_nodes,
        maxfun_prof=maxfun_prof,
        use_lr=use_lr,
        sig_t=sig_t,
        sig_r=sig_r,
        chi2_min=chi2_min,
        delta_chi2=delta_chi2,
        sigma_t_f_hetero=sigma_t_f_hetero,
        sigma_r_f_hetero=sigma_r_f_hetero,
        rmse_thresh_active=rmse_thresh_active,
        live_point_cb=live_streamer,
        d_vals=d_vals,
        n_curves=n_curves,
        k_curves=k_curves,
        rmse_vals=rmse_vals,
        chi2_vals=chi2_vals,
    )


    d_prev = float(d0)

    x_prev = np.asarray(x_nodes_center, dtype=np.float64).copy()

    step = float(max(1e-6, getattr(pconf, "step_nm_initial", pconf.step_nm)))

    step_growth = float(max(getattr(pconf, "step_growth", 1.4) or 1.4, 1.0))

    step_cap = float(max(getattr(pconf, "step_nm_max", pconf.step_nm), 1e-6))

    span = 0.0

    nsteps = 0

    effective_max_span = float(pconf.max_span_nm)
    _d_range = float(abs(max(cfg.d_lo, cfg.d_hi) - min(cfg.d_lo, cfg.d_hi)))
    _max_span_safety = min(_d_range * 0.45, max(effective_max_span * 30.0, 300.0))
    _span_hist: list[float] = [0.0]
    _rmse_hist: list[float] = [float(rmse_opt) if np.isfinite(float(rmse_opt)) else float("nan")]

    last_good_d: float | None = None

    last_good_x: np.ndarray | None = None
    last_good_y: float = -delta_chi2 if use_lr else (rmse_opt - rmse_thresh_active)

    dir_lbl = "+d" if float(walk_sign) > 0 else "-d"

    n_valid_side = 0
    _auto_escalated: bool = False  # P0.3: tracks if seed-gate escalation triggered

    log.info(
        "%s Walk %s: start d=%.6f nm | step=%.4g nm | span_max=%.4g nm",
        _LOG_PREFIX,
        dir_lbl,
        d_prev,
        step,
        float(pconf.max_span_nm),
    )

    while nsteps < int(pconf.max_steps_each_side) and span < effective_max_span:
        d_try = float(d_prev + walk_sign * step)

        if d_try < float(min(cfg.d_lo, cfg.d_hi)) - 1e-9 or d_try > float(max(cfg.d_lo, cfg.d_hi)) + 1e-9:
            log.info(
                "%s Walk %s: stop (d bound) | d_try=%.6f nm not in [%.6f, %.6f]",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                float(min(cfg.d_lo, cfg.d_hi)),
                float(max(cfg.d_lo, cfg.d_hi)),
            )

            break

        # --- Iso-Phase Warm-Start (Physics scaling) ---
        # Optical path invariant: n * d ~ constant. To stay exactly in the interference
        # valley without forcing the optimizer to slide down the gradient, we project n.
        x_smart_seed = _generate_iso_phase_seed(x_prev, sk, d_prev, d_try, cfg)

        fit, _, metricv = _best_fit_at_d(
            cfg,
            sk=sk,
            d_nm=float(d_try),
            x_seed_primary=x_smart_seed,
            x_seed_secondary=x_nodes_center,
            x_seed_default=x0_default,
            bounds_nodes=bounds_nodes,
            maxfun=maxfun_prof,
            use_lr=use_lr,
            sig_t=sig_t,
            sig_r=sig_r,
            chi2_min_ref=float(chi2_min) if (use_lr and np.isfinite(chi2_min)) else None,
            delta_chi2=float(delta_chi2) if np.isfinite(delta_chi2) else 0.0,
            pconf=pconf,
            stage_label=f"Step {dir_lbl}",
            sigma_t_f=sigma_t_f_hetero,
            sigma_r_f=sigma_r_f_hetero,
        )

        if fit is None or not np.isfinite(float(fit.get("rmse", float("nan")))):
            log.info("%s Walk %s: stop (fit invalid) | d=%.6f nm", _LOG_PREFIX, dir_lbl, d_try)

            break

        rm = float(fit["rmse"])
        rmse_seed_fit = fit.get("rmse_seed_before_refit")
        rmse_refit_fit = fit.get("rmse_refit_attempted")
        has_seed_gate = (
            rmse_seed_fit is not None
            and rmse_refit_fit is not None
            and np.isfinite(float(rmse_seed_fit))
            and np.isfinite(float(rmse_refit_fit))
        )
        if has_seed_gate:
            seed_gate_eval_count += 1
            if bool(fit.get("seed_kept_over_refit", False)):
                seed_gate_kept_count += 1
            seed_gate_delta_refit_minus_seed.append(float(rmse_refit_fit) - float(rmse_seed_fit))

        # P0.3 FIX: Auto-escalation if seed-gate saturating (>50% kept on first 3 evals)
        if seed_gate_eval_count >= 3 and nsteps <= 5:
            _kept_rate = float(seed_gate_kept_count) / float(seed_gate_eval_count)
            if _kept_rate > 0.5 and not _auto_escalated:
                _auto_escalated = True
                _old_maxfun = maxfun_prof
                maxfun_prof = int(maxfun_prof * 2.0)
                log.warning(
                    "%s Walk %s: seed-gate saturation detected (%.0f%% kept). "
                    "Auto-escalating maxfun %d -> %d. Consider increasing polish budget or enabling refit_pure_spectral.",
                    _LOG_PREFIX,
                    dir_lbl,
                    100.0 * _kept_rate,
                    _old_maxfun,
                    maxfun_prof,
                )

        ok = False
        chi_v = float("nan")
        y_v = float("nan")

        if use_lr:
            chi_v = float(metricv)
            y_v = chi_v - (chi2_min + delta_chi2)
            ok = np.isfinite(chi_v) and np.isfinite(chi2_min) and (y_v <= 0)
        else:
            y_v = rm - rmse_thresh_active
            ok = rm <= rmse_thresh_active

        if use_lr:
            log.info(
                "%s Walk %s: d=%.6f nm | chi2=%.8f | Deltachi2=%+.8f | RMSE=%.8f | nit=%d nfev=%d",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(chi_v),
                float(chi_v - chi2_min) if np.isfinite(chi2_min) else float("nan"),
                float(rm),
                int(fit.get("nit", 0)),
                int(fit.get("nfev", 0)),
            )

        else:
            log.info(
                "%s Walk %s: d=%.6f nm | RMSE=%.8f | DeltaRMSE(vs_ref_best)=%+.8f | seed_gate=%s | DeltaRMSE(refit-seed)=%s | nit=%d nfev=%d",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(rm),
                float(rm - rmse_opt) if np.isfinite(rmse_opt) else float("nan"),
                "kept" if bool(fit.get("seed_kept_over_refit", False)) else "refit",
                (f"{(float(rmse_refit_fit) - float(rmse_seed_fit)):+.8f}" if has_seed_gate else "n/a"),
                int(fit.get("nit", 0)),
                int(fit.get("nfev", 0)),
            )

        # --- Spike detection vs local parabola ---
        # B4 FIX: use all_d_vals/all_rmse_vals (every evaluated point) instead of
        # d_vals/rmse_vals (accepted-only). This prevents the parabola from being
        # biased toward low-RMSE points and incorrectly flagging natural RMSE rises.
        all_d_vals.append(float(d_try))
        all_rmse_vals.append(float(rm))
        parab_tol_abs = float(getattr(pconf, "parabola_spike_tolerance_abs", 2e-5))
        is_spike, rm_pred, _tol_eff = _detect_corridor_spike(
            all_d_vals, all_rmse_vals, d_try, rm, float(d0), parab_tol_abs
        )

        if is_spike:
            log.info(
                "%s Walk %s: spike detected at d=%.6f nm (RMSE=%.8f vs pred=%.8f). Retrying with jitter...",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                rm,
                rm_pred,
            )
            pconf_retry = pconf.replace(n_starts=max(3, int(pconf.n_starts) + 2))

            fit_retry, _, _ = _best_fit_at_d(
                cfg,
                sk=sk,
                d_nm=float(d_try),
                x_seed_primary=x_smart_seed,
                x_seed_secondary=x_nodes_center,
                x_seed_default=x0_default,
                bounds_nodes=bounds_nodes,
                maxfun=maxfun_prof * 2,
                use_lr=use_lr,
                sig_t=sig_t,
                sig_r=sig_r,
                chi2_min_ref=chi2_min if use_lr else None,
                delta_chi2=delta_chi2,
                pconf=pconf_retry,
                stage_label=f"Retry {dir_lbl}",
                sigma_t_f=sigma_t_f_hetero,
                sigma_r_f=sigma_r_f_hetero,
            )

            if fit_retry is not None:
                rm_retry = float(fit_retry.get("rmse", float("inf")))
                if rm_retry < rm:
                    log.info("%s Walk %s: retry improved RMSE %.8f -> %.8f", _LOG_PREFIX, dir_lbl, rm, rm_retry)
                    fit = fit_retry
                    rm = rm_retry
                    # Re-check after retry
                    if rm <= rm_pred + _tol_eff:
                        is_spike = False
                        log.info("%s Walk %s: retry recovered point at d=%.6f nm", _LOG_PREFIX, dir_lbl, d_try)

        if is_spike:
            log.warning(
                "%s Walk %s: rejecting point at d=%.6f nm (persistent spike RMSE=%.8f vs pred=%.8f).",
                _LOG_PREFIX,
                dir_lbl,
                d_try,
                rm,
                rm_pred,
            )
            # Advance thickness to avoid looping, but do not add the point to results
            # and do not validate the step.
            d_prev = float(d_try)
            nsteps += 1
            # x_prev remains the last stable point, favouring a good seed at the next step.
            continue

        force_points = (
            nsteps < max(3, int(getattr(pconf, "min_valid_each_side", 0)))
            or (target_min_span > 0.0 and span < target_min_span)
        )

        if ok or force_points:
            d_vals.append(float(d_try))

            n_curves.append(np.asarray(fit["n_lam"], dtype=np.float64))

            k_curves.append(np.asarray(fit["k_lam"], dtype=np.float64))

            x_curves.append(np.asarray(fit["x_nodes_best"], dtype=np.float64).ravel().copy())

            rmse_vals.append(rm)

            chi2_vals.append(float(chi_v) if np.isfinite(chi_v) else float("nan"))
            if live_streamer is not None:
                live_streamer.push_point(
                    float(d_try),
                    float(rm),
                    np.asarray(fit["n_lam"], dtype=np.float64).ravel(),
                    np.asarray(fit["k_lam"], dtype=np.float64).ravel(),
                    float(chi_v) if np.isfinite(chi_v) else float("nan"),
                )

            fit_nfev_values.append(float(fit.get("nfev", float("nan"))))

            fit_nit_values.append(float(fit.get("nit", float("nan"))))

            fit_try_values.append(float(fit.get("n_try", float("nan"))))

            fit_fail_values.append(float(fit.get("n_failed_fit", float("nan"))))

            x_prev = np.asarray(fit["x_nodes_best"], dtype=np.float64).ravel().copy()

            d_prev = float(d_try)

            span = abs(d_prev - float(d0))
            if ok:
                last_good_d = float(d_prev)
                last_good_x = x_prev.copy()
                last_good_y = float(y_v)
                # Update the "clean" history for the parabola
                clean_d_vals.append(float(d_prev))
                clean_rmse_vals.append(float(rm))

            nsteps += 1

            step = min(step_cap, step * step_growth)

            _span_hist.append(span)
            _rmse_hist.append(rm)
            if len(_span_hist) >= 3 and rm < rmse_thresh_active and np.isfinite(rmse_thresh_active) and np.isfinite(rm):
                _slope = float("nan")
                _nm_remaining = float("nan")
                _ds = _span_hist[-1] - _span_hist[-2]
                _dr = _rmse_hist[-1] - _rmse_hist[-2]
                if _ds > 1e-10 and _dr > 1e-15:
                    _slope = _dr / _ds
                    _nm_remaining = (rmse_thresh_active - rm) / _slope
                    secant_step = float(np.clip(_nm_remaining, step, step_cap * 2.0))
                    if secant_step > step:
                        step = secant_step

                # Parabolic prediction: fit quadratic on last 3 clean points to estimate
                # distance to threshold more accurately than the linear secant.
                if len(clean_d_vals) >= 3 and not use_lr:
                    try:
                        _cd = np.asarray(clean_d_vals[-3:], dtype=np.float64) - float(d0)
                        _cr = np.asarray(clean_rmse_vals[-3:], dtype=np.float64)
                        _pa, _pb, _pc = np.polyfit(_cd, _cr, 2)
                        if np.isfinite(_pa) and _pa > 0.0:
                            _disc = _pb**2 - 4.0 * _pa * (_pc - float(rmse_thresh_active))
                            if _disc >= 0.0:
                                _root = (-_pb + float(walk_sign) * np.sqrt(_disc)) / (2.0 * _pa)
                                _d_pred = float(d0) + float(_root)
                                _para_step = abs(_d_pred - float(d_prev)) * 0.85
                                if np.isfinite(_para_step) and _para_step > step:
                                    step = float(np.clip(_para_step, step, step_cap * 3.0))
                                    log.debug(
                                        "%s Walk %s: parabolic step prediction d_boundary~%.4f nm -> step %.4g nm",
                                        _LOG_PREFIX,
                                        dir_lbl,
                                        float(_d_pred),
                                        float(step),
                                    )
                    except (np.linalg.LinAlgError, ValueError):
                        log.debug("%s parabola fit failed at d=%.6f nm (non-critical)", _LOG_PREFIX, float(d0))

                if np.isfinite(_slope) and np.isfinite(_nm_remaining) and _nm_remaining > 0.0:
                    _projected = span + _nm_remaining * 1.15
                    if _projected > effective_max_span:
                        _new_span = min(_projected, _max_span_safety)
                        if _new_span > effective_max_span + 0.5:
                            log.info(
                                "%s Walk %s: auto-extend span %.1f -> %.1f nm "
                                "(RMSE slope=%.3g /nm, ~%.1f nm to threshold)",
                                _LOG_PREFIX,
                                dir_lbl,
                                effective_max_span,
                                _new_span,
                                _slope,
                                _nm_remaining,
                            )
                        effective_max_span = max(effective_max_span, _new_span)

            if ok:
                n_valid_side += 1

            continue

        if not ok and not force_points and last_good_d is not None and last_good_x is not None:
            rb = ctx.refine_bracket(last_good_d, last_good_x, last_good_y, float(d_try), y_v, walk_sign)

            if rb is not None:
                n_refines += 1

                log.info(
                    "%s Walk %s: refined boundary on admissible side ~ d=%.6f nm",
                    _LOG_PREFIX,
                    dir_lbl,
                    float(rb[0]),
                )

        if use_lr and np.isfinite(chi_v) and np.isfinite(chi2_min):
            chi_lim = float(chi2_min) + float(delta_chi2)

            log.info(
                "%s Walk %s: stop (LR Deltaχ²) | d=%.6f nm χ²=%.6g > χ²_center+Delta=%.6g "
                "(Deltaχ² vs center=%+.6g | RMSE=%.8f; the alpha×RMSE threshold logged above does not apply to the LR criterion)",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(chi_v),
                float(chi_lim),
                float(chi_v - chi2_min),
                float(rm),
            )

        else:
            log.info(
                "%s Walk %s: stop (RMSE > seuil) | d=%.6f nm RMSE=%.8f > %.8f",
                _LOG_PREFIX,
                dir_lbl,
                float(d_try),
                float(rm),
                float(rmse_thresh_active),
            )

        break

    return {
        "d_vals": d_vals,
        "n_curves": n_curves,
        "k_curves": k_curves,
        "x_curves": x_curves,
        "rmse_vals": rmse_vals,
        "chi2_vals": chi2_vals,
        "fit_nfev_values": fit_nfev_values,
        "fit_nit_values": fit_nit_values,
        "fit_try_values": fit_try_values,
        "fit_fail_values": fit_fail_values,
        "n_valid_side": int(n_valid_side),
        "n_refines": int(n_refines),
        "seed_gate_eval_count": int(seed_gate_eval_count),
        "seed_gate_kept_count": int(seed_gate_kept_count),
        "seed_gate_delta_refit_minus_seed": seed_gate_delta_refit_minus_seed,
        "seed_gate_auto_escalated": bool(_auto_escalated),
    }

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

            except (TypeError, ValueError):
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

def _bootstrap_single_replicate(
    cfg_b: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig,
    qref: int,
    lam: np.ndarray,
    log_run_1based: int | None = None,
) -> dict[str, Any]:
    """Run profiling + quick refit for one draw (cfg_b); structured return for aggregation."""

    lam = np.asarray(lam, dtype=np.float64).ravel()

    out: dict[str, Any] = {"status": "exception", "nvalid": 0}

    try:
        base_for: dict[str, Any] = base_result

        if int(qref) > 0:
            br = quick_pwlnk_refit_result_dict(cfg_b, base_result, maxfun=int(qref))

            if br is not None:
                base_for = br

        extra = compute_profiled_corridors_by_d(cfg_b, base_for, pconf=pconf, log_coaching=False)

    except NUMERICAL_FAULT_EXCEPTIONS:
        if log_run_1based is not None:
            log.exception("%s [BOOT] failed run=%d", _LOG_PREFIX, int(log_run_1based))

        else:
            log.exception("%s [BOOT] internal run failed", _LOG_PREFIX)

        return out

    d_int = extra.get("profile_d_interval_nm", None)

    out["nvalid"] = int(np.asarray(extra.get("profile_d_values_nm", [])).size)

    if not (isinstance(d_int, (tuple, list)) and len(d_int) == 2):
        out["status"] = "bad_interval"

        return out

    try:
        dlo = float(d_int[0])

        dhi = float(d_int[1])

    except (TypeError, ValueError):
        out["status"] = "bad_interval"

        return out

    n_lo = np.asarray(extra.get("corridor_n_lo", []), dtype=np.float64).ravel()

    n_hi = np.asarray(extra.get("corridor_n_hi", []), dtype=np.float64).ravel()

    k_lo = np.asarray(extra.get("corridor_k_lo", []), dtype=np.float64).ravel()

    k_hi = np.asarray(extra.get("corridor_k_hi", []), dtype=np.float64).ravel()

    if not (n_lo.size == lam.size == n_hi.size == k_lo.size == k_hi.size):
        out["status"] = "shape"

        return out

    out["status"] = "ok"

    out["dlo"] = dlo

    out["dhi"] = dhi

    out["n_lo"] = n_lo

    out["n_hi"] = n_hi

    out["k_lo"] = k_lo

    out["k_hi"] = k_hi

    return out

def _bootstrap_pool_entry(payload: tuple[Any, ...]) -> tuple[int, dict[str, Any]]:
    """ProcessPoolExecutor entry point (picklable, module level)."""

    b, cfg_b, base_result, pconf, qref, lam = payload

    r = _bootstrap_single_replicate(
        cfg_b,
        base_result,
        pconf=pconf,
        qref=int(qref),
        lam=lam,
        log_run_1based=int(b) + 1,
    )

    return int(b), r

def _resample_residuals_block(e: np.ndarray, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap resample of residuals (wrap-around)."""

    ee = np.asarray(e, dtype=np.float64).ravel()
    n = int(ee.size)
    if n == 0:
        return ee.copy()
    L = int(max(1, min(block_len, n)))
    if L == 1:
        idx = rng.integers(0, n, size=n, endpoint=False)
        return ee[idx]
    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=n_blocks, endpoint=False)
    out = np.empty(n_blocks * L, dtype=np.float64)
    pos = 0
    for s in starts:
        j = (s + np.arange(L)) % n
        out[pos : pos + L] = ee[j]
        pos += L
    return out[:n]


def _theoretical_TR_from_base_result(
    cfg: "SplineOptConfig",
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

    if (
        cfg.data_type in (DataType.TRANSMISSION, DataType.BOTH)
        and cfg.t_exp is not None
        and float(cfg.weight_t) > 0
    ):
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


def compute_bootstrap_corridors_by_d(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig,
    n_boot: int,
    percentile: float = 0.95,
    seed: int = 0,
    sigma_t: float | None = None,
    sigma_r: float | None = None,
    mode: str = "parametric",
    block_len: int = 1,
    quick_refit_maxfun: int | None = None,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """V2.4: parametric bootstrap for bands.

    Builds B synthetic (T/R) datasets by adding Gaussian noise (sigma_T, sigma_R),

    reruns ``compute_profiled_corridors_by_d`` and aggregates:

      - n/k corridor percentiles (on lambda)

      - distribution of d_interval bounds.

    ``n_workers``: parallelism for replicates (``ProcessPoolExecutor``). Default: ``cfg.corridor_bootstrap_n_workers`` or 1.

    On failure (pickle, worker), falls back to sequential.

    """

    B = int(max(0, n_boot))

    if B <= 0:
        return {}

    p = float(np.clip(percentile, 0.5, 0.999999))

    q_lo = 0.5 * (1.0 - p)

    q_hi = 1.0 - q_lo

    rng = np.random.default_rng(int(seed))

    mode = str(mode or "parametric").strip().lower()

    if mode not in ("parametric", "residual"):
        mode = "parametric"

    blk = int(max(1, block_len))

    # Default sigma: consistent with LR mode (auto := RMSE_opt) when not provided.

    rmse_opt = float(base_result.get("rmse", float("nan")))

    sigma_auto = float(rmse_opt) if np.isfinite(rmse_opt) and rmse_opt > 0 else 1.0

    sig_t = float(sigma_t) if (sigma_t is not None and float(sigma_t) > 0) else sigma_auto

    sig_r = float(sigma_r) if (sigma_r is not None and float(sigma_r) > 0) else sigma_auto

    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    t0 = np.asarray(cfg.t_exp, dtype=np.float64).ravel() if cfg.t_exp is not None else None

    r0 = np.asarray(cfg.r_exp, dtype=np.float64).ravel() if cfg.r_exp is not None else None

    if lam.size < 3:
        return {}

    if t0 is not None and t0.size != lam.size:
        return {}

    if r0 is not None and r0.size != lam.size:
        return {}

    from certus.spline.spline_objective import _spline_objective_lam_mask

    qref = int(quick_refit_maxfun) if quick_refit_maxfun is not None else 0

    hetero_param = bool(getattr(cfg, "corridor_profile_d_sigma_hetero", False)) and mode == "parametric"

    floor_abs = max(1e-8, 0.01 * float(sigma_auto))

    h_scale = float(max(getattr(cfg, "corridor_profile_d_sigma_hetero_scale", 1.0) or 0.0, 0.0))

    st_hetero, sr_hetero = _hetero_sigma_masked_from_base(cfg, base_result, scale=h_scale, floor_abs=floor_abs)

    sigma_T_full: np.ndarray | None = None

    sigma_R_full: np.ndarray | None = None

    if hetero_param:
        mobj = _spline_objective_lam_mask(cfg)

        if st_hetero is not None and t0 is not None:
            sigma_T_full = np.full(lam.size, float(sig_t), dtype=np.float64)

            sigma_T_full[mobj] = np.asarray(st_hetero, dtype=np.float64).ravel()

        if sr_hetero is not None and r0 is not None:
            sigma_R_full = np.full(lam.size, float(sig_r), dtype=np.float64)

            sigma_R_full[mobj] = np.asarray(sr_hetero, dtype=np.float64).ravel()

    d_lo_list: list[float] = []

    d_hi_list: list[float] = []

    n_lo_list: list[np.ndarray] = []

    n_hi_list: list[np.ndarray] = []

    k_lo_list: list[np.ndarray] = []

    k_hi_list: list[np.ndarray] = []

    n_ok = 0

    run_b: list[int] = []

    run_ok: list[int] = []

    run_dlo: list[float] = []

    run_dhi: list[float] = []

    run_nvalid: list[int] = []

    log.info(
        "%s [BOOT] start | mode=%s blk=%d | B=%d | p=%.3f (q=[%.4f,%.4f]) | sigma_T=%.6g sigma_R=%.6g | prof_mode=%s | "
        "hetero_sigma(lambda)=%s | quick_refit_maxfun=%d",
        _LOG_PREFIX,
        str(mode),
        int(blk),
        int(B),
        float(p),
        float(q_lo),
        float(q_hi),
        float(sig_t),
        float(sig_r),
        str(getattr(pconf, "mode", "alpha")),
        bool(hetero_param),
        int(qref),
    )

    # Residual mode: needs T_th / R_th and residuals.

    t_th0, r_th0 = (None, None)

    eT0, eR0 = (None, None)

    if mode == "residual":
        t_th0, r_th0 = _theoretical_TR_from_base_result(cfg, base_result)

        if t0 is not None and t_th0 is not None:
            m = np.isfinite(t0) & np.isfinite(t_th0)

            eT0 = (t0[m] - t_th0[m]).astype(np.float64, copy=False)

        if r0 is not None and r_th0 is not None:
            m = np.isfinite(r0) & np.isfinite(r_th0)

            eR0 = (r0[m] - r_th0[m]).astype(np.float64, copy=False)

        if (t0 is not None and (t_th0 is None or eT0 is None or eT0.size < 3)) and (r0 is None):
            return {}

        if (r0 is not None and (r_th0 is None or eR0 is None or eR0.size < 3)) and (t0 is None):
            return {}

    nw = int(n_workers) if n_workers is not None else int(getattr(cfg, "corridor_bootstrap_n_workers", 1) or 1)

    nw = max(1, nw)

    boot_workers_effective = 1

    replicates: list[tuple[int, SplineOptConfig]] = []

    for b in range(B):
        t_b = None

        r_b = None

        if mode == "parametric":
            mobj = _spline_objective_lam_mask(cfg)

            if t0 is not None:
                t_b = t0.copy()

                if hetero_param:
                    idx_t = mobj & np.isfinite(t_b)

                    if np.any(idx_t):
                        stv = (
                            sigma_T_full[idx_t]
                            if sigma_T_full is not None
                            else np.full(int(np.count_nonzero(idx_t)), float(sig_t), dtype=np.float64)
                        )

                        t_b[idx_t] = t_b[idx_t] + rng.normal(0.0, stv, size=int(np.count_nonzero(idx_t)))

                else:
                    m = np.isfinite(t_b)

                    if np.any(m):
                        t_b[m] = t_b[m] + rng.normal(0.0, float(sig_t), size=int(np.count_nonzero(m)))

            if r0 is not None:
                r_b = r0.copy()

                if hetero_param:
                    idx_r = mobj & np.isfinite(r_b)

                    if np.any(idx_r):
                        srv = (
                            sigma_R_full[idx_r]
                            if sigma_R_full is not None
                            else np.full(int(np.count_nonzero(idx_r)), float(sig_r), dtype=np.float64)
                        )

                        r_b[idx_r] = r_b[idx_r] + rng.normal(0.0, srv, size=int(np.count_nonzero(idx_r)))

                else:
                    m = np.isfinite(r_b)

                    if np.any(m):
                        r_b[m] = r_b[m] + rng.normal(0.0, float(sig_r), size=int(np.count_nonzero(m)))

        else:
            if t0 is not None and t_th0 is not None and eT0 is not None:
                t_b = t0.copy()

                m = np.isfinite(t_b) & np.isfinite(t_th0)

                e_star = _resample_residuals_block(eT0, blk, rng)

                t_b[m] = t_th0[m] + e_star[: int(np.count_nonzero(m))]

            if r0 is not None and r_th0 is not None and eR0 is not None:
                r_b = r0.copy()

                m = np.isfinite(r_b) & np.isfinite(r_th0)

                e_star = _resample_residuals_block(eR0, blk, rng)

                r_b[m] = r_th0[m] + e_star[: int(np.count_nonzero(m))]

        cfg_b = cfg.replace(t_exp=t_b, r_exp=r_b)

        replicates.append((int(b), cfg_b))

    batch_out: dict[int, dict[str, Any]] = {}

    use_parallel = nw > 1 and B > 1

    if use_parallel:
        try:
            from concurrent.futures import ProcessPoolExecutor, as_completed

            n_proc = int(min(nw, B))

            with ProcessPoolExecutor(max_workers=n_proc) as ex:
                futs = {
                    ex.submit(
                        _bootstrap_pool_entry,
                        (b, cfg_b, base_result, pconf, qref, lam),
                    ): int(b)
                    for b, cfg_b in replicates
                }

                for fut in as_completed(futs):
                    bi, r = fut.result()

                    batch_out[int(bi)] = r

            boot_workers_effective = n_proc

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s [BOOT] parallel failed - sequential fallback.", _LOG_PREFIX)

            use_parallel = False

            batch_out.clear()

    if not use_parallel or len(batch_out) != B:
        if use_parallel and len(batch_out) != B:
            log.warning("%s [BOOT] incomplete parallel results - sequential fallback.", _LOG_PREFIX)

        batch_out = {}

        for b, cfg_b in replicates:
            batch_out[int(b)] = _bootstrap_single_replicate(
                cfg_b,
                base_result,
                pconf=pconf,
                qref=qref,
                lam=lam,
                log_run_1based=int(b) + 1,
            )

        boot_workers_effective = 1

    for b in range(B):
        r = batch_out[int(b)]

        st = str(r.get("status", "exception"))

        run_b.append(int(b))

        if st == "ok":
            d_lo_list.append(float(r["dlo"]))

            d_hi_list.append(float(r["dhi"]))

            n_lo_list.append(np.asarray(r["n_lo"], dtype=np.float64).ravel())

            n_hi_list.append(np.asarray(r["n_hi"], dtype=np.float64).ravel())

            k_lo_list.append(np.asarray(r["k_lo"], dtype=np.float64).ravel())

            k_hi_list.append(np.asarray(r["k_hi"], dtype=np.float64).ravel())

            n_ok += 1

            run_ok.append(1)

            run_dlo.append(float(r["dlo"]))

            run_dhi.append(float(r["dhi"]))

            run_nvalid.append(int(r.get("nvalid", 0)))

        else:
            run_ok.append(0)

            run_dlo.append(float("nan"))

            run_dhi.append(float("nan"))

            run_nvalid.append(int(r.get("nvalid", 0)))

        if (b + 1) % max(1, B // 10) == 0:
            log.info("%s [BOOT] progress %d/%d | ok=%d", _LOG_PREFIX, int(b + 1), int(B), int(n_ok))

    if n_ok < 3:
        log.warning("%s [BOOT] stop | too few valid runs (%d/%d)", _LOG_PREFIX, int(n_ok), int(B))

        _log_coaching_bootstrap_outcome(
            B=int(B),
            n_ok=int(n_ok),
            p=float(p),
            mode=str(mode),
            qref=int(qref),
            d_lo_q=float("nan"),
            d_hi_q=float("nan"),
        )

        return {}

    d_lo_a = np.asarray(d_lo_list, dtype=np.float64)

    d_hi_a = np.asarray(d_hi_list, dtype=np.float64)

    n_lo_a = np.stack(n_lo_list, axis=0)

    n_hi_a = np.stack(n_hi_list, axis=0)

    k_lo_a = np.stack(k_lo_list, axis=0)

    k_hi_a = np.stack(k_hi_list, axis=0)

    # Percentile bands: aggregate envelopes (lo/hi) from each run.

    # For k, compute quantiles in ln(k) space (better numerical stability), then map back to k.

    boot_n_lo = np.nanquantile(n_lo_a, q_lo, axis=0)

    boot_n_hi = np.nanquantile(n_hi_a, q_hi, axis=0)

    L_lo_a = np.log(np.maximum(k_lo_a, 1e-300))

    L_hi_a = np.log(np.maximum(k_hi_a, 1e-300))

    boot_L_lo = np.nanquantile(L_lo_a, q_lo, axis=0)

    boot_L_hi = np.nanquantile(L_hi_a, q_hi, axis=0)

    boot_k_lo = np.exp(boot_L_lo)

    boot_k_hi = np.exp(boot_L_hi)

    out = {
        "boot_enabled": True,
        "boot_n": int(B),
        "boot_n_ok": int(n_ok),
        "boot_seed": int(seed),
        "boot_percentile": float(p),
        "boot_q_lo": float(q_lo),
        "boot_q_hi": float(q_hi),
        "boot_sigma_t": float(sig_t),
        "boot_sigma_r": float(sig_r),
        "boot_mode": str(mode),
        "boot_block_len": int(blk),
        "boot_runs_b": np.asarray(run_b, dtype=np.int64),
        "boot_runs_ok": np.asarray(run_ok, dtype=np.int64),
        "boot_runs_d_lo_nm": np.asarray(run_dlo, dtype=np.float64),
        "boot_runs_d_hi_nm": np.asarray(run_dhi, dtype=np.float64),
        "boot_runs_n_valid": np.asarray(run_nvalid, dtype=np.int64),
        "boot_d_lo_samples_nm": d_lo_a,
        "boot_d_hi_samples_nm": d_hi_a,
        "boot_d_lo_q_nm": float(np.nanquantile(d_lo_a, q_lo)),
        "boot_d_hi_q_nm": float(np.nanquantile(d_hi_a, q_hi)),
        "boot_corridor_n_lo": np.asarray(boot_n_lo, dtype=np.float64),
        "boot_corridor_n_hi": np.asarray(boot_n_hi, dtype=np.float64),
        "boot_corridor_k_lo": np.asarray(boot_k_lo, dtype=np.float64),
        "boot_corridor_k_hi": np.asarray(boot_k_hi, dtype=np.float64),
        "boot_corridor_L_lo": np.asarray(boot_L_lo, dtype=np.float64),
        "boot_corridor_L_hi": np.asarray(boot_L_hi, dtype=np.float64),
        "boot_quick_refit_maxfun": int(qref),
        "boot_sigma_hetero_parametric": bool(hetero_param),
        "boot_n_workers_effective": int(boot_workers_effective),
    }

    log.info(
        "%s [BOOT] done | ok=%d/%d | d_lo q=%.4f | d_hi q=%.4f",
        _LOG_PREFIX,
        int(n_ok),
        int(B),
        float(out["boot_d_lo_q_nm"]),
        float(out["boot_d_hi_q_nm"]),
    )

    _log_coaching_bootstrap_outcome(
        B=int(B),
        n_ok=int(n_ok),
        p=float(p),
        mode=str(mode),
        qref=int(qref),
        d_lo_q=float(out["boot_d_lo_q_nm"]),
        d_hi_q=float(out["boot_d_hi_q_nm"]),
    )

    return out

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
            except (ValueError, TypeError, RuntimeError):
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
            nk_from_x_pwlnk,
            x_slice_n_to_physical_nodes,
            spectral_mse_rmse_masked_from_nk,
            SplinePWLObjective,
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
        except (TypeError, ValueError, RuntimeError):
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
            except (TypeError, ValueError, RuntimeError):
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
    except (TypeError, ValueError, RuntimeError):
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
            int(len(missing_base_targets)),
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
    cfg: "SplineOptConfig",
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
            "global_opt=%.8f @ d=%.6f nm \u2014 le flux GUI peut fusionner le global (cassure) ; un polish profond "
            "depuis le minimum courbe reste possible.",
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
class RegularGridProfileContext:
    cfg: Any
    sk: Any
    bounds_nodes: Any
    lam_full: Any
    maxfun: int
    maxfun_polish: int
    live_cb: Any
    d_arr: Any
    n_tot: int
    step_ref: float
    d_lo_b: float
    d_hi_b: float
    stop_check: Any
    max_extra_per_event: int
    k: int
    
    abs_best_seen_rmse: float
    d_list: list
    r_list: list
    n_list: list
    k_list: list
    nit_list: list
    nfev_list: list
    point_kind_list: list
    point_status_code_list: list
    x_nodes_best_list: list
    branch_events: list

    def _touch_absolute_best(self, d_nm: float, rmse: float, *, tag: str) -> None:
        import numpy as np
        if not (np.isfinite(rmse) and np.isfinite(float(d_nm))):
            return
        rf = float(rmse)
        df = float(d_nm)
        if rf + 1e-15 >= float(self.abs_best_seen_rmse):
            return
        self.abs_best_seen_rmse = rf
        log.info(
            "%s manual RMSE(d) grid | ABSOLUTE BEST (new record) | d_nm=%s | rmse=%s | tag=%s",
            _LOG_PREFIX, repr(df), repr(rf), str(tag),
        )

    def _emit_live(self, current_d_nm: float, step_progress: float) -> None:
        import numpy as np
        if self.live_cb is None:
            return
        try:
            order_live = np.argsort(np.asarray(self.d_list, dtype=np.float64))
            d_live = np.asarray([self.d_list[i] for i in order_live], dtype=np.float64)
            r_live = np.asarray([self.r_list[i] for i in order_live], dtype=np.float64)
            kind_live = np.asarray([self.point_kind_list[i] for i in order_live], dtype=np.int32)
            st_live = np.asarray([self.point_status_code_list[i] for i in order_live], dtype=np.int32)
            done_base = int(np.sum(kind_live == 0))
            done_extra = int(np.sum(kind_live == 1))

            self.live_cb(
                {
                    "profile_d_values_nm": d_live,
                    "profile_d_rmse_values": r_live,
                    "profile_d_manual_grid_point_kind": kind_live,
                    "profile_d_manual_grid_point_status_code": st_live,
                    "profile_d_manual_grid_current_d_nm": float(current_d_nm),
                    "profile_d_status": "manual_grid_live",
                    "profile_d_manual_grid_progress": float(step_progress),
                    "profile_d_manual_grid_done_points": int(d_live.size),
                    "profile_d_manual_grid_total_points": int(self.d_arr.size),
                    "profile_d_manual_grid_base_done_points": int(done_base),
                    "profile_d_manual_grid_extra_done_points": int(done_extra),
                    "profile_d_manual_grid_breakpoint_events": list(self.branch_events),
                }
            )
        except (TypeError, ValueError, RuntimeError, AttributeError):
            log.debug("%s failed to invoke progress_cb in profile_walk_d (non-critical)", _LOG_PREFIX)

    def _append_fit_record(
        self,
        d_t: float,
        fit: dict,
        *,
        point_kind: int = 0,
        point_status_code: int = 0,
    ) -> bool:
        import numpy as np
        n_lam = np.asarray(fit.get("n_lam", []), dtype=np.float64).ravel()
        k_lam = np.asarray(fit.get("k_lam", []), dtype=np.float64).ravel()
        if n_lam.size != self.lam_full.size or k_lam.size != self.lam_full.size:
            log.warning("%s manual grid: n_lam/k_lam size mismatch at d=%.4f nm (skip point)", _LOG_PREFIX, float(d_t))
            return False

        d_new = float(d_t)
        rm_new = float(fit.get("rmse", float("nan")))
        nit_new = float(fit.get("nit", float("nan")))
        nfev_new = float(fit.get("nfev", float("nan")))
        x_new = np.asarray(fit.get("x_nodes_best", []), dtype=np.float64).ravel().copy()

        i_same = -1
        for i0, d0 in enumerate(self.d_list):
            if np.isclose(float(d0), d_new, rtol=0.0, atol=1e-9):
                i_same = int(i0)
                break

        if i_same >= 0:
            rm_old = float(self.r_list[i_same])
            keep_new = bool(np.isfinite(rm_new) and ((not np.isfinite(rm_old)) or (rm_new < rm_old - 1e-12)))
            if not keep_new:
                _manual_grid_tag_base_on_duplicate_discard(self.point_kind_list, i_same, incoming_point_kind=int(point_kind))
                log.info("%s manual grid: duplicate d=%.6f nm discarded | rmse_old=%.8f <= rmse_new=%.8f", _LOG_PREFIX, d_new, rm_old, rm_new)
                return False

            self.r_list[i_same] = rm_new
            self.n_list[i_same] = n_lam
            self.k_list[i_same] = k_lam
            self.nit_list[i_same] = nit_new
            self.nfev_list[i_same] = nfev_new
            self.point_kind_list[i_same] = int(min(int(self.point_kind_list[i_same]), int(point_kind)))
            self.point_status_code_list[i_same] = int(min(int(self.point_status_code_list[i_same]), int(point_status_code)))
            self.x_nodes_best_list[i_same] = x_new
            log.info("%s manual grid: duplicate d=%.6f nm replaced | rmse_old=%.8f -> rmse_new=%.8f", _LOG_PREFIX, d_new, rm_old, rm_new)
            self._touch_absolute_best(d_new, rm_new, tag="grid_duplicate_improved")
            return True

        self.d_list.append(d_new)
        self.r_list.append(rm_new)
        self.n_list.append(n_lam)
        self.k_list.append(k_lam)
        self.nit_list.append(nit_new)
        self.nfev_list.append(nfev_new)
        self.point_kind_list.append(int(point_kind))
        self.point_status_code_list.append(int(point_status_code))
        self.x_nodes_best_list.append(x_new)
        self._touch_absolute_best(d_new, rm_new, tag="grid_new_point")
        return True

    def _fit_point_with_extra_polish(self, d_nm: float, x_seed_in: np.ndarray) -> dict | None:
        import numpy as np
        fit0 = _fit_nodes_at_fixed_d(
            self.cfg, self.sk, float(d_nm), np.asarray(x_seed_in, dtype=np.float64).ravel().copy(),
            self.bounds_nodes, maxfun=int(self.maxfun), keep_nominal_seed_if_refit_worse=True,
            seed_keep_tol_rel=0.0, seed_keep_tol_abs=1e-5, pure_spectral=True,
        )

        if fit0 is None:
            try:
                x_seed = clip_to_bounds(np.asarray(x_seed_in, dtype=np.float64).ravel().copy(), self.bounds_nodes[:, 0], self.bounds_nodes[:, 1])
                if x_seed.size != 2 * int(self.k): return None
                x_full_seed = np.concatenate((np.asarray([float(d_nm)], dtype=np.float64), x_seed))
                n_lam_seed, k_lam_seed = nk_from_x_pwlnk(
                    x_full_seed, self.lam_full, self.sk, self.cfg.k_clip_lo, self.cfg.k_clip_hi,
                    sig_pre=None, n_mono_band_nm=self.cfg.n_mono_band_nm, profile_interp=str(self.cfg.nk_profile_interp or "smooth"),
                )
                mse_seed, rmse_seed = spectral_mse_rmse_masked_from_nk(
                    self.cfg, {}, self.lam_full, np.asarray(n_lam_seed, dtype=np.float64).ravel(),
                    np.asarray(k_lam_seed, dtype=np.float64).ravel(), float(d_nm),
                )
                rmse_seed_f = float(rmse_seed)
                mse_seed_f = float(mse_seed) if np.isfinite(float(mse_seed)) else float("nan")
                if not np.isfinite(rmse_seed_f):
                    from certus.spline.spline_objective import SplinePWLObjective
                    obj_seed = SplinePWLObjective(self.cfg, self.sk)
                    m_obj_seed = float(obj_seed(x_full_seed))
                    if np.isfinite(m_obj_seed) and m_obj_seed < 1e29:
                        rmse_seed_f = float(np.sqrt(max(m_obj_seed, 0.0)))
                        if not np.isfinite(mse_seed_f): mse_seed_f = float(m_obj_seed)
                    else: return None
                n_slice_seed = x_seed[:self.k]
                n_nodes_phys_seed = (np.asarray(n_slice_seed, dtype=np.float64).copy() if self.cfg.n_mono_band_nm is None else x_slice_n_to_physical_nodes(n_slice_seed, self.sk, self.cfg.n_mono_band_nm))
                L_nodes_seed = np.asarray(x_seed[self.k:], dtype=np.float64).copy()
                return {
                    "success": False, "message": "fallback_seed_eval_after_refit_failure", "nit": 0, "nfev": 0,
                    "d_nm": float(d_nm), "rmse": rmse_seed_f, "mse": float(mse_seed_f) if np.isfinite(float(mse_seed_f)) else float("nan"),
                    "x_nodes_best": x_seed.copy(), "n_nodes_physical": n_nodes_phys_seed, "L_nodes": L_nodes_seed,
                    "n_lam": np.asarray(n_lam_seed, dtype=np.float64).ravel().copy(), "k_lam": np.asarray(k_lam_seed, dtype=np.float64).ravel().copy(),
                    "fallback_from_seed": True, "fallback_from_objective": bool(not np.isfinite(float(rmse_seed))),
                }
            except Exception:
                return None

        x_mid = np.asarray(fit0.get("x_nodes_best", x_seed_in), dtype=np.float64).ravel().copy()
        fit1 = _fit_nodes_at_fixed_d(
            self.cfg, self.sk, float(d_nm), x_mid, self.bounds_nodes, maxfun=int(self.maxfun_polish),
            keep_nominal_seed_if_refit_worse=True, seed_keep_tol_rel=0.0, seed_keep_tol_abs=1e-5, pure_spectral=True,
        )

        if fit1 is None: return fit0
        rm0 = float(fit0.get("rmse", float("nan")))
        rm1 = float(fit1.get("rmse", float("nan")))
        if np.isfinite(rm1) and (not np.isfinite(rm0) or rm1 <= rm0):
            fit1["nfev"] = int((fit0.get("nfev", 0)) + (fit1.get("nfev", 0)))
            fit1["nit"] = int((fit0.get("nit", 0)) + (fit1.get("nit", 0)))
            return fit1
        return fit0

    def _choose_branch_direction_sign(
        self, *, d_break: float, x_seed_start: np.ndarray, side_origin: int, rmse_break: float,
    ) -> int:
        import numpy as np
        d_step = float(max(0.5 * float(self.step_ref), 1e-4))
        probes = []
        for sgn in (+1, -1):
            d_try = float(d_break + float(sgn) * d_step)
            if not (self.d_lo_b - 1e-12 <= d_try <= self.d_hi_b + 1e-12): continue
            fit_p = self._fit_point_with_extra_polish(float(d_try), np.asarray(x_seed_start, dtype=np.float64).ravel().copy())
            if fit_p is None: continue
            rm_p = float(fit_p.get("rmse", float("nan")))
            if not np.isfinite(rm_p): continue
            probes.append((int(sgn), float(rm_p), fit_p))
        if not probes: return 0
        probes.sort(key=lambda t: t[1])
        best_sign, best_rmse, _ = probes[0]
        if np.isfinite(rmse_break) and (best_rmse <= float(rmse_break) - 1e-12): return int(best_sign)
        return int(-1 if side_origin > 0 else +1)

    def _branch_reverse_from_breakpoint(
        self, *, d_break: float, x_seed_start: np.ndarray, side_origin: int, branch_sign: int, primary_step_idx: int,
    ) -> tuple[int, np.ndarray]:
        import numpy as np
        extra_ok = 0
        reverse_sign = int(np.sign(branch_sign))
        if reverse_sign == 0:
            return 0, np.asarray(x_seed_start, dtype=np.float64).ravel().copy()

        d_step = float(max(0.5 * float(self.step_ref), 1e-4))
        for j in range(1, int(self.max_extra_per_event) + 1):
            if self.stop_check is not None and bool(self.stop_check()): break
            d_try = float(d_break + reverse_sign * d_step * float(j))
            if not (self.d_lo_b - 1e-12 <= d_try <= self.d_hi_b + 1e-12): break
            fit_b = self._fit_point_with_extra_polish(float(d_try), x_seed_start)
            if fit_b is None: continue
            st_code_b = 0
            if bool(fit_b.get("fallback_from_objective", False)): st_code_b = 2
            elif bool(fit_b.get("fallback_from_seed", False)): st_code_b = 1
            if not self._append_fit_record(d_try, fit_b, point_kind=1, point_status_code=int(st_code_b)): continue
            extra_ok += 1
            x_seed_start = np.asarray(fit_b.get("x_nodes_best", x_seed_start), dtype=np.float64).ravel().copy()
            self._emit_live(float(d_try), float(primary_step_idx + 1) / float(max(1, self.n_tot)))
        return int(extra_ok), np.asarray(x_seed_start, dtype=np.float64).ravel().copy()

def compute_regular_grid_rmse_profile(
    cfg: SplineOptConfig,
    base_result: dict,
    d_targets_nm: np.ndarray,
    *,
    profile_polish_maxfun: int | None = None,
    breakpoint_lookback_points: int = 5,
    visit_anchor_nm: float | None = None,
    progress_cb: Any | None = None,
    stop_check: Any | None = None,
    live_cb: Any | None = None,
) -> dict[str, Any]:
    """Recompute RMSE(d) on an imposed thickness grid (refit n,L at fixed d).

    Same convention as corridor profiling ("scientific nominal" base if available,

    otherwise ``base_result`` as-is). Returns ``profile_d_*`` keys to merge into the GUI result dict.

    """

    from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference

    t0 = time.perf_counter()

    nom_pack = extract_nominal_best_polished_corridor_reference(base_result)

    base_eff: dict[str, Any]

    if nom_pack is not None:
        skn = np.asarray(nom_pack["sigma_knots"], dtype=np.float64).ravel()

        xsg = nom_pack.get("x_seg_spline_sigma")

        base_eff = dict(base_result)

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

    else:
        base_eff = dict(base_result)

    sk, _n_phys0, _L0, d0, _ = _extract_knots_and_nodes_from_result(base_eff)

    k = int(sk.size)

    x_nodes0 = _x_nodes0_from_mesh_x_if_consistent(base_eff, sk=sk, d0_nm=float(d0))

    if x_nodes0 is None:
        if cfg.n_mono_band_nm is None:
            n_slice0 = np.asarray(_n_phys0, dtype=np.float64).copy()

        else:
            from certus.spline.spline_objective import physical_nodes_to_x_slice_n

            n_slice0 = physical_nodes_to_x_slice_n(_n_phys0, sk, cfg.n_mono_band_nm)

        x_nodes0 = np.concatenate((n_slice0, np.asarray(_L0, dtype=np.float64).copy()))

    # P1.3 FIX: Pass k_hard_lower_bound to enforce physical k >= 0 constraint
    bounds_nodes, _ = _bounds_for_nodes_only(cfg, k, k_hard_lower_bound=0.0)

    x_nodes0 = clip_to_bounds(np.asarray(x_nodes0, dtype=np.float64).ravel(), bounds_nodes[:, 0], bounds_nodes[:, 1])

    raw = np.asarray(d_targets_nm, dtype=np.float64).ravel()

    raw = raw[np.isfinite(raw)]

    if raw.size == 0:
        return {"profile_d_status": "manual_grid_empty", "profile_d_manual_grid_note": "no finite d targets"}

    d_unique: list[float] = []

    for v in sorted(set(float(x) for x in raw.tolist())):
        if not d_unique or abs(v - d_unique[-1]) > 1e-9:
            d_unique.append(v)

    d_arr = np.asarray(d_unique, dtype=np.float64)

    if d_arr.size == 0:
        return {"profile_d_status": "manual_grid_empty", "profile_d_manual_grid_note": "empty after dedup"}

    # Sweep center: requested grid (visit_anchor_nm or target median), not the nominal pack d.
    # Otherwise the "first/last" order remains anchored on the old thickness after GUI recentering.
    if visit_anchor_nm is not None and np.isfinite(float(visit_anchor_nm)):
        d_visit_anchor = float(visit_anchor_nm)

    else:
        d_visit_anchor = float(np.median(d_arr)) if d_arr.size else float(d0)

    i_center = int(np.argmin(np.abs(d_arr - float(d_visit_anchor))))

    visit_indices: list[int] = [i_center]

    for ofs in range(1, int(d_arr.size)):
        i_r = i_center + ofs

        if i_r < int(d_arr.size):
            visit_indices.append(int(i_r))

        i_l = i_center - ofs

        if i_l >= 0:
            visit_indices.append(int(i_l))

    if visit_indices:
        order_dbg = np.asarray([float(d_arr[i]) for i in visit_indices], dtype=np.float64)
        log.info(
            "%s manual RMSE(d) grid strategy | visit_start_d=%.6f nm (anchor=%.6f) | nominal_pack_d=%.6f nm | "
            "visit_order=%d pts | first=%s | last=%s",
            _LOG_PREFIX,
            float(d_arr[i_center]),
            float(d_visit_anchor),
            float(d0),
            int(order_dbg.size),
            (", ".join(f"{v:.4f}" for v in order_dbg[: min(5, int(order_dbg.size))]) if order_dbg.size > 0 else "-"),
            (
                ", ".join(f"{v:.4f}" for v in order_dbg[max(0, int(order_dbg.size) - 5) :])
                if order_dbg.size > 0
                else "-"
            ),
        )

    maxfun_base = int(corridor_profile_refit_maxfun(cfg, profile_polish_maxfun))

    # User request: push per-point refit/polish further for RMSE(d) grid.
    maxfun = int(max(maxfun_base, round(1.8 * float(maxfun_base))))

    maxfun_polish = int(max(maxfun + 1, round(1.35 * float(maxfun))))

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

    d_list: list[float] = []

    r_list: list[float] = []

    n_list: list[np.ndarray] = []

    k_list: list[np.ndarray] = []

    nit_list: list[float] = []

    nfev_list: list[float] = []

    point_kind_list: list[int] = []
    # 0=fit, 1=fallback_seed, 2=fallback_objective, 3=fallback_emergency
    point_status_code_list: list[int] = []
    # x_nodes_best per point — used by P0 re-pass to identify the global-best seed.
    x_nodes_best_list: list[np.ndarray] = []

    x_seed_center = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    x_seed_right = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    x_seed_left = np.asarray(x_nodes0, dtype=np.float64).ravel().copy()

    n_tot = int(len(visit_indices))

    step_ref = float(np.nanmedian(np.abs(np.diff(d_arr)))) if d_arr.size >= 2 else 1.0

    step_ref = float(max(step_ref, 1e-4))

    side_last_rmse: dict[int, float] = {+1: float("nan"), -1: float("nan")}


    side_recent_rmse: dict[int, list[float]] = {+1: [], -1: []}

    side_recent_d: dict[int, list[float]] = {+1: [], -1: []}

    side_last_break_index: dict[int, int] = {+1: -10_000_000, -1: -10_000_000}

    branch_events: list[dict[str, float]] = []

    global_opt_events: list[dict[str, float]] = []

    n_branch_trigger = 0

    n_branch_extra_points = 0

    n_global_opt_runs = 0

    n_global_opt_improved = 0

    max_branch_events = 6

    max_extra_per_event = 30

    d_lo_grid = float(np.min(d_arr))

    d_hi_grid = float(np.max(d_arr))

    # Important: do NOT constrain manual grid exploration by the initial stage-2 d bounds.
    # We keep a local envelope around the user-requested RMSE(d) grid and allow reverse extras.
    d_lo_b = float(d_lo_grid - float(max_extra_per_event) * 0.5 * float(step_ref))

    d_hi_b = float(d_hi_grid + float(max_extra_per_event) * 0.5 * float(step_ref))

    rmse_abs_candidates = [
        float(base_result.get("rmse", float("nan"))),
        float(base_result.get("spectral_rmse_best_value", float("nan"))),
        float(base_result.get("spectral_rmse_segments", float("nan"))),
        float(base_eff.get("rmse", float("nan"))),
        float(base_eff.get("spectral_rmse_best_value", float("nan"))),
        float(base_eff.get("spectral_rmse_segments", float("nan"))),
    ]
    rmse_abs_ref = float(min([v for v in rmse_abs_candidates if np.isfinite(v)], default=float("nan")))
    # Baseline nominal RMSE (before any global-opt update) to compare against the discrete grid minimum.
    rmse_nominal_baseline_for_grid = float(rmse_abs_ref)
    best_global_result: dict[str, Any] | None = None
    best_global_rmse = float("nan")

    abs_best_seen_rmse = float("inf")


    lookback_points = int(max(2, breakpoint_lookback_points))
    min_gain_abs_prevn = 2e-6
    min_gain_rel_prevn = 5e-4
    min_gain_abs_parab = 2e-6
    min_breakpoint_spacing_points = max(6, int(lookback_points))

    log.info(
        "%s manual RMSE(d) grid budgets | base_maxfun=%d | point_maxfun=%d | polish_maxfun=%d | break_lookback=%d | explore_bounds=[%.6f, %.6f] nm",
        _LOG_PREFIX,
        int(maxfun_base),
        int(maxfun),
        int(maxfun_polish),
        int(lookback_points),
        float(d_lo_b),
        float(d_hi_b),
    )

    ctx = RegularGridProfileContext(
        cfg=cfg, sk=sk, bounds_nodes=bounds_nodes, lam_full=lam_full,
        maxfun=maxfun, maxfun_polish=maxfun_polish, live_cb=live_cb,
        d_arr=d_arr, n_tot=n_tot, step_ref=step_ref, d_lo_b=d_lo_b, d_hi_b=d_hi_b,
        stop_check=stop_check, max_extra_per_event=max_extra_per_event, k=k,
        abs_best_seen_rmse=abs_best_seen_rmse,
        d_list=d_list, r_list=r_list, n_list=n_list, k_list=k_list,
        nit_list=nit_list, nfev_list=nfev_list,
        point_kind_list=point_kind_list, point_status_code_list=point_status_code_list,
        x_nodes_best_list=x_nodes_best_list, branch_events=branch_events
    )

    for step_i, ji in enumerate(visit_indices):
        if stop_check is not None and bool(stop_check()):
            log.info("%s manual grid: stop requested after %d/%d points", _LOG_PREFIX, step_i, n_tot)

            break

        d_t = float(d_arr[int(ji)])

        if progress_cb is not None:
            try:
                progress_cb(float(step_i) / float(max(1, n_tot)), f"RMSE grid: d={d_t:.4f} nm ({step_i + 1}/{n_tot})")

            except (TypeError, ValueError, RuntimeError, AttributeError):
                log.debug("%s failed to invoke progress_cb in _execute_manual_grid (non-critical)", _LOG_PREFIX)

        if int(ji) == i_center:
            x_seed_in = x_seed_center

            side = 0

        elif int(ji) > i_center:
            x_seed_in = x_seed_right

            side = +1

        else:
            x_seed_in = x_seed_left

            side = -1

        fit = ctx._fit_point_with_extra_polish(float(d_t), x_seed_in)

        if fit is None:
            log.info("%s manual grid: refit failed at d=%.6f nm", _LOG_PREFIX, d_t)

            continue

        point_status_code = 0
        if bool(fit.get("fallback_from_objective", False)):
            point_status_code = 2
        elif bool(fit.get("fallback_from_seed", False)):
            point_status_code = 1
        if not ctx._append_fit_record(
            d_t,
            fit,
            point_kind=0,
            point_status_code=int(point_status_code),
        ):
            continue

        x_seed_new = np.asarray(fit.get("x_nodes_best", x_seed_in), dtype=np.float64).ravel().copy()

        if int(ji) == i_center:
            x_seed_center = x_seed_new

            x_seed_right = x_seed_new.copy()

            x_seed_left = x_seed_new.copy()

        elif int(ji) > i_center:
            x_seed_right = x_seed_new

        else:
            x_seed_left = x_seed_new

        ctx._emit_live(float(d_t), float(step_i + 1) / float(max(1, n_tot)))

        if side != 0:
            rm_now = float(fit.get("rmse", float("nan")))

            (
                is_break,
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
            ) = _detect_breakpoint(
                side,
                float(d_t),
                rm_now,
                side_last_rmse,
                side_recent_rmse,
                side_recent_d,
                lookback_points,
                float(min_gain_abs_prevn),
                float(min_gain_rel_prevn),
                float(min_gain_abs_parab),
            )

            if bool(is_break):
                if int(abs(int(ji) - int(side_last_break_index.get(side, -10_000_000)))) < int(
                    min_breakpoint_spacing_points
                ):
                    is_break = False

            side_last_rmse[side] = rm_now


            side_recent_rmse.setdefault(side, []).append(float(rm_now))

            side_recent_d.setdefault(side, []).append(float(d_t))

            if np.isfinite(gain_abs) and np.isfinite(gain_rel):
                should_trace = bool(is_break or step_i <= 10 or step_i % 10 == 0 or gain_abs > 0.0)

                if should_trace:
                    log.info(
                        "%s manual grid break-check | side=%s | d=%.6f nm | rmse_now=%.8f | gain_abs=%+.6e vs thr_abs=%.6e | gain_rel=%+.3f%% vs thr_rel=%.3f%% | best_prevN=%.8f (N=%d) | gain_vs_prevN=%+.6e | parab_pred=%.8f | gain_vs_parab=%+.6e vs thr_parab=%.6e | trigger_prevN=%s | trigger_parab=%s | trigger=%s",
                        _LOG_PREFIX,
                        ("right" if side > 0 else "left"),
                        float(d_t),
                        float(rm_now),
                        float(gain_abs),
                        float(abs_thr),
                        100.0 * float(gain_rel),
                        100.0 * float(rel_thr),
                        float(best_prev5) if np.isfinite(best_prev5) else float("nan"),
                        int(lookback_points),
                        float(gain_vs_prev5) if np.isfinite(gain_vs_prev5) else float("nan"),
                        float(parab_pred) if np.isfinite(parab_pred) else float("nan"),
                        float(parab_gain) if np.isfinite(parab_gain) else float("nan"),
                        float(parab_thr) if np.isfinite(parab_thr) else float("nan"),
                        ("yes" if trigger_prev5 else "no"),
                        ("yes" if trigger_parabola else "no"),
                        ("yes" if is_break else "no"),
                    )

            if is_break and n_branch_trigger < int(max_branch_events):
                n_branch_trigger += 1
                side_last_break_index[side] = int(ji)

                log.info(
                    "%s manual grid breakpoint detected | side=%s | d=%.6f nm | DeltaRMSE=%+.6e (%.2f%%) -> reverse exploration",
                    _LOG_PREFIX,
                    ("right" if side > 0 else "left"),
                    float(d_t),
                    float(gain_abs),
                    100.0 * float(gain_rel),
                )

                n_global_opt_runs += 1
                maxfun_global = int(max(300, maxfun_polish, maxfun, maxfun_base))
                cand_global = _run_global_opt_from_breakpoint(
                    d_break=float(d_t),
                    fit_break=fit,
                    side_origin=int(side),
                    k=k,
                    base_eff=base_eff,
                    sk=sk,
                    cfg=cfg,
                    maxfun_global=maxfun_global,
                )
                rmse_global = (
                    float(cand_global.get("rmse", float("nan"))) if isinstance(cand_global, dict) else float("nan")
                )
                d_global_eval = float(d_t)
                if isinstance(cand_global, dict):
                    dg_ev = cand_global.get("d_nm")
                    if isinstance(dg_ev, (int, float)) and np.isfinite(float(dg_ev)):
                        d_global_eval = float(dg_ev)
                if np.isfinite(rmse_global):
                    ctx._touch_absolute_best(d_global_eval, float(rmse_global), tag="global_opt_eval")
                beat_abs = bool(
                    np.isfinite(rmse_global)
                    and (
                        (
                            not np.isfinite(rmse_abs_ref)
                            and (not np.isfinite(best_global_rmse) or rmse_global < best_global_rmse)
                        )
                        or (np.isfinite(rmse_abs_ref) and rmse_global + 1e-12 < rmse_abs_ref)
                        or (np.isfinite(best_global_rmse) and rmse_global + 1e-12 < best_global_rmse)
                    )
                )
                if beat_abs and isinstance(cand_global, dict):
                    n_global_opt_improved += 1
                    best_global_rmse = float(rmse_global)
                    best_global_result = dict(cand_global)
                    if np.isfinite(rmse_abs_ref):
                        rmse_abs_ref = float(min(rmse_abs_ref, rmse_global))
                    else:
                        rmse_abs_ref = float(rmse_global)
                global_opt_events.append(
                    {
                        "d_break_nm": float(d_t),
                        "side": float(side),
                        "rmse_global": float(rmse_global),
                        "beat_absolute_best": float(1.0 if beat_abs else 0.0),
                    }
                )
                if np.isfinite(rmse_global):
                    log.info(
                        "%s manual grid breakpoint global-opt | d_break=%.6f nm | side_origin=%s | rmse_global=%.8f | rmse_abs_ref=%.8f | beat_abs=%s",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                        float(rmse_global),
                        float(rmse_abs_ref) if np.isfinite(rmse_abs_ref) else float("nan"),
                        ("yes" if beat_abs else "no"),
                    )
                else:
                    log.info(
                        "%s manual grid breakpoint global-opt | d_break=%.6f nm | side_origin=%s | rmse_global=n/a | beat_abs=no",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                    )

                branch_sign = ctx._choose_branch_direction_sign(
                    d_break=float(d_t),
                    x_seed_start=x_seed_new.copy(),
                    side_origin=int(side),
                    rmse_break=float(rm_now),
                )
                if int(branch_sign) == 0:
                    log.info(
                        "%s manual grid breakpoint branch-sense | d_break=%.6f nm | side_origin=%s | no viable direction",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                    )
                    n_extra, x_seed_rev_end = 0, x_seed_new.copy()
                else:
                    log.info(
                        "%s manual grid breakpoint branch-sense | d_break=%.6f nm | side_origin=%s | chosen=%s",
                        _LOG_PREFIX,
                        float(d_t),
                        ("right" if side > 0 else "left"),
                        ("right" if int(branch_sign) > 0 else "left"),
                    )
                    n_extra, x_seed_rev_end = ctx._branch_reverse_from_breakpoint(
                        d_break=float(d_t),
                        x_seed_start=x_seed_new.copy(),
                        side_origin=int(side),
                        branch_sign=int(branch_sign),
                        primary_step_idx=int(step_i),
                    )

                n_branch_extra_points += int(n_extra)
                if np.asarray(x_seed_rev_end, dtype=np.float64).size == np.asarray(x_seed_new, dtype=np.float64).size:
                    if side > 0:
                        x_seed_left = np.asarray(x_seed_rev_end, dtype=np.float64).ravel().copy()
                    else:
                        x_seed_right = np.asarray(x_seed_rev_end, dtype=np.float64).ravel().copy()

                log.info(
                    "%s manual grid reverse-explore done | d_break=%.6f nm | side_origin=%s | n_extra=%d | opposite_seed_updated=%s",
                    _LOG_PREFIX,
                    float(d_t),
                    ("right" if side > 0 else "left"),
                    int(n_extra),
                    ("yes" if int(n_extra) > 0 else "no"),
                )

                branch_events.append(
                    {
                        "d_break_nm": float(d_t),
                        "gain_abs_rmse": float(gain_abs),
                        "gain_rel_frac": float(gain_rel),
                        "side": float(side),
                        "n_extra_points": float(n_extra),
                        "trigger_prevN": float(1.0 if bool(trigger_prev5) else 0.0),
                        "trigger_parabola": float(1.0 if bool(trigger_parabola) else 0.0),
                        "branch_dir_sign": float(branch_sign) if "branch_sign" in locals() else float("nan"),
                    }
                )
            elif is_break:
                log.info(
                    "%s manual grid breakpoint skipped | side=%s | d=%.6f nm | reason=max_branch_events reached (%d/%d)",
                    _LOG_PREFIX,
                    ("right" if side > 0 else "left"),
                    float(d_t),
                    int(n_branch_trigger),
                    int(max_branch_events),
                )

    # -- P0 re-pass: rescue points trapped in a local (n,k) minimum ----------
    # Problem: chained warm-start (each point seeded from its neighbor)
    # can propagate a bad local minimum across an entire exploration arm.
    # Solution: after the main loop, re-fit each "suspect" point once
    # using the seed from the global optimum.
    _profile_p0_suspects(
        d_list,
        r_list,
        x_nodes_best_list,
        n_list,
        k_list,
        nfev_list,
        k,
        lam_full,
        stop_check,
        ctx._fit_point_with_extra_polish,
        ctx._touch_absolute_best,
    )
    # ─────────────────────────────────────────────────────────────────────────────

    coverage_complete = _profile_manual_grid_coverage_audit(
        d_arr,
        d_list,
        point_kind_list,
        x_seed_center,
        x_nodes0,
        bounds_nodes,
        lam_full,
        sk,
        cfg,
        base_eff,
        r_list,
        rmse_abs_ref,
        k,
        _build_emergency_fit_record,
        ctx._append_fit_record,
        ctx._emit_live,
    )

    return _package_profile_grid_result(
        d_list=d_list,
        r_list=r_list,
        n_list=n_list,
        k_list=k_list,
        nit_list=nit_list,
        nfev_list=nfev_list,
        point_kind_list=point_kind_list,
        point_status_code_list=point_status_code_list,
        x_nodes_best_list=x_nodes_best_list,
        t0=t0,
        d_arr=d_arr,
        d0=d0,
        i_center=i_center,
        nom_pack_present=bool(nom_pack is not None),
        n_branch_trigger=n_branch_trigger,
        n_branch_extra_points=n_branch_extra_points,
        n_global_opt_runs=n_global_opt_runs,
        n_global_opt_improved=n_global_opt_improved,
        branch_events=branch_events,
        global_opt_events=global_opt_events,
        best_global_rmse=best_global_rmse,
        best_global_result=best_global_result,
        rmse_nominal_baseline_for_grid=rmse_nominal_baseline_for_grid,
        rmse_abs_ref=rmse_abs_ref,
        sk=sk,
        cfg=cfg,
        base_eff=base_eff,
        k=k,
        coverage_complete=coverage_complete,
    )




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


def _package_corridor_results(ctx: CorridorProfileContext) -> dict[str, Any]:
    # Envelopes (corridors): min/max over all valid curves (linear n and linear k).

    # UI log₁₀(k): center refit lies in [k_lo, k_hi] in k but need not bisect [log10(k_lo), log10(k_hi)].

    n_stack = np.vstack([c.reshape(1, -1) for c in ctx.n_curves])

    k_stack = np.vstack([c.reshape(1, -1) for c in ctx.k_curves])

    n_lo = np.nanmin(n_stack, axis=0)

    n_hi = np.nanmax(n_stack, axis=0)

    k_lo = np.nanmin(k_stack, axis=0)

    k_hi = np.nanmax(k_stack, axis=0)

    # P2.2 FIX: Detect n/k crossing (non-physical: n < k in any part of spectrum)
    # This indicates the corridor is allowing non-physical dispersion relations
    if n_stack.ndim == 2 and k_stack.ndim == 2 and n_stack.shape == k_stack.shape:
        _n_cross = np.nanmin(n_stack, axis=0)  # min n per lambda
        _k_cross = np.nanmax(k_stack, axis=0)  # max k per lambda
        _crossing_mask = _n_cross < _k_cross  # non-physical: n < k
        if np.any(_crossing_mask):
            _n_bad = int(np.sum(_crossing_mask))
            _frac_bad = float(np.mean(_crossing_mask))
            log.warning(
                "%s n/k CROSSING DETECTED: n < k at %d wavelengths (%.1f%%). "
                "This is non-physical for passive dielectrics. "
                "The corridor tolerance may be too permissive. "
                "Consider tightening rmse_alpha (mode='alpha') or reducing rmse_abs_tolerance.",
                _LOG_PREFIX,
                _n_bad,
                100.0 * _frac_bad,
            )

    if ctx.scientific_nominal and ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None:
        # Crucial Physical Coherence: The base nominal Polish *is* the anchor of the corridor.

        # If the local searches shifted, this anchor MUST remain within its own bounded envelope.

        n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
            n_lo, n_hi, k_lo, k_hi, ctx.corridor_ref_n_lam, ctx.corridor_ref_k_lam
        )

        log.debug(
            "%s Scientific Nominal: Base reference natively injected into min/max bounds to ensure 100%% consistency.",
            _LOG_PREFIX,
        )

    elif not ctx.scientific_nominal:
        n_nom_r = np.asarray(ctx.base_result.get("n_lam"), dtype=np.float64).ravel()

        k_nom_r = np.asarray(ctx.base_result.get("k_lam"), dtype=np.float64).ravel()

        if int(n_nom_r.size) >= int(n_lo.size) and int(k_nom_r.size) >= int(k_lo.size):
            n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
                n_lo, n_hi, k_lo, k_hi, n_nom_r, k_nom_r
            )

            log.debug(
                "%s Envelope widened to include reported n_lam/k_lam (bold UI curve inside lo/hi).",
                _LOG_PREFIX,
            )

    # Legacy: align corridor_reference_* on stack[0]. Scientific: reference = nominal best (already fixed).

    if (
        (not ctx.scientific_nominal)
        and ctx.corridor_ref_n_lam is not None
        and ctx.corridor_ref_k_lam is not None
        and int(n_stack.shape[0]) > 0
    ):
        ctx.corridor_ref_n_lam = np.asarray(n_stack[0], dtype=np.float64).ravel().copy()

        ctx.corridor_ref_k_lam = np.asarray(k_stack[0], dtype=np.float64).ravel().copy()

    if ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None and int(n_stack.shape[0]) > 0:
        m_chk = np.isfinite(k_lo) & np.isfinite(k_hi) & np.isfinite(ctx.corridor_ref_k_lam) & (ctx.corridor_ref_k_lam > 0.0)

        if np.any(m_chk):
            k_r = ctx.corridor_ref_k_lam[m_chk]

            lo_m = k_lo[m_chk]

            hi_m = k_hi[m_chk]

            bad_m = (k_r < lo_m - 1e-12) | (k_r > hi_m + 1e-12)

            if bool(np.any(bad_m)):
                idx_sub = int(np.where(bad_m)[0][0])

                idx_full = int(np.flatnonzero(m_chk)[idx_sub])

                log.warning(
                    "%s k corridor health: k_ref outside [k_lo,k_hi] at lambda[%d] (min/max inconsistency) - "
                    "k_ref=%.6e k_lo=%.6e k_hi=%.6e",
                    _LOG_PREFIX,
                    idx_full,
                    float(ctx.corridor_ref_k_lam[idx_full]),
                    float(k_lo[idx_full]),
                    float(k_hi[idx_full]),
                )

    d_arr = np.asarray(ctx.d_vals, dtype=np.float64)

    rm_arr = np.asarray(ctx.rmse_vals, dtype=np.float64)

    c_arr = np.asarray(ctx.chi2_vals, dtype=np.float64)

    n_stack = np.asarray(n_stack, dtype=np.float64)

    k_stack = np.asarray(k_stack, dtype=np.float64)

    order = np.argsort(d_arr)

    d_arr = d_arr[order]

    rm_arr = rm_arr[order]

    c_arr = c_arr[order] if c_arr.size == d_arr.size else np.full(d_arr.shape, np.nan, dtype=np.float64)

    if n_stack.ndim == 2 and n_stack.shape[0] == order.size:
        n_stack = n_stack[order, :]

    if k_stack.ndim == 2 and k_stack.shape[0] == order.size:
        k_stack = k_stack[order, :]

    d_interval_raw = (float(np.min(d_arr)), float(np.max(d_arr)))
    i_best_rm = int(np.argmin(rm_arr)) if rm_arr.size else -1
    parab_half_window_pts = int(max(1, int(getattr(ctx.pconf, "parabola_half_window_pts", 3) or 3)))
    parab_fit = _fit_local_quadratic_rmse_profile(
        d_arr,
        rm_arr,
        i_best_rm,
        parab_half_window_pts,
        0.0,
    )
    parab_center_nm = (
        float(parab_fit.get("d_center", float("nan"))) if bool(parab_fit.get("ok", False)) else float("nan")
    )
    center_mode = str(getattr(ctx.pconf, "symmetric_interval_center_mode", "parabola") or "parabola").strip().lower()
    if bool(getattr(ctx.pconf, "force_symmetric_interval", True)):
        if center_mode == "parabola" and np.isfinite(parab_center_nm):
            d_center_sym = float(parab_center_nm)
            center_source = "parabola"
        else:
            d_center_sym = float(ctx.d0)
            center_source = "nominal"
    else:
        d_center_sym = float(parab_center_nm) if np.isfinite(parab_center_nm) else float(ctx.d0)
        center_source = "parabola" if np.isfinite(parab_center_nm) else "sampled_best"
    if not np.isfinite(d_center_sym):
        d_center_sym = float(ctx.d0)
        center_source = "nominal"
    if bool(parab_fit.get("ok", False)):
        log.info(
            "%s Local quadratic RMSE(d) center | center=%.6f nm | anchor=%.6f nm | curvature=%.6e | slope@anchor=%+.6e | window=[%.6f, %.6f] nm",
            _LOG_PREFIX,
            float(d_center_sym),
            float(parab_fit.get("anchor_nm", float("nan"))),
            float(parab_fit.get("curvature", float("nan"))),
            float(parab_fit.get("slope_at_anchor", float("nan"))),
            float(parab_fit.get("window_nm", (float("nan"), float("nan")))[0]),
            float(parab_fit.get("window_nm", (float("nan"), float("nan")))[1]),
        )
    side_neg = d_center_sym - d_arr[d_arr <= d_center_sym + 1e-12]
    side_pos = d_arr[d_arr >= d_center_sym - 1e-12] - d_center_sym
    half_neg = float(np.max(side_neg)) if side_neg.size else 0.0
    half_pos = float(np.max(side_pos)) if side_pos.size else 0.0
    half_sym = float(max(0.0, min(half_neg, half_pos)))
    min_half_sym = float(
        max(0.0, float(getattr(ctx.pconf, "symmetric_interval_min_half_width_rel", 0.002) or 0.0))
    ) * max(abs(float(ctx.d0)), 1e-12)
    half_bounds = float(
        max(0.0, min(float(d_center_sym - float(ctx.cfg.d_lo)), float(ctx.cfg.d_hi - float(d_center_sym))))
    )
    if half_bounds > 0.0:
        half_sym = float(min(max(half_sym, min_half_sym), half_bounds))
    else:
        half_sym = 0.0
    if half_sym + 1e-12 < min_half_sym:
        log.warning(
            "%s Symmetric minimum half-width clipped by d-bounds | requested=%.6f nm | available=%.6f nm | center=%.6f nm | bounds=[%.6f, %.6f] nm",
            _LOG_PREFIX,
            float(min_half_sym),
            float(half_bounds),
            float(d_center_sym),
            float(ctx.cfg.d_lo),
            float(ctx.cfg.d_hi),
        )
    elif min_half_sym > 0.0 and half_sym <= min_half_sym + 1e-12:
        log.info(
            "%s Symmetric minimum half-width enforced | center=%.6f nm | half_width=%.6f nm (%.4f%% of d_opt)",
            _LOG_PREFIX,
            float(d_center_sym),
            float(half_sym),
            100.0 * float(half_sym) / max(abs(float(ctx.d0)), 1e-12),
        )
    if bool(getattr(ctx.pconf, "force_symmetric_interval", False)):
        d_sym_lo = float(d_center_sym - half_sym)
        d_sym_hi = float(d_center_sym + half_sym)
    else:
        # Enforce minimum half-width even in asymmetric mode
        d_sym_lo = min(float(d_center_sym - half_neg), float(d_center_sym - min_half_sym))
        d_sym_hi = max(float(d_center_sym + half_pos), float(d_center_sym + min_half_sym))
        d_sym_lo = max(d_sym_lo, float(ctx.cfg.d_lo))
        d_sym_hi = min(d_sym_hi, float(ctx.cfg.d_hi))

    valid_lo = d_arr[d_arr <= d_sym_lo + 1e-9]
    if valid_lo.size > 0:
        d_sym_lo = float(np.max(valid_lo))

    valid_hi = d_arr[d_arr >= d_sym_hi - 1e-9]
    if valid_hi.size > 0:
        d_sym_hi = float(np.min(valid_hi))

    pos_valid = int(np.count_nonzero(d_arr > ctx.d0 + 1e-12))
    neg_valid = int(np.count_nonzero(d_arr < ctx.d0 - 1e-12))
    d_interval_sym = (float(d_sym_lo), float(d_sym_hi))

    log.info(
        "%s Auto-widened interval to guaranteed physical mesh (min_excursion included) | "
        "raw_interval=[%.6f, %.6f] nm | reported_interval=[%.6f, %.6f] nm",
        _LOG_PREFIX,
        float(d_interval_raw[0]),
        float(d_interval_raw[1]),
        float(d_sym_lo),
        float(d_sym_hi),
    )



    # -- Source 2: intrinsic method uncertainty +/-1e-4 on k (in linear k) ----
    # Applied BEFORE stats so that logk_span reflects the final corridor (union of both sources).
    # Formule : k_lo_final = max(min(k_lo_algo, max(k_ref − 1e-4, 1e-6)), 1e-6)
    #           k_hi_final = max(k_hi_algo, k_ref + 1e-4)
    k_ref_for_min = (
        np.asarray(ctx.corridor_ref_k_lam, dtype=np.float64).ravel()
        if ctx.corridor_ref_k_lam is not None
        else np.asarray([], dtype=np.float64)
    )
    if k_ref_for_min.size != np.asarray(k_lo, dtype=np.float64).ravel().size:
        k_ref_for_min = 0.5 * (np.asarray(k_lo, dtype=np.float64).ravel() + np.asarray(k_hi, dtype=np.float64).ravel())
    k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
        np.asarray(k_lo, dtype=np.float64),
        np.asarray(k_hi, dtype=np.float64),
        np.asarray(k_ref_for_min, dtype=np.float64),
        min_half_width=1e-4,
    )
    if int(k_min_changed) > 0:
        log.info(
            "%s corridor k-min-width enforced | half_width=1.0e-4 | adjusted_points=%d",
            _LOG_PREFIX,
            int(k_min_changed),
        )
    _log_corridor_envelope_diagnostics(
        n_lo=n_lo,
        n_hi=n_hi,
        k_lo=k_lo,
        k_hi=k_hi,
        k_stack=k_stack,
        corridor_ref_k_lam=ctx.corridor_ref_k_lam,
        base_k_lam=np.asarray(ctx.base_result.get("k_lam", []), dtype=np.float64).ravel(),
    )


    if ctx.log_coaching:
        _log_coaching_corridor_outcome(
            pconf=ctx.pconf,
            use_lr=ctx.use_lr,
            use_abs_delta=bool(ctx.use_abs_delta),
            d0=float(ctx.d0),
            d_arr=d_arr,
            rm_arr=rm_arr,
            rmse_opt=ctx.rmse_opt,
            rmse_thresh=ctx.rmse_thresh_active,
            polish_maxfun=int(ctx.maxfun_prof),
            base_result=ctx.base_result,
        )

    out_prof: dict[str, Any] = {
        "profile_d_polish_maxfun_effective": int(ctx.maxfun_prof),
        "profile_d_enabled": True,
        # P1.4 FIX: Unified heteroscedastic sigma for both LR and alpha modes
        "profile_d_sigma_hetero": bool(
            ctx._use_hetero and (ctx.sigma_t_f_hetero is not None or ctx.sigma_r_f_hetero is not None)
        ),
        "profile_d_sigma_hetero_scale": float(
            getattr(ctx.pconf, "heteroscedastic_sigma_scale", None)
            or getattr(ctx.pconf, "sigma_hetero_scale", 1.0)
            or 1.0
        )
        if ctx._use_hetero
        else None,
        "profile_d_use_heteroscedastic_sigma": bool(getattr(ctx.pconf, "use_heteroscedastic_sigma", False)),
        "profile_d_heteroscedastic_sigma_floor": float(getattr(ctx.pconf, "heteroscedastic_sigma_floor", 1e-6))
        if ctx._use_hetero
        else None,
        "profile_d_mode": str(ctx.pconf.mode),
        "profile_d_acceptance_mode": (
            "lr"
            if ctx.use_lr
            else (
                "delta_rmse_abs_best_polished"
                if (ctx.use_abs_delta and ctx.scientific_nominal)
                else ("delta_rmse_abs" if ctx.use_abs_delta else "alpha_heuristic")
            )
        ),
        "profile_d_scientific_nominal": bool(ctx.scientific_nominal),
        "profile_rmse_best_ref": float(ctx.rmse_opt) if ctx.scientific_nominal else None,
        "profile_delta_rmse_abs": float(ctx.tol_abs_effective) if ctx.use_abs_delta else None,
        "profile_corridor_nominal_label": (
            str(ctx.nom_pack.get("label", "")) if ctx.scientific_nominal and ctx.nom_pack is not None else None
        ),
        "profile_d_rmse_threshold_mode": str(ctx.rmse_thr_sub) if not ctx.use_lr else "alpha",
        "profile_d_rmse_abs_tolerance": float(ctx.tol_abs_effective) if ctx.use_abs_delta else None,
        "profile_d_rmse_abs_tolerance_nominal": float(ctx.tol_abs) if ctx.use_abs_delta else None,
        "profile_d_rmse_abs_tolerance_adaptive": bool(ctx.use_adaptive_abs_delta),
        "profile_d_rmse_abs_tolerance_adaptive_ok": bool(ctx.adaptive_abs_meta.get("ok", False))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_geom": float(ctx.adaptive_abs_meta.get("delta_rmse_geom", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_noise": float(ctx.adaptive_abs_meta.get("delta_rmse_noise", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_profile_sigma": float(ctx.adaptive_abs_meta.get("profile_sigma", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_curvature": float(ctx.adaptive_abs_meta.get("curvature", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_center_nm": float(ctx.adaptive_abs_meta.get("center_nm", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_abs_tolerance_h_ref_nm": float(ctx.adaptive_abs_meta.get("h_ref_nm", float("nan")))
        if ctx.use_abs_delta
        else None,
        "profile_d_rmse_alpha": float(ctx.pconf.rmse_alpha),
        "profile_d_rmse_opt": float(ctx.rmse_opt),
        "profile_d_rmse_ref_source": str(ctx.rmse_ref_tag),
        "profile_d_rmse_thresh": float(ctx.rmse_thresh_active),
        "profile_d_rmse_accept_max": float(ctx.rmse_thresh_active) if not ctx.use_lr else None,
        "profile_d_rmse_thresh_nominal": float(ctx.rmse_thresh) if (not ctx.use_lr) else None,
        "profile_d_threshold_basis_effective": str(ctx.threshold_basis_eff),
        "profile_d_threshold_fallback_reason": str(ctx.threshold_fallback_reason),
        "profile_d_auto_relaxed_threshold": bool(ctx.auto_relaxed_alpha),
        "profile_d_lr_conf": float(ctx.pconf.lr_conf_level) if ctx.use_lr else None,
        "profile_d_lr_delta_chi2": float(ctx.delta_chi2) if ctx.use_lr else None,
        "profile_d_sigma_t": float(ctx.sig_t) if ctx.use_lr else None,
        "profile_d_sigma_r": float(ctx.sig_r) if ctx.use_lr else None,
        "profile_d_values_nm": d_arr,
        "profile_d_rmse_values": rm_arr,
        "profile_d_chi2_values": c_arr,
        "profile_d_n_curves": np.asarray(n_stack, dtype=np.float64),
        "profile_d_k_curves": np.asarray(k_stack, dtype=np.float64),
        "profile_d_interval_nm": d_interval_sym,
        "profile_d_interval_raw_nm": d_interval_raw,
        "profile_d_interval_center_nm": float(d_center_sym),
        "profile_d_interval_center_source": str(center_source),
        "profile_d_interval_half_width_nm": 0.5 * float(max(0.0, d_interval_sym[1] - d_interval_sym[0])),
        "profile_d_parabola_ok": bool(parab_fit.get("ok", False)),
        "profile_d_parabola_center_nm": float(parab_fit.get("d_center", float("nan"))),
        "profile_d_parabola_anchor_nm": float(parab_fit.get("anchor_nm", float("nan"))),
        "profile_d_parabola_curvature": float(parab_fit.get("curvature", float("nan"))),
        "profile_d_parabola_slope_at_anchor": float(parab_fit.get("slope_at_anchor", float("nan"))),
        "profile_d_parabola_window_nm": parab_fit.get("window_nm", (float("nan"), float("nan"))),
        "profile_d_parabola_coeffs": parab_fit.get("coeffs", (float("nan"), float("nan"), float("nan"))),
        "profile_d_status": (
            "degenerate" if (int(pos_valid) < ctx.min_side or int(neg_valid) < ctx.min_side) else "ok"
        ),
        "profile_d_valid_side_pos": int(pos_valid),
        "profile_d_valid_side_neg": int(neg_valid),
        "profile_d_boundary_refine_calls": int(ctx.boundary_refine_calls),
        "profile_d_fit_fail_rate": float(
            np.nanmean(
                np.asarray(ctx.fit_fail_values, dtype=np.float64)
                / np.maximum(np.asarray(ctx.fit_try_values, dtype=np.float64), 1.0)
            )
        )
        if ctx.fit_try_values
        else float("nan"),
        "profile_d_seed_gate_eval_count": int(ctx.seed_gate_eval_count),
        "profile_d_seed_gate_kept_count": int(ctx.seed_gate_kept_count),
        "profile_d_seed_gate_kept_rate": (
            float(ctx.seed_gate_kept_count) / float(ctx.seed_gate_eval_count)
            if int(ctx.seed_gate_eval_count) > 0
            else float("nan")
        ),
        "profile_d_seed_gate_center_kept": bool(ctx.center_seed_kept),
        "profile_d_seed_gate_mean_delta_refit_minus_seed": (
            float(np.nanmean(ctx.seed_gate_deltas)) if ctx.seed_gate_deltas.size else float("nan")
        ),
        "profile_d_seed_gate_min_delta_refit_minus_seed": (
            float(np.nanmin(ctx.seed_gate_deltas)) if ctx.seed_gate_deltas.size else float("nan")
        ),
        "profile_d_seed_gate_max_delta_refit_minus_seed": (
            float(np.nanmax(ctx.seed_gate_deltas)) if ctx.seed_gate_deltas.size else float("nan")
        ),
        "profile_d_seed_gate_std_delta_refit_minus_seed": (
            float(np.nanstd(ctx.seed_gate_deltas)) if ctx.seed_gate_deltas.size else float("nan")
        ),
        # P0.3 FIX: Corridor quality status flags
        "profile_d_seed_gate_saturated": bool(ctx.seed_gate_saturated_global),
        "profile_d_seed_gate_auto_escalated": bool(ctx.seed_gate_auto_escalated_global),
        # P1.1 FIX: User RMSE mask for manual spectral exclusion
        "profile_d_user_rmse_mask": (
            np.asarray(ctx._user_mask, dtype=bool).copy()
            if ctx._user_mask is not None and len(np.asarray(ctx._user_mask)) > 0
            else None
        ),
        "profile_d_mean_nfev": float(np.nanmean(np.asarray(ctx.fit_nfev_values, dtype=np.float64)))
        if ctx.fit_nfev_values
        else float("nan"),
        "profile_d_mean_nit": float(np.nanmean(np.asarray(ctx.fit_nit_values, dtype=np.float64)))
        if ctx.fit_nit_values
        else float("nan"),
        "corridor_n_lo": np.asarray(n_lo, dtype=np.float64),
        "corridor_n_hi": np.asarray(n_hi, dtype=np.float64),
        "corridor_k_lo": np.asarray(k_lo, dtype=np.float64),
        "corridor_k_hi": np.asarray(k_hi, dtype=np.float64),
        "corridor_k_min_half_width": float(1e-4),
        "corridor_k_min_half_width_enforced_points": int(k_min_changed),
    }

    if ctx.corridor_ref_n_lam is not None and ctx.corridor_ref_k_lam is not None:
        out_prof["corridor_reference_n_lam"] = ctx.corridor_ref_n_lam

        out_prof["corridor_reference_k_lam"] = ctx.corridor_ref_k_lam

    return out_prof

def _compute_corridor_rmse_threshold(
    cfg: "SplineOptConfig",
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
                _LOG_PREFIX, _alpha_user, alpha_intelligent, _N_eff,
            )
        else:
            log.info(
                "%s Corridor intelligent threshold | N_eff=%d (N_obs=%d, N_params=%d) => alpha=%.5f",
                _LOG_PREFIX, _N_eff, _N_data, _N_params, alpha_intelligent,
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
            _LOG_PREFIX, _alpha_user, alpha_intelligent,
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
            _LOG_PREFIX, str(corridor_seed_x_source), float(rmse_seed0),
            str(rmse_ref_tag), float(rmse_opt), float(dv), float(tol_rm),
        )
        if float(dv) > float(tol_rm):
            xref = str(corridor_seed_x_source)
            if "roundtrip" in xref.lower():
                log.info(
                    "%s Corridor seed vs %s: |Delta|=%.3e > tol=%.3e (x_source=%s). "
                    "Often expected when the packed seed differs from the polished nominal pack; "
                    "investigate only if envelopes look inconsistent (mono ξ / export mismatch otherwise).",
                    _LOG_PREFIX, str(rmse_ref_tag), float(dv), float(tol_rm), xref,
                )
            else:
                log.warning(
                    "%s Corridor seed vs spectral_rmse_best_value: |Delta|=%.3e exceeds tol=%.3e — "
                    "check x_seg_spline_sigma vs n_lam_seg_spline_sigma export, bounds clip, or mono ξ round-trip.",
                    _LOG_PREFIX, float(dv), float(tol_rm),
                )

    return rmse_thresh



def _prep_corridor_base_eff(
    cfg, base_result, pconf, use_abs_delta, use_lr
):
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
        base_eff, sk, n_nodes_phys0, L_nodes0, d0, _prof_geom,
        x_nodes0, corridor_seed_x_source, bounds_nodes, x0_default,
        mse_seed0, rmse_seed0, scientific_nominal, nom_pack, sk_n_log,
    )

def _log_corridor_start_config(
    cfg, pconf, use_abs_delta, k, d0, rmse_opt, rmse_ref_tag, rmse_thr_sub,
    use_adaptive_abs_delta, tol_abs, rmse_thresh, maxfun_prof, scientific_nominal,
    use_lr, delta_chi2, sig_t, sig_r, sigma_t_f_hetero, sigma_r_f_hetero
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
    if not (bool(getattr(pconf, "rmse_threshold_mode", "").strip().lower() in ("abs_delta_adaptive", "alpha_plus_adaptive_delta")) and np.isfinite(rmse_opt) and center_fit is not None):
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
    if bool(adaptive_abs_meta.get("ok", False)) and np.isfinite(float(adaptive_abs_meta.get("delta_rmse_tol", float("nan")))):
        tol_abs_effective = float(adaptive_abs_meta.get("delta_rmse_tol", float(tol_abs)))
        _alpha_f = float(pconf.rmse_alpha) if use_alpha_factor else 1.0
        rmse_thresh_active = _alpha_f * float(rmse_opt) + float(tol_abs_effective)
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
    pconf, use_lr, use_abs_delta, rm_c, rmse_thresh_active, rmse_opt,
    threshold_basis_eff, rmse_thresh
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

class CorridorContextBuilder:
    def __init__(
        self,
        cfg,
        base_result,
        pconf=None,
        log_coaching=True,
        profile_polish_maxfun=None,
        live_cb=None,
    ):
        self.cfg = cfg
        self.base_result = base_result
        self.pconf = pconf or ProfileCorridorConfig()
        self.log_coaching = log_coaching
        self.profile_polish_maxfun = profile_polish_maxfun
        self.live_cb = live_cb
        self.live_stream_lock = threading.Lock()
        self.live_streamer = CorridorLiveStreamer(
            live_cb=live_cb,
            live_stream_lock=self.live_stream_lock,
            live_d_vals=[],
            live_rmse_vals=[],
            live_n_curves=[],
            live_k_curves=[],
            live_chi2_vals=[],
        )

        self.d_vals = []
        self.n_curves = []
        self.k_curves = []
        self.x_curves = []
        self.rmse_vals = []
        self.chi2_vals = []
        self.fit_nfev_values = []
        self.fit_nit_values = []
        self.fit_try_values = []
        self.fit_fail_values = []

        self.live_d_vals = []
        self.live_rmse_vals = []
        self.live_n_curves = []
        self.live_k_curves = []
        self.live_chi2_vals = []

    def _emit_live_profile(self, current_d_nm=None):
        self.live_streamer.emit_profile(current_d_nm=current_d_nm)

    def _push_live_point(self, d_nm, rmse, n_lam=None, k_lam=None, chi2=None):
        self.live_streamer.push_point(d_nm, rmse, n_lam=n_lam, k_lam=k_lam, chi2=chi2)

    def _push_live_point_from_payload(self, payload):
        self.live_streamer.push_payload(payload)

    def _resolve_config_and_base(self):
        maxfun_prof = int(corridor_profile_refit_maxfun(self.cfg, self.profile_polish_maxfun))
        t0 = time.perf_counter()
        lam_full = np.asarray(self.cfg.lam_nm, dtype=np.float64).ravel()
        use_lr = str(getattr(self.pconf, "mode", "alpha")).strip().lower() == "lr"
        rmse_thr_sub = str(getattr(self.pconf, "rmse_threshold_mode", "alpha") or "alpha").strip().lower()
        use_abs_delta = (not use_lr) and rmse_thr_sub in (
            "abs_delta",
            "alpha_plus_delta",
            "abs_delta_adaptive",
            "alpha_plus_adaptive_delta",
        )
        use_alpha_factor = rmse_thr_sub in ("alpha_plus_delta", "alpha_plus_adaptive_delta")
        use_adaptive_abs_delta = (not use_lr) and rmse_thr_sub in ("abs_delta_adaptive", "alpha_plus_adaptive_delta")
        tol_abs = float(max(float(getattr(self.pconf, "rmse_abs_tolerance", 2.5e-4) or 0.0), 0.0))

        if use_abs_delta:
            log.info(
                "%s Threshold mode resolved early | rmse_threshold_mode=%s | delta_mode=%s | alpha_factor=%s | fixed_delta_nominal=%.6f",
                _LOG_PREFIX,
                str(rmse_thr_sub),
                "adaptive(local parabola+roughness)" if use_adaptive_abs_delta else "fixed(abs_delta)",
                "on" if use_alpha_factor else "off",
                float(tol_abs),
            )

        (
            base_eff, sk, n_nodes_phys0, L_nodes0, d0, _prof_geom,
            x_nodes0, corridor_seed_x_source, bounds_nodes, x0_default,
            mse_seed0, rmse_seed0, scientific_nominal, nom_pack, sk_n_log,
        ) = _prep_corridor_base_eff(
            cfg=self.cfg, base_result=self.base_result, pconf=self.pconf,
            use_abs_delta=use_abs_delta, use_lr=use_lr
        )
        k = int(sk.size)
        n_b = np.asarray(base_eff.get("n_lam"), dtype=np.float64).ravel()
        k_b = np.asarray(base_eff.get("k_lam"), dtype=np.float64).ravel()
        rmse_spectral_curves = float("nan")

        if n_b.size == lam_full.size and k_b.size == lam_full.size:
            _, rmse_sc = spectral_mse_rmse_masked_from_nk(self.cfg, base_eff, lam_full, n_b, k_b, float(d0))
            rmse_spectral_curves = float(rmse_sc) if np.isfinite(float(rmse_sc)) else float("nan")

        if scientific_nominal and nom_pack is not None:
            rmse_opt = float(nom_pack["rmse_best"])
            rmse_ref_tag = "spectral_rmse_best_value"
        else:
            rmse_opt, rmse_ref_tag = _pick_rmse_reference_for_profile(self.cfg, base_eff, sk, float(d0), x_nodes0)
            if use_abs_delta and np.isfinite(rmse_spectral_curves):
                rmse_opt = float(rmse_spectral_curves)
                rmse_ref_tag = "spectral_rmse_base_nk"

        rmse_thresh = _compute_corridor_rmse_threshold(
            self.cfg, self.pconf, rmse_opt, rmse_seed0, sk, use_lr, use_abs_delta,
            use_alpha_factor, tol_abs, rmse_ref_tag, corridor_seed_x_source,
            scientific_nominal, nom_pack, log, _LOG_PREFIX,
        )

        rmse_thresh_active = float(rmse_thresh)
        auto_relaxed_alpha = False
        threshold_fallback_reason = ""
        threshold_basis_eff = str(getattr(self.pconf, "threshold_basis", "max") or "max").strip().lower()
        delta_chi2 = float(_chi2.ppf(float(np.clip(self.pconf.lr_conf_level, 1e-6, 0.999999)), 1)) if use_lr else float("nan")
        sigma_auto = float(rmse_opt) if np.isfinite(rmse_opt) and rmse_opt > 0 else 1.0
        sig_t = float(self.pconf.sigma_t) if (self.pconf.sigma_t is not None and float(self.pconf.sigma_t) > 0) else sigma_auto
        sig_r = float(self.pconf.sigma_r) if (self.pconf.sigma_r is not None and float(self.pconf.sigma_r) > 0) else sigma_auto

        sigma_t_f_hetero: np.ndarray | None = None
        sigma_r_f_hetero: np.ndarray | None = None

        _use_hetero = bool(
            getattr(self.pconf, "use_heteroscedastic_sigma", False) or getattr(self.pconf, "sigma_hetero_residual", False)
        )
        if _use_hetero:
            _heto_scale = float(
                getattr(self.pconf, "heteroscedastic_sigma_scale", None) or getattr(self.pconf, "sigma_hetero_scale", 1.0) or 1.0
            )
            _heto_floor = float(
                getattr(self.pconf, "heteroscedastic_sigma_floor", None)
                or (max(1e-8, 0.01 * float(rmse_opt)) if np.isfinite(rmse_opt) else 1e-6)
            )

            sigma_t_f_hetero, sigma_r_f_hetero = _hetero_sigma_masked_from_base(
                self.cfg,
                base_eff,
                scale=_heto_scale,
                floor_abs=_heto_floor,
            )

            if sigma_t_f_hetero is not None or sigma_r_f_hetero is not None:
                log.info(
                    "%s Unified heteroscedastic sigma (max(floor, scale×|residual|)) | scale=%.4g floor_abs=%.4g | mode=%s",
                    _LOG_PREFIX,
                    _heto_scale,
                    _heto_floor,
                    "LR" if use_lr else "alpha",
                )

        _user_mask = getattr(self.pconf, "user_rmse_mask", None)
        if _user_mask is not None and len(np.asarray(_user_mask)) > 0:
            log.info(
                "%s User RMSE mask applied: %d wavelengths excluded",
                _LOG_PREFIX,
                int(np.sum(~np.asarray(_user_mask, dtype=bool))),
            )

        _log_corridor_base_geometry(
            sk=np.asarray(sk, dtype=np.float64),
            n_phys=np.asarray(n_nodes_phys0, dtype=np.float64),
            L_nodes=np.asarray(L_nodes0, dtype=np.float64),
            d0=float(d0),
            sk_n_stored=sk_n_log,
            diag=_prof_geom,
            rmse_ref_pipeline=float(rmse_opt),
            rmse_seed_no_refit=float(rmse_seed0),
            mse_seed_no_refit=float(mse_seed0),
            use_abs_delta=bool(use_abs_delta),
        )

        _log_corridor_start_config(
            cfg=self.cfg, pconf=self.pconf, use_abs_delta=use_abs_delta, k=k, d0=float(d0),
            rmse_opt=float(rmse_opt), rmse_ref_tag=str(rmse_ref_tag), rmse_thr_sub=str(rmse_thr_sub),
            use_adaptive_abs_delta=use_adaptive_abs_delta, tol_abs=float(tol_abs),
            rmse_thresh=float(rmse_thresh), maxfun_prof=maxfun_prof, scientific_nominal=scientific_nominal,
            use_lr=use_lr, delta_chi2=float(delta_chi2), sig_t=float(sig_t), sig_r=float(sig_r),
            sigma_t_f_hetero=sigma_t_f_hetero, sigma_r_f_hetero=sigma_r_f_hetero,
        )

        return (
            maxfun_prof, lam_full, use_lr, rmse_thr_sub, use_abs_delta,
            use_alpha_factor, use_adaptive_abs_delta, tol_abs,
            base_eff, sk, n_nodes_phys0, L_nodes0, d0, _prof_geom,
            x_nodes0, corridor_seed_x_source, bounds_nodes, x0_default,
            mse_seed0, rmse_seed0, scientific_nominal, nom_pack, sk_n_log,
            k, n_b, k_b, rmse_spectral_curves, rmse_opt, rmse_ref_tag,
            rmse_thresh, rmse_thresh_active, auto_relaxed_alpha,
            threshold_fallback_reason, threshold_basis_eff, delta_chi2,
            sig_t, sig_r, sigma_t_f_hetero, sigma_r_f_hetero, _use_hetero,
            _user_mask, t0
        )

    def _process_center_solution(
        self, maxfun_prof, lam_full, use_lr, rmse_thr_sub, use_abs_delta,
        use_alpha_factor, use_adaptive_abs_delta, tol_abs, base_eff, sk, d0,
        x_nodes0, bounds_nodes, x0_default, rmse_seed0, scientific_nominal, nom_pack,
        n_b, k_b, rmse_spectral_curves, rmse_opt, rmse_ref_tag, rmse_thresh, delta_chi2,
        sig_t, sig_r, sigma_t_f_hetero, sigma_r_f_hetero, threshold_basis_eff,
        _use_hetero, _user_mask, t0
    ):
        boundary_refine_calls = 0
        corridor_ref_n_lam = None
        corridor_ref_k_lam = None

        if use_abs_delta and n_b.size == lam_full.size and k_b.size == lam_full.size:
            if scientific_nominal and nom_pack is not None:
                first_rmse = float(rmse_opt)
            elif np.isfinite(rmse_spectral_curves):
                first_rmse = float(rmse_spectral_curves)
            else:
                first_rmse = None

            if first_rmse is not None:
                self.d_vals.append(float(d0))
                self.n_curves.append(n_b.copy())
                self.k_curves.append(k_b.copy())
                self.rmse_vals.append(first_rmse)
                self.chi2_vals.append(float("nan"))
                self.fit_nfev_values.append(float("nan"))
                self.fit_nit_values.append(float("nan"))
                self.fit_try_values.append(float("nan"))
                self.fit_fail_values.append(float("nan"))
                self.live_streamer.push_point(float(d0), float(first_rmse), n_b.copy(), k_b.copy(), float("nan"))

                if scientific_nominal and nom_pack is not None:
                    corridor_ref_n_lam = np.asarray(nom_pack["n_lam"], dtype=np.float64).ravel().copy()
                    corridor_ref_k_lam = np.asarray(nom_pack["k_lam"], dtype=np.float64).ravel().copy()
                else:
                    corridor_ref_n_lam = n_b.copy()
                    corridor_ref_k_lam = k_b.copy()

        fit0, _, metric0 = _best_fit_at_d(
            self.cfg,
            sk=sk,
            d_nm=float(d0),
            x_seed_primary=x_nodes0,
            x_seed_secondary=None,
            x_seed_default=x0_default,
            bounds_nodes=bounds_nodes,
            maxfun=maxfun_prof,
            use_lr=use_lr,
            sig_t=sig_t,
            sig_r=sig_r,
            chi2_min_ref=None,
            delta_chi2=float(delta_chi2) if np.isfinite(delta_chi2) else 0.0,
            pconf=self.pconf,
            stage_label="Center",
            sigma_t_f=sigma_t_f_hetero,
            sigma_r_f=sigma_r_f_hetero,
        )

        chi2_min = float(metric0) if (use_lr and np.isfinite(metric0)) else float("nan")
        rm_c = (
            float(fit0["rmse"]) if fit0 is not None and np.isfinite(float(fit0.get("rmse", float("nan")))) else float("nan")
        )

        adaptive_abs_meta, tol_abs_effective = _eval_adaptive_abs_tolerance(
            self.cfg,
            pconf=self.pconf,
            sk=sk,
            d0=float(d0),
            center_fit=fit0,
            x_nodes0=x_nodes0,
            x0_default=x0_default,
            bounds_nodes=bounds_nodes,
            maxfun_prof=maxfun_prof,
            sig_t=sig_t,
            sig_r=sig_r,
            sigma_t_f_hetero=sigma_t_f_hetero,
            sigma_r_f_hetero=sigma_r_f_hetero,
            tol_abs=tol_abs,
            rmse_opt=rmse_opt,
            rmse_thresh=rmse_thresh,
            use_alpha_factor=use_alpha_factor,
            live_streamer=self.live_streamer if use_adaptive_abs_delta else None,
        )

        rmse_thresh_active = float(rmse_thresh)
        if bool(adaptive_abs_meta.get("ok", False)) and np.isfinite(float(adaptive_abs_meta.get("delta_rmse_tol", float("nan")))):
            _alpha_f = float(self.pconf.rmse_alpha) if use_alpha_factor else 1.0
            rmse_thresh = _alpha_f * float(rmse_opt) + float(tol_abs)
            rmse_thresh_active = _alpha_f * float(rmse_opt) + float(tol_abs_effective)
        else:
            log.info(
                "%s Adaptive DeltaRMSE unavailable around d0=%.6f nm - fallback to fixed DeltaRMSE=%.6e",
                _LOG_PREFIX,
                float(d0),
                float(tol_abs),
            )

        (
            rmse_thresh_active, auto_relaxed_alpha, threshold_basis_eff, threshold_fallback_reason
        ) = _eval_corridor_threshold_fallback(
            pconf=self.pconf, use_lr=use_lr, use_abs_delta=use_abs_delta, rm_c=float(rm_c),
            rmse_thresh_active=float(rmse_thresh_active), rmse_opt=float(rmse_opt),
            threshold_basis_eff=str(threshold_basis_eff), rmse_thresh=float(rmse_thresh),
        )

        fit0_ok = False
        if fit0 is not None and np.isfinite(float(fit0.get("rmse", float("nan")))):
            fit0_ok = np.isfinite(chi2_min) if use_lr else (float(fit0["rmse"]) <= rmse_thresh_active)

        center_seed_kept = False
        center_seed_gate_delta_refit_minus_seed = float("nan")
        center_seed_gate_eval_count = 1 if fit0 is not None else 0
        center_seed_gate_kept_count = 0
        if fit0 is not None:
            _rm_seed0 = fit0.get("rmse_seed_before_refit")
            _rm_refit0 = fit0.get("rmse_refit_attempted")
            if (
                _rm_seed0 is not None
                and _rm_refit0 is not None
                and np.isfinite(float(_rm_seed0))
                and np.isfinite(float(_rm_refit0))
            ):
                center_seed_kept_count = int(bool(fit0.get("seed_kept_over_refit", False)))
                center_seed_gate_kept_count = center_seed_kept_count
                center_seed_gate_delta_refit_minus_seed = float(_rm_refit0) - float(_rm_seed0)

        if (not fit0_ok) and (not use_lr) and np.isfinite(float(rmse_seed0)) and np.isfinite(float(rmse_thresh_active)):
            if float(rmse_seed0) <= float(rmse_thresh_active):
                fit0_ok = True
                center_seed_kept = True

        if fit0 is not None and fit0_ok:
            if center_seed_kept:
                self.d_vals.append(float(d0))
                self.n_curves.append(np.asarray(base_eff.get("n_lam"), dtype=np.float64).ravel().copy())
                self.k_curves.append(np.asarray(base_eff.get("k_lam"), dtype=np.float64).ravel().copy())
                self.x_curves.append(x_nodes0.copy())
                self.rmse_vals.append(float(rmse_seed0))
                self.chi2_vals.append(float("nan"))
                self.fit_nfev_values.append(float("nan"))
                self.fit_nit_values.append(float("nan"))
                self.fit_try_values.append(0.0)
                self.fit_fail_values.append(float(fit0.get("n_failed_fit", float("nan"))) if fit0 is not None else float("nan"))
                self._push_live_point(
                    float(d0),
                    float(rmse_seed0),
                    np.asarray(base_eff.get("n_lam"), dtype=np.float64).ravel().copy(),
                    np.asarray(base_eff.get("k_lam"), dtype=np.float64).ravel().copy(),
                    float("nan"),
                )

                if scientific_nominal and nom_pack is not None:
                    corridor_ref_n_lam = np.asarray(nom_pack["n_lam"], dtype=np.float64).ravel().copy()
                    corridor_ref_k_lam = np.asarray(nom_pack["k_lam"], dtype=np.float64).ravel().copy()
                else:
                    corridor_ref_n_lam = np.asarray(base_eff.get("n_lam"), dtype=np.float64).ravel().copy()
                    corridor_ref_k_lam = np.asarray(base_eff.get("k_lam"), dtype=np.float64).ravel().copy()

                x_nodes_center = x_nodes0.copy()
                log.info(
                    "%s Center: keeping nominal seed at d=d_opt | spectral RMSE **without refit**=%.8f <= active threshold %.8f "
                    "(center refit RMSE=%s). Refitted center kept only as diagnostic; corridor remains anchored on the nominal model.",
                    _LOG_PREFIX,
                    float(rmse_seed0),
                    float(rmse_thresh_active),
                    (
                        f"{float(fit0['rmse']):.8f}"
                        if fit0 is not None and np.isfinite(float(fit0.get("rmse", float("nan"))))
                        else "n/a"
                    ),
                )
            else:
                self.d_vals.append(float(fit0["d_nm"]))
                self.n_curves.append(np.asarray(fit0["n_lam"], dtype=np.float64))
                self.k_curves.append(np.asarray(fit0["k_lam"], dtype=np.float64))
                self.x_curves.append(np.asarray(fit0["x_nodes_best"], dtype=np.float64).ravel().copy())
                self.rmse_vals.append(float(fit0["rmse"]))
                self.chi2_vals.append(float(chi2_min) if use_lr else float("nan"))
                self.fit_nfev_values.append(float(fit0.get("nfev", float("nan"))))
                self.fit_nit_values.append(float(fit0.get("nit", float("nan"))))
                self.fit_try_values.append(float(fit0.get("n_try", float("nan"))))
                self.fit_fail_values.append(float(fit0.get("n_failed_fit", float("nan"))))
                self._push_live_point(
                    float(fit0["d_nm"]),
                    float(fit0["rmse"]),
                    np.asarray(fit0["n_lam"], dtype=np.float64).ravel(),
                    np.asarray(fit0["k_lam"], dtype=np.float64).ravel(),
                    float(chi2_min) if use_lr else float("nan"),
                )

                if not scientific_nominal:
                    corridor_ref_n_lam = np.asarray(fit0["n_lam"], dtype=np.float64).ravel().copy()
                    corridor_ref_k_lam = np.asarray(fit0["k_lam"], dtype=np.float64).ravel().copy()

                x_nodes_center = np.asarray(fit0["x_nodes_best"], dtype=np.float64).ravel().copy()
                mo0 = fit0.get("mse_objective")
                mo0s = f"{float(mo0):.6e}" if mo0 is not None and np.isfinite(float(mo0)) else "n/a"

                if use_abs_delta:
                    log.info(
                        "%s Center: OK | Spectral RMSE **after refit** (d=d_opt)=%.8f | RMSE_ref threshold=%.8f (%s) | "
                        "refit_objective_MSE=%s | chi2_min=%s | Delta(refit - seed without refit)=%+.6e | "
                        "Delta(refit - nominal RMSE_ref)=%+.6e",
                        _LOG_PREFIX,
                        float(fit0["rmse"]),
                        float(rmse_opt),
                        str(rmse_ref_tag),
                        mo0s,
                        f"{chi2_min:.8f}" if use_lr and np.isfinite(chi2_min) else "n/a",
                        float(fit0["rmse"]) - float(rmse_seed0),
                        float(fit0["rmse"]) - float(rmse_opt),
                    )
                else:
                    log.info(
                        "%s Center: OK | spectral RMSE **after refit** (d=d_opt)=%.8f | pipeline RMSE_ref=%.8f (%s) | "
                        "refit_objective_MSE=%s | chi2_min=%s | Delta(refit RMSE - no-refit seed)=%+.6e | "
                        "Delta(refit RMSE - RMSE_ref)=%+.6e",
                        _LOG_PREFIX,
                        float(fit0["rmse"]),
                        float(rmse_opt),
                        str(rmse_ref_tag),
                        mo0s,
                        f"{chi2_min:.8f}" if use_lr and np.isfinite(chi2_min) else "n/a",
                        float(fit0["rmse"]) - float(rmse_seed0),
                        float(fit0["rmse"]) - float(rmse_opt),
                    )
        else:
            if not bool(self.pconf.include_center_even_if_nan):
                if self.log_coaching:
                    _log_coaching_corridor_failure(
                        reason="centre_fail",
                        pconf=self.pconf,
                        use_lr=use_lr,
                        rmse_opt=rmse_opt,
                        rmse_thresh=rmse_thresh_active,
                        d0=float(d0),
                    )
                return {"profile_d_status": "failed"}

            x_nodes_center = x_nodes0.copy()
            log.warning("%s Center: failed | continue=%s", _LOG_PREFIX, bool(self.pconf.include_center_even_if_nan))

        return CorridorProfileContext(
            _use_hetero=_use_hetero,
            _user_mask=_user_mask,
            adaptive_abs_meta=adaptive_abs_meta,
            auto_relaxed_alpha=auto_relaxed_alpha,
            base_result=self.base_result,
            boundary_refine_calls=boundary_refine_calls,
            center_seed_kept=center_seed_kept,
            cfg=self.cfg,
            chi2_vals=self.chi2_vals,
            d0=d0,
            d_vals=self.d_vals,
            delta_chi2=delta_chi2,
            fit_fail_values=self.fit_fail_values,
            fit_nfev_values=self.fit_nfev_values,
            fit_nit_values=self.fit_nit_values,
            fit_try_values=self.fit_try_values,
            k_curves=self.k_curves,
            log_coaching=self.log_coaching,
            maxfun_prof=maxfun_prof,
            min_side=int(max(0, getattr(self.pconf, "min_valid_each_side", 0))),
            n_curves=self.n_curves,
            nom_pack=nom_pack,
            pconf=self.pconf,
            rmse_opt=rmse_opt,
            rmse_ref_tag=rmse_ref_tag,
            rmse_thr_sub=rmse_thr_sub,
            rmse_thresh=rmse_thresh,
            rmse_thresh_active=rmse_thresh_active,
            rmse_vals=self.rmse_vals,
            scientific_nominal=scientific_nominal,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.asarray([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=sig_r,
            sig_t=sig_t,
            sigma_r_f_hetero=sigma_r_f_hetero,
            sigma_t_f_hetero=sigma_t_f_hetero,
            t0=t0,
            threshold_basis_eff=threshold_basis_eff,
            threshold_fallback_reason=threshold_fallback_reason,
            tol_abs=tol_abs,
            tol_abs_effective=tol_abs_effective,
            use_abs_delta=use_abs_delta,
            use_adaptive_abs_delta=use_adaptive_abs_delta,
            use_lr=use_lr,
            sk=sk,
            x_nodes_center=x_nodes_center,
            x0_default=x0_default,
            bounds_nodes=bounds_nodes,
            chi2_min=chi2_min,
            x_curves=self.x_curves,
            corridor_ref_n_lam=corridor_ref_n_lam,
            corridor_ref_k_lam=corridor_ref_k_lam,
            _push_live_point_from_payload=self._push_live_point_from_payload,
            live_streamer=self.live_streamer,
            center_seed_gate_eval_count=center_seed_gate_eval_count,
            center_seed_gate_kept_count=center_seed_gate_kept_count,
            center_seed_gate_delta_refit_minus_seed=center_seed_gate_delta_refit_minus_seed,
        )

    def build(self) -> CorridorProfileContext | dict:
        """Compute d interval and n/k corridors by profiling (refit nodes at fixed d).

        Returns a dict of fields to merge into the pipeline result (or empty dict if disabled / impossible).

        """
        pconf = self.pconf or ProfileCorridorConfig()
        if not bool(pconf.enabled):
            return {}

        (
            maxfun_prof, lam_full, use_lr, rmse_thr_sub, use_abs_delta,
            use_alpha_factor, use_adaptive_abs_delta, tol_abs,
            base_eff, sk, n_nodes_phys0, L_nodes0, d0, _prof_geom,
            x_nodes0, corridor_seed_x_source, bounds_nodes, x0_default,
            mse_seed0, rmse_seed0, scientific_nominal, nom_pack, sk_n_log,
            k, n_b, k_b, rmse_spectral_curves, rmse_opt, rmse_ref_tag,
            rmse_thresh, rmse_thresh_active, auto_relaxed_alpha,
            threshold_fallback_reason, threshold_basis_eff, delta_chi2,
            sig_t, sig_r, sigma_t_f_hetero, sigma_r_f_hetero, _use_hetero,
            _user_mask, t0
        ) = self._resolve_config_and_base()

        if lam_full.size < 3 or not np.isfinite(rmse_opt) or not np.isfinite(rmse_thresh):
            if self.log_coaching:
                _log_coaching_corridor_failure(
                    reason="rmse_meta_invalid",
                    pconf=self.pconf,
                    use_lr=use_lr,
                    rmse_opt=rmse_opt,
                    rmse_thresh=rmse_thresh,
                    d0=float(d0),
                )
            return {"profile_d_status": "failed"}

        result = self._process_center_solution(
            maxfun_prof=maxfun_prof, lam_full=lam_full, use_lr=use_lr,
            rmse_thr_sub=rmse_thr_sub, use_abs_delta=use_abs_delta,
            use_alpha_factor=use_alpha_factor, use_adaptive_abs_delta=use_adaptive_abs_delta,
            tol_abs=tol_abs, base_eff=base_eff, sk=sk, d0=d0,
            x_nodes0=x_nodes0, bounds_nodes=bounds_nodes, x0_default=x0_default,
            rmse_seed0=rmse_seed0, scientific_nominal=scientific_nominal, nom_pack=nom_pack,
            n_b=n_b, k_b=k_b, rmse_spectral_curves=rmse_spectral_curves, rmse_opt=rmse_opt,
            rmse_ref_tag=rmse_ref_tag, rmse_thresh=rmse_thresh, delta_chi2=delta_chi2,
            sig_t=sig_t, sig_r=sig_r, sigma_t_f_hetero=sigma_t_f_hetero,
            sigma_r_f_hetero=sigma_r_f_hetero, threshold_basis_eff=threshold_basis_eff,
            _use_hetero=_use_hetero, _user_mask=_user_mask, t0=t0
        )
        return result


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
    builder = CorridorContextBuilder(
        cfg=cfg,
        base_result=base_result,
        pconf=pconf,
        log_coaching=log_coaching,
        profile_polish_maxfun=profile_polish_maxfun,
        live_cb=live_cb,
    )
    return builder.build()

def compute_profiled_corridors_by_d(
    cfg: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig | None = None,
    log_coaching: bool = True,
    profile_polish_maxfun: int | None = None,
    live_cb: Any | None = None,
) -> dict[str, Any]:
    ctx = _setup_corridor_context(
        cfg,
        base_result,
        pconf=pconf,
        log_coaching=log_coaching,
        profile_polish_maxfun=profile_polish_maxfun,
        live_cb=live_cb,
    )
    if isinstance(ctx, dict):
        return ctx

    target_min_span = 0.0
    if hasattr(ctx, "adaptive_abs_meta") and isinstance(ctx.adaptive_abs_meta, dict) and ctx.adaptive_abs_meta.get("ok", False):
        _curv = float(ctx.adaptive_abs_meta.get("curvature", float("nan")))
        _dtol = float(ctx.adaptive_abs_meta.get("delta_rmse_tol", float("nan")))
        if np.isfinite(_curv) and _curv > 0.0 and np.isfinite(_dtol) and _dtol > 0.0:
            target_min_span = float(np.sqrt(_dtol / _curv))

    def _run_walks_sequential() -> tuple[dict[str, Any], dict[str, Any]]:

        return (
            _corridor_profile_walk_side(
                1.0,
                ctx.pconf,
                ctx.cfg,
                ctx.sk,
                ctx.d0,
                ctx.x_nodes_center,
                ctx.x0_default,
                ctx.bounds_nodes,
                ctx.maxfun_prof,
                ctx.use_lr,
                ctx.chi2_min,
                ctx.delta_chi2,
                ctx.rmse_thresh_active,
                ctx.rmse_opt,
                ctx.sig_t,
                ctx.sig_r,
                ctx.sigma_t_f_hetero,
                ctx.sigma_r_f_hetero,
                ctx.live_streamer,
                target_min_span=target_min_span,
            ),
            _corridor_profile_walk_side(
                -1.0,
                ctx.pconf,
                ctx.cfg,
                ctx.sk,
                ctx.d0,
                ctx.x_nodes_center,
                ctx.x0_default,
                ctx.bounds_nodes,
                ctx.maxfun_prof,
                ctx.use_lr,
                ctx.chi2_min,
                ctx.delta_chi2,
                ctx.rmse_thresh_active,
                ctx.rmse_opt,
                ctx.sig_t,
                ctx.sig_r,
                ctx.sigma_t_f_hetero,
                ctx.sigma_r_f_hetero,
                ctx.live_streamer,
                target_min_span=target_min_span,
            ),
        )

    parallel_walks = bool(getattr(ctx.cfg, "corridor_profile_d_parallel_walks", True))

    if parallel_walks:
        try:
            p_plus = ctx.pconf.replace(rng_seed=int(ctx.pconf.rng_seed) + 1_000_003)

            p_minus = ctx.pconf.replace(rng_seed=int(ctx.pconf.rng_seed) + 1_000_019)

            with ThreadPoolExecutor(max_workers=2) as _pool:
                _f_plus = _pool.submit(
                    _corridor_profile_walk_side,
                    1.0,
                    p_plus,
                    ctx.cfg,
                    ctx.sk,
                    ctx.d0,
                    ctx.x_nodes_center,
                    ctx.x0_default,
                    ctx.bounds_nodes,
                    ctx.maxfun_prof,
                    ctx.use_lr,
                    ctx.chi2_min,
                    ctx.delta_chi2,
                    ctx.rmse_thresh_active,
                    ctx.rmse_opt,
                    ctx.sig_t,
                    ctx.sig_r,
                    ctx.sigma_t_f_hetero,
                    ctx.sigma_r_f_hetero,
                    ctx.live_streamer,
                    target_min_span=target_min_span,
                )

                _f_minus = _pool.submit(
                    _corridor_profile_walk_side,
                    -1.0,
                    p_minus,
                    ctx.cfg,
                    ctx.sk,
                    ctx.d0,
                    ctx.x_nodes_center,
                    ctx.x0_default,
                    ctx.bounds_nodes,
                    ctx.maxfun_prof,
                    ctx.use_lr,
                    ctx.chi2_min,
                    ctx.delta_chi2,
                    ctx.rmse_thresh_active,
                    ctx.rmse_opt,
                    ctx.sig_t,
                    ctx.sig_r,
                    ctx.sigma_t_f_hetero,
                    ctx.sigma_r_f_hetero,
                    ctx.live_streamer,
                    target_min_span=target_min_span,
                )

                r_plus = _f_plus.result()

                r_minus = _f_minus.result()

        except NUMERICAL_FAULT_EXCEPTIONS:
            log.exception("%s parallel +/-d walks failed - sequential fallback.", _LOG_PREFIX)

            r_plus, r_minus = _run_walks_sequential()

    else:
        r_plus, r_minus = _run_walks_sequential()

    ctx.d_vals.extend(r_plus["d_vals"])

    ctx.d_vals.extend(r_minus["d_vals"])

    ctx.n_curves.extend(r_plus["n_curves"])

    ctx.n_curves.extend(r_minus["n_curves"])

    ctx.k_curves.extend(r_plus["k_curves"])

    ctx.k_curves.extend(r_minus["k_curves"])

    ctx.x_curves.extend(r_plus["x_curves"])

    ctx.x_curves.extend(r_minus["x_curves"])

    ctx.rmse_vals.extend(r_plus["rmse_vals"])

    ctx.rmse_vals.extend(r_minus["rmse_vals"])

    ctx.chi2_vals.extend(r_plus["chi2_vals"])

    ctx.chi2_vals.extend(r_minus["chi2_vals"])

    ctx.fit_nfev_values.extend(r_plus["fit_nfev_values"])

    ctx.fit_nfev_values.extend(r_minus["fit_nfev_values"])

    ctx.fit_nit_values.extend(r_plus["fit_nit_values"])

    ctx.fit_nit_values.extend(r_minus["fit_nit_values"])

    ctx.fit_try_values.extend(r_plus["fit_try_values"])

    ctx.fit_try_values.extend(r_minus["fit_try_values"])

    ctx.fit_fail_values.extend(r_plus["fit_fail_values"])

    ctx.fit_fail_values.extend(r_minus["fit_fail_values"])

    pos_valid = int(r_plus["n_valid_side"])

    neg_valid = int(r_minus["n_valid_side"])

    ctx.boundary_refine_calls = int(r_plus["n_refines"]) + int(r_minus["n_refines"])
    ctx.seed_gate_eval_count = (
        int(r_plus.get("seed_gate_eval_count", 0))
        + int(r_minus.get("seed_gate_eval_count", 0))
        + int(ctx.center_seed_gate_eval_count)
    )
    ctx.seed_gate_kept_count = (
        int(r_plus.get("seed_gate_kept_count", 0))
        + int(r_minus.get("seed_gate_kept_count", 0))
        + int(ctx.center_seed_gate_kept_count)
    )
    ctx.seed_gate_deltas = np.asarray(
        list(np.asarray(r_plus.get("seed_gate_delta_refit_minus_seed", []), dtype=np.float64).ravel())
        + list(np.asarray(r_minus.get("seed_gate_delta_refit_minus_seed", []), dtype=np.float64).ravel())
        + (
            [float(ctx.center_seed_gate_delta_refit_minus_seed)]
            if np.isfinite(float(ctx.center_seed_gate_delta_refit_minus_seed))
            else []
        ),
        dtype=np.float64,
    )

    # P0.3 FIX: Global seed-gate status for corridor quality assessment
    _sg_global_rate = (
        float(ctx.seed_gate_kept_count) / float(ctx.seed_gate_eval_count)
        if int(ctx.seed_gate_eval_count) > 0
        else float("nan")
    )
    ctx.seed_gate_saturated_global = (
        np.isfinite(_sg_global_rate) and _sg_global_rate > 0.5 and int(ctx.seed_gate_eval_count) >= 5
    )
    if ctx.seed_gate_saturated_global:
        log.warning(
            "%s Corridor seed-gate SATURATED (%.0f%% kept > 50%%). "
            "Result may be non-informative (envelope artificially tight). "
            "Consider increasing corridor_profile_d_polish_maxfun or enabling refit_pure_spectral.",
            _LOG_PREFIX,
            100.0 * _sg_global_rate,
        )
    ctx.seed_gate_auto_escalated_global = bool(
        r_plus.get("seed_gate_auto_escalated", False) or r_minus.get("seed_gate_auto_escalated", False)
    )

    min_req = int(max(1, ctx.pconf.min_valid_points))

    if ctx.scientific_nominal:
        min_req = 1

    ctx.min_side = int(max(0, getattr(ctx.pconf, "min_valid_each_side", 0)))

    if len(ctx.d_vals) < min_req:
        if len(ctx.d_vals) >= 1 and ctx.auto_relaxed_alpha:
            log.warning(
                "%s Continuing with %d valid point(s) (< min_valid_points=%d) after automatic RMSE threshold lift "
                "(envelope may be narrow or degenerate).",
                _LOG_PREFIX,
                int(len(ctx.d_vals)),
                min_req,
            )

        else:
            # P1.2 FIX: Detect plateau scenario (RMSE almost flat -> threshold too strict)
            _is_plateau = False
            if len(ctx.d_vals) >= 2 and len(ctx.rmse_vals) >= 2:
                _rmse_arr = np.asarray(ctx.rmse_vals, dtype=np.float64)
                _rmse_mean = float(np.nanmean(_rmse_arr))
                _rmse_std = float(np.nanstd(_rmse_arr))
                _cv = _rmse_std / _rmse_mean if _rmse_mean > 0 else 0.0  # coefficient of variation
                # Plateau: low CV (< 2%) and all points near threshold
                _all_near_thresh = np.all(np.abs(_rmse_arr - ctx.rmse_thresh_active) < 0.01 * ctx.rmse_thresh_active)
                if _cv < 0.02 and _all_near_thresh:
                    _is_plateau = True

            if _is_plateau:
                log.warning(
                    "%s PLATEAU DETECTED: RMSE nearly flat (CV<2%%) with all points near threshold. "
                    "The tolerance is likely too strict for this data. Suggestions: "
                    "(1) Increase rmse_abs_tolerance by ~2x; "
                    "(2) Switch to mode='alpha' with alpha=1.05; "
                    "(3) Enable use_heteroscedastic_sigma=True if noise varies with wavelength; "
                    "(4) Check if data has sufficient spectral contrast for n/k inference. "
                    "Current: %d valid points (min_req=%d), RMSE_mean=%.6f, thresh=%.6f",
                    _LOG_PREFIX,
                    int(len(ctx.d_vals)),
                    min_req,
                    float(_rmse_mean),
                    float(ctx.rmse_thresh_active),
                )
            else:
                log.warning(
                    "%s Abort: too few valid solutions (%d < %d).",
                    _LOG_PREFIX,
                    int(len(ctx.d_vals)),
                    min_req,
                )

            if ctx.log_coaching:
                _log_coaching_corridor_failure(
                    reason="too_few_valid",
                    pconf=ctx.pconf,
                    use_lr=ctx.use_lr,
                    rmse_opt=ctx.rmse_opt,
                    rmse_thresh=ctx.rmse_thresh_active,
                    d0=float(ctx.d0),
                )

            return {"profile_d_status": "failed"}

    if ctx.min_side > 0 and (pos_valid < ctx.min_side or neg_valid < ctx.min_side):
        log.warning(
            "%s Degenerate corridor: valid_side(+d=%d, -d=%d) < min_valid_each_side=%d.",
            _LOG_PREFIX,
            int(pos_valid),
            int(neg_valid),
            int(ctx.min_side),
        )

    ctx = CorridorProfileContext(
        _use_hetero=ctx._use_hetero,
        _user_mask=ctx._user_mask,
        adaptive_abs_meta=ctx.adaptive_abs_meta,
        auto_relaxed_alpha=ctx.auto_relaxed_alpha,
        base_result=ctx.base_result,
        boundary_refine_calls=ctx.boundary_refine_calls,
        center_seed_kept=ctx.center_seed_kept,
        cfg=ctx.cfg,
        chi2_vals=ctx.chi2_vals,
        d0=ctx.d0,
        d_vals=ctx.d_vals,
        delta_chi2=ctx.delta_chi2,
        fit_fail_values=ctx.fit_fail_values,
        fit_nfev_values=ctx.fit_nfev_values,
        fit_nit_values=ctx.fit_nit_values,
        fit_try_values=ctx.fit_try_values,
        k_curves=ctx.k_curves,
        log_coaching=ctx.log_coaching,
        maxfun_prof=ctx.maxfun_prof,
        min_side=ctx.min_side,
        n_curves=ctx.n_curves,
        nom_pack=ctx.nom_pack,
        pconf=ctx.pconf,
        rmse_opt=ctx.rmse_opt,
        rmse_ref_tag=ctx.rmse_ref_tag,
        rmse_thr_sub=ctx.rmse_thr_sub,
        rmse_thresh=ctx.rmse_thresh,
        rmse_thresh_active=ctx.rmse_thresh_active,
        rmse_vals=ctx.rmse_vals,
        scientific_nominal=ctx.scientific_nominal,
        seed_gate_auto_escalated_global=ctx.seed_gate_auto_escalated_global,
        seed_gate_deltas=ctx.seed_gate_deltas,
        seed_gate_eval_count=ctx.seed_gate_eval_count,
        seed_gate_kept_count=ctx.seed_gate_kept_count,
        seed_gate_saturated_global=ctx.seed_gate_saturated_global,
        sig_r=ctx.sig_r,
        sig_t=ctx.sig_t,
        sigma_r_f_hetero=ctx.sigma_r_f_hetero,
        sigma_t_f_hetero=ctx.sigma_t_f_hetero,
        t0=ctx.t0,
        threshold_basis_eff=ctx.threshold_basis_eff,
        threshold_fallback_reason=ctx.threshold_fallback_reason,
        tol_abs=ctx.tol_abs,
        tol_abs_effective=ctx.tol_abs_effective,
        use_abs_delta=ctx.use_abs_delta,
        use_adaptive_abs_delta=ctx.use_adaptive_abs_delta,
        use_lr=ctx.use_lr,
        sk=ctx.sk,
        x_nodes_center=ctx.x_nodes_center,
        x0_default=ctx.x0_default,
        bounds_nodes=ctx.bounds_nodes,
        chi2_min=ctx.chi2_min,
        x_curves=ctx.x_curves,
        corridor_ref_n_lam=ctx.corridor_ref_n_lam,
        corridor_ref_k_lam=ctx.corridor_ref_k_lam,
        _push_live_point_from_payload=ctx._push_live_point_from_payload,
        live_streamer=ctx.live_streamer,
        center_seed_gate_eval_count=ctx.center_seed_gate_eval_count,
        center_seed_gate_kept_count=ctx.center_seed_gate_kept_count,
        center_seed_gate_delta_refit_minus_seed=ctx.center_seed_gate_delta_refit_minus_seed,
    )
    return _package_corridor_results(ctx)
