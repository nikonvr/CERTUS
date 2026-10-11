"""D100 -- STRAT's on/off settings take the loaded file and their defaults, not their construction state.

The on/off settings of STRAT are `CertusBooleanField`, a check box that keeps the `.text()` / `.setText()` contract of
the text field it replaced. `populate_gui_from_config`, through which the loaded file and the defaults of
`set_default_values` reach the widgets, wrote into `QLineEdit` widgets only. The check boxes therefore kept their
construction state, and `collect_params`, which reads the widget first, sent `allow_rate`, `slit_bias_enabled`,
`search_resolution`, `sym_adaptive_same_wl` and `sym_prefer_on_tie` to the computation as false, whatever the file
said: no Rate and no slit bias in any STRAT run from 2026-09-08 (f006e7eb) to 2026-10-11.

`sym_enable` is left out: `collect_params` writes it as True without reading its widget, a separate matter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

ROOT = Path(__file__).resolve().parents[2]
#: The reference configuration. It is only READ here: every variant is a copy in tmp_path.
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"

#: The on/off settings `collect_params` reads from their widget, with the value `set_default_values` gives each
#: ("the defaults are those of the real machine": Rate allowed, slit bias and slit search on).
DEFAULTS = {
    "allow_rate": True,
    "slit_bias_enabled": True,
    "search_resolution": True,
    "sym_adaptive_same_wl": True,
    "sym_allow_hybrid": False,
    "sym_prefer_on_tie": True,
}


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT on/off settings", main_windows_only=True)


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


def _sent(window) -> dict[str, bool]:
    params = window.collect_params()
    return {key: params[key] for key in DEFAULTS}


def test_the_defaults_reach_the_computation(strat_window):
    assert _sent(strat_window) == DEFAULTS


@pytest.mark.parametrize("value", [1, 0])
def test_the_loaded_file_reaches_the_computation(strat_window, tmp_path, value):
    _load(strat_window, tmp_path, **dict.fromkeys(DEFAULTS, value))
    assert _sent(strat_window) == dict.fromkeys(DEFAULTS, bool(value))
