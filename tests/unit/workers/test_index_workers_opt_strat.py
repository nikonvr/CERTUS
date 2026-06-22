import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from certus.workers.certus_index_workers_opt_strat import IndexOptimizationStrategy
from certus.core.certus_index_core import OptimizationConfig, DataType

@pytest.fixture
def mock_worker():
    worker = MagicMock()
    worker.logger = MagicMock()
    worker.progress = MagicMock()
    worker.best_params = np.ones(7)
    worker.best_mse = 100.0
    
    config = MagicMock(spec=OptimizationConfig)
    config.thickness_min = 10.0
    config.thickness_max = 100.0
    config.lambda_min = 400.0
    config.lambda_max = 800.0
    config.use_normalized = False
    config.weight_T = 1.0
    config.weight_R = 1.0
    config.is_frosted_glass = False
    config.has_absorbing_substrate = False
    config.k_sub_data = None
    config.substrate_thickness_nm = 1000000.0
    config.data_type = DataType.BOTH
    config.lambda_max_fit = None
    config.exclude_min = None
    config.exclude_max = None
    worker.config = config
    
    worker._finalize_if_stopped.return_value = False
    worker._stop_event = MagicMock()
    worker.thickness_initial = 50.0
    
    return worker

class TestIndexOptimizationStrategy:
    @patch('certus.workers.certus_index_workers_opt_strat.scipy.optimize.minimize')
    @patch('certus.workers.certus_index_workers_opt_strat.TLUObjective')
    def test_run_subset_optim(self, mock_obj_cls, mock_minimize, mock_worker):
        strat = IndexOptimizationStrategy()
        
        mock_obj_inst = MagicMock()
        mock_obj_inst.get_bounds.return_value = np.array([[10.0, 100.0]] * 7)
        mock_obj_inst.return_value = 0.5
        mock_obj_cls.return_value = mock_obj_inst
        
        mock_res1 = MagicMock()
        mock_res1.x = np.ones(7) * 2.0
        mock_res1.fun = 0.4
        
        mock_res2 = MagicMock()
        mock_res2.x = np.ones(7) * 3.0
        mock_res2.fun = 0.6
        
        mock_minimize.side_effect = [mock_res1, mock_res2]
        
        clues_slice = slice(0, 2)
        wls = np.array([400.0, 500.0])
        n_sub = np.array([1.5, 1.5])
        target_T = np.array([0.5, 0.5])
        target_R = np.array([0.5, 0.5])
        exclude_range = None
        
        result = strat._run_subset_optim(mock_worker, clues_slice, wls, n_sub, target_T, target_R, exclude_range)
        assert result is not None
        assert np.array_equal(result, mock_res1.x)
        assert mock_minimize.call_count == 2
        
    @patch('certus.workers.certus_index_workers_opt_strat._get_substrate_n_array_index')
    @patch('certus.workers.certus_index_workers_opt_strat.TLUObjective')
    def test_prepare_run_inputs(self, mock_obj_cls, mock_get_sub, mock_worker):
        strat = IndexOptimizationStrategy()
        
        import pandas as pd
        mock_worker.config.target_data = pd.DataFrame({
            'lambda': [400.0, 500.0],
            'T': [0.5, 0.5],
            'R': [0.5, 0.5]
        })
        mock_worker.config.substrate = "Mock Substrate"
        mock_worker.config.substrate_sellmeier_id = 1
        mock_worker.config.n_sub_data = None
        mock_worker.config.exclude_min = None
        mock_worker.config.exclude_max = None
        
        mock_get_sub.return_value = np.array([1.5, 1.5])
        mock_obj_cls.return_value = MagicMock()
        
        res = strat._prepare_run_inputs(mock_worker, mock_worker.config)
        assert len(res) == 6
        assert len(res[0]) == 2 # wls
        
    @patch('certus.workers.certus_index_workers_opt_strat.scipy.optimize.minimize')
    def test_run_phase5_final_optimization(self, mock_minimize, mock_worker):
        strat = IndexOptimizationStrategy()
        
        obj = MagicMock()
        obj.get_bounds.return_value = np.array([[10.0, 100.0]] * 7)
        obj.return_value = 0.5 # For the manual call inside the method
        
        mock_res1 = MagicMock()
        mock_res1.x = np.ones(7) * 2.0
        mock_res1.fun = 0.4
        
        mock_res2 = MagicMock()
        mock_res2.x = np.ones(7) * 3.0
        mock_res2.fun = 0.6
        
        mock_minimize.side_effect = [mock_res1, mock_res2]
        
        params_list = [np.ones(7), np.ones(7)]
        strat._run_phase5_final_optimization(mock_worker, obj, params_list)
        
        assert mock_worker.best_mse == 0.4
        
    @patch('certus.workers.certus_index_workers_opt_strat.estimate_initial_params')
    @patch('certus.workers.certus_index_workers_opt_strat.PGlobalOptimizerINDEX')
    def test_run_phase1_global_search(self, mock_opt_cls, mock_est, mock_worker):
        strat = IndexOptimizationStrategy()
        
        obj = MagicMock()
        obj.get_bounds.return_value = np.array([[10.0, 100.0]] * 7)
        obj.return_value = 0.5
        obj.format_diag_line.return_value = "diag"
        obj.format_k_line.return_value = "k"
        
        mock_est.return_value = np.ones(7)
        
        mock_opt = MagicMock()
        mock_opt.n_evals = 100
        mock_best = MagicMock()
        mock_best.x = np.ones(7) * 2.0
        mock_best.y = 0.1
        mock_opt.optimize.return_value = mock_best
        mock_opt_cls.return_value = mock_opt
        
        wls = np.array([400.0, 500.0])
        n_sub = np.array([1.5, 1.5])
        target_T = np.array([0.5, 0.5])
        
        mock_worker.config.high_precision = False
        mock_worker.config.random_seed = None
        
        res = strat._run_phase1_global_search(mock_worker, mock_worker.config, obj, wls, target_T, n_sub)
        
        assert res is False # Should return False if not stopped early
        assert mock_worker.best_mse == 0.1
