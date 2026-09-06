"""LA LIMITE D'UN CONTROLE DOIT SE VOIR — etape 3.3.

📏 Mesure du 2026-09-06, avant correctif : `BORDER` valait **1,35:1** sur `SURFACE` en mode
clair et **1,48:1** en sombre, la ou WCAG 1.4.11 (*Non-text Contrast*) exige **3,0** pour la
limite d'un composant d'interface. Un champ de saisie n'etait delimite par rien de
perceptible.

## 🔴 POURQUOI UN SECOND JETON, ET PAS `BORDER` RELEVE

C'est le point de cette etape, et il ne se voit pas dans le chiffre de depart.

`BORDER` a **122 usages**, et il ne sert pas qu'a border : il est le **FOND** des boutons
DESACTIVES (`certus_theme.py`, `certus_ux.py`), des separateurs de menu et des poignees
d'ascenseur. Le relever d'un bloc aurait donc rendu un controle **desactive** plus sombre,
donc plus present, qu'un controle **actif** -- une regression d'usage deguisee en gain
d'accessibilite.

Et c'aurait sur-applique la regle : **WCAG exempte explicitement les elements desactives** de
toute exigence de contraste. Le correctif juste n'est pas « monter le jeton », c'est
« separer le jeton qui porte une affordance de celui qui decore ».

## Ce que ce fichier verrouille

1. `BORDER_STRONG` tient 3:1 **sur les deux fonds** -- `SURFACE` et `BACKGROUND` -- parce
   qu'un champ peut se poser sur l'un comme sur l'autre. Verifier un seul fond aurait laisse
   passer `#7792b1`, qui donne 3,22:1 sur SURFACE et **2,86:1** sur BACKGROUND.
2. Les controles dont le contour est l'affordance l'utilisent bien.
3. 🔑 Les usages DECORATIFS et le fond des controles desactives **restent sur `BORDER`**.
   Sans ce troisieme point, la prochaine passe « harmonisera » les deux jetons et refera
   exactement le defaut que l'etape a evite.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PyQt6")

SEUIL = 3.0
COMMENTAIRE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _regle(qss: str, selecteur: str) -> str:
    qss = COMMENTAIRE.sub("", qss)
    trouve = re.search(
        r"([^{}]*" + re.escape(selecteur) + r"[^{}]*)\{([^}]*)\}", qss, re.MULTILINE
    )
    assert trouve, f"aucune regle ne porte {selecteur!r}"
    return trouve.group(2)


class TestLeJetonTientLeSeuil:
    @pytest.mark.parametrize("mode", ["light", "dark"])
    @pytest.mark.parametrize("fond", ["SURFACE", "BACKGROUND"])
    def test_border_strong_atteint_3_pour_1_sur_les_deux_fonds(self, mode: str, fond: str) -> None:
        """Les DEUX fonds : un champ se pose sur une carte comme sur la fenetre."""
        from certus.ui.certus_a11y import contrast_ratio
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        ratio = contrast_ratio(CertusTheme.BORDER_STRONG, getattr(CertusTheme, fond))
        assert ratio >= SEUIL, (
            f"{mode}/{fond} : BORDER_STRONG={CertusTheme.BORDER_STRONG} a {ratio:.2f}:1"
        )

    @pytest.mark.parametrize("mode", ["light", "dark"])
    def test_le_jeton_doux_est_TOUJOURS_sous_le_seuil(self, mode: str) -> None:
        """Controle negatif. Si `BORDER` passait 3:1, les deux jetons auraient fusionne
        et le fond des boutons desactives serait devenu aussi lourd qu'un controle actif.
        C'est precisement ce que l'etape 3.3 a refuse de faire.
        """
        from certus.ui.certus_a11y import contrast_ratio
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure(mode)
        ratio = contrast_ratio(CertusTheme.BORDER, CertusTheme.SURFACE)
        assert ratio < SEUIL, (
            f"{mode} : BORDER est monte a {ratio:.2f}:1. S'il a ete releve volontairement, "
            "verifie d'abord ce que deviennent les FONDS qui l'utilisent -- boutons "
            "desactives, separateurs, poignees d'ascenseur."
        )

    def test_les_deux_jetons_sont_distincts(self) -> None:
        from certus.ui.certus_theme import CertusTheme

        for mode in ("light", "dark"):
            CertusTheme.configure(mode)
            assert CertusTheme.BORDER != CertusTheme.BORDER_STRONG, mode


class TestLesControlesUtilisentLeBonJeton:
    def test_les_champs_de_saisie_portent_la_bordure_forte(self, qapp) -> None:
        from certus.ui.certus_theme import CertusTheme

        CertusTheme.configure("light")
        corps = _regle(CertusTheme.get_standard_stylesheet(), "QLineEdit, QComboBox")
        assert CertusTheme.BORDER_STRONG in corps, corps

    def test_le_bouton_par_defaut_porte_la_bordure_forte(self, qapp) -> None:
        from certus.ui.certus_theme import CertusTheme
        from certus.utils.certus_ux import build_premium_overrides

        CertusTheme.configure("light")
        corps = _regle(build_premium_overrides(), "QPushButton ")
        assert CertusTheme.BORDER_STRONG in corps, corps


class TestLeDESACTIVERESTEENRETRAIT:
    """🔑 Le garde-fou qui compte. Un controle inactif ne doit pas gagner en presence."""

    def test_le_fond_des_boutons_desactives_reste_sur_le_jeton_doux(self, qapp) -> None:
        from certus.ui.certus_theme import CertusTheme
        from certus.utils.certus_ux import build_premium_overrides

        CertusTheme.configure("light")
        qss = COMMENTAIRE.sub("", build_premium_overrides())
        desactives = re.findall(r"QPushButton[^{}]*:disabled[^{}]*\{([^}]*)\}", qss)
        assert desactives, "aucune regle :disabled sur un bouton"
        for corps in desactives:
            fond = re.search(r"background-color\s*:\s*([^;]+);", corps)
            if fond:
                assert CertusTheme.BORDER_STRONG not in fond.group(1), (
                    "un bouton desactive a pris la bordure FORTE comme fond : il paraitra "
                    "plus present qu'un bouton actif. WCAG exempte les elements desactives."
                )
