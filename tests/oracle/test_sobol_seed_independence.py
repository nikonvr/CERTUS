"""Noise draws from the robustness consensus must be independent.

Consensus averages results across multiple seeds to estimate robustness
of a stack. If two members receive the SAME noise, their agreement no longer has any
statistical value: it measures an identity, not a convergence. This file freezes
the independence of the draws.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_strat_robustness import _get_cached_sobol_noise


# Reproduces the generation of consensus seeds:
# certus/utils/certus_strat_context.py:598, stride value 1 by default (:610).
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

    CAUTION: the derivation was ``local_seed = base_seed + noise_idx``. Combined
    to consecutive consensus seeds (stride = 1 by default), it produced
    un recouvrement triangulaire massif — (graine 42, niveau 1) et (graine 43,
    level 0) gave the same seed, therefore the same noise:

        3 graines x 3 niveaux =  9 tirages ->  5 distincts (44 % perdus)
        5 graines x 4 niveaux = 20 tirages ->  8 distincts (60 % perdus)
        8 graines x 5 niveaux = 40 tirages -> 12 distincts (70 % perdus)

    Sharing the noise between members inflates their apparent agreement, so OVERESTIMATES the
    robustness — the opposite of what is asked of this analysis.
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
    """Same input, same noise: the analysis must remain reproducible."""
    first = _get_cached_sobol_noise(42, 3, 8, 4)
    second = _get_cached_sobol_noise(42, 3, 8, 4)

    assert np.array_equal(first, second)


def test_bruit_dans_les_bornes_physiques() -> None:
    """The noise is clipped in [-1, 1] and centered: contract of the law used."""
    noise = _get_cached_sobol_noise(42, 0, 16, 4)

    assert np.all(np.isfinite(noise))
    assert noise.min() >= -1.0
    assert noise.max() <= 1.0
