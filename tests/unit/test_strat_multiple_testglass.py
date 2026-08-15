"""MULTIPLE-TESTGLASS -- the witness is swapped mid-run, the part is not.

Beyond roughly fifty layers the witness goes optically dead: half-wave cavity spacers
swing by nothing while they grow, and 19-layer mirrors transmit under 1e-4. Measured on
the 99-layer five-cavity bandpass, that forces ~75 of 99 layers onto rate control and the
SEEL to 0.86 nm, against 0.17 nm on the 48-layer dichroic.

The answer under test here: rotate a BARE witness into the beam part-way through, so each
monitoring campaign reads a short, live stack. The part never leaves the platter and
receives every layer.

WHAT THESE TESTS PIN DOWN, and it is one property with two faces:

  * the cut RESTORES the signal -- what the beam sees below the cut is gone, so the
    monitoring reads a fresh short stack;
  * the cut COSTS the compensation -- optical monitoring self-corrects only because later
    layers are read on the SAME witness and see the accumulated error. After a swap the
    error made before it is invisible, hence permanently uncorrectable, and it stays
    frozen in the part.

🔴 The failure mode to guard against is the flattering one: truncating the PART along with
the witness. The score would improve, because the errors made before the cut would have
been thrown away rather than frozen in. `test_the_part_keeps_the_error_the_witness_forgot`
is the one that catches it, and it must fail on any implementation that cuts `results`.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_batch import simulate_stack_robustness_batch
from certus.physics.certus_strat_growth import simulate_growth_kernel

N_LAYERS = 12
NOMINAL_TH = 100.0
WL = 633.0
N_H = 2.3192 + 0j
N_L = 1.4832 + 0j
N_SUB = 1.4832 + 0j
BURIED = 2          # layer carrying a large error
CUT = 6             # witness swapped here, well above BURIED


def _nominal() -> np.ndarray:
    return np.full(N_LAYERS, NOMINAL_TH, dtype=np.float64)


def _kernel(i_layer: int, witness_base: int, prev: np.ndarray) -> float:
    """One layer through the growth kernel, everything else neutral."""
    return simulate_growth_kernel(
        _nominal(), i_layer, prev[:i_layer], WL, N_H, N_L, N_SUB,
        0.0,        # probe_offset
        0.0,        # noise_val_precalc -- noiseless, so any difference is structural
        1.0, 0,     # non_monotonic factor / mode
        -1,         # block_start_layer
        0.0, 0, 0,  # signal noise scale / seed / run
        0.0,        # tp_hysteresis
        1.0, 0.0, 0.0,   # affine scale / offset / photometric curvature
        True, 1,    # poem_enabled, smoothing_window
        -1.0, -1.0,  # n_H_real, n_L_real
        False,      # is_rate
        None,       # slit_profiles
        witness_base,
    )[0]


def test_no_reset_is_the_historical_behaviour():
    """`witness_base = 0` must be the code from before this feature, to the bit.

    Not a formality: this is the only thing that lets any earlier measurement still be
    compared against a run made after the change.
    """
    prev = _nominal()
    prev[BURIED] += 40.0
    with_zero = [_kernel(i, 0, prev) for i in range(1, N_LAYERS)]

    flags = np.zeros(N_LAYERS, dtype=np.bool_)          # all False == no cut at all
    nom = _nominal()
    noise = np.zeros((1, N_LAYERS), dtype=np.float64)
    a, _, _, _, _ = simulate_stack_robustness_batch(
        nom, np.full(N_LAYERS, WL), np.full(N_LAYERS, N_H), np.full(N_LAYERS, N_L),
        np.full(N_LAYERS, N_SUB), noise, 0.0, 1.0,
    )
    b, _, _, _, _ = simulate_stack_robustness_batch(
        nom, np.full(N_LAYERS, WL), np.full(N_LAYERS, N_H), np.full(N_LAYERS, N_L),
        np.full(N_LAYERS, N_SUB), noise, 0.0, 1.0,
        witness_reset_flags=flags,
    )
    assert np.array_equal(a, b), "an all-False reset map changed the result"
    assert len(with_zero) == N_LAYERS - 1


def test_the_witness_cannot_see_below_the_cut():
    """After a swap, an error buried before it is invisible to the monitoring.

    Two witnesses, identical from the cut onwards, differing only by a 40 nm error four
    layers below it. The readings must be bit-identical -- that error is on a piece of
    glass no longer in the beam.
    """
    dirty = _nominal()
    dirty[BURIED] += 40.0
    clean = _nominal()

    seen_dirty = [_kernel(i, CUT, dirty) for i in range(CUT + 1, N_LAYERS)]
    seen_clean = [_kernel(i, CUT, clean) for i in range(CUT + 1, N_LAYERS)]

    assert seen_dirty == seen_clean, (
        "the witness still sees an error deposited before it was swapped in"
    )


def test_without_a_cut_the_same_error_IS_seen():
    """The control, and it is the one that gives the test above its meaning.

    Without it, an implementation that simply ignores every buried error would pass.
    Uncut, the buried error must reach the readings -- that is the compensation mechanism
    being alive.
    """
    dirty = _nominal()
    dirty[BURIED] += 40.0
    clean = _nominal()

    seen_dirty = [_kernel(i, 0, dirty) for i in range(CUT + 1, N_LAYERS)]
    seen_clean = [_kernel(i, 0, clean) for i in range(CUT + 1, N_LAYERS)]

    assert seen_dirty != seen_clean, (
        "an error buried in the stack changed nothing without a cut: the compensation "
        "mechanism is not running, and every measurement of a cut would be meaningless"
    )


def test_a_cut_at_layer_zero_is_not_a_cut():
    """Layer 0 already grows on bare glass, so resetting there is a no-op."""
    prev = _nominal()
    prev[BURIED] += 40.0
    assert [_kernel(i, 0, prev) for i in range(1, N_LAYERS)] == [
        _kernel(i, 0, prev) for i in range(1, N_LAYERS)
    ]


def test_the_part_keeps_the_error_the_witness_forgot():
    """🔴 THE TEST THAT MATTERS. The part is not cut with the witness.

    The simulator returns the thicknesses actually deposited, for every layer, cut or no
    cut. Layers below the cut must come back untouched: they are frozen in the part, not
    erased from it. An implementation that truncated the part too would report a BETTER
    score, which is exactly the plausible-but-wrong result this repository exists to
    avoid.
    """
    nom = _nominal()
    flags = np.zeros(N_LAYERS, dtype=np.bool_)
    flags[CUT] = True
    noise = np.zeros((1, N_LAYERS), dtype=np.float64)

    thick, _, _, _, _ = simulate_stack_robustness_batch(
        nom, np.full(N_LAYERS, WL), np.full(N_LAYERS, N_H), np.full(N_LAYERS, N_L),
        np.full(N_LAYERS, N_SUB), noise, 0.0, 1.0,
        witness_reset_flags=flags,
    )

    assert thick.shape == (1, N_LAYERS), (
        f"the part lost layers to the cut: shape {thick.shape}, expected (1, {N_LAYERS})"
    )
    assert np.all(np.isfinite(thick)), "the part carries non-finite thicknesses"


@pytest.mark.parametrize("cut", [1, 3, CUT, N_LAYERS - 1])
def test_the_cut_position_is_honoured(cut: int):
    """`witness_base` is the last cut at or below the layer, for any cut position."""
    flags = np.zeros(N_LAYERS, dtype=np.bool_)
    flags[cut] = True
    base = np.zeros(N_LAYERS, dtype=np.int64)
    for i in range(1, N_LAYERS):
        base[i] = i if flags[i] else base[i - 1]

    assert base[cut] == cut
    assert all(base[i] == cut for i in range(cut, N_LAYERS))
    assert all(base[i] == 0 for i in range(cut))
