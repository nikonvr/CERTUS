"""A numeric setting must not accept what its reader cannot parse (plan UX, 4.3).

Every numeric setting of STRAT is a free-text field with no validator. The
settings layer reads them with ``float(text)`` and, on failure, falls back to a
default **silently**: the screen shows what the operator typed, the engine uses
something else.

🔑 The decimal comma is the sharp edge. On a French keyboard ``1,5`` is the
natural way to write one and a half - and ``float("1,5")`` raises, so the value
is dropped without a word. On a metrology tool that is a wrong run, not a typo.

⚠️ What this guard does NOT check: numeric RANGES. No bound for these settings
exists anywhere in the code - no pydantic constraint, no setRange - so a range
would have to be invented, and an invented bound on a physics parameter is
worse than none. The contract checked here is the one the code really states:
**whatever the field accepts, its reader must be able to parse.**
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

#: Reads as a comma-separated LIST ("0.5,1,2"), not a single number.
LIST_VALUED = {"robustness_noise_factors"}


@pytest.fixture(scope="module")
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _numeric_line_edits(win) -> dict:
    from PyQt6.QtWidgets import QLineEdit

    return {key: w for key, w in win.widgets.items() if isinstance(w, QLineEdit) and key not in LIST_VALUED}


def test_there_are_numeric_fields_to_check(strat):
    """Guard against the guard: an empty set would make everything below pass."""
    assert len(_numeric_line_edits(strat)) >= 30, (
        f"only {len(_numeric_line_edits(strat))} field(s) found - has the layout changed?"
    )


def test_every_numeric_field_has_a_validator(strat):
    naked = sorted(k for k, w in _numeric_line_edits(strat).items() if w.validator() is None)
    assert not naked, (
        f"{len(naked)} numeric setting(s) accept any text, and their reader falls back to a default in silence: {naked}"
    )


@pytest.mark.parametrize("bad", ["abc", "1,5", "1.2.3", "oui"])
def test_a_numeric_field_refuses_what_float_cannot_parse(strat, bad):
    """Anything the field accepts must survive float() - that is the real contract."""
    from PyQt6.QtGui import QValidator

    offenders = []
    for key, widget in _numeric_line_edits(strat).items():
        v = widget.validator()
        if v is None:
            continue
        state, _text, _pos = v.validate(bad, len(bad))
        if state == QValidator.State.Acceptable:
            try:
                float(bad)
            except ValueError:
                offenders.append(key)
    assert not offenders, f"field(s) accepting {bad!r}, which float() rejects: {offenders[:5]}"


def test_a_numeric_field_still_accepts_a_plain_number(strat):
    """A validator that refuses valid input would be worse than none."""
    from PyQt6.QtGui import QValidator

    refused = []
    for key, widget in _numeric_line_edits(strat).items():
        v = widget.validator()
        if v is None:
            continue
        state, _t, _p = v.validate("1.5", 3)
        if state == QValidator.State.Invalid:
            refused.append(key)
    assert not refused, f"field(s) refusing the valid value '1.5': {refused[:5]}"


def test_the_list_valued_field_keeps_accepting_its_list(strat):
    """robustness_noise_factors holds '0.5,1,2' - a number validator would break it."""
    from PyQt6.QtGui import QValidator

    widget = strat.widgets.get("robustness_noise_factors")
    if widget is None:
        pytest.skip("robustness_noise_factors is not in this layout")

    v = widget.validator()
    if v is None:
        return  # no validator at all is the acceptable state here
    state, _t, _p = v.validate("0.5,1,2", 7)
    assert state != QValidator.State.Invalid, (
        "the noise-factor list can no longer be typed: a number validator was applied to a comma-separated field"
    )
