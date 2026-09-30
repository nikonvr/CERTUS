"""The progress bar reads the share of the work that is done, and nothing else (audit UX-09, plan S6.3).

`DualStageProgressWidget.update` blended the share of iterations with `evals / (last_evals + evals)`, where `last_evals`
had been set to `evals` a few lines before: the ratio was always 1/2, and the bar read `0.7 p + 0.15` whenever the run
reported evaluations (DESIGN, INDEX and METAL do, on every update). A finished run stopped at 85 %, and a run whose total
is unknown showed 15 %. `start()` did not clear the smoothed value either, so the second run of a session began where the
first had stopped.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

# The display moves at most 8 % per update (`smooth_progress`): this many updates settle it on its target.
SETTLE = 20


@pytest.fixture
def widget(qapp):
    from certus.ui.certus_ui_widgets_progress import EnhancedProgressWidget

    w = EnhancedProgressWidget()
    try:
        yield w
    finally:
        w.close()
        w.deleteLater()


def settle(widget, iteration: int, max_iter: int, evals: int = 0, progress_pct: int = -1) -> int:
    """Report the same state until the smoothed display has reached it; what the bar and its label then say."""
    for _ in range(SETTLE):
        widget.update(iteration, max_iter, evals=evals, progress_pct=progress_pct, animate=False)
    shown = widget.progress_bar.value()
    assert widget._overall_value_label.text() == f"{shown}%", "the label and the bar disagree"
    return shown


def test_a_run_that_reports_evaluations_reaches_one_hundred(widget) -> None:
    """The scene of the audit: DESIGN reports `evals` on every update, and its bar stopped at 85 %."""
    assert settle(widget, 10, 10, evals=250_000) == 100


def test_the_bar_reads_the_share_of_iterations_done(widget) -> None:
    """0.7 p + 0.15 is right at one point only (p = 1/2): at 20 % it read 29 %."""
    assert settle(widget, 2, 10, evals=5_000) == 20


def test_the_bar_is_never_ahead_of_the_work(widget) -> None:
    """A third of the iterations is 33 %, not 34: a bar that rounds up claims work that is not done."""
    assert settle(widget, 1, 3, evals=100) == 33
    assert settle(widget, 2, 3, evals=200) == 66


def test_the_bar_does_not_invent_progress_when_the_total_is_unknown(widget) -> None:
    """No total, some evaluations: the old blend drew 15 % of nothing."""
    assert settle(widget, 0, 0, evals=5_000) == 0


def test_an_explicit_percentage_still_decides(widget) -> None:
    """STRAT, METAL and the spline window report their own percentage."""
    assert settle(widget, 1, 10, evals=10, progress_pct=70) == 70


def test_a_new_run_starts_from_zero_after_a_finished_one(widget) -> None:
    """`update` starts a run that is not started; the smoothed value of the last one must not come with it."""
    assert settle(widget, 10, 10, evals=1_000) == 100
    widget.stop()

    widget.update(1, 10, evals=10, animate=False)

    assert widget.progress_bar.value() <= 10, "the second run began where the first one had stopped"
    assert widget._overall_value_label.text() == f"{widget.progress_bar.value()}%"


def test_a_widget_reset_between_two_runs_starts_the_next_one_from_zero(widget) -> None:
    """A window goes idle with `reset()` (the end-of-busy handler of the base app), then `update` starts the next run."""
    assert settle(widget, 10, 10, evals=1_000) == 100
    widget.reset()

    widget.update(1, 10, evals=10, animate=False)

    assert widget.progress_bar.value() <= 10, "the run after `reset()` began where the previous one had stopped"


def test_the_bar_never_goes_backwards_within_a_run(widget) -> None:
    """The smoothing is meant to be monotonic: a late update with a smaller share must not pull the bar back."""
    assert settle(widget, 6, 10, evals=100) == 60

    widget.update(3, 10, evals=200, animate=False)

    assert widget.progress_bar.value() == 60
