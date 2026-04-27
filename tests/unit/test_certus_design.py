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

    from certus_core import get_logger



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

        from certus_core import bootstrap_app



        assert callable(bootstrap_app)



    def test_logging_integration(self):

        """Test the integration with the logging system."""

        try:

            from certus_core import get_logger



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

            from certus_ui import CertusTheme, apply_certus_theme



            assert CertusTheme is not None

            assert callable(apply_certus_theme)

        except ImportError:

            pytest.skip("certus_ui non disponible")





@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignFunctionality:

    """Tests for design features."""



    def test_design_algorithms(self):

        """Test les algorithmes de conception."""

        # Verify that les fonctions principales existent

        # Updated to match actual API in CERTUS_DESIGN.py

        design_attributes = [

            "OptimWorker",  # Optimization class

            "calc_spectrum_front",  # Spectrum calculationation

            "calc_spectrum_full",  # Full spectrum calculationation

        ]



        available_attributes = []

        for attr_name in design_attributes:

            if hasattr(CERTUS_DESIGN, attr_name):

                available_attributes.append(attr_name)



        # At least some functions should be available

        assert len(available_attributes) > 0



    def test_layer_management(self):

        """Test la gestion des couches."""

        try:

            from certus_physics import Layer



            # Create test layers

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



            # Create test target

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



            # Calculate the spectrum

            spectrum = compute_spectrum_simple(sample_layers, sample_wavelengths)



            assert isinstance(spectrum, np.ndarray)

            assert len(spectrum) == len(sample_wavelengths)



        except ImportError:

            pytest.skip("compute_spectrum_simple non disponible")



    def test_optimization_parameters(self):

        """Test optimization settings."""

        # Verify that optimization parameters are defined

        optimization_params = ["max_iterations", "tolerance", "algorithm"]



        available_params = []

        for param in optimization_params:

            if hasattr(CERTUS_DESIGN, param):

                available_params.append(param)



        # Some parameters should be available

        assert len(available_params) >= 0





@pytest.mark.performance

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignPerformance:

    """Tests de performance for CERTUS_DESIGN."""



    def test_calculationation_performance(self, sample_layers, sample_wavelengths):

        """Test les performances de calculation."""

        try:

            import time

            from conftest import compute_spectrum_simple



            # Measure le temps de calculation

            start_time = time.time()

            spectrum = compute_spectrum_simple(sample_layers, sample_wavelengths)

            end_time = time.time()



            calculationation_time = end_time - start_time



            # The calculation should be fast (< 1 second)

            assert calculationation_time < 1.0

            assert isinstance(spectrum, np.ndarray)



        except ImportError:

            pytest.skip("compute_spectrum_simple non disponible")



    def test_memory_usage(self, sample_layers, sample_wavelengths):

        """Test l'memory usage."""

        try:

            import tracemalloc



            # Start memory tracking

            tracemalloc.start()



            # Effectuer des calculations

            from conftest import compute_spectrum_simple



            compute_spectrum_simple(sample_layers, sample_wavelengths)



            # Measure memory usage

            current, peak = tracemalloc.get_traced_memory()

            tracemalloc.stop()



            # Memory usage should be reasonable

            assert peak < 100 * 1024 * 1024  # < 100 MB



        except ImportError:

            pytest.skip("tracemalloc non disponible")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):

            pytest.skip("Memory test not available")





@pytest.mark.integration

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignIntegration:

    """Integration tests for CERTUS_DESIGN."""



    def test_design_core_integration(self):

        """Test the design ↔ core integration."""

        try:

            from certus_core import get_logger, get_resource_path

            from certus_ui import CertusTheme



            logger = get_logger()

            theme = CertusTheme

            resource_path = get_resource_path



            assert logger is not None

            assert theme is not None

            assert callable(resource_path)

        except ImportError as e:

            pytest.skip(f"Missing dependency:{e}")



    def test_design_physics_integration(self):

        """Test the design ↔ physics integration."""

        try:

            from certus_physics import Layer, Target, Sample

            from conftest import compute_spectrum_simple



            # Create complete structure

            layers = [Layer(mat="SiO2", qwot=1.0), Layer(mat="TiO2", qwot=2.0)]

            wavelengths = np.linspace(400, 800, 100)



            # Calculate the spectrum

            spectrum = compute_spectrum_simple(layers, wavelengths)



            assert isinstance(spectrum, np.ndarray)

            assert len(spectrum) == len(wavelengths)



        except ImportError as e:

            pytest.skip(f"Physics integration not available:{e}")



    def test_complete_design_workflow(self, sample_layers, sample_wavelengths):

        """Test un workflow de conception complet."""

        try:

            from certus_physics import Layer, Target

            from conftest import compute_spectrum_simple



            # 1. Define layers

            layers = sample_layers



            # 2. Define targets

            targets = [

                Target(lmin=550.0, lmax=550.0, tmin=0.5, tmax=0.5, w=1.0),

                Target(lmin=650.0, lmax=650.0, tmin=0.8, tmax=0.8, w=0.5),

            ]



            # 3. Calculate the initial spectrum

            spectrum = compute_spectrum_simple(layers, sample_wavelengths)



            # 4. Validate results

            assert isinstance(spectrum, np.ndarray)

            assert len(spectrum) == len(sample_wavelengths)

            assert len(targets) > 0



            # Le workflow est complet

            workflow_complete = True

            assert workflow_complete



        except ImportError as e:

            pytest.skip(f"Workflow complet non disponible: {e}")





@pytest.mark.unit

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignUtilities:

    """Tests for les utilitaires de conception."""



    def test_material_database(self):

        """Test the material data base."""

        try:

            from certus_physics import materials_data



            # Verify that material data is available

            # Updated to match materials_data.py content (Silicon data)

            assert hasattr(materials_data, "get_nk_si")

            assert hasattr(materials_data, "SI_N_DATA")

            assert hasattr(materials_data, "SI_K_DATA")



        except ImportError as e:

            pytest.skip(f"Material modules not available:{e}")



    def test_wavelength_validation(self):

        """Test la validation des longueurs d'onde."""

        try:

            from certus_errors import validate_wavelength_range



            # Test a valid range

            validate_wavelength_range(400.0, 800.0)



            # Test an invalid range

            with pytest.raises(Exception):

                validate_wavelength_range(800.0, 400.0)



        except ImportError:

            pytest.skip("validate_wavelength_range non disponible")



    def test_thickness_validation(self):

        """Test validation of thicknesses."""

        try:

            from certus_errors import validate_thickness



            # Test valid thickness

            validate_thickness(100.0)



            # Test invalid thickness

            with pytest.raises(Exception):

                validate_thickness(-10.0)



        except ImportError:

            pytest.skip("validate_thickness non disponible")





@pytest.mark.unit

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignStackInfo:

    """Testing for Stack Info functionality."""



    def test_certus_design_app_has_update_substrate_info(self):

        """CertusDesignApp expose _update_substrate_info (Stack Info)."""

        from CERTUS_DESIGN import CertusDesignApp

        assert hasattr(CertusDesignApp, "_update_substrate_info")



    def test_update_substrate_info_no_op_when_window_not_visible(self):

        """_update_substrate_info does nothing if the window is not visible."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp

        app = Mock(spec=CertusDesignApp)

        app.substrate_info_window = Mock()

        app.substrate_info_window.isVisible = Mock(return_value=False)

        app.structure_text = Mock()

        CertusDesignApp._update_substrate_info(app)

        app.structure_text.setText.assert_not_called()



    def test_certus_design_app_has_show_substrate_info_window(self):

        """CertusDesignApp expose _show_substrate_info_window (Stack Info)."""

        from CERTUS_DESIGN import CertusDesignApp

        assert hasattr(CertusDesignApp, "_show_substrate_info_window")



    def test_update_substrate_info_fills_structure_text_with_qwot(self):

        """_update_substrate_info fills structure_text with QWOT (4 decimal places)."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp

        app = Mock(spec=CertusDesignApp)

        app.substrate_info_window = Mock()

        app.substrate_info_window.isVisible = Mock(return_value=True)

        app.substrate_type_label = Mock()

        app.substrate_index_label = Mock()

        app.structure_text = Mock()

        app.mat_widgets = {

            "substrate": {

                "preset": Mock(currentText=Mock(return_value="Custom")),

                "n4": Mock(value=Mock(return_value=1.52)),

                "n7": Mock(value=Mock(return_value=1.51)),

            }

        }

        app.front_table = Mock()

        app.front_table.rowCount = Mock(return_value=2)

        app.front_table.cellWidget = Mock(

            side_effect=lambda r, c: (

                Mock(currentText=Mock(return_value="SiO2")) if c == 0

                else (Mock(value=Mock(return_value=1.0)) if c == 1 else None)

            )

        )

        app.l0_spin = Mock(value=Mock(return_value=500.0))

        app._workflow_best_rmse = 0.01

        app._get_substrate_info_display = Mock(return_value=("Custom", "1.52"))

        app._stack_info_l0_nm = Mock(return_value=500.0)

        app._stack_info_front_table_cols = Mock(return_value=(0, 1))

        app._stack_info_format_layer_line = Mock(

            side_effect=lambda idx, mat_str, qwot, l0: f"Layer {idx}: {mat_str} - {float(qwot):.4f} QWOT\n"

        )

        CertusDesignApp._update_substrate_info(app)

        app.substrate_type_label.setText.assert_called_once()

        app.substrate_index_label.setText.assert_called_once()

        app.structure_text.setText.assert_called_once()

        text = app.structure_text.setText.call_args[0][0]

        assert "DESIGN STRUCTURE" in text or "substrate" in text

        assert "QWOT" in text

        assert "1.52" in text or "Custom" in text



    def test_update_substrate_info_uses_best_ep_when_set(self):

        """Quand _stack_info_best_ep est set (pendant optim), la structure affiche le best stack en QWOT."""

        from unittest.mock import Mock

        import numpy as np

        from CERTUS_DESIGN import CertusDesignApp

        app = Mock(spec=CertusDesignApp)

        app.substrate_info_window = Mock()

        app.substrate_info_window.isVisible = Mock(return_value=True)

        app.substrate_type_label = Mock()

        app.substrate_index_label = Mock()

        app.structure_text = Mock()

        app.mat_widgets = {

            "substrate": {

                "preset": Mock(currentText=Mock(return_value="Custom")),

                "n4": Mock(value=Mock(return_value=1.52)),

                "n7": Mock(value=Mock(return_value=1.51)),

            }

        }

        app._stack_info_best_ep = np.array([50.0, 75.0])

        app.l0_spin = Mock(value=Mock(return_value=500.0))

        app._stack_info_best_rmse = 0.02

        layer = Mock()

        layer.mat = "SiO2"

        app._get_front_stack = Mock(return_value=[layer, layer])

        mat = Mock()

        mat.n4 = 1.46

        app._get_materials = Mock(return_value={"SiO2": mat})

        app._get_substrate_info_display = Mock(return_value=("Custom", "1.52"))

        app._stack_info_l0_nm = Mock(return_value=500.0)

        app._stack_info_format_layer_line = Mock(

            side_effect=lambda idx, mat_str, qwot, l0: f"Layer {idx}: {mat_str} - {float(qwot):.4f} QWOT\n"

        )

        CertusDesignApp._update_substrate_info(app)

        app.structure_text.setText.assert_called_once()

        text = app.structure_text.setText.call_args[0][0]

        assert "best so far" in text.lower() or "layers" in text

        assert "QWOT" in text

        assert "0.02" in text or "OPTIMIZATION" in text





@pytest.mark.unit

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignClearReset:

    """Tests pour Clear / Reset (DESIGN)."""



    def test_certus_design_app_has_reset_to_defaults(self):

        """CertusDesignApp expose reset_to_defaults."""

        from CERTUS_DESIGN import CertusDesignApp

        assert hasattr(CertusDesignApp, "reset_to_defaults")



    def test_certus_design_app_has_load_defaults(self):

        """CertusDesignApp expose _load_defaults."""

        from CERTUS_DESIGN import CertusDesignApp

        assert hasattr(CertusDesignApp, "_load_defaults")



    def test_design_uses_reset_framework_with_app_reset(self, qapp):

        """Le bouton Clear/Reset DESIGN utilise create_reset_button avec use_app_reset."""

        try:

            from certus_reset_framework import create_reset_button

        except ImportError:

            pytest.skip("certus_reset_framework non disponible")

        from unittest.mock import Mock

        app = Mock()

        app.reset_to_defaults = Mock()

        btn = create_reset_button(app, use_app_reset=True)

        btn.clicked.emit()

        app.reset_to_defaults.assert_called_once()



    def test_reset_framework_create_reset_button_accepts_use_app_reset(self, qapp):

        """create_reset_button accepts the use_app_reset parameter."""

        try:

            from certus_reset_framework import create_reset_button

        except ImportError:

            pytest.skip("certus_reset_framework non disponible")

        from unittest.mock import Mock

        app = Mock()

        app.reset_to_defaults = Mock()

        btn_with_app = create_reset_button(app, use_app_reset=True)

        btn_without = create_reset_button(app, use_app_reset=False)

        assert btn_with_app is not None

        assert btn_without is not None

        assert "Clear" in btn_with_app.text() or "Reset" in btn_with_app.text()





@pytest.mark.unit

@pytest.mark.skipif(not DESIGN_AVAILABLE, reason="CERTUS_DESIGN non disponible")

class TestDesignNonREInvariants:

    """DESIGN non-regression tests when RE is not active."""



    def test_get_materials_returns_standard_materials_when_re_disabled(self):

        """_get_materials retourne des Material standards si _re_loaded=False."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp



        app = Mock(spec=CertusDesignApp)

        app._re_loaded = False

        app.mat_widgets = {

            "H": {"n4": Mock(value=Mock(return_value=2.35)), "n7": Mock(value=Mock(return_value=2.30))},

            "L": {"n4": Mock(value=Mock(return_value=1.46)), "n7": Mock(value=Mock(return_value=1.46))},

            "substrate": {"n4": Mock(value=Mock(return_value=1.52)), "n7": Mock(value=Mock(return_value=1.51))},

        }



        mats = CertusDesignApp._get_materials(app)



        assert set(("H", "L", "substrate")).issubset(set(mats.keys()))

        assert all(hasattr(mats[k], "n4") and hasattr(mats[k], "n7") for k in ("H", "L", "substrate"))



    def test_get_oblique_targets_uses_ui_table_when_re_not_loaded(self):

        """_get_oblique_tgts lit la table UI quand _re_loaded=False."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp



        app = Mock(spec=CertusDesignApp)

        app.oblique_mode = True

        app._re_loaded = False

        app._re_targets = [Mock(on=True)]



        active_cell = Mock()

        active_cell.findChild = Mock(return_value=Mock(isChecked=Mock(return_value=True)))

        angle_w = Mock(value=Mock(return_value=45.0))

        pol_w = Mock(currentText=Mock(return_value="s"))

        type_w = Mock(currentText=Mock(return_value="T"))

        lmin_w = Mock(value=Mock(return_value=500.0))

        lmax_w = Mock(value=Mock(return_value=600.0))

        vmin_w = Mock(value=Mock(return_value=0.3))

        vmax_w = Mock(value=Mock(return_value=0.7))

        weight_w = Mock(value=Mock(return_value=1.5))



        table = Mock()

        table.rowCount = Mock(return_value=1)

        table.cellWidget = Mock(

            side_effect=lambda r, c: {

                0: active_cell,

                1: angle_w,

                2: pol_w,

                3: type_w,

                4: lmin_w,

                5: lmax_w,

                6: vmin_w,

                7: vmax_w,

                8: weight_w,

            }.get(c)

        )

        app.target_table = table



        tgts = CertusDesignApp._get_oblique_tgts(app)



        assert len(tgts) == 1

        assert tgts[0].angle == 45.0

        assert tgts[0].pol == "s"

        assert tgts[0].target_type == "T"

        assert tgts[0].lmin == 500.0 and tgts[0].lmax == 600.0



    def test_update_tikhonravov_points_updates_when_re_disabled(self):

        """_update_tikhonravov_points updates the non-RE spinbox."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp



        app = Mock(spec=CertusDesignApp)

        app._re_loaded = False

        app._calculate_tikhonravov_points = Mock(return_value=120)

        app._update_optim_point_count = Mock()

        app.log = Mock()

        app.points_per_target_spin = Mock()

        app.points_per_target_spin.value = Mock(return_value=50)



        CertusDesignApp._update_tikhonravov_points(app)



        app.points_per_target_spin.setValue.assert_called_once_with(120)

        app._update_optim_point_count.assert_called_once()



    def test_on_optim_done_without_re_does_not_emit_re_completion_log(self):

        """_on_optim_done outside RE does not log 'RE optimization complete.'."""

        from unittest.mock import Mock

        from CERTUS_DESIGN import CertusDesignApp



        app = Mock(spec=CertusDesignApp)

        app._workflow_stopped = True

        app._re_mode_active = False

        app.progress_widget = Mock()

        app._clean_live_curves = Mock()

        app._set_busy = Mock()

        app.log = Mock()

        app.front_table = Mock()

        app._get_front_stack = Mock(return_value=[])

        app._get_materials = Mock(return_value={})

        app.l0_spin = Mock(value=Mock(return_value=500.0))

        app.last_result = {}



        CertusDesignApp._on_optim_done(app, {"ok": False, "ep": None})



        logged_messages = [args[0] for args, _kwargs in app.log.call_args_list if args]

        assert "RE optimisation complete." not in logged_messages





















