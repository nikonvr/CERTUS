import numpy as np
import logging
import time
import math
from copy import deepcopy
from typing import Any, Callable

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, CFG, ensure_numpy_array, get_complex_dtype, get_float_dtype, get_resource_path, certus_timestamp_display, certus_timestamp_file, setup_module_logging
from certus.workers.certus_design_worker_utils import build_pglobal_optimizer, build_pglobal_config_from_cfg, optim_backside_flags_from_cfg, optim_bounds_thickness_global, optim_bounds_thickness_healing, optim_bounds_thickness_local, optim_calc_oblique_selected, optim_display_wavelength_grid, optim_oblique_attach_local_positions, optim_oblique_configs_from_groups, optim_oblique_group_targets_on_wavelengths, optim_oblique_unique_display_keys, optim_post_optim_time_budget_seconds, optim_prepare_stack_nk_back, optim_qwot_values_from_ep_stack, optim_rmse_display_string, optim_rmse_is_valid_for_log, optim_var_indices_from_stack, prepare_pglobal_inputs_from_state, prepare_pglobal_optimizer_runtime, run_coord_descent_5cycles, run_pglobal_restart_loop, maybe_upgrade_grid_tikhonravov
# from certus.core.certus_design_core import *  # Unused
from certus.core.certus_design_core import (
    _design_compute_oblique_error_common,
    _design_compute_oblique_error_and_grad_analytic_common,
    _design_objective_wrapper_common,
    _design_gradient_func_pglobal_common,
    _design_optimization_callback_common
)

class ColorOptimizationStrategy:
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

