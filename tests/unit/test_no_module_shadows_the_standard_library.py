"""No module of the project can be taken for a module of the standard library.

The families of CERTUS are told apart by a prefix in the file name: `certus_re_*` is reverse engineering, `CERTUS_RE.py`
its entry script. `re` alone is the regular expressions of the standard library, and `import re` must go on meaning that
everywhere: a file `re.py` at the root of the repository would be imported in its place by every script started there (the
root is the first entry of `sys.path`), and a `re.py` anywhere under `certus/` would make each `re` in a review ambiguous.

So: nothing at the root, file or directory, and no module under `certus/`, bears the name of a standard library module.
The modules of the INDEX SPLINE window import with absolute paths only, which is what lets a function move from one of
them to another without its imports changing meaning.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tracked_sources() -> list[str]:
    done = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    return done.stdout.split("\n")


def test_nothing_at_the_root_bears_the_name_of_a_standard_library_module() -> None:
    tops = {path.split("/")[0].removesuffix(".py") for path in tracked_sources() if path}
    assert sorted(tops & sys.stdlib_module_names) == []


def test_no_module_of_certus_bears_the_name_of_a_standard_library_module() -> None:
    shadows = [
        path
        for path in tracked_sources()
        if path.startswith("certus/") and any(part.removesuffix(".py") in sys.stdlib_module_names for part in path.split("/")[1:])
    ]
    assert shadows == []


def test_the_family_named_re_is_always_written_with_its_prefix() -> None:
    names = {Path(path).stem.lower() for path in tracked_sources() if path}
    assert "re" not in names
    assert "certus_re" in names


def test_the_modules_of_the_index_spline_window_import_with_absolute_paths() -> None:
    relative = []
    for path in sorted((ROOT / "certus" / "ui").glob("certus_index_spline*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        relative += [f"{path.name}:{n.lineno}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]
    assert relative == []
