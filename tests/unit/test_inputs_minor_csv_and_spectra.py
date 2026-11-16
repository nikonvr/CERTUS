"""Three input minors of the audit of 2026-11-15 (L4-m1, L4-m2, L4-m3).

L4-m1: a French CSV of two columns, "400,5;0,91", was read with ',' as separator, and without a header its first line
       of data became the column names.
L4-m2: a spectrum whose T is longer than its R was cut to the range of R without a word.
L4-m3: an index sheet in micrometres was read as nanometres, so every query hit the last row: a constant index.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from certus.utils.certus_data import load_spectrum_columns, read_csv_robust


def test_l4_m1_a_french_csv_of_two_columns_is_read_with_its_separator(tmp_path) -> None:
    path = tmp_path / "mesure.csv"
    path.write_text("400,5;0,91\n401,0;0,92\n401,5;0,93\n", encoding="utf-8")
    df = read_csv_robust(str(path))
    assert df.shape == (3, 2)
    np.testing.assert_allclose(df.iloc[:, 0].to_numpy(dtype=float), [400.5, 401.0, 401.5])
    np.testing.assert_allclose(df.iloc[:, 1].to_numpy(dtype=float), [0.91, 0.92, 0.93])


def test_l4_m1_a_csv_with_a_header_keeps_it(tmp_path) -> None:
    path = tmp_path / "mesure.csv"
    path.write_text("lambda;T\n400,5;0,91\n401,0;0,92\n", encoding="utf-8")
    df = read_csv_robust(str(path))
    assert list(df.columns) == ["lambda", "T"]
    assert len(df) == 2


def test_l4_m2_a_cut_column_is_reported(tmp_path, caplog) -> None:
    path = tmp_path / "spectre.csv"
    pd.DataFrame({"x": [400.0, 500.0, 600.0, 700.0], "t": [0.9, 0.91, 0.92, 0.93], "r": [0.05, 0.06, None, None]}).to_csv(
        path, index=False
    )
    certus_logger = logging.getLogger("CERTUS")
    certus_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="CERTUS"):
            result = load_spectrum_columns(str(path))
    finally:
        certus_logger.removeHandler(caplog.handler)
    assert result.n_rows == 2
    assert any("2 of 4 rows dropped" in r.getMessage() for r in caplog.records)


@pytest.fixture
def db_class():
    from certus.utils.certus_strat_db import RobustMaterialDatabase

    return RobustMaterialDatabase


def test_l4_m3_a_sheet_in_micrometres_is_converted(db_class) -> None:
    db = db_class.__new__(db_class)
    db.logger = logging.getLogger("t")
    sheet = pd.DataFrame({"Wavelength (um)": [0.4, 0.5, 0.6], "n": [1.47, 1.46, 1.455], "k": [0.0, 0.0, 0.0]})
    out = db._standardize_dataframe(sheet, "SiO2-um")
    np.testing.assert_allclose(out["wl"].to_numpy(), [400.0, 500.0, 600.0])


def test_l4_m3_a_sheet_in_nanometres_is_unchanged(db_class) -> None:
    db = db_class.__new__(db_class)
    db.logger = logging.getLogger("t")
    sheet = pd.DataFrame({"Wavelength (nm)": [400.0, 500.0], "n": [1.47, 1.46], "k": [0.0, 0.0]})
    np.testing.assert_allclose(db._standardize_dataframe(sheet, "SiO2")["wl"].to_numpy(), [400.0, 500.0])
