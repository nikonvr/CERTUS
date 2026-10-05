"""Dead-symbol audit with Qt-aware heuristics.

Scans Python modules for top-level functions and class methods that appear
unused, with a conservative whitelist model for CI enforcement.

THE TWO PERIMETERS ARE NOT THE SAME, and conflating them was a defect.
Candidates are looked for in reviewed modules -- the root entry points,
certus_physics, certus/metal, certus/spline, certus/core, certus/domain and
certus/physics -- so each package's candidates
can be examined before the CI gate expands. References are looked for across the entire
runtime tree instead: a call counts wherever it lives.

Measured on 2026-09-08: collecting references in the narrow perimeter reported
32 unresolved candidates, 27 of which are called from the application package
the tool never opened. A permanently red gate teaches everyone to ignore red.

Tests stay OUT of the reference perimeter on purpose: a symbol only a test
calls is dead in production, and counting the test would hide it.

Known limitation, stated so nobody credits the tool with more than it does:
matching is by bare name, not by qualified symbol. A method is considered
alive when any other class calls something of the same name. The tool
therefore under-reports, which is the safe direction for a gate -- but green
does not prove the absence of dead code.
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
    """Scan reviewed runtime modules: root *.py, certus_physics and reviewed certus packages.

    certus/metal holds the METAL applications that lived at the root until 2026-09-28:
    moving them must not take them out of the audit. certus/spline was measured
    and added in D24, followed by spline, core, domain and physics. Tests and
    tooling scripts are excluded.
    """
    files: list[Path] = list(root.glob("*.py"))

    for package in (
        root / "certus_physics",
        root / "certus" / "metal",
        root / "certus" / "spline",
        root / "certus" / "core",
        root / "certus" / "domain",
        root / "certus" / "physics",
    ):
        if not package.exists():
            continue
        for path in package.rglob("*.py"):
            rel_parts = set(path.relative_to(root).parts)
            if rel_parts & EXCLUDED_DIR_NAMES:
                continue
            files.append(path)

    return sorted(set(files))


def _iter_reference_files(root: Path) -> list[Path]:
    """Every runtime module a call could live in.

    Wider than the candidate perimeter on purpose: a reference counts wherever
    it is written. `scripts/` is included because the project runs those
    constantly -- a symbol used only there is used.

    `tests/` and `tools/` are excluded. A test-only symbol is dead in
    production, and the audits under `tools/` name symbols as data rather than
    calling them.
    """
    files: list[Path] = list(root.glob("*.py"))

    for package in ("certus", "certus_physics", "scripts"):
        directory = root / package
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if set(path.relative_to(root).parts) & EXCLUDED_DIR_NAMES:
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


def _is_framework_decorated(decorators: tuple[str, ...]) -> bool:
    auto_invoked = {"pyqtSlot", "pyqtProperty", "Slot", "Property", "field_validator", "model_validator"}
    return any(name in auto_invoked for name in decorators)


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

        local_name_uses: dict[str, list[int]] = defaultdict(list)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                refs[node.id].append((path, node.lineno))
                local_name_uses[node.id].append(node.lineno)
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

        # `from module import original as local` is a production reference to
        # `original` only when the local spelling is actually used in this file.
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for imported in node.names:
                    if imported.asname:
                        refs[imported.name].extend(
                            (path, line) for line in local_name_uses.get(imported.asname, [])
                        )

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
    if defn.is_method and _is_framework_decorated(defn.decorators):
        return True
    if defn.is_method and EVENT_HANDLER_RE.match(defn.name):
        return True
    return False


def run_audit(whitelist_path: Path) -> tuple[list[Definition], list[Definition], list[Definition]]:
    defs = _collect_definitions(_iter_python_files(ROOT))
    refs = _collect_references(_iter_reference_files(ROOT))

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
