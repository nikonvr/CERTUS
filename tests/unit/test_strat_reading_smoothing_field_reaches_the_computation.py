"""D102 -- the "Reading smoothing (k)" field of the STRAT window reaches the computation.

`collect_params` read `reading_smoothing_window` from the loaded file only, while the window showed the field and the
status banner read the field: typing 8 there made the banner list "lissage de lecture" as active and the run use the
file's value -- 1 when the file has none. The field now comes first, and the file when the window has no such field.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

ROOT = Path(__file__).resolve().parents[2]
#: The reference configuration. It is only READ here: every variant is a copy in tmp_path.
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
KEY = "reading_smoothing_window"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT reading smoothing", main_windows_only=True)


@pytest.fixture
def strat_window(qapp):
    from certus.ui.certus_strat_ui import CertusSTRATApp

    return CertusSTRATApp()


def _active(window) -> str:
    """The "ACTIF" part of the status banner: the error sources it says the run will use."""
    return next((part for part in window.machine_status.text().split("|") if "ACTIF" in part), "")


def test_one_reading_by_default(strat_window):
    assert strat_window.collect_params()[KEY] == 1
    assert "lissage de lecture" not in _active(strat_window)


def test_what_is_typed_reaches_the_computation(strat_window):
    strat_window.widgets[KEY].setText("8")
    assert strat_window.collect_params()[KEY] == 8


def test_the_banner_and_the_run_agree(strat_window):
    strat_window.widgets[KEY].setText("8")
    assert "lissage de lecture" in _active(strat_window)
    assert strat_window.collect_params()[KEY] == 8


def test_a_loaded_file_sets_the_field_and_the_run(strat_window, tmp_path):
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg[KEY] = 8
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    assert strat_window.load_configuration(str(path))
    assert strat_window.widgets[KEY].text() == "8"
    assert strat_window.collect_params()[KEY] == 8
