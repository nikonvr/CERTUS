"""A selector comparison counts as proof only when the full suite sees the fault and the selection catches it."""

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture
def probe(monkeypatch):
    before = set(sys.modules)
    monkeypatch.syspath_prepend(str(SCRIPTS))  # the script imports mutation_pilot without the scripts. prefix
    try:
        yield importlib.import_module("probe_test_selector")
    finally:
        for name in set(sys.modules) - before:
            del sys.modules[name]


GREEN = {"green": True, "failed": []}


def red(*failed):
    return {"green": False, "failed": list(failed)}


def test_two_green_suites_prove_nothing(probe):
    assert probe.classify("", ["tests/unit/test_a.py"], GREEN, GREEN) == ("UNDETECTED", [])


@pytest.mark.parametrize(
    ("reason", "selected_files", "selected", "full", "expected"),
    [
        ("", ["tests/unit/test_a.py"], red("tests/unit/test_a.py::t"), GREEN, ("DIVERGENT", [])),
        ("", ["tests/unit/test_a.py"], GREEN, red("tests/unit/test_a.py::t"), ("ESCAPED", [])),
        ("", ["tests/unit/test_a.py"], red("tests/unit/test_a.py::t"),
         red("tests/unit/test_a.py::t", "tests/ui/test_b.py::u[1]"), ("ESCAPED", ["tests/ui/test_b.py::u[1]"])),
        ("", ["tests/unit/test_a.py"], red("tests/unit/test_a.py::t"), red("tests/unit/test_a.py::t"), ("OK", [])),
        ("conftest.py changed", [], red("tests/ui/test_b.py::u"), red("tests/ui/test_b.py::u"), ("OK", [])),
    ],
)
def test_only_a_caught_fault_is_ok(probe, reason, selected_files, selected, full, expected):
    assert probe.classify(reason, selected_files, selected, full) == expected
