"""
Value Objects for Optical Domain
"""

from .wavelength import Wavelength, WavelengthRange
from .thickness import Thickness
from .refractive_index import RefractiveIndex, RefractiveIndexDispersion

__all__ = [
    "Wavelength",
    "WavelengthRange",
    "Thickness",
    "RefractiveIndex",
    "RefractiveIndexDispersion",
]
