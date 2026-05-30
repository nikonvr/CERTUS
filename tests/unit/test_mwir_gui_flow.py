from __future__ import annotations

from types import SimpleNamespace as _RealSimpleNamespace

class _Harness(_RealSimpleNamespace):
    @staticmethod
    def _format_post_optimization_status(display, fallback_result=None):
        return CertusIndexSplineApp._format_post_optimization_status(display, fallback_result)

    @staticmethod
    def _result_uses_split_mesh(result):
        return CertusIndexSplineApp._result_uses_split_mesh(result)

    @staticmethod
    def _prepare_worker_restart(self):
        pass  # safe stub since it modifies QThread/GUI state

    @staticmethod
    def _rmse_from_result_dict(result):
        return CertusIndexSplineApp._rmse_from_result_dict(result)

    @staticmethod
    def _runtime_metrics_from_result_dict(display):
        return CertusIndexSplineApp._runtime_metrics_from_result_dict(display)

    @staticmethod
    def _summarize_manual_mesh_change(b, r):
        return CertusIndexSplineApp._summarize_manual_mesh_change(b, r)

    @staticmethod
    def _manual_mesh_change_log_line(label, summary):
        return CertusIndexSplineApp._manual_mesh_change_log_line(label, summary)

    @staticmethod
    def _post_optimization_ready_status(status_text):
        return CertusIndexSplineApp._post_optimization_ready_status(status_text)

SimpleNamespace = _Harness

import numpy as np

from CERTUS_INDEX_SPLINE import CertusIndexSplineApp
from certus.ui.certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog


class _Signal:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.connections: list = []

    def connect(self, callback) -> None:
        self.connections.append(callback)

    def emit(self, *args) -> None:
        self.calls.append(args)


class _FakeWorkerSignals:
    def __init__(self) -> None:
        self.progress = _Signal()
        self.live = _Signal()
        self.finished = _Signal()
        self.error = _Signal()


class _FakeWorker:
    def __init__(self, func, *args, **kwargs) -> None:
        self.func = func
        self.args = args
        self.kwargs = dict(kwargs)  # mutable dict so _wire_worker_signals can inject progress_cb
        self.signals = _FakeWorkerSignals()
        self.started = False

    def start(self) -> None:
        self.started = True


def _make_wire_worker_signals(app_ref):
    """Minimal _wire_worker_signals that injects progress_cb into worker kwargs (mirroring production code)."""
    def _wire(progress_fn):
        app_ref._worker.kwargs["progress_cb"] = progress_fn

    return _wire


class _Toggle:
    def __init__(self) -> None:
        self.states: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:
        self.states.append(bool(enabled))


class _Label:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def setText(self, text: str) -> None:
        self.texts.append(str(text))


class _Logger:
    def __init__(self) -> None:
        self.info_calls: list[str] = []
        self.warning_calls: list[str] = []

    def info(self, msg: str, *args) -> None:
        self.info_calls.append(msg % args if args else str(msg))

    def warning(self, msg: str, *args) -> None:
        self.warning_calls.append(msg % args if args else str(msg))


class _Cfg:
    def replace(self):
        return self


def test_on_worker_done_uses_raw_result_for_manual_dialog_and_worker(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.uninstall_skeleton", lambda *_args, **_kwargs: None)

    recorded: dict[str, object] = {}
    raw_result = {"sigma_knots": [1.0, 2.0, 3.0], "mse": 1e-6, "rmse": 1e-3}
    merged_display = {
        "sigma_knots": [1.0, 1.5, 2.0, 3.0],
        "mse": 2e-6,
        "rmse": 9e-4,
        "gui_display_from_best_live": True,
    }

    app = SimpleNamespace(
        _worker_role="main",
        _auto_best_two_stage_refine=False,
        tabs_main=object(),
        lbl_status=_Label(),
        logger=None,
        _refresh_post_optimization_option_controls=lambda: None,
        _last_result=None,
        _best_live_result=None,
        _is_rmse_d_grid_worker_finalize_dict=lambda _result: False,
        _display_result_prefer_best_live=lambda _result: merged_display,
        _plot_result=lambda _display, **_kwargs: recorded.setdefault("plot", _display),
        _refresh_data_table=lambda: recorded.setdefault("refreshed", True),
        _result_needs_deferred_corridors=lambda _display: False,
        export_excel=lambda **kwargs: recorded.setdefault("export", kwargs),
        _can_offer_manual_extra_knots=lambda result: (recorded.setdefault("can_offer", result), True)[1],
        _prompt_manual_extra_knots=lambda result: (recorded.setdefault("prompt", result), [1650.0])[1],
        _start_manual_sigma_insert_worker=lambda result, lambdas, delta_ns=0.0: recorded.setdefault("start", (result, lambdas, delta_ns)),
    )

    CertusIndexSplineApp._on_worker_done(app, raw_result)

    assert app._last_result is merged_display
    assert recorded["plot"] is merged_display
    assert recorded["can_offer"] is raw_result
    assert recorded["prompt"] is raw_result
    assert recorded["start"][0] is raw_result
    assert recorded["start"][1] == [1650.0]
    assert recorded["start"][2] == 0.0


def test_on_worker_done_starts_manual_stage_before_deferred_corridors(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.uninstall_skeleton", lambda *_args, **_kwargs: None)

    recorded: dict[str, object] = {}
    raw_result = {"sigma_knots": [1.0, 2.0, 3.0], "mse": 1e-6, "rmse": 1e-3}
    logger = _Logger()

    app = SimpleNamespace(
        _worker_role="main",
        _auto_best_two_stage_refine=False,
        tabs_main=object(),
        lbl_status=_Label(),
        logger=logger,
        _refresh_post_optimization_option_controls=lambda: None,
        _last_result=None,
        _best_live_result=None,
        _worker=SimpleNamespace(func=lambda: None),
        _is_rmse_d_grid_worker_finalize_dict=lambda _result: False,
        _display_result_prefer_best_live=lambda _result: _result,
        _plot_result=lambda _display, **_kwargs: None,
        _refresh_data_table=lambda: None,
        _result_needs_deferred_corridors=lambda _display: True,
        _start_deferred_corridor_worker=lambda _display, **_kwargs: recorded.setdefault("corridor", _display),
        export_excel=lambda **_kwargs: recorded.setdefault("export", True),
        _can_offer_manual_extra_knots=lambda _result: True,
        _prompt_manual_extra_knots=lambda _result: [1650.0],
        _start_manual_sigma_insert_worker=lambda result, lambdas, delta_ns=0.0: recorded.setdefault("manual", (result, lambdas, delta_ns)),
    )

    CertusIndexSplineApp._on_worker_done(app, raw_result)

    assert recorded["manual"][0] is raw_result
    assert recorded["manual"][1] == [1650.0]
    assert recorded["manual"][2] == 0.0
    assert "corridor" not in recorded
    assert "export" not in recorded
    assert any(
        "Manual extra-knot stage available after optimization; this stage runs before deferred corridors." in msg
        for msg in logger.info_calls
    )
    assert any(
        "Manual extra-knot stage accepted; deferred corridors are postponed until manual insertion completes." in msg
        for msg in logger.info_calls
    )


def test_on_worker_done_skips_second_manual_prompt_after_manual_completion(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.uninstall_skeleton", lambda *_args, **_kwargs: None)

    recorded: dict[str, object] = {}
    manual_result = {"sigma_knots": [1.0, 1.5, 2.0, 3.0], "mse": 8e-7, "rmse": 9e-4}

    app = SimpleNamespace(
        _worker_role="manual_auto_clean",
        _auto_best_two_stage_refine=False,
        tabs_main=object(),
        lbl_status=_Label(),
        logger=None,
        _refresh_post_optimization_option_controls=lambda: None,
        _last_result=None,
        _best_live_result=None,
        _is_rmse_d_grid_worker_finalize_dict=lambda _result: False,
        _display_result_prefer_best_live=lambda _result: _result,
        _plot_result=lambda _display, **_kwargs: None,
        _refresh_data_table=lambda: None,
        _result_needs_deferred_corridors=lambda _display: True,
        _start_deferred_corridor_worker=lambda display, **_kwargs: recorded.setdefault("corridor", display) or True,
        export_excel=lambda **_kwargs: recorded.setdefault("export", True),
        _can_offer_manual_extra_knots=lambda _result: False,
        _prompt_manual_extra_knots=lambda _result: None,
        _start_manual_sigma_insert_worker=lambda *_args, **_kwargs: recorded.setdefault("manual", True),
    )

    CertusIndexSplineApp._on_worker_done(app, manual_result)

    assert "corridor" not in recorded
    assert "manual" not in recorded
    assert "export" in recorded
    assert "Available actions: Manual knots / Corridors" in app.lbl_status.texts[-1]


def test_start_manual_sigma_insert_worker_scales_progress_to_ui_range(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.GenericWorker", _FakeWorker)
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.install_skeleton", lambda *_args, **_kwargs: None)

    app = SimpleNamespace(
        _last_run_cfg=object(),
        _worker=None,
        logger=None,
        tabs_main=object(),
        _cleanup_thread=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        _on_progress=lambda *_args, **_kwargs: None,
        _on_live_update=lambda *_args, **_kwargs: None,
        _on_worker_done=lambda *_args, **_kwargs: None,
        _on_worker_err=lambda *_args, **_kwargs: None,
        _baseline_substrate_n_for_result=lambda *_args, **_kwargs: None,
        btn_run=_Toggle(),
        btn_stop=_Toggle(),
        lbl_status=_Label(),
        _prog_reset_bar=lambda: None,
        _set_worker_running_state=lambda _running: None,
    )
    app._wire_worker_signals = _make_wire_worker_signals(app)
    result = {"sigma_knots": [1.0, 2.0], "rmse": 1e-3}

    CertusIndexSplineApp._start_manual_sigma_insert_worker(app, result, [1000.0])

    assert isinstance(app._worker, _FakeWorker)
    assert app._worker.started is True
    assert np.allclose(app._worker.kwargs["target_sigma_knots"], [0.001])

    progress_cb = app._worker.kwargs["progress_cb"]
    progress_cb(12.5, "phase")

    assert app._worker.signals.progress.calls
    last_pct, last_msg = app._worker.signals.progress.calls[-1]
    assert last_pct == 1250
    assert "phase" in last_msg


def test_start_manual_sigma_insert_worker_passes_multiple_knots_as_sorted_sigma(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.GenericWorker", _FakeWorker)
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.install_skeleton", lambda *_args, **_kwargs: None)

    app = SimpleNamespace(
        _last_run_cfg=object(),
        _worker=None,
        logger=None,
        tabs_main=object(),
        _cleanup_thread=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        _on_progress=lambda *_args, **_kwargs: None,
        _on_live_update=lambda *_args, **_kwargs: None,
        _on_worker_done=lambda *_args, **_kwargs: None,
        _on_worker_err=lambda *_args, **_kwargs: None,
        _baseline_substrate_n_for_result=lambda *_args, **_kwargs: None,
        btn_run=_Toggle(),
        btn_stop=_Toggle(),
        lbl_status=_Label(),
        _prog_reset_bar=lambda: None,
        _set_worker_running_state=lambda _running: None,
    )
    app._wire_worker_signals = _make_wire_worker_signals(app)
    result = {"sigma_knots": [1.0, 2.0], "rmse": 1e-3}

    CertusIndexSplineApp._start_manual_sigma_insert_worker(app, result, [3000.0, 1650.0, 1000.0])

    assert isinstance(app._worker, _FakeWorker)
    assert app._worker.started is True
    assert np.allclose(app._worker.kwargs["target_sigma_knots"], [1.0 / 3000.0, 1.0 / 1650.0, 1.0 / 1000.0])


def test_build_manual_repartition_target_sigma_knots_log_uses_geometric_spacing_at_current_k() -> None:
    selected_lambda = [3000.0, 1650.0, 1000.0]

    target = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(selected_lambda, mode="log")

    assert target.size == len(selected_lambda)
    assert np.all(np.diff(target) > 0.0)
    assert np.isclose(float(target[0]), 1.0 / 3000.0)
    assert np.isclose(float(target[-1]), 1.0 / 1000.0)
    ratios = target[1:] / target[:-1]
    assert np.allclose(ratios, ratios[0])


def test_build_manual_repartition_target_sigma_knots_sigma_uses_linear_spacing_at_current_k() -> None:
    selected_lambda = [3000.0, 1650.0, 1000.0, 800.0]

    target = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(selected_lambda, mode="sigma")

    assert target.size == len(selected_lambda)
    assert np.all(np.diff(target) > 0.0)
    assert np.isclose(float(target[0]), 1.0 / 3000.0)
    assert np.isclose(float(target[-1]), 1.0 / 800.0)
    diffs = np.diff(target)
    assert np.allclose(diffs, diffs[0])


def test_start_manual_sigma_repartition_worker_uses_current_selected_k_not_result_k(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.GenericWorker", _FakeWorker)
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.install_skeleton", lambda *_args, **_kwargs: None)

    app = SimpleNamespace(
        _last_run_cfg=object(),
        _worker=None,
        logger=None,
        tabs_main=object(),
        _stop_event=None,
        _cleanup_thread=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        _on_progress=lambda *_args, **_kwargs: None,
        _on_live_update=lambda *_args, **_kwargs: None,
        _on_worker_done=lambda *_args, **_kwargs: None,
        _on_worker_err=lambda *_args, **_kwargs: None,
        _baseline_substrate_n_for_result=lambda *_args, **_kwargs: None,
        btn_run=_Toggle(),
        btn_stop=_Toggle(),
        lbl_status=_Label(),
        _prog_reset_bar=lambda: None,
        _set_worker_running_state=lambda _running: None,
    )
    app._wire_worker_signals = _make_wire_worker_signals(app)
    result = {"sigma_knots": [0.2, 0.4, 0.6, 0.8, 1.0], "rmse": 1e-3}
    selected_lambda = [3000.0, 1650.0, 1000.0]

    CertusIndexSplineApp._start_manual_sigma_repartition_worker(
        app,
        result,
        selected_lambda,
        0.0,
        mode="log",
    )

    assert isinstance(app._worker, _FakeWorker)
    assert app._worker.started is True
    assert app._worker_role == "manual_repartition_log"
    target_sigma = np.asarray(app._worker.kwargs["target_sigma_knots"], dtype=np.float64)
    assert target_sigma.size == len(selected_lambda)
    assert target_sigma.size != len(result["sigma_knots"])
    ratios = target_sigma[1:] / target_sigma[:-1]
    assert np.allclose(ratios, ratios[0])


def test_start_deferred_corridor_worker_logs_after_stage(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.GenericWorker", _FakeWorker)

    logger = _Logger()
    app = SimpleNamespace(
        _last_run_cfg=_Cfg(),
        _worker=None,
        _worker_role="manual_sigma_insert",
        _stop_event=None,
        _cfg_with_result_substrate=lambda cfg, _result: cfg,
        _cleanup_thread=lambda: None,
        _on_progress=lambda *_args, **_kwargs: None,
        _on_corridor_rmse_grid_live_update=lambda *_args, **_kwargs: None,
        _on_worker_done=lambda *_args, **_kwargs: None,
        _on_worker_err=lambda *_args, **_kwargs: None,
        _rmse_from_result_dict=lambda result: float(result.get("rmse", float("nan"))),
        _prog_reset_bar=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        btn_run=_Toggle(),
        btn_stop=_Toggle(),
        lbl_status=_Label(),
        logger=logger,
    )
    result = {"d_nm": 123.4, "rmse": 1.2e-3}

    ok = CertusIndexSplineApp._start_deferred_corridor_worker(app, result)

    assert ok is True
    cfg_used = app._worker.args[0]
    assert getattr(cfg_used, "corridor_profile_d_enabled") is True
    assert any(
        "launching deferred corridor worker | after_stage=manual_sigma_insert" in msg
        for msg in logger.info_calls
    )


def test_start_deferred_corridor_worker_sets_standard_base_mode(monkeypatch) -> None:
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.GenericWorker", _FakeWorker)

    logger = _Logger()
    app = SimpleNamespace(
        _last_run_cfg=_Cfg(),
        _worker=None,
        _worker_role="manual_sigma_insert",
        _stop_event=None,
        _cfg_with_result_substrate=lambda cfg, _result: cfg,
        _cleanup_thread=lambda: None,
        _on_progress=lambda *_args, **_kwargs: None,
        _on_corridor_rmse_grid_live_update=lambda *_args, **_kwargs: None,
        _on_worker_done=lambda *_args, **_kwargs: None,
        _on_worker_err=lambda *_args, **_kwargs: None,
        _rmse_from_result_dict=lambda result: float(result.get("rmse", float("nan"))),
        _prog_reset_bar=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        btn_run=_Toggle(),
        btn_stop=_Toggle(),
        lbl_status=_Label(),
        logger=logger,
    )
    result = {"d_nm": 123.4, "rmse": 1.2e-3}

    ok = CertusIndexSplineApp._start_deferred_corridor_worker(app, result)

    assert ok is True
    cfg_used = app._worker.args[0]
    assert getattr(cfg_used, "corridor_profile_d_enabled") is True
    assert app.lbl_status.texts[-1] == "Corridors: calculation in progress..."


def test_manual_corridor_button_uses_raw_last_worker_result() -> None:
    recorded: dict[str, object] = {}
    raw_result = {"rmse": 1e-3, "d_nm": 123.4}

    app = SimpleNamespace(
        _last_worker_result=raw_result,
        _last_result={"rmse": 2e-3, "d_nm": 999.0},
        logger=None,
        _manual_postprocess_seed_result=lambda: CertusIndexSplineApp._manual_postprocess_seed_result(app),
        _start_deferred_corridor_worker=lambda result, **kwargs: recorded.setdefault("launch", (result, kwargs)) or True,
    )

    CertusIndexSplineApp._on_btn_corridor_clicked(app)

    assert recorded["launch"][0] is raw_result
    assert recorded["launch"][1] == {}


def test_manual_knots_button_uses_raw_last_worker_result() -> None:
    recorded: dict[str, object] = {}
    raw_result = {"rmse": 1e-3, "d_nm": 123.4, "sigma_knots": [1.0, 2.0, 3.0]}

    app = SimpleNamespace(
        _last_worker_result=raw_result,
        _last_result={"rmse": 2e-3, "d_nm": 999.0, "sigma_knots": [1.0, 2.0, 3.0]},
        logger=None,
        _manual_postprocess_seed_result=lambda: CertusIndexSplineApp._manual_postprocess_seed_result(app),
        _can_offer_manual_extra_knots=lambda result: recorded.setdefault("offer", result) is raw_result,
        _open_manual_extra_knots_dialog=lambda result: recorded.setdefault("open", result),
    )

    CertusIndexSplineApp._on_btn_manual_knots_clicked(app)

    assert recorded["offer"] is raw_result
    assert recorded["open"] is raw_result


def test_manual_knots_button_skips_relaunch_when_dialog_cancelled() -> None:
    recorded: dict[str, object] = {}
    raw_result = {"rmse": 1e-3, "d_nm": 123.4, "sigma_knots": [1.0, 2.0, 3.0]}
    logger = _Logger()

    app = SimpleNamespace(
        _last_worker_result=raw_result,
        _last_result={"rmse": 2e-3, "d_nm": 999.0, "sigma_knots": [1.0, 2.0, 3.0]},
        logger=logger,
        _manual_postprocess_seed_result=lambda: CertusIndexSplineApp._manual_postprocess_seed_result(app),
        _can_offer_manual_extra_knots=lambda _result: True,
        _open_manual_extra_knots_dialog=lambda result: recorded.setdefault("open", result),
    )

    CertusIndexSplineApp._on_btn_manual_knots_clicked(app)

    assert recorded["open"] is raw_result
    assert "launch" not in recorded
    assert logger.info_calls == []


def test_curve_minimum_deep_refit_does_not_auto_start_corridors() -> None:
    recorded: dict[str, object] = {}
    result = {"sigma_knots": [1.0, 2.0, 3.0], "mse": 1e-6, "rmse": 1e-3, "d_nm": 123.4}

    app = SimpleNamespace(
        _worker_role="curve_min_deep",
        btn_run=SimpleNamespace(setEnabled=lambda enabled: recorded.setdefault("run", []).append(bool(enabled))),
        btn_stop=SimpleNamespace(setEnabled=lambda enabled: recorded.setdefault("stop", []).append(bool(enabled))),
        lbl_status=_Label(),
        logger=None,
        _last_worker_result=None,
        _last_result=None,
        _corridor_rmse_manual_active=True,
        _corridor_rmse_manual_lo=1.0,
        _corridor_rmse_manual_hi=2.0,
        _display_result_prefer_best_live=lambda payload: payload,
        _plot_result=lambda display, **_kwargs: recorded.setdefault("plot", display),
        _refresh_data_table=lambda: recorded.setdefault("refreshed", True),
        _refresh_post_optimization_option_controls=lambda: recorded.setdefault("controls", True),
        _result_needs_deferred_corridors=lambda _display: recorded.setdefault("corridor_check", True),
        _start_deferred_corridor_worker=lambda display, **kwargs: recorded.setdefault("corridor_launch", (display, kwargs)),
        export_excel=lambda **kwargs: recorded.setdefault("export", kwargs),
    )

    CertusIndexSplineApp._finish_curve_minimum_deep_worker_done(app, result)

    assert app._worker_role == "idle"
    assert app._last_worker_result == result
    assert app._last_result is result
    assert recorded["plot"] is result
    assert recorded["refreshed"] is True
    assert recorded["controls"] is True
    assert recorded["export"] == {"auto_export": True}
    assert "Available actions: Manual knots / Corridors" in app.lbl_status.texts[-1]
    assert "corridor_check" not in recorded
    assert "corridor_launch" not in recorded


def test_on_live_update_routes_corridor_profile_only_payload_to_rmse_live_handler() -> None:
    recorded: dict[str, object] = {}
    payload = {
        "profile_d_status": "manual_grid_live",
        "profile_d_values_nm": np.asarray([1999.5, 2000.0], dtype=np.float64),
        "profile_d_rmse_values": np.asarray([0.0013, 0.0011], dtype=np.float64),
    }

    app = SimpleNamespace(
        _on_corridor_rmse_grid_live_update=lambda live_payload: recorded.setdefault("payload", live_payload),
    )

    CertusIndexSplineApp._on_live_update(app, payload)

    assert recorded["payload"] is payload


def test_on_worker_done_manual_dialog_logs_requested_and_applied_mesh(monkeypatch, qapp) -> None:
    _ = qapp
    monkeypatch.setattr("CERTUS_INDEX_SPLINE.uninstall_skeleton", lambda *_args, **_kwargs: None)

    dialog = ManualSigmaKnotDialog(
        sigma_knots=np.asarray([1.0 / 2200.0, 1.0 / 1800.0, 1.0 / 1400.0, 1.0 / 800.0], dtype=np.float64),
        lam_model_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0, 2200.0], dtype=np.float64),
        y_model=np.asarray([0.8, 0.79, 0.77, 0.73, 0.7], dtype=np.float64),
        lam_measurement_nm=np.asarray([800.0, 1200.0, 1600.0, 2000.0, 2200.0], dtype=np.float64),
        y_measurement=np.asarray([0.81, 0.8, 0.76, 0.72, 0.69], dtype=np.float64),
        y_label="T",
    )
    assert dialog._remove_nearest_lambda_knot(1400.0, tolerance_nm=5.0) is True
    assert dialog._remove_nearest_lambda_knot(1800.0, tolerance_nm=5.0) is True

    result = {
        "sigma_knots": np.sort(np.asarray([1.0 / 2200.0, 1.0 / 800.0], dtype=np.float64)),
        "rmse": 0.00091,
        "mse": 0.00091**2,
        "d_nm": 1700.5,
        "lam_nm": np.asarray([800.0, 1200.0, 1600.0, 2000.0, 2200.0], dtype=np.float64),
        "t_theo": np.asarray([0.8, 0.79, 0.77, 0.73, 0.7], dtype=np.float64),
    }

    app = SimpleNamespace(
        _worker_role="manual_sigma_insert",
        _auto_best_two_stage_refine=False,
        tabs_main=object(),
        lbl_status=_Label(),
        logger=None,
        _last_result=None,
        _last_worker_result=None,
        _best_live_result=None,
        _worker=SimpleNamespace(func=lambda: None),
        _corridor_auto_refine_plan=None,
        _is_rmse_d_grid_worker_finalize_dict=lambda _result: False,
        _display_result_prefer_best_live=lambda _result: _result,
        _plot_result=lambda *_args, **_kwargs: None,
        _refresh_data_table=lambda: None,
        _refresh_post_optimization_option_controls=lambda: None,
        _can_offer_manual_extra_knots=lambda _result: False,
        export_excel=lambda **_kwargs: None,
        _manual_knots_dialog=dialog,
    )
    app._refresh_manual_dialog_preview = lambda dlg, preview: CertusIndexSplineApp._refresh_manual_dialog_preview(app, dlg, preview)

    CertusIndexSplineApp._on_worker_done(app, result)

    runtime_text = dialog.txt_runtime_log.toPlainText()
    assert "Requested mesh | K 4->2 (Delta -2)" in runtime_text
    assert "Applied mesh | K 4->2 (Delta -2)" in runtime_text
    assert "removed=2 [1400.0, 1800.0]" in runtime_text