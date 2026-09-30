"""A lazy module imports nothing until it is used, imports once, and finds a submodule by its path (certus_lazy_imports).

`certus/core/certus_lazy_imports.py` exists to keep start-up short: scipy, matplotlib and openpyxl are loaded when
something first touches them. It was covered at 52.3 % on 2026-09-30 and no test named it. A wrapper that imports
at construction, or at every access, would give the cost back without any error to show for it.
"""

from __future__ import annotations

import sys
import types

import pytest

from certus.core import certus_lazy_imports as lazy
from certus.core.certus_lazy_imports import LazyModule, is_available

NAME = "certus_test_heavy_module"


@pytest.fixture(autouse=True)
def _not_imported():
    sys.modules.pop(NAME, None)
    yield
    sys.modules.pop(NAME, None)


def _fake_import(module: types.ModuleType, calls: list):
    def import_func(name: str):
        calls.append(name)
        return module

    return import_func


def test_nothing_is_imported_before_the_first_access_and_only_once_after() -> None:
    calls: list[str] = []
    heavy = types.SimpleNamespace(answer=42, other="x")
    module = LazyModule(NAME, _fake_import(heavy, calls))

    assert calls == []  # building the wrapper costs nothing
    assert module.answer == 42
    assert module.other == "x"
    assert calls == [NAME]  # the second access reuses the first import


def test_a_submodule_is_reached_through_the_attributes_of_its_parents() -> None:
    calls: list[str] = []
    top = types.SimpleNamespace(sub=types.SimpleNamespace(deep=types.SimpleNamespace(value=7)))
    module = LazyModule("certus_test_heavy_module.sub.deep", _fake_import(top, calls))

    assert module.value == 7
    assert calls == ["certus_test_heavy_module.sub.deep"]


def test_a_module_already_imported_is_taken_from_sys_modules_without_importing() -> None:
    calls: list[str] = []
    sys.modules[NAME] = types.SimpleNamespace(marker="already here")

    assert LazyModule(NAME, _fake_import(types.SimpleNamespace(), calls)).marker == "already here"
    assert calls == []


def test_calling_and_listing_go_to_the_module() -> None:
    callable_module = LazyModule(NAME, _fake_import(lambda *args, **kwargs: (args, kwargs), []))

    assert callable_module(1, key="v") == ((1,), {"key": "v"})
    assert "answer" in dir(LazyModule(NAME, _fake_import(types.SimpleNamespace(answer=1), [])))


def test_availability_is_read_without_importing() -> None:
    assert is_available("numpy") is True
    assert is_available("certus_no_such_module_anywhere") is False
    assert is_available("") is False  # find_spec raises ValueError on an empty name: that is "not available"


def test_the_shortcuts_hand_back_the_same_wrapper_each_time_and_it_works() -> None:
    assert lazy.lazy_scipy() is lazy.lazy_scipy()
    assert lazy.lazy_scipy_optimize() is lazy.lazy_scipy_optimize()
    assert callable(lazy.lazy_scipy_optimize().minimize)  # the real scipy.optimize.minimize, loaded on this access
    assert lazy.check_scipy_available() is True
