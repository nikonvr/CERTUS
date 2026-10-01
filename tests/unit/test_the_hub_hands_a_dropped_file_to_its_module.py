"""A file dropped on the hub reaches the module that opens it.

`dropEvent` chose the module able to read the file and started it with `launch_module(script)`: the module
opened EMPTY, and the file the user had dropped was never named to it, in the sources as in the frozen suite
(found while repairing the frozen hub, REL-01). The modules read `sys.argv[1]` as the file to open ("Load file
from CLI if provided"), so the file goes there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = Path(__file__).resolve().parents[2]


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
    """Every `QProcess.start` is recorded and none is run: dropping a file on a real hub spawns a process.

    A dialog would block the suite for good (nobody answers it), so here any is a failure.
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
        # `sys.frozen` is faked does not outlive it.
        for cached in {get_resource_path, CERTUS_HUB.get_resource_path}:
            cached.cache_clear()

    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(QProcess, "start", lambda self, *_a: calls.append((self.program(), self.arguments())))
    monkeypatch.setattr(QMessageBox, "critical", no_dialog)
    monkeypatch.setattr(QMessageBox, "warning", no_dialog)
    forget_resource_folders()
    yield calls
    forget_resource_folders()


class Drop:
    """The part of a `QDropEvent` that the hub reads: the URLs of the files, and the acceptance."""

    def __init__(self, *paths: Path):
        from PyQt6.QtCore import QMimeData, QUrl

        self._mime = QMimeData()
        self._mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        self.accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True


@pytest.mark.parametrize(
    ("name", "script"),
    [
        ("my_design.json", "CERTUS_DESIGN.py"),
        ("strat_config.json", "CERTUS_STRAT.py"),
        ("index_measurement.csv", "CERTUS_INDEX.py"),
        ("spectrum.xlsx", "CERTUS_INDEX.py"),
    ],
)
def test_the_dropped_file_is_the_command_line_of_the_module_that_reads_it(hub, started, tmp_path, name, script) -> None:
    dropped = tmp_path / name
    event = Drop(dropped)

    hub.dropEvent(event)

    assert event.accepted
    [(program, args)] = started
    assert program == sys.executable
    assert args[0] == str(ROOT / script)
    assert len(args) == 2
    assert Path(args[1]) == dropped


def test_in_the_frozen_suite_the_file_follows_the_name_of_the_module(hub, started, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    dropped = tmp_path / "strat_config.json"

    hub.dropEvent(Drop(dropped))

    [(program, args)] = started
    assert program == sys.executable
    assert args[:2] == ["--run-module", "CERTUS_STRAT"]
    assert len(args) == 3
    assert Path(args[2]) == dropped


def test_only_the_first_of_several_dropped_files_is_opened(hub, started, tmp_path) -> None:
    first, second = tmp_path / "first_design.json", tmp_path / "second_design.json"

    hub.dropEvent(Drop(first, second))

    [(_program, args)] = started
    assert len(args) == 2
    assert Path(args[1]) == first


def test_a_card_starts_its_module_with_nothing_to_open(hub, started) -> None:
    hub.launch_module("CERTUS_DESIGN.py")

    assert started == [(sys.executable, [str(ROOT / "CERTUS_DESIGN.py")])]
