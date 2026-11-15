"""Chantier 44: `simulate_stack_robustness_batch(stack_carry=True)` carries the stack matrices instead of rebuilding them.

The carried products are the same products in the same order, so the two paths may differ in the last bits only (the
owner accepted that on 2026-11-15) and must agree on every decision: which runs crash, and the thickness of every
layer to 1e-9 relative. Not to 1e-12: the parabolic inversion amplifies a last-bit gap of the matrices, measured up to
7.7e-12 relative (5.7e-10 nm) on this case, and which side of it a run falls on depends on the Numba cache. The case crosses wavelength blocks longer than the four-layer memory of the scan, a Rate layer and a
witness swap, the three places where the carried stack has to be rebuilt.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_strat_batch import simulate_stack_robustness_batch


def _run(carry: bool, *, rate: bool, witness: bool, arming: int) -> tuple[np.ndarray, ...]:
    nominal = np.tile([53.19, 85.62], 9)
    n = len(nominal)
    wls = np.array([540.0] * 7 + [600.0] * 6 + [500.0] * 5)
    disp = (wls - 540.0) * 1e-4
    rng = np.random.default_rng(44)
    rate_flags = np.zeros(n, dtype=np.bool_)
    rate_flags[9] = rate
    swaps = np.zeros(n, dtype=np.bool_)
    swaps[15] = witness
    return simulate_stack_robustness_batch(
        nominal, wls, (2.35 + disp).astype(np.complex128), (1.46 + disp).astype(np.complex128),
        np.full(n, 1.52 + 0j), rng.normal(0.0, 5e-4, (12, n)), 3.0, 2.0, 0, np.full(n, 5e-4), 7, 8.3e-4, 0.0, 0.0,
        0.01, 3, True, 1, 0.005, 5, 450.0, 650.0, rate_flags if rate else None, None, swaps if witness else None,
        False, False, arming, carry,
    )  # fmt: skip


@pytest.mark.parametrize(("rate", "witness", "arming"), [(False, False, 2), (True, True, 2), (True, False, 0)])
def test_the_carried_stacks_give_the_same_decisions_and_thicknesses(rate, witness, arming):
    rebuilt = _run(False, rate=rate, witness=witness, arming=arming)
    carried = _run(True, rate=rate, witness=witness, arming=arming)
    crashed_rebuilt = rebuilt[0] > 1e5
    np.testing.assert_array_equal(crashed_rebuilt, carried[0] > 1e5)
    np.testing.assert_allclose(carried[0][~crashed_rebuilt], rebuilt[0][~crashed_rebuilt], rtol=1e-9, atol=0.0)
    np.testing.assert_allclose(carried[1], rebuilt[1], rtol=1e-9, atol=1e-15)


def test_the_carry_is_off_by_default():
    import inspect

    default = inspect.signature(simulate_stack_robustness_batch.py_func).parameters["stack_carry"].default
    assert default is False
