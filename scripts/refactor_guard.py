"""REFACTOR GUARD: a move of code is proved, not asserted.

    python scripts/refactor_guard.py snapshot --out FILE
    python scripts/refactor_guard.py compare REFERENCE NEW [--manifest FILE ...] [--full]
    python scripts/refactor_guard.py report FILE [--window NAME] [--full]

`snapshot` imports the application windows of THIS tree in a fresh interpreter (Qt offscreen) and writes down what a pure
move of code has to leave as it was:

  - the surface of each window class, through its whole MRO: for every attribute a project class defines, the class that
    wins the lookup, its kind (function, staticmethod, classmethod, property, signal, data), a fingerprint of its bytecode
    (constants and nested functions included, file name and line numbers left out), its signature, and the object each
    global name it loads resolves to in ITS module;
  - the MRO itself, and the names that more than one project class of that MRO defines;
  - the namespace of each module of the INDEX SPLINE group, name by name, and the classes these modules define;
  - what the facade module CERTUS_INDEX_SPLINE resolves each reachable name to, and which of its submodules hold it;
  - the seams: every module attribute a test replaces (monkeypatch.setattr, mock.patch, patch.object), read in the test
    sources.

`compare` holds a later snapshot against the reference. Without a manifest, anything that differs is reported. A manifest
(JSON, one per phase, several can be given) names the differences a phase is ALLOWED to make, and nothing else passes:

    {"moved_methods": [{"name": "_f", "from": "pkg.old:OldMixin", "to": "pkg.new:NewMixin"}],
     "moved_objects": [{"from": "pkg.old:helper", "to": "pkg.new:helper"}],
     "changed_code": ["pkg.new:helper"], "rebound": ["pkg.old:helper"],
     "new_classes": ["pkg.new:NewMixin"], "removed_from_mro": [], "added_attributes": ["pkg.win:Window.name"],
     "acknowledged_seams": {"pkg.old:np": "why the tests that replace it do not reach the moved code"}}

A moved function keeps its bytecode and its signature, and each global it loads resolves to the same object in the module
it moved to. A method that leaves a class for one this class does not inherit is gone from it: its `moved_methods` entry is
what allows that, provided the class it names defines the method, unchanged. A name that a module exposed stays there. A moved function that loads a global which the tests replace in the
module it LEFT fails the comparison until a manifest acknowledges it: the test would patch a module the code no longer reads.

`report` prints, from a snapshot, the names that several project classes of a window define and the seams of the group.

What the guard does not see: the module name that `logging` calls print when they pass `__name__`, the qualified names in
tracebacks, the `__annotations__` of a module, and whatever only an instance holds. Bytecode belongs to one Python version:
both snapshots must come from the same one.

Exit code: 0 `GUARD=OK`, 1 `GUARD=DIFF`, 2 the command itself is wrong (bad call, wrong tree, version mismatch).
"""

from __future__ import annotations

import annotationlib
import argparse
import ast
import builtins
import dis
import hashlib
import importlib
import inspect
import json
import os
import platform
import re
import subprocess
import sys
import types
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 1
PROJECT = ("certus", "CERTUS")

#: The application windows, as tests/unit/test_self_attributes_are_defined.py lists them.
WINDOWS = (
    "certus.ui.certus_design_ui:CertusDesignApp",
    "certus.ui.certus_field_ui:CertusFieldApp",
    "certus.ui.certus_index_ui:CertusIndexApp",
    "certus.ui.certus_index_spline_ui:CertusIndexSplineApp",
    "CERTUS_RE:CertusREApp",
    "certus.ui.certus_strat_ui:CertusStratApp",
    "certus.ui.certus_metal_single_gui:CertusMetalSingleApp",
    "certus.ui.certus_metal_bilayer_gui:CertusMetalBilayerApp",
    "CERTUS_HUB:CertusHub",
)
#: The modules whose namespace is recorded: the INDEX SPLINE group, and the two modules other families borrow from.
NAMESPACES = (
    "certus/ui/certus_index_spline*.py",
    "certus/spline/certus_index_spline_core.py",
    "certus/spline/certus_index_spline_excel_export.py",
    "certus/workers/certus_strat_workers.py",
    "certus/utils/certus_index_utils.py",
)
FACADES = ("CERTUS_INDEX_SPLINE",)
#: Pairs of classes (by name) that follow one another in an MRO and have to go on doing so.
MUST_STAY_ADJACENT = (("_CorridorWorkerMixin", "_CorridorTabMixin"),)

#: Globals that name the module itself: they differ as soon as a function changes module, and that is the move.
DRIFTING_GLOBALS = frozenset(
    {"__name__", "__file__", "__spec__", "__package__", "__loader__", "__cached__", "__builtins__", "__doc__"}
)
#: What the class statement writes by itself: not an attribute anyone defined.
CLASS_MACHINERY = frozenset(
    {
        "__module__", "__dict__", "__weakref__", "__doc__", "__qualname__", "__firstlineno__", "__static_attributes__",
        "__annotations__", "__annotate__", "__annotate_func__", "__annotations_cache__", "__classdictcell__",
        "__classcell__", "__orig_bases__", "__parameters__", "__type_params__", "__abstractmethods__", "_abc_impl",
    }
)
#: Written by a metaclass at each import, with the id() of the class inside: not an attribute anyone defined either.
CLASS_MACHINERY_PREFIXES = ("__pydantic_",)
#: Module names whose value is made anew at each run (`_env` holds a run identifier with the time in it): the name is
#: recorded, and its type, not its value.
VOLATILE_NAMES = frozenset({"_env"})
SHOWN = 40
_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+|0x[0-9A-Fa-f]{8,}")


class GuardError(Exception):
    """The command cannot answer: wrong tree, snapshots that cannot be compared, a manifest that cannot be read."""


# =============================================================================
# Fingerprints
# =============================================================================
def _root_pattern(root: Path) -> re.Pattern[str]:
    """The spellings of `root` a repr can hold: as it is, with doubled backslashes (inside a quoted string), with slashes."""
    plain = str(root)
    spellings = sorted({plain, plain.replace("\\", "\\\\"), root.as_posix()}, key=len, reverse=True)
    return re.compile("|".join(re.escape(s) for s in spellings), re.IGNORECASE)


def stable_repr(value: Any, root_pattern: re.Pattern[str]) -> str:
    """`repr(value)` without what changes from one run or one checkout to the next: addresses, set order, the tree path."""
    try:
        text = repr(sorted(repr(v) for v in value)) if isinstance(value, (set, frozenset)) else repr(value)
    except Exception:  # a repr that raises is still a value: all it has to do is say the same thing twice
        text = f"<unrepresentable {type(value).__qualname__}>"
    return root_pattern.sub("<ROOT>", _ADDRESS.sub("", text))


def _constant(value: Any) -> Any:
    if isinstance(value, types.CodeType):
        return ("code", code_fingerprint(value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_constant(v) for v in value))
    if isinstance(value, frozenset):
        return ("frozenset", tuple(sorted(repr(_constant(v)) for v in value)))
    return (type(value).__name__, repr(value))


def code_fingerprint(code: types.CodeType) -> str:
    """What the code does, and nothing about where it was written: no file name, no line number, no qualified name."""
    parts = (
        code.co_name, code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_flags, code.co_code,
        tuple(_constant(c) for c in code.co_consts), code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars,
        code.co_exceptiontable,
    )
    return hashlib.sha256(repr(parts).encode("utf-8", "backslashreplace")).hexdigest()[:20]


def global_names(code: types.CodeType) -> set[str]:
    """The global names `code` loads or stores, nested functions included."""
    names = {
        i.argval
        for i in dis.get_instructions(code)
        if ("GLOBAL" in i.opname or i.opname == "LOAD_NAME") and isinstance(i.argval, str)
    }
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            names |= global_names(constant)
    return names


def _cell_value(cell: Any) -> Any:
    try:
        return cell.cell_contents
    except ValueError:
        return "<empty cell>"


def _signature(func: types.FunctionType, root_pattern: re.Pattern[str]) -> str:
    try:  # annotations as text: evaluating them would need the names a module imports for the type checker only
        signature = inspect.signature(func, follow_wrapped=False, annotation_format=annotationlib.Format.STRING)
    except (TypeError, ValueError):
        return "<no signature>"
    return root_pattern.sub("<ROOT>", _ADDRESS.sub("", str(signature)))


def class_id(klass: type) -> str:
    return f"{klass.__module__}:{klass.__qualname__}"


# =============================================================================
# Snapshot
# =============================================================================
class Recorder:
    """Builds a snapshot. Descriptors and functions are stored once and referred to by index."""

    def __init__(self, root: Path, project: tuple[str, ...]) -> None:
        self.project = project
        self.root_pattern = _root_pattern(root)
        self.descriptors: list[str] = []
        self._descriptor_index: dict[str, int] = {}
        self.functions: list[dict[str, Any]] = []
        self._function_index: dict[int, int] = {}
        self._alive: list[Any] = []  # an id() is only unique while its object lives
        self.classes: dict[str, dict[str, Any]] = {}

    def is_project(self, module_name: str | None) -> bool:
        return bool(module_name) and str(module_name).startswith(self.project)

    def _intern(self, text: str) -> int:
        index = self._descriptor_index.get(text)
        if index is None:
            index = self._descriptor_index[text] = len(self.descriptors)
            self.descriptors.append(text)
        return index

    def describe(self, value: Any) -> int:
        """Which object this is: a module, a class or a function by where it is defined, anything else by type and repr."""
        if isinstance(value, types.ModuleType):
            return self._intern(f"module:{value.__name__}")
        if isinstance(value, type):
            return self._intern(f"class:{value.__module__}:{value.__qualname__}")
        if isinstance(value, types.MethodType):
            value = value.__func__
        if isinstance(value, (types.FunctionType, types.BuiltinFunctionType)):
            return self._intern(f"func:{value.__module__}:{value.__qualname__}")
        digest = hashlib.sha256(stable_repr(value, self.root_pattern).encode("utf-8", "backslashreplace")).hexdigest()
        return self._intern(f"val:{type(value).__module__}.{type(value).__qualname__}:{digest[:16]}")

    def named(self, name: str, value: Any) -> int:
        """`describe(value)`, unless the name is one whose value changes at each run."""
        if name in VOLATILE_NAMES:
            return self._intern(f"val:{type(value).__module__}.{type(value).__qualname__}:<made anew at each run>")
        return self.describe(value)

    def _global(self, namespace: dict[str, Any], name: str) -> int:
        if name in namespace:
            return self.named(name, namespace[name])
        return self._intern(f"builtin:{name}" if hasattr(builtins, name) else "<unbound>")

    def function(self, func: Any) -> int:
        """The record of a callable. A function wrapped by a decorator carries the record of what it wraps."""
        known = self._function_index.get(id(func))
        if known is not None:
            return known
        index = self._function_index[id(func)] = len(self.functions)
        self._alive.append(func)
        record: dict[str, Any] = {
            "module": getattr(func, "__module__", None),
            "qualname": getattr(func, "__qualname__", type(func).__qualname__),
        }
        self.functions.append(record)
        if not isinstance(func, types.FunctionType):
            record["value"] = self.describe(func)
            return index
        record["code"] = code_fingerprint(func.__code__)
        record["signature"] = _signature(func, self.root_pattern)
        record["globals"] = {n: self._global(func.__globals__, n) for n in sorted(global_names(func.__code__))}
        if func.__closure__:
            record["closure"] = [self.describe(_cell_value(cell)) for cell in func.__closure__]
        wrapped = getattr(func, "__wrapped__", None)
        if callable(wrapped):
            record["wrapped"] = self.function(wrapped)
        return index

    def _attribute(self, raw: Any, project_owned: bool) -> dict[str, Any]:
        if isinstance(raw, staticmethod):
            return {"kind": "staticmethod", "impl": [self.function(raw.__func__)]}
        if isinstance(raw, classmethod):
            return {"kind": "classmethod", "impl": [self.function(raw.__func__)]}
        if isinstance(raw, property):
            parts = (raw.fget, raw.fset, raw.fdel)
            return {"kind": "property", "impl": [None if f is None else self.function(f) for f in parts]}
        if isinstance(raw, types.FunctionType):
            return {"kind": "function", "impl": [self.function(raw)]}
        if type(raw).__name__ == "pyqtSignal":
            return {"kind": "signal", "value": self._intern(f"signal:{stable_repr(raw, self.root_pattern)}")}
        return {"kind": "data" if project_owned else "foreign", "value": self.describe(raw)}

    def klass(self, klass: type) -> str:
        """Records the surface of `klass`: every name a project class of its MRO defines, as the lookup resolves it."""
        identity = class_id(klass)
        if identity in self.classes:
            return identity
        mro = klass.__mro__
        names: set[str] = set()
        for base in mro:
            if self.is_project(base.__module__):
                names.update(vars(base))
        attrs: dict[str, dict[str, Any]] = {}
        for name in sorted(names - CLASS_MACHINERY):
            if name.startswith(CLASS_MACHINERY_PREFIXES):
                continue
            holders = [base for base in mro if name in vars(base)]
            owned = self.is_project(holders[0].__module__)
            entry = {"owner": class_id(holders[0]), **self._attribute(vars(holders[0])[name], owned)}
            project_holders = [class_id(base) for base in holders if self.is_project(base.__module__)]
            if len(project_holders) > 1:
                entry["defined_by"] = project_holders
            attrs[name] = entry
        self.classes[identity] = {"mro": [class_id(base) for base in mro], "attrs": attrs}
        return identity

    def module(self, module: types.ModuleType) -> dict[str, list[int]]:
        """The namespace of `module`: each name and the object behind it; a function defined there brings its record."""
        names: dict[str, list[int]] = {}
        for name, value in sorted(vars(module).items()):
            if name.startswith("__") and name.endswith("__") and name != "__all__":
                continue
            entry = [self.named(name, value)]
            if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
                entry.append(self.function(value))
            elif isinstance(value, type) and value.__module__ == module.__name__:
                self.klass(value)
            names[name] = entry
        return names

    def facade(self, facade: types.ModuleType) -> dict[str, list[Any]]:
        """What the facade answers for each name its submodules hold, and which of them hold it (a write reaches all)."""
        submodules = list(getattr(facade, "_submodules", ()))
        reachable = sorted({n for sub in submodules for n in vars(sub) if not (n.startswith("__") and n.endswith("__"))})
        return {
            name: [self.named(name, getattr(facade, name)), [sub.__name__ for sub in submodules if hasattr(sub, name)]]
            for name in reachable
        }


def take_snapshot(
    root: Path,
    windows: Sequence[str],
    namespaces: Sequence[str],
    facades: Sequence[str] = (),
    project: tuple[str, ...] = PROJECT,
    test_files: Iterable[Path] = (),
) -> dict[str, Any]:
    """Imports what is named (the caller has put `root` on `sys.path`) and returns the snapshot, ready for `json.dumps`."""
    recorder = Recorder(root, project)
    recorded_windows = []
    for spec in windows:
        module_name, _, class_name = spec.partition(":")
        recorded_windows.append(recorder.klass(getattr(importlib.import_module(module_name), class_name)))
    modules = {name: recorder.module(importlib.import_module(name)) for name in namespaces}
    recorded_facades = {name: recorder.facade(importlib.import_module(name)) for name in facades}
    return {
        "meta": {"format": FORMAT, "python": platform.python_version()},
        "windows": recorded_windows,
        "classes": recorder.classes,
        "modules": modules,
        "facades": recorded_facades,
        "seams": seams_in(root, project, test_files),
        "functions": recorder.functions,
        "descriptors": recorder.descriptors,
    }


# =============================================================================
# Seams: what the tests replace, read in their source
# =============================================================================
def _raw_dotted(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _raw_dotted(expr.value)
        return None if base is None else f"{base}.{expr.attr}"
    return None


def _resolved(expr: ast.AST, aliases: dict[str, str]) -> str | None:
    """The dotted path `expr` stands for, when it starts at a name the file imported."""
    raw = _raw_dotted(expr)
    if raw is None:
        return None
    head, _, tail = raw.partition(".")
    if head not in aliases:
        return None
    return f"{aliases[head]}.{tail}" if tail else aliases[head]


def _string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Name -> dotted path, for every import of the file and every `x = importlib.import_module("a.b")`."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                first = alias.name.split(".")[0]
                aliases[alias.asname or first] = alias.name if alias.asname else first
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            aliases.update({alias.asname or alias.name: f"{node.module}.{alias.name}" for alias in node.names})
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            call = node.value
            if isinstance(call, ast.Call) and (_raw_dotted(call.func) or "").endswith("import_module") and call.args:
                imported = _string(call.args[0])
                if imported:
                    aliases[node.targets[0].id] = imported
    return aliases


def _object_and_name(args: list[ast.expr], aliases: dict[str, str]) -> str | None:
    if len(args) >= 2 and _string(args[1]):
        base = _resolved(args[0], aliases)
        return None if base is None else f"{base}.{_string(args[1])}"
    return None


def _patched_target(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """The dotted path a call replaces: `x.setattr("a.b.c", v)`, `x.setattr(module, "c", v)`, `patch("a.b.c")`, `patch.object(...)`."""
    raw = _raw_dotted(call.func) or ""
    if isinstance(call.func, ast.Attribute) and call.func.attr in ("setattr", "delattr"):
        if call.args and _string(call.args[0]):
            return _string(call.args[0])
        return _object_and_name(call.args, aliases)
    if raw == "patch" or raw.endswith(".patch"):
        return _string(call.args[0]) if call.args else None
    if raw.endswith("patch.object"):
        return _object_and_name(call.args, aliases)
    return None


def _split_module(dotted: str, root: Path) -> tuple[str, str] | None:
    """`a.b.c.name` -> (`a.b.c`, `name`), `a.b.c` being the longest prefix that is a module file under `root`."""
    parts = dotted.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        if root.joinpath(*parts[:cut]).with_suffix(".py").is_file():
            return ".".join(parts[:cut]), ".".join(parts[cut:])
    return None


def _parsed(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, ValueError):
        return None


def seams_in(root: Path, project: tuple[str, ...], test_files: Iterable[Path]) -> list[list[Any]]:
    """Every `[module, name, file, line]` where a test replaces the attribute `name` of the project module `module`."""
    found: list[list[Any]] = []
    for path in test_files:
        tree = _parsed(path)
        if tree is None:
            continue
        aliases = _aliases(tree)
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        for node in ast.walk(tree):
            target = _patched_target(node, aliases) if isinstance(node, ast.Call) else None
            split = _split_module(target, root) if target else None
            if split is not None and split[0].startswith(project):
                found.append([split[0], split[1], relative, node.lineno])
    return sorted(found)


# =============================================================================
# Comparison
# =============================================================================
class Allowance:
    """What the manifests allow to differ."""

    def __init__(self, manifests: Sequence[dict[str, Any]]) -> None:
        relocated: dict[str, str] = {}
        self.method_moves: set[tuple[str, str, str]] = set()
        for manifest in manifests:
            for move in manifest.get("moved_methods", ()):
                relocated[f"{move['from']}.{move['name']}"] = f"{move['to']}.{move['name']}"
                self.method_moves.add((move["name"], move["from"], move["to"]))
            relocated.update({move["from"]: move["to"] for move in manifest.get("moved_objects", ())})
        # A thing moved in one phase and again in a later one: the reference has to reach its last place.
        self.relocated = {old: self._last(relocated, new) for old, new in relocated.items()}
        self.changed_code = self._union(manifests, "changed_code")
        self.rebound = self._union(manifests, "rebound")
        self.new_classes = self._union(manifests, "new_classes")
        self.removed_from_mro = self._union(manifests, "removed_from_mro")
        self.added_attributes = self._union(manifests, "added_attributes")
        self.acknowledged_seams = {key for manifest in manifests for key in manifest.get("acknowledged_seams", {})}

    @staticmethod
    def _last(relocated: dict[str, str], identity: str) -> str:
        for _ in range(len(relocated)):
            if identity not in relocated:
                break
            identity = relocated[identity]
        return identity

    @staticmethod
    def _union(manifests: Sequence[dict[str, Any]], key: str) -> set[str]:
        return {item for manifest in manifests for item in manifest.get(key, ())}

    def translate(self, identity: str) -> str:
        """Where `module:qualname` is after the moves; what a moved function nests moves with it."""
        for old, new in self.relocated.items():
            if identity == old:
                return new
            if identity.startswith(f"{old}."):
                return new + identity[len(old):]
        return identity

    def translate_descriptor(self, text: str) -> str:
        kind, _, rest = text.partition(":")
        return f"{kind}:{self.translate(rest)}" if kind in ("func", "class") else text


def _function_id(record: dict[str, Any]) -> str:
    return f"{record['module']}:{record['qualname']}"


class _Comparison:
    def __init__(self, old: dict[str, Any], new: dict[str, Any], allow: Allowance) -> None:
        self.old, self.new, self.allow = old, new, allow
        self.problems: list[str] = []
        self.notes: list[str] = []
        self._seen: set[tuple[int, int]] = set()
        self._new_by_id: dict[str, int] = {}
        for index, record in enumerate(new["functions"]):
            self._new_by_id.setdefault(_function_id(record), index)

    def _same(self, old_index: int, new_index: int, binding: str | None = None) -> bool:
        if self.allow.translate_descriptor(self.old["descriptors"][old_index]) == self.new["descriptors"][new_index]:
            return True
        return binding is not None and binding in self.allow.rebound

    def _was_and_is(self, old_index: int, new_index: int) -> str:
        return f"is {self.new['descriptors'][new_index]}, was {self.old['descriptors'][old_index]}"

    def function(self, old_index: int, new_index: int, where: str) -> None:
        if (old_index, new_index) in self._seen:
            return
        self._seen.add((old_index, new_index))
        a, b = self.old["functions"][old_index], self.new["functions"][new_index]
        old_id, new_id = _function_id(a), _function_id(b)
        if self.allow.translate(old_id) != new_id:
            self.problems.append(f"MOVED     | {where} | {old_id} is now {new_id}, and no manifest says so")
        if "code" not in a or "code" not in b:
            if "code" in a or "code" in b or not self._same(a["value"], b["value"]):
                self.problems.append(f"KIND      | {where} | {new_id} is no longer the same kind of callable")
            return
        if new_id not in self.allow.changed_code and old_id not in self.allow.changed_code:
            if a["code"] != b["code"]:
                self.problems.append(f"BYTECODE  | {where} | {new_id} does not have the bytecode of {old_id}")
            if a["signature"] != b["signature"]:
                self.problems.append(f"SIGNATURE | {where} | {new_id}{b['signature']}, was {a['signature']}")
            self._globals(a, b, where)
            closure_a, closure_b = a.get("closure", []), b.get("closure", [])
            if len(closure_a) != len(closure_b) or not all(
                self._same(x, y) for x, y in zip(closure_a, closure_b, strict=False)
            ):
                self.problems.append(f"CLOSURE   | {where} | {new_id} does not close over what {old_id} did")
        if ("wrapped" in a) != ("wrapped" in b):
            self.problems.append(f"WRAPPER   | {where} | {new_id} is decorated differently from {old_id}")
        elif "wrapped" in a:
            self.function(a["wrapped"], b["wrapped"], where)

    def _globals(self, a: dict[str, Any], b: dict[str, Any], where: str) -> None:
        for name, old_index in a["globals"].items():
            if name in DRIFTING_GLOBALS:
                continue
            new_index = b["globals"].get(name)
            if new_index is None:
                self.problems.append(f"GLOBAL    | {where} | `{name}` is no longer loaded")
            elif not self._same(old_index, new_index, f"{b['module']}:{name}") and (
                f"{a['module']}:{name}" not in self.allow.rebound
            ):
                detail = self._was_and_is(old_index, new_index)
                self.problems.append(f"GLOBAL    | {where} | `{name}` in {b['module']} {detail}")

    def mro(self, identity: str, old_mro: list[str], new_mro: list[str]) -> None:
        expected = [self.allow.translate(c) for c in old_mro if c not in self.allow.removed_from_mro]
        actual = [c for c in new_mro if c not in self.allow.new_classes]
        if expected != actual:
            at = next((i for i, (x, y) in enumerate(zip(expected, actual, strict=False)) if x != y), min(len(expected), len(actual)))
            was = expected[at] if at < len(expected) else "<end>"
            now = actual[at] if at < len(actual) else "<end>"
            self.problems.append(f"MRO       | {identity} | position {at}: {now}, was {was}")
        before, after = [c.rpartition(":")[2] for c in old_mro], [c.rpartition(":")[2] for c in new_mro]
        for left, right in MUST_STAY_ADJACENT:
            if left in before and right in before and before.index(right) == before.index(left) + 1:
                if left not in after or right not in after or after.index(right) != after.index(left) + 1:
                    self.problems.append(f"MRO       | {identity} | {right} no longer follows {left} immediately")

    def classes(self) -> None:
        expected: set[str] = set()
        for identity, a in self.old["classes"].items():
            target = self.allow.translate(identity)
            expected.add(target)
            b = self.new["classes"].get(target)
            if b is None:
                self.problems.append(f"CLASS     | {identity} | gone")
                continue
            self.mro(identity, a["mro"], b["mro"])
            for name, x in a["attrs"].items():
                self._attribute(f"{identity}.{name}", name, x, b["attrs"].get(name))
            for name in sorted(b["attrs"].keys() - a["attrs"].keys()):
                if f"{target}.{name}" not in self.allow.added_attributes:
                    self.problems.append(f"ATTRIBUTE | {target}.{name} | new, and no manifest names it")
        for identity in sorted(self.new["classes"].keys() - expected - self.allow.new_classes):
            self.problems.append(f"CLASS     | {identity} | new, and no manifest names it")

    def _attribute(self, where: str, name: str, x: dict[str, Any], y: dict[str, Any] | None) -> None:
        if y is None:
            self._gone(where, name, x)
            return
        if x["kind"] != y["kind"]:
            self.problems.append(f"KIND      | {where} | {y['kind']}, was {x['kind']}")
            return
        moved = (name, x["owner"], y["owner"]) in self.allow.method_moves
        if y["owner"] != self.allow.translate(x["owner"]) and not moved:
            self.problems.append(f"OWNER     | {where} | resolved in {y['owner']}, was in {x['owner']}")
        if "impl" in x:
            for i, j in zip(x["impl"], y["impl"], strict=True):
                if i is None or j is None:
                    if i != j:
                        self.problems.append(f"KIND      | {where} | a property accessor appeared or went")
                else:
                    self.function(i, j, where)
        elif not self._same(x["value"], y["value"], where):
            self.problems.append(f"VALUE     | {where} | {self._was_and_is(x['value'], y['value'])}")

    def _gone(self, where: str, name: str, x: dict[str, Any]) -> None:
        """A class no longer has the attribute: a move, if a manifest sends it to a class that defines it, unchanged."""
        for moved, origin, target in sorted(self.allow.method_moves):
            if moved != name or origin != x["owner"]:
                continue
            landed = self.new["classes"].get(target, {}).get("attrs", {}).get(name)
            if landed is None or landed["owner"] != target:
                self.problems.append(f"ATTRIBUTE | {where} | gone, and {target}, where a manifest sends it, does not define it")
            elif landed["kind"] != x["kind"]:
                self.problems.append(f"KIND      | {where} | {landed['kind']} in {target}, was {x['kind']}")
            elif "impl" in x:
                for i, j in zip(x["impl"], landed["impl"], strict=True):
                    if i is None or j is None:
                        if i != j:
                            self.problems.append(f"KIND      | {where} | a property accessor appeared or went")
                    else:
                        self.function(i, j, where)
            return
        self.problems.append(f"ATTRIBUTE | {where} | gone")

    def modules(self) -> None:
        for module, a in self.old["modules"].items():
            b = self.new["modules"].get(module)
            if b is None:
                self.problems.append(f"MODULE    | {module} | gone")
                continue
            for name, entry in a.items():
                where = f"{module}:{name}"
                other = b.get(name)
                if other is None:
                    self.problems.append(f"NAME      | {where} | gone from the module (an import or a test may read it there)")
                    continue
                if not self._same(entry[0], other[0], where):
                    self.problems.append(f"NAME      | {where} | {self._was_and_is(entry[0], other[0])}")
                if len(entry) > 1:  # a function this module defined: wherever it lives now, it is the same function
                    target = self._new_by_id.get(self.allow.translate(_function_id(self.old["functions"][entry[1]])))
                    if target is None:
                        self.problems.append(f"FUNCTION  | {where} | no longer defined anywhere the snapshot looks")
                    else:
                        self.function(entry[1], target, where)
            added = len(b.keys() - a.keys())
            if added:
                self.notes.append(f"NAMES     | {module} | {added} new name(s)")
        for module in sorted(self.new["modules"].keys() - self.old["modules"].keys()):
            self.notes.append(f"MODULE    | {module} | new")

    def facades(self) -> None:
        for facade, a in self.old["facades"].items():
            b = self.new["facades"].get(facade, {})
            for name, (descriptor, holders) in a.items():
                other = b.get(name)
                where = f"{facade}:{name}"
                if other is None:
                    self.problems.append(f"FACADE    | {where} | no longer reachable")
                elif not self._same(descriptor, other[0], where):
                    self.problems.append(f"FACADE    | {where} | {self._was_and_is(descriptor, other[0])}")
                elif holders != other[1]:
                    self.notes.append(f"FACADE    | {where} | held by {other[1]}, was {holders}")

    def seams(self) -> None:
        """A moved function reads its globals in the module it moved to: a test that replaces one in the module it left misses it."""
        replaced: dict[tuple[str, str], str] = {}
        for module, name, file, line in self.new["seams"]:
            holders = self.old["facades"].get(module, {}).get(name, [None, [module]])[1]
            for holder in holders:
                replaced.setdefault((holder, name), f"{file}:{line}")
        for record in self.old["functions"]:
            old_id = _function_id(record)
            new_id = self.allow.translate(old_id)
            old_module, new_module = old_id.partition(":")[0], new_id.partition(":")[0]
            if old_module == new_module or "globals" not in record:
                continue
            for name in record["globals"]:
                at = replaced.get((old_module, name))
                if at is not None and f"{old_module}:{name}" not in self.allow.acknowledged_seams:
                    self.problems.append(
                        f"SEAM      | {new_id} | loads `{name}`, which {at} replaces in {old_module}: "
                        "the moved code no longer reads it there"
                    )


def compare(old: dict[str, Any], new: dict[str, Any], manifests: Sequence[dict[str, Any]] = ()) -> tuple[list[str], list[str]]:
    """The differences no manifest allows, and the ones worth a look that are allowed (new names, a facade holder)."""
    for snapshot in (old, new):
        if snapshot.get("meta", {}).get("format") != FORMAT:
            raise GuardError(f"snapshot format {snapshot.get('meta', {}).get('format')!r}, this guard reads {FORMAT}")
    if old["meta"]["python"] != new["meta"]["python"]:
        raise GuardError(f"snapshots of two Python versions: {old['meta']['python']} and {new['meta']['python']}")
    comparison = _Comparison(old, new, Allowance(manifests))
    comparison.classes()
    comparison.modules()
    comparison.facades()
    comparison.seams()
    return sorted(set(comparison.problems)), sorted(set(comparison.notes))


# =============================================================================
# Command line
# =============================================================================
def _tracked_tests(root: Path) -> list[Path]:
    """The test sources git tracks (the tree holds copies of itself under .claude/worktrees: never walk it)."""
    done = subprocess.run(["git", "ls-files", "--", "tests"], cwd=root, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise GuardError(f"git ls-files failed in {root}: {done.stderr.strip()}")
    return [root / line for line in done.stdout.splitlines() if line.endswith(".py")]


def _snapshot_this_tree() -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    certus = importlib.import_module("certus")
    resolved = [Path(p).resolve() for p in certus.__path__]
    if not resolved or resolved[0] != ROOT / "certus":
        raise GuardError(f"`import certus` resolves to {resolved}, not to this tree ({ROOT / 'certus'})")
    namespaces = sorted(
        {path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".") for pattern in NAMESPACES for path in ROOT.glob(pattern)}
    )
    return take_snapshot(ROOT, WINDOWS, namespaces, FACADES, PROJECT, _tracked_tests(ROOT))


def _read(path: str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuardError(f"cannot read {path}: {exc}") from exc


def _print_lines(lines: list[str], full: bool) -> None:
    for line in lines if full else lines[:SHOWN]:
        print(line)
    if not full and len(lines) > SHOWN:
        print(f"... {len(lines) - SHOWN} more (--full prints them all)")


def _cmd_snapshot(args: argparse.Namespace) -> int:
    snapshot = _snapshot_this_tree()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(
        f"windows={len(snapshot['windows'])} classes={len(snapshot['classes'])} modules={len(snapshot['modules'])} "
        f"functions={len(snapshot['functions'])} seams={len(snapshot['seams'])} python={snapshot['meta']['python']}"
    )
    print(f"SNAPSHOT={out.as_posix()}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    problems, notes = compare(_read(args.reference), _read(args.new), [_read(m) for m in args.manifest])
    _print_lines(problems, args.full)
    if args.full:
        _print_lines(notes, True)
    print(f"problems={len(problems)} notes={len(notes)}")
    print("GUARD=OK" if not problems else "GUARD=DIFF")
    return 0 if not problems else 1


def _cmd_report(args: argparse.Namespace) -> int:
    snapshot = _read(args.file)
    lines: list[str] = []
    for window in snapshot["windows"]:
        if args.window and args.window not in window:
            continue
        shared = {n: a["defined_by"] for n, a in snapshot["classes"][window]["attrs"].items() if "defined_by" in a}
        lines.append(f"WINDOW    | {window} | mro={len(snapshot['classes'][window]['mro'])} defined_twice={len(shared)}")
        lines += [f"TWICE     | {window}.{name} | {' > '.join(owners)}" for name, owners in sorted(shared.items())]
    counted: dict[tuple[str, str], list[str]] = {}
    for module, name, file, line in snapshot["seams"]:
        if module in snapshot["modules"] or module in snapshot["facades"]:
            counted.setdefault((module, name), []).append(f"{file}:{line}")
    lines += [f"SEAM      | {module}:{name} | {len(at)} site(s), first {at[0]}" for (module, name), at in sorted(counted.items())]
    _print_lines(lines, args.full)
    print(f"lines={len(lines)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Proves that a move of code changed nothing but the place.")
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot", help="write the snapshot of this tree")
    snapshot.add_argument("--out", required=True)
    snapshot.set_defaults(run=_cmd_snapshot)
    comparing = commands.add_parser("compare", help="hold a snapshot against a reference")
    comparing.add_argument("reference")
    comparing.add_argument("new")
    comparing.add_argument("--manifest", action="append", default=[])
    comparing.add_argument("--full", action="store_true")
    comparing.set_defaults(run=_cmd_compare)
    report = commands.add_parser("report", help="print what several classes define and the seams of the group")
    report.add_argument("file")
    report.add_argument("--window", default="")
    report.add_argument("--full", action="store_true")
    report.set_defaults(run=_cmd_report)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except GuardError as exc:
        print(f"GUARD=ERROR {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
