"""
CERTUS STRAT MACHINE MODEL
==========================
Part of CERTUS Suite (2026)

Centralized hardware specifications for optical deposition monitoring machines
(e.g., Bühler Leybold Optics OMS 5100).
"""

from dataclasses import dataclass
from typing import Callable
import numpy as np

OMS5100_DEFAULT_READING_NOISE_PCT: float = 0.05
OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM: float = 0.5
OMS5100_DEFAULT_5_SIGMA_FACTOR: float = 1.66


@dataclass
class MachineModel:
    """Hardware specification model for an optical monitoring system (e.g. OMS 5100).

    Attributes:
        name: Name of the monitoring system.
        date: Reference date for hardware specs.
        reading_noise_floor_pct: Measured RMS reading noise floor (% of T).
        monochromator_resolution_nm: Monochromator step / precision in nm.
        trigger_tolerance: Level trigger tolerance in T units (0..1).
        tp_hysteresis_factor: Turning point detector hysteresis multiplier.
        sigma_wl_func: Optional function(wl_nm -> float) returning wavelength-dependent noise sigma.
    """

    name: str = "Bühler Leybold Optics OMS 5100"
    date: str = "2026-08-08"
    reading_noise_floor_pct: float = OMS5100_DEFAULT_READING_NOISE_PCT
    monochromator_resolution_nm: float = OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM
    trigger_tolerance: float = 0.05
    tp_hysteresis_factor: float = OMS5100_DEFAULT_5_SIGMA_FACTOR
    sigma_wl_func: Callable[[float], float] | None = None

    def get_sigma(self, wl_nm: float) -> float:
        """Return RMS reading noise sigma (in T units 0..1) for a given wavelength in nm."""
        if self.sigma_wl_func is not None:
            return max(0.0, float(self.sigma_wl_func(wl_nm)))
        return max(0.0, float(self.reading_noise_floor_pct) / 100.0)

    def get_sigma_array(self, wls_nm: np.ndarray) -> np.ndarray:
        """Return array of noise sigmas across wavelength grid wls_nm."""
        wls = np.ascontiguousarray(wls_nm, dtype=np.float64)
        if self.sigma_wl_func is not None:
            return np.array([self.get_sigma(float(w)) for w in wls], dtype=np.float64)
        flat_val = self.get_sigma(550.0)
        return np.full_like(wls, flat_val, dtype=np.float64)
