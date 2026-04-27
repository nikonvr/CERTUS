"""Tests certus_design_worker_utils (sans Qt)."""

from types import SimpleNamespace

import numpy as np
import pytest

from certus_design_worker_utils import (
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    optim_post_optim_time_budget_seconds,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_prepare_stack_nk_back,
)


def _mat_const(ncomplex: complex):
    class _M:
        def get_nk(self, wls):
            w = np.asarray(wls, dtype=np.float64)
            return np.full(w.shape, ncomplex, dtype=np.complex128)

    return _M()


def test_optim_oblique_unique_display_keys_order():
    a = SimpleNamespace(angle=30.0, pol="s")
    b = SimpleNamespace(angle=30.0, pol="s")
    c = SimpleNamespace(angle=45.0, pol="p")
    assert optim_oblique_unique_display_keys([a, b, c]) == [(30.0, "s"), (45.0, "p")]


def test_optim_oblique_group_targets_on_wavelengths():
    wls = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    t1 = SimpleNamespace(
        lmin=400.0,
        lmax=500.0,
        angle=15.0,
        pol="s",
        tmin=0.0,
        tmax=1.0,
        target_type="R",
        w=2.0,
    )
    t2 = SimpleNamespace(
        lmin=500.0,
        lmax=500.0,
        angle=15.0,
        pol="s",
        tmin=0.5,
        tmax=0.5,
        target_type="T",
        w=1.0,
    )
    g = optim_oblique_group_targets_on_wavelengths(wls, [t1, t2])
    assert (15.0, "s") in g
    clues = g[(15.0, "s")]["clues_set"]
    assert clues == {0, 1}


def test_optim_oblique_configs_from_groups_and_local_positions():
    wls = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    n_sub = np.asarray([1.52, 1.52, 1.52], dtype=np.complex128)
    n_layers_T = np.ones((3, 2), dtype=np.complex128) * (2.0 + 0j)
    clues = np.array([0, 2], dtype=np.int64)
    config_groups = {
        (10.0, "s"): {
            "clues_set": {0, 2},
            "targets": [
                {
                    "clues": clues,
                    "tgt_vals": np.array([0.1, 0.3]),
                    "target_type": "R",
                    "weight": 1.0,
                }
            ],
        }
    }
    cfgs = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T)
    assert len(cfgs) == 1
    c0 = cfgs[0]
    assert c0["angle"] == 10.0 and c0["pol"] == "s" and c0["is_s_pol"] is True
    np.testing.assert_array_equal(c0["all_clues"], np.array([0, 2], dtype=np.int64))
    assert c0["wls_config"].shape == (2,) and c0["n_sub_config"].shape == (2,)
    assert c0["n_layers_T_config"].shape == (2, 2)
    optim_oblique_attach_local_positions(cfgs)
    lp = c0["targets"][0]["local_positions"]
    np.testing.assert_array_equal(lp, np.array([0, 1], dtype=np.int64))


def test_optim_oblique_group_skips_empty_band():
    wls = np.array([400.0, 500.0], dtype=np.float64)
    t = SimpleNamespace(
        lmin=600.0,
        lmax=700.0,
        angle=0.0,
        pol="s",
        tmin=0.0,
        tmax=1.0,
        target_type="R",
        w=1.0,
    )
    assert optim_oblique_group_targets_on_wavelengths(wls, [t]) == {}


def test_optim_backside_flags_defaults():
    hbs, hbc, sb = optim_backside_flags_from_cfg({})
    assert hbs is False and hbc is False and sb == []


def test_optim_backside_flags_stack_requires_coat_flag():
    cfg = {"back": True, "use_back_coat": False, "stack_back": [object()]}
    hbs, hbc, sb = optim_backside_flags_from_cfg(cfg)
    assert hbc is True and hbs is False and len(sb) == 1


def test_optim_backside_flags_none_stack_back_normalized():
    cfg = {"use_back_coat": True, "stack_back": None}
    hbs, hbc, sb = optim_backside_flags_from_cfg(cfg)
    assert sb == [] and hbs is False


def test_optim_backside_flags_coated_stack():
    cfg = {"use_back_coat": True, "stack_back": [1, 2], "back": True}
    hbs, hbc, sb = optim_backside_flags_from_cfg(cfg)
    assert hbs is True and hbc is True and sb == [1, 2]


def test_optim_post_optim_time_budget_seconds_piecewise():
    assert optim_post_optim_time_budget_seconds(0) == pytest.approx(30.0)
    assert optim_post_optim_time_budget_seconds(10) == pytest.approx(30.0)
    assert optim_post_optim_time_budget_seconds(11) == pytest.approx(
        30.0 + 1.0 * (180.0 - 30.0) / (26 - 10)
    )
    assert optim_post_optim_time_budget_seconds(26) == pytest.approx(180.0)
    assert optim_post_optim_time_budget_seconds(40) == pytest.approx(600.0)
    assert optim_post_optim_time_budget_seconds(-3) == pytest.approx(30.0)


def test_optim_calc_oblique_selected_front_only_branch():
    calls = {"front": 0, "backside": 0, "full": 0}

    def _full(*args, **kwargs):
        calls["full"] += 1
        return ("Rfull", "Tfull")

    def _backside(*args, **kwargs):
        calls["backside"] += 1
        return ("Rback", "Tback")

    def _front(*args, **kwargs):
        calls["front"] += 1
        return ("Rfront", "Tfront")

    out = optim_calc_oblique_selected(
        np.array([500.0], dtype=np.float64),
        np.ones((1, 1), dtype=np.complex128),
        np.array([100.0], dtype=np.float64),
        np.array([1.52 + 0j], dtype=np.complex128),
        30.0,
        "s",
        has_back_calc=False,
        has_back_stack=True,
        d_back=np.array([10.0], dtype=np.float64),
        n_back_T=np.ones((1, 1), dtype=np.complex128),
        calc_spectrum_full_oblique_exact=_full,
        calc_spectrum_oblique_backside_vectorized=_backside,
        calc_spectrum_oblique_vectorized=_front,
    )
    assert out == ("Rfront", "Tfront")
    assert calls == {"front": 1, "backside": 0, "full": 0}


def test_optim_bounds_thickness_local():
    ep = np.array([100.0, 50.0])
    b = optim_bounds_thickness_local(ep, np.array([0], dtype=np.int64), 10.0)
    assert b.shape == (1, 2)
    assert b[0, 0] == pytest.approx(90.0) and b[0, 1] == pytest.approx(110.0)
    b2 = optim_bounds_thickness_local(np.array([5.0]), np.array([0]), 10.0)
    assert b2[0, 0] == pytest.approx(0.0)


def test_optim_bounds_thickness_healing():
    class _M:
        def get_nk(self, w):
            return np.array([2.0 + 0j], dtype=np.complex128)

    stack = [SimpleNamespace(mat="H")]
    mats = {"H": _M()}
    ep = np.array([100.0])
    b = optim_bounds_thickness_healing(
        ep, np.array([0], dtype=np.int64), stack, mats, 500.0
    )
    assert b[0, 0] == pytest.approx(75.0) and b[0, 1] == pytest.approx(125.0)


def test_optim_bounds_thickness_global():
    stack = [SimpleNamespace(mat="H")]
    mats = {"H": SimpleNamespace(n4=2.0)}
    ep = np.array([100.0])
    b = optim_bounds_thickness_global(
        ep, np.array([0], dtype=np.int64), stack, mats, 500.0
    )
    assert b[0, 0] == pytest.approx(0.0)
    assert b[0, 1] == pytest.approx(120.0)


def test_optim_var_indices_from_stack():
    stack = [
        SimpleNamespace(var=True),
        SimpleNamespace(var=False),
        SimpleNamespace(var=True),
    ]
    idx = optim_var_indices_from_stack(stack)
    np.testing.assert_array_equal(idx, np.array([0, 2], dtype=np.int64))


def test_optim_rmse_display_string_and_valid():
    assert optim_rmse_is_valid_for_log(0.0) is True
    assert optim_rmse_is_valid_for_log(None) is False
    assert optim_rmse_is_valid_for_log(float("nan")) is False
    assert optim_rmse_display_string(0.123456789) == "0.123457"
    assert optim_rmse_display_string(None) == "N/A"


def test_optim_qwot_values_from_ep_stack():
    stack = [SimpleNamespace(mat="H")]
    mats = {"H": SimpleNamespace(n4=2.0)}
    ep = np.array([100.0], dtype=np.float64)
    qw = optim_qwot_values_from_ep_stack(ep, stack, mats, 500.0)
    assert len(qw) == 1
    assert qw[0] == pytest.approx(4.0 * 2.0 * 100.0 / 500.0)


def test_optim_qwot_values_dict_material_and_l0_zero():
    stack = [SimpleNamespace(mat="H")]
    mats = {"H": {"n4": 1.52}}
    ep = np.array([50.0])
    assert optim_qwot_values_from_ep_stack(ep, stack, mats, 0.0) == [0.0]


def test_optim_display_wavelength_grid_defaults():
    cfg = {}
    wls = optim_display_wavelength_grid(cfg, float_dtype=np.float64)
    assert wls.size == 300
    assert wls.dtype == np.float64
    # marge 20 % : min ~ 380 - 76 = 304, plancher 200 -> 304 ; max 780 + 156
    assert float(wls[0]) == pytest.approx(304.0)
    assert float(wls[-1]) == pytest.approx(936.0)


def test_optim_display_wavelength_grid_respects_uv_floor():
    cfg = {"wls_min": 350.0, "wls_max": 800.0}
    wls = optim_display_wavelength_grid(cfg, float_dtype=np.float64)
    assert float(wls[0]) == pytest.approx(max(200.0, 350.0 - 70.0))
    assert float(wls[-1]) == pytest.approx(800.0 + 160.0)


def test_optim_display_wavelength_grid_custom_n_points():
    wls = optim_display_wavelength_grid({"wls_min": 400.0, "wls_max": 800.0}, n_points=50)
    assert wls.size == 50


def test_optim_prepare_stack_nk_back_without_back_stack():
    wls = np.array([400.0, 500.0], dtype=np.float64)
    mats = {
        "substrate": _mat_const(1.52 + 0j),
        "H": _mat_const(2.0 + 0j),
    }
    stack = [SimpleNamespace(mat="H")]
    ep_back = np.array([], dtype=np.float64)
    mats_nk, n_sub, n_layers_T, n_back_T, d_back = optim_prepare_stack_nk_back(
        mats,
        stack,
        wls,
        stack_back=[],
        ep_back=ep_back,
        has_back_stack=False,
        complex_dtype=np.complex128,
        float_dtype=np.float64,
    )
    assert set(mats_nk.keys()) == {"substrate", "H"}
    assert n_sub.shape == (2,)
    assert n_layers_T.shape == (2, 1)
    assert n_back_T.shape == (2, 0)
    assert d_back.size == 0


def test_optim_prepare_stack_nk_back_with_back_stack():
    wls = np.array([400.0, 500.0], dtype=np.float64)
    mats = {
        "substrate": _mat_const(1.52 + 0j),
        "H": _mat_const(2.0 + 0j),
        "L": _mat_const(1.45 + 0j),
    }
    stack = [SimpleNamespace(mat="H")]
    stack_back = [SimpleNamespace(mat="L")]
    ep_back = np.array([50.0], dtype=np.float64)
    _mnk, _ns, n_layers_T, n_back_T, d_back = optim_prepare_stack_nk_back(
        mats,
        stack,
        wls,
        stack_back=stack_back,
        ep_back=ep_back,
        has_back_stack=True,
        complex_dtype=np.complex128,
        float_dtype=np.float64,
    )
    assert n_layers_T.shape == (2, 1)
    assert n_back_T.shape == (2, 1)
    assert d_back.shape == (1,)
    assert float(d_back[0]) == pytest.approx(50.0)
