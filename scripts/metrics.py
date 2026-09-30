"""LES INDICATEURS DU PLAN D'AMELIORATION, EN UNE COMMANDE.

    python scripts\\metrics.py                       # le tableau, mesure ici et maintenant
    python scripts\\metrics.py --rapide              # le statique seulement (quelques secondes)
    python scripts\\metrics.py --json mesures.json   # et le meme tableau pour une machine
    python scripts\\metrics.py --couverture cov.json --couverture-noyaux noyaux.json --ouverture

Le plan de huit semaines de l'audit du 2026-09-30 commence et finit chaque semaine par ce
tableau : sans lui, « ca va mieux » est un sentiment. La colonne `base` porte les chiffres de
l'audit (sur 78fda46), la colonne `cible` ceux de la semaine 8 ; `--base FICHIER.json` compare
a une mesure precedente de ce script au lieu de l'audit.

🔴 **Un chiffre qu'on n'a pas mesure s'ecrit `n/a`, jamais 0.** Un indicateur absent (pas de
`gh`, pas de fichier de couverture, `ruff` introuvable) est dit absent, avec sa raison en bas
du tableau ; le zero est une mesure, et une mesure fausse est pire qu'un trou.

📏 Ce que chaque ligne mesure EXACTEMENT :

  - `arch.*` et `tests.*` (statique) : l'arbre des fichiers `.py` suivis par git, lu a l'AST.
    Une arete d'import est l'import, au niveau du module, d'un module par un autre ; elle est
    « montante » quand la couche qui importe est plus basse que celle qu'elle importe
    (domain < physics < core = utils < metal = spline < workers < ui). Un import dans une
    fonction n'est ni une arete ni un cycle.
  - `lint.*` : les violations que `extend-ignore` MASQUE, donc `ruff --isolated`, les huit
    familles de `pyproject.toml`, `E501` exclue.
  - `tests.oracle|unit|ui|reste` : ce que pytest COLLECTE (`--collect-only`), pas ce qui passe ;
    la validation complete est `CLAUDE.md` section 2.
  - `ui.boutons_sous_4_5` : le contraste WCAG du texte des six variantes de bouton plein, dans
    les deux themes (douze boutons), lu dans les feuilles de style que `CertusTheme` rend.
  - `couverture.*` : lues dans un JSON de `coverage json` ; le pourcentage est celui des LIGNES
    (`covered_lines / num_statements`), jamais celui du fichier qui melange les branches.
  - `pub.*` : `git` (commits sans equivalent en amont) et `gh` (executions de la CI sur HEAD).

Ce n'est pas une garde : le code de sortie est 0 quoi qu'il mesure. Les cliquets qui refusent
une regression sont des tests (`tests/oracle/test_lint_debt_ratchet.py`, le garde d'architecture).
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: (cle, libelle, base du 2026-09-30, cible de la semaine 8, sens : "min" = plus bas est mieux).
#: Une ligne sans cible est une information, pas un objectif.
INDICATEURS: tuple[tuple[str, str, float | None, float | None, str | None], ...] = (
    ("tests.oracle", "tests collectes : oracle", 1086, None, None),
    ("tests.unit", "tests collectes : unit", 2808, None, None),
    ("tests.ui", "tests collectes : ui", 798, None, None),
    ("tests.reste", "tests collectes : le reste de tests/", 347, None, None),
    ("couverture.lignes", "couverture des lignes de certus/ (%)", 46.8, 55.0, "max"),
    ("couverture.noyaux", "couverture de certus/physics, JIT coupe (%)", 45.9, 70.0, "max"),
    ("tests.modules_sans_test", "modules certus/ qu'aucun test ne nomme", 69, 40, "min"),
    ("couverture.modules_faibles", "modules certus/ couverts a moins de 15 % (>= 50 lignes)", 13, 8, "min"),
    ("tests.sans_assertion", "tests sans aucune assertion", 57, 0, "min"),
    ("lint.violations", "dette de lint masquee : violations", 3319, 1500, "min"),
    ("lint.regles", "dette de lint masquee : regles", 32, 24, "min"),
    ("arch.fonctions_gt300", "fonctions de plus de 300 lignes", 52, 35, "min"),
    ("arch.fonctions_cc_gt60", "fonctions de complexite > 60", 20, 12, "min"),
    ("arch.fichiers_gt1500", "fichiers certus/ de plus de 1 500 lignes", 23, 18, "min"),
    ("arch.cycles", "cycles d'imports", 8, 3, "min"),
    ("arch.aretes_montantes", "aretes d'import montantes entre couches", 47, 20, "min"),
    ("arch.except_avales", "except larges avales", 74, 30, "min"),
    ("arch.annotees_pct", "fonctions de certus/ annotees (%)", 72, None, None),
    ("arch.any", "occurrences de `Any` dans certus/", 1510, None, None),
    ("arch.fichiers_py", "fichiers .py suivis", 777, None, None),
    ("arch.lignes_py", "lignes de .py suivis", 269193, None, None),
    ("ui.boutons_sous_4_5", "boutons pleins sous 4,5:1 (sur 12)", 5, 0, "min"),
    ("ouverture.hub", "ouverture du hub, hors ecran (s)", 3.02, 1.0, "min"),
    ("ouverture.modules_max", "ouverture du module le plus lent (s)", 3.9, 2.5, "min"),
    ("gel.taille_mo", "dossier gele dist/CERTUS_HUB (Mo)", 443, 300, "min"),
    ("pub.commits_locaux", "commits sans equivalent en amont", 53, 0, "min"),
    ("pub.ci_rouge", "executions de CI rouges sur HEAD", None, 0, "min"),
)

COUCHES = {
    "certus.domain": 0, "certus.physics": 1, "certus.core": 2, "certus.utils": 2,
    "certus.metal": 3, "certus.spline": 3, "certus.workers": 4, "certus.ui": 5,
}  # fmt: skip
QT = ("PyQt6", "PyQt5", "PySide", "pyqtgraph")

#: Les familles que `pyproject.toml` selectionne ; `extend-ignore` en masque une partie.
FAMILLES_LINT = "E,F,I,B,UP,RUF,PT,PERF"

SUITES = {
    "oracle": ["tests/oracle"],
    "unit": ["tests/unit"],
    "ui": ["tests/ui"],
    "reste": ["tests", "--ignore=tests/oracle", "--ignore=tests/unit", "--ignore=tests/ui"],
}

MODULES_OUVERTS = {
    "CERTUS_HUB": ("CERTUS_HUB", "CertusHub"),
    "CERTUS_DESIGN": ("certus.ui.certus_design_ui", "CertusDesignApp"),
    "CERTUS_STRAT": ("certus.ui.certus_strat_ui", "CertusStratApp"),
    "CERTUS_INDEX": ("certus.ui.certus_index_ui", "CertusIndexApp"),
    "CERTUS_INDEX_SPLINE": ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    "CERTUS_FIELD": ("certus.ui.certus_field_ui", "CertusFieldApp"),
    "CERTUS_RE": ("CERTUS_RE", "CertusREApp"),
    "CERTUS_METAL_SINGLE": ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    "CERTUS_METAL_BILAYER": ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
}


# =============================================================================
# Les sources
# =============================================================================


def _git(racine: Path, *args: str) -> str | None:
    """La sortie de `git`, ou None : jamais une exception, jamais un verrou pris."""
    try:
        r = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def fichiers_suivis(racine: Path, *motifs: str) -> list[str]:
    """Les fichiers suivis par git qui repondent aux motifs ; hors d'un depot git, ceux du disque."""
    if (racine / ".git").exists():
        try:
            sortie = subprocess.run(
                ["git", "--no-optional-locks", "ls-files", "-z", *motifs],
                cwd=racine, capture_output=True, check=True, timeout=60,
            ).stdout  # fmt: skip
            return sorted(f for f in sortie.decode("utf-8", "replace").split("\0") if f)
        except (OSError, subprocess.SubprocessError):
            pass
    ignores = {".git", "__pycache__", "node_modules", ".venv", "build", "dist"}
    trouves = {
        p.relative_to(racine).as_posix()
        for motif in motifs
        for p in racine.rglob(motif)
        if p.is_file() and not ignores & set(p.relative_to(racine).parts)
    }
    return sorted(trouves)


def lire(racine: Path, fichiers: list[str]) -> dict[str, str]:
    """Le texte de chaque fichier ; un fichier illisible est ignore, pas devine."""
    sources = {}
    for f in fichiers:
        try:
            sources[f] = (racine / f).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
    return sources


# =============================================================================
# Architecture (statique)
# =============================================================================


def _nom_module(f: str) -> str:
    p = f[:-3].replace("/", ".")
    return p[:-9] if p.endswith(".__init__") else p


def _imports(f: str, noeuds: list[ast.stmt]) -> list[str]:
    """Les modules que `noeuds` importent, les imports relatifs resolus contre `f`."""
    sortie: list[str] = []
    for node in noeuds:
        if isinstance(node, ast.Import):
            sortie += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = _nom_module(f).split(".")
                coupe = node.level - 1 if f.endswith("__init__.py") else node.level
                ancre = parts[: len(parts) - coupe] if coupe else parts
                base = ".".join(ancre + ([node.module] if node.module else []))
            sortie.append(base)
            sortie += [f"{base}.{a.name}" for a in node.names]
    return sortie


def _imports_de_niveau_module(arbre: ast.Module) -> list[ast.stmt]:
    """Les imports qui s'executent a l'import du module : ni dans une fonction, ni dans une classe."""
    trouves: list[ast.stmt] = []

    def visiter(noeuds: list[ast.stmt]) -> None:
        for n in noeuds:
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if isinstance(n, ast.Import | ast.ImportFrom):
                trouves.append(n)
            for champ in ("body", "orelse", "finalbody"):
                sous = getattr(n, champ, None)
                if isinstance(sous, list):
                    visiter(sous)
            if isinstance(n, ast.Try):
                for h in n.handlers:
                    visiter(h.body)

    visiter(arbre.body)
    return trouves


def graphe_imports(arbres: dict[str, ast.Module]) -> tuple[dict[str, set[str]], dict[str, str]]:
    """(module -> modules qu'il importe au niveau module, module -> fichier)."""
    modules = {_nom_module(f): f for f in arbres}

    def resoudre(nom: str) -> str:
        candidat = nom
        while candidat and candidat not in modules:
            candidat = candidat.rsplit(".", 1)[0] if "." in candidat else ""
        return candidat

    graphe: dict[str, set[str]] = collections.defaultdict(set)
    for f, arbre in arbres.items():
        m = _nom_module(f)
        for noeud in _imports_de_niveau_module(arbre):
            for nom in _imports(f, [noeud]):
                if nom.startswith(QT):
                    continue
                cible = resoudre(nom)
                if cible and cible != m:
                    graphe[m].add(cible)
    return graphe, modules


def _couche(f: str | None) -> str | None:
    parts = (f or "").split("/")
    if parts[0] == "certus" and len(parts) > 1 and f"certus.{parts[1]}" in COUCHES:
        return f"certus.{parts[1]}"
    return None


def aretes_montantes(graphe: dict[str, set[str]], modules: dict[str, str]) -> collections.Counter:
    """Les imports d'une couche haute par une couche plus basse, comptes par paire de couches."""
    n: collections.Counter = collections.Counter()
    for a, cibles in graphe.items():
        la = _couche(modules.get(a))
        for b in cibles:
            lb = _couche(modules.get(b))
            if la in COUCHES and lb in COUCHES and la != lb and COUCHES[la] < COUCHES[lb]:
                n[(la, lb)] += 1
    return n


def cycles(graphe: dict[str, set[str]], modules: dict[str, str]) -> list[list[str]]:
    """Les composantes fortement connexes de plus d'un module dans `certus*` (Tarjan, sans recursion)."""
    noeuds = [m for m in modules if m.startswith("certus")]
    suivants = {v: [w for w in graphe.get(v, ()) if w in modules and w.startswith("certus")] for v in noeuds}
    index: dict[str, int] = {}
    bas: dict[str, int] = {}
    sur_pile: set[str] = set()
    pile: list[str] = []
    composantes: list[list[str]] = []
    compteur = 0
    for depart in noeuds:
        if depart in index:
            continue
        index[depart] = bas[depart] = compteur
        compteur += 1
        pile.append(depart)
        sur_pile.add(depart)
        travail = [(depart, iter(suivants[depart]))]
        while travail:
            v, voisins = travail[-1]
            descend = False
            for w in voisins:
                if w not in index:
                    index[w] = bas[w] = compteur
                    compteur += 1
                    pile.append(w)
                    sur_pile.add(w)
                    travail.append((w, iter(suivants[w])))
                    descend = True
                    break
                if w in sur_pile:
                    bas[v] = min(bas[v], index[w])
            if descend:
                continue
            travail.pop()
            if travail:
                parent = travail[-1][0]
                bas[parent] = min(bas[parent], bas[v])
            if bas[v] == index[v]:
                composante = []
                while True:
                    w = pile.pop()
                    sur_pile.discard(w)
                    composante.append(w)
                    if w == v:
                        break
                if len(composante) > 1:
                    composantes.append(composante)
    return composantes


class _Complexite(ast.NodeVisitor):
    """La complexite cyclomatique d'une fonction : 1 + ses embranchements."""

    def __init__(self) -> None:
        self.n = 1

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(
            node,
            ast.If | ast.For | ast.While | ast.AsyncFor | ast.ExceptHandler | ast.IfExp | ast.comprehension | ast.Assert,
        ):
            self.n += 1
        if isinstance(node, ast.BoolOp):
            self.n += len(node.values) - 1
        super().generic_visit(node)


def fonctions(arbres: dict[str, ast.Module]) -> list[tuple[int, int, str, str]]:
    """(lignes, complexite, fichier, nom) de chaque fonction de `certus*`."""
    sortie = []
    for f, arbre in arbres.items():
        if not f.startswith("certus"):
            continue
        for node in ast.walk(arbre):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                c = _Complexite()
                c.visit(node)
                sortie.append((getattr(node, "end_lineno", node.lineno) - node.lineno + 1, c.n, f, node.name))
    return sortie


def except_avales(arbres: dict[str, ast.Module]) -> int:
    """Les `except` larges (nu, Exception, BaseException) dont le corps ne fait rien."""
    n = 0
    for f, arbre in arbres.items():
        if not f.startswith("certus"):
            continue
        for node in ast.walk(arbre):
            if not isinstance(node, ast.ExceptHandler):
                continue
            t = node.type
            large = t is None or (isinstance(t, ast.Name) and t.id in ("Exception", "BaseException"))
            muet = all(
                isinstance(b, ast.Pass | ast.Continue)
                or (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))
                for b in node.body
            )
            n += large and muet
    return n


def architecture(sources: dict[str, str]) -> tuple[dict[str, int], dict[str, Any]]:
    """Les mesures `arch.*` de `sources` (chemin -> texte) et leur detail."""
    arbres: dict[str, ast.Module] = {}
    for f, texte in sources.items():
        try:
            arbres[f] = ast.parse(texte, filename=f)
        except (SyntaxError, ValueError):
            continue
    graphe, modules = graphe_imports(arbres)
    montantes = aretes_montantes(graphe, modules)
    fonctions_certus = fonctions(arbres)

    total = annotees = anys = 0
    for f, arbre in arbres.items():
        if not f.startswith("certus"):
            continue
        for node in ast.walk(arbre):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                total += 1
                args = [a for a in node.args.args if a.arg not in ("self", "cls")]
                annotees += node.returns is not None and all(a.annotation is not None for a in args)
        anys += len(re.findall(r"\bAny\b", sources[f]))

    mesures = {
        "arch.fichiers_py": len(sources),
        "arch.lignes_py": sum(len(t.splitlines()) for t in sources.values()),
        "arch.fonctions_gt300": sum(1 for lignes, *_ in fonctions_certus if lignes > 300),
        "arch.fonctions_cc_gt60": sum(1 for _, cc, *_ in fonctions_certus if cc > 60),
        "arch.fichiers_gt1500": sum(1 for f, t in sources.items() if f.startswith("certus") and len(t.splitlines()) > 1500),
        "arch.cycles": len(cycles(graphe, modules)),
        "arch.aretes_montantes": sum(montantes.values()),
        "arch.except_avales": except_avales(arbres),
        "arch.annotees_pct": round(100 * annotees / max(total, 1)),
        "arch.any": anys,
    }
    detail = {"aretes_montantes": {f"{a} -> {b}": n for (a, b), n in sorted(montantes.items(), key=lambda kv: -kv[1])}}
    return mesures, detail


# =============================================================================
# Tests (statique)
# =============================================================================

_APPELS_ASSERTION = frozenset((
    "raises", "warns", "approx", "fail", "assert_allclose", "assert_array_equal", "assert_almost_equal",
    "assert_equal", "assertEqual", "assertTrue", "assertFalse", "assertRaises", "assert_called",
    "assert_called_once", "assert_called_with", "assert_called_once_with", "assert_not_called",
    "assert_any_call", "check", "assert_array_almost_equal", "assert_array_less", "given",
))  # fmt: skip
_PREFIXES_ASSERTION = ("assert", "_assert", "check_", "_check", "verify", "_verify", "expect")
_CONTEXTES_ASSERTION = frozenset(("raises", "warns", "assertRaises", "assertWarns", "catch_warnings"))


def _nom_appel(appel: ast.Call) -> str:
    f = appel.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")


def a_une_assertion(
    fonction: ast.FunctionDef | ast.AsyncFunctionDef,
    locales: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] | None = None,
    _profondeur: int = 3,
) -> bool:
    """La fonction affirme-t-elle quelque chose : `assert`, `pytest.raises`, un `assert_*`, un assistant ?

    Un assistant DEFINI DANS LE MEME FICHIER (`locales`) compte pour ce qu'il fait, pas pour son nom : le
    2026-09-30, quatre fichiers avaient un `check()` qui comptait PASS et FAIL sans jamais affirmer, et le
    nom suffisait a faire croire que les 25 tests qui l'appellent affirmaient. Un assistant importe, dont on
    ne lit pas le corps, reste juge sur son nom.
    """
    locales = locales or {}
    for n in ast.walk(fonction):
        if isinstance(n, ast.Assert):
            return True
        if isinstance(n, ast.Call):
            nom = _nom_appel(n)
            if nom in locales and locales[nom] is not fonction:
                if _profondeur > 0 and a_une_assertion(locales[nom], locales, _profondeur - 1):
                    return True
                continue
            if nom in _APPELS_ASSERTION or nom.startswith(_PREFIXES_ASSERTION):
                return True
        if isinstance(n, ast.With):
            for item in n.items:
                if isinstance(item.context_expr, ast.Call) and _nom_appel(item.context_expr) in _CONTEXTES_ASSERTION:
                    return True
    return False


def tests_statiques(tests: dict[str, str], modules_certus: list[str]) -> dict[str, int]:
    """Les mesures `tests.*` : fonctions de test, sans assertion, modules que aucun test ne nomme."""
    collectables: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, dict[str, Any]]] = []
    for f, texte in tests.items():
        nom = posixpath.basename(f)
        if not (nom.startswith("test_") or nom.endswith("_test.py")):
            continue
        try:
            arbre = ast.parse(texte)
        except (SyntaxError, ValueError):
            continue
        locales = {n.name: n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
        for node in ast.walk(arbre):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                collectables += [
                    (b, locales)
                    for b in node.body
                    if isinstance(b, ast.FunctionDef | ast.AsyncFunctionDef) and b.name.startswith("test")
                ]
        collectables += [
            (n, locales)
            for n in arbre.body
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test")
        ]

    # Un module est « nomme » quand son nom apparait comme mot entier dans un fichier de tests.
    mots = set(re.findall(r"\w+", "\n".join(tests.values())))
    modules = [posixpath.basename(f)[:-3] for f in modules_certus if posixpath.basename(f) != "__init__.py"]
    return {
        "tests.fichiers": len(tests),
        "tests.fonctions": len(collectables),
        "tests.sans_assertion": sum(1 for fn, locales in collectables if not a_une_assertion(fn, locales)),
        "tests.modules": len(modules),
        "tests.modules_sans_test": sum(1 for m in modules if m not in mots),
    }


# =============================================================================
# Ce qui demande un programme externe : ruff, pytest, Qt, git, gh
# =============================================================================


def lire_statistiques_ruff(texte: str) -> tuple[int, int]:
    """(violations, regles distinctes) d'une sortie `ruff check --statistics`."""
    total = 0
    regles = set()
    for ligne in texte.splitlines():
        m = re.match(r"\s*(\d+)\s+([A-Z]+\d+)\b", ligne)
        if m:
            total += int(m.group(1))
            regles.add(m.group(2))
    return total, len(regles)


def _commande_ruff() -> list[str] | None:
    essai = [sys.executable, "-m", "ruff"]
    try:
        if subprocess.run([*essai, "--version"], capture_output=True, timeout=60).returncode == 0:
            return essai
    except (OSError, subprocess.SubprocessError):
        pass
    trouve = shutil.which("ruff")
    return [trouve] if trouve else None


def lint(racine: Path) -> tuple[dict[str, int | None], dict[str, str]]:
    """La dette que `extend-ignore` masque : `ruff --isolated`, les familles de pyproject, E501 exclue."""
    cles = ("lint.violations", "lint.regles")
    commande = _commande_ruff()
    if commande is None:
        return dict.fromkeys(cles), dict.fromkeys(cles, "ruff introuvable")
    try:
        r = subprocess.run(
            [*commande, "check", ".", "--isolated", "--select", FAMILLES_LINT, "--ignore", "E501",
             "--line-length", "120", "--target-version", "py314", "--statistics"],
            cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        return dict.fromkeys(cles), dict.fromkeys(cles, f"ruff n'a pas repondu ({type(exc).__name__})")
    violations, regles = lire_statistiques_ruff(r.stdout)
    if not violations and r.returncode not in (0, 1):
        return dict.fromkeys(cles), dict.fromkeys(cles, f"ruff a echoue (code {r.returncode})")
    return {"lint.violations": violations, "lint.regles": regles}, {}


def contraste(a: str, b: str) -> float:
    """Le rapport de contraste WCAG de deux couleurs `#rrggbb` (4,5 : le seuil AA du texte normal)."""

    def luminance(h: str) -> float:
        h = h.lstrip("#")[:6]
        canaux = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


_COULEURS_DES_BOUTONS = r"""
import json, os, re, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, sys.argv[1])
from certus.core.certus_core import ensure_numba_cache_dir
ensure_numba_cache_dir()
from certus.ui.certus_theme import CertusTheme
sortie = []
for mode in ("light", "dark"):
    CertusTheme.configure(mode)
    for variante in ("primary", "secondary", "info", "success", "warning", "danger"):
        base = CertusTheme.get_button_style(variante).split("QPushButton:hover")[0]
        fond = re.search(r"background-color:\s*(#[0-9a-fA-F]{6})", base).group(1)
        texte = re.search(r"[^-]color:\s*(#[0-9a-fA-F]{6})", base).group(1)
        sortie.append([mode, variante, texte, fond])
print("@@" + json.dumps(sortie), flush=True)
"""


def _environnement_qt() -> dict[str, str]:
    config = Path(tempfile.gettempdir()) / "certus_metrics_config"
    config.mkdir(exist_ok=True)
    return {**os.environ, "QT_QPA_PLATFORM": "offscreen", "CERTUS_CONFIG_DIR": str(config)}


def boutons(racine: Path) -> tuple[dict[str, int | None], dict[str, str]]:
    """Combien des douze boutons pleins (six variantes, deux themes) ont un texte sous 4,5:1."""
    cle = "ui.boutons_sous_4_5"
    try:
        r = subprocess.run(
            [sys.executable, "-c", _COULEURS_DES_BOUTONS, str(racine)],
            cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=_environnement_qt(), timeout=300,
        )  # fmt: skip
        ligne = next((x for x in r.stdout.splitlines() if x.startswith("@@")), None)
        if ligne is None:
            return {cle: None}, {cle: f"la lecture du theme a echoue : {(r.stderr or r.stdout).strip()[-120:]}"}
        lignes = json.loads(ligne[2:])
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {cle: None}, {cle: f"la lecture du theme a echoue ({type(exc).__name__})"}
    return {cle: sum(1 for _, _, texte, fond in lignes if contraste(texte, fond) < 4.5)}, {}


def collecte(racine: Path) -> tuple[dict[str, int | None], dict[str, str]]:
    """Ce que pytest collecte dans chacune des quatre suites (`--collect-only`, rien ne s'execute)."""
    mesures: dict[str, int | None] = {}
    absents: dict[str, str] = {}
    for nom, args in SUITES.items():
        cle = f"tests.{nom}"
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider", *args],
                cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=_environnement_qt(), timeout=900,
            )  # fmt: skip
        except (OSError, subprocess.SubprocessError) as exc:
            mesures[cle], absents[cle] = None, f"pytest n'a pas repondu ({type(exc).__name__})"
            continue
        m = re.search(r"(\d+)(?:/\d+)? tests? collected", r.stdout)
        if m and r.returncode == 0:
            mesures[cle] = int(m.group(1))
        else:
            mesures[cle], absents[cle] = None, f"la collecte a echoue (code {r.returncode})"
    return mesures, absents


def gel(racine: Path) -> tuple[dict[str, float | None], dict[str, str]]:
    """La taille de `dist/CERTUS_HUB`, en Mo de 10^6 octets, s'il existe (il n'est jamais suivi par git)."""
    dossier = racine / "dist" / "CERTUS_HUB"
    if not dossier.is_dir():
        return {"gel.taille_mo": None}, {"gel.taille_mo": "pas de dossier gele (tools\\build_frozen.ps1, hors de Drive)"}
    return {"gel.taille_mo": round(sum(p.stat().st_size for p in dossier.rglob("*") if p.is_file()) / 1e6, 1)}, {}


def publication(racine: Path, *, reseau: bool = True) -> tuple[dict[str, int | None], dict[str, str], dict[str, Any]]:
    """Les commits que l'amont n'a pas, et les executions de CI rouges sur HEAD (par `gh`, si present)."""
    mesures: dict[str, int | None] = {"pub.commits_locaux": None, "pub.ci_rouge": None}
    absents: dict[str, str] = {}
    detail: dict[str, Any] = {}
    avance = _git(racine, "rev-list", "--count", "@{u}..HEAD")
    if avance is not None and avance.isdigit():
        mesures["pub.commits_locaux"] = int(avance)
    else:
        absents["pub.commits_locaux"] = "pas de branche amont"
    sha = _git(racine, "rev-parse", "HEAD")
    if not reseau or not sha or not shutil.which("gh"):
        absents["pub.ci_rouge"] = "gh absent ou reseau coupe" if sha else "pas de commit"
        return mesures, absents, detail
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--commit", sha, "--limit", "50", "--json", "workflowName,status,conclusion,headBranch"],
            cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )  # fmt: skip
        courses = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        courses = None
    if courses is None:
        absents["pub.ci_rouge"] = "gh n'a pas repondu (connexion ?)"
    elif not courses:
        absents["pub.ci_rouge"] = "aucune execution pour HEAD (commit non pousse ?)"
    else:
        mesures["pub.ci_rouge"] = sum(1 for c in courses if c.get("conclusion") == "failure")
        detail["ci"] = sorted(f"{c['workflowName']} ({c['headBranch']}): {c.get('conclusion') or c['status']}" for c in courses)
    return mesures, absents, detail


def couverture(chemin: Path) -> dict[str, float]:
    """Le pourcentage de LIGNES d'un JSON `coverage json` : tout `certus/`, et `certus/physics/` seul."""

    def pourcentage(fichiers: list[dict[str, Any]]) -> float:
        lignes = sum(f["summary"]["num_statements"] for f in fichiers)
        couvertes = sum(f["summary"]["covered_lines"] for f in fichiers)
        return round(100 * couvertes / lignes, 1) if lignes else 0.0

    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    par_fichier = {f.replace("\\", "/"): v for f, v in donnees["files"].items()}
    certus = [v for f, v in par_fichier.items() if f.startswith("certus/")]
    physique = [v for f, v in par_fichier.items() if f.startswith("certus/physics/")]
    return {"lignes": pourcentage(certus), "physics": pourcentage(physique)}


def modules_faibles(chemins: list[Path], seuil: float = 15.0, minimum: int = 50) -> int:
    """Combien de fichiers de `certus/` (d'au moins `minimum` lignes) restent sous `seuil` % dans TOUTES les mesures.

    Un fichier compte pour sa MEILLEURE couverture parmi les JSON donnes : un noyau compile est invisible dans la
    mesure ordinaire et se voit dans celle qui coupe la compilation. C'est ce qui remplace « aucun test ne nomme
    ce module », une mesure de noms : le 2026-09-30, 64 modules n'etaient nommes par aucun test, et 13 seulement
    etaient couverts a moins de 15 % par toutes les suites.
    """
    meilleure: dict[str, float] = {}
    for chemin in chemins:
        for nom, valeur in json.loads(chemin.read_text(encoding="utf-8"))["files"].items():
            nom = nom.replace("\\", "/")
            resume = valeur["summary"]
            if nom.startswith("certus/") and resume["num_statements"] >= minimum:
                pc = 100 * resume["covered_lines"] / resume["num_statements"]
                meilleure[nom] = max(meilleure.get(nom, 0.0), pc)
    return sum(1 for pc in meilleure.values() if pc < seuil)


_OUVERTURE = r"""
import importlib, json, os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, sys.argv[1])
from certus.core.certus_core import ensure_numba_cache_dir
ensure_numba_cache_dir()
t0 = time.perf_counter()
from PyQt6.QtWidgets import QApplication
app = QApplication([])
classe = getattr(importlib.import_module(sys.argv[2]), sys.argv[3])
fenetre = classe()
fenetre.show()
for _ in range(20):
    app.processEvents()
print("@@" + json.dumps({"total": time.perf_counter() - t0}), flush=True)
os._exit(0)
"""


def ouverture(racine: Path) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any]]:
    """Le temps d'ouverture hors ecran de chaque fenetre, un interprete neuf chacune, le meilleur de deux."""
    temps: dict[str, float] = {}
    for nom, (module, classe) in MODULES_OUVERTS.items():
        meilleur = None
        for _ in range(2):  # le premier passage peut remplir le cache de Numba
            try:
                r = subprocess.run(
                    [sys.executable, "-c", _OUVERTURE, str(racine), module, classe],
                    cwd=racine, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=_environnement_qt(), timeout=240,
                )  # fmt: skip
            except (OSError, subprocess.SubprocessError):
                break
            ligne = next((x for x in r.stdout.splitlines() if x.startswith("@@")), None)
            if ligne is None:
                break
            total = json.loads(ligne[2:])["total"]
            meilleur = total if meilleur is None else min(meilleur, total)
        if meilleur is not None:
            temps[nom] = round(meilleur, 2)
    modules = [t for n, t in temps.items() if n != "CERTUS_HUB"]
    mesures = {"ouverture.hub": temps.get("CERTUS_HUB"), "ouverture.modules_max": max(modules) if modules else None}
    absents = {cle: "la fenetre ne s'est pas ouverte" for cle, v in mesures.items() if v is None}
    return mesures, absents, {"ouverture_s": temps}


# =============================================================================
# Le tableau
# =============================================================================


def atteinte(cle: str, valeur: float | None) -> bool | None:
    """La cible de `cle` est-elle atteinte, dans le bon sens ? None : pas de cible, ou pas de mesure."""
    for k, _, _, cible, sens in INDICATEURS:
        if k == cle:
            if valeur is None or cible is None or sens is None:
                return None
            return valeur <= cible if sens == "min" else valeur >= cible
    return None


def _format(v: float | None) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"
    return f"{v:,}".replace(",", " ")


def rendre(mesures: dict[str, Any], absents: dict[str, str], base: dict[str, Any] | None = None, *, titre: str = "") -> str:
    """Le tableau : indicateur, mesure, base, cible, et si la cible est atteinte."""
    base = base or {}
    lignes = [titre] if titre else []
    lignes.append(f"{'indicateur':<46} {'mesure':>9} {'base':>9} {'cible':>8}")
    lignes.append("-" * 77)
    for cle, libelle, base_audit, cible, sens in INDICATEURS:
        valeur = mesures.get(cle)
        if cle not in mesures and cle not in absents:
            continue  # cette execution ne l'a pas demande : ni mesure, ni raison de l'absence
        attendu = base.get(cle, base_audit)
        ok = atteinte(cle, valeur)
        cible_txt = "" if cible is None else ("<= " if sens == "min" else ">= ") + _format(cible)
        marque = "" if ok is None else ("  OK" if ok else "")
        lignes.append(f"{libelle:<46} {_format(valeur):>9} {_format(attendu):>9} {cible_txt:>8}{marque}")
    if absents:
        lignes.append("")
        lignes.append("n/a : pas mesure, et pourquoi")
        lignes += [f"  {cle}: {raison}" for cle, raison in sorted(absents.items())]
    return "\n".join(lignes)


def mesurer(
    racine: Path,
    *,
    statique_seulement: bool = False,
    reseau: bool = True,
    avec_ouverture: bool = False,
    fichier_couverture: Path | None = None,
    fichier_noyaux: Path | None = None,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    """(mesures, absents, detail) : chaque ligne de INDICATEURS, mesuree ou dite absente."""
    mesures: dict[str, Any] = {}
    absents: dict[str, str] = {}
    detail: dict[str, Any] = {}

    sources = lire(racine, fichiers_suivis(racine, "*.py"))
    m, d = architecture(sources)
    mesures.update(m)
    detail.update(d)
    tests = {f: t for f, t in sources.items() if f.startswith("tests/")}
    certus = [f for f in sources if f.startswith("certus/")]
    mesures.update(tests_statiques(tests, certus))

    for cle, fichier, option in (
        ("couverture.lignes", fichier_couverture, "--couverture"),
        ("couverture.noyaux", fichier_noyaux, "--couverture-noyaux"),
    ):
        if fichier is None:
            mesures[cle], absents[cle] = None, f"option {option} FICHIER.json (coverage json)"
            continue
        try:
            lues = couverture(fichier)
            mesures[cle] = lues["lignes"] if cle == "couverture.lignes" else lues["physics"]
        except (OSError, ValueError, KeyError) as exc:
            mesures[cle], absents[cle] = None, f"{fichier.name} illisible ({type(exc).__name__})"

    fournis = [fichier for fichier in (fichier_couverture, fichier_noyaux) if fichier is not None]
    if fournis:
        try:
            mesures["couverture.modules_faibles"] = modules_faibles(fournis)
        except (OSError, ValueError, KeyError) as exc:
            mesures["couverture.modules_faibles"] = None
            absents["couverture.modules_faibles"] = f"JSON de couverture illisible ({type(exc).__name__})"
    else:
        mesures["couverture.modules_faibles"] = None
        absents["couverture.modules_faibles"] = "option --couverture FICHIER.json (coverage json)"

    if statique_seulement:
        for cle in ("lint.violations", "lint.regles", "ui.boutons_sous_4_5", "gel.taille_mo", "pub.ci_rouge",
                    *(f"tests.{nom}" for nom in SUITES)):  # fmt: skip
            mesures[cle], absents[cle] = None, "--rapide"
        mesures["pub.commits_locaux"] = None
        avance = _git(racine, "rev-list", "--count", "@{u}..HEAD")
        if avance is not None and avance.isdigit():
            mesures["pub.commits_locaux"] = int(avance)
        else:
            absents["pub.commits_locaux"] = "pas de branche amont"
    else:
        for etape in (lint(racine), boutons(racine), collecte(racine), gel(racine)):
            mesures.update(etape[0])
            absents.update(etape[1])
        m, a, d = publication(racine, reseau=reseau)
        mesures.update(m)
        absents.update(a)
        detail.update(d)
    if avec_ouverture:
        m, a, d = ouverture(racine)
        mesures.update(m)
        absents.update(a)
        detail.update(d)
    return mesures, absents, detail


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Les indicateurs du plan d'amelioration de CERTUS, en une commande.")
    p.add_argument("--racine", type=Path, default=ROOT, help="le depot a mesurer (defaut : celui de ce script)")
    p.add_argument("--rapide", action="store_true", help="le statique seulement : ni ruff, ni pytest, ni Qt, ni gh")
    p.add_argument("--sans-reseau", action="store_true", help="ne pas interroger gh (la CI de HEAD)")
    p.add_argument("--ouverture", action="store_true", help="mesurer aussi l'ouverture des dix fenetres (environ 2 min)")
    p.add_argument("--couverture", type=Path, help="JSON de `coverage json` de la suite ordinaire")
    p.add_argument("--couverture-noyaux", type=Path, help="JSON de `coverage json` pris avec NUMBA_DISABLE_JIT=1")
    p.add_argument("--base", type=Path, help="un JSON ecrit par ce script : la base de comparaison, au lieu de l'audit")
    p.add_argument("--json", type=Path, help="ecrire aussi les mesures, avec leur provenance (sans ecraser)")
    args = p.parse_args(argv)

    base = None
    if args.base:
        base = json.loads(args.base.read_text(encoding="utf-8")).get("mesures", {})
    mesures, absents, detail = mesurer(
        args.racine,
        statique_seulement=args.rapide,
        reseau=not args.sans_reseau,
        avec_ouverture=args.ouverture,
        fichier_couverture=args.couverture,
        fichier_noyaux=args.couverture_noyaux,
    )
    commit = _git(args.racine, "rev-parse", "--short", "HEAD")
    if commit is None:
        etat = "hors depot git"
    else:
        etat = f"{commit}, " + ("arbre propre" if _git(args.racine, "status", "--porcelain") == "" else "arbre modifie")
    titre = f"CERTUS - indicateurs du plan ({etat}) ; base : " + (args.base.name if args.base else "audit du 2026-09-30")
    print(rendre(mesures, absents, base, titre=titre))
    montantes = detail.get("aretes_montantes")
    if montantes:
        print("\naretes montantes : " + ", ".join(f"{paire} {n}" for paire, n in montantes.items()))
    if args.json:
        try:
            from _artefact import ecrire_json
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from _artefact import ecrire_json
        ecrire_json(args.json, {"mesures": mesures, "absents": absents, "detail": detail})
    return 0


if __name__ == "__main__":
    sys.exit(main())
