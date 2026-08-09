"""Contrats du cache de base spline.

``SplineBasisCache`` remplace la construction d'un ``CubicSpline`` par un produit
matrice-vecteur. Deux choses doivent rester vraies : la matrice reproduit exactement
the interpolation it claims to replace, and the cache key correctly identifies
the equivalent entries.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from certus.physics.certus_optical_models import SplineBasisCache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Chaque test part d'un cache vide, et le laisse vide."""
    SplineBasisCache.clear()
    yield
    SplineBasisCache.clear()


KNOTS = np.array([400.0, 600.0, 800.0, 1000.0])
TARGETS = np.linspace(400.0, 1000.0, 601)


def test_basis_reproduit_exactement_le_spline_natural() -> None:
    """B @ v must reproduce CubicSpline(bc_type="natural") to machine precision.

    La condition aux limites compte : le projet utilise "natural" (13 occurrences
    against 1 explicit "not-a-knot"). Compare to scipy default — not-a-knot —
    gives a difference of 7.4e-3, which is not a fault but a change in
    convention. This test fixes the correct reference.
    """
    basis = SplineBasisCache.get(KNOTS, TARGETS)
    values = np.array([2.30, 2.10, 2.00, 1.95])

    expected = CubicSpline(KNOTS, values, bc_type="natural")(TARGETS)

    assert np.max(np.abs(basis @ values - expected)) < 1e-12


def test_positions_de_noeuds_differentes_donnent_des_bases_differentes() -> None:
    """GUARDS: the cache must NEVER make a database obsolete.

    The key includes node positions, so moving nodes produce a
    cache miss — expensive, but okay. If one day the key stopped working
    include, this test would catch the most severe silent regression possible:
    a base calculated for other nodes, therefore a false n,k profile.
    """
    moved = KNOTS.copy()
    moved[1] += 1e-4

    basis_a = SplineBasisCache.get(KNOTS, TARGETS)
    basis_b = SplineBasisCache.get(moved, TARGETS)

    assert basis_a is not basis_b
    assert not np.allclose(basis_a, basis_b)


def test_cle_deduplique_les_dtypes_equivalents() -> None:
    """float32 and float64 of same values ​​must share ONE cache entry.

    The key is constructed by .tobytes(): without explicit normalization to float64,
    the same values ​​in float32 would produce different bytes and therefore a
    second entry, doubling the construction cost.
    """
    SplineBasisCache.get(KNOTS, TARGETS)
    SplineBasisCache.get(KNOTS.astype(np.float32), TARGETS.astype(np.float32))

    assert len(SplineBasisCache._cache) == 1


def test_cache_touche_sur_appel_identique() -> None:
    """Two identical calls should return the SAME object, not a copy."""
    first = SplineBasisCache.get(KNOTS, TARGETS)
    second = SplineBasisCache.get(KNOTS, TARGETS)

    assert first is second


def _knots(i: int) -> np.ndarray:
    """A distinct vector of nodes per index, like a gradient step."""
    k = KNOTS.copy()
    k[1] += 1e-3 * (i + 1)
    return k


def test_saturation_evince_une_entree_et_non_tout_le_cache() -> None:
    """GUARD: exceeding the limit must NEVER clear the entire cache.

    Le garde-fou d'origine faisait ``if len(_cache) > 500: _cache.clear()``. Avec
    18,402 distinct node vectors on a real run of METAL_SINGLE, it was emptying
    everything looped and threw the hot starters in with the cold ones. This test fails
    on this version: after saturation, the cache fell back to 1 entry.
    """
    n = SplineBasisCache._MAX_ENTRIES + 20
    for i in range(n):
        SplineBasisCache.get(_knots(i), TARGETS)

    assert len(SplineBasisCache._cache) == SplineBasisCache._MAX_ENTRIES


def test_eviction_retire_la_plus_ancienne_utilisee() -> None:
    """Recency matters: a reused entry must survive saturation.

    This is the whole point of the LRU on this cache. No finite differences
    consecutive ones share their nodes; an entry that has just been used is the one
    who will serve again. Evicting it is exactly the mistake that the total dump made.
    """
    veteran = _knots(0)
    first = SplineBasisCache.get(veteran, TARGETS)

    #We saturate the cache by reusing `veteran` each turn: it is therefore
    #always the most recently used entry, therefore the last to be evicted.
    #The identity of the object is what matters — a numerical equality does not
    #would not distinguish a preserved entry from a reconstructed entry.
    for i in range(1, SplineBasisCache._MAX_ENTRIES + 20):
        SplineBasisCache.get(_knots(i), TARGETS)
        assert SplineBasisCache.get(veteran, TARGETS) is first
