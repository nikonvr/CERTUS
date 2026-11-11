"""Corridor refactoring, step 2 of a slice extraction: the move itself, text unchanged.

    python reports/refactor_corridors_2026-11-11/tools/move.py SPEC.json

Moves methods, text unchanged (decorators and the comment lines right above them included), from their classes to ONE
new class in a new module. SPEC: {"target": path, "class": name, "module_doc": str, "class_doc": str,
"imports": [lines], "methods": [[stem, Class, method], ...]}. The imports of the new module are given, not guessed.
Prints what it moved and the classes it left without a statement.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

UI = Path("certus/ui")


def read(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").split("\n")


def write(path: Path, lines: list[str]) -> None:
    path.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    by_file: dict[Path, list[tuple[str, str]]] = {}
    for stem, klass, method in spec["methods"]:
        by_file.setdefault(UI / f"certus_index_spline_{stem}.py", []).append((klass, method))
    taken: dict[tuple[str, str], list[str]] = {}
    for path, wanted in by_file.items():
        lines = read(path)
        tree = ast.parse("\n".join(lines))
        spans = []
        for klass, method in wanted:
            node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == klass)
            func = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method)
            start = min([func.lineno, *(d.lineno for d in func.decorator_list)])
            while lines[start - 2].strip().startswith("#"):
                start -= 1
            spans.append((start, func.end_lineno, klass, method))
        for start, end, klass, method in sorted(spans, reverse=True):
            taken[(klass, method)] = lines[start - 1:end]
            stop = end
            while stop < len(lines) and lines[stop].strip() == "":
                stop += 1
            del lines[start - 1:stop]
            print(f"moved  {path.stem.replace('certus_index_spline_', '')}:{klass}.{method}  lines {start}-{end} ({end - start + 1})")
        while lines and lines[-1] == "":
            lines.pop()
        lines.append("")
        tree = ast.parse("\n".join(lines))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                rest = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
                if not rest:
                    print(f"EMPTY  {path.name}:{node.name} has no statement left (docstring: {len(node.body)})")
        write(path, lines)
    out = [f'"""{spec["module_doc"]}"""', "", "from __future__ import annotations", "", *spec["imports"], "", ""]
    out += [f"class {spec['class']}:", f'    """{spec["class_doc"]}"""', ""]
    for _stem, klass, method in spec["methods"]:
        out += [*taken[(klass, method)], ""]
    write(Path(spec["target"]), out)
    print(f"wrote  {spec['target']}  {len(out)} lines")


if __name__ == "__main__":
    main()
