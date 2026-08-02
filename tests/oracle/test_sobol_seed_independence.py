"""Les tirages de bruit du consensus de robustesse doivent être indépendants.

Le consensus moyenne les résultats sur plusieurs graines afin d'estimer la robustesse
d'un empilement. Si deux membres reçoivent le MÊME bruit, leur accord n'a plus de
valeur statistique : il mesure une identité, pas une convergence. Ce fichier fige
l'indépendance des tirages.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_strat_robustness import _get_cached_sobol_noise


# Reproduit la génération de graines du consensus :
# certus/utils/certus_strat_context.py:598, stride valant 1 par défaut (:610).
def _consensus_seeds(base_seed: int, num_seeds: int, stride: int = 1) -> list[int]:
    return [base_seed + i * stride for i in range(num_seeds)]


@pytest.mark.parametrize(
    "num_seeds, num_levels",
    [(3, 3), (5, 4), (8, 5)],
)
def test_pas_de_bruit_partage_entre_membres_du_consensus(
    num_seeds: int, num_levels: int
) -> None:
    """Chaque couple (graine de consensus, niveau de bruit) doit avoir SON tirage.

    GARDE-FOU : la dérivation était ``local_seed = base_seed + noise_idx``. Combinée
    à des graines de consensus consécutives (stride = 1 par défaut), elle produisait
    un recouvrement triangulaire massif — (graine 42, niveau 1) et (graine 43,
    niveau 0) donnaient la même graine, donc le même bruit :

        3 graines x 3 niveaux =  9 tirages ->  5 distincts (44 % perdus)
        5 graines x 4 niveaux = 20 tirages ->  8 distincts (60 % perdus)
        8 graines x 5 niveaux = 40 tirages -> 12 distincts (70 % perdus)

    Partager le bruit entre membres gonfle leur accord apparent, donc SURESTIME la
    robustesse — l'inverse de ce qu'on demande à cette analyse.
    """
    num_runs = 8
    num_layers = 4

    signatures = set()
    for seed in _consensus_seeds(42, num_seeds):
        for level in range(num_levels):
            noise = _get_cached_sobol_noise(seed, level, num_runs, num_layers)
            signatures.add(np.asarray(noise, dtype=np.float64).tobytes())

    expected = num_seeds * num_levels
    assert len(signatures) == expected, (
        f"{expected} tirages demandes mais seulement {len(signatures)} bruits "
        f"distincts : des membres du consensus partagent leur realisation."
    )


def test_tirages_reproductibles() -> None:
    """Même entrée, même bruit : l'analyse doit rester reproductible."""
    first = _get_cached_sobol_noise(42, 3, 8, 4)
    second = _get_cached_sobol_noise(42, 3, 8, 4)

    assert np.array_equal(first, second)


def test_bruit_dans_les_bornes_physiques() -> None:
    """Le bruit est écrêté dans [-1, 1] et centré : contrat de la loi utilisée."""
    noise = _get_cached_sobol_noise(42, 0, 16, 4)

    assert np.all(np.isfinite(noise))
    assert noise.min() >= -1.0
    assert noise.max() <= 1.0
