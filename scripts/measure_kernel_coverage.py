"""LA COUVERTURE DES NOYAUX COMPILES, MESUREE SANS COMPILATION (audit v2, plan S3.1 et S3.2 ; indicateur "couverture des noyaux").

    python scripts\\measure_kernel_coverage.py                        mesure et dit le pourcentage de certus/physics/
    python scripts\\measure_kernel_coverage.py --json noyaux.json     ... et garde le JSON de `coverage json`
    python scripts\\measure_kernel_coverage.py --check                ... et sort avec 1 sous le plancher "noyaux" de tests/coverage_floors.json

Numba compile les noyaux, et `coverage` ne voit pas une ligne de code compile : `certus/physics/` paraissait a 20,3 % (mesure du 2026-09-30). Avec
`NUMBA_DISABLE_JIT=1` les noyaux sont du Python et se lisent.

CE QUE LA MESURE LANCE, ET POURQUOI C'EST CELA. Tout ce qui teste les noyaux, et seulement cela :

    tests/oracle, tests/core, tests/property      les repertoires entiers (la reference TMM independante, les noyaux, les invariants)
    tests/unit -m kernels                         les fichiers de unit qui portent `pytestmark = pytest.mark.kernels` : ceux dont l'objet est un noyau

La mesure du 2026-09-30 (45,9 %) ne lancait que oracle + core : elle ignorait les tests ecrits ensuite pour les noyaux de STRAT (S3.2, S5.1), qui sont
dans unit. Avec eux : 73,9 % (le 2026-10-01). Un fichier de unit qui teste un noyau et ne porte pas le marqueur ne compte pas ici : le marqueur est la
liste, et un nouveau test de noyau l'ajoute en une ligne. Les tests qui supposent la compilation (l'identite binaire froid / chaud, le cache) ne
portent pas le marqueur ; deux tests de l'oracle sautent d'eux-memes sous `NUMBA_DISABLE_JIT=1`.

Le code de sortie : 0 la mesure est faite (et, avec --check, aucun plancher n'est perce) ; 1 un test a echoue, ou un plancher est perce ; 2 le JSON est
illisible ou absent.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_coverage_floors as floors_module  # noqa: E402

PREFIX = "certus/physics/"
WHOLE_DIRECTORIES = ("tests/oracle", "tests/core", "tests/property")
MARKER = "kernels"


def commands(report: Path) -> list[list[str]]:
    """The two pytest runs that make the measure: the whole directories, then the marked unit tests, appended to the same coverage data."""
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "--cov=certus"]
    return [
        [*base, *WHOLE_DIRECTORIES, "--cov-report="],
        [*base, "tests/unit", "-m", MARKER, "--cov-append", f"--cov-report=json:{report}"],
    ]


def environment(coverage_data: Path) -> dict[str, str]:
    return {**os.environ, "NUMBA_DISABLE_JIT": "1", "COVERAGE_FILE": str(coverage_data), "PYTHONIOENCODING": "utf-8"}


def physics_lines(report: dict) -> tuple[int, int]:
    """(covered lines, lines) of `certus/physics/` in a `coverage json` report."""
    found = floors_module.coverage_by_prefix(report, [PREFIX])[PREFIX]
    if found is None:
        raise KeyError(f"no file of {PREFIX} in the report")
    return found


def main(argv: Sequence[str] | None = None, run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Couverture de certus/physics/ sans compilation (oracle, core, property, unit -m kernels).")
    parser.add_argument("--json", type=Path, help="ou garder le JSON de `coverage json` (defaut : un fichier temporaire)")
    parser.add_argument("--check", action="store_true", help="sortir avec 1 sous le plancher 'noyaux' de tests/coverage_floors.json")
    parser.add_argument("--planchers", type=Path, default=floors_module.FLOORS, help="le fichier des planchers")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="certus_kernel_cov_") as scratch:
        report = args.json or Path(scratch) / "kernel_coverage.json"
        env = environment(Path(scratch) / "coverage.data")
        failed_tests = False
        for command in commands(report):
            print("$", " ".join(command), flush=True)
            failed_tests |= run(command, cwd=ROOT, env=env).returncode != 0
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            covered, lines = physics_lines(data)
        except (OSError, ValueError, KeyError) as error:
            print(f"COUVERTURE DES NOYAUX : JSON illisible ou incomplet ({type(error).__name__}: {error})", file=sys.stderr)
            return 2

    print(f"{PREFIX} : {100 * covered / lines:.1f} % ({covered}/{lines} lignes), NUMBA_DISABLE_JIT=1, oracle + core + property + unit -m {MARKER}")
    if failed_tests:
        print("UN TEST A ECHOUE : la mesure est faite, elle n'est pas fiable avant que les tests passent", file=sys.stderr)
    status = 1 if failed_tests else 0
    if args.check:
        try:
            plancher = json.loads(args.planchers.read_text(encoding="utf-8"))["noyaux"]
        except (OSError, ValueError, KeyError) as error:
            print(f"planchers illisibles ({type(error).__name__}: {error})", file=sys.stderr)
            return 2
        below, to_raise, _missing = floors_module.check(data, plancher)
        for line in below:
            print(f"  SOUS LE PLANCHER  {line}")
        for line in to_raise:
            print(f"  {line}")
        status = 1 if below or failed_tests else 0
    return status


if __name__ == "__main__":
    raise SystemExit(main())
