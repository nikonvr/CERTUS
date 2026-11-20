"""STRAT JSON loading coherence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from certus.ui.certus_strat_ui import CertusSTRATApp  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT JSON loading", main_windows_only=True)


@pytest.mark.unit
def test_strat_json_example_loads_canonical_h_material(qapp):
    """The example JSON should load the canonical H/L/substrate labels."""

    app = QApplication.instance() or qapp
    assert app is not None

    window = CertusSTRATApp()

    sample_config = {
        "h_type_custom": False,
        "l_type_custom": False,
        "h_material_file": "H800-Nb2O5",
        "l_material_file": "H800-SiO2",
        "substrate_choice": "Silice",
        "stack_multipliers": [1.0, 1.0, 1.0],
    }

    window.populate_gui_from_config(sample_config)

    assert window.widgets["h_type_file"].isChecked() is True
    assert window.widgets["l_type_file"].isChecked() is True
    assert window.widgets["h_material_file"].currentText() == "H800-Nb2O5"
    assert window.widgets["l_material_file"].currentText() == "H800-SiO2"
    assert window.widgets["substrate_choice"].currentText() == "SiO2"

    params = window.collect_params()
    assert params["h_material_file"] == "H800-Nb2O5"
    assert params["l_material_file"] == "H800-SiO2"
    assert params["substrate_choice"] == "SiO2"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected_mode", "expected_mc", "expected_topk"),
    [
        ("JSON-strat-example-fast.json", "fast", 50, 20),
        ("JSON-strat-example.json", "premium", 150, 40),
        ("JSON-strat-example-deep.json", "deep", 300, 100),
        ("JSON-strat-bandpass-3cav-fast.json", "fast", 50, 20),
        ("JSON-strat-bandpass-3cav.json", "premium", 150, 40),
        ("JSON-strat-bandpass-3cav-deep.json", "deep", 300, 100),
    ],
)
def test_strat_execution_mode_presets_loading(qapp, filename, expected_mode, expected_mc, expected_topk):
    """Verify that all FAST/PREMIUM/DEEP presets for 48c and 35c load their execution mode and params correctly."""
    app = QApplication.instance() or qapp
    assert app is not None

    root = Path(__file__).resolve().parents[2]
    json_path = root / "example" / "example_strat" / filename
    assert json_path.exists(), f"Missing preset file: {json_path}"

    window = CertusSTRATApp()
    window.load_configuration(str(json_path))

    assert window.widgets["execution_mode"].currentText() == expected_mode
    params = window.collect_params()
    assert params["execution_mode"] == expected_mode
    assert params["robustness_num_runs"] == expected_mc
    assert params["dp_top_k"] == expected_topk



def test_strat_local_search_rounds_reaches_the_worker_params(qapp, tmp_path):
    import json

    source = Path(__file__).resolve().parents[2] / "example/example_strat/JSON-strat-example-fast.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    config["strat_local_search_rounds"] = 3
    path = tmp_path / "strat_rounds.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    window = CertusSTRATApp()
    assert window.load_configuration(str(path))
    assert window.collect_params()["strat_local_search_rounds"] == 3
    assert window._collect_config()["strat_local_search_rounds"] == 3


def test_strat_local_search_check_seeds_reaches_the_worker_params(qapp, tmp_path):
    """Chantier 7 (2026-11-20): the number of fresh check seeds comes from the component file, and is saved with it."""
    import json

    source = Path(__file__).resolve().parents[2] / "example/example_strat/JSON-strat-example-fast.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    config["strat_local_search_check_seeds"] = 6
    path = tmp_path / "strat_check_seeds.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    window = CertusSTRATApp()
    assert window.load_configuration(str(path))
    assert window.collect_params()["strat_local_search_check_seeds"] == 6
    assert window._collect_config()["strat_local_search_check_seeds"] == 6


def test_without_the_key_the_check_keeps_two_seeds(qapp):
    window = CertusSTRATApp()
    source = Path(__file__).resolve().parents[2] / "example/example_strat/JSON-strat-example-fast.json"
    assert window.load_configuration(str(source))
    assert window.collect_params()["strat_local_search_check_seeds"] == 2
    assert "strat_local_search_check_seeds" not in window._collect_config()
