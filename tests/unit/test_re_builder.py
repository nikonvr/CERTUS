from __future__ import annotations

import numpy as np
import pytest

from certus_re_results_builder import REResultsBuilder


@pytest.mark.unit
def test_re_results_builder_build_error_payload_contract() -> None:
    payload = REResultsBuilder.build_error_payload([10.0, 20.0])
    assert payload["ok"] is False
    assert payload["results"] == []
    assert payload["ep0"] == [10.0, 20.0]


@pytest.mark.unit
def test_re_results_builder_build_finished_payload_contract() -> None:
    payload = REResultsBuilder.build_finished_payload(
        results=[{"label": "best", "rmse_combined": 1.23}],
        ep0=np.array([100.0, 200.0], dtype=np.float64),
        rmse_initial_milestone=[3.0],
        rmse_phase1_milestone=[2.0],
        rmse_final_milestone=[1.0],
        stopped_by_user=False,
        re_qwot_alphas=(1.0, 0.0, 0.0, 0.0),
    )
    assert payload["ok"] is True
    assert payload["results"][0]["label"] == "best"
    assert np.allclose(payload["ep0"], np.array([100.0, 200.0], dtype=np.float64))


@pytest.mark.unit
def test_re_results_builder_ensure_results_and_top_adds_stop_fallback() -> None:
    results: list[dict] = []
    top = REResultsBuilder.ensure_results_and_top(
        results=results,
        stop_requested=True,
        cfg_ep0=[10.0, 20.0],
        rmse_initial_sp=1.0,
        rmse_initial_q=2.0,
        rmse_initial_u=3.0,
    )
    assert len(results) == 1
    assert top is not None
    assert top["label"] == "initial (stop before first TRF iter)"
    assert np.allclose(top["ep"], np.array([10.0, 20.0], dtype=np.float64))


@pytest.mark.unit
def test_re_results_builder_ensure_results_and_top_keeps_existing_top() -> None:
    results = [{"label": "best", "rmse_combined": 0.5}]
    top = REResultsBuilder.ensure_results_and_top(
        results=results,
        stop_requested=True,
        cfg_ep0=[1.0],
        rmse_initial_sp=9.0,
        rmse_initial_q=9.0,
        rmse_initial_u=9.0,
    )
    assert len(results) == 1
    assert top is results[0]
    assert top["label"] == "best"


@pytest.mark.unit
def test_re_results_builder_sort_enrich_and_top_applies_pipeline() -> None:
    calls: list[str] = []
    results = [{"label": "z", "rmse_combined": 2.0}, {"label": "a", "rmse_combined": 1.0}]

    def _sort(items: list[dict]) -> None:
        calls.append("sort")
        items.sort(key=lambda x: float(x["rmse_combined"]))

    def _enrich(items: list[dict], *, alpha_rank_ref: float, compute_qwot_rmse_raw) -> None:
        calls.append("enrich")
        for idx, item in enumerate(items):
            item["rank"] = idx + 1
            item["alpha_rank_ref"] = alpha_rank_ref
            item["qwot_probe"] = float(compute_qwot_rmse_raw(item))

    top = REResultsBuilder.sort_enrich_and_top(
        results=results,
        alpha_rank_ref=0.25,
        compute_qwot_rmse_raw=lambda r: r["rmse_combined"] * 10.0,
        sort_results=_sort,
        enrich_results=_enrich,
    )
    assert calls == ["sort", "enrich"]
    assert top is results[0]
    assert top["label"] == "a"
    assert results[0]["rank"] == 1
    assert results[0]["alpha_rank_ref"] == 0.25
    assert results[0]["qwot_probe"] == 10.0


@pytest.mark.unit
def test_re_results_builder_finalize_reconcile_top_matches_ensure_then_sort() -> None:
    calls: list[str] = []
    results: list[dict] = [
        {"label": "b", "rmse_combined": 2.0},
        {"label": "a", "rmse_combined": 1.0},
    ]

    def _sort(items: list[dict]) -> None:
        calls.append("sort")
        items.sort(key=lambda x: float(x["rmse_combined"]))

    def _enrich(items: list[dict], **kwargs) -> None:
        calls.append("enrich")

    top1 = REResultsBuilder.finalize_reconcile_top(
        results=results,
        stop_requested=False,
        cfg_ep0=[],
        rmse_initial_sp=0.0,
        rmse_initial_q=0.0,
        rmse_initial_u=0.0,
        alpha_rank_ref=0.1,
        compute_qwot_rmse_raw=lambda r: 0.0,
        sort_results=_sort,
        enrich_results=_enrich,
    )
    assert top1 is not None
    assert top1["label"] == "a"
    assert calls == ["sort", "enrich"]

    r_stop: list[dict] = []
    top_stop = REResultsBuilder.finalize_reconcile_top(
        results=r_stop,
        stop_requested=True,
        cfg_ep0=[1.0, 2.0],
        rmse_initial_sp=1.0,
        rmse_initial_q=2.0,
        rmse_initial_u=3.0,
        alpha_rank_ref=0.0,
        compute_qwot_rmse_raw=lambda r: 0.0,
        sort_results=_sort,
        enrich_results=_enrich,
    )
    assert len(r_stop) == 1
    assert top_stop is not None
    assert top_stop["label"] == "initial (stop before first TRF iter)"
    assert np.allclose(top_stop["ep"], np.array([1.0, 2.0], dtype=np.float64))


@pytest.mark.unit
def test_re_results_builder_top_metrics_for_none() -> None:
    metrics = REResultsBuilder.top_metrics(None)
    assert np.isnan(metrics["best_sp"])
    assert np.isnan(metrics["best_ot"])
    assert np.isnan(metrics["best_combined"])
    assert np.isnan(metrics["rmse_final_u"])


@pytest.mark.unit
def test_re_results_builder_top_metrics_from_payload() -> None:
    metrics = REResultsBuilder.top_metrics(
        {"rmse": 1.25, "rmse_qwot": 2.5, "rmse_combined": 0.75}
    )
    assert metrics["best_sp"] == 1.25
    assert metrics["best_ot"] == 2.5
    assert metrics["best_combined"] == 0.75
    assert metrics["rmse_final_u"] == 0.75


@pytest.mark.unit
def test_re_results_builder_final_diagnostic_payload_normalizes_values() -> None:
    payload = REResultsBuilder.final_diagnostic_payload(
        best_sp=1.5,
        best_ot=float("nan"),
        alpha_current=0.2,
        alpha_gui=0.1,
        rmse_final_u=0.8,
        rmse_initial_u=1.0,
        rmse_initial_sp=2.0,
        rmse_initial_q=0.3,
    )
    assert payload["best_sp"] == 1.5
    assert payload["ot_fin"] == 0.0
    assert payload["alpha_current"] == 0.2
    assert payload["alpha_gui"] == 0.1
    assert payload["delta_rmse"] == pytest.approx(-0.2)
    assert payload["delta_sp"] == pytest.approx(-0.5)
    assert payload["delta_qwot"] == pytest.approx(-0.3)


@pytest.mark.unit
def test_re_results_builder_cauchy_barrier_diagnostic_payload_none_without_coeffs() -> None:
    payload = REResultsBuilder.cauchy_barrier_diagnostic_payload(
        top_result={"label": "x"},
        wls=np.array([500.0, 600.0], dtype=np.float64),
        lambda_ref=550.0,
        n_sub_nominal=np.array([1.5 + 0j, 1.6 + 0j]),
        barrier_sqrt_w=2.0,
        tube_delta=0.01,
        substrate_phi_matrix=lambda _w, _l: np.eye(2),
        barrier_residuals_jac=lambda *_args, **_kwargs: (np.array([0.0]), None),
    )
    assert payload is None


@pytest.mark.unit
def test_re_results_builder_cauchy_barrier_diagnostic_payload_computes_stats() -> None:
    def _phi(_wls, _lambda_ref):
        return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)

    def _residuals(_th, _phi_m, _ntab, *, sqrt_w):
        assert sqrt_w == 3.0
        return np.array([0.0, 1e-6, -2e-6], dtype=np.float64), None

    payload = REResultsBuilder.cauchy_barrier_diagnostic_payload(
        top_result={
            "re_sub_cauchy_a0": 1.0,
            "re_sub_cauchy_a1": 2.0,
            "re_sub_cauchy_a2": 3.0,
        },
        wls=np.array([500.0, 600.0], dtype=np.float64),
        lambda_ref=550.0,
        n_sub_nominal=np.array([1.5 + 0j, 1.6 + 0j]),
        barrier_sqrt_w=3.0,
        tube_delta=0.02,
        substrate_phi_matrix=_phi,
        barrier_residuals_jac=_residuals,
    )
    assert payload is not None
    assert payload["n_active"] == 2
    assert payload["n_total"] == 3
    assert payload["tube_delta"] == 0.02
    assert payload["res_norm"] == pytest.approx(np.linalg.norm([0.0, 1e-6, -2e-6]))


@pytest.mark.unit
def test_re_results_builder_finalize_message_bundle_builds_all_outputs() -> None:
    bundle = REResultsBuilder.finalize_message_bundle(
        results=[{"label": "best"}],
        top_result={"label": "best"},
        alpha_rank_ref=0.33,
        elapsed_s=12.0,
        best_sp=1.0,
        best_ot=2.0,
        best_combined=3.0,
        rmse_initial_milestone=[4.0],
        rmse_phase1_milestone=[3.5],
        rmse_final_milestone=[3.0],
        stopped_by_user=False,
        ranking_log_suffix=lambda _top, alpha: f"rank(alpha={alpha})",
        finished_main_log_line=lambda t, sp, ot, c, r, n: f"main({t},{sp},{ot},{c},{r},{n})",
        rmse_milestone_log_line=lambda i, p1, f: f"rmse({i[0]},{p1[0]},{f[0]})",
        progress_message_done=lambda **kwargs: f"progress(stop={kwargs['stopped_by_user']})",
    )
    assert bundle["rank_line"] == "rank(alpha=0.33)"
    assert bundle["finished_main_log"] == "main(12.0,1.0,2.0,3.0,rank(alpha=0.33),1)"
    assert bundle["rmse_milestone_log"] == "rmse(4.0,3.5,3.0)"
    assert bundle["progress_done"] == "progress(stop=False)"


@pytest.mark.unit
def test_re_results_builder_finalize_tail_bundle_includes_finished_payload() -> None:
    ep0 = np.array([1.0, 2.0], dtype=np.float64)
    tail = REResultsBuilder.finalize_tail_bundle(
        results=[{"label": "best", "rmse_combined": 0.1}],
        top_result={"label": "best", "rmse_combined": 0.1},
        ep0=ep0,
        alpha_rank_ref=0.1,
        elapsed_s=5.0,
        best_sp=0.1,
        best_ot=0.2,
        best_combined=0.3,
        rmse_initial_milestone=[1.0],
        rmse_phase1_milestone=[0.5],
        rmse_final_milestone=[0.3],
        stopped_by_user=False,
        re_qwot_alphas=(1.0, 0.0, 0.0, 0.0),
        ranking_log_suffix=lambda _t, a: f"r={a}",
        finished_main_log_line=lambda *a: "main",
        rmse_milestone_log_line=lambda *a: "mile",
        progress_message_done=lambda **k: "done",
    )
    assert tail["finished_main_log"] == "main"
    assert tail["rmse_milestone_log"] == "mile"
    assert tail["progress_done"] == "done"
    assert "ok" in tail["finished_payload"]
    assert np.allclose(tail["finished_payload"]["ep0"], ep0)


@pytest.mark.unit
def test_re_results_builder_stop_live_emit_payload_returns_none_when_not_stopped() -> None:
    payload = REResultsBuilder.stop_live_emit_payload(
        stop_requested=False,
        top_result={"ep": [1.0], "nfev": 5, "rmse_combined": 0.1},
        correc_nominal=("pct", 0.0, 0.0, 0.0),
        p2_to_correc=lambda _r, _u: ("pct", 1.0, 1.0, 1.0),
    )
    assert payload is None


@pytest.mark.unit
def test_re_results_builder_stop_live_emit_payload_uses_p2_correc_when_knots_present() -> None:
    payload = REResultsBuilder.stop_live_emit_payload(
        stop_requested=True,
        top_result={
            "ep": [10.0, 20.0],
            "nfev": 9,
            "rmse_combined": 0.25,
            "re_dH_knots": [0.1],
            "re_dL_knots": [0.2],
            "re_sub_cauchy_a0": 1.0,
        },
        correc_nominal=("pct", 0.0, 0.0, 0.0),
        p2_to_correc=lambda _r, use_sub_c3: ("pct", 9.0, 8.0, float(use_sub_c3)),
    )
    assert payload is not None
    assert np.allclose(payload["ep"], np.array([10.0, 20.0], dtype=np.float64))
    assert payload["nfev"] == 9
    assert payload["correc"] == ("pct", 9.0, 8.0, 1.0)
    assert payload["force"] is True
    assert payload["rmse_override"] == 0.25
