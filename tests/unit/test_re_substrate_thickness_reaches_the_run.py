"""Chantier 47: the substrate thickness of an RE run reaches its objective and its curves.

The run's state (`_re_state`) carries `substrate_thickness_nm`, read from the configuration; the objective's physics
loop and the phase-4 curve of DESIGN's spectral worker pass it on. A state without it is a state at 1 mm, with the bits
of before (C1).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.core.certus_re_objectives import _global_evaluate_oblique_physics
from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM
from certus.workers.certus_spectral_workers import _re_phase4_oblique_spectrum

WLS = np.array([450.0, 550.0, 650.0, 800.0, 1000.0, 1200.0])


def _layers(k: float):
    rng = np.random.default_rng(47)
    n = rng.uniform(1.4, 2.3, (len(WLS), 3)).astype(np.complex128)
    d = rng.uniform(50.0, 160.0, 3)
    return d, n, np.array([complex(1.52, -k)] * len(WLS))


def _objective(k: float, state_extra: dict) -> list[np.ndarray]:
    d, n, n_sub = _layers(k)
    every = np.arange(len(WLS), dtype=np.int64)
    meta = {"angle": 30.0, "pol": "avg", "include_backside": True, "pos_all_union": every,
            "buckets": [{"local_positions": every, "idx_union": every, "R": {}, "T": {}}]}
    ctx = SimpleNamespace(oblique_config_meta=[meta], wls=WLS, var_idx=np.arange(3, dtype=np.int64),
                          _re_state={"is_phase4": False, **state_extra})
    seen: list[np.ndarray] = []
    _global_evaluate_oblique_physics(ctx, d, n, n_sub, np.ones(len(WLS)), True, False,
                                     lambda y, dy, _stats, _w: seen.extend([np.array(y), np.array(dy)]))
    return seen


def _phase4(k: float, **kw) -> list[np.ndarray]:
    d, n, n_sub = _layers(k)
    knots = np.array([1.0, 2.0, 3.0])
    lam = np.array([400.0, 800.0, 1300.0])
    return list(_re_phase4_oblique_spectrum(wls_arr=WLS, n_front_T=n, d_front_arr=d, n_sub_arr=n_sub, angle=30.0,
                                            pol="avg", include_backside=True, beam_aperture=2.0, ak=knots, alk=lam,
                                            nk=3, **kw))


@pytest.mark.parametrize("k", [0.0, 1e-5])
def test_a_state_without_a_thickness_is_a_state_at_one_millimetre(k) -> None:
    pairs = [(_objective(k, {}), _objective(k, {"substrate_thickness_nm": DEFAULT_SUBSTRATE_THICKNESS_NM})),
             (_phase4(k), _phase4(k, substrate_thickness_nm=DEFAULT_SUBSTRATE_THICKNESS_NM))]
    for before, at_1mm in pairs:
        for a, b in zip(before, at_1mm, strict=True):
            assert np.array_equal(a.view(np.uint64), b.view(np.uint64))


def test_the_thickness_of_the_run_acts_on_an_absorbing_substrate() -> None:
    thick = {"substrate_thickness_nm": 2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM}
    for a, b in zip(_objective(1e-5, {}), _objective(1e-5, thick), strict=True):
        assert not np.array_equal(a, b)
    for a, b in zip(_phase4(1e-5), _phase4(1e-5, substrate_thickness_nm=2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM),
                    strict=True):
        assert not np.array_equal(a, b)
    for a, b in zip(_objective(0.0, {}), _objective(0.0, thick), strict=True):
        assert np.array_equal(a, b)
