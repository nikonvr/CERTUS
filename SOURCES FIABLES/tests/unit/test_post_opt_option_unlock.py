from __future__ import annotations

from types import SimpleNamespace as _RealSimpleNamespace

class _Harness(_RealSimpleNamespace):
    @staticmethod
    def _format_post_optimization_status(display, fallback_result=None):
        return "mocked_status"

    @staticmethod
    def _result_uses_split_mesh(result):
        return False

    @staticmethod
    def _prepare_worker_restart(self):
        pass

    @staticmethod
    def _rmse_from_result_dict(result):
        return float(result.get("rmse", float("nan")))

    @staticmethod
    def _runtime_metrics_from_result_dict(display):
        return 0.0, 0.0

    @staticmethod
    def _summarize_manual_mesh_change(b, r):
        return "mesh_change"

    @staticmethod
    def _manual_mesh_change_log_line(label, summary):
        return f"{label}: {summary}"

    @staticmethod
    def _post_optimization_ready_status(status_text):
        return f"Ready: {status_text}"

SimpleNamespace = _Harness
from unittest.mock import MagicMock

import numpy as np

import CERTUS_INDEX_SPLINE as spline_gui
from CERTUS_INDEX_SPLINE import CertusIndexSplineApp


class _Toggle:
    def __init__(self, checked: bool = True) -> None:
        self._checked = bool(checked)
        self.enabled_states: list[bool] = []

    def isChecked(self) -> bool:
        return self._checked

    def setEnabled(self, enabled: bool) -> None:
        self.enabled_states.append(bool(enabled))


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = str(text)


def test_post_opt_option_controls_are_locked_before_first_result() -> None:
    app = SimpleNamespace(
        _last_result=None,
        _worker_role="idle",
        btn_manual_knots_toggle=_Toggle(True),
        btn_corridor_toggle=_Toggle(True),
        chk_corridor_d=_Toggle(True),
        lbl_corridors_run_state=_Label(),
        lbl_corridors_state_adv=_Label(),
        lbl_corridors_tab_state=_Label(),
        _refresh_corridors_gui_state_labels=lambda: CertusIndexSplineApp._refresh_corridors_gui_state_labels(app),
    )

    CertusIndexSplineApp._refresh_post_optimization_option_controls(app)

    assert app.btn_manual_knots_toggle.enabled_states[-1] is False
    assert app.btn_corridor_toggle.enabled_states[-1] is False
    assert app.chk_corridor_d.enabled_states[-1] is False
    assert "available after optimization" in app.lbl_corridors_run_state.text


def test_post_opt_option_controls_unlock_after_result_when_idle() -> None:
    app = SimpleNamespace(
        _last_result={"rmse": 1e-3},
        _worker_role="idle",
        btn_manual_knots_toggle=_Toggle(True),
        btn_corridor_toggle=_Toggle(True),
        chk_corridor_d=_Toggle(True),
        lbl_corridors_run_state=_Label(),
        lbl_corridors_state_adv=_Label(),
        lbl_corridors_tab_state=_Label(),
        _refresh_corridors_gui_state_labels=lambda: CertusIndexSplineApp._refresh_corridors_gui_state_labels(app),
    )

    CertusIndexSplineApp._refresh_post_optimization_option_controls(app)

    assert app.btn_manual_knots_toggle.enabled_states[-1] is True
    assert app.btn_corridor_toggle.enabled_states[-1] is True
    assert app.chk_corridor_d.enabled_states[-1] is False
    assert "ready to launch" in app.lbl_corridors_run_state.text


def test_corridor_state_label_reports_completed_when_profile_exists() -> None:
    app = SimpleNamespace(
        _last_result={"profile_d_enabled": True},
        btn_corridor_toggle=_Toggle(True),
        lbl_corridors_run_state=_Label(),
        lbl_corridors_state_adv=_Label(),
        lbl_corridors_tab_state=_Label(),
    )

    CertusIndexSplineApp._refresh_corridors_gui_state_labels(app)

    assert "already computed" in app.lbl_corridors_run_state.text


def test_worker_done_non_dict_restores_idle_and_unlocks_post_opt_controls(monkeypatch) -> None:
    monkeypatch.setattr(spline_gui, "uninstall_skeleton", lambda *_args, **_kwargs: None)
    app = SimpleNamespace(
        _last_result={"rmse": 1e-3},
        _worker_role="main",
        _worker=None,
        logger=None,
        tabs_main=object(),
        lbl_status=_Label(),
        btn_run=_Toggle(True),
        btn_stop=_Toggle(True),
        btn_manual_knots_toggle=_Toggle(True),
        btn_corridor_toggle=_Toggle(True),
        chk_corridor_d=_Toggle(True),
        lbl_corridors_run_state=_Label(),
        lbl_corridors_state_adv=_Label(),
        lbl_corridors_tab_state=_Label(),
        _is_rmse_d_grid_worker_finalize_dict=CertusIndexSplineApp._is_rmse_d_grid_worker_finalize_dict,
        _refresh_corridors_gui_state_labels=lambda: CertusIndexSplineApp._refresh_corridors_gui_state_labels(app),
        _refresh_post_optimization_option_controls=lambda: CertusIndexSplineApp._refresh_post_optimization_option_controls(app),
    )

    CertusIndexSplineApp._on_worker_done(app, None)

    assert app._worker_role == "idle"
    assert app.btn_run.enabled_states[-1] is True
    assert app.btn_stop.enabled_states[-1] is False
    assert app.btn_manual_knots_toggle.enabled_states[-1] is True
    assert app.btn_corridor_toggle.enabled_states[-1] is True


def test_curve_minimum_deep_non_dict_refreshes_post_opt_controls(monkeypatch) -> None:
    monkeypatch.setattr(spline_gui.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    app = SimpleNamespace(
        _last_result={"rmse": 1e-3},
        _worker_role="curve_min_deep",
        logger=None,
        lbl_status=_Label(),
        btn_run=_Toggle(True),
        btn_stop=_Toggle(True),
        btn_manual_knots_toggle=_Toggle(True),
        btn_corridor_toggle=_Toggle(True),
        chk_corridor_d=_Toggle(True),
        lbl_corridors_run_state=_Label(),
        lbl_corridors_state_adv=_Label(),
        lbl_corridors_tab_state=_Label(),
        _refresh_corridors_gui_state_labels=lambda: CertusIndexSplineApp._refresh_corridors_gui_state_labels(app),
        _refresh_post_optimization_option_controls=lambda: CertusIndexSplineApp._refresh_post_optimization_option_controls(app),
    )

    CertusIndexSplineApp._finish_curve_minimum_deep_worker_done(app, None)

    assert app._worker_role == "idle"
    assert app.btn_run.enabled_states[-1] is True
    assert app.btn_stop.enabled_states[-1] is False
    assert app.btn_manual_knots_toggle.enabled_states[-1] is True
    assert app.btn_corridor_toggle.enabled_states[-1] is True


def test_result_uses_split_mesh_detects_split_from_x_encoding() -> None:
    assert CertusIndexSplineApp._result_uses_split_mesh({"x_encoding": "split_sigma_free_knots"}) is True
    assert CertusIndexSplineApp._result_uses_split_mesh({"x_encoding": "xi_n_mono"}) is False


def test_format_post_optimization_status_uses_polish_iters_label_when_only_nit_polish_present() -> None:
    status = CertusIndexSplineApp._format_post_optimization_status(
        {"mse": 4.0e-6, "d_nm": 1715.95, "rmse_fit_lambda_nm": (250.0, 5000.0), "nit_polish": 336},
        None,
    )

    assert "iters [cubic-spline-sigma-polish]=336" in status


def test_format_post_optimization_status_prefers_solver_eval_count_when_available() -> None:
    status = CertusIndexSplineApp._format_post_optimization_status(
        {"mse": 4.0e-6, "d_nm": 1715.95, "rmse_fit_lambda_nm": (250.0, 5000.0), "nit_total": 674},
        {"nit_polish": 336},
    )

    assert "evals [global optimizer]=674" in status


def test_continue_corridor_auto_refine_after_deep_reruns_corridors_without_free_node_stage() -> None:
    calls: list[dict] = []
    seed = {"rmse": 1e-3, "d_nm": 3000.0}
    app = SimpleNamespace(
        _corridor_auto_refine_plan={"stage": "deep", "rerun_corridor": True, "origin": "corridor"},
        _manual_postprocess_seed_result=lambda: dict(seed),
        _start_deferred_corridor_worker=lambda result: calls.append(dict(result)) or True,
        logger=None,
    )

    restarted = CertusIndexSplineApp._continue_corridor_auto_refine_after_deep(app)

    assert restarted is True
    assert app._corridor_auto_refine_plan is None
    assert calls == [seed]


def test_continue_corridor_auto_refine_after_deep_ignores_legacy_stage_flags() -> None:
    calls: list[dict] = []
    seed = {"rmse": 1e-3, "d_nm": 3000.0}
    app = SimpleNamespace(
        _corridor_auto_refine_plan={"stage": "deep", "rerun_corridor": True, "origin": "corridor"},
        _last_run_cfg=SimpleNamespace(legacy_stage_enabled=True, legacy_auto_enabled=True),
        _manual_postprocess_seed_result=lambda: dict(seed),
        _start_deferred_corridor_worker=lambda result: calls.append(dict(result)) or True,
        logger=None,
    )

    restarted = CertusIndexSplineApp._continue_corridor_auto_refine_after_deep(app)

    assert restarted is True
    assert app._corridor_auto_refine_plan is None
    assert calls == [seed]


def test_corridor_grid_skips_adoption_when_coverage_incomplete() -> None:
    merged: list[dict] = []
    auto_refine_calls: list[tuple[dict, bool, str]] = []
    logger = MagicMock()
    app = SimpleNamespace(
        _worker_role="rmse_grid",
        btn_run=_Toggle(True),
        btn_stop=_Toggle(True),
        lbl_status=_Label(),
        logger=logger,
        _last_result={"rmse": 0.01, "d_nm": 3000.0},
        _last_worker_result=None,
        _corridor_rmse_requested_grid=np.array([], dtype=np.float64),
        _set_corridor_grid_busy=lambda busy: None,
        _plot_corridor_rmse_tab=lambda upd: None,
        _set_corridor_grid_progress_ui=lambda **kwargs: None,
        _set_corridor_grid_completed_badge=lambda: None,
        _merge_rmse_grid_promotion_into_nominal=lambda promoted, adoption_log_tag: merged.append(dict(promoted)),
        _schedule_corridor_auto_refine=lambda seed, rerun_corridor, origin: auto_refine_calls.append(
            (dict(seed), bool(rerun_corridor), str(origin))
        ) or True,
        _rmse_from_result_dict=CertusIndexSplineApp._rmse_from_result_dict,
    )
    result = {
        "profile_d_values_nm": np.asarray([2999.0, 3000.0, 3001.0], dtype=np.float64),
        "profile_d_rmse_values": np.asarray([0.003, 0.002, 0.001], dtype=np.float64),
        "profile_d_manual_grid_total_points": 3,
        "profile_d_manual_grid_base_done_points": 3,
        "profile_d_manual_grid_extra_done_points": 0,
        "profile_d_manual_grid_breakpoint_count": 0,
        "profile_d_manual_grid_extra_points": 0,
        "profile_d_manual_grid_global_opt_runs": 1,
        "profile_d_manual_grid_global_opt_improved": 1,
        "profile_d_manual_grid_best_global_rmse": 0.0009,
        "profile_d_manual_grid_elapsed_ms": 12.0,
        "profile_d_manual_grid_best_global_result": {"rmse": 0.0009, "d_nm": 3001.0},
        "profile_d_manual_grid_curve_minimum_result": {"rmse": 0.0010, "d_nm": 3001.0},
        "profile_d_manual_grid_curve_beats_nominal": True,
        "profile_d_manual_grid_curve_vs_nominal_delta_rmse": -0.009,
        "profile_d_manual_grid_coverage_complete": False,
    }

    CertusIndexSplineApp._finish_corridor_rmse_d_grid_worker_done(app, result)

    assert merged == []
    assert auto_refine_calls == []
    logger.error.assert_called()
    assert app._worker_role == "idle"
