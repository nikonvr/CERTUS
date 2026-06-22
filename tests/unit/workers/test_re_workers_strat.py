import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from certus.workers.certus_re_workers_phase3 import REPhase3Strategy
from certus.workers.certus_re_workers_phase4 import REPhase4Strategy
from certus.workers.certus_re_workers_context import REContextStrategy
from certus.workers.certus_re_workers_math import REMathStrategy

class MockMaterial:
    def get_nk(self, wls):
        return np.ones(len(wls), dtype=np.complex128)

class MockLayer:
    def __init__(self, mat):
        self.mat = mat

@pytest.fixture
def mock_re_worker():
    worker = MagicMock()
    worker._stop = False
    
    mock_mat = MockMaterial()
    worker.cfg = {
        're_phase3_shake_rounds': 2,
        'mats': {'Substrate': mock_mat, 'H': mock_mat, 'L': mock_mat},
        'stack': [MockLayer('H'), MockLayer('L'), MockLayer('H'), MockLayer('L'), MockLayer('H')],
        'ep0': np.array([10.0, 10.0, 10.0, 10.0, 10.0]),
        'l0': 500.0,
        'wls_min': 400.0,
        'wls_max': 800.0
    }
    
    L = SimpleNamespace()
    
    # Common mock fields
    L.n_layers_count = 5
    L.results = [{
        'label': 'Legacy',
        'ep': np.ones(5),
        're_dH_knots': np.zeros(10),
        're_dL_knots': np.zeros(10),
        're_knots_nm': np.zeros(10),
        're_spline_lam_node2_nm': 500.0,
        'rmse': 1.0,
        'rmse_combined': 1.0,
        'success': True
    }]
    
    L._p2_ctx = {
        '_nk': 10,
        'i0': 5,
        'i_lam': 25,
        'b_lb': np.zeros(26),
        'b_ub': np.ones(26) * 100,
        'bounds_p2_trf': (np.zeros(26), np.ones(26) * 100),
        '_cb2_ref': MagicMock(),
        '_p2_trf_log_tag': ['TEST'],
        '_eval_both_p2': MagicMock(return_value=(0.5, 0.5, 0.5)),
        '_fun_res_p2': MagicMock(return_value=np.zeros(10)),
        '_jac_res_p2': MagicMock(return_value=np.zeros((10, 10))),
        '_p2_ki_slot': False
    }
    
    L._use_sub_c3_shared = False
    L._alpha_slot = [False]
    L._a_p3 = 1.0
    L.re_p2_plan = [MagicMock()]
    L._pct_p3 = MagicMock(return_value=5.0)
    L._emit_re_prog = MagicMock()
    L._emit_re_spectrum_live = MagicMock()
    L._report_mse_spectral = MagicMock(return_value=1.0)
    L._compute_qwot_rmse = MagicMock(return_value=1.0)
    L._rmse_combined = MagicMock(return_value=1.0)
    L.rmse_final_milestone = [1.0]
    L.re_p4_grid = []
    L.oblique_config_meta = []
    L._re_state = {
        're_aperture_knots': np.ones(10),
        're_p4_beam_knots_lam_nm': np.ones(10) * 500.0,
        'is_phase4': True
    }
    L._re_use_staged_order = False
    L._correc_nom = (None, None)
    L.wls = np.linspace(400, 800, 10)
    L._ap_gui = 1.0
    L.re_env_s = 0.0
    
    worker._re_phase_ns = L
    return worker

class TestREPhase3Strategy:
    @patch('certus.workers.certus_re_workers_phase3.least_squares')
    def test_execute_phase3_shakes(self, mock_ls, mock_re_worker):
        strat = REPhase3Strategy()
        
        # Mock least_squares to improve RMSE
        mock_res = MagicMock()
        mock_res.x = np.ones(26)
        mock_res.cost = 0.1 # Improved cost
        mock_ls.return_value = mock_res
        
        # Setup worker state for phase 3
        mock_re_worker._re_phase_ns.results[0]['rmse_combined'] = 10.0 # Force improvement
        
        strat._execute_phase3_shakes(mock_re_worker)
        
        assert mock_ls.called
        assert mock_re_worker._re_phase_ns._emit_re_prog.called

class TestREPhase4Strategy:
    def test_get_phase4_aperture_bounds(self, mock_re_worker):
        strat = REPhase4Strategy()
        mock_re_worker.cfg['re_phase4_ap_bounds_deg'] = [2.0, 15.0]
        lo, hi = strat._get_phase4_aperture_bounds(mock_re_worker)
        assert lo == 2.0
        assert hi == 15.0
        
    @patch('certus.workers.certus_re_workers_phase4.scipy.optimize.least_squares')
    def test_execute_phase4_beam(self, mock_ls, mock_re_worker):
        strat = REPhase4Strategy()
        
        mock_re_worker._re_phase_ns.re_p4_grid = [(0.1, 0.2)]
        mock_re_worker._re_phase_ns._p2_ctx['_eval_both_p2a'] = MagicMock(return_value=(0.5, 0.5, 0.5))
        mock_re_worker._re_phase_ns._p2_ctx['_fun_res_p2a'] = MagicMock(return_value=np.zeros(10))
        mock_re_worker._re_phase_ns._p2_ctx['_jac_res_p2a'] = MagicMock(return_value=np.zeros((10, 10)))
        mock_re_worker.cfg['re_phase4_maxiter'] = 10
        
        mock_res = MagicMock()
        mock_res.x = np.ones(14)
        mock_res.cost = 0.1
        mock_ls.return_value = mock_res
        
        strat._execute_phase4_beam(mock_re_worker)
        assert mock_re_worker._re_phase_ns._emit_re_prog.called

class TestREContextStrategy:
    def test_build_re_run_context(self, mock_re_worker):
        # Ensure it creates the L namespace
        L = REContextStrategy._build_re_run_context(mock_re_worker, 0.0)
        assert hasattr(L, 'results')
        
class TestREMathStrategy:
    def test_math_strategy_exists(self):
        strat = REMathStrategy()
        assert hasattr(strat, '_compute_fun_res_p2')
