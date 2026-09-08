"""The COLOUR TOKENS of a filled button must be a legible pair (plan UX, 4.1).

🔴 READ THIS BEFORE TRUSTING THIS FILE. It asserts a property of the TOKENS,
and nothing obliges the shipped stylesheet to use them. It was green from the
day it was written while `build_premium_overrides` still hardcoded a literal
white on both filled buttons - the very defect the paragraph below describes.
Measured 2026-09-08: 2.54:1 on the primary fill and 2.77:1 on the danger fill,
in dark mode, painted on screen, while every assertion here passed.

What actually catches that is `test_ux_button_label_is_painted`, which renders
the button and reads the pixels back. **This guard is necessary and not
sufficient**: keep both, and never take a green here for a legible button.

The stylesheet was routed to the tokens on 2026-09-08, so the figures below are
now what ships. They are kept because they say WHY the pair must be a pair.

Measured 2026-09-04, WCAG 2.1 relative luminance:

    light   #ffffff on DANGER  #dc2626  =  4.83:1   passes AA
    dark    #ffffff on DANGER  #f87171  =  2.77:1   FAILS AA (needs 4.5:1)
    dark    PRIMARY_TEXT on PRIMARY     =  7.02:1   passes (already tokenised)

A hardcoded colour cannot follow the theme; that is the whole reason
CertusTheme exists. The ratio is computed here rather than asserted from a
table, so the test still means something after a palette change.

⚠️ The 2.77:1 line above was, until 2026-09-08, a description of the LIVE
state written inside a guard that could not see it. That is the lesson, and it
became rule R13 of the plan: measure what is RENDERED, not what is declared.
"""

from __future__ import annotations

import pytest

AA_NORMAL_TEXT = 4.5


def _relative_luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(fg: str, bg: str) -> float:
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_helper_agrees_with_a_known_pair() -> None:
    """A ratio helper nobody checked would silently validate anything."""
    assert _contrast("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    assert _contrast("#ffffff", "#0f62fe") == pytest.approx(5.00, abs=0.05)


#: (fill token, label token). DANGER's label is DANGER_LABEL, not DANGER_TEXT:
#: the latter is the text of a light DANGER_BG badge and means something else.
BUTTON_ROLES = [("PRIMARY", "PRIMARY_TEXT"), ("DANGER", "DANGER_LABEL")]


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("fill,label", BUTTON_ROLES)
def test_button_label_meets_aa_in_both_modes(mode: str, fill: str, label: str) -> None:
    """Every action button must reach 4.5:1 in the theme the operator chose."""
    from certus.ui.certus_theme import CertusTheme

    try:
        CertusTheme.configure(mode)
        bg = getattr(CertusTheme, fill)
        fg = getattr(CertusTheme, label)
        ratio = _contrast(fg, bg)
        assert ratio >= AA_NORMAL_TEXT, (
            f"{mode}: {label} {fg} on {fill} {bg} = {ratio:.2f}:1, below AA {AA_NORMAL_TEXT}:1"
        )
    finally:
        CertusTheme.configure("light")


@pytest.mark.parametrize("role", ["PRIMARY", "DANGER"])
def test_button_stylesheet_carries_no_hardcoded_colour(role: str) -> None:
    """A literal hex in the stylesheet cannot follow CertusTheme.configure()."""
    from certus.ui.certus_theme import CertusTheme

    builder = getattr(CertusTheme, f"get_{role.lower()}_button_stylesheet")
    try:
        CertusTheme.configure("dark")
        css = builder()
        assert "#ffffff" not in css.lower(), (
            f"{role} button hardcodes white; in dark mode that is unreadable on the "
            f"themed background"
        )
    finally:
        CertusTheme.configure("light")
