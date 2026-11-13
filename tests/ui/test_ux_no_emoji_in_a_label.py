"""No label, button, tab or group title draws an emoji (U8, B6).

Measured on 2026-11-12 (`scripts/audit_ux_certus.py::emoji_labels`, 1440x900, at opening): 36 labels in 9 windows
— the Reset button of eight windows, three buttons of DESIGN, five card titles and two buttons of FIELD, the nine
tiles of the HUB (METAL SINGLE and METAL BILAYER with the same 🛡️), nine pictograms of STRAT's welcome page. An emoji
is drawn by the emoji font of the system: its look changes from one machine to the next and ignores the theme. The
suite's icons are the SVG of `certus.ui.certus_icons` (decision Q32 of the plan).
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker


@pytest.mark.parametrize("app", sorted(MODULES))
def test_no_label_of_the_window_draws_an_emoji(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["emoji_labels"] == [], f"{app} draws emojis in its labels: {row['emoji_labels']}"
