from __future__ import annotations

from certus_a11y import contrast_ratio
from certus_ui import CertusBaseApp, CertusTheme


def _semantic_pairs() -> list[tuple[str, str]]:
    return [
        (CertusTheme.TEXT_MAIN, CertusTheme.SURFACE),
        (CertusTheme.SUCCESS_TEXT, CertusTheme.SUCCESS_BG),
        (CertusTheme.WARNING_TEXT, CertusTheme.WARNING_BG),
        (CertusTheme.DANGER_TEXT, CertusTheme.DANGER_BG),
        (CertusTheme.INFO_TEXT, CertusTheme.INFO_BG),
    ]


def test_w45_wcag_aa_contrast_pairs_light_and_dark() -> None:
    for mode in ("light", "dark"):
        CertusTheme.configure(mode)
        for fg, bg in _semantic_pairs():
            assert contrast_ratio(fg, bg) >= 4.5


def test_w45_shortcut_catalog_contains_core_entries() -> None:
    class _Stub:
        def _toggle_theme(self):
            return None

        def open_shortcuts_overlay(self):
            return None

        def close(self):
            return None

    cmds = CertusBaseApp._default_commands(_Stub())
    by_id = {c.id: c for c in cmds}

    assert "view.toggle_theme" in by_id
    assert "help.shortcuts" in by_id
    assert "app.quit" in by_id
    assert by_id["help.shortcuts"].shortcut == "F1"
    assert by_id["app.quit"].shortcut == "Ctrl+W"
