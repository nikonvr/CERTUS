"""No button may be shorter than the suite's floor (plan UX, 4.4).

A minimum height was applied across the suite in an earlier phase, but SMOOTHER
and SUBSTRATE INDEX were absent from the harness at the time and never received
it. Measured 2026-09-08: one cramped button in each - the only two left.

The floor comes from the harness itself (``BUTTON_MIN_H``), so this guard cannot
drift away from the value the audit reports.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

from scripts.audit_ux_certus import BUTTON_MIN_H, MODULES, _run_worker


def test_the_floor_is_a_real_constraint():
    """Contrôle négatif : a zero floor would make every module pass."""
    assert BUTTON_MIN_H >= 20, f"the button floor is {BUTTON_MIN_H} px - it constrains nothing"


@pytest.mark.parametrize("app_name", list(MODULES.keys()))
def test_no_button_is_shorter_than_the_floor(app_name: str) -> None:
    row = _run_worker(app_name, 1920, 1080)
    assert "ERROR" not in row, f"audit worker failed for {app_name}: {row.get('ERROR')}"

    short = row.get("btn_short", 0)
    assert not short, (
        f"{app_name}: {short} button(s) under {BUTTON_MIN_H} px high - a cramped "
        "target is harder to hit and reads as unfinished next to the rest of the suite"
    )
