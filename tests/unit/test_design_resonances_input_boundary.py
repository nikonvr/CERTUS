"""The native optional tool must not silently change the optical model or target weights."""
from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_resonances import prepare_design_resonances, resonance_lower_bounds
from certus.physics.certus_opt_tmm import Material
from certus_physics.structures import Layer, Target


def example() -> tuple[dict, list, list, np.ndarray]:
    return ({"H": Material(2.35, 2.35), "L": Material(1.45, 1.45), "Substrate": Material(1.52, 1.52)},
            [Layer("H", 1., False), Layer("L", 1., True)], [Target(400, 440, 0., 0.)], np.array([50., 80.]))


def test_the_snapshot_keeps_exact_thicknesses_and_locked_layers():
    mats, layers, targets, d = example()
    before = d.copy()
    request = prepare_design_resonances(mats, layers, targets, d)
    np.testing.assert_array_equal(request.thicknesses.view(np.uint64), d.view(np.uint64))
    np.testing.assert_array_equal(request.variable_indices, [1])
    request.thicknesses[0] += 1
    np.testing.assert_array_equal(d, before)
    assert len(request.problem.grid()[0]) == 41


def test_dispersion_is_not_replaced_with_a_sampled_constant_index():
    mats, layers, targets, d = example()
    mats["H"] = Material(2.35, 2.30)
    with pytest.raises(ValueError, match="400-nm and 700-nm"):
        prepare_design_resonances(mats, layers, targets, d)


@pytest.mark.parametrize("flag", ["oblique", "backside"])
def test_unsupported_optical_geometries_are_rejected(flag):
    mats, layers, targets, d = example()
    with pytest.raises(ValueError, match="normal incidence"):
        prepare_design_resonances(mats, layers, targets, d, **{flag: True})


def test_unequal_target_weights_are_not_silently_dropped():
    mats, layers, targets, d = example()
    targets.append(Target(450, 460, 1., 1., w=2.))
    with pytest.raises(ValueError, match="equal target weights"):
        prepare_design_resonances(mats, layers, targets, d)


def test_the_file_optical_floor_is_combined_with_the_explicit_physical_floor():
    mats, layers, targets, d = example()
    request = prepare_design_resonances(mats, layers, targets, d)
    bounds = resonance_lower_bounds(request.problem, 0.5, 2.35)
    np.testing.assert_allclose(bounds, [1., 2.35 / 1.45])

