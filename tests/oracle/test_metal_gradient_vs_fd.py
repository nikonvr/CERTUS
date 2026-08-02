"""Le gradient du bicouche métallique doit être la dérivée de son coût, composante par composante.

Ce gradient portait un défaut d'indexation : la boucle sur les positions de nœuds
écrivait ``grad[offset + 2 * num_knots + i]`` alors que le bloc des nœuds k s'étend
jusqu'à ``offset + 2 * spline_knot_count``, avec ``spline_knot_count = num_knots + 1``.
Deux positions trop tôt, donc :

    k[3], k[4]              gradients écrasés par ceux de lambda
    lambda[0]               recevait le gradient de lambda[2]
    lambda[1], lambda[2]    exactement 0, alors que la dérivée est non nulle

L'optimiseur partait dans la mauvaise direction sur les deux derniers nœuds k et ne
déplaçait jamais les dernières positions de nœuds. Aucune erreur n'était levée.

Le vecteur d'optimisation mêle des grandeurs d'échelles très différentes — épaisseurs
en nm, coefficient de Cauchy de l'ordre du millier, indices d'ordre 1, positions en
nm. La vérification est donc faite PAR BLOC, chacun contre sa propre norme.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from gradient_harness import check_gradient  # noqa: E402

from certus.physics.gradient_metal import (  # noqa: E402
    compute_metal_bilayer_gradient_analytic,
)


WAVELENGTHS = np.linspace(400.0, 900.0, 60)
TARGET_REFLECTANCE = np.full(WAVELENGTHS.size, 0.35)
# Substrat type silicium : fortement réfringent et légèrement absorbant.
SUBSTRATE = np.full(WAVELENGTHS.size, complex(4.0, -0.05), dtype=np.complex128)


def _pack(num_knots: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Vecteur d'optimisation et découpage en familles de paramètres.

    Disposition : [eM, eL, n_inf, A] [n x (num_knots+1)] [k x (num_knots+1)]
                  [lambda x (num_knots-1)]
    """
    knot_values = num_knots + 1
    inner_lambda = knot_values - 2

    thicknesses = [25.0, 90.0]
    cauchy = [1.46, 3000.0]
    n_nodes = np.linspace(2.60, 2.00, knot_values)
    k_nodes = np.linspace(0.90, 0.40, knot_values)
    inner = np.linspace(
        WAVELENGTHS.min() + 100.0, WAVELENGTHS.max() - 120.0, inner_lambda
    )

    params = np.concatenate((thicknesses, cauchy, n_nodes, k_nodes, inner))

    offset = 4
    blocks = [
        (0, 2),  # epaisseurs eM, eL
        (2, 4),  # Cauchy n_inf, A
        (offset, offset + knot_values),  # noeuds n
        (offset + knot_values, offset + 2 * knot_values),  # noeuds k
        (offset + 2 * knot_values, params.size),  # positions lambda
    ]
    return params, blocks


@pytest.mark.parametrize("num_knots", [3, 4, 6], ids=["K3", "K4", "K6"])
def test_gradient_metal_bilayer_coincide_avec_les_differences_finies(
    num_knots: int,
) -> None:
    """GARDE-FOU : toutes les familles de paramètres, pas seulement les premières.

    Le défaut d'indexation ne touchait que la FIN du vecteur — nœuds k terminaux et
    positions lambda. Un test qui ne vérifierait que les épaisseurs et les indices
    serait passé sans rien voir.
    """
    params, blocks = _pack(num_knots)

    def cost_and_grad(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        return compute_metal_bilayer_gradient_analytic(
            candidate,
            num_knots,
            WAVELENGTHS,
            TARGET_REFLECTANCE,
            1.0,
            SUBSTRATE,
        )

    check_gradient(
        cost_and_grad,
        params,
        step=1e-6,
        # Les gradients des positions lambda sont eux-memes calcules par differences
        # finies internes (h = 1e-5) : on compare donc une FD a une FD, ce qui est
        # legitimement plus bruite qu'une comparaison a une derivee analytique.
        rtol=2e-3,
        blocks=blocks,
        label=f"gradient metal bicouche K={num_knots}",
    )


def test_aucune_composante_du_gradient_n_est_muette() -> None:
    """Aucune famille de paramètres ne doit recevoir un gradient identiquement nul.

    C'est le symptôme direct du défaut d'indexation : les dernières positions lambda
    n'étaient jamais écrites et restaient à zéro. Un paramètre dont le gradient est
    toujours nul n'est jamais optimisé — silencieusement.
    """
    num_knots = 4
    params, blocks = _pack(num_knots)

    _, gradient = compute_metal_bilayer_gradient_analytic(
        params, num_knots, WAVELENGTHS, TARGET_REFLECTANCE, 1.0, SUBSTRATE
    )
    gradient = np.asarray(gradient, dtype=np.float64)

    for start, stop in blocks:
        block = gradient[start:stop]
        assert np.max(np.abs(block)) > 0.0, (
            f"bloc [{start}:{stop}] entierement nul — "
            f"ces parametres ne seront jamais optimises"
        )
