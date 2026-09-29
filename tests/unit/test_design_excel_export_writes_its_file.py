"""DESIGN's « Export to Excel » asks for a file and writes it.

ExportManager.export_excel opened its save dialog with the manager as parent:
QFileDialog refuses a parent that is not a QWidget, so the export raised TypeError before
writing anything — swallowed by safe_ui_action into a log line — from the split of the
window into managers (c79316b, 2026-06-13) to 2026-09-29.
"""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN Excel export", main_windows_only=True)


def test_the_excel_export_writes_the_chosen_file(qapp, monkeypatch, tmp_path) -> None:
    from PyQt6.QtWidgets import QFileDialog, QWidget

    from certus.ui.certus_design_ui import CertusDesignApp

    target = tmp_path / "design.xlsx"

    def save_dialog(parent, *args, **kwargs):
        # The real dialog raises TypeError on a parent that is not a widget.
        if parent is not None and not isinstance(parent, QWidget):
            raise TypeError(f"argument 1 has unexpected type {type(parent).__name__!r}")
        return str(target), "Excel (*.xlsx)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", save_dialog)
    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))

    app.export_excel()

    assert target.is_file()
