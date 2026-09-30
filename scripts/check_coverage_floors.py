"""LE CLIQUET DE COUVERTURE : AUCUN PAQUET NE DESCEND SOUS SON PLANCHER.

    python scripts\\check_coverage_floors.py cov.json
    python scripts\\check_coverage_floors.py cov.json --noyaux cov_noyaux.json

`cov.json` sort de `coverage json` apres la suite ordinaire (`pytest --cov=certus`), `cov_noyaux.json`
apres `NUMBA_DISABLE_JIT=1 pytest tests/oracle tests/core --cov=certus` : sans elle, Numba compile les
noyaux et `coverage` ne voit pas une ligne de `certus/physics/` (mesure du 2026-09-30 : 20,3 % avec la
compilation, 45,9 % sans).

🔑 Ce que le cliquet fait, et ne fait pas. Un plancher par paquet, dans `tests/coverage_floors.json` :
la commande echoue (code 1) quand un paquet mesure MOINS que son plancher. Elle ne fait jamais monter un
plancher toute seule : quand un paquet depasse le sien de plus de trois points, elle le DIT (« a relever »),
et la personne qui releve le plancher le fait dans un commit, comme le cliquet du lint ne perd une regle
qu'a la main. Les planchers sont ceux de la mesure du jour, moins un point : ils protegent ce qui existe,
ils ne fixent pas un objectif (les objectifs sont ceux du plan, `scripts/metrics.py`).

⚠️ Un pourcentage de LIGNES (`covered_lines / num_statements`), jamais celui du fichier `coverage` qui
melange les branches.

Le code de sortie : 0 aucun paquet sous son plancher, 1 au moins un, 2 un fichier illisible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOORS = ROOT / "tests" / "coverage_floors.json"

#: A partir de combien de points au-dessus du plancher on suggere de le relever.
RAISE_MARGIN = 3.0


def coverage_by_prefix(report: dict, prefixes: list[str]) -> dict[str, tuple[int, int] | None]:
    """{prefixe: (lignes couvertes, lignes) ou None s'il n'y a aucun fichier} d'un JSON de `coverage json`."""
    files = {name.replace("\\", "/"): v["summary"] for name, v in report["files"].items()}
    out: dict[str, tuple[int, int] | None] = {}
    for prefix in prefixes:
        chosen = [s for name, s in files.items() if name.startswith(prefix)]
        lines = sum(s["num_statements"] for s in chosen)
        out[prefix] = (sum(s["covered_lines"] for s in chosen), lines) if lines else None
    return out


def check(report: dict, floors: dict[str, float]) -> tuple[list[str], list[str], list[str]]:
    """(paquets sous leur plancher, paquets a relever, paquets sans fichier) pour un rapport et ses planchers."""
    below, to_raise, missing = [], [], []
    measured = coverage_by_prefix(report, list(floors))
    for prefix, floor in floors.items():
        found = measured[prefix]
        if found is None:
            missing.append(prefix)
            continue
        covered, lines = found
        percent = 100 * covered / lines
        if percent < floor:
            below.append(f"{prefix}: {percent:.1f} % < plancher {floor:.1f} % ({covered}/{lines} lignes)")
        elif percent - floor > RAISE_MARGIN:
            to_raise.append(f"{prefix}: {percent:.1f} % pour un plancher de {floor:.1f} % : a relever")
    return below, to_raise, missing


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Aucun paquet ne descend sous son plancher de couverture.")
    parser.add_argument("couverture", type=Path, help="JSON de `coverage json` de la suite ordinaire")
    parser.add_argument("--noyaux", type=Path, help="JSON pris avec NUMBA_DISABLE_JIT=1 (oracle + core)")
    parser.add_argument("--planchers", type=Path, default=FLOORS, help="le fichier des planchers")
    args = parser.parse_args(argv)

    try:
        floors = _load(args.planchers)
        runs = [("lignes", args.couverture, floors["lignes"])]
        if args.noyaux:
            runs.append(("noyaux", args.noyaux, floors["noyaux"]))
        results = [(name, *check(_load(path), plancher)) for name, path, plancher in runs]
    except (OSError, ValueError, KeyError) as exc:
        print(f"COUVERTURE : fichier illisible ou incomplet ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2

    failed = False
    for name, below, to_raise, missing in results:
        print(f"[{name}] " + ("aucun paquet sous son plancher" if not below else f"{len(below)} paquet(s) sous leur plancher"))
        for line in below:
            print(f"  SOUS LE PLANCHER  {line}")
        if below:
            print(f"  (les planchers valent pour : {floors.get('_mesure_' + name, '?')})")
        for line in to_raise:
            print(f"  {line}")
        for prefix in missing:
            print(f"  sans fichier      {prefix} (aucune ligne mesuree : plancher ignore)")
        failed = failed or bool(below)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
