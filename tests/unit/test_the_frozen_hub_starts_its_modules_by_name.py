"""The frozen hub starts a module through its own executable, by name.

`launch_module` ran `<folder>/CERTUS_DESIGN.exe` in a frozen build: an executable that
`certus_hub.spec` never produced (it froze `CERTUS_HUB.py` alone, as one file), so from the frozen
hub none of the ten cards could start a module. In the frozen suite `sys.executable` is the one
executable, and a module is started as `CERTUS_HUB.exe --run-module NAME [file]`; the entry
(`certus.core.certus_frozen_entry`) runs it as `python NAME.py [file]` would. The modules read
`sys.argv[1]` as the file to open, so the flag and the name must not stay in `sys.argv`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# The hub: what it starts
# =============================================================================


@pytest.fixture
def hub(qapp):
    from CERTUS_HUB import CertusHub

    window = CertusHub()
    try:
        yield window
    finally:
        window.active_processes.clear()
        window.close()


@pytest.fixture
def started(monkeypatch):
    """Every `QProcess.start` is recorded and none is run: activating a card of a real hub spawns a process.

    A dialog would block the suite for good (nobody answers it): the hub reports a script it cannot
    find with `QMessageBox.critical`, so here that is a failure.
    """
    import CERTUS_HUB
    from PyQt6.QtCore import QProcess
    from PyQt6.QtWidgets import QMessageBox

    from certus.core.certus_core import get_resource_path

    def no_dialog(_parent, title, text, *_a, **_k):
        pytest.fail(f"the hub opened a dialog: {title}: {text}")

    def forget_resource_folders():
        # `get_resource_path` is cached, and the hub holds the function it imported: a test that reloaded
        # `certus_core` leaves the hub with another one. Both are cleared, so that the folder read while
        # `sys.frozen` is faked does not outlive it, nor a folder left by an earlier test.
        for cached in {get_resource_path, CERTUS_HUB.get_resource_path}:
            cached.cache_clear()

    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(QProcess, "start", lambda self, *_a: calls.append((self.program(), self.arguments())))
    monkeypatch.setattr(QMessageBox, "critical", no_dialog)
    monkeypatch.setattr(QMessageBox, "warning", no_dialog)
    forget_resource_folders()
    yield calls
    forget_resource_folders()


def test_the_frozen_hub_starts_a_module_through_its_own_executable(hub, started, monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    hub.launch_module("CERTUS_DESIGN.py")

    assert started == [(sys.executable, ["--run-module", "CERTUS_DESIGN"])]


def test_from_the_sources_a_module_is_still_a_script_run_by_the_interpreter(hub, started) -> None:
    hub.launch_module("CERTUS_DESIGN.py")

    assert started == [(sys.executable, [str(ROOT / "CERTUS_DESIGN.py")])]


# =============================================================================
# The entry: what it runs
# =============================================================================


@pytest.fixture
def entry():
    from certus.core import certus_frozen_entry

    return certus_frozen_entry


@pytest.fixture
def runs(entry, monkeypatch):
    """`runpy.run_module` replaced by a recorder of what it is asked, and of the `sys.argv` it would see."""
    recorded: list[dict] = []
    monkeypatch.setattr(sys, "argv", list(sys.argv))  # `main` assigns `sys.argv`: put back at the end

    def record(name, *, run_name=None, alter_sys=False):
        recorded.append({"module": name, "run_name": run_name, "alter_sys": alter_sys, "argv": list(sys.argv)})
        return {}

    monkeypatch.setattr(entry.runpy, "run_module", record)
    return recorded


def test_a_named_module_runs_as_its_own_main_with_only_its_arguments(entry, runs) -> None:
    assert entry.main(["--run-module", "CERTUS_FIELD", "config.json"]) == 0

    # `CERTUS_DESIGN.py config.json`: the module reads sys.argv[1] as the file to open.
    assert runs == [
        {"module": "CERTUS_FIELD", "run_name": "__main__", "alter_sys": True, "argv": ["CERTUS_FIELD.py", "config.json"]}
    ]


def test_without_the_flag_the_hub_runs_and_its_arguments_are_left_alone(entry, runs, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["CERTUS_HUB.exe"])

    assert entry.main() == 0

    assert runs == [{"module": "CERTUS_HUB", "run_name": "__main__", "alter_sys": True, "argv": ["CERTUS_HUB.exe"]}]


@pytest.mark.parametrize(
    "argv",
    [["--run-module"], ["--run-module", ""], ["--run-module", "os"], ["--run-module", "certus.core.certus_core"]],
)
def test_only_a_module_of_the_hub_can_be_named(entry, runs, capsys, argv) -> None:
    assert entry.main(argv) == entry.USAGE_ERROR

    assert runs == []
    assert "is not a CERTUS module" in capsys.readouterr().err


def test_every_card_of_the_hub_names_a_module_that_can_be_started(entry, runs) -> None:
    from certus.core.certus_hub_config import HUB_APP_CATALOG

    names = [Path(item["script"]).stem for item in HUB_APP_CATALOG]

    assert list(entry.catalog_modules()) == names
    for name in names:
        assert (ROOT / f"{name}.py").is_file(), f"the hub offers {name}, which is not a script of the repository"
        assert entry.main(["--run-module", name]) == 0
    assert [run["module"] for run in runs] == names


# =============================================================================
# The entry: what it leaves when a module cannot start
# =============================================================================


def _module_that_cannot_start(entry, monkeypatch, exception):
    def fails(name, **_kwargs):
        raise exception

    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(entry.runpy, "run_module", fails)


def test_a_frozen_module_that_cannot_start_leaves_its_exception_in_a_log(entry, monkeypatch, tmp_path) -> None:
    # A windowed executable has no console: the bootloader's "Unhandled exception in script" box
    # does not carry the exception, and STRAT ended in it for a month of `scripts/` not bundled.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "CERTUS_HUB.exe"))
    _module_that_cannot_start(entry, monkeypatch, ModuleNotFoundError("No module named 'orchestre_multigraine'"))

    with pytest.raises(ModuleNotFoundError):  # still raised: the box the user knows stays
        entry.main(["--run-module", "CERTUS_STRAT"])

    log = (tmp_path / entry.STARTUP_LOG).read_text(encoding="utf-8")
    assert "CERTUS_STRAT" in log
    assert "No module named 'orchestre_multigraine'" in log


def test_from_the_sources_nothing_is_written(entry, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _module_that_cannot_start(entry, monkeypatch, ModuleNotFoundError("boom"))

    with pytest.raises(ModuleNotFoundError):
        entry.main(["--run-module", "CERTUS_STRAT"])

    assert entry.record_startup_failure("CERTUS_STRAT") is None
    assert list(tmp_path.iterdir()) == []


def test_a_module_that_exits_is_not_a_failure(entry, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "CERTUS_HUB.exe"))
    _module_that_cannot_start(entry, monkeypatch, SystemExit(0))  # `sys.exit(app.exec())` at the end of a session

    with pytest.raises(SystemExit):
        entry.main(["--run-module", "CERTUS_STRAT"])

    assert list(tmp_path.iterdir()) == []


def test_a_windowed_executable_gets_standard_streams(entry, monkeypatch) -> None:
    # `sys.stdout` and `sys.stderr` are None in a windowed executable; `scripts/orchestre_multigraine.py`
    # reconfigures them when it is imported, which the STRAT tab does at start-up.
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    seen = []
    monkeypatch.setattr(entry.runpy, "run_module", lambda name, **_kwargs: seen.append((sys.stdout, sys.stderr)))

    entry.main(["--run-module", "CERTUS_STRAT"])

    [(out, err)] = seen
    try:
        for stream in (out, err):
            stream.reconfigure(encoding="utf-8", errors="replace")
            print("written and dropped", file=stream)
    finally:
        out.close()
        err.close()


def test_a_console_is_left_alone(entry, monkeypatch) -> None:
    out, err = sys.stdout, sys.stderr

    entry.ensure_standard_streams()

    assert (sys.stdout, sys.stderr) == (out, err)
