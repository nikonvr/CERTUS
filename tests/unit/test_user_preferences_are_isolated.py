"""Tests never rewrite the user's own preferences, and never drop reports into reports/.

`certus_export.json` and `certus_theme.json` live next to the application and are tracked
by git. Until 2026-09-26 the test suite wrote them: `save_export_config`,
`save_theme_config` and `save_font_config` are called by unit, integration and interface
tests -- one of which believed it redirected the file, but patched a function the
preference manager never calls. And the automatic export, on by default, made every full
optimisation run by a test drop a report into the user's `reports/` (one on 2026-09-26,
from the headless METAL SINGLE test).

`tests/conftest.py` now sets CERTUS_CONFIG_DIR to a private directory, with the automatic
export off, before anything imports certus; subprocesses inherit it through the
environment. These tests check that the redirection is in force, and that the mechanism
works in both directions -- active when set, the former path when unset.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from certus.core.certus_config import ConfigManager, get_resource_path

ROOT = Path(__file__).resolve().parents[2]
PROBE = "certus_isolation_probe.json"


@pytest.mark.unit
def test_the_suite_runs_on_private_preferences() -> None:
    private = os.environ.get("CERTUS_CONFIG_DIR", "")
    assert private, "tests/conftest.py must set CERTUS_CONFIG_DIR before importing certus"
    assert not Path(private).resolve().is_relative_to(ROOT), "the private copy must live outside the repository"


@pytest.mark.unit
def test_the_automatic_export_is_off_under_test() -> None:
    # Read the private file itself: the cached value may have been toggled by another test.
    assert ConfigManager("certus_export.json", True, "auto_export_enabled").reload() is False


@pytest.mark.unit
def test_a_saved_preference_lands_in_the_configured_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    manager = ConfigManager(PROBE, "light", "theme_mode")
    # Checked BEFORE writing: on code that ignores the variable this fails without creating
    # a file next to the application.
    assert manager._path() == tmp_path / PROBE
    assert manager.save("dark") is True
    assert (tmp_path / PROBE).exists()
    assert ConfigManager(PROBE, "light", "theme_mode").get() == "dark"


@pytest.mark.unit
def test_without_the_variable_the_path_is_the_former_one(monkeypatch) -> None:
    """Inert when unset (constraint C1): exactly the former path. Nothing is written here."""
    monkeypatch.delenv("CERTUS_CONFIG_DIR", raising=False)
    manager = ConfigManager(PROBE, "light", "theme_mode")
    assert manager._path() == Path(get_resource_path(PROBE))


@pytest.mark.unit
def test_a_pytest_session_leaves_no_private_directory_behind(tmp_path) -> None:
    """The private copy is removed when the session ends (2026-09-26: 65 left in one day).

    A real pytest session runs in a subprocess whose temporary folder is `tmp_path`, with
    CERTUS_CONFIG_DIR unset so that tests/conftest.py creates its own directory there.
    """
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "CERTUS_CONFIG_DIR"}
    for var in ("TMPDIR", "TEMP", "TMP"):
        env[var] = str(tmp_path)
    target = "tests/unit/test_user_preferences_are_isolated.py::test_the_suite_runs_on_private_preferences"
    run = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-cov", "-p", "no:cacheprovider"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert sorted(p.name for p in tmp_path.glob("certus_test_prefs_*")) == []
