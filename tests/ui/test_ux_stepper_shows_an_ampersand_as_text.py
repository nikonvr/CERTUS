"""A step label with an ampersand is shown as written, and does not steal Alt+Space (audit UX A10, ETAT D85).

`QPushButton("Mesh & optimizer")` reads the ampersand as the mnemonic marker of the NEXT character, which here is
the space: the label was painted "Mesh _optimizer" (the space underlined) in the INDEX SPLINE workflow guide, and the
button registered Alt+Space, the Windows system-menu shortcut, three times over ("Substrate (n) & layer thickness",
"Mesh & optimizer", "Corridors & RMSE(d)"). The audit read the underlined space as a variable-like name.

The stepper doubles the ampersand for the button, and keeps the label as written for the tooltip.
"""

from __future__ import annotations

import pytest

from certus.ui.certus_ui_widgets_layout import CertusStepper

LABELS = ["Load spectrum", "Substrate (n) & layer thickness", "Mesh & optimizer", "Corridors & RMSE(d)"]


@pytest.mark.parametrize("columns", [1, 2])
def test_a_step_label_with_an_ampersand_registers_no_mnemonic(qapp, columns) -> None:
    stepper = CertusStepper(LABELS, columns=columns)
    for label, button in zip(LABELS, stepper._btns, strict=True):
        assert button.shortcut().isEmpty(), f"{label!r} registered {button.shortcut().toString()!r}"


@pytest.mark.parametrize("columns", [1, 2])
def test_a_step_label_with_an_ampersand_keeps_its_ampersand_on_screen(qapp, columns) -> None:
    stepper = CertusStepper(LABELS, columns=columns)
    for label, button in zip(LABELS, stepper._btns, strict=True):
        assert button.text().replace("&&", "&") == label
        assert button.toolTip().endswith(label), "the tooltip is not a mnemonic text: it must keep the label as written"
