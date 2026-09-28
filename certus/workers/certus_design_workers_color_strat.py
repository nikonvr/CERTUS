from typing import Any

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

