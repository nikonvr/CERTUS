"""The "best" spectrum kept on screen was computed with the settings of now (audit 2026-11-15, C-L6a).

DESIGN and RE keep the best evaluated spectrum and show it again when a later evaluation is worse. The snapshot was
reset on a load or an optimisation only: with RMSE 0.010 without the backside, ticking the backside (true RMSE 0.030)
left the curve and the "0.010" of the previous setting on screen. The snapshot now carries the settings of the
evaluation that produced it and is dropped as soon as they change.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui import certus_spectrum_eval_ui as ev
from certus_physics import ObliqueTarget, Target


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "best spectrum settings", main_windows_only=True)


def _result(rmse: float, generation: int, ep: list[float]) -> dict:
    return {"rmse": rmse, "ep": np.array(ep), "eval_generation_id": generation, "oblique_mode": False}


def _finish(app, rmse: float, settings: tuple, ep: list[float]) -> dict:
    app._current_eval_generation += 1
    app._current_eval_settings = settings
    return ev.spectrum_eval_on_finished_prepare_display(app, _result(rmse, app._current_eval_generation, ep), None)


def test_a_worse_evaluation_after_a_changed_setting_is_shown_as_it_is(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    n = len(app._get_front_stack())
    first, second = [100.0] * n, [120.0] * n

    shown = _finish(app, 0.010, ("no backside",), first)
    assert shown["rmse"] == 0.010

    shown = _finish(app, 0.030, ("backside",), second)
    assert shown["rmse"] == 0.030, "the spectrum of the previous setting was shown again"
    np.testing.assert_array_equal(shown["ep"], second)
    assert app._best_eval_rmse == 0.030


def test_with_unchanged_settings_the_best_spectrum_is_still_kept(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    n = len(app._get_front_stack())
    _finish(app, 0.010, ("same",), [100.0] * n)
    shown = _finish(app, 0.030, ("same",), [120.0] * n)
    assert shown["rmse"] == 0.010


def _cfg(**changed) -> dict:
    material = SimpleNamespace(n4=2.35, n7=2.25, _is_tabular=False)
    substrate = SimpleNamespace(n4=1.47, n7=1.455, _is_tabular=False)
    cfg = {
        "variant": "design",
        "mats": {"H": material, "substrate": substrate},
        "stack": [SimpleNamespace(mat="H")],
        "ep": np.array([100.0]),
        "tgts": [Target(400.0, 700.0, 0.9, 1.0)],
        "oblique_mode": False,
        "oblique_tgts": [],
        "wls_vis": np.linspace(400.0, 700.0, 31),
        "wls_optim": np.linspace(400.0, 700.0, 11),
        "back": False,
        "l0": 550.0,
        "eval_generation_id": 7,
    }
    cfg.update(changed)
    return cfg


def test_the_settings_signature_ignores_the_thicknesses_and_the_generation() -> None:
    assert ev.spectrum_eval_settings_signature(_cfg()) == ev.spectrum_eval_settings_signature(
        _cfg(ep=np.array([250.0]), eval_generation_id=8)
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"back": True},
        {"tgts": [Target(400.0, 700.0, 0.5, 1.0)]},
        {"oblique_mode": True, "oblique_tgts": [ObliqueTarget(45.0, "s", 400.0, 700.0, 0.9, 1.0, "R")]},
        {"mats": {"H": SimpleNamespace(n4=2.35, n7=2.25, _is_tabular=False),
                  "substrate": SimpleNamespace(n4=1.52, n7=1.51, _is_tabular=False)}},
        {"wls_optim": np.linspace(450.0, 700.0, 11)},
        {"use_back_coat": True, "stack_back": [SimpleNamespace(mat="H")], "ep_back": np.array([80.0])},
    ],
    ids=["backside", "targets", "oblique targets", "substrate", "optimisation grid", "back coating"],
)
def test_the_settings_signature_changes_with_each_input_of_the_evaluation(changed: dict) -> None:
    assert ev.spectrum_eval_settings_signature(_cfg(**changed)) != ev.spectrum_eval_settings_signature(_cfg())


def test_starting_an_evaluation_records_its_settings(qapp, monkeypatch) -> None:
    import certus.workers.certus_spectral_workers as sw

    class _Worker:
        def __init__(self, cfg) -> None:
            self.signals = SimpleNamespace(
                finished=SimpleNamespace(connect=lambda *_a: None), error=SimpleNamespace(connect=lambda *_a: None)
            )

        def start(self) -> None:
            pass

        def isRunning(self) -> bool:
            return False

    monkeypatch.setattr(sw, "EvalWorker", _Worker)
    app = SimpleNamespace(_current_eval_generation=0, _set_busy=lambda *_a: None, eval_worker=None)
    monkeypatch.setattr(ev, "spectrum_eval_feedback", lambda *_a, **_k: None)

    ev.spectrum_eval_start_worker(app, _cfg(back=True), 0.0)

    assert app._current_eval_settings == ev.spectrum_eval_settings_signature(_cfg(back=True))
