"""
Value Objects for Optical Domain
"""

from .refractive_index import RefractiveIndex, RefractiveIndexDispersion
from .thickness import Thickness
from .wavelength import Wavelength, WavelengthRange

__all__ = [
    "RefractiveIndex",
    "RefractiveIndexDispersion",
    "Thickness",
    "Wavelength",
    "WavelengthRange",
]
