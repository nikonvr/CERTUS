"""A pure move of code passes the refactor guard, and nothing else does.

scripts/refactor_guard.py is the net under the refactoring of the INDEX SPLINE corridors: it photographs the window
classes (who defines each method, its bytecode, what each global it loads resolves to), the namespaces of the modules and
the attributes the tests replace, and it compares two photographs. A phase of the refactoring is accepted when the only
differences are the ones its manifest names.

A net that lets a change through is worse than no net: it is tried here on a small package written twice, before and
after. The move of a method and of the helper it calls, body untouched, must pass with its manifest; the same move must be
refused without the manifest, with a body that changed, with a global that resolves to something else in the new module,
with a name that left the old module, with an MRO in another order, and when a test still replaces, in the module the
code left, a global the moved code loads.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "rgpkg"


def _guard():
    spec = importlib.util.spec_from_file_location("certus_scripts_refactor_guard", ROOT / "scripts" / "refactor_guard.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _guard()

#: `_env` and `__pydantic_core_schema__` stand for what the real modules make anew at each import (a run identifier with the
#: time in it, a schema with the id() of its class): a photograph that held their value would never be the same twice.
HELPERS = """from __future__ import annotations

import time

LIMIT = 3
_env = {"run_id": time.perf_counter_ns()}


def scale(x):
    return x * LIMIT
"""

OLD_BEFORE = """from __future__ import annotations

import math

from rgpkg.helpers import scale

STEP = 2


def helper(x):
    return scale(x) + STEP


class OldMixin:
    def compute(self, x: int = 1) -> int:
        return helper(x) + math.floor(1.5)

    def other(self) -> str:
        return "other"
"""

WINDOW = """from __future__ import annotations

import time

from rgpkg.old import OldMixin


class Base:
    __pydantic_core_schema__ = {"ref": time.perf_counter_ns()}

    def base(self) -> int:
        return 0


class Window(OldMixin, Base):
    pass
"""

#: The move: `compute` and the helper it calls leave old.py for new.py, and old.py keeps every name it had.
NEW = """from __future__ import annotations

import math

from rgpkg.helpers import scale

STEP = 2


def helper(x):
    return scale(x) + STEP


class NewMixin:
    def compute(self, x: int = 1) -> int:
        return helper(x) + math.floor(1.5)
"""

OLD_AFTER = """from __future__ import annotations

import math

from rgpkg.helpers import scale
from rgpkg.new import STEP, NewMixin, helper


class OldMixin(NewMixin):
    def other(self) -> str:
        return "other"
"""

BEFORE = {"__init__.py": "", "helpers.py": HELPERS, "old.py": OLD_BEFORE, "win.py": WINDOW}
AFTER = {"__init__.py": "", "helpers.py": HELPERS, "old.py": OLD_AFTER, "new.py": NEW, "win.py": WINDOW}
MANIFEST = {
    "moved_methods": [{"name": "compute", "from": "rgpkg.old:OldMixin", "to": "rgpkg.new:NewMixin"}],
    "moved_objects": [{"from": "rgpkg.old:helper", "to": "rgpkg.new:helper"}],
    "new_classes": ["rgpkg.new:NewMixin"],
}


def _forget_the_package() -> None:
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]:
        del sys.modules[name]


@pytest.fixture
def snapshot_of(tmp_path, monkeypatch):
    """Writes one variant of the package in its own directory, imports it alone, and returns its snapshot."""

    def build(tag: str, files: dict[str, str], tests: dict[str, str] | None = None) -> dict:
        root = tmp_path / tag
        (root / PACKAGE).mkdir(parents=True)
        for name, text in files.items():
            (root / PACKAGE / name).write_text(text, encoding="utf-8")
        test_files = []
        for name, text in (tests or {}).items():
            path = root / "tests" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            test_files.append(path)
        _forget_the_package()
        monkeypatch.syspath_prepend(str(root))
        namespaces = [f"{PACKAGE}.{Path(name).stem}" for name in files if name != "__init__.py"]
        return guard.take_snapshot(root, [f"{PACKAGE}.win:Window"], namespaces, (), (PACKAGE,), test_files)

    yield build
    _forget_the_package()


def kinds(problems: list[str]) -> set[str]:
    return {problem.split("|")[0].strip() for problem in problems}


# =============================================================================
# What passes
# =============================================================================
def test_the_same_tree_photographed_twice_is_the_same(snapshot_of) -> None:
    problems, notes = guard.compare(snapshot_of("one", BEFORE), snapshot_of("two", BEFORE))
    assert problems == []
    assert notes == []


def test_a_pure_move_passes_with_its_manifest(snapshot_of) -> None:
    before, after = snapshot_of("before", BEFORE), snapshot_of("after", AFTER)
    assert before["classes"]["rgpkg.win:Window"]["attrs"]["compute"]["owner"] == "rgpkg.old:OldMixin"
    assert after["classes"]["rgpkg.win:Window"]["attrs"]["compute"]["owner"] == "rgpkg.new:NewMixin"

    problems, notes = guard.compare(before, after, [MANIFEST])

    assert problems == []
    assert "MODULE    | rgpkg.new | new" in notes


def test_a_body_that_changed_passes_only_when_the_manifest_names_it(snapshot_of) -> None:
    changed = {**AFTER, "new.py": NEW.replace("math.floor(1.5)", "math.floor(1.5) + 1")}
    before, after = snapshot_of("before", BEFORE), snapshot_of("after", changed)

    refused, _ = guard.compare(before, after, [MANIFEST])
    allowed, _ = guard.compare(before, after, [MANIFEST, {"changed_code": ["rgpkg.new:NewMixin.compute"]}])

    assert kinds(refused) == {"BYTECODE"}
    assert allowed == []


# =============================================================================
# What is refused
# =============================================================================
def test_the_same_move_is_refused_without_a_manifest(snapshot_of) -> None:
    problems, _ = guard.compare(snapshot_of("before", BEFORE), snapshot_of("after", AFTER))
    assert {"OWNER", "MOVED", "MRO", "CLASS", "NAME"} <= kinds(problems)


def test_a_global_that_resolves_to_something_else_in_the_new_module_is_refused(snapshot_of) -> None:
    other_step = {**AFTER, "new.py": NEW.replace("STEP = 2", "STEP = 5")}
    problems, _ = guard.compare(snapshot_of("before", BEFORE), snapshot_of("after", other_step), [MANIFEST])
    assert any(p.startswith("GLOBAL") and "`STEP` in rgpkg.new" in p for p in problems)


def test_a_name_that_left_the_old_module_is_refused(snapshot_of) -> None:
    no_math = {**AFTER, "old.py": OLD_AFTER.replace("import math\n\n", "")}
    problems, _ = guard.compare(snapshot_of("before", BEFORE), snapshot_of("after", no_math), [MANIFEST])
    assert [p for p in problems if p.startswith("NAME")] == [
        "NAME      | rgpkg.old:math | gone from the module (an import or a test may read it there)"
    ]


def test_an_mro_in_another_order_is_refused(snapshot_of) -> None:
    reordered = {**BEFORE, "win.py": WINDOW.replace("Window(OldMixin, Base)", "Window(Base, OldMixin)")}
    problems, _ = guard.compare(snapshot_of("before", BEFORE), snapshot_of("after", reordered))
    assert kinds(problems) == {"MRO"}


def test_a_method_that_another_class_now_wins_is_refused(snapshot_of) -> None:
    shadowed = {**BEFORE, "win.py": WINDOW.replace("    pass\n", "    def other(self) -> str:\n        return 'window'\n")}
    problems, _ = guard.compare(snapshot_of("before", BEFORE), snapshot_of("after", shadowed))
    assert "OWNER     | rgpkg.win:Window.other | resolved in rgpkg.win:Window, was in rgpkg.old:OldMixin" in problems


def test_a_seam_left_behind_by_the_move_is_refused_until_it_is_acknowledged(snapshot_of) -> None:
    seam = {"test_seam.py": 'def test_it(monkeypatch):\n    monkeypatch.setattr("rgpkg.old.scale", None)\n'}
    before, after = snapshot_of("before", BEFORE), snapshot_of("after", AFTER, seam)

    refused, _ = guard.compare(before, after, [MANIFEST])
    acknowledged = {"acknowledged_seams": {"rgpkg.old:scale": "the test calls nothing that moved"}}
    allowed, _ = guard.compare(before, after, [MANIFEST, acknowledged])

    assert refused == [
        "SEAM      | rgpkg.new:helper | loads `scale`, which tests/test_seam.py:2 replaces in rgpkg.old: "
        "the moved code no longer reads it there"
    ]
    assert allowed == []


def test_snapshots_of_two_python_versions_are_not_compared(snapshot_of) -> None:
    before = snapshot_of("before", BEFORE)
    other = {**before, "meta": {**before["meta"], "python": "0.0.0"}}
    with pytest.raises(guard.GuardError, match="two Python versions"):
        guard.compare(before, other)


# =============================================================================
# The seams, the command line, the list of windows
# =============================================================================
SEAMS = """import importlib
from unittest import mock
from unittest.mock import patch

import rgpkg.old as old_module
from rgpkg import helpers

target = importlib.import_module("rgpkg.win")


def test_forms(monkeypatch, mocker, local_object):
    monkeypatch.setattr("rgpkg.old.scale", None)
    monkeypatch.setattr(old_module, "STEP", 3)
    monkeypatch.setattr(helpers, "LIMIT", 4, raising=False)
    monkeypatch.setattr(target.Window, "base", None)
    with patch("rgpkg.helpers.scale"):
        pass
    with mock.patch.object(old_module, "helper"):
        pass
    mocker.patch("rgpkg.old.math")
    monkeypatch.setattr(local_object, "attribute", 1)
    monkeypatch.setattr("os.getcwd", None)
"""


def test_every_way_a_test_replaces_a_module_attribute_is_read(snapshot_of) -> None:
    snapshot = snapshot_of("seams", BEFORE, {"test_forms.py": SEAMS})
    assert [(module, name) for module, name, _file, _line in snapshot["seams"]] == [
        ("rgpkg.helpers", "LIMIT"),
        ("rgpkg.helpers", "scale"),
        ("rgpkg.old", "STEP"),
        ("rgpkg.old", "helper"),
        ("rgpkg.old", "math"),
        ("rgpkg.old", "scale"),
        ("rgpkg.win", "Window.base"),
    ]


def test_the_command_says_ok_or_diff_and_exits_accordingly(snapshot_of, tmp_path, capsys) -> None:
    files = {}
    for tag, tree in (("before", BEFORE), ("after", AFTER)):
        files[tag] = tmp_path / f"{tag}.json"
        files[tag].write_text(json.dumps(snapshot_of(tag, tree)), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")

    with_manifest = guard.main(["compare", str(files["before"]), str(files["after"]), "--manifest", str(manifest)])
    said_with = capsys.readouterr().out
    without = guard.main(["compare", str(files["before"]), str(files["after"])])
    said_without = capsys.readouterr().out
    unreadable = guard.main(["compare", str(files["before"]), str(tmp_path / "absent.json")])
    said_unreadable = capsys.readouterr().out

    assert with_manifest == 0
    assert said_with.splitlines()[-1] == "GUARD=OK"
    assert without == 1
    assert said_without.splitlines()[-1] == "GUARD=DIFF"
    assert unreadable == 2
    assert said_unreadable.startswith("GUARD=ERROR")


def test_the_guard_photographs_the_windows_the_attribute_sweep_reads() -> None:
    sweep = (ROOT / "tests" / "unit" / "test_self_attributes_are_defined.py").read_text(encoding="utf-8")
    listed = re.search(r"WINDOWS = \[(.*?)\]", sweep, re.DOTALL)
    assert listed is not None
    assert set(re.findall(r'"([\w.]+:\w+)"', listed.group(1))) == set(guard.WINDOWS)
