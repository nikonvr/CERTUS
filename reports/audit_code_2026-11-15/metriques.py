"""Static metrics over every tracked `certus/` module (ast only, nothing is imported or run).

    python reports/audit_code_2026-11-15/metriques.py > reports/audit_code_2026-11-15/metriques.txt
"""

from __future__ import annotations

import ast
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
files = [f for f in subprocess.run(["git", "ls-files", "certus/*.py"], cwd=ROOT, capture_output=True, text=True,
                                   check=True).stdout.split() if f.endswith(".py")]
pkg_of = lambda f: f.split("/")[1] if f.count("/") > 1 else "(racine)"  # noqa: E731
stats = collections.defaultdict(lambda: collections.Counter())
funcs = []
imports = collections.Counter()
broad = []
for f in files:
    src = (ROOT / f).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        print("SYNTAX", f, exc)
        continue
    pk = pkg_of(f)
    lines = src.count("\n") + 1
    stats[pk]["fichiers"] += 1
    stats[pk]["lignes"] += lines
    stats[pk]["fichiers>1000"] += lines > 1000
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = (node.end_lineno or node.lineno) - node.lineno + 1
            a = node.args
            nargs = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs) + bool(a.vararg) + bool(a.kwarg)
            depth = 0

            def walk(n_, d):
                global depth
                depth = max(depth, d)
                for c in ast.iter_child_nodes(n_):
                    walk(c, d + isinstance(c, (ast.If, ast.For, ast.While, ast.Try, ast.With)))
            walk(node, 0)
            funcs.append((n, nargs, depth, f, node.name))
            stats[pk]["fonctions"] += 1
            stats[pk]["fonctions>100l"] += n > 100
            stats[pk]["fonctions>10args"] += nargs > 10
            stats[pk]["imbrication>=6"] += depth >= 6
            stats[pk]["sans_docstring"] += ast.get_docstring(node) is None and not node.name.startswith("_")
        elif isinstance(node, ast.ExceptHandler):
            t = node.type
            if t is None or (isinstance(t, ast.Name) and t.id in ("Exception", "BaseException")):
                stats[pk]["except_large"] += 1
                if any(isinstance(b, ast.Pass) for b in node.body) and len(node.body) == 1:
                    stats[pk]["except_large_pass"] += 1
                    broad.append(f"{f}:{node.lineno}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            if mod and mod.startswith("certus."):
                tgt = mod.split(".")[1]
                if tgt != pk:
                    imports[(pk, tgt)] += 1
    stats[pk]["TODO/FIXME"] += len(re.findall(r"#\s*(TODO|FIXME|XXX|HACK)", src))
    stats[pk]["emojis"] += len(re.findall(r"[\U0001F300-\U0001FAFF]", src))
out = {"par_paquet": {k: dict(v) for k, v in sorted(stats.items())},
       "aretes_entre_paquets": {f"{a}->{b}": n for (a, b), n in sorted(imports.items())},
       "fonctions_les_plus_longues": [f"{n} l, {na} args, prof {d}: {f}::{nm}" for n, na, d, f, nm in sorted(funcs, reverse=True)[:25]],
       "fonctions_les_plus_d_arguments": [f"{na} args: {f}::{nm}" for n, na, d, f, nm in sorted(funcs, key=lambda x: -x[1])[:15]],
       "except_large_pass_exemples": broad[:20], "except_large_pass_total": len(broad)}
lens = sorted(n for n, *_ in funcs)
out["longueur_fonction"] = {"n": len(lens), "mediane": lens[len(lens) // 2], "p90": lens[int(0.9 * len(lens))], "max": lens[-1]}
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
