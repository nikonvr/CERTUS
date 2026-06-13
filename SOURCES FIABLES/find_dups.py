from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
}

DEFAULT_EXTENSIONS = {".py"}
CACHE_FILE = ".ast_analyzer_cache.json"


@dataclass(slots=True)
class FunctionRecord:
    file: str
    qualname: str
    name: str
    lineno: int
    end_lineno: int
    args: int
    statements: int
    complexity: int
    ast_hash: str
    canonical_hash: str
    source: str


@dataclass(slots=True)
class ClassRecord:
    file: str
    qualname: str
    name: str
    lineno: int
    end_lineno: int
    methods: int
    ast_hash: str
    canonical_hash: str


@dataclass(slots=True)
class FileSummary:
    file: str
    lines: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    max_function_complexity: int = 0
    todo_like_comments: int = 0


@dataclass(slots=True)
class AnalysisResult:
    file: str
    mtime_ns: int
    size: int
    summary: FileSummary
    functions: list[FunctionRecord]
    classes: list[ClassRecord]
    error: str | None = None


class ParentTracker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.parents: dict[ast.AST, ast.AST | None] = {}
        self._stack: list[ast.AST] = []

    def generic_visit(self, node: ast.AST):
        self.parents[node] = self._stack[-1] if self._stack else None
        self._stack.append(node)
        super().generic_visit(node)
        self._stack.pop()


class _ASTNormalizer(ast.NodeTransformer):
    """Normalize an AST so structurally similar code hashes together."""

    def __init__(self) -> None:
        super().__init__()
        self._name_map: dict[str, str] = {}
        self._counter = 0

    def _canonical_name(self, original: str) -> str:
        if original not in self._name_map:
            self._counter += 1
            self._name_map[original] = f"var_{self._counter}"
        return self._name_map[original]

    def visit_Name(self, node: ast.Name):
        return ast.copy_location(ast.Name(id=self._canonical_name(node.id), ctx=type(node.ctx)()), node)

    def visit_arg(self, node: ast.arg):
        return ast.copy_location(ast.arg(arg=self._canonical_name(node.arg), annotation=None, type_comment=None), node)

    def visit_Attribute(self, node: ast.Attribute):
        node = self.generic_visit(node)
        return ast.copy_location(node, node) if isinstance(node, ast.AST) else node

    def visit_Constant(self, node: ast.Constant):
        value = node.value
        if isinstance(value, str):
            value = "<str>"
        elif isinstance(value, (int, float, complex)):
            value = "<num>"
        elif value is None:
            value = None
        elif isinstance(value, bool):
            value = bool(value)
        return ast.copy_location(ast.Constant(value=value, kind=None), node)


class Analyzer(ast.NodeVisitor):
    def __init__(self, source: str, file_path: Path) -> None:
        self.source = source
        self.file_path = file_path
        self.module = ast.parse(source)
        self.parents = ParentTracker()
        self.parents.visit(self.module)
        self.function_records: list[FunctionRecord] = []
        self.class_records: list[ClassRecord] = []
        self.summary = FileSummary(file=str(file_path), lines=source.count("\n") + 1)
        self._scope: list[str] = []
        self._visit_module()

    def _qualname(self, name: str) -> str:
        return ".".join(self._scope + [name]) if self._scope else name

    def _visit_module(self) -> None:
        for node in self.module.body:
            self.visit(node)

    def _hash_ast(self, node: ast.AST, normalize: bool) -> str:
        target = _ASTNormalizer().visit(ast.fix_missing_locations(node)) if normalize else node
        dump = ast.dump(target, annotate_fields=False, include_attributes=False)
        return hashlib.sha1(dump.encode("utf-8")).hexdigest()

    def _statement_count(self, node: ast.AST) -> int:
        return sum(1 for n in ast.walk(node) if isinstance(n, ast.stmt))

    def _cyclomatic_complexity(self, node: ast.AST) -> int:
        complexity = 1
        decision_nodes = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.With,
            ast.AsyncWith,
            ast.Try,
            ast.ExceptHandler,
            ast.BoolOp,
            ast.IfExp,
            ast.comprehension,
            ast.Match,
        )
        match_case_type = getattr(ast, "match_case", None)
        for n in ast.walk(node):
            if isinstance(n, decision_nodes):
                complexity += 1
            if match_case_type is not None and isinstance(n, match_case_type):
                complexity += 1
        return complexity

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        try:
            source = ast.get_source_segment(self.source, node) or ""
        except Exception:
            source = ""
        record = FunctionRecord(
            file=str(self.file_path),
            qualname=self._qualname(node.name),
            name=node.name,
            lineno=getattr(node, "lineno", 0),
            end_lineno=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
            args=len(getattr(node.args, "posonlyargs", [])) + len(node.args.args) + len(node.args.kwonlyargs),
            statements=self._statement_count(node),
            complexity=self._cyclomatic_complexity(node),
            ast_hash=self._hash_ast(node, normalize=False),
            canonical_hash=self._hash_ast(node, normalize=True),
            source=source.strip(),
        )
        self.function_records.append(record)
        self.summary.functions += 1
        self.summary.max_function_complexity = max(self.summary.max_function_complexity, record.complexity)

    def _record_class(self, node: ast.ClassDef) -> None:
        methods = sum(1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        record = ClassRecord(
            file=str(self.file_path),
            qualname=self._qualname(node.name),
            name=node.name,
            lineno=getattr(node, "lineno", 0),
            end_lineno=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
            methods=methods,
            ast_hash=self._hash_ast(node, normalize=False),
            canonical_hash=self._hash_ast(node, normalize=True),
        )
        self.class_records.append(record)
        self.summary.classes += 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record_class(node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_Import(self, node: ast.Import) -> None:
        self.summary.imports += 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.summary.imports += 1


def iter_python_files(root: Path, include_hidden: bool = False) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and (include_hidden or not d.startswith("."))]
        for name in files:
            path = current / name
            if path.suffix not in DEFAULT_EXTENSIONS:
                continue
            if not include_hidden and any(part.startswith(".") for part in path.parts):
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            yield path


def _load_cache(cache_path: Path) -> dict[str, dict[str, int]]:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache_path: Path, cache: dict[str, dict[str, int]]) -> None:
    try:
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _scan_file(path: Path, cache_entry: dict[str, int] | None = None) -> AnalysisResult:
    stat = path.stat()
    try:
        source = path.read_text(encoding="utf-8")
        analyzer = Analyzer(source, path)
        return AnalysisResult(
            file=str(path),
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            summary=analyzer.summary,
            functions=analyzer.function_records,
            classes=analyzer.class_records,
        )
    except Exception as exc:
        return AnalysisResult(
            file=str(path),
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            summary=FileSummary(file=str(path)),
            functions=[],
            classes=[],
            error=f"{type(exc).__name__}: {exc}",
        )


def _bucket(items: Iterable[FunctionRecord | ClassRecord], attr: str) -> dict[str, list]:
    buckets: dict[str, list] = defaultdict(list)
    for item in items:
        buckets[getattr(item, attr)].append(item)
    return buckets


def _render_groups(records: list[FunctionRecord], min_group_size: int, key_attr: str = "canonical_hash") -> list[dict[str, object]]:
    groups = []
    for group_hash, bucket in _bucket(records, key_attr).items():
        if len(bucket) < min_group_size:
            continue
        groups.append(
            {
                "hash": group_hash,
                "size": len(bucket),
                "items": [
                    {
                        "file": r.file,
                        "qualname": r.qualname,
                        "line": r.lineno,
                        "end_line": r.end_lineno,
                        "complexity": r.complexity,
                        "statements": r.statements,
                    }
                    for r in bucket
                ],
            }
        )
    return sorted(groups, key=lambda g: (-int(g["size"]), str(g["hash"])))


def _render_class_groups(records: list[ClassRecord], min_group_size: int = 2) -> list[dict[str, object]]:
    groups = []
    for group_hash, bucket in _bucket(records, "canonical_hash").items():
        if len(bucket) < min_group_size:
            continue
        groups.append(
            {
                "hash": group_hash,
                "size": len(bucket),
                "items": [
                    {"file": r.file, "qualname": r.qualname, "line": r.lineno, "methods": r.methods}
                    for r in bucket
                ],
            }
        )
    return sorted(groups, key=lambda g: (-int(g["size"]), str(g["hash"])))


def _dedupe_similar(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: dict[tuple[str, ...], dict[str, object]] = {}
    out: list[dict[str, object]] = []
    for group in groups:
        fingerprint = tuple(sorted(item["qualname"] for item in group["items"]))
        if fingerprint in seen:
            continue
        seen[fingerprint] = group
        out.append(group)
    return out


def build_report(
    root: Path,
    min_dup_size: int,
    min_complexity: int,
    include_hidden: bool = False,
    jobs: int = 1,
    cache_enabled: bool = True,
) -> dict[str, object]:
    cache_path = root / CACHE_FILE
    cache = _load_cache(cache_path) if cache_enabled else {}
    paths = list(iter_python_files(root, include_hidden=include_hidden))
    results: list[AnalysisResult] = []

    if jobs > 1 and len(paths) > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(_scan_file, path, cache.get(str(path))): path for path in paths}
            for fut in as_completed(futures):
                results.append(fut.result())
    else:
        for path in paths:
            results.append(_scan_file(path, cache.get(str(path))))

    results.sort(key=lambda r: r.file)

    all_functions: list[FunctionRecord] = []
    all_classes: list[ClassRecord] = []
    file_summaries: list[FileSummary] = []
    parse_errors: list[dict[str, str]] = []
    new_cache: dict[str, dict[str, int]] = {}

    for result in results:
        new_cache[result.file] = {"mtime_ns": result.mtime_ns, "size": result.size}
        if result.error == "CACHED":
            cached_summary = cache.get(result.file, {})
            file_summaries.append(
                FileSummary(
                    file=result.file,
                    lines=cached_summary.get("lines", 0),
                    functions=cached_summary.get("functions", 0),
                    classes=cached_summary.get("classes", 0),
                    imports=cached_summary.get("imports", 0),
                    max_function_complexity=cached_summary.get("max_function_complexity", 0),
                    todo_like_comments=cached_summary.get("todo_like_comments", 0),
                )
            )
            continue
        if result.error:
            parse_errors.append({"file": result.file, "error": result.error})
            continue

        file_summaries.append(result.summary)
        all_functions.extend(result.functions)
        all_classes.extend(result.classes)

        if cache_enabled:
            new_cache[result.file].update(
                {
                    "lines": result.summary.lines,
                    "functions": result.summary.functions,
                    "classes": result.summary.classes,
                    "imports": result.summary.imports,
                    "max_function_complexity": result.summary.max_function_complexity,
                    "todo_like_comments": result.summary.todo_like_comments,
                }
            )

    if cache_enabled:
        _save_cache(cache_path, new_cache)

    duplicate_functions = _dedupe_similar(_render_groups(all_functions, min_dup_size, key_attr="canonical_hash"))
    duplicate_classes = _render_class_groups(all_classes, 2)
    large_functions = [
        {
            "file": r.file,
            "qualname": r.qualname,
            "line": r.lineno,
            "end_line": r.end_lineno,
            "statements": r.statements,
            "complexity": r.complexity,
        }
        for r in sorted(all_functions, key=lambda r: (-r.complexity, -r.statements, r.file, r.lineno))
        if r.complexity >= min_complexity
    ]

    files_hotspots = [
        {
            "file": fs.file,
            "lines": fs.lines,
            "functions": fs.functions,
            "classes": fs.classes,
            "imports": fs.imports,
            "max_function_complexity": fs.max_function_complexity,
            "hot_score": fs.functions * 2 + fs.classes * 2 + fs.imports + fs.max_function_complexity,
        }
        for fs in file_summaries
    ]
    files_hotspots.sort(key=lambda x: (-x["hot_score"], -x["functions"], -x["classes"], x["file"]))

    return {
        "root": str(root),
        "files_scanned": len(file_summaries),
        "jobs": jobs,
        "cache_enabled": cache_enabled,
        "parse_errors": parse_errors,
        "summary": {
            "functions": len(all_functions),
            "classes": len(all_classes),
            "duplicate_function_groups": len(duplicate_functions),
            "duplicate_class_groups": len(duplicate_classes),
            "large_functions": len(large_functions),
        },
        "top_complex_functions": large_functions[:25],
        "duplicate_functions": duplicate_functions,
        "duplicate_classes": duplicate_classes,
        "files": files_hotspots[:200],
    }


def print_human_report(report: dict[str, object]) -> None:
    summary = report["summary"]
    print(f"AST report for {report['root']}")
    print(f"Files scanned: {report['files_scanned']} | jobs: {report['jobs']} | cache: {'on' if report['cache_enabled'] else 'off'}")
    print(
        "Functions: {functions} | Classes: {classes} | Duplicate function groups: {dup_f} | Duplicate class groups: {dup_c} | Large functions: {large}".format(
            functions=summary["functions"],
            classes=summary["classes"],
            dup_f=summary["duplicate_function_groups"],
            dup_c=summary["duplicate_class_groups"],
            large=summary["large_functions"],
        )
    )

    if report["parse_errors"]:
        print(f"Parse errors: {len(report['parse_errors'])}")

    if report["duplicate_functions"]:
        print("\nDuplicate function groups:")
        for group in report["duplicate_functions"][:20]:
            print(f"- size {group['size']} | hash {group['hash']}")
            for item in group["items"]:
                print(f"  - {item['file']}:{item['line']}-{item['end_line']} {item['qualname']} (complexity {item['complexity']})")

    if report["top_complex_functions"]:
        print("\nTop complex functions:")
        for item in report["top_complex_functions"][:15]:
            print(
                f"- {item['complexity']:>3} | {item['file']}:{item['line']}-{item['end_line']} | {item['qualname']} | {item['statements']} statements"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ultimate AST analyzer for CERTUS")
    parser.add_argument("path", nargs="?", default="certus", help="Root directory to scan")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--min-dup-size", type=int, default=2, help="Minimum duplicate group size")
    parser.add_argument("--min-complexity", type=int, default=12, help="Minimum cyclomatic complexity to flag")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden directories and files")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2), help="Parallel workers")
    parser.add_argument("--no-cache", action="store_true", help="Disable incremental cache")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    report = build_report(root, args.min_dup_size, args.min_complexity, args.include_hidden, max(1, args.jobs), not args.no_cache)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_human_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
