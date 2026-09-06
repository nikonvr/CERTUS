"""IL N'Y A QU'UNE ECHELLE TYPOGRAPHIQUE — etape 3.1.

📏 Mesure du 2026-09-06 : **162 declarations `font-size:` en dur** hors des fichiers de
palette, sur **23 valeurs distinctes**, avec **px et pt melanges**.

## 🔑 CE QUE L'ETAPE DEMANDAIT, ET POURQUOI ON NE L'A PAS FAIT LITTERALEMENT

Elle disait « ajouter `FONT_SIZE_XS/SM/BASE/LG/XL/DISPLAY` a `CertusTheme` ».

Or `certus/utils/certus_ux.py` declare **deja** une classe `Typography` portant la meme
echelle, dans la meme unite. Et ses **huit jetons de TAILLE ne servaient nulle part** en
production : trois usages seulement, tous pour `FAMILY_UI` / `FAMILY_MONO`, plus un test qui
verifie que les tailles croissent.

`CertusTheme.FONT_SIZE_BASE = 10` et `Typography.BODY = 10` etaient donc **le meme fait ecrit
deux fois**. Declarer une seconde echelle en aurait fait trois. Les noms demandes existent,
mais comme **vues** sur l'echelle en place.

## Ce qui a ete route, et ce qui ne l'a PAS ete

Seules les declarations **en pt tombant exactement sur un pas** ont ete routees — cinq, dans
`certus_ux.py`. Preuve que c'est un refactor pur : les feuilles de style sortent
**identiques au caractere**, empreinte SHA-256 comparee avant et apres.

🔴 **Les 157 restantes ne sont pas un oubli.** La majorite est en **px** — `11px` a lui seul
revient **56 fois**, c'est la taille la plus repandue de toute la suite. Convertir px en pt
change le rendu des onze fenetres : a 96 dpi, 10 pt valent 13,3 px, donc un libelle a 11 px
est plus **petit** que la base tout en paraissant plus grand dans la source. **Choisir
l'unite se fait les yeux sur un ecran**, pas dans une passe de nuit.

Les valeurs pt hors echelle — 9,5 · 11 · 13 · 15 — sont laissees telles quelles plutot que
poussees sur un pas voisin : les arrondir serait un changement de rendu deguise en refactor.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

#: `FONT_SIZE_*` du theme -> jeton de `Typography` dont il est la vue.
CORRESPONDANCE = {
    "FONT_SIZE_XS": "CAPTION",
    "FONT_SIZE_SM": "BODY_SM",
    "FONT_SIZE_BASE": "BODY",
    "FONT_SIZE_LG": "H3",
    "FONT_SIZE_XL": "H2",
    "FONT_SIZE_DISPLAY": "DISPLAY",
}


class TestUneSeuleEchelle:
    @pytest.mark.parametrize("jeton,source", sorted(CORRESPONDANCE.items()))
    def test_le_theme_est_une_VUE_sur_l_echelle_existante(self, jeton: str, source: str) -> None:
        from certus.ui.certus_theme import CertusTheme
        from certus.utils.certus_ux import Typography

        attendu = getattr(Typography, source)
        obtenu = getattr(CertusTheme, jeton)
        assert obtenu == attendu, (
            f"{jeton} vaut {obtenu} alors que Typography.{source} vaut {attendu}. "
            "Les deux echelles ont diverge — c'est exactement ce que l'aliasing empeche."
        )

    def test_l_echelle_est_strictement_croissante(self) -> None:
        from certus.ui.certus_theme import CertusTheme

        tailles = [getattr(CertusTheme, n) for n in
                   ("FONT_SIZE_XS", "FONT_SIZE_SM", "FONT_SIZE_BASE",
                    "FONT_SIZE_LG", "FONT_SIZE_XL", "FONT_SIZE_DISPLAY")]
        assert tailles == sorted(set(tailles)), f"echelle non monotone : {tailles}"


class TestLeRefactorNAPasChangeLeRendu:
    """🔑 Un refactor pur doit rendre la MEME feuille. Verifie au caractere pres."""

    def test_les_tailles_routees_sortent_a_leur_valeur_d_origine(self, qapp) -> None:
        import re

        from certus.ui.certus_theme import CertusTheme
        from certus.utils.certus_ux import build_premium_overrides

        CertusTheme.configure("light")
        qss = build_premium_overrides()
        tailles = sorted({t for t, _ in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)(pt)", qss)},
                         key=float)
        # 📏 Valeurs presentes avant l'etape : 8, 9, 9.5, 10, 11. Le routage n'a change
        # AUCUNE d'entre elles ; il a seulement remplace des litteraux par des jetons.
        assert tailles == ["8", "9", "9.5", "10", "11"], (
            f"les tailles en pt de la feuille ont change : {tailles}. Le routage devait "
            "etre un refactor pur."
        )

    def test_aucun_jeton_non_resolu_ne_fuit_dans_la_feuille(self, qapp) -> None:
        """Un `{font_sm}` litteral signifierait une f-string cassee — QSS l'ignorerait."""
        from certus.utils.certus_ux import build_premium_overrides

        qss = build_premium_overrides()
        fuites = [x for x in ("{font_xs}", "{font_sm}", "{font_base}") if x in qss]
        assert not fuites, f"jetons non substitues dans la feuille : {fuites}"


class TestLEchelleNEstPasUnTROISIEMEDoublon:
    """Controle negatif : si `Typography` disparaissait, l'aliasing masquerait le trou."""

    def test_la_source_existe_toujours(self) -> None:
        from certus.utils.certus_ux import Typography

        for source in CORRESPONDANCE.values():
            assert hasattr(Typography, source), (
                f"Typography.{source} a disparu. Le theme y fait reference : si l'echelle "
                "demenage, deplace la reference plutot que de recopier les valeurs."
            )
