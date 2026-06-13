#!/usr/bin/env python3
"""Audit tool: list every `signal.connect(lambda …)` site in the workspace.

Usage
-----
    python tools/lambda_connect_audit.py              # print full table
    python tools/lambda_connect_audit.py --count-only # print total count
    python tools/lambda_connect_audit.py --ci         # exit 1 if any site found
    python tools/lambda_connect_audit.py --ci --max-count 78  # ratchet baseline

Memory-leak risk: a `connect(lambda: ...)` that captures `self` creates an
implicit reference cycle preventing garbage collection of the QObject.  All
such sites should be replaced by `functools.partial`, a named method, or a
direct slot reference.

CI integration (lint.yml)::

        - name: lambda-connect audit
            run: python tools/lambda_connect_audit.py --ci --max-count 78
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Files to skip (reference copies, build artefacts, etc.)
_SKIP_NAMES = frozenset({"CERTUS_STRAT_OLD.py"})
_PATTERN = re.compile(r"\.connect\s*\(\s*lambda\b")


def _scan(root: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for py_file in sorted(root.glob("*.py")):
        if py_file.name in _SKIP_NAMES:
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if _PATTERN.search(line):
                hits.append((py_file.name, lineno, line.rstrip()))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Print only the total site count.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit with code 1 if site count exceeds --max-count.",
    )
    parser.add_argument(
        "--max-count",
        type=int,
        default=0,
        metavar="N",
        help="With --ci: allow up to N sites (ratchet baseline). Default 0 = strict.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    hits = _scan(root)

    if args.count_only:
        print(len(hits))
        return 0

    if hits:
        print(f"# connect(lambda) sites: {len(hits)}\n")
        max_file = max(len(f) for f, _, _ in hits)
        for filename, lineno, line in hits:
            print(f"  {filename:{max_file}}:{lineno:<6}  {line.strip()[:100]}")
    else:
        print("# connect(lambda) sites: 0 — clean!")

    if args.ci and len(hits) > args.max_count:
        print(
            f"\nCI FAIL: {len(hits)} connect(lambda) site(s) found "
            f"(allowed: {args.max_count}). "
            "Replace with functools.partial, a named method, or a direct slot reference.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
