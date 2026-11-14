"""VERIFICATION CIBLEE : les tests que touche ce qui a change, pas toute la suite.

    python scripts\\verify_changed.py                  # ce qui differe de HEAD (suivis et non suivis), puis les tests
    python scripts\\verify_changed.py --base master~3  # ce qui differe d'un autre commit
    python scripts\\verify_changed.py --files a.py b.json
    python scripts\\verify_changed.py --list           # la selection et sa raison, sans rien lancer
    python scripts\\verify_changed.py --c1             # lance aussi `c1_diff.py HEAD` quand un noyau a change
    python scripts\\verify_changed.py --audit-calls tests\\unit  # la preuve : ce que les tests executent, le graphe le voit-il ?

POURQUOI. La validation de CLAUDE.md §2 dure 17 min en parallele, 40 en serie. Une ligne d'interface ne touche pas
l'oracle, et un noyau ne touche pas l'audit d'ergonomie. Cette commande choisit les fichiers de test que le changement
peut faire changer d'issue, et seulement eux.

COMMENT ELLE CHOISIT (au grain du fichier de test) :

  1. les fichiers modifies : `git diff --name-only BASE`, plus les non suivis non ignores ;
  2. un graphe d'imports STATIQUE (ast) de tous les `.py` suivis : imports de module et de fonction, relatifs, `from
     paquet import sous_module`, chaines qui nomment un module (`importlib.import_module("certus.x")`, registre des
     imports paresseux) ou un fichier (`"certus/physics/x.py"`). Pas la couverture : elle ne voit pas l'interieur des
     noyaux compiles, le graphe statique si ;
  3. un test est retenu si sa cloture d'imports atteint un fichier modifie. `from paquet import nom` mene au fichier
     qui DEFINIT `nom` (re-exports suivis : `from certus_physics import Target` ne tire pas toute la physique) ; ce que
     l'import d'un module execute en passant (re-exports, conftest) est couvert par l'etape suivante ;
  3b. un module du depot a change : `pytest --collect-only tests` verifie que toute la suite s'importe encore ;
  4. un test qui LIT des sources (`read_text`, `glob`, `ast.parse`, `ls-files`...) est retenu si un fichier modifie est
     sous un chemin qu'il nomme ; s'il n'en nomme aucun lisible, il est TOUJOURS joue ;
  5. un fichier de donnees modifie (json, md...) rend « modifie » tout `.py` qui cite son nom ;
  6. paliers : un `.md` lance les trois controles documentaires ; un fichier de `certus/physics/`, ou un `.py` qui cite
     numba, ajoute `tests/oracle/` entier et rappelle `c1_diff.py HEAD` ; `pyproject.toml`, un `conftest.py`, les
     verrous, un `.py` hors du graphe, ou une selection de plus de 60 % des tests : la suite complete
     (`validate_parallel.py`).

CE QU'ELLE NE DIT PAS. `VERIF_CIBLEE=GO` dit « aucun test touche n'echoue », pas « 0 failed » sur la suite : la
validation complete de CLAUDE.md §2 reste la reference avant de committer. La selection se prouve par `--audit-calls`
: chaque fonction du depot qu'un test execute (profil Python) doit etre dans sa cloture statique ; un ecart est un trou
du graphe, a corriger ici, pas a ignorer.

Code de sortie : 0 `VERIF_CIBLEE=GO`, 1 `VERIF_CIBLEE=NO-GO`, 2 la commande est mal appelee, 3 `VERIF_CIBLEE=COMPLETE`
(la suite complete est demandee : lancer `validate_parallel.py`).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Un de ces fichiers modifie : la suite complete. Ils changent la collecte, l'environnement ou les dependances.
FULL_SUITE_TRIGGERS = ("pyproject.toml", "requirements.lock", "uv.lock", "tests/slow_tier.py", "tests/qt_lifecycle.py",
                       "tests/qt_leaks.py", "certus_hub.spec")
#: Au-dela de cette part des fichiers de test, la selection ne fait plus gagner de temps : la suite complete.
FULL_SUITE_SHARE = 0.60
#: Un test qui lit des sources contient l'un de ces appels.
READS_SOURCES = re.compile(r"read_text\(|\.glob\(|rglob\(|ast\.parse|ls-files|os\.walk")
#: ... et il les lit dans le depot.
NAMES_THE_REPOSITORY = re.compile(r"parents\[|\bROOT\b|__file__")
PATH_LIKE = re.compile(r"[\w.\-]+(/[\w.\-]+)+/?|[\w\-]+\.(py|md|json|toml|spec|txt|yml|ps1|bat|html)")
DOC_SUFFIXES = (".md", ".html")
DOC_CHECKS = ("coherence_md", "check_claude_md", "check_docs")


def git(*args: str) -> list[str]:
    out = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} : {out.stderr.strip()}")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def changed_files(base: str) -> list[str]:
    files = set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(f.replace("\\", "/") for f in files)


# =============================================================================
# Le graphe d'imports
# =============================================================================


MODULE = "<module>"  # le code de niveau module d'un fichier (imports, constantes, appels)
WHOLE = "*"  # tout le fichier : un module manipule comme objet, ou importe par une chaine
Node = tuple[str, str]  # (fichier, symbole de niveau module | MODULE | WHOLE) ; un fichier de test : (fichier, WHOLE)


@dataclass
class Graph:
    files: list[str]
    modules: dict[str, set[str]] = field(default_factory=dict)  # nom de module -> fichiers
    edges: dict[Node, set[Node]] = field(default_factory=dict)  # noeud -> noeuds qu'il utilise
    spans: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)  # fichier -> (debut, fin, symbole)
    reads: dict[str, set[str] | None] = field(default_factory=dict)  # test qui lit des sources -> chemins (None : tout)
    sources: dict[str, str] = field(default_factory=dict)
    unparsable: set[str] = field(default_factory=set)
    class_lines: set[tuple[str, int]] = field(default_factory=set)  # (fichier, ligne) de chaque `class`


def module_names(path: str) -> list[str]:
    stem = path[:-3]
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    names = [stem.replace("/", ".")]
    if "/" in path and Path(path).stem != "__init__":
        names.append(Path(path).stem)  # un script met son dossier dans sys.path et importe ses voisins par leur nom nu
    return names


def package_of(path: str) -> str:
    stem = path[: -len("/__init__.py")] if path.endswith("/__init__.py") else path.rsplit("/", 1)[0] if "/" in path else ""
    return stem.replace("/", ".")


def _path_chain(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        if not (isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)):
            return None
        parts.append(node.right.value)
        node = node.left
    return "/".join(reversed(parts)) if parts else None


def _resolve_base(path: str, node: ast.ImportFrom) -> str:
    base = node.module or ""
    if node.level:
        anchor = package_of(path).split(".") if package_of(path) else []
        anchor = anchor[: len(anchor) - (node.level - 1)] if node.level > 1 else anchor
        base = ".".join([*anchor, base] if base else anchor)
    return base


@dataclass
class _File:
    path: str
    tree: ast.Module
    defs: dict[str, ast.AST] = field(default_factory=dict)  # def et class de niveau module
    assigned: set[str] = field(default_factory=set)  # noms affectes au niveau module
    bindings: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # nom -> (module, symbole | None)
    lazy: dict[str, tuple[str, str]] = field(default_factory=dict)  # re-export paresseux : nom -> (module, symbole)


def _bind_imports(path: str, nodes: Iterable[ast.AST], bindings: dict[str, tuple[str, str | None]]) -> None:
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = (alias.name, None)
                else:
                    bindings[alias.name.split(".")[0]] = (alias.name.split(".")[0], None)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_base(path, node)
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = (base, alias.name)


def _parse(path: str, tree: ast.Module) -> _File:
    info = _File(path, tree)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            info.defs[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                info.assigned.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            if isinstance(node.value, ast.Dict):
                # Un module a `__getattr__` sert ses noms paresseux par une table {"nom": ("module", "symbole")}.
                for key, value in zip(node.value.keys, node.value.values, strict=True):
                    if (isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, (ast.Tuple, ast.List))
                            and len(value.elts) >= 2 and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts[:2])):
                        info.lazy[key.value] = (value.elts[0].value, value.elts[1].value)
    _bind_imports(path, [n for top in tree.body if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                         for n in ast.walk(top)], info.bindings)
    return info


def build_graph(files: Iterable[str]) -> Graph:
    graph = Graph(files=sorted(files))
    tracked = set(graph.files)
    for path in graph.files:
        if path.endswith(".py"):
            for name in module_names(path):
                graph.modules.setdefault(name, set()).add(path)
    parsed: dict[str, _File] = {}
    for path in graph.files:
        if not path.endswith(".py"):
            continue
        try:
            source = (ROOT / path).read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            graph.unparsable.add(path)
            continue
        graph.sources[path] = source
        parsed[path] = _parse(path, tree)
        graph.class_lines |= {(path, line) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                              for line in (n.lineno, *(d.lineno for d in n.decorator_list))}

    def symbol(module: str, name: str, depth: int = 0) -> set[Node]:
        """Les noeuds que designe `name` pris dans `module` : sous-module, definition (re-exports suivis), ou niveau module."""
        if f"{module}.{name}" in graph.modules:
            return {(f, WHOLE) for f in graph.modules[f"{module}.{name}"]}
        found: set[Node] = set()
        for path in graph.modules.get(module, ()):
            info = parsed.get(path)
            if info is None:
                found.add((path, WHOLE))
            elif name in info.defs:
                found.add((path, name))
            elif name in info.bindings and name not in info.assigned and depth < 10:
                origin, original = info.bindings[name]
                found |= symbol(origin, original, depth + 1) if original else {(f, WHOLE) for f in graph.modules.get(origin, ())}
                found.add((path, MODULE))
            else:
                found.add((path, MODULE))
                if "__getattr__" in info.defs:
                    found.add((path, "__getattr__"))
                    if name in info.lazy and depth < 10:
                        found |= symbol(*info.lazy[name], depth + 1)
        return found

    def whole(module: str) -> set[Node]:
        return {(f, WHOLE) for f in graph.modules.get(module, ())}

    for path, info in parsed.items():
        is_test = path.startswith("tests/") and Path(path).name != "conftest.py"
        groups: dict[str, list[ast.AST]] = {}
        if is_test:
            groups[WHOLE] = [info.tree]
        else:
            groups[MODULE] = [n for n in info.tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            for name, node in info.defs.items():
                groups[name] = [node]
            graph.spans[path] = sorted(
                (min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))]), node.end_lineno or node.lineno, name)
                for name, node in info.defs.items()
            )
            graph.edges[(path, WHOLE)] = {(path, MODULE), *((path, n) for n in info.defs)}
        named_paths: set[str] = set()
        dynamic_import = "import_module" in graph.sources[path]
        for group, roots in groups.items():
            uses: set[Node] = set() if group in (MODULE, WHOLE) else {(path, MODULE)}
            local: dict[str, tuple[str, str | None]] = {}
            _bind_imports(path, [n for root in roots for n in ast.walk(root)], local)
            bindings = {**info.bindings, **local}
            for root in roots:
                attribute_bases = {id(n.value) for n in ast.walk(root) if isinstance(n, ast.Attribute)}
                for node in ast.walk(root):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        if not is_test:
                            continue  # un import seul ne fait rien qu'a l'import (--collect-only) ; ses noms, si
                        for alias in node.names:
                            if isinstance(node, ast.Import):
                                parts = alias.name.split(".")
                                for i in range(1, len(parts) + 1):
                                    uses |= {(f, MODULE) for f in graph.modules.get(".".join(parts[:i]), ())}
                            else:
                                base = _resolve_base(path, node)
                                uses |= {(f, MODULE) for f in graph.modules.get(base, ())}
                                uses |= whole(base) if alias.name == "*" else symbol(base, alias.name)
                    elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                        chain = []
                        cursor: ast.AST = node
                        while isinstance(cursor, ast.Attribute):
                            chain.append(cursor.attr)
                            cursor = cursor.value
                        if isinstance(cursor, ast.Name) and cursor.id in bindings and bindings[cursor.id][1] is None:
                            module = bindings[cursor.id][0]
                            for attr in reversed(chain):
                                if f"{module}.{attr}" in graph.modules:
                                    module = f"{module}.{attr}"
                                    continue
                                uses |= symbol(module, attr)
                                break
                            else:
                                uses |= whole(module)
                    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        name = node.id
                        if name in local or (name in info.bindings and name not in info.defs and name not in info.assigned):
                            module, original = bindings[name]
                            if original is None:
                                if id(node) not in attribute_bases:
                                    uses |= whole(module)
                            else:
                                uses |= symbol(module, original)
                        elif name in info.defs:
                            uses.add((path, name))
                        elif name in info.assigned:
                            uses.add((path, MODULE))
                    elif isinstance(node, ast.Call) and "import" in _callee(node.func):
                        for arg in node.args[:1]:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                uses |= whole(arg.value)
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                        text = node.value
                        if text in graph.modules and ("." in text or (is_test and dynamic_import)):
                            uses |= whole(text)
                        elif PATH_LIKE.fullmatch(text):
                            named_paths.add(text.rstrip("/"))
                            if is_test and text in tracked and text.endswith(".py"):
                                uses.add((text, WHOLE))
                    elif isinstance(node, ast.BinOp):
                        chained = _path_chain(node)
                        if chained:
                            named_paths.add(chained.rstrip("/"))
                            if is_test and chained.endswith(".py"):
                                uses |= {(f, WHOLE) for f in tracked if f == chained or f.endswith("/" + chained)}
            if is_test:
                uses |= _fixtures_used(path, info.tree, tracked, parsed)
            uses.discard((path, group))
            graph.edges[(path, group)] = uses
        if is_test and READS_SOURCES.search(graph.sources[path]):
            real = {p for p in named_paths if _exists_somewhere(p, tracked)}
            if real:
                graph.reads[path] = real
            elif NAMES_THE_REPOSITORY.search(graph.sources[path]):
                graph.reads[path] = None
    return graph


def _is_fixture(node: ast.AST) -> tuple[bool, bool]:
    """(est une fixture, est autouse)."""
    for deco in getattr(node, "decorator_list", []):
        text = ast.unparse(deco)
        if "fixture" in text:
            return True, "autouse=True" in text.replace(" ", "")
    return False, False


def _fixtures_used(test: str, tree: ast.Module, tracked: set[str], parsed: dict[str, _File]) -> set[Node]:
    """Les fixtures des conftest d'un test qu'il demande (parametres), les autouse, et leur niveau module."""
    wanted = {a.arg for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              for a in [*n.args.args, *n.args.kwonlyargs]}
    wanted |= {e.value for n in ast.walk(tree) if isinstance(n, ast.Call) and "usefixtures" in ast.unparse(n.func)
               for e in n.args if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    uses: set[Node] = set()
    for conf in conftests_of(test, tracked):
        info = parsed.get(conf)
        if info is None:
            uses.add((conf, WHOLE))
            continue
        uses.add((conf, MODULE))
        for name, node in info.defs.items():
            fixture, autouse = _is_fixture(node)
            if fixture and (autouse or name in wanted):
                uses.add((conf, name))
            if not fixture and name.startswith("pytest_"):
                uses.add((conf, name))  # les hooks agissent sur chaque test
    return uses


def _callee(func: ast.AST) -> str:
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def _exists_somewhere(path: str, tracked: set[str]) -> bool:
    if path in tracked or (ROOT / path).is_dir():
        return True
    return any(f"{d}/{path}" in tracked or (ROOT / d / path).is_dir() for d in ("certus", "scripts", "tests", "docs", "tools"))


def _resolved_prefixes(paths: set[str], tracked: set[str]) -> set[str]:
    out = set()
    for p in paths:
        if p in tracked or (ROOT / p).is_dir():
            out.add(p)
        for d in ("certus", "scripts", "tests", "docs", "tools"):
            if f"{d}/{p}" in tracked or (ROOT / d / p).is_dir():
                out.add(f"{d}/{p}")
    return out


def reverse(graph: Graph) -> dict[Node, set[Node]]:
    back: dict[Node, set[Node]] = {}
    for node, uses in graph.edges.items():
        for used in uses:
            back.setdefault(used, set()).add(node)
    return back


def users_of(back: dict[Node, set[Node]], start: Iterable[Node]) -> set[Node]:
    seen: set[Node] = set()
    stack = list(start)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(back.get(node, ()))
        if node[1] not in (WHOLE,):
            stack.append((node[0], WHOLE))  # qui manipule le module entier voit chacun de ses symboles
    return seen


def changed_lines(path: str, base: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]] | None:
    """Lignes modifiees (nouveau fichier, ancien fichier) d'apres `git diff -U0` ; None : fichier non suivi a la base."""
    out = subprocess.run(("git", "diff", "-U0", base, "--", path), cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=False).stdout
    if not out:
        return None if not git_tracked_at(base, path) else ([], [])
    new, old = [], []
    for match in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", out, re.MULTILINE):
        o, oc, n, nc = int(match[1]), int(match[2] or 1), int(match[3]), int(match[4] or 1)
        old.append((o, o + max(oc, 1) - 1))
        new.append((n, n + max(nc, 1) - 1))
    return new, old


def git_tracked_at(base: str, path: str) -> bool:
    return subprocess.run(("git", "cat-file", "-e", f"{base}:{path}"), cwd=ROOT, capture_output=True, check=False).returncode == 0


def nodes_at(spans: list[tuple[int, int, str]], ranges: list[tuple[int, int]]) -> set[str]:
    hit: set[str] = set()
    for lo, hi in ranges:
        inside = [name for start, end, name in spans if start <= hi and lo <= end]
        hit.update(inside)
        covered = sorted((max(lo, start), min(hi, end)) for start, end, _name in spans if start <= hi and lo <= end)
        cursor = lo
        for a, b in covered:
            if a > cursor:
                break
            cursor = max(cursor, b + 1)
        if cursor <= hi:
            hit.add(MODULE)
    return hit


def old_spans(base: str, path: str) -> list[tuple[int, int, str]]:
    text = subprocess.run(("git", "show", f"{base}:{path}"), cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False).stdout
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    return sorted((min([n.lineno, *(d.lineno for d in getattr(n, "decorator_list", []))]), n.end_lineno or n.lineno, n.name)
                  for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


def test_files(graph: Graph) -> list[str]:
    return [f for f in graph.files if f.startswith("tests/") and Path(f).name.startswith("test_") and f.endswith(".py")]


def conftests_of(test: str, tracked: set[str]) -> list[str]:
    parts = test.split("/")[:-1]
    return [c for i in range(1, len(parts) + 1) if (c := "/".join([*parts[:i], "conftest.py"])) in tracked]


# =============================================================================
# La selection
# =============================================================================


@dataclass
class Selection:
    changed: list[str]
    tests: dict[str, str] = field(default_factory=dict)  # fichier de test -> raison
    docs: bool = False
    kernels: list[str] = field(default_factory=list)
    full_suite: str = ""  # raison de demander la suite complete ("" : non)
    collect: bool = False  # un module du depot a change : toute la suite doit encore s'importer (`--collect-only`)
    total_tests: int = 0


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _fingerprints(tree: ast.Module, path: str) -> tuple[dict[str, str], str, dict[str, tuple[str, str | None]]]:
    """Empreinte de chaque def/class (sans docstrings), du code de niveau module hors imports, et des liaisons d'import."""
    defs: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    inner.body = _strip_docstring(inner.body) or [ast.Pass()]
            defs[node.name] = ast.dump(node)
    rest = [n for n in _strip_docstring(list(tree.body))
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    bindings: dict[str, tuple[str, str | None]] = {}
    _bind_imports(path, [n for top in tree.body if isinstance(top, (ast.Import, ast.ImportFrom)) for n in ast.walk(top)], bindings)
    return defs, ast.dump(ast.Module(body=rest, type_ignores=[])), bindings


def changed_nodes(graph: Graph, path: str, base: str) -> set[Node]:
    """Les symboles d'un .py dont le code (hors docstrings, commentaires, mise en page) differe de `base`."""
    if path.startswith("tests/") and Path(path).name != "conftest.py":
        return {(path, WHOLE)}
    if path not in graph.sources or not git_tracked_at(base, path):
        return {(path, WHOLE)}
    old_text = subprocess.run(("git", "show", f"{base}:{path}"), cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False).stdout
    try:
        old = _fingerprints(ast.parse(old_text), path)
        new = _fingerprints(ast.parse(graph.sources[path]), path)
    except SyntaxError:
        return {(path, WHOLE)}
    names = {n for n in set(old[0]) | set(new[0]) if old[0].get(n) != new[0].get(n)}
    if old[1] != new[1] or set(old[0]) - set(new[0]):
        names.add(MODULE)  # code de niveau module, ou un symbole disparu : ceux qui le nommaient passent par la
    rebound = {n for n in set(old[2]) | set(new[2]) if old[2].get(n) != new[2].get(n)}
    if rebound:
        tree = ast.parse(graph.sources[path])
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and any(
                    isinstance(n, ast.Name) and n.id in rebound for n in ast.walk(node)):
                names.add(node.name)
    return {(path, n) for n in names}


def select(graph: Graph, changed: list[str], base: str = "HEAD", whole_files: bool = False, explain: bool = False) -> Selection:
    sel = Selection(changed=changed)
    tracked = set(graph.files) | set(changed)
    tests = test_files(graph)
    sel.total_tests = len(tests)
    present = [c for c in changed if (ROOT / c).exists()]
    deleted = [c for c in changed if not (ROOT / c).exists()]
    for c in changed:
        if c in FULL_SUITE_TRIGGERS or Path(c).name == "conftest.py":
            sel.full_suite = f"{c} change la collecte ou l'environnement de toute la suite"
        if c.endswith(DOC_SUFFIXES):
            sel.docs = True
        if c.endswith(".py") and c in graph.unparsable:
            sel.full_suite = f"{c} ne s'analyse pas (erreur de syntaxe ?) : le graphe ne sait pas qui l'importe"
    if deleted:
        sel.full_suite = sel.full_suite or f"fichier supprime ({deleted[0]}) : ses importeurs ne se voient plus"
    start: set[Node] = set()
    files_touched = {c for c in present if c.endswith(".py")}
    for c in sorted(files_touched):
        start |= {(c, WHOLE)} if whole_files else changed_nodes(graph, c, base)
    # Un fichier de donnees modifie : les symboles qui citent son nom sont touches.
    for c in present:
        if c.endswith(".py") or c.endswith(DOC_SUFFIXES):
            continue
        for needle in {Path(c).name, c}:
            for path, source in graph.sources.items():
                if needle not in source:
                    continue
                files_touched.add(path)
                lines = [i + 1 for i, line in enumerate(source.splitlines()) if needle in line]
                hit = nodes_at(graph.spans.get(path, []), [(n, n) for n in lines]) if path in graph.spans else {WHOLE}
                start |= {(path, h) for h in hit}
    for c in files_touched:
        if c.startswith("certus/physics/") or c == "certus/core/_certus_physics_impl.py" or (
            not c.startswith("tests/") and "numba" in graph.sources.get(c, "")):
            sel.kernels.append(c)
    sel.kernels.sort()
    sel.collect = any(not c.startswith("tests/") for c in files_touched)
    reached = users_of(reverse(graph), start)
    for test in tests:
        if (test, WHOLE) in reached:
            mine = forward(graph, [(test, WHOLE)]) if explain else set()
            hit = sorted(f"{f}::{n}" for f, n in start & mine)
            sel.tests[test] = f"utilise {hit[0]}" + (f" (+{len(hit) - 1})" if len(hit) > 1 else "") if hit else "utilise"
            continue
        if test in graph.reads:
            prefixes = graph.reads[test]
            if prefixes is None:
                sel.tests[test] = "lit des sources sans dire lesquelles : toujours joue"
                continue
            resolved = _resolved_prefixes(prefixes, tracked)
            touched = sorted(c for c in present for p in resolved if c == p or c.startswith(p + "/"))
            if touched:
                sel.tests[test] = f"lit {touched[0]}"
    if sel.kernels:
        for test in tests:
            if test.startswith("tests/oracle/") and test not in sel.tests:
                sel.tests[test] = f"noyau modifie ({sel.kernels[0]}) : tout l'oracle"
    if sel.total_tests and len(sel.tests) > FULL_SUITE_SHARE * sel.total_tests:
        sel.full_suite = sel.full_suite or f"{len(sel.tests)} fichiers de test sur {sel.total_tests} : autant tout jouer"
    return sel


def forward(graph: Graph, start: Iterable[Node]) -> set[Node]:
    seen: set[Node] = set()
    stack = list(start)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.edges.get(node, ()))
    return seen


# =============================================================================
# L'execution
# =============================================================================

_COUNT = re.compile(r"(\d+) (passed|failed|errors?)")


def run(command: list[str]) -> tuple[int, str]:
    out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return out.returncode, out.stdout + out.stderr


def last_lines(text: str, n: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def execute(sel: Selection, workers: int, c1: bool) -> bool:
    ok = True
    py = [c for c in sel.changed if c.endswith(".py") and (ROOT / c).exists()]
    if py:
        code, out = run([sys.executable, "-m", "ruff", "check", *py])
        print(f"  ruff ({len(py)} fichiers) : {'PASS' if code == 0 else 'FAIL'}")
        if code:
            print(last_lines(out))
            ok = False
    if sel.docs:
        for name in DOC_CHECKS:
            code, out = run([sys.executable, f"scripts/{name}.py"])
            print(f"  {name} : {'PASS' if code == 0 else 'FAIL'}")
            if code:
                print(last_lines(out, 8))
                ok = False
    if sel.collect:
        code, out = run([sys.executable, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider", "--collect-only", "tests"])
        print(f"  import de toute la suite (--collect-only) : {'PASS' if code == 0 else 'FAIL'}")
        if code:
            print(last_lines(out))
            ok = False
    if sel.tests:
        command = [sys.executable, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider", *sorted(sel.tests)]
        if workers > 1 and len(sel.tests) > 1 and importlib.util.find_spec("xdist") is not None:
            command += ["-n", str(workers), "--dist", "loadfile"]
        code, out = run(command)
        summary = next((line for line in reversed(out.splitlines()) if _COUNT.search(line)), "aucun resume pytest")
        print(f"  pytest ({len(sel.tests)} fichiers) : {summary.strip('= ')}")
        if code:
            print(last_lines(out, 25))
            ok = False
    if sel.kernels:
        if c1:
            code, out = run([sys.executable, "scripts/c1_diff.py", "HEAD"])
            print(f"  c1_diff HEAD : {'PASS' if code == 0 else 'FAIL'}")
            if code:
                print(last_lines(out))
                ok = False
        else:
            print("  noyau modifie : `python scripts\\c1_diff.py HEAD` avant de committer (ou --c1)")
    return ok


AUDIT_PLUGIN = r"""
import json, os, sys
from contextlib import contextmanager
from pathlib import Path
ROOT = str(Path(os.environ["VERIFY_ROOT"]).resolve())
TOOL = 4
SEEN = {}
CURRENT = [None]
mon = sys.monitoring
ACTIVE = [False]
def _start(code, offset):
    if not ACTIVE[0]:
        return None
    name = code.co_filename
    if name.startswith(ROOT) and code.co_name not in ("<module>", "__annotate__"):
        rel = Path(name).resolve().relative_to(ROOT).as_posix()
        if not rel.startswith("tests/"):
            SEEN.setdefault(CURRENT[0], set()).add((rel, code.co_firstlineno))
    return mon.DISABLE
mon.use_tool_id(TOOL, "verify_changed_audit")
mon.register_callback(TOOL, mon.events.PY_START, _start)
mon.set_events(TOOL, mon.events.PY_START)
import pytest
@contextmanager
def _record(item):
    test = item.nodeid.split("::")[0]
    if test != CURRENT[0]:
        CURRENT[0] = test
        mon.restart_events()
    SEEN.setdefault(test, set())
    ACTIVE[0] = True
    try:
        yield
    finally:
        ACTIVE[0] = False
@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    with _record(item):
        return (yield)
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    with _record(item):
        return (yield)
@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item):
    with _record(item):
        return (yield)
def pytest_sessionfinish(session, exitstatus):
    mon.set_events(TOOL, 0)
    suffix = "." + session.config.workerinput["workerid"] if hasattr(session.config, "workerinput") else ""
    with open(os.environ["VERIFY_OUT"] + suffix, "w", encoding="utf-8") as fh:
        json.dump({k: sorted(v) for k, v in SEEN.items()}, fh)
"""


def audit_calls(graph: Graph, tests: list[str], workers: int = 1) -> int:
    """La preuve : chaque fonction du depot qu'un test EXECUTE (sys.monitoring) est-elle dans sa cloture statique ?

    Un noyau compile n'est pas vu de l'interieur (ce que le graphe voit par les noms) ; le code de niveau module,
    execute a l'import, est laisse a `--collect-only`.
    """
    import tempfile

    tracked = set(graph.files)
    with tempfile.TemporaryDirectory() as tmp:
        plugin = Path(tmp) / "verify_changed_audit_plugin.py"
        plugin.write_text(AUDIT_PLUGIN, encoding="utf-8")
        out = Path(tmp) / "calls.json"
        env = {**os.environ, "VERIFY_ROOT": str(ROOT), "VERIFY_OUT": str(out),
               "PYTHONPATH": os.pathsep.join([tmp, os.environ.get("PYTHONPATH", "")])}
        parallel = ["-n", str(workers), "--dist", "loadfile"] if workers > 1 else []
        code, text = run_env([sys.executable, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider", "-p",
                              "verify_changed_audit_plugin", *parallel, *tests], env)
        if not out.exists():
            print(last_lines(text))
            return 2
        seen: dict[str, set[tuple[str, int]]] = {}
        for result in [out, *Path(tmp).glob("calls.json.*")]:
            for test, calls in json.loads(result.read_text(encoding="utf-8")).items():
                seen.setdefault(test, set()).update((rel, line) for rel, line in calls)
    holes = 0
    for test, calls in sorted(seen.items()):
        reach = forward(graph, [(c, WHOLE) for c in (test, *conftests_of(test, tracked))])
        reach_files = {f for f, n in reach if n == WHOLE}
        missing = set()
        for rel, line in calls:
            if rel in reach_files or rel not in graph.spans:
                continue
            owner = next((name for start, end, name in graph.spans[rel] if start <= line <= end), MODULE)
            if (rel, line) in graph.class_lines:
                continue  # le corps d'une classe, execute a son import
            if (rel, owner) not in reach:
                missing.add(f"{rel}::{owner}")
        if missing:
            holes += 1
            print(f"  TROU {test} : {', '.join(sorted(missing)[:4])}" + (" ..." if len(missing) > 4 else ""))
    status = "TROUS" if holes else "ECHEC" if code else "OK"
    if code:
        print(last_lines(text))
    print(f"AUDIT_APPELS={status} ({len(seen)} fichiers de test, {holes} avec un trou ; pytest "
          f"{'vert' if code == 0 else 'ROUGE'})")
    return 0 if holes == 0 and code == 0 else 1


def run_env(command: list[str], env: dict[str, str]) -> tuple[int, str]:
    out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         check=False, env=env)
    return out.returncode, out.stdout + out.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--files", nargs="+")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--c1", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 2)))
    parser.add_argument("--audit-calls", nargs="+", metavar="TEST")
    parser.add_argument("--audit-workers", type=int, default=1, help="workers de l'audit d'appels (defaut : serie)")
    args = parser.parse_args(argv)
    graph = build_graph(git("ls-files", "*.py") + git("ls-files", "--others", "--exclude-standard", "*.py"))
    if args.audit_calls:
        return audit_calls(graph, args.audit_calls, max(1, args.audit_workers))
    changed = sorted(f.replace("\\", "/") for f in args.files) if args.files else changed_files(args.base)
    if not changed:
        print("Rien n'a change.\nVERIF_CIBLEE=GO (0 test)")
        return 0
    sel = select(graph, changed, args.base, explain=args.list)
    print(f"{len(changed)} fichier(s) modifie(s) ; {len(sel.tests)} fichier(s) de test sur {sel.total_tests}")
    if args.list:
        for test, why in sorted(sel.tests.items()):
            print(f"  {test} -- {why}")
    if sel.full_suite:
        print(f"Suite complete demandee : {sel.full_suite}.\n  python scripts\\validate_parallel.py\nVERIF_CIBLEE=COMPLETE")
        return 3
    if args.list:
        return 0
    ok = execute(sel, args.workers, args.c1)
    print(f"VERIF_CIBLEE={'GO' if ok else 'NO-GO'} ({len(sel.tests)} fichiers de test sur {sel.total_tests} ; la suite"
          " complete reste la reference avant de committer)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
