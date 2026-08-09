"""Each analytical gradient must be the derivative of the cost it accompanies.

A false gradient does not change anything: it moves the optimum. These tests close this door
for all project functions that export a couple (cost, gradient).

See ``gradient_harness.py`` for the method and choice of step.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from gradient_harness import check_gradient, non_uniform_weights  # noqa: E402


# ── Corpus commun ────────────────────────────────────────────────────────────

WAVELENGTHS = np.linspace(450.0, 750.0, 14)
THICKNESSES = np.array([82.0, 118.0, 64.0, 131.0])
#Project order: index 0 = substrate rating, index N-1 = incident rating.
STACK_NK = [(2.30, 0.015), (1.46, 0.0), (2.30, 0.015), (1.46, 0.0)]
SUBSTRATE = 1.52


def _layers_matrix(n_wavelengths: int) -> np.ndarray:
    """(n_wls, n_layers) d'indices complexes, convention n - ik."""
    row = np.array([complex(n, -k) for n, k in STACK_NK], dtype=np.complex128)
    return np.tile(row, (n_wavelengths, 1))


def _substrate_vector(n_wavelengths: int) -> np.ndarray:
    return np.full(n_wavelengths, complex(SUBSTRATE, 0.0), dtype=np.complex128)


# ── compute_gradient_all_layers_analytic ─────────────────────────────────────


@pytest.mark.parametrize("uniform_weights", [True, False], ids=["poids-1", "poids-varies"])
def test_gradient_all_layers_matches_finite_differences(uniform_weights: bool) -> None:
    """Multi-layer gradient at normal incidence, with and without uniform weights.

    Le cas « poids-varies » est le plus important : une normalisation par le nombre
    of points instead of the sum of the weights is INVISIBLE when all the weights
    are equal to 1, the two denominators then differing only by a constant factor.
    """
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

    n_wls = WAVELENGTHS.size
    layers = _layers_matrix(n_wls)
    substrate = _substrate_vector(n_wls)
    targets = np.full(n_wls, 0.88)
    weights = np.ones(n_wls) if uniform_weights else non_uniform_weights(n_wls)
    var_idx = np.arange(THICKNESSES.size, dtype=np.int64)
    no_back_layers = np.zeros((n_wls, 0), dtype=np.complex128)
    no_back_thick = np.zeros(0, dtype=np.float64)

    def cost_and_grad(thicknesses: np.ndarray) -> tuple[float, np.ndarray]:
        return compute_gradient_all_layers_analytic(
            thicknesses,
            layers,
            substrate,
            WAVELENGTHS,
            targets,
            weights,
            0.0,
            True,
            no_back_layers,
            no_back_thick,
            var_idx,
        )

    check_gradient(cost_and_grad, THICKNESSES, label="compute_gradient_all_layers_analytic")


# ── compute_oblique_gradient_contrib_analytic ────────────────────────────────


@pytest.mark.parametrize("angle_deg", [0.0, 30.0, 55.0])
@pytest.mark.parametrize("s_pol", [True, False], ids=["pol-s", "pol-p"])
@pytest.mark.parametrize("on_reflectance", [False, True], ids=["cible-T", "cible-R"])
def test_oblique_gradient_matches_finite_differences(
    angle_deg: float, s_pol: bool, on_reflectance: bool
) -> None:
    """Gradient en incidence oblique, aux deux polarisations et sur les deux cibles.

    Balaye le produit angle x polarisation x nature de cible : c'est la combinatoire
    where a sign or tilted admittance error is most easily hidden, because
    it can be exact to 0 degrees and false beyond that.
    """
    from certus.physics.gradient_oblique import compute_oblique_gradient_contrib_analytic

    n_wls = WAVELENGTHS.size
    layers = _layers_matrix(n_wls)
    substrate = _substrate_vector(n_wls)
    targets = np.full(n_wls, 0.30 if on_reflectance else 0.88)
    weights = non_uniform_weights(n_wls)
    var_idx = np.arange(THICKNESSES.size, dtype=np.int64)

    def cost_and_grad(thicknesses: np.ndarray) -> tuple[float, np.ndarray]:
        #BE CAREFUL OF THE CONTRACT. This function returns (err_sum, grad_raw, weight_sum)
        # NON NORMALISES, comme sa docstring l'annonce. err_sum vaut Somme(w.diff^2),
        #whose derivative is 2.Sum(w.diff.d(diff)/dp): the factor 2 and the division
        #by the sum of the weights are applied by THE CALLER, not here.
        # Cf. certus/workers/certus_design_engine.py:195 :
        #     return total_err / total_weight, (2.0 / total_weight) * grad_raw
        #
        # Comparer grad_raw directement a la difference finie de err_sum donnerait un
        #ratio of exactly 2 — a spectacular false positive. We therefore reproduce
        #here the engine assembly, which has the advantage of testing what the optimizer
        # recoit reellement.
        err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
            thicknesses,
            layers,
            substrate,
            WAVELENGTHS,
            targets,
            weights,
            angle_deg,
            s_pol,
            on_reflectance,
            var_idx,
        )

        if weight_sum < 1e-12:
            pytest.skip("somme des poids nulle : point d'evaluation degenere")

        return err_sum / weight_sum, (2.0 / weight_sum) * np.asarray(grad_raw)

    check_gradient(
        cost_and_grad,
        THICKNESSES,
        label=f"oblique {angle_deg}deg {'s' if s_pol else 'p'} "
        f"{'R' if on_reflectance else 'T'}",
    )


# ── Le harnais mord-il ? ─────────────────────────────────────────────────────


def test_le_harnais_detecte_un_gradient_faux() -> None:
    """GARDE-FOU DU GARDE-FOU.

    A verification harness that detects nothing is worse than absent: it gives
    false assurance. Here we submit to it a deliberately distorted gradient of a factor
    1.05 — an error of 5%, of the same order as those actually encountered in
    this deposit — and we demand that he refuse it.
    """
    from gradient_harness import GradientMismatch
    from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

    n_wls = WAVELENGTHS.size
    layers = _layers_matrix(n_wls)
    substrate = _substrate_vector(n_wls)
    targets = np.full(n_wls, 0.88)
    weights = non_uniform_weights(n_wls)
    var_idx = np.arange(THICKNESSES.size, dtype=np.int64)
    no_back_layers = np.zeros((n_wls, 0), dtype=np.complex128)
    no_back_thick = np.zeros(0, dtype=np.float64)

    def cost_and_grad_fausse(thicknesses: np.ndarray) -> tuple[float, np.ndarray]:
        cost, grad = compute_gradient_all_layers_analytic(
            thicknesses,
            layers,
            substrate,
            WAVELENGTHS,
            targets,
            weights,
            0.0,
            True,
            no_back_layers,
            no_back_thick,
            var_idx,
        )
        return cost, np.asarray(grad) * 1.05

    with pytest.raises(GradientMismatch):
        check_gradient(cost_and_grad_fausse, THICKNESSES, label="gradient sabote")


def test_le_harnais_refuse_un_gradient_nul() -> None:
    """An identically zero gradient would trivially coincide with a zero FD.

    The harness must refuse this case rather than declare it compliant: a test which
    passing on a degenerate point demonstrates nothing.
    """
    from gradient_harness import GradientMismatch

    def cost_and_grad_nul(params: np.ndarray) -> tuple[float, np.ndarray]:
        return 1.0, np.zeros_like(params)

    with pytest.raises(GradientMismatch, match="identically zero"):
        check_gradient(cost_and_grad_nul, np.array([1.0, 2.0]), label="gradient nul")
