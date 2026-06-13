"""STRAT JSON loading coherence tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("CERTUS_STRAT")

from PyQt6.QtWidgets import QApplication

from certus.ui.certus_strat_ui import CertusSTRATApp  # type: ignore[attr-defined]


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
