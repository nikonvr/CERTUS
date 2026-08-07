"""La dette de lint masquée ne peut que rétrécir.

``pyproject.toml`` neutralise un ensemble de règles ruff par ``extend-ignore``. Son
propre commentaire annonce l'intention : « Each ignored rule below maps to a planned
cleanup batch; remove the entry once the batch lands. »

Sans mécanisme, cette liste grandit — c'est le sens naturel des choses : ajouter une
règle à l'ignore transforme une dette VISIBLE en dette INVISIBLE, et coûte une ligne.
Le cliquet ci-dessous inverse cette pente : la liste ne peut que diminuer.

Deux tests, deux rôles distincts :

* le cliquet proprement dit, qui interdit d'ajouter une règle ;
* un détecteur de dette soldée, qui signale les règles dont plus aucune violation
  n'existe et qui peuvent donc sortir de la liste. Sans lui, une dette payée reste
  masquée indéfiniment et la règle ne protège plus personne.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Plafond du cliquet. Mesuré le 2026-08-02, après retrait de B018, B025, F822 et
# UP032 dont la dette venait d'être soldée.
#
# CE NOMBRE NE DOIT JAMAIS AUGMENTER. Si un changement légitime exige d'ignorer une
# règle supplémentaire, c'est une décision à prendre explicitement, pas un effet de
# bord — et il faut alors solder une autre règle en échange.
MAX_IGNORED_RULES = 68


def _ignored_rules() -> list[str]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    ruff = config.get("tool", {}).get("ruff", {})
    lint = ruff.get("lint", ruff)
    return list(lint.get("extend-ignore") or lint.get("extend_ignore") or [])


def test_la_liste_extend_ignore_ne_grandit_pas() -> None:
    """GARDE-FOU : le nombre de règles masquées ne peut que décroître.

    Une dette qu'on ne peut plus augmenter finit par disparaître. C'est tout l'objet
    de ce test : rendre le silence coûteux.
    """
    ignored = _ignored_rules()

    assert len(ignored) <= MAX_IGNORED_RULES, (
        f"extend-ignore compte {len(ignored)} regles, plafond fixe a "
        f"{MAX_IGNORED_RULES}.\n"
        f"Ajouter une regle a l'ignore transforme une dette VISIBLE en dette "
        f"INVISIBLE. Si c'est vraiment necessaire, solde une autre regle en echange "
        f"et abaisse MAX_IGNORED_RULES d'autant."
    )


def test_aucune_regle_ignoree_n_a_une_dette_deja_soldee() -> None:
    """Une règle sans violation n'a plus rien à faire dans extend-ignore.

    Elle y reste souvent par inertie, longtemps après que le nettoyage a eu lieu :
    la règle est alors désactivée sans raison, et ne protège plus contre une
    régression future. Ce test transforme ce nettoyage en action visible.
    """
    ignored = _ignored_rules()
    if not ignored:
        pytest.skip("aucune regle ignoree")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            ".",
            "--select",
            ",".join(sorted(ignored)),
            "--output-format",
            "concise",
            "--no-cache",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )

    violated = set()
    for line in (result.stdout or "").splitlines():
        for rule in ignored:
            if f" {rule} " in line:
                violated.add(rule)
                break

    settled = sorted(set(ignored) - violated)

    assert not settled, (
        f"{len(settled)} regle(s) ignoree(s) n'ont plus AUCUNE violation : leur dette "
        f"est soldee, elles peuvent sortir de extend-ignore et redevenir actives.\n"
        f"  {settled}\n"
        f"Pense a abaisser MAX_IGNORED_RULES d'autant."
    )
