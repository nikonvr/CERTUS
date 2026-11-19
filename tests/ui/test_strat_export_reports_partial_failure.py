"""Regression tests for UX-1: STRAT export status reflects partial or failed artifacts."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from certus.ui import certus_strat_ui_export as export_mod
from certus.ui.certus_strat_ui_export import CertusStratExportMixin
from certus.utils.certus_atomic_io import atomic_open as real_atomic_open


class _FakeLabel:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _DummyStratExportHost(CertusStratExportMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_strat_export_host")
        self.opti_results = {"execution_time": 1.5, "strategies_results": []}
        self.validation_status = "OK"
        self.validation_warnings: list[str] = []
        self._last_config_file = ""
        self._reports_exported = False
        self.status_label = _FakeLabel()

    def collect_params(self) -> dict:
        return {
            "scan_wl_min": 400,
            "scan_wl_max": 700,
            "l0": 550,
            "nH_id": "H",
            "nL_id": "L",
            "nSub_id": "SiO2",
            "stack_string": "H,L",
            "robustness_seed": 42,
        }

    def set_validation_status(self, status: str) -> None:
        self.validation_status = status

    def add_validation_warning(self, warning: str) -> None:
        self.validation_warnings.append(warning)


def _patch_report_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_mod, "get_resource_path", lambda _name: str(tmp_path))


def _excel_bytes() -> io.BytesIO:
    return io.BytesIO(b"PK\x03\x04dummy-xlsx-payload")


class _FakeWs:
    def append(self, _row) -> None:
        pass


class _FakeWb:
    def __init__(self) -> None:
        self.sheetnames = ["Summary"]

    def create_sheet(self, _name: str) -> _FakeWs:
        return _FakeWs()

    def __delitem__(self, _name: str) -> None:
        pass


def _patch_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    import openpyxl

    monkeypatch.setattr(openpyxl, "load_workbook", lambda _p: _FakeWb())


def test_on_excel_ready_all_succeed_sets_saved_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(export_mod, "atomic_save_workbook", lambda *_a, **_kw: None)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: True)
    _patch_openpyxl(monkeypatch)
    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    host.on_excel_ready(_excel_bytes(), {"rmse": 0.01234, "params": host.collect_params()})

    assert host.status_label.text().startswith("✓ Saved:")
    assert host._reports_exported is True


def test_on_excel_ready_html_failure_reports_partial_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(export_mod, "atomic_save_workbook", lambda *_a, **_kw: None)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: False)
    _patch_openpyxl(monkeypatch)
    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    host.on_excel_ready(_excel_bytes(), {"rmse": 0.01234, "params": host.collect_params()})

    status = host.status_label.text()
    assert not status.startswith("✓ Saved")
    assert "Partial export" in status
    assert "Excel" in status
    assert "Manifest" in status
    assert "HTML" in status
    assert host._reports_exported is False


def test_on_excel_ready_manifest_failure_reports_partial_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(export_mod, "atomic_save_workbook", lambda *_a, **_kw: None)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: True)
    _patch_openpyxl(monkeypatch)

    def _failing_manifest_open(path, *args, **kwargs):
        if str(path).endswith(".manifest.json"):
            raise OSError("disk full")
        return real_atomic_open(path, *args, **kwargs)

    monkeypatch.setattr(export_mod, "atomic_open", _failing_manifest_open)

    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    host.on_excel_ready(_excel_bytes(), {"rmse": 0.01234, "params": host.collect_params()})

    status = host.status_label.text()
    assert not status.startswith("✓ Saved")
    assert "Partial export" in status
    assert "Manifest" in status
    assert "Excel" in status
    assert "HTML" in status
    assert host._reports_exported is False


def test_auto_export_results_all_succeed_sets_saved_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: True)
    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    host._auto_export_results()

    assert host.status_label.text().startswith("✓ Saved:")
    assert host._reports_exported is True


def test_auto_export_results_html_failure_reports_partial_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: False)
    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    host._auto_export_results()

    status = host.status_label.text()
    assert not status.startswith("✓ Saved")
    assert "Partial export" in status
    assert "HTML" in status
    assert "Excel" in status
    assert host._reports_exported is False


def test_auto_export_results_total_failure_reports_export_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_report_dir(monkeypatch, tmp_path)
    host = _DummyStratExportHost()
    monkeypatch.setattr(host, "_manifest_source_paths", lambda: [])

    def _boom_excel(*_a, **_kw):
        raise OSError("cannot write excel")

    monkeypatch.setattr(host, "_write_export_excel", _boom_excel)
    monkeypatch.setattr(export_mod, "generate_html_report", lambda *_a, **_kw: False)

    host._auto_export_results()

    status = host.status_label.text()
    assert not status.startswith("✓ Saved")
    assert "Export failed" in status
    assert host._reports_exported is False
