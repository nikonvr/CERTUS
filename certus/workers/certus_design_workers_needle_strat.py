import numpy as np
import logging
import time
import math
from copy import deepcopy
from typing import Any, Callable
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, CFG, ensure_numpy_array, get_complex_dtype, get_float_dtype, get_resource_path, certus_timestamp_display, certus_timestamp_file, setup_module_logging
from certus.workers.certus_design_worker_utils import build_pglobal_optimizer, build_pglobal_config_from_cfg, optim_backside_flags_from_cfg, optim_bounds_thickness_global, optim_bounds_thickness_healing, optim_bounds_thickness_local, optim_calc_oblique_selected, optim_display_wavelength_grid, optim_oblique_attach_local_positions, optim_oblique_configs_from_groups, optim_oblique_group_targets_on_wavelengths, optim_oblique_unique_display_keys, optim_post_optim_time_budget_seconds, optim_prepare_stack_nk_back, optim_qwot_values_from_ep_stack, optim_rmse_display_string, optim_rmse_is_valid_for_log, optim_var_indices_from_stack, prepare_pglobal_inputs_from_state, prepare_pglobal_optimizer_runtime, run_coord_descent_5cycles, run_pglobal_restart_loop, maybe_upgrade_grid_tikhonravov
from certus_physics import needle_scan_cached, cost_numba_fast
from certus.core.certus_design_core import (
    _design_compute_oblique_error_common,
    _design_compute_oblique_error_and_grad_analytic_common,
    _design_objective_wrapper_common,
    _design_gradient_func_pglobal_common,
    _design_optimization_callback_common
)

class NeedleOptimizationStrategy:
    @staticmethod
    def _compute_oblique_error(worker, ep_test) -> Any:
        return _design_compute_oblique_error_common(worker, ep_test)

    @staticmethod

    def _compute_oblique_error_and_grad_analytic(worker, ep_test) -> Any:
        return _design_compute_oblique_error_and_grad_analytic_common(worker, ep_test)

    @staticmethod

    def _objective_wrapper(worker, x) -> Any:
        return _design_objective_wrapper_common(worker, x)

    @staticmethod

    def _gradient_func_pglobal(worker, x) -> Any:
        return _design_gradient_func_pglobal_common(worker, x)

    @staticmethod

    def _optimization_callback(worker, sample) -> Any:
        return _design_optimization_callback_common(worker, sample)

    @staticmethod

    def _run_needle_cached_scan(worker, *, N: int, scan_mask: np.ndarray, needle_mat_names: list[str], mats_nk: dict, complex_dtype, wls: np.ndarray, n_layers_T_orig: np.ndarray, n_sub: np.ndarray, ep_base: np.ndarray, tgt_vals: np.ndarray, tgt_weights: np.ndarray, STEP_NM: float, PROBE_THICKNESS: float, has_back: bool, n_back_T: np.ndarray, d_back: np.ndarray, float_dtype) -> dict[str, Any] | None:
        """Run cached needle scan path (normal mode, no backside)."""
        n_needle_arr = np.zeros((N, len(wls)), dtype=complex_dtype)
        for i in range(N):
            if scan_mask[i]:
                n_needle_arr[i] = mats_nk[needle_mat_names[i]]
        n_needle_T = np.ascontiguousarray(n_needle_arr.T)
        best_layer, best_depth, best_cost = needle_scan_cached(wls, n_layers_T_orig, n_needle_T, n_sub, ep_base, tgt_vals, tgt_weights, STEP_NM, PROBE_THICKNESS, scan_mask)
        if best_layer < 0:
            return None
        i = int(best_layer)
        d_layer = float(ep_base[i])
        needle_mat = needle_mat_names[i]
        if d_layer > STEP_NM + 0.1 and needle_mat:
            n_needle_col = mats_nk[needle_mat].reshape(-1, 1)
            n_current_col = n_layers_T_orig[:, i:i + 1]
            mat_left = n_layers_T_orig[:, :i]
            mat_right = n_layers_T_orig[:, i + 1:]
            n_test_T = np.hstack([mat_left, n_current_col, n_needle_col, n_current_col, mat_right])
            n_test_T = np.ascontiguousarray(n_test_T)
            n_base = len(ep_base)
            ep_test = np.empty(n_base + 2, dtype=float_dtype)
            ep_test[:i] = ep_base[:i]
            ep_test[i + 3:] = ep_base[i + 1:]
            ep_test[i + 1] = PROBE_THICKNESS
            refine_step = 0.5
            z_min = max(STEP_NM, float(best_depth) - STEP_NM)
            z_max = min(d_layer - 0.1, float(best_depth) + STEP_NM)
            if z_max > z_min:
                for z in np.arange(z_min, z_max + 0.5 * refine_step, refine_step):
                    d_left = float(z)
                    d_right = d_layer - d_left
                    ep_test[i] = d_left
                    ep_test[i + 2] = d_right
                    c_refined = cost_numba_fast(ep_test, n_test_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, has_back, n_back_T, d_back)
                    if c_refined < best_cost:
                        best_cost = float(c_refined)
                        best_depth = float(d_left)
        return {'action': 'split', 'layer_idx': int(best_layer), 'depth': float(best_depth), 'needle_mat': needle_mat_names[int(best_layer)], 'cost': float(best_cost)}

    @staticmethod

    def _build_needle_scan_mask(worker, stack: list, mats_nk: dict) -> tuple[list[str], np.ndarray]:
        """Build per-layer candidate needle material names and scan mask."""
        excluded_layers = set(worker.cfg.get('excluded_layers', []))
        needle_mat_names = []
        scan_mask = []
        available_mats = list(mats_nk.keys())
        for idx, layer in enumerate(stack):
            mat_name = getattr(layer, 'mat', None)
            if mat_name is None:
                mat_name = layer['mat'] if isinstance(layer, dict) and 'mat' in layer else None
            if mat_name is None:
                continue
            
            mat_name = str(mat_name)
            opp_mat = mat_name
            for m in available_mats:
                if m != mat_name:
                    opp_mat = m
                    break
            
            needle_mat_names.append(opp_mat)
            scan_mask.append(idx not in excluded_layers and opp_mat in mats_nk)
        return (needle_mat_names, np.asarray(scan_mask, dtype=bool))

    @staticmethod

    def _run_needle_fallback_scan(worker, *, stack: list, ep_base: np.ndarray, n_layers_T_orig: np.ndarray, needle_mat_names: list[str], mats_nk: dict, float_dtype, wls: np.ndarray, oblique_mode: bool, compute_oblique_error_needle, n_sub: np.ndarray, tgt_vals, tgt_weights, has_back: bool, n_back_T: np.ndarray, d_back: np.ndarray, STEP_NM: float, PROBE_THICKNESS: float) -> dict[str, Any] | None:
        """Run fallback per-position needle scan (oblique/backside compatible)."""
        best_res = None
        min_cost = float('inf')
        N_layers = len(stack)
        for i, layer in enumerate(stack):
            if worker.isInterruptionRequested():
                return best_res
            
            pct = int(100 * i / max(1, N_layers))
            if hasattr(worker, "signals") and hasattr(worker.signals, "progress"):
                worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Needle scan: layer {i}/{N_layers}", display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='NEEDLE_SCAN', metadata={'layer': i, 'total_layers': N_layers}))

            d_layer = ep_base[i]
            if d_layer < STEP_NM + 0.1:
                continue
            needle_mat = needle_mat_names[i]
            if not needle_mat:
                continue
            n_needle_col = mats_nk[needle_mat].reshape(-1, 1)
            n_current_col = n_layers_T_orig[:, i:i + 1]
            mat_left = n_layers_T_orig[:, :i]
            mat_right = n_layers_T_orig[:, i + 1:]
            n_test_T = np.hstack([mat_left, n_current_col, n_needle_col, n_current_col, mat_right])
            n_test_T = np.ascontiguousarray(n_test_T)
            z_positions = np.arange(STEP_NM, d_layer - 0.1, STEP_NM)
            n_base = len(ep_base)
            ep_test = np.empty(n_base + 2, dtype=float_dtype)
            ep_test[:i] = ep_base[:i]
            ep_test[i + 3:] = ep_base[i + 1:]
            ep_test[i + 1] = PROBE_THICKNESS
            for z in z_positions:
                d_left = z
                d_right = d_layer - z
                ep_test[i] = d_left
                ep_test[i + 2] = d_right
                if oblique_mode:
                    c = compute_oblique_error_needle(ep_test, n_test_T)
                else:
                    c = cost_numba_fast(ep_test, n_test_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, has_back, n_back_T, d_back)
                if c < min_cost:
                    min_cost = c
                    best_res = {'action': 'split', 'layer_idx': i, 'depth': z, 'needle_mat': needle_mat, 'cost': min_cost}
        return best_res

