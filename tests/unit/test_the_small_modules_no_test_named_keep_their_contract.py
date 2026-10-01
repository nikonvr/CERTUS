"""Small modules that no test named keep their contract (plan S3.7, 57 modules of `certus/` named by no test on 2026-10-01).

A module that no test names is a module whose behavior can change without a red line. These are the cheap ones, pure or
nearly: what each promises in its docstring or its name is said here as a value, so a change of that promise is a failure and
not a surprise. A module is only worth its line in this file if its tests fail when its behavior moves: each assertion
below was written from the code's own text and checked by breaking the code (the planted errors are in the commit message).

Covered here: `certus_design_tokens`, `certus_runtime`, `certus_exclusions`, `certus_ui_shared`, `certus_warmup`,
`certus_strat_machine`, `certus_metal_defaults`, `certus_metal_orchestrator`, `event_bus`.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# certus_design_tokens


def test_the_corridor_slider_sheet_carries_each_token_in_its_own_rule():
    from certus.core.certus_design_tokens import TOKENS, slider_corridor_half_stylesheet

    sheet = slider_corridor_half_stylesheet()
    rules = dict(re.findall(r"(QSlider::[\w-]+:horizontal) \{([^}]*)\}", sheet))
    assert set(rules) == {
        "QSlider::groove:horizontal",
        "QSlider::sub-page:horizontal",
        "QSlider::add-page:horizontal",
        "QSlider::handle:horizontal",
    }
    assert TOKENS["slider_corridor_groove_bg"] in rules["QSlider::groove:horizontal"]
    assert TOKENS["slider_corridor_subpage_bg"] in rules["QSlider::sub-page:horizontal"]
    assert TOKENS["slider_corridor_addpage_bg"] in rules["QSlider::add-page:horizontal"]
    assert TOKENS["slider_corridor_handle_bg"] in rules["QSlider::handle:horizontal"]
    assert sheet.count("{") == sheet.count("}") == 4


def test_the_design_tokens_are_hex_colors():
    from certus.core.certus_design_tokens import TOKENS

    assert TOKENS
    assert all(re.fullmatch(r"#[0-9a-f]{6}", value) for value in TOKENS.values())


# =============================================================================
# certus_runtime

THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


@pytest.fixture
def clean_env(monkeypatch):
    """A private copy of the environment without the thread variables: `setdefault` must not leak into the session."""
    monkeypatch.setattr(os, "environ", {k: v for k, v in os.environ.items() if k not in THREAD_VARS})
    return os.environ


def test_the_number_of_cores_is_never_below_one():
    from certus.core.certus_runtime import _resolve_n_cores

    assert _resolve_n_cores(4) == 4
    assert _resolve_n_cores(0) == 1
    assert _resolve_n_cores(-3) == 1
    assert _resolve_n_cores(None) == max(1, os.cpu_count() or 1)


def test_the_thread_limits_are_set_once_and_never_override_a_choice(clean_env):
    from certus.core.certus_runtime import set_num_threads

    clean_env["OMP_NUM_THREADS"] = "2"  # the operator's choice
    assert set_num_threads(5) == 5
    assert clean_env["OMP_NUM_THREADS"] == "2"
    assert [clean_env[v] for v in THREAD_VARS[1:]] == ["5"] * 4


def test_the_numba_cache_directory_is_read_from_the_environment_or_empty(clean_env):
    from certus.core.certus_runtime import setup_numba_cache

    clean_env.pop("NUMBA_CACHE_DIR", None)
    assert setup_numba_cache() == ""
    clean_env["NUMBA_CACHE_DIR"] = "somewhere"
    assert setup_numba_cache() == "somewhere"


def test_build_runtime_gathers_the_logger_the_cache_and_the_cores(clean_env, monkeypatch):
    import certus.core.certus_runtime as runtime

    asked = {}
    logger = logging.getLogger("test-runtime")
    monkeypatch.setattr(runtime, "setup_logging", lambda **kw: asked.update(kw) or logger)
    clean_env["NUMBA_CACHE_DIR"] = "cache-dir"
    built = runtime.build_runtime(log_file="run.log", level=logging.WARNING, n_cores=3)
    assert (built.logger, built.cache_dir, built.n_cores) == (logger, "cache-dir", 3)
    assert asked == {"log_file": "run.log", "level": logging.WARNING}
    with pytest.raises(AttributeError):
        built.n_cores = 9  # frozen


# =============================================================================
# certus_exclusions


def test_the_serialization_filter_drops_the_three_objects_json_cannot_hold():
    from certus.utils.certus_exclusions import filter_params_for_serialization

    params = {"logger": 1, "materials_db": 2, "clues_at_wl": 3, "gui_parent": 4, "thickness": [1.0]}
    assert filter_params_for_serialization(params) == {"gui_parent": 4, "thickness": [1.0]}
    assert params["logger"] == 1  # the input is not touched


def test_the_gui_filter_drops_the_logger_the_database_and_the_parent_window():
    from certus.utils.certus_exclusions import filter_params_for_gui

    params = {"logger": 1, "materials_db": 2, "clues_at_wl": 3, "gui_parent": 4, "thickness": [1.0]}
    assert filter_params_for_gui(params) == {"clues_at_wl": 3, "thickness": [1.0]}


def test_the_exclusion_sets_are_frozen_sets_and_the_alias_is_the_same_object():
    import certus.utils.certus_exclusions as ex

    assert isinstance(ex.PARAMS_EXCLUDE_LOGGER_DB, frozenset)
    assert ex.PARAMS_EXCLUDE_NON_SERIALIZABLE is ex.PARAMS_EXCLUDE_LOGGER_DB
    assert set(ex.__all__) <= set(dir(ex))


# =============================================================================
# certus_ui_shared


def test_the_zoom_factor_stays_between_half_and_two_and_a_half():
    from certus.ui.certus_ui_shared import _clamp_zoom_factor

    assert _clamp_zoom_factor(1.0) == 1.0
    assert _clamp_zoom_factor(0.1) == 0.5
    assert _clamp_zoom_factor(9) == 2.5
    assert _clamp_zoom_factor("1.5") == 1.5


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, "0 s"),
        (-5, "0 s"),
        (0, "0 s"),
        (59.4, "59 s"),
        (59.6, "1 min 00 s"),
        (60, "1 min 00 s"),
        (125, "2 min 05 s"),
        (3599, "59 min 59 s"),
        (3600, "1 h 00 min"),
        (3661, "1 h 01 min"),
        (7322, "2 h 02 min"),
    ],
)
def test_a_duration_is_written_in_seconds_then_minutes_then_hours(seconds, expected):
    from certus.ui.certus_ui_shared import _format_progress_duration

    assert _format_progress_duration(seconds) == expected


class _Owner:
    def __init__(self):
        self.label = None
        self.sheets = []

    def setStyleSheet(self, sheet):
        self.sheets.append(sheet)


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


@pytest.fixture
def keep_app_font(qapp):
    saved = qapp.font()
    yield qapp
    qapp.setFont(saved)


def test_zoom_clamps_records_the_factor_writes_the_label_and_scales_the_font(keep_app_font):
    from certus.ui.certus_ui_shared import apply_app_zoom

    owner = _Owner()
    owner.label = _Label()
    assert apply_app_zoom(owner, 9, label_attr="label", base_font_size=10) == 2.5
    assert owner._zoom_factor == 2.5
    assert owner.label.text == "Zoom 250%"
    assert keep_app_font.font().pointSize() == 25
    assert apply_app_zoom(owner, 0.5, label_attr="label", base_font_size=10) == 0.5
    assert keep_app_font.font().pointSize() == 9  # never below 9 pt


def test_zoom_applies_the_style_sheet_and_the_toast_and_survives_their_failures(keep_app_font, caplog):
    from certus.ui.certus_ui_shared import apply_app_zoom

    owner, toasts = _Owner(), []
    apply_app_zoom(owner, 1.2, label_attr="absent", stylesheet_fn=lambda: "QWidget {}", toast_fn=lambda *a, **k: toasts.append((a, k)))
    assert owner.sheets == ["QWidget {}"]
    assert toasts == [((owner, "Zoom 120%", "info"), {"duration_ms": 1200})]

    def boom(*_args, **_kwargs):
        raise RuntimeError("no")

    with caplog.at_level(logging.DEBUG, logger="CERTUS"):
        assert apply_app_zoom(owner, 1.0, label_attr="absent", stylesheet_fn=boom, toast_fn=boom) == 1.0
    assert sum("Silenced exception" in r.getMessage() for r in caplog.records) == 2


# =============================================================================
# certus_warmup


def test_the_warmup_reports_each_step_in_order_and_the_kernels_still_accept_its_dummy_data(caplog):
    """The warmup swallows its own errors (a log line): a kernel whose signature moved would warm nothing, silently."""
    from certus.physics.certus_warmup import run_warmup

    steps: list[str] = []
    with caplog.at_level(logging.ERROR, logger="CERTUS_WARMUP"):
        run_warmup(steps.append)
    assert steps == [
        "Warming up TMM Matrix functions...",
        "Warming up TMM Oblique functions...",
        "Warming up TMM Single Layer functions...",
        "Warming up Colorimetry functions...",
        "Numba warmup completed.",
    ]
    assert [r.getMessage() for r in caplog.records if r.name == "CERTUS_WARMUP"] == []


def test_the_warmup_runs_without_a_callback():
    from certus.physics.certus_warmup import run_warmup

    run_warmup()


# =============================================================================
# certus_strat_machine


def test_the_machine_model_defaults_are_those_of_the_oms_5100():
    from certus.physics.certus_strat_machine import (
        OMS5100_DEFAULT_5_SIGMA_FACTOR,
        OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM,
        OMS5100_DEFAULT_READING_NOISE_PCT,
        MachineModel,
    )

    machine = MachineModel()
    assert machine.name.endswith("OMS 5100")
    assert machine.reading_noise_floor_pct == OMS5100_DEFAULT_READING_NOISE_PCT == 0.05
    assert machine.monochromator_resolution_nm == OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM == 0.5
    assert machine.tp_hysteresis_factor == OMS5100_DEFAULT_5_SIGMA_FACTOR == 1.66
    assert machine.trigger_tolerance == 0.05
    assert machine.sigma_wl_func is None


def test_the_flat_noise_is_the_floor_in_percent_of_t_as_a_fraction():
    from certus.physics.certus_strat_machine import MachineModel

    assert MachineModel().get_sigma(400.0) == pytest.approx(5e-4)
    assert MachineModel(reading_noise_floor_pct=0.2).get_sigma(900.0) == pytest.approx(2e-3)
    assert MachineModel(reading_noise_floor_pct=-1.0).get_sigma(550.0) == 0.0  # never negative


def test_a_noise_function_of_the_wavelength_replaces_the_flat_floor_and_is_floored_at_zero():
    from certus.physics.certus_strat_machine import MachineModel

    machine = MachineModel(sigma_wl_func=lambda wl: (wl - 500.0) / 1e5)
    assert machine.get_sigma(600.0) == pytest.approx(1e-3)
    assert machine.get_sigma(400.0) == 0.0
    assert machine.get_sigma_array(np.array([400.0, 500.0, 700.0])).tolist() == pytest.approx([0.0, 0.0, 2e-3])


def test_the_flat_noise_array_has_the_shape_of_the_grid_and_ignores_the_wavelength():
    from certus.physics.certus_strat_machine import MachineModel

    sigmas = MachineModel().get_sigma_array(np.linspace(400.0, 800.0, 5))
    assert sigmas.shape == (5,)
    assert sigmas.dtype == np.float64
    assert sigmas.tolist() == pytest.approx([5e-4] * 5)
    assert MachineModel().get_sigma_array(np.array([], dtype=np.float64)).shape == (0,)


# =============================================================================
# certus_metal_defaults, certus_metal_orchestrator


def test_the_metal_defaults_module_imports_nothing():
    """Its docstring's promise: the METAL computation can read the defaults without PyQt6, pyqtgraph or certus.ui."""
    tree = ast.parse((ROOT / "certus" / "metal" / "certus_metal_defaults.py").read_text(encoding="utf-8-sig"))
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)] == []


def test_the_metal_defaults_have_their_documented_values():
    import certus.metal.certus_metal_defaults as d

    assert (d.DEFAULT_EM_MIN, d.DEFAULT_EM_MAX) == (5, 50)
    assert (d.DEFAULT_NK_MIN, d.DEFAULT_NK_MAX) == (0.0, 10.0)
    assert d.DEFAULT_NUM_KNOTS == 5
    assert d.DEFAULT_MIN_KNOT_DISTANCE == 20.0
    assert d.DEFAULT_EXCEL_FILENAME == "metal_results.xlsx"
    assert (d.DEFAULT_POPSIZE, d.DEFAULT_MAXITER, d.DEFAULT_TOL) == (15, 800, 0.005)
    assert (d.DEFAULT_MUTATION_MIN, d.DEFAULT_MUTATION_MAX, d.DEFAULT_RECOMBINATION) == (0.5, 1.0, 0.7)
    assert (d.DEFAULT_UPDATING, d.DEFAULT_WORKERS) == ("deferred", 1)


def test_the_common_module_reexports_every_default_unchanged():
    import certus.metal.certus_metal_common as common
    import certus.metal.certus_metal_defaults as defaults

    names = [n for n in vars(defaults) if n.startswith("DEFAULT_")]
    assert len(names) == 15
    assert [n for n in names if getattr(common, n) != getattr(defaults, n)] == []


def test_the_orchestrator_exposes_the_two_job_specs_of_the_common_module():
    import certus.metal.certus_metal_common as common
    import certus.metal.certus_metal_orchestrator as orchestrator

    assert orchestrator.__all__ == ["MetalJobSpec", "METAL_SINGLE_SPEC", "METAL_BILAYER_SPEC"]
    assert orchestrator.METAL_SINGLE_SPEC is common.METAL_SINGLE_SPEC
    assert orchestrator.METAL_BILAYER_SPEC is common.METAL_BILAYER_SPEC
    assert isinstance(orchestrator.METAL_SINGLE_SPEC, orchestrator.MetalJobSpec)


# =============================================================================
# event_bus


def test_an_event_needs_a_type_and_an_aggregate_and_is_immutable():
    from certus.domain.optical.events.event_bus import DomainEvent

    with pytest.raises(ValueError, match="event_type cannot be empty"):
        DomainEvent("", "stack-1", {})
    with pytest.raises(ValueError, match="aggregate_id cannot be empty"):
        DomainEvent("LayerAdded", "", {})
    event = DomainEvent("LayerAdded", "stack-1", {"material": "TiO2"})
    assert event.event_id.startswith("evt-")
    assert event.timestamp > 0
    with pytest.raises(AttributeError):
        event.event_type = "other"


def test_a_published_event_reaches_its_subscribers_only_and_is_stored():
    from certus.domain.optical.events.event_bus import DomainEvent, EventBus

    bus, got_a, got_b = EventBus(), [], []
    bus.subscribe("LayerAdded", got_a.append)
    bus.subscribe("LayerRemoved", got_b.append)
    added = DomainEvent("LayerAdded", "stack-1", {"position": 0})
    bus.publish(added)
    assert got_a == [added]
    assert got_b == []
    assert bus.event_count() == 1


def test_a_failing_handler_does_not_stop_the_next_one_nor_the_storage(capsys):
    from certus.domain.optical.events.event_bus import DomainEvent, EventBus

    bus, seen = EventBus(), []

    def broken(_event):
        raise RuntimeError("handler broke")

    bus.subscribe("X", broken)
    bus.subscribe("X", seen.append)
    event = DomainEvent("X", "agg", {})
    bus.publish(event)
    assert seen == [event]
    assert bus.event_count() == 1
    assert "handler broke" in capsys.readouterr().out


def test_replay_returns_one_aggregate_in_order_and_the_store_copy_is_independent():
    from certus.domain.optical.events.event_bus import DomainEvent, EventBus

    bus = EventBus()
    first, other, second = DomainEvent("A", "s1", {}), DomainEvent("A", "s2", {}), DomainEvent("B", "s1", {})
    for event in (first, other, second):
        bus.publish(event)
    assert bus.replay("s1") == [first, second]
    assert bus.replay("nobody") == []
    snapshot = bus.get_all_events()
    snapshot.clear()
    assert bus.event_count() == 3


def test_clear_forgets_the_events_and_the_handlers():
    from certus.domain.optical.events.event_bus import DomainEvent, EventBus

    bus, seen = EventBus(), []
    bus.subscribe("A", seen.append)
    bus.publish(DomainEvent("A", "s", {}))
    bus.clear()
    assert bus.event_count() == 0
    bus.publish(DomainEvent("A", "s", {}))
    assert len(seen) == 1  # the handler was dropped


def test_the_global_bus_is_one_object():
    from certus.domain.optical.events.event_bus import get_event_bus

    assert get_event_bus() is get_event_bus()
