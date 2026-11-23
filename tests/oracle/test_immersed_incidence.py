"""An immersed stack (lit from a medium of index n_inc, not from air) is computed exactly by the air kernels.

`certus.domain.immersion.to_air_equivalent` divides every index by n_inc and multiplies every thickness by it,
at the same angle; the oblique kernels of CERTUS, which take the incident medium to be air, then give the R and T
that the independent oracle `tests/oracle/tmm_reference.py::rt_stack_oblique` computes directly in the immersed
system. This is what lets DESIGN solve problems such as the immersed polarizing notch filter of the OIC 2025
design contest (cube of index 1.80, 45 degrees) without a new transfer-matrix formula (CLAUDE.md, rule 7).
"""

from __future__ import annotations

import numpy as np
import pytest
from tmm_reference import rt_stack_oblique

WLS = np.array([400.0, 450.0, 551.3, 700.0])
N_INC = [1.33, 1.52, 1.80, 2.10]
ANGLES = [0.0, 20.0, 45.0, 60.0]
POLARIZATIONS = ["s", "p"]


def _stack(n_layers: int, absorbing: bool, rng: np.random.Generator):
    n = rng.uniform(1.38, 2.35, (len(WLS), n_layers)).astype(np.complex128)
    if absorbing:
        n = n - 1j * 0.02 * rng.random((len(WLS), n_layers))
    d = rng.uniform(5.0, 300.0, n_layers)
    return n, d


@pytest.mark.parametrize("absorbing", [False, True], ids=["lossless", "absorbing"])
@pytest.mark.parametrize("polarization", POLARIZATIONS)
@pytest.mark.parametrize("angle", ANGLES)
@pytest.mark.parametrize("n_inc", N_INC)
def test_the_air_equivalent_matches_the_oracle_in_immersion(n_inc, angle, polarization, absorbing) -> None:
    from certus.domain.immersion import to_air_equivalent
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n, d = _stack(7, absorbing, np.random.default_rng(11))
    n_sub = np.full(len(WLS), complex(n_inc, 0.0))  # the second prism of a cube: exit medium = incident medium

    n_eq, d_eq, n_sub_eq = to_air_equivalent(n, d, n_sub, n_inc)
    r, t = calc_spectrum_oblique_vectorized(WLS, n_eq, d_eq, n_sub_eq, angle, polarization)

    for i, wl in enumerate(WLS):
        r_ref, t_ref = rt_stack_oblique(
            float(wl), n[i], d, angle, polarization == "s", n_inc=complex(n_inc, 0.0), n_sub=n_sub[i]
        )
        assert r[i] == pytest.approx(r_ref, abs=1e-12)
        assert t[i] == pytest.approx(t_ref, abs=1e-12)


@pytest.mark.parametrize("polarization", POLARIZATIONS)
def test_immersion_changes_the_answer_so_this_test_cannot_pass_for_the_wrong_reason(polarization) -> None:
    # The same stack lit from air at 45 degrees and from a cube of index 1.80 at 45 degrees differ: the
    # translation is not a no-op.
    n, d = _stack(7, False, np.random.default_rng(11))
    r_air, _ = rt_stack_oblique(450.0, n[1], d, 45.0, polarization == "s", n_inc=1.0, n_sub=complex(1.8, 0.0))
    r_imm, _ = rt_stack_oblique(450.0, n[1], d, 45.0, polarization == "s", n_inc=1.8, n_sub=complex(1.8, 0.0))
    assert abs(r_air - r_imm) > 0.01


def test_an_incident_index_of_one_returns_the_same_arrays() -> None:
    # The default path (air) must not be touched: same objects, so the same bits (C1).
    from certus.domain.immersion import to_air_equivalent

    n, d = _stack(3, True, np.random.default_rng(2))
    n_sub = np.full(len(WLS), complex(1.52, 0.0))
    n_eq, d_eq, n_sub_eq = to_air_equivalent(n, d, n_sub, 1.0)
    assert n_eq is n
    assert d_eq is d
    assert n_sub_eq is n_sub


@pytest.mark.parametrize("bad", [0.5, 0.0, -1.8, float("nan"), float("inf")])
def test_an_incident_index_below_one_or_not_finite_is_refused(bad) -> None:
    from certus.domain.immersion import to_air_equivalent

    n, d = _stack(2, False, np.random.default_rng(1))
    with pytest.raises(ValueError, match="incident medium index"):
        to_air_equivalent(n, d, np.full(len(WLS), complex(1.52, 0.0)), bad)


#: Regimes the random stacks above do not reach (22/11 review): layers that become evanescent in the cube, total
#: internal reflection at the exit, an absorbing exit medium, and layers far thinner than the floor of a contest.
EDGE_CASES = [
    pytest.param([2.25, 1.38] * 4, 1.80, 60.0, id="M-layers-evanescent-at-60deg"),
    pytest.param([2.25, 1.38, 1.65, 1.45] * 2, 1.80, 70.0, id="three-materials-evanescent-at-70deg"),
    pytest.param([2.25, 1.38] * 4, 1.45, 60.0, id="total-internal-reflection-at-the-exit"),
    pytest.param([2.25, 1.38] * 4, complex(1.7, -0.3), 45.0, id="absorbing-exit-medium"),
]


@pytest.mark.parametrize("polarization", POLARIZATIONS)
@pytest.mark.parametrize(("indices", "n_exit", "angle"), EDGE_CASES)
def test_the_air_equivalent_holds_in_the_regimes_of_high_angle(indices, n_exit, angle, polarization) -> None:
    from certus.domain.immersion import to_air_equivalent
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n = np.tile(np.asarray(indices, dtype=np.complex128), (len(WLS), 1))
    d = np.random.default_rng(7).uniform(0.5, 200.0, len(indices))
    n_sub = np.full(len(WLS), complex(n_exit))
    n_eq, d_eq, n_sub_eq = to_air_equivalent(n, d, n_sub, 1.80)
    r, t = calc_spectrum_oblique_vectorized(WLS, n_eq, d_eq, n_sub_eq, angle, polarization)
    for i, wl in enumerate(WLS):
        r_ref, t_ref = rt_stack_oblique(float(wl), n[i], d, angle, polarization == "s", n_inc=1.80 + 0j, n_sub=n_sub[i])
        assert r[i] == pytest.approx(r_ref, abs=1e-12)
        assert t[i] == pytest.approx(t_ref, abs=1e-12)
