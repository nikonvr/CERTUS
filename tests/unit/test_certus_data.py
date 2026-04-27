"""
Unit tests for certus_data.py
Covers read_data_file_robust, read_csv_robust, constants.
"""

import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus_data import (
    read_csv_robust,
    read_data_file_robust,
    generate_html_report,
    OPENPYXL_AVAILABLE,
)


class TestReadDataFileRobust:
    """Tests for read_data_file_robust dispatch and validation."""

    def test_invalid_filepath_none_raises(self):
        with pytest.raises(ValueError, match="Invalid filepath"):
            read_data_file_robust(None)

    def test_invalid_filepath_empty_raises(self):
        with pytest.raises(ValueError, match="Invalid filepath"):
            read_data_file_robust("")

    def test_invalid_filepath_not_string_raises(self):
        with pytest.raises(ValueError, match="Invalid filepath"):
            read_data_file_robust(123)

    def test_dispatches_to_csv_for_csv_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"wl,R,T\n400,0.1,0.9\n500,0.2,0.8\n")
            f.flush()
            path = f.name
        try:
            df = read_data_file_robust(path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) >= 1
            assert "wl" in df.columns or df.shape[1] >= 2
        finally:
            os.unlink(path)

    def test_dispatches_to_csv_for_txt_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"lambda,value\n400,0.5\n500,0.6\n")
            f.flush()
            path = f.name
        try:
            df = read_data_file_robust(path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) >= 1
        finally:
            os.unlink(path)

    @pytest.mark.skipif(not OPENPYXL_AVAILABLE, reason="openpyxl not available")
    def test_dispatches_to_excel_for_xlsx_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            pd.DataFrame({"A": [1, 2], "B": [3, 4]}).to_excel(path, index=False)
            df = read_data_file_robust(path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
        finally:
            p = Path(path)
            if p.exists():
                p.unlink()


class TestGenerateHtmlReport:
    """Tests for generate_html_report sections and table content types."""

    def test_report_with_table_dataframe(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
            ok = generate_html_report(
                path, "Report", [{"title": "Table", "type": "table", "content": df}]
            )
            assert ok is True
            html = Path(path).read_text(encoding="utf-8")
            assert "Report" in html
            assert "<table" in html
            assert "1" in html and "2" in html
        finally:
            p = Path(path)
            if p.exists():
                p.unlink()

    def test_report_with_table_list_of_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            rows = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
            ok = generate_html_report(
                path, "Report", [{"title": "Data", "type": "table", "content": rows}]
            )
            assert ok is True
            html = Path(path).read_text(encoding="utf-8")
            assert "<table" in html
            assert "1" in html and "3" in html
        finally:
            p = Path(path)
            if p.exists():
                p.unlink()

    def test_report_with_table_single_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            row = {"param": "value", "n": 42}
            ok = generate_html_report(
                path, "Report", [{"title": "KV", "type": "table", "content": row}]
            )
            assert ok is True
            html = Path(path).read_text(encoding="utf-8")
            assert "<table" in html
            assert "value" in html and "42" in html
        finally:
            p = Path(path)
            if p.exists():
                p.unlink()


class TestReadCsvRobust:
    """Basic tests for read_csv_robust."""

    def test_read_simple_csv(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"x,y\n1,2\n3,4\n")
            f.flush()
            path = f.name
        try:
            df = read_csv_robust(path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["x", "y"]
        finally:
            os.unlink(path)
