"""Exercise the real tests/ui fixtures across test and module boundaries (D11).

A closed CERTUS window is only hidden. tests/ui used to leave every one behind, and each
made the next construction slower. The fixtures must destroy the main windows a test built
when the test ends, those a module-scoped fixture built when the module ends -- and nothing
else: a module window may cache a popup it built during one test and reuse it in the next,
and a loose widget keeps the lifetime its test gave it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_STATE = "state = {}\n"

_MODULE_A = '''
import pytest
from PyQt6 import sip
from PyQt6.QtWidgets import QMainWindow, QMenu, QWidget

from shared_state import state


@pytest.fixture(scope="module")
def window(qapp):
    win = QMainWindow()
    state["module_window"] = win
    yield win
    win.close()


def test_1_build_things(window):
    window.cached_menu = QMenu(window)  # a top-level popup, owned by the module window
    state["test_window"] = QMainWindow()  # built by the test itself
    state["loose"] = QWidget()  # not a main window: left alone


def test_2_only_the_test_window_is_gone(window):
    assert not sip.isdeleted(window.cached_menu), "a module window's popup died with a test"
    assert sip.isdeleted(state["test_window"]), "a window built by a test outlived it"
    assert not sip.isdeleted(state["loose"]), "a loose widget was destroyed by the fixture"
'''

_MODULE_B = '''
from PyQt6 import sip

from shared_state import state


def test_3_the_module_window_is_gone(qapp):
    assert sip.isdeleted(state["module_window"]), "a module-scoped window outlived its module"
'''

#: The fixtures tests/ui had before: a QApplication, and nothing that destroys a window.
_BARE_CONFTEST = '''
import sys

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv or ["certus-test"])
'''


@pytest.mark.parametrize("isolated", [False, True])
def test_ui_fixtures_destroy_windows_at_the_right_boundary(tmp_path, isolated):
    """The same scenario fails with the bare fixtures and passes with the real ones."""
    tests_dir = Path(__file__).parents[1]
    if isolated:
        for name, source in (
            ("conftest.py", tests_dir / "ui" / "conftest.py"),
            ("qt_lifecycle.py", tests_dir / "qt_lifecycle.py"),
        ):
            (tmp_path / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        (tmp_path / "conftest.py").write_text(_BARE_CONFTEST, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "shared_state.py").write_text(_STATE, encoding="utf-8")
    (tmp_path / "test_a_module.py").write_text(_MODULE_A, encoding="utf-8")
    (tmp_path / "test_b_next_module.py").write_text(_MODULE_B, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTEST_ADDOPTS="")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60,
    )
    output = run.stdout + run.stderr
    if isolated:
        assert run.returncode == 0, output
        assert "3 passed" in output, output
    else:
        assert run.returncode == 1, output
        assert "a window built by a test outlived it" in output, output
        assert "a module-scoped window outlived its module" in output, output
