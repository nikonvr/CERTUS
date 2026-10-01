from __future__ import annotations

import importlib
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

import certus_physics.materials_data as md


@pytest.mark.parametrize(
    ("file_to_simulate", "expected_in_log"),
    [
        ("material_constants.xlsx", "material_constants.xlsx"),
        ("clues.xlsx", "clues.xlsx"),
    ]
)
def test_materials_data_graceful_fallback_on_corrupt_xlsx(caplog, file_to_simulate, expected_in_log) -> None:
    """Verify that if the Excel file exists but is corrupt/fails to load, we fall back to stub arrays.
    
    This tests both the modern 'material_constants.xlsx' and the legacy 'clues.xlsx'.
    """
    original_is_file = Path.is_file

    def mock_is_file(self):
        if self.name == file_to_simulate:
            return True
        # Ensure the other spreadsheet is simulated as absent to avoid interference
        if self.name in ("clues.xlsx", "material_constants.xlsx"):
            return False
        return original_is_file(self)

    with patch.object(Path, "is_file", mock_is_file):
        # Force pandas.read_excel to raise ValueError
        with patch("pandas.read_excel", side_effect=ValueError("Mock Excel Corruption")):
            caplog.clear()
            with caplog.at_level(logging.WARNING):
                importlib.reload(md)
                
                # Check that warning was logged with correct path details
                warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
                assert len(warnings) > 0
                assert "Mock Excel Corruption" in warnings[0]
                assert expected_in_log in warnings[0]
                assert "falling back to built-in silicon constants" in warnings[0].lower()
                
                # Verify that the variables are filled with the stub arrays
                stub_wl, stub_n, stub_k = md._silicon_stub_arrays()
                assert len(md.SI_WAVELENGTH_NM) == len(stub_wl)
                assert md.SI_WAVELENGTH_NM[0] == stub_wl[0]
                assert md.SI_N_DATA[0] == stub_n[0]
                assert md.SI_K_DATA[0] == stub_k[0]

    # Clean up and restore module to normal state
    importlib.reload(md)


def test_find_materials_xlsx_path_priority() -> None:
    """Verify that material_constants.xlsx takes priority over clues.xlsx."""
    original_is_file = Path.is_file

    # Case 1: Both exist -> should choose material_constants.xlsx
    def mock_both_exist(self):
        if self.name in ("clues.xlsx", "material_constants.xlsx"):
            return True
        return original_is_file(self)

    with patch.object(Path, "is_file", mock_both_exist):
        path = md._find_materials_xlsx_path()
        assert path is not None
        assert "material_constants.xlsx" in path

    # Case 2: Only clues.xlsx exists -> should choose clues.xlsx
    def mock_only_legacy_exist(self):
        if self.name == "clues.xlsx":
            return True
        if self.name == "material_constants.xlsx":
            return False
        return original_is_file(self)

    with patch.object(Path, "is_file", mock_only_legacy_exist):
        path = md._find_materials_xlsx_path()
        assert path is not None
        assert "clues.xlsx" in path

    # Case 3: None exist -> should return None
    def mock_none_exist(self):
        if self.name in ("clues.xlsx", "material_constants.xlsx"):
            return False
        return original_is_file(self)

    with patch.object(Path, "is_file", mock_none_exist):
        path = md._find_materials_xlsx_path()
        assert path is None


def test_load_si_from_xlsx_exceptions() -> None:
    """Verify that _load_si_from_xlsx raises specific Certus exceptions on failures."""
    import pandas as pd

    from certus.utils.errors import CertusFileError, CertusMaterialError

    # Case 1: File does not exist
    with pytest.raises(CertusFileError, match="Silicon spreadsheet not found"):
        md._load_si_from_xlsx("non_existent_file.xlsx")

    # Case 2: Reading sheet fails (mock pandas raises ValueError)
    with patch("pandas.read_excel", side_effect=ValueError("Excel read failure")):
        with patch("pathlib.Path.is_file", return_value=True):
            with pytest.raises(CertusFileError, match="Cannot read sheet"):
                md._load_si_from_xlsx("dummy.xlsx")

    # Case 3: Fewer than 2 data points
    bad_df_few = pd.DataFrame({"wl": [500.0], "n": [3.5], "k": [0.0]})
    with patch("pandas.read_excel", return_value=bad_df_few):
        with patch("pathlib.Path.is_file", return_value=True):
            with pytest.raises(CertusMaterialError, match="fewer than 2 data points"):
                md._load_si_from_xlsx("dummy.xlsx")

    # Case 4: Non-increasing wavelengths
    bad_df_non_inc = pd.DataFrame({"wl": [500.0, 500.0], "n": [3.5, 3.6], "k": [0.0, 0.0]})
    with patch("pandas.read_excel", return_value=bad_df_non_inc):
        with patch("pathlib.Path.is_file", return_value=True):
            with pytest.raises(CertusMaterialError, match="not strictly increasing"):
                md._load_si_from_xlsx("dummy.xlsx")


# ---------------------------------------------------------------------------
# The Si data must come from the VERSIONED sheet, not from the 15-point stub.
#
# material_constants.xlsx and clues.xlsx were the only sources searched, and neither
# has ever been committed: every clone silently used the stub. Measured 2026-09-25
# against the 'Si-substrate' sheet of example/database_index/indices.xlsx: air/Si
# reflectance off by -11 points at 400 nm and +0.9 point near 900 nm -- for INDEX,
# RE and METAL BILAYER on a silicon substrate.
# ---------------------------------------------------------------------------

_VERSIONED_DB = Path(__file__).resolve().parents[2] / "example" / "database_index" / "indices.xlsx"


def _versioned_sheet():
    import pandas as pd

    df = pd.read_excel(_VERSIONED_DB, sheet_name="Si-substrate", header=0, engine="openpyxl")
    df.columns = df.columns.astype(str).str.strip().str.lower()
    df = df.sort_values(by="wl_nm").dropna(subset=["wl_nm", "n"])
    return df["wl_nm"].to_numpy(float), df["n"].to_numpy(float), df["k"].to_numpy(float)


def test_si_data_is_the_versioned_sheet_without_a_local_override() -> None:
    import numpy as np

    importlib.reload(md)
    if md._find_materials_xlsx_path():
        pytest.skip("a local material_constants.xlsx / clues.xlsx override is present")
    wl, n, k = _versioned_sheet()
    assert md.SI_SOURCE.replace("\\", "/").endswith("example/database_index/indices.xlsx")
    assert len(md.SI_WAVELENGTH_NM) == len(wl) == 566
    np.testing.assert_array_equal(md.SI_WAVELENGTH_NM, wl)
    np.testing.assert_array_equal(md.SI_N_DATA, n)
    np.testing.assert_array_equal(md.SI_K_DATA, k)


def test_get_nk_si_returns_the_sheet_with_the_macleod_sign() -> None:
    import numpy as np

    importlib.reload(md)
    if md._find_materials_xlsx_path():
        pytest.skip("a local material_constants.xlsx / clues.xlsx override is present")
    wl, n, k = _versioned_sheet()
    probe = np.array([400.0, 900.0, 1500.0])
    expected = np.interp(probe, wl, n) - 1j * np.interp(probe, wl, k)
    got = md.get_nk_si(probe)
    np.testing.assert_allclose(got, expected, rtol=0, atol=1e-12)
    assert np.all(got.imag <= 0.0), "n - ik: an absorbing substrate has a NEGATIVE imaginary part"


def test_stub_fallback_is_a_warning_not_an_info(monkeypatch, caplog) -> None:
    monkeypatch.setattr(md, "_si_candidate_paths", lambda: [])
    with caplog.at_level(logging.INFO):
        wl, _n, _k, source = md._load_si_data()
    stub_wl, _, _ = md._silicon_stub_arrays()
    assert source == "built-in stub"
    assert len(wl) == len(stub_wl)
    assert any(r.levelno == logging.WARNING and "falling back" in r.getMessage().lower() for r in caplog.records)
