"""DesignOrchestrator reads the needle checkpoint and the evaluation count on the window.

Two families of reads of `DesignOrchestrator` were written on the orchestrator, which holds
neither: `getattr(self, "_pre_needle_checkpoint", None)` (the checkpoint is stored on the window,
so an aborted Needle never found it and never went back to it: it finalized the structure the
failed attempts had degraded) and `getattr(self, "_optim_n_evals", 0)` (the count is kept on the
window: the evaluations of a stage were not added to the running total at the three points
where the workflow restarts a local optimization). Found on 2026-09-29 by listing every guard a
class puts on a name it never holds.

The orchestrator only stores its window, so a namespace stands for it here.
"""

from __future__ import annotations

from types import SimpleNamespace


def _window(**extra):
    calls = {"reverted": 0, "evaluated": 0, "scheduled": []}
    ui = SimpleNamespace(
        log=lambda *a, **k: None,
        _set_busy=lambda *a, **k: None,
        _schedule_eval=lambda *a, **k: calls.__setitem__("evaluated", calls["evaluated"] + 1),
        _revert_to_checkpoint=lambda: calls.__setitem__("reverted", calls["reverted"] + 1),
        schedule_task=lambda delay, func: calls["scheduled"].append(delay),
        run_optim=lambda *a, **k: None,
        **extra,
    )
    return ui, calls


def test_an_aborted_needle_goes_back_to_the_checkpoint_of_the_window() -> None:
    from certus.core.certus_design_orchestrator import DesignOrchestrator

    ui, calls = _window(_pre_needle_checkpoint={"rmse": 0.01, "table": []})
    orchestrator = DesignOrchestrator(ui)
    orchestrator._needle_fail_count = 3

    orchestrator._abort_needle_after_failed_retries()

    assert calls["reverted"] == 1
    assert calls["evaluated"] == 0


def test_an_aborted_needle_without_checkpoint_finalizes_the_structure() -> None:
    from certus.core.certus_design_orchestrator import DesignOrchestrator

    ui, calls = _window()
    orchestrator = DesignOrchestrator(ui)
    orchestrator._needle_fail_count = 3

    orchestrator._abort_needle_after_failed_retries()

    assert calls["reverted"] == 0
    assert calls["evaluated"] == 1


def test_pruning_the_overshoot_adds_the_evaluations_of_the_stage_to_the_total() -> None:
    from certus.core.certus_design_orchestrator import DesignOrchestrator

    ui, calls = _window(
        allow_growth_check=SimpleNamespace(isChecked=lambda: False),
        _prune_to_target=lambda target: 2,
        _workflow_best_rmse=0.5,
        _best_eval_rmse=0.5,
        accumulated_evals=100,
        _optim_n_evals=40,
    )
    orchestrator = DesignOrchestrator(ui)
    orchestrator._overshoot_active = True
    orchestrator._original_target_count = 5
    orchestrator._target_layer_count = 9

    assert orchestrator._maybe_prune_needle_overshoot(9) is True

    assert ui.accumulated_evals == 140
    assert calls["scheduled"] == [50]
