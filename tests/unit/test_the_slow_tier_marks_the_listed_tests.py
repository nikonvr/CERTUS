"""The slow tests are listed and marked: `pytest -m "not slow"` is the fast tier (audit v2, plan S3.3).

Measured warm on 2026-10-01, `tests/unit` takes 15 min 39 and 156 of its test functions take 85 % of that; the 4 000 others take two minutes and a half. Those
functions are listed in `tests/slow_tests.json`, `tests/conftest.py` marks them `slow` at collection (`tests/slow_tier.py` does the work), and
`scripts/refresh_slow_tests.py` rewrites the list from a `--durations` log. What is pinned here:

    a function is slow whatever its parameters, a class-based test is found by its class, an absent or broken list marks nothing
    the script adds the phases of an instance, keeps the worst instance of a function, applies the threshold, and replaces only the folders it measured
    the committed list names tests that exist: a renamed test would fall out of it silently and slow the fast tier down
    in a real pytest, `-m slow` selects a listed test and `-m "not slow"` leaves it out
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import refresh_slow_tests as refresh  # noqa: E402
import slow_tier  # noqa: E402

LIST = ROOT / "tests" / "slow_tests.json"

LOG = """\
============================= slowest durations =============================
12.50s call     tests/unit/test_a.py::test_heavy[x1]
 3.00s setup    tests/unit/test_a.py::test_heavy[x1]
 0.50s teardown tests/unit/test_a.py::test_heavy[x1]
 2.00s call     tests/unit/test_a.py::test_heavy[x2]
 0.90s call     tests/unit/test_a.py::test_light
 0.40s setup    tests/unit/test_a.py::test_light
 1.10s call     tests/unit/test_a.py::TestC::test_in_class
 1.00s call     tests/unit/test_a.py::test_edge
 7.00s call     tests/ui/test_b.py::test_window
 not a duration line
"""


# --- the marking ---------------------------------------------------------------------------------------------------------------------------


def test_a_function_is_slow_whatever_its_parameters():
    slow = frozenset({"tests/unit/test_a.py::test_heavy"})
    assert slow_tier.is_slow("tests/unit/test_a.py::test_heavy[x1]", slow)
    assert slow_tier.is_slow("tests/unit/test_a.py::test_heavy[a-b-1.0]", slow)
    assert slow_tier.is_slow("tests/unit/test_a.py::test_heavy", slow)
    assert not slow_tier.is_slow("tests/unit/test_a.py::test_heavy_but_not_listed[x1]", slow)
    assert not slow_tier.is_slow("tests/unit/test_other.py::test_heavy", slow)


def test_a_test_of_a_class_is_found_by_its_class():
    slow = frozenset({"tests/unit/test_a.py::TestC::test_in_class"})
    assert slow_tier.is_slow("tests/unit/test_a.py::TestC::test_in_class[p]", slow)
    assert not slow_tier.is_slow("tests/unit/test_a.py::test_in_class", slow)


def test_only_the_listed_items_are_marked():
    class Item:
        def __init__(self, nodeid):
            self.nodeid, self.markers = nodeid, []

        def add_marker(self, marker):
            self.markers.append(marker)

    items = [Item("tests/unit/test_a.py::test_heavy[1]"), Item("tests/unit/test_a.py::test_light"), Item("tests/unit/test_a.py::test_heavy[2]")]
    marked = slow_tier.mark_slow(items, frozenset({"tests/unit/test_a.py::test_heavy"}), "SLOW")
    assert marked == 2
    assert [item.markers for item in items] == [["SLOW"], [], ["SLOW"]]


def test_an_absent_or_broken_list_marks_nothing(tmp_path):
    assert slow_tier.slow_test_ids(tmp_path / "absent.json") == frozenset()
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert slow_tier.slow_test_ids(broken) == frozenset()
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"tests": 3}), encoding="utf-8")
    assert slow_tier.slow_test_ids(wrong) == frozenset()


def test_the_list_is_read_from_the_tests_key(tmp_path):
    path = tmp_path / "list.json"
    path.write_text(json.dumps({"tests": {"tests/unit/test_a.py::test_x": 3.2}}), encoding="utf-8")
    assert slow_tier.slow_test_ids(path) == frozenset({"tests/unit/test_a.py::test_x"})


# --- the script that rewrites the list -----------------------------------------------------------------------------------------------------


def test_the_phases_of_an_instance_are_added():
    per_instance = refresh.phases_by_instance(LOG)
    assert per_instance["tests/unit/test_a.py::test_heavy[x1]"] == pytest.approx(16.0)
    assert per_instance["tests/unit/test_a.py::test_heavy[x2]"] == pytest.approx(2.0)
    assert per_instance["tests/unit/test_a.py::test_light"] == pytest.approx(1.3)
    assert len(per_instance) == 6  # the line that is not a duration is ignored


def test_a_function_takes_the_duration_of_its_worst_instance():
    worst = refresh.worst_by_function(refresh.phases_by_instance(LOG))
    assert worst["tests/unit/test_a.py::test_heavy"] == pytest.approx(16.0)


def test_the_threshold_keeps_exactly_the_functions_at_or_above_it():
    assert set(refresh.slow_functions(LOG, 1.0)) == {
        "tests/unit/test_a.py::test_heavy",
        "tests/unit/test_a.py::test_light",
        "tests/unit/test_a.py::TestC::test_in_class",
        "tests/unit/test_a.py::test_edge",  # exactly at the threshold: slow
        "tests/ui/test_b.py::test_window",
    }
    assert set(refresh.slow_functions(LOG, 2.0)) == {"tests/unit/test_a.py::test_heavy", "tests/ui/test_b.py::test_window"}
    assert refresh.slow_functions(LOG, 2.0)["tests/unit/test_a.py::test_heavy"] == 16.0


def test_the_folders_that_were_measured_are_replaced_and_the_others_kept():
    existing = {"tests/unit/test_a.py::test_gone": 9.0, "tests/ui/test_b.py::test_kept": 4.0, "tests/unit/test_c.py::test_kept_too": 2.0}
    measured = {"tests/unit": {"tests/unit/test_a.py::test_heavy": 16.0}}
    assert refresh.merge(existing, measured) == {
        "tests/ui/test_b.py::test_kept": 4.0,
        "tests/unit/test_a.py::test_heavy": 16.0,
    }


def test_a_folder_name_is_not_a_prefix_of_its_neighbour():
    existing = {"tests/unit_extra/test_a.py::test_x": 3.0}
    assert refresh.merge(existing, {"tests/unit": {}}) == existing


def test_the_script_writes_the_list_it_computed(tmp_path, capsys):
    log = tmp_path / "unit.out"
    log.write_text(LOG, encoding="utf-8")
    target = tmp_path / "slow.json"
    assert refresh.main(["--suite", "tests/unit", str(log), "--liste", str(target), "--write"]) == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert set(written["tests"]) == {
        "tests/unit/test_a.py::test_heavy",
        "tests/unit/test_a.py::test_light",
        "tests/unit/test_a.py::TestC::test_in_class",
        "tests/unit/test_a.py::test_edge",
    }
    assert written["seuil_secondes"] == 1.0
    assert "4 nouvelles" in capsys.readouterr().out


def test_without_write_the_list_is_only_compared(tmp_path):
    log = tmp_path / "unit.out"
    log.write_text(LOG, encoding="utf-8")
    target = tmp_path / "slow.json"
    assert refresh.main(["--suite", "tests/unit", str(log), "--liste", str(target)]) == 0
    assert not target.exists()


def test_a_log_without_durations_is_refused(tmp_path, capsys):
    log = tmp_path / "empty.out"
    log.write_text("== 10 passed in 3 s ==\n", encoding="utf-8")
    assert refresh.main(["--suite", "tests/unit", str(log), "--liste", str(tmp_path / "slow.json")]) == 2
    assert "aucune duree" in capsys.readouterr().err


# --- the committed list --------------------------------------------------------------------------------------------------------------------


def _defined_in(path: Path, qualified: str) -> bool:
    """`test_y` or `TestC::test_y`: is it defined in the file?"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    parts = qualified.split("::")
    scope: list[ast.stmt] = tree.body
    for index, name in enumerate(parts):
        found = next((n for n in scope if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and n.name == name), None)
        if found is None:
            return False
        if index < len(parts) - 1:
            scope = found.body if isinstance(found, ast.ClassDef) else []
    return True


def test_the_committed_list_names_tests_that_exist():
    data = json.loads(LIST.read_text(encoding="utf-8"))
    tests = data["tests"]
    assert len(tests) >= 100  # 156 in tests/unit alone when it was measured; a list that collapses is a list that was lost
    missing = []
    for node, seconds in tests.items():
        file, _, qualified = node.partition("::")
        assert "\\" not in node, node
        assert file.startswith("tests/"), node
        assert seconds >= data["seuil_secondes"], node
        path = ROOT / file
        if not path.is_file() or not _defined_in(path, qualified):
            missing.append(node)
    assert not missing, f"{len(missing)} listed test(s) no longer exist, so they are fast now or renamed: {missing[:5]}"


def test_the_list_is_sorted_so_that_a_refresh_is_a_small_diff():
    tests = list(json.loads(LIST.read_text(encoding="utf-8"))["tests"])
    assert tests == sorted(tests)


# --- in a real pytest ----------------------------------------------------------------------------------------------------------------------


def _collect(*args: str) -> str:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov", "-p", "no:cacheprovider", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    assert done.returncode in (0, 5), done.stdout[-800:] + done.stderr[-800:]  # 5: nothing selected
    return done.stdout


def test_slow_selects_a_listed_test_and_not_slow_leaves_it_out():
    tests = json.loads(LIST.read_text(encoding="utf-8"))["tests"]
    node = next(n for n in tests if n.startswith("tests/unit/") and "::" in n and n.count("::") == 1)
    file, _, name = node.partition("::")
    assert name in _collect("-m", "slow", file)
    assert name not in _collect("-m", "not slow", file)
