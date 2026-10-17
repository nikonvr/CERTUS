"""The analytical gradient of the spline objective must be the derivative of its cost.

This gradient had no independent verification, while its chain rule
had a defect: in ``smooth`` mode — the DEFAULT mode from K >= 4 — the factor
``exp(L_lam)`` was evaluated with PIECELY LINEAR interpolation, while
direct model interpolates by cubic matrix. Fixed, but nothing stopped it from
revenir.

Both modes are tested: ``smooth`` is the default path, ``pwl`` that of
repli quand K < 4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from gradient_harness import GradientMismatch, check_gradient

from certus.core.certus_index_config import DataType
from certus.spline.certus_index_spline_config import SplineOptConfig
from certus.spline.spline_objective import SplinePWLObjective


def _make_config(n_points: int = 40) -> SplineOptConfig:
    """Minimal but realistic configuration: transmission measurement on substrate.

    The data is synthetic and smooth; it doesn't matter if they correspond to a
    real stacking, what is tested is the internal consistency of the couple (cost,
    gradient), not physical accuracy — this falls under the TMM oracle.
    """
    lam = np.linspace(420.0, 900.0, n_points)

    #Synthetic transmission, smooth and strictly in (0, 1).
    t_exp = 0.80 + 0.06 * np.sin(lam / 90.0)

    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=np.full(n_points, 1.52),
        data_type=DataType.TRANSMISSION,
        n_seg=3,
        d_lo=50.0,
        d_hi=400.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="test",
    )


def _sigma_knots(config: SplineOptConfig, count: int) -> np.ndarray:
    """Nodes equally distributed in sigma = 1/lambda, ascending order."""
    lam = np.asarray(config.lam_nm, dtype=np.float64)
    sig_lo = 1.0 / lam.max()
    sig_hi = 1.0 / lam.min()
    return np.linspace(sig_lo, sig_hi, count)


def _pack(thickness_nm: float, n_values: np.ndarray, k_values: np.ndarray) -> np.ndarray:
    """Vecteur d'optimisation : [d, n_noeuds..., ln(k)_noeuds...] (dim = 1 + 2K)."""
    return np.concatenate(([thickness_nm], n_values, np.log(k_values)))


# K >= 4 triggers “smooth” mode; K = 3 forces the "pwl" fallback.
@pytest.mark.parametrize(
    ("knot_count", "expected_mode"),
    [(3, "pwl"), (4, "smooth"), (6, "smooth")],
    ids=["K3-pwl", "K4-smooth", "K6-smooth"],
)
def test_gradient_spline_coincide_avec_les_differences_finies(
    knot_count: int, expected_mode: str
) -> None:
    """GUARD: The chain rule must follow the model interpolation.

    In ``smooth`` mode, evaluate the factor ``exp(L_lam)`` with linear weights
    instead of the cubic matrix produces a false gradient — hence an optimizer which
    converges elsewhere, without the slightest visible error.
    """
    config = _make_config()
    knots = _sigma_knots(config, knot_count)
    objective = SplinePWLObjective(config, knots)

    assert objective._interp_mode == expected_mode, (
        f"le mode d'interpolation attendu etait {expected_mode}, "
        f"obtenu {objective._interp_mode} — le test ne couvre pas ce qu'il croit"
    )

    # Deliberately UNALIGNED node values.
    #
    #With values ​​in linear progression, a cubic spline passing through
    # aligned points IS the line: smoothed interpolation and linear by
    #pieces match exactly, and the test becomes blind to any confusion
    #between the two. Checked — with np.linspace, reintroduce default rule
    #"smooth" mode channel did not fail any tests.
    #A curved profile, closer to a real dispersion, separates them.
    positions = np.linspace(0.0, 1.0, knot_count)
    n_values = 2.10 + 0.25 * np.exp(-3.0 * positions)
    k_values = 0.004 + 0.016 * positions**2
    params = _pack(120.0, n_values, k_values)

    gradient = objective._compute_analytic_gradient(params)
    if gradient is None:
        pytest.skip("gradient analytique non supporte pour cette configuration")

    def cost_and_grad(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        analytic = objective._compute_analytic_gradient(candidate)
        return float(objective(candidate)), analytic

    #No wider than for the thicknesses: the nodes n and ln(k) are of order 1,
    # step 100, and a step of 1e-6 would be dominated by the rounding.
    #Division into families: [thickness] [nodes n] [nodes ln(k)].
    #
    #Without this division, the test is BLIND to block k. Measured on this
    # configuration: the gradient is ~6.7e+02 on nodes n and ~1e-04 on nodes
    #nodes ln(k), six orders of magnitude difference. Compared to the overall standard, a
    #2% error on block k weighs 3e-09 — undetectable. But it is precisely the
    # block k that the "smooth" mode chain rule affects, via its factor
    #exp(L_lam). Verified: without cutting, reintroducing the fault did not cause a failure
    #no testing.
    blocks = [
        (0, 1),
        (1, 1 + knot_count),
        (1 + knot_count, 1 + 2 * knot_count),
    ]

    check_gradient(
        cost_and_grad,
        params,
        step=1e-7,
        rtol=1e-4,
        blocks=blocks,
        label=f"gradient spline K={knot_count} mode={expected_mode}",
    )


def test_le_mode_smooth_est_bien_le_defaut() -> None:
    """The default mode should remain "smooth" whenever K allows it.

    Si ce contrat changeait, les tests ci-dessus continueraient de passer tout en
    no longer covering the path actually taken in production.
    """
    config = _make_config()
    objective = SplinePWLObjective(config, _sigma_knots(config, 5))

    assert objective._interp_mode == "smooth"
    assert objective._interp_mat is not None


def test_mode_et_matrice_restent_coherents() -> None:
    """GARDE-FOU : _interp_mode et _interp_mat doivent s'accorder.

    They were resolved together then _interp_mode was reassigned lower
    with the raw string from the config. For K < 4, this restored “smooth” while
    _interp_mat was None: the gradient took the smooth branch and operated on
    None.
    """
    config = _make_config()

    for knot_count in (2, 3, 4, 8):
        objective = SplinePWLObjective(config, _sigma_knots(config, knot_count))

        if objective._interp_mode == "smooth":
            assert objective._interp_mat is not None, (
                f"K={knot_count} : mode smooth mais matrice absente"
            )
        else:
            assert objective._interp_mode == "pwl"


# --- Reflection data, alone or with transmission, and a thicker layer (parity with the published version) ------------
#
# The published INDEX SPLINE ("1.1-revised") never uses this gradient; the current code does. The test above checks
# transmission alone at 120 nm. Measured on 2026-10-06 (reports/PARITE_ZENODO_ECARTS_LONGS_2026-10-06.md): with R
# data, and at 380 nm, the gradient is the derivative of its cost too.


def _make_reflection_config(kind: str, n_points: int = 40) -> SplineOptConfig:
    lam = np.linspace(420.0, 900.0, n_points)
    data_type = DataType.REFLECTION if kind == "R" else DataType.BOTH
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=None if kind == "R" else 0.80 + 0.06 * np.sin(lam / 90.0),
        r_exp=0.15 + 0.05 * np.cos(lam / 70.0),
        n_sub=np.full(n_points, 1.52),
        data_type=data_type,
        n_seg=3,
        d_lo=50.0,
        d_hi=400.0,
        weight_t=0.0 if kind == "R" else 1.0,
        weight_r=1.0,
        substrate_name="test",
    )


def _curved_point(knot_count: int, thickness_nm: float) -> np.ndarray:
    positions = np.linspace(0.0, 1.0, knot_count)
    return _pack(thickness_nm, 2.10 + 0.25 * np.exp(-3.0 * positions), 0.004 + 0.016 * positions**2)


def _blocks(knot_count: int) -> list[tuple[int, int]]:
    return [(0, 1), (1, 1 + knot_count), (1 + knot_count, 1 + 2 * knot_count)]


@pytest.mark.parametrize("thickness_nm", [120.0, 380.0])
@pytest.mark.parametrize("knot_count", [3, 4, 6], ids=["K3-pwl", "K4-smooth", "K6-smooth"])
@pytest.mark.parametrize("kind", ["R", "RT"])
def test_the_gradient_holds_with_reflection_data(kind: str, knot_count: int, thickness_nm: float) -> None:
    """The step is 1e-4, not the 1e-7 above: on these data the cost is 50 to 120 and the components 1e-6 to 1e-4, and
    at 1e-7 the rounding of the cost (eps x cost / h) moved finite differences up to 8e-3 away from a gradient that is
    right; they converge to it as the step grows (4e-9 to 6e-6 at 1e-3 and 1e-4, measured)."""
    config = _make_reflection_config(kind)
    objective = SplinePWLObjective(config, _sigma_knots(config, knot_count))
    params = _curved_point(knot_count, thickness_nm)

    if objective._compute_analytic_gradient(params) is None:
        pytest.fail("no analytic gradient for reflection data: the optimizer would fall back on finite differences")

    def cost_and_grad(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        return float(objective(candidate)), objective._compute_analytic_gradient(candidate)

    check_gradient(
        cost_and_grad,
        params,
        step=1e-4,
        rtol=1e-4,
        blocks=_blocks(knot_count),
        label=f"spline gradient {kind} K={knot_count} d={thickness_nm:.0f}",
    )


@pytest.mark.parametrize("knot_count", [3, 4, 6], ids=["K3-pwl", "K4-smooth", "K6-smooth"])
def test_the_check_sees_an_error_on_the_reflection_part(knot_count: int) -> None:
    """GUARD: the check above is not blind to the reflection part. A gradient taken with 10 % less weight on R than the
    cost it is compared to is refused (measured: a relative gap of about 6e-3, sixty times the tolerance)."""
    config = _make_reflection_config("RT")
    knots = _sigma_knots(config, knot_count)
    right = SplinePWLObjective(config, knots)
    config_wrong = _make_reflection_config("RT")
    config_wrong.weight_r = 0.9
    wrong = SplinePWLObjective(config_wrong, knots)
    params = _curved_point(knot_count, 120.0)

    with pytest.raises(GradientMismatch):
        check_gradient(
            lambda candidate: (float(right(candidate)), wrong._compute_analytic_gradient(candidate)),
            params,
            step=1e-4,
            rtol=1e-4,
            blocks=_blocks(knot_count),
            label=f"wrong R weight K={knot_count}",
        )
