"""A helper named like a verification must verify: a `check()` that only counts cannot fail a test.

Measured 2026-09-30: four test files (`test_gradient_vs_fd`, `test_needle_cached`, `test_tmm_coherence`,
`test_tmm_inline`) each had a `check(name, got, ref)` that added one to PASS or FAIL and printed a tick or a
cross, and never asserted. It was written for a script (`sys.exit(FAIL)` at the bottom of the file) and run by
pytest, where nothing reads FAIL: the 25 tests that call it, among them the finite-difference checks of the
gradients and the TMM coherence checks, could not fail. Once `check` asserts, a planted error of 0.1 % in R
makes 7 of those 30 tests fail.

This guard reads every helper of `tests/` whose name says it verifies (`assert*`, `check*`, `verify*`, `expect*`,
`validate*`, with or without a leading underscore) and refuses one whose body neither asserts nor hands the work
to a local helper that does.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

VERIFIER = re.compile(r"^_?(assert|check|verify|expect|validate)\w*$")

#: Named like a check, and not one: a Qt timer callback that decides when a headless run has gone idle.
NOT_A_CHECK = {"tests/headless/test_design.py::check_idle"}


def _contains_an_assertion(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Assert | ast.Raise):
            return True
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in {"fail", "raises", "warns", "skip", "xfail", "exit"} or name.startswith(("assert", "_assert")):
                return True
    return False


def helpers_that_verify_nothing(source: str) -> list[str]:
    """Names of the verification-like helpers of `source` that neither assert nor delegate to one that does."""
    functions = {
        node.name: node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    verifiers = {name: node for name, node in functions.items() if VERIFIER.match(name)}
    empty = []
    for name, node in verifiers.items():
        if _contains_an_assertion(node):
            continue
        callees = {
            call.func.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id != name
        }
        if any(callee in functions and _contains_an_assertion(functions[callee]) for callee in callees):
            continue
        empty.append(name)
    return empty


def test_the_scanner_tells_a_helper_that_counts_from_one_that_contains_an_assertion() -> None:
    """Negative control: with a scanner that finds nothing, the guard below would pass for nothing."""
    counts_only = (
        "PASS = FAIL = 0\n"
        "def check(name, got, ref):\n"
        "    global PASS, FAIL\n"
        "    ok = abs(got - ref) < 1e-6\n"
        "    if ok:\n        PASS += 1\n    else:\n        FAIL += 1\n"
        "    print(name, ok)\n"
    )
    asserts = counts_only + "    assert ok, name\n"
    delegates = asserts + "def check_all(x):\n    check('x', x, 1.0)\n"
    raises = "def verify(x):\n    if x < 0:\n        raise ValueError(x)\n"

    assert helpers_that_verify_nothing(counts_only) == ["check"]
    assert helpers_that_verify_nothing(asserts) == []
    assert helpers_that_verify_nothing(delegates) == []  # check_all hands the work to `check`, which asserts
    assert helpers_that_verify_nothing(raises) == []
    assert helpers_that_verify_nothing("def helper():\n    pass\n") == []  # not named like a check


def test_no_helper_named_like_a_check_verifies_nothing() -> None:
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        offenders += [
            f"{relative}::{name}"
            for name in helpers_that_verify_nothing(path.read_text(encoding="utf-8-sig"))
            if f"{relative}::{name}" not in NOT_A_CHECK
        ]

    assert not offenders, (
        f"Helpers named like a check whose body asserts nothing: {offenders}. Under pytest nothing reads the PASS/FAIL "
        "counters they increment, so the tests that call them cannot fail: add `assert ok, ...`."
    )
