"""No test run writes the user's registry (R11).

`QSettings(organization, application)` is HKCU\\Software\\<organization> on Windows. Every window
closed by a test used to save its geometry, splitters and table headers there, and a test of the
INDEX SPLINE fit options wrote them for real: the user's own layout and defaults were rewritten
by each run. certus_settings sends them to an INI file under CERTUS_CONFIG_DIR, which the test
suite sets; unset, it builds exactly the QSettings of before.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FACTORY = "certus/utils/certus_qsettings.py"


def test_under_config_dir_the_settings_are_an_ini_file_there(qapp, tmp_path, monkeypatch) -> None:
    from PyQt6.QtCore import QSettings

    from certus.utils.certus_qsettings import certus_settings

    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    s = certus_settings("CERTUS", "ProbeR11")
    assert s.format() == QSettings.Format.IniFormat
    s.setValue("probe/value", 42)
    s.sync()
    written = Path(s.fileName())
    assert written.is_relative_to(tmp_path), s.fileName()
    assert written.is_file(), s.fileName()


def test_without_config_dir_it_is_the_native_settings_of_before(qapp, monkeypatch) -> None:
    """Nothing is written here: the objects are only compared."""
    from PyQt6.QtCore import QSettings

    from certus.utils.certus_qsettings import certus_settings

    monkeypatch.delenv("CERTUS_CONFIG_DIR", raising=False)
    ours, before = certus_settings("CERTUS", "ProbeR11"), QSettings("CERTUS", "ProbeR11")
    assert ours.format() == before.format() == QSettings.Format.NativeFormat
    assert ours.fileName() == before.fileName()
    assert (ours.organizationName(), ours.applicationName()) == ("CERTUS", "ProbeR11")


def test_the_test_session_itself_is_redirected(qapp) -> None:
    """tests/conftest.py sets CERTUS_CONFIG_DIR for the whole session and its subprocesses."""
    import os

    from certus.utils.certus_qsettings import certus_settings

    assert os.environ.get("CERTUS_CONFIG_DIR"), "the test session no longer isolates preferences"
    assert Path(certus_settings("CERTUS", "ProbeR11").fileName()).is_relative_to(os.environ["CERTUS_CONFIG_DIR"])


def test_each_process_starts_from_its_own_settings(qapp, tmp_path, monkeypatch) -> None:
    """A worker subprocess must not restore what an earlier test saved.

    With one file shared by the whole session, 10 UI tests failed in the full suite and passed
    alone: windows measured in workers restored the geometry earlier windows had saved.
    """
    import os
    import sys

    from certus.utils.certus_qsettings import certus_settings

    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    mine = certus_settings("CERTUS", "ProbeR11")
    mine.setValue("window/geometry", "saved-by-the-parent")
    mine.sync()
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "from certus.utils.certus_qsettings import certus_settings\n"
        "print(certus_settings('CERTUS', 'ProbeR11').value('window/geometry'))\n"
    )
    child = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                           env=dict(os.environ), timeout=120)
    assert child.stdout.strip() == "None", child.stdout + child.stderr
    assert certus_settings("CERTUS", "ProbeR11").value("window/geometry") == "saved-by-the-parent"


def _direct_constructions() -> list[str]:
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    found = []
    for rel in out.split():
        if rel.startswith(("tests/", "scripts/", "tools/", "docs/")) or rel == FACTORY:
            continue
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
        found += [f"{rel}:{n.lineno}" for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "QSettings"]
    return found


@pytest.mark.unit
def test_no_production_code_builds_its_own_qsettings() -> None:
    """A direct QSettings(...) would escape CERTUS_CONFIG_DIR and write the registry again."""
    direct = _direct_constructions()
    assert not direct, "use certus.utils.certus_qsettings.certus_settings instead:\n  " + "\n  ".join(direct)
