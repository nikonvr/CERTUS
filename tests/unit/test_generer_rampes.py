"""LA FABRICATION DES RAMPES DE LANCEMENT -- la methode qui a livre le resultat.

WHY THIS EXISTS. On 2026-08-21 `r75x2` at 2 nm went from **0 depositable strategies out of
1617** to **197 out of 1810**, SEEL **0.5676 nm**, on the production path with no override at
all. What produced that was not an algorithm but a METHOD, executed by hand -- run K seeds,
harvest the depositable strategies of those that find any, keep the best, declare them as
`injected_strategies`. `scripts/generer_rampes.py` fixes that method into one command.

THREE DEFECTS WERE FOUND BY TRYING IT, and every one of them is guarded here.

    1. deduplicating by EQUALITY of the wavelength set collapsed 547 candidates to ONE ramp
    2. resolving the artifact by its canonical NAME picked the OLDEST file, because the probe
       appends a timestamp when a homonym exists
    3. an artifact from before 2026-08-20 carries `blocs: null` -- and the first version of the
       script produced ONE ramp with an EMPTY plan, which looked like a result

The third is the one this repository punishes: it does not raise, it returns something
plausible. An artifact without plans is now REFUSED, and its seed goes into a THIRD state --
neither sterile nor fertile, but TO BE REMEASURED.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generer_rampes as GR  # noqa: E402


def _strat(seel_carre: float, crash: float, *blocs: tuple[int, int, float]) -> dict:
    return {
        "score": seel_carre,
        "crash_rate": crash,
        "n_blocs": len(blocs),
        "origine": "ELITE",
        "blocs": [{"start": a, "end": b, "wavelength": w} for a, b, w in blocs],
    }


class TestLePlanEtLaDistance:
    def test_le_plan_est_la_suite_des_triplets(self):
        s = _strat(0.08, 0.01, (0, 8, 450.0), (8, 25, 610.0))
        assert GR._plan(s["blocs"]) == ((0, 8, 450.0), (8, 25, 610.0))

    @pytest.mark.parametrize("blocs", [None, [], [{"start": 0, "end": 1}]])
    def test_un_plan_incomplet_ne_casse_pas(self, blocs):
        assert GR._plan(blocs) == ()

    def test_deux_plans_identiques_sont_a_distance_nulle(self):
        a = ((0, 8, 450.0), (8, 25, 610.0))
        assert GR._distance(a, a) == 0

    def test_LA_DISTANCE_MESUREE_ENTRE_LA_GAGNANTE_ET_SA_RAMPE(self):
        """Le cas reel du 2026-08-21 : un pas de λ, un pas de frontiere -> 3 blocs differents.

        C'est cette mesure qui impose une DISTANCE plutot qu'une egalite : deux plans separes
        de 1 a 3 blocs sont dans le voisinage qu'ELITE parcourt en quelques rondes.
        """
        rampe = ((25, 33, 615.0), (33, 53, 685.0), (53, 57, 647.0))
        gagnante = ((25, 33, 616.0), (33, 52, 685.0), (52, 57, 647.0))
        assert GR._distance(rampe, gagnante) == 3

    def test_deux_nombres_de_blocs_differents_sont_MAXIMALEMENT_loin(self):
        """Ce ne sont pas des voisins : ce sont des structures differentes."""
        a = ((0, 8, 450.0),)
        b = ((0, 4, 450.0), (4, 8, 610.0))
        assert GR._distance(a, b) > 1000


class TestLaSelection:
    def test_elle_garde_la_MEILLEURE_en_premier(self):
        r = [(42, _strat(0.30, 0.01, (0, 5, 600.0))), (77, _strat(0.08, 0.01, (0, 5, 700.0)))]
        gardees, _ec, _j = GR.choisir_rampes(r, 2)
        assert gardees[0][0] == 77, "la meilleure au score doit etre prise d'abord"

    def test_elle_prefere_le_PLUS_LOIN_au_deuxieme_meilleur(self):
        """Le coeur du glouton max-min : des DIRECTIONS, pas des copies."""
        base = _strat(0.080, 0.01, (0, 5, 600.0), (5, 10, 610.0))
        proche = _strat(0.081, 0.01, (0, 5, 600.0), (5, 10, 611.0))   # 1 bloc d'ecart
        loin = _strat(0.090, 0.01, (0, 5, 500.0), (5, 10, 700.0))     # 2 blocs d'ecart
        gardees, _ec, _j = GR.choisir_rampes(
            [(1, base), (2, proche), (3, loin)], 2
        )
        assert [g for g, _s in gardees] == [1, 3], (
            "la 2e retenue doit etre la PLUS LOIN, pas la 2e au score"
        )

    def test_les_doublons_EXACTS_sont_ecartes(self):
        p = ((0, 5, 600.0),)
        s = _strat(0.08, 0.01, *p)
        gardees, ecartees, _j = GR.choisir_rampes([(1, s), (2, dict(s)), (3, dict(s))], 10)
        assert len(gardees) == 1
        assert ecartees == 2

    def test_elle_compte_les_JEUX_DE_LAMBDA_distincts(self):
        """Diagnostic : une seule lignee est un signal, et il doit remonter."""
        a = _strat(0.08, 0.01, (0, 5, 600.0), (5, 10, 610.0))
        b = _strat(0.09, 0.01, (0, 6, 600.0), (6, 10, 610.0))   # memes λ, autres frontieres
        c = _strat(0.10, 0.01, (0, 5, 500.0), (5, 10, 700.0))   # autres λ
        _g, _e, jeux = GR.choisir_rampes([(1, a), (2, b), (3, c)], 3)
        assert jeux == 2, "a et b partagent leur jeu de λ ; c en a un autre"

    @pytest.mark.parametrize("combien", [0, -1])
    def test_un_budget_nul_rend_quand_meme_la_meilleure(self, combien):
        """Mieux vaut une rampe qu'aucune : le budget borne, il n'annule pas."""
        gardees, _e, _j = GR.choisir_rampes([(1, _strat(0.08, 0.01, (0, 5, 600.0)))], combien)
        assert len(gardees) == 1

    def test_une_recolte_vide_rend_du_vide_sans_lever(self):
        assert GR.choisir_rampes([], 10) == ([], 0, 0)

    def test_le_budget_plafonne_bien(self):
        r = [(i, _strat(0.08 + i / 100, 0.01, (0, 5, 600.0 + i))) for i in range(20)]
        gardees, ecartees, _j = GR.choisir_rampes(r, 5)
        assert len(gardees) == 5
        assert ecartees == 15


class TestLeRefusDesArtefactsSANSPLANS:
    """🔴 Le defaut grave : il ne levait pas, il rendait un resultat plausible."""

    def test_un_artefact_a_blocs_nuls_est_REFUSE(self):
        d = {"strategies": [{"score": 0.08, "crash_rate": 0.01, "blocs": None,
                             "lambdas": [None, None]}]}
        assert not GR._porte_les_plans(d)

    def test_un_artefact_complet_est_accepte(self):
        d = {"strategies": [_strat(0.08, 0.01, (0, 5, 600.0))]}
        assert GR._porte_les_plans(d)

    def test_un_artefact_PARTIEL_est_refuse_aussi(self):
        """Tout ou rien : une recolte a moitie aveugle est pire qu'un refus."""
        d = {"strategies": [_strat(0.08, 0.01, (0, 5, 600.0)),
                            {"score": 0.09, "crash_rate": 0.01, "blocs": None}]}
        assert not GR._porte_les_plans(d)

    @pytest.mark.parametrize("d", [{}, {"strategies": []}, {"strategies": None}])
    def test_un_artefact_vide_est_refuse(self, d):
        assert not GR._porte_les_plans(d)


class TestLaResolutionDeLArtefact:
    """Le nom canonique est souvent le PLUS ANCIEN -- la sonde suffixe les homonymes."""

    def _ecrire(self, dossier: Path, nom: str, avec_plans: bool) -> Path:
        st = ([_strat(0.08, 0.01, (0, 5, 600.0))] if avec_plans
              else [{"score": 0.08, "crash_rate": 0.01, "blocs": None}])
        q = dossier / nom
        q.write_text(json.dumps({"verdict": "OK", "strategies": st}), encoding="utf-8")
        return q

    def test_elle_ignore_le_fichier_SANS_plans_et_prend_le_suffixe(self, tmp_path, monkeypatch):
        rep = tmp_path / "reports"
        rep.mkdir()
        self._ecrire(rep, "blocs_vs_plantage_r75x2_deep_s077.json", avec_plans=False)
        bon = self._ecrire(rep, "blocs_vs_plantage_r75x2_deep_s077_20260820.json", avec_plans=True)
        monkeypatch.setattr(GR, "ROOT", tmp_path)
        assert GR._artefact("r75x2", 77) == bon

    def test_elle_rend_None_quand_AUCUN_ne_porte_de_plans(self, tmp_path, monkeypatch):
        rep = tmp_path / "reports"
        rep.mkdir()
        self._ecrire(rep, "blocs_vs_plantage_r75x2_deep_s042.json", avec_plans=False)
        monkeypatch.setattr(GR, "ROOT", tmp_path)
        assert GR._artefact("r75x2", 42) is None

    def test_elle_rend_None_quand_il_n_y_a_rien(self, tmp_path, monkeypatch):
        (tmp_path / "reports").mkdir()
        monkeypatch.setattr(GR, "ROOT", tmp_path)
        assert GR._artefact("r75x2", 999) is None


class TestLaRecolte:
    def _ecrire(self, tmp_path: Path, verdict: str, strats: list[dict]) -> Path:
        q = tmp_path / "a.json"
        q.write_text(json.dumps({"verdict": verdict, "strategies": strats}), encoding="utf-8")
        return q

    def test_un_verdict_NON_OK_est_ecarte(self, tmp_path, capsys):
        q = self._ecrire(tmp_path, "SURCHARGES_NON_APPLIQUEES", [_strat(0.08, 0.01, (0, 5, 600.0))])
        assert GR._recolter(q) == []
        assert "ecarte" in capsys.readouterr().out

    def test_seules_les_DEPOSABLES_sont_recoltees(self, tmp_path):
        q = self._ecrire(tmp_path, "OK", [
            _strat(0.08, 0.010, (0, 5, 600.0)),   # deposable
            _strat(0.08, 0.050, (0, 5, 610.0)),   # a la limite : deposable
            _strat(0.08, 0.051, (0, 5, 620.0)),   # au-dela : non
            _strat(0.08, 1.000, (0, 5, 630.0)),   # mur
        ])
        assert len(GR._recolter(q)) == 2

    def test_la_tolerance_est_celle_de_l_utilisateur(self):
        """👤 : 95 % des depositions doivent se terminer. Pas un reglage de ce script."""
        assert GR.TOLERANCE_PLANTAGE == 0.05


class TestLeSEEL:
    def test_il_vaut_deux_racines_du_score(self):
        assert GR._seel({"score": 0.08053}) == pytest.approx(0.56756, abs=1e-5)

    @pytest.mark.parametrize("s", [{}, {"score": None}, {"score": "x"}, {"score": -1.0}])
    def test_un_score_absurde_rend_l_infini_au_lieu_de_lever(self, s):
        assert GR._seel(s) == float("inf")


class TestLeNombreDeRampes:
    def test_il_suit_elite_parent_top_k(self):
        """🔑 Ce n'est pas un nombre invente : le metier d'une rampe est d'etre PARENT.

        Si le defaut du noyau change, celui-ci doit changer avec -- ce test le rappellera.
        """
        import inspect

        from certus.core import certus_strat_consensus as C
        src = inspect.getsource(C)
        assert 'params.get("elite_parent_top_k", 10)' in src, (
            "le defaut du noyau a change : ajuste RAMPES_PAR_DEFAUT"
        )
        assert GR.RAMPES_PAR_DEFAUT == 10
