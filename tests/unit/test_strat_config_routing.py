"""LE JSON ATTEINT-IL LE CALCUL ? -- le controle qui manquait, et qui a coute cher.

📏 Mesure du 2026-08-20 : on charge un JSON portant onze leviers de recherche, on lit
`collect_params`, et **DIX ressortent a `None`**. Ils n'existaient que par surcharge de sonde,
donc tout le savoir des campagnes etait inaccessible depuis l'application elle-meme.

Le cas qui l'a revele : `rate_tail_sweep` est la seule voie connue pour rendre `r75x2`
deposable a 2 nm -- et la production ne pouvait pas l'armer. Et `robustness_seed` valait
TOUJOURS 42, quoi que porte la configuration, parce que `_get_float_safe` interroge un widget
qui n'existe pas.

🔴 CES TESTS DOIVENT ECHOUER SUR LE CODE D'AVANT. C'est le controle 2 du §12 de `CLAUDE.md` --
un test qui passe des deux cotes ne prouve rien. Sur le code d'avant :
  - les deux aides `_config_list_int` / `_config_list_of_list_int` n'existent pas -> ImportError
  - les huit cles sont absentes du dictionnaire de `collect_params` -> le test de routage echoue
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# 🔴 IMPORT DIFFERE, ET C'EST DELIBERE. Importe en tete, `_config_list_int` faisait echouer
# la COLLECTE sur le code d'avant (ImportError), ce qui masquait les tests de routage --
# les plus importants du fichier. Ils doivent echouer parce que les CLES SONT ABSENTES,
# pas parce qu'une aide n'existe pas encore. Un test qui echoue pour la mauvaise raison ne
# prouve pas ce qu'il annonce.
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "certus" / "ui" / "certus_strat_ui_state.py"

#: Les leviers dont la mesure du 2026-08-20 a montre qu'ils n'atteignaient pas le calcul.
#: 🔒 Chacun doit valoir sa valeur INACTIVE en l'absence de cle JSON -- regle d'or du §9.
LEVIERS_DE_RECHERCHE = (
    "rate_tail_sweep",
    "rate_layer_sets",
    "rate_by_swing",
    "rate_tail_keep_optical",
    "require_turning_point",
    "optical_prefix_sweep",
    "elite_min_improvement",
    "robustness_seed",
    "phase_a_seed",
)


def _cles_de_collect_params() -> set[str]:
    """Les cles litterales du dictionnaire construit par `collect_params`.

    Lecture par AST plutot que par execution : `collect_params` a besoin d'une application
    Qt vivante, et ce controle doit rester utilisable sans afficheur.
    """
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "collect_params":
            return {
                cle.value
                for sous in ast.walk(noeud)
                if isinstance(sous, ast.Dict)
                for cle in sous.keys
                if isinstance(cle, ast.Constant) and isinstance(cle.value, str)
            }
    raise AssertionError("collect_params introuvable dans certus_strat_ui_state.py")


@pytest.mark.parametrize("cle", LEVIERS_DE_RECHERCHE)
def test_le_levier_est_route_depuis_le_json(cle: str) -> None:
    """Chaque levier de recherche doit apparaitre dans le dictionnaire de `collect_params`.

    🔴 ECHOUE SUR LE CODE D'AVANT : les huit premiers en etaient absents, et les deux graines
    y etaient lues par `_get_float_safe`, qui interroge un widget inexistant et rend donc
    toujours son defaut.
    """
    assert cle in _cles_de_collect_params(), (
        f"`{cle}` n'est pas construit par collect_params : une configuration qui le porte "
        f"sera SILENCIEUSEMENT ignoree, comme les dix cles mesurees le 2026-08-20."
    )


def test_la_graine_se_replie_sur_la_configuration_chargee() -> None:
    """La graine doit etre lue dans `_loaded_config`, pas seulement dans un widget absent.

    🔴 ECHOUE SUR LE CODE D'AVANT, qui ecrivait
        `int(self._get_float_safe("robustness_seed", 42))`
    sans repli. Consequence mesuree : la meilleure configuration connue de `r75x2`
    (SEEL 0,5692, graine 77) etait structurellement hors de portee de la production.
    """
    src = SOURCE.read_text(encoding="utf-8")
    i = src.find('"robustness_seed":')
    assert i > 0, "la cle robustness_seed a disparu de collect_params"
    bloc = src[i:i + 400]
    assert "_loaded_config" in bloc, (
        "robustness_seed ne se replie pas sur la configuration chargee : "
        "aucun widget ne porte ce nom, donc la valeur du JSON est ignoree."
    )


class TestConfigListInt:
    """`_config_list_int` -- absente du code d'avant, donc l'import seul suffit a echouer."""

    @staticmethod
    def _f():
        from certus.ui.certus_strat_ui_state import _config_list_int
        return _config_list_int

    def test_liste_reelle(self) -> None:
        assert self._f()({"k": [46, 52, 58]}, "k") == [46, 52, 58]

    def test_forme_chaine_d_un_editeur_json(self) -> None:
        assert self._f()({"k": "46,52,58"}, "k") == [46, 52, 58]

    def test_flottants_tronques(self) -> None:
        assert self._f()({"k": [46.0, "52"]}, "k") == [46, 52]

    @pytest.mark.parametrize("valeur", [None, "", "abc", 42, {"a": 1}])
    def test_valeur_inutilisable_rend_la_liste_vide(self, valeur: object) -> None:
        """🔒 Regle d'or : l'absence rend `[]`, ce que le noyau recevait avant. Pas d'erreur."""
        assert self._f()({"k": valeur}, "k") == []

    def test_cle_absente(self) -> None:
        assert self._f()({}, "k") == []

    def test_config_qui_n_est_pas_un_dictionnaire(self) -> None:
        assert self._f()(None, "k") == []


class TestConfigListOfListInt:
    """`_config_list_of_list_int` -- meme contrat, pour `rate_layer_sets`."""

    @staticmethod
    def _f():
        from certus.ui.certus_strat_ui_state import _config_list_of_list_int
        return _config_list_of_list_int

    def test_liste_de_listes(self) -> None:
        assert self._f()({"k": [[25, 30], [40]]}, "k") == [[25, 30], [40]]

    def test_forme_chaine(self) -> None:
        assert self._f()({"k": "25-30;40"}, "k") == [[25, 30], [40]]

    def test_groupe_vide_ecarte(self) -> None:
        assert self._f()({"k": [[], [7]]}, "k") == [[7]]

    @pytest.mark.parametrize("valeur", [None, "", 42])
    def test_valeur_inutilisable_rend_la_liste_vide(self, valeur: object) -> None:
        assert self._f()({"k": valeur}, "k") == []
