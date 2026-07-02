import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from certus.workers.certus_design_workers_needle_strat import NeedleOptimizationStrategy

class TestNeedleOptimizationStrategy:
    @pytest.fixture
    def mock_worker(self):
        worker = MagicMock()
        worker.isInterruptionRequested.return_value = False
        worker.cfg = {'excluded_layers': [0]}
        return worker

    def test_build_needle_scan_mask(self, mock_worker):
        strat = NeedleOptimizationStrategy()
        
        stack = [
            {'mat': 'TiO2'},  # excluded by index 0
            {'mat': 'SiO2'},  # not excluded, in mats
            {'mat': 'Unknown'}, # not excluded, but not in mats
            {}                # no mat
        ]
        mats_nk = {'TiO2': np.array([2.0]), 'SiO2': np.array([1.5])}
        
        names, mask = strat._build_needle_scan_mask(mock_worker, stack, mats_nk)
        assert names == ['SiO2', 'TiO2', 'TiO2']
        assert len(mask) == 3
        assert not mask[0]  # idx 0 excluded
        assert mask[1]  # idx 1 in mats
        assert mask[2]  # idx 2 opposite mat 'TiO2' is in mats

    @patch('certus.workers.certus_design_workers_needle_strat.needle_scan_cached')
    @patch('certus.workers.certus_design_workers_needle_strat.cost_numba_fast')
    def test_run_needle_cached_scan(self, mock_cost, mock_scan, mock_worker):
        strat = NeedleOptimizationStrategy()
        
        N = 2
        scan_mask = np.array([True, False])
        needle_mat_names = ['TiO2', 'SiO2']
        mats_nk = {'TiO2': np.array([2.0]), 'SiO2': np.array([1.5])}
        complex_dtype = np.complex128
        float_dtype = np.float64
        wls = np.array([500.0])
        n_layers_T_orig = np.array([[2.0, 1.5]])
        n_sub = np.array([1.52])
        ep_base = np.array([50.0, 50.0])
        tgt_vals = np.array([0.5])
        tgt_weights = np.array([1.0])
        STEP_NM = 1.0
        PROBE_THICKNESS = 1.0
        has_back = False
        n_back_T = np.array([])
        d_back = np.array([])
        
        # Scenario 1: scan returns no improvement
        mock_scan.return_value = (-1, 0.0, 0.0)
        res = strat._run_needle_cached_scan(
            mock_worker, N=N, scan_mask=scan_mask, needle_mat_names=needle_mat_names,
            mats_nk=mats_nk, complex_dtype=complex_dtype, wls=wls,
            n_layers_T_orig=n_layers_T_orig, n_sub=n_sub, ep_base=ep_base,
            tgt_vals=tgt_vals, tgt_weights=tgt_weights, STEP_NM=STEP_NM,
            PROBE_THICKNESS=PROBE_THICKNESS, has_back=has_back, n_back_T=n_back_T,
            d_back=d_back, float_dtype=float_dtype
        )
        assert res is None
        
        # Scenario 2: scan returns improvement, refinement is run
        mock_scan.return_value = (0, 25.0, 10.0) # layer 0, depth 25.0, cost 10.0
        mock_cost.return_value = 5.0 # refinement cost
        
        res2 = strat._run_needle_cached_scan(
            mock_worker, N=N, scan_mask=scan_mask, needle_mat_names=needle_mat_names,
            mats_nk=mats_nk, complex_dtype=complex_dtype, wls=wls,
            n_layers_T_orig=n_layers_T_orig, n_sub=n_sub, ep_base=ep_base,
            tgt_vals=tgt_vals, tgt_weights=tgt_weights, STEP_NM=STEP_NM,
            PROBE_THICKNESS=PROBE_THICKNESS, has_back=has_back, n_back_T=n_back_T,
            d_back=d_back, float_dtype=float_dtype
        )
        assert res2 is not None
        assert res2['action'] == 'split'
        assert res2['layer_idx'] == 0
        assert res2['cost'] == 5.0

    @patch('certus.workers.certus_design_workers_needle_strat.cost_numba_fast')
    def test_run_needle_fallback_scan(self, mock_cost, mock_worker):
        strat = NeedleOptimizationStrategy()
        
        stack = [{'mat': 'TiO2'}, {'mat': 'SiO2'}]
        ep_base = np.array([50.0, 50.0])
        n_layers_T_orig = np.array([[2.0, 1.5]])
        needle_mat_names = ['TiO2', 'SiO2']
        mats_nk = {'TiO2': np.array([2.0]), 'SiO2': np.array([1.5])}
        float_dtype = np.float64
        wls = np.array([500.0])
        n_sub = np.array([1.52])
        tgt_vals = np.array([0.5])
        tgt_weights = np.array([1.0])
        has_back = False
        n_back_T = np.array([])
        d_back = np.array([])
        STEP_NM = 20.0
        PROBE_THICKNESS = 1.0
        
        # Test oblique mode False
        mock_cost.return_value = 1.5
        def mock_oblique_error(ep_test, n_test):
            return 2.0
            
        res = strat._run_needle_fallback_scan(
            mock_worker, stack=stack, ep_base=ep_base, n_layers_T_orig=n_layers_T_orig,
            needle_mat_names=needle_mat_names, mats_nk=mats_nk, float_dtype=float_dtype,
            wls=wls, oblique_mode=False, compute_oblique_error_needle=mock_oblique_error,
            n_sub=n_sub, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back=has_back,
            n_back_T=n_back_T, d_back=d_back, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS
        )
        assert res is not None
        assert res['cost'] == 1.5
        
        # Test oblique mode True
        res_oblique = strat._run_needle_fallback_scan(
            mock_worker, stack=stack, ep_base=ep_base, n_layers_T_orig=n_layers_T_orig,
            needle_mat_names=needle_mat_names, mats_nk=mats_nk, float_dtype=float_dtype,
            wls=wls, oblique_mode=True, compute_oblique_error_needle=mock_oblique_error,
            n_sub=n_sub, tgt_vals=tgt_vals, tgt_weights=tgt_weights, has_back=has_back,
            n_back_T=n_back_T, d_back=d_back, STEP_NM=STEP_NM, PROBE_THICKNESS=PROBE_THICKNESS
        )
        assert res_oblique is not None
        assert res_oblique['cost'] == 2.0

    @patch('certus.workers.certus_design_workers_needle_strat._design_compute_oblique_error_common')
    def test_compute_oblique_error(self, mock_common, mock_worker):
        strat = NeedleOptimizationStrategy()
        strat._compute_oblique_error(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_needle_strat._design_compute_oblique_error_and_grad_analytic_common')
    def test_compute_oblique_error_and_grad_analytic(self, mock_common, mock_worker):
        strat = NeedleOptimizationStrategy()
        strat._compute_oblique_error_and_grad_analytic(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_needle_strat._design_objective_wrapper_common')
    def test_objective_wrapper(self, mock_common, mock_worker):
        strat = NeedleOptimizationStrategy()
        strat._objective_wrapper(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_needle_strat._design_gradient_func_pglobal_common')
    def test_gradient_func_pglobal(self, mock_common, mock_worker):
        strat = NeedleOptimizationStrategy()
        strat._gradient_func_pglobal(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()
        
    @patch('certus.workers.certus_design_workers_needle_strat._design_optimization_callback_common')
    def test_optimization_callback(self, mock_common, mock_worker):
        strat = NeedleOptimizationStrategy()
        strat._optimization_callback(mock_worker, np.array([1.0]))
        mock_common.assert_called_once()

