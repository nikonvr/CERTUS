"""The DESIGN Excel export is written after an optimisation (audit 2026-11-15, M-L5c).

The export tested ``if ep:`` on the thicknesses; after an optimisation they are an array, whose truth value raises: no
file was written.
"""

from __future__ import annotations

import numpy as np
import openpyxl
import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN audit guards", main_windows_only=True)


@pytest.fixture
def design(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


def test_the_excel_export_is_written_when_the_thicknesses_are_an_array(design, monkeypatch, tmp_path) -> None:
    import certus.ui.certus_design_ui_export as export_module

    target = tmp_path / "design.xlsx"
    monkeypatch.setattr(export_module, "certus_get_save_file_name", lambda *_a, **_k: str(target))
    monkeypatch.setattr(design, "smart_cleanup", lambda *_a, **_k: 0)
    n = len(design._get_front_stack())
    assert n > 1
    design.ep_current = np.linspace(80.0, 120.0, n)

    design.export_excel()

    assert target.exists(), "the export wrote no file"
    rows = [list(r) for r in openpyxl.load_workbook(target)["Stack"].iter_rows(values_only=True)]
    assert any(r and r[0] == "TOTAL" for r in rows), "the stack sheet has no TOTAL row"
