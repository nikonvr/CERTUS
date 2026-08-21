"""INJECTION DE PLANS -- la mesure qui dit si la cible existe.

WHY THIS EXISTS. On `r75x2` at 2 nm, seed 77 finds 547 depositable strategies and seed 42 finds
none on 1617. Four search levers were tried against that zero -- ELITE cap raised to 480, a
five-seed screening union, the confidence-bounded crash gate, the Rate tail -- and all four
returned zero. One question has not moved for two days, and no search lever can answer it:

    DOES THE HEALTHY REGION EXIST AT SEED 42 AT ALL?

The 12 best plans of seed 77 are on disk with their wavelengths, and their export is verified
exact. Handing them to seed 42 and letting the PRODUCTION path score them answers it directly:
they hold, and what is missing is the search; they crash, and the 0.5692 belongs to its own
realisation.

The plans enter through `inherited_strategies` -- a channel that already exists, is already
tested, and already carries strategies from one block count to the next. They are filtered on
`n_blocks == n_blk`, contract-checked, screened and scored by exactly the code every other
candidate goes through. There is no second path to be wrong about, which is the whole point:
`probe_renoter.py` took the other route -- a reconstructed context -- and has never reproduced
its own fixed point.
"""

from __future__ import annotations

import inspect
import json

import pytest

from certus.workers import certus_strat_workers as W
from certus.workers.certus_strat_workers import _resolve_injected_strategies as R


def _plan(*bornes: tuple[int, int, float], nom: str = "p") -> dict:
    return {"nom": nom, "blocs": [
        {"start": a, "end": b, "wavelength": w} for a, b, w in bornes
    ]}


class TestInerte:
    """Sans la cle, rien n'est ajoute -- le chemin d'avant, au bit."""

    @pytest.mark.parametrize("params", [{}, {"injected_strategies": None},
                                        {"injected_strategies": ""},
                                        {"injected_strategies": []}])
    def test_rien_a_injecter(self, params):
        assert R(params) == []

    def test_un_objet_sans_get_ne_casse_pas(self):
        assert R(object()) == []


class TestChargement:
    def test_une_liste_de_plans(self):
        out = R({"injected_strategies": [_plan((0, 5, 600.0), (5, 10, 610.0))]})
        assert len(out) == 1
        assert out[0]["n_blocks"] == 2
        assert [b["wavelength"] for b in out[0]["blocks"]] == [600.0, 610.0]

    def test_les_deux_orthographes_blocs_et_blocks(self):
        a = R({"injected_strategies": [{"blocs": [{"start": 0, "end": 5, "wavelength": 600.0}]}]})
        b = R({"injected_strategies": [{"blocks": [{"start": 0, "end": 5, "wavelength": 600.0}]}]})
        assert len(a) == len(b) == 1
        assert a[0]["blocks"] == b[0]["blocks"]

    def test_la_cle_wl_des_vieux_artefacts_est_acceptee(self):
        out = R({"injected_strategies": [{"blocs": [{"start": 0, "end": 5, "wl": 600.0}]}]})
        assert out[0]["blocks"][0]["wavelength"] == 600.0

    def test_un_fichier_json(self, tmp_path):
        f = tmp_path / "plans.json"
        f.write_text(json.dumps([_plan((0, 5, 600.0)), _plan((0, 3, 610.0), (3, 5, 620.0))]),
                     encoding="utf-8")
        out = R({"injected_strategies": str(f)})
        assert [p["n_blocks"] for p in out] == [1, 2]

    def test_un_fichier_enveloppe_dans_plans(self, tmp_path):
        f = tmp_path / "plans.json"
        f.write_text(json.dumps({"plans": [_plan((0, 5, 600.0))]}), encoding="utf-8")
        assert len(R({"injected_strategies": str(f)})) == 1

    def test_le_nom_du_plan_marque_l_origine(self):
        out = R({"injected_strategies": [_plan((0, 5, 600.0), nom="gagnante_s077")]})
        assert out[0]["origin"] == "INJECTED(gagnante_s077)"

    def test_les_identifiants_sont_distincts(self):
        out = R({"injected_strategies": [_plan((0, 5, 600.0)), _plan((0, 5, 610.0))]})
        assert len({p["strategy_id"] for p in out}) == 2


class TestCeQuiDoitLeverOuEtreEcarte:
    def test_un_fichier_manquant_LEVE_et_ne_se_tait_pas(self, tmp_path):
        """🔴 Le silence serait le pire des comportements.

        Une injection silencieusement vide rendrait un run identique trait pour trait a un run
        sans injection -- et on conclurait « les plans plantent » alors qu'AUCUN n'a ete
        evalue. C'est exactement le motif que ce depot paie : ca ne produit pas d'erreur, ca
        produit un resultat plausible.
        """
        with pytest.raises(FileNotFoundError):
            R({"injected_strategies": str(tmp_path / "absent.json")})

    def test_autre_chose_qu_une_liste_leve(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({"pas": "une liste"}), encoding="utf-8")
        with pytest.raises(TypeError):
            R({"injected_strategies": str(f)})

    def test_les_blocs_malformes_sont_ecartes_sans_casser(self):
        out = R({"injected_strategies": [
            {"blocs": [{"start": 0, "end": 5}]},                       # pas de lambda
            {"blocs": [{"start": 0, "wavelength": 600.0}]},             # pas de fin
            {"blocs": ["pas un dict"]},
            {"blocs": []},
            _plan((0, 5, 600.0)),                                       # le seul valide
        ]})
        assert len(out) == 1
        assert out[0]["blocks"][0]["wavelength"] == 600.0


class TestNBlocksEstDERIVE:
    def test_un_compte_declare_faux_est_CORRIGE_pas_repris(self):
        """🔴 Faire confiance au fichier ferait tomber le plan en silence.

        Le worker filtre sur `n_blocks == n_blk` PUIS verifie le contrat avec
        `expected_n_blocks=n_blk`. Un plan qui declarerait 9 blocs en portant 11 serait donc
        propose au mauvais nombre de blocs, rejete par le contrat, et disparaitrait -- sans un
        mot. On derive le compte de la liste, toujours.
        """
        out = R({"injected_strategies": [
            {"n_blocks": 99, "blocs": [{"start": 0, "end": 5, "wavelength": 600.0},
                                       {"start": 5, "end": 9, "wavelength": 610.0}]},
        ]})
        assert out[0]["n_blocks"] == 2


class TestLesDouzePlansReels:
    """Le fichier que la mesure utilisera vraiment, charge tel quel."""

    def test_les_12_plans_de_la_graine_77_se_chargent(self):
        out = R({"injected_strategies": "reports/plans/plans_s077_vers_s042.json"})
        assert len(out) == 12
        import collections
        assert dict(sorted(collections.Counter(p["n_blocks"] for p in out).items())) == {
            9: 4, 10: 2, 11: 6
        }

    def test_ils_tiennent_dans_la_plage_restreinte_7_13(self):
        """🔑 Sinon la restriction de plage les rendrait inatteignables, et le test serait vide."""
        out = R({"injected_strategies": "reports/plans/plans_s077_vers_s042.json"})
        assert all(7 <= p["n_blocks"] <= 13 for p in out)

    def test_les_blocs_pavent_l_empilement_sans_trou(self):
        out = R({"injected_strategies": "reports/plans/plans_s077_vers_s042.json"})
        for p in out:
            couvert = set()
            for b in p["blocks"]:
                couvert |= set(range(b["start"], b["end"]))
            assert couvert == set(range(75)), f"{p['origin']} ne pave pas [0,75)"


class TestLeCablageDansLeWorker:
    """Le mecanisme est inutile si le worker ne le lit pas -- garde structurel."""

    def test_le_worker_verse_les_plans_dans_inherited_strategies(self):
        src = inspect.getsource(W)
        i = src.index("_injectes = _resolve_injected_strategies(params)")
        bloc = src[i : i + 400]
        assert "inherited_strategies = list(inherited_strategies or []) + _injectes" in bloc, (
            "les plans injectes doivent entrer par le canal de l'heritage, pas par un chemin neuf"
        )

    def test_l_injection_precede_le_filtre_par_nombre_de_blocs(self):
        """Sinon les plans seraient ajoutes APRES le tri et jamais consideres."""
        src = inspect.getsource(W)
        assert src.index("_injectes = _resolve_injected_strategies(params)") < src.index(
            'if s.get("n_blocks") != n_blk:'
        )
