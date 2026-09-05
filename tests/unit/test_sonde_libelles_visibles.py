"""LA SONDE DE L'ETAPE 3.0 MORD-ELLE ENCORE ?

POURQUOI CE FICHIER EXISTE, ET IL A UNE CAUSE PRECISE.

La premiere version de `scripts/sonde_libelles_visibles.py` etait FAUSSE, et d'une facon
qui aurait produit des corrections erronees plutot qu'une absence de resultat. Elle cherchait
le double espace d'un mnemonique Qt **dans la source**, alors qu'il n'existe qu'**au rendu** :

    source   "Substrate (n) & layer thickness"     <- espaces SIMPLES
    ecran    "Substrate (n)  layer thickness"      <- Qt a retire le '&'

Elle classait donc ces chaines en « separateur efface » et aurait prescrit de retablir un
tiret la ou il faut DOUBLER l'esperluette. Le controle negatif interne de la sonde l'a refute
au premier lancement -- exit 2 -- et c'est tout ce qui a empeche une mesure fausse de passer
pour une mesure.

CE QUE CE FICHIER NE FAIT PAS. Il n'assere aucun COMPTE. Les comptes se periment a chaque
edition de libelle, et l'etape 3.0 existe justement pour les ramener a zero. Asserer
« 20 separateurs » ici obligerait a modifier ce test a chaque correction, ce qui est le
contraire d'un garde-fou. Les tests de comptage decrits par l'etape 3.0 seront ecrits QUAND
elle sera faite -- aujourd'hui ils echoueraient, et c'est leur preuve d'utilite.

Ce fichier verrouille donc la LOGIQUE DE DETECTION, qui elle ne doit jamais changer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.sonde_libelles_visibles import (  # noqa: E402
    _controle_negatif,
    _esperluette_seule,
    _est_emoji,
    _mutile,
)


class TestLeSeparateurEfface:
    """Un double espace ENTRE deux caracteres de texte, dans la source."""

    @pytest.mark.parametrize(
        "texte",
        [
            "Optical Profiles  n(lambda) and ln k(lambda)",
            "1  Recalculate RMSE(d)",
            "example/sapphire fresnel.xlsx  no k column",
        ],
    )
    def test_il_voit_un_trou(self, texte: str) -> None:
        assert _mutile(texte)

    @pytest.mark.parametrize(
        "texte",
        [
            "Run Optimization",
            "  indente en debut de chaine",
            "fin de chaine  ",
        ],
    )
    def test_il_ne_voit_pas_de_trou_ou_il_n_y_en_a_pas(self, texte: str) -> None:
        """Une indentation ou une espace terminale n'est pas un separateur retire."""
        assert not _mutile(texte)


class TestLEsperluetteMangeeParQt:
    """🔑 Le cas contre-intuitif : la source est INTACTE, c'est le rendu qui troue."""

    def test_elle_est_vue_malgre_des_espaces_simples(self) -> None:
        texte = "Substrate (n) & layer thickness"
        assert _esperluette_seule(texte)
        assert not _mutile(texte), (
            "regression: la sonde cherche a nouveau le trou dans la SOURCE. "
            "Il n'y est pas -- Qt le fabrique en retirant le '&'."
        )

    def test_une_esperluette_doublee_est_deja_correcte(self) -> None:
        """`&&` est la forme corrigee : Qt affiche un '&' et ne cree aucun raccourci."""
        assert not _esperluette_seule("Substrate (n) && layer thickness")

    @pytest.mark.parametrize(
        "texte",
        [
            "<span style='color:#ff8c00;'>&#9646;</span> = Smart Delta",
            "the <b>n &amp; log10 k</b> tab",
        ],
    )
    def test_une_entite_html_n_est_pas_un_mnemonique(self, texte: str) -> None:
        """Qt rend l'entite telle quelle. La compter serait un faux positif."""
        assert not _esperluette_seule(texte)

    def test_les_deux_defauts_peuvent_coexister(self) -> None:
        """Ils ne s'excluent pas -- une meme ligne peut demander DEUX correctifs.

        Mesure : `certus_index_spline_rendering.py` porte
        '2  Substrate n(lambda) & layer thickness d (nm)', qui a le trou APRES le '2'
        et l'esperluette au milieu.
        """
        texte = "2  Substrate n(lambda) & layer thickness d (nm)"
        assert _mutile(texte)
        assert _esperluette_seule(texte)


class TestLEmoji:
    """Perimetre de l'etape 3.5. Teste caractere par caractere, jamais par un seuil."""

    @pytest.mark.parametrize("texte", ["▶  Run", "\U0001f52c Stack information"])
    def test_il_voit_un_symbole(self, texte: str) -> None:
        assert _est_emoji(texte)

    def test_il_ne_prend_pas_une_lettre_grecque_pour_un_emoji(self) -> None:
        """λ est une LETTRE -- c'est la cible de 3.0, surtout pas une icone a retirer."""
        assert not _est_emoji("Center λ (nm)")

    def test_il_ne_prend_pas_un_tiret_cadratin_pour_un_emoji(self) -> None:
        """Le separateur que 3.0 va REMETTRE ne doit pas etre signale par 3.5."""
        assert not _est_emoji("Materials — Parameters")


class TestLeControleNegatifInterne:
    """La sonde porte son propre controle. S'il se tait, la sonde ne prouve rien.

    C'est la regle du §1 de `CLAUDE.md` : *un harnais dont tout passe toujours ne prouve
    rien*. La sonde sort en 2 -- ni 0 ni 1 -- quand ce controle echoue, precisement pour
    qu'on ne prenne pas son silence pour un resultat.
    """

    def test_les_trois_verifications_mordent(self) -> None:
        voit_trou, voit_lambda, ne_confond_pas = _controle_negatif()
        assert voit_trou, "la sonde ne repere plus un double espace plante"
        assert voit_lambda, "la sonde ne repere plus un `lambda` plante"
        assert ne_confond_pas, (
            "la sonde confond a nouveau une esperluette avec un separateur efface -- "
            "c'est exactement le defaut de sa premiere version"
        )
