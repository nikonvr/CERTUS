"""FIELD, INDEX SPLINE and RE open the file the hub hands them (audit UX A04, ETAT D81).

The hub starts a module with the file it chose on the command line ("`launch_module(script, files=[path])`", and the
comment of `dropEvent`: "The module opens the file it is given; without it a drop only started an empty window").
Measured 2026-10-02, DESIGN, STRAT, INDEX and the two METAL read `sys.argv[1]` in their `main`, and FIELD, INDEX SPLINE
and RE did not: a configuration the hub had just routed to FIELD opened an empty window.

`open_command_line_file` opens that file as a drop on the window would, so that the answer is the same and says whether
it worked; the three `main` functions call it once their window is up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import certus.ui.certus_ui_utils as ui_utils

ROOT = Path(__file__).resolve().parents[2]


class _Window:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def _handle_dropped_file(self, path: str) -> None:
        self.opened.append(path)


@pytest.fixture(autouse=True)
def immediate_timer(monkeypatch):
    """`QTimer.singleShot(100, fn)` runs `fn` at once: the test has no event loop to wait for."""
    monkeypatch.setattr(ui_utils.QTimer, "singleShot", staticmethod(lambda _ms, fn: fn()))


def test_the_file_named_on_the_command_line_is_opened_as_a_drop(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    window = _Window()

    ui_utils.open_command_line_file(window, ["CERTUS_FIELD.py", str(config)])

    assert window.opened == [str(config)]


@pytest.mark.parametrize(
    "argv",
    [["CERTUS_FIELD.py"], ["CERTUS_FIELD.py", "--no-splash"], ["CERTUS_FIELD.py", "does_not_exist.json"]],
    ids=["no-argument", "a-flag", "a-file-that-is-not-there"],
)
def test_nothing_is_opened_when_the_command_line_names_no_file(argv) -> None:
    window = _Window()

    ui_utils.open_command_line_file(window, argv)

    assert window.opened == []


@pytest.mark.parametrize("script", ["CERTUS_FIELD.py", "CERTUS_INDEX_SPLINE.py", "CERTUS_RE.py"])
def test_the_main_of_each_of_the_three_modules_opens_its_file(script) -> None:
    source = (ROOT / script).read_text(encoding="utf-8-sig")
    assert "open_command_line_file(" in source, f"{script} ignores the file the hub gives it"
