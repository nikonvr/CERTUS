"""Unit tests for the P6 scaffold: ``ReportSection`` + ``build_standard_report``.

These tests exercise the Excel path only; HTML generation requires PyQt6 and
is covered indirectly by the existing ``generate_html_report`` path. The
builder is opt-in, so these tests only verify the scaffolding API.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from certus_data import (
    EXCEL_SHEET_NAME_MAX_LENGTH,
    ReportSection,
    build_standard_report,
    get_missing_manifest_fields,
)
from certus_metrology import RunContext, RunManifest


# ---------------------------------------------------------------------------
# ReportSection
# ---------------------------------------------------------------------------


class TestReportSection:
    def test_is_frozen(self):
        sec = ReportSection(title="x", kind="text", content="hello")
        with pytest.raises((AttributeError, Exception)):
            sec.title = "y"  # type: ignore[misc]

    def test_to_html_dict_matches_legacy_schema(self):
        sec = ReportSection(title="Results", kind="table", content=[{"a": 1}])
        d = sec.to_html_dict()
        assert d == {"title": "Results", "type": "table", "content": [{"a": 1}]}

    def test_excel_sheet_name_uses_title_by_default(self):
        sec = ReportSection(title="Clean", kind="table", content=pd.DataFrame())
        assert sec.excel_sheet_name() == "Clean"

    def test_excel_sheet_name_truncates_long_title(self):
        long_title = "x" * 80
        sec = ReportSection(title=long_title, kind="table", content=pd.DataFrame())
        out = sec.excel_sheet_name()
        assert len(out) == EXCEL_SHEET_NAME_MAX_LENGTH
        assert out == "x" * EXCEL_SHEET_NAME_MAX_LENGTH

    def test_excel_sheet_name_strips_illegal_chars(self):
        sec = ReportSection(title="a/b\\c?d*e[f]g:h", kind="table", content=pd.DataFrame())
        out = sec.excel_sheet_name()
        for ch in "\\/?*[]:":
            assert ch not in out

    def test_excel_sheet_name_empty_fallback(self):
        sec = ReportSection(title="", kind="text", content="")
        assert sec.excel_sheet_name() == "Sheet"

    def test_override_sheet_name(self):
        sec = ReportSection(
            title="Very Long Human Readable Title",
            kind="table",
            content=pd.DataFrame(),
            sheet_name="SHORT",
        )
        assert sec.excel_sheet_name() == "SHORT"

    def test_include_flags_default_true(self):
        sec = ReportSection(title="x", kind="text", content="")
        assert sec.include_in_html is True
        assert sec.include_in_excel is True


# ---------------------------------------------------------------------------
# build_standard_report
# ---------------------------------------------------------------------------


class TestBuildStandardReport:
    def test_no_outputs_requested_returns_empty_dict(self):
        result = build_standard_report([ReportSection("x", "text", "hello")])
        assert result == {}

    def test_excel_table_writes_sheet(self, tmp_path):
        df = pd.DataFrame({"wavelength_nm": [400, 500, 600], "R": [0.1, 0.2, 0.3]})
        sections = [ReportSection(title="Spectrum", kind="table", content=df)]
        excel = tmp_path / "report.xlsx"
        result = build_standard_report(sections, excel_path=str(excel))
        assert result["excel"] is True
        assert excel.exists()
        loaded = pd.read_excel(excel, sheet_name="Spectrum")
        assert list(loaded.columns) == ["wavelength_nm", "R"]
        assert len(loaded) == 3

    def test_excel_kv_writes_sheet_with_key_value_columns(self, tmp_path):
        sections = [
            ReportSection(title="Metrics", kind="kv", content={"RMSE": 0.012, "iters": 100})
        ]
        excel = tmp_path / "report.xlsx"
        result = build_standard_report(sections, excel_path=str(excel))
        assert result["excel"] is True
        loaded = pd.read_excel(excel, sheet_name="Metrics")
        assert list(loaded.columns) == ["Key", "Value"]
        assert set(loaded["Key"]) == {"RMSE", "iters"}

    def test_excel_text_goes_to_summary_sheet(self, tmp_path):
        sections = [
            ReportSection(title="Intro", kind="text", content="Report generated OK."),
            ReportSection(title="Data", kind="table", content=pd.DataFrame({"x": [1]})),
        ]
        excel = tmp_path / "report.xlsx"
        build_standard_report(sections, excel_path=str(excel))
        xls = pd.ExcelFile(excel)
        assert "Summary" in xls.sheet_names
        assert "Data" in xls.sheet_names
        summary = pd.read_excel(excel, sheet_name="Summary")
        assert "Intro" in summary["Section"].tolist()

    def test_excel_skips_image_sections(self, tmp_path):
        sections = [
            ReportSection(title="Chart", kind="image", content="base64-stuff"),
            ReportSection(title="Data", kind="table", content=pd.DataFrame({"x": [1]})),
        ]
        excel = tmp_path / "report.xlsx"
        build_standard_report(sections, excel_path=str(excel))
        xls = pd.ExcelFile(excel)
        assert "Chart" not in xls.sheet_names
        assert "Data" in xls.sheet_names

    def test_excel_deduplicates_sheet_names(self, tmp_path):
        sections = [
            ReportSection(title="Same", kind="table", content=pd.DataFrame({"a": [1]})),
            ReportSection(title="Same", kind="table", content=pd.DataFrame({"b": [2]})),
        ]
        excel = tmp_path / "report.xlsx"
        build_standard_report(sections, excel_path=str(excel))
        xls = pd.ExcelFile(excel)
        # Two sheets must exist with distinct names
        assert "Same" in xls.sheet_names
        assert any(n != "Same" and n.startswith("Same") for n in xls.sheet_names)

    def test_include_in_excel_false_skipped(self, tmp_path):
        sections = [
            ReportSection(
                title="HiddenInExcel", kind="table",
                content=pd.DataFrame({"x": [1]}), include_in_excel=False,
            ),
            ReportSection(title="Visible", kind="table", content=pd.DataFrame({"y": [1]})),
        ]
        excel = tmp_path / "report.xlsx"
        build_standard_report(sections, excel_path=str(excel))
        xls = pd.ExcelFile(excel)
        assert "HiddenInExcel" not in xls.sheet_names
        assert "Visible" in xls.sheet_names

    def test_excel_graceful_on_bad_path(self):
        sections = [ReportSection(title="x", kind="table", content=pd.DataFrame({"a": [1]}))]
        # Non-existent directory
        bad_path = Path("Z:/") / ("nonexistent_dir_" + os.urandom(4).hex()) / "r.xlsx"
        result = build_standard_report(sections, excel_path=str(bad_path))
        assert result["excel"] is False

    def test_excel_adds_manifest_sheet_when_manifest_provided(self, tmp_path):
        ctx = RunContext.create(app_id="CERTUS_TEST", app_version="26_01", seed=42)
        manifest = RunManifest(run_context=ctx)
        sections = [ReportSection(title="Data", kind="table", content=pd.DataFrame({"x": [1]}))]
        excel = tmp_path / "report_manifest.xlsx"
        result = build_standard_report(
            sections, excel_path=str(excel), run_manifest=manifest
        )
        assert result["excel"] is True
        xls = pd.ExcelFile(excel)
        assert "Manifest" in xls.sheet_names

    def test_strict_manifest_blocks_export_when_missing(self, tmp_path):
        sections = [ReportSection(title="Data", kind="table", content=pd.DataFrame({"x": [1]}))]
        excel = tmp_path / "report_strict_missing.xlsx"
        result = build_standard_report(
            sections,
            excel_path=str(excel),
            require_complete_manifest=True,
        )
        assert result["excel"] is False
        assert not excel.exists()

    def test_strict_manifest_blocks_export_when_incomplete(self, tmp_path):
        sections = [ReportSection(title="Data", kind="table", content=pd.DataFrame({"x": [1]}))]
        excel = tmp_path / "report_strict_incomplete.xlsx"
        result = build_standard_report(
            sections,
            excel_path=str(excel),
            run_manifest={"run_id": "x"},
            require_complete_manifest=True,
        )
        assert result["excel"] is False
        assert not excel.exists()

    def test_get_missing_manifest_fields_helper(self):
        missing_all = get_missing_manifest_fields(None)
        assert "run_id" in missing_all
        assert "params_hash" in missing_all

        missing_partial = get_missing_manifest_fields({"run_id": "x", "app_id": "CERTUS_X"})
        assert "started_at_utc" in missing_partial
        assert "app_version" in missing_partial
        assert "status" in missing_partial
        assert "params_hash" in missing_partial


def test_helpers_are_in_certus_data_all():
    import certus_data
    assert "ReportSection" in certus_data.__all__
    assert "build_standard_report" in certus_data.__all__
