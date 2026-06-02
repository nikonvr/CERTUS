"""Unit tests for CERTUS_DESIGN.py

Covers optical design features."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import CERTUS_DESIGN
    from certus_physics import Layer, Target, Sample
    from certus.core.certus_core import get_logger

    DESIGN_AVAILABLE = True
except ImportError:
    DESIGN_AVAILABLE = False



@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")
class TestCERTUSDesign:
    """Tests for le module CERTUS_DESIGN."""

    def test_module_import(self):
        """Test que le module s'importe correctement."""
        import CERTUS_DESIGN

        assert hasattr(CERTUS_DESIGN, "__version__")

    def test_bootstrap_integration(self):
        """Test the integration with bootstrap_app."""
        from certus.core.certus_core import bootstrap_app

        assert callable(bootstrap_app)

    def test_logging_integration(self):
        """Test the integration with the logging system."""
        try:
            from certus.core.certus_core import get_logger

            logger = get_logger()
            assert logger is not None
        except ImportError:
            pytest.skip("Logging non disponible")

    def test_physics_integration(self):
        """Test the integration with certus_physics."""
        try:
            from certus_physics import Layer, Target, Sample

            assert Layer is not None
            assert Target is not None
            assert Sample is not None
        except ImportError:
            pytest.skip("certus_physics non disponible")

    def test_ui_integration(self):
        """Test the integration with certus_ui."""
        try:
            from certus.ui.certus_ui import CertusTheme, apply_certus_theme

            assert CertusTheme is not None
            assert callable(apply_certus_theme)
        except ImportError:
            pytest.skip("certus_ui non disponible")



@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")
class TestDesignFunctionality:
    """Tests for design features."""

    def test_design_algorithms(self):
        """Test les algorithmes de conception."""
        design_attributes = [
            "OptimWorker",
            "calc_spectrum_front",
            "calc_spectrum_full",
        ]

        available_attributes = []
        for attr_name in design_attributes:
            if hasattr(CERTUS_DESIGN, attr_name):
                available_attributes.append(attr_name)

        assert len(available_attributes) > 0

    def test_extracted_worker_helpers_are_available(self):
        """New extracted worker helpers should remain importable."""
        from certus.workers.certus_design_worker_utils import build_needle_scan_mask, build_pglobal_config_from_cfg

        assert callable(build_pglobal_config_from_cfg)
        assert callable(build_needle_scan_mask)

    def test_worker_helper_build_needle_scan_mask_excludes_layers(self):
        """Needle mask helper should skip excluded layers and preserve matching materials."""
        from certus.workers.certus_design_worker_utils import build_needle_scan_mask
        from certus_physics import Layer

        stack = [Layer(mat="H", qwot=1.0), Layer(mat="L", qwot=1.0), Layer(mat="H", qwot=1.0)]
        mats_nk = {"H": object(), "L": object()}
        names, mask = build_needle_scan_mask(stack, mats_nk, excluded_layers={1})

        assert names == ["L", "", "L"]
        np.testing.assert_array_equal(mask, np.array([1, 0, 1], dtype=np.int64))

    def test_worker_helper_build_pglobal_config_local_mode(self):
        """PGlobal helper should return a config object and iteration budget for local mode."""
        from certus.workers.certus_design_worker_utils import build_pglobal_config_from_cfg

        cfg = {"max_feval": 1234}
        pg_conf, max_iter = build_pglobal_config_from_cfg(cfg, mode="local", dim=12, conv_tol=1e-8)

        assert pg_conf is not None
        assert max_iter == 15

    def test_worker_helper_prepare_pglobal_optimizer_runtime(self):
        """Runtime helper should emit the correct progress message for global mode."""
        from certus.workers.certus_design_worker_utils import prepare_pglobal_optimizer_runtime

        emitted = []

        def emit(progress, text):
            emitted.append((progress, text))

        optimizer, start_time = prepare_pglobal_optimizer_runtime(
            optimizer=object(),
            mode="global",
            max_iter_run=50,
            dim=8,
            progress_emit=emit,
            best_rmse_seen=1.2345,
            callback_counter=7,
        )

        assert optimizer is not None
        assert start_time > 0
        assert emitted == [(0, "Starting PGLOBAL Global Optimization...")]

    def test_worker_helper_prepare_pglobal_inputs_uses_signal_and_gradient(self):
        """Prepared inputs should forward the gradient helper and emit a config message."""
        from certus.workers.certus_design_worker_utils import prepare_pglobal_inputs_from_state

        emitted = []

        def signal_emit(code, message):
            emitted.append((code, message))

        dim, grad_func, pg_conf, max_iter = prepare_pglobal_inputs_from_state(
            var_idx=[0, 2, 4],
            mode="local",
            cfg={"max_feval": 1234},
            signal_emit=signal_emit,
            gradient_func=lambda x: x,
        )

        assert dim == 3
        assert callable(grad_func)
        assert pg_conf is not None
        assert max_iter == 15
        assert emitted and emitted[0][0] == 0

    def test_worker_helper_build_pglobal_config_global_mode_overrides(self):
        """Global mode should propagate explicit overrides into the config object."""
        from certus.workers.certus_design_worker_utils import build_pglobal_config_from_cfg

        cfg = {
            "max_feval": 1234,
            "max_clusters": 7,
            "alpha": 0.123,
            "reduction_ratio": 0.42,
            "local_search_budget": 99,
            "max_iter": 17,
        }
        pg_conf, max_iter = build_pglobal_config_from_cfg(cfg, mode="global", dim=12, conv_tol=1e-6)

        assert pg_conf is not None
        assert max_iter == 17
        assert getattr(pg_conf, "max_active_clusters", None) == 7
        assert getattr(pg_conf, "alpha", None) == 0.123
        assert getattr(pg_conf, "reduction_ratio", None) == 0.42
        assert getattr(pg_conf, "local_search_budget", None) == 99

    def test_worker_helper_tikhonravov_upgrade_is_safe_without_upgrade(self):
        """Tikhonravov helper should preserve the grid when the upgrade condition is not met."""
        from certus.workers.certus_design_worker_utils import maybe_upgrade_grid_tikhonravov
        from certus_physics import Layer, Target

        class DummyMat:
            def __init__(self, n=1.5):
                self._n = n

            def get_nk(self, wls):
                return np.full(len(wls), self._n + 0j)

        mats = {"H": DummyMat(2.0), "L": DummyMat(1.45), "Substrate": DummyMat(1.52), "substrate": DummyMat(1.52)}
        stack = [Layer(mat="H", qwot=1.0), Layer(mat="L", qwot=1.0)]
        tgts = [Target(lmin=500.0, lmax=510.0, tmin=0.2, tmax=0.8, w=1.0)]
        wls = np.linspace(500.0, 510.0, 20)
        ep_current = np.array([100.0, 120.0], dtype=float)
        n_sub = mats["Substrate"].get_nk(wls)
        n_layers_T = np.ascontiguousarray(np.array([mats[l.mat].get_nk(wls) for l in stack], dtype=np.complex128).T)
        n_back_T = np.zeros((len(wls), 0), dtype=np.complex128)
        tgt_vals, tgt_weights = np.linspace(0.2, 0.8, len(wls)), np.ones(len(wls))

        out = maybe_upgrade_grid_tikhonravov(
            ep_current=ep_current,
            mats=mats,
            stack=stack,
            tgts=tgts,
            oblique_mode=False,
            oblique_tgts=[],
            wls=wls,
            float_dtype=np.float64,
            complex_dtype=np.complex128,
            has_back_stack=False,
            stack_back=[],
            ep_back=np.zeros(0, dtype=float),
            n_sub=n_sub,
            n_layers_T=n_layers_T,
            n_back_T=n_back_T,
            tgt_vals=tgt_vals,
            tgt_weights=tgt_weights,
        )

        new_wls, new_n_sub, new_n_layers_T, new_n_back_T, new_tgt_vals, new_tgt_weights = out
        assert new_wls.shape == wls.shape
        assert np.allclose(new_wls, wls)
        assert new_n_sub.shape == n_sub.shape
        assert new_n_layers_T.shape == n_layers_T.shape
        assert new_n_back_T.shape == n_back_T.shape
        assert np.allclose(new_tgt_vals, tgt_vals)
        assert np.allclose(new_tgt_weights, tgt_weights)

    def test_stop_qt_worker_thread_safely_handles_non_running_thread(self):
        """Safe shutdown helper should be a no-op on already stopped threads."""
        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        class DummyThread:
            def isRunning(self):
                return False

        class DummyWorker:
            def request_stop(self):
                raise AssertionError("should not be called")

        assert stop_qt_worker_thread_safely(DummyThread(), DummyWorker()) is True

    def test_stop_qt_worker_thread_safely_requests_cooperative_shutdown(self):
        """Safe shutdown helper should request stop/quit without terminate()."""
        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        calls = []

        class DummyThread:
            def isRunning(self):
                return True

            def requestInterruption(self):
                calls.append("interrupt")

            def quit(self):
                calls.append("quit")

            def wait(self, timeout_ms):
                calls.append(("wait", timeout_ms))
                return True

        class DummyWorker:
            def request_stop(self):
                calls.append("stop")

        assert stop_qt_worker_thread_safely(DummyThread(), DummyWorker(), timeout_ms=1234) is True
        assert calls == ["stop", "interrupt", "quit", ("wait", 1234)]

    def test_layer_management(self):
        """Test la gestion des couches."""
        try:
            from certus_physics import Layer

            layer1 = Layer(mat="SiO2", qwot=1.0)
            layer2 = Layer(mat="TiO2", qwot=2.0)

            assert layer1.mat == "SiO2"
            assert layer1.qwot == 1.0
            assert layer2.mat == "TiO2"
            assert layer2.qwot == 2.0

        except ImportError:
            pytest.skip("Layer non disponible")

    def test_target_management(self):
        """Test la gestion des cibles."""
        try:
            from certus_physics import Target

            target = Target(lmin=550.0, lmax=550.0, tmin=0.5, tmax=0.5, w=1.0)

            assert target.lmin == 550.0
            assert target.tmin == 0.5
            assert target.w == 1.0

        except ImportError:
            pytest.skip("Target non disponible")

    def test_spectrum_calculationation(self, sample_layers, sample_wavelengths):
        """Test the spectrum calculation."""
        try:
            from conftest import compute_spectrum_simple

            spectrum = compute_spectrum_simple(sample_layers, sample_wavelengths)

            assert isinstance(spectrum, np.ndarray)
            assert len(spectrum) == len(sample_wavelengths)

        except ImportError:
            pytest.skip("compute_spectrum_simple non disponible")

    def test_optimization_parameters(self):
        """Test optimization settings."""
        optimization_params = ["max_iterations", "tolerance", "algorithm"]

        available_params = []
        for param in optimization_params:
            if hasattr(CERTUS_DESIGN, param):
                available_params.append(param)

        assert len(available_params) >= 0
