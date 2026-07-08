"""
CERTUS Domain - Layer Entity

Entity représentant une couche optique dans un stack.
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
    Couche optique dans un stack multicouche.

    Entity (pas value object): a une identité (position dans le stack).

    Invariants:
    - material_id non vide
    - thickness > 0
    - refractive_index valide (n≥1, k≥0)

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
        """Validation invariants."""
        if not self.material_id or not isinstance(self.material_id, str):
            raise ValueError("material_id must be non-empty string")

        if not isinstance(self.thickness, Thickness):
            raise TypeError(f"thickness must be Thickness, got {type(self.thickness)}")

        if not isinstance(self.refractive_index, RefractiveIndex):
            raise TypeError(f"refractive_index must be RefractiveIndex, got {type(self.refractive_index)}")

    def optical_thickness_at(self, wavelength: Wavelength) -> float:
        """
        Épaisseur optique n×d à une longueur d'onde.

        Args:
            wavelength: Longueur d'onde

        Returns:
            Épaisseur optique en nm
        """
        return self.thickness.optical_thickness(self.refractive_index.n)

    def is_quarter_wave_at(self, wavelength: Wavelength, tolerance: float = 0.05) -> bool:
        """
        Vérifie si la couche est λ/4 à cette longueur d'onde.

        Args:
            wavelength: Longueur d'onde de référence
            tolerance: Tolérance relative (0.05 = 5%)

        Returns:
            True si QWOT ≈ 1.0 (à tolérance près)
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
