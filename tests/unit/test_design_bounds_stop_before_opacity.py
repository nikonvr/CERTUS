"""DESIGN never asks the kernels for a layer past opacity (D46).

Past `|Im phase| = PHASE_IMAG_OVERFLOW` the kernels answer (R, T) = (0, 0) instead of the semi-infinite absorber, and
the Python wrappers refuse such a layer. The global bound of DESIGN is 1.2 x max(quarter wave at lambda0, start): for a
metal in the infrared, whose real index is tiny, that "quarter wave" is hundreds of micrometres, and the optimiser could
step into the (0, 0) answer. The bounds now stop 1 % before opacity, where the response no longer moves with the
thickness anyway; a layer that does not absorb keeps its bounds to the bit.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.core.certus_design_worker_utils import (
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_opaque_thickness_limits,
)
from certus.physics.certus_inputs import require_layers_below_overflow

WLS = np.linspace(8000.0, 12000.0, 41)


class _Metal:
    n4 = 0.02

    def get_nk(self, wls):
        return np.full(len(wls), 0.02 - 60.0j)


def _metal_indices() -> np.ndarray:
    return np.full((len(WLS), 1), 0.02 - 60.0j)


def test_an_infrared_metal_is_bounded_before_the_kernels_overflow():
    stack = [SimpleNamespace(mat="M")]
    mats = {"M": _Metal()}
    n_layers = _metal_indices()
    limits = optim_opaque_thickness_limits(n_layers, WLS)
    bounds = optim_bounds_thickness_global(np.array([200.0]), np.array([0]), stack, mats, 10000.0, opaque_limits=limits)
    uncapped = optim_bounds_thickness_global(np.array([200.0]), np.array([0]), stack, mats, 10000.0)
    assert uncapped[0, 1] > 100_000.0  # the "quarter wave" of a tiny real index: 150 micrometres
    require_layers_below_overflow(np.array([bounds[0, 1]]), n_layers, WLS)  # the bound itself is still computable
    with pytest.raises(ValueError, match="absorbs too much"):
        require_layers_below_overflow(np.array([bounds[0, 1] * 1.02]), n_layers, WLS)


def test_a_layer_that_does_not_absorb_keeps_its_bounds_to_the_bit():
    stack = [SimpleNamespace(mat="H")]
    mats = {"H": SimpleNamespace(n4=2.0, get_nk=lambda w: np.full(len(w), 2.0 + 0j))}
    limits = optim_opaque_thickness_limits(np.full((len(WLS), 1), 2.0 + 0j), WLS)
    assert np.isinf(limits).all()
    for bound in (optim_bounds_thickness_global, optim_bounds_thickness_healing):
        capped = bound(np.array([100.0]), np.array([0]), stack, mats, 500.0, opaque_limits=limits)
        plain = bound(np.array([100.0]), np.array([0]), stack, mats, 500.0)
        assert capped.tobytes() == plain.tobytes()
    capped = optim_bounds_thickness_local(np.array([100.0]), np.array([0]), 2.0, opaque_limits=limits)
    assert capped.tobytes() == optim_bounds_thickness_local(np.array([100.0]), np.array([0]), 2.0).tobytes()


def test_the_healing_bounds_stop_before_opacity_and_stay_a_valid_box():
    stack = [SimpleNamespace(mat="M")]
    mats = {"M": _Metal()}
    limits = optim_opaque_thickness_limits(_metal_indices(), WLS)
    thick = float(limits[0]) - 10.0  # a layer just under the limit: healing would add lambda0 / 10 = 1 micrometre
    bounds = optim_bounds_thickness_healing(np.array([thick]), np.array([0]), stack, mats, 10000.0, opaque_limits=limits)
    assert bounds[0, 1] <= limits[0]
    assert bounds[0, 0] <= bounds[0, 1]


def test_the_local_bounds_stop_before_opacity_too():
    limits = optim_opaque_thickness_limits(_metal_indices(), WLS)
    thick = float(limits[0]) - 1.0  # the local box is +/- 2 nm: its upper side would pass the limit
    bounds = optim_bounds_thickness_local(np.array([thick]), np.array([0]), 2.0, opaque_limits=limits)
    assert bounds[0, 1] == pytest.approx(limits[0])
    assert bounds[0, 0] == pytest.approx(thick - 2.0)
