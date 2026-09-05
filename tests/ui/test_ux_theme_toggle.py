"""The theme toggle must show which theme it offers.

Measured 2026-09-04, certus/ui/certus_ui_widgets_utils.py:175:

    self.setText("" if mode == "light" else "")

Both branches are the empty string, so the 32x32 round button rendered as an
empty circle in all eleven windows - the only control in the suite whose entire
purpose is invisible.

The glyphs must stay inside the Basic Multilingual Plane: an emoji outside it
renders as a tofu box depending on the installed font, which is the same class
of defect the audit harness had to fix for its width measurements.
"""

from __future__ import annotations

from pathlib import Path


def test_theme_toggle_source_has_no_degenerate_ternary() -> None:
    src = Path("certus/ui/certus_ui_widgets_utils.py").read_text(encoding="utf-8")
    assert 'setText("" if mode == "light" else "")' not in src


def test_theme_toggle_shows_a_glyph_in_both_modes(qapp, monkeypatch) -> None:
    """Whatever the persisted preference, the button must carry a visible glyph."""
    import importlib

    mod = importlib.import_module("certus.ui.certus_ui_widgets_utils")

    seen = {}
    for mode in ("light", "dark"):
        monkeypatch.setattr(mod, "load_theme_config", lambda m=mode: m)
        toggle = mod.CertusThemeToggle()
        seen[mode] = toggle.text()
        toggle.deleteLater()

    assert seen["light"].strip(), "the toggle is blank in light mode"
    assert seen["dark"].strip(), "the toggle is blank in dark mode"
    assert seen["light"] != seen["dark"], "the toggle looks identical in both modes"

    for mode, text in seen.items():
        for ch in text.strip():
            assert ord(ch) <= 0xFFFF, f"{mode}: U+{ord(ch):04X} is outside the BMP and may render as tofu"
