"""LA VALIDATION DE CLAUDE.md §2 SUR TOUS LES COEURS, EN UNE COMMANDE.

    python scripts\\validate_parallel.py                   # toutes les etapes, tous les coeurs
    python scripts\\validate_parallel.py --only unit ui    # certaines etapes (docs = les trois controles documentaires)
    python scripts\\validate_parallel.py --workers 8       # workers de `unit` et du reste
    python scripts\\validate_parallel.py --out DOSSIER     # ou poser les journaux (defaut : dossier temporaire)
    python scripts\\validate_parallel.py --no-confirm      # ne pas rejouer en serie les echecs

🔑 LA RECETTE, MESUREE le 2026-10-18 (Windows, 16 coeurs, pytest-xdist 3.8) : environ 17 minutes au lieu de 40 en serie.

  - les controles documentaires D'ABORD, sur machine calme, et leur CODE DE SORTIE compte, pas leur phrase de synthese
    (`coherence_md.py` dit « 0 point a instruire » et sort pourtant en 1 s'il trouve une commande morte) ;
  - `tests/unit/` : `-n N --dist loadfile` (un fichier reste sur un worker : etat de classe, etat de module) ;
  - `tests/ui/` : **6 workers au plus**. A 16 l'audit d'ergonomie echoue (2 echecs, 12 erreurs « skeleton was still
    building ») et ne va pas plus vite : il attend que les fenetres aient fini de se construire, et la charge l'en empeche ;
  - le reste de `tests/`, sans `performance` : `-n N --dist loadfile` ;
  - `tests/performance/` EN SERIE, en dernier, machine calme : pytest-benchmark se coupe sous xdist, et ces tests chronometrent.

📏 CE QUE CETTE COMMANDE NE DIT PAS. La reference de CLAUDE.md §2 reste la suite complete en SERIE, « 0 failed ». Un echec
obtenu en parallele est rejoue SEUL, en serie : rouge seul, c'est un echec reel ; vert seul, c'est un artefact de charge ou
d'ordre (un test qui chronometre a la microseconde, une limite Hypothesis depassee par la premiere compilation d'un cache froid,
un audit d'interface qui n'a pas fini de se construire), signale mais qui n'invalide pas. Le verdict `VALIDATION=GO` dit donc
« aucun echec reel en parallele », pas « 0 failed en serie ». Le 2026-10-18, ces artefacts etaient une course sur des
preferences partagees entre workers, l'audit d'ergonomie a 16 workers, un test qui chronometre a la microseconde et une limite
Hypothesis depassee a froid ; un test du harnais C1 qu'il fallait mettre a jour, lui, restait rouge seul : un echec reel.

⚠️ Le premier passage apres un changement de cle du cache Numba (un fichier qui cite numba a change) recompile tout a froid :
il est plus long, et un test peut depasser sa limite une fois. Le rejeu seul le tranche ; ce n'est pas un defaut de la recette.

Sans pytest-xdist (`pip install pytest-xdist`, qui n'est pas declare dans pyproject.toml), les etapes tournent en serie, et
la commande le dit.

Le code de sortie : 0 `VALIDATION=GO`, 1 `VALIDATION=NO-GO`, 2 la commande elle-meme est mal appelee.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Au plus ce nombre de workers pour `tests/ui/` (mesure le 2026-10-18 : 6 passe, 16 echoue sans aller plus vite).
UI_WORKERS = 6

#: Au-dela, un nombre d'echecs qui ne se rejoue plus a la main : la commande ne rejoue pas, et le dit.
MAX_REPLAY = 40

PYTEST = (sys.executable, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider")
DOCS = ("coherence_md", "check_claude_md", "check_docs")
#: Les etapes, dans l'ordre de la recette.
STAGES = ("ruff", *DOCS, "oracle", "unit", "ui", "rest", "performance")


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    kind: str  # "pytest" : on lit un resume de pytest et on rejoue les echecs ; "check" : seul le code de sortie compte


@dataclass
class Result:
    stage: Stage
    returncode: int
    seconds: float
    counts: dict[str, int]
    failed: list[str]
    log: Path
    status: str = "PASS"  # PASS | ARTEFACT (echecs vert seuls) | FAIL
    persistent: list[str] = field(default_factory=list)  # les echecs qui le restent seuls, en serie
    replayed: list[str] = field(default_factory=list)  # les echecs qui ne le sont plus seuls


# =============================================================================
# Le plan
# =============================================================================


def has_xdist() -> bool:
    return importlib.util.find_spec("xdist") is not None


def build_plan(workers: int, ui_workers: int, xdist: bool, only: list[str] | None = None) -> list[Stage]:
    """Les etapes de la recette, dans l'ordre ; `only` en garde certaines (`docs` vaut les trois controles)."""
    if only:
        wanted = [name for item in only for name in (DOCS if item == "docs" else (item,))]
        unknown = [name for name in wanted if name not in STAGES]
        if unknown:
            raise ValueError(f"etape inconnue : {', '.join(unknown)} (connues : docs, {', '.join(STAGES)})")
    else:
        wanted = list(STAGES)

    def parallel(count: int) -> tuple[str, ...]:
        return ("-n", str(max(1, count)), "--dist", "loadfile") if xdist else ()

    plan = {
        "ruff": Stage("ruff", (sys.executable, "-m", "ruff", "check", "."), "check"),
        "oracle": Stage("oracle", (*PYTEST, "tests/oracle/"), "pytest"),
        "unit": Stage("unit", (*PYTEST, "tests/unit/", *parallel(workers)), "pytest"),
        "ui": Stage("ui", (*PYTEST, "tests/ui/", *parallel(min(ui_workers, workers))), "pytest"),
        "rest": Stage(
            "rest",
            (
                *PYTEST, "tests/", "--ignore=tests/oracle", "--ignore=tests/unit", "--ignore=tests/ui",
                "--ignore=tests/performance", *parallel(workers),
            ),
            "pytest",
        ),
        "performance": Stage("performance", (*PYTEST, "tests/performance"), "pytest"),
    }  # fmt: skip
    for name in DOCS:
        plan[name] = Stage(name, (sys.executable, f"scripts/{name}.py"), "check")
    return [plan[name] for name in STAGES if name in wanted]


# =============================================================================
# Lire un resume de pytest
# =============================================================================

_COUNT = re.compile(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?|warnings?|deselected)")
_FINAL = re.compile(r"\bin \d+(?:\.\d+)?s\b")


def parse_summary(text: str) -> dict[str, int]:
    """Les comptes de la derniere ligne de resume (`1 failed, 5514 passed in 507.27s`) ; {} si pytest n'en a pas rendu."""
    for line in reversed(text.splitlines()):
        if _FINAL.search(line) and _COUNT.search(line):
            counts: dict[str, int] = {}
            for number, word in _COUNT.findall(line):
                word = {"errors": "error", "warnings": "warning"}.get(word, word)
                counts[word] = counts.get(word, 0) + int(number)
            return counts
    return {}


# `FAILED fichier::test[parametres avec espaces] - message`. Les crochets sont lus en entier : un parametre peut contenir « - ».
_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+?(?:\[[^\]]*\])?)(?: - .*)?\s*$")


def failed_ids(text: str) -> list[str]:
    """Les identifiants des lignes `FAILED ...` et `ERROR ...` du court resume, sans le message, sans doublon."""
    ids = (match.group(1) for line in text.splitlines() if (match := _FAILED.match(line)))
    return list(dict.fromkeys(ids))


# =============================================================================
# Jouer une etape, rejouer ses echecs seuls
# =============================================================================


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run_stage(stage: Stage, out_dir: Path) -> Result:
    log = out_dir / f"{stage.name}.log"
    start = time.monotonic()
    with open(log, "wb") as stream:
        returncode = subprocess.run(
            stage.command, cwd=ROOT, env=_env(), stdout=stream, stderr=subprocess.STDOUT, check=False
        ).returncode
    text = log.read_text(encoding="utf-8", errors="replace")
    counts = parse_summary(text) if stage.kind == "pytest" else {}
    failed = failed_ids(text) if stage.kind == "pytest" else []
    return Result(stage, returncode, time.monotonic() - start, counts, failed, log)


def replay_alone(ids: list[str], out_dir: Path, name: str) -> list[str]:
    """Rejoue ces tests EN SERIE, sans xdist ; rend ceux qui echouent encore (aucun : tous verts seuls)."""
    log = out_dir / f"{name}_replay.log"
    with open(log, "wb") as stream:
        returncode = subprocess.run(
            (*PYTEST, *ids), cwd=ROOT, env=_env(), stdout=stream, stderr=subprocess.STDOUT, check=False
        ).returncode
    if returncode == 0:
        return []
    still = failed_ids(log.read_text(encoding="utf-8", errors="replace"))
    return still or list(ids)  # un code non nul sans identifiant lisible : on ne declare rien de vert


def execute(
    plan: list[Stage],
    out_dir: Path,
    *,
    confirm: bool = True,
    run: Callable[[Stage, Path], Result] = run_stage,
    replay: Callable[[list[str], Path, str], list[str]] = replay_alone,
    show: Callable[[str], None] = print,
) -> list[Result]:
    results = []
    for stage in plan:
        result = run(stage, out_dir)
        if result.returncode == 0:
            result.status = "PASS"
        elif confirm and stage.kind == "pytest" and 0 < len(result.failed) <= MAX_REPLAY:
            show(f"  {stage.name} : {len(result.failed)} echec(s) en parallele, rejeu seul en serie...")
            result.persistent = replay(result.failed, out_dir, stage.name)
            result.replayed = [i for i in result.failed if i not in result.persistent]
            result.status = "FAIL" if result.persistent else "ARTEFACT"
        else:
            result.status = "FAIL"
        show(f"  {stage.name:<16s}{result.status:<10s}{_clock(result.seconds)}  {_counts(result.counts)}")
        results.append(result)
    return results


# =============================================================================
# Le verdict
# =============================================================================


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{n} {word}" for word, n in counts.items() if word != "warning")


def verdict(results: list[Result]) -> bool:
    """Vrai quand aucune etape n'a d'echec reel : toutes vertes, ou rouges seulement en parallele."""
    return bool(results) and all(r.status != "FAIL" for r in results)


def report(results: list[Result]) -> list[str]:
    lines = []
    for r in results:
        if r.status == "ARTEFACT":
            lines.append(f"ARTEFACT de charge ou d'ordre ({r.stage.name}), verts seuls en serie :")
            lines += [f"    {i}" for i in r.replayed]
        elif r.status == "FAIL":
            if r.persistent:
                lines.append(f"ECHEC REEL ({r.stage.name}), rouge aussi seul en serie :")
                lines += [f"    {i}" for i in r.persistent]
            else:
                lines.append(f"ECHEC ({r.stage.name}), code {r.returncode}, non rejoue : lire {r.log}")
    lines.append("VALIDATION=GO" if verdict(results) else "VALIDATION=NO-GO")
    lines.append("La reference de CLAUDE.md section 2 reste la suite complete en serie.")
    return lines


# =============================================================================
# La commande
# =============================================================================


def _git(*args: str) -> str:
    done = subprocess.run(("git", "-c", "core.longpaths=true", *args), cwd=ROOT, capture_output=True, text=True, check=False)
    return done.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):  # une console cp1252 ne doit pas pouvoir perdre un verdict sur un print()
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", metavar="ETAPE", help=f"parmi : docs, {', '.join(STAGES)}")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1, help="workers de unit et du reste (defaut : tous les coeurs)")
    parser.add_argument("--ui-workers", type=int, default=UI_WORKERS, help=f"workers de ui (defaut : {UI_WORKERS}, jamais plus que --workers)")
    parser.add_argument("--out", type=Path, help="dossier des journaux (defaut : un dossier temporaire)")
    parser.add_argument("--no-confirm", action="store_true", help="ne pas rejouer seuls, en serie, les tests en echec")
    args = parser.parse_args(argv)

    xdist = has_xdist()
    try:
        plan = build_plan(args.workers, args.ui_workers, xdist, args.only)
    except ValueError as error:
        parser.error(str(error))
    out_dir = args.out or Path(tempfile.mkdtemp(prefix="certus_validation_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"VALIDATION PARALLELE -- {_git('rev-parse', '--short', 'HEAD')}, {len(_git('status', '--porcelain', '--untracked-files=no').splitlines())} fichier(s) suivi(s) modifie(s)")
    print(f"  python {sys.version.split()[0]}, {args.workers} worker(s), ui {min(args.ui_workers, args.workers)}, journaux : {out_dir}")
    if not xdist:
        print("  pytest-xdist est absent : unit, ui et rest tournent EN SERIE (pip install pytest-xdist)")
    results = execute(plan, out_dir, confirm=not args.no_confirm)
    print()
    lines = report(results)
    summary = "\n".join(lines)
    (out_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    return 0 if verdict(results) else 1


if __name__ == "__main__":
    sys.exit(main())
