"""Tests for certus_strat_context.py — DI container.

Covers:
- StratContext creation, activation, nesting
- Singleton pattern (get_current / set_current)
- emit_stat batching logic
- flush_stats
- Cache management
- StratContextManager (context manager protocol)
- get_context helper
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus.utils.certus_strat_context import StratContext, StratContextManager, get_context


@pytest.fixture(autouse=True)
def _reset_global_context():
    """Reset global context before and after each test."""
    prev = StratContext.get_current()
    StratContext.set_current(None)
    yield
    StratContext.set_current(prev)


class TestStratContextCreation:
    def test_default_construction(self):
        ctx = StratContext()
        assert ctx.material_db is None
        assert ctx.stats_queue is None
        assert ctx.sp_buffer == 0

    def test_with_material_db(self):
        db = MagicMock()
        ctx = StratContext(material_db=db)
        assert ctx.material_db is db

    def test_post_init_creates_lock(self):
        ctx = StratContext()
        assert ctx.sp_lock is not None


class TestSingletonPattern:
    def test_no_context_initially(self):
        assert StratContext.get_current() is None

    def test_set_and_get(self):
        ctx = StratContext()
        StratContext.set_current(ctx)
        assert StratContext.get_current() is ctx

    def test_set_none(self):
        ctx = StratContext()
        StratContext.set_current(ctx)
        StratContext.set_current(None)
        assert StratContext.get_current() is None


class TestContextManagerProtocol:
    def test_activate_sets_current(self):
        ctx = StratContext()
        with ctx.activate():
            assert StratContext.get_current() is ctx
        assert StratContext.get_current() is None

    def test_nested_contexts(self):
        ctx1 = StratContext()
        ctx2 = StratContext()
        with ctx1.activate():
            assert StratContext.get_current() is ctx1
            with ctx2.activate():
                assert StratContext.get_current() is ctx2
            assert StratContext.get_current() is ctx1
        assert StratContext.get_current() is None

    def test_context_manager_returns_ctx(self):
        ctx = StratContext()
        with ctx.activate() as active:
            assert active is ctx

    def test_context_manager_restores_on_exception(self):
        ctx = StratContext()
        try:
            with ctx.activate():
                raise ValueError("test")
        except ValueError:
            pass
        assert StratContext.get_current() is None


class TestEmitStat:
    def test_sp_batching(self):
        """SP counter should batch until >= 500."""
        queue = MagicMock()
        ctx = StratContext(stats_queue=queue)
        for _ in range(499):
            ctx.emit_stat("SP", 1)
        queue.put.assert_not_called()
        # 500th should flush
        ctx.emit_stat("SP", 1)
        queue.put.assert_called_once_with(("SP", 500))

    def test_non_sp_immediate(self):
        """Non-SP counters should emit immediately."""
        queue = MagicMock()
        ctx = StratContext(stats_queue=queue)
        ctx.emit_stat("MS", 5)
        queue.put.assert_called_once_with(("MS", 5))

    def test_no_queue_no_crash(self):
        ctx = StratContext()
        ctx.emit_stat("SP", 1)  # Should not raise
        ctx.emit_stat("MS", 1)

    def test_broken_pipe_handled(self):
        queue = MagicMock()
        queue.put.side_effect = BrokenPipeError
        ctx = StratContext(stats_queue=queue)
        ctx.emit_stat("MS", 1)  # Should not raise


class TestFlushStats:
    def test_flush_sends_buffered(self):
        queue = MagicMock()
        ctx = StratContext(stats_queue=queue)
        for _ in range(100):
            ctx.emit_stat("SP", 1)
        queue.put.assert_not_called()
        ctx.flush_stats()
        queue.put.assert_called_once_with(("SP", 100))

    def test_flush_empty_noop(self):
        queue = MagicMock()
        ctx = StratContext(stats_queue=queue)
        ctx.flush_stats()
        queue.put.assert_not_called()

    def test_flush_resets_buffer(self):
        queue = MagicMock()
        ctx = StratContext(stats_queue=queue)
        ctx.emit_stat("SP", 10)
        ctx.flush_stats()
        assert ctx.sp_buffer == 0


class TestCacheManagement:
    def test_clear_cache(self):
        ctx = StratContext()
        ctx.clues_cache["test"] = "data"
        ctx.clear_cache()
        assert len(ctx.clues_cache) == 0


class TestGetContext:
    def test_creates_default_if_none(self):
        assert StratContext.get_current() is None
        ctx = get_context()
        assert ctx is not None
        assert StratContext.get_current() is ctx

    def test_returns_existing(self):
        ctx = StratContext()
        StratContext.set_current(ctx)
        result = get_context()
        assert result is ctx


class TestWorkerInit:
    def test_worker_init_sets_current(self):
        ctx = StratContext()
        ctx.worker_init()
        assert StratContext.get_current() is ctx
