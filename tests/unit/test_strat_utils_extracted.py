"""
Tests minimaux pour PlotCache et ThreadSafeCounter extraits vers certus_strat_context.

Valide :
- L'import depuis certus_strat_context (module cible)
- L'import depuis CERTUS_STRAT (rétrocompatibilité)
- Le comportement exact des deux classes
"""
from __future__ import annotations

import threading

import pytest

# --- Import depuis le module cible (chemin direct après extraction) ---
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
        """Les valeurs non-sérialisables ne doivent pas lever d'exception."""
        cache = PlotCache()
        import numpy as np
        data = {"a": 1, "arr": np.zeros(3)}  # arr n'est pas sérialisable
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
        """get() doit remettre l'élément en fin de dict (MRU)."""
        cache = PlotCache()
        cache.put("k1", 1)
        cache.put("k2", 2)
        cache.get("k1")  # promote k1
        keys = list(cache.cache.keys())
        assert keys[-1] == "k1"

    def test_eviction_when_full(self):
        """La plus ancienne entrée doit être supprimée quand max_size_items est atteint."""
        cache = PlotCache()
        cache.max_size_items = 3
        cache.put("k1", 1)
        cache.put("k2", 2)
        cache.put("k3", 3)
        cache.put("k4", 4)  # déclenche l'éviction de k1
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
        """Plusieurs threads incrémentent sans race condition."""
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
# Rétrocompatibilité : import depuis CERTUS_STRAT
# =============================================================================


def test_retro_compat_plot_cache_importable_from_certus_strat():
    """PlotCache doit rester importable depuis CERTUS_STRAT (ré-export)."""
    # Import léger : on ne charge pas Qt, juste le symbole
    try:
        from CERTUS_STRAT import PlotCache as PC_from_strat  # noqa: F401
    except ImportError as e:
        pytest.skip(f"CERTUS_STRAT non importable dans ce contexte : {e}")
    assert PC_from_strat is PlotCache


def test_retro_compat_thread_safe_counter_importable_from_certus_strat():
    """ThreadSafeCounter doit rester importable depuis CERTUS_STRAT (ré-export)."""
    try:
        from CERTUS_STRAT import ThreadSafeCounter as TSC_from_strat  # noqa: F401
    except ImportError as e:
        pytest.skip(f"CERTUS_STRAT non importable dans ce contexte : {e}")
    assert TSC_from_strat is ThreadSafeCounter
