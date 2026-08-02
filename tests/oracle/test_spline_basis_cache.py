"""Contrats du cache de base spline.

``SplineBasisCache`` remplace la construction d'un ``CubicSpline`` par un produit
matrice-vecteur. Deux choses doivent rester vraies : la matrice reproduit exactement
l'interpolation qu'elle prétend remplacer, et la clé de cache identifie correctement
les entrées équivalentes.
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
    """B @ v doit reproduire CubicSpline(bc_type="natural") à la précision machine.

    La condition aux limites compte : le projet utilise "natural" (13 occurrences
    contre 1 "not-a-knot" explicite). Comparer au défaut de scipy — not-a-knot —
    donne un écart de 7,4e-3, qui n'est pas un défaut mais un changement de
    convention. Ce test fige la bonne référence.
    """
    basis = SplineBasisCache.get(KNOTS, TARGETS)
    values = np.array([2.30, 2.10, 2.00, 1.95])

    expected = CubicSpline(KNOTS, values, bc_type="natural")(TARGETS)

    assert np.max(np.abs(basis @ values - expected)) < 1e-12


def test_positions_de_noeuds_differentes_donnent_des_bases_differentes() -> None:
    """GARDE-FOU : le cache ne doit JAMAIS rendre une base périmée.

    La clé inclut les positions de nœuds, donc des nœuds mobiles produisent un
    échec de cache — coûteux, mais correct. Si un jour la clé cessait de les
    inclure, ce test attraperait la régression silencieuse la plus grave possible :
    une base calculée pour d'autres nœuds, donc un profil n,k faux.
    """
    moved = KNOTS.copy()
    moved[1] += 1e-4

    basis_a = SplineBasisCache.get(KNOTS, TARGETS)
    basis_b = SplineBasisCache.get(moved, TARGETS)

    assert basis_a is not basis_b
    assert not np.allclose(basis_a, basis_b)


def test_cle_deduplique_les_dtypes_equivalents() -> None:
    """float32 et float64 de mêmes valeurs doivent partager UNE entrée de cache.

    La clé est construite par .tobytes() : sans normalisation explicite en float64,
    les mêmes valeurs en float32 produiraient des octets différents et donc une
    seconde entrée, doublant le coût de construction.
    """
    SplineBasisCache.get(KNOTS, TARGETS)
    SplineBasisCache.get(KNOTS.astype(np.float32), TARGETS.astype(np.float32))

    assert len(SplineBasisCache._cache) == 1


def test_cache_touche_sur_appel_identique() -> None:
    """Deux appels identiques doivent rendre le MÊME objet, pas une copie."""
    first = SplineBasisCache.get(KNOTS, TARGETS)
    second = SplineBasisCache.get(KNOTS, TARGETS)

    assert first is second


def _knots(i: int) -> np.ndarray:
    """Un vecteur de nœuds distinct par indice, comme un pas de gradient."""
    k = KNOTS.copy()
    k[1] += 1e-3 * (i + 1)
    return k


def test_saturation_evince_une_entree_et_non_tout_le_cache() -> None:
    """GARDE-FOU : dépasser la borne ne doit JAMAIS vider le cache entier.

    Le garde-fou d'origine faisait ``if len(_cache) > 500: _cache.clear()``. Avec
    18 402 vecteurs de nœuds distincts sur un run réel de METAL_SINGLE, il vidait
    tout en boucle et jetait les entrées chaudes avec les froides. Ce test échoue
    sur cette version : après saturation, le cache y retombait à 1 entrée.
    """
    n = SplineBasisCache._MAX_ENTRIES + 20
    for i in range(n):
        SplineBasisCache.get(_knots(i), TARGETS)

    assert len(SplineBasisCache._cache) == SplineBasisCache._MAX_ENTRIES


def test_eviction_retire_la_plus_ancienne_utilisee() -> None:
    """La récence compte : une entrée réutilisée doit survivre à la saturation.

    C'est tout l'intérêt du LRU sur ce cache. Les pas de différences finies
    consécutifs partagent leurs nœuds ; une entrée qui vient de servir est celle
    qui resservira. L'évincer est exactement l'erreur que faisait le vidage total.
    """
    veteran = _knots(0)
    first = SplineBasisCache.get(veteran, TARGETS)

    # On sature le cache en réutilisant `veteran` à chaque tour : il est donc
    # toujours l'entrée la plus récemment utilisée, donc la dernière à évincer.
    # L'identité de l'objet est ce qui compte — une égalité numérique ne
    # distinguerait pas une entrée conservée d'une entrée reconstruite.
    for i in range(1, SplineBasisCache._MAX_ENTRIES + 20):
        SplineBasisCache.get(_knots(i), TARGETS)
        assert SplineBasisCache.get(veteran, TARGETS) is first
