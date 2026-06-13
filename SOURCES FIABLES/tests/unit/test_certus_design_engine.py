"""Unit tests for the CERTUS_DESIGN physics bridge."""

from __future__ import annotations

import numpy as np
import pytest

from certus.workers.certus_design_engine import DesignPhysicsBridge


@pytest.mark.unit
def test_design_physics_bridge_returns_safe_sentinel_on_dimension_mismatch() -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0, 2], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0, 20.0, 30.0], dtype=np.float64),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((0, 0), dtype=np.complex128),
        n_sub=np.zeros(0, dtype=np.complex128),
        wls=np.zeros(0, dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[],
    )

    cost = bridge.objective(np.array([1.0], dtype=np.float64))
    grad_cost, grad = bridge.gradient(np.array([1.0], dtype=np.float64))

    assert cost == 1e30
    assert grad_cost == 1e30
    assert grad.shape == (2,)
    assert np.all(grad == 0.0)


@pytest.mark.unit
def test_design_physics_bridge_delegates_to_flat_cost_and_gradient(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_cost_numba_fast(ep_test, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, min_thickness, has_back_calc, n_back_T, d_back):
        calls["objective_ep"] = ep_test.copy()
        calls["objective_min_thickness"] = min_thickness
        return 12.5

    def fake_gradient(ep_test, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, min_thickness, has_back_calc, n_back_T, d_back, var_idx):
        calls["gradient_ep"] = ep_test.copy()
        calls["gradient_var_idx"] = var_idx.copy()
        return 3.5, np.array([0.1, 0.2], dtype=np.float64)

    import certus.workers.certus_design_engine as engine_mod

    monkeypatch.setattr(engine_mod, "cost_numba_fast", fake_cost_numba_fast)
    monkeypatch.setattr(engine_mod, "compute_gradient_all_layers_analytic", fake_gradient)

    bridge = DesignPhysicsBridge(
        var_idx=np.array([0, 2], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0, 20.0, 30.0], dtype=np.float64),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 3), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=np.array([0.5], dtype=np.float64),
        tgt_weights=np.array([1.0], dtype=np.float64),
        oblique_configs=[],
    )

    cost = bridge.objective(np.array([11.0, 31.0], dtype=np.float64))
    grad_cost, grad = bridge.gradient(np.array([11.0, 31.0], dtype=np.float64))

    assert cost == 12.5
    assert grad_cost == 3.5
    assert np.allclose(grad, [0.1, 0.2])
    assert np.allclose(calls["objective_ep"], [11.0, 20.0, 31.0])
    assert np.allclose(calls["gradient_ep"], [11.0, 20.0, 31.0])
    assert np.allclose(calls["gradient_var_idx"], [0, 2])


@pytest.mark.unit
def test_design_physics_bridge_reuses_ep_buffer_for_partial_updates() -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([1], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0, 20.0, 30.0], dtype=np.float64),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 3), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=np.array([0.5], dtype=np.float64),
        tgt_weights=np.array([1.0], dtype=np.float64),
        oblique_configs=[],
    )

    ep_first = bridge._build_ep(np.array([25.0], dtype=np.float64))
    first_snapshot = ep_first.copy()
    ep_second = bridge._build_ep(np.array([26.0], dtype=np.float64))

    assert np.allclose(first_snapshot, [10.0, 25.0, 30.0])
    assert np.allclose(ep_second, [10.0, 26.0, 30.0])
    assert bridge.ep_buffer is not None
    assert np.allclose(bridge.ep_buffer, [10.0, 26.0, 30.0])


@pytest.mark.unit
def test_design_physics_bridge_oblique_empty_configs_returns_safe_sentinel() -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0], dtype=np.int64),
        all_variable=False,
        ep0=np.array([15.0], dtype=np.float64),
        oblique_mode=True,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 1), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[],
    )

    cost = bridge.objective(np.array([16.0], dtype=np.float64))
    grad_cost, grad = bridge.gradient(np.array([16.0], dtype=np.float64))

    assert cost == 1e30
    assert grad_cost == 1e30
    assert np.allclose(grad, [0.0])


@pytest.mark.unit
def test_design_physics_bridge_all_variable_builds_contiguous_copy() -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0, 1], dtype=np.int64),
        all_variable=True,
        ep0=np.array([10.0, 20.0], dtype=np.float64),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((0, 0), dtype=np.complex128),
        n_sub=np.zeros(0, dtype=np.complex128),
        wls=np.zeros(0, dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[],
    )

    x = np.array([11.0, 22.0], dtype=np.float64)
    ep = bridge._build_ep(x)

    assert np.allclose(ep, x)
    assert ep.flags.c_contiguous
    assert np.shares_memory(ep, x)


@pytest.mark.unit
def test_design_physics_bridge_rejects_thickness_below_minimum_when_fixed_layer_present() -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0], dtype=np.int64),
        all_variable=False,
        ep0=np.array([0.00001, 0.5], dtype=np.float64),
        oblique_mode=False,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 2), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=np.array([0.5], dtype=np.float64),
        tgt_weights=np.array([1.0], dtype=np.float64),
        oblique_configs=[],
    )

    cost = bridge.objective(np.array([0.00001], dtype=np.float64))
    grad_cost, grad = bridge.gradient(np.array([0.00001], dtype=np.float64))

    assert cost == 1e30
    assert grad_cost == 1e30
    assert np.allclose(grad, [0.0])


@pytest.mark.unit
def test_design_physics_bridge_oblique_objective_delegates_to_selected_kernel(monkeypatch) -> None:
    import certus.workers.certus_design_engine as engine_mod

    seen: dict[str, object] = {}

    def fake_selected(wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol, *, has_back_calc, has_back_stack, d_back, n_back_T, calc_spectrum_full_oblique_exact, calc_spectrum_oblique_backside_vectorized, calc_spectrum_oblique_vectorized):
        seen["wls_arr"] = wls_arr.copy()
        seen["angle"] = angle
        seen["pol"] = pol
        return np.array([0.6], dtype=np.float64), np.array([0.2], dtype=np.float64)

    monkeypatch.setattr(engine_mod, "optim_calc_oblique_selected", fake_selected)

    bridge = DesignPhysicsBridge(
        var_idx=np.array([0], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0], dtype=np.float64),
        oblique_mode=True,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 1), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[{
            "wls_config": np.array([550.0], dtype=np.float64),
            "n_layers_T_config": np.zeros((1, 1), dtype=np.complex128),
            "n_sub_config": np.zeros(1, dtype=np.complex128),
            "angle": 45.0,
            "pol": "s",
            "sw_cfg": np.array([1.0], dtype=np.float64),
            "targets": [{"local_positions": np.array([0], dtype=np.int64), "target_type": "R", "tgt_vals": np.array([0.5], dtype=np.float64), "weight": 1.0}],
        }],
    )

    cost = bridge.objective(np.array([11.0], dtype=np.float64))

    assert cost == pytest.approx(0.01)
    assert np.allclose(seen["wls_arr"], [550.0])
    assert seen["angle"] == 45.0
    assert seen["pol"] == "s"


@pytest.mark.unit
def test_design_physics_bridge_oblique_objective_delegates_to_helper(monkeypatch) -> None:
    import certus.workers.certus_design_engine as engine_mod

    calls: dict[str, object] = {}

    def fake_calc_selected(*args, **kwargs):
        calls["called"] = True
        calls["wls"] = np.asarray(args[0]).copy()
        return np.array([0.2, 0.4], dtype=np.float64), np.array([0.1, 0.3], dtype=np.float64)

    monkeypatch.setattr(engine_mod, "optim_calc_oblique_selected", fake_calc_selected)

    bridge = DesignPhysicsBridge(
        var_idx=np.array([0], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0], dtype=np.float64),
        oblique_mode=True,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 1), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([500.0, 600.0], dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[
            {
                "wls_config": np.array([500.0, 600.0], dtype=np.float64),
                "n_layers_T_config": np.zeros((2, 1), dtype=np.complex128),
                "n_sub_config": np.zeros(2, dtype=np.complex128),
                "angle": 45.0,
                "pol": "s",
                "is_s_pol": True,
                "sw_cfg": np.array([1.0, 1.0], dtype=np.float64),
                "targets": [
                    {
                        "local_positions": np.array([0, 1], dtype=np.int64),
                        "tgt_vals": np.array([0.2, 0.4], dtype=np.float64),
                        "target_type": "R",
                        "weight": 1.0,
                    }
                ],
                "all_clues": np.array([0, 1], dtype=np.int64),
            }
        ],
    )

    cost = bridge.objective(np.array([10.0], dtype=np.float64))

    assert calls.get("called") is True
    assert np.allclose(calls["wls"], [500.0, 600.0])
    assert cost >= 0.0


@pytest.mark.unit
def test_design_physics_bridge_oblique_gradient_delegates_to_analytic_hook(monkeypatch) -> None:
    bridge = DesignPhysicsBridge(
        var_idx=np.array([0], dtype=np.int64),
        all_variable=False,
        ep0=np.array([10.0], dtype=np.float64),
        oblique_mode=True,
        has_back_calc=False,
        has_back_stack=False,
        d_back=np.zeros(0, dtype=np.float64),
        n_back_T=np.zeros((0, 0), dtype=np.complex128),
        n_layers_T=np.zeros((1, 1), dtype=np.complex128),
        n_sub=np.zeros(1, dtype=np.complex128),
        wls=np.array([550.0], dtype=np.float64),
        tgt_vals=None,
        tgt_weights=None,
        oblique_configs=[],
    )

    calls: list[np.ndarray] = []

    def fake_hook(ep_test):
        calls.append(ep_test.copy())
        return 7.0, np.array([0.33], dtype=np.float64)

    monkeypatch.setattr(bridge, "compute_oblique_error_and_grad_analytic", fake_hook)

    cost, grad = bridge.gradient(np.array([11.0], dtype=np.float64))

    assert cost == 7.0
    assert np.allclose(grad, [0.33])
    assert len(calls) == 1
    assert np.allclose(calls[0], [11.0])
