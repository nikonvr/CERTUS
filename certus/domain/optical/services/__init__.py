"""
CERTUS Domain - TMM Calculator Domain Service (Protocol)

Domain service pour calculs TMM.
L'implémentation sera dans infrastructure layer.
"""

from typing import Protocol
from certus.domain.optical.entities import OpticalStack
from certus.domain.optical.value_objects import WavelengthRange


class Spectrum(Protocol):
    """
    Spectrum result (protocol - duck typing).

    L'implémentation réelle sera dans infrastructure.
    """

    wavelengths: tuple[float, ...]
    reflectance: tuple[float, ...]
    transmittance: tuple[float, ...]
    absorptance: tuple[float, ...]


class TMM_Calculator(Protocol):
    """
    Domain service protocol pour calculs TMM.

    Interface définie dans le domain, implémentation dans infrastructure.
    Permet de découpler le domain de l'implémentation physics.

    Examples:
        >>> calculator = LegacyTMM_Adapter()  # Infrastructure
        >>> spectrum = calculator.calculate_spectrum(stack, wl_range, 100)
    """

    def calculate_spectrum(
        self,
        stack: OpticalStack,
        wavelength_range: WavelengthRange,
        num_points: int = 100,
    ) -> Spectrum:
        """
        Calculate optical spectrum using TMM.

        Args:
            stack: Optical stack to analyze
            wavelength_range: Spectral range [min, max] nm
            num_points: Number of wavelength sampling points

        Returns:
            Calculated spectrum with R(λ), T(λ), A(λ)

        Raises:
            ValueError: If num_points < 2 or invalid wavelength range
        """
        ...

    def calculate_at_wavelength(
        self,
        stack: OpticalStack,
        wavelength: float,
    ) -> tuple[float, float, float]:
        """
        Calculate R, T, A at single wavelength.

        Args:
            stack: Optical stack
            wavelength: Wavelength in nm

        Returns:
            (R, T, A) tuple at this wavelength
        """
        ...


class SpectrumAnalyzer(Protocol):
    """
    Domain service protocol pour analyse de spectres.

    Analyse les spectres calculés (métriques, features extraction).
    """

    def calculate_rmse(
        self,
        calculated: Spectrum,
        target: Spectrum,
    ) -> float:
        """
        Calculate RMSE between calculated and target spectrum.

        Args:
            calculated: Calculated spectrum
            target: Target spectrum

        Returns:
            RMSE value
        """
        ...

    def extract_band_edges(
        self,
        spectrum: Spectrum,
        threshold: float = 0.5,
    ) -> tuple[float, float]:
        """
        Extract band-pass filter edges.

        Args:
            spectrum: Spectrum to analyze
            threshold: Threshold for edge detection (0-1)

        Returns:
            (lambda_low, lambda_high) band edges in nm
        """
        ...
