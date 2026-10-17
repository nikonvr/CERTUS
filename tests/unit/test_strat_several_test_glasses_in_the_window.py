"""Several test glasses from the window: the layers where a NEW test glass enters (`witness_reset_layers`).

The kernel has taken the setting since 2026-08-15 (`010a2c4a`), but the window did not show it and `collect_params`
did not route it: a configuration file could not set it either. These tests hold the window's side: a field, empty by
default (one test glass, the former path), that reaches the computation as typed, survives a save and a load, refuses
what cannot be applied, empties when a file carries no plan of its own, and shows in the status banner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

ROOT = Path(__file__).resolve().parents[2]
#: The reference configuration (48 layers; the window opens on a 46-layer example). It is only READ here.
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
KEY = "witness_reset_layers"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT test glasses", main_windows_only=True)


@pytest.fixture
def strat_window(qapp):
    from certus.ui.certus_strat_ui import CertusSTRATApp

    return CertusSTRATApp()


def _load(window, tmp_path: Path, **values) -> None:
    """Load the reference configuration with `values` written over it, through a file, as a user does."""
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg.update(values)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    assert window.load_configuration(str(path))


def _witness_problems(window) -> list[str]:
    label = window._field_label(KEY)
    return [p for p in window.input_problems(window.collect_params()) if p.startswith(label)]


def test_one_test_glass_by_default(strat_window):
    assert strat_window.widgets[KEY].text() == ""
    assert strat_window.collect_params()[KEY] == []
    assert "TEMOINS 1" in strat_window.machine_status.text()


@pytest.mark.parametrize("typed", ["12;22;32", "12, 22 32", "[12, 22, 32]", "32;12;22;12"])
def test_what_is_typed_reaches_the_computation(strat_window, typed):
    strat_window.widgets[KEY].setText(typed)
    assert strat_window.collect_params()[KEY] == [12, 22, 32]
    assert _witness_problems(strat_window) == []
    assert "TEMOINS 4 (neufs aux couches 12, 22, 32)" in strat_window.machine_status.text()


@pytest.mark.parametrize("stored", [[12, 22, 32], "12;22;32"])
def test_a_loaded_file_sets_the_plan(strat_window, tmp_path, stored):
    _load(strat_window, tmp_path, **{KEY: stored})
    assert strat_window.collect_params()[KEY] == [12, 22, 32]
    assert _witness_problems(strat_window) == []


def test_a_file_without_a_plan_runs_one_test_glass(strat_window, tmp_path):
    strat_window.widgets[KEY].setText("22;42")
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg.pop(KEY, None)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    assert strat_window.load_configuration(str(path))
    assert strat_window.collect_params()[KEY] == []


def test_the_plan_survives_a_save_and_a_load(strat_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    strat_window.widgets[KEY].setText("12;22;32")
    path = tmp_path / "saved.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "JSON (*.json)"))
    strat_window.save_configuration()
    assert path.is_file()
    strat_window.widgets[KEY].setText("")
    assert strat_window.load_configuration(str(path))
    assert strat_window.collect_params()[KEY] == [12, 22, 32]


@pytest.mark.parametrize("typed", ["22;abc", "0", "46", "22;99"])
def test_a_plan_that_cannot_be_applied_stops_the_run(strat_window, typed):
    strat_window.widgets[KEY].setText(typed)
    assert _witness_problems(strat_window), typed
    assert "TEMOINS ?" in strat_window.machine_status.text()


def test_the_reader_keeps_what_it_cannot_read_apart():
    from certus.ui import certus_strat_witness as witness

    assert witness.parse("22; x ;42,,") == ([22, 42], ["x"])
    assert witness.parse([42, 22, 42]) == ([22, 42], [])
    assert witness.parse(None) == ([], [])
