"""
CERTUS Domain - Layer Entity

Entity representing an optical layer within a stack.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from certus.domain.optical.value_objects import (
    Thickness,
    RefractiveIndex,
    Wavelength,
)


@dataclass
class Layer:
    """
    Optical layer in a multilayer stack.

    Entity (not value object): has an identity (position in stack).

    Invariants:
    - non-empty material_id
    - thickness > 0
    - valid refractive_index (n>=1, k>=0)

    Examples:
        >>> layer = Layer("TiO2", Thickness(50.0), RefractiveIndex(2.3, 0.0))
        >>> layer.optical_thickness_at(Wavelength(550.0))
        115.0
    """

    material_id: str
    thickness: Thickness
    refractive_index: RefractiveIndex
    metadata: Optional[dict] = None

    def __post_init__(self):
        """Invariant validation."""
        if not self.material_id or not isinstance(self.material_id, str):
            raise ValueError("material_id must be non-empty string")

        if not isinstance(self.thickness, Thickness):
            raise TypeError(f"thickness must be Thickness, got {type(self.thickness)}")

        if not isinstance(self.refractive_index, RefractiveIndex):
            raise TypeError(f"refractive_index must be RefractiveIndex, got {type(self.refractive_index)}")

    def optical_thickness_at(self, wavelength: Wavelength) -> float:
        """
        Optical thickness n*d at a wavelength.

        Args:
            wavelength: Wavelength

        Returns:
            Optical thickness in nm
        """
        return self.thickness.optical_thickness(self.refractive_index.n)

    def is_quarter_wave_at(self, wavelength: Wavelength, tolerance: float = 0.05) -> bool:
        """
        Check if the layer is quarter-wave (lambda/4) at this wavelength.

        Args:
            wavelength: Reference wavelength
            tolerance: Relative tolerance (0.05 = 5%)

        Returns:
            True if QWOT ≈ 1.0 (within tolerance)
        """
        qwot = self.thickness.qwot_at_wavelength(wavelength.nm, self.refractive_index.n)
        return abs(qwot - 1.0) < tolerance

    def is_absorbing(self, threshold: float = 1e-6) -> bool:
        """Check if layer absorbs light (k > threshold)."""
        return self.refractive_index.is_absorbing(threshold)

    def is_transparent(self, threshold: float = 1e-6) -> bool:
        """Check if layer is transparent (k ≈ 0)."""
        return self.refractive_index.is_transparent(threshold)

    def __str__(self) -> str:
        return f"Layer({self.material_id}, {self.thickness}, n={self.refractive_index.n:.3f})"

    def __repr__(self) -> str:
        return (
            f"Layer(material_id='{self.material_id}', "
            f"thickness={self.thickness!r}, "
            f"refractive_index={self.refractive_index!r})"
        )
