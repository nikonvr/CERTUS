"""The preflight counts the modified files with the long-path support of git.

Without `core.longpaths`, git on Windows cannot open the paths of more than 260 characters under reports/: it listed 38
of them as deleted, and the preflight reported 62 modified files for 24 real ones (reports/AUDIT_SUITE_CERTUS_2026-10-18.md,
C05). The script runs its checks when it is imported, so this test reads its syntax tree instead of calling it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "preflight.py"


def _git_status_calls() -> list[list[str]]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run":
            literals = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if literals[:1] == ["git"] and "status" in literals:
                found.append(literals)
    return found


@pytest.mark.unit
def test_every_git_status_of_the_preflight_asks_for_long_paths() -> None:
    calls = _git_status_calls()
    assert calls, "the preflight no longer runs git status: this test has nothing left to watch"
    for literals in calls:
        assert literals[1:3] == ["-c", "core.longpaths=true"], literals
