"""`scripts/resumer_artefact_sonde.py` counts an artifact of the probe the way the reports of 2026-10-12 do.

An AI that takes over the measurements of ETAT section 0 reads its artifacts with this script: a count that differs from the reports (the
threshold of a depositable plan, the class of a plan, the numbering of the layers) would make its tables incomparable with theirs.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import resumer_artefact_sonde as r

N = 6
BLOCS = [{"start": 0, "end": 3, "wavelength": 600.0}, {"start": 3, "end": 6, "wavelength": 640.0}]


def _plan(sid: int, crash: float, score: float, rate: list[int]) -> dict:
    return {"id": sid, "origine": "ELITE", "n_blocs": 2, "crash_rate": crash, "score": score, "rate_layers": rate, "blocs": BLOCS}


def _artefact() -> dict:
    return {
        "composant": "toy",
        "mode": "deep",
        "seed": 7,
        "config": {"overrides": {"elite_rate_moves": True}},
        "provenance": {"git_commit": "0123456789abcdef", "git_dirty": False},
        "strategies": [
            _plan(1, 0.01, 0.04, []),  # pure optics
            _plan(2, 0.00, 0.01, [3, 4, 5]),  # a tail: the best
            _plan(3, 0.02, 0.02, [2, 4, 5]),  # optics after Rate
            _plan(4, 0.50, 0.001, []),  # does not terminate: never the best, whatever its score
            _plan(5, 0.05, 0.001, [3, 4, 5]),  # exactly at the gate: not depositable
        ],
    }


def test_the_runs_of_layers_are_numbered_from_one_like_the_table_of_the_application() -> None:
    assert r.paquets([17, 18, 19, 25]) == [(17, 19), (25, 25)]
    assert r.en_couches(r.paquets(range(17, 75))) == "L18-L75"
    assert r.en_couches(r.paquets([17, 18, 19, 25])) == "L18-L20, L26"
    assert r.en_couches([]) == "aucun"


@pytest.mark.parametrize(
    ("rate", "expected"),
    [([], "optique pur"), ([3, 4, 5], "queue"), ([5], "queue"), ([2, 4, 5], "mixte"), ([2, 3], "mixte"), (None, "optique pur")],
)
def test_the_class_of_a_plan(rate, expected) -> None:
    assert r.classe(rate, N) == expected


def test_the_counts_of_an_artifact() -> None:
    out = r.resumer(_artefact())

    assert out["strategies"] == 5
    assert out["deposables"] == 3  # the plan at exactly 5 % is not depositable
    assert out["n_couches"] == N
    assert out["commit"] == "01234567"
    assert out["meilleur_seel"] == pytest.approx(2.0 * math.sqrt(0.01))
    assert {k: v["plans"] for k, v in out["classes"].items()} == {"optique pur": 1, "queue": 1, "mixte": 1}
    assert out["classes"]["mixte"]["meilleur_seel"] == pytest.approx(2.0 * math.sqrt(0.02))
    assert out["paquets_de_rate"] == {0: 1, 1: 1, 2: 1}
    assert out["plantage_minimal"] == 0.0


def test_the_best_plan_is_the_best_depositable_one() -> None:
    out = r.resumer(_artefact())

    assert out["meilleur"]["id"] == 2  # plan 4 has a lower score and does not terminate
    assert r.forme_du_plan(out["meilleur"], N) == "Rate L4-L6 ; optique L1-L3 ; 2 blocs (1-3 a 600 nm, 4-6 a 640 nm)"


def test_an_artifact_without_a_depositable_plan_says_so() -> None:
    artefact = _artefact()
    artefact["strategies"] = [_plan(1, 1.0, float("inf"), [])]

    out = r.resumer(artefact)

    assert out["meilleur"] is None
    assert out["meilleur_seel"] is None
    assert "aucun deposable" in r.texte(out)


def test_the_script_prints_one_summary_per_file(tmp_path, capsys) -> None:
    chemin = tmp_path / "artefact.json"
    chemin.write_text(json.dumps(_artefact()), encoding="utf-8")

    assert r.main([str(chemin), str(chemin)]) == 0

    sortie = capsys.readouterr().out
    assert sortie.count("toy | deep | graine 7 | commit 01234567") == 2
    assert "meilleur SEEL 0.2000 nm" in sortie
