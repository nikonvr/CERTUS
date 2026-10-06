"""D88: a STRAT configuration naming a material the database does not have must not be computed with another one.

A combo box asked for a text it does not offer keeps its previous choice. Measured on 2026-10-06 on the judge of
peace with the H material renamed: the list stayed on `IR-H400-SiO2`, the run computed n_H = 1.4773 at 550 nm
instead of 2.3579, and only two log lines said so. The run is now refused, with the reason on screen, until the
operator picks the material in the list.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from certus.ui.certus_strat_ui import CertusSTRATApp  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    """The windows a test builds are destroyed when it ends (D11): closing only hides them."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT missing material", main_windows_only=True)


def _load(tmp_path: Path, **changes) -> CertusSTRATApp:
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config.update(changes)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    window = CertusSTRATApp()
    assert window.load_configuration(str(path))
    return window


@pytest.mark.unit
def test_a_material_missing_from_the_database_refuses_the_run(qapp, tmp_path, monkeypatch):
    import certus.ui.certus_strat_ui_worker as worker_module

    window = _load(tmp_path, h_material_file="H800-Nb2O5-ABSENT")
    refused: list[list[str]] = []
    started: list[bool] = []

    class _NoWorker:
        def __init__(self, *args, **kwargs):
            started.append(True)
            raise RuntimeError("the run was started")

    monkeypatch.setattr(window, "refuse_to_run", lambda problems: refused.append(list(problems)))
    monkeypatch.setattr(worker_module, "WorkerThread", _NoWorker)

    try:
        window.run_workflow(23)
    except RuntimeError:
        pass

    assert started == [], "the run started with a material the configuration did not ask for"
    assert len(refused) == 1
    assert any("H800-Nb2O5-ABSENT" in problem for problem in refused[0])


@pytest.mark.unit
def test_the_operator_s_own_pick_in_the_list_settles_the_material(qapp, tmp_path):
    window = _load(tmp_path, h_material_file="H800-Nb2O5-ABSENT")
    combo = window.widgets["h_material_file"]
    assert window.material_problems()

    combo.activated.emit(combo.currentIndex())  # what a click in the list sends

    assert window.material_problems() == []


@pytest.mark.unit
def test_the_shipped_configuration_raises_no_material_problem(qapp, tmp_path):
    window = _load(tmp_path)

    assert window.material_problems() == []
    assert window.widgets["h_material_file"].currentText() == "H800-Nb2O5"
