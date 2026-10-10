"""The stop solved on the exact signal (`exact_inversion`, D97) is the oracle's crossing; the default keeps the parabola.

`_invert_thickness_from_probes` fits a parabola through three probes at +/- `probe_offset` of the nominal thickness and
solves the stopping level on it. Measured on 2026-10-10 on the judge of paix, noise-free, upstream errors of 0.3 nm:
0.021 nm RMS off the exact stop under POEM, up to 1.53 nm at an absolute level, where the stop moves several nanometres.
`_invert_thickness_exact` solves the same level on the closed form of the growing layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
from tmm_reference import rt_stack, stack_matrix

from certus.physics.certus_strat_growth import (
    _invert_thickness_exact,
    _invert_thickness_from_probes,
    simulate_growth_kernel,
)

pytestmark = pytest.mark.kernels

N_SUB, N_H, N_L = 1.52, 2.35, 1.46
WL = 560.0


def _case(seed: int):
    rng = np.random.default_rng(seed)
    n_below = int(rng.integers(2, 7))
    thick_below = rng.uniform(40.0, 130.0, n_below)
    indices = [N_H if j % 2 == 0 else N_L for j in range(n_below)]
    n_cur = N_H if n_below % 2 == 0 else N_L
    nominal = float(rng.uniform(50.0, 120.0))
    return thick_below, indices, n_cur, nominal


def _oracle_t(thick_below, indices, n_cur, d) -> float:
    return rt_stack(WL, [*indices, n_cur], [*thick_below, d], 1.0, N_SUB)[1]


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("offset_nm", [0.4, 3.0, -2.5])
def test_the_exact_inversion_returns_the_oracles_crossing(seed, offset_nm) -> None:
    thick_below, indices, n_cur, nominal = _case(seed)
    m = stack_matrix(indices, thick_below, WL)
    d_true = nominal + offset_nm
    level = _oracle_t(thick_below, indices, n_cur, d_true)
    # The solver returns the crossing NEAREST the nominal thickness, as the parabola does. When the level is crossed
    # again closer to it (on the other side of an extremum), that other crossing is the answer: such draws are skipped.
    grid = np.arange(nominal - 10.0, nominal + 10.0, 0.01)
    values = np.array([_oracle_t(thick_below, indices, n_cur, d) - level for d in grid])
    roots = grid[1:][np.sign(values[1:]) != np.sign(values[:-1])]
    if roots.size == 0 or abs(roots[np.argmin(np.abs(roots - nominal))] - d_true) > 0.02:
        pytest.skip("another crossing of this level lies nearer the nominal thickness")

    got = _invert_thickness_exact(
        WL, n_cur + 0j, nominal, 2.5, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], 1.0, 0.0, 0.0, None, 3, level,
    )

    assert nominal + got == pytest.approx(d_true, abs=1e-6)


def test_far_from_the_nominal_thickness_the_parabola_is_off_and_the_exact_solve_is_not() -> None:
    thick_below, indices, n_cur, nominal = _case(3)
    m = stack_matrix(indices, thick_below, WL)
    d_true = nominal + 6.0
    level = _oracle_t(thick_below, indices, n_cur, d_true)
    args = (WL, n_cur + 0j, nominal, 2.5, N_SUB + 0j, m[0, 0], m[0, 1], m[1, 0], m[1, 1], 1.0, 0.0, 0.0, None, 3, level)

    exact = nominal + _invert_thickness_exact(*args)
    parabola = nominal + _invert_thickness_from_probes(*args)

    assert exact == pytest.approx(d_true, abs=1e-6)
    assert abs(parabola - d_true) > 1e-3  # the parabola extrapolates six nanometres away from its probes


def test_the_kernel_takes_the_exact_inversion_only_when_asked() -> None:
    """With an upstream error and no noise, the two stops differ; without the flag the kernel is the parabola."""
    nominal = np.array([62.0, 95.0, 58.0, 101.0, 64.0])
    prev = nominal[:4] * np.array([1.01, 0.985, 1.02, 0.99])
    common = (nominal, 4, prev, WL, N_H + 0j, N_L + 0j, N_SUB + 0j, 2.5, 0.0, 2.0, 0, -1, 0.0, 0, 0, 8.3e-4,
              1.0, 0.0, 0.0, False, 1, -1.0, -1.0, False, None, 0, 0.0, None)  # fmt: skip

    default = simulate_growth_kernel(*common)[0]
    parabola = simulate_growth_kernel(*common, False)[0]
    exact = simulate_growth_kernel(*common, True)[0]

    assert default == parabola
    assert exact != parabola
