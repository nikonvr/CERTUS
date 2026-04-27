"""Aggressive dead-code / orphan / duplicate audit for the Certus codebase.

Strategy
--------
1. Collect every top-level def / class / method via AST across root + tools.
2. Collect every reference (Name.id, Attribute.attr, Constant str).
3. Cross-reference. A symbol is *orphan* if its name is referenced **only**
   at its own definition site or inside its own body.
4. Aggressive mode: do not whitelist Qt slot strings unless the call site
   matches `connect(...)`, `invokeMethod(...)`, or decorator `@pyqtSlot`.
5. Duplicate detection: SHA-256 of the AST-unparsed function body
   (docstring stripped) for every function with body LOC >= 8.
6. Unused imports: per file, names imported and never referenced in the AST.

Output: Markdown to stdout. Pipe to a file in reports/ for archival.

Usage
-----
    python tools/dead_code_audit.py --output reports/CERTUS_DEAD_CODE_AUDIT_<date>.md
    python tools/dead_code_audit.py        # stdout (UTF-8 forced)

Notes
-----
* Test files are scanned for *references* (so a test-only symbol is NOT
  flagged orphan), but their own defs are excluded from the orphan output.
* `__main__` blocks and dunder methods are excluded.
* The `_<name>` prefix is **not** an exclusion — private helpers can be
  orphans too, that is precisely what we hunt.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows so the markdown report renders correctly
# (the report contains -, --, and other non-cp1252 glyphs).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(".")
TESTS_DIR = ROOT / "tests"
TOOLS_DIR = ROOT / "tools"
SCRIPTS_DIR = ROOT / "scripts"

# Excluded from orphan candidates (entry points, magic methods, fixtures, etc.)
PROTECTED_EXACT = {
    "main",
    "__main__",
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    "setUpModule",
    "tearDownModule",
    "pytest_configure",
    "pytest_collection_modifyitems",
    "conftest",
}
PROTECTED_PREFIXES = ("test_",)
DUNDER_RE = re.compile(r"^__[a-z_]+__$")

# Qt-aware reference patterns (regex search across strings to assess slot usage).
QT_CONNECT_RE = re.compile(r"\.connect\s*\(\s*(?:self\.)?([A-Za-z_][A-Za-z0-9_]*)")
QT_INVOKE_RE = re.compile(r"invokeMethod\s*\(\s*[^,]+,\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']")
QT_PROPERTY_RE = re.compile(r"pyqtProperty\s*\([^)]*?(?:fget|fset|fdel)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")

# Duplicate detection threshold (body LOC).
DUP_MIN_LOC = 8


@dataclass
class Definition:
    name: str
    qualname: str
    file: Path
    line: int
    end_line: int
    body_loc: int
    body_hash: str
    is_method: bool = False
    is_class: bool = False
    decorators: list[str] = field(default_factory=list)


@dataclass
class FileScan:
    path: Path
    src: str
    tree: ast.AST
    is_test: bool


def _is_protected(name: str) -> bool:
    if name in PROTECTED_EXACT:
        return True
    if DUNDER_RE.match(name):
        return True
    for prefix in PROTECTED_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


def _collect_files() -> list[FileScan]:
    files: list[FileScan] = []
    for p in sorted(ROOT.glob("*.py")):
        files.append(_load(p, is_test=False))
    if TOOLS_DIR.exists():
        for p in sorted(TOOLS_DIR.glob("*.py")):
            if p.name.startswith("_") or p.name == "dead_code_audit.py":
                continue
            files.append(_load(p, is_test=False))
    # `scripts/` contains operator entry points that consume the public API
    # of root modules. Treated as reference-only sources (their own defs are
    # not flagged as orphans by `_collect_defs`, which skips non-root files).
    if SCRIPTS_DIR.exists():
        for p in sorted(SCRIPTS_DIR.rglob("*.py")):
            files.append(_load(p, is_test=True))  # is_test=True == "reference-only"
    if TESTS_DIR.exists():
        for p in sorted(TESTS_DIR.rglob("*.py")):
            files.append(_load(p, is_test=True))
    return [f for f in files if f is not None]


def _load(path: Path, *, is_test: bool) -> FileScan | None:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return None
    return FileScan(path=path, src=src, tree=tree, is_test=is_test)


def _hash_body(node: ast.AST) -> tuple[str, int]:
    """Return (sha256, body LOC) of the function body, docstring stripped."""
    body = list(getattr(node, "body", []))
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body:
        return ("", 0)
    try:
        dump = "\n".join(ast.unparse(b) for b in body)
    except Exception:
        return ("", 0)
    loc = dump.count("\n") + 1
    h = hashlib.sha256(dump.encode("utf-8")).hexdigest()[:16]
    return (h, loc)


def _decorator_names(node: ast.AST) -> list[str]:
    out: list[str] = []
    for d in getattr(node, "decorator_list", []) or []:
        if isinstance(d, ast.Name):
            out.append(d.id)
        elif isinstance(d, ast.Attribute):
            out.append(d.attr)
        elif isinstance(d, ast.Call):
            f = d.func
            if isinstance(f, ast.Name):
                out.append(f.id)
            elif isinstance(f, ast.Attribute):
                out.append(f.attr)
    return out


def _collect_defs(scans: list[FileScan]) -> list[Definition]:
    defs: list[Definition] = []
    for s in scans:
        if s.is_test:
            continue
        # top-level fns + classes
        for node in ast.iter_child_nodes(s.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                h, loc = _hash_body(node)
                defs.append(
                    Definition(
                        name=node.name,
                        qualname=node.name,
                        file=s.path,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        body_loc=loc,
                        body_hash=h,
                        is_method=False,
                        is_class=False,
                        decorators=_decorator_names(node),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                h, loc = _hash_body(node)
                defs.append(
                    Definition(
                        name=node.name,
                        qualname=node.name,
                        file=s.path,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        body_loc=loc,
                        body_hash=h,
                        is_method=False,
                        is_class=True,
                        decorators=_decorator_names(node),
                    )
                )
                for sub in ast.iter_child_nodes(node):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        sh, sloc = _hash_body(sub)
                        defs.append(
                            Definition(
                                name=sub.name,
                                qualname=f"{node.name}.{sub.name}",
                                file=s.path,
                                line=sub.lineno,
                                end_line=sub.end_lineno or sub.lineno,
                                body_loc=sloc,
                                body_hash=sh,
                                is_method=True,
                                is_class=False,
                                decorators=_decorator_names(sub),
                            )
                        )
    return defs


def _collect_references(scans: list[FileScan]) -> dict[str, list[tuple[Path, int]]]:
    refs: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for s in scans:
        for node in ast.walk(s.tree):
            if isinstance(node, ast.Name):
                refs[node.id].append((s.path, node.lineno))
            elif isinstance(node, ast.Attribute):
                refs[node.attr].append((s.path, node.lineno))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v.isidentifier():
                    refs[v].append((s.path, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                # `from mod import foo as bar` references `foo` even if locally bound to `bar`.
                for alias in node.names:
                    if alias.name and alias.name != "*":
                        refs[alias.name].append((s.path, node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    head = alias.name.split(".", 1)[0] if alias.name else ""
                    if head:
                        refs[head].append((s.path, node.lineno))
        # additional Qt regex sweep on raw src (catches `connect(self.X)` etc.)
        for m in QT_CONNECT_RE.finditer(s.src):
            refs[m.group(1)].append((s.path, 0))
        for m in QT_INVOKE_RE.finditer(s.src):
            refs[m.group(1)].append((s.path, 0))
        for m in QT_PROPERTY_RE.finditer(s.src):
            refs[m.group(1)].append((s.path, 0))
    return refs


def _is_self_ref(d: Definition, ref: tuple[Path, int]) -> bool:
    return ref[0] == d.file and d.line <= ref[1] <= d.end_line


def _collect_imports(scans: list[FileScan]) -> dict[Path, list[tuple[int, str, str]]]:
    """Return, per file: list of (line, alias, module) for each import that has zero
    AST reference inside the same file."""
    out: dict[Path, list[tuple[int, str, str]]] = {}
    for s in scans:
        if s.is_test:
            continue
        used = set()
        for node in ast.walk(s.tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                base = node
                while isinstance(base, ast.Attribute):
                    base = base.value
                if isinstance(base, ast.Name):
                    used.add(base.id)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.isidentifier():
                    used.add(node.value)
        unused: list[tuple[int, str, str]] = []
        for node in ast.walk(s.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    if bound not in used:
                        unused.append((node.lineno, bound, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or "."
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname or alias.name
                    if bound not in used:
                        unused.append((node.lineno, bound, mod))
        if unused:
            out[s.path] = unused
    return out


def main(argv: list[str] | None = None) -> None:  # noqa: C901
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the markdown report to this path (UTF-8). If absent, write to stdout.",
    )
    args = parser.parse_args(argv)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        sink = args.output.open("w", encoding="utf-8", newline="\n")
    else:
        sink = sys.stdout

    _orig_print = print

    def _emit(*items: object) -> None:
        text = " ".join(str(it) for it in items)
        sink.write(text + "\n")

    # Local print rebinding via `print = _emit` doesn't propagate to nested closures,
    # so we redirect stdout instead while building the report. This keeps the
    # rest of the function readable and unchanged.
    if args.output is not None:
        sys.stdout = sink
    try:
        _build_report()
    finally:
        if args.output is not None:
            sys.stdout = sys.__stdout__
            sink.close()


def _build_report() -> None:  # noqa: C901
    scans = _collect_files()
    defs = _collect_defs(scans)
    refs = _collect_references(scans)

    # ---------- 1. Orphan top-level functions ----------
    orphan_fns: list[Definition] = []
    for d in defs:
        if d.is_method or d.is_class:
            continue
        if _is_protected(d.name):
            continue
        external = [r for r in refs.get(d.name, []) if not _is_self_ref(d, r)]
        if not external:
            orphan_fns.append(d)

    # ---------- 2. Orphan classes ----------
    orphan_cls: list[Definition] = []
    cls_methods: dict[str, list[Definition]] = defaultdict(list)
    for d in defs:
        if d.is_method:
            cls = d.qualname.split(".", 1)[0]
            cls_methods[cls].append(d)
    for d in defs:
        if not d.is_class or _is_protected(d.name):
            continue
        external = [r for r in refs.get(d.name, []) if not _is_self_ref(d, r)]
        if not external:
            orphan_cls.append(d)

    # ---------- 3. Orphan methods (private only) ----------
    # We keep only methods not on protected lists, not Qt-decorated, body LOC >= 3.
    orphan_methods: list[Definition] = []
    for d in defs:
        if not d.is_method or _is_protected(d.name):
            continue
        if any(dec in {"pyqtSlot", "Slot", "pyqtProperty", "property", "staticmethod", "classmethod", "abstractmethod", "override"} for dec in d.decorators):
            continue
        if d.body_loc < 3:
            continue
        external = [r for r in refs.get(d.name, []) if not _is_self_ref(d, r)]
        if not external:
            orphan_methods.append(d)

    # ---------- 4. Test-only symbols ----------
    test_only: list[tuple[Definition, int]] = []
    for d in defs:
        if d.is_method or d.is_class:
            continue
        if _is_protected(d.name):
            continue
        ext_runtime = []
        ext_test = []
        for r in refs.get(d.name, []):
            if _is_self_ref(d, r):
                continue
            if str(r[0]).startswith(str(TESTS_DIR)):
                ext_test.append(r)
            else:
                ext_runtime.append(r)
        if ext_test and not ext_runtime:
            test_only.append((d, len(ext_test)))

    # ---------- 5. Duplicate function bodies ----------
    by_hash: dict[str, list[Definition]] = defaultdict(list)
    for d in defs:
        if d.is_class:
            continue
        if d.body_loc < DUP_MIN_LOC:
            continue
        if not d.body_hash:
            continue
        by_hash[d.body_hash].append(d)
    duplicates = [(h, lst) for h, lst in by_hash.items() if len(lst) >= 2]
    duplicates.sort(key=lambda kv: -kv[1][0].body_loc * len(kv[1]))

    # ---------- 6. Unused imports ----------
    unused_imports = _collect_imports(scans)

    # ---------- Output ----------
    print("# CERTUS — Dead Code / Orphan / Duplicate Audit")
    print()
    print("> Generated by `tools/dead_code_audit.py` (aggressive mode).")
    print(">")
    print(f"> **Scope:** {sum(1 for s in scans if not s.is_test)} source files + {sum(1 for s in scans if s.is_test)} test files.")
    print(f"> **Defs scanned:** {sum(1 for d in defs if not d.is_class and not d.is_method)} top-level fns + "
          f"{sum(1 for d in defs if d.is_class)} classes + {sum(1 for d in defs if d.is_method)} methods.")
    print(">")
    print("> **Aggressive heuristics.** A finding here is a *candidate*, not a guarantee.")
    print("> Verify each flag against Qt slot mechanisms, dynamic dispatch, or framework hooks before deletion.")
    print()
    print("### Known false-positive patterns (review BEFORE deleting)")
    print()
    print("- **Qt event overrides** invoked by the framework, not from Python: ")
    print("  `enterEvent`, `leaveEvent`, `mousePressEvent`, `keyPressEvent`, `paintEvent`, ")
    print("  `resizeEvent`, `showEvent`, `hideEvent`, `closeEvent`, `timerEvent`, `wheelEvent`, ")
    print("  `focusInEvent`, `focusOutEvent`, `dragEnterEvent`, `dropEvent`, `contextMenuEvent`, ")
    print("  `changeEvent`, `eventFilter`.")
    print("- **pyqtgraph hooks** invoked via duck-typing: `tickStrings`, `tickValues`, `paint`, ")
    print("  `boundingRect`, `mouseClickEvent`, `hoverEvent`.")
    print("- **`from __future__ import annotations`** is a compile-time directive; flagged as 'unused' ")
    print("  trivially but keep — required for PEP 563 deferred evaluation.")
    print("- **`field` / `dataclass` / `Optional`** referenced only in type annotations may be flagged ")
    print("  if the file uses string-based forward references; keep when the symbol is in `*.pyi` style.")
    print()
    print("---")
    print()

    # 1. Orphan top-level fns
    print("## 1. Orphan top-level functions")
    print()
    print(f"**Total candidates: {len(orphan_fns)}**")
    print()
    if orphan_fns:
        print("| File | Line | Name | Body LOC |")
        print("| :--- | ---: | :--- | ---: |")
        orphan_fns.sort(key=lambda d: (str(d.file), d.line))
        for d in orphan_fns:
            print(f"| `{d.file}` | {d.line} | `{d.name}` | {d.body_loc} |")
    print()

    # 2. Orphan classes
    print("## 2. Orphan classes (never instantiated nor inherited)")
    print()
    print(f"**Total candidates: {len(orphan_cls)}**")
    print()
    if orphan_cls:
        print("| File | Line | Class | Methods |")
        print("| :--- | ---: | :--- | ---: |")
        orphan_cls.sort(key=lambda d: (str(d.file), d.line))
        for d in orphan_cls:
            n_meth = len(cls_methods.get(d.name, []))
            print(f"| `{d.file}` | {d.line} | `{d.name}` | {n_meth} |")
    print()

    # 3. Orphan methods
    print("## 3. Orphan methods (no AST/regex reference, not Qt-decorated)")
    print()
    print(f"**Total candidates: {len(orphan_methods)}**")
    print()
    if orphan_methods:
        # Group by file for readability
        by_file: dict[Path, list[Definition]] = defaultdict(list)
        for d in orphan_methods:
            by_file[d.file].append(d)
        for f in sorted(by_file, key=lambda p: str(p)):
            print(f"### {f}")
            print()
            print("| Line | Class.Method | Body LOC |")
            print("| ---: | :--- | ---: |")
            for d in sorted(by_file[f], key=lambda d: d.line):
                print(f"| {d.line} | `{d.qualname}` | {d.body_loc} |")
            print()

    # 4. Test-only
    print("## 4. Symbols referenced **only** by tests")
    print()
    print(f"**Total candidates: {len(test_only)}**")
    print()
    if test_only:
        print("| File | Line | Name | Test refs |")
        print("| :--- | ---: | :--- | ---: |")
        test_only.sort(key=lambda kv: (str(kv[0].file), kv[0].line))
        for d, n in test_only:
            print(f"| `{d.file}` | {d.line} | `{d.name}` | {n} |")
    print()

    # 5. Duplicates
    print(f"## 5. Duplicate function bodies (≥ {DUP_MIN_LOC} LOC, exact match)")
    print()
    print(f"**Total clusters: {len(duplicates)}**")
    print()
    if duplicates:
        print("| Hash | Body LOC | × | Sites |")
        print("| :--- | ---: | ---: | :--- |")
        for h, lst in duplicates[:80]:
            sites = ", ".join(f"`{d.file}:{d.line}` ({d.qualname})" for d in lst[:6])
            if len(lst) > 6:
                sites += f", + {len(lst) - 6} more"
            print(f"| `{h}` | {lst[0].body_loc} | {len(lst)} | {sites} |")
        if len(duplicates) > 80:
            print()
            print(f"*… {len(duplicates) - 80} smaller duplicate clusters elided.*")
    print()

    # 6. Unused imports
    n_unused = sum(len(v) for v in unused_imports.values())
    print(f"## 6. Unused imports — top 30 files (total: {n_unused} unused names across {len(unused_imports)} files)")
    print()
    if unused_imports:
        ranked = sorted(unused_imports.items(), key=lambda kv: -len(kv[1]))[:30]
        print("| File | Unused count | Sample (line: name from module) |")
        print("| :--- | ---: | :--- |")
        for f, lst in ranked:
            sample = "; ".join(f"{ln}: `{nm}` from `{mod}`" for ln, nm, mod in lst[:4])
            if len(lst) > 4:
                sample += f"; + {len(lst) - 4} more"
            print(f"| `{f}` | {len(lst)} | {sample} |")
    print()

    # Summary
    print("---")
    print()
    print("## Summary")
    print()
    print(f"- **Orphan top-level functions:** {len(orphan_fns)}")
    print(f"- **Orphan classes:** {len(orphan_cls)}")
    print(f"- **Orphan methods (private, non-Qt):** {len(orphan_methods)}")
    print(f"- **Test-only public symbols:** {len(test_only)}")
    print(f"- **Duplicate function-body clusters (≥ {DUP_MIN_LOC} LOC):** {len(duplicates)}")
    print(f"- **Files with unused imports:** {len(unused_imports)} (total {n_unused} unused names)")


if __name__ == "__main__":
    main()
