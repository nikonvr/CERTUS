"""
Wavelength Value Object

Représente une longueur d'onde avec invariants physiques.
Immutable par design (frozen dataclass).
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Wavelength:
    """
    Longueur d'onde en nanomètres.

    Invariants:
    - 100nm ≤ λ ≤ 10000nm (UV proche → IR moyen)
    - Valeur finie (pas NaN, pas Inf)

    Examples:
        >>> wl = Wavelength(550.0)  # Vert
        >>> wl.to_meters()
        5.5e-07
        >>> wl.to_micrometers()
        0.55
    """

    nm: float

    # Limites physiques réalistes pour optique couches minces
    MIN_NM: float = 100.0  # UV proche
    MAX_NM: float = 10000.0  # IR moyen

    def __post_init__(self):
        """Validation invariants."""
        if not isinstance(self.nm, (int, float)):
            raise TypeError(f"Wavelength must be numeric, got {type(self.nm)}")

        if not np.isfinite(self.nm):
            raise ValueError(f"Wavelength must be finite, got {self.nm}")

        if not (self.MIN_NM <= self.nm <= self.MAX_NM):
            raise ValueError(f"Wavelength {self.nm}nm out of range [{self.MIN_NM}, {self.MAX_NM}]nm")

    def to_meters(self) -> float:
        """Convert to meters (SI unit)."""
        return self.nm * 1e-9

    def to_micrometers(self) -> float:
        """Convert to micrometers."""
        return self.nm * 1e-3

    def to_angstroms(self) -> float:
        """Convert to angstroms (Å)."""
        return self.nm * 10.0

    @classmethod
    def from_meters(cls, meters: float) -> Wavelength:
        """Create from meters."""
        return cls(meters * 1e9)

    @classmethod
    def from_micrometers(cls, micrometers: float) -> Wavelength:
        """Create from micrometers."""
        return cls(micrometers * 1e3)

    def energy_ev(self) -> float:
        """
        Photon energy in electron-volts.

        E = hc/λ ≈ 1240 eV·nm / λ[nm]
        """
        return 1239.84193 / self.nm  # Planck constant × speed of light / e

    def frequency_hz(self) -> float:
        """Frequency in Hz."""
        c = 299792458.0  # Speed of light m/s
        return c / self.to_meters()

    def __str__(self) -> str:
        return f"{self.nm:.2f}nm"

    def __repr__(self) -> str:
        return f"Wavelength({self.nm})"


@dataclass(frozen=True)
class WavelengthRange:
    """
    Range de longueurs d'onde [min, max].

    Invariants:
    - min < max
    - Tous deux valides selon Wavelength invariants
    """

    min_wl: Wavelength
    max_wl: Wavelength

    def __post_init__(self):
        if self.min_wl.nm >= self.max_wl.nm:
            raise ValueError(f"Invalid range: min={self.min_wl.nm} >= max={self.max_wl.nm}")

    def contains(self, wavelength: Wavelength) -> bool:
        """Check if wavelength is in range."""
        return self.min_wl.nm <= wavelength.nm <= self.max_wl.nm

    def span_nm(self) -> float:
        """Range span in nm."""
        return self.max_wl.nm - self.min_wl.nm

    def center(self) -> Wavelength:
        """Center wavelength."""
        return Wavelength((self.min_wl.nm + self.max_wl.nm) / 2)

    def linspace(self, num_points: int) -> list[Wavelength]:
        """Generate linearly spaced wavelengths."""
        if num_points < 2:
            raise ValueError("num_points must be >= 2")

        wl_values = np.linspace(self.min_wl.nm, self.max_wl.nm, num_points)
        return [Wavelength(wl) for wl in wl_values]

    def __str__(self) -> str:
        return f"[{self.min_wl.nm:.1f}-{self.max_wl.nm:.1f}nm]"
