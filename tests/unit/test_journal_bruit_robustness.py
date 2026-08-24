"""LE JOURNAL DOIT RESTER LISIBLE -- et surtout ne pas devenir MUET.

## 🔴 CE QUI A ETE MESURE, ET QUI A MOTIVE LE CORRECTIF

📏 Le 2026-08-24, sur un run entier (`reports/hysteresis05_2026-08-24/journal_s404.log`), les
deux messages de `_filter_finite_robustness_scores` tiraient ainsi :

    2440 lignes ERROR au total
      -> 2400 sur une population de UNE strategie
      ->    7 sur DEUX
      ->    3 sur 601        <- les seules informatives

soit un rapport signal/bruit de **0,12 %**. Et 11 028 `WARNING` supplementaires, un par
strategie ecartee pour score non fini. Un `grep ERROR` sur le journal ne rendait plus rien
d'exploitable -- ce qui neutralisait aussi les gardes poses ailleurs, dont celui de la
malediction du vainqueur dans `certus_strat_workers.py`.

## 🔑 LES DEUX CAS N'APPELLENT PAS LE MEME REMEDE, ET C'EST LE COEUR DE CE FICHIER

| message | remede | pourquoi |
|---|---|---|
| `[ROBUSTNESS] NONE of the N` et `[REGIME] DEGENERE` | **seuil `N >= 2`** | ils decrivent un CLASSEMENT sans signal ; un classement d'un seul element n'est pas un classement. Et le cas `N = 1` est deja consigne par strategie dans l'artefact via `crash_eliminated` |
| `ecartee(s) pour score NON FINI` | **agregation** | quand il reste des survivants, ces strategies sont ecartees et n'atteignent JAMAIS l'artefact : leur nombre n'est recuperable nulle part, donc un seuil le perdrait |

> Une ligne de journal ne se justifie que si son information n'est **nulle part ailleurs**.
> En double → on coupe. Unique → on garde, agregee si elle est volumineuse.

## 🔴 LE TEST QUI COMPTE LE PLUS EST CELUI QUI VERIFIE QU'ON PARLE ENCORE

Remplacer un instrument bruyant par un instrument muet serait pire que le mal : le message du
regime degenere a coute **deux jours** de recherche en 2026-08-21 avant d'exister. Le premier
test de ce fichier existe pour qu'il ne disparaisse jamais en silence.
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from certus.core.certus_strat_robustness import _filter_finite_robustness_scores

LOGGER = logging.getLogger("test_journal_bruit_robustness")


def _strat(sid: int, score: float, crash: float = 1.0) -> dict:
    return {
        "strategy": {"strategy_id": sid},
        "robustness_score": score,
        "crash_rate": crash,
        "rmse_worst": 0.1 + sid * 1e-6,
    }


def _lignes(caplog, niveau: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == niveau]


class TestOnParleEncoreQuandCaCompte:
    """🔴 LE GARDE ANTI-MUTISME. Sans lui, le correctif de bruit pourrait tout eteindre."""

    def test_une_population_degeneree_de_601_parle_toujours(self, caplog):
        lot = [_strat(i, np.inf) for i in range(601)]
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            out = _filter_finite_robustness_scores(lot, logger=LOGGER)

        erreurs = _lignes(caplog, logging.ERROR)
        assert len(erreurs) == 1, "le regime degenere d'une VRAIE population doit crier"
        assert "601" in erreurs[0]
        regime = [m for m in _lignes(caplog, logging.WARNING) if "REGIME" in m]
        assert len(regime) == 1 and "601" in regime[0]
        assert len(out) == 601, "et il rend toujours le classement de repli"

    def test_le_seuil_est_a_DEUX_pas_a_dix(self, caplog):
        """Deux elements font un classement. C'est la definition, pas un reglage."""
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            _filter_finite_robustness_scores(
                [_strat(1, np.inf), _strat(2, np.inf)], logger=LOGGER
            )
        assert len(_lignes(caplog, logging.ERROR)) == 1


class TestOnSeTaitQuandCaNeDitRien:
    def test_une_seule_strategie_ne_declenche_ni_ERROR_ni_REGIME(self, caplog):
        """2400 des 2440 ERROR d'un run venaient de ce cas exact."""
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            out = _filter_finite_robustness_scores([_strat(7, np.inf)], logger=LOGGER)

        assert _lignes(caplog, logging.ERROR) == []
        assert [m for m in _lignes(caplog, logging.WARNING) if "REGIME" in m] == []
        # 🔑 ET L'INFORMATION N'EST PAS PERDUE : elle part dans l'artefact par cette cle.
        assert out[0]["crash_eliminated"] is True


class TestLeScoreNonFiniEstAGREGE:
    def test_une_seule_ligne_pour_tout_un_lot(self, caplog):
        lot = [_strat(i, np.inf) for i in range(40)] + [_strat(99, 0.5)]
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            out = _filter_finite_robustness_scores(lot, logger=LOGGER)

        nonfini = [m for m in _lignes(caplog, logging.WARNING) if "NON FINI" in m]
        assert len(nonfini) == 1, "une ligne par appel, pas une par strategie"
        assert "40" in nonfini[0], "et elle porte le COMPTE, qui n'est nulle part ailleurs"
        # il reste un survivant : les 40 ecartees ne rejoindront JAMAIS l'artefact,
        # ce qui est exactement pourquoi ce compte doit etre journalise.
        assert [r["strategy"]["strategy_id"] for r in out] == [99]

    def test_aucune_ligne_quand_tout_est_fini(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            _filter_finite_robustness_scores([_strat(1, 0.2), _strat(2, 0.3)], logger=LOGGER)
        assert [m for m in _lignes(caplog, logging.WARNING) if "NON FINI" in m] == []


class TestLInstrumentNeChangeRienAuCalcul:
    """Un garde-fou qui deplace un resultat n'est plus un garde-fou."""

    @pytest.mark.parametrize("n", [1, 2, 601])
    def test_le_classement_rendu_est_le_meme_quel_que_soit_le_bavardage(self, n, caplog):
        lot = [_strat(i, np.inf, crash=1.0 - i * 1e-4) for i in range(n)]
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            out = _filter_finite_robustness_scores(lot, logger=LOGGER)

        # trie par crash croissant : l'ordre ne doit rien devoir au niveau de journal
        assert [r["strategy"]["strategy_id"] for r in out] == sorted(
            range(n), key=lambda i: 1.0 - i * 1e-4
        )
        assert all(r["crash_eliminated"] is True for r in out)
        assert all(np.isfinite(r["robustness_score"]) for r in out)

    def test_les_survivants_passent_intacts_et_les_autres_sont_ecartes(self, caplog):
        lot = [_strat(1, 0.4), _strat(2, np.inf), _strat(3, 0.1)]
        with caplog.at_level(logging.DEBUG, logger=LOGGER.name):
            out = _filter_finite_robustness_scores(lot, logger=LOGGER)
        assert [r["strategy"]["strategy_id"] for r in out] == [1, 3]
        assert all("crash_eliminated" not in r for r in out)
