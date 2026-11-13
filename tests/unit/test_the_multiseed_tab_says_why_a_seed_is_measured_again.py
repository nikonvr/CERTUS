"""The multi-seed tab says which seed is measured again on resume, and why (U12 B).

The orchestrator refuses the measure of a seed from another slit, other kernels or another commit, and measures it
again (`refusee` event). Without its own state, the row would read « waiting », and the operator would not know that
a measure on disk was set aside.
"""

from __future__ import annotations

from certus.ui.certus_strat_multigraine_ui import ETAT_AFFICHE, EtatMultigraine


def _state(*events: dict) -> EtatMultigraine:
    e = EtatMultigraine()
    for v in events:
        e.appliquer(v)
    return e


REFUSED = {"evt": "refusee", "graine": 101, "raison": "slit 2.0 nm in the artefact, 1 nm asked"}


def test_a_refused_seed_says_it_is_measured_again_and_why() -> None:
    e = _state({"evt": "demarrage", "graines": [101]}, REFUSED)
    line = e.lignes[101]
    assert line.etat == "a remesurer"
    assert line.motif == REFUSED["raison"]
    assert ETAT_AFFICHE["a remesurer"] == "measured again"


def test_a_refused_seed_never_launched_is_not_tried() -> None:
    e = _state({"evt": "demarrage", "graines": [101]}, REFUSED, {"evt": "notation", "graine": 42})
    assert e.lignes[101].etat == "non essayee"


def test_a_refused_seed_once_launched_runs() -> None:
    e = _state({"evt": "demarrage", "graines": [101]}, REFUSED, {"evt": "lancee", "graine": 101, "pid": 1})
    assert e.lignes[101].etat == "en cours"
