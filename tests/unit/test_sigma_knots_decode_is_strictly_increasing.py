"""``sigma_knots_decode`` returns a strictly increasing mesh, whatever the log-proportions (audit 2026-11-15, M-L3a).

The forward sweep pushed each knot at least ``eps_s`` above the previous one, then the last knot was reset to ``s_hi``:
when the last intervals are tiny, the knot before the last ended above it (3.01 before 3.0) and the spline was built on
a mesh that goes backwards.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.spline.spline_objective import sigma_knots_decode

S_LO, S_HI = 1.0, 3.0


@pytest.mark.parametrize("tail", [-2.0, -8.0, -20.0])
@pytest.mark.parametrize("eps_s", [None, 0.001, 0.01])
def test_the_mesh_is_strictly_increasing_and_keeps_its_ends(tail: float, eps_s: float | None) -> None:
    raw = np.array([0.0, 0.0, 0.0, 0.0, tail, tail])
    sk = sigma_knots_decode(raw, S_LO, S_HI, eps_s)
    eps = 0.01 if eps_s is None else eps_s
    assert sk[0] == S_LO
    assert sk[-1] == S_HI
    assert np.all(np.diff(sk) >= eps * (1.0 - 1e-9)), f"knots {sk}"


def test_tiny_first_intervals_stay_increasing_too() -> None:
    sk = sigma_knots_decode(np.array([-20.0, -20.0, 0.0, 0.0, 0.0, 0.0]), S_LO, S_HI)
    assert np.all(np.diff(sk) > 0.0), f"knots {sk}"


def test_a_regular_mesh_is_returned_to_the_bit() -> None:
    raw = np.array([0.3, -0.2, 0.1, 0.0, -0.4, 0.25])
    ww = np.exp(raw)
    expected = np.concatenate(([S_LO], S_LO + np.cumsum(ww / ww.sum() * (S_HI - S_LO))[:-1], [S_HI]))
    np.testing.assert_array_equal(sigma_knots_decode(raw, S_LO, S_HI), expected)


def test_the_work_buffers_give_the_same_mesh() -> None:
    raw = np.array([0.0, 0.0, 0.0, 0.0, -20.0, -20.0])
    work: dict[str, np.ndarray] = {}
    np.testing.assert_array_equal(
        sigma_knots_decode(raw, S_LO, S_HI, work=work, reuse_output=True), sigma_knots_decode(raw, S_LO, S_HI)
    )
