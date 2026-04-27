"""Unit tests for ``load_spectrum_columns`` and ``SpectrumLoadResult``
(P8 scaffold in ``certus_data``).

The helper runs without Qt and is fully testable from generated CSV/Excel
fixtures written to ``tmp_path``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from certus_data import (
    SpectrumLoadResult,
    load_spectrum_columns,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_csv(tmp_path, name: str, df: pd.DataFrame, **kwargs) -> str:
    path = tmp_path / name
    df.to_csv(path, index=False, **kwargs)
    return str(path)


def _write_xlsx(tmp_path, name: str, df: pd.DataFrame) -> str:
    path = tmp_path / name
    df.to_excel(path, index=False)
    return str(path)


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------


class TestLoadSpectrumColumnsCSV:
    def test_returns_spectrum_load_result(self, tmp_path):
        df = pd.DataFrame({"lambda_nm": [400.0, 500.0, 600.0], "T": [0.5, 0.6, 0.7]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert isinstance(result, SpectrumLoadResult)
        assert result.n_rows == 3
        assert result.source_path.endswith("spec.csv")

    def test_renames_columns_to_standard_roles(self, tmp_path):
        df = pd.DataFrame({"WL": [400, 500, 600], "T": [0.5, 0.6, 0.7], "R": [0.1, 0.2, 0.3]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert list(result.dataframe.columns) == ["lambda", "T", "R"]
        assert set(result.y_columns) == {"T", "R"}

    def test_keep_source_names_when_column_roles_empty(self, tmp_path):
        df = pd.DataFrame({"WL": [400, 500, 600], "T%": [50, 60, 70]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, column_roles={})
        assert list(result.dataframe.columns) == ["WL", "T%"]

    def test_limits_columns_to_max_columns(self, tmp_path):
        df = pd.DataFrame({
            "x": [1.0, 2.0, 3.0], "a": [0.1, 0.2, 0.3],
            "b": [0.4, 0.5, 0.6], "c": [0.7, 0.8, 0.9],
        })
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, max_columns=2)
        assert result.dataframe.shape[1] == 2

    def test_drops_non_numeric_rows(self, tmp_path):
        path = tmp_path / "spec.csv"
        path.write_text("x,y\n400,0.5\n500,0.6\nbad,bad\n600,0.7\n", encoding="utf-8")
        result = load_spectrum_columns(str(path))
        assert result.n_rows == 3
        assert list(result.x) == [400.0, 500.0, 600.0]

    def test_sorts_ascending_by_default(self, tmp_path):
        df = pd.DataFrame({"x": [600, 400, 500], "y": [0.3, 0.1, 0.2]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        np.testing.assert_array_equal(result.x, [400.0, 500.0, 600.0])
        np.testing.assert_array_equal(result.y_columns["T"], [0.1, 0.2, 0.3])

    def test_no_sort_when_disabled(self, tmp_path):
        df = pd.DataFrame({"x": [600, 400, 500], "y": [0.3, 0.1, 0.2]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, sort_ascending=False)
        np.testing.assert_array_equal(result.x, [600.0, 400.0, 500.0])


# ---------------------------------------------------------------------------
# Unit detection + conversion
# ---------------------------------------------------------------------------


class TestUnitDetection:
    def test_detects_nm_by_default(self, tmp_path):
        df = pd.DataFrame({"x": [400.0, 500.0, 600.0], "y": [0.1, 0.2, 0.3]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert result.x_unit == "nm"

    def test_detects_um_and_converts_to_nm(self, tmp_path):
        df = pd.DataFrame({"x": [0.4, 0.5, 0.6], "y": [0.1, 0.2, 0.3]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert result.x_unit == "nm"
        np.testing.assert_array_almost_equal(result.x, [400.0, 500.0, 600.0])

    def test_um_unit_preserved_when_to_nm_false(self, tmp_path):
        df = pd.DataFrame({"x": [0.4, 0.5, 0.6], "y": [0.1, 0.2, 0.3]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, to_nm=False)
        assert result.x_unit == "um"
        np.testing.assert_array_almost_equal(result.x, [0.4, 0.5, 0.6])

    def test_forced_x_unit_overrides_detection(self, tmp_path):
        # 400 nm would be auto-detected as nm, but force 'um' -> no conversion, stays 400
        df = pd.DataFrame({"x": [400.0, 500.0], "y": [0.1, 0.2]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, x_unit="um", to_nm=True)
        # forced unit is 'um' → to_nm applies → x*1000
        assert result.x_unit == "nm"
        np.testing.assert_array_almost_equal(result.x, [400000.0, 500000.0])


# ---------------------------------------------------------------------------
# Percent → fraction heuristic
# ---------------------------------------------------------------------------


class TestPercentNormalisation:
    def test_converts_percent_columns_to_fractions(self, tmp_path):
        df = pd.DataFrame({"x": [400, 500, 600], "y": [50.0, 60.0, 70.0]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert result.normalised_to_fraction is True
        np.testing.assert_array_almost_equal(result.y_columns["T"], [0.5, 0.6, 0.7])

    def test_keeps_fraction_columns_untouched(self, tmp_path):
        df = pd.DataFrame({"x": [400, 500, 600], "y": [0.5, 0.6, 0.7]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path)
        assert result.normalised_to_fraction is False
        np.testing.assert_array_almost_equal(result.y_columns["T"], [0.5, 0.6, 0.7])

    def test_disabled_when_normalise_percent_false(self, tmp_path):
        df = pd.DataFrame({"x": [400, 500, 600], "y": [50.0, 60.0, 70.0]})
        path = _write_csv(tmp_path, "spec.csv", df)
        result = load_spectrum_columns(path, normalise_percent=False)
        assert result.normalised_to_fraction is False
        np.testing.assert_array_almost_equal(result.y_columns["T"], [50.0, 60.0, 70.0])


# ---------------------------------------------------------------------------
# Excel + error paths
# ---------------------------------------------------------------------------


class TestExcelAndErrors:
    def test_reads_xlsx_file(self, tmp_path):
        df = pd.DataFrame({"WL": [400, 500, 600], "T": [0.5, 0.6, 0.7]})
        path = _write_xlsx(tmp_path, "spec.xlsx", df)
        result = load_spectrum_columns(path)
        assert result.n_rows == 3

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_spectrum_columns("C:/this/does/not/exist.csv")

    def test_raises_on_all_nan_file(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("x,y\nfoo,bar\nbaz,qux\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_spectrum_columns(str(path))


# ---------------------------------------------------------------------------
# __all__ exposure
# ---------------------------------------------------------------------------


def test_helpers_are_in_certus_data_all():
    import certus_data
    assert "SpectrumLoadResult" in certus_data.__all__
    assert "load_spectrum_columns" in certus_data.__all__


def test_result_is_frozen():
    result = SpectrumLoadResult(
        dataframe=pd.DataFrame(), x=np.array([]), y_columns={},
        x_unit="nm", normalised_to_fraction=False, n_rows=0, source_path="",
    )
    with pytest.raises((AttributeError, Exception)):
        result.n_rows = 10  # type: ignore[misc]
