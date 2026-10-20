"""Loading a measurement sheet must not destroy a wavelength grid finer than the rounding asks for.

`CurveSmootherGUI.load_file` reads the workbook with `round_wavelength_decimals=1`, which rounded the whole axis in the
DataFrame; "Save Clean Data" then wrote that rounded axis, so a spectrum measured every 0.05 nm came back on a 0.1 nm grid
with repeated wavelengths (UX-55 in docs/AUDITS.md). The rounding now snaps the axis to the decimal grid only when it
loses nothing (floating-point noise such as 400.0000000004); a real finer grid is kept as it was measured.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from certus.ui.certus_measurement_excel_ui import read_measurement_excel


def _read(tmp_path, wavelengths, decimals=1) -> np.ndarray:
    path = tmp_path / "measurement.xlsx"
    pd.DataFrame({"Wavelength": wavelengths, "T": np.linspace(0.1, 0.9, len(wavelengths))}).to_excel(path, index=False)
    df = read_measurement_excel(str(path), None, round_wavelength_decimals=decimals)
    assert df is not None
    return df.iloc[:, 0].to_numpy(dtype=np.float64)


def test_a_grid_finer_than_the_rounding_is_kept_as_measured(tmp_path) -> None:
    measured = [400.00, 400.05, 400.10, 400.15, 400.20]

    axis = _read(tmp_path, measured)

    assert np.array_equal(axis, np.asarray(measured))


def test_a_finer_grid_does_not_end_up_with_repeated_wavelengths(tmp_path) -> None:
    axis = _read(tmp_path, [500.00, 500.04, 500.08, 500.12, 500.16, 500.20])

    assert len(np.unique(axis)) == len(axis)


def test_floating_point_noise_on_a_decimal_grid_is_still_snapped(tmp_path) -> None:
    """The cleanup the rounding was there for is kept: nothing is lost by snapping this axis."""
    axis = _read(tmp_path, [400.0000000004, 400.1000000003, 400.1999999996])

    assert np.array_equal(axis, np.asarray([400.0, 400.1, 400.2]))


def test_no_rounding_is_asked_no_rounding_is_done(tmp_path) -> None:
    measured = [400.013, 400.057, 400.101]

    axis = _read(tmp_path, measured, decimals=None)

    assert np.array_equal(axis, np.asarray(measured))
