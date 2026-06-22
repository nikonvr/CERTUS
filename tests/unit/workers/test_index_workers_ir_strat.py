import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from certus.workers.certus_index_workers_ir_strat import IRGlobalModelStrategy
from certus.utils.certus_index_utils import DataType

class TestIRGlobalModelStrategy:
    @pytest.fixture
    def mock_worker(self):
        worker = MagicMock()
        worker.config = MagicMock()
        worker.config.target_data = pd.DataFrame({'lambda': [500.0, 600.0], 'T': [0.5, 0.5], 'R': [0.5, 0.5]})
        worker.config.lambda_min = 400.0
        worker.config.lambda_max = 800.0
        worker.config.lambda_max_fit = 800.0
        worker.config.exclude_min = None
        worker.config.exclude_max = None
        worker.config.is_frosted_glass = False
        worker.config.use_normalized = False
        worker.config.weight_T = 1.0
        worker.config.weight_R = 1.0
        worker.config.has_absorbing_substrate = False
        worker.config.data_type = DataType.BOTH
        worker.config.substrate_sellmeier_id = 1
        worker.config.n_sub_data = np.array([1.5, 1.5])
        worker.config.k_sub_data = np.array([0.0, 0.0])
        worker.config.is_frosted_glass = False
        worker.config.has_absorbing_substrate = False
        worker.tlu_results = MagicMock()
        worker.tlu_results.optimal_thickness = 100.0
        worker.tlu_results.df_results = pd.DataFrame({'lambda': [500.0, 600.0], 'n_calc': [2.0, 2.0], 'k_calc': [0.1, 0.1]})
        worker.logger = MagicMock()
        worker.error = MagicMock()
        worker.progress = MagicMock()
        worker._stop_event = MagicMock()
        worker.best_mse = 10.0
        return worker

    @patch('certus.workers.certus_index_workers_ir_strat.calculate_bare_substrate_RT')
    @patch('certus.workers.certus_index_workers_ir_strat.calculate_bare_substrate_R')
    def test_prepare_ir_phase2_inputs(self, mock_R, mock_RT, mock_worker):
        strat = IRGlobalModelStrategy()
        mock_RT.return_value = np.array([0.9, 0.9])
        mock_R.return_value = np.array([0.1, 0.1])
        
        l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness = strat._prepare_ir_phase2_inputs(mock_worker)
        assert len(l_full) == 2
        assert thickness == 100.0
        assert target_T is not None
        assert target_R is not None

    @patch('certus.workers.certus_index_workers_ir_strat.fit_sellmeier_global')
    @patch('certus.workers.certus_index_workers_ir_strat.fit_k_global_8p')
    @patch('certus.workers.certus_index_workers_ir_strat.scipy.optimize.minimize')
    @patch('certus.workers.certus_index_workers_ir_strat.PGlobalOptimizerINDEX')
    def test_run_ir_stage0_to_stage2(self, mock_optimizer_cls, mock_minimize, mock_fit_k, mock_fit_sell, mock_worker):
        strat = IRGlobalModelStrategy()
        
        l_full = np.array([500.0, 600.0])
        n_sub_full = np.array([1.5, 1.5])
        df_tlu = mock_worker.tlu_results.df_results
        n_tlu_ref = np.array([2.0, 2.0])
        obj = MagicMock()
        obj.return_value = 1.0 # mock calling the objective
        obj.wl_um = np.array([0.5, 0.6])
        obj.wls = np.array([500.0, 600.0])
        obj.target_T = np.array([0.5, 0.5])
        obj.target_R = np.array([0.5, 0.5])
        obj.n_sub = np.array([1.5, 1.5])
        thickness = 100.0
        
        mock_fit_sell.return_value = (None, np.array([2.0, 1.0, 0.1, 1.0, 0.1]))
        mock_fit_k.return_value = (None, np.array([0.5, -15.0, 0.1, -20.0, 1e-6, 5.0, 1.0, 2.0]))
        
        mock_min_res = MagicMock()
        mock_min_res.fun = 0.5
        mock_min_res.x = np.ones(13)
        mock_min_res.nit = 10
        mock_minimize.return_value = mock_min_res
        
        mock_opt_instance = MagicMock()
        mock_opt_instance.n_evals = 100
        mock_opt_instance.best_x = np.ones(13)
        mock_opt_instance.best_y = 0.1
        
        mock_pg_res = MagicMock()
        mock_pg_res.x = np.ones(13)
        mock_pg_res.y = 0.1
        mock_pg_res.nit = 10
        mock_opt_instance.optimize.return_value = mock_pg_res
        mock_optimizer_cls.return_value = mock_opt_instance
        
        res_pg, opt = strat._run_ir_stage0_to_stage2(mock_worker, mock_worker.config, l_full, n_sub_full, df_tlu, n_tlu_ref, obj, thickness)
        assert res_pg is not None
        assert opt is not None

    @patch('certus.workers.certus_index_workers_ir_strat.scipy.optimize.minimize')
    def test_run_phase21_refinement(self, mock_minimize, mock_worker):
        strat = IRGlobalModelStrategy()
        
        obj = MagicMock()
        obj.wl_um = np.array([0.5, 0.6])
        obj.k_max_guard = 1.0
        
        target_T = np.array([0.5, 0.5])
        k_spline_knots_lambda_um = np.array([0.4, 0.5, 0.6, 0.7])
        k_spline_knots_values = np.array([0.1, 0.1, 0.1, 0.1])
        p_opt_final = np.ones(13)
        res_pg = MagicMock()
        res_pg.x = np.ones(13)
        l_full = np.array([500.0, 600.0])
        thickness = 100.0
        n_sub_full = np.array([1.5, 1.5])
        
        mock_min_res = MagicMock()
        mock_min_res.fun = 0.1
        mock_min_res.x = np.ones(5 + len(k_spline_knots_values))
        mock_minimize.return_value = mock_min_res
        
        n_T, k_T, p_opt_T = strat._run_phase21_refinement(
            mock_worker, mock_worker.config, obj, target_T, k_spline_knots_lambda_um, 
            k_spline_knots_values, p_opt_final, res_pg, l_full, thickness, n_sub_full
        )
        assert n_T is not None
        assert k_T is not None
        assert p_opt_T is not None

    def test_package_results(self, mock_worker):
        strat = IRGlobalModelStrategy()
        
        n = np.array([2.0, 2.0])
        k = np.array([0.1, 0.1])
        thickness = 100.0
        l_full = np.array([500.0, 600.0])
        p_opt = np.ones(13)
        
        mock_worker.config.target_data = pd.DataFrame({'lambda': l_full})
        
        with patch('certus.workers.certus_index_workers_ir_strat._compute_RT_from_config') as mock_compute:
            mock_compute.return_value = (np.array([0.5, 0.5]), np.array([0.5, 0.5]), np.array([0.9, 0.9]))
            res = strat._package_results(mock_worker, n, k, thickness, l_full, p_opt)
            assert res is not None
            assert res.optimal_thickness == 100.0
            assert len(res.df_results) == 2
