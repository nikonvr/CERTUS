"""LE PILOTE DE MUTATION : LES TESTS VOIENT-ILS UNE FAUTE POSEE DANS LE CODE ? (S3.6)

    python scripts\\mutation_pilot.py certus/physics/certus_inputs.py certus/physics/certus_oblique_substrate.py
    python scripts\\mutation_pilot.py certus/physics/certus_inputs.py --json mutation.json --workers 8
    python scripts\\mutation_pilot.py --rerun mutation.json        # seulement les survivants d'une passe precedente
    python scripts\\mutation_pilot.py certus/physics/certus_inputs.py --baseline tests/mutation_baseline.json

Un test qui passe ne dit pas qu'il garde quelque chose. Cet outil pose UNE faute a la fois dans un module (un `<` qui
devient `<=`, un `+` qui devient `-`, une constante qui bouge d'un, un `raise` qui devient `pass`, un `max` qui devient
`min`, un `.real` qui devient `.imag`), lance les tests, et compte : un mutant TUE est une faute que les tests voient,
un SURVIVANT est une faute qu'ils laissent passer (un test manque, ou la faute ne change rien : mutant equivalent, a
juger a la main).

Pourquoi un outil maison : mutmut 3 refuse Windows (« please use the WSL », issue 397 de son depot), et ce poste n'a
pas de distribution WSL. Les operateurs sont ceux de mutmut (comparaisons, arithmetique, booleens, constantes, `return`)
plus ceux de la physique de ce depot (`raise` retire, `max` / `min`, `real` / `imag`, `sin` / `cos`, `abs` retire).

Ce que l'outil fait, et ne fait pas :
- il travaille sur des COPIES du depot (les fichiers suivis ou non caches par git, sans `reports/` : un test ecrit
  pour tuer un survivant compte avant d'etre commite), jamais sur le depot : une faute posee n'y reste pas, meme si
  l'on interrompt l'outil. Une copie par fil ;
- les tests tournent avec `NUMBA_DISABLE_JIT=1` : un noyau compile n'est pas un code que Python peut muter, et son
  cache (cle : les sources qui disent `numba`) garderait l'ancien appele sous un appelant inchange (R33). Sans
  compilation, la faute posee est exactement celle que les tests executent. Deux tests d'oracle sautent alors ;
- par defaut : `tests/oracle`, `tests/core` et chaque fichier de test qui nomme le module. `--tests` en donne d'autres ;
- le TEMOIN d'abord : le module re-ecrit SANS faute (analyse puis `ast.unparse`) doit passer les tests, sinon l'outil
  s'arrete : un score mesure sur des tests rouges ne dit rien ;
- un timeout compte comme un mutant tue (une boucle infinie posee est vue) ; un mutant qui ne se compile pas n'est
  pas genere ; un mutant sans test collecte est une ERREUR, hors du score.

Le cliquet : `--baseline` lit `tests/mutation_baseline.json`, qui nomme les survivants ACCEPTES (chacun avec sa raison :
une egalite entre deux flottants qu'aucune entree n'atteint, un mutant equivalent) ; un survivant qui n'y est pas fait
sortir le code 1, un accepte qui ne survit plus est signale (a retirer du fichier).

Le score est tues / (tues + survivants). `score_sans_chaines` laisse de cote les constantes de texte (messages d'erreur,
noms), que peu de tests lisent mot a mot : le chiffre a retenir pour juger les tests de comportement.

Le code de sortie : 0 passe faite, 1 un survivant que le fichier de base n'accepte pas, 2 le temoin echoue ou un
argument est faux.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_COMPARE: dict[type, type] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
_ARITHMETIC: dict[type, type] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Div,
    ast.Mod: ast.Mult,
    ast.Pow: ast.Mult,
}
_BOOLEAN: dict[type, type] = {ast.And: ast.Or, ast.Or: ast.And}
_SYMBOL: dict[type, str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.And: "and",
    ast.Or: "or",
}
#: Les noms que l'on echange contre leur contraire : ce que fait un mot de travers dans une formule de physique.
_SWAP: dict[str, str] = {
    "max": "min",
    "min": "max",
    "all": "any",
    "any": "all",
    "argmax": "argmin",
    "argmin": "argmax",
    "real": "imag",
    "imag": "real",
    "sin": "cos",
    "cos": "sin",
}
_SWAPPABLE_NAMES = frozenset({"max", "min", "all", "any"})
_TESTS_ALWAYS = ("tests/oracle", "tests/core")
_TIMEOUT_DEFAULT = 180.0


@dataclasses.dataclass(frozen=True)
class Variant:
    """Une faute possible sur un noeud : sa famille, ce qu'elle remplace, par quoi, et le geste qui la pose."""

    kind: str
    old: str
    new: str
    make: Callable[[ast.AST], ast.AST | None]


@dataclasses.dataclass(frozen=True)
class Mutant:
    """Une faute posee : ou (ligne et colonne du noeud, et la ligne d'origine), laquelle, et le texte du module fautif."""

    module: str
    line: int
    col: int
    kind: str
    old: str
    new: str
    source: str
    text: str

    def key(self) -> tuple[str, int, int, str, str, str]:
        return (self.module, self.line, self.col, self.kind, self.old, self.new)


def _set_compare(index: int, new: type, node: ast.Compare) -> None:
    node.ops[index] = new()


def _set_operator(new: type, node: ast.BinOp | ast.BoolOp | ast.AugAssign) -> None:
    node.op = new()


def _set_constant(value: object, node: ast.Constant) -> None:
    node.value = value


def _set_name(new: str, node: ast.Name) -> None:
    node.id = new


def _set_attribute(new: str, node: ast.Attribute) -> None:
    node.attr = new


def _negate_test(node: ast.If | ast.While | ast.IfExp) -> None:
    node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)


def _return_none(node: ast.Return) -> None:
    node.value = ast.Constant(value=None)


def _drop_operator(node: ast.UnaryOp) -> ast.AST:
    return node.operand


def _drop_call(node: ast.Call) -> ast.AST:
    return node.args[0]


def _raise_becomes_pass(node: ast.Raise) -> ast.AST:
    return ast.Pass()


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_abs(node: ast.Call) -> bool:
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return name == "abs" and len(node.args) == 1 and not node.keywords


def _constant_variants(node: ast.Constant) -> list[Variant]:
    value = node.value
    if isinstance(value, bool):
        return [Variant("const-bool", repr(value), repr(not value), partial(_set_constant, not value))]
    if isinstance(value, (int, float)):
        return [Variant("const-number", repr(value), repr(value + 1), partial(_set_constant, value + 1))]
    if isinstance(value, str):
        changed = f"XX{value}XX"
        return [Variant("const-str", repr(value), repr(changed), partial(_set_constant, changed))]
    return []


def _variants(node: ast.AST) -> list[Variant]:
    """Les fautes que l'on sait poser sur ce noeud, toujours dans le meme ordre (l'index d'une faute est stable)."""
    out: list[Variant] = []
    if isinstance(node, ast.Compare):
        for i, op in enumerate(node.ops):
            new = _COMPARE.get(type(op))
            if new:
                out.append(Variant("compare", _SYMBOL[type(op)], _SYMBOL[new], partial(_set_compare, i, new)))
    elif isinstance(node, (ast.BinOp, ast.AugAssign)) and type(node.op) in _ARITHMETIC:
        new = _ARITHMETIC[type(node.op)]
        out.append(Variant("arithmetic", _SYMBOL[type(node.op)], _SYMBOL[new], partial(_set_operator, new)))
    elif isinstance(node, ast.BoolOp):
        new = _BOOLEAN[type(node.op)]
        out.append(Variant("boolean", _SYMBOL[type(node.op)], _SYMBOL[new], partial(_set_operator, new)))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub)):
        symbol = "not" if isinstance(node.op, ast.Not) else "-"
        out.append(Variant("unary", symbol, "", _drop_operator))
    elif isinstance(node, ast.Constant):
        out.extend(_constant_variants(node))
    elif isinstance(node, (ast.If, ast.While, ast.IfExp)):
        out.append(Variant("condition", "test", "not test", _negate_test))
    elif isinstance(node, ast.Return) and node.value is not None and not _is_none(node.value):
        out.append(Variant("return", "return value", "return None", _return_none))
    elif isinstance(node, ast.Raise):
        out.append(Variant("raise", "raise", "pass", _raise_becomes_pass))
    elif isinstance(node, ast.Call) and _is_abs(node):
        out.append(Variant("abs", "abs(x)", "x", _drop_call))
    elif isinstance(node, ast.Name) and node.id in _SWAPPABLE_NAMES:
        out.append(Variant("swap", node.id, _SWAP[node.id], partial(_set_name, _SWAP[node.id])))
    elif isinstance(node, ast.Attribute) and node.attr in _SWAP:
        out.append(Variant("swap", node.attr, _SWAP[node.attr], partial(_set_attribute, _SWAP[node.attr])))
    return out


class _Replace(ast.NodeTransformer):
    """Remplace un noeud (le `Not` retire, le `raise` devenu `pass`) la ou une affectation sur place ne suffit pas."""

    def __init__(self, target: ast.AST, replacement: ast.AST) -> None:
        self.target = target
        self.replacement = replacement

    def visit(self, node: ast.AST) -> ast.AST:
        return self.replacement if node is self.target else self.generic_visit(node)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Les positions (dans `ast.walk`) des chaines qui sont des docstrings : les muter ne change rien."""
    index = {id(n): i for i, n in enumerate(ast.walk(tree))}
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(index[id(first.value)])
    return found


def _mutable_nodes(tree: ast.AST) -> set[int]:
    """Les positions des noeuds que l'on mute : le corps des fonctions et la valeur des constantes de module.

    Ni les decorateurs (`@njit(cache=True)` : sans effet une fois la compilation coupee), ni les valeurs par defaut,
    ni les annotations, ni les docstrings.
    """
    index = {id(n): i for i, n in enumerate(ast.walk(tree))}
    chosen: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chosen.update(index[id(sub)] for stmt in node.body for sub in ast.walk(stmt))
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None:
            chosen.update(index[id(sub)] for sub in ast.walk(stmt.value))
    return chosen - _docstring_nodes(tree)


def _apply(source: str, position: int, variant_number: int) -> str:
    """Le texte de `source` avec la faute `variant_number` posee sur le noeud `position` de `ast.walk`."""
    tree = ast.parse(source)
    target = list(ast.walk(tree))[position]
    replacement = _variants(target)[variant_number].make(target)
    if replacement is not None:
        tree = _Replace(target, replacement).visit(tree)
    return ast.unparse(ast.fix_missing_locations(tree))


def control_source(source: str) -> str:
    """Le module re-ecrit sans aucune faute : ce que tous les mutants ont en commun, le temoin de l'outil."""
    return ast.unparse(ast.parse(source))


def iter_mutants(source: str, module: str = "<module>") -> list[Mutant]:
    """Toutes les fautes d'un module : valides (le texte se compile) et differentes du temoin."""
    tree = ast.parse(source)
    control = control_source(source)
    mutable = _mutable_nodes(tree)
    lines = source.splitlines()
    mutants: list[Mutant] = []
    for position, node in enumerate(ast.walk(tree)):
        if position not in mutable:
            continue
        for number, variant in enumerate(_variants(node)):
            text = _apply(source, position, number)
            if text == control:
                continue
            try:
                compile(text, module, "exec")
            except (SyntaxError, ValueError):
                continue
            line = getattr(node, "lineno", 0)
            shown = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            mutants.append(Mutant(module, line, getattr(node, "col_offset", 0), variant.kind, variant.old, variant.new, text, shown))
    return mutants


def _tracked_files(root: Path) -> list[str]:
    """Les fichiers a copier : ceux que git suit ou ne cache pas (un test neuf, pas encore ajoute, compte), sans `reports/`.

    Tout l'arbre si ce n'est pas un depot.
    """
    if (root / ".git").exists():
        command = ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
        done = subprocess.run(command, capture_output=True, check=False)
        if done.returncode == 0:
            names = sorted({n for n in done.stdout.decode("utf-8", "replace").split("\0") if n})
            return [n for n in names if not n.startswith("reports/") and (root / n).is_file()]
    skipped = {".git", "__pycache__", "reports", "htmlcov", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    return [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not skipped.intersection(p.relative_to(root).parts)
    ]


def make_copies(root: Path, where: Path, count: int) -> list[Path]:
    """`count` copies du depot sous `where` : une par fil, pour qu'une faute posee ne gene pas celle d'un autre."""
    first = where / "w0"
    for name in _tracked_files(root):
        target = first / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    copies = [first]
    for k in range(1, count):
        shutil.copytree(first, where / f"w{k}")
        copies.append(where / f"w{k}")
    return copies


def default_tests(root: Path, module: str) -> list[str]:
    """`tests/oracle`, `tests/core` et chaque fichier de test qui IMPORTE le module (une ligne `import` ou `from` qui le nomme).

    Un test qui ne fait que citer son nom dans une chaine (le test de cet outil, qui donne des chemins en exemple) ne le
    lit pas : le lancer pour chaque faute ajouterait ses secondes a chacune.
    """
    stem = Path(module).stem
    chosen = [t for t in _TESTS_ALWAYS if (root / t).exists()]
    pattern = re.compile(rf"^[ \t]*(?:from|import)\b[^\n]*\b{re.escape(stem)}\b", re.MULTILINE)
    tests_dir = root / "tests"
    for path in sorted(tests_dir.rglob("test_*.py")) if tests_dir.exists() else []:
        relative = path.relative_to(root).as_posix()
        if not relative.startswith(tuple(f"{t}/" for t in _TESTS_ALWAYS)):
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                chosen.append(relative)
    return chosen


def run_tests(workdir: Path, tests: list[str], timeout: float) -> tuple[str, int, str]:
    """(statut, code de sortie, sortie) de pytest dans `workdir`, sans compilation, au premier echec."""
    env = {
        **os.environ,
        "NUMBA_DISABLE_JIT": "1",
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    command = [sys.executable, "-B", "-m", "pytest", *tests, "-x", "-q", "--no-header", "-p", "no:cacheprovider", "-o", "addopts="]
    command += ["--tb=line", "-rf"]
    try:
        done = subprocess.run(
            command, cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return "timeout", -1, ""
    status = {0: "survived", 1: "killed", 2: "killed"}.get(done.returncode, "error")
    return status, done.returncode, done.stdout


def _killer(output: str) -> str:
    """Le premier test vu en echec (ou en erreur de collecte) dans la sortie de pytest, ou une chaine vide."""
    found = re.search(r"^(?:FAILED|ERROR) (\S+)", output, re.MULTILINE)
    return found.group(1) if found else ""


def _run_one(pool: queue.Queue, root: Path, mutant: Mutant, tests: list[str], timeout: float) -> dict:
    workdir = pool.get()
    target = workdir / mutant.module
    original = (root / mutant.module).read_bytes()
    started = time.monotonic()
    try:
        target.write_text(mutant.source, encoding="utf-8")
        status, code, output = run_tests(workdir, tests, timeout)
    finally:
        target.write_bytes(original)
        pool.put(workdir)
    return {
        "module": mutant.module,
        "line": mutant.line,
        "col": mutant.col,
        "kind": mutant.kind,
        "old": mutant.old,
        "new": mutant.new,
        "status": status,
        "code": code,
        "killer": _killer(output),
        "seconds": round(time.monotonic() - started, 1),
        "text": mutant.text,
    }


def summarize(results: list[dict]) -> dict[str, dict]:
    """Par module : les comptes et les deux scores (complet, et sans les constantes de texte)."""
    modules: dict[str, dict] = {}
    for module in sorted({r["module"] for r in results}):
        mine = [r for r in results if r["module"] == module]
        modules[module] = {"mutants": len(mine)}
        for label, chosen in (("score", mine), ("score_sans_chaines", [r for r in mine if r["kind"] != "const-str"])):
            killed = sum(r["status"] in ("killed", "timeout") for r in chosen)
            survived = sum(r["status"] == "survived" for r in chosen)
            modules[module][label] = round(killed / (killed + survived), 4) if killed + survived else None
        for status in ("killed", "timeout", "survived", "error"):
            modules[module][status] = sum(r["status"] == status for r in mine)
    return modules


def run_pilot(
    root: Path,
    modules: list[str],
    tests: list[str] | None = None,
    workers: int = 4,
    timeout: float = _TIMEOUT_DEFAULT,
    only: set[tuple] | None = None,
    limit: int | None = None,
    log: Callable[[str], None] = print,
) -> list[dict]:
    """Pose les fautes de `modules` (chemins relatifs a `root`) une a une, dans des copies, et rend un resultat par faute."""
    plan: list[tuple[Mutant, list[str]]] = []
    for module in modules:
        source = (root / module).read_text(encoding="utf-8-sig")
        mine = iter_mutants(source, module)
        if only is not None:
            mine = [m for m in mine if m.key() in only]
        plan += [(m, tests or default_tests(root, module)) for m in (mine[:limit] if limit else mine)]
    where = Path(tempfile.mkdtemp(prefix="certus_mutation_"))
    try:
        pool: queue.Queue = queue.Queue()
        for copy in make_copies(root, where, max(1, min(workers, len(plan) or 1))):
            pool.put(copy)
        _check_controls(root, modules, tests, pool, timeout, log)
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=pool.qsize()) as executor:
            futures = [executor.submit(_run_one, pool, root, m, t, timeout) for m, t in plan]
            for done in as_completed(futures):
                results.append(done.result())
                _log_result(log, len(results), len(plan), results[-1])
        return sorted(results, key=lambda r: (r["module"], r["line"], r["col"], r["kind"], r["new"]))
    finally:
        shutil.rmtree(where, ignore_errors=True)


def _check_controls(root: Path, modules: list[str], tests: list[str] | None, pool: queue.Queue, timeout: float, log: Callable) -> None:
    """Le temoin de chaque module : re-ecrit sans faute, il passe les tests, sinon on s'arrete."""
    workdir = pool.get()
    try:
        for module in modules:
            original = (root / module).read_bytes()
            target = workdir / module
            try:
                target.write_text(control_source(original.decode("utf-8-sig")), encoding="utf-8")
                status, code, output = run_tests(workdir, tests or default_tests(root, module), timeout)
            finally:
                target.write_bytes(original)
            if status != "survived":
                tail = "\n".join(output.splitlines()[-12:])
                raise SystemExit(f"LE TEMOIN ECHOUE pour {module} (statut {status}, code {code}) : les tests ne passent pas sans faute.\n{tail}")
            log(f"temoin de {module} : les tests passent sans faute")
    finally:
        pool.put(workdir)


def _log_result(log: Callable[[str], None], done: int, total: int, result: dict) -> None:
    symbol = {"killed": "tue     ", "timeout": "tue (t) ", "survived": "SURVIT  ", "error": "erreur  "}[result["status"]]
    log(f"[{done}/{total}] {symbol} {result['module']}:{result['line']} {result['kind']} {result['old']} -> {result['new']}")


def _survivors_key(results: list[dict]) -> set[tuple]:
    return {(r["module"], r["line"], r["col"], r["kind"], r["old"], r["new"]) for r in results if r["status"] == "survived"}


def _report(results: list[dict], log: Callable[[str], None]) -> None:
    for module, numbers in summarize(results).items():
        score = f"{100 * numbers['score']:.1f} %" if numbers["score"] is not None else "-"
        no_text = f"{100 * numbers['score_sans_chaines']:.1f} %" if numbers["score_sans_chaines"] is not None else "-"
        log(
            f"\n{module} : {numbers['mutants']} fautes, {numbers['killed']} tuees, {numbers['timeout']} timeouts, "
            f"{numbers['survived']} survivants, {numbers['error']} erreurs ; score {score}, sans chaines {no_text}"
        )
        for r in (r for r in results if r["module"] == module and r["status"] == "survived"):
            log(f"  SURVIVANT ligne {r['line']:>4} {r['kind']:<12} {r['old']} -> {r['new']}    | {r['text']}")


def survivor_key(result: dict) -> tuple[str, str, str, str, str]:
    """Ce qui identifie une faute d'une passe a l'autre : le module et le TEXTE de la ligne, pas son numero."""
    return (result["module"], result["text"], result["kind"], result["old"], result["new"])


def compare_baseline(results: list[dict], baseline: dict) -> tuple[list[dict], list[dict]]:
    """(survivants que la base n'accepte pas, survivants acceptes qui ne survivent plus dans les modules joues)."""
    accepted = {survivor_key(a): a for a in baseline.get("accepted_survivors", [])}
    survivors = [r for r in results if r["status"] == "survived"]
    unaccepted = [r for r in survivors if survivor_key(r) not in accepted]
    played = {r["module"] for r in results}
    alive = {survivor_key(r) for r in survivors}
    gone = [a for key, a in accepted.items() if a["module"] in played and key not in alive]
    return unaccepted, gone


def _check_baseline(results: list[dict], path: Path, log: Callable[[str], None]) -> int:
    unaccepted, gone = compare_baseline(results, json.loads(path.read_text(encoding="utf-8")))
    for r in gone:
        log(f"ACCEPTE QUI NE SURVIT PLUS (a retirer de {path.name}) : {r['module']} {r['kind']} {r['old']} -> {r['new']} | {r['text']}")
    for r in unaccepted:
        log(f"SURVIVANT NON ACCEPTE : {r['module']}:{r['line']} {r['kind']} {r['old']} -> {r['new']} | {r['text']}")
    log(f"base {path.name} : {len(unaccepted)} survivant(s) non accepte(s), {len(gone)} accepte(s) qui ne survit plus")
    return 1 if unaccepted else 0


def _git_head(root: Path) -> str | None:
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
    return done.stdout.strip() or None if done.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Pose des fautes une a une dans un module et compte celles que les tests voient.")
    parser.add_argument("modules", nargs="*", help="chemins relatifs a la racine du depot")
    parser.add_argument("--root", type=Path, default=ROOT, help="la racine du depot (les copies en viennent)")
    parser.add_argument("--tests", nargs="+", help="les tests a lancer (defaut : oracle, core et ceux qui nomment le module)")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1), help="nombre de copies et de fils")
    parser.add_argument("--timeout", type=float, default=_TIMEOUT_DEFAULT, help="secondes par faute avant de la compter tuee")
    parser.add_argument("--limit", type=int, help="les N premieres fautes de chaque module (essai)")
    parser.add_argument("--json", type=Path, help="ecrit le resultat complet dans ce fichier")
    parser.add_argument("--rerun", type=Path, help="un JSON precedent : ne rejoue que ses survivants")
    parser.add_argument("--baseline", type=Path, help="les survivants acceptes : un autre fait sortir le code 1")
    args = parser.parse_args(argv)

    modules = list(args.modules)
    only = None
    if args.rerun:
        previous = json.loads(args.rerun.read_text(encoding="utf-8"))
        only = _survivors_key(previous["mutants"])
        modules = modules or sorted({k[0] for k in only})
    if not modules:
        parser.error("aucun module : donner des chemins, ou --rerun")
    missing = [m for m in modules if not (args.root / m).is_file()]
    if missing:
        print(f"MODULE ABSENT : {', '.join(missing)}", file=sys.stderr)
        return 2
    started = time.monotonic()
    results = run_pilot(args.root, modules, args.tests, args.workers, args.timeout, only, args.limit)
    _report(results, print)
    print(f"\n{len(results)} fautes en {time.monotonic() - started:.0f} s")
    if args.json:
        payload = {
            "commit": _git_head(args.root),
            "runner": "NUMBA_DISABLE_JIT=1 pytest -x, une copie du depot par fil",
            "modules": summarize(results),
            "mutants": results,
        }
        args.json.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return _check_baseline(results, args.baseline, print) if args.baseline else 0


if __name__ == "__main__":
    sys.exit(main())
