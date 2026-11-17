"""Chantier 47: `substrate_thickness_nm` of a DESIGN run reaches each relay down to the kernels.

Absent, every relay is at 1 mm (the bits before, C1); given, an absorbing substrate seen with its back face answers
to it. A relay that dropped it would compute at 1 mm without a word (CLAUDE.md section 4).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_substrate_absorption import (
    DEFAULT_SUBSTRATE_THICKNESS_NM,
    substrate_thickness_nm_from_mm,
    substrate_thickness_nm_of,
)

WLS = np.array([450.0, 550.0, 650.0, 800.0, 1000.0])
THICK = 3.0 * DEFAULT_SUBSTRATE_THICKNESS_NM


def _optics(k: float = 1e-5):
    rng = np.random.default_rng(83)
    n = rng.uniform(1.4, 2.3, (len(WLS), 3)).astype(np.complex128)
    d = rng.uniform(50.0, 160.0, 3)
    n_sub = np.array([complex(1.52, -k)] * len(WLS))
    return n, d, n_sub


def test_the_millimetres_of_a_configuration() -> None:
    assert substrate_thickness_nm_from_mm(1.0) == DEFAULT_SUBSTRATE_THICKNESS_NM
    assert substrate_thickness_nm_from_mm(2.5) == 2.5e6
    assert substrate_thickness_nm_from_mm(0.5) == 5.0e5  # a plate thinner than the default is a thickness too
    for empty in (None, "", "x", 0.0, -1.0, float("nan")):
        assert substrate_thickness_nm_from_mm(empty) == DEFAULT_SUBSTRATE_THICKNESS_NM


def test_a_dict_and_the_worker_dto_both_give_it() -> None:
    from certus.core.certus_design_workers_dto import NeedleWorkerRequest, OptimWorkerRequest

    assert substrate_thickness_nm_of({}) == DEFAULT_SUBSTRATE_THICKNESS_NM
    assert substrate_thickness_nm_of({"substrate_thickness_nm": None}) == DEFAULT_SUBSTRATE_THICKNESS_NM
    assert substrate_thickness_nm_of({"substrate_thickness_nm": THICK}) == THICK
    for request in (OptimWorkerRequest, NeedleWorkerRequest):
        assert substrate_thickness_nm_of(request.from_legacy({"substrate_thickness_nm": THICK}).params) == THICK
        assert substrate_thickness_nm_of(request.from_legacy({}).params) == DEFAULT_SUBSTRATE_THICKNESS_NM


@pytest.mark.parametrize("worker_name", ["OptimWorker", "NeedleWorker", "ColorWorker"])
def test_the_workers_read_it_from_their_configuration(worker_name) -> None:
    import certus.workers.certus_design_workers as workers

    cls = getattr(workers, worker_name)
    assert cls({"substrate_thickness_nm": THICK})._substrate_thickness_nm == THICK
    assert cls({})._substrate_thickness_nm == DEFAULT_SUBSTRATE_THICKNESS_NM


def test_the_spectral_evaluation_and_the_oblique_selection_pass_it_on() -> None:
    from certus.core.certus_design_worker_utils import optim_calc_oblique_selected
    from certus.physics.certus_tmm_oblique import (
        calc_spectrum_full_oblique_exact,
        calc_spectrum_oblique_backside_vectorized,
        calc_spectrum_oblique_vectorized,
    )
    from certus.workers.certus_spectral_workers import _calc_oblique_selected_kernel, _transmission_non_oblique

    n, d, n_sub = _optics()
    empty_n, empty_d = np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0)
    back = {"n_back_T": empty_n, "d_back": empty_d}

    def normal(**kw):
        return _transmission_non_oblique(wls=WLS, n_front_T=n, d_front=d, n_sub=n_sub, back_enabled=True, **back, **kw)

    assert np.array_equal(normal(), normal(substrate_thickness_nm=DEFAULT_SUBSTRATE_THICKNESS_NM))
    assert not np.array_equal(normal(), normal(substrate_thickness_nm=THICK))

    kernels = {
        "calc_spectrum_full_oblique_exact": calc_spectrum_full_oblique_exact,
        "calc_spectrum_oblique_backside_vectorized": calc_spectrum_oblique_backside_vectorized,
        "calc_spectrum_oblique_vectorized": calc_spectrum_oblique_vectorized,
    }
    for stack in (False, True):
        nb, db = (n[:, :2].copy(), d[:2].copy()) if stack else (empty_n, empty_d)

        def utils(stack=stack, nb=nb, db=db, **kw):
            return optim_calc_oblique_selected(WLS, n, d, n_sub, 30.0, "s", has_back_calc=True, has_back_stack=stack,
                                               d_back=db, n_back_T=nb, **kernels, **kw)[1]

        def spectral(stack=stack, nb=nb, db=db, **kw):
            return _calc_oblique_selected_kernel(wls_arr=WLS, n_front_T=n, d_front_arr=d, n_sub_arr=n_sub, angle=30.0,
                                                 pol="s", has_back_calc=True, has_back_stack=stack, n_back_T_arr=nb,
                                                 d_back_arr=db, **kw)[1]

        for path in (utils, spectral):
            assert np.array_equal(path(), path(substrate_thickness_nm=DEFAULT_SUBSTRATE_THICKNESS_NM))
            assert not np.array_equal(path(), path(substrate_thickness_nm=THICK))


def test_the_bridge_and_the_core_accessor_carry_it() -> None:
    from types import SimpleNamespace

    from certus.core.certus_design_core import substrate_thickness_of
    from certus.workers.certus_design_engine import DesignPhysicsBridge

    assert substrate_thickness_of(SimpleNamespace()) == DEFAULT_SUBSTRATE_THICKNESS_NM
    assert substrate_thickness_of(SimpleNamespace(_substrate_thickness_nm=THICK)) == THICK

    n, d, n_sub = _optics()
    common = dict(var_idx=np.arange(3), all_variable=True, ep0=d, oblique_mode=False, has_back_calc=True,
                  has_back_stack=False, d_back=np.zeros(0), n_back_T=np.zeros((len(WLS), 0), dtype=np.complex128),
                  n_layers_T=n, n_sub=n_sub, wls=WLS, tgt_vals=np.full(len(WLS), 0.5), tgt_weights=np.ones(len(WLS)),
                  oblique_configs=[])
    default, thick = DesignPhysicsBridge(**common), DesignPhysicsBridge(**common, substrate_thickness_nm=THICK)
    assert default.substrate_thickness_nm == DEFAULT_SUBSTRATE_THICKNESS_NM
    assert default.objective(d) != thick.objective(d)
    assert default.gradient(d)[0] != thick.gradient(d)[0]
