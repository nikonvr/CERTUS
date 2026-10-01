"""LA LISTE DES TESTS LENTS : `pytest -m "not slow"` est le palier rapide (audit v2, plan S3.3).

    pytest tests/unit -q --no-cov --durations=0 --durations-min=0.5 > unit.out
    python scripts/refresh_slow_tests.py --suite tests/unit unit.out --suite tests/ui ui.out            dit ce que la liste deviendrait
    python scripts/refresh_slow_tests.py --suite tests/unit unit.out --write                           la reecrit (tests/slow_tests.json)

POURQUOI UNE LISTE DE DONNEES ET PAS UN MARQUEUR DANS CHAQUE FICHIER. 156 fonctions de `tests/unit` sur 4 200 prennent 85 % des 15 min 39 de la suite
(mesure a chaud du 2026-10-01) ; poser `@pytest.mark.slow` dans autant de fichiers, puis le tenir a jour a chaque test qui ralentit ou accelere, ne se
ferait pas. `tests/conftest.py` lit `tests/slow_tests.json` a la collecte et marque `slow` les fonctions listees (tous leurs parametres : la duree d'un test
parametre est celle du pire de ses exemplaires). Ce script refait la liste a partir d'un journal de `--durations`.

CE QU'IL CALCULE. La duree d'un exemplaire est la SOMME de ses phases (setup + call + teardown : un test dont la fenetre coute 3 s a construire est lent
meme si son appel dure 10 ms). La duree d'une fonction est celle du pire de ses exemplaires. Une fonction est lente a partir de `--threshold` secondes
(1 par defaut). `--durations-min` du journal doit etre <= au seuil, sinon des phases manquent et la somme est sous-estimee.

CE QU'IL NE FAIT PAS. Il ne lance pas les tests. Pour chaque `--suite DOSSIER JOURNAL`, les entrees de la liste sous DOSSIER sont REMPLACEES par celles du
journal (un test devenu rapide sort de la liste) ; les entrees des autres dossiers sont gardees. Le journal doit donc venir d'une execution COMPLETE du dossier.

Le code de sortie : 0 la liste est ecrite ou affichee, 2 un journal ne contient aucune duree.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOW_TESTS = ROOT / "tests" / "slow_tests.json"
THRESHOLD = 1.0

DURATION = re.compile(r"^\s*(?P<seconds>\d+(?:\.\d+)?)s (?P<phase>call|setup|teardown)\s+(?P<node>\S+)")


def phases_by_instance(log: str) -> dict[str, float]:
    """node id (parameters included) -> the sum of its phases listed in a pytest `--durations` log."""
    total: dict[str, float] = defaultdict(float)
    for line in log.splitlines():
        found = DURATION.match(line)
        if found:
            total[found["node"]] += float(found["seconds"])
    return dict(total)


def worst_by_function(instances: dict[str, float]) -> dict[str, float]:
    """node id without parameters -> the duration of the slowest of its instances."""
    worst: dict[str, float] = {}
    for node, seconds in instances.items():
        function = node.split("[", 1)[0]
        worst[function] = max(worst.get(function, 0.0), seconds)
    return worst


def slow_functions(log: str, threshold: float = THRESHOLD) -> dict[str, float]:
    return {node: round(seconds, 1) for node, seconds in sorted(worst_by_function(phases_by_instance(log)).items()) if seconds >= threshold}


def merge(existing: dict[str, float], measured: dict[str, dict[str, float]]) -> dict[str, float]:
    """The new list: the entries of the folders that were measured are replaced by the measure, the others are kept."""
    merged = {node: seconds for node, seconds in existing.items() if not any(node.startswith(folder.rstrip("/") + "/") for folder in measured)}
    for folder_list in measured.values():
        merged.update(folder_list)
    return dict(sorted(merged.items()))


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Refait tests/slow_tests.json a partir de journaux de pytest --durations.")
    parser.add_argument("--suite", nargs=2, action="append", metavar=("DOSSIER", "JOURNAL"), required=True, help="un dossier de tests et le journal de son execution complete")
    parser.add_argument("--threshold", type=float, default=THRESHOLD, help="secondes a partir desquelles une fonction est lente")
    parser.add_argument("--liste", type=Path, default=SLOW_TESTS, help="le fichier de la liste")
    parser.add_argument("--write", action="store_true", help="ecrire la liste (sinon, seulement la comparer)")
    args = parser.parse_args(argv)

    measured: dict[str, dict[str, float]] = {}
    for folder, log in args.suite:
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        if not phases_by_instance(text):
            print(f"{log} : aucune duree (pytest --durations=0 --durations-min=...)", file=sys.stderr)
            return 2
        measured[folder.replace("\\", "/")] = {node: seconds for node, seconds in slow_functions(text, args.threshold).items() if node.startswith(folder.replace("\\", "/").rstrip("/") + "/")}

    try:
        existing = json.loads(args.liste.read_text(encoding="utf-8"))["tests"]
    except (OSError, ValueError, KeyError):
        existing = {}
    merged = merge(existing, measured)
    gone = sorted(set(existing) - set(merged))
    new = sorted(set(merged) - set(existing))
    print(f"liste : {len(existing)} -> {len(merged)} fonctions lentes (seuil {args.threshold:g} s) ; {len(new)} nouvelles, {len(gone)} sorties")
    for node in new[:20]:
        print(f"  + {merged[node]:6.1f} s  {node}")
    for node in gone[:20]:
        print(f"  - {existing[node]:6.1f} s  {node}")
    if args.write:
        data = {
            "_commentaire": (
                "Les fonctions de test qui prennent le plus de temps (setup + call + teardown du pire de leurs exemplaires). tests/conftest.py les marque `slow` a la "
                "collecte : `pytest -m \"not slow\"` est le palier rapide. Refaite par scripts/refresh_slow_tests.py a partir d'un journal de `pytest --durations`."
            ),
            "seuil_secondes": args.threshold,
            "tests": merged,
        }
        args.liste.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"ecrite : {args.liste}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
