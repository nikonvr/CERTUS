"""COUVERTURE EN LONGUEUR D'ONDE du minage -- rappeler la DP sous contrainte.

WHY THIS EXISTS, AND IT WAS BORN OF A MEASUREMENT.

Measured 2026-08-21 on `r75x2` at 2 nm, seed 42. Phase A declares a MEDIAN of 86 admissible
wavelengths per layer. The search produces **14 to 29** distinct ones per block count, and
**65 of the grid's 301** across its whole 1617-strategy population -- spending 104 to 160
strategies on roughly five to seven duplicates per wavelength.

    The budget for spread is already being spent -- on redundancy.

And the price is measured: the family of 72 depositable strategies needs 685 nm on the block
covering layers 33-52, and that wavelength appears in **ZERO** of the 1617. Six levers were
tried and each returned zero depositable strategies -- ELITE cap 480, span +/-2 nm,
confidence-bound crash gate, five screening seeds, widened profile x3-x4, parent wavelength
diversity. None of them could have worked: they all widen the search AROUND WHAT ALREADY
EXISTS, and the required wavelength exists nowhere.

This pass is different in kind: it does not widen, it FORCES. Restricting one layer of the
cost map to a single wavelength makes the DP return the best COHERENT grouping using it.
"""

from __future__ import annotations

import logging

import pytest

from certus.core.certus_strat_ranking import (
    _COUVERTURE_ID_OFFSET,
    _COUVERTURE_ID_STRIDE,
    _couverture_wl_groupings,
    _solution_wls,
    mine_strategies_for_block_count,
)

LOGGER = logging.getLogger("test_wl_coverage")


def _sol(*wls: float) -> dict:
    """Une solution de DP telle qu'elle sort : `blocks_info = [(debut, fin, lambda), ...]`."""
    return {"blocks_info": [(i, i + 1, float(w)) for i, w in enumerate(wls)]}


#: Une carte de cout ou 700 nm est ADMISSIBLE partout et la moins chere NULLE PART.
#: C'est exactement la situation mesuree : la lambda dont la famille gagnante a besoin est
#: admissible, et le k-meilleurs ne la choisit jamais.
CARTE = {
    0: {500.0: 1.0, 600.0: 2.0, 700.0: 9.0},
    1: {500.0: 1.1, 600.0: 2.1, 700.0: 8.0},   # <- 700 y est la moins chere
    2: {500.0: 1.2, 600.0: 2.2, 700.0: 9.5},
}


class TestSolutionWls:
    def test_lit_les_lambdas_d_une_solution(self):
        assert _solution_wls(_sol(500, 600, 500)) == {500.0, 600.0}

    @pytest.mark.parametrize("sol", [{}, {"blocks_info": None}, {"blocks_info": []}])
    def test_une_solution_sans_blocs_ne_casse_pas(self, sol):
        assert _solution_wls(sol) == set()


class TestInerte:
    """Budget nul -> rien. C'est le chemin par defaut du minage."""

    @pytest.mark.parametrize("budget", [0, -1])
    def test_budget_nul_ou_negatif(self, budget):
        appels = []
        out = _couverture_wl_groupings(
            CARTE, [_sol(500, 500)], lambda c, k: appels.append(1) or [], budget, LOGGER
        )
        assert out == []
        assert appels == [], "la DP ne doit meme pas etre rappelee"

    def test_rien_a_couvrir_quand_tout_est_deja_employe(self):
        appels = []
        deja = [_sol(500, 600, 700)]
        out = _couverture_wl_groupings(
            CARTE, deja, lambda c, k: appels.append(1) or [_sol(500)], 10, LOGGER
        )
        assert out == []
        assert appels == []


class TestLeComportementQuiCompte:
    def test_elle_force_la_lambda_ABSENTE(self):
        """Le coeur : 700 nm est admissible et jamais choisie. On la force."""
        vues = []

        def faux_dp(carte, k):
            vues.append(carte)
            return [_sol(700, 700)]

        out = _couverture_wl_groupings(CARTE, [_sol(500, 600)], faux_dp, 10, LOGGER)
        assert len(out) == 1
        assert 700.0 in _solution_wls(out[0])
        # Une seule couche est contrainte, les autres restent LIBRES : c'est ce qui distingue
        # cette passe d'une mutation -- le reste du plan est re-optimise autour d'elle.
        (carte,) = vues
        contraintes = [c for c, d in carte.items() if len(d) == 1]
        assert contraintes == [1], "la couche forcee doit etre la SEULE contrainte"

    def test_la_couche_forcee_est_celle_ou_la_lambda_est_LA_MOINS_CHERE(self):
        """Ce n'est pas un reglage : c'est ou la Phase A la juge la plus naturelle."""
        vues = []
        _couverture_wl_groupings(
            CARTE, [_sol(500, 600)], lambda c, k: vues.append(c) or [_sol(700)], 10, LOGGER
        )
        (carte,) = vues
        assert carte[1] == {700.0: 8.0}, "700 nm est la moins chere sur la couche 1"

    def test_la_DP_est_rappelee_avec_top_k_UN(self):
        """Sous contrainte, on ne veut que le MEILLEUR groupement coherent."""
        ks = []
        _couverture_wl_groupings(
            CARTE, [_sol(500, 600)], lambda c, k: ks.append(k) or [_sol(700)], 10, LOGGER
        )
        assert ks == [1]

    def test_la_carte_d_origine_n_est_PAS_modifiee(self):
        """Sinon la contrainte fuirait dans les appels suivants, et dans le k-meilleurs."""
        avant = {k: dict(v) for k, v in CARTE.items()}
        _couverture_wl_groupings(CARTE, [_sol(500)], lambda c, k: [_sol(700)], 10, LOGGER)
        assert CARTE == avant

    def test_l_ordre_est_le_COUT_CROISSANT(self):
        """Pour que le budget, s'il mord, morde sur les MOINS prometteuses."""
        carte = {0: {500.0: 1.0, 610.0: 3.0, 620.0: 2.0, 630.0: 4.0}}
        vus = []

        def faux_dp(c, k):
            (couche,) = [d for d in c.values() if len(d) == 1]
            vus.append(next(iter(couche)))
            return [_sol(500)]

        _couverture_wl_groupings(carte, [_sol(500)], faux_dp, 10, LOGGER)
        assert vus == [620.0, 610.0, 630.0], "cout 2.0 < 3.0 < 4.0"


class TestLesEchecsSontDITS:
    """Un elagage silencieux se lit comme une couverture complete."""

    def test_l_infaisable_est_compte_et_journalise(self, caplog):
        with caplog.at_level(logging.INFO, logger="test_wl_coverage"):
            out = _couverture_wl_groupings(CARTE, [_sol(500)], lambda c, k: [], 10, LOGGER)
        assert out == []
        msg = " ".join(r.getMessage() for r in caplog.records)
        assert "[WL-COUVERTURE]" in msg
        assert "2 infaisable(s)" in msg, msg

    def test_le_budget_qui_mord_est_DIT(self, caplog):
        carte = {0: {500.0: 1.0, 610.0: 2.0, 620.0: 3.0, 630.0: 4.0}}
        with caplog.at_level(logging.INFO, logger="test_wl_coverage"):
            out = _couverture_wl_groupings(
                carte, [_sol(500)], lambda c, k: [_sol(610)], 1, LOGGER
            )
        assert len(out) == 1
        msg = " ".join(r.getMessage() for r in caplog.records)
        assert "NON TRAITEE(S) faute de budget" in msg, msg
        assert "2 NON TRAITEE(S)" in msg, msg

    def test_rien_a_faire_est_DIT_aussi(self, caplog):
        with caplog.at_level(logging.INFO, logger="test_wl_coverage"):
            _couverture_wl_groupings(
                CARTE, [_sol(500, 600, 700)], lambda c, k: [], 10, LOGGER
            )
        msg = " ".join(r.getMessage() for r in caplog.records)
        assert "absente" in msg, msg


# --- de bout en bout, a travers le minage reel -------------------------------

#: 700 nm est admissible sur les quatre couches et n'est la moins chere sur aucune -- donc le
#: k-meilleurs ne la retient pas, quel que soit `top_k`.
RAW = {
    0: [{"wl": 500.0, "cost": 1.0}, {"wl": 600.0, "cost": 2.0}, {"wl": 700.0, "cost": 9.0}],
    1: [{"wl": 500.0, "cost": 1.0}, {"wl": 600.0, "cost": 2.0}, {"wl": 700.0, "cost": 8.0}],
    2: [{"wl": 500.0, "cost": 2.0}, {"wl": 600.0, "cost": 1.0}, {"wl": 700.0, "cost": 9.0}],
    3: [{"wl": 500.0, "cost": 2.0}, {"wl": 600.0, "cost": 1.0}, {"wl": 700.0, "cost": 9.0}],
}
N_BLOCKS = 2


def _miner(**kw):
    return mine_strategies_for_block_count(
        n_blocks=N_BLOCKS, raw_results_thickness=RAW, raw_results_sq=RAW,
        num_layers=4, top_k=3, **kw
    )


def _lambdas(strats) -> set:
    out = set()
    for s in strats:
        for b in s.get("blocks") or []:
            if b.get("wavelength") is not None:
                out.add(float(b["wavelength"]))
    return out


def _est_couverture(s) -> bool:
    champs = (str(s.get("origin", "")), str(s.get("origin_details", "")))
    return any("COUVERTURE" in c for c in champs)


class TestDeBoutEnBout:
    def test_par_DEFAUT_le_resultat_est_IDENTIQUE(self):
        """La regle d'or : le chemin inactif rend ce qu'il rendait."""
        a = _miner()
        b = _miner(enable_wl_coverage=False, wl_coverage_top_k=0)
        assert [s["strategy_id"] for s in a] == [s["strategy_id"] for s in b]
        assert [s.get("blocks") for s in a] == [s.get("blocks") for s in b]

    def test_sans_la_passe_700nm_est_ABSENTE(self):
        """La premisse du test suivant, verifiee et non supposee."""
        assert 700.0 not in _lambdas(_miner())

    def test_ARMEE_elle_fait_entrer_700nm(self):
        assert 700.0 in _lambdas(_miner(enable_wl_coverage=True))

    def test_elle_AJOUTE_sans_rien_retirer(self):
        avant = _miner()
        apres = _miner(enable_wl_coverage=True)
        assert len(apres) > len(avant)
        assert {s["strategy_id"] for s in avant} <= {s["strategy_id"] for s in apres}

    def test_les_identifiants_ne_COLLISIONNENT_pas(self):
        """Le defaut que ce decoupage previent, et il etait reel.

        Le plan est `n_blocks * 1000 + offset + rang`, offsets 0/100/200 pour les trois cartes
        de cout et 800 pour les graines structurees. En mode DEEP `top_k` vaut **exactement
        100** : le plan est SATURE. Allonger la liste en place aurait donne au 101e groupement
        l'identifiant du 1er de la carte suivante.
        """
        ids = [s["strategy_id"] for s in _miner(enable_wl_coverage=True)]
        assert len(ids) == len(set(ids)), "deux strategies sous un meme identifiant"

    def test_l_origine_de_la_couverture_est_DISTINCTE(self):
        """Sinon on ne saurait pas si une gagnante vient de l'optimalite ou de la couverture."""
        assert [s for s in _miner(enable_wl_coverage=True) if _est_couverture(s)]

    def test_les_identifiants_de_couverture_sont_dans_LEUR_plage(self):
        for s in _miner(enable_wl_coverage=True):
            if not _est_couverture(s):
                continue
            reste = s["strategy_id"] - N_BLOCKS * 1000
            assert _COUVERTURE_ID_OFFSET <= reste < 800, f"id {s['id']} hors plage reservee"

    def test_le_budget_ecrete_est_journalise(self, caplog):
        """Le plafond dur est la largeur de la plage d'identifiants, pas un reglage."""
        with caplog.at_level(logging.WARNING):
            _miner(enable_wl_coverage=True, wl_coverage_top_k=_COUVERTURE_ID_STRIDE + 1)
        msg = " ".join(r.getMessage() for r in caplog.records)
        assert "ecrete" in msg, msg


class TestLesCompteursRemontent:
    """Le journal du mineur est MUET -- les compteurs sont le seul canal fiable.

    Mesure du 2026-08-21 : la ligne `info` inconditionnelle du logger `ThinFilm`
    (« Mining: n_blocks=... ») apparait ZERO fois dans les journaux de campagne, alors que le
    logger `W{n_blk}` du worker passe. Un run de cinquante minutes a ete rendu ininterpretable :
    impossible de distinguer « la passe n'a pas tourne » de « chaque lambda etait infaisable ».

        Un instrument dont la sortie n'atteint pas le resultat n'est pas un instrument.
    """

    def test_ils_comptent_les_ajoutees_et_les_infaisables(self):
        stats: dict = {}
        appels = {"n": 0}

        def faux_dp(carte, k):
            appels["n"] += 1
            return [_sol(700)] if appels["n"] == 1 else []

        _couverture_wl_groupings(CARTE, [_sol(500)], faux_dp, 10, LOGGER, stats)
        assert stats["absentes"] == 2, stats
        assert stats["ajoutees"] == 1, stats
        assert stats["infaisables"] == 1, stats
        assert stats["appels_dp"] == 2, stats

    def test_ils_comptent_le_hors_budget(self):
        carte = {0: {500.0: 1.0, 610.0: 2.0, 620.0: 3.0, 630.0: 4.0}}
        stats: dict = {}
        _couverture_wl_groupings(carte, [_sol(500)], lambda c, k: [_sol(610)], 1, LOGGER, stats)
        assert stats["ajoutees"] == 1 and stats["non_traitees"] == 2, stats

    def test_RIEN_A_COUVRIR_se_distingue_de_PAS_TOURNE(self):
        """Le coeur du correctif. Ces deux etats se lisaient pareil, et ca a coute un run."""
        stats: dict = {}
        _couverture_wl_groupings(CARTE, [_sol(500, 600, 700)], lambda c, k: [], 10, LOGGER, stats)
        assert stats, "un dictionnaire VIDE veut dire « pas tourne » : il doit etre rempli"
        assert stats["absentes"] == 0
        assert stats["appels_dp"] == 0
        assert stats["deja_employees"] == 3

    def test_sans_dictionnaire_rien_ne_casse(self):
        """L'argument est optionnel : le chemin d'avant reste intact.

        `CARTE` porte trois lambdas et la solution n'en emploie qu'une : il en reste DEUX
        absentes, donc deux groupements. (Premiere attente ecrite a 1 -- corrigee par le test.)
        """
        out = _couverture_wl_groupings(CARTE, [_sol(500)], lambda c, k: [_sol(700)], 10, LOGGER)
        assert len(out) == 2

    def test_ils_s_ACCUMULENT_sur_les_trois_cartes_de_cout(self):
        """Le mineur appelle la passe une fois par carte ; les compteurs somment."""
        stats: dict = {}
        for _ in range(3):
            _couverture_wl_groupings(CARTE, [_sol(500)], lambda c, k: [_sol(700)], 10, LOGGER, stats)
        assert stats["ajoutees"] == 6, stats

    def test_de_bout_en_bout_le_mineur_les_remplit(self):
        stats: dict = {}
        _miner(enable_wl_coverage=True, wl_coverage_stats=stats)
        assert stats.get("ajoutees", 0) > 0, stats
        assert stats.get("appels_dp", 0) > 0, stats

    def test_par_DEFAUT_ils_restent_VIDES(self):
        """Un dictionnaire vide est le signal « la passe n'a pas tourne ». Il doit rester vrai."""
        stats: dict = {}
        _miner(wl_coverage_stats=stats)
        assert stats == {}, stats
