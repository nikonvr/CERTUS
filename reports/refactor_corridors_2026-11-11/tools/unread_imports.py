"""Corridor refactoring, Phase 8: the names a module of the INDEX SPLINE group imports and no longer reads, since the moves.

    python reports/refactor_corridors_2026-11-11/tools/unread_imports.py REVISION

Compares each module of the group with what it was at REVISION (the commit of Phase 0). A name counts when the module
imports it at module level today, imported it then, read it then and does not read it now: a move took its last reader
away. The names stay where they are (a module keeps the names it exposed: a test or another module may read them there);
this only lists them. Prints a Markdown table.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

UI = "certus/ui"


def imported_and_read(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported |= {alias.asname or alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            imported |= {alias.asname or alias.name.partition(".")[0] for alias in node.names}
    read = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    quoted = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return imported, read | (quoted & imported)  # a name quoted in `__all__` is exposed on purpose


def main() -> None:
    revision = sys.argv[1]
    listed = subprocess.run(["git", "ls-files", f"{UI}/certus_index_spline*.py"], capture_output=True, text=True, check=True)
    rows = []
    for path in sorted(p for p in listed.stdout.split("\n") if p):
        then = subprocess.run(["git", "show", f"{revision}:{path}"], capture_output=True, check=False)
        if then.returncode != 0:
            continue  # a module the refactoring created
        imported_then, read_then = imported_and_read(then.stdout.decode("utf-8-sig"))
        imported_now, read_now = imported_and_read(Path(path).read_text(encoding="utf-8-sig"))
        left = sorted((imported_now & imported_then & read_then) - read_now)
        if left:
            rows.append((Path(path).stem.replace("certus_index_spline_", ""), left))
    print("| Module (`certus_index_spline_…`) | Noms importés que le module ne lit plus | Nombre |")
    print("|---|---|---|")
    for stem, names in rows:
        print(f"| `{stem}` | {', '.join(f'`{n}`' for n in names)} | {len(names)} |")
    print(f"\nTotal : {sum(len(names) for _, names in rows)} noms dans {len(rows)} modules.")


if __name__ == "__main__":
    main()
