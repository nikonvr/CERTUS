"""Chantier 47: the substrate thickness reaches the RE entry points (oblique, back face seen).

At 1 mm (the default) every entry point keeps the bits of the call without the argument (C1); at 2 mm an absorbing
substrate gives another answer, and a non-absorbing one the same.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM
from certus.utils.certus_re_helpers import _re_calc_spectrum_for_config, _re_eval_angle_physics_for

WLS = np.array([450.0, 550.0, 650.0, 800.0, 1000.0, 1200.0])


def _case(k: float):
    rng = np.random.default_rng(47)
    n = rng.uniform(1.4, 2.3, (len(WLS), 3)).astype(np.complex128)
    d = rng.uniform(50.0, 160.0, 3)
    n_sub = np.array([complex(1.52, -k)] * len(WLS))
    return d, n, n_sub


def _outputs(case, thickness=None):
    d, n, n_sub = case
    kw = {} if thickness is None else {"substrate_thickness_nm": thickness}
    var = np.arange(3, dtype=np.int64)
    out = []
    for pol in ("s", "p", "avg"):
        out += list(_re_calc_spectrum_for_config(WLS, n, d, n_sub, 30.0, pol, True, **kw))
        out += list(_re_calc_spectrum_for_config(WLS, n, d, n_sub, 30.0, pol, True, phase4_average=True, **kw))
        out += list(_re_eval_angle_physics_for(None, 30.0, pol, True, d, n, n_sub, WLS, None, var, **kw))
    return out


@pytest.mark.parametrize("k", [0.0, 1e-5])
def test_one_millimetre_keeps_the_bits_of_the_default(k) -> None:
    case = _case(k)
    for a, b in zip(_outputs(case), _outputs(case, DEFAULT_SUBSTRATE_THICKNESS_NM), strict=True):
        assert np.array_equal(np.asarray(a).view(np.uint64), np.asarray(b).view(np.uint64))


def test_the_thickness_acts_on_an_absorbing_substrate_only() -> None:
    absorbing, clear = _case(1e-5), _case(0.0)
    thin, thick = _outputs(absorbing), _outputs(absorbing, 2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM)
    for a, b in zip(thin, thick, strict=True):
        assert not np.array_equal(a, b)
    for a, b in zip(_outputs(clear), _outputs(clear, 2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM), strict=True):
        assert np.array_equal(a, b)
