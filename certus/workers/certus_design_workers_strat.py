import numpy as np
import logging
import time
import math
from copy import deepcopy
from typing import Any, Callable

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, CFG, ensure_numpy_array, get_complex_dtype, get_float_dtype, get_resource_path, certus_timestamp_display, certus_timestamp_file, setup_module_logging
from certus.workers.certus_design_worker_utils import build_pglobal_optimizer, build_pglobal_config_from_cfg, optim_backside_flags_from_cfg, optim_bounds_thickness_global, optim_bounds_thickness_healing, optim_bounds_thickness_local, optim_calc_oblique_selected, optim_display_wavelength_grid, optim_oblique_attach_local_positions, optim_oblique_configs_from_groups, optim_oblique_group_targets_on_wavelengths, optim_oblique_unique_display_keys, optim_post_optim_time_budget_seconds, optim_prepare_stack_nk_back, optim_qwot_values_from_ep_stack, optim_rmse_display_string, optim_rmse_is_valid_for_log, optim_var_indices_from_stack, prepare_pglobal_inputs_from_state, prepare_pglobal_optimizer_runtime, run_coord_descent_5cycles, run_pglobal_restart_loop, maybe_upgrade_grid_tikhonravov
from certus_physics import cost_numba_fast, compute_gradient_all_layers_analytic, prepare_targets_vectorized, PGlobalConfig
from certus.workers.certus_design_workers_dto import OptimWorkerResult
from certus.utils.certus_progress_tracker import build_progress_callback, build_progress_snapshot, StepState
from certus.core.certus_design_core import (
    _design_compute_oblique_error_common,
    _design_compute_oblique_error_and_grad_analytic_common,
    _design_objective_wrapper_common,
    _design_gradient_func_pglobal_common,
    _design_optimization_callback_common
)

class DesignOptimizationStrategy:
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

    def _run_pre_polish(worker, x0_start, var_idx, gradient_func_to_use, objective_wrapper) -> Any:
        """Run a short local gradient descent before global search.
    
            Performs up to 50 backtracking-line-search iterations starting from
            ``x0_start``, respecting the ``CFG.MIN_THICKNESS`` lower bound and the
            worker stop event. Emits a single ``progress`` start signal, then a
            terminal ``Pre-Polish complete. RMSE: ...`` signal at the end.
    
            Parameters
            ----------
            x0_start : np.ndarray
                Initial point in the variable subspace (length == ``len(var_idx)``).
            var_idx : Sequence[int]
                Index list of optimizable layers (used only to size the bounds clip).
            gradient_func_to_use : Callable
                Returns ``(cost, grad)`` for a candidate point.
            objective_wrapper : Callable
                Returns ``cost`` for a candidate point.
    
            Returns
            -------
            np.ndarray
                Polished starting point (caller-side replacement of ``x0_start``).
            """
        worker.signals.progress_snapshot.emit(build_progress_snapshot(message='Pre-Polish: Running local gradient descent...', display_ratio=0.0, progress_ratio=0.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='PRE_POLISH'))
        can_use_grad = True
        pp_current_x = x0_start.copy()
        pp_current_cost = objective_wrapper(pp_current_x)
        for pp_iter in range(50):
            if worker._stop_event.is_set():
                break
            if can_use_grad:
                c, g = gradient_func_to_use(pp_current_x)
            g_norm = np.linalg.norm(g)
            if g_norm < 1e-08:
                break
            direction = -g / g_norm
            alpha = 1.0
            if pp_iter > 0:
                alpha = 2.0
            improved_step = False
            for _ in range(10):
                x_trial = pp_current_x + alpha * direction
                for i_b, _ in enumerate(var_idx):
                    if x_trial[i_b] < CFG.MIN_THICKNESS:
                        x_trial[i_b] = CFG.MIN_THICKNESS
                c_trial = objective_wrapper(x_trial)
                if c_trial < pp_current_cost:
                    pp_current_x = x_trial
                    pp_current_cost = c_trial
                    improved_step = True
                    break
                alpha *= 0.5
            if not improved_step:
                break
        pp_rmse_str = f'{np.sqrt(pp_current_cost):.6f}' if pp_current_cost < 1e+20 else 'N/A'
        worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f'Pre-Polish complete. RMSE: {pp_rmse_str}', display_ratio=0.0, progress_ratio=0.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='PRE_POLISH', metadata={'rmse': pp_rmse_str}))
        return pp_current_x

    @staticmethod

    def _run_pglobal_setup(worker, mode, max_iter_run, dim, objective_wrapper, bounds, pg_conf, x0_start, gradient_func_to_use) -> tuple:
        """Build and configure the PGlobalOptimizer for the current run.
    
            Creates the optimizer with analytic gradient (L-BFGS-B), stores it on
            ``self._optimizer`` for live introspection, emits the appropriate
            progress message based on ``mode``, captures the start timestamp and
            logs the initial state.
    
            Parameters
            ----------
            mode : str
                Optimization mode: ``'local'``, ``'healing'`` or anything else
                (treated as global).
            max_iter_run : int
                Iteration budget for the run (used for logging only here).
            dim : int
                Problem dimensionality (used for logging only here).
            objective_wrapper, bounds, pg_conf : Any
                Forwarded directly to ``PGlobalOptimizer``.
            x0_start : np.ndarray
                Initial point used to densify sampling around the start design.
            gradient_func_to_use : Callable
                Analytic gradient routine forwarded to L-BFGS-B.
    
            Returns
            -------
            tuple
                ``(optimizer, opt_start_time)`` to be consumed by the restart loop.
            """
        optimizer = build_pglobal_optimizer(objective_wrapper=objective_wrapper, bounds=bounds, stop_event=worker._stop_event, pg_conf=pg_conf, x0_start=x0_start, gradient_func=gradient_func_to_use)
        worker._optimizer = optimizer
        pglobal_progress = build_progress_callback(worker.signals.progress_snapshot.emit, "DESIGN", "PGLOBAL")
        return prepare_pglobal_optimizer_runtime(optimizer=optimizer, mode=mode, max_iter_run=max_iter_run, dim=dim, progress_emit=pglobal_progress, best_rmse_seen=worker.best_rmse_seen, callback_counter=worker._callback_counter)

    @staticmethod

    def _run_pglobal_restart_loop(worker, *, mode, optimizer, objective_wrapper, bounds, pg_conf, gradient_func_to_use, max_iter_run, callback, opt_start_time) -> Any:
        """Run the PGLOBAL auto-restart loop and return the best sample found."""
        pglobal_progress = build_progress_callback(worker.signals.progress_snapshot.emit, "DESIGN", "PGLOBAL")
        return run_pglobal_restart_loop(mode=mode, optimizer=optimizer, objective_wrapper=objective_wrapper, bounds=bounds, pg_conf=pg_conf, gradient_func_to_use=gradient_func_to_use, max_iter_run=max_iter_run, callback=callback, opt_start_time=opt_start_time, stop_event=worker._stop_event, progress_emit=pglobal_progress, cfg=worker.cfg, callback_counter_getter=lambda: worker._callback_counter, set_optimizer=lambda new_optimizer: setattr(worker, '_optimizer', new_optimizer))

    @staticmethod

    def _evaluate_thicknesses(worker, ep_test, *, oblique_mode, compute_oblique_error, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back) -> Any:
        """Evaluate a thickness configuration."""
        if oblique_mode:
            return compute_oblique_error(ep_test)
        return cost_numba_fast(ep_test, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, CFG.MIN_THICKNESS, has_back_calc, n_back_T, d_back)

    @staticmethod

    def _get_gradient_analytic(worker, ep_test, *, oblique_mode, compute_oblique_error_and_grad_analytic, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back, var_idx) -> Any:
        """Compute cost and analytic gradient for refinement."""
        if oblique_mode:
            return compute_oblique_error_and_grad_analytic(ep_test)
        cost, grad = compute_gradient_all_layers_analytic(ep_test, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, CFG.MIN_THICKNESS, has_back_calc, n_back_T, d_back, var_idx)
        return (cost, grad)

    @staticmethod

    def _run_coord_descent_5cycles(worker, *, ep_current, best_cost, var_idx, oblique_mode, compute_oblique_error, compute_oblique_error_and_grad_analytic, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back) -> tuple:
        """Run final 5-cycle coordinate-descent refinement and return updated state."""
        use_gradient = True
        cycle_no_gain = 0
        cycle_rel_gain_min = float(worker.cfg.get('cycle_rel_gain_min', 0.0002))
        cycle_no_gain_patience = int(worker.cfg.get('cycle_no_gain_patience', 1))
        for cycle in range(5):
            if worker._stop_event.is_set():
                break
            cycle_start_best = float(best_cost)
            ep_current.copy()
            float_dtype = get_float_dtype()
            n_vars = len(var_idx)
            steps = np.full(n_vars, 2.0, dtype=float_dtype)
            min_step_val = 0.0001
            min_steps = np.full(n_vars, min_step_val, dtype=float_dtype)
            if use_gradient:
                for _ in range(50):
                    try:
                        cost_curr, grad = worker._get_gradient_analytic(ep_current, oblique_mode=oblique_mode, compute_oblique_error_and_grad_analytic=compute_oblique_error_and_grad_analytic, n_layers_T=n_layers_T, n_sub=n_sub, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back_calc=has_back_calc, n_back_T=n_back_T, d_back=d_back, var_idx=var_idx)
                        if cost_curr < best_cost:
                            best_cost = cost_curr
                        grad_norm = np.linalg.norm(grad)
                        if grad_norm < 1e-08:
                            break
                        direction = -grad / grad_norm
                        alpha = 2.0
                        improved_step = False
                        for _ in range(10):
                            ep_trial = ep_current.copy()
                            for i, v_idx in enumerate(var_idx):
                                ep_trial[v_idx] += alpha * direction[i]
                                ep_trial[v_idx] = max(CFG.MIN_THICKNESS, ep_trial[v_idx])
                            cost_trial = worker._evaluate_thicknesses(ep_trial, oblique_mode=oblique_mode, compute_oblique_error=compute_oblique_error, n_layers_T=n_layers_T, n_sub=n_sub, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back_calc=has_back_calc, n_back_T=n_back_T, d_back=d_back)
                            if cost_trial < best_cost - 1e-08 * alpha * grad_norm:
                                ep_current = ep_trial
                                best_cost = cost_trial
                                improved_step = True
                                break
                            alpha *= 0.5
                        if not improved_step:
                            break
                    except (ValueError, RuntimeError, np.linalg.LinAlgError) as e:
                        logging.debug(f'Gradient optimization failed, fallback to coordinate descent: {e}')
                        use_gradient = False
                        break
            if not use_gradient:
                for _ in range(200):
                    improved = False
                    for i, v_idx in enumerate(var_idx):
                        if steps[i] < min_steps[i]:
                            continue
                        original_val = ep_current[v_idx]
                        step = steps[i]
                        ep_current[v_idx] = original_val + step
                        ep_current[v_idx] = max(CFG.MIN_THICKNESS, ep_current[v_idx])
                        cost_plus = worker._evaluate_thicknesses(ep_current, oblique_mode=oblique_mode, compute_oblique_error=compute_oblique_error, n_layers_T=n_layers_T, n_sub=n_sub, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back_calc=has_back_calc, n_back_T=n_back_T, d_back=d_back)
                        if cost_plus < best_cost:
                            best_cost = cost_plus
                            steps[i] *= 1.2
                            improved = True
                            continue
                        ep_current[v_idx] = original_val - step
                        ep_current[v_idx] = max(CFG.MIN_THICKNESS, ep_current[v_idx])
                        cost_minus = worker._evaluate_thicknesses(ep_current, oblique_mode=oblique_mode, compute_oblique_error=compute_oblique_error, n_layers_T=n_layers_T, n_sub=n_sub, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back_calc=has_back_calc, n_back_T=n_back_T, d_back=d_back)
                        if cost_minus < best_cost:
                            best_cost = cost_minus
                            steps[i] *= 1.2
                            improved = True
                        else:
                            ep_current[v_idx] = original_val
                            steps[i] *= 0.5
                    if not improved:
                        break
            current_rmse = np.sqrt(best_cost) if best_cost < 1e+20 else 1000000000.0
            if current_rmse < worker.best_rmse_seen:
                worker.best_rmse_seen = current_rmse
            worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f'Refine cycle {cycle + 1}/5 - RMSE: {current_rmse:.6f}', display_ratio=(95 + cycle) / 100.0, progress_ratio=(95 + cycle) / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='FINAL_REFINEMENT', metadata={'cycle': cycle + 1, 'rmse': current_rmse}))
            if np.isfinite(cycle_start_best) and np.isfinite(best_cost):
                rel_gain_cycle = (cycle_start_best - best_cost) / max(abs(cycle_start_best), 1e-12)
                if rel_gain_cycle < cycle_rel_gain_min:
                    cycle_no_gain += 1
                else:
                    cycle_no_gain = 0
                if cycle_no_gain > cycle_no_gain_patience:
                    logging.info(f'OptimWorker: final refinement stopped on stagnation ({cycle_no_gain} cycle(s) below {cycle_rel_gain_min * 100:.3f}% gain).')
                    break
        return (ep_current, best_cost)

    @staticmethod

    def _finalize_and_emit_optimization_result(worker, ep_current, best_cost) -> None:
        """Finalize best solution selection and emit success payload."""
        ep_final = ep_current.copy()
        final_rmse = np.sqrt(best_cost) if best_cost < 1e+20 else 1000000000.0
        
        # Compare against the callback's best_rmse_final, not best_rmse_seen
        # (because best_rmse_seen was already updated by coord descent itself)
        callback_best_rmse = getattr(worker, 'best_rmse_final', float('inf'))
        
        if final_rmse <= callback_best_rmse:
            worker.best_rmse_seen = final_rmse
            worker.best_ep_final = ep_final.copy()
            worker.best_rmse_final = final_rmse
        elif hasattr(worker, 'best_ep_final') and worker.best_ep_final is not None:
            ep_final = worker.best_ep_final
            final_rmse = worker.best_rmse_final
            logging.info(f'OptimWorker: Keeping callback best (RMSE={final_rmse:.6e}) over coord descent (RMSE={np.sqrt(best_cost):.6e})')
        else:
            worker.best_ep_final = ep_final.copy()
            worker.best_rmse_final = final_rmse
        result_payload = OptimWorkerResult.success(
            ep=ep_final,
            rmse=float(final_rmse),
            trace=worker.request.trace,
        )
        worker.signals.finished.emit(result_payload.to_legacy_dict())

    @staticmethod

    def _maybe_upgrade_grid_tikhonravov(worker, *, ep_current: np.ndarray, mats: dict, stack, tgts, oblique_mode: bool, oblique_tgts, wls: np.ndarray, float_dtype, complex_dtype, has_back_stack: bool, stack_back, ep_back: np.ndarray, n_sub: np.ndarray, n_layers_T: np.ndarray, n_back_T: np.ndarray, tgt_vals, tgt_weights) -> tuple:
        """Apply optional Tikhonravov-driven wavelength grid densification before final polish."""
        try:
            lambda_min = min((t.lmin for t in tgts if t.valid())) if not oblique_mode else min((t.lmin for t in oblique_tgts if t.valid()))
            lambda_max = max((t.lmax for t in tgts if t.valid())) if not oblique_mode else max((t.lmax for t in oblique_tgts if t.valid()))
            wl_ref = (lambda_min + lambda_max) / 2.0
            L_total = 0.0
            for i, layer in enumerate(stack):
                if i >= len(ep_current):
                    continue
                mat_obj = mats.get(layer.mat)
                if mat_obj:
                    n_ref = mat_obj.get_nk(np.array([wl_ref]))[0].real
                    L_total += n_ref * ep_current[i]
            if L_total > 1e-06 and lambda_max > lambda_min:
                nu_min = 1.0 / lambda_max
                nu_max = 1.0 / lambda_min
                delta_nu = nu_max - nu_min
                marge = 10.0
                N_tikhon = int(np.ceil(2.0 * L_total * delta_nu * marge))
                N_tikhon = max(10, min(5000, N_tikhon))
                current_n_points = len(wls)
                if N_tikhon > current_n_points * 1.15:
                    logging.info(f'Tikhonravov: Upgrading grid from {current_n_points} to {N_tikhon} points for final refinement')
                    active_tgts_for_grid = [t for t in (oblique_tgts if oblique_mode else tgts) if t.valid()]
                    wls_list_new = []
                    for t in active_tgts_for_grid:
                        start = max(t.lmin, 0.001)
                        end = max(t.lmax, start + 0.001)
                        sigma_min = 1.0 / end
                        sigma_max = 1.0 / start
                        sigma_grid = np.linspace(sigma_min, sigma_max, N_tikhon)
                        wls_list_new.append(1.0 / sigma_grid)
                    wls = np.unique(np.concatenate(wls_list_new))
                    wls = np.ascontiguousarray(wls.astype(float_dtype))
                    mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
                    _sub_key = 'substrate' if 'substrate' in mats_nk else 'Substrate'
                    n_sub = np.ascontiguousarray(mats_nk[_sub_key])
                    n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)
                    n_layers_T = np.ascontiguousarray(n_layers.T)
                    if has_back_stack:
                        n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)
                        n_back_T = np.ascontiguousarray(n_back.T)
                    if not oblique_mode:
                        tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
                    else:
                        config_groups = {}
                        for tgt in [t for t in oblique_tgts if t.valid()]:
                            mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)
                            if not np.any(mask):
                                continue
                            key = (tgt.angle, tgt.pol)
                            clues = np.where(mask)[0]
                            if key not in config_groups:
                                config_groups[key] = {'clues_set': set(), 'targets': []}
                            config_groups[key]['clues_set'].update(clues.tolist())
                            wls_tgt = wls[clues]
                            denom = max(tgt.lmax - tgt.lmin, 1e-09)
                            slope = (tgt.tmax - tgt.tmin) / denom
                            tgt_vals_oblique = tgt.tmin + slope * (wls_tgt - tgt.lmin)
                            config_groups[key]['targets'].append({'clues': clues, 'tgt_vals': tgt_vals_oblique, 'target_type': tgt.target_type, 'weight': tgt.w})
                        oblique_configs = []
                        for (angle, pol), group in config_groups.items():
                            all_clues = np.array(sorted(group['clues_set']), dtype=np.int64)
                            idx_to_local = {idx: i for i, idx in enumerate(all_clues)}
                            oblique_configs.append({'angle': angle, 'pol': pol, 'all_clues': all_clues, 'wls_config': wls[all_clues], 'n_sub_config': n_sub[all_clues], 'n_layers_T_config': n_layers_T[all_clues, :], 'idx_to_local': idx_to_local, 'targets': group['targets']})
                        for config in oblique_configs:
                            idx_to_local = config['idx_to_local']
                            for tgt_data in config['targets']:
                                tgt_data['local_positions'] = np.array([idx_to_local[i] for i in tgt_data['clues']], dtype=np.int64)
                    logging.info(f'Tikhonravov: Grid upgraded successfully to {len(wls)} points')
        except NUMERICAL_FAULT_EXCEPTIONS as tikhon_err:
            logging.warning(f'Tikhonravov grid update failed, using original grid: {tikhon_err}')
        return (wls, n_sub, n_layers_T, n_back_T, tgt_vals, tgt_weights)

    @staticmethod

    def _build_pglobal_config(worker, *, mode: str, dim: int, conv_tol: float) -> tuple[PGlobalConfig, int]:
        """Build PGlobal configuration and max iteration budget from mode and dimensions."""
        return build_pglobal_config_from_cfg(cfg=worker.cfg, mode=mode, dim=dim, conv_tol=conv_tol)

    @staticmethod

    def _initialize_runtime_state_for_optimization(worker, *, has_back_calc: bool, has_back_stack: bool, d_back: float, n_back_T: np.ndarray, var_idx: list[int], ep0: np.ndarray, wls: np.ndarray, tgt_vals, tgt_weights, n_layers_T: np.ndarray, n_sub: np.ndarray, oblique_mode: bool, oblique_configs, display_oblique_keys, oblique_tgts, n_lay_T_disp: np.ndarray, n_sub_disp: np.ndarray, n_back_T_disp: np.ndarray) -> None:
        """Store run-time state on ``self`` and perform fixed-layer sanity checks once."""
        all_variable = len(var_idx) == len(ep0)
        worker._has_back_calc = has_back_calc
        worker._has_back_stack = has_back_stack
        worker._d_back = d_back
        worker._n_back_T = n_back_T
        worker._var_idx = var_idx
        worker._ep0 = ep0
        worker._wls = wls
        worker._tgt_vals = tgt_vals
        worker._tgt_weights = tgt_weights
        worker._n_layers_T = n_layers_T
        worker._n_sub = n_sub
        worker._oblique_mode = oblique_mode
        if oblique_configs is not None:
            worker._oblique_configs = oblique_configs
        if display_oblique_keys is not None:
            worker._display_oblique_keys = display_oblique_keys
        if oblique_tgts is not None:
            worker._oblique_tgts = oblique_tgts
        worker._n_lay_T_disp = n_lay_T_disp
        worker._n_sub_disp = n_sub_disp
        worker._n_back_T_disp = n_back_T_disp
        worker._all_variable = all_variable
        worker._ep_buffer = np.array(ep0, dtype=np.float64, copy=True)
        if not all_variable:
            min_thick = CFG.MIN_THICKNESS
            fixed_mask = np.ones(len(ep0), dtype=bool)
            fixed_mask[var_idx] = False
            if np.any((ep0[fixed_mask] > 1e-12) & (ep0[fixed_mask] < min_thick)):
                logging.warning('Fixed layer violates MIN_THICKNESS')
        worker.cost_func = worker._objective_wrapper
        worker._last_cost_func = worker._objective_wrapper

    @staticmethod

    def _prepare_optimizer_entry(worker, *, ep0: np.ndarray, var_idx: list[int], mode: str, gradient_func_to_use) -> tuple:
        """Prepare entry point objects for PGlobal (x0, objective, callback, oblique helpers)."""
        x0_start = ep0[var_idx].copy()
        objective_wrapper = worker._objective_wrapper
        callback = worker._optimization_callback
        compute_oblique_error = worker._compute_oblique_error
        compute_oblique_error_and_grad_analytic = worker._compute_oblique_error_and_grad_analytic
        if worker.cfg.get('pre_polish') and len(var_idx) > 0 and (mode == 'global'):
            x0_start = worker._run_pre_polish(x0_start, var_idx, gradient_func_to_use, objective_wrapper)
        return (x0_start, objective_wrapper, callback, compute_oblique_error, compute_oblique_error_and_grad_analytic)

    @staticmethod

    def _prepare_pglobal_inputs(worker, *, var_idx: list[int], mode: str) -> tuple:
        """Build PGlobal preamble objects and emit initial progress line."""
        from certus.workers.certus_design_worker_utils import prepare_pglobal_inputs_from_state
        pglobal_progress = build_progress_callback(worker.signals.progress_snapshot.emit, "DESIGN", "PGLOBAL")
        return prepare_pglobal_inputs_from_state(var_idx=var_idx, mode=mode, cfg=worker.cfg, signal_emit=pglobal_progress, gradient_func=worker._gradient_func_pglobal)

