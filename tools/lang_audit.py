#!/usr/bin/env python3
"""Audit non-ASCII/accented string literals in Python sources (#46)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ACCENTED_CHARS = set("àâäéèêëîïôöùûüÿçÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇ")


def _looks_user_text(s: str) -> bool:
    s = str(s or "").strip()
    if len(s) < 3:
        return False
    if s.startswith(("http://", "https://")):
        return False
    return True


def scan_file(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return out

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            txt = node.value
            if not _looks_user_text(txt):
                continue
            if any(ch in ACCENTED_CHARS for ch in txt):
                preview = " ".join(txt.split())[:120]
                out.append((int(getattr(node, "lineno", 0)), preview))
    return out


def main() -> int:
    def _safe_print(msg: str) -> None:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))

    root = Path(".")
    py_files = sorted(p for p in root.rglob("*.py") if ".venv" not in p.parts and "build" not in p.parts)
    total = 0
    for p in py_files:
        matches = scan_file(p)
        if not matches:
            continue
        total += len(matches)
        _safe_print(f"{p}:")
        for ln, prev in matches[:20]:
            _safe_print(f"  L{ln}: {prev}")
        if len(matches) > 20:
            _safe_print(f"  ... +{len(matches)-20} more")
    _safe_print(f"\nTotal accented literals: {total}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
