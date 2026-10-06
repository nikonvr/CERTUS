"""The step tracker and the rich tooltip take their colours from the palette, as tokens that follow the theme.

From the branch claude/charming-wright-43077a (2026-09-07), ported onto today's code (decided by the owner on
2026-10-06: evaluate, then integrate). The badge part of that branch was already done another way (`_VARIANT_TOKENS`).
What remained: the PENDING step and the tooltip body asked for a `MID` / `TEXT_MUTED` token the palette does not have,
and fell back on a hexadecimal, light in both themes; and `step_color` returned `str()` of its token, which strips the
name a theme toggle needs to repaint the step titles.
"""

from __future__ import annotations

from certus.ui.certus_ui import CertusTheme as T


def test_a_pending_step_has_the_secondary_text_colour_of_the_palette():
    from certus.utils.certus_progress_tracker import StepState, step_color

    assert step_color(StepState.PENDING) == T.TEXT_SUB


def test_a_step_colour_keeps_its_token_name_in_a_style_sheet():
    from certus.utils.certus_progress_tracker import StepState, step_color

    assert "/*T:PRIMARY*/" in f"color: {step_color(StepState.RUNNING)}"


def test_the_tooltip_body_takes_the_secondary_text_token(qapp):
    from certus.ui import certus_tooltips

    popup = certus_tooltips._build_popup_class()()
    try:
        assert "/*T:TEXT_SUB*/" in popup.styleSheet()
    finally:
        popup.deleteLater()
