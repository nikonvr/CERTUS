"""The colour-matching functions of the colorimetry are the CIE's, so a spectrally flat reflector has no colour (D92).

Since the initial commit, `certus_colorimetry` carried an x̄, ȳ, z̄ that were not the CIE 1931 functions: ȳ followed the
CIE curve up to 425 nm, then ran through it twice too fast and peaked at 490 nm instead of 555, and x̄ peaked at 460 nm
instead of 600. A perfect reflector (R = 1 at every wavelength) came out at L*a*b* = (100, 60.4, -113.1), a saturated
violet, instead of (100, 0, 0) (measured on 2026-10-06), and the Monte-Carlo colour analysis of DESIGN with it.

The reference rows are copied from the CIE's own file, CIE_xyz_1931_2deg.csv (CIE 2019, DOI 10.25039/CIE.DS.xvudnb9b,
CC BY-SA 4.0), not from the module under test.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics import certus_colorimetry as colorimetry

#: (wavelength in nm, x̄, ȳ, z̄): rows of CIE_xyz_1931_2deg.csv.
CIE_ROWS = (
    (380.0, 0.001368, 0.000039, 0.006450001),
    (445.0, 0.34806, 0.0298, 1.7826),
    (555.0, 0.5120501, 1.0, 0.005749999),
    (600.0, 1.0622, 0.631, 0.0008),
    (700.0, 0.01135916, 0.004102, 0.0),
    (780.0, 0.00004150994, 0.00001499, 0.0),
)


@pytest.mark.parametrize(("wavelength", "x_bar", "y_bar", "z_bar"), CIE_ROWS)
def test_the_tables_hold_the_rows_of_the_cie_file(wavelength, x_bar, y_bar, z_bar):
    (i,) = np.flatnonzero(colorimetry.CIE_LAMBDA == wavelength)

    assert (colorimetry.CIE_X[i], colorimetry.CIE_Y[i], colorimetry.CIE_Z[i]) == (x_bar, y_bar, z_bar)


def test_y_bar_peaks_at_555_nm_and_x_bar_at_600_nm():
    assert colorimetry.CIE_LAMBDA[np.argmax(colorimetry.CIE_Y)] == 555.0
    assert colorimetry.CIE_LAMBDA[np.argmax(colorimetry.CIE_X)] == 600.0


@pytest.mark.parametrize("reflectance", [1.0, 0.5, 0.04])
def test_a_spectrally_flat_reflector_has_no_colour(reflectance):
    wavelengths = np.arange(380.0, 781.0, 1.0)

    _lightness, a, b = colorimetry.xyz_to_lab(
        colorimetry.xyz_from_spectrum(wavelengths, np.full_like(wavelengths, reflectance))
    )

    assert abs(a) < 0.02
    assert abs(b) < 0.02
