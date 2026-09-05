"""Garde-fous d'intégrité GUI et de non-régression pour l'ensemble de la suite CERTUS.

Vérifie systématiquement :
1. Qu'aucune des applications de la suite (11 fenêtres pour 10 modules) ne pollue QT_QPA_PLATFORM à l'import (écran invisible).
2. Que toutes les fenêtres satellites et boîtes de dialogue secondaires s'instancient sans NameError.
"""

from __future__ import annotations

import os
import pytest
from PyQt6.QtWidgets import QWidget, QDialog, QMainWindow


APPS_REGISTRY = [
    ("HUB", "CERTUS_HUB", "CertusHub"),
    ("DESIGN", "certus.ui.certus_design_ui", "CertusDesignApp"),
    ("STRAT", "certus.ui.certus_strat_ui", "CertusStratApp"),
    ("RE", "CERTUS_RE", "CertusREApp"),
    ("INDEX", "certus.ui.certus_index_ui", "CertusIndexApp"),
    ("INDEX_SPLINE", "certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    ("FIELD", "certus.ui.certus_field_ui", "CertusFieldApp"),
    ("SMOOTHER", "certus.utils.certus_curve_smoother", "CurveSmootherGUI"),
    ("SUBSTRATE_INDEX", "certus.ui.certus_substrate_ui", "SubstrateIndexGUI"),
    ("METAL_SINGLE", "CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    ("METAL_BILAYER", "CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
]


@pytest.mark.parametrize("app_name,mod_path,cls_name", APPS_REGISTRY)
def test_app_import_does_not_poison_qpa_platform(app_name: str, mod_path: str, cls_name: str) -> None:
    """Garantit qu'aucun import ne force QT_QPA_PLATFORM=offscreen."""
    os.environ.pop("QT_QPA_PLATFORM", None)

    mod = __import__(mod_path, fromlist=[cls_name])
    app_cls = getattr(mod, cls_name, None)

    assert app_cls is not None, f"Application class {cls_name} not found in {mod_path}"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", (
        f"Régression critique : {app_name} ({mod_path}) a forcé QT_QPA_PLATFORM=offscreen !"
    )


def test_suite_auxiliary_windows_and_dialogs_instantiate(qapp, monkeypatch) -> None:
    """Vérifie que les fenêtres et dialogues secondaires de la suite s'instancient sans NameError."""
    _ = qapp
    parent = QWidget()

    # 1. FIELD — Fenêtre d'empilement détachée
    from certus.ui.certus_field_common import DetachedStackWindow
    stack_panel = QWidget()
    det_win = DetachedStackWindow(stack_panel, parent=parent)
    assert det_win is not None
    det_win.deleteLater()

    # 2. INDEX / SPLINE — Dialogues de nœuds manuels et d'initialisation
    import numpy as np
    from certus.ui.certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog
    diag = ManualSigmaKnotDialog(
        sigma_knots=np.array([500.0]),
        lam_model_nm=None,
        y_model=None,
        lam_measurement_nm=None,
        y_measurement=None,
        y_label="T",
        parent=parent,
    )
    assert diag is not None
    diag.deleteLater()

    from certus.ui.certus_smart_init_curve_editor import SmartInitNKCurveEditorDialog
    diag_nk = SmartInitNKCurveEditorDialog(
        parent=parent,
        n_lo=1.0,
        n_hi=3.0,
        L_lo=-10.0,
        L_hi=0.0,
        k_clip_lo=1e-5,
        get_sk=lambda: np.array([1.0 / 500.0]),
        get_n_phys=lambda: np.array([1.5]),
        get_L_nodes=lambda: np.array([-5.0]),
        set_n_at=lambda _i, _v: None,
        set_L_at=lambda _i, _v: None,
        request_recalc=lambda: None,
        study_lambda_window=lambda: (400.0, 800.0),
    )
    assert diag_nk is not None
    diag_nk.deleteLater()

    # 3. RE — Dialogue de résultats
    from certus.ui.certus_re_ui import CertusREResultsDialog
    from certus.ui.certus_qt_widgets import QDoubleSpinBox
    monkeypatch.setattr(CertusREResultsDialog, "exec", lambda self: 0)
    monkeypatch.setattr(CertusREResultsDialog, "show", lambda self: None)
    dummy_re = QWidget(parent)
    dummy_re.l0_spin = QDoubleSpinBox(dummy_re)
    dummy_re.l0_spin.setValue(550.0)
    dummy_re._get_materials = lambda: {}
    dummy_re._re_envelope_scale_from_gui = lambda: 1.0
    dummy_re._re_spline_lam2_nm_from_result = lambda r: 2000.0
    dummy_re._re_initial_stack = []
    dummy_re.log = lambda msg: None
    re_diag = CertusREResultsDialog(
        dummy_re,
        [{"label": "Run 1", "rmse": 0.01, "nfev": 10, "ep": np.array([])}],
        np.array([]),
        announce_in_log=False,
    )
    assert re_diag is not None
    re_diag.deleteLater()
    dummy_re.deleteLater()

    # 4. SUBSTRATE — Dialogue de table d'indice
    from certus.ui.certus_substrate_ui import IndexTableDialog
    idx_diag = IndexTableDialog(np.array([500.0]), {}, {}, {})
    assert idx_diag is not None
    idx_diag.deleteLater()

    # 5. UI UTILS — Fenêtre détachée de graphique
    from certus.ui.certus_ui_widgets_utils import DetachedPlotWindow
    dummy_plot = QWidget()
    det_plot = DetachedPlotWindow(dummy_plot, parent=parent, title="Test Plot")
    assert det_plot is not None
    det_plot.deleteLater()

    # 6. STRAT — Toutes les fenêtres satellites
    from certus.ui.certus_strat_json_ui import JsonViewerWindow
    from certus.ui.certus_strat_popout_ui import PopOutWindow
    from certus.ui.certus_strat_monitor_ui import LiveMonitorWindow
    from certus.ui.certus_strat_thickness_ui import TransmissionVsThicknessWindow
    from certus.ui.certus_strat_spectrum_ui import InteractiveSpectrumWindow
    from certus.ui.certus_strat_performance_ui import StrategySpectralPerformanceWindow
    from certus.ui.certus_strat_table_ui import StrategiesTableWindow
    from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
    from certus.ui.certus_strat_indices_ui import InteractiveIndicesWindow
    from certus.ui.certus_strat_stack_progress_widget import CertusStratStackProgressWidget

    dummy_strategy = {"strategy": {"strategy_id": 900000001, "blocks": [], "layers": []}}
    strat_spectral_data = {"wavelengths": np.array([500.0]), "T_nominal": np.array([0.5])}
    strat_indices_data = {"wavelengths": np.array([500.0]), "nH": np.array([2.0]), "nL": np.array([1.5])}
    monkeypatch.setattr("certus.ui.certus_strat_performance_ui.simulate_spectral_distribution_for_ui", lambda *a, **kw: None)

    for win_factory in [
        lambda: JsonViewerWindow(parent, "JSON Viewer", "{}"),
        lambda: PopOutWindow(QWidget(), parent=parent, title="Test"),
        lambda: LiveMonitorWindow(parent),
        lambda: TransmissionVsThicknessWindow(parent, dummy_strategy, {}, {}),
        lambda: InteractiveSpectrumWindow(parent, strat_spectral_data),
        lambda: StrategySpectralPerformanceWindow(parent, dummy_strategy, {}, {}),
        lambda: StrategiesTableWindow(parent, [], [], False),
        lambda: InteractiveHeatmapWindow(parent, {}),
        lambda: InteractiveIndicesWindow(parent, strat_indices_data),
        lambda: CertusStratStackProgressWidget(parent),
    ]:
        w = win_factory()
        assert w is not None
        w.deleteLater()

    parent.deleteLater()


def test_curve_smoother_save_file_guardrail(qapp, tmp_path, monkeypatch):
    """Ensure CurveSmoother prompts for save path, does not overwrite source silently, and handles save."""
    import pandas as pd
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    from certus.utils.certus_curve_smoother import CurveSmootherGUI

    smoother = CurveSmootherGUI()

    src_file = tmp_path / "measured_spectrum.xlsx"
    df = pd.DataFrame({
        "Wavelength": [400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0, 750.0],
        "Intensity": [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0],
    })
    df.to_excel(src_file, index=False)

    smoother.df = df
    smoother.file_path = str(src_file)

    target_file = tmp_path / "measured_spectrum_clean.xlsx"

    # Mock QFileDialog.getSaveFileName to return target_file
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target_file), "Excel Files (*.xlsx)"),
    )

    # Mock QMessageBox dialogs
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    smoother.save_file()

    assert target_file.exists(), "Target file should have been created."
    res_sheets = pd.read_excel(target_file, sheet_name=None)
    assert "clean_measurements" in res_sheets
    smoother.deleteLater()


def test_design_clear_button_actually_clears(qapp, monkeypatch):
    """Measured 2026-09-04: the button silently did nothing — its reset manager was
    built on the LayoutManager delegate, so QMessageBox.question raised TypeError
    into a Qt slot, where it was swallowed."""
    import pytest
    from PyQt6.QtWidgets import QMessageBox
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.utils.certus_reset_framework import create_reset_button

    # Guardrail: create_reset_button must fail immediately with TypeError if passed a non-QWidget
    class DummyNonWidget:
        pass

    with pytest.raises(TypeError, match="must be a QWidget"):
        create_reset_button(DummyNonWidget())

    window = CertusDesignApp()
    initial_rows = window.front_table.rowCount()
    assert initial_rows == 4, "Default design should have initial 4 layers."

    # Add extra layers to verify reset restores factory defaults
    window.add_front_layer()
    window.add_front_layer()
    assert window.front_table.rowCount() == 6

    # Mock QMessageBox.question to confirm reset
    question_called = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: (question_called.append(True), QMessageBox.StandardButton.Yes)[1],
    )

    window.clear_btn.click()

    assert len(question_called) == 1, "Confirmation dialog must be called on clear_btn click."
    assert window.front_table.rowCount() == initial_rows, "Front table should be reset to default 4 layers."
    window.close()
    window.deleteLater()


@pytest.mark.parametrize("mod_name,app_cls_name", [
    ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
])
def test_metal_run_button_visible_and_cards_painted_at_1366(qapp, mod_name, app_cls_name):
    """Measured 2026-09-04: in both METAL apps at 1366x768, the '▶ Run' button was
    469-700 px below the window viewport because actions were buried inside the
    scroll area, and nested cards had conflicting opacity effects."""
    from PyQt6.QtCore import Qt
    import importlib

    mod = importlib.import_module(mod_name)
    app_cls = getattr(mod, app_cls_name)
    win = app_cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1366, 768)
    win.show()

    qapp.processEvents()

    # Guard 1: btn_run must be strictly within the visible window viewport
    run_btn = win.btn_run
    run_center = run_btn.mapTo(win, run_btn.rect().center())
    assert 0 <= run_center.y() <= win.height(), (
        f"{mod_name}: btn_run Y ({run_center.y()}) must be within window height ({win.height()})"
    )

    # Guard 2: Parameter cards must be painted and visible (not blocked at opacity 0.0)
    for card in win.params_widget.findChildren(object):
        if type(card).__name__ == "CertusCard":
            eff = card.graphicsEffect()
            if eff is not None and hasattr(eff, "opacity"):
                assert eff.opacity() > 0.0, f"{mod_name}: card {card} must not be invisible (opacity 0)"

    # Guard 3: All parameter inputs in the grid must be visible
    from PyQt6.QtWidgets import QComboBox, QLineEdit
    inputs = [w for w in win.params_widget.findChildren((QLineEdit, QComboBox)) if w.isVisible()]
    assert len(inputs) >= 8, f"{mod_name}: parameter inputs must be visible (found {len(inputs)})"

    win.close()
    win.deleteLater()


def _find_window_shortcut(window, sequence: str):
    from PyQt6.QtGui import QKeySequence, QShortcut
    from certus.ui.certus_ui_utils import normalized_shortcut
    target = normalized_shortcut(sequence)
    for sc in window.findChildren(QShortcut):
        if normalized_shortcut(sc.key()) == target:
            return sc
    return None


def test_strat_esc_stops_optimization_and_ctrl_w_closes_aux(qapp, monkeypatch):
    """Measured 2026-09-04: Esc closed auxiliary windows instead of stopping STRAT
    (a 2h39 run). Esc must call request_stop_optimization, and Ctrl+W must close auxiliary windows."""
    from certus.ui.certus_strat_ui import CertusStratApp

    stop_called = []
    close_aux_called = []
    monkeypatch.setattr(CertusStratApp, "request_stop_optimization", lambda self: stop_called.append(True))
    monkeypatch.setattr(CertusStratApp, "close_all_auxiliary_windows", lambda self: close_aux_called.append(True))

    win = CertusStratApp()

    # Find and trigger Esc shortcut
    esc_sc = _find_window_shortcut(win, "Esc")
    assert esc_sc is not None, "STRAT must have an Esc shortcut"
    esc_sc.activated.emit()
    assert len(stop_called) == 1, "Esc must call request_stop_optimization"
    assert len(close_aux_called) == 0, "Esc must NOT close auxiliary windows"

    # Find and trigger Ctrl+W shortcut
    ctrl_w_sc = _find_window_shortcut(win, "Ctrl+W")
    assert ctrl_w_sc is not None, "STRAT must have a Ctrl+W shortcut"
    ctrl_w_sc.activated.emit()
    assert len(close_aux_called) == 1, "Ctrl+W must close auxiliary windows"

    win.close()
    win.deleteLater()


def test_design_ctrl_o_loads_config_not_optim(qapp, monkeypatch):
    """Measured 2026-09-04: Ctrl+O launched local optimization in DESIGN instead of
    loading configuration. Ctrl+O must invoke load_config, and Ctrl+Shift+G must run local optim."""
    from certus.ui.certus_design_ui import CertusDesignApp

    load_called = []
    optim_called = []
    monkeypatch.setattr(CertusDesignApp, "load_config", lambda self, *a, **kw: load_called.append(True))
    monkeypatch.setattr(CertusDesignApp, "run_optim", lambda self, mode: optim_called.append(mode))

    win = CertusDesignApp()

    ctrl_o_sc = _find_window_shortcut(win, "Ctrl+O")
    assert ctrl_o_sc is not None, "DESIGN must have a Ctrl+O shortcut"
    ctrl_o_sc.activated.emit()
    assert len(load_called) == 1, "Ctrl+O must trigger load_config"
    assert len(optim_called) == 0, "Ctrl+O must NEVER trigger optimization"

    ctrl_shift_g_sc = _find_window_shortcut(win, "Ctrl+Shift+G")
    assert ctrl_shift_g_sc is not None, "DESIGN must have a Ctrl+Shift+G shortcut for local optim"
    ctrl_shift_g_sc.activated.emit()
    assert optim_called == ["local"], "Ctrl+Shift+G must trigger local optimization"

    win.close()
    win.deleteLater()




