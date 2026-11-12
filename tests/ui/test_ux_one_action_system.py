"""The eleven windows share one action system (U6).

Measured on 2026-11-12 (`scripts/audit_ux_certus.py::action_buttons`, 1440x900, buttons visible at opening):

    primary actions   DESIGN 11, RE 6, STRAT 5 ("Show Details" among them), INDEX SPLINE 4, every other window 1
                      (the HUB's being "Scientific Documentation")
    off-palette fill  "Clear / Reset" painted #5a3a00 in eight windows: no theme follows it
    vocabulary        "STOP Calculation", "STOP", "Halt" for the same gesture; "RUN FULL WORKFLOW",
                      "START OPTIMIZATION", "EVALUATE" in capitals

The rules: one primary action per window, the one that starts its main computation; every fill comes from the palette;
a label is written in sentence case (acronyms aside), the button that interrupts a computation reads "Stop" and the one
that clears the window reads "Reset".
"""

from __future__ import annotations

import re

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker

#: Words written in capitals because they are names, not because they shout: acronyms and the modules of the suite.
ACRONYMS = frozenset({"CSV", "JSON", "MC", "PGLOBAL", "QWOT", "RMSE", "SEEL", "TMM", "XLS", "XLSX"}) | frozenset(
    {"CERTUS", "DESIGN", "FIELD", "HUB", "INDEX", "METAL", "SMOOTHER", "SPLINE", "STRAT", "SUBSTRATE"}
)


@pytest.fixture(scope="module")
def buttons() -> dict[str, list[str]]:
    rows = {}
    for app in sorted(MODULES):
        row = _run_worker(app, 1440, 900)
        assert "ERROR" not in row, row.get("ERROR")
        rows[app] = row["action_buttons"]
    return rows


def _split(item: str) -> tuple[str, str]:
    role, _, text = item.partition("|")
    return role, text


@pytest.mark.parametrize("app", sorted(MODULES))
def test_a_window_has_one_primary_action_at_most(app, buttons) -> None:
    # A step badge ("1", "2-4") marks where the user is, it is not an action.
    primary = [t for r, t in map(_split, buttons[app]) if r == "primary" and not re.fullmatch(r"[\d\s\-]*", t)]

    assert len(primary) <= 1, f"{app} has {len(primary)} primary actions: {primary}"


@pytest.mark.parametrize("app", sorted(MODULES))
def test_no_button_is_painted_outside_the_palette(app, buttons) -> None:
    raw = [item for item in buttons[app] if item.startswith("raw:")]

    assert not raw, f"{app} paints buttons with a colour no theme follows: {raw}"


@pytest.mark.parametrize("app", sorted(MODULES))
def test_one_vocabulary_in_sentence_case(app, buttons) -> None:
    texts = [t for _, t in map(_split, buttons[app])]
    shouting = [t for t in texts if any(w not in ACRONYMS for w in re.findall(r"\b[A-Z]{3,}\b", t))]
    stops = [t for t in texts if re.match(r"(?i)(stop|halt|abort)\b", t) and t != "Stop"]
    resets = [t for t in texts if re.search(r"(?i)\breset\b", t) and t != "Reset"]

    assert not shouting, f"{app} writes labels in capitals: {shouting}"
    assert not stops, f"{app} interrupts a computation with another word than 'Stop': {stops}"
    assert not resets, f"{app} clears the window with another label than 'Reset': {resets}"
