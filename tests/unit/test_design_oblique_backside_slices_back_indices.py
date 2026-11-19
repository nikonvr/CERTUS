"""Regression tests for C1: oblique back-side stack must slice n_back_T per config and use _n_back_T_disp."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from certus.core import certus_design_core as design_core
from certus.core.certus_design_worker_utils import (
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
)
from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact
from certus.workers.certus_design_engine import DesignPhysicsBridge
from certus_physics.structures import ObliqueTarget


def _build_oblique_backside_fixture():
    wls = np.linspace(400.0, 1000.0, 61, dtype=np.float64)
    n_front = np.column_stack(
        [
            2.30 + 0.08 * (500.0 / wls) ** 2,
            1.46 + 0.02 * (500.0 / wls) ** 2,
        ]
    ).astype(np.complex128)
    d_front = np.array([60.0, 90.0], dtype=np.float64)
    # Strongly dispersive back layer so wls[0:21] != wls[40:61]
    n_back = np.column_stack([1.45 + 0.80 * (400.0 / wls) ** 2]).astype(np.complex128)
    d_back = np.array([110.0], dtype=np.float64)
    n_sub = np.full(len(wls), 1.52 + 0j, dtype=np.complex128)

    tgt = ObliqueTarget(45.0, "s", 800.0, 1000.0, 0.0, 0.0, "R", 1.0, True, True)
    groups = optim_oblique_group_targets_on_wavelengths(wls, [tgt])
    cfgs = optim_oblique_configs_from_groups(groups, wls, n_sub, n_front)
    optim_oblique_attach_local_positions(cfgs)
    for cfg in cfgs:
        cfg["sw_cfg"] = np.ones(len(cfg["wls_config"]), dtype=np.float64)

    idx = cfgs[0]["all_clues"]
    r_true, _ = calc_spectrum_full_oblique_exact(
        wls[idx], d_front, n_front[idx], d_back, n_back[idx], n_sub[idx], 45.0, True
    )
    expected_mse = float(np.mean(r_true**2))
    return wls, n_front, d_front, n_back, d_back, n_sub, cfgs, expected_mse


@pytest.mark.unit
def test_design_physics_bridge_compute_oblique_error_slices_n_back_T() -> None:
    wls, n_front, d_front, n_back, d_back, n_sub, cfgs, expected_mse = _build_oblique_backside_fixture()
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0, 1], dtype=np.int64),
        all_variable=True,
        ep0=d_front.copy(),
        oblique_mode=True,
        has_back_calc=True,
        has_back_stack=True,
        d_back=d_back,
        n_back_T=n_back,
        n_layers_T=n_front,
        n_sub=n_sub,
        wls=wls,
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=cfgs,
    )
    grad_cost, _ = bridge.compute_oblique_error_and_grad_analytic(d_front)
    eval_cost = bridge.compute_oblique_error(d_front)
    assert grad_cost == pytest.approx(expected_mse, rel=1e-12, abs=1e-12)
    assert eval_cost == pytest.approx(expected_mse, rel=1e-12, abs=1e-12)


@pytest.mark.unit
def test_design_compute_oblique_error_common_slices_n_back_T() -> None:
    _, _, d_front, n_back, d_back, _, cfgs, expected_mse = _build_oblique_backside_fixture()
    fake_app = SimpleNamespace(
        _oblique_configs=cfgs,
        _has_back_calc=True,
        _has_back_stack=True,
        _d_back=d_back,
        _n_back_T=n_back,
        _substrate_thickness_nm=1_000_000.0,
    )
    err = design_core._design_compute_oblique_error_common(fake_app, d_front)
    assert err == pytest.approx(expected_mse, rel=1e-12, abs=1e-12)


@pytest.mark.unit
def test_design_optimization_callback_uses_n_back_T_disp_on_display_grid(monkeypatch) -> None:
    seen_back_lengths: list[int] = []

    def fake_selected(
        wls_arr,
        n_front_T,
        d_front_arr,
        n_sub_arr,
        angle,
        pol,
        *,
        has_back_calc,
        has_back_stack,
        d_back,
        n_back_T,
        calc_spectrum_full_oblique_exact,
        calc_spectrum_oblique_backside_vectorized,
        calc_spectrum_oblique_vectorized,
        substrate_thickness_nm=None,
    ):
        seen_back_lengths.append(len(n_back_T))
        assert len(n_back_T) == len(wls_arr)
        return np.zeros(len(wls_arr), dtype=np.float64), np.ones(len(wls_arr), dtype=np.float64)

    monkeypatch.setattr(design_core, "optim_calc_oblique_selected", fake_selected)

    wls_disp = np.linspace(400.0, 1000.0, 121, dtype=np.float64)
    n_front_disp = np.full((121, 2), 2.0 + 0j, dtype=np.complex128)
    n_sub_disp = np.full(121, 1.5 + 0j, dtype=np.complex128)
    n_back_disp = np.full((121, 1), 1.7 + 0j, dtype=np.complex128)
    n_back_opt = np.full((61, 1), 1.7 + 0j, dtype=np.complex128)

    fake_app = SimpleNamespace(
        _stop_event=Event(),
        _optimizer=SimpleNamespace(clusterer=SimpleNamespace(clusters=[]), n_evals=10),
        _callback_counter=9,  # becomes 10 -> triggers immediate emit
        best_rmse_seen=float("inf"),
        best_ep_final=None,
        best_rmse_final=float("inf"),
        cfg={"max_feval": 100},
        _ep0=np.array([60.0, 90.0], dtype=np.float64),
        _var_idx=np.array([0, 1], dtype=np.int64),
        _oblique_mode=True,
        _display_oblique_keys=[(45.0, "s")],
        _oblique_tgts=[],
        _wls_display=wls_disp,
        _n_lay_T_disp=n_front_disp,
        _n_sub_disp=n_sub_disp,
        _n_back_T_disp=n_back_disp,
        _n_back_T=n_back_opt,
        _d_back=np.array([100.0], dtype=np.float64),
        _has_back_calc=True,
        _has_back_stack=True,
        _substrate_thickness_nm=1_000_000.0,
        _last_live_emit_time=0.0,  # triggers second 5s live emit
    )
    sample = SimpleNamespace(x=np.array([60.0, 90.0], dtype=np.float64), y=0.01, generation=1)
    design_core._design_optimization_callback_common(fake_app, sample)

    assert seen_back_lengths == [121, 121]


@pytest.mark.unit
def test_needle_worker_oblique_error_slices_n_back_T(monkeypatch, qapp) -> None:
    from certus.core.certus_design_worker_utils import optim_oblique_config_weights
    from certus.workers.certus_design_workers import NeedleWorker
    from certus_physics import Material
    from certus_physics.structures import Layer

    wls, _, d_front, n_back, d_back, _, cfgs, _ = _build_oblique_backside_fixture()
    mat_h = Material(2.30, 2.30)
    mat_l = Material(1.46, 1.46)
    mat_sub = Material(1.52, 1.52)
    mats = {"H": mat_h, "L": mat_l, "substrate": mat_sub}
    stack = [Layer("H", float(d_front[0])), Layer("L", float(d_front[1]))]
    tgt = ObliqueTarget(45.0, "s", 800.0, 1000.0, 0.0, 0.0, "R", 1.0, True, True)

    captured: dict[str, float] = {}

    _, n_front_ref, _, _, _, n_sub_ref, _, _ = _build_oblique_backside_fixture()
    idx = cfgs[0]["all_clues"]
    r_true, _ = calc_spectrum_full_oblique_exact(
        wls[idx], d_front, n_front_ref[idx], d_back, n_back[idx], n_sub_ref[idx], 45.0, True
    )
    sw = optim_oblique_config_weights(cfgs[0])
    expected_needle_mse = float(np.sum(sw * (r_true**2)) / np.sum(sw))

    def fake_prepare_design_cost_context(*args, **kwargs):
        return SimpleNamespace(wls=wls, mats_nk={"H": n_front_ref[:, 0], "L": n_front_ref[:, 1]}, n_sub=n_sub_ref, n_front=n_front_ref)

    monkeypatch.setattr("certus.workers.certus_design_workers.prepare_design_cost_context", fake_prepare_design_cost_context)

    worker = NeedleWorker(
        {
            "stack": stack,
            "mats": mats,
            "ep": d_front.copy(),
            "wls": wls,
            "tgts": [],
            "oblique_mode": True,
            "oblique_tgts": [tgt],
            "has_back": True,
            "n_back_T": n_back,
            "d_back": d_back,
        }
    )

    def fake_fallback(*, ep_base, n_layers_T_orig, compute_oblique_error_needle, **kwargs):
        captured["needle_mse"] = float(compute_oblique_error_needle(ep_base, n_layers_T_orig))
        return None

    monkeypatch.setattr(worker, "_run_needle_fallback_scan", fake_fallback)
    worker.run()

    assert captured["needle_mse"] == pytest.approx(expected_needle_mse, rel=1e-12, abs=1e-12)
