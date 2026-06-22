import pytest
import numpy as np
from unittest.mock import MagicMock
from certus.workers.certus_design_workers_strat import DesignOptimizationStrategy
from certus.core.certus_core import CFG

class TestDesignOptimizationStrategy:
    @pytest.fixture
    def mock_worker(self):
        worker = MagicMock()
        worker.isInterruptionRequested.return_value = False
        worker._stop_event.is_set.return_value = False
        worker.cfg = {'MIN_THICKNESS': 1.0, 'MAX_THICKNESS': 1000.0, 'pre_polish': False, 'coord_descent': False, 'tikhonravov_grid_upgrade': False, 'cycle_rel_gain_min': 0.0002, 'cycle_no_gain_patience': 1}
        worker._wls = np.array([500.0, 600.0])
        worker._ep_buffer = np.array([50.0, 50.0])
        worker._var_idx = [0, 1]
        worker.best_mse = 100.0
        worker.best_rmse_seen = 100.0
        worker.best_rmse_final = float('inf')
        worker.best_ep_final = None
        worker.best_params = [np.array([50.0, 50.0])]
        worker._callback_counter = 0
        worker._get_gradient_analytic.return_value = (5.0, np.array([0.1, 0.1]))
        worker._evaluate_thicknesses.return_value = 5.0
        
        class Signals:
            progress = MagicMock()
            progress_snapshot = MagicMock()
            result = MagicMock()
            live = MagicMock()
            finished = MagicMock()
        worker.signals = Signals()
        return worker

    def test_run_pre_polish_no_improvement(self, mock_worker):
        strat = DesignOptimizationStrategy()
        x0_start = np.array([50.0, 50.0])
        var_idx = [0, 1]
        
        def mock_grad(x):
            return np.array([0.1, 0.1])
            
        def mock_obj(x):
            return np.sum(x**2)
            
        res = strat._run_pre_polish(mock_worker, x0_start, var_idx, mock_grad, mock_obj)
        assert len(res) == 2
        mock_worker.signals.progress_snapshot.emit.assert_called()

    def test_run_pglobal_setup(self, mock_worker):
        strat = DesignOptimizationStrategy()
        def mock_obj(x):
            return np.sum(x**2)
            
        bounds = [(1.0, 1000.0), (1.0, 1000.0)]
        pg_conf = MagicMock()
        pg_conf.pop_size = 10
        pg_conf.mutation_rate = 0.5
        pg_conf.mutation_strategy = "rand/1"
        pg_conf.recombination_rate = 0.5
        pg_conf.tol = 1e-4
        
        opt, start_time = strat._run_pglobal_setup(
            mock_worker, mode="global", max_iter_run=100, dim=2,
            objective_wrapper=mock_obj, bounds=bounds, pg_conf=pg_conf,
            x0_start=np.array([50.0, 50.0]), gradient_func_to_use=None
        )
        assert opt is not None
        assert start_time > 0

    def test_evaluate_thicknesses(self, mock_worker):
        strat = DesignOptimizationStrategy()
        ep_test = np.array([10.0, 20.0])
        
        def mock_compute_oblique_error(ep):
            return 0.5
            
        err = strat._evaluate_thicknesses(
            mock_worker, ep_test, oblique_mode=True, compute_oblique_error=mock_compute_oblique_error,
            n_layers_T=None, n_sub=None, wls=None, tgt_vals=None, tgt_weights=None,
            has_back_calc=False, n_back_T=None, d_back=None
        )
        assert err == 0.5

    def test_get_gradient_analytic(self, mock_worker):
        strat = DesignOptimizationStrategy()
        ep_test = np.array([10.0, 20.0])
        var_idx = [0, 1]
        
        def mock_compute_oblique_error_and_grad_analytic(ep):
            return 0.5, np.array([0.1, 0.2])
            
        err, grad = strat._get_gradient_analytic(
            mock_worker, ep_test, oblique_mode=True, compute_oblique_error_and_grad_analytic=mock_compute_oblique_error_and_grad_analytic,
            n_layers_T=None, n_sub=None, wls=None, tgt_vals=None, tgt_weights=None,
            has_back_calc=False, n_back_T=None, d_back=None, var_idx=var_idx
        )
        assert err == 0.5
        assert np.allclose(grad, [0.1, 0.2])

    def test_run_coord_descent_5cycles(self, mock_worker):
        strat = DesignOptimizationStrategy()
        ep_current = np.array([50.0, 50.0])
        best_cost = 10.0
        var_idx = [0, 1]
        
        def mock_compute_oblique_error(ep):
            return 5.0
            
        def mock_compute_oblique_error_and_grad_analytic(ep):
            return 5.0, np.array([0.1, 0.1])
            
        ep_new, cost_new = strat._run_coord_descent_5cycles(
            mock_worker, ep_current=ep_current, best_cost=best_cost, var_idx=var_idx,
            oblique_mode=True, compute_oblique_error=mock_compute_oblique_error,
            compute_oblique_error_and_grad_analytic=mock_compute_oblique_error_and_grad_analytic,
            n_layers_T=None, n_sub=None, wls=None, tgt_vals=None, tgt_weights=None,
            has_back_calc=False, n_back_T=None, d_back=None
        )
        assert len(ep_new) == 2
        assert cost_new <= best_cost

    def test_finalize_and_emit_optimization_result(self, mock_worker):
        strat = DesignOptimizationStrategy()
        strat._finalize_and_emit_optimization_result(mock_worker, np.array([50.0]), 1.0)
        mock_worker.signals.finished.emit.assert_called_once()
