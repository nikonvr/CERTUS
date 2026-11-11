"""Corridor refactoring, step 1 of a slice extraction: what the methods to move load from their modules.

    python reports/refactor_corridors_2026-11-11/tools/plan_move.py SNAPSHOT stem:Class.method [stem:Class.method ...]

For the methods to move, prints each global name they load, what it resolves to in the origin module (from the guard
snapshot), the top-level statement of the origin module that binds it, and the test seams on that (module, name).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PREFIX = "certus.ui.certus_index_spline_"


def binding(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    extra = f" as {alias.asname}" if alias.asname else ""
                    return f"from {node.module} import {alias.name}{extra}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (alias.asname or alias.name.partition(".")[0]) == name:
                    extra = f" as {alias.asname}" if alias.asname else ""
                    return f"import {alias.name}{extra}"
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return f"<defined here, line {node.lineno}>"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(n, ast.Name) and n.id == name for t in targets for n in ast.walk(t)):
                return f"<assigned here, line {node.lineno}: {ast.unparse(node)[:80]}>"
    return "<no top-level binding>"


def main() -> None:
    snapshot = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    by_id = {f"{r['module']}:{r['qualname']}": r for r in snapshot["functions"]}
    seams: dict[tuple[str, str], list[str]] = {}
    for seam in snapshot["seams"]:
        seams.setdefault((seam[0], seam[1]), []).append(str(seam[2:]))
    rows: dict[str, dict[str, set[str]]] = {}
    for spec in sys.argv[2:]:
        stem, _, qualname = spec.partition(":")
        module = PREFIX + stem
        record = by_id.get(f"{module}:{qualname}")
        if record is None:
            print(f"MISSING  {spec}")
            continue
        if "wrapped" in record:
            print(f"WRAPPED  {spec} (decorated)")
        tree = ast.parse(Path(module.replace(".", "/") + ".py").read_text(encoding="utf-8-sig"))
        for name, index in record.get("globals", {}).items():
            row = rows.setdefault(name, {"is": set(), "from": set(), "seams": set(), "users": set()})
            row["is"].add(snapshot["descriptors"][index][:90])
            row["from"].add(f"{stem}: {binding(tree, name)}")
            row["users"].add(qualname.rpartition(".")[2])
            for where in seams.get((module, name), ()):
                row["seams"].add(f"{stem}.{name} {where[:110]}")
    for name in sorted(rows):
        row = rows[name]
        print(f"{name}")
        for what in sorted(row["is"]):
            print(f"    is    {what}")
        for what in sorted(row["from"]):
            print(f"    from  {what}")
        for what in sorted(row["seams"]):
            print(f"    SEAM  {what}")
        print(f"    used by {len(row['users'])}: {', '.join(sorted(row['users']))[:150]}")


if __name__ == "__main__":
    main()
