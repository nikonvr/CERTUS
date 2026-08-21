"""DIVERSITE EN LONGUEUR D'ONDE du vivier de parents -- l'axe ou ELITE se deplace.

WHY THIS EXISTS. Measured 2026-08-21 on `r75x2` at 2 nm, seed 42, with the `[ELITE-PARENTS]`
instrument -- the strategies ELITE actually starts from, at ten blocks:

    5 parent lines  ->  ONE distinct set of wavelengths

They were near-duplicates of a single lineage: drop a block, duplicate a block, and that is
all. `elite_parent_top_k` bought ten COPIES, not ten DIRECTIONS. `_apply_block_diversity` does
not prevent it -- it diversifies the block PARTITION, an axis orthogonal to the one ELITE moves
in -- and that is why four widening levers each returned zero depositable strategies: a bigger
cap, a wider span and five seeds all search harder AROUND THE SAME POINT.

The headroom is measured on the same run: Phase A declares a MEDIAN of 86 admissible
wavelengths per layer, the search produces 14 to 29 per block count, and it spends 104 to 160
strategies on roughly five to seven duplicates per wavelength. The budget for spread is already
being spent -- on redundancy.
"""

from __future__ import annotations

import logging

import pytest

from certus.core.certus_strat_ranking import _apply_wl_diversity_if_enabled
from certus.utils.certus_strat_context import _apply_wl_diversity, _wl_set

LOGGER = logging.getLogger("test_wl_diversity")


def _it(*wls: float) -> dict:
    return {"strategy": {"blocks": [
        {"start": i, "end": i + 1, "wavelength": float(w)} for i, w in enumerate(wls)
    ]}}


#: 📏 La situation MESUREE : cinq quasi-doublons d'une lignee, puis deux directions reelles.
#: Les cinq premieres sont les parents observes a dix blocs ; la sixieme porte les λ de la
#: gagnante ; la septieme une region encore differente.
POP_MESUREE = [
    _it(483, 610, 610, 609, 688, 686, 739, 687, 483, 690),
    _it(483, 610, 609, 688, 686, 739, 687, 483, 690),
    _it(483, 610, 610, 609, 686, 739, 687, 483, 690),
    _it(483, 610, 610, 609, 688, 686, 739, 687, 483),
    _it(483, 610, 610, 609, 688, 686, 739, 483, 690),
    _it(450, 610, 615, 685, 647, 700, 511, 687, 704),
    _it(494, 470, 609, 658, 682, 705, 480, 487, 623),
]


class TestInerte:
    """🔒 Sans le drapeau, la liste ressort IDENTIQUE -- chemin d'avant au bit."""

    def test_absent_ne_touche_a_rien(self):
        out = _apply_wl_diversity_if_enabled(POP_MESUREE, {}, LOGGER)
        assert out is POP_MESUREE

    def test_explicitement_faux_ne_touche_a_rien(self):
        out = _apply_wl_diversity_if_enabled(
            POP_MESUREE, {"enable_wl_diversity": False}, LOGGER
        )
        assert out is POP_MESUREE

    def test_arme_il_reordonne(self):
        out = _apply_wl_diversity_if_enabled(
            POP_MESUREE, {"enable_wl_diversity": True, "wl_diversity_top_k": 3}, LOGGER
        )
        assert out is not POP_MESUREE
        assert len(out) == len(POP_MESUREE)


class TestLeComportementQuiCompte:
    def test_la_tete_gagne_en_diversite_sur_le_cas_MESURE(self):
        avant = len({_wl_set(x["strategy"]["blocks"]) for x in POP_MESUREE[:3]})
        out = _apply_wl_diversity(POP_MESUREE, top_k=3)
        apres = len({_wl_set(x["strategy"]["blocks"]) for x in out[:3]})
        assert avant == 2, "le cas de depart doit bien etre redondant"
        assert apres == 3, "la tete doit porter trois DIRECTIONS distinctes"

    def test_le_jeu_de_la_GAGNANTE_entre_dans_la_tete(self):
        """🔑 Il etait 6e au rang. C'est tout l'objet de la passe.

        Sans elle, ELITE ne l'a jamais comme parent -- et sa mutation etant locale et
        une-a-la-fois, il ne peut pas l'atteindre : trois λ nouvelles a introduire, dont une
        a 30 nm.
        """
        cible = _wl_set(POP_MESUREE[5]["strategy"]["blocks"])
        assert cible not in {_wl_set(x["strategy"]["blocks"]) for x in POP_MESUREE[:3]}
        out = _apply_wl_diversity(POP_MESUREE, top_k=3)
        assert cible in {_wl_set(x["strategy"]["blocks"]) for x in out[:3]}

    def test_le_MIEUX_CLASSE_reste_premier(self):
        """🔒 La passe etale, elle ne renverse pas le classement de tete."""
        out = _apply_wl_diversity(POP_MESUREE, top_k=4)
        assert out[0] is POP_MESUREE[0]

    def test_rien_n_est_perdu(self):
        out = _apply_wl_diversity(POP_MESUREE, top_k=3)
        assert len(out) == len(POP_MESUREE)
        assert {id(x) for x in out} == {id(x) for x in POP_MESUREE}

    def test_la_queue_garde_son_ordre_relatif(self):
        out = _apply_wl_diversity(POP_MESUREE, top_k=2)
        queue = out[2:]
        rangs = [POP_MESUREE.index(x) for x in queue]
        assert rangs == sorted(rangs), "la queue ne doit pas etre melangee"


class TestLaLimITEHonnete:
    def test_elle_ne_peut_PAS_creer_une_lambda_absente(self):
        """⚠️ La reserve, et elle est testee pour ne pas etre oubliee.

        📏 Sur `r75x2`, la famille gagnante exige 450 nm, qui figure dans ZERO des 1617
        strategies de la graine 42. Etaler les parents est donc NECESSAIRE et NON SUFFISANT.
        Une passe de diversite ne fabrique rien -- elle choisit.
        """
        pop = [_it(600, 610), _it(600, 620), _it(610, 620)]
        out = _apply_wl_diversity(pop, top_k=3)
        vues = set()
        for x in out:
            vues |= _wl_set(x["strategy"]["blocks"])
        assert vues == {600.0, 610.0, 620.0}
        assert 450.0 not in vues


class TestCasDegeneres:
    @pytest.mark.parametrize("top_k", [0, -1])
    def test_top_k_nul_ou_negatif(self, top_k):
        assert _apply_wl_diversity(POP_MESUREE, top_k=top_k) is POP_MESUREE

    def test_liste_vide_et_singleton(self):
        assert _apply_wl_diversity([], top_k=5) == []
        un = [_it(600)]
        assert _apply_wl_diversity(un, top_k=5) is un

    def test_top_k_plus_grand_que_la_liste(self):
        out = _apply_wl_diversity(POP_MESUREE, top_k=99)
        assert len(out) == len(POP_MESUREE)

    def test_strategies_sans_blocs_ne_cassent_pas(self):
        pop = [{"strategy": {}}, {}, _it(600, 610), {"strategy": {"blocks": None}}]
        out = _apply_wl_diversity(pop, top_k=3)
        assert len(out) == 4

    def test_deux_ensembles_vides_sont_identiques_pas_infiniment_loin(self):
        """Sinon deux strategies sans λ seraient prises pour deux directions."""
        pop = [{"strategy": {"blocks": []}}, {"strategy": {"blocks": []}}, _it(600)]
        out = _apply_wl_diversity(pop, top_k=2)
        assert _wl_set(out[1]["strategy"]["blocks"]) == {600.0}, (
            "le vrai different doit passer avant le doublon vide"
        )


class TestLaJournalisation:
    def test_la_passe_DIT_ce_qu_elle_a_change(self, caplog):
        """🔴 Une passe de diversite qui ne diversifie rien cree une fausse explication."""
        with caplog.at_level(logging.INFO, logger="test_wl_diversity"):
            _apply_wl_diversity_if_enabled(
                POP_MESUREE,
                {"enable_wl_diversity": True, "wl_diversity_top_k": 3},
                LOGGER,
            )
        msgs = " ".join(r.getMessage() for r in caplog.records)
        assert "[WL-DIVERSITE]" in msgs
        assert "2 jeu(x)" in msgs and "-> 3" in msgs

    def test_le_top_k_retombe_sur_celui_des_blocs(self):
        """Un seul reglage a connaitre si l'on n'en veut qu'un."""
        out = _apply_wl_diversity_if_enabled(
            POP_MESUREE,
            {"enable_wl_diversity": True, "block_diversity_top_k": 3},
            LOGGER,
        )
        assert len({_wl_set(x["strategy"]["blocks"]) for x in out[:3]}) == 3


class TestLeDefautLatentDuTopK:
    """🔴 Un defaut qui n'aurait leve QUE sur le chemin arme, donc jamais dans la suite.

    `params.get(cle, defaut)` rend `None` quand la cle EXISTE avec la valeur `None` -- il ne
    retombe PAS sur le defaut. Le routage posait `None` en l'absence de cle JSON, et
    `int(None)` aurait leve un TypeError au premier run avec la passe armee.
    """

    @pytest.mark.parametrize("valeur", [None, 0])
    def test_un_top_k_vide_retombe_sur_celui_des_blocs(self, valeur):
        out = _apply_wl_diversity_if_enabled(
            POP_MESUREE,
            {"enable_wl_diversity": True, "wl_diversity_top_k": valeur,
             "block_diversity_top_k": 3},
            LOGGER,
        )
        assert len({_wl_set(x["strategy"]["blocks"]) for x in out[:3]}) == 3

    def test_tout_vide_retombe_sur_dix(self):
        out = _apply_wl_diversity_if_enabled(
            POP_MESUREE,
            {"enable_wl_diversity": True, "wl_diversity_top_k": None,
             "block_diversity_top_k": None},
            LOGGER,
        )
        assert len(out) == len(POP_MESUREE)
