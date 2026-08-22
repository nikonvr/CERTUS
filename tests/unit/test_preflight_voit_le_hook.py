"""LE CONTROLE DU HOOK DOIT VOIR LE HOOK QUE GIT VOIT -- pas celui d'un chemin devine.

WHY THIS EXISTS, ET C'EST LE PIRE SENS POSSIBLE POUR UN CONTROLE FAUX.

Le 2026-08-22, le hook `post-commit` a demenage de `.git/hooks/` (non versionne, donc perdu a
chaque clone) vers `.githooks/` (versionne), ou il s'arme par une commande :

    git config core.hooksPath .githooks

Le §2 de `scripts/preflight.py` lisait `.git/hooks/post-commit` EN DUR. Sous la configuration
VOULUE, ce dossier est vide -- le controle imprimait donc, sur la machine neuve du jour meme :

    [OK ] post-commit is disabled: committing stays local (found: (none))

pendant que le commit suivant POUSSAIT vers le depot PUBLIC `github.com/nikonvr/CERTUS`.

🔑 Ce n'est pas un controle muet, c'est un controle qui AFFIRME l'etat sur lequel repose tout
le reste : « commiter, c'est publier, donc rien de personnel n'entre dans l'index »
(`CLAUDE.md` §2). Un [OK] la-dessus autorise exactement ce qu'il est cense interdire.

🔴 Et c'etait la TROISIEME occurrence de la meme faute dans ce seul fichier -- `EXPECTED_ROOT`
code en dur, le `.venv` code en dur, puis `.git/hooks`. La faute n'est pas le chemin, c'est de
RECALCULER une valeur que git sait donner. D'ou les deux moities de ce test :

  A. la source ne code plus le chemin en dur et demande sa valeur effective ;
  B. la primitive sur laquelle repose la reparation fait bien ce qu'on croit -- verifie dans un
     depot JETABLE, sous les DEUX configurations, avec le controle negatif qui montre que
     l'ancienne logique se serait trompee.

B existe parce que A seul ne mord pas : une source peut appeler la bonne commande et mal en
lire la sortie, et une version de git plus ancienne pourrait ignorer `core.hooksPath`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
PREFLIGHT = RACINE / "scripts" / "preflight.py"


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    )
    return proc.stdout.strip()


# ---------------------------------------------------------------------------
# A. LA SOURCE
# ---------------------------------------------------------------------------

def test_preflight_demande_a_git_ou_vivent_les_hooks() -> None:
    """Le §2 doit interroger git, pas supposer `.git/hooks`."""
    src = PREFLIGHT.read_text(encoding="utf-8")
    assert '"--git-path", "hooks"' in src, (
        "preflight.py ne demande plus a git ou sont les hooks. Sans cela il ne voit pas un "
        "hook arme par core.hooksPath, et imprime [OK] sur un depot qui PUBLIE a chaque commit."
    )


def test_preflight_ne_code_plus_le_chemin_des_hooks_en_dur() -> None:
    """`ROOT / ".git" / "hooks"` ne doit subsister que comme REPLI, jamais comme source."""
    src = PREFLIGHT.read_text(encoding="utf-8")
    lignes_actives = [
        ligne for ligne in src.splitlines()
        if 'ROOT / ".git" / "hooks"' in ligne and not ligne.lstrip().startswith("#")
    ]
    assert len(lignes_actives) <= 1, (
        "Plusieurs lectures en dur de .git/hooks : le repli a du redevenir le chemin principal.\n"
        + "\n".join(lignes_actives)
    )
    if lignes_actives:
        assert "else" in lignes_actives[0], (
            "La seule lecture en dur de .git/hooks doit etre le REPLI d'une valeur demandee a "
            f"git, pas le chemin nominal : {lignes_actives[0].strip()}"
        )


# ---------------------------------------------------------------------------
# B. LA PRIMITIVE, DANS UN DEPOT JETABLE -- avec son controle negatif
# ---------------------------------------------------------------------------

@pytest.fixture
def depot(tmp_path: Path) -> Path:
    """Un depot neuf, avec un hook arme a la mode `.githooks` -- jamais le vrai depot."""
    _git("init", "-q", cwd=tmp_path)
    hooks = tmp_path / ".githooks"
    hooks.mkdir()
    (hooks / "post-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return tmp_path


def test_git_path_suit_core_hookspath_quand_il_est_pose(depot: Path) -> None:
    _git("config", "core.hooksPath", ".githooks", cwd=depot)
    assert Path(_git("rev-parse", "--git-path", "hooks", cwd=depot)) == Path(".githooks")


def test_git_path_rend_le_dossier_par_defaut_quand_il_ne_l_est_pas(depot: Path) -> None:
    assert Path(_git("rev-parse", "--git-path", "hooks", cwd=depot)) == Path(".git/hooks")


def test_controle_negatif_l_ancienne_logique_manquait_le_hook_arme(depot: Path) -> None:
    """🔴 Le test qui prouve que les precedents mordent.

    Sur ce depot, un `post-commit` EST arme et le commit suivant pousserait. L'ancienne
    logique -- lire `.git/hooks/post-commit` -- ne le voit pas. C'est le bug, reproduit.
    """
    _git("config", "core.hooksPath", ".githooks", cwd=depot)

    ancien = depot / ".git" / "hooks" / "post-commit"
    nouveau = depot / Path(_git("rev-parse", "--git-path", "hooks", cwd=depot)) / "post-commit"

    assert not ancien.is_file(), "le depot de test ne reproduit plus le cas qui a casse"
    assert nouveau.is_file(), "la resolution effective doit trouver le hook arme"
