"""A failed phase B block is recorded, so the report can say the ranking is incomplete (audit 2026-11-15, L3-m7)."""

from __future__ import annotations

import inspect

from certus.utils.certus_strat_context import _note_failed_phase_b_block
from certus.workers import certus_strat_workers as workers


def test_a_failed_block_is_recorded_and_the_next_block_inherits_nothing() -> None:
    params: dict = {}
    assert _note_failed_phase_b_block(params, 5) == []
    assert _note_failed_phase_b_block(params, 4) == []
    assert params["phase_b_failed_blocks"] == [5, 4]


def test_every_error_branch_of_phase_b_records_its_block() -> None:
    source = inspect.getsource(workers._run_phaseB_parallel_execution)
    assert source.count("_note_failed_phase_b_block(params, n_blk)") == 3
    assert 'params["phase_b_failed_blocks"] = []' in source
