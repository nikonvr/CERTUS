"""Integration tests for CERTUS Suite
Covers interactions between modules and complete workflows."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Imports conditionnels
try:
    from certus_physics import Layer, Target, Sample
    from certus_core import get_logger, get_resource_path, setup_logging
    from certus_ui import CertusTheme, apply_certus_theme
    from certus_errors import (
        CertusError,
        CertusValidationError,
        validate_wavelength_range,
    )

    PHYSICS_AVAILABLE = True
except ImportError:
    PHYSICS_AVAILABLE = False

from conftest import compute_spectrum_simple


@pytest.mark.integration
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Modules core non disponibles")
class TestCoreIntegration:
    """Integration tests for core modules."""

    def test_core_modules_interaction(self):
        """Test l'interaction entre les modules core."""
        # Verify that all core modules can be imported together
        logger = get_logger()
        theme = CertusTheme
        resource_path = get_resource_path

        assert logger is not None
        assert theme is not None
        assert callable(resource_path)

    def test_logging_integration(self):
        """Test the integration of the logging system."""
        # Configure le logging
        logger = setup_logging()

        # Tester que le logger fonctionne
        logger.info("Test integration")

        assert logger.name == "CERTUS"
        assert len(logger.handlers) > 0

    def test_theme_integration(self):
        """Test theme system integration."""
        # Configure theme
        CertusTheme.configure("light")

        # Verify that the colors are defined
        assert CertusTheme.BACKGROUND is not None
        assert CertusTheme.TEXT_MAIN is not None
        assert CertusTheme.PRIMARY is not None

    def test_resource_management(self):
        """Test la gestion des ressources."""
        # Test avec un fichier existant
        try:
            resource_path = get_resource_path("certus_theme.json")
            assert isinstance(resource_path, str)
        except FileNotFoundError:
            pytest.skip("certus_theme.json not found")


@pytest.mark.integration
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Physics module non disponible")
class TestPhysicsIntegration:
    """Integration tests for the physics module."""

    def test_physics_workflow(self, sample_layers, sample_wavelengths):
        """Test un workflow physics complet."""
        # Create a test structure
        layers = sample_layers
        wavelengths = sample_wavelengths

        # Calculate the spectrum
        spectrum = compute_spectrum_simple(layers, wavelengths)

        # Validate the results
        assert isinstance(spectrum, np.ndarray)
        assert len(spectrum) == len(wavelengths)
        assert np.all(np.isfinite(spectrum))

    def test_layer_target_interaction(self):
        """Test l'interaction entre Layer et Target."""
        # Create layers and targets
        layers = [Layer(mat="SiO2", qwot=1.0), Layer(mat="TiO2", qwot=0.5)]

        targets = [
            Target(lmin=550.0, lmax=550.0, tmin=0.5, tmax=0.5, w=1.0),
            Target(lmin=650.0, lmax=650.0, tmin=0.8, tmax=0.8, w=0.5),
        ]

        # Valider les objets
        assert len(layers) == 2
        assert len(targets) == 2
        assert all(hasattr(layer, "mat") for layer in layers)
        assert all(hasattr(target, "lmin") for target in targets)

    def test_validation_integration(self):
        """Test the integration of validation functions."""
        # Validate a wavelength range
        validate_wavelength_range(400.0, 800.0)

        # Valider des couches
        from certus_errors import validate_thickness

        validate_thickness(100.0)

        # Validate refractive clues
        from certus_errors import validate_refractive_index

        validate_refractive_index(1.5, 0.0)


@pytest.mark.integration
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Modules non disponibles")
class TestModuleInteraction:
    """Tests d'interaction entre les modules principaux."""

    def test_module_availability(self):
        """Test the availability of main modules."""
        modules_to_test = ["certus_core", "certus_ui", "certus_errors"]

        available_modules = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                available_modules.append(module_name)
            except ImportError:
                pass

        # At least core modules should be available
        assert len(available_modules) >= 2

    def test_configuration_persistence(self, temp_directory):
        """Test la persistance de la configuration."""
        # Test theme configuration
        from certus_core import save_theme_config, load_theme_config

        save_theme_config("dark")
        theme = load_theme_config()
        assert theme == "dark"

        save_theme_config("light")
        theme = load_theme_config()
        assert theme == "light"

    def test_error_propagation(self):
        """Test la propagation des errors entre modules."""
        # Create an error and check that it propagate correctly
        try:
            raise CertusValidationError(
                "Test integration", "Test details", "Test suggestion"
            )
        except CertusValidationError as e:
            assert e.message == "Test integration"
            assert e.details == "Test details"
            assert e.suggestion == "Test suggestion"


@pytest.mark.integration
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Physics module non disponible")
class TestWorkflowIntegration:
    """Tests for les workflows complets."""

    def test_optical_design_workflow(self, sample_layers, sample_wavelengths):
        """Test a complete optical design workflow."""
        # 1. Define layers
        layers = sample_layers

        # 2. Define wavelengths
        wavelengths = sample_wavelengths

        # 3. Calculate the spectrum
        spectrum = compute_spectrum_simple(layers, wavelengths)

        # 4. Validate results
        assert isinstance(spectrum, np.ndarray)
        assert len(spectrum) == len(wavelengths)
        assert np.all(np.isfinite(spectrum))

        # 5. Check physical constraints
        assert np.all(spectrum >= 0)  # R/T must be positive
        assert np.all(spectrum <= 1)  # R/T must be <= 1

    def test_validation_workflow(self):
        """Test un workflow de validation complet."""
        # 1. Valider les longueurs d'onde
        validate_wavelength_range(400.0, 800.0)

        # 2. Validate the thicknesses
        from certus_errors import validate_thickness

        validate_thickness(100.0)

        # 3. Validate the clues
        from certus_errors import validate_refractive_index

        validate_refractive_index(1.5, 0.0)

        # 4. Valider les data spectrales
        from certus_errors import validate_spectral_data

        wavelengths = np.linspace(400, 800, 100)
        values = np.random.uniform(0, 1, 100)
        validate_spectral_data(wavelengths, values)

    def test_configuration_workflow(self):
        """Test un workflow de configuration complet."""
        # 1. Configure le logging
        setup_logging()

        # 2. Configure theme
        CertusTheme.configure("light")

        # 3. Saver la configuration
        from certus_core import save_theme_config, load_theme_config

        save_theme_config("dark")

        # 4. Charger la configuration
        theme = load_theme_config()
        assert theme == "dark"

        # 5. Valider la configuration
        assert CertusTheme.BACKGROUND is not None


@pytest.mark.performance
@pytest.mark.integration
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Physics module non disponible")
class TestPerformanceIntegration:
    """Performance testing for integration workflows."""

    def test_calculationation_performance(self, sample_layers, sample_wavelengths):
        """Test les performances de calculation dans un workflow."""
        import time

        # Measure le temps de calculation
        start_time = time.time()
        spectrum = compute_spectrum_simple(sample_layers, sample_wavelengths)
        end_time = time.time()

        calculationation_time = end_time - start_time

        # The calculation should be quick
        assert calculationation_time < 1.0
        assert isinstance(spectrum, np.ndarray)

    def test_memory_usage(self, sample_layers, sample_wavelengths):
        """Test l'memory usage dans un workflow."""
        try:
            import tracemalloc

            # Start memory tracking
            tracemalloc.start()

            # Effectuer des calculations
            compute_spectrum_simple(sample_layers, sample_wavelengths)

            # Measure memory usage
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Memory usage should be reasonable
            assert peak < 50 * 1024 * 1024  # < 50 MB

        except ImportError:
            pytest.skip("tracemalloc non disponible")


@pytest.mark.e2e
@pytest.mark.skipif(not PHYSICS_AVAILABLE, reason="Modules non disponibles")
class TestEndToEndIntegration:
    """End-to-end testing for the entire system."""

    def test_complete_optical_simulation(self, sample_layers, sample_wavelengths):
        """Test a complete optical simulation."""
        # 1. Configuration initiale
        logger = setup_logging()
        CertusTheme.configure("light")

        # 2. Validation of inputs
        validate_wavelength_range(sample_wavelengths[0], sample_wavelengths[-1])

        # 3. Optical calculation
        spectrum = compute_spectrum_simple(sample_layers, sample_wavelengths)

        # 4. Validation of results
        assert isinstance(spectrum, np.ndarray)
        assert len(spectrum) == len(sample_wavelengths)
        assert np.all(np.isfinite(spectrum))

        # 5. Logging results
        logger.info(f"Simulation completed: {len(spectrum)} points calculated")

        # Le workflow est complet
        assert True

    def test_error_handling_workflow(self):
        """Test un workflow complet avec gestion d'errors."""
        # 1. Configuration
        logger = setup_logging()

        # 2. Attempting an invalid operation
        try:
            validate_wavelength_range(800.0, 400.0)  # Invalide
            assert False, "Devrait lever une exception"
        except (CertusValidationError, ValueError) as e:
            # 3. Logger l'error
            logger.warning(f"Validation error: {e}")

            # 4. Check error handling
            assert True  # The exception has been raised

        # Le workflow d'error est correct
        assert True
