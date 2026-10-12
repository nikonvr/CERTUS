"""Optics may resume after a Rate layer: the kernel reads nothing of how the layers before a layer were laid.

👤 2026-10-12: *"do you allow going back to optics after the Rate? It is important"* -- and, from the machine, packets of optics at
one wavelength, then a packet of Rate, then a packet of optics at another wavelength. The kernel allows it, and this pins how:

- a layer that is not laid by Rate is stopped from its own signal, whatever the layers before it were: `prev_rate_flags` is read by
  the Rate layers only, to leave out of their estimate the layers that carry no measurement;
- a Rate layer has no trigger, so it cannot crash, and the cost goes to the layer after it (it borrows no extremum from it).

The stack is a TOY (eight quarter-wave layers at 1500 nm): it checks mechanisms, not a physical conclusion.
"""

import numpy as np
import pytest

import certus_physics  # noqa: F401  (facade: avoids the circular import)
from certus.physics.certus_strat_growth import RATE_TURN_NM, simulate_growth_kernel

pytestmark = pytest.mark.kernels

N_H = complex(2.3, 0.0)
N_L = complex(1.45, 0.0)
N_SUB = complex(1.52, 0.0)
L0 = 1500.0
P_THICK = np.array([L0 / (4.0 * (2.3 if i % 2 == 0 else 1.45)) for i in range(8)], dtype=np.float64)
CRASH_SENTINEL = 1e5
NOT_MONITORED = -1.0
NO_CONSTRAINT = 1e18


def _grow(i_layer, prev, wl, *, is_rate=False, flags=None, block_start=-1):
    return simulate_growth_kernel(
        P_THICK,
        i_layer,
        np.asarray(prev, dtype=np.float64),
        float(wl),
        N_H,
        N_L,
        N_SUB,
        2.0,
        0.0,
        1.0,
        0,
        block_start,
        is_rate=is_rate,
        prev_rate_flags=flags,
    )


def _upstream(i_layer: int, ratio: float) -> np.ndarray:
    """What was really laid before `i_layer`: the nominal thicknesses, each off by the same relative error, as a Rate run leaves them."""
    return P_THICK[:i_layer] / ratio


@pytest.mark.parametrize("wl", [1300.0, 1500.0, 1700.0])
@pytest.mark.parametrize("i_layer", [3, 5, 7])
def test_an_optical_layer_does_not_read_which_layers_before_it_were_laid_by_rate(i_layer, wl) -> None:
    prev = _upstream(i_layer, 1.004)
    flags = np.zeros(i_layer, dtype=np.bool_)
    flags[1:i_layer] = True  # everything after the first layer was laid by Rate

    with_flags = _grow(i_layer, prev, wl, flags=flags)
    without = _grow(i_layer, prev, wl, flags=None)

    assert with_flags == without  # bit for bit: the path of an optical layer has no use for the flags


def test_an_optical_layer_after_rate_layers_still_compensates_what_they_left_upstream() -> None:
    """The layer is stopped from its own signal: a 1 nm error upstream moves its thickness, it does not go unseen."""
    i_layer, wl = 7, 1200.0  # a wavelength at which the toy stack monitors layer 7 well (test_strat_poem.py: a gain of 10.9)
    clean = _upstream(i_layer, 1.0)
    shifted = clean.copy()
    shifted[i_layer - 1] += 1.0
    flags = np.zeros(i_layer, dtype=np.bool_)
    flags[i_layer - 1] = True  # the layer just before was laid by Rate

    reference = _grow(i_layer, clean, wl, flags=flags)[0]
    after_rate = _grow(i_layer, shifted, wl, flags=flags)[0]

    assert reference < CRASH_SENTINEL
    assert after_rate < CRASH_SENTINEL
    assert abs(after_rate - reference) > 0.05, "the layer ignored the error left upstream: it is not monitored from its own signal"


def test_a_rate_layer_has_no_trigger_so_it_cannot_crash() -> None:
    i_layer = 4
    prev = _upstream(i_layer, 1.01)  # 1 % thinner than nominal everywhere

    thickness, swing, margin_level, margin_missed, margin_fabricated = _grow(i_layer, prev, 1500.0, is_rate=True)

    assert swing == NOT_MONITORED
    assert (margin_level, margin_missed, margin_fabricated) == (NO_CONSTRAINT, NO_CONSTRAINT, NO_CONSTRAINT)
    # the thickness commanded: the nominal one over the mean ratio of the layers of the same material laid under optical control
    ratio = np.mean([P_THICK[j] / prev[j] for j in (2, 0)])
    assert thickness == pytest.approx(round(P_THICK[i_layer] / (ratio * RATE_TURN_NM)) * RATE_TURN_NM)


def test_a_rate_layer_leaves_out_of_its_estimate_the_layers_laid_by_rate() -> None:
    """A layer laid by Rate carries no measurement: counting it would quote the estimate back to itself."""
    i_layer = 6
    prev = _upstream(i_layer, 1.01)
    prev[2] = P_THICK[2] / 1.05  # a Rate layer whose ratio is far from the others'
    flags = np.zeros(i_layer, dtype=np.bool_)
    flags[2] = True

    with_flag = _grow(i_layer, prev, 1500.0, is_rate=True, flags=flags)[0]
    without_flag = _grow(i_layer, prev, 1500.0, is_rate=True, flags=None)[0]

    assert with_flag != without_flag
    ratio = np.mean([P_THICK[j] / prev[j] for j in (0, 4)])  # layer 2 is out
    assert with_flag == pytest.approx(round(P_THICK[i_layer] / (ratio * RATE_TURN_NM)) * RATE_TURN_NM)
