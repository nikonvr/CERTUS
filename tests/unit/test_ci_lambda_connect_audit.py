"""Le verdict de la CI doit tomber ICI, pas seulement sur GitHub.

`lint.yml` lance `tools/lambda_connect_audit.py --ci --max-count 0`. Un
`connect(lambda ...)` est refusé parce que la lambda n'est référencée nulle part :
Qt ne garantit alors ni sa durée de vie ni la déconnexion, et un slot nommé ou un
`functools.partial` se déconnecte, se teste et se lit.

🔴 **Ce job était rouge sur ses TROIS étapes**, mesuré le 2026-09-08 — le format,
cet audit, et l'audit de symboles morts. Un job rouge en permanence n'est pas un
garde-fou : personne ne le regarde. Et personne ne l'avait regardé, puisque les
deux workflows ne se déclenchaient même pas sur la branche de travail.

⚠️ Ce test ne duplique pas l'audit, il l'**exécute**. S'il change, le test suit
sans qu'on ait à le récrire — c'est la seule façon qu'il ne mente pas.

📌 L'audit des symboles morts a son propre fichier, `test_ci_dead_symbol_audit.py`.
⚠️ Ce renvoi disait qu'il n'était « délibérément pas repris, parce qu'il rend 32
candidats dont chacun demande un jugement » : les 32 étaient à 27 sur 32 des faux
positifs de périmètre, corrigés le 2026-09-08. Il en reste 7, tous mesurés.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "lambda_connect_audit.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_audit_exists_and_runs():
    """Contrôle négatif : un audit introuvable ferait passer le test suivant."""
    assert AUDIT.is_file(), f"{AUDIT} est introuvable — lint.yml le lance pourtant"
    assert _run("--max-count", "9999").returncode == 0, "l'audit échoue même avec un plafond absurde"


def test_the_audit_can_still_fail():
    """Contrôle négatif, l'autre sens : un plafond impossible doit être refusé.

    Sans lui, un audit devenu incapable de compter passerait pour vert.
    """
    out = _run("--ci", "--max-count", "-1")
    assert out.returncode != 0, "un plafond négatif est accepté : l'audit ne compte plus rien"


def test_no_signal_is_connected_to_a_lambda():
    out = _run("--ci", "--max-count", "0")
    assert out.returncode == 0, "des signaux sont connectés à une lambda, ce que la CI refuse :\n" + (
        out.stdout or out.stderr
    )
