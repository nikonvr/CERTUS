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

#: Their pictogram IS the content (the tiles of the HUB, the welcome page of STRAT): an SVG icon renders empty on Windows
#: with Python >= 3.14 (`certus_icons._qsvg_stack_known_unstable`) and would leave a blank square. They wait for the
#: owner's decision on that guard (REPRISE.md of reports/refactor_corridors_2026-11-11, 2026-11-12).
WAITING_FOR_THE_SVG_DECISION = frozenset({"CERTUS_STRAT"})


@pytest.mark.parametrize("app", sorted(MODULES))
def test_no_label_of_the_window_draws_an_emoji(app) -> None:
    if app in WAITING_FOR_THE_SVG_DECISION:
        pytest.xfail("waits for the owner's decision on the SVG guard")
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["emoji_labels"] == [], f"{app} draws emojis in its labels: {row['emoji_labels']}"
