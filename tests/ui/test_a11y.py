from __future__ import annotations

from certus.ui.certus_a11y import contrast_ratio
from certus.ui.certus_ui import CertusBaseApp, CertusTheme


import pytest

SEMANTIC_TOKENS = (
    "SUCCESS_BG",
    "SUCCESS_TEXT",
    "WARNING_BG",
    "WARNING_TEXT",
    "DANGER_BG",
    "DANGER_TEXT",
    "INFO_BG",
    "INFO_TEXT",
)


def _snapshot() -> dict[str, str]:
    return {k: getattr(CertusTheme, k) for k in SEMANTIC_TOKENS}


@pytest.mark.xfail(
    strict=True,
    reason="8 jetons sémantiques identiques en clair et en sombre — sera levé à l'étape 3.4",
)
def test_dark_mode_actually_changes_the_semantic_tokens() -> None:
    """Guards the reason the previous test proved nothing.

    Measured 2026-09-04: SUCCESS_BG/TEXT, WARNING_BG/TEXT, DANGER_BG/TEXT and
    INFO_BG/TEXT were identical in both modes, so 4 of the 5 pairs the contrast
    test iterated over in 'dark' were in fact re-testing the light values.
    """
    CertusTheme.configure("light")
    light = _snapshot()
    CertusTheme.configure("dark")
    dark = _snapshot()
    CertusTheme.configure("light")
    unchanged = {k for k in light if light[k] == dark[k]}
    assert not unchanged, f"jetons identiques en clair et en sombre : {sorted(unchanged)}"


def test_wcag_aa_on_every_text_pair_in_both_modes() -> None:
    for mode in ("light", "dark"):
        CertusTheme.configure(mode)
        pairs = [
            (CertusTheme.TEXT_MAIN, CertusTheme.SURFACE),
            (CertusTheme.TEXT_MAIN, CertusTheme.BACKGROUND),
            (CertusTheme.TEXT_SUB, CertusTheme.SURFACE),
            (CertusTheme.TEXT_SUB, CertusTheme.BACKGROUND),
            (CertusTheme.SUCCESS_TEXT, CertusTheme.SUCCESS_BG),
            (CertusTheme.WARNING_TEXT, CertusTheme.WARNING_BG),
            (CertusTheme.DANGER_TEXT, CertusTheme.DANGER_BG),
            (CertusTheme.INFO_TEXT, CertusTheme.INFO_BG),
            (CertusTheme.PRIMARY_TEXT, CertusTheme.PRIMARY),
        ]
        for fg, bg in pairs:
            cr = contrast_ratio(fg, bg)
            assert cr >= 4.5, f"Mode {mode}: {fg} sur {bg} a un ratio {cr:.2f} < 4.5"
    CertusTheme.configure("light")


def test_wcag_non_text_contrast_on_borders_in_both_modes() -> None:
    """WCAG 1.4.11 sur la bordure qui PORTE l'affordance — étape 3.3, faite le 2026-09-06.

    ⚠️ **Ce test était un `xfail(strict=True)` dont la raison annonçait « sera levé à
    l'étape 3.3 » en montant `BORDER` à 3:1. L'étape a été faite, et elle a conclu
    l'inverse.**

    `BORDER` a 122 usages, et il sert de **fond** — pas de bordure — aux boutons
    DÉSACTIVÉS, aux séparateurs de menu et aux poignées d'ascenseur. Le monter aurait
    rendu un contrôle désactivé plus présent qu'un contrôle actif, et aurait sur-appliqué
    la règle : **WCAG exempte explicitement les éléments désactivés**.

    C'est donc `BORDER_STRONG` qui porte le seuil, et `BORDER` reste volontairement en
    dessous. Le contrôle négatif correspondant — *« `BORDER` est-il TOUJOURS sous 3:1 ? »* —
    vit dans `tests/ui/test_ux_border_contrast.py`, avec la vérification sur les **deux**
    fonds : `#7792b1` avait été écarté pour 3,22 sur SURFACE mais **2,86 sur BACKGROUND**.
    """
    for mode in ("light", "dark"):
        CertusTheme.configure(mode)
        cr = contrast_ratio(CertusTheme.BORDER_STRONG, CertusTheme.SURFACE)
        assert cr >= 3.0, (
            f"Mode {mode}: BORDER_STRONG ({CertusTheme.BORDER_STRONG}) sur SURFACE "
            f"({CertusTheme.SURFACE}) a un ratio {cr:.2f} < 3.0"
        )
    CertusTheme.configure("light")


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
