"""DESIGN's target table offers the two waves that a kernel computes: s and p (PHY-02).

The table offered `Avg` ("unpolarized average") and every kernel computed p for it. A configuration saved with
`Avg` loads as `s`, and says so. The window is destroyed at the end of each test (`qt_lifecycle`, autouse).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def design_window(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN targets", main_windows_only=True)


def test_the_target_table_of_design_offers_s_and_p_only() -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.oblique_check.setChecked(True)  # the columns of the oblique table: active, angle, polarization, type...
    app.add_target()
    combo = app.target_table.cellWidget(app.target_table.rowCount() - 1, 2)

    assert [combo.itemText(i) for i in range(combo.count())] == ["s", "p"]


def test_a_configuration_saved_with_avg_says_that_it_keeps_s() -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.oblique_check.setChecked(True)
    logs = []
    app.log = lambda message, level="INFO": logs.append((level, message))

    app.state_manager._apply_target_config(
        [{"angle": 45.0, "polarization": "Avg", "target_type": "T", "lmin": 500, "lmax": 600}], oblique_mode=True
    )

    row = app.target_table.rowCount() - 1
    assert app.target_table.cellWidget(row, 2).currentText() == "s"
    assert any(level == "WARNING" and "'Avg'" in message for level, message in logs)
