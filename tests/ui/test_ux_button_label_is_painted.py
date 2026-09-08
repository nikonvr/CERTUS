"""An action button's label must actually be readable on screen (plan UX, 4.2).

The UX dossier records "Scientific Documentation" as rendering white on white.
``open_documentation`` hands its page to the SYSTEM browser, so the claim could
only be about the button itself. Measured 2026-09-08 by painting the button and
reading the pixels back: 97.6 % of it is ``#ffffff``, the rest is its border,
and there is no ink at all - in BOTH themes.

Two independent causes, both found by this guard:

1. the HUB's bottom bar carried a stylesheet with NO SELECTOR, which in Qt
   applies to the widget *and every child*. Its ``background-color`` therefore
   reached the button, and being set on a nearer ancestor it beat the window's
   ``QPushButton#CertusPrimaryBtn`` rule - while that rule's ``color`` still
   applied. White text, white paper;
2. that same rule hardcoded ``color: #ffffff`` instead of the label token, so
   even once the fill came through, dark mode gave 2.54:1 on the primary fill
   and 2.77:1 on the danger fill.

⚠️ ``test_ux_button_contrast`` asserts the TOKEN pair and was green throughout:
it never looked at the stylesheet that actually ships. This guard measures what
is painted, which is the only thing the operator sees.
"""

from __future__ import annotations

import os
from collections import Counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

AA_NORMAL_TEXT = 4.5
#: Under this, two colours are an anti-aliasing step of one another, not ink on paper.
INK_THRESHOLD = 1.6


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = [c / 255 for c in rgb]
    linear = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _painted_contrast(widget, crop: int = 3) -> tuple[float, str, str]:
    """Paint the widget, then report the contrast between its paper and its ink.

    Two precautions, both of which a first version got wrong:

    - the outer ``crop`` pixels are dropped, because a border is not a label and
      a dark border on a pale fill would otherwise read as perfect legibility;
    - ink is the colour FURTHEST from the paper, not the most frequent one after
      it. Anti-aliasing makes the halo far more common than the glyph core, and
      taking the frequent one scored black-on-white at 2.52:1.

    Returns ``(ratio, ink, paper)``; ratio is 1.0 when nothing on the widget is
    distinct enough from its background to be a glyph.
    """
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    widget.render(painter)
    painter.end()

    counter: Counter = Counter()
    for y in range(crop, image.height() - crop):
        for x in range(crop, image.width() - crop):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() >= 250:
                counter[(pixel.red(), pixel.green(), pixel.blue())] += 1
    if not counter:
        return 1.0, "none", "none"

    paper = counter.most_common(1)[0][0]
    # A glyph core covers several pixels; a lone one is resampling noise.
    floor = max(3, int(0.0005 * sum(counter.values())))
    candidates = [rgb for rgb, n in counter.items() if n >= floor]
    ink = max(candidates, key=lambda rgb: _contrast(rgb, paper)) if candidates else None
    if ink is None or _contrast(ink, paper) < INK_THRESHOLD:
        return 1.0, "none", _hex(paper)
    return _contrast(ink, paper), _hex(ink), _hex(paper)


def test_the_probe_sees_an_invisible_button(qapp):
    """Contrôle négatif : a rigged white-on-white button must be caught."""
    from PyQt6.QtWidgets import QPushButton

    rigged = QPushButton("invisible")
    rigged.setStyleSheet("background-color: #ffffff; color: #ffffff; border: none;")
    rigged.resize(220, 40)
    ratio, _ink, _paper = _painted_contrast(rigged)
    assert ratio < AA_NORMAL_TEXT, "the probe cannot even see a deliberately invisible button"


def test_the_probe_sees_a_legible_button(qapp):
    """Contrôle négatif, other way round: it must not condemn a readable button."""
    from PyQt6.QtWidgets import QPushButton

    fine = QPushButton("readable")
    fine.setStyleSheet("background-color: #ffffff; color: #000000; border: none;")
    fine.resize(220, 40)
    ratio, ink, paper = _painted_contrast(fine)
    assert ratio >= AA_NORMAL_TEXT, f"the probe condemns black on white: {ink} on {paper} = {ratio:.2f}:1"


# =============================================================================
# The shared rules: every primary and danger button of the suite
# =============================================================================


@pytest.fixture
def themed(request, qapp):
    """Build the premium sheet for one mode and hand it back with the mode."""
    from certus.ui.certus_theme import CertusTheme
    from certus.utils.certus_ux import build_premium_overrides

    mode = request.param
    try:
        CertusTheme.configure(mode)
        # Guard against the guard: a mode that did not take would silently make
        # both parametrisations measure the same palette.
        yield mode, build_premium_overrides(mode)
    finally:
        CertusTheme.configure("light")


@pytest.mark.parametrize("themed", ["light", "dark"], indirect=True)
@pytest.mark.parametrize("role", ["PRIMARY_BUTTON", "DANGER_BUTTON"])
def test_an_action_button_label_reaches_aa(themed, role: str):
    from PyQt6.QtWidgets import QPushButton

    from certus.utils.certus_ux import OBJ

    mode, sheet = themed
    button = QPushButton("Scientific Documentation")
    button.setObjectName(getattr(OBJ, role))
    button.setStyleSheet(sheet)
    button.resize(240, 40)

    ratio, ink, paper = _painted_contrast(button)
    assert ratio >= AA_NORMAL_TEXT, (
        f"{role} in {mode}: label painted {ink} on {paper} = {ratio:.2f}:1, below AA ({AA_NORMAL_TEXT}:1)"
    )


# =============================================================================
# The HUB documentation button, in the window that ships it
# =============================================================================


@pytest.fixture
def hub_for_mode(request, qapp, monkeypatch):
    """A HUB built with a faked persisted preference, exactly as it launches.

    ⚠️ The mode is set ONLY through the preference, never by calling
    ``CertusTheme.configure`` first. That is the real path: the window applies
    the preference while it is being built, and pre-configuring the palette
    here would measure a state the application never reaches.

    ⚠️ Function-scoped and rebuilt per mode: a window bakes theme tokens into
    widget-level stylesheets as it is built, so two modes cannot share one.
    """
    from PyQt6.QtCore import Qt

    from certus.core import certus_core
    from certus.ui import certus_ui_utils
    from certus.ui.certus_theme import CertusTheme

    mode = request.param
    monkeypatch.setattr(certus_core, "load_theme_config", lambda: mode)
    monkeypatch.setattr(certus_ui_utils, "load_theme_config", lambda: mode)

    from CERTUS_HUB import CertusHub

    win = CertusHub()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    qapp.processEvents()

    # Guard against the guard: if the preference did not reach the palette,
    # both parametrisations would measure the same theme.
    expected_dark = mode == "dark"
    assert (CertusTheme.SURFACE.lower() != "#ffffff") is expected_dark, (
        f"asked for {mode} but the window came up with SURFACE={CertusTheme.SURFACE}"
    )
    try:
        yield mode, win
    finally:
        win.close()
        CertusTheme.configure("light")


@pytest.mark.parametrize("hub_for_mode", ["light", "dark"], indirect=True)
def test_the_documentation_button_label_is_visible(hub_for_mode):
    """The dossier's oldest open complaint, measured instead of believed."""
    mode, win = hub_for_mode
    button = win.btn_docs
    assert button.text().strip(), "the documentation button has no label to render"

    ratio, ink, paper = _painted_contrast(button)
    assert ratio >= AA_NORMAL_TEXT, (
        f"'Scientific Documentation' in {mode}: label painted {ink} on {paper} = {ratio:.2f}:1 - "
        "the operator cannot read the button"
    )
