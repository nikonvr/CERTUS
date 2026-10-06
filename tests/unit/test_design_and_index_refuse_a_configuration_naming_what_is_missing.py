"""D88 beyond STRAT: DESIGN and INDEX load nothing from a configuration that names what they do not offer.

A combo box asked for a text it does not offer keeps its previous choice, without a word. DESIGN loaded a layer naming
an unknown slot as the first slot; INDEX kept its previous substrate. Each would then compute with something the file
did not name. The shared loader now asks the window first (`_config_load_problems`), says why on screen, and loads
nothing.

DESIGN had a third case, worse because silent in every old file: its preset lists offer only "Custom", and a slot saved
with a named preset (the shipped example has `TiO2 (H)`) skipped the indices the file saved with it, so the slot kept
the indices it had before the load. Those indices are now applied; a file that saved none for such a slot is refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

import certus.ui.certus_base_app_config_mixin as config_mixin

ROOT = Path(__file__).resolve().parents[2]
DESIGN_EXAMPLE = ROOT / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "configuration naming what is missing", main_windows_only=True)


@pytest.fixture
def shown(monkeypatch):
    """The text of each warning the loader shows (instead of a modal box)."""
    texts: list[str] = []
    monkeypatch.setattr(config_mixin.QMessageBox, "warning", lambda parent, title, text, *a, **k: texts.append(text))
    return texts


def _write(tmp_path: Path, config: dict) -> str:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


@pytest.mark.unit
def test_design_applies_the_indices_saved_with_a_preset_no_list_offers(qapp, tmp_path, shown):
    from certus.ui.certus_design_ui import CertusDesignApp

    config = json.loads(DESIGN_EXAMPLE.read_text(encoding="utf-8"))
    config["materials"]["H"].update({"preset": "TiO2 (H)", "n4": 2.41, "n7": 2.33})
    window = CertusDesignApp()

    assert window.load_config(_write(tmp_path, config)) is True

    assert shown == []
    assert window.mat_widgets["H"]["preset"].currentText() == "Custom"
    assert window.mat_widgets["H"]["n4"].value() == pytest.approx(2.41)
    assert window.mat_widgets["H"]["n7"].value() == pytest.approx(2.33)


@pytest.mark.unit
def test_design_loads_nothing_when_a_preset_no_list_offers_saved_no_indices(qapp, tmp_path, shown):
    from certus.ui.certus_design_ui import CertusDesignApp

    config = json.loads(DESIGN_EXAMPLE.read_text(encoding="utf-8"))
    config["materials"]["H"] = {"preset": "TiO2 (H) ABSENT"}
    window = CertusDesignApp()

    assert window.load_config(_write(tmp_path, config)) is False

    assert len(shown) == 1
    assert "TiO2 (H) ABSENT" in shown[0]


@pytest.mark.unit
def test_design_loads_nothing_when_a_layer_names_an_unknown_material(qapp, tmp_path, shown):
    from certus.ui.certus_design_ui import CertusDesignApp

    config = json.loads(DESIGN_EXAMPLE.read_text(encoding="utf-8"))
    config["front"][1]["mat"] = "Z"
    window = CertusDesignApp()

    assert window.load_config(_write(tmp_path, config)) is False

    assert len(shown) == 1
    assert '"Z"' in shown[0]


@pytest.mark.unit
def test_design_still_loads_its_shipped_example(qapp, tmp_path, shown):
    from certus.ui.certus_design_ui import CertusDesignApp

    window = CertusDesignApp()

    assert window.load_config(str(DESIGN_EXAMPLE)) is True
    assert shown == []
    assert window.mat_widgets["H"]["n4"].value() == pytest.approx(2.35)


@pytest.mark.unit
def test_index_loads_nothing_when_its_substrate_is_unknown(qapp, tmp_path, shown):
    from certus.ui.certus_index_ui import CertusIndexApp

    window = CertusIndexApp()
    before = window.cb_sub.currentText()

    assert window.load_config(_write(tmp_path, {"substrate": "Unobtainium"})) is False

    assert len(shown) == 1
    assert "Unobtainium" in shown[0]
    assert window.cb_sub.currentText() == before


@pytest.mark.unit
def test_index_still_loads_a_substrate_it_offers(qapp, tmp_path, shown):
    from certus.ui.certus_index_ui import CertusIndexApp

    window = CertusIndexApp()
    other = next(window.cb_sub.itemText(i) for i in range(window.cb_sub.count()) if i != window.cb_sub.currentIndex())

    assert window.load_config(_write(tmp_path, {"substrate": other})) is True
    assert shown == []
    assert window.cb_sub.currentText() == other
