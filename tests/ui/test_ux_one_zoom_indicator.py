"""A window shows the interface scale once, and in its status bar (U4).

Measured on 2026-11-12 (`scripts/audit_ux_certus.py::zoom_indicators`, 1440x900):

    DESIGN, STRAT, RE  "Zoom 100%" twice in the status bar: the window built its own label, then the base class,
                       which did not know of it, added another
    INDEX SPLINE       no status bar: the label of the base class was parented to the window and drawn on its top-left
                       corner, under the menu bar

The base class now owns the one label: a window that builds its status bar gives its label to the base class, and a
window without a status bar has no label (the zoom is still announced by a toast).
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker


@pytest.mark.parametrize("app", sorted(MODULES))
def test_the_scale_is_shown_once_at_most_and_in_the_status_bar(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    shown = row["zoom_indicators"]

    assert len(shown) <= 1, f"{app} shows the scale {len(shown)} times: {shown}"
    assert all(item.startswith("status bar|") for item in shown), f"{app} shows the scale outside its status bar: {shown}"
