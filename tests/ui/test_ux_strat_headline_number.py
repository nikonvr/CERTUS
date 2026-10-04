"""STRAT's headline strip must report the quantity the project reports (plan UX, 5.1).

``CLAUDE.md`` §22 is explicit: the SEEL - the equivalent thickness error per
layer, in nanometres - is *« la seule grandeur à rapporter — jamais le RMSE
brut »*. It is the only figure a chamber operator reads directly. The strip
above STRAT's plots showed ``ROBUSTNESS SCORE`` to six decimals and no SEEL.

Reading ``_refresh_synthesis_kpis`` against the shape the solver really emits
(``_finalize_robustness_results``, ``certus_strat_robustness.py``) turned up two
more defects in the same nine lines:

- ``n_blocks`` is read from the top of the result dict, where it does not
  exist - it lives in ``result["strategy"]``. The BLOCKS figure was therefore
  always blank;
- the winner is taken as ``strategies[0]``, bypassing
  ``select_best_strat_result`` - the helper written precisely because *« older
  or partially populated payloads may keep placeholder zeros at the top »*. The
  strip could headline a strategy that did not win.

⚠️ The SEEL is NOT recomputed here. It is derived exactly as the results table
does it (``certus_strat_table_ui``): the calibration lives in
``APP_CONTEXT["seel_data"]`` and is produced at step 0. When it is absent the
strip must stay blank and say nothing - a headline number invented from a
missing calibration is the worst failure this repository knows.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

from certus.ui.certus_overview_tab import PLACEHOLDER


@pytest.fixture(scope="module")
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


@pytest.fixture(autouse=True)
def clean_app_context():
    """APP_CONTEXT is a process-wide dict; leaking a calibration would poison the suite."""
    from certus.utils.certus_strat_service import APP_CONTEXT

    saved = APP_CONTEXT.get("seel_data", "__absent__")
    APP_CONTEXT.pop("seel_data", None)
    try:
        yield APP_CONTEXT
    finally:
        if saved == "__absent__":
            APP_CONTEXT.pop("seel_data", None)
        else:
            APP_CONTEXT["seel_data"] = saved


def _result(sid: int, score: float, crash: float, n_blocks: int, rmse_p95: float) -> dict:
    """One element of ``all_strategies_results``, shaped as the solver emits it."""
    return {
        "strategy_id": sid,
        "strategy": {"strategy_id": sid, "n_blocks": n_blocks, "origin": "TEST", "blocks": []},
        "results_per_noise": [
            {"noise_level": 0.5, "rmse_p95": rmse_p95 * 0.5, "rmse_mean": rmse_p95 * 0.4},
            {"noise_level": 1.0, "rmse_p95": rmse_p95, "rmse_mean": rmse_p95 * 0.9},
            {"noise_level": 2.0, "rmse_p95": rmse_p95 * 2.0, "rmse_mean": rmse_p95 * 1.8},
        ],
        "robustness_score": score,
        "crash_rate": crash,
    }


def _shown(win, key: str) -> str:
    return win.kpi_banner._values[key].text()


def _refresh(win, strategies: list[dict]) -> None:
    win.final_results = {"all_strategies_results": strategies}
    win._refresh_synthesis_kpis()


# =============================================================================
# Contrôles négatifs
# =============================================================================


def test_the_strip_exists_and_can_be_read(strat):
    """Without this, every assertion below would be vacuous."""
    assert getattr(strat, "kpi_banner", None) is not None, "STRAT has no KPI strip"
    assert strat.kpi_banner._values, "the KPI strip carries no field"


def test_the_crash_headline_identifies_the_worst_noise_level(strat):
    from PyQt6.QtWidgets import QLabel

    captions = {label.text() for label in strat.kpi_banner.findChildren(QLabel)}
    assert "WORST CRASH RATE" in captions


def test_the_strip_reports_a_finished_run_at_all(strat):
    """The harness must be able to make the strip say something."""
    _refresh(strat, [_result(1, 0.0123, 0.0, 6, 0.09)])
    assert _shown(strat, "crash") != PLACEHOLDER, "the strip stays blank on a perfectly ordinary run"


# =============================================================================
# The three defects
# =============================================================================


def test_the_block_count_is_reported(strat):
    """``n_blocks`` lives under ``strategy``; read from the top it is always None."""
    _refresh(strat, [_result(1, 0.0123, 0.0, 6, 0.09)])
    assert _shown(strat, "blocks") == "6", (
        f"BLOCKS shows {_shown(strat, 'blocks')!r} for a 6-block winner - the figure never reaches the operator"
    )


def test_the_headline_is_the_winner_not_the_first_row(strat):
    """A placeholder zero at the top must not become the headline."""
    placeholder = _result(1, 0.0, 0.0, 99, 0.0)
    winner = _result(2, 0.0123, 0.0, 6, 0.09)
    _refresh(strat, [placeholder, winner])

    assert _shown(strat, "blocks") == "6", (
        f"the strip headlines the first row ({_shown(strat, 'blocks')} blocks) instead of the winning strategy"
    )


def test_the_seel_is_reported_when_it_can_be_computed(strat, clean_app_context):
    """SEEL = fit_k · RMSE_p95^fit_alpha, the calibration produced at step 0."""
    clean_app_context["seel_data"] = {"fit_k": 2.0, "fit_alpha": 0.5}
    _refresh(strat, [_result(1, 0.0123, 0.0, 6, 0.09)])

    shown = _shown(strat, "seel")
    assert shown != PLACEHOLDER, "SEEL is blank although its calibration is available"
    # 2 * sqrt(0.09) = 0.600
    assert "0.6" in shown, f"SEEL shows {shown!r}, expected 0.600 nm for RMSE_p95 = 0.09 with k=2, alpha=0.5"


def test_the_seel_stays_blank_when_it_cannot_be_computed(strat):
    """No calibration, no number. An invented headline is worse than none."""
    _refresh(strat, [_result(1, 0.0123, 0.0, 6, 0.09)])

    shown = _shown(strat, "seel")
    assert not any(ch.isdigit() for ch in shown), (
        f"SEEL shows {shown!r} although step 0 never ran - the strip is inventing a figure"
    )
