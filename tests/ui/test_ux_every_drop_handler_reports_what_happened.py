"""Every window announces a dropped file as it went: loaded, or refused (audit UX A02, ETAT D79).

The real windows, the real drop events (Qt does not hand a synthetic drop event to a widget outside a real drag, so
the test does what Qt does: the event filters installed on the window first, then its `dropEvent`). A drop reaches a window by one of two doors: the filter that
`enable_file_drop` installs (DESIGN and STRAT for a configuration; RE, METAL and INDEX SPLINE for a data file), or the
base window's `dropEvent` and its router (FIELD and INDEX, and every other kind of file). Both end in
`open_dropped_file`, so one table covers them: for each window, a file it refuses and a file it loads, dropped the way
an operator drops it.

The rule is the same everywhere: "Loaded: <file>" in success for a file that was loaded, "Load failed: <file>" as an
error for any other, and never the success of a refusal (measured 2026-10-02: FIELD, STRAT and RE said "Loaded"
after an error dialog or a silent failure).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QMessageBox

import certus.ui.certus_base_app_run_mixin as run_mixin
import certus.ui.certus_ui_utils as ui_utils

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "example"


def _field(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    return CertusFieldApp()


def _design(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


def _strat(qapp):
    from certus.ui.certus_strat_ui import CertusStratApp

    return CertusStratApp()


def _re(qapp):
    from CERTUS_RE import CertusREApp

    return CertusREApp()


def _metal_single(qapp):
    from certus.metal.certus_metal_single_app import CertusMetalSingleApp

    return CertusMetalSingleApp()


def _metal_bilayer(qapp):
    from certus.metal.certus_metal_bilayer_app import CertusMetalBilayerApp

    return CertusMetalBilayerApp()


def _spline(qapp):
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    return CertusIndexSplineApp()


def _index(qapp):
    from certus.ui.certus_index_ui import CertusIndexApp

    return CertusIndexApp()


def _text_file(name: str, text: str):
    def write(_win, folder: Path) -> Path:
        path = folder / name
        path.write_text(text, encoding="utf-8")
        return path

    return write


def _copy_of(*parts: str):
    def write(_win, folder: Path) -> Path:
        source = EXAMPLES.joinpath(*parts)
        path = folder / source.name
        shutil.copyfile(source, path)
        return path

    return write


def _field_config(win, folder: Path) -> Path:
    path = folder / "field_config.json"
    path.write_text(json.dumps(win._collect_config(), default=str), encoding="utf-8")
    return path


# (window, a file it refuses, a file it loads)
CASES = {
    "FIELD config": (_field, _text_file("broken.json", "{"), _field_config),
    "DESIGN config": (_design, _text_file("broken.json", "{"), _copy_of("example_design", "JSON-design-example.json")),
    "STRAT config": (_strat, _text_file("broken.json", "{"), _copy_of("example_strat", "JSON-strat-example.json")),
    "RE workbook": (_re, _text_file("broken.xlsx", "not a workbook"), _copy_of("example_RE", "reverse_sample.xlsx")),
    "METAL SINGLE data": (
        _metal_single,
        _text_file("broken.csv", "only_one_column\n1\n2\n3\n"),
        _copy_of("example_metal_single", "Target_Titane_Simu_20nm.xlsx"),
    ),
    "METAL BILAYER data": (
        _metal_bilayer,
        _text_file("broken.csv", "only_one_column\n1\n2\n3\n"),
        _copy_of("example_metal_bilayer", "CSV-metal-example.csv"),
    ),
    "INDEX SPLINE data": (
        _spline,
        _text_file("broken.csv", "nothing,here\n"),
        _copy_of("example_index_spline", "TOTAL.xlsx"),
    ),
    "INDEX data": (
        _index,
        _text_file("broken.csv", "nothing,here\n"),
        _copy_of("example_index", "CSV-index-example.csv"),
    ),
}


@pytest.fixture
def announced(monkeypatch):
    """What the operator was told by a toast, and no message box that would block the test."""
    shown: list[tuple[str, str]] = []

    def record(_parent, text, level="info", **_kwargs):
        shown.append((level, text))

    monkeypatch.setattr(run_mixin, "show_toast", record)
    monkeypatch.setattr(ui_utils, "show_toast", record)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    for name in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *_a, **_k: QMessageBox.StandardButton.Ok))
    return shown


def _drop(win, path: Path) -> None:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    event = QDropEvent(
        QPointF(5.0, 5.0), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    for drop_filter in win.findChildren(ui_utils._CertusDropFilter):
        if drop_filter.eventFilter(win, event):
            return
    win.dropEvent(event)


def _drop_on(qapp, make, write, folder: Path) -> list[Path]:
    win = make(qapp)
    try:
        path = write(win, folder)
        _drop(win, path)
        return [path]
    finally:
        win.close()


@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_a_refused_file_is_announced_as_a_failure(qapp, announced, tmp_path, case) -> None:
    make, refused, _loaded = CASES[case]

    (path,) = _drop_on(qapp, make, refused, tmp_path)

    assert announced == [("error", f"Load failed: {path.name}")], announced


@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_a_loaded_file_is_announced_as_loaded(qapp, announced, tmp_path, case) -> None:
    make, _refused, loaded = CASES[case]

    (path,) = _drop_on(qapp, make, loaded, tmp_path)

    assert announced == [("success", f"Loaded: {path.name}")], announced
