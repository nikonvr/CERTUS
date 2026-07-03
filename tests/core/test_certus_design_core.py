import pytest
import numpy as np
from unittest.mock import MagicMock
from certus.core.certus_design_core import (
    _design_objective_wrapper_common,
    _design_compute_oblique_error_common,
    _design_gradient_func_pglobal_common,
)
from certus.core.certus_core import CFG

class MockApp:
    def __init__(self):
        self._var_idx = np.array([1])
        self._all_variable = False
        self._ep_buffer = np.array([10.0, 10.0, 10.0])
        self._ep0 = np.array([10.0, 10.0, 10.0])
        self._oblique_mode = False
        self._n_layers_T = np.zeros((10, 3), dtype=np.complex128)
        self._n_sub = np.zeros(10, dtype=np.complex128)
        self._wls = np.linspace(400, 800, 10)
        self._tgt_vals = np.ones(10)
        self._tgt_weights = np.ones(10)
        self._has_back_calc = False
        self._n_back_T = np.zeros((10, 1), dtype=np.complex128)
        self._d_back = np.zeros(1)
        
        # Helper for testing oblique error
        self._compute_oblique_error_called = False
        self._compute_oblique_error_and_grad_called = False

    def _compute_oblique_error(self, ep_buffer):
        self._compute_oblique_error_called = True
        return 42.0

    def _compute_oblique_error_and_grad_analytic(self, ep_buffer):
        self._compute_oblique_error_and_grad_called = True
        return 42.0, np.ones_like(self._var_idx)


def test_design_objective_wrapper_common_wrong_len():
    app = MockApp()
    # Provide wrong length for x
    x = np.array([1.0, 2.0])
    cost = _design_objective_wrapper_common(app, x)
    assert cost == 1e30

def test_design_objective_wrapper_common_min_thick_violation():
    app = MockApp()
    x = np.array([1e-6]) # below min_thick
    cost = _design_objective_wrapper_common(app, x)
    assert cost == 1e30

def test_design_objective_wrapper_common_oblique_dispatch():
    app = MockApp()
    app._oblique_mode = True
    x = np.array([15.0])
    cost = _design_objective_wrapper_common(app, x)
    assert cost == 42.0
    assert app._compute_oblique_error_called

def test_design_gradient_func_pglobal_common_wrong_len():
    app = MockApp()
    x = np.array([1.0, 2.0])
    cost, grad = _design_gradient_func_pglobal_common(app, x)
    assert cost == 1e30
    assert (grad == 0.0).all()

def test_design_gradient_func_pglobal_common_min_thick_violation():
    app = MockApp()
    x = np.array([1e-6])
    cost, grad = _design_gradient_func_pglobal_common(app, x)
    assert cost == 1e30
    assert grad[0] > 0.0 # penalty gradient

def test_design_gradient_func_pglobal_common_oblique_dispatch():
    app = MockApp()
    app._oblique_mode = True
    x = np.array([15.0])
    cost, grad = _design_gradient_func_pglobal_common(app, x)
    assert cost == 42.0
    assert app._compute_oblique_error_and_grad_called

def test_design_compute_oblique_error_common_no_weight():
    app = MockApp()
    app._oblique_configs = [
        {
            "wls_config": np.array([500.0]),
            "n_layers_T_config": np.zeros((1, 1), dtype=np.complex128),
            "n_sub_config": np.zeros(1, dtype=np.complex128),
            "angle": 0.0,
            "pol": "s",
            "sw_cfg": np.array([1.0]),
            "targets": [
                {
                    "local_positions": np.array([0]),
                    "target_type": "R",
                    "tgt_vals": np.array([0.5]),
                    "weight": 0.0 # ZERO WEIGHT
                }
            ]
        }
    ]
    app._has_back_calc = False
    app._has_back_stack = False
    app._d_back = np.zeros(0)
    app._n_back_T = np.zeros((1, 0), dtype=np.complex128)

    ep_test = np.array([10.0])
    cost = _design_compute_oblique_error_common(app, ep_test)
    assert cost == 1e30 # Weight is 0 -> 1e30 fallback


from certus.core.certus_design_core import _design_optimization_callback_common

class MockSample:
    def __init__(self, y, x, gen):
        self.y = y
        self.x = x
        self.generation = gen

class MockSignal:
    def __init__(self):
        self.emissions = []
    def emit(self, *args):
        self.emissions.append(args)

class MockSignals:
    def __init__(self):
        self.progress = MockSignal()
        self.progress_snapshot = MockSignal()
        self.update_stats = MockSignal()
        self.result = MockSignal()

class MockOptimizer:
    def __init__(self):
        self.n_evals = 100
        class Clusterer:
            clusters = [1, 2, 3]
        self.clusterer = Clusterer()

class MockCallbackApp(MockApp):
    def __init__(self):
        super().__init__()
        self._stop_event = MagicMock()
        self._stop_event.is_set.return_value = False
        
        self.best_rmse_seen = 1e9
        self._callback_counter = 0
        self.cfg = {'max_feval': 1000}
        self.signals = MockSignals()
        self.on_progress_snapshot = self.signals.progress_snapshot.emit
        self.on_result = self.signals.result.emit
        self.on_update_stats = self.signals.update_stats.emit
        self._optimizer = MockOptimizer()
        self.best_ep_final = None
        self.best_rmse_final = None
        self._last_live_emit_time = 0
        self._oblique_mode = False
        self._wls_display = np.array([500.0])
        self._n_lay_T_disp = np.zeros((1, 3), dtype=np.complex128)
        self._n_sub_disp = np.zeros(1, dtype=np.complex128)
        self._display_oblique_keys = []
        self._has_back_calc = False

def test_design_optimization_callback_common_stop_event():
    app = MockCallbackApp()
    app._stop_event.is_set.return_value = True
    sample = MockSample(y=10.0, x=np.array([1.0]), gen=1)
    
    _design_optimization_callback_common(app, sample)
    assert app._callback_counter == 0 # Should return immediately

def test_design_optimization_callback_common_first_improvement():
    app = MockCallbackApp()
    # Provide a sample with y = 0.25 (rmse = 0.5)
    sample = MockSample(y=0.25, x=np.array([2.0]), gen=1)
    
    _design_optimization_callback_common(app, sample)
    
    assert app.best_rmse_seen == 0.5
    assert app.best_rmse_final == 0.5
    assert app.best_ep_final is not None
    assert app.best_ep_final[1] == 2.0
    
    # Check that progress_snapshot signal was emitted (current_rmse < best_rmse_seen initially)
    assert len(app.signals.progress_snapshot.emissions) > 0
    # Check that result signal was emitted (improvement_ratio > 0.01)
    assert len(app.signals.result.emissions) > 0
    
def test_design_optimization_callback_common_oblique_mode():
    app = MockCallbackApp()
    app._oblique_mode = True
    app._oblique_tgts = []
    
    sample = MockSample(y=0.01, x=np.array([3.0]), gen=2)
    _design_optimization_callback_common(app, sample)
    
    assert app.best_rmse_seen == 0.1
    assert len(app.signals.result.emissions) > 0
    # The emitted result dictionary should contain 'spectra_display' and 'self._oblique_mode' == True
    result_dict = app.signals.result.emissions[0][0]
    assert result_dict['self._oblique_mode'] is True
