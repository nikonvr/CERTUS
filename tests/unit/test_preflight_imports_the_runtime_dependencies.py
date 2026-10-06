"""LE PREFLIGHT DOIT IMPORTER LES DEPENDANCES, PAS SEULEMENT LES TROUVER.

Le 2026-10-02 (ETAT D78), `pydantic 2.14.0a1` exigeait `pydantic-core 2.47.0` alors que `2.49.0` etait
installe. Le module existait, mais son controle de version levait `SystemError` a l'import : sept fenetres
sur sept mouraient avant de s'afficher, et `scripts/preflight.py` disait `PREFLIGHT=GO` (il n'importait que
le calcul optique, et `find_spec` ne voit pas un import qui echoue).

Le test lance le vrai script avec, devant les paquets installes, un `pydantic` factice qui leve la meme
erreur, puis un autre qui s'importe : le premier doit donner `PREFLIGHT=STOP` avec la cause, le second ne doit
pas accuser les dependances. Le second empeche le premier de passer pour un controle qui refuse tout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PREFLIGHT = Path(__file__).resolve().parents[2] / "scripts" / "preflight.py"
CONTROLE = "runtime dependencies import"


def _preflight_avec_pydantic(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    paquet = tmp_path / "pydantic"
    paquet.mkdir()
    (paquet / "__init__.py").write_text(source, encoding="utf-8")
    chemin = os.pathsep.join(filter(None, (str(tmp_path), os.environ.get("PYTHONPATH"))))
    env = {**os.environ, "PYTHONPATH": chemin}
    return subprocess.run(
        (sys.executable, str(PREFLIGHT)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )


def _ligne_du_controle(sortie: str) -> str:
    lignes = [ligne for ligne in sortie.splitlines() if CONTROLE in ligne and ligne.lstrip().startswith("[")]
    assert len(lignes) == 1, f"le preflight doit imprimer une ligne `{CONTROLE}` :\n{sortie}"
    return lignes[0]


def test_an_import_that_raises_stops_the_preflight_and_names_the_cause(tmp_path: Path) -> None:
    proc = _preflight_avec_pydantic(
        tmp_path,
        'raise SystemError("The installed pydantic-core version (9.9.9) is incompatible")\n',
    )
    ligne = _ligne_du_controle(proc.stdout)
    assert "[BAD]" in ligne, ligne
    for attendu in ("pydantic", "SystemError", "9.9.9"):
        assert attendu in ligne, ligne
    assert "PREFLIGHT=STOP" in proc.stdout, proc.stdout
    assert proc.returncode == 1


def test_an_importable_dependency_does_not_stop_the_preflight(tmp_path: Path) -> None:
    proc = _preflight_avec_pydantic(tmp_path, "")
    assert "[OK ]" in _ligne_du_controle(proc.stdout)
