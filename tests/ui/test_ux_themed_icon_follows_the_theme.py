"""An icon given by `set_themed_icon` is redrawn in the new palette when the theme changes (U8).

`certus_icon` paints once, in the colour of the moment: the theme switch cleared the cache but left every icon already
on a button in the old palette. A themed icon remembers its name and the token of its colour.
"""

from __future__ import annotations


def _ink(button) -> str:
    image = button.icon().pixmap(20, 20).toImage()
    inked = [image.pixelColor(x, y) for x in range(20) for y in range(20) if image.pixelColor(x, y).alpha() > 200]
    assert inked, "the icon has no opaque pixel"
    return inked[len(inked) // 2].name()


def test_a_themed_icon_takes_the_colour_of_the_new_palette(qapp, monkeypatch) -> None:
    # SVG rendering is off by default on Windows with Python >= 3.14 (`certus_icons._qsvg_stack_known_unstable`).
    monkeypatch.setenv("CERTUS_SVG_ICONS", "1")
    from PyQt6.QtWidgets import QPushButton

    from certus.ui.certus_icons import clear_icon_cache, set_themed_icon
    from certus.ui.certus_theme import CertusTheme

    CertusTheme.configure("light")
    clear_icon_cache()
    try:
        button = QPushButton("Reset")
        set_themed_icon(button, "refresh-ccw", "TEXT_MAIN")
        light = _ink(button)
        assert light == str(CertusTheme.TEXT_MAIN).lower(), light

        CertusTheme.configure("dark")
        CertusTheme.refresh_widget_sheets(qapp)
        dark = _ink(button)

        assert dark == str(CertusTheme.TEXT_MAIN).lower(), (light, dark)
        assert light != dark
    finally:
        CertusTheme.configure("light")


def test_a_widget_without_a_themed_icon_is_left_alone(qapp) -> None:
    from PyQt6.QtWidgets import QPushButton

    from certus.ui.certus_icons import redraw_themed_icon

    assert redraw_themed_icon(QPushButton("plain")) is False
