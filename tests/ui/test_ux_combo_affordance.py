"""UN SELECTEUR DOIT SE VOIR COMME UN SELECTEUR — etape 3.8.

Le theme portait `QComboBox::down-arrow` avec une image vide : la fleche etait EFFACEE sans
que rien la remplace. Un `QComboBox` devenait alors visuellement identique a un `QLineEdit`,
et plus rien n'indiquait qu'il se deroule. Mesure du 2026-09-04 : 6 combos dans DESIGN seul.

## Pourquoi la fleche NATIVE, et pas le `chevron-down` du depot

`certus/ui/certus_icons.py` porte bien un `chevron-down`. Mais QSS veut un **chemin
d'image**, et ce meme module garde `is_svg_icon_rendering_disabled()` : la pile QtSvg est
connue instable ici. Faire dependre l'affordance la plus elementaire d'un sous-systeme que le
projet desactive parfois lui-meme, ce serait echanger un defaut CERTAIN contre un defaut
INTERMITTENT -- lequel est pire, parce qu'il ne se reproduit pas quand on le cherche.

## 🔑 CE TEST DEPOUILLE LES COMMENTAIRES, ET CE N'EST PAS UNE PRECAUTION THEORIQUE

En ecrivant le correctif, le commentaire qui EXPLIQUAIT la regle supprimee la contenait en
QSS litteral. Comme il vit dans une f-string, il etait recrache dans la feuille, et la
verification a cru que la regle etait toujours la. **Un controle qui lit une feuille de style
sans retirer ses commentaires lit aussi ce qu'on raconte a leur sujet.**
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PyQt6")

#: Qt parse les commentaires `/* ... */` et les ignore. Un controle doit faire pareil.
COMMENTAIRE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _qss_sans_commentaires() -> str:
    from certus.ui.certus_theme import CertusTheme

    return COMMENTAIRE.sub("", CertusTheme.get_standard_stylesheet())


class TestLaFlecheNEstPlusEffacee:
    def test_aucune_regle_ne_vide_l_image_de_la_fleche(self, qapp) -> None:
        qss = _qss_sans_commentaires()
        fleche = re.search(r"QComboBox::down-arrow[^{}]*\{([^}]*)\}", qss)
        if fleche is None:
            return  # aucune regle : Qt dessine sa fleche native, c'est l'etat voulu
        assert "image" not in fleche.group(1), (
            "QComboBox::down-arrow force a nouveau son image. Si c'est pour en fournir une "
            "vraie, tres bien -- mais verifie que le rendu SVG n'est pas desactive "
            "(is_svg_icon_rendering_disabled), sinon la fleche disparait par intermittence."
        )

    def test_la_zone_de_deroulement_garde_sa_place(self, qapp) -> None:
        """La fleche native a besoin de la largeur reservee par `drop-down`."""
        qss = _qss_sans_commentaires()
        zone = re.search(r"QComboBox::drop-down[^{}]*\{([^}]*)\}", qss)
        assert zone, "la zone de deroulement a disparu : la fleche native n'a plus de place"
        largeur = re.search(r"width\s*:\s*(\d+)px", zone.group(1))
        assert largeur and int(largeur.group(1)) >= 16, (
            f"zone de deroulement trop etroite : {zone.group(1)!r}"
        )


class TestLeControleLitBienLaFeuilleEtPasSesCommentaires:
    """Le defaut qui a trompe l'auteur du correctif. Il ne doit pas revenir.

    Sans ce controle, un commentaire citant la regle suffirait a faire echouer -- ou pire, a
    faire passer -- le test ci-dessus pour de mauvaises raisons.
    """

    def test_un_commentaire_qui_cite_la_regle_est_ignore(self) -> None:
        feuille = (
            "/* on avait QComboBox::down-arrow { image: none; } et c'etait un defaut */\n"
            "QComboBox::drop-down { border: none; width: 22px; }\n"
        )
        propre = COMMENTAIRE.sub("", feuille)
        assert "image: none" not in propre
        assert "drop-down" in propre

    def test_il_verrait_la_vraie_regle_si_elle_revenait(self) -> None:
        feuille = "QComboBox::down-arrow { image: none; }\n"
        propre = COMMENTAIRE.sub("", feuille)
        fleche = re.search(r"QComboBox::down-arrow[^{}]*\{([^}]*)\}", propre)
        assert fleche is not None and "image" in fleche.group(1), (
            "le controle ne reconnait plus la regle qu'il existe pour interdire"
        )
