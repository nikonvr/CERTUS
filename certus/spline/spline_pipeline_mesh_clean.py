from __future__ import annotations
from .spline_pipeline_utils import (
    _WorkerProgressCoordinator,
    _log_manual_insert_decision,
    _spl_rmse_improves_meaningfully,
    _spl_rmse_regression_exceeds_tolerance,
    _validated_extra_sigma_knots,
    _should_skip_manual_insert_for_equal_mesh,
    _sigma_knot_difference_for_log,
    _sigma_knots_to_lambda_nm_for_log,
    _format_lambda_knots_nm_for_log,
    _sigma_mesh_change_summary_for_log,
    _knots_cache_key,
    _fmt_d_nm,
    _meshes_match,
    _candidate_mesh_matches_target,
    _pipeline_mesh_dimensions,
    _log_worker_start_payload,
    _log_final_insert_enter,
    _log_after_final_insert,
    _log_fixed_mesh_stage_summary,
    _log_after_final_stage_summary,
    _emit_enter_fixed_mesh_stage,
    _sync_theoretical_tr_from_nk_dict,
    _stop_with_snapshot_if_requested,
    enforce_local_optimization_policy,
)
from .spline_pipeline_mesh_insert import (
    insert_manual_sigma_nodes,
    insert_mwir_mid_sigma_node,
    worker_spline_mwir_insert_node,
    worker_spline_manual_sigma_insert,
    worker_spline_auto_add_one_knot,
    _sensitivity_rank_inner_indices,
    _build_local_pull_variants,
    _build_local_refine_variants,
)

"""Main spline pipeline: JSON logging, RMSE snapshots, worker orchestration."""
import copy as _copy
from certus.utils.certus_copy_utils import copy_spline_result
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
import logging
from dataclasses import dataclass
import time
from threading import Event
from typing import Any, Callable
import numpy as np
from scipy.interpolate import PchipInterpolator
from certus.spline.certus_index_spline_core import (
    K_MIN_PHYS,
    SplineOptConfig,
    _canonical_knots_min_lambda_kw,
    canonical_spline_sigma_knots,
    corridor_profile_refit_maxfun,
    _bounds_x0_for_sigma_knots,
    _log_index_spline_best_config,
    log_index_spline_d_trace,
    _log_spline_pipeline_json,
    _reflectance_absolute_backside_from_nk,
    apply_rmse_fit_window_nk_nan_to_result,
    enforce_k_floor_on_nodes,
    snapshot_result_with_rmse_fit_meta,
    x_slice_n_to_physical_nodes,
    physical_nodes_to_x_slice_n,
)
from certus.utils.certus_index_utils import (
    _ratio_theoretical_from_nk,
    _reflectance_ratio_theoretical_from_nk,
    _sorted_finite_sigma_knots as _sorted_finite_sigma_knots_for_log,
    _transmittance_absolute_from_nk,
)
from certus_physics import (
    clip_to_bounds,
)
from certus.spline.spline_objective import (
    build_segment_optimizer_x_vector,
    build_spline_objective_masked_grid,
    spectral_mse_rmse_masked_from_nk,
    spline_objective_mse_on_masked_grid,
)
from certus.spline.spline_finalize import (
    _collect_post_s3_candidates,
    _finalize_spectral_rmse_mesh_polish_and_best,
    _log_skipped_knot_insertion_fixed_mesh,
    _select_final_scientific_candidate,
    _spectral_polish_node_mesh_profile,
)
from certus.spline.certus_corridor_config import ProfileCorridorConfig
from certus.spline.spline_profile_corridors import compute_profiled_corridors_by_d
from certus.spline.certus_corridor_utils import widen_corridor_envelope_to_include_nk_in_result
from certus.spline.certus_corridor_logger import (
    log_coaching_corridor_pipeline_skip_empty,
    log_coaching_uncertainty_parameter_guide,
)


@dataclass
class AutoCleanKnotsContext:
    tolerance: float
    nominal_rmse: float
    progress_cb: Any | None
    progress_units_total: int
    progress_units_done: int

    def emit_progress(self, units_inc: int, message: str) -> None:
        if self.progress_cb is None:
            return
        self.progress_units_done = int(
            min(self.progress_units_total, self.progress_units_done + max(int(units_inc), 0))
        )
        pct = 99.0 * (float(self.progress_units_done) / float(max(self.progress_units_total, 1)))
        self.progress_cb(float(np.clip(pct, 0.0, 99.0)), str(message))

    def decisive_improvement_margin(self) -> float:
        return float(max(5.0e-6, 0.25 * float(max(self.tolerance, 0.0))))

    def have_decisive_local_candidate(self, rmse_value: float) -> bool:
        return bool(np.isfinite(rmse_value) and rmse_value <= (self.nominal_rmse - self.decisive_improvement_margin()))


def _auto_clean_cache_result(
    cache: dict,
    cache_key: tuple[float, ...],
    cand: dict | None,
    rmse_value: float,
) -> tuple[dict | None, float]:
    payload = (cand, float(rmse_value))
    cache[cache_key] = payload
    return payload


def _auto_clean_prescreen_result(
    *,
    log: "logging.Logger",
    cache: dict,
    cache_key: tuple[float, ...],
    cand: dict,
    rmse_value: float,
    test_knots: np.ndarray,
    nominal_rmse: float,
    tolerance: float,
    prescreen_margin_abs: float,
    candidate_polish_maxfun: int,
    prescreen_maxfun: int,
) -> tuple[dict | None, float] | None:
    k_sz = int(np.asarray(test_knots, dtype=np.float64).size)
    if not np.isfinite(rmse_value):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] prescreen produced non-finite RMSE | K=%d", k_sz)
        return _auto_clean_cache_result(cache, cache_key, None, float("inf"))
    if not _candidate_mesh_matches_target(cand, test_knots):
        log.warning(
            "INDEX_SPLINE [AUTO_CLEAN] prescreen returned inconsistent mesh | K_target=%d | rmse_fast=%.8f",
            k_sz,
            float(rmse_value),
        )
        return _auto_clean_cache_result(cache, cache_key, None, rmse_value)
    gate = float(nominal_rmse + tolerance + prescreen_margin_abs)
    if rmse_value > gate:
        log.debug(
            "INDEX_SPLINE [AUTO_CLEAN] prescreen rejected variant | K=%d | rmse_fast=%.8f | gate=%.8f",
            k_sz,
            float(rmse_value),
            float(gate),
        )
        return _auto_clean_cache_result(cache, cache_key, None, rmse_value)
    if int(candidate_polish_maxfun) <= int(prescreen_maxfun):
        return _auto_clean_cache_result(cache, cache_key, cand, rmse_value)
    return None


def _eval_clean_variant(
    test_knots: np.ndarray,
    stop_event,
    step_eval_cache: dict,
    cfg_prescreen,
    cfg_candidate,
    best_result_out: dict,
    nominal_rmse: float,
    tolerance: float,
    prescreen_enabled: bool,
    prescreen_margin_abs: float,
    candidate_polish_maxfun: int,
    prescreen_maxfun: int,
    log: "logging.Logger",
) -> tuple[dict | None, float]:
    """Evaluate a single knot-removal variant with optional prescreen + full polish.

    Returns (result_dict_or_None, rmse).
    """
    if stop_event.is_set():
        return None, float("inf")

    cache_key = _knots_cache_key(test_knots)
    cached = step_eval_cache.get(cache_key)
    if cached is not None:
        return cached

    warm_seed = best_result_out
    if prescreen_enabled:
        cand_fast = insert_manual_sigma_nodes(
            cfg_prescreen,
            best_result_out,
            stop_event,
            np.asarray([], dtype=np.float64),
            target_sigma_knots=test_knots,
            force_reopt=True,
            live_cb=None,
        )
        rmse_fast = float(cand_fast.get("rmse", float("inf")))
        prescreen_out = _auto_clean_prescreen_result(
            log=log,
            cache=step_eval_cache,
            cache_key=cache_key,
            cand=cand_fast,
            rmse_value=rmse_fast,
            test_knots=test_knots,
            nominal_rmse=nominal_rmse,
            tolerance=tolerance,
            prescreen_margin_abs=prescreen_margin_abs,
            candidate_polish_maxfun=candidate_polish_maxfun,
            prescreen_maxfun=prescreen_maxfun,
        )
        if prescreen_out is not None:
            return prescreen_out
        if int(candidate_polish_maxfun) > int(prescreen_maxfun):
            warm_seed = cand_fast

    cand = insert_manual_sigma_nodes(
        cfg_candidate,
        warm_seed,
        stop_event,
        np.asarray([], dtype=np.float64),
        target_sigma_knots=test_knots,
        force_reopt=True,
        live_cb=None,
    )
    rmse_cand = float(cand.get("rmse", float("inf")))
    if not np.isfinite(rmse_cand):
        log.warning(
            "INDEX_SPLINE [AUTO_CLEAN] candidate polish produced non-finite RMSE | K=%d",
            int(np.asarray(test_knots, dtype=np.float64).size),
        )
    if not _candidate_mesh_matches_target(cand, test_knots):
        log.warning(
            "INDEX_SPLINE [AUTO_CLEAN] candidate polish returned inconsistent mesh | K_target=%d | rmse=%.8f",
            int(np.asarray(test_knots, dtype=np.float64).size),
            float(rmse_cand),
        )
        return _auto_clean_cache_result(step_eval_cache, cache_key, None, rmse_cand)
    log.debug(
        "INDEX_SPLINE [AUTO_CLEAN] candidate polish done | K=%d | rmse=%.8f | delta_nominal=%+.8f | within_tol=%s",
        int(np.asarray(test_knots, dtype=np.float64).size),
        float(rmse_cand),
        float(rmse_cand - nominal_rmse) if np.isfinite(rmse_cand) else float("nan"),
        str(rmse_cand <= nominal_rmse + tolerance) if np.isfinite(rmse_cand) else "n/a",
    )
    return _auto_clean_cache_result(step_eval_cache, cache_key, cand, rmse_cand)


def worker_spline_auto_clean_knots(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    target_sigma_knots: np.ndarray,
    tolerance: float,
    force_clean: bool = False,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: iteratively remove the least sensitive knots until RMSE degrades by more than tolerance."""

    log = logging.getLogger("CERTUS")
    step_eval_cache: dict[tuple[float, ...], tuple[dict[str, Any] | None, float]] = {}

    pull_enabled = bool(getattr(cfg, "auto_clean_neighbor_pull_enabled", True))
    pull_ratios_raw = getattr(cfg, "auto_clean_neighbor_pull_ratios", (0.20,))
    pull_ratios: list[float] = []
    if pull_enabled:
        try:
            for rr in np.asarray(pull_ratios_raw, dtype=np.float64).ravel():
                rv = float(rr)
                if np.isfinite(rv) and 0.0 < rv < 0.49:
                    pull_ratios.append(rv)
        except ValueError, TypeError:
            pull_ratios = [0.20]
        if not pull_ratios:
            pull_ratios = [0.20]

    strict_tol_mode = bool(float(tolerance) <= 1e-12)

    # Conditional local refinement around the best per-removal variant.
    # We exclusively respect the user's choice (GUI checkbox). The
    # forced deactivation in strict mode was masking valid removals.
    local_refine_enabled = bool(getattr(cfg, "auto_clean_neighbor_pull_local_refine_enabled", False))
    local_refine_rel_step = float(getattr(cfg, "auto_clean_neighbor_pull_local_refine_rel_step", 0.05) or 0.05)
    local_refine_rel_step = float(np.clip(local_refine_rel_step, 0.005, 0.20))

    # Performance knobs (absolute acceptance criterion remains unchanged).
    candidate_polish_maxfun = int(max(120, int(getattr(cfg, "auto_clean_candidate_polish_maxfun", 2000) or 2000)))
    prescreen_enabled = bool(getattr(cfg, "auto_clean_candidate_prescreen_enabled", True))
    prescreen_maxfun = int(max(80, int(getattr(cfg, "auto_clean_candidate_prescreen_maxfun", 120) or 120)))
    prescreen_margin_default = 0.0 if strict_tol_mode else max(2.0e-4, 2.0 * float(max(tolerance, 0.0)))
    prescreen_margin_abs = float(
        getattr(cfg, "auto_clean_candidate_prescreen_margin_abs", prescreen_margin_default) or prescreen_margin_default
    )
    if not np.isfinite(prescreen_margin_abs) or prescreen_margin_abs < 0.0:
        prescreen_margin_abs = float(prescreen_margin_default)

    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] start | tolerance=+%.6f | strict_mode=%s | neighbor_pull=%s | pull_ratios=%s | local_refine=%s(step=%.4f) | prescreen=%s(maxfun=%d, margin=+%.6f) | candidate_maxfun=%d",
        float(tolerance),
        "on" if strict_tol_mode else "off",
        "on" if pull_enabled else "off",
        ",".join(f"{r:.3f}" for r in pull_ratios) if pull_enabled else "n/a",
        "on" if (pull_enabled and local_refine_enabled) else "off",
        float(local_refine_rel_step),
        "on" if prescreen_enabled else "off",
        int(prescreen_maxfun),
        float(prescreen_margin_abs),
        int(candidate_polish_maxfun),
    )

    current_result = copy_spline_result(base_result)
    current_knots = np.sort(target_sigma_knots)
    if current_knots.size >= 2:
        _diff = np.diff(current_knots)
        if np.any(_diff <= 0.0):
            log.warning(
                "INDEX_SPLINE [AUTO_CLEAN] target mesh has non-strict spacing | K=%d | min_gap=%+.3e",
                int(current_knots.size),
                float(np.min(_diff)) if _diff.size else float("nan"),
            )
        lam_pos = ", ".join(f"{1.0/max(s, 1e-30):.1f}" for s in current_knots)
        log.info(
            "INDEX_SPLINE [AUTO_CLEAN] target mesh summary | K_target=%d | sigma_min=%.8e | sigma_max=%.8e | span=%.8e\n    Lambda positions (nm): %s",
            int(current_knots.size),
            float(current_knots[0]),
            float(current_knots[-1]),
            float(current_knots[-1] - current_knots[0]),
            lam_pos,
        )

    if progress_cb:
        progress_cb(0.0, "Cleaning: calculating nominal RMSE...")

    nominal_result = insert_manual_sigma_nodes(
        cfg,
        current_result,
        stop_event,
        np.asarray([], dtype=np.float64),
        target_sigma_knots=current_knots,
        force_reopt=True,
        live_cb=live_cb,
    )
    if stop_event.is_set():
        return None

    nominal_rmse = float(nominal_result.get("rmse", float("inf")))
    if not np.isfinite(nominal_rmse):
        log.warning("INDEX_SPLINE [AUTO_CLEAN] abort: nominal RMSE is non-finite.")
        return None
    _d_nom = nominal_result.get("d_nm", float("nan"))
    try:
        _d_nom_f = float(_d_nom)
    except TypeError, ValueError:
        _d_nom_f = float("nan")
    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] nominal reference | K=%d | RMSE=%.8f | d=%s",
        int(current_knots.size),
        float(nominal_rmse),
        f"{_d_nom_f:.3f} nm" if np.isfinite(_d_nom_f) else "n/a",
    )

    best_result_out = nominal_result
    active_knots = current_knots.copy()
    cfg_candidate = cfg.replace(manual_node_insert_polish_maxfun=int(candidate_polish_maxfun))
    cfg_prescreen = cfg.replace(manual_node_insert_polish_maxfun=int(min(candidate_polish_maxfun, prescreen_maxfun)))

    # Build a conservative work budget so progress can move during long iterative tests.
    initial_k = int(max(active_knots.size, 0))
    max_pull_variants = 1 + (3 * len(pull_ratios) if pull_enabled else 0)
    max_refine_variants = 8 if (pull_enabled and local_refine_enabled) else 0
    progress_units_total = 1  # nominal RMSE initialization
    for kk in range(initial_k, 2, -1):
        n_removed_candidates = max(0, kk - 2)
        progress_units_total += n_removed_candidates * (max_pull_variants + max_refine_variants)
        progress_units_total += 1  # validation deep polish slot per step

    ctx = AutoCleanKnotsContext(
        tolerance=tolerance,
        nominal_rmse=nominal_rmse,
        progress_cb=progress_cb,
        progress_units_total=progress_units_total,
        progress_units_done=1,
    )

    step = 0
    while True:
        if stop_event.is_set():
            break
        K = active_knots.size
        if K <= 2:
            break
        step_eval_cache.clear()
        log.info(
            "INDEX_SPLINE [AUTO_CLEAN] step=%d start | K=%d | nominal_rmse=%.8f | acceptance_rmse<=%.8f",
            int(step + 1),
            int(K),
            float(nominal_rmse),
            float(nominal_rmse + tolerance),
        )

        best_cand_rmse = float("inf")
        best_cand_result = None
        best_cand_knots = None
        best_cand_variant = "baseline"

        top_n_sensitivity = int(max(1, int(getattr(cfg, "auto_clean_top_n_sensitivity", 4) or 4)))
        inner_indices = list(range(1, K - 1))

        if len(inner_indices) > top_n_sensitivity:
            inner_indices = _sensitivity_rank_inner_indices(
                cfg,
                active_knots,
                best_result_out,
                K,
                inner_indices,
                top_n_sensitivity,
                tolerance,
                strict_tol_mode,
                log,
                step,
            )

        for i in inner_indices:
            if stop_event.is_set():
                break

            variants = _build_local_pull_variants(active_knots, i, pull_enabled, pull_ratios)
            log.debug(
                "INDEX_SPLINE [AUTO_CLEAN] step=%d evaluating removal idx=%d/%d | variants=%d",
                int(step + 1),
                int(i),
                int(K - 2),
                int(len(variants)),
            )
            local_best_rmse = float("inf")
            local_best_knots = None
            local_best_variant = "baseline"

            def _update_best_candidate(vname: str, tk: np.ndarray, is_refine: bool = False) -> float:
                nonlocal best_cand_rmse, best_cand_result, best_cand_knots, best_cand_variant
                nonlocal local_best_rmse, local_best_knots, local_best_variant

                cand, cand_rmse = _eval_clean_variant(
                    tk,
                    stop_event,
                    step_eval_cache,
                    cfg_prescreen,
                    cfg_candidate,
                    best_result_out,
                    nominal_rmse,
                    tolerance,
                    prescreen_enabled,
                    prescreen_margin_abs,
                    candidate_polish_maxfun,
                    prescreen_maxfun,
                    log,
                )
                if cand is not None:
                    if cand_rmse < best_cand_rmse:
                        best_cand_rmse = cand_rmse
                        best_cand_result = cand
                        best_cand_knots = tk
                        best_cand_variant = str(vname)
                    if cand_rmse < local_best_rmse:
                        local_best_rmse = cand_rmse
                        local_best_knots = tk
                        local_best_variant = str(vname)
                else:
                    gate = float(nominal_rmse + tolerance + prescreen_margin_abs)
                    if is_refine:
                        kind_str = f"refine_variant={vname}"
                    elif vname == "baseline":
                        kind_str = "baseline"
                    else:
                        kind_str = f"variant={vname}"

                    if np.isfinite(cand_rmse):
                        log.debug(
                            "INDEX_SPLINE [AUTO_CLEAN] step=%d idx=%d %s rejected before polish | rmse_fast=%.8f | gate=%.8f",
                            int(step + 1),
                            int(i),
                            kind_str,
                            float(cand_rmse),
                            float(gate),
                        )
                    else:
                        log.debug(
                            "INDEX_SPLINE [AUTO_CLEAN] step=%d idx=%d %s failed/non-finite",
                            int(step + 1),
                            int(i),
                            kind_str,
                        )
                return cand_rmse

            # 1. Evaluate baseline first (always variants[0])
            baseline_name, baseline_knots = variants[0]
            ctx.emit_progress(1, f"Step {step + 1}: testing knot removal {i}/{K - 2} [{baseline_name}]...")
            baseline_rmse = _update_best_candidate(baseline_name, baseline_knots)

            # Early-exit: if baseline already improves RMSE by more than a full tolerance
            # margin, pull-variants cannot change the final outcome meaningfully.
            if baseline_name == "baseline" and np.isfinite(baseline_rmse) and baseline_rmse < nominal_rmse - tolerance:
                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d knot=%d early-exit (baseline rmse=%.8f << nominal-tol %.8f)",
                    int(step + 1),
                    int(i),
                    float(baseline_rmse),
                    float(nominal_rmse - tolerance),
                )
            else:
                # 2. Evaluate remaining pull-variants sequentially.
                # This avoids a backlog of stale computations that would continue running
                # even after a clearly better candidate has already been found.
                remaining_variants = variants[1:]
                if (
                    remaining_variants
                    and not stop_event.is_set()
                    and not ctx.have_decisive_local_candidate(local_best_rmse)
                ):
                    for vname, tk in remaining_variants:
                        if stop_event.is_set() or ctx.have_decisive_local_candidate(local_best_rmse):
                            break
                        ctx.emit_progress(1, f"Step {step + 1}: testing knot removal {i}/{K - 2} [{vname}]...")
                        try:
                            _update_best_candidate(vname, tk)
                        except (ValueError, TypeError, RuntimeError) as e:
                            log.debug("INDEX_SPLINE [AUTO_CLEAN] variant %s failed: %s", vname, e)

            # Conditional local 2D refinement around local best for this removed index.
            refine_trigger = np.isfinite(local_best_rmse) and (
                (local_best_rmse <= nominal_rmse + tolerance) or (local_best_rmse <= nominal_rmse + 1.25 * tolerance)
            )
            if (
                refine_trigger
                and local_best_knots is not None
                and not stop_event.is_set()
                and not ctx.have_decisive_local_candidate(local_best_rmse)
            ):
                refine_variants = _build_local_refine_variants(
                    active_knots,
                    i,
                    local_best_knots,
                    pull_enabled,
                    local_refine_enabled,
                    local_refine_rel_step,
                )
                if refine_variants:
                    for vname, tk in refine_variants:
                        if stop_event.is_set() or ctx.have_decisive_local_candidate(local_best_rmse):
                            break
                        ctx.emit_progress(1, f"Step {step + 1}: 2D refinement [{vname}]...")
                        try:
                            _update_best_candidate(vname, tk, is_refine=True)
                        except (ValueError, TypeError, RuntimeError) as e:
                            log.debug("INDEX_SPLINE [AUTO_CLEAN] refine variant %s failed: %s", vname, e)

                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] local refine summary | step=%d | removed_idx=%d | best_variant=%s | local_rmse=%.8f",
                    int(step + 1),
                    int(i),
                    str(local_best_variant),
                    float(local_best_rmse),
                )
            else:
                log.debug(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d removed_idx=%d local refine skipped | trigger=%s | have_seed=%s",
                    int(step + 1),
                    int(i),
                    str(refine_trigger),
                    str(local_best_knots is not None),
                )

        if stop_event.is_set():
            break

        if not np.isfinite(best_cand_rmse):
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] stop: no finite candidate at step=%d | K=%d",
                int(step + 1),
                int(K),
            )
            if progress_cb:
                progress_cb(-1, "Cleaning finished: no finite candidate found for knot removal.")
            break

        if best_cand_rmse <= nominal_rmse + tolerance or force_clean:
            # The selected candidate is already a fully polished K-1 solution.
            # Re-running the exact same target mesh creates redundant 05b work and stale
            # follow-up jobs without improving the acceptance guarantee meaningfully.
            ctx.emit_progress(1, f"Accepting best removal [{best_cand_variant}]...")
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] step=%d candidate accepted for validation | variant=%s | K_before=%d -> K_after=%d | rmse_candidate=%.8f | nominal=%.8f | delta=%+.8f | force_clean=%s",
                int(step + 1),
                str(best_cand_variant),
                int(K),
                int(best_cand_knots.size) if best_cand_knots is not None else -1,
                float(best_cand_rmse),
                float(nominal_rmse),
                float(best_cand_rmse - nominal_rmse),
                str(force_clean),
            )
            final_cand = best_cand_result if best_cand_result is not None else None
            final_rmse = float(best_cand_rmse)
            d_prev = _fmt_d_nm(best_result_out.get("d_nm"))
            d_new = _fmt_d_nm(final_cand.get("d_nm")) if isinstance(final_cand, dict) else "n/a"

            final_mesh_ok = _candidate_mesh_matches_target(final_cand, np.asarray(best_cand_knots, dtype=np.float64))

            if final_cand is not None and final_mesh_ok and (final_rmse <= nominal_rmse + tolerance or force_clean):
                active_knots = np.asarray(best_cand_knots, dtype=np.float64).ravel().copy()
                best_result_out = final_cand
                if live_cb is not None:
                    live_cb(best_result_out)
                step += 1
                lam_pos = ", ".join(f"{1.0/max(s, 1e-30):.1f}" for s in active_knots)
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d accepted | variant=%s | K=%d | RMSE=%.8f | nominal_delta=%+.8f | force_clean=%s\n    Lambda positions (nm): %s",
                    int(step),
                    str(best_cand_variant),
                    int(active_knots.size),
                    float(final_rmse),
                    float(final_rmse - nominal_rmse),
                    str(force_clean),
                    lam_pos,
                )
                if progress_cb:
                    progress_cb(
                        -1,
                        f"Knot removed! [{best_cand_variant}] K={active_knots.size}. RMSE={final_rmse:.6f} (+{final_rmse - nominal_rmse:.6f}) | d: {d_prev} -> {d_new}",
                    )
                if force_clean:
                    break
            else:
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] step=%d rejected after final consistency check | variant=%s | mesh_ok=%s | RMSE=%.8f | nominal_delta=%+.8f | tolerance=+%.8f | force_clean=%s",
                    int(step + 1),
                    str(best_cand_variant),
                    str(final_mesh_ok),
                    float(final_rmse),
                    float(final_rmse - nominal_rmse),
                    float(tolerance),
                    str(force_clean),
                )
                if progress_cb:
                    progress_cb(
                        -1,
                        f"Cleaning finished: removal rejected at final consistency check (mesh mismatch or +{final_rmse - nominal_rmse:.6f} > tolerance) | d: {d_prev} -> {d_new}.",
                    )
                break
        else:
            log.info(
                "INDEX_SPLINE [AUTO_CLEAN] stop: best candidate exceeds tolerance | step=%d | best_variant=%s | best_delta=%+.8f | tolerance=+%.8f",
                int(step + 1),
                str(best_cand_variant),
                float(best_cand_rmse - nominal_rmse),
                float(tolerance),
            )
            if progress_cb:
                progress_cb(
                    -1, f"Cleaning finished: best candidate exceeds tolerance (+{best_cand_rmse - nominal_rmse:.6f})."
                )
            break

    # --- Final deep re-polish of cleaned mesh (full budget, mirrors local re-opt button) ---
    if step > 0 and not stop_event.is_set():
        final_deep_maxfun = int(
            max(
                candidate_polish_maxfun + 1,
                int(
                    getattr(cfg, "auto_clean_final_polish_maxfun", None)
                    or int(getattr(cfg, "polish_maxfun", 8000) or 8000)
                ),
            )
        )
        if final_deep_maxfun > candidate_polish_maxfun:
            if progress_cb:
                progress_cb(99.0, f"Deep re-polish of final mesh K={active_knots.size} (maxfun={final_deep_maxfun})...")
            cfg_final_deep = cfg.replace(manual_node_insert_polish_maxfun=final_deep_maxfun)
            final_knots = active_knots.copy()
            deep_final = insert_manual_sigma_nodes(
                cfg_final_deep,
                copy_spline_result(best_result_out),
                stop_event,
                np.asarray([], dtype=np.float64),
                target_sigma_knots=final_knots,
                force_reopt=True,
                live_cb=live_cb,
            )
            if not stop_event.is_set():
                deep_final_rmse = float(deep_final.get("rmse", float("inf")))
                _rmse_before_deep = float(best_result_out.get("rmse", float("nan")))
                log.info(
                    "INDEX_SPLINE [AUTO_CLEAN] final deep re-polish | K=%d | RMSE %.8f -> %.8f | delta=%+.8f",
                    int(final_knots.size),
                    float(_rmse_before_deep),
                    float(deep_final_rmse),
                    float(deep_final_rmse - _rmse_before_deep),
                )
                if np.isfinite(deep_final_rmse):
                    best_result_out = deep_final
                    if live_cb is not None:
                        live_cb(best_result_out)

    was_canceled = bool(stop_event.is_set())
    if progress_cb:
        if was_canceled:
            progress_cb(
                -1,
                f"Advanced cleaning canceled. K={active_knots.size} | RMSE={float(best_result_out.get('rmse', 0)):.6f}",
            )
        else:
            progress_cb(
                100.0,
                f"Advanced cleaning finished. K={active_knots.size} | RMSE={float(best_result_out.get('rmse', 0)):.6f}",
            )

    log.info(
        "INDEX_SPLINE [AUTO_CLEAN] done | canceled=%s | steps=%d | K_final=%d | RMSE_final=%.8f | RMSE_nominal=%.8f | delta_nominal=%+.8f",
        str(was_canceled),
        int(step),
        int(active_knots.size),
        float(best_result_out.get("rmse", float("nan"))),
        float(nominal_rmse),
        float(best_result_out.get("rmse", float("nan")) - nominal_rmse)
        if np.isfinite(float(best_result_out.get("rmse", float("nan"))))
        else float("nan"),
    )

    return best_result_out


def worker_spline_autoshift_delta_ns(
    base_result: dict,
    cfg: SplineOptConfig,
    stop_event: Event,
    *,
    target_sigma_knots: np.ndarray | None = None,
    progress_cb=None,
    live_cb=None,
) -> dict | None:
    """Standalone worker: find optimal delta_ns in [-0.01, 0.01] with Brent search.

    The worker first probes five evenly spaced points to build a valid local
    bracket, then refines the best minimum with ``scipy.optimize.minimize_scalar``
    using ``method=\"brent\"``. Each candidate receives an independent deep copy
    of ``base_result`` so ``insert_manual_sigma_nodes`` cannot corrupt the seed
    for subsequent evaluations.
    """

    log = logging.getLogger("CERTUS")

    n_sub_base = np.asarray(base_result.get("n_sub_base", cfg.n_sub), dtype=np.float64).ravel().copy()

    # --- helpers --------------------------------------------------------
    def _try_shift(d_ns: float, maxfun_override: int | None = None) -> tuple[dict | None, float]:
        """Run a full polish at *d_ns* and return (result, rmse)."""
        seed = copy_spline_result(base_result)  # isolation totale

        cfg_args = {
            "substrate_n_offset": d_ns,
            "substrate_n_base": n_sub_base.copy(),
            "n_sub": n_sub_base + d_ns,
        }
        if maxfun_override is not None:
            cfg_args["manual_node_insert_polish_maxfun"] = maxfun_override

        cfg_cand = cfg.replace(**cfg_args)

        try:
            cand = insert_manual_sigma_nodes(
                cfg_cand,
                seed,
                stop_event,
                np.asarray([], dtype=np.float64),
                target_sigma_knots=target_sigma_knots,
                force_reopt=True,
                progress_cb=None,
                live_cb=live_cb,
            )
        except (ValueError, TypeError, RuntimeError) as ex:
            log.warning("INDEX_SPLINE [AUTOSHIFT] cand %+.4f failed: %s", d_ns, ex)
            return None, float("inf")
        r = float(cand.get("rmse", float("inf")))
        return cand, r

    # --- 1D Brent search for optimal delta_ns ---
    from scipy.optimize import minimize_scalar

    best_result_out = copy_spline_result(base_result)
    best_rmse = float(best_result_out.get("rmse", float("inf")))
    best_dns = 0.0
    tested: dict[float, tuple[dict | None, float]] = {}
    eval_count = [0]
    max_brent_evals = 18

    def _f_for_brent(d_ns: float) -> float:
        if stop_event.is_set():
            return float("inf")
        d_key = round(float(d_ns), 6)
        if d_key in tested:
            return tested[d_key][1]
        cand, r = _try_shift(d_key, maxfun_override=1000)
        tested[d_key] = (cand, r)
        eval_count[0] += 1
        nonlocal best_result_out, best_rmse, best_dns
        if cand is not None and np.isfinite(r) and r < best_rmse - 1e-8:
            best_rmse = r
            best_result_out = cand
            best_dns = d_key
            log.info("INDEX_SPLINE [AUTOSHIFT] brent improved: dns=%+.6f RMSE=%.8f", d_key, r)
        if progress_cb:
            pct = 90.0 * float(min(eval_count[0], max_brent_evals)) / float(max_brent_evals)
            progress_cb(float(np.clip(pct, 0.0, 89.0)), f"Autoshift Brent eval {eval_count[0]} : delta_ns={d_key:+.6f}")
        return float(r) if np.isfinite(r) else float("inf")

    # Initial bracketing: 5 evenly spaced points to identify (a, b, c) with f(b) = min.
    bracket_pts = np.linspace(-0.01, 0.01, 5)
    for d_ns in bracket_pts:
        if stop_event.is_set():
            break
        _f_for_brent(float(d_ns))

    if not stop_event.is_set():
        finite_pts = sorted(
            ((d, tested[d][1]) for d in tested if np.isfinite(tested[d][1])),
            key=lambda t: t[0],
        )
        # Looks for a triplet bracketing a strict minimum.
        best_triplet = None
        for i in range(1, len(finite_pts) - 1):
            a, fa = finite_pts[i - 1]
            b, fb = finite_pts[i]
            c, fc = finite_pts[i + 1]
            if fb <= fa and fb <= fc:
                best_triplet = (a, b, c)
                break
        if best_triplet is not None:
            try:
                res = minimize_scalar(
                    _f_for_brent,
                    bracket=best_triplet,
                    method="brent",
                    options={"xtol": 5e-4, "maxiter": max_brent_evals},
                )
                log.info(
                    "INDEX_SPLINE [AUTOSHIFT] brent done | x=%+.6f | fun=%.8f | nit=%d",
                    float(res.x),
                    float(res.fun),
                    int(res.nit),
                )
            except (ValueError, RuntimeError) as ex:
                log.warning("INDEX_SPLINE [AUTOSHIFT] brent failed, fallback to grid best: %s", ex)
        else:
            log.info("INDEX_SPLINE [AUTOSHIFT] no strict bracket, keep grid best dns=%+.6f", best_dns)

    # --- Final deep reoptimization at the best delta ns ---
    if progress_cb:
        progress_cb(90.0, f"Autoshift: final deep re-optimization on delta ns = {best_dns:+.6f}...")

    final_cand, final_rmse = _try_shift(best_dns, maxfun_override=40000)
    if final_cand is not None and np.isfinite(final_rmse):
        best_result_out = final_cand
        best_rmse = final_rmse

    if progress_cb:
        progress_cb(100.0, f"Autoshift finished. Best shift: {best_dns:+.6f} | RMSE={best_rmse:.8f}")

    log.info(
        "INDEX_SPLINE [AUTOSHIFT] DONE | best_dns=%+.6f | best_rmse=%.8f",
        best_dns,
        best_rmse,
    )
    return best_result_out
