"""INDEX-SPLINE helpers that no test named keep their contract (plan S3.7, third batch).

`certus_index_spline_io` writes the result of a run to disk (what a later session reads back), `certus_corridor_bootstrap`
resamples residuals and runs one replicate of the bootstrap that gives the thickness interval, and the two logging modules
(`certus_corridor_logger`, `spline_corridor_log_coaching`) tell the user, in the log panel, what to do about a corridor that came
out capped, empty, flat or brittle. Each piece of advice is a branch on a number (a span against `max_span_nm`, a yield
under one half, a ratio above 3): a branch that moves is advice that changes, so each threshold is pinned on both sides.

Every assertion was read from the code, then broken once on purpose (the planted errors are listed in the commit message).
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import numpy as np
import pytest

LOGGER = "CERTUS"
PREFIX = "INDEX_SPLINE [CORRIDORS d]"


def _messages(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


# =============================================================================
# certus_index_spline_io


def _result(**extra) -> dict:
    base = {
        "mse": 1e-4,
        "rmse": 0.01,
        "d_nm": 812.5,
        "n_seg": 3,
        "sigma_knots": np.array([0.001, 0.0015, 0.002]),
        "nfev_pglobal": 120,
        "nit_polish": 45,
        "x": np.array([1.0, 2.0]),
        "lam_nm": np.array([400.0, 500.0]),
        "n_lam": np.array([1.5, 1.6]),
        "k_lam": np.array([0.0, 0.001]),
        "t_theo": np.array([0.9, 0.8]),
        "r_theo": np.array([0.05, 0.06]),
    }
    base.update(extra)
    return base


def test_an_exported_result_is_plain_json_and_carries_the_headline_numbers():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    out = export_spline_result_jsonable(_result(n_mono_band_nm=(400, 700), x_encoding="ln"))
    json.dumps(out)  # no ndarray, no numpy scalar left
    assert (out["mse"], out["rmse"], out["d_nm"], out["n_seg"]) == (1e-4, 0.01, 812.5, 3)
    assert out["K"] == 3
    assert (out["nfev_pglobal"], out["nit_polish"]) == (120, 45)
    assert out["n_mono_band_nm"] == [400.0, 700.0]
    assert out["x_encoding"] == "ln"
    assert (out["t_is_ratio"], out["adaptive_mesh"], out["continuous_model"]) == (False, False, False)


def test_the_arrays_are_lists_of_floats_and_can_be_left_out():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    full = export_spline_result_jsonable(_result())
    assert full["lam_nm"] == [400.0, 500.0]
    assert full["sigma_knots"] == [0.001, 0.0015, 0.002]
    assert full["x"] == [1.0, 2.0]
    slim = export_spline_result_jsonable(_result(), full_arrays=False)
    assert not {"x", "sigma_knots", "lam_nm", "n_lam", "k_lam", "t_theo", "r_theo"} & set(slim)
    assert slim["K"] == 3  # the count survives


def test_a_missing_headline_number_exports_as_zero_and_a_missing_band_as_none():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    out = export_spline_result_jsonable({})
    assert (out["mse"], out["rmse"], out["d_nm"], out["n_seg"], out["K"]) == (0.0, 0.0, 0.0, 0, 0)
    assert out["n_mono_band_nm"] is None


def test_an_optional_array_is_written_only_when_the_result_has_it():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    absent = export_spline_result_jsonable(_result())
    assert not {"ln_k_lam", "nl_lam_nm", "n_lam_nl", "k_lam_nl", "n_nodes_physical"} & set(absent)
    present = export_spline_result_jsonable(
        _result(ln_k_lam=[0.1], nl_lam_nm=[500.0], n_lam_nl=[1.55], k_lam_nl=[0.002], n_nodes_physical=[1.5, 1.6])
    )
    assert present["ln_k_lam"] == [0.1]
    assert present["n_nodes_physical"] == [1.5, 1.6]


def test_a_scalar_that_is_not_finite_is_not_written():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    out = export_spline_result_jsonable(
        _result(spectral_rmse_segments=0.02, spectral_rmse_best_value=float("nan"), nl_alpha_opt=float("inf"), d_nm_nl=812.0)
    )
    assert out["spectral_rmse_segments"] == 0.02
    assert "spectral_rmse_best_value" not in out
    assert "nl_alpha_opt" not in out
    assert out["d_nm_nl"] == 812.0
    assert "d_nm_nl" not in export_spline_result_jsonable(_result(d_nm_nl="not a number"))  # unreadable: dropped, not raised


def test_the_nonlinear_second_pass_fields_are_written_with_their_types():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    out = export_spline_result_jsonable(
        _result(
            nl_profile_mode="free",
            nl_optim_ok=1,
            nl_second_pass_applied=0,
            nl_alpha_grid_n="9",
            nl_alpha_grid_step=0.25,
            nl_alpha_budget_mode="fast",
            nl_second_pass_maxfun="1500",
            pwl_baseline_mse=3e-4,
            nk_profile_interp="smooth",
        )
    )
    assert out["nl_profile_mode"] == "free"
    assert out["nl_optim_ok"] is True
    assert out["nl_second_pass_applied"] is False
    assert out["nl_alpha_grid_n"] == 9
    assert out["nl_alpha_grid_step"] == 0.25
    assert out["nl_alpha_budget_mode"] == "fast"
    assert out["nl_second_pass_maxfun"] == 1500
    assert out["pwl_baseline_mse"] == 3e-4
    assert out["nk_profile_interp"] == "smooth"


def test_the_stages_of_an_automatic_knot_search_are_embedded_once_and_their_indices_are_kept():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    stage_a = _result(sigma_knots=np.array([0.001, 0.002]))
    stage_b = _result(sigma_knots=np.array([0.001, 0.0015, 0.002, 0.0025]), auto_knot_stages=[{"sigma_knots": [1.0]}])
    parent = _result(auto_knot_stages=[stage_a, stage_b], auto_knot_best_stage_index=1, auto_knots_K_best=4)
    out = export_spline_result_jsonable(parent)
    assert (out["auto_knot_best_stage_index"], out["auto_knots_K_best"], out["auto_knots_K_last"]) == (1, 4, 4)
    assert [s["K"] for s in out["stages"]] == [2, 4]
    assert all("stages" not in s for s in out["stages"])  # no nesting beyond one level
    assert "stages" not in export_spline_result_jsonable(parent, embed_child_stages=False)
    json.dumps(out)


def test_the_smart_mesh_description_is_copied_as_given():
    from certus.spline.certus_index_spline_io import export_spline_result_jsonable

    assert export_spline_result_jsonable(_result(smart_mesh={"n_knots": 7}))["smart_mesh"] == {"n_knots": 7}
    assert "smart_mesh" not in export_spline_result_jsonable(_result(smart_mesh={}))


# =============================================================================
# certus_corridor_bootstrap


def test_a_block_of_one_is_a_plain_resample_with_replacement():
    from certus.spline.certus_corridor_bootstrap import _resample_residuals_block

    e = np.arange(10, dtype=np.float64)
    out = _resample_residuals_block(e, 1, np.random.default_rng(3))
    assert out.shape == (10,)
    assert set(out.tolist()) <= set(e.tolist())
    assert len(set(out.tolist())) < 10  # with replacement: this seed repeats a value


def test_a_longer_block_keeps_consecutive_residuals_together_and_wraps_around():
    """With e = 0..n-1 the value IS the index: inside a block each step is +1 modulo n."""
    from certus.spline.certus_corridor_bootstrap import _resample_residuals_block

    n, block = 12, 4
    out = _resample_residuals_block(np.arange(n, dtype=np.float64), block, np.random.default_rng(7))
    assert out.shape == (n,)
    for start in range(0, n, block):
        piece = out[start : start + block]
        assert [(int(piece[i + 1]) - int(piece[i])) % n for i in range(len(piece) - 1)] == [1] * (len(piece) - 1)


def test_the_resample_is_truncated_to_the_length_of_the_residuals_and_the_block_is_capped_at_it():
    from certus.spline.certus_corridor_bootstrap import _resample_residuals_block

    e = np.arange(10, dtype=np.float64)
    assert _resample_residuals_block(e, 4, np.random.default_rng(1)).shape == (10,)  # 3 blocks of 4 = 12, cut to 10
    capped = _resample_residuals_block(e, 99, np.random.default_rng(1))
    assert capped.shape == (10,)
    assert sorted(capped.tolist()) == e.tolist()  # one block of 10: a rotation of the residuals


def test_an_empty_residual_vector_gives_an_empty_vector():
    from certus.spline.certus_corridor_bootstrap import _resample_residuals_block

    out = _resample_residuals_block(np.array([], dtype=np.float64), 3, np.random.default_rng(0))
    assert out.shape == (0,)
    assert out.dtype == np.float64


def test_the_resample_is_reproducible_for_a_seed_and_never_touches_its_input():
    from certus.spline.certus_corridor_bootstrap import _resample_residuals_block

    e = np.linspace(-1.0, 1.0, 20)
    before = e.copy()
    a = _resample_residuals_block(e, 5, np.random.default_rng(42))
    b = _resample_residuals_block(e, 5, np.random.default_rng(42))
    assert a.tolist() == b.tolist()
    assert e.tolist() == before.tolist()


LAM = np.linspace(400.0, 700.0, 4)


def _profiled(**over) -> dict:
    extra = {
        "profile_d_interval_nm": (810.0, 815.0),
        "profile_d_values_nm": [810.0, 812.0, 815.0],
        "corridor_n_lo": np.full(4, 1.50),
        "corridor_n_hi": np.full(4, 1.60),
        "corridor_k_lo": np.zeros(4),
        "corridor_k_hi": np.full(4, 0.01),
    }
    extra.update(over)
    return extra


@pytest.fixture
def replicate(monkeypatch):
    """`_bootstrap_single_replicate` with the profiling and the quick refit replaced by recorders."""
    import certus.spline.certus_corridor_bootstrap as boot
    import certus.spline.spline_profile_corridors as profiling

    calls = {"profile": [], "refit": []}
    state = {"extra": _profiled(), "refit": {"refit": True}, "raise": None}

    def fake_profile(cfg, base, *, pconf, log_coaching):
        calls["profile"].append((cfg, base, pconf, log_coaching))
        if state["raise"] is not None:
            raise state["raise"]
        return state["extra"]

    def fake_refit(cfg, base, maxfun):
        calls["refit"].append((cfg, base, maxfun))
        return state["refit"]

    monkeypatch.setattr(profiling, "compute_profiled_corridors_by_d", fake_profile)
    monkeypatch.setattr(boot, "quick_pwlnk_refit_result_dict", fake_refit)

    def run(qref=0, **kw):
        return boot._bootstrap_single_replicate("cfg", {"base": 1}, pconf="pconf", qref=qref, lam=kw.pop("lam", LAM), **kw)

    return SimpleNamespace(run=run, calls=calls, state=state)


def test_a_good_replicate_returns_the_interval_and_the_four_envelopes(replicate):
    out = replicate.run()
    assert out["status"] == "ok"
    assert (out["dlo"], out["dhi"], out["nvalid"]) == (810.0, 815.0, 3)
    assert out["n_lo"].tolist() == [1.5] * 4
    assert out["n_hi"].tolist() == [1.6] * 4
    assert out["k_hi"].tolist() == [0.01] * 4
    cfg, base, pconf, log_coaching = replicate.calls["profile"][0]
    assert (cfg, base, pconf, log_coaching) == ("cfg", {"base": 1}, "pconf", False)  # the coaching log stays off in a replicate


def test_the_quick_refit_runs_only_when_asked_and_its_result_becomes_the_base(replicate):
    replicate.run(qref=0)
    assert replicate.calls["refit"] == []
    assert replicate.calls["profile"][-1][1] == {"base": 1}
    replicate.run(qref=2500)
    assert replicate.calls["refit"] == [("cfg", {"base": 1}, 2500)]
    assert replicate.calls["profile"][-1][1] == {"refit": True}


def test_a_refit_that_gives_nothing_leaves_the_base_result_in_place(replicate):
    replicate.state["refit"] = None
    replicate.run(qref=500)
    assert replicate.calls["profile"][-1][1] == {"base": 1}


def test_a_numerical_failure_is_a_status_not_an_error_and_is_logged_with_its_run_number(replicate, caplog):
    replicate.state["raise"] = RuntimeError("singular")
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        failed = replicate.run(log_run_1based=7)
        anonymous = replicate.run()
    assert failed == {"status": "exception", "nvalid": 0}
    assert anonymous == {"status": "exception", "nvalid": 0}
    text = _messages(caplog)
    assert "[BOOT] failed run=7" in text
    assert "[BOOT] internal run failed" in text


@pytest.mark.parametrize("interval", [None, (810.0,), (1.0, 2.0, 3.0), 812.0])
def test_an_interval_that_is_not_a_pair_is_a_bad_interval_but_still_counts_its_valid_points(replicate, interval):
    replicate.state["extra"] = _profiled(profile_d_interval_nm=interval)
    out = replicate.run()
    assert out["status"] == "bad_interval"
    assert out["nvalid"] == 3


def test_an_interval_that_is_not_made_of_numbers_is_a_bad_interval(replicate):
    replicate.state["extra"] = _profiled(profile_d_interval_nm=(None, 815.0))
    assert replicate.run()["status"] == "bad_interval"


def test_an_envelope_that_does_not_have_one_value_per_wavelength_is_a_shape_error(replicate):
    replicate.state["extra"] = _profiled(corridor_k_hi=np.full(3, 0.01))
    assert replicate.run()["status"] == "shape"
    replicate.state["extra"] = _profiled(corridor_n_lo=[])
    assert replicate.run()["status"] == "shape"


def test_the_wavelength_grid_may_be_given_as_a_nested_list(replicate):
    assert replicate.run(lam=[[400.0, 500.0, 600.0, 700.0]])["status"] == "ok"


def test_the_pool_entry_unpacks_its_payload_and_numbers_the_run_from_one(replicate, caplog):
    import certus.spline.certus_corridor_bootstrap as boot

    replicate.state["raise"] = RuntimeError("x")
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        index, result = boot._bootstrap_pool_entry((4, "cfg", {"base": 1}, "pconf", 0, LAM))
    assert index == 4
    assert result["status"] == "exception"
    assert "[BOOT] failed run=5" in _messages(caplog)  # the fifth run: the index counts from zero, the log from one
    replicate.state["raise"] = None
    assert boot._bootstrap_pool_entry((0, "cfg", {"base": 1}, "pconf", 100, LAM))[1]["status"] == "ok"
    assert replicate.calls["refit"][-1][2] == 100


# =============================================================================
# spline_corridor_log_coaching: each piece of advice appears on its side of its threshold


def _coach(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    import certus.spline.spline_corridor_log_coaching as coaching

    return coaching


def _pconf(**over):
    return SimpleNamespace(**{"max_span_nm": 10.0, "min_valid_points": 3, **over})


def _outcome(coaching, **over):
    args = {
        "pconf": _pconf(),
        "use_lr": False,
        "use_abs_delta": False,
        "d0": 100.0,
        "d_arr": np.linspace(97.0, 103.0, 6),
        "rm_arr": np.linspace(0.010, 0.012, 6),
        "rmse_opt": 0.010,
        "rmse_thresh": 0.020,
        "polish_maxfun": 500,
        "base_result": {},
    }
    args.update(over)
    coaching._log_coaching_corridor_outcome(**args)


def test_a_corridor_that_hits_the_span_on_both_sides_is_called_capped(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, d_arr=np.linspace(90.0, 110.0, 21))
    assert "THICKNESS CORRIDOR CAPPED" in _messages(caplog)
    assert "THICKNESS SENSITIVE" not in _messages(caplog)


def test_reaching_the_rmse_threshold_is_not_being_capped(caplog):
    """A corridor limited by the threshold, not by the span: 85 % of the threshold is the line."""
    coaching = _coach(caplog)
    _outcome(coaching, d_arr=np.linspace(90.0, 110.0, 21), rm_arr=np.full(21, 0.0170), rmse_thresh=0.020)  # exactly 85 %
    assert "CAPPED" not in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.linspace(90.0, 110.0, 21), rm_arr=np.full(21, 0.0169), rmse_thresh=0.020)  # just under
    assert "CAPPED" in _messages(caplog)


def test_the_span_has_a_tolerance_of_two_percent_of_it_and_at_least_a_twentieth_of_a_nanometre(caplog):
    coaching = _coach(caplog)
    # max_span 10 -> eps = 0.2 nm: a side that falls 0.2 short is still on the limit, 0.3 short is not
    _outcome(coaching, d_arr=np.array([89.8, 100.0, 110.2, 95.0, 105.0]))
    assert "CAPPED" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.array([90.3, 100.0, 109.7, 95.0, 105.0]))
    assert "CAPPED" not in _messages(caplog)


def test_an_interval_limited_by_the_threshold_on_both_sides_is_called_sensitive(caplog):
    coaching = _coach(caplog)
    _outcome(coaching)
    text = _messages(caplog)
    assert "THICKNESS SENSITIVE" in text
    assert "span ~ 6 nm over 6 evaluated points" in text


def test_five_points_are_needed_to_call_a_corridor_sensitive(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, d_arr=np.linspace(98.0, 102.0, 4), rm_arr=np.linspace(0.010, 0.012, 4))
    assert "SENSITIVE" not in _messages(caplog)


def test_one_or_two_valid_points_are_called_few_and_three_or_four_highly_constrained(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, d_arr=np.array([99.0, 100.0]), rm_arr=np.array([0.010, 0.011]))
    assert "FEW VALID POINTS (2)" in _messages(caplog)
    assert "HIGHLY CONSTRAINED" not in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.linspace(99.0, 101.0, 3), rm_arr=np.linspace(0.010, 0.011, 3))
    assert "HIGHLY CONSTRAINED (Only 3 valid points)" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.linspace(99.0, 101.0, 4), rm_arr=np.linspace(0.010, 0.011, 4))  # min_valid_points + 1 = 4
    assert "HIGHLY CONSTRAINED (Only 4 valid points)" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.linspace(99.0, 101.0, 5), rm_arr=np.linspace(0.010, 0.011, 5))  # one more than that
    assert "HIGHLY CONSTRAINED" not in _messages(caplog)


def test_a_likelihood_ratio_corridor_gets_none_of_the_point_count_advice(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, use_lr=True, d_arr=np.array([100.0]), rm_arr=np.array([0.010]))
    text = _messages(caplog)
    assert "FEW VALID" not in text
    assert "HIGHLY CONSTRAINED" not in text
    assert "THICKNESS SENSITIVE" not in text


def test_forty_one_admissible_points_across_the_whole_range_are_a_degenerate_valley(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, d_arr=np.linspace(90.0, 110.0, 41), rm_arr=np.linspace(0.010, 0.013, 41))
    assert "WIDE DEGENERATIVE VALLEY" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, d_arr=np.linspace(90.0, 110.0, 40), rm_arr=np.linspace(0.010, 0.013, 40))
    assert "WIDE DEGENERATIVE VALLEY" not in _messages(caplog)  # forty is not more than forty


def test_a_cost_that_does_not_move_with_the_thickness_is_flat(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, rm_arr=np.full(6, 0.0105))
    assert "FLAT COST FUNCTION" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, rm_arr=np.linspace(0.0105, 0.0105 + 2e-6, 6))
    assert "FLAT COST FUNCTION" not in _messages(caplog)  # 2e-6 of spread is not flat


def test_a_dictionary_rmse_far_from_the_solvers_is_warned_unless_the_threshold_is_absolute(caplog):
    coaching = _coach(caplog)
    _outcome(coaching, base_result={"spectral_rmse_segments": 0.010, "rmse": 0.020})
    assert "RMSE DEVIATION WARNING" in _messages(caplog)
    assert "|Delta|/solver ~ 1.00" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, base_result={"spectral_rmse_segments": 0.010, "rmse": 0.0139})  # 39 %
    assert "DEVIATION" not in _messages(caplog)
    caplog.clear()
    _outcome(coaching, base_result={"spectral_rmse_segments": 0.010, "rmse": 0.0141})  # 41 %
    assert "DEVIATION" in _messages(caplog)
    caplog.clear()
    _outcome(coaching, use_abs_delta=True, base_result={"spectral_rmse_segments": 0.010, "rmse": 0.020})
    assert "DEVIATION" not in _messages(caplog)


def test_the_outcome_analysis_is_framed_and_ends_with_the_note_about_the_ribbons(caplog):
    coaching = _coach(caplog)
    _outcome(coaching)
    lines = [r.getMessage() for r in caplog.records]
    assert "Smart Coaching: Result Analysis & Feedback" in lines[0]
    assert "NOTE: The n(lambda) and k(lambda) ribbons" in lines[-2]
    assert set(lines[-1].removeprefix(PREFIX + " ")) == {"━"}


@pytest.mark.parametrize(
    ("reason", "advice"),
    [("rmse_meta_invalid", "INVALID METRIC"), ("centre_fail", "CENTER DENIED"), ("too_few_valid", "TOO FEW VALID POINTS")],
)
def test_each_failure_reason_has_its_own_advice(caplog, reason, advice):
    coaching = _coach(caplog)
    coaching._log_coaching_corridor_failure(reason=reason, pconf=_pconf(), use_lr=False, rmse_opt=0.01, rmse_thresh=0.02, d0=812.34567)
    text = _messages(caplog)
    assert f"Failure Analysis ({reason})" in text
    assert advice in text
    assert sum(tag in text for tag in ("INVALID METRIC", "CENTER DENIED", "TOO FEW VALID POINTS")) == 1


def test_the_too_few_valid_advice_quotes_the_optimal_thickness_to_four_decimals(caplog):
    coaching = _coach(caplog)
    coaching._log_coaching_corridor_failure(reason="too_few_valid", pconf=_pconf(), use_lr=False, rmse_opt=0.01, rmse_thresh=0.02, d0=812.34567)
    assert "d_opt ~ 812.3457 nm" in _messages(caplog)


def test_an_unknown_failure_reason_gets_the_frame_and_no_advice(caplog):
    coaching = _coach(caplog)
    coaching._log_coaching_corridor_failure(reason="other", pconf=_pconf(), use_lr=False, rmse_opt=0.01, rmse_thresh=0.02, d0=1.0)
    assert len(caplog.records) == 2


def _bootstrap(coaching, **over):
    args = {"B": 100, "n_ok": 90, "p": 0.95, "mode": "x", "qref": 4000, "d_lo_q": 810.0, "d_hi_q": 815.0}
    args.update(over)
    coaching._log_coaching_bootstrap_outcome(**args)


def test_a_bootstrap_with_less_than_half_its_replicates_is_called_low_yield(caplog):
    coaching = _coach(caplog)
    _bootstrap(coaching, n_ok=49)
    assert "LOW BOOTSTRAP YIELD (49% OK)" in _messages(caplog)
    caplog.clear()
    _bootstrap(coaching, n_ok=50)
    assert "LOW BOOTSTRAP YIELD" not in _messages(caplog)


def test_a_bootstrap_with_no_replicate_asked_does_not_divide_by_zero(caplog):
    coaching = _coach(caplog)
    _bootstrap(coaching, B=0, n_ok=0)
    assert "LOW BOOTSTRAP YIELD (0% OK)" in _messages(caplog)


def test_a_quick_refit_under_two_thousand_evaluations_is_called_shallow_and_zero_means_none(caplog):
    coaching = _coach(caplog)
    _bootstrap(coaching, qref=1999)
    assert "SHALLOW REFIT (maxfun=1999)" in _messages(caplog)
    for qref in (2000, 0, -5):
        caplog.clear()
        _bootstrap(coaching, qref=qref)
        assert "SHALLOW REFIT" not in _messages(caplog)


def test_the_bootstrap_interval_is_quoted_with_its_probability_and_span(caplog):
    coaching = _coach(caplog)
    _bootstrap(coaching, p=0.9, d_lo_q=810.12345, d_hi_q=815.5)
    text = _messages(caplog)
    assert "DISPERSION RESULT (p=0.90): [810.1235, 815.5000] nm (span ~ 5.38 nm)" in text
    caplog.clear()
    _bootstrap(coaching, d_lo_q=812.0, d_hi_q=812.0)
    assert "DISPERSION RESULT" not in _messages(caplog)
    caplog.clear()
    _bootstrap(coaching, d_lo_q=float("nan"), d_hi_q=815.0)
    assert "DISPERSION RESULT" not in _messages(caplog)


def _regularization(coaching, **over):
    weights = np.array([0.1, 1.0, 10.0])
    args = {
        "weights": weights,
        "d_lo": np.array([99.0, 99.0, 99.0]),
        "d_hi": np.array([101.0, 101.0, 101.0]),
        "nw": np.array([0.01, 0.01, 0.01]),
        "kw": np.array([0.001, 0.001, 0.001]),
    }
    args.update(over)
    coaching._log_coaching_reg_sensitivity_outcome(**args)


def test_a_flat_regularization_scan_has_no_advice(caplog):
    coaching = _coach(caplog)
    _regularization(coaching)
    assert len(caplog.records) == 2  # the frame only


def test_a_single_weight_is_not_a_scan_and_logs_only_its_title(caplog):
    coaching = _coach(caplog)
    _regularization(coaching, weights=np.array([1.0]))
    assert [r.getMessage() for r in caplog.records] == [PREFIX + " ━━━ Smart Coaching: Regularization Profile ━━━"]


def test_a_thickness_interval_that_changes_threefold_with_the_regularization_is_flagged(caplog):
    coaching = _coach(caplog)
    _regularization(coaching, d_hi=np.array([101.0, 101.0, 105.0]))  # widths 2, 2, 6: exactly 3
    assert "REGULARIZATION DEPENDENCE" not in _messages(caplog)
    caplog.clear()
    _regularization(coaching, d_hi=np.array([101.0, 101.0, 105.5]))  # widths 2, 2, 6.5
    assert "REGULARIZATION DEPENDENCE (Varies by ~3.25×)" in _messages(caplog)


def test_the_index_and_extinction_corridors_are_flagged_above_a_ratio_of_two_and_a_half(caplog):
    coaching = _coach(caplog)
    _regularization(coaching, nw=np.array([0.01, 0.01, 0.025]), kw=np.array([0.001, 0.001, 0.0025]))  # exactly 2.5
    assert "CORRIDOR DEPENDS" not in _messages(caplog)
    assert "EXTREMELY DEPENDENT" not in _messages(caplog)
    caplog.clear()
    _regularization(coaching, nw=np.array([0.01, 0.01, 0.03]), kw=np.array([0.001, 0.001, 0.004]))
    text = _messages(caplog)
    assert "n(lambda) CORRIDOR DEPENDS ON REGULARIZATION (Varies by ~3.00×)" in text
    assert "k(lambda) CORRIDOR EXTREMELY DEPENDENT ON REGULARIZATION (Varies by ~4.00×)" in text


def test_arrays_that_do_not_match_the_weights_are_ignored(caplog):
    coaching = _coach(caplog)
    _regularization(coaching, d_hi=np.array([101.0, 105.0]), nw=np.array([1.0, 9.0]), kw=np.array([1.0, 9.0]))
    assert len(caplog.records) == 2


def test_the_parameter_guide_names_every_setting_it_explains_and_is_framed(caplog):
    coaching = _coach(caplog)
    coaching.log_coaching_uncertainty_parameter_guide()
    lines = [r.getMessage() for r in caplog.records]
    assert "Parameter guide" in lines[0]
    assert set(lines[-1].removeprefix(PREFIX + " ")) == {"━"}
    text = "\n".join(lines)
    for topic in ("RMSE_ref + Delta", "alpha", "max_span_nm", "step_nm", "Refit budget", "Bootstrap", "REG-SENS", "n_starts"):
        assert topic in text
    assert len(lines) == 15


def test_the_empty_pipeline_reminder_points_at_the_three_diagnoses(caplog):
    coaching = _coach(caplog)
    coaching.log_coaching_corridor_pipeline_skip_empty()
    (record,) = caplog.records
    assert "[COACH] SKIP/EMPTY" in record.getMessage()
    for diagnosis in ("centre_fail", "too_few_valid", "rmse_meta_invalid"):
        assert diagnosis in record.getMessage()


# =============================================================================
# certus_corridor_logger


@pytest.mark.parametrize(
    ("wrapper", "kwargs"),
    [
        ("_log_coaching_corridor_outcome", dict(pconf="p", use_lr=True, use_abs_delta=True, d0=1.0, d_arr="d", rm_arr="r", rmse_opt=2.0, rmse_thresh=3.0, polish_maxfun=4, base_result={"a": 1})),
        ("_log_coaching_corridor_failure", dict(reason="centre_fail", pconf="p", use_lr=False, rmse_opt=2.0, rmse_thresh=3.0, d0=1.0)),
        ("_log_coaching_bootstrap_outcome", dict(B=10, n_ok=9, p=0.9, mode="m", qref=3, d_lo_q=1.0, d_hi_q=2.0)),
        ("_log_coaching_reg_sensitivity_outcome", dict(weights="w", d_lo="l", d_hi="h", nw="n", kw="k")),
    ],
)
def test_the_logger_wrappers_hand_every_argument_to_the_coaching_module(monkeypatch, wrapper, kwargs):
    import certus.spline.certus_corridor_logger as logger_module
    import certus.spline.spline_corridor_log_coaching as coaching

    seen = []
    monkeypatch.setattr(coaching, wrapper, lambda **kw: seen.append(kw))
    getattr(logger_module, wrapper)(**kwargs)
    assert seen == [kwargs]


@pytest.mark.parametrize("name", ["log_coaching_uncertainty_parameter_guide", "log_coaching_corridor_pipeline_skip_empty"])
def test_the_two_argument_free_wrappers_call_the_coaching_module(monkeypatch, name):
    import certus.spline.certus_corridor_logger as logger_module
    import certus.spline.spline_corridor_log_coaching as coaching

    called = []
    monkeypatch.setattr(coaching, name, lambda: called.append(name))
    getattr(logger_module, name)()
    assert called == [name]


def test_the_envelope_statistics_are_logged_with_the_count_of_reference_points_inside(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    logger_module._log_corridor_envelope_diagnostics(
        n_lo=np.array([1.5, 1.5, 1.5]),
        n_hi=np.array([1.6, 1.7, 1.8]),
        k_lo=np.array([0.01, 0.02, 0.03]),
        k_hi=np.array([0.02, 0.04, 0.09]),
        k_stack=np.zeros((1, 3)),
        corridor_ref_k_lam=np.array([0.015, 0.05, 0.05]),
        base_k_lam=np.zeros(3),
    )
    text = _messages(caplog)
    assert "n_span median=2.000000e-01 max=3.000000e-01" in text
    assert "k_span median=2.000000e-02 max=6.000000e-02" in text
    assert "log10(k)_span median=3.010300e-01 max=4.771213e-01" in text
    assert "k_ref_inside=2/3" in text
    assert "k-vs-ref" not in text  # one curve is not a family of curves


def test_without_a_reference_curve_the_base_curve_is_the_reference_and_without_finite_data_the_stats_say_so(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    nan = np.full(2, np.nan)
    logger_module._log_corridor_envelope_diagnostics(nan, nan, nan, nan, np.zeros((1, 2)), None, np.array([0.01, 0.02]))
    text = _messages(caplog)
    assert "n_span median=n/a max=n/a" in text
    assert "k_span median=n/a max=n/a" in text
    assert "k_ref_inside=0/0" in text


def test_a_family_of_accepted_curves_is_compared_with_the_reference_in_decades(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    ref = np.array([0.01, 0.01, 0.01])
    stack = np.array([[0.01, 0.01, 0.01], [0.1, 0.01, 0.001]])  # the second is one decade above, equal, one decade below
    logger_module._log_corridor_envelope_diagnostics(
        np.full(3, 1.5), np.full(3, 1.6), np.full(3, 0.001), np.full(3, 0.2), stack, ref, ref
    )
    text = _messages(caplog)
    assert "accepted_curves=2" in text
    assert "max|Δlog10(k)| across curves: median=5.000000e-01 max=1.000000e+00" in text


def test_the_start_line_warns_of_a_refit_budget_under_three_hundred_evaluations(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    cfg = SimpleNamespace(polish_maxfun=2500, nk_profile_interp="smooth", n_mono_band_nm=None, weight_t=1.0, weight_r=1.0, rmse_fit_lambda_nm=None)
    pconf = SimpleNamespace(
        step_nm=0.5, max_span_nm=10.0, max_steps_each_side=20, refine_boundary=True, refine_tol_nm=0.01, refine_max_iter=30, rmse_alpha=1.05, lr_conf_level=0.95
    )

    def start(maxfun_prof, use_lr=False, use_abs_delta=False):
        caplog.clear()
        logger_module._log_corridor_start_config(
            cfg, pconf, use_abs_delta, 5, 812.5, 0.01, "segments", "sub", False, 0.002, 0.012, maxfun_prof, False, use_lr, 3.84, 0.01, 0.02, None, None
        )
        return caplog.records

    records = start(299)
    assert [r.levelno for r in records if r.levelno >= logging.WARNING] == [logging.WARNING]
    assert "maxfun=299" in _messages(caplog)
    assert not [r for r in start(300) if r.levelno >= logging.WARNING]
    assert "L-BFGS-B budget per refit (profiling): maxfun=300 (main run polish=2500)" in _messages(caplog)


def test_the_start_line_says_which_threshold_rules_and_the_likelihood_mode_is_logged_only_when_used(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    cfg = SimpleNamespace(polish_maxfun=2500, nk_profile_interp="smooth", n_mono_band_nm=None, weight_t=1.0, weight_r=0.5, rmse_fit_lambda_nm=None)
    pconf = SimpleNamespace(
        step_nm=0.5, max_span_nm=10.0, max_steps_each_side=20, refine_boundary=True, refine_tol_nm=0.01, refine_max_iter=30, rmse_alpha=1.05, lr_conf_level=0.95
    )

    def start(use_abs_delta, use_lr):
        caplog.clear()
        logger_module._log_corridor_start_config(
            cfg, pconf, use_abs_delta, 5, 812.5, 0.01, "segments", "sub", False, 0.002, 0.012, 2500, False, use_lr, 3.84, 0.01, 0.02, None, None
        )
        return _messages(caplog)

    relative = start(False, False)
    assert "alpha×RMSE threshold (alpha=1.050 -> 0.01200000)" in relative
    assert "Mode LR" not in relative
    absolute = start(True, True)
    assert "absolute threshold RMSE <= 0.01000000 + Delta=0.002000 -> 0.01200000" in absolute
    assert "Mode LR | conf=0.9500 -> Deltaχ²=3.840000 | sigma_T=0.01 sigma_R=0.02 (constants)" in absolute


def test_the_geometry_log_lists_each_knot_with_its_wavelength_and_names_the_seed_variant(caplog):
    import certus.spline.certus_corridor_logger as logger_module

    caplog.set_level(logging.INFO, logger=LOGGER)
    diag = {"x_encoding": "ln", "sigma_knots_n_key_present": True, "remeshed_n_sigma_n_to_sigma_L": False, "sigma_grids_coincide": True, "sigma_atol_nm_inv": 1e-9}

    def geometry(use_abs_delta):
        caplog.clear()
        logger_module._log_corridor_base_geometry(
            sk=np.array([0.002, 0.001]),
            n_phys=np.array([1.5, 1.6]),
            L_nodes=np.array([-5.0, -4.0]),
            d0=812.5,
            sk_n_stored=np.array([0.002, 0.001]),
            diag=diag,
            rmse_ref_pipeline=0.010,
            rmse_seed_no_refit=0.013,
            mse_seed_no_refit=1.69e-4,
            use_abs_delta=use_abs_delta,
        )
        return _messages(caplog)

    clipped = geometry(False)
    assert "x_encoding=ln" in clipped
    assert "sigma_L (nm⁻¹) K=2" in clipped
    assert "sigma_n (nm⁻¹) K=2" in clipped
    assert "knot  1/2  sigma=2.000000e-03 nm⁻¹  lambda~500.00 nm  n=1.500000  ln_k=-5.0000000" in clipped
    assert "knot  2/2  sigma=1.000000e-03 nm⁻¹  lambda~1000.00 nm" in clipped
    assert "(clipped seed, d=d_opt) = 0.01300000" in clipped
    assert "seed-ref gap=+3.000000e-03" in clipped
    assert "bounded seed" in geometry(True)
    assert "seed-threshold gap=+3.000000e-03" in geometry(True)
