"""The absorbing substrate has one model, and the backside limits one definition.

Measured on 2026-09-30, before `certus_substrate_absorption.py`: three normal-incidence kernels treated
every `|k| > 1e-8` as a semi-infinite absorber (`T = 0`, a jump), STRAT validated its backside
approximation up to `1e-5`, INDEX had a Beer-Lambert plate with a thickness of its own, and the oblique
plate kernels dropped the absorption. Five modules of `certus/physics` each declared the two backside
limits (`K_MAX_LAYER_BACKSIDE`, `K_MAX_SUBSTRATE_BACKSIDE`).
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIMITS = ("K_MAX_LAYER_BACKSIDE", "K_MAX_SUBSTRATE_BACKSIDE")
STRAT_MODULES = ("batch", "dp", "growth", "math", "nucleation")


def _module_level_assignments(path: Path) -> set[str]:
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_the_backside_limits_are_defined_once() -> None:
    shared = ROOT / "certus" / "physics" / "certus_substrate_absorption.py"
    definers = [
        path.relative_to(ROOT).as_posix()
        for package in ("certus", "certus_physics")
        for path in (ROOT / package).rglob("*.py")
        if set(LIMITS) & _module_level_assignments(path)
    ]

    assert definers == [shared.relative_to(ROOT).as_posix()]


@pytest.mark.parametrize("name", STRAT_MODULES)
def test_the_strat_modules_read_the_values_they_always_had(name) -> None:
    import importlib

    module = importlib.import_module(f"certus.physics.certus_strat_{name}")

    assert module.K_MAX_LAYER_BACKSIDE == 0.001
    assert module.K_MAX_SUBSTRATE_BACKSIDE == 0.00001


def test_the_facade_exposes_the_same_limits() -> None:
    import certus_physics
    from certus.physics import certus_substrate_absorption as shared

    assert certus_physics.K_MAX_LAYER_BACKSIDE is shared.K_MAX_LAYER_BACKSIDE
    assert certus_physics.K_MAX_SUBSTRATE_BACKSIDE is shared.K_MAX_SUBSTRATE_BACKSIDE


# =============================================================================
# The plate: Beer-Lambert through the substrate
# =============================================================================


def test_no_absorption_is_exactly_no_loss() -> None:
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance

    assert substrate_internal_transmittance(0.0, 550.0, 1.0e6, 1.0) == 1.0
    assert substrate_internal_transmittance(0.0, 550.0, 1.0e6, 0.3) == 1.0


def test_a_glass_of_1_per_cm_transmits_a_third_through_a_centimetre() -> None:
    # k = 4.4e-6 at 550 nm is alpha = 4 pi k / lambda = 1.005 cm^-1 (the glass of the audit): a centimetre of
    # it keeps exp(-1.005) of the flux, and a millimetre 0.90.
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance

    alpha_per_cm = 4.0 * math.pi * 4.4e-6 / 550.0e-7

    assert substrate_internal_transmittance(4.4e-6, 550.0, 1.0e7, 1.0) == pytest.approx(math.exp(-alpha_per_cm))
    assert substrate_internal_transmittance(4.4e-6, 550.0, 1.0e6, 1.0) == pytest.approx(math.exp(-alpha_per_cm / 10))


def test_the_loss_grows_with_the_absorption_the_thickness_and_the_obliquity() -> None:
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance as tau

    assert tau(1e-6, 550.0, 1e6, 1.0) > tau(1e-5, 550.0, 1e6, 1.0) > tau(1e-4, 550.0, 1e6, 1.0)
    assert tau(1e-5, 550.0, 1e5, 1.0) > tau(1e-5, 550.0, 1e6, 1.0)
    assert tau(1e-5, 550.0, 1e6, 1.0) > tau(1e-5, 550.0, 1e6, 0.5)  # a longer path through the plate
    assert tau(1e-5, 1100.0, 1e6, 1.0) > tau(1e-5, 550.0, 1e6, 1.0)  # less absorbed at longer wavelength


def test_the_sign_of_k_does_not_matter_and_a_grazing_ray_does_not_cross() -> None:
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance as tau

    assert tau(-1e-5, 550.0, 1e6, 1.0) == tau(1e-5, 550.0, 1e6, 1.0)
    assert tau(1e-5, 550.0, 1e6, 0.0) == 0.0


def test_the_semi_infinite_absorber_is_the_limit_of_the_plate() -> None:
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance as tau

    assert tau(1.0, 550.0, 1e6, 1.0) < 1e-100


# =============================================================================
# The same model as INDEX's, which was the only plate with a thickness
# =============================================================================


def _plate(rf, tf, rf_inside, rb, tb, tau):
    """The incoherent plate of `certus_substrate_absorption`: what the kernels combine."""
    denominator = 1.0 - rf_inside * rb * tau * tau
    return rf + tf * tf * rb * tau * tau / denominator, tf * tb * tau / denominator


@pytest.mark.parametrize("k", [1e-7, 4.4e-6, 1e-4, 1e-3])
@pytest.mark.parametrize("wavelength", [450.0, 800.0])
def test_the_plate_agrees_with_the_index_module_plate(k, wavelength) -> None:
    # A film of index 1 between air and the substrate changes nothing: R and T of INDEX's plate are then
    # those of the bare substrate, whose interfaces have closed forms. The attenuation is the only thing
    # the two implementations must agree on.
    from certus.physics.certus_substrate_absorption import substrate_internal_transmittance
    from certus.physics.certus_tmm_single_layer import _calculate_RT_absorbing_sub_single

    n_sub, thickness = 1.52, 1.0e6
    r_interface = ((n_sub - 1.0) / (n_sub + 1.0)) ** 2
    t_interface = 1.0 - r_interface
    tau = substrate_internal_transmittance(k, wavelength, thickness, 1.0)

    r_expected, t_expected = _plate(r_interface, t_interface, r_interface, r_interface, t_interface, tau)
    r_index, t_index = _calculate_RT_absorbing_sub_single(wavelength, 1.0, 0.0, 100.0, n_sub, k, thickness)

    assert r_index == pytest.approx(r_expected, abs=1e-12)
    assert t_index == pytest.approx(t_expected, abs=1e-12)
