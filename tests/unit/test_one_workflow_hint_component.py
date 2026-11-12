"""The static guide of a workflow is one component (U7, B1).

Measured on 2026-11-12: DESIGN, RE, METAL and STRAT wrote their guide by hand, "1 Build stack · 2 ..." in STRAT and
"1 Load data  →  2 ..." elsewhere, in three styles. They now call `create_workflow_hint`. INDEX SPLINE's `CertusStepper`
is a navigation control, not a guide, and stays.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.unit.test_visible_units_and_symbols_are_whole import INTERFACE, visible_strings

ROOT = Path(__file__).resolve().parents[2]
#: A numbered list of steps written in one string: "1 Something", a separator, "2 Something".
HAND_WRITTEN_GUIDE = re.compile(r"\b1 [A-Za-z].*?(→|·|->|\|).*?\b2 [A-Za-z]")
GUIDED_WINDOWS = (
    "certus_design_ui_layout.py",
    "certus_metal_base_app.py",
    "certus_re_layout_mixin.py",
    "certus_strat_ui_layout.py",
)


def test_no_window_writes_its_workflow_guide_by_hand():
    found = [
        f"{path.name}:{line} {text[:60]!r}"
        for path in INTERFACE
        for line, text in visible_strings(path)
        if HAND_WRITTEN_GUIDE.search(text)
    ]
    assert found == []


def test_the_guided_windows_call_the_component():
    sources = {path.name: path.read_text(encoding="utf-8-sig") for path in INTERFACE}
    missing = [name for name in GUIDED_WINDOWS if "create_workflow_hint(" not in sources[name]]
    assert missing == []
