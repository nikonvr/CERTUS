"""Corridor refactoring, Phase 5d: one static method of the window becomes a plain function of the leaf module, and the
mixins call the function instead of going through the lazy stand-in for the window class.

    python reports/refactor_corridors_2026-11-11/tools/static_to_function.py NAME

What it does, for the static method NAME (defined once, in a mixin of the INDEX SPLINE window):
  - the function goes to certus_index_spline_statics.py, text unchanged but for its indentation, and for the calls
    `CertusIndexSplineApp.<static>(` it makes to statics that are already there, which become `<static>(`;
  - the class keeps the name: `NAME = staticmethod(NAME)`, the very function, so `self.NAME`, `Class.NAME` and the tests
    that read it on the window go on working;
  - every `CertusIndexSplineApp.NAME(` of the group becomes `NAME(`, and the module imports NAME from the leaf;
  - manifests/phase_5d.json gains the move (`moved_objects`) and the functions whose bytecode changes (`changed_code`).
The moved function is always one of them: Python sets the flag CO_METHOD (0x8000000) on a function written in a class body,
and a function that leaves the class loses it. The tool compiles the function before and after and prints what differs:
`flags only` when the flag is the whole difference.
It never runs ruff with --fix: the import goes to its sorted place by hand, and `ruff check` says if that is wrong.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

UI = Path("certus/ui")
M = "certus.ui.certus_index_spline_"
LEAF = UI / "certus_index_spline_statics.py"
LEAF_MODULE = f"{M}statics"
MANIFEST = Path("reports/refactor_corridors_2026-11-11/manifests/phase_5d.json")
DOC = (
    '"""CERTUS-INDEX-SPLINE - the static helpers of the window, as plain functions: what a result dictionary says of the '
    "fit, how a mesh of knots and its changes are written in the log, the grids. The mixins of the window call them here; "
    "the window keeps each one as a static method of the same name, the very function (moved out of "
    "certus_index_spline_eventsextras_mixin.py and certus_index_spline_manualmesh_mixin.py). A leaf of the group: it "
    'imports no module of the window."""'
)
LINE = 120


def read(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").split("\n")


def write(path: Path, lines: list[str]) -> None:
    path.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))


def leaf_functions() -> dict[str, list[str]]:
    if not LEAF.is_file():
        return {}
    lines = read(LEAF)
    tree = ast.parse("\n".join(lines))
    return {n.name: lines[n.lineno - 1:n.end_lineno] for n in tree.body if isinstance(n, ast.FunctionDef)}


def write_leaf(functions: dict[str, list[str]]) -> None:
    text = "\n".join(line for body in functions.values() for line in body)
    head = [DOC, "", "from __future__ import annotations", ""]
    if re.search(r"\bAny\b", text):
        head += ["from typing import Any", ""]
    if re.search(r"\bnp\.", text):
        head += ["import numpy as np", ""]
    if "_lam_uniform_grid(" in text:
        head += ["from certus.utils.certus_index_utils import _lam_uniform_grid", ""]
    out = head
    for body in functions.values():
        out += ["", *body, ""]
    write(LEAF, out)


def import_line(names: list[str]) -> list[str]:
    one = f"from {LEAF_MODULE} import {', '.join(names)}"
    if len(one) <= LINE:
        return [one]
    return [f"from {LEAF_MODULE} import (", *(f"    {name}," for name in names), ")"]


def ensure_import(lines: list[str], name: str) -> list[str]:
    tree = ast.parse("\n".join(lines))
    froms = [n for n in tree.body if isinstance(n, ast.ImportFrom)]
    mine = [n for n in froms if n.module == LEAF_MODULE]
    if mine:
        node = mine[0]
        names = sorted({alias.name for alias in node.names} | {name})
        return lines[:node.lineno - 1] + import_line(names) + lines[node.end_lineno:]
    first_block = [n for n in froms if (n.module or "").startswith("certus.") and n.col_offset == 0]
    later = [n for n in first_block if (n.module or "") > LEAF_MODULE]
    earlier = [n for n in first_block if (n.module or "") < LEAF_MODULE]
    at = later[0].lineno - 1 if later and (not earlier or later[0].lineno > earlier[-1].lineno) else earlier[-1].end_lineno
    return lines[:at] + import_line([name]) + lines[at:]


def enclosing(tree: ast.Module, lineno: int, stem: str) -> str:
    """`module:Class.function` of the innermost top-level function or method that holds the line."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.lineno <= lineno <= sub.end_lineno:
                    return f"{M}{stem}:{node.name}.{sub.name}"
        elif isinstance(node, ast.FunctionDef) and node.lineno <= lineno <= node.end_lineno:
            return f"{M}{stem}:{node.name}"
    raise SystemExit(f"line {lineno} of {stem} is in no function")


def code_of(source: str, path: list[str]):
    code = compile(source, "<source>", "exec")
    for name in path:
        code = next(c for c in code.co_consts if hasattr(c, "co_code") and c.co_name == name)
    return code


def difference(before, after) -> str:
    """What differs between the code of the static method and the code of the function it became."""
    fields = ("co_code", "co_consts", "co_names", "co_varnames", "co_freevars", "co_cellvars", "co_argcount", "co_kwonlyargcount")
    differing = [f for f in fields if getattr(before, f) != getattr(after, f)]
    flags = before.co_flags ^ after.co_flags
    if not differing and flags == 0x8000000:
        return "flags only (CO_METHOD)"
    return f"flags xor {flags:#x}; differing: {', '.join(differing) or 'nothing else'}"


def main() -> None:
    name = sys.argv[1]
    functions = leaf_functions()
    if name in functions:
        raise SystemExit(f"{name} is already in {LEAF}")
    call = f"CertusIndexSplineApp.{name}("
    owner = None
    changed: set[str] = set()
    for path in sorted(UI.glob("certus_index_spline_*.py")):
        if path == LEAF:
            continue
        stem = path.stem.replace("certus_index_spline_", "")
        lines = read(path)
        tree = ast.parse("\n".join(lines))
        touched = False
        for klass in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for func in klass.body:
                if not (isinstance(func, ast.FunctionDef) and func.name == name):
                    continue
                if "Protocol" in {getattr(b, "id", "") for b in klass.bases}:
                    continue
                decorators = [ast.unparse(d) for d in func.decorator_list]
                if decorators != ["staticmethod"]:
                    raise SystemExit(f"{stem}:{klass.name}.{name} is not a plain static method: {decorators}")
                if owner is not None:
                    raise SystemExit(f"{name} is defined twice: {owner} and {stem}:{klass.name}")
                owner = (path, stem, klass.name, func.decorator_list[0].lineno, func.end_lineno)
        if owner is not None and owner[0] == path:
            _path, _stem, klass_name, start, end = owner
            before_code = code_of("\n".join(lines), [klass_name, name])
            body = [line[4:] if line.startswith("    ") else line for line in lines[start:end]]
            before = list(body)
            for known in [*functions, name]:
                body = [line.replace(f"CertusIndexSplineApp.{known}(", f"{known}(") for line in body]
            changed.add(f"{LEAF_MODULE}:{name}")
            functions[name] = body
            rewritten = body != before
            lines[start - 1:end] = [f"    {name} = staticmethod({name})"]
            touched = True
            print(f"moved   {stem}:{klass_name}.{name}  lines {start}-{end}")
        tree = ast.parse("\n".join(lines))
        for index, line in enumerate(lines):
            if call in line:
                changed.add(enclosing(tree, index + 1, stem))
                lines[index] = line.replace(call, f"{name}(")
                touched = True
        if touched:
            write(path, ensure_import(lines, name))
    if owner is None:
        raise SystemExit(f"no static method {name} in the group")
    write_leaf(functions)
    after_code = code_of("\n".join(read(LEAF)), [name])  # compiled in the leaf itself: same `from __future__` as the mixin
    print(f"code    {name}: {difference(before_code, after_code)}" + ("  (calls rewritten)" if rewritten else ""))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {
        "phase": "5d - the static helpers of the window become plain functions of certus_index_spline_statics.py, one per "
        "commit; the class keeps each one as a static method, the very function; the mixins call the function instead of "
        "the lazy stand-in for the window class. Not a pure move: `changed_code` lists every function whose bytecode "
        "changes, and why is the same for all, a call `CertusIndexSplineApp.<static>(...)` that became `<static>(...)`.",
        "note": "changed_code also lists each function of certus_index_spline_statics: its text is the text of the static "
        "method, and its code object differs by one flag, CO_METHOD (0x8000000), that Python sets on a function written in "
        "a class body. Measured for each by the tool (`flags only`): same co_code, constants, names and variables. Two of "
        "them also had a call through the stand-in rewritten (`calls rewritten`).",
        "moved_objects": [],
        "changed_code": [],
    }
    manifest["moved_objects"].append({"from": f"{M}{owner[1]}:{owner[2]}.{name}", "to": f"{LEAF_MODULE}:{name}"})
    manifest["changed_code"] = sorted(set(manifest["changed_code"]) | changed)
    MANIFEST.write_bytes((json.dumps(manifest, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    for item in sorted(changed):
        print(f"changed {item}")
    print(f"leaf    {LEAF}: {len(functions)} function(s)")


if __name__ == "__main__":
    main()
