"""A 1920x1080 screen at 150 % keeps the rules of the UX harness (U13, scaled screen).

Windows at 150 % gives a 1920x1080 screen 1280x720 logical pixels: smaller than the 1366x768 the audit already
holds, and the most common laptop setting. `scripts/audit_ux_certus.py --scale 1.5` draws each window at that
scale (the row carries the `device_pixel_ratio` Qt really used, so a scale that does not reach Qt fails here).

Measured 2026-11-13 before the fix: DESIGN and INDEX SPLINE showed 2 buttons without a tooltip each, the left and
right arrows Qt adds to a tab bar whose tabs no longer fit: no tooltip (Qt names them for a screen reader).
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker, _verdicts

LAYOUT_RULES = ("plot area", "overflows", "hides")


@pytest.mark.parametrize("app", list(MODULES))
def test_the_window_keeps_the_rules_at_150_percent(app) -> None:
    row = _run_worker(app, 1280, 720, scale=1.5)
    assert "ERROR" not in row, row.get("ERROR")
    assert row["device_pixel_ratio"] == 1.5, "the scale did not reach Qt: this would audit 1x"

    assert row["btn_no_tooltip"] == 0, f"{app}: {row['btn_no_tooltip']} visible button(s) without a tooltip"
    broken = [v for v in _verdicts(row) if any(rule in v for rule in LAYOUT_RULES)]
    assert not broken, f"{app} at 1280x720, 150 %: {broken}"


def test_a_tab_bar_gives_its_scroll_arrows_a_tooltip(qapp) -> None:
    from PyQt6.QtWidgets import QTabWidget, QToolButton, QWidget

    from certus.ui.certus_ui_widgets_utils import name_tab_scroll_buttons

    tabs = QTabWidget()
    for i in range(12):
        tabs.addTab(QWidget(), f"A rather long tab title {i}")
    tabs.resize(300, 200)
    name_tab_scroll_buttons(tabs)
    arrows = tabs.tabBar().findChildren(QToolButton)
    assert len(arrows) == 2
    for arrow in arrows:
        assert arrow.toolTip(), arrow.objectName()
    tabs.deleteLater()
