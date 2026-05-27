import numpy as np
import pytest
import pandas as pd
from certus.utils.errors import (
    validate_wavelength_range,
    validate_thickness,
    validate_refractive_index,
    CertusValidationError
)
from certus.utils.certus_data import numpy_encoder, SharedIndicesManager, SharedIndicesWorker

def test_validate_wavelength_range():
    # Success cases
    validate_wavelength_range(400.0, 700.0)
    validate_wavelength_range(100.0, 20000.0)
    
    # Failure cases
    with pytest.raises(CertusValidationError, match="must be less than"):
        validate_wavelength_range(700.0, 400.0)
    
    with pytest.raises(CertusValidationError, match="below the physical limit"):
        validate_wavelength_range(50.0, 400.0)
        
    with pytest.raises(CertusValidationError, match="exceeds the physical limit"):
        validate_wavelength_range(400.0, 25000.0)

def test_validate_thickness():
    # Success cases
    validate_thickness(100.0)
    validate_thickness(0.0, allow_zero=True)
    
    # Failure cases
    with pytest.raises(CertusValidationError, match="Negative thickness"):
        validate_thickness(-10.0)
        
    with pytest.raises(CertusValidationError, match="Zero thickness not allowed"):
        validate_thickness(0.0, allow_zero=False)
        
    with pytest.raises(CertusValidationError, match="Thickness too large"):
        validate_thickness(2000000.0)

def test_validate_refractive_index():
    # Success cases
    validate_refractive_index(1.5, 0.01)
    validate_refractive_index(0.5, allow_below_one=True)
    
    # Failure cases
    with pytest.raises(CertusValidationError, match="Refractive index too low"):
        validate_refractive_index(0.5, allow_below_one=False)
    
    with pytest.raises(CertusValidationError, match="Negative refractive index"):
        validate_refractive_index(-1.0)

def test_numpy_encoder():
    assert numpy_encoder(np.int64(42)) == 42
    assert numpy_encoder(np.float64(3.14)) == 3.14
    assert numpy_encoder(np.array([1, 2, 3])) == [1, 2, 3]
    assert numpy_encoder("test") == "test"

def test_shared_indices_workflow():
    clues = {
        500.0: {"H": 2.3, "L": 1.45, "substrate": 1.52},
        600.0: {"H": 2.2, "L": 1.44, "substrate": 1.51}
    }
    
    with SharedIndicesManager(clues) as manager:
        ctx = manager.get_context_info()
        assert "shm_name" in ctx
        
        with SharedIndicesWorker(ctx) as worker:
            # Exact match
            res_500 = worker.get(500.0)
            assert res_500["H"] == pytest.approx(2.3)
            
            # Interpolation
            res_550 = worker.get(550.0)
            assert pytest.approx(res_550["H"]) == 2.25
            
            # Boundary (below)
            res_400 = worker.get(400.0)
            assert res_400["H"] == pytest.approx(2.3)
            
            # Boundary (above)
            res_700 = worker.get(700.0)
            assert res_700["H"] == pytest.approx(2.2)
