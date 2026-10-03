"""RE writes its workflow once, and its speed modes in one line (audit UX A09, ETAT D87).

Measured 2026-10-02, the left panel of RE opened on a "Workflow" card ("1 Load workbook -> 2 Evaluate spectrum -> 3 Run
RE -> 4 Inspect results") and, a few lines below, a "RE workflow" card that said the first three steps again; the
"RE optimization" card then spent four sentences on Slow, Medium and Fast, which the tooltip of each mode already
carries.
"""

from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QLabel


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    win.show()
    try:
        yield win
    finally:
        win.close()


def _texts(win) -> list[str]:
    return [re.sub("<[^>]+>", "", label.text()) for label in win.findChildren(QLabel) if label.text()]


def test_the_workflow_is_stated_once(re_window) -> None:
    stated = [t for t in _texts(re_window) if "Load workbook" in t and "Evaluate spectrum" in t]
    assert len(stated) == 1, f"the workflow is written {len(stated)} times: {stated}"


def test_the_speed_modes_have_one_line_and_the_detail_is_in_their_tooltip(re_window) -> None:
    lines = [t for t in _texts(re_window) if "Slow" in t and "Fast" in t]
    assert len(lines) == 1
    assert len(lines[0]) < 160, f"the line on the speed modes is {len(lines[0])} characters: {lines[0]!r}"
    for radio in (re_window.re_speed_slow_radio, re_window.re_speed_medium_radio, re_window.re_speed_fast_radio):
        assert radio.toolTip(), f"{radio.text()} lost the detail that the line no longer carries"
