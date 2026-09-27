"""D3 -- the ranking logs through the logger the pipeline carries, not into the void.

`mine_strategies_for_block_count` logged to `logging.getLogger("ThinFilm")`, which has no
handler, and neither has the root: Python drops every `info` it receives (its last-resort
handler only lets WARNING and above reach stderr). Measured in the application on
2026-09-27: `ThinFilm` handlers [], root handlers [], INFO enabled False. So the miner's
unconditional "Mining: n_blocks=..." line never reached a campaign log, while the worker's
own `W{n_blk}` logger did. The miner now takes the caller's logger -- `params["logger"]`,
which is the `W{n_blk}` logger inside a block worker -- and falls back on `ThinFilm` only
when it is given none.

The deliberate mute around `calculate_dynamics_ULTIMATE` (`_RateSwingContext.swing_at`)
works on `ThinFilm` and must keep working: the last class guards it.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pytest

from certus.core.certus_strat_ranking import mine_strategies_for_block_count

#: 700 nm is admissible on every layer and the cheapest on none (as in test_wl_coverage).
RAW = {
    0: [{"wl": 500.0, "cost": 1.0}, {"wl": 600.0, "cost": 2.0}, {"wl": 700.0, "cost": 9.0}],
    1: [{"wl": 500.0, "cost": 1.0}, {"wl": 600.0, "cost": 2.0}, {"wl": 700.0, "cost": 8.0}],
    2: [{"wl": 500.0, "cost": 2.0}, {"wl": 600.0, "cost": 1.0}, {"wl": 700.0, "cost": 9.0}],
    3: [{"wl": 500.0, "cost": 2.0}, {"wl": 600.0, "cost": 1.0}, {"wl": 700.0, "cost": 9.0}],
}


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def carried():
    """A logger set up like the worker's `W{n_blk}`: its own handler, no propagation."""
    logger = logging.getLogger("test_strat_ranking_logger.carried")
    handler = _Lines()
    previous = (logger.level, logger.propagate)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield logger, handler
    logger.removeHandler(handler)
    logger.setLevel(previous[0])
    logger.propagate = previous[1]


def _mine(**kw):
    return mine_strategies_for_block_count(
        n_blocks=2, raw_results_thickness=RAW, raw_results_sq=RAW, num_layers=4, top_k=3, **kw
    )


def _fingerprint(strategies: list[dict]) -> list[tuple]:
    """Identifier, blocks and cost of each strategy, floats as `float.hex` (CLAUDE.md C1)."""
    return [
        (
            s["strategy_id"],
            s.get("origin_details"),
            [(b["start"], b["end"], float(b["wavelength"]).hex()) for b in s["blocks"]],
            float(s.get("total_cost", 0.0)).hex(),
        )
        for s in strategies
    ]


class TestTheMinerLogsWhereItIsTold:
    def test_the_mining_line_reaches_the_carried_logger(self, carried):
        logger, handler = carried
        _mine(logger=logger)
        assert [line for line in handler.lines if line.startswith("Mining: n_blocks=2")], handler.lines

    def test_so_do_its_coverage_lines(self, carried):
        logger, handler = carried
        _mine(logger=logger, enable_wl_coverage=True)
        assert [line for line in handler.lines if "[WL-COUVERTURE]" in line], handler.lines

    def test_the_strategies_do_not_depend_on_the_logger(self, carried):
        """Where the lines go changes nothing mined, to the bit."""
        logger, _ = carried
        for coverage in (False, True):
            without = _fingerprint(_mine(enable_wl_coverage=coverage))
            assert without, "premise: the miner returns strategies"
            assert _fingerprint(_mine(enable_wl_coverage=coverage, logger=logger)) == without

    def test_given_no_logger_it_still_falls_back_on_thinfilm(self, caplog):
        """The former path, for every caller that passes none. Passes before and after."""
        with caplog.at_level(logging.INFO, logger="ThinFilm"):
            _mine()
        assert [
            r for r in caplog.records
            if r.name == "ThinFilm" and r.getMessage().startswith("Mining: n_blocks=2")
        ]


class TestTheCallersHandTheirLogger:
    def test_the_block_worker_hands_its_w_logger(self, monkeypatch):
        from certus.workers import certus_strat_workers as workers

        seen: dict = {}

        def fake_miner(*args, **kwargs):
            seen.update(kwargs)
            return []

        monkeypatch.setattr(workers, "mine_strategies_for_block_count", fake_miner)
        pre_calc = {"raw_results_thickness": RAW, "raw_results_sq": RAW, "num_layers": 4}
        params = {"sym_enable": False}
        out = workers._parallel_block_worker(
            (2, pre_calc, params, 1, 1, 1, [], {"wl": None, "size": 0})
        )
        assert out["strategies_results"] == [], "premise: the worker went through the miner"
        assert seen.get("logger") is logging.getLogger("W2")
        assert seen["logger"] is params["logger"], "the logger the pipeline carries"

    def test_the_sequential_phase_b_hands_the_params_logger(self, monkeypatch, carried):
        from certus.core import certus_strat_pipeline as pipeline

        logger, _ = carried
        seen: list = []

        def fake_miner(*args, **kwargs):
            seen.append(kwargs.get("logger"))
            return []

        monkeypatch.setattr(pipeline, "mine_strategies_for_block_count", fake_miner)
        phase_a = {"raw_results_thickness": RAW, "raw_results_sq": RAW, "num_layers": 4}
        out = pipeline._prepare_block_strategy_phase_b(phase_a, {"logger": logger})
        assert out["all_strategies"] == []
        assert seen, "premise: Phase B went through the miner"
        assert all(s is logger for s in seen), seen


class TestTheDeliberateMuteStillHolds:
    """`_RateSwingContext.swing_at` hands `calculate_dynamics_ULTIMATE` ONE wavelength, whose
    standard deviation is zero by construction, so its "suspiciously flat" warnings would fire
    on every call; `swing_at` raises `ThinFilm` to ERROR around the call, then restores it.
    D3 routes the ranking elsewhere and leaves this alone. Guards: pass before and after."""

    @staticmethod
    def _context_args() -> dict:
        return {
            "p_thick_nominal": np.array([100.0]),
            "clues_at_wl": {600.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},
            "nominal_matrix_cache": np.zeros((1, 1, 2, 2), dtype=np.complex128),
            "all_wls": np.array([600.0]),
        }

    def test_unmuted_the_same_call_does_warn(self, caplog):
        """The negative control: without the mute there IS something to silence."""
        from certus.utils.certus_strat_service import calculate_dynamics_ULTIMATE

        a = self._context_args()
        with caplog.at_level(logging.DEBUG, logger="ThinFilm"):
            calculate_dynamics_ULTIMATE(
                np.array([600.0]), 0, 100.0, a["clues_at_wl"], a["nominal_matrix_cache"], a["all_wls"]
            )
        assert [r for r in caplog.records if r.name == "ThinFilm" and "[DYNAMICS]" in r.getMessage()]

    def test_the_swing_probe_mutes_it_and_restores_the_level(self, caplog):
        from certus.core.certus_strat_robustness import _RateSwingContext

        context = _RateSwingContext(threshold=0.02, **self._context_args())
        with caplog.at_level(logging.DEBUG, logger="ThinFilm"):
            swing = context.swing_at(0, 600.0)
            level_after = logging.getLogger("ThinFilm").level
        assert math.isfinite(swing), "premise: the probe really called the dynamics"
        assert context.n_absents == 0
        assert not [
            r for r in caplog.records if r.name == "ThinFilm" and r.levelno >= logging.WARNING
        ]
        assert level_after == logging.DEBUG, "the level is restored after the call"
