"""Tests unitaires : certus_data — I/O, timing, shared memory, reporting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from certus_data import (
    ReportSection,
    build_standard_report,
    load_spectrum_columns,
    get_missing_manifest_fields,
    WL_TOLERANCE,
    CSV_SAMPLE_SIZE,
    MANIFEST_REQUIRED_FIELDS,
    EXCEL_SHEET_NAME_MAX_LENGTH,
    numpy_encoder,
    read_csv_robust,
    read_data_file_robust,
    to_csv_robust,
    TimingLogger,
    PerformanceMonitor,
    PERF_MONITOR,
    SharedIndicesManager,
    SharedIndicesWorker,
    SharedArrayManager,
    SharedArrayWorker,
    SpectrumLoadResult,
)

from certus_index_spline_core import normalize_spectrum_dataframe


# ── ReportSection ──


class TestReportSection:
    def test_creates_with_required_args(self) -> None:
        s = ReportSection(title="Test", content="Hello", kind="text")
        assert s.title == "Test"
        assert s.content == "Hello"


# ── numpy_encoder ──


class TestNumpyEncoder:
    def test_encodes_int64(self) -> None:
        result = numpy_encoder(np.int64(42))
        assert isinstance(result, int)
        assert result == 42

    def test_encodes_float64(self) -> None:
        result = numpy_encoder(np.float64(3.14))
        assert isinstance(result, float)

    def test_encodes_array(self) -> None:
        result = numpy_encoder(np.array([1.0, 2.0]))
        assert isinstance(result, list)
        assert len(result) == 2

    def test_encodes_string_fallback(self) -> None:
        result = numpy_encoder({"key": "val"})
        assert isinstance(result, str)


# ── read_csv_robust ──


class TestReadCsvRobust:
    def test_read_comma_separated(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("a,b\n1.0,2.0\n3.0,4.0\n", encoding="utf-8")
        df = read_csv_robust(str(f))
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (2, 2)

    def test_read_semicolon_separated(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("a;b\n1,0;2,0\n3,0;4,0\n", encoding="utf-8")
        df = read_csv_robust(str(f))
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (2, 2)

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_csv_robust("/nonexistent/path.csv")

    def test_invalid_path_raises(self) -> None:
        with pytest.raises(ValueError):
            read_csv_robust("")


# ── read_data_file_robust ──


class TestReadDataFileRobust:
    def test_dispatches_csv(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        df = read_data_file_robust(str(f))
        assert isinstance(df, pd.DataFrame)

    def test_invalid_path_raises(self) -> None:
        with pytest.raises(ValueError):
            read_data_file_robust("")


# ── to_csv_robust ──


class TestToCsvRobust:
    def test_writes_csv(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        f = tmp_path / "output.csv"
        to_csv_robust(df, str(f), index=False)
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "1.0" in content

    def test_european_format(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"a": [1.5], "b": [2.5]})
        f = tmp_path / "euro.csv"
        to_csv_robust(df, str(f), decimal_separator=",", index=False)
        content = f.read_text(encoding="utf-8")
        assert ";" in content  # semicolon separator for EU format

    def test_empty_df_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            to_csv_robust(pd.DataFrame(), str(tmp_path / "empty.csv"))


# ── TimingLogger ──


class TestTimingLogger:
    def test_start_and_end(self) -> None:
        t = TimingLogger()
        t.start("test")
        t.end("test")
        assert "test" not in t.start_times

    def test_end_without_start_noop(self) -> None:
        t = TimingLogger()
        t.end("nonexistent")  # should not raise

    def test_global_timing(self) -> None:
        t = TimingLogger()
        t.start_global("global_test")
        t.end_global("global_test")
        assert "global_test" not in t.start_times


# ── PerformanceMonitor ──


class TestPerformanceMonitor:
    def test_measure_context(self) -> None:
        mon = PerformanceMonitor()
        with mon.measure("test_op"):
            _ = sum(range(100))
        assert "test_op" in mon.metrics
        assert len(mon.metrics["test_op"]) == 1

    def test_report_empty(self) -> None:
        mon = PerformanceMonitor()
        assert "No data" in mon.report()

    def test_report_with_data(self) -> None:
        mon = PerformanceMonitor()
        with mon.measure("calc"):
            pass
        report = mon.report()
        assert "calc" in report
        assert "ms" in report


# ── SharedIndicesManager / Worker ──


class TestSharedIndicesRoundtrip:
    def test_manager_worker_roundtrip(self) -> None:
        clues = {
            400.0: {"H": 2.3, "L": 1.45, "substrate": 1.52},
            500.0: {"H": 2.28, "L": 1.44, "substrate": 1.51},
        }
        with SharedIndicesManager(clues) as mgr:
            ctx = mgr.get_context_info()
            assert "shm_name" in ctx
            with SharedIndicesWorker(ctx) as worker:
                result = worker.get(400.0)
                assert abs(result["H"] - 2.3) < 0.01
                assert abs(result["L"] - 1.45) < 0.01


# ── SharedArrayManager / Worker ──


class TestSharedArrayRoundtrip:
    def test_manager_worker_roundtrip(self) -> None:
        arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
        with SharedArrayManager(arr) as mgr:
            ctx = mgr.get_context_info()
            with SharedArrayWorker(ctx) as worker:
                retrieved = worker.get_array()
                np.testing.assert_allclose(retrieved, arr)


# ── ManifestFields ──


class TestManifestFields:
    def test_required_fields_is_list(self) -> None:
        assert isinstance(MANIFEST_REQUIRED_FIELDS, (list, tuple))
        assert len(MANIFEST_REQUIRED_FIELDS) > 0

    def test_get_missing_fields_full_manifest(self) -> None:
        full = {k: "value" for k in MANIFEST_REQUIRED_FIELDS}
        missing = get_missing_manifest_fields(full)
        assert len(missing) == 0

    def test_get_missing_fields_empty_manifest(self) -> None:
        missing = get_missing_manifest_fields({})
        assert len(missing) == len(MANIFEST_REQUIRED_FIELDS)


# ── Constants ──


class TestConstants:
    def test_wl_tolerance_positive(self) -> None:
        assert WL_TOLERANCE > 0

    def test_csv_sample_size_positive(self) -> None:
        assert CSV_SAMPLE_SIZE > 0

    def test_excel_sheet_name_limit(self) -> None:
        assert EXCEL_SHEET_NAME_MAX_LENGTH == 31


# ── LoadSpectrumColumns ──


class TestLoadSpectrumColumns:
    def test_load_csv_file(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "test_spectrum.csv"
        csv_path.write_text(
            "wavelength,T,R\n400,0.5,0.3\n500,0.6,0.2\n600,0.7,0.1\n",
            encoding="utf-8",
        )
        result = load_spectrum_columns(str(csv_path))
        assert result is not None
        assert result.n_rows == 3
        assert list(result.dataframe.columns) == ["lambda", "T", "R"]
        np.testing.assert_allclose(result.x, np.array([400.0, 500.0, 600.0]))

    def test_load_xlsx_and_percent_normalization(self, tmp_path: Path) -> None:
        pytest.importorskip("openpyxl")
        xlsx_path = tmp_path / "test_spectrum.xlsx"
        df = pd.DataFrame(
            {
                "Wavelength nm": [400.0, 500.0, 600.0],
                "Trel-NB250 600": [28.9104, 31.0610, 32.1450],
            }
        )
        df.to_excel(xlsx_path, index=False)

        result = load_spectrum_columns(str(xlsx_path))
        assert result.x_unit == "nm"
        assert result.normalised_to_fraction is True
        assert list(result.dataframe.columns) == ["lambda", "T"]
        np.testing.assert_allclose(result.dataframe["T"].to_numpy(), np.array([0.289104, 0.31061, 0.32145]))

    def test_load_um_conversion(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "test_um.csv"
        csv_path.write_text("lambda,T\n0.4,50\n0.5,60\n", encoding="utf-8")
        result = load_spectrum_columns(str(csv_path), x_unit="um", to_nm=True)
        np.testing.assert_allclose(result.x, np.array([400.0, 500.0]))
        assert result.x_unit == "nm"

    def test_load_raises_for_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_spectrum_columns("/definitely/missing.xlsx")

    def test_normalize_spectrum_dataframe_fallbacks(self) -> None:
        df = pd.DataFrame({"Wavelength nm": [400.0, 500.0], "Trel": [0.5, 0.6]})
        out = normalize_spectrum_dataframe(df)
        assert "lambda" in out.columns
        assert out.columns[0] == "lambda"

    def test_normalize_spectrum_dataframe_renames_reflection(self) -> None:
        df = pd.DataFrame({"lambda": [400.0, 500.0], "Reflection": [0.1, 0.2]})
        out = normalize_spectrum_dataframe(df)
        assert "lambda" in out.columns
        assert "T" in out.columns
        np.testing.assert_allclose(out["T"].to_numpy(), np.array([0.1, 0.2]))


# ── PERF_MONITOR singleton ──


class TestPerfMonitorSingleton:
    def test_global_instance(self) -> None:
        assert isinstance(PERF_MONITOR, PerformanceMonitor)


# ── ReportSection helpers ──


class TestReportSectionHelpers:
    def test_to_html_dict(self) -> None:
        s = ReportSection(title="Test", kind="text", content="Hello")
        d = s.to_html_dict()
        assert d["title"] == "Test"
        assert d["type"] == "text"
        assert d["content"] == "Hello"

    def test_excel_sheet_name_truncates(self) -> None:
        s = ReportSection(title="A" * 50, kind="text", content="x")
        name = s.excel_sheet_name()
        assert len(name) <= EXCEL_SHEET_NAME_MAX_LENGTH

    def test_excel_sheet_name_cleans_illegal_chars(self) -> None:
        s = ReportSection(title="Test/Sheet:1[2]", kind="text", content="x")
        name = s.excel_sheet_name()
        assert "/" not in name
        assert ":" not in name
        assert "[" not in name
        assert "]" not in name

    def test_excel_sheet_name_override(self) -> None:
        s = ReportSection(title="Title", kind="text", content="x", sheet_name="Custom")
        assert s.excel_sheet_name() == "Custom"


# ── build_standard_report ──


class TestBuildStandardReport:
    def test_excel_output(self, tmp_path: Path) -> None:
        sections = [
            ReportSection(title="Summary", kind="kv", content={"key": "value"}),
            ReportSection(
                title="Data",
                kind="table",
                content=pd.DataFrame({"x": [1, 2], "y": [3, 4]}),
            ),
            ReportSection(title="Note", kind="text", content="Some text"),
        ]
        xlsx = str(tmp_path / "report.xlsx")
        result = build_standard_report(sections, excel_path=xlsx)
        assert result.get("excel") is True
        assert Path(xlsx).exists()

    def test_no_output_requested(self) -> None:
        sections = [ReportSection(title="T", kind="text", content="x")]
        result = build_standard_report(sections)
        assert "excel" not in result
        assert "html" not in result

    def test_manifest_dict(self, tmp_path: Path) -> None:
        sections = [
            ReportSection(title="Data", kind="kv", content={"a": 1}),
        ]
        xlsx = str(tmp_path / "report_m.xlsx")
        manifest = {"run_id": "r1", "app_id": "test"}
        result = build_standard_report(sections, excel_path=xlsx, run_manifest=manifest)
        assert result.get("excel") is True

    def test_require_complete_manifest_fails(self, tmp_path: Path) -> None:
        sections = [ReportSection(title="T", kind="text", content="x")]
        xlsx = str(tmp_path / "report_f.xlsx")
        result = build_standard_report(
            sections,
            excel_path=xlsx,
            run_manifest={"incomplete": True},
            require_complete_manifest=True,
        )
        assert result.get("excel") is False

