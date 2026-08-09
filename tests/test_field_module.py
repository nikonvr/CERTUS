import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from certus.core.certus_field_core import (
    _trapz_numba, 
    calculate_electric_field, 
    calculate_opt_metrics
)
from certus.workers.certus_field_workers_dto import FieldParamsDTO, FieldWorkerRequest
from certus.workers.certus_field_workers import FieldWorkerThread, top_level_objective_function
from certus.ui.certus_field_services import FieldExportService, FieldPlotData, FieldStackService

# ---------------------------------------------------------
# TESTS CORE (Numba & Math)
# ---------------------------------------------------------
def test_trapz_numba_linear():
    """Testing Numba trapezoidal integration on a linear function."""
    y = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    x = np.array([0.0, 1.0, 2.0], dtype=np.float64)
    res = _trapz_numba(y, x)
    assert np.isclose(res, 4.0), f"Expected 4.0, got {res}"

def test_trapz_numba_constant():
    """Test on a constant."""
    y = np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
    x = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float64)
    res = _trapz_numba(y, x)
    assert np.isclose(res, 15.0), f"Expected 15.0, got {res}"

def test_calculate_electric_field_basic():
    """Testing the field analytical calculation pipeline."""
    z_coords, E2_values, ep_c1_cn, integrals, averages = calculate_electric_field(
        n1_r=2.0, n2_r=1.5, nSub_r=1.5,
        l0=1000.0, lambda_calc=1000.0,
        emp_factors=[1.0, 1.0], n_superstrate_real=1.0,
        integral_points=50
    )
    
    assert len(ep_c1_cn) == 2, "Doit avoir 2 couches"
    assert len(integrals) == 2, "Doit avoir 2 intégrales"
    assert len(averages) == 2, "Doit avoir 2 moyennes"
    assert len(z_coords) == len(E2_values)
    assert np.all(E2_values >= 0), "|E|² doit toujours être >= 0"
    assert np.isfinite(np.max(E2_values))

def test_calculate_opt_metrics():
    """Testing structured feedback of optimization metrics."""
    metrics = calculate_opt_metrics(
        n1_r=2.0, n2_r=1.5, nSub_r=1.5,
        l0=1000.0, emp_factors_list=[1.0, 1.0, 1.0], 
        n_super=1.0, integral_points=50
    )
    
    assert 'R' in metrics
    assert 'max_avg_1' in metrics
    assert 'max_avg_2' in metrics
    assert 'ratio_average' in metrics
    assert 0.0 <= metrics['R'] <= 1.0
    assert np.isfinite(metrics['ratio_average']) or np.isinf(metrics['ratio_average'])

def test_top_level_objective_function():
    """Testing the L-BFGS-B optimization cost function (with lists)."""
    p = [1.0, 1.0]
    cost = top_level_objective_function(
        p, n1_rs=[2.0], n2_rs=[1.5], nSub_rs=[1.5], l0=1000.0,
        seuil_int_1=0.5, seuil_int_2=0.5, alpha=10.0, 
        integral_points=50, n_supers=[1.0], lambda_calcs=[1000.0]
    )
    assert isinstance(cost, float)
    assert cost > 0.0, "Le coût doit être positif"


def test_top_level_objective_function_invalid_inputs():
    """Invalid entries must return a high bound cost."""
    cost = top_level_objective_function(
        [np.nan],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=0.5,
        seuil_int_2=0.5,
        alpha=10.0,
        integral_points=50,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
    )
    assert cost >= 1e30


def test_top_level_objective_function_reflectance_window_penalty():
    """The rmin/rmax bounds must influence the cost monotonically."""
    base_cost = top_level_objective_function(
        [1.0, 1.0],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=0.5,
        seuil_int_2=0.5,
        alpha=10.0,
        integral_points=50,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
        rmin=0.0,
        rmax=1.0,
    )
    windowed_cost = top_level_objective_function(
        [1.0, 1.0],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=0.5,
        seuil_int_2=0.5,
        alpha=10.0,
        integral_points=50,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
        rmin=0.8,
        rmax=0.9,
    )
    assert windowed_cost >= base_cost


def test_calculate_opt_metrics_invalid_l0_returns_safe_defaults():
    """Un l0 non physique ne doit pas casser le contrat de sortie."""
    metrics = calculate_opt_metrics(
        n1_r=2.0,
        n2_r=1.5,
        nSub_r=1.5,
        l0=0.0,
        emp_factors_list=[1.0, 1.0],
        n_super=1.0,
        integral_points=50,
    )
    assert metrics == {'R': 0, 'ratio_average': 0, 'max_avg_1': 0, 'max_avg_2': 0, 'max_peak_1': 0, 'max_peak_2': 0}


def test_field_stack_service_load_stack():
    """The loading helper must fill the table with a deterministic alternation."""
    from PyQt6.QtWidgets import QTableWidget

    table = QTableWidget()
    FieldStackService.load_stack(table, [1.0, 2.0, 3.0], [0, 1, 0])
    assert table.rowCount() == 3
    assert table.item(0, 0).text() == "H"
    assert table.item(1, 0).text() == "L"
    assert table.item(2, 0).text() == "H"
    assert table.item(1, 1).text() == "2.0000"


def test_field_stack_service_normalize_layer_types():
    """The standardizer must provide a safe and stable alternation."""
    assert FieldStackService.normalize_layer_types([0, 1, 0], 3) == [0, 1, 0]
    assert FieldStackService.normalize_layer_types([9], 3) == [0, 1, 0]
    assert FieldStackService.normalize_layer_types(None, 4) == [0, 1, 0, 1]


def test_field_export_service_build_plot_data_and_frames():
    """Les helpers d'export doivent produire des structures stables."""
    result = type(
        "DummyResult",
        (),
        {
            "z_coords": [0.0, 1.0],
            "E2_values_list": [[1.0, 2.0]],
            "lambda_calcs": [1064.0],
            "ep_c1_cn": [10.0],
        },
    )()
    plot_data = FieldExportService.build_plot_data(result)
    frames = FieldExportService.build_plot_export_frames(plot_data)
    assert plot_data["z_coords"] == [0.0, 1.0]
    assert "Field_1" in frames
    assert list(frames["Field_1"].columns) == ["z (nm)", "|E|^2", "lambda_calc_nm"]


def test_field_plot_data_round_trip():
    """The plot DTO must convert cleanly from a generic source."""
    payload = FieldPlotData.from_any(
        type(
            "Dummy",
            (),
            {
                "z_coords": (0.0, 2.0),
                "E2_values_list": ((1.0, 3.0),),
                "lambda_calcs": (532.0,),
                "ep_c1_cn": (5.0,),
            },
        )()
    )
    assert payload.z_coords == [0.0, 2.0]
    assert payload.E2_values_list == [[1.0, 3.0]]
    assert payload.to_dict()["lambda_calcs"] == [532.0]

# ---------------------------------------------------------
# TESTS WORKERS (Async Tasks)
# ---------------------------------------------------------
def test_field_worker_calculate():
    """Worker test in 'calculate' mode without UI."""
    params = FieldParamsDTO(
        n1_rs=[2.1], n2_rs=[1.46], nSub_rs=[1.52], n_supers=[1.0],
        l0=1064.0, lambda_calcs=[1064.0], emp_factors=[1.0, 1.0],
        seuil_int_1=0.5, seuil_int_2=0.5, alpha=10.0, maxiter=10
    )
    req = FieldWorkerRequest(action="calculate", params=params)
    worker = FieldWorkerThread(req)

    result_container = []
    def on_finished(res):
        result_container.append(res)

    worker.signals.finished.connect(on_finished)
    worker.run()

    assert len(result_container) == 1, "Le signal finished n'a pas été émis correctement"
    res = result_container[0]
    assert res.success is True
    assert res.message == "Calculation successful."
    assert len(res.z_coords) > 0
    assert len(res.E2_values_list) > 0


def test_field_worker_calculate_invalid_parameter_shapes_emits_error():
    """The worker should fail cleanly if the parameter lists are inconsistent."""
    params = FieldParamsDTO(
        n1_rs=[2.1],
        n2_rs=[1.46],
        nSub_rs=[1.52],
        n_supers=[1.0],
        l0=1064.0,
        lambda_calcs=[1064.0, 532.0],
        emp_factors=[1.0, 1.0],
        seuil_int_1=0.5,
        seuil_int_2=0.5,
        alpha=10.0,
        maxiter=10,
    )
    worker = FieldWorkerThread(FieldWorkerRequest(action="calculate", params=params))

    errors = []
    worker.signals.error.connect(lambda err: errors.append(err))
    worker.run()

    assert len(errors) == 1
    assert "inconsistent parameter" in errors[0][1].lower()

@patch('certus.workers.certus_field_workers.minimize')
def test_field_worker_optimize(mock_minimize):
    """Testing the worker in 'optimize' mode with scipy.minimize mock."""
    # Simulation du retour de minimize
    mock_res = MagicMock()
    mock_res.x = np.array([1.1, 0.9])
    mock_res.success = True
    mock_res.message = "Optimization terminated successfully."
    mock_minimize.return_value = mock_res

    params = FieldParamsDTO(
        n1_rs=[2.1], n2_rs=[1.46], nSub_rs=[1.52], n_supers=[1.0],
        l0=1064.0, lambda_calcs=[1064.0], emp_factors=[1.0, 1.0],
        seuil_int_1=0.5, seuil_int_2=0.5, alpha=10.0, maxiter=5
    )
    req = FieldWorkerRequest(action="optimize", params=params)
    worker = FieldWorkerThread(req)
    
    result_container = []
    worker.signals.finished.connect(lambda res: result_container.append(res))
    
    worker.run()
    
    assert mock_minimize.called, "scipy.minimize doit être appelé"
    assert len(result_container) == 1
    res = result_container[0]
    assert res.success is True
    # We check that the result returns the optimized factors
    assert res.opt_emp_factors == [1.1, 0.9]
    assert res.opt_metrics is not None

def test_field_worker_optimize_integration():
    """REAL (non-mocked) integration test of the L-BFGS-B optimization."""
    params = FieldParamsDTO(
        n1_rs=[2.1], n2_rs=[1.46], nSub_rs=[1.52], n_supers=[1.0],
        l0=1064.0, lambda_calcs=[1064.0], emp_factors=[1.0], # 1 seule couche pour aller vite
        seuil_int_1=0.5, seuil_int_2=0.5, alpha=10.0, maxiter=5
    )
    req = FieldWorkerRequest(action="optimize", params=params)
    worker = FieldWorkerThread(req)
    
    result_container = []
    worker.signals.finished.connect(lambda res: result_container.append(res))
    
    worker.run()
    
    assert len(result_container) == 1
    res = result_container[0]
    assert res.opt_emp_factors is not None
    assert len(res.opt_emp_factors) == 1
    #We verify that L-BFGS-B has respected the limits [0.01, 5.0]
    assert 0.01 <= res.opt_emp_factors[0] <= 5.0

def test_field_worker_optimize_global_integration():
    """Real integration test for global optimization by PGLOBAL."""
    params = FieldParamsDTO(
        n1_rs=[2.1], n2_rs=[1.46], nSub_rs=[1.52], n_supers=[1.0],
        l0=1064.0, lambda_calcs=[1064.0], emp_factors=[1.0],
        seuil_int_1=0.5, seuil_int_2=0.5, alpha=10.0, maxiter=5,
        global_opt=True
    )
    req = FieldWorkerRequest(action="optimize", params=params)
    worker = FieldWorkerThread(req)
    
    result_container = []
    worker.signals.finished.connect(lambda res: result_container.append(res))
    
    worker.run()
    
    assert len(result_container) == 1
    res = result_container[0]
    assert res.opt_emp_factors is not None
    assert len(res.opt_emp_factors) == 1
    assert 0.01 <= res.opt_emp_factors[0] <= 5.0


# ---------------------------------------------------------
# TESTS VERIFICATION & EXTRA COVERAGE
# ---------------------------------------------------------
def test_get_layer_properties_from_list_empty():
    from certus.core.certus_field_core import get_layer_properties_from_list
    res_indices, res_ep = get_layer_properties_from_list(2.0, 1.5, [], None, 1000.0)
    assert len(res_indices) == 0
    assert len(res_ep) == 0

    res_indices, res_ep = get_layer_properties_from_list(2.0, 1.5, [1.0], None, -10.0)
    assert len(res_indices) == 0
    assert len(res_ep) == 0

def test_get_layer_properties_from_list_mismatched():
    from certus.core.certus_field_core import get_layer_properties_from_list
    # mismatched layer_types length should fall back to default alternating
    res_indices, res_ep = get_layer_properties_from_list(2.0, 1.5, [1.0, 2.0], [0], 1000.0)
    assert len(res_indices) == 2
    assert np.isclose(res_indices[0].real, 2.0)
    assert np.isclose(res_indices[1].real, 1.5)

def test_calculate_electric_field_empty():
    from certus.core.certus_field_core import calculate_electric_field
    z, e2, ep, integrals, averages = calculate_electric_field(2.0, 1.5, 1.5, 1000.0, 1000.0, [])
    assert len(z) == 1
    assert z[0] == 0
    assert len(e2) == 1
    assert e2[0] == 1
    assert len(ep) == 0
    assert len(integrals) == 0
    assert len(averages) == 0

def test_certus_field_app_ui_lifecycle():
    from certus.ui.certus_field_ui import CertusFieldApp
    app_window = CertusFieldApp()
    assert app_window is not None
    assert "CERTUS" in app_window.windowTitle()
    # test basic widget availability
    assert app_window.plot_widget is not None
    assert app_window.spectral_plot_widget is not None
    assert app_window.profile_plot_widget is not None
    # Verify chk_min_field is present in the UI
    assert app_window.chk_min_field is not None
    app_window.close()

def test_top_level_objective_function_active_field_minimization():
    """Checks continuous cost calculation in active field minimization mode."""
    from certus.workers.certus_field_workers import top_level_objective_function

    #Standard cost with min_field_active=False
    cost_standard = top_level_objective_function(
        [1.0, 1.0],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=10.0,
        seuil_int_2=10.0,
        alpha=2.0,
        integral_points=50,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
        min_field_active=False
    )
    assert cost_standard > 0.0

    #Active cost with min_field_active=True
    cost_active = top_level_objective_function(
        [1.0, 1.0],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=10.0,
        seuil_int_2=10.0,
        alpha=2.0,
        integral_points=50,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
        min_field_active=True
    )
    assert cost_active > cost_standard

def test_field_smart_cleanup():
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    from certus.ui.certus_field_ui import CertusFieldApp
    app = CertusFieldApp()
    table = app.table_layers
    table.blockSignals(True)
    table.setRowCount(0)
    
    table.insertRow(0)
    table.setItem(0, 0, QTableWidgetItem("H"))
    table.setItem(0, 1, QTableWidgetItem("1.0000"))
    table.setItem(0, 2, QTableWidgetItem("100.0"))
    
    table.insertRow(1)
    table.setItem(1, 0, QTableWidgetItem("H"))
    table.setItem(1, 1, QTableWidgetItem("0.5000"))
    table.setItem(1, 2, QTableWidgetItem("50.0"))
    
    table.insertRow(2)
    table.setItem(2, 0, QTableWidgetItem("L"))
    table.setItem(2, 1, QTableWidgetItem("0.0001"))
    table.setItem(2, 2, QTableWidgetItem("0.01"))
    table.blockSignals(False)
    
    removed = app.smart_cleanup(table)
    assert removed == 2
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "H"
    assert float(table.item(0, 1).text()) == 1.5
    app.close()

def test_field_worker_needle():
    from certus.workers.certus_field_workers import FieldWorkerThread
    from certus.workers.certus_field_workers_dto import FieldWorkerRequest, FieldParamsDTO
    
    params = FieldParamsDTO(
        emp_factors=[2.0, 2.0],
        layer_types=[0, 1],
        n1_rs=[2.0],
        n2_rs=[1.5],
        nSub_rs=[1.5],
        l0=1000.0,
        seuil_int_1=10.0,
        seuil_int_2=10.0,
        alpha=2.0,
        integral_points=5,
        n_supers=[1.0],
        lambda_calcs=[1000.0],
    )
    
    worker = FieldWorkerThread(FieldWorkerRequest(action="needle", params=params))
    
    results = []
    def on_finished(res):
        results.append(res)
        
    worker.signals.finished.connect(on_finished)
    worker.run()
    
    assert len(results) == 1
    res = results[0]
    assert res.success is True
    assert res.opt_emp_factors is not None
    assert res.opt_layer_types is not None


def test_field_synthesis_loop_callbacks():
    """Verify that CertusFieldApp executes the Needle synthesis loop state machine."""
    from certus.ui.certus_field_ui import CertusFieldApp
    from certus.workers.certus_field_workers_dto import FieldWorkerResult
    
    app = CertusFieldApp()
    app.chk_allow_growth.setChecked(True)
    
    # Mock _start_worker to prevent actual thread launch
    start_calls = []
    def dummy_start(req):
        start_calls.append(req)
    app._start_worker = dummy_start
    
    # 1. Start optimization
    app.on_opt_clicked()
    
    assert app._synthesis_active is True
    assert app._synthesis_best_cost == float('inf')
    assert app._synthesis_checkpoint is not None
    assert len(start_calls) == 1
    assert start_calls[-1].action == "optimize"
    
    # Simulate first optimize worker finish (with success)
    app.worker = MagicMock()
    app.worker.request.action = "optimize"
    
    # Set mock cost return values
    app._compute_cost = MagicMock(return_value=0.5)
    
    # Mock result
    result1 = FieldWorkerResult(
        success=True,
        opt_emp_factors=[1.2, 1.2],
        opt_layer_types=[0, 1],
        message="Optimize step 1 done"
    )
    
    app.on_worker_finished(result1)
    
    # Verify that cost (0.5) < inf, so it saved checkpoint and started needle
    assert app._synthesis_best_cost == 0.5
    assert app._synthesis_checkpoint["cost"] == 0.5
    assert app._synthesis_checkpoint["emp_factors"] == [1.2, 1.2]
    assert len(start_calls) == 2
    assert start_calls[-1].action == "needle"
    
    # Simulate needle worker finish with successful insertion
    app.worker = MagicMock()
    app.worker.request.action = "needle"
    
    result2 = FieldWorkerResult(
        success=True,
        opt_emp_factors=[1.2, 0.0001, 1.2],
        opt_layer_types=[0, 1, 0],
        message="Needle found insertion"
    )
    
    app.on_worker_finished(result2)
    
    # Verify that layer count increased, so it queued optimize worker
    assert len(start_calls) == 3
    assert start_calls[-1].action == "optimize"
    
    # Simulate second optimize worker finish with no improvement
    app.worker = MagicMock()
    app.worker.request.action = "optimize"
    
    # Cost did not improve (e.g. 0.6 > 0.5)
    app._compute_cost = MagicMock(return_value=0.6)
    
    result3 = FieldWorkerResult(
        success=True,
        opt_emp_factors=[1.2, 0.01, 1.2],
        opt_layer_types=[0, 1, 0],
        message="Optimize step 2 done"
    )
    
    # Mock revert to verify it is called
    app._revert_to_synthesis_checkpoint = MagicMock()
    
    app.on_worker_finished(result3)
    
    # Verify synthesis is stopped and reverted
    assert app._synthesis_active is False
    assert app._revert_to_synthesis_checkpoint.called
    assert app.btn_opt.isEnabled() is True
    assert hasattr(app.progress_widget, "detail_label")
    assert app.progress_widget.detail_label.text().startswith("Status:")
    
    app.close()


def test_field_pareto_front():
    """Verify Pareto Front recording, UI initialization, loading, and clearing."""
    from certus.ui.certus_field_ui import CertusFieldApp
    from unittest.mock import MagicMock
    
    app = CertusFieldApp()
    
    assert app.pareto_history == {}
    assert app.pareto_window is None
    
    # 1. Update Pareto record
    app._update_pareto_record([1.0, 1.0, 1.0], 0.25)
    
    assert 3 in app.pareto_history
    rec = app.pareto_history[3]
    assert rec["best_cost"] == 0.25
    assert rec["emp_rmse"] == [1.0, 1.0, 1.0]
    
    # 2. Ensure Pareto UI lazily initializes
    assert app._ensure_pareto_ui() is True
    assert app.pareto_window is not None
    assert app.pareto_table.rowCount() == 1
    
    # 3. Simulate double clicking to load design
    app._restore_pareto_champion = MagicMock()
    app.on_calc_clicked = MagicMock()
    
    # Double-click column 1 (Best Cost)
    app._load_pareto_design(0, 1)
    app._restore_pareto_champion.assert_called_with([1.0, 1.0, 1.0], [0, 1, 0])
    
    # 4. Clear Pareto
    app._clear_pareto()
    assert app.pareto_history == {}
    assert app.pareto_table.rowCount() == 0
    
    app.close()


def test_certus_field_app_reset():
    """Verify that reset_to_defaults correctly resets the UI elements and layers in CertusFieldApp."""
    from certus.ui.certus_field_ui import CertusFieldApp
    app = CertusFieldApp()
    
    # Mutate values away from default
    app.combo_mat_H.setCurrentText("SiO2")
    app.edit_l0.setValue(500.0)
    app.edit_seuil1.setValue(10.0)
    app.table_layers.setRowCount(3)
    
    # Call reset bypass confirmation
    from certus.utils.certus_reset_framework import reset_app_to_defaults
    reset_app_to_defaults(app, confirm=False)
    
    # Assert reset to defaults
    assert app.combo_mat_H.currentText() == "H800-Nb2O5"
    assert app.edit_l0.value() == 1064.0
    assert app.edit_seuil1.value() == 3.0
    assert app.table_layers.rowCount() == 9
    
    app.close()

