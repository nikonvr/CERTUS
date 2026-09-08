"""Le golden master, en tests que `pytest` collecte vraiment.

🔴 POURQUOI CE FICHIER EXISTE. `test_convergence.py`, a cote, porte un nom que
`pytest` ramasse — mais c'est un SCRIPT : il n'expose que `main()` et un
`if __name__`. `pytest tests/regression/` rendait donc **`collected 0 items`**,
pendant que `RUN_CONVERGENCE_TESTS.bat` annonce en en-tete que cette suite est
*« OBLIGATOIRE avant toute validation de code »*. **Un zero silencieux dans une
suite verte** — mesure le 2026-09-08.

Ce module n'en est pas une copie : il **appelle** les fonctions du script. Si le
script change, ces tests suivent sans qu'on ait a les recrire.

📏 MESURE DU 2026-09-08, script lance a la main, 7 modules, < 8 min au total :

    DESIGN         SAUTE (absent de la base)
    RE             0.014595  <=  0.014734   PASS
    STRAT          RMSE: inf                FAIL
    INDEX          SAUTE (absent de la base)
    SPLINE         0.003393  <=  0.003427   PASS
    METAL_SINGLE   0.006100  <=  0.008192   PASS
    METAL_BILAYER  0.015017  <=  0.015168   PASS

🔴 **DESIGN ET STRAT NE SONT PAS MESURABLES, ET LEUR PRESENCE ETAIT NUISIBLE.**
`tests/headless/test_design.py` et `test_strat.py` **remplacent le calcul par un
mock** — ce que `CLAUDE.md` §4 dit depuis longtemps, et que ce harnais ignorait.
Le mock de STRAT emet `{"strategies": []}` : sans strategie, la RMSE vaut
l'infini, donc **aucune execution ne peut atteindre sa ligne de base `0.01706`**,
qui est un fossile d'avant le mock. Une entree qui ne peut pas passer produit un
rouge que personne ne peut corriger, et apprend a ignorer la suite.

📌 **INDEX est mesurable — il ne mocke pas — mais n'a pas de ligne de base.**
Elle n'est pas inventee ici : `scripts/collect_rmse.py` la produit, et enteriner
une reference est une decision qui revient au proprietaire du projet.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "regression"))

from test_convergence import TESTS, run_test_and_extract_rmse  # noqa: E402

BASELINE_PATH = ROOT / "tests" / "regression" / "baseline_rmse.json"

#: 1 % — la meme tolerance que le script.
TOLERANCE = 1.01

#: Les modules dont le script headless MOCKE le calcul : les mesurer n'a aucun sens.
NON_MESURABLES = {"DESIGN", "STRAT"}


def _baseline() -> dict[str, float]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_the_baseline_exists_and_is_readable():
    """Contrôle négatif : sans base, tout le reste passerait a vide."""
    assert BASELINE_PATH.is_file(), f"{BASELINE_PATH} absent — lance scripts/collect_rmse.py"
    assert _baseline(), "la base de reference est vide"


def test_no_mocked_module_is_declared_measurable():
    """Un module dont le calcul est mocke ne peut pas porter de reference.

    C'est ce qui rendait la suite rouge sans recours : la ligne de base de STRAT
    ne peut etre atteinte par aucune execution.
    """
    fautifs = sorted(NON_MESURABLES & set(_baseline()))
    assert not fautifs, (
        f"{fautifs} figurent dans la base alors que leur script headless mocke le calcul : "
        "leur reference est inatteignable par construction"
    )


def test_the_declared_list_matches_what_is_measurable():
    """Contrôle négatif : une liste vide ferait passer la parametrisation a vide."""
    mesurables = [n for n, _ in TESTS if n not in NON_MESURABLES]
    assert len(mesurables) >= 4, f"seulement {len(mesurables)} module(s) mesurable(s) declare(s)"


@pytest.mark.slow
@pytest.mark.parametrize(
    "name,script",
    [(n, s) for n, s in TESTS if n not in NON_MESURABLES],
    ids=[n for n, _ in TESTS if n not in NON_MESURABLES],
)
def test_convergence_has_not_regressed(name: str, script: str):
    """La RMSE d'un module ne doit pas depasser sa reference de plus de 1 %.

    ⚠️ Marque `slow` : chaque module lance un vrai pipeline en sous-processus.
    L'ensemble a coute moins de 8 min le 2026-09-08, mais ce n'est pas une
    commande qu'on lance entre deux editions.
    """
    baseline = _baseline()
    if name not in baseline:
        pytest.skip(f"{name} n'a pas de ligne de base — scripts/collect_rmse.py la produit")

    rmse, sortie = run_test_and_extract_rmse(name, script)
    assert rmse is not None, f"{name} : aucune RMSE exploitable dans la sortie\n{sortie[-600:]}"

    limite = baseline[name] * TOLERANCE
    assert rmse <= limite, (
        f"{name} : la convergence a regresse — RMSE {rmse:.6f} > {limite:.6f} (reference {baseline[name]:.6f} + 1 %)"
    )
