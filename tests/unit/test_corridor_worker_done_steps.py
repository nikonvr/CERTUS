"""`_on_worker_done` hands three of its steps to methods of their own (audit v2, plan S5.2).

`_on_worker_done` is what the index-spline window runs when any of its workers is done: 379 lines, complexity 72. Three blocks come out of it:

    _settle_a_run_that_returned_no_result_dict   the worker came back without a dictionary: the manual dialog is freed, the run buttons are reset, the reason is logged
    _log_the_result_dictionary_received          a result dictionary came back: two log lines, a thickness trace and one structured JSON event, only when the window has a logger
    _hand_the_result_to_the_manual_dialog        a manual pipeline stage is done: the dialog shows the mesh that was applied, adopts the knots and the substrate offset, and keeps the best configuration

Pinned here without a fit and without Qt: the window is a namespace, the dialog a recorder that shares one timeline with the logger.
"""

from __future__ import annotations

import inspect
import math
from types import SimpleNamespace

import numpy as np
import pytest

from certus.spline import certus_index_spline_corridor_worker as module
from certus.spline.certus_index_spline_corridor_ui import ManualSigmaKnotDialog
from certus.spline.certus_index_spline_corridor_worker import _CorridorWorkerMixin

ROLES = ("manual_sigma_insert", "manual_autoshift", "manual_auto_add_one", "manual_auto_clean", "manual_repartition_log", "manual_repartition_sigma")


class Logger:
    """Records every call as (level, message, args) on a timeline that the dialog and the traces may share."""

    def __init__(self, timeline: list | None = None) -> None:
        self.timeline = [] if timeline is None else timeline

    def info(self, msg, *args) -> None:
        self.timeline.append(("info", msg, args))

    def warning(self, msg, *args) -> None:
        self.timeline.append(("warning", msg, args))

    def exception(self, msg, *args) -> None:
        self.timeline.append(("exception", msg, args))

    def calls(self, level: str) -> list[tuple]:
        return [entry for entry in self.timeline if isinstance(entry, tuple) and entry[0] == level]


class Dialog(ManualSigmaKnotDialog):
    """A manual-knot dialog that only records what it is told: no Qt object stands behind it (the base `__init__` is not called)."""

    def __init__(self, timeline: list | None = None, base=(), requested=(), explode_on_adopt: bool = False) -> None:
        self.timeline = [] if timeline is None else timeline
        self._base_sigma_knots = np.asarray(base, dtype=np.float64)
        self.requested = np.asarray(requested, dtype=np.float64)
        self.explode_on_adopt = explode_on_adopt

    def set_runtime_busy(self, busy) -> None:
        self.timeline.append(("busy", busy))

    def append_runtime_log(self, text) -> None:
        self.timeline.append(("log", text))

    def selected_sigma_knots(self):
        return self.requested

    def adopt_sigma_knots(self, knots) -> None:
        if self.explode_on_adopt:
            raise RuntimeError("boom")
        self.timeline.append(("knots", [float(k) for k in knots]))

    def adopt_delta_ns(self, value) -> None:
        self.timeline.append(("delta_ns", value))

    def set_runtime_progress(self, percent, text) -> None:
        self.timeline.append(("progress", percent, text))

    def set_runtime_metrics(self, d_nm, rmse) -> None:
        self.timeline.append(("metrics", d_nm, rmse))

    def update_best_config(self, result, knots) -> None:
        self.timeline.append(("best", result, [float(k) for k in knots]))


# --- _settle_a_run_that_returned_no_result_dict ----------------------------------------------------------------------------------------


class Widget:
    def __init__(self, name: str, events: list) -> None:
        self.name = name
        self.events = events

    def setText(self, text) -> None:
        self.events.append((self.name, text))

    def setEnabled(self, enabled) -> None:
        self.events.append((self.name, enabled))


def settle(result, role="main", dialog=None, logger=None):
    events: list = []
    app = SimpleNamespace(
        logger=logger,
        _worker_role="main",
        lbl_status=Widget("status", events),
        btn_run=Widget("run", events),
        btn_stop=Widget("stop", events),
        _refresh_post_optimization_option_controls=lambda: events.append("refresh"),
    )
    _CorridorWorkerMixin._settle_a_run_that_returned_no_result_dict(app, result, role, ROLES, dialog)
    return app, events


def test_a_run_without_a_result_dict_resets_the_window_and_refreshes_the_controls_last():
    app, events = settle(None)
    assert events == [("status", "Canceled or no result (dict)"), ("run", True), ("stop", False), "refresh"]
    assert app._worker_role == "idle"


@pytest.mark.parametrize("role", ROLES)
def test_a_manual_pipeline_role_frees_its_dialog(role):
    dialog = Dialog()
    settle(None, role=role, dialog=dialog)
    assert dialog.timeline == [("busy", False), ("log", "Re-optimization finished without usable result.")]


@pytest.mark.parametrize(
    ("role", "dialog"),
    [("main", Dialog()), ("corridors", Dialog()), ("manual_sigma_insert", None), ("manual_sigma_insert", object())],
    ids=["another role", "the corridors role", "no dialog", "something that is not a dialog"],
)
def test_nothing_else_touches_a_dialog_nor_needs_one(role, dialog):
    _app, events = settle(None, role=role, dialog=dialog)
    assert events[-1] == "refresh"
    if isinstance(dialog, Dialog):
        assert dialog.timeline == []


def test_a_missing_result_is_logged_with_its_usual_causes():
    logger = Logger()
    settle(None, logger=logger)
    ((level, message, args),) = logger.timeline
    assert level == "warning"
    assert message.startswith("[INDEX_SPLINE.GUI] worker finished without a result dictionary")
    assert "Stop button during calculation" in message
    assert args == ()


@pytest.mark.parametrize("result", [[], [1, 2], "text", 0], ids=["empty list", "list", "str", "zero"])
def test_a_result_of_the_wrong_type_is_logged_by_its_type_even_when_it_is_falsy(result):
    logger = Logger()
    settle(result, logger=logger)
    assert logger.timeline == [("warning", "[INDEX_SPLINE.GUI] worker returned %s instead of a result dictionary - result ignored", (type(result).__name__,))]


def test_the_reason_is_logged_before_the_controls_are_refreshed():
    timeline: list = []
    logger = Logger(timeline)
    app = SimpleNamespace(
        logger=logger,
        lbl_status=Widget("status", timeline),
        btn_run=Widget("run", timeline),
        btn_stop=Widget("stop", timeline),
        _refresh_post_optimization_option_controls=lambda: timeline.append("refresh"),
    )
    _CorridorWorkerMixin._settle_a_run_that_returned_no_result_dict(app, None, "main", ROLES, None)
    assert [entry if isinstance(entry, str) else entry[0] for entry in timeline][-2:] == ["warning", "refresh"]


# --- _log_the_result_dictionary_received -----------------------------------------------------------------------------------------------


@pytest.fixture
def traces(monkeypatch):
    seen = SimpleNamespace(d_trace=[], events=[], timeline=[])

    def d_trace(logger, text, d_nm, **kwargs):
        seen.timeline.append("d_trace")
        seen.d_trace.append((logger, text, d_nm, kwargs))

    def event(logger, *args, **kwargs):
        seen.timeline.append("event")
        seen.events.append((logger, args, kwargs))

    monkeypatch.setattr(module, "log_index_spline_d_trace", d_trace)
    monkeypatch.setattr(module, "log_structured_json_event", event)
    return seen


def receive(traces, result, role="main", worker="solver", split=False, logger="new"):
    logger = Logger() if logger == "new" else logger
    app = SimpleNamespace(logger=logger, _result_uses_split_mesh=lambda res: split)
    _CorridorWorkerMixin._log_the_result_dictionary_received(app, result, role, worker)
    return logger


def first_line(logger):
    return next(entry for entry in logger.calls("info") if "result dictionary received" in entry[1])


def details_line(logger):
    return next(entry for entry in logger.calls("info") if "worker details" in entry[1])


def test_without_a_logger_nothing_is_read_and_nothing_is_logged(traces):
    receive(traces, "not even a dict", logger=None)
    assert traces.timeline == []


def test_the_first_line_gives_the_rmse_the_thickness_the_role_the_worker_and_the_operation(traces):
    logger = receive(traces, {"mse": 4e-6, "d_nm": 1234.5, "op_id": 12})
    _level, _message, args = first_line(logger)
    assert args[0] == pytest.approx(0.002)
    assert args[1:5] == (1234.5, "main", "solver", "12")
    assert args[5] == ""


def test_a_negative_mse_gives_a_zero_rmse_and_a_result_without_figures_gives_a_nan_thickness(traces):
    logger = receive(traces, {"mse": -1e-6})
    args = first_line(logger)[2]
    assert args[0] == 0.0
    assert math.isnan(args[1])
    assert first_line(receive(traces, {}))[2][0] == 0.0


def test_a_result_without_an_operation_id_says_n_a(traces):
    assert first_line(receive(traces, {}))[2][4] == "n/a"


def test_the_pipeline_watermark_is_added_when_it_is_finite(traces):
    logger = receive(traces, {"pipeline_best_rmse_watermark": 0.0015, "pipeline_best_rmse_stage": "stage 2"})
    assert first_line(logger)[2][5] == " | pipeline watermark (best RMSE seen during run): 0.001500 (@ stage 2)"


@pytest.mark.parametrize("watermark", [None, float("nan"), float("inf")], ids=["none", "nan", "inf"])
def test_no_watermark_hint_without_a_finite_watermark(traces, watermark):
    logger = receive(traces, {"pipeline_best_rmse_watermark": watermark, "pipeline_best_rmse_stage": "stage 2"})
    assert first_line(logger)[2][5] == ""


def test_the_thickness_trace_names_the_role_and_the_worker(traces):
    logger = receive(traces, {"d_nm": 1234.5, "op_id": 7}, role="rmse_grid", worker="grid_worker")
    assert traces.d_trace == [
        (logger, "[INDEX_SPLINE.GUI] worker result received | role=rmse_grid|worker=grid_worker | op_id=7", 1234.5, {"detail": "worker=grid_worker"})
    ]


def test_an_unknown_worker_leaves_the_role_bare_in_the_trace(traces):
    logger = receive(traces, {"d_nm": 1.0}, role="main", worker="?")
    assert traces.d_trace == [(logger, "[INDEX_SPLINE.GUI] worker result received | role=main | op_id=n/a", 1.0, {"detail": "worker=?"})]


@pytest.mark.parametrize(
    ("continuous", "adaptive", "flags"),
    [(1, 0, (True, False)), (0, "yes", (False, True)), (1, "yes", (True, True)), (0, None, (False, False))],
    ids=["continuous only", "adaptive only", "both", "neither"],
)
def test_the_details_line_reads_the_mesh_kind_from_the_window_and_the_flags_from_the_result(traces, continuous, adaptive, flags):
    logger = receive(traces, {"mse": 2e-6, "continuous_model": continuous, "adaptive_mesh": adaptive}, split=1)
    _level, message, args = details_line(logger)
    assert message == "[INDEX_SPLINE.GUI] worker details | mse=%.6e | split=%s | continuous=%s | adaptive=%s"
    assert args == (2e-6, True, *flags)


def test_the_details_line_defaults_are_a_nan_mse_and_false_flags(traces):
    args = details_line(receive(traces, {}))[2]
    assert math.isnan(args[0])
    assert args[1:] == (False, False, False)


def test_the_structured_event_carries_every_figure(traces):
    logger = receive(traces, {"mse": 4e-6, "d_nm": 1234.5, "op_id": 12, "continuous_model": 1, "adaptive_mesh": 0}, role="main", worker="solver", split=True)
    assert len(traces.events) == 1
    event_logger, args, kwargs = traces.events[0]
    assert event_logger is logger
    assert args == ("AUTO_BEST_JSON", "worker_done")
    assert kwargs.pop("rmse") == pytest.approx(0.002)
    assert kwargs == {
        "role": "main",
        "worker": "solver",
        "op_id": "12",
        "mse": 4e-6,
        "rmse_convention": "sqrt(max(mse,0))",
        "d_nm": 1234.5,
        "split": True,
        "continuous": True,
        "adaptive": False,
    }


def test_the_structured_event_defaults_to_a_nan_mse_and_thickness_and_a_zero_rmse(traces):
    receive(traces, {})
    kwargs = traces.events[0][2]
    assert math.isnan(kwargs["mse"])
    assert math.isnan(kwargs["d_nm"])
    assert kwargs["rmse"] == 0.0


def test_the_four_records_come_in_the_order_received_trace_details_event(traces):
    receive(traces, {"mse": 1e-6}, logger=Logger(traces.timeline))
    kinds = []
    for entry in traces.timeline:
        if isinstance(entry, str):
            kinds.append(entry)
        else:
            kinds.append("received" if "result dictionary received" in entry[1] else "details")
    assert kinds == ["received", "d_trace", "details", "event"]


# --- _hand_the_result_to_the_manual_dialog ---------------------------------------------------------------------------------------------


def manual_window(logger=None, metrics=(1700.5, 0.00091), raw_rmse=0.00091, timeline=None):
    timeline = [] if timeline is None else timeline
    return SimpleNamespace(
        logger=logger,
        _runtime_metrics_from_result_dict=lambda display: metrics,
        _refresh_manual_dialog_preview=lambda dialog, display: timeline.append(("preview", display)),
        _summarize_manual_mesh_change=lambda before, after: {"after_sigma_knots": np.asarray(after, dtype=np.float64)},
        _manual_mesh_change_log_line=lambda label, summary: f"{label} K={summary['after_sigma_knots'].size}",
        _rmse_from_result_dict=lambda result: raw_rmse,
    )


def hand(result, display=None, role="manual_sigma_insert", dialog=None, with_logger=False, **window_changes):
    dialog = Dialog(base=[1.0, 2.0, 3.0], requested=[1.0, 3.0]) if dialog is None else dialog
    logger = Logger(dialog.timeline) if with_logger else None
    app = manual_window(logger=logger, timeline=dialog.timeline, **window_changes)
    _CorridorWorkerMixin._hand_the_result_to_the_manual_dialog(app, result, role, ROLES, dialog, {} if display is None else display)
    return dialog.timeline


def test_a_whole_manual_stage_frees_the_dialog_shows_the_mesh_and_ends_with_the_metrics():
    result = {"sigma_knots": [1.0, 3.0]}
    display = {"sigma_knots": [9.0]}
    assert hand(result, display) == [
        ("busy", False),
        ("preview", display),
        ("log", "Requested mesh K=2"),
        ("log", "Applied mesh K=2"),
        ("knots", [1.0, 3.0]),
        ("progress", 100.0, "Re-optimisation terminee"),
        ("metrics", 1700.5, 0.00091),
        ("log", "Re-optimisation terminee | RMSE=0.000910"),
        ("best", result, [1.0, 3.0]),
    ]


def test_the_preview_is_refreshed_with_the_display_not_with_the_raw_result():
    result, display = {"sigma_knots": [1.0, 3.0]}, {"sigma_knots": [1.0, 3.0], "marker": True}
    preview = next(entry for entry in hand(result, display) if entry[0] == "preview")
    assert preview[1] is display


@pytest.mark.parametrize(
    ("role", "dialog"),
    [("main", Dialog()), ("corridors", Dialog()), ("manual_sigma_insert", None), ("manual_sigma_insert", object())],
    ids=["another role", "the corridors role", "no dialog", "something that is not a dialog"],
)
def test_other_roles_and_missing_dialogs_are_left_alone(role, dialog):
    logger = Logger()
    app = manual_window(logger=logger)
    _CorridorWorkerMixin._hand_the_result_to_the_manual_dialog(app, {"sigma_knots": [1.0]}, role, ROLES, dialog, {})
    assert logger.timeline == []  # a stage run on something that is no dialog would be caught and logged by the crash guard
    if isinstance(dialog, Dialog):
        assert dialog.timeline == []


@pytest.mark.parametrize("role", ROLES)
def test_every_manual_pipeline_role_is_handed_to_the_dialog(role):
    assert hand({"sigma_knots": [1.0, 3.0]}, role=role)[0] == ("busy", False)


WARNING = ("log", "Worker returned a different mesh than requested; keeping the applied mesh below.")


@pytest.mark.parametrize(
    ("applied", "warns"),
    [
        ([1.0, 3.0], False),
        ([1.0, 3.0 + 1e-15], False),
        ([1.0, 3.0, 4.0], True),
        ([1.0, 3.5], True),
        ([1.0, 3.0 + 1e-6], True),
    ],
    ids=["same mesh", "same within the tolerance", "other size", "other knot", "a knot moved by one part in three million"],
)
def test_a_mesh_that_differs_from_the_request_is_flagged_between_the_requested_and_the_applied_lines(applied, warns):
    timeline = hand({"sigma_knots": applied})
    assert (WARNING in timeline) is warns
    if warns:
        logs = [entry for entry in timeline if entry[0] == "log"]
        assert logs[1] == WARNING
        assert logs[0][1].startswith("Requested")
        assert logs[2][1].startswith("Applied")


def test_a_tiny_knot_difference_is_still_a_difference():
    dialog = Dialog(base=[1e-4, 1e-3], requested=[5e-4, 1e-3])
    assert WARNING in hand({"sigma_knots": [5e-4 + 1e-9, 1e-3]}, dialog=dialog)


def test_without_knots_in_the_result_the_display_knots_are_applied_but_not_kept_as_best():
    timeline = hand({}, {"sigma_knots": [2.0, 4.0]})
    assert ("knots", [2.0, 4.0]) in timeline
    assert not any(entry[0] == "best" for entry in timeline)


def test_without_knots_anywhere_nothing_is_adopted_and_nothing_is_kept():
    timeline = hand({}, {})
    assert [entry[0] for entry in timeline if entry[0] in ("knots", "best")] == []
    assert ("log", "Applied mesh K=0") in timeline


@pytest.mark.parametrize(
    ("result", "display", "expected"),
    [
        ({"substrate_n_offset": 0.25}, {"substrate_n_offset": 0.5}, 0.25),
        ({}, {"substrate_n_offset": 0.5}, 0.5),
        ({"substrate_n_offset": 0}, {"substrate_n_offset": 0.5}, 0.0),
    ],
    ids=["the result's offset wins", "the display's offset is the fallback", "a zero offset is still an offset"],
)
def test_the_substrate_offset_is_adopted_as_a_float_after_the_knots(result, display, expected):
    timeline = hand({"sigma_knots": [1.0, 3.0], **result}, display)
    names = [entry[0] for entry in timeline]
    delta = timeline[names.index("delta_ns")]
    assert delta == ("delta_ns", expected)
    assert isinstance(delta[1], float)
    assert names.index("knots") < names.index("delta_ns") < names.index("progress")


def test_without_a_substrate_offset_none_is_adopted():
    assert "delta_ns" not in [entry[0] for entry in hand({"sigma_knots": [1.0, 3.0]}, {})]


@pytest.mark.parametrize(
    ("rmse", "text"),
    [(0.00091, "0.000910"), (float("nan"), "n/a"), (float("inf"), "n/a")],
    ids=["finite", "nan", "inf"],
)
def test_the_final_line_prints_a_finite_rmse_with_six_decimals_and_n_a_otherwise(rmse, text):
    timeline = hand({"sigma_knots": [1.0, 3.0]}, metrics=(1700.5, rmse))
    assert ("log", f"Re-optimisation terminee | RMSE={text}") in timeline
    metrics = next(entry for entry in timeline if entry[0] == "metrics")
    assert metrics[1] == 1700.5
    assert metrics[2] == rmse or (math.isnan(rmse) and math.isnan(metrics[2]))


def test_the_logger_hears_which_mesh_was_applied_just_before_the_best_configuration_is_kept():
    timeline = hand({"sigma_knots": [1.0, 3.0]}, with_logger=True)
    info = ("info", "[INDEX_SPLINE.GUI] manual pipeline applied mesh | role=%s | %s", ("manual_sigma_insert", "applied K=2"))
    assert info in timeline
    kinds = [entry[0] for entry in timeline]
    assert kinds.index("info") == kinds.index("best") - 1
    assert timeline[kinds.index("info") - 1][0] == "log"


def test_without_a_logger_the_stage_is_silent():
    assert not any(entry[0] in ("info", "warning", "exception") for entry in hand({"sigma_knots": [1.0, 3.0]}))


def test_the_best_configuration_is_kept_from_the_raw_result_and_its_raw_knots():
    result = {"sigma_knots": [1.0, 3.0], "marker": "raw"}
    best = next(entry for entry in hand(result, {"sigma_knots": [7.0, 8.0]}) if entry[0] == "best")
    assert best[1] is result
    assert best[2] == [1.0, 3.0]


def test_a_best_configuration_without_a_finite_rmse_is_not_kept():
    assert not any(entry[0] == "best" for entry in hand({"sigma_knots": [1.0, 3.0]}, raw_rmse=float("nan")))
    assert not any(entry[0] == "best" for entry in hand({"sigma_knots": [1.0, 3.0]}, raw_rmse=float("inf")))


def test_a_failing_dialog_is_logged_with_its_traceback_and_the_window_goes_on():
    dialog = Dialog(base=[1.0, 2.0, 3.0], requested=[1.0, 3.0], explode_on_adopt=True)
    timeline = hand({"sigma_knots": [1.0, 3.0]}, dialog=dialog, with_logger=True)
    ((_, message, args),) = [entry for entry in timeline if entry[0] == "exception"]
    assert message == "INDEX_SPLINE [CRASH GUARD] manual dialog finalization failed: %s\n%s"
    assert args[0] == "RuntimeError"
    assert "RuntimeError: boom" in args[1]
    assert not any(entry[0] in ("progress", "metrics", "best") for entry in timeline)


def test_a_failing_dialog_without_a_logger_is_swallowed_silently():
    dialog = Dialog(base=[1.0, 2.0, 3.0], requested=[1.0, 3.0], explode_on_adopt=True)
    timeline = hand({"sigma_knots": [1.0, 3.0]}, dialog=dialog)
    assert not any(entry[0] in ("progress", "metrics", "best") for entry in timeline)


# --- the handler hands them their work -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        "self._settle_a_run_that_returned_no_result_dict(result, role, manual_pipeline_roles, manual_dlg)",
        "self._log_the_result_dictionary_received(result, role, worker_name)",
        "self._hand_the_result_to_the_manual_dialog(result, role, manual_pipeline_roles, manual_dlg, display)",
    ],
)
def test_the_handler_calls_each_step_with_the_values_it_computed(call):
    assert call in inspect.getsource(_CorridorWorkerMixin._on_worker_done)


def test_the_handler_returns_right_after_settling_a_run_without_a_dict():
    source = inspect.getsource(_CorridorWorkerMixin._on_worker_done)
    settle_call = "self._settle_a_run_that_returned_no_result_dict(result, role, manual_pipeline_roles, manual_dlg)"
    assert source[source.index(settle_call) + len(settle_call) :].lstrip().startswith("return")
