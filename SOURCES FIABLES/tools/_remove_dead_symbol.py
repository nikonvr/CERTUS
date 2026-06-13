"""One-shot helper: remove a top-level class/function or a method by
AST-resolved name + line range. Disposable.

Usage:
    python tools/_remove_dead_symbol.py <FILE> <SYMBOL>          [--dry-run]
    python tools/_remove_dead_symbol.py <FILE> <CLASS>.<METHOD>  [--dry-run]

Behavior:
- Top-level form: locates `class NAME(...)` or `def NAME(...)` at module level.
- Dotted form: locates `def METHOD(...)` inside `class CLASS(...)`.
- Computes the source range (lineno..end_lineno) using the AST.
- Extends the range upward to absorb a single immediately-preceding blank line
  (for clean diff), and downward to absorb up to two trailing blank lines.
- Rewrites the file. With --dry-run, prints the lines that would be removed.

Safety:
- Refuses to remove if the symbol name resolves to more than one definition.
- Refuses to remove if the file does not parse before / after the edit.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _find_top_level(tree: ast.Module, name: str) -> ast.AST | None:
    matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name]
    if len(matches) == 0:
        print(f"ERROR: symbol '{name}' not found at top level.", file=sys.stderr)
        return None
    if len(matches) > 1:
        print(f"ERROR: symbol '{name}' defined {len(matches)} times at top level (lines: "
              f"{', '.join(str(m.lineno) for m in matches)}).", file=sys.stderr)
        return None
    return matches[0]


def _find_method(tree: ast.Module, class_name: str, method_name: str) -> ast.AST | None:
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
    if not classes:
        print(f"ERROR: class '{class_name}' not found at top level.", file=sys.stderr)
        return None
    if len(classes) > 1:
        print(f"ERROR: class '{class_name}' defined {len(classes)} times at top level.", file=sys.stderr)
        return None
    cls = classes[0]
    methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not methods:
        print(f"ERROR: method '{class_name}.{method_name}' not found.", file=sys.stderr)
        return None
    if len(methods) > 1:
        print(f"ERROR: method '{class_name}.{method_name}' defined {len(methods)} times "
              f"(lines: {', '.join(str(m.lineno) for m in methods)}).", file=sys.stderr)
        return None
    return methods[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove a top-level class/function by name.")
    parser.add_argument("file", type=Path)
    parser.add_argument("symbol", type=str)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        return 2

    src = args.file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"ERROR: cannot parse {args.file}: {e}", file=sys.stderr)
        return 2

    if "." in args.symbol:
        class_name, _, method_name = args.symbol.partition(".")
        node = _find_method(tree, class_name, method_name)
    else:
        node = _find_top_level(tree, args.symbol)
    if node is None:
        return 2

    start = node.lineno  # 1-indexed
    end = node.end_lineno or start  # 1-indexed inclusive
    lines = src.splitlines(keepends=True)

    # Extend upward by 1 blank line (for diff cleanliness).
    if start - 2 >= 0 and lines[start - 2].strip() == "":
        start -= 1
    # Extend downward up to 2 blank lines.
    j = end
    while j < len(lines) and lines[j].strip() == "" and (j - end) < 2:
        j += 1
    end = j

    removed = lines[start - 1:end]
    new_lines = lines[: start - 1] + lines[end:]
    new_src = "".join(new_lines)

    if args.dry_run:
        print(f"--- would remove {len(removed)} lines from {args.file} (start={start}, end={end}) ---")
        for i, ln in enumerate(removed, start=start):
            print(f"{i:6d}|{ln}", end="")
        return 0

    # Validate parse before writing
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"ERROR: post-removal source does not parse: {e}", file=sys.stderr)
        return 3

    args.file.write_text(new_src, encoding="utf-8", newline="\n")
    if isinstance(node, ast.ClassDef):
        kind = "class"
    elif "." in args.symbol:
        kind = "method"
    else:
        kind = "function"
    print(f"REMOVED: {kind} '{args.symbol}' ({len(removed)} lines, {start}..{end - 1}) from {args.file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
