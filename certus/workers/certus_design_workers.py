"""

CERTUS-DESIGN.py - Optical Filter Design & Optimization

=========================================================

"""
from certus.core.certus_core import __version__
import os
from pathlib import Path
import multiprocessing
import sys
import functools
from certus.core.certus_core import create_module_environment
env = create_module_environment(__file__, 'CERTUS_DESIGN')
script_dir = env['script_dir']
import logging
import time
import traceback
import copy
from certus.utils.certus_logging import get_structured_logger
from certus.workers.certus_design_workers_strat import DesignOptimizationStrategy
from certus.workers.certus_design_workers_needle_strat import NeedleOptimizationStrategy
from threading import Event
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg
from certus.ui.certus_qt_widgets import QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QKeySequence, QLabel, QPushButton, QScrollArea, QShortcut, QSpinBox, QSplitter, QStackedWidget, QStatusBar, QStyle, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QThread, QTimer, Qt, QVBoxLayout, QWidget, pyqtSignal
from PyQt6.QtCore import QObject
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, CFG, ensure_numpy_array, get_complex_dtype, get_float_dtype, get_resource_path, certus_timestamp_display, certus_timestamp_file, setup_module_logging
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState, build_progress_callback
from certus.utils.errors import safe_ui_action
from certus.workers.certus_design_worker_utils import build_pglobal_optimizer, build_pglobal_config_from_cfg, optim_backside_flags_from_cfg, optim_bounds_thickness_global, optim_bounds_thickness_healing, optim_bounds_thickness_local, optim_calc_oblique_selected, optim_display_wavelength_grid, optim_oblique_attach_local_positions, optim_oblique_configs_from_groups, optim_oblique_group_targets_on_wavelengths, optim_oblique_unique_display_keys, optim_post_optim_time_budget_seconds, optim_prepare_stack_nk_back, optim_qwot_values_from_ep_stack, optim_rmse_display_string, optim_rmse_is_valid_for_log, optim_var_indices_from_stack, prepare_pglobal_inputs_from_state, prepare_pglobal_optimizer_runtime, run_coord_descent_5cycles, run_pglobal_restart_loop
from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import ColorWorkerRequest, ColorWorkerResult, NeedleWorkerResult, NeedleWorkerRequest, OptimWorkerRequest, OptimWorkerResult
from certus_physics import Layer, Material, ObliqueTarget, PGlobalConfig, PGlobalOptimizer, Target, calc_spectrum_full_oblique_exact, calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized, compute_gradient_all_layers_analytic, compute_oblique_rt_and_grads_analytic, compute_oblique_gradient_contrib_analytic, cost_numba_fast, delta_e_2000, init_thickness, lab_to_rgb, needle_scan_cached, prepare_targets_vectorized, xyz_from_spectrum, xyz_to_lab
from certus.utils.certus_index_utils import spectral_rmse_weights
from certus.ui.certus_ui import CertusTheme, CertusBaseApp, CertusScientificPlot, CertusThemeToggle, CertusCard, CertusCollapsible, CertusStatusPill, install_standard_shortcuts, enable_file_drop, show_toast, EnhancedProgressWidget, FlashyCard, WelcomeGuideWidget, WorkerSignals, certus_get_save_file_name, confirm_stop_with_timeout, copy_app_logs_to_clipboard, create_flashy_grid, create_header_logo_widget, create_top_actions_bar, get_export_config, init_certus_app, open_documentation
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker
from certus.ui.certus_spectrum_eval_ui import spectrum_eval_apply_axes_legend_scale, spectrum_eval_build_worker_cfg, spectrum_eval_on_finished_prepare_display, spectrum_eval_plot_curves, spectrum_eval_run_preamble, spectrum_eval_start_worker
from certus_physics import calc_spectrum_front_wrapper, calc_spectrum_full_wrapper, calc_spectrum_full_exact_wrapper
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full = calc_spectrum_full_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper
# from certus.core.certus_design_core import *  # Unused
from certus.core.certus_design_core import _design_objective_wrapper_common, _design_compute_oblique_error_common, _design_gradient_func_pglobal_common, _design_compute_oblique_error_and_grad_analytic_common, _design_optimization_callback_common

class OptimWorker(QObject):
    """PGLOBAL Optimization Worker"""

    def __init__(self, cfg: dict[str, Any] | OptimWorkerRequest) -> None:
        super().__init__()
        self.design_strat = DesignOptimizationStrategy()
        self.request = cfg if isinstance(cfg, OptimWorkerRequest) else OptimWorkerRequest.from_legacy(cfg)
        self.cfg = dict(self.request.cfg)
        self.signals = WorkerSignals()
        self.on_progress_snapshot = self.signals.progress_snapshot.emit
        self.on_update_stats = self.signals.update_stats.emit
        self.on_result = self.signals.result.emit
        self._stop_event = Event()
        float_dtype = get_float_dtype()
        self._wls_display = optim_display_wavelength_grid(cfg, float_dtype=float_dtype)
        self.best_rmse_seen = float('inf')
        self.best_ep_final = None
        self.best_rmse_final = float('inf')
        self._callback_counter = 0
        self._last_result_emit_time = 0.0
        self._last_live_emit_time = 0.0
        self._progress_snapshot_sent = False

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

    def request_stop(self) -> None:
        self._stop_event.set()

    def _compute_oblique_error(self, ep_test) -> Any:
        return self.design_strat._compute_oblique_error(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return self.design_strat._compute_oblique_error_and_grad_analytic(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return self.design_strat._objective_wrapper(self, x)

    def _gradient_func_pglobal(self, x) -> Any:
        return self.design_strat._gradient_func_pglobal(self, x)

    def _optimization_callback(self, sample) -> Any:
        if not self._progress_snapshot_sent:
            snap = build_progress_snapshot(
                message="Design optimization",
                sub_message="PGLOBAL restart",
                progress_ratio=0.0,
                display_ratio=0.0,
                eta_seconds=None,
                confidence=0.25,
                state=StepState.RUNNING,
                module="DESIGN",
                phase="PGLOBAL",
                metadata={"y": float(getattr(sample, 'y', float('inf')))},
            )
            try:
                self.signals.progress_snapshot.emit(snap)
                self._progress_snapshot_sent = True
            except Exception:
                pass
        return self.design_strat._optimization_callback(self, sample)

    def _run_pre_polish(self, x0_start, var_idx, gradient_func_to_use, objective_wrapper) -> Any:
        return self.design_strat._run_pre_polish(self, x0_start, var_idx, gradient_func_to_use, objective_wrapper)

    def _run_pglobal_setup(self, mode, max_iter_run, dim, objective_wrapper, bounds, pg_conf, x0_start, gradient_func_to_use) -> tuple:
        return self.design_strat._run_pglobal_setup(self, mode, max_iter_run, dim, objective_wrapper, bounds, pg_conf, x0_start, gradient_func_to_use)

    def _run_pglobal_restart_loop(self, *, mode, optimizer, objective_wrapper, bounds, pg_conf, gradient_func_to_use, max_iter_run, callback, opt_start_time) -> Any:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._run_pglobal_restart_loop(self, **kwargs)

    def _evaluate_thicknesses(self, ep_test, *, oblique_mode, compute_oblique_error, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back) -> Any:
        kwargs = locals().copy()
        kwargs.pop('self')
        kwargs.pop('ep_test')
        return self.design_strat._evaluate_thicknesses(self, ep_test, **kwargs)

    def _get_gradient_analytic(self, ep_test, *, oblique_mode, compute_oblique_error_and_grad_analytic, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back, var_idx) -> Any:
        kwargs = locals().copy()
        kwargs.pop('self')
        kwargs.pop('ep_test')
        return self.design_strat._get_gradient_analytic(self, ep_test, **kwargs)

    def _run_coord_descent_5cycles(self, *, ep_current, best_cost, var_idx, oblique_mode, compute_oblique_error, compute_oblique_error_and_grad_analytic, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, has_back_calc, n_back_T, d_back) -> tuple:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._run_coord_descent_5cycles(self, **kwargs)

    def _finalize_and_emit_optimization_result(self, ep_current, best_cost) -> None:
        return self.design_strat._finalize_and_emit_optimization_result(self, ep_current, best_cost)

    def _maybe_upgrade_grid_tikhonravov(self, *, ep_current: np.ndarray, mats: dict, stack, tgts, oblique_mode: bool, oblique_tgts, wls: np.ndarray, float_dtype, complex_dtype, has_back_stack: bool, stack_back, ep_back: np.ndarray, n_sub: np.ndarray, n_layers_T: np.ndarray, n_back_T: np.ndarray, tgt_vals, tgt_weights) -> tuple:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._maybe_upgrade_grid_tikhonravov(self, **kwargs)

    def _build_pglobal_config(self, *, mode: str, dim: int, conv_tol: float) -> tuple[PGlobalConfig, int]:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._build_pglobal_config(self, **kwargs)

    def _initialize_runtime_state_for_optimization(self, *, has_back_calc: bool, has_back_stack: bool, d_back: float, n_back_T: np.ndarray, var_idx: list[int], ep0: np.ndarray, wls: np.ndarray, tgt_vals, tgt_weights, n_layers_T: np.ndarray, n_sub: np.ndarray, oblique_mode: bool, oblique_configs, display_oblique_keys, oblique_tgts, n_lay_T_disp: np.ndarray, n_sub_disp: np.ndarray, n_back_T_disp: np.ndarray) -> None:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._initialize_runtime_state_for_optimization(self, **kwargs)

    def _prepare_optimizer_entry(self, *, ep0: np.ndarray, var_idx: list[int], mode: str, gradient_func_to_use) -> tuple:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._prepare_optimizer_entry(self, **kwargs)

    def _abort_if_no_variable_layers(self, var_idx: list[int]) -> bool:
        """Emit an error and return True when no variable layer is available."""
        if len(var_idx) == 0:
            self.signals.error.emit('No variable layers')
            return True
        return False

    def _emit_best_if_stopped(self) -> bool:
        """Emit best-so-far solution and return True when stop event is raised."""
        if self._stop_event.is_set() and hasattr(self, 'best_ep_final') and (self.best_ep_final is not None):
            self.signals.finished.emit({'ok': True, 'ep': self.best_ep_final, 'rmse': self.best_rmse_final})
            return True
        return False

    def _prepare_pglobal_inputs(self, *, var_idx: list[int], mode: str) -> tuple:
        kwargs = locals().copy()
        kwargs.pop('self')
        return self.design_strat._prepare_pglobal_inputs(self, **kwargs)

    def run(self) -> None:
        """

        Execute the optimization worker thread.

        This method runs the complete optimization workflow including:

        - Spectral evaluation

        - Local and global optimization

        - Target calculationations

        - Result processing

        Args:

            self: OptimWorker instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling

            - Emits progress signals during execution

        """
        try:
            logger = logging.getLogger("CERTUS")
            if hasattr(self.request.trace, "run_id") and self.request.trace.run_id:
                logger = get_structured_logger(
                    logger, 
                    run_context=getattr(self.request, "run_context", None),
                    trace=self.request.trace, 
                    app_id="CERTUS_DESIGN"
                )
            
            initiated_by = getattr(self.request, "initiated_by", "unknown") or "unknown"
            logger.info(f"[OPTIM] Starting optimization worker. Initiated by: {initiated_by}")

            mats = self.cfg['mats']
            stack = self.cfg['stack']
            float_dtype = get_float_dtype()
            complex_dtype = get_complex_dtype()
            ep0 = ensure_numpy_array(self.cfg['ep0'], dtype=float_dtype)
            wls = self.cfg['wls']
            tgts = self.cfg['tgts']
            l0 = self.cfg['l0']
            mode = self.cfg.get('mode', 'global')
            ep_back = ensure_numpy_array(self.cfg.get('ep_back', []), dtype=float_dtype)
            has_back_stack, has_back_calc, stack_back = optim_backside_flags_from_cfg(self.cfg)
            mats_nk, n_sub, n_layers_T, n_back_T, d_back = optim_prepare_stack_nk_back(mats, stack, wls, stack_back=stack_back, ep_back=ep_back, has_back_stack=has_back_stack, complex_dtype=complex_dtype, float_dtype=float_dtype)
            oblique_mode = self.cfg.get('oblique_mode', False)
            oblique_tgts = self.cfg.get('oblique_tgts', [])
            if oblique_mode and has_back_calc and has_back_stack:
                logging.info('[OPTIM] Oblique+backside with back coating: using full oblique exact kernel.')
            elif oblique_mode and has_back_calc:
                logging.info('[OPTIM] Oblique+backside (bare substrate): using oblique backside kernel.')
            if oblique_mode:
                valid_targets = [tgt for tgt in oblique_tgts if tgt.valid()]
                display_oblique_keys = optim_oblique_unique_display_keys(valid_targets)
                config_groups = optim_oblique_group_targets_on_wavelengths(wls, valid_targets)
                oblique_configs = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T)
                optim_oblique_attach_local_positions(oblique_configs)
                for config in oblique_configs:
                    config['sw_cfg'] = spectral_rmse_weights(np.asarray(config['wls_config'], dtype=np.float64))
                tgt_vals = None
                tgt_weights = None
            else:
                self._compute_oblique_error = None
                self._compute_oblique_error_and_grad_analytic = None
                tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
                display_oblique_keys = []
            var_idx = optim_var_indices_from_stack(stack)
            if self._abort_if_no_variable_layers(var_idx):
                return
            float_dtype = get_float_dtype()
            if mode == 'local':
                delta_nm = self.cfg.get('local_delta_nm', 2.0)
                bounds = optim_bounds_thickness_local(ep0, var_idx, delta_nm, float_dtype=float_dtype)
            elif mode == 'healing':
                bounds = optim_bounds_thickness_healing(ep0, var_idx, stack, mats, l0, float_dtype=float_dtype)
            else:
                bounds = optim_bounds_thickness_global(ep0, var_idx, stack, mats, l0, float_dtype=float_dtype)
            complex_dtype = get_complex_dtype()
            _mats_disp, n_sub_disp, n_lay_T_disp, n_back_T_disp, _d_back_disp = optim_prepare_stack_nk_back(mats, stack, self._wls_display, stack_back=stack_back, ep_back=ep_back, has_back_stack=has_back_stack, complex_dtype=complex_dtype, float_dtype=float_dtype)
            self._initialize_runtime_state_for_optimization(has_back_calc=has_back_calc, has_back_stack=has_back_stack, d_back=d_back, n_back_T=n_back_T, var_idx=var_idx, ep0=ep0, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, n_layers_T=n_layers_T, n_sub=n_sub, oblique_mode=oblique_mode, oblique_configs=oblique_configs if oblique_mode else None, display_oblique_keys=display_oblique_keys, oblique_tgts=oblique_tgts, n_lay_T_disp=n_lay_T_disp, n_sub_disp=n_sub_disp, n_back_T_disp=n_back_T_disp)
            dim, gradient_func_to_use, pg_conf, max_iter_run = self._prepare_pglobal_inputs(var_idx=var_idx, mode=mode)
            x0_start, objective_wrapper, callback, compute_oblique_error, compute_oblique_error_and_grad_analytic = self._prepare_optimizer_entry(ep0=ep0, var_idx=var_idx, mode=mode, gradient_func_to_use=gradient_func_to_use)
            optimizer, opt_start_time = self._run_pglobal_setup(mode, max_iter_run, dim, objective_wrapper, bounds, pg_conf, x0_start, gradient_func_to_use)
            pglobal_progress = build_progress_callback(self.signals.progress_snapshot.emit, "DESIGN", "PGLOBAL")
            best_sample_overall = run_pglobal_restart_loop(mode=mode, optimizer=optimizer, objective_wrapper=objective_wrapper, bounds=bounds, pg_conf=pg_conf, gradient_func_to_use=gradient_func_to_use, max_iter_run=max_iter_run, callback=callback, opt_start_time=opt_start_time, stop_event=self._stop_event, progress_emit=pglobal_progress, cfg=self.cfg, callback_counter_getter=lambda: self._callback_counter, set_optimizer=lambda opt: setattr(self, '_optimizer', opt))
            if self._emit_best_if_stopped():
                return
            if best_sample_overall:
                ep_current = ep0.copy()
                ep_current[var_idx] = best_sample_overall.x
                best_cost = best_sample_overall.y
                from certus.workers.certus_design_worker_utils import maybe_upgrade_grid_tikhonravov
                wls, n_sub, n_layers_T, n_back_T, tgt_vals, tgt_weights = maybe_upgrade_grid_tikhonravov(ep_current=ep_current, mats=mats, stack=stack, tgts=tgts, oblique_mode=oblique_mode, oblique_tgts=oblique_tgts, wls=wls, float_dtype=float_dtype, complex_dtype=complex_dtype, has_back_stack=has_back_stack, stack_back=stack_back, ep_back=ep_back, n_sub=n_sub, n_layers_T=n_layers_T, n_back_T=n_back_T, tgt_vals=tgt_vals, tgt_weights=tgt_weights)
                try:
                    self.signals.progress_snapshot.emit(build_progress_snapshot(message='Final refinement (5x coordinate descent)...', display_ratio=0.95, progress_ratio=0.95, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='FINAL_REFINEMENT'))
                except RuntimeError:
                    logging.debug('OptimWorker: signals already deleted, aborting final refinement.')
                    return
                refine_progress = build_progress_callback(self.signals.progress_snapshot.emit, "DESIGN", "FINAL_REFINEMENT")
                ep_current, best_cost, self.best_rmse_seen = run_coord_descent_5cycles(ep_current=ep_current, best_cost=best_cost, var_idx=var_idx, oblique_mode=oblique_mode, compute_oblique_error=compute_oblique_error, compute_oblique_error_and_grad_analytic=compute_oblique_error_and_grad_analytic, n_layers_T=n_layers_T, n_sub=n_sub, wls=wls, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back_calc=has_back_calc, n_back_T=n_back_T, d_back=d_back, cfg=self.cfg, evaluate_thicknesses=self._evaluate_thicknesses, get_gradient_analytic=self._get_gradient_analytic, progress_emit=refine_progress, best_rmse_seen=self.best_rmse_seen)
                self._finalize_and_emit_optimization_result(ep_current, best_cost)
            else:
                self.signals.finished.emit(OptimWorkerResult.failure(
                    trace=self.request.trace,
                ).to_legacy_dict())
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f'Optimization worker error: {e}')
            try:
                self.signals.error.emit(traceback.format_exc())
            except RuntimeError:
                logging.debug('OptimWorker: signals already deleted, skipping error emit.')

class ColorWorker(QObject):
    """Worker for Monte Carlo color analysis"""

    def __init__(self, cfg: dict[str, Any] | ColorWorkerRequest) -> None:
        super().__init__()
        self.request = cfg if isinstance(cfg, ColorWorkerRequest) else ColorWorkerRequest.from_legacy(cfg)
        self.cfg = dict(self.request.cfg)
        self.signals = WorkerSignals()

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

    def _compute_oblique_error(self, ep_test) -> Any:
        return self.color_strat._compute_oblique_error(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return self.color_strat._compute_oblique_error_and_grad_analytic(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return self.color_strat._objective_wrapper(self, x)

    def _gradient_func_pglobal(self, x) -> Any:
        return self.color_strat._gradient_func_pglobal(self, x)

    def _optimization_callback(self, sample) -> Any:
        return self.color_strat._optimization_callback(self, sample)

    def run(self) -> None:
        try:
            float_dtype = get_float_dtype()
            complex_dtype = get_complex_dtype()
            stack = self.request.params.stack
            ep0 = np.array(self.request.params.ep, dtype=float_dtype)
            mats = self.request.params.mats
            n_samples = self.request.params.n if self.request.params.n is not None else 100
            sigma = self.request.params.sigma if self.request.params.sigma is not None else 0.0
            rng_seed = self.request.params.run_seed
            rng = np.random.default_rng(rng_seed)
            wls = np.linspace(380, 780, 81).astype(float_dtype)
            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
            n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)
            n_layers_T = np.ascontiguousarray(n_layers.T)
            _sub_key_c = 'substrate' if 'substrate' in mats_nk else 'Substrate'
            n_sub = np.ascontiguousarray(mats_nk[_sub_key_c])
            _, Rs_nom = calc_spectrum_front(wls, n_layers_T, ep0, n_sub)
            xyz_nom = xyz_from_spectrum(wls, Rs_nom)
            lab_nom = xyz_to_lab(xyz_nom)
            labs = np.empty((n_samples, 3), dtype=np.float64)
            for i in range(n_samples):
                ep_perturbed = ep0 + rng.normal(0, sigma, len(ep0))
                ep_perturbed = np.maximum(ep_perturbed, 0.0)
                _, Rs = calc_spectrum_front(wls, n_layers_T, ep_perturbed, n_sub)
                labs[i] = xyz_to_lab(xyz_from_spectrum(wls, Rs))
                
                if i % max(1, n_samples // 20) == 0:
                    pct = int(100 * i / n_samples)
                    self.signals.progress_snapshot.emit(build_progress_snapshot(message=f"Monte Carlo: {i}/{n_samples}", display_ratio=pct / 100.0, progress_ratio=pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='DESIGN', phase='MONTE_CARLO', metadata={'sample': i, 'total_samples': n_samples}))
            result_payload = ColorWorkerResult.success(
                lab_nom=lab_nom,
                labs=labs,
                run_context=getattr(self.request, "run_context", None),
                trace=self.request.trace,
            )
            self.signals.finished.emit(result_payload.to_legacy_dict())
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f'Color optimization worker error: {e}')
            self.signals.error.emit(traceback.format_exc())

class NeedleWorker(QObject):
    """Worker for layer insertion (Needle algorithm)"""

    def __init__(self, cfg: dict[str, Any] | NeedleWorkerRequest) -> None:
        super().__init__()
        self.needle_strat = NeedleOptimizationStrategy()
        self.request = cfg if isinstance(cfg, NeedleWorkerRequest) else NeedleWorkerRequest.from_legacy(cfg)
        self.cfg = dict(self.request.cfg)
        self.signals = WorkerSignals()

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

    def _compute_oblique_error(self, ep_test) -> Any:
        return self.needle_strat._compute_oblique_error(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return self.needle_strat._compute_oblique_error_and_grad_analytic(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return self.needle_strat._objective_wrapper(self, x)

    def _gradient_func_pglobal(self, x) -> Any:
        return self.needle_strat._gradient_func_pglobal(self, x)

    def _optimization_callback(self, sample) -> Any:
        return self.needle_strat._optimization_callback(self, sample)

    def run(self) -> Any:
        try:
            float_dtype = get_float_dtype()
            complex_dtype = get_complex_dtype()
            stack = self.request.params.stack
            mats = self.request.params.mats
            ep_base = np.array(self.request.params.ep if self.request.params.ep is not None else [], dtype=float_dtype)
            wls = self.request.params.wls if self.request.params.wls is not None else np.array([])
            tgts = self.request.params.tgts if self.request.params.tgts is not None else []
            current_layers = len(stack)
            if current_layers >= CFG.MAX_LAYERS:
                self.signals.finished.emit(NeedleWorkerResult.action_only(
                    'max_layers_reached',
                    trace=self.request.trace,
                ).to_legacy_dict())
                return
            oblique_mode = self.request.params.oblique_mode
            oblique_tgts = self.request.params.oblique_tgts
            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
            _sub_key_n = 'substrate' if 'substrate' in mats_nk else 'Substrate'
            n_sub = np.ascontiguousarray(mats_nk[_sub_key_n])
            
            # Backface extraction
            has_back = self.request.params.has_back
            n_back_T = self.request.params.n_back_T
            d_back = self.request.params.d_back
            if n_back_T is None:
                n_back_T = np.zeros((len(wls), 0), dtype=complex_dtype)
            if d_back is None:
                d_back = np.zeros(0, dtype=float_dtype)
            has_back_stack = n_back_T.shape[1] > 0 and len(d_back) > 0
            n_lay_list = [mats_nk[l.mat] for l in stack]
            if not n_lay_list:
                self.signals.finished.emit(NeedleWorkerResult.action_only(
                    'empty_init',
                    trace=self.request.trace,
                ).to_legacy_dict())
                return
            n_layers_orig = np.array(n_lay_list, dtype=complex_dtype)
            n_layers_T_orig = np.ascontiguousarray(n_layers_orig.T)
            if oblique_mode:
                valid_targets = [tgt for tgt in oblique_tgts if tgt.valid()]
                config_groups = optim_oblique_group_targets_on_wavelengths(wls, valid_targets)
                oblique_configs_needle = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T_orig)
                optim_oblique_attach_local_positions(oblique_configs_needle)

                def compute_oblique_error_needle(ep_test, n_layers_T_test) -> Any:
                    """Calculate oblique mode error - grouped by (angle, pol)"""
                    total_err = 0.0
                    total_wt = 0.0
                    for config in oblique_configs_needle:
                        n_layers_T_config = n_layers_T_test[config['all_clues'], :]
                        R_config, T_config = optim_calc_oblique_selected(config['wls_config'], n_layers_T_config, ep_test, config['n_sub_config'], config['angle'], config['pol'], has_back_calc=has_back, has_back_stack=has_back_stack, d_back=d_back, n_back_T=n_back_T, calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact, calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized)
                        _sw_cfg = spectral_rmse_weights(np.asarray(config['wls_config'], dtype=np.float64))
                        for tgt_data in config['targets']:
                            local_positions = tgt_data['local_positions']
                            if tgt_data['target_type'] == 'R':
                                vals = R_config[local_positions]
                            else:
                                vals = T_config[local_positions]
                            diff = vals - tgt_data['tgt_vals']
                            _sw = _sw_cfg[local_positions]
                            err = np.sum(_sw * diff * diff) * tgt_data['weight']
                            total_err += err
                            total_wt += tgt_data['weight'] * np.sum(_sw)
                    if total_wt < 1e-12:
                        return 1e+30
                    return total_err / total_wt
            else:
                tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
            STEP_NM = 1.0
            PROBE_THICKNESS = 0.01
            best_res = None
            N = len(stack)
            needle_mat_names, scan_mask = self._build_needle_scan_mask(stack, mats_nk)
            use_cached = not oblique_mode and (not has_back)
            if use_cached:
                best_res = self._run_needle_cached_scan(N=N, scan_mask=scan_mask, needle_mat_names=needle_mat_names, mats_nk=mats_nk, complex_dtype=complex_dtype, wls=wls, n_layers_T_orig=n_layers_T_orig, n_sub=n_sub, ep_base=ep_base, tgt_vals=tgt_vals, tgt_weights=tgt_weights, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS, has_back=has_back, n_back_T=n_back_T, d_back=d_back, float_dtype=float_dtype)
            else:
                best_res = self._run_needle_fallback_scan(stack=stack, ep_base=ep_base, n_layers_T_orig=n_layers_T_orig, needle_mat_names=needle_mat_names, mats_nk=mats_nk, float_dtype=float_dtype, wls=wls, oblique_mode=oblique_mode, compute_oblique_error_needle=compute_oblique_error_needle if oblique_mode else None, n_sub=n_sub, tgt_vals=tgt_vals if not oblique_mode else None, tgt_weights=tgt_weights if not oblique_mode else None, has_back=has_back, n_back_T=n_back_T, d_back=d_back, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS)
            if best_res is not None:
                best_res["run_id"] = self.request.trace.run_id  # legacy compat if needed
            result_payload = NeedleWorkerResult.from_legacy(best_res)
            self.signals.finished.emit(result_payload.to_legacy_dict())
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f'Needle optimization worker error: {e}')
            self.signals.error.emit(traceback.format_exc())

    def _run_needle_cached_scan(self, *, N: int, scan_mask: np.ndarray, needle_mat_names: list[str], mats_nk: dict, complex_dtype, wls: np.ndarray, n_layers_T_orig: np.ndarray, n_sub: np.ndarray, ep_base: np.ndarray, tgt_vals: np.ndarray, tgt_weights: np.ndarray, STEP_NM: float, PROBE_THICKNESS: float, has_back: bool, n_back_T: np.ndarray, d_back: np.ndarray, float_dtype) -> dict[str, Any] | None:
        return self.needle_strat._run_needle_cached_scan(self, N=N, scan_mask=scan_mask, needle_mat_names=needle_mat_names, mats_nk=mats_nk, complex_dtype=complex_dtype, wls=wls, n_layers_T_orig=n_layers_T_orig, n_sub=n_sub, ep_base=ep_base, tgt_vals=tgt_vals, tgt_weights=tgt_weights, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS, has_back=has_back, n_back_T=n_back_T, d_back=d_back, float_dtype=float_dtype)

    def _build_needle_scan_mask(self, stack: list, mats_nk: dict) -> tuple[list[str], np.ndarray]:
        return self.needle_strat._build_needle_scan_mask(self, stack, mats_nk)

    def _run_needle_fallback_scan(self, *, stack: list, ep_base: np.ndarray, n_layers_T_orig: np.ndarray, needle_mat_names: list[str], mats_nk: dict, float_dtype, wls: np.ndarray, oblique_mode: bool, compute_oblique_error_needle, n_sub: np.ndarray, tgt_vals, tgt_weights, has_back: bool, n_back_T: np.ndarray, d_back: np.ndarray, STEP_NM: float, PROBE_THICKNESS: float) -> dict[str, Any] | None:
        return self.needle_strat._run_needle_fallback_scan(self, stack=stack, ep_base=ep_base, n_layers_T_orig=n_layers_T_orig, needle_mat_names=needle_mat_names, mats_nk=mats_nk, float_dtype=float_dtype, wls=wls, oblique_mode=oblique_mode, compute_oblique_error_needle=compute_oblique_error_needle, n_sub=n_sub, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back=has_back, n_back_T=n_back_T, d_back=d_back, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS)