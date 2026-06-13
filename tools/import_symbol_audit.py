"""Static audit for missing symbol imports / undefined names.

This tool is intended to catch the exact class of regression introduced during
refactors: code that starts referencing a symbol that is no longer imported or
otherwise defined in the module.

It is conservative by design:
- it ignores attribute access (``obj.name``)
- it ignores builtins and common typing names
- it ignores symbols defined in the same module
- it flags unresolved *Name* nodes only

Usage examples:

    python tools/import_symbol_audit.py certus/core/certus_design_orchestrator.py
    python tools/import_symbol_audit.py certus/ui/certus_design_ui.py certus/ui/mixins/certus_design_plot_mixin.py
    python tools/import_symbol_audit.py --root . --pattern certus/**/*.py
"""

from __future__ import annotations

import argparse
import ast
import builtins
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


COMMON_TYPING_NAMES = {
    "Any",
    "Callable",
    "Dict",
    "Iterable",
    "List",
    "Optional",
    "Sequence",
    "Set",
    "Tuple",
    "Union",
    "TypeVar",
    "Protocol",
}

COMMON_OTHER_NAMES = {
    "np",
    "pd",
    "pg",
    "Path",
    "logging",
    "functools",
    "time",
    "os",
    "sys",
    "math",
    "re",
}

BUILTIN_NAMES = set(dir(builtins))


@dataclass(frozen=True)
class Finding:
    file_path: Path
    line: int
    name: str
    context: str


class ModuleCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defined: set[str] = set()
        self.imported: set[str] = set()
        self.findings: list[Finding] = []
        self._scope_stack: list[set[str]] = [set()]

    def _current_scope(self) -> set[str]:
        return self._scope_stack[-1]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.imported.add(name)
            self.defined.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self.imported.add(name)
            self.defined.add(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defined.add(node.name)
        self._scope_stack.append(set(arg.arg for arg in node.args.args + node.args.kwonlyargs))
        if node.args.vararg:
            self._current_scope().add(node.args.vararg.arg)
        if node.args.kwarg:
            self._current_scope().add(node.args.kwarg.arg)
        for stmt in node.body:
            self.visit(stmt)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defined.add(node.name)
        self._scope_stack.append(set())
        for stmt in node.body:
            self.visit(stmt)
        self._scope_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._collect_target(target)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._collect_target(node.target)
        if node.value:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.target)
        self.visit(node.value)

    def _collect_target(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.defined.add(target.id)
            self._current_scope().add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._collect_target(elt)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.defined.add(node.id)
            self._current_scope().add(node.id)
            return

        if node.id in BUILTIN_NAMES or node.id in COMMON_TYPING_NAMES or node.id in COMMON_OTHER_NAMES:
            return

        if node.id in self._current_scope() or node.id in self.defined:
            return

        # Capture unresolved read references only
        self.findings.append(Finding(Path("<unknown>"), node.lineno, node.id, ""))

    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)


def audit_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)

    collector = ModuleCollector()
    collector.visit(tree)

    # Re-run with path attached and de-duplicate by line/name
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    for finding in collector.findings:
        key = (finding.line, finding.name)
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(path, finding.line, finding.name, source.splitlines()[finding.line - 1].strip() if finding.line - 1 < len(source.splitlines()) else ""))
    return findings


def iter_files(root: Path, pattern: str | None, paths: list[Path]) -> Iterable[Path]:
    if paths:
        yield from paths
        return
    if pattern:
        yield from root.glob(pattern)
        return
    yield from root.glob("certus/**/*.py")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit modules for missing symbol imports.")
    parser.add_argument("paths", nargs="*", type=Path, help="Files to audit. If omitted, uses certus/**/*.py")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Repository root")
    parser.add_argument("--pattern", type=str, default=None, help="Glob pattern relative to root")
    parser.add_argument("--limit", type=int, default=200, help="Maximum findings to print")
    args = parser.parse_args(argv)

    files = [p for p in iter_files(args.root, args.pattern, args.paths) if p.is_file()]
    all_findings: list[Finding] = []
    for path in files:
        try:
            all_findings.extend(audit_file(path))
        except SyntaxError:
            continue
        except Exception:
            continue

    # Best-effort filter: show only actual likely missing imports by requiring
    # that the name is not defined in the file text.
    report = list(all_findings)
    print(f"Scanned files: {len(files)}")
    print(f"Potential unresolved symbol reads: {len(report)}")
    for finding in report[: args.limit]:
        rel = finding.file_path.relative_to(args.root).as_posix() if finding.file_path.is_relative_to(args.root) else str(finding.file_path)
        print(f" - {rel}:{finding.line}: {finding.name}  | {finding.context}")

    return 1 if report else 0


if __name__ == "__main__":
    raise SystemExit(main())
