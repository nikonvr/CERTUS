"""
Refractive Index Value Object

Représente l'indice de réfraction complexe n + ik.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RefractiveIndex:
    """
    Indice de réfraction complexe: n + ik

    n: partie réelle (vitesse phase)
    k: partie imaginaire (absorption)

    Invariants:
    - n >= 1.0 (physique, n=1 pour vide)
    - k >= 0.0 (absorption toujours positive)
    - Valeurs finies

    Examples:
        >>> ri = RefractiveIndex(n=1.5, k=0.0)  # Verre sans absorption
        >>> ri.to_complex()
        (1.5+0j)
        >>> ri.is_absorbing()
        False
    """

    n: float  # Real part
    k: float  # Imaginary part (extinction coefficient)

    MIN_N: float = 1.0  # Physics: n >= 1 (vacuum = 1.0)
    MAX_N: float = 10.0  # Realistic upper bound for thin films
    MAX_K: float = 10.0  # High absorption bound for metals

    def __post_init__(self):
        """Physical invariants validation."""
        if not isinstance(self.n, (int, float)) or not isinstance(self.k, (int, float)):
            raise TypeError("n and k must be numeric")

        if not (np.isfinite(self.n) and np.isfinite(self.k)):
            raise ValueError(f"n and k must be finite, got n={self.n}, k={self.k}")

        if self.n < self.MIN_N:
            raise ValueError(f"Real part n={self.n} < {self.MIN_N} violates physics (n >= 1)")

        if self.n > self.MAX_N:
            raise ValueError(f"Real part n={self.n} > {self.MAX_N} suspiciously high")

        if self.k < 0.0:
            raise ValueError(f"Extinction coefficient k={self.k} < 0 (must be >= 0)")

        if self.k > self.MAX_K:
            raise ValueError(f"Extinction coefficient k={self.k} > {self.MAX_K} extreme")

    def to_complex(self) -> complex:
        """Indice complexe dans la convention du projet : ``n̂ = n − ik`` (k >= 0).

        Cette classe renvoyait auparavant ``n + ik``, à rebours de la convention
        Macleod utilisée partout ailleurs dans CERTUS. Le résultat de
        ``reflectance_normal_incidence`` est identique dans les deux conventions
        (``|r|²`` est invariant par conjugaison), donc le défaut était LATENT — mais
        toute valeur issue d'ici et transmise au TMM produisait un milieu à GAIN,
        silencieusement « rattrapé » par la garde de ``compute_TMM_generic``.

        Returns:
            ``complex(n, -k)``.
        """
        return complex(self.n, -self.k)

    def is_absorbing(self, threshold: float = 1e-6) -> bool:
        """Check if material absorbs (k > threshold)."""
        return self.k > threshold

    def is_transparent(self, threshold: float = 1e-6) -> bool:
        """Check if material is transparent (k ≈ 0)."""
        return self.k <= threshold

    def absorption_coefficient(self, wavelength_nm: float) -> float:
        """
        Absorption coefficient α = 4πk/λ (in nm⁻¹).

        Intensity decay: I(z) = I₀ exp(-αz)

        Args:
            wavelength_nm: Wavelength in nm

        Returns:
            α in nm⁻¹
        """
        if wavelength_nm <= 0:
            raise ValueError(f"Invalid wavelength: {wavelength_nm}")

        return (4 * np.pi * self.k) / wavelength_nm

    def penetration_depth_nm(self, wavelength_nm: float) -> float:
        """
        Penetration depth δ = 1/α = λ/(4πk) (in nm).

        Depth where intensity drops to 1/e.

        Returns:
            Penetration depth in nm (inf if k=0)
        """
        if self.k == 0.0:
            return float("inf")

        return wavelength_nm / (4 * np.pi * self.k)

    def reflectance_normal_incidence(self) -> float:
        """
        Reflectance at normal incidence from air (n=1).

        R = |(n_complex - 1) / (n_complex + 1)|²

        Returns:
            Reflectance [0, 1]
        """
        n_complex = self.to_complex()
        r = (n_complex - 1.0) / (n_complex + 1.0)
        return abs(r) ** 2

    def __str__(self) -> str:
        if self.is_transparent():
            return f"n={self.n:.4f}"
        else:
            return f"n={self.n:.4f} + i{self.k:.6f}"

    def __repr__(self) -> str:
        return f"RefractiveIndex(n={self.n}, k={self.k})"


@dataclass(frozen=True)
class RefractiveIndexDispersion:
    """
    Dispersion de l'indice: n(λ), k(λ).

    Permet de représenter la dépendance en longueur d'onde.
    Pour l'instant, stub pour évolution future.
    """

    wavelengths_nm: tuple[float, ...]
    n_values: tuple[float, ...]
    k_values: tuple[float, ...]

    def __post_init__(self):
        if not (len(self.wavelengths_nm) == len(self.n_values) == len(self.k_values)):
            raise ValueError("Wavelengths, n and k arrays must have same length")

        if len(self.wavelengths_nm) < 2:
            raise ValueError("Need at least 2 wavelength points for dispersion")

        # Validate all indices
        for n, k in zip(self.n_values, self.k_values):
            RefractiveIndex(n, k)  # Will raise if invalid

    def at_wavelength(self, wavelength_nm: float) -> RefractiveIndex:
        """Interpolate n, k at given wavelength (linear)."""
        n_interp = np.interp(wavelength_nm, self.wavelengths_nm, self.n_values)
        k_interp = np.interp(wavelength_nm, self.wavelengths_nm, self.k_values)
        return RefractiveIndex(n=float(n_interp), k=float(k_interp))
