"""Unit tests for MachineModel and wavelength-dependent noise sigma(lambda) (Actions 5.8 & 5.9)."""

import numpy as np
import pytest

import certus_physics
from certus_physics import MachineModel


def test_machine_model_default_oms5100():
    """Verify default MachineModel captures OMS 5100 specifications."""
    model = MachineModel()
    assert model.name == "Bühler Leybold Optics OMS 5100"
    assert model.reading_noise_floor_pct == 0.05
    assert model.monochromator_resolution_nm == 0.5
    assert model.get_sigma(550.0) == 0.0005


def test_machine_model_wavelength_dependent_sigma():
    """Verify MachineModel supports wavelength-dependent noise sigma(lambda)."""
    # Simulate higher noise in UV/IR edges
    def custom_sigma(wl_nm: float) -> float:
        return 0.0005 + 0.001 * abs(wl_nm - 550.0) / 500.0

    model = MachineModel(sigma_wl_func=custom_sigma)
    assert model.get_sigma(550.0) == 0.0005
    assert model.get_sigma(1050.0) == 0.0015

    wls = np.array([350.0, 550.0, 1050.0], dtype=np.float64)
    sigmas = model.get_sigma_array(wls)
    assert np.allclose(sigmas, [0.0009, 0.0005, 0.0015])
