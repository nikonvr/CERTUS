"""The DESIGN export status names the files it really wrote (follow-up of the UX audit 2026-11-18, item 1).

Like STRAT, DESIGN set "✓ Saved" once the export flow ended: an HTML report that failed (the generator returns
False) or an xlsx skipped for want of openpyxl still read as saved, and an Excel write that raised left the previous
status on screen. The status must say "✓ Saved" only when the xlsx and the HTML both exist, and otherwise name
what was written and what is missing. It names the folder, and a "Retry missing" button writes again the missing
files only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from certus.ui import certus_design_ui_export as export
from certus.utils import certus_data


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN export status", main_windows_only=True)


@pytest.fixture
def design(qapp, tmp_path, monkeypatch):
    from certus.ui.certus_design_ui import CertusDesignApp

    monkeypatch.setattr(export, "get_resource_path", lambda name: str(tmp_path / name))
    win = CertusDesignApp()
    win.ep_current = np.linspace(80.0, 120.0, len(win._get_front_stack()))
    wl = np.linspace(400.0, 700.0, 31)
    win.last_result = {"rmse": 0.01, "vis": {"l": wl, "Ts": np.full_like(wl, 0.5)}}
    win.status_label.setText("before export")
    return win


def _fails_for(real, suffix: str, exc: type[Exception], broken: list[bool] | None = None):
    """``real`` unchanged, except that a path ending with ``suffix`` raises ``exc`` while ``broken[0]`` holds."""
    broken = broken if broken is not None else [True]

    def wrapper(*args, **kwargs):
        if broken[0] and any(str(a).endswith(suffix) for a in args):
            raise exc(f"injected failure for {suffix}")
        return real(*args, **kwargs)

    return wrapper


def _written(tmp_path: Path) -> set[str]:
    folder = tmp_path / "reports"
    return {p.suffix.lstrip(".") for p in folder.iterdir()} if folder.exists() else set()


def test_everything_written_says_saved_and_where(design, tmp_path) -> None:
    design.export_results()
    assert _written(tmp_path) == {"xlsx", "html"}
    status = design.status_label.text()
    assert status.startswith("✓ Saved: ")
    assert f" in {tmp_path / 'reports'}" in status
    assert not design.retry_export_btn.isVisibleTo(design)


def test_a_failed_html_is_named_missing(design, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(certus_data, "atomic_open", _fails_for(certus_data.atomic_open, ".html", ValueError))
    design.export_results()
    assert _written(tmp_path) == {"xlsx"}
    status = design.status_label.text()
    assert "✓ Saved" not in status
    assert "written: xlsx; missing: html" in status


def test_an_xlsx_skipped_without_openpyxl_is_named_missing(design, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(export, "OPENPYXL_AVAILABLE", False)
    design.export_results()
    assert _written(tmp_path) == {"html"}
    status = design.status_label.text()
    assert "✓ Saved" not in status
    assert "written: html; missing: xlsx" in status


def test_a_failed_excel_write_still_writes_the_html(design, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(export, "atomic_save_workbook", _fails_for(export.atomic_save_workbook, ".xlsx", OSError))
    design.export_results()
    assert _written(tmp_path) == {"html"}
    assert "written: html; missing: xlsx" in design.status_label.text()


def test_nothing_written_says_not_saved(design, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(export, "atomic_save_workbook", _fails_for(export.atomic_save_workbook, ".xlsx", OSError))
    monkeypatch.setattr(certus_data, "atomic_open", _fails_for(certus_data.atomic_open, ".html", OSError))
    design.export_results()
    assert _written(tmp_path) == set()
    status = design.status_label.text()
    assert status.startswith("✗ Not saved: ")
    assert "missing: xlsx, html" in status


def test_retry_writes_only_the_missing_html(design, tmp_path, monkeypatch) -> None:
    broken = [True]
    monkeypatch.setattr(certus_data, "atomic_open", _fails_for(certus_data.atomic_open, ".html", OSError, broken))
    design.export_results()
    assert design.retry_export_btn.isVisibleTo(design)
    (xlsx,) = (tmp_path / "reports").glob("*.xlsx")
    before = xlsx.stat().st_mtime_ns

    broken[0] = False
    design.retry_export_btn.click()

    assert _written(tmp_path) == {"xlsx", "html"}
    assert design.status_label.text().startswith("✓ Saved: ")
    assert not design.retry_export_btn.isVisibleTo(design)
    assert xlsx.stat().st_mtime_ns == before, "the retry rewrote the xlsx that was already written"
