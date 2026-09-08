"""Booleans must be checkboxes, not free-text fields (plan UX, 4.3).

Seven STRAT settings are on/off switches typed into a text box labelled
"(0/1)": slit bias, slit search, Rate mode, and four SYM flags. Nothing stops
an operator entering 2, "oui" or a blank, and nothing tells them what happens
then - the reader falls back to a default, silently.

⚠️ The subtlety that makes this more than a widget swap: the whole settings
layer reads these widgets through ``_get_float_safe``, which calls ``.text()``.
A bare ``QCheckBox`` returns its *label* there, so swapping the class alone
would feed the engine a default instead of the operator's choice - a wrong
value that looks like a working screen. The replacement therefore has to keep
the ``.text()`` / ``.setText()`` contract.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

BOOLEAN_KEYS = (
    "slit_bias_enabled",
    "search_resolution",
    "allow_rate",
    "sym_enable",
    "sym_adaptive_same_wl",
    "sym_allow_hybrid",
    "sym_prefer_on_tie",
)


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


def test_every_boolean_setting_exists(strat):
    """Guard against the guard: a missing key would make the rest vacuous."""
    missing = [k for k in BOOLEAN_KEYS if k not in strat.widgets]
    assert not missing, f"unknown setting key(s), the guard would test nothing: {missing}"


@pytest.mark.parametrize("key", BOOLEAN_KEYS)
def test_a_boolean_setting_is_a_checkbox(strat, key):
    from PyQt6.QtWidgets import QCheckBox

    widget = strat.widgets[key]
    assert isinstance(widget, QCheckBox), (
        f"{key} is a {type(widget).__name__}: an on/off setting typed as free text accepts 2, 'oui' or nothing at all"
    )


@pytest.mark.parametrize("key", BOOLEAN_KEYS)
def test_a_boolean_setting_still_reads_as_zero_or_one(strat, key):
    """The settings layer reads these through .text() - that contract must hold."""
    widget = strat.widgets[key]

    widget.setText("1")
    assert widget.text().strip() == "1", f"{key}: setText('1') did not read back as '1'"
    assert float(widget.text()) == 1.0, f"{key}: '1' is not readable as a number"

    widget.setText("0")
    assert widget.text().strip() == "0", f"{key}: setText('0') did not read back as '0'"
    assert float(widget.text()) == 0.0, f"{key}: '0' is not readable as a number"


@pytest.mark.parametrize("key", BOOLEAN_KEYS)
def test_clicking_a_boolean_setting_changes_what_is_read(strat, key):
    """A checkbox the engine cannot see would be worse than the text field."""
    widget = strat.widgets[key]

    widget.setChecked(True)
    assert widget.text().strip() == "1", f"{key}: checked but reads {widget.text()!r}"

    widget.setChecked(False)
    assert widget.text().strip() == "0", f"{key}: unchecked but reads {widget.text()!r}"


@pytest.mark.parametrize("key", BOOLEAN_KEYS)
def test_a_boolean_setting_keeps_a_visible_label(strat, key):
    """Turning the field into a checkbox must not lose the wording next to it."""
    widget = strat.widgets[key]
    label = widget.accessibleName() or getattr(widget, "_certus_label", "")
    assert str(label).strip(), f"{key} has no label a reader could announce"
