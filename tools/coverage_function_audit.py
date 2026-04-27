"""Map pytest-cov "Missing" line ranges to top-level functions of a target module.

Designed to support PHY-1 Step 2 (backlog couverture KPI-5). Generates a sorted
list of uncovered functions by size (LOC) so micro-batches B.22..B.N can be
dispatched in priority order.

Usage:
    python tools/coverage_function_audit.py \
        --target _certus_physics_impl.py \
        --xml coverage.xml

Or, parse the pytest --cov-report=term-missing dump captured to a file:

    python tools/coverage_function_audit.py \
        --target _certus_physics_impl.py \
        --term-report coverage_missing.txt

Output is plain text (markdown table) on stdout.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FuncInfo:
    name: str
    qualname: str
    start: int
    end: int
    loc: int
    missed: int
    cover_pct: float


def _iter_functions(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """Yield (function_node, qualified_name) for every function/method defined."""
    out: list[tuple[ast.AST, str]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{child.name}"
                out.append((child, qualname))
                visit(child, f"{qualname}.")

    visit(tree, "")
    return out


def _parse_term_missing(text: str) -> set[int]:
    """Parse the `Missing` column produced by `pytest --cov-report=term-missing`."""
    missed: set[int] = set()
    # Find the line for the target file (first column == module path/name).
    # Lines look like: `_certus_physics_impl.py    4650   4280     8%   586-670, 705, ...`
    block_started = False
    buffer = ""
    for line in text.splitlines():
        if not block_started:
            if line.lstrip().startswith("Name") and "Missing" in line:
                block_started = True
            continue
        if line.startswith("---") or line.startswith("==="):
            if buffer:
                break
            continue
        # Append continuation: pytest-cov wraps long missing lists across lines.
        if line.lstrip().startswith("TOTAL"):
            break
        buffer += " " + line
    # buffer holds the data row(s); extract the trailing missing ranges
    m = re.search(r"\d+%\s+(?P<missing>.+)$", buffer.strip())
    if not m:
        return missed
    raw = m.group("missing")
    # Split on commas — entries can be "586-670" or single integers "705".
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or entry == "":
            continue
        if "-" in entry:
            try:
                start, end = entry.split("-", 1)
                missed.update(range(int(start), int(end) + 1))
            except ValueError:
                continue
        else:
            try:
                missed.add(int(entry))
            except ValueError:
                continue
    return missed


def _parse_coverage_xml(xml_path: Path, target_filename: str) -> set[int]:
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    missed: set[int] = set()
    for cls in root.findall(".//class"):
        filename = cls.attrib.get("filename", "")
        if not filename.endswith(target_filename):
            continue
        for ln in cls.findall(".//line"):
            try:
                hits = int(ln.attrib.get("hits", "0"))
                num = int(ln.attrib.get("number", "0"))
            except ValueError:
                continue
            if hits == 0 and num > 0:
                missed.add(num)
        break
    return missed


def audit(target: Path, missed_lines: set[int]) -> list[FuncInfo]:
    text = target.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(text, filename=str(target))
    out: list[FuncInfo] = []
    for node, qualname in _iter_functions(tree):
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", start) or start)
        if end < start:
            end = start
        loc = end - start + 1
        miss_in_func = sum(1 for n in range(start, end + 1) if n in missed_lines)
        cover = 100.0 * (1.0 - miss_in_func / loc) if loc > 0 else 0.0
        out.append(
            FuncInfo(
                name=getattr(node, "name", "?"),
                qualname=qualname,
                start=start,
                end=end,
                loc=loc,
                missed=miss_in_func,
                cover_pct=cover,
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Target python file (relative to repo root)")
    parser.add_argument("--term-report", help="Path to a captured `pytest --cov-report=term-missing` text dump")
    parser.add_argument("--xml", help="Path to a coverage.xml report (preferred when available)")
    parser.add_argument("--top", type=int, default=20, help="How many uncovered functions to display")
    parser.add_argument("--min-loc", type=int, default=10, help="Ignore functions smaller than this many LOC")
    args = parser.parse_args()

    target = (REPO_ROOT / args.target).resolve()
    if not target.exists():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2

    if args.xml:
        missed = _parse_coverage_xml(Path(args.xml), target.name)
    elif args.term_report:
        missed = _parse_term_missing(Path(args.term_report).read_text(encoding="utf-8", errors="ignore"))
    else:
        print("ERROR: provide either --xml or --term-report", file=sys.stderr)
        return 2

    funcs = audit(target, missed)
    fully_uncovered = [f for f in funcs if f.loc >= args.min_loc and f.missed == f.loc]
    partially = [f for f in funcs if f.loc >= args.min_loc and 0 < f.missed < f.loc]

    fully_uncovered.sort(key=lambda f: -f.loc)
    partially.sort(key=lambda f: (-f.missed, -f.loc))

    print(f"# Coverage Function Audit — {target.name}")
    print("")
    print(f"- Missed lines (raw): **{len(missed)}**")
    print(f"- Functions analysed: **{len(funcs)}**")
    print(f"- Fully uncovered (>= {args.min_loc} LOC): **{len(fully_uncovered)}**")
    print(f"- Partially uncovered (>= {args.min_loc} LOC): **{len(partially)}**")
    print("")
    print(f"## Top {args.top} fully uncovered functions (by LOC desc)")
    print("")
    print("| Rank | Qualname | Lines | LOC |")
    print("| ---: | :--- | :---: | ---: |")
    for i, f in enumerate(fully_uncovered[: args.top], 1):
        print(f"| {i} | `{f.qualname}` | {f.start}-{f.end} | {f.loc} |")
    print("")
    print(f"## Top {args.top} partially uncovered functions (by missed lines desc)")
    print("")
    print("| Rank | Qualname | Lines | LOC | Missed | Cover % |")
    print("| ---: | :--- | :---: | ---: | ---: | ---: |")
    for i, f in enumerate(partially[: args.top], 1):
        print(f"| {i} | `{f.qualname}` | {f.start}-{f.end} | {f.loc} | {f.missed} | {f.cover_pct:.1f}% |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
