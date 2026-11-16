"""DESIGN exports and saves the design as it is, in theme colours (audit 2026-11-15, L5-m1, L5-m7).

L5-m1: export and save ran smart_cleanup, which removed layers under 1 nm and merged neighbours: exporting changed
       the design, and the Spectrum sheet stayed the one of the design before the cleanup.
L5-m7: certus_design_ui_plot drew targets and labels in hard-coded hexadecimal colours and black, outside the theme.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN minor export", main_windows_only=True)


def test_l5_m1_the_excel_export_does_not_clean_the_design(qapp, monkeypatch, tmp_path) -> None:
    import certus.ui.certus_design_ui_export as export_module
    from certus.ui.certus_design_ui import CertusDesignApp

    design = CertusDesignApp()
    monkeypatch.setattr(export_module, "certus_get_save_file_name", lambda *_a, **_k: str(tmp_path / "d.xlsx"))
    called: list[bool] = []
    monkeypatch.setattr(design, "smart_cleanup", lambda *_a, **_k: called.append(True) or 1)
    design.ep_current = np.linspace(80.0, 120.0, len(design._get_front_stack()))

    design.export_excel()

    assert not called, "exporting cleaned the design"
    assert (tmp_path / "d.xlsx").exists()


def test_l5_m7_the_design_plot_uses_theme_colours() -> None:
    source = (ROOT / "certus" / "ui" / "certus_design_ui_plot.py").read_text(encoding="utf-8")
    assert not re.findall(r"[\"']#[0-9a-fA-F]{6}[\"']", source)
    assert 'color="black"' not in source
