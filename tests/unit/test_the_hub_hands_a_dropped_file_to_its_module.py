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
    from PyQt6.QtCore import QProcess
    from PyQt6.QtWidgets import QMessageBox

    import CERTUS_HUB
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


@pytest.fixture
def told(monkeypatch) -> list[str]:
    """What the hub tells the operator about a drop (the toast), recorded instead of shown."""
    import CERTUS_HUB

    messages: list[str] = []
    monkeypatch.setattr(CERTUS_HUB, "show_toast", lambda _parent, text, *_a, **_k: messages.append(text))
    return messages


@pytest.fixture
def chooser(monkeypatch):
    """The file chooser of a multi-file drop: records what it offered and answers ``answer[0]`` (None declines)."""
    from PyQt6.QtWidgets import QInputDialog

    offered: list[list[str]] = []
    answer: list[str | None] = [None]

    def get_item(_parent, _title, _label, items, *_a, **_k):
        offered.append(list(items))
        return (answer[0] or "", answer[0] is not None)

    monkeypatch.setattr(QInputDialog, "getItem", get_item)
    return offered, answer


# UX audit 2026-11-18, item 2: the hub took the first of several dropped files and silently set the others aside.


def test_one_dropped_file_is_opened_and_said_so(hub, started, told, tmp_path) -> None:
    hub.dropEvent(Drop(tmp_path / "my_design.json"))

    assert len(started) == 1
    [message] = told
    assert "my_design.json" in message
    assert "set aside" not in message


def test_of_two_dropped_files_the_operator_chooses_which_opens(hub, started, told, chooser, tmp_path) -> None:
    offered, answer = chooser
    first, second = tmp_path / "first_design.json", tmp_path / "second_design.json"
    answer[0] = "second_design.json"

    hub.dropEvent(Drop(first, second))

    assert offered == [["first_design.json", "second_design.json"]]
    [(_program, args)] = started
    assert Path(args[1]) == second
    [message] = told
    assert "1 of 2 files" in message
    assert "set aside: first_design.json" in message


def test_declining_the_choice_opens_nothing_and_says_so(hub, started, told, chooser, tmp_path) -> None:
    hub.dropEvent(Drop(tmp_path / "first_design.json", tmp_path / "second_design.json"))

    assert started == []
    [message] = told
    assert "Nothing opened" in message


def test_a_file_the_suite_cannot_read_is_named_as_set_aside(hub, started, told, tmp_path) -> None:
    hub.dropEvent(Drop(tmp_path / "my_design.json", tmp_path / "photo.png"))

    [(_program, args)] = started
    assert Path(args[1]) == tmp_path / "my_design.json"
    [message] = told
    assert "set aside: photo.png (not a file CERTUS reads)" in message


def test_a_card_starts_its_module_with_nothing_to_open(hub, started) -> None:
    hub.launch_module("CERTUS_DESIGN.py")

    assert started == [(sys.executable, [str(ROOT / "CERTUS_DESIGN.py")])]
