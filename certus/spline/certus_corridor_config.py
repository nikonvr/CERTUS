from dataclasses import dataclass, field
from typing import *
from pydantic import BaseModel, ConfigDict
import numpy as np
from certus.core.certus_core import *
from certus.spline.certus_index_spline_core import *

import logging

log = logging.getLogger('CERTUS')
_LOG_PREFIX = "INDEX_SPLINE [CORRIDOR EXPLORE]"

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
    # Modified per USER request: force an automatic calculation every 0.5nm.
    step_nm: float = 0.5

    # Adaptive march: initial step, growth factor, step cap.

    step_nm_initial: float = 0.5

    step_growth: float = 1.0

    step_nm_max: float = 0.5

    parabola_half_window_pts: int = 4

    # Force a symmetric reported d-interval even when the accepted sampled points are imbalanced.
    # Modified per USER request: force symmetry.
    force_symmetric_interval: bool = True

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
        from certus.spline.certus_corridor_fitter import _fit_nodes_at_fixed_d
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

        # Speed optimization: if fit0 was successful (converged under maxfun limit), we can skip the polish step.
        # This prevents running a redundant second minimize which halves profiling time when warm-starting.
        if bool(fit0.get("success", False)) or int(fit0.get("nfev", 0)) < int(self.maxfun):
            return fit0

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
