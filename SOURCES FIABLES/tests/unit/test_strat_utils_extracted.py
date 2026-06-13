"""
Minimal tests for PlotCache and ThreadSafeCounter extracted to certus_strat_context.

Validates:
- Import from certus_strat_context (target module)
- Import from CERTUS_STRAT (backward compatibility)
- Exact behavior of the two classes
"""
from __future__ import annotations

import threading

import pytest

# --- Import from the target module (direct path after extraction) ---
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter


# =============================================================================
# PlotCache
# =============================================================================


class TestPlotCacheHash:
    def test_dict_with_scalars_is_stable(self):
        cache = PlotCache()
        data = {"a": 1, "b": 2.5, "c": "hello"}
        h1 = cache.get_hash(data)
        h2 = cache.get_hash(data)
        assert h1 == h2

    def test_different_dicts_give_different_hashes(self):
        cache = PlotCache()
        h1 = cache.get_hash({"x": 1})
        h2 = cache.get_hash({"x": 2})
        assert h1 != h2

    def test_non_dict_object_returns_string_hash(self):
        cache = PlotCache()
        h = cache.get_hash([1, 2, 3])
        assert isinstance(h, str)
        assert len(h) > 0

    def test_non_serializable_values_are_filtered(self):
        """Non-serializable values must not raise an exception."""
        cache = PlotCache()
        import numpy as np
        data = {"a": 1, "arr": np.zeros(3)}  # arr is not serializable
        h = cache.get_hash(data)
        assert isinstance(h, str)


class TestPlotCachePutGet:
    def test_put_and_get_returns_item(self):
        cache = PlotCache()
        cache.put("k1", "value1")
        assert cache.get("k1") == "value1"

    def test_get_missing_key_returns_none(self):
        cache = PlotCache()
        assert cache.get("nonexistent") is None

    def test_lru_promotion(self):
        """get() must put the element at the end of the dict (MRU)."""
        cache = PlotCache()
        cache.put("k1", 1)
        cache.put("k2", 2)
        cache.get("k1")  # promote k1
        keys = list(cache.cache.keys())
        assert keys[-1] == "k1"

    def test_eviction_when_full(self):
        """The oldest entry must be removed when max_size_items is reached."""
        cache = PlotCache()
        cache.max_size_items = 3
        cache.put("k1", 1)
        cache.put("k2", 2)
        cache.put("k3", 3)
        cache.put("k4", 4)  # triggers eviction of k1
        assert cache.get("k1") is None
        assert cache.get("k4") == 4

    def test_size_stays_bounded(self):
        cache = PlotCache()
        cache.max_size_items = 5
        for i in range(20):
            cache.put(f"key_{i}", i)
        assert len(cache.cache) <= cache.max_size_items


# =============================================================================
# ThreadSafeCounter
# =============================================================================


class TestThreadSafeCounter:
    def test_initial_count_is_zero(self):
        c = ThreadSafeCounter()
        assert c._count == 0

    def test_increment_returns_new_value(self):
        c = ThreadSafeCounter()
        assert c.increment() == 1
        assert c.increment() == 2

    def test_reset_sets_count_to_zero(self):
        c = ThreadSafeCounter()
        c.increment()
        c.increment()
        c.reset()
        assert c._count == 0

    def test_set_signal_stores_value(self):
        c = ThreadSafeCounter()
        sentinel = object()
        c.set_signal(sentinel)
        assert c.signal is sentinel

    def test_thread_safe_increments(self):
        """Multiple threads increment without race condition."""
        c = ThreadSafeCounter()
        n_threads = 20
        n_increments = 50

        def worker():
            for _ in range(n_increments):
                c.increment()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert c._count == n_threads * n_increments


# =============================================================================
# Backward compatibility: import from CERTUS_STRAT
# =============================================================================


def test_retro_compat_plot_cache_importable_from_certus_strat():
    """PlotCache must remain importable from CERTUS_STRAT (re-export)."""
    # Lightweight import: we do not load Qt, just the symbol
    try:
        from CERTUS_STRAT import PlotCache as PC_from_strat  # noqa: F401
    except ImportError as e:
        pytest.skip(f"CERTUS_STRAT not importable in this context: {e}")
    assert PC_from_strat is PlotCache


def test_retro_compat_thread_safe_counter_importable_from_certus_strat():
    """ThreadSafeCounter must remain importable from CERTUS_STRAT (re-export)."""
    try:
        from CERTUS_STRAT import ThreadSafeCounter as TSC_from_strat  # noqa: F401
    except ImportError as e:
        pytest.skip(f"CERTUS_STRAT not importable in this context: {e}")
    assert TSC_from_strat is ThreadSafeCounter

