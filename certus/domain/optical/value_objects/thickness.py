"""
Thickness Value Object

Représente une épaisseur de couche mince.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Thickness:
    """
    Épaisseur de couche en nanomètres.

    Invariants:
    - 0 < thickness ≤ 100000nm (10µm max réaliste)
    - Valeur finie

    Examples:
        >>> t = Thickness(100.0)  # 100nm
        >>> t.to_meters()
        1e-07
    """

    nm: float

    MIN_NM: float = 0.0  # Strictement positif
    MAX_NM: float = 100000.0  # 10µm max

    def __post_init__(self):
        """Validation invariants."""
        if not isinstance(self.nm, (int, float)):
            raise TypeError(f"Thickness must be numeric, got {type(self.nm)}")

        if not np.isfinite(self.nm):
            raise ValueError(f"Thickness must be finite, got {self.nm}")

        if not (self.MIN_NM < self.nm <= self.MAX_NM):
            raise ValueError(f"Thickness {self.nm}nm out of range ({self.MIN_NM}, {self.MAX_NM}]nm")

    def to_meters(self) -> float:
        """Convert to meters."""
        return self.nm * 1e-9

    def to_micrometers(self) -> float:
        """Convert to micrometers."""
        return self.nm * 1e-3

    def to_angstroms(self) -> float:
        """Convert to angstroms."""
        return self.nm * 10.0

    @classmethod
    def from_meters(cls, meters: float) -> Thickness:
        """Create from meters."""
        return cls(meters * 1e9)

    @classmethod
    def from_micrometers(cls, micrometers: float) -> Thickness:
        """Create from micrometers."""
        return cls(micrometers * 1e3)

    def optical_thickness(self, refractive_index: float) -> float:
        """
        Optical thickness = n × d (physical thickness).

        Args:
            refractive_index: Real part of refractive index (n)

        Returns:
            Optical thickness in nm
        """
        if refractive_index < 1.0:
            raise ValueError(f"Invalid refractive index: {refractive_index} < 1.0")

        return self.nm * refractive_index

    def qwot_at_wavelength(self, wavelength_nm: float, n: float) -> float:
        """
        Express thickness in Quarter-Wave Optical Thickness (QWOT) units.

        QWOT = λ/(4n) where λ is wavelength, n is refractive index
        Thickness in QWOT = (4nd)/λ

        Args:
            wavelength_nm: Wavelength in nm
            n: Refractive index

        Returns:
            Thickness expressed in QWOT units
        """
        if wavelength_nm <= 0:
            raise ValueError(f"Invalid wavelength: {wavelength_nm}")
        if n < 1.0:
            raise ValueError(f"Invalid refractive index: {n}")

        return (4 * n * self.nm) / wavelength_nm

    def __str__(self) -> str:
        if self.nm < 1000:
            return f"{self.nm:.2f}nm"
        else:
            return f"{self.nm / 1000:.3f}µm"

    def __repr__(self) -> str:
        return f"Thickness({self.nm})"
