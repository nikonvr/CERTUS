"""Dead-symbol audit with Qt-aware heuristics.

Scans Python modules for top-level functions and class methods that appear
unused, with a conservative whitelist model for CI enforcement.
"""

from __future__ import annotations

import argparse
import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WHITELIST = ROOT / "tools" / "dead_symbol_whitelist.txt"

EXCLUDED_DIR_NAMES = {
    ".venv",
    ".git",
    "__pycache__",
    "build",
    "dist",
    "artifacts",
    "certus_optical_suite.egg-info",
}

EVENT_HANDLER_RE = re.compile(r"^_on_[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class Definition:
    symbol_id: str
    name: str
    file_path: Path
    start_line: int
    end_line: int
    is_method: bool
    decorators: tuple[str, ...]


def _iter_python_files(root: Path) -> list[Path]:
    """Scan runtime modules only: root *.py + certus_physics package.

    Tests and tooling scripts are intentionally excluded from candidates.
    """
    files: list[Path] = list(root.glob("*.py"))

    physics_dir = root / "certus_physics"
    if physics_dir.exists():
        for path in physics_dir.rglob("*.py"):
            rel_parts = set(path.relative_to(root).parts)
            if rel_parts & EXCLUDED_DIR_NAMES:
                continue
            files.append(path)

    return sorted(set(files))


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    names: list[str] = []
    for deco in node.decorator_list:
        if isinstance(deco, ast.Name):
            names.append(deco.id)
        elif isinstance(deco, ast.Attribute):
            names.append(deco.attr)
        elif isinstance(deco, ast.Call):
            fn = deco.func
            if isinstance(fn, ast.Name):
                names.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.append(fn.attr)
    return tuple(names)


def _is_qt_decorated(decorators: tuple[str, ...]) -> bool:
    qt_decorators = {"pyqtSlot", "pyqtProperty", "Slot", "Property"}
    return any(name in qt_decorators for name in decorators)


def _collect_definitions(py_files: list[Path]) -> list[Definition]:
    defs: list[Definition] = []

    for path in py_files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            continue

        module_name = path.relative_to(ROOT).as_posix().removesuffix(".py").replace("/", ".")

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.append(
                    Definition(
                        symbol_id=f"{module_name}:{node.name}",
                        name=node.name,
                        file_path=path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        is_method=False,
                        decorators=_decorator_names(node),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        defs.append(
                            Definition(
                                symbol_id=f"{module_name}:{node.name}.{sub.name}",
                                name=sub.name,
                                file_path=path,
                                start_line=sub.lineno,
                                end_line=sub.end_lineno or sub.lineno,
                                is_method=True,
                                decorators=_decorator_names(sub),
                            )
                        )

    return defs


def _collect_references(py_files: list[Path]) -> dict[str, list[tuple[Path, int]]]:
    refs: dict[str, list[tuple[Path, int]]] = defaultdict(list)

    for path in py_files:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                refs[node.id].append((path, node.lineno))
            elif isinstance(node, ast.Attribute):
                refs[node.attr].append((path, node.lineno))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.isidentifier():
                    refs[node.value].append((path, node.lineno))
            elif isinstance(node, ast.Call):
                # QMetaObject.invokeMethod(obj, "slot_name", ...)
                if isinstance(node.func, ast.Attribute) and node.func.attr == "invokeMethod":
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        slot_name = node.args[1].value
                        if slot_name.isidentifier():
                            refs[slot_name].append((path, node.lineno))

    return refs


def _is_self_reference(defn: Definition, ref: tuple[Path, int]) -> bool:
    path, line = ref
    return path == defn.file_path and defn.start_line <= line <= defn.end_line


def _load_whitelist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def _write_whitelist(path: Path, symbol_ids: list[str]) -> None:
    header = [
        "# Dead-symbol whitelist",
        "# One symbol id per line: module_path:Function or module_path:Class.method",
        "# Generated from current baseline with tools/dead_symbol_audit.py --write-whitelist",
        "",
    ]
    body = sorted(set(symbol_ids))
    path.write_text("\n".join(header + body) + "\n", encoding="utf-8")


def _is_excluded_by_heuristic(defn: Definition) -> bool:
    if defn.name.startswith("__") and defn.name.endswith("__"):
        return True
    if _is_qt_decorated(defn.decorators):
        return True
    if defn.is_method and EVENT_HANDLER_RE.match(defn.name):
        return True
    return False


def run_audit(whitelist_path: Path) -> tuple[list[Definition], list[Definition], list[Definition]]:
    py_files = _iter_python_files(ROOT)
    defs = _collect_definitions(py_files)
    refs = _collect_references(py_files)

    candidates: list[Definition] = []
    for defn in defs:
        if _is_excluded_by_heuristic(defn):
            continue
        hits = refs.get(defn.name, [])
        external_hits = [hit for hit in hits if not _is_self_reference(defn, hit)]
        if not external_hits:
            candidates.append(defn)

    whitelist = _load_whitelist(whitelist_path)
    unresolved = [defn for defn in candidates if defn.symbol_id not in whitelist]
    return candidates, unresolved, defs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit dead symbols with CI gating.")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero when unresolved candidates exist.")
    parser.add_argument(
        "--whitelist",
        type=Path,
        default=DEFAULT_WHITELIST,
        help="Whitelist file path.",
    )
    parser.add_argument(
        "--write-whitelist",
        action="store_true",
        help="Overwrite whitelist with current candidate baseline and exit 0.",
    )
    args = parser.parse_args(argv)

    candidates, unresolved, defs = run_audit(args.whitelist)

    if args.write_whitelist:
        _write_whitelist(args.whitelist, [d.symbol_id for d in candidates])
        print(f"Wrote whitelist baseline: {args.whitelist} ({len(candidates)} entries)")
        return 0

    print(f"Scanned definitions: {len(defs)}")
    print(f"Dead-symbol candidates (pre-whitelist): {len(candidates)}")
    print(f"Unresolved candidates: {len(unresolved)}")

    for defn in unresolved[:200]:
        rel = defn.file_path.relative_to(ROOT).as_posix()
        print(f" - {defn.symbol_id} ({rel}:{defn.start_line})")

    if args.ci and unresolved:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
