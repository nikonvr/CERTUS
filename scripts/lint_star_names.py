"""Snapshot, for every module that does `from X import *`, the names it USES and finds bound.

Ruff cannot see what a module takes through `import *` (F405 is ignored): removing a name from
the source module breaks it silently. Used for UP035 and prescribed for R9 (docs/ETAT.md).

Usage: python scripts/lint_star_names.py OUT.json   (run from the repo root, QT offscreen)
A name used in the module's AST and present in its namespace after import is recorded; a later
snapshot must contain at least the same pairs, or a star import lost a name.
"""
import ast
import importlib
import json
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())

files = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout.split()
out = {}
for f in files:
    if f.startswith(("docs/", "tests/")):
        continue
    src = open(f, encoding="utf-8-sig").read()
    if "import *" not in src:
        continue
    tree = ast.parse(src)
    if not any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names) for n in ast.walk(tree)):
        continue
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    modname = f[:-3].replace("/", ".")
    try:
        mod = importlib.import_module(modname)
    except Exception as exc:  # recorded, so that a module that stops importing is seen too
        out[modname] = {"error": f"{type(exc).__name__}: {exc}"}
        continue
    ns = vars(mod)
    out[modname] = sorted(n for n in used if n in ns)

json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True)
errors = [m for m, v in out.items() if isinstance(v, dict)]
print(f"{len(out)} star-importing modules snapshotted; import errors: {errors}")
