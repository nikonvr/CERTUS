"""The STRAT export status names the files it really wrote (UX audit 2026-11-18, item 1).

Both export paths set "✓ Saved" unconditionally: a manifest JSON or an HTML report that failed to write only reached
the log, and the automatic path still said "Saved" when nothing at all had been written. The operator left believing
the report existed. The status must say "✓ Saved" only when the xlsx, the manifest JSON and the HTML all exist, and
otherwise name what was written and what is missing. It names the folder, and a "Retry missing" button writes
again the missing files only.
"""

from __future__ import annotations

import io
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from pathlib import Path

import openpyxl
import pytest

from certus.ui import certus_strat_ui_export as export
from certus.utils import certus_data


@pytest.fixture
def strat(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    monkeypatch.setattr(export, "get_resource_path", lambda _name: str(tmp_path))
    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        yield win
    finally:
        win.close()


def _fails_for(real, suffix: str, exc: type[Exception], broken: list[bool] | None = None):
    """``real`` unchanged, except that a path ending with ``suffix`` raises ``exc`` while ``broken[0]`` holds."""
    broken = broken if broken is not None else [True]

    def wrapper(path, *args, **kwargs):
        if broken[0] and str(path).endswith(suffix):
            raise exc(f"injected failure for {suffix}")
        return real(path, *args, **kwargs)

    return wrapper


def _excel_signal(strat) -> None:
    stream = io.BytesIO()
    openpyxl.Workbook().save(stream)
    strat.on_excel_ready(stream, {"rmse": 0.004, "params": {}})


def _automatic(strat) -> None:
    strat._reports_exported = False
    strat.opti_results = {
        "strategies_results": [
            {
                "strategy_id": 7,
                "strategy": {"strategy_id": 7, "n_blocks": 1, "blocks": [{"start": 0, "end": 3, "wavelength": 550.0}]},
                "rmse": 0.004,
                "robustness_score": 0.0064,
            }
        ]
    }
    strat._auto_export_results()


def _written(tmp_path: Path) -> set[str]:
    names = [p.name for p in tmp_path.iterdir()]
    kinds = {".manifest.json": "json", ".xlsx": "xlsx", ".html": "html"}
    return {kind for name in names for suffix, kind in kinds.items() if name.endswith(suffix)}


def _mtimes(tmp_path: Path) -> dict[str, int]:
    return {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()}


def test_everything_written_says_saved_and_where(strat, tmp_path) -> None:
    _excel_signal(strat)
    assert _written(tmp_path) == {"xlsx", "json", "html"}
    status = strat.status_label.text()
    assert status.startswith("✓ Saved: ")
    assert f" in {tmp_path}" in status
    assert not strat.retry_export_btn.isVisibleTo(strat)
    assert strat._reports_exported is True


def test_a_failed_manifest_is_named_missing(strat, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(export, "atomic_open", _fails_for(export.atomic_open, ".manifest.json", OSError))
    _excel_signal(strat)
    assert _written(tmp_path) == {"xlsx", "html"}
    status = strat.status_label.text()
    assert "✓ Saved" not in status
    assert "missing: manifest json" in status
    assert "written: xlsx, html" in status
    assert strat._reports_exported is False


@pytest.mark.parametrize("run", [_excel_signal, _automatic], ids=["excel_signal", "automatic"])
def test_a_failed_html_is_named_missing(strat, tmp_path, monkeypatch, run) -> None:
    monkeypatch.setattr(certus_data, "atomic_open", _fails_for(certus_data.atomic_open, ".html", ValueError))
    run(strat)
    assert _written(tmp_path) == {"xlsx", "json"}
    status = strat.status_label.text()
    assert "✓ Saved" not in status
    assert "missing: html" in status
    assert "written: xlsx, manifest json" in status
    assert strat._reports_exported is False


def test_a_failed_excel_and_html_are_named_missing(strat, tmp_path, monkeypatch) -> None:
    """The audit's fifth case. The manifest JSON no longer depends on the xlsx: it is written, and said so."""
    monkeypatch.setattr(certus_data, "atomic_open", _fails_for(certus_data.atomic_open, ".html", ValueError))
    monkeypatch.setattr(export, "atomic_excel_writer", _fails_for(export.atomic_excel_writer, ".xlsx", ValueError))
    monkeypatch.setattr(export, "to_excel_robust", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("injected")))
    _automatic(strat)
    assert _written(tmp_path) == {"json"}
    status = strat.status_label.text()
    assert "✓ Saved" not in status
    assert "written: manifest json; missing: xlsx, html" in status
    assert strat._reports_exported is False


def test_nothing_written_says_not_saved(strat, tmp_path, monkeypatch) -> None:
    for module in (export, certus_data):
        monkeypatch.setattr(module, "atomic_open", _fails_for(module.atomic_open, "", OSError))
    monkeypatch.setattr(export, "atomic_excel_writer", _fails_for(export.atomic_excel_writer, ".xlsx", OSError))
    _automatic(strat)
    assert _written(tmp_path) == set()
    status = strat.status_label.text()
    assert status.startswith("✗ Not saved: ")
    assert "missing: xlsx, manifest json, html" in status
    assert strat._reports_exported is False


@pytest.mark.parametrize(
    ("module", "suffix", "exc", "kind"),
    [(certus_data, ".html", ValueError, "html"), (export, ".manifest.json", OSError, "manifest json")],
    ids=["html", "manifest"],
)
def test_retry_writes_only_the_missing_file(strat, tmp_path, monkeypatch, module, suffix, exc, kind) -> None:
    broken = [True]
    monkeypatch.setattr(module, "atomic_open", _fails_for(module.atomic_open, suffix, exc, broken))
    _excel_signal(strat)
    assert f"missing: {kind};" in strat.status_label.text()
    assert strat.retry_export_btn.isVisibleTo(strat)
    assert strat._reports_exported is False
    before = _mtimes(tmp_path)

    broken[0] = False  # the cause is gone (the operator closed the file, freed the disk...)
    strat.retry_export_btn.click()

    assert _written(tmp_path) == {"xlsx", "json", "html"}
    assert strat.status_label.text().startswith("✓ Saved: ")
    assert not strat.retry_export_btn.isVisibleTo(strat)
    assert strat._reports_exported is True
    after = _mtimes(tmp_path)
    assert {name: after[name] for name in before} == before, "the retry rewrote a file that was already written"
