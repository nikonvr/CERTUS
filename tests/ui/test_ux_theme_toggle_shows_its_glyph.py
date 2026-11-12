"""The theme toggle shows its glyph under the sheet of the suite (A10).

Measured on 2026-11-12 (ink pixels of the toggle, 1440x900): 72 in DESIGN, 0 in the nine other windows that have it.
The toggle is a fixed 32x32 round button whose caption is a glyph at H2 size; the sheet of the suite gives every push
button a padding and a minimum height, which left no room for the glyph and stretched the button to 32x46. DESIGN
showed it because its compact sheet overrides those two rules.
"""

from __future__ import annotations

import pytest


def _ink(widget) -> int:
    image = widget.grab().toImage()
    paper = image.pixelColor(image.width() // 2, 3)
    count = 0
    for x in range(6, image.width() - 6):
        for y in range(6, image.height() - 6):
            c = image.pixelColor(x, y)
            if abs(c.red() - paper.red()) + abs(c.green() - paper.green()) + abs(c.blue() - paper.blue()) > 120:
                count += 1
    return count


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_toggle_draws_its_glyph_inside_its_32_px(qapp, mode) -> None:
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from certus.ui.certus_theme import CertusTheme
    from certus.ui.certus_ui_utils import apply_certus_theme
    from certus.ui.certus_ui_widgets_utils import CertusThemeToggle

    CertusTheme.configure(mode)
    try:
        host = QWidget()
        apply_certus_theme(host)
        toggle = CertusThemeToggle(host)
        QVBoxLayout(host).addWidget(toggle)
        host.resize(120, 120)
        host.show()
        qapp.processEvents()

        assert (toggle.width(), toggle.height()) == (32, 32)
        assert _ink(toggle) > 20, f"the toggle shows no glyph in {mode}"
    finally:
        CertusTheme.configure("light")
