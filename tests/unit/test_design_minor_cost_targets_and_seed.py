"""Three DESIGN minors of the audit of 2026-11-15 (L1-m2, L1-m3, L1-m5).

L1-m2: with fewer than 5 admissible points (a laser line), the fast cost returned 1e12 and the cost-and-gradient path
       its true value: the two paths judged one design differently.
L1-m3: in normal incidence two overlapping targets kept only the last row there, silently.
L1-m5: PGlobal ran unseeded in DESIGN and consumed its local searches in their order of completion.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np

from certus.core.certus_design_worker_utils import build_pglobal_config_from_cfg
from certus.physics import certus_optimizers
from certus.physics.design_fast_normal import compute_gradient_lossless_front_fast, cost_lossless_front_fast
from certus.ui.certus_spectrum_eval_ui import _warn_overlapping_targets, overlapping_target_ranges


def _stack(n_wls: int):
    wls = np.linspace(500.0, 600.0, n_wls)
    n = np.tile(np.array([2.3, 1.46]), (n_wls, 1))
    return dict(
        ep=np.array([60.0, 90.0]),
        n_layers_real=n,
        inv_n_layers_real=1.0 / n,
        n_sub_real=np.full(n_wls, 1.52),
        k0_wls=2.0 * np.pi / wls,
        tgt_vals=np.full(n_wls, 0.9),
    )


def test_l1_m2_a_target_of_fewer_than_five_points_is_judged_alike_by_both_paths() -> None:
    a = _stack(3)
    weights = np.ones(3)
    cost = cost_lossless_front_fast(a["ep"], a["n_layers_real"], a["inv_n_layers_real"], a["n_sub_real"], a["k0_wls"], a["tgt_vals"], weights)
    with_grad, grad = compute_gradient_lossless_front_fast(
        a["ep"], a["n_layers_real"], a["inv_n_layers_real"], a["n_sub_real"], a["k0_wls"], a["tgt_vals"], weights, np.array([0, 1])
    )
    assert cost == 1e12
    assert with_grad == cost
    assert np.all(grad == 0.0)


def test_l1_m2_enough_points_keep_the_kernel_value() -> None:
    a = _stack(11)
    weights = np.ones(11)
    cost = cost_lossless_front_fast(a["ep"], a["n_layers_real"], a["inv_n_layers_real"], a["n_sub_real"], a["k0_wls"], a["tgt_vals"], weights)
    with_grad, _ = compute_gradient_lossless_front_fast(
        a["ep"], a["n_layers_real"], a["inv_n_layers_real"], a["n_sub_real"], a["k0_wls"], a["tgt_vals"], weights, np.array([0, 1])
    )
    assert abs(with_grad - cost) <= 1e-12 * max(1.0, cost)


def _tgt(lmin: float, lmax: float):
    return SimpleNamespace(lmin=lmin, lmax=lmax)


def test_l1_m3_overlaps_are_found_and_said_once() -> None:
    tgts = [_tgt(400.0, 600.0), _tgt(550.0, 700.0), _tgt(800.0, 900.0)]
    assert overlapping_target_ranges(tgts) == [(1, 2, 550.0, 600.0)]
    logged: list[tuple[str, str]] = []
    app = SimpleNamespace(log=lambda message, level="INFO": logged.append((level, message)))
    _warn_overlapping_targets(app, tgts)
    _warn_overlapping_targets(app, tgts)
    assert len(logged) == 1
    assert logged[0][0] == "WARNING"
    assert "550-600 nm" in logged[0][1]


def test_l1_m3_targets_that_do_not_overlap_say_nothing() -> None:
    logged: list[str] = []
    app = SimpleNamespace(log=lambda message, level="INFO": logged.append(message))
    _warn_overlapping_targets(app, [_tgt(400.0, 500.0), _tgt(510.0, 600.0)])
    assert not logged


def test_l1_m5_every_design_mode_is_seeded() -> None:
    for mode in ("local", "healing", "global"):
        conf, _ = build_pglobal_config_from_cfg({}, mode=mode, dim=6, conv_tol=1e-8)
        assert conf.random_seed == 0, mode
    conf, _ = build_pglobal_config_from_cfg({"run_seed": 17}, mode="global", dim=6, conv_tol=1e-8)
    assert conf.random_seed == 17


def test_l1_m5_local_searches_are_consumed_in_the_order_of_the_tasks() -> None:
    source = inspect.getsource(certus_optimizers.PGlobalOptimizer._dispatch_and_collect)
    assert "as_completed(" not in source
    assert "for future in list(futures):" in source
