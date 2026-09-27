"""Snapshot the FINAL namespace of given modules: what each name is bound to once imported.

A lint change that removes or moves imports must leave this snapshot unchanged -- except for the
source of the functions it edits on purpose. Used for R8 (F811) and prescribed for R9 (docs/ETAT.md).

Usage: python scripts/lint_ns_snapshot.py OUT.json mod1 mod2 ...   (repo root, QT offscreen)
For a function/class: module, qualname and a hash of its source; for a module: its name;
otherwise the type and, for small immutable values, the value. Two snapshots must be equal.
"""
import hashlib
import importlib
import inspect
import json
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())


def describe(obj):
    if isinstance(obj, types.ModuleType):
        return ["module", obj.__name__]
    if inspect.isfunction(obj) or inspect.isclass(obj) or hasattr(obj, "py_func"):
        target = getattr(obj, "py_func", obj)
        try:
            src = inspect.getsource(target)
        except (OSError, TypeError):
            src = ""
        return ["code", getattr(target, "__module__", "?"), getattr(target, "__qualname__", "?"),
                hashlib.sha1(src.encode()).hexdigest()[:12]]
    if isinstance(obj, (int, float, str, bool, bytes, type(None), tuple, frozenset)):
        return ["value", type(obj).__name__, repr(obj)[:200]]
    return ["object", type(obj).__module__ + "." + type(obj).__qualname__]


out = {}
for name in sys.argv[2:]:
    try:
        mod = importlib.import_module(name)
    except Exception as exc:
        out[name] = {"error": f"{type(exc).__name__}: {exc}"}
        continue
    out[name] = {k: describe(v) for k, v in sorted(vars(mod).items()) if k not in ("__builtins__", "__cached__", "__loader__", "__spec__", "__file__")}
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True)
print(f"{len(out)} modules snapshotted; errors: {[m for m, v in out.items() if 'error' in v]}")
