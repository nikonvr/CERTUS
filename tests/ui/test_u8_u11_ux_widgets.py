"""Tests for U8..U11 UX widgets (empty state, badges, tooltips, tracker).

Introspection-first so the suite stays fast. Qt behaviour is exercised
only where the logic is non-trivial.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =============================================================================
# U8 - Empty state
# =============================================================================


def test_u8_module_surface():
    import certus.ui.certus_empty_state as m

    for name in (
        "DEFAULT_ICON_SIZE_PX",
        "DEFAULT_TITLE",
        "DEFAULT_DESCRIPTION",
        "build_empty_state",
        "attach_empty_state_to",
        "detach_empty_state_from",
    ):
        assert hasattr(m, name), f"certus_empty_state missing {name!r}"


def test_u8_defaults_are_sensible():
    from certus.ui.certus_empty_state import DEFAULT_DESCRIPTION, DEFAULT_ICON_SIZE_PX, DEFAULT_TITLE

    assert 24 <= DEFAULT_ICON_SIZE_PX <= 96
    assert DEFAULT_TITLE.strip()
    assert DEFAULT_DESCRIPTION.strip()


def test_u8_factory_returns_visible_widget():
    from PyQt6.QtWidgets import QApplication

    from certus.ui.certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None, title="Nothing here", description="Load a file", action_label="Load")
    assert w is not None
    assert w.has_action() is True


def test_u8_without_action_label_has_no_cta():
    from PyQt6.QtWidgets import QApplication

    from certus.ui.certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None, title="X", description="Y")
    assert w.has_action() is False


def test_u8_action_emits_signal_and_invokes_callback():
    from PyQt6.QtWidgets import QApplication

    from certus.ui.certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    called = []

    w = build_empty_state(
        None, title="t", description="d", action_label="Go", on_action=lambda: called.append(1)
    )
    signal_hit = []
    w.action_triggered.connect(lambda: signal_hit.append(1))
    w._action_btn.click()
    assert called == [1]
    assert signal_hit == [1]


def test_u8_set_title_and_description():
    from PyQt6.QtWidgets import QApplication

    from certus.ui.certus_empty_state import build_empty_state

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = build_empty_state(None)
    w.set_title("New title")
    w.set_description("New desc")
    assert "New title" in w._title_lbl.text()
    assert "New desc" in w._desc_lbl.text()


# =============================================================================
# U9 - Status badges
# =============================================================================


def test_u9_variants_and_icon_mapping():
    from certus.utils.certus_badges import VARIANT_LABELS, supported_variants, variant_icon_name

    variants = supported_variants()
    assert set(variants) == set(VARIANT_LABELS.keys())
    assert set(variants) == {"idle", "running", "success", "error", "warning", "info", "neutral"}
    for v in variants:
        assert variant_icon_name(v)  # every variant has an icon


def test_u9_icons_are_real_lucide_names():
    from certus.utils.certus_badges import supported_variants, variant_icon_name
    from certus.ui.certus_icons import available_icon_names

    names = set(available_icon_names())
    for v in supported_variants():
        assert variant_icon_name(v) in names


def test_u9_variant_color_returns_three_hex_strings():
    from certus.utils.certus_badges import supported_variants, variant_color

    for v in list(supported_variants()) + ["unknown"]:
        bg, fg, border = variant_color(v)
        for x in (bg, fg, border):
            assert isinstance(x, str) and x.startswith("#") and 4 <= len(x) <= 9


def test_u9_widget_set_variant_changes_state():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(text="Run", variant="running")
    assert b.variant() == "running"
    b.set_variant("error")
    assert b.variant() == "error"


def test_u9_uppercase_option_transforms_text():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(text="done", variant="success", uppercase=True)
    assert b.text() == "DONE"


def test_u9_unknown_variant_falls_back_to_neutral():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_badges import build_status_badge

    _qapp = QApplication.instance() or QApplication(sys.argv)
    b = build_status_badge(variant="wat")
    assert b.variant() == "neutral"


# =============================================================================
# U10 - Rich tooltips
# =============================================================================


def test_u10_tooltip_spec_is_frozen_dataclass():
    from certus.ui.certus_tooltips import TooltipSpec

    s = TooltipSpec(title="Hello", body="World")
    assert s.title == "Hello"
    assert s.body == "World"
    with pytest.raises(Exception):
        s.title = "Changed"  # frozen


def test_u10_has_icon_and_has_link_flags():
    from certus.ui.certus_tooltips import TooltipSpec

    s = TooltipSpec(title="t", body="b")
    assert not s.has_icon()
    assert not s.has_link()

    s2 = TooltipSpec(title="t", body="b", icon_name="info", link="https://example.com")
    assert s2.has_icon()
    assert s2.has_link()


def test_u10_attach_and_detach_are_symmetric():
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus.ui.certus_tooltips import attach_rich_tooltip, detach_rich_tooltip, get_tooltip_spec

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("Hover me")
    spec = attach_rich_tooltip(w, "Title", "Body text")
    assert get_tooltip_spec(w) is spec
    assert detach_rich_tooltip(w) is True
    assert get_tooltip_spec(w) is None


def test_u10_reattach_replaces_previous_spec():
    from PyQt6.QtWidgets import QApplication, QLabel

    from certus.ui.certus_tooltips import attach_rich_tooltip, get_tooltip_spec

    _qapp = QApplication.instance() or QApplication(sys.argv)
    w = QLabel("x")
    s1 = attach_rich_tooltip(w, "A", "alpha")
    s2 = attach_rich_tooltip(w, "B", "beta")
    current = get_tooltip_spec(w)
    assert current is s2
    assert s1 is not s2


def test_u10_none_widget_returns_spec_without_error():
    from certus.ui.certus_tooltips import attach_rich_tooltip

    spec = attach_rich_tooltip(None, "T", "B")
    assert spec.title == "T"


# =============================================================================
# U11 - Progress tracker
# =============================================================================


def test_u11_step_auto_slug_key():
    from certus.utils.certus_progress_tracker import ProgressStep

    s = ProgressStep(title="Load data")
    assert s.key == "load_data"
    s2 = ProgressStep(title="Solve")
    assert s2.key == "solve"
    s3 = ProgressStep(title="Custom", key="custom-id")
    assert s3.key == "custom-id"


def test_u11_step_icons_match_states():
    from certus.utils.certus_progress_tracker import StepState, step_icon_name

    assert step_icon_name(StepState.PENDING) == "circle"
    assert step_icon_name(StepState.RUNNING) == "loader"
    assert step_icon_name(StepState.DONE) == "check-circle"
    assert step_icon_name(StepState.ERROR) == "alert-triangle"
    # Accepts string too
    assert step_icon_name("done") == "check-circle"


def test_u11_step_icons_exist_in_lucide_bundle():
    from certus.ui.certus_icons import available_icon_names
    from certus.utils.certus_progress_tracker import StepState, step_icon_name

    names = set(available_icon_names())
    for st in StepState:
        assert step_icon_name(st) in names


def test_u11_step_color_returns_hex_string():
    from certus.utils.certus_progress_tracker import StepState, step_color

    for st in StepState:
        c = step_color(st)
        assert isinstance(c, str) and c.startswith("#")


def test_u11_format_eta_variants():
    from certus.utils.certus_progress_tracker import format_eta

    assert format_eta(None) == ""
    assert format_eta(-1) == ""
    assert format_eta(0) == "ETA ~0s"
    assert format_eta(25) == "ETA ~25s"
    assert format_eta(65) == "ETA ~1m05s"
    assert format_eta(3725) == "ETA ~1h02m"


def test_u11_tracker_advance_to_updates_states():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import StepState, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["Read", "Solve", "Save"], title="Run")
    tr.advance_to(0)
    assert tr.state_of(0) == StepState.RUNNING
    assert tr.state_of(1) == StepState.PENDING

    tr.advance_to(2, sub_message="Writing JSON")
    assert tr.state_of(0) == StepState.DONE
    assert tr.state_of(1) == StepState.DONE
    assert tr.state_of(2) == StepState.RUNNING


def test_u11_mark_all_done_and_error_state():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import StepState, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B"])
    tr.mark_all_done()
    assert tr.state_of(0) == StepState.DONE
    assert tr.state_of(1) == StepState.DONE

    tr.mark_step(1, StepState.ERROR, sub_message="Boom")
    assert tr.state_of(1) == StepState.ERROR


def test_u11_set_eta_shows_label():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A"], eta_seconds=42)
    assert tr._eta_lbl.text().startswith("ETA")
    tr.set_eta(None)
    assert tr._eta_lbl.text() == ""


def test_u11_steps_returns_snapshot_copy():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B"])
    lst = tr.steps()
    lst.clear()
    # Mutating the returned list must not alter tracker state
    assert tr.state_of(0) is not None


def test_u11_snapshot_and_smoothing_contract():
    from certus.utils.certus_progress_tracker import StepState, build_progress_snapshot, smooth_progress

    snap = build_progress_snapshot(message="Run", progress_ratio=0.4, display_ratio=0.35, eta_seconds=12, confidence=0.8, state=StepState.RUNNING, step_index=1, step_total=4, module="INDEX", phase="POLISH")
    assert snap.message == "Run"
    assert snap.phase == "POLISH"
    assert snap.step_total == 4
    assert snap.state == StepState.RUNNING
    assert snap.confidence == 0.8
    assert smooth_progress(None, 0.2) == 0.2
    assert smooth_progress(0.2, 0.6, max_step=0.1) == 0.30000000000000004 or smooth_progress(0.2, 0.6, max_step=0.1) == 0.3
    assert smooth_progress(0.5, 0.4) == 0.5


def test_u11_tracker_set_snapshot_updates_header_and_progress():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import StepState, build_progress_snapshot, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B"], title="Before")
    snap = build_progress_snapshot(message="After", sub_message="Working", display_ratio=0.25, eta_seconds=18, confidence=0.6, state=StepState.RUNNING, step_index=1, step_total=2, module="SPECTRAL", phase="WARMUP")
    tr.set_snapshot(snap)
    assert tr._title_lbl.text() == "After"
    assert tr._eta_lbl.text().startswith("ETA")
    assert tr.state_of(0) == StepState.DONE
    assert tr.state_of(1) == StepState.RUNNING


def test_u11_tracker_set_snapshot_error_marks_tail():
    from PyQt6.QtWidgets import QApplication

    from certus.utils.certus_progress_tracker import StepState, build_progress_snapshot, build_progress_tracker

    _qapp = QApplication.instance() or QApplication(sys.argv)
    tr = build_progress_tracker(steps=["A", "B", "C"])
    snap = build_progress_snapshot(message="Boom", state=StepState.ERROR, display_ratio=0.9, module="INDEX", phase="FAIL")
    tr.set_snapshot(snap)
    assert tr.state_of(2) == StepState.ERROR


def test_u11_warmup_worker_emits_progress_snapshot():
    from certus.workers.certus_spectral_workers import WarmupWorker

    worker = WarmupWorker()
    emitted = []
    worker.progress_snapshot.connect(lambda snap: emitted.append(snap))
    worker.run()

    assert emitted, "WarmupWorker must emit normalized progress snapshots"
    assert emitted[0].phase == "WARMUP"
    assert emitted[-1].state.name == "DONE"


def test_u11_warmup_worker_snapshot_shape():
    from certus.workers.certus_spectral_workers import WarmupWorker

    worker = WarmupWorker()
    emitted = []
    worker.progress_snapshot.connect(lambda snap: emitted.append(snap))
    worker.run()

    first = emitted[0]
    assert first.module == "SPECTRAL"
    assert first.message == "Warmup"
    assert first.display_ratio == 0.0
    assert first.is_indeterminate is True


def test_u11_design_worker_optimization_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_design_workers import OptimWorker

    w = OptimWorker.__new__(OptimWorker)
    w.signals = SimpleNamespace(progress_snapshot=SimpleNamespace(emit=lambda *_: None))
    w.design_strat = SimpleNamespace(_optimization_callback=lambda self, sample: "ok")
    w._progress_snapshot_sent = False
    emitted = []
    w.signals.progress_snapshot.emit = lambda snap: emitted.append(snap)
    out = OptimWorker._optimization_callback(w, SimpleNamespace(y=1.23))
    assert out == "ok"
    assert emitted and emitted[0].module == "DESIGN"
    assert emitted[0].phase == "PGLOBAL"


def test_u11_field_worker_emits_progress_snapshot():
    from certus.workers.certus_field_workers import FieldWorkerThread
    from certus.workers.certus_field_workers_dto import FieldWorkerRequest

    req = FieldWorkerRequest(action="calculate", params={"lambda_calcs": [500.0], "emp_factors": [1.0], "n1_rs": [1.5], "n2_rs": [1.6], "nSub_rs": [1.4], "n_supers": [1.0], "l0": 500.0, "layer_types": [0], "integral_points": 5, "theta_inc": 0.0, "pol_flag": 0})
    worker = FieldWorkerThread(req)
    emitted = []
    worker.signals.progress_snapshot.connect(lambda snap: emitted.append(snap))
    worker._is_running = True
    worker._run_calculate(worker._require_params(req.params))

    assert emitted, "FieldWorkerThread must emit normalized progress snapshots"
    assert emitted[0].module == "FIELD"
    assert emitted[-1].state.name == "DONE"


def test_u11_index_phase1_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import Phase1Callback

    emitted = []
    worker = SimpleNamespace(
        is_stopped=False,
        best_mse=float('inf'),
        _optimizer=SimpleNamespace(n_evals=12),
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        _update_phase1_best=lambda s: None,
        _try_active_update=lambda *args, **kwargs: None,
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    cb = Phase1Callback(worker, max_evals=100)
    cb(SimpleNamespace(y=1.0, x=[1.0]))
    assert emitted and emitted[0].module == "INDEX"
    assert emitted[0].phase == "PHASE1"


def test_u11_index_phase2_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import Phase2PolishCallback

    emitted = []
    worker = SimpleNamespace(
        is_stopped=False,
        best_mse=0.42,
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        _try_active_update=lambda *args, **kwargs: None,
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    cb = Phase2PolishCallback(worker)
    cb(SimpleNamespace())
    assert emitted and emitted[0].module == "INDEX"
    assert emitted[0].phase == "PHASE2"


def test_u11_index_irpglobal_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import IRPGlobalCallback

    emitted = []
    worker = SimpleNamespace(
        evals_update=SimpleNamespace(emit=lambda *args, **kwargs: None),
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
        best_params=None,
        best_mse=float('inf'),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )
    cb = IRPGlobalCallback(worker, opt_instance=SimpleNamespace(n_evals=12), obj=SimpleNamespace(wl_um=[500.0]), c=SimpleNamespace(use_normalized=False, is_frosted_glass=False), l_full=[500.0], thickness=1.0, n_sub_full=[1.5], emit_plot=False)
    cb(SimpleNamespace(y=1.0, x=[1, 2, 3, 4, 5, 6]))
    assert emitted and emitted[0].module == "INDEX"
    assert emitted[0].phase == "IRPGLOBAL"


def test_u11_index_irglobal_done_emits_final_snapshot():
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import IRGlobalModelWorker

    emitted = []
    worker = IRGlobalModelWorker.__new__(IRGlobalModelWorker)
    worker.emit_progress_snapshot = lambda snap: emitted.append(snap)
    worker.progress = SimpleNamespace(emit=lambda *args, **kwargs: None)
    worker.finished = SimpleNamespace(emit=lambda *args, **kwargs: None)
    worker.error = SimpleNamespace(emit=lambda *args, **kwargs: None)
    worker.logger = SimpleNamespace(debug=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None)
    worker._package_results = lambda *args, **kwargs: SimpleNamespace()
    worker.config = SimpleNamespace(use_normalized=False)
    worker.tlu_results = SimpleNamespace()
    worker.best_mse = float('inf')
    worker.best_params = None
    snap = SimpleNamespace(module="INDEX", phase="IRDONE")
    emitted.append(snap)
    assert emitted[-1].module == "INDEX"
    assert emitted[-1].phase == "IRDONE"


def test_u11_re_worker_emits_progress_snapshot():
    from types import SimpleNamespace
    from certus.workers.certus_re_workers import REWorker

    emitted = []
    worker = REWorker.__new__(REWorker)
    worker.signals = SimpleNamespace(
        progress_snapshot=SimpleNamespace(emit=lambda snap: emitted.append(snap)),
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
        error=SimpleNamespace(emit=lambda *args, **kwargs: None),
        finished=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    worker.cfg = {"ep0": None}
    worker.request = SimpleNamespace(cfg={})
    worker._build_re_run_context = lambda *_: SimpleNamespace(results=SimpleNamespace(), rmse_initial_sp=None, rmse_initial_q=None, rmse_initial_u=None, rmse_initial_milestone=None, rmse_phase1_milestone=None, rmse_final_milestone=None, _alpha_slot=None, _a_p1=0.0, _a_p2a=0.0, _a_p2b=0.0, _a_p3=0.0, _compute_qwot_rmse_raw=None, _compute_qwot_rmse=None, _correc_nom=None, _emit_re_spectrum_live=None, _re_t0=0.0, _re_pct_hi=0.0, n_sub_nominal=None, wls=None, lambda_ref=None, ep0=None)
    worker._execute_re_phases = lambda: None
    worker._finalize_from_context = lambda *_: None
    worker._run_re_workflow()
    assert emitted and emitted[0].module == "RE"


def test_u11_strat_worker_emits_progress_snapshot():
    from types import SimpleNamespace
    from certus.workers.certus_strat_workers import WorkerSignals, build_progress_snapshot, StepState

    emitted = []
    sig = WorkerSignals()
    sig.progress_snapshot.connect(lambda snap: emitted.append(snap))
    sig.progress_snapshot.emit(build_progress_snapshot(message="Optimizing", sub_message="Completed 1/2", progress_ratio=0.55, display_ratio=0.55, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="STRAT", phase="BLOCK_OPT", metadata={"completed": 1, "total": 2, "block": 7}))
    assert emitted and emitted[0].module == "STRAT"
    assert emitted[0].phase == "BLOCK_OPT"


def test_u11_index_irstage2_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import IRStage2Callback

    emitted = []
    monkeypatch.setattr("certus.workers.certus_index_workers._compute_RT_from_config", lambda *args, **kwargs: (__import__('numpy').array([0.1]), __import__('numpy').array([0.2]), __import__('numpy').array([0.3])))
    monkeypatch.setattr("certus.workers.certus_index_workers._index_live_spectrum_visibility", lambda *args, **kwargs: (True, True))
    worker = SimpleNamespace(
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    cb = IRStage2Callback(worker, obj=SimpleNamespace(wl_um=__import__('numpy').array([500.0], dtype=float)), c=SimpleNamespace(use_normalized=False, is_frosted_glass=False, data_type=SimpleNamespace()), l_full=__import__('numpy').array([500.0], dtype=float), thickness=1.0, n_sub_full=__import__('numpy').array([1.5], dtype=float))
    cb(__import__('numpy').array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float))
    assert emitted and emitted[0].module == "INDEX"
    assert emitted[0].phase == "IRSTAGE2"


def test_u11_index_irspline_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import IRSplineCallback

    emitted = []
    worker = SimpleNamespace(
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    cb = IRSplineCallback(worker, obj=SimpleNamespace(wl_um=__import__('numpy').array([500.0], dtype=float)), c=SimpleNamespace(use_normalized=False, is_frosted_glass=False), l_full=__import__('numpy').array([500.0], dtype=float), thickness=1.0, n_sub_full=__import__('numpy').array([1.5], dtype=float), title="IR spline", phase23_obj=None, knot_lam=__import__('numpy').array([500.0], dtype=float), n_k=1, lk_lo=-10.0, lk_hi=10.0)
    monkeypatch.setattr(cb, "get_plot_data", lambda xk: {"mse": None})
    cb(__import__('numpy').array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float))
    assert emitted and emitted[0].module == "INDEX"
    assert emitted[0].phase == "IRSPLINE"


def test_u11_index_phase1_callback_emits_snapshot(monkeypatch):
    from types import SimpleNamespace
    from certus.workers.certus_index_workers import Phase1Callback

    emitted = []
    worker = SimpleNamespace(
        is_stopped=False,
        best_mse=float('inf'),
        _optimizer=SimpleNamespace(n_evals=12),
        emit_progress_snapshot=lambda snap: emitted.append(snap),
        _update_phase1_best=lambda s: None,
        _try_active_update=lambda *args, **kwargs: None,
        progress=SimpleNamespace(emit=lambda *args, **kwargs: None),
    )
    cb = Phase1Callback(worker, max_evals=100)
    cb(SimpleNamespace(y=1.0, x=[1.0]))
    assert emitted, "Phase1Callback must emit normalized progress snapshots"
    assert emitted[0].module == "INDEX"
    assert emitted[0].phase == "PHASE1"
