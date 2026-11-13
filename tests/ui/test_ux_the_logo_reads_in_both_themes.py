"""The word of the logo reads on the header in both themes (audit A10, U13).

`certus.svg` writes its words in navy and black: on the dark header they vanished. The SVG guard hid it on Windows
until PyQt6 6.11 (Q35): the logo was not drawn at all. Measured on the painted pixels, the word's ink must reach the
4.5:1 of body text against the header.
"""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_theme import CertusTheme


def _best_contrast(widget, background: str) -> float:
    """Contrast of the logo's main ink (the most frequent colour after the fill: arc and word) against the header.

    A grab is filled with the palette's window colour, not the header's: that fill is set aside, and the ink is
    measured against the colour the header really paints. The accent of the drawing does not count: it is not the word.
    """
    from collections import Counter

    image = widget.grab().toImage()
    colours = Counter(QColor(image.pixel(x, y)).name() for y in range(image.height()) for x in range(image.width()))
    (_fill, _), (ink, _) = colours.most_common(2)
    return contrast_ratio(ink, background)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_logo_word_reads_on_the_header(qapp, mode) -> None:
    from PyQt6.QtSvgWidgets import QSvgWidget

    from certus.ui.certus_ui_widgets_factory import create_header_logo_widget

    was_dark = CertusTheme.DARK_MODE
    CertusTheme.configure(mode)
    try:
        header = create_header_logo_widget("CERTUS", "test")
        header.resize(600, 60)
        header.show()
        qapp.processEvents()
        (logo,) = header.findChildren(QSvgWidget)
        assert _best_contrast(logo, CertusTheme.SURFACE) >= 4.5, f"logo unreadable on the {mode} header"
        header.close()
        header.deleteLater()
    finally:
        CertusTheme.configure("dark" if was_dark else "light")


def test_the_logo_follows_a_theme_change(qapp) -> None:
    """Built in light, switched to dark: the header changes colour, the logo must follow."""
    from PyQt6.QtSvgWidgets import QSvgWidget

    from certus.ui.certus_ui_widgets_factory import create_header_logo_widget

    was_dark = CertusTheme.DARK_MODE
    CertusTheme.configure("light")
    try:
        header = create_header_logo_widget("CERTUS", "test")
        header.resize(600, 60)
        header.show()
        CertusTheme.configure("dark")
        CertusTheme.refresh_widget_sheets(qapp)
        qapp.processEvents()
        (logo,) = header.findChildren(QSvgWidget)
        assert _best_contrast(logo, CertusTheme.SURFACE) >= 4.5, "the logo kept its light-theme ink"
        header.close()
        header.deleteLater()
    finally:
        CertusTheme.configure("dark" if was_dark else "light")
