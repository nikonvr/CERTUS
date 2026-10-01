"""The empty-state panel is announced by its title, and its labels and button say their own text (plan S6.5).

Measured on 2026-10-01: the panel gave its title label the accessible name "Empty state title", its description label
"Empty state description", its icon "Empty state icon" and its button "Empty state action". An accessible name REPLACES the text a
label or a button shows: a screen reader said "Empty state title" where the title says "No spectrum loaded", and "Empty state
action" where the button says "Load". The panel itself is named by its title; the others carry no name of their own.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QLabel, QPushButton


def _panel(qapp):
    from certus.ui.certus_empty_state import build_empty_state

    return build_empty_state(None, title="No spectrum loaded", description="Load a file to begin.", action_label="Load")


def test_the_panel_is_named_by_its_title(qapp):
    panel = _panel(qapp)
    assert panel.accessibleName() == "No spectrum loaded"


def test_no_label_of_the_panel_hides_its_text_behind_a_name(qapp):
    panel = _panel(qapp)  # held: a panel without a parent takes its children with it when it is collected
    labels = panel.findChildren(QLabel)
    assert {"No spectrum loaded", "Load a file to begin."} <= {label.text() for label in labels}
    assert [label.accessibleName() for label in labels] == [""] * len(labels)


def test_the_action_button_is_read_by_its_caption(qapp):
    panel = _panel(qapp)
    (button,) = panel.findChildren(QPushButton)
    assert button.text() == "Load"
    assert button.accessibleName() == ""
