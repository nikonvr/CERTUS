"""No window opens on a blank plot (U10, C1).

Measured on 2026-11-13 (`scripts/audit_ux_certus.py::empty_plots`, 1440x900, at opening): eight pyqtgraph plots
showed empty axes from 0 to 1 and nothing else — FIELD 3, INDEX 1, INDEX SPLINE 2, SMOOTHER 1, SUBSTRATE INDEX 1.
An empty plot carries a card that says what to do (`certus_empty_state.attach_plot_empty_state`).
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker


@pytest.mark.parametrize("app", sorted(MODULES))
def test_an_empty_plot_says_what_to_do(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["empty_plots"] == [], f"{app} opens blank plots: {row['empty_plots']}"
