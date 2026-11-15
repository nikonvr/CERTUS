"""A measurement file is in percent or in fractions as a whole, never column by column (audit 2026-11-15, M-L4c).

The percent decision was taken per column: an antireflection R in percent (maximum below 1) next to a T in percent
(maximum 92) was kept as a fraction, a reflectance 100 times too large. RE decided per column of the measurement sheet;
INDEX and METAL through ``load_spectrum_columns``, whose threshold was also 1.5 instead of 1.05.
"""

from __future__ import annotations

import numpy as np
import openpyxl
import pandas as pd

from certus.ui.certus_re_excel_mixin import CertusREExcelMixin
from certus.ui.certus_re_table_mixin import CertusRETableMixin
from certus.utils.certus_data import load_spectrum_columns

WLS = [500.0, 550.0, 600.0, 650.0]
R_PERCENT = [0.8, 0.5, 0.3, 0.6]
T_PERCENT = [91.0, 92.0, 91.5, 90.0]


class _Sheet(CertusREExcelMixin, CertusRETableMixin):
    def log(self, *_args, **_kwargs) -> None:
        pass


def _measurement_sheet(r_values: list[float], t_values: list[float]):
    ws = openpyxl.Workbook().active
    ws.append(["wavelength (nm)", "R 8 s", "T 0"])
    for row in zip(WLS, r_values, t_values, strict=True):
        ws.append(list(row))
    return ws


def test_re_reads_a_small_r_in_percent_next_to_a_t_in_percent() -> None:
    _wls, columns, _notes = _Sheet()._parse_re_measurement(_measurement_sheet(R_PERCENT, T_PERCENT))
    by_type = {spec.target_type: values for spec, values in columns}
    np.testing.assert_allclose(by_type["T"], np.array(T_PERCENT) / 100.0)
    np.testing.assert_allclose(by_type["R"], np.array(R_PERCENT) / 100.0)


def test_re_keeps_a_sheet_of_fractions() -> None:
    r_frac, t_frac = [0.008, 0.005, 0.003, 0.006], [0.91, 0.92, 0.915, 0.90]
    _wls, columns, _notes = _Sheet()._parse_re_measurement(_measurement_sheet(r_frac, t_frac))
    by_type = {spec.target_type: values for spec, values in columns}
    np.testing.assert_allclose(by_type["T"], t_frac)
    np.testing.assert_allclose(by_type["R"], r_frac)


def _csv(tmp_path, columns: dict[str, list[float]]) -> str:
    path = tmp_path / "spectrum.csv"
    pd.DataFrame({"x": WLS, **columns}).to_csv(path, index=False)
    return str(path)


def test_the_spectrum_loader_scales_every_column_of_a_percent_file(tmp_path) -> None:
    result = load_spectrum_columns(_csv(tmp_path, {"t": T_PERCENT, "r": R_PERCENT}))
    assert result.normalised_to_fraction is True
    np.testing.assert_allclose(result.y_columns["T"], np.array(T_PERCENT) / 100.0)
    np.testing.assert_allclose(result.y_columns["R"], np.array(R_PERCENT) / 100.0)


def test_the_spectrum_loader_reads_an_antireflection_r_in_percent(tmp_path) -> None:
    result = load_spectrum_columns(_csv(tmp_path, {"r": [0.2, 0.6, 1.2, 0.9]}), column_roles={0: "lambda", 1: "R"})
    assert result.normalised_to_fraction is True
    np.testing.assert_allclose(result.y_columns["R"], [0.002, 0.006, 0.012, 0.009])


def test_the_spectrum_loader_keeps_a_file_of_fractions(tmp_path) -> None:
    result = load_spectrum_columns(_csv(tmp_path, {"t": [0.91, 0.92, 1.01, 0.90], "r": [0.008, 0.005, 0.003, 0.006]}))
    assert result.normalised_to_fraction is False
    np.testing.assert_allclose(result.y_columns["T"], [0.91, 0.92, 1.01, 0.90])
