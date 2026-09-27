"""Hooks shared by the unit tests."""

from __future__ import annotations

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A failed counted check fails its test.

    Four physics suites are also scripts (`test_tmm_coherence`, `test_gradient_vs_fd`,
    `test_tmm_inline`, `test_needle_cached`): their `check()` helpers count failures in a
    module-level `FAIL` and print `[FAIL]`, and only their `main()` exits non-zero. Under
    pytest nothing read that counter: with every check forced to fail, the four files
    still reported 30 passed.
    """
    module = getattr(item, "module", None)
    before = getattr(module, "FAIL", None)
    result = yield
    if isinstance(before, int):
        failed = module.FAIL - before
        assert failed == 0, f"{failed} counted check(s) failed in this test: see its [FAIL] lines"
    return result
