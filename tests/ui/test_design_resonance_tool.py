"""The optional tool dispatches real work explicitly and applies only its unchanged input snapshot."""
from __future__ import annotations

import time

import numpy as np
import pytest
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QWidget

from certus.core.certus_design_resonances import prepare_design_resonances
from certus.physics.certus_opt_tmm import Material
from certus.physics.design_resonances import ResonanceAnalysis, ResonanceRefinement, ResonanceSettings
from certus.ui import certus_design_resonances_dialog as tool
from certus_physics.structures import Layer, Target


@pytest.fixture(autouse=True)
def _qt_scope(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN resonances")


@pytest.fixture
def window(qapp):
    ui = QWidget()
    ui.ep_current = np.array([50.1234567890123, 80.9876543210987])
    ui.oblique_mode = False
    ui._is_busy = False
    ui.back_check, ui.back_coat_check = QCheckBox(ui), QCheckBox(ui)
    ui.l0_spin = QDoubleSpinBox(ui)
    ui.l0_spin.setRange(100, 2000)
    ui.l0_spin.setValue(500.)
    ui.materials = {"H": Material(2.35, 2.35), "L": Material(1.45, 1.45), "Substrate": Material(1.52, 1.52)}
    ui.layers = [Layer("H", 1., False), Layer("L", 1., True)]
    ui.targets = [Target(400, 440, 0., 0.)]
    ui._get_materials = lambda: ui.materials
    ui._get_front_stack = lambda: ui.layers
    ui._get_tgts = lambda: ui.targets
    ui.applied = []
    ui.evaluations = []
    ui._apply_qw_values_to_front_table = ui.applied.append
    ui._update_thickness_display = lambda: None
    ui._schedule_eval = ui.evaluations.append
    ui.log = lambda *_args: None
    return ui


def analysis() -> ResonanceAnalysis:
    return ResonanceAnalysis(0.01, 0.02, (), (), ())


def test_opening_the_tool_neither_runs_physics_nor_changes_thicknesses(window, monkeypatch):
    before = window.ep_current.copy()
    monkeypatch.setattr(tool, "analyze_resonances", lambda *_args, **_kwargs: pytest.fail("implicit calculation"))
    monkeypatch.setattr(tool, "refine_resonances", lambda *_args, **_kwargs: pytest.fail("implicit refinement"))
    tab = tool.build_resonance_tab(window)
    dialog = tool.DesignResonanceDialog(window)
    assert tab is not None
    assert dialog._thread is None
    assert not dialog.apply_button.isEnabled()
    np.testing.assert_array_equal(window.ep_current.view(np.uint64), before.view(np.uint64))
    dialog.close()


def test_worker_passes_settings_bounds_and_fixed_layers_to_the_native_refinement(window, monkeypatch):
    request = prepare_design_resonances(window.materials, window.layers, window.targets, window.ep_current)
    settings = ResonanceSettings(rounds=3, burst=7, height_threshold=0.002)
    received = {}

    def refine(problem, d, **kwargs):
        received.update(kwargs)
        return ResonanceRefinement(d, analysis(), analysis(), 0, (analysis(),))

    monkeypatch.setattr(tool, "refine_resonances", refine)
    worker = tool._ResonanceWorker(request, settings, 0.5, True)
    results = []
    worker.result.connect(results.append)
    worker.run()
    assert len(results) == 1
    assert received["settings"] is settings
    np.testing.assert_array_equal(received["variable_indices"], [1])
    np.testing.assert_array_equal(received["lower_bounds"], [0.5, 0.5])


def test_explicit_apply_keeps_full_precision_and_requests_standard_evaluation(window):
    dialog = tool.DesignResonanceDialog(window)
    dialog._request = dialog._current_input()
    d = window.ep_current + np.array([0., 0.1234567890123])
    dialog._result = ResonanceRefinement(d, analysis(), analysis(), 1, (analysis(),))
    dialog._refining = True
    dialog._apply()
    np.testing.assert_array_equal(window.ep_current.view(np.uint64), d.view(np.uint64))
    assert len(window.applied) == 1
    assert window.evaluations == [True]
    assert window._use_exact_ep
    dialog.close()


def test_stale_results_do_not_overwrite_an_edited_design(window):
    dialog = tool.DesignResonanceDialog(window)
    dialog._request = dialog._current_input()
    dialog._result = ResonanceRefinement(window.ep_current.copy(), analysis(), analysis(), 0, (analysis(),))
    window.ep_current[0] += 1
    before = window.ep_current.copy()
    dialog._apply()
    assert not window.applied
    assert "changed" in dialog.status.text()
    np.testing.assert_array_equal(window.ep_current, before)
    dialog.close()


def test_async_analysis_returns_on_the_gui_thread_without_enabling_apply(window, qapp):
    before = window.ep_current.copy()
    dialog = tool.DesignResonanceDialog(window)
    dialog.analyze_button.click()
    deadline = time.monotonic() + 30
    while dialog._thread is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert dialog._thread is None, dialog.status.text()
    assert dialog._result is not None, dialog.status.text()
    assert not dialog.apply_button.isEnabled()
    np.testing.assert_array_equal(window.ep_current, before)
    dialog.close()


def test_named_button_slots_and_finished_cleanup_are_connected(window, monkeypatch):
    calls = []
    monkeypatch.setattr(tool.DesignResonanceDialog, "_start", lambda _self, refine: calls.append(refine))
    tab = tool.build_resonance_tab(window)
    tab.findChild(tool.QPushButton).click()
    dialog = window.resonance_dialog
    dialog.analyze_button.click()
    dialog.refine_button.click()
    assert calls == [False, True]
    dialog.close()
    assert window.resonance_dialog is None
