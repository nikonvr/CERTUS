from __future__ import annotations

import numpy as np

from certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog


def _make_dialog(qapp):
    _ = qapp
    return ManualSigmaKnotDialog(
        sigma_knots=np.asarray([1.0 / 2200.0, 1.0 / 1400.0, 1.0 / 800.0], dtype=np.float64),
        lam_model_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0], dtype=np.float64),
        y_model=np.asarray([0.8, 0.78, 0.74, 0.7], dtype=np.float64),
        lam_measurement_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0], dtype=np.float64),
        y_measurement=np.asarray([0.81, 0.79, 0.73, 0.69], dtype=np.float64),
        y_label="T",
    )


def test_dialog_go_disabled_until_row_added(qapp) -> None:
    dlg = _make_dialog(qapp)

    assert dlg.btn_go.text() == "Local re-optimization"
    assert dlg.btn_skip.text() == "Keep current result"
    assert dlg.btn_go.isEnabled() is True
    assert dlg.selected_lambda_knots() == [800.0, 1400.0, 2200.0]

    dlg.add_lambda_knot(1500.0)

    assert dlg.btn_go.isEnabled() is True
    assert dlg.selected_lambda_knots() == [800.0, 1400.0, 1500.0, 2200.0]


def test_dialog_selected_sigma_knots_are_sorted(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1800.0)
    dlg.add_lambda_knot(1000.0)

    sigma = dlg.selected_sigma_knots()

    assert np.all(np.diff(sigma) >= 0.0)
    assert np.allclose(sigma, np.sort([1.0 / 2200.0, 1.0 / 1400.0, 1.0 / 800.0, 1.0 / 1800.0, 1.0 / 1000.0]))


def test_dialog_marks_duplicate_existing_knot_invalid(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1400.0)

    assert dlg._is_selection_valid() is False
    assert dlg.btn_go.isEnabled() is False


def test_dialog_add_lambda_from_plot_x_adds_row(qapp) -> None:
    dlg = _make_dialog(qapp)

    ok = dlg._add_lambda_from_plot_x(1333.0)

    assert ok is True
    assert dlg.selected_lambda_knots() == [800.0, 1333.0, 1400.0, 2200.0]


def test_dialog_rows_and_preview_lines_stay_aligned_after_unsorted_add(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1800.0)
    dlg.add_lambda_knot(1000.0)

    row_values = [float(row.spin.value()) for row in dlg._row_widgets]
    line_values = [float(row.preview_line.value()) for row in dlg._row_widgets if row.preview_line is not None]

    assert row_values == [800.0, 1000.0, 1400.0, 1800.0, 2200.0]
    assert line_values == row_values


def test_dialog_drag_line_updates_spin_value(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1500.0)
    row = next(r for r in dlg._row_widgets if abs(float(r.spin.value()) - 1500.0) < 1e-9)
    assert row.preview_line is not None

    row.preview_line.setValue(1725.0)
    dlg._on_line_position_changed(row)

    assert abs(float(row.spin.value()) - 1725.0) < 1e-9
    assert dlg.selected_lambda_knots() == [800.0, 1400.0, 1725.0, 2200.0]


def test_dialog_spin_update_moves_preview_line(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1500.0)
    row = next(r for r in dlg._row_widgets if abs(float(r.spin.value()) - 1500.0) < 1e-9)
    assert row.preview_line is not None

    row.spin.setValue(1610.0)

    assert abs(float(row.preview_line.value()) - 1610.0) < 1e-9


def test_dialog_remove_nearest_lambda_knot_removes_matching_row(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1500.0)
    dlg.add_lambda_knot(1800.0)

    ok = dlg._remove_nearest_lambda_knot(1510.0, tolerance_nm=20.0)

    assert ok is True
    assert dlg.selected_lambda_knots() == [800.0, 1400.0, 1800.0, 2200.0]


def test_dialog_remove_nearest_lambda_knot_returns_false_when_miss(qapp) -> None:
    dlg = _make_dialog(qapp)
    dlg.add_lambda_knot(1500.0)

    ok = dlg._remove_nearest_lambda_knot(1700.0, tolerance_nm=10.0)

    assert ok is False
    assert dlg.selected_lambda_knots() == [800.0, 1400.0, 1500.0, 2200.0]


def test_dialog_preexisting_rows_are_present_with_remove_button(qapp) -> None:
    dlg = _make_dialog(qapp)

    assert len(dlg._row_widgets) == 3
    assert [float(r.spin.value()) for r in dlg._row_widgets] == [800.0, 1400.0, 2200.0]
    assert all(r.lbl_kind.text() == "Pre-existing" for r in dlg._row_widgets)


def test_dialog_delta_ns_defaults_to_zero_and_is_emitted(qapp) -> None:
    dlg = _make_dialog(qapp)
    captured: list[tuple[list[float], float]] = []

    dlg.local_apply_requested.connect(lambda knots, delta: captured.append((list(knots), float(delta))))
    dlg.spin_delta_ns.setValue(0.0125)
    dlg._on_apply_keep_open()

    assert abs(dlg.substrate_delta_ns() - 0.0125) < 1e-12
    assert captured == [([800.0, 1400.0, 2200.0], 0.0125)]


def test_dialog_local_apply_emits_reduced_mesh_after_multiple_removals(qapp) -> None:
    dlg = ManualSigmaKnotDialog(
        sigma_knots=np.asarray([1.0 / 2200.0, 1.0 / 1800.0, 1.0 / 1400.0, 1.0 / 800.0], dtype=np.float64),
        lam_model_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0, 2200.0], dtype=np.float64),
        y_model=np.asarray([0.8, 0.79, 0.77, 0.73, 0.7], dtype=np.float64),
        lam_measurement_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0, 2200.0], dtype=np.float64),
        y_measurement=np.asarray([0.81, 0.8, 0.76, 0.72, 0.69], dtype=np.float64),
        y_label="T",
    )
    captured: list[tuple[list[float], float]] = []

    dlg.local_apply_requested.connect(lambda knots, delta: captured.append((list(knots), float(delta))))

    assert dlg._remove_nearest_lambda_knot(1400.0, tolerance_nm=5.0) is True
    assert dlg._remove_nearest_lambda_knot(1800.0, tolerance_nm=5.0) is True

    dlg._on_apply_keep_open()

    assert captured == [([800.0, 2200.0], 0.0)]


def test_dialog_apply_delta_button_emits_preview_signal(qapp) -> None:
    dlg = _make_dialog(qapp)
    captured: list[float] = []

    dlg.delta_preview_requested.connect(lambda delta: captured.append(float(delta)))
    dlg.spin_delta_ns.setValue(-0.004)
    dlg._on_apply_delta_preview()

    assert dlg.btn_apply_delta.text() == "Apply (Polish)"
    assert captured
    assert abs(captured[-1] - (-0.004)) < 1e-12


def test_dialog_delta_spin_change_emits_preview_signal_immediately(qapp) -> None:
    dlg = _make_dialog(qapp)
    captured: list[float] = []

    dlg.delta_preview_requested.connect(lambda delta: captured.append(float(delta)))
    dlg.spin_delta_ns.setValue(0.003)

    assert captured
    assert abs(captured[-1] - 0.003) < 1e-12


def test_dialog_update_model_preview_refreshes_visible_curve(qapp) -> None:
    dlg = _make_dialog(qapp)
    updated_y = np.asarray([0.91, 0.87, 0.82, 0.79], dtype=np.float64)

    dlg.update_model_preview(
        np.asarray([800.0, 1200.0, 1600.0, 2000.0], dtype=np.float64),
        updated_y,
    )

    x_curve, y_curve = dlg._model_curve.getData()
    assert np.allclose(np.asarray(x_curve, dtype=np.float64), [800.0, 1200.0, 1600.0, 2000.0])
    assert np.allclose(np.asarray(y_curve, dtype=np.float64), updated_y)
    assert np.allclose(dlg._y_model_preview, updated_y)


def test_dialog_adopt_sigma_knots_rebuilds_rows_as_new_baseline(qapp) -> None:
    dlg = _make_dialog(qapp)

    new_sigma = np.sort(np.asarray([1.0 / 2200.0, 1.0 / 1600.0, 1.0 / 1100.0, 1.0 / 800.0], dtype=np.float64))
    dlg.adopt_sigma_knots(new_sigma)

    assert np.allclose(dlg._base_sigma_knots, new_sigma)
    assert dlg.selected_lambda_knots() == [800.0, 1100.0, 1600.0, 2200.0]
    assert all(r.lbl_kind.text() == "Pre-existing" for r in dlg._row_widgets)


def test_dialog_update_best_config_persists_after_runtime_metrics_update(qapp) -> None:
    dlg = _make_dialog(qapp)
    result = {
        "rmse": 0.002137,
        "d_nm": 17050.0,
        "substrate_n_offset": 0.001,
    }
    sigma = np.sort(np.asarray([1.0 / 2200.0, 1.0 / 1550.0, 1.0 / 800.0], dtype=np.float64))

    # Reproduces the GUI order: runtime metrics are updated before best snapshot persistence.
    dlg.set_runtime_metrics(result["d_nm"], result["rmse"])
    dlg.update_best_config(result, sigma)

    best = dlg.get_best_config()
    assert best is not None
    best_result, best_sigma = best
    assert np.isclose(float(best_result["rmse"]), result["rmse"])
    assert np.allclose(best_sigma, sigma)
    assert dlg.btn_recall_best.isEnabled() is True


def test_dialog_update_best_config_keeps_lowest_snapshot(qapp) -> None:
    dlg = _make_dialog(qapp)
    res_worse = {"rmse": 0.002500, "d_nm": 17050.0}
    res_best = {"rmse": 0.002137, "d_nm": 17050.0}
    sigma_worse = np.sort(np.asarray([1.0 / 2200.0, 1.0 / 1500.0, 1.0 / 800.0], dtype=np.float64))
    sigma_best = np.sort(np.asarray([1.0 / 2200.0, 1.0 / 1600.0, 1.0 / 1200.0, 1.0 / 800.0], dtype=np.float64))

    dlg.update_best_config(res_worse, sigma_worse)
    dlg.update_best_config(res_best, sigma_best)

    best = dlg.get_best_config()
    assert best is not None
    best_result, best_sigma = best
    assert np.isclose(float(best_result["rmse"]), float(res_best["rmse"]))
    assert np.allclose(best_sigma, sigma_best)


def test_dialog_busy_state_enables_stop_and_emits_stop_request(qapp) -> None:
    dlg = _make_dialog(qapp)
    captured: list[str] = []

    dlg.stop_requested.connect(lambda: captured.append("stop"))
    dlg.set_runtime_busy(True)

    assert dlg.btn_stop_runtime.text() == "Cancel optimization"
    assert dlg.btn_stop_runtime.isEnabled() is True
    assert dlg.btn_skip.isEnabled() is False
    assert dlg.btn_go.isEnabled() is False
    assert dlg.spin_delta_ns.isEnabled() is False

    dlg.btn_stop_runtime.click()

    assert captured == ["stop"]
    assert "Stop requested by user..." in dlg.txt_runtime_log.toPlainText()

    dlg.set_runtime_busy(False)

    assert dlg.btn_stop_runtime.isEnabled() is False
    assert dlg.btn_skip.isEnabled() is True
    assert dlg.btn_go.isEnabled() is True
    assert dlg.spin_delta_ns.isEnabled() is True