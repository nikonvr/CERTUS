"""The cached needle scan with an incoherent back side picks the candidate of the uncached scan, at its cost.

Before, a design with a back side scanned needles by recomputing the whole stack for every position
(`_run_needle_fallback_scan`); `needle_scan_cached_backside` reuses the cached products of the layers below and
above each candidate and computes the back side once. Measured on 2026-10-23: x19.5 (34 layers, 140 wavelengths)
to x39.4 (96 layers, 601 wavelengths) faster, same candidate, cost equal to 1e-15
(reports/DESIGN_bs5050_2026-10-22/journal.md). The oracle's incoherent plate checks the cost of the choice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

STEP, PROBE = 2.0, 1.0


def _case(n_sub_value: complex):
    wls = np.linspace(400.0, 900.0, 60)
    ep = np.array([30.0, 90.0, 55.0, 120.0, 40.0, 75.0])
    n_h, n_l = np.full(len(wls), 2.3 + 0j), np.full(len(wls), 1.46 + 0j)
    mats = "HLHLHL"
    n_of, other = {"H": n_h, "L": n_l}, {"H": "L", "L": "H"}
    n_t = np.ascontiguousarray(np.array([n_of[m] for m in mats], dtype=np.complex128).T)
    n_needle_t = np.ascontiguousarray(np.array([n_of[other[m]] for m in mats], dtype=np.complex128).T)
    n_sub = np.full(len(wls), n_sub_value, dtype=np.complex128)
    return wls, ep, n_t, n_needle_t, n_sub


def _uncached(wls, ep, n_t, n_needle_t, n_sub, tgt, w, n_back, d_back):
    from certus.physics.gradient_utils import cost_numba_fast

    best = (np.inf, -1, 0.0)
    for i, d in enumerate(ep):
        n_test = np.ascontiguousarray(np.hstack([n_t[:, :i], n_t[:, i:i + 1], n_needle_t[:, i:i + 1], n_t[:, i:i + 1], n_t[:, i + 1:]]))
        ep_test = np.empty(len(ep) + 2)
        ep_test[:i], ep_test[i + 3:], ep_test[i + 1] = ep[:i], ep[i + 1:], PROBE
        for z in np.arange(STEP, d - 0.1, STEP):
            ep_test[i], ep_test[i + 2] = z, d - z
            c = cost_numba_fast(ep_test, n_test, n_sub, wls, tgt, w, 0.0, True, n_back, d_back)
            if c < best[0]:
                best = (float(c), i, float(z))
    return best


@pytest.mark.parametrize("n_sub_value", [1.52 + 0j, 1.76 - 0.0005j])
def test_the_cached_scan_with_a_back_side_picks_the_uncached_candidate(n_sub_value) -> None:
    from certus.physics.certus_opt_needle import needle_scan_cached_backside
    from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact

    wls, ep, n_t, n_needle_t, n_sub = _case(n_sub_value)
    tgt, w = np.full(len(wls), 0.5), np.ones(len(wls))
    n_back, d_back = np.zeros((len(wls), 0), dtype=np.complex128), np.zeros(0)
    _rf, _tf, _rfp, rb_prime, tb = calc_spectrum_full_exact(wls, ep, n_t, d_back, n_back, n_sub)

    layer, depth, cost = needle_scan_cached_backside(wls, n_t, n_needle_t, n_sub, ep, tgt, w, STEP, PROBE,
                                                     np.ones(len(ep), dtype=np.int64), rb_prime, tb)
    reference = _uncached(wls, ep, n_t, n_needle_t, n_sub, tgt, w, n_back, d_back)

    assert (int(layer), float(depth)) == (reference[1], reference[2])
    assert cost == pytest.approx(reference[0], rel=1e-12)


def test_the_cost_of_the_chosen_candidate_is_the_oracle_cost() -> None:
    from tmm_reference import rt_plate_incoherent

    from certus.physics.certus_opt_needle import needle_scan_cached_backside
    from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact

    wls, ep, n_t, n_needle_t, n_sub = _case(1.52 + 0j)
    tgt, w = np.full(len(wls), 0.5), np.ones(len(wls))
    n_back, d_back = np.zeros((len(wls), 0), dtype=np.complex128), np.zeros(0)
    _rf, _tf, _rfp, rb_prime, tb = calc_spectrum_full_exact(wls, ep, n_t, d_back, n_back, n_sub)
    layer, depth, cost = needle_scan_cached_backside(wls, n_t, n_needle_t, n_sub, ep, tgt, w, STEP, PROBE,
                                                     np.ones(len(ep), dtype=np.int64), rb_prime, tb)

    i, z = int(layer), float(depth)
    columns = [*[n_t[:, k] for k in range(i)], n_t[:, i], n_needle_t[:, i], n_t[:, i], *[n_t[:, k] for k in range(i + 1, len(ep))]]
    thicknesses = np.array([*ep[:i], z, PROBE, ep[i] - z, *ep[i + 1:]])
    t = np.array([rt_plate_incoherent(wl, [col[k] for col in columns], thicknesses, [], [], 1.52 + 0j, 0.0, True, 1e6)[1]
                  for k, wl in enumerate(wls)])

    assert cost == pytest.approx(float(np.mean((t - 0.5) ** 2)), rel=1e-10)
