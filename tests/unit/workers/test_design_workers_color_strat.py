import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from certus.workers.certus_design_workers_color_strat import ColorOptimizationStrategy

class TestColorOptimizationStrategy:
    @pytest.fixture
    def mock_worker(self):
        worker = MagicMock()
        return worker

    @patch('certus.workers.certus_design_workers_color_strat._design_compute_oblique_error_common')
    def test_compute_oblique_error(self, mock_common, mock_worker):
        strat = ColorOptimizationStrategy()
        strat._compute_oblique_error(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_color_strat._design_compute_oblique_error_and_grad_analytic_common')
    def test_compute_oblique_error_and_grad_analytic(self, mock_common, mock_worker):
        strat = ColorOptimizationStrategy()
        strat._compute_oblique_error_and_grad_analytic(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_color_strat._design_objective_wrapper_common')
    def test_objective_wrapper(self, mock_common, mock_worker):
        strat = ColorOptimizationStrategy()
        strat._objective_wrapper(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_color_strat._design_gradient_func_pglobal_common')
    def test_gradient_func_pglobal(self, mock_common, mock_worker):
        strat = ColorOptimizationStrategy()
        strat._gradient_func_pglobal(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_color_strat._design_optimization_callback_common')
    def test_optimization_callback(self, mock_common, mock_worker):
        strat = ColorOptimizationStrategy()
        strat._optimization_callback(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
