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
