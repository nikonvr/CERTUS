"""FIELD's post-optimization cleanup removes the thin layers and merges what becomes adjacent.

After every optimization, FIELD removes the layers thinner than « dmin » and relaunches a local
optimization. Until 2026-09-29 the removal called `rebuild_material_pattern`, a method of the
stack panel that the window does not have: whenever a thin layer was not the last one left,
the cleanup raised AttributeError, the re-optimization never started, and the table kept two
adjacent layers of the same material. Relabelling the rows H, L, H… would not have been right
either: it changes the material of every layer after the removed one. The layers keep their
material; two neighbours of the same material become one layer, QWOT summed.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "FIELD thin-layer cleanup", main_windows_only=True)


@pytest.fixture
def field_app(qapp, monkeypatch):
    from certus.ui.certus_field_ui import CertusFieldApp

    monkeypatch.setattr("certus.ui.certus_field_state_mixin.show_toast", lambda *a, **k: None)
    return CertusFieldApp()


def _load(app, rows) -> None:
    from PyQt6.QtWidgets import QTableWidgetItem

    table = app.table_layers
    app._is_updating_table = True
    app.stack_panel.is_updating_table = True
    try:
        table.setRowCount(0)
        for material, qwot in rows:
            row = table.rowCount()
            table.insertRow(row)
            for column, text in enumerate((material, f"{qwot:.4f}", "0.0")):
                table.setItem(row, column, QTableWidgetItem(text))
    finally:
        app._is_updating_table = False
        app.stack_panel.is_updating_table = False
    app._update_thicknesses()


def _stack(app) -> list[tuple[str, float]]:
    table = app.table_layers
    return [(table.item(r, 0).text(), float(table.item(r, 1).text())) for r in range(table.rowCount())]


def test_a_thin_inner_layer_goes_and_its_neighbours_merge(field_app) -> None:
    _load(field_app, [("H", 1.0), ("L", 0.02), ("H", 1.0), ("L", 1.0)])

    removed = field_app._remove_thin_layers_strict(5.0)

    assert _stack(field_app) == [("H", 2.0), ("L", 1.0)]
    assert removed == 1


def test_a_thin_first_layer_goes_and_the_others_keep_their_material(field_app) -> None:
    _load(field_app, [("H", 0.02), ("L", 1.0), ("H", 1.0)])

    field_app._remove_thin_layers_strict(5.0)

    assert _stack(field_app) == [("L", 1.0), ("H", 1.0)]


def test_the_relaunched_optimization_starts_from_the_cleaned_stack(field_app, monkeypatch) -> None:
    requests = []
    monkeypatch.setattr(field_app, "_start_worker", requests.append)
    _load(field_app, [("H", 1.0), ("L", 0.02), ("H", 1.0), ("L", 1.0)])

    assert field_app._cleanup_thin_layers_and_reoptimize(source="optimization") is True

    [request] = requests
    assert request.action == "optimize"
    assert list(request.params.emp_factors) == [2.0, 1.0]
    assert list(request.params.layer_types) == [0, 1]


def test_the_merged_layer_shows_its_new_thickness(field_app, monkeypatch) -> None:
    """The thickness column followed the QWOT only when the re-optimization came back."""
    monkeypatch.setattr(field_app, "_start_worker", lambda request: None)
    _load(field_app, [("H", 1.0), ("L", 0.02), ("H", 1.0), ("L", 1.0)])
    one_qwot_nm = float(field_app.table_layers.item(0, 2).text())

    field_app._cleanup_thin_layers_and_reoptimize(source="optimization")

    assert float(field_app.table_layers.item(0, 2).text()) == pytest.approx(2 * one_qwot_nm, abs=0.02)
