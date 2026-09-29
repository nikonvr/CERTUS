"""D1 -- a setting the user sees must reach the computation, or not exist.

CLAUDE.md, section 4: a visible parameter that does not reach the computation is worse than
an absent one, because it supplies a false explanation. Each class below guards one setting
that was shown, saved or logged while no computing line read it. None could be wired both
trivially and bit for bit, so each was REMOVED, and each class fails on the code before its
removal.

The last class guards the other half of D1: the execution mode sets budgets over those the
configuration states. The mode still wins -- which of the two should is the user's decision --
but `collect_params` now says it, in one line.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import re
from contextlib import contextmanager
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

ROOT = Path(__file__).resolve().parents[2]
#: The reference configuration. It is only READ here: every variant is a copy in tmp_path.
EXAMPLE = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
MODES = ("fast", "premium", "deep", "extreme")


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT settings", main_windows_only=True)


@pytest.fixture
def strat_window(qapp):
    from certus.ui.certus_strat_ui import CertusSTRATApp

    return CertusSTRATApp()


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@contextmanager
def _captured(logger: logging.Logger):
    """The lines `logger` emits inside the block. The STRAT window logger does not
    propagate (it feeds the Show Details panel), so `caplog` would see nothing."""
    handler = _Lines()
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def _load(window, tmp_path: Path, **extra) -> dict:
    """Load the reference configuration plus `extra` keys, through a file, as a user does."""
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg.update(extra)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    window.load_configuration(str(path))
    return cfg


def _told_ignored(lines: list[str]) -> list[str]:
    return [line for line in lines if "no longer a setting" in line]


def _save(window, tmp_path: Path, monkeypatch) -> dict:
    """What "Save configuration" writes, the file dialog answered with a path in tmp_path."""
    from PyQt6.QtWidgets import QFileDialog

    target = tmp_path / "saved.json"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    window.save_configuration()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert "robustness_num_runs" in saved, "premise: the file was written by the window"
    return saved


class TestFastAutoBlocks:
    """`fast_auto_blocks` was set to True by `collect_params` and printed by the FAST mode
    banner, while nothing read it: the branch that consumed it had been deleted
    (`_compute_blocks_range_for_params`)."""

    def test_collect_params_no_longer_carries_it(self, strat_window):
        assert "fast_auto_blocks" not in strat_window.collect_params()

    def test_the_fast_mode_log_line_no_longer_announces_it(self):
        from certus.ui import certus_strat_ui_worker

        assert "fast_auto_blocks" not in inspect.getsource(certus_strat_ui_worker)


class TestStrategyPhaseTimeout:
    """`strategy_phase_timeout` had a field ("Max Time per Iteration"), a default, a place in
    saved files and a value of its own in `extreme` (10 800 s), while no computing line read
    it: no pass was ever cancelled."""

    def test_no_field_shows_it(self, strat_window):
        assert "strategy_phase_timeout" not in strat_window.widgets

    @pytest.mark.parametrize("mode", MODES)
    def test_no_mode_puts_it_in_the_parameters(self, strat_window, mode):
        strat_window.widgets["execution_mode"].setCurrentText(mode)
        params = strat_window.collect_params()
        assert params["execution_mode"] == mode, "premise: the mode under test is the one run"
        assert "strategy_phase_timeout" not in params

    def test_a_file_that_carries_it_still_loads_and_says_it_is_ignored(self, strat_window, tmp_path):
        with _captured(strat_window.logger) as lines:
            cfg = _load(strat_window, tmp_path)
        assert "strategy_phase_timeout" in cfg, "premise: the reference file carries the key"
        assert strat_window._loaded_config.get("strategy_phase_timeout") == cfg["strategy_phase_timeout"]
        told = _told_ignored(lines)
        assert len(told) == 1 and "strategy_phase_timeout" in told[0], lines
        assert "strategy_phase_timeout" not in strat_window.collect_params()

    def test_saving_no_longer_writes_it(self, strat_window, tmp_path, monkeypatch):
        assert "strategy_phase_timeout" not in _save(strat_window, tmp_path, monkeypatch)


class TestMachineSamplingDd:
    """`machine_sampling_dd` had a field ("Machine grid"), a place in saved files and in the
    status banner, and a `collect_params` key read from the file only -- the field itself
    never reached `collect_params`. Nothing past `collect_params` read the key either: the one
    kernel call that could carry it (`certus_strat_batch.py`) passes 0.0 by position."""

    def test_no_field_shows_it(self, strat_window):
        assert "machine_sampling_dd" not in strat_window.widgets

    def test_the_status_banner_no_longer_reports_it(self, strat_window):
        assert "machine_sampling_dd" not in [key for key, *_ in strat_window._MACHINE_SOURCES]
        strat_window._refresh_machine_status()
        banner = strat_window.machine_status.text()
        assert "lissage de lecture" in banner, "premise: the banner reports the sources"
        assert "grille machine" not in banner

    @pytest.mark.parametrize("mode", MODES)
    def test_no_mode_puts_it_in_the_parameters(self, strat_window, mode):
        strat_window.widgets["execution_mode"].setCurrentText(mode)
        assert "machine_sampling_dd" not in strat_window.collect_params()

    def test_a_file_that_sets_it_still_loads_and_says_it_is_ignored(self, strat_window, tmp_path):
        with _captured(strat_window.logger) as lines:
            _load(strat_window, tmp_path, machine_sampling_dd=0.125)
        assert strat_window._loaded_config.get("machine_sampling_dd") == 0.125
        told = _told_ignored(lines)
        assert len(told) == 1 and "machine_sampling_dd" in told[0], lines
        assert "machine_sampling_dd" not in strat_window.collect_params()

    def test_saving_no_longer_writes_it(self, strat_window, tmp_path, monkeypatch):
        assert "machine_sampling_dd" not in _save(strat_window, tmp_path, monkeypatch)


def _string_constants(module) -> set[str]:
    """The string literals of a module's CODE -- comments are not in the AST."""
    tree = ast.parse(inspect.getsource(module))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


class TestDpYieldWeight:
    """`dp_yield_weight` went from the file into `collect_params`, and the full pipeline added
    `w x (-log(1 - p))` to a cost map built from `raw_results_sq` -- whose entries carry no
    crash rate. The yield term was zero at every weight (the map came out identical, bit for
    bit, at 1, 200 and 1e6), and that map feeds the fusion heuristics of the inheritance
    step, not the per-block DP that the `[YIELD]` log line announced."""

    @pytest.mark.parametrize("mode", MODES)
    def test_no_mode_puts_it_in_the_parameters(self, strat_window, mode):
        strat_window.widgets["execution_mode"].setCurrentText(mode)
        assert "dp_yield_weight" not in strat_window.collect_params()

    def test_a_file_that_sets_it_still_loads_and_says_it_is_ignored(self, strat_window, tmp_path):
        with _captured(strat_window.logger) as lines:
            _load(strat_window, tmp_path, dp_yield_weight=200.0)
        assert strat_window._loaded_config.get("dp_yield_weight") == 200.0
        told = _told_ignored(lines)
        assert len(told) == 1 and "dp_yield_weight" in told[0], lines
        assert "dp_yield_weight" not in strat_window.collect_params()

    def test_the_pipeline_no_longer_reads_it(self):
        from certus.workers import certus_strat_workers_pipeline as pipeline

        constants = _string_constants(pipeline)
        assert "raw_results_sq" in constants, "premise: the pipeline code is the one read"
        assert "dp_yield_weight" not in constants

    def test_no_helper_still_claims_to_build_the_dp_objective(self):
        """Once the setting was gone the two helpers had no caller left, and their
        docstrings still called their output "the DP objective when w > 0"."""
        from certus.core import certus_strat_ranking as ranking

        assert hasattr(ranking, "mine_strategies_for_block_count"), "premise: the module"
        assert not hasattr(ranking, "build_yield_cost_map")
        assert not hasattr(ranking, "combine_cost_and_yield")


class TestSeelEquivalenceHalfWidth:
    """`seel_equivalence_half_width` defined a RELATIVE equivalence class for SEEL (6 % of
    the value, `SCORE_RESOLUTION_REL`) that no ranking applied: its only callers were its own
    tests. `rank_key_seel_yield_margin` bins at the fixed 0.01 nm step decided on 2026-08-14,
    and never read the `score_resolution_rel` argument it accepted."""

    def test_the_rule_no_ranking_applied_is_gone(self):
        from certus.core import certus_strat_ranking as ranking

        assert hasattr(ranking, "SEEL_RESOLUTION_NM"), "premise: the applied step stays"
        assert not hasattr(ranking, "seel_equivalence_half_width")
        assert not hasattr(ranking, "SCORE_RESOLUTION_REL")

    def test_the_ranking_key_accepts_no_argument_it_ignores(self):
        from certus.core.certus_strat_ranking import rank_key_seel_yield_margin

        assert list(inspect.signature(rank_key_seel_yield_margin).parameters) == [
            "seel_nm",
            "crash_rate",
            "critical_margin_in_A",
        ]


#: What each mode has always set, copied from the `collect_params` of e3ce77d. Written out
#: here rather than read from the code, so that the tests also hold the budgets themselves.
MODE_BUDGETS = {
    "fast": {"robustness_num_runs": 50, "consensus_num_runs": 50, "n_screen_runs": 10,
             "elite_rounds": 1, "dp_top_k": 20, "k_keep_survivors": 6},
    "premium": {"robustness_num_runs": 150, "consensus_num_runs": 150, "n_screen_runs": 25,
                "elite_rounds": 2, "dp_top_k": 40, "k_keep_survivors": 10,
                "mining_candidates_limit": 3000},
    "deep": {"robustness_num_runs": 300, "consensus_num_runs": 300, "n_screen_runs": 50,
             "elite_rounds": 3, "dp_top_k": 100, "k_keep_survivors": 25,
             "mining_candidates_limit": 10000},
    # `phase_a_keep_limit` (200) and `screening_keep_top_k` (20) are no longer set: no computing line
    # read them, and they left with the six settings of test_strat_settings_nothing_reads.py.
    "extreme": {"robustness_num_runs": 300, "consensus_num_runs": 300, "n_screen_runs": 50,
                "elite_rounds": 3, "dp_top_k": 100, "k_keep_survivors": 40,
                "mining_candidates_limit": 12000, "top_k_parents": 80,
                "max_fusions_per_parent": 15},
}


def _mode_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith("[MODE]")]


class TestTheModeOverrideIsSaid:
    """The execution mode sets its budgets whatever the configuration states: loaded in the
    application, the reference file declares `robustness_num_runs` 300 and runs at 150 in
    `premium`, and nothing said so. The mode still wins; `collect_params` now says it."""

    def test_the_reference_file_is_told_it_runs_at_150_where_it_declares_300(
        self, strat_window, tmp_path
    ):
        cfg = _load(strat_window, tmp_path)
        assert cfg["execution_mode"] == "premium", "premise"
        assert str(cfg["robustness_num_runs"]) == "300", "premise"
        with _captured(strat_window.logger) as lines:
            params = strat_window.collect_params()
        assert params["robustness_num_runs"] == 150, "the mode still wins: no run changes"
        said = _mode_lines(lines)
        assert len(said) == 1, lines
        assert "robustness_num_runs 300 -> 150 (overridden)" in said[0], said[0]

    @pytest.mark.parametrize("mode", MODES)
    def test_every_budget_the_mode_sets_is_said_with_both_values(self, strat_window, mode):
        strat_window.widgets["execution_mode"].setCurrentText(mode)
        with _captured(strat_window.logger) as lines:
            params = strat_window.collect_params()
        said = _mode_lines(lines)
        assert len(said) == 1, lines
        body = said[0].split(": ", 1)[1]
        for key, value in MODE_BUDGETS[mode].items():
            assert params[key] == value, f"{mode}: {key} is no longer what the mode set"
            assert re.search(rf"(^|, ){key} \S+ -> {value}( \(overridden\))?(,|$)", body), (
                f"{mode}: {key} is not said with both values: {said[0]}"
            )
        assert said[0].startswith(f"[MODE] {mode.upper()} sets {len(MODE_BUDGETS[mode])} budgets")

    def test_it_is_said_once_per_configuration_not_at_every_call(self, strat_window):
        with _captured(strat_window.logger) as lines:
            for _ in range(3):
                strat_window.collect_params()
        assert len(_mode_lines(lines)) == 1, "plots and exports call collect_params too"
        strat_window.widgets["execution_mode"].setCurrentText("deep")
        with _captured(strat_window.logger) as lines:
            strat_window.collect_params()
        assert len(_mode_lines(lines)) == 1, "another configuration is said again"
