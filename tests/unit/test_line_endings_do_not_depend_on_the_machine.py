"""The repository stores LF whatever `core.autocrlf` says on the machine that commits.

Measured 2026-09-30, before `.gitattributes` existed: this machine has `core.autocrlf=true`, so 2 266 text files
are LF in the index and CRLF on disk, and every commit says `LF will be replaced by CRLF`. Nothing in the
repository fixed the rule: a contributor whose git converted nothing would have committed CRLF, and a shell
script (`.githooks/post-commit`, `scripts/*.sh`) checked out with CRLF does not start (`/bin/sh^M`).

`git check-attr` answers what git itself will do with a path, which is the property that matters.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(ROOT), "--no-optional-locks", *args], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _attribute(name: str, path: str) -> str:
    """The value git gives `name` for `path`: `lf`, `auto`, `unset`, `unspecified`..."""
    line = _git("check-attr", name, "--", path).strip()
    return line.rsplit(": ", 1)[1]


def _first_tracked(pattern: str) -> str:
    tracked = _git("ls-files", pattern).split("\n")
    assert tracked[0], f"no tracked file matches {pattern}: the checks below would prove nothing"
    return tracked[0]


def test_text_files_are_normalised_by_git_itself() -> None:
    assert _attribute("text", "scripts/metrics.py") == "auto"
    assert _attribute("text", "CLAUDE.md") == "auto"


@pytest.mark.parametrize("path", [".githooks/post-commit", "anything/new_script.sh"])
def test_what_an_interpreter_reads_keeps_its_line_feeds(path) -> None:
    assert _attribute("eol", path) == "lf"


@pytest.mark.parametrize("pattern", ["*.xlsx", "*.npy"])
def test_binary_data_is_never_converted(pattern) -> None:
    assert _attribute("text", _first_tracked(pattern)) == "unset"
