"""The gradient of the metallic bilayer must be the derivative of its cost, component by component.

This gradient carried an indexing defect: the loop on the node positions
wrote ``grad[offset + 2 * num_knots + i]`` while the block of nodes k extends
up to ``offset + 2 * spline_knot_count``, with ``spline_knot_count = num_knots + 1``.
Two positions too early, therefore:

    k[3], k[4] gradients overwritten by those of lambda
    lambda[0]               recevait le gradient de lambda[2]
    lambda[1], lambda[2] exactly 0, while the derivative is non-zero

The optimizer was going in the wrong direction on the last two k nodes and was not
never moved the last node positions. No error was raised.

The optimization vector mixes quantities of very different scales — thicknesses
en nm, coefficient de Cauchy de l'ordre du millier, indices d'ordre 1, positions en
nm. The verification is therefore carried out PER BLOCK, each against its own standard.
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
# Silicon type substrate: highly refractive and slightly absorbent.
SUBSTRATE = np.full(WAVELENGTHS.size, complex(4.0, -0.05), dtype=np.complex128)


def _pack(num_knots: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Optimization vector and division into families of parameters.

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
    """GUARDS: all families of parameters, not just the first ones.

    The indexing defect only affected the END of the vector — k terminal nodes and
    lambda positions. A test that would only check thicknesses and indices
    would have passed without seeing anything.
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
        #The gradients of the lambda positions are themselves calculated by differences
        #internal finites (h = 1e-5): we therefore compare an FD to an FD, which is
        #legitimately noisier than a comparison to an analytical derivative.
        rtol=2e-3,
        blocks=blocks,
        label=f"gradient metal bicouche K={num_knots}",
    )


def test_aucune_composante_du_gradient_n_est_muette() -> None:
    """No family of parameters must receive an identically zero gradient.

    This is the direct symptom of the indexing fault: the last lambda positions
    were never written and remained at zero. A parameter whose gradient is
    always zero is never optimized — silently.
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
