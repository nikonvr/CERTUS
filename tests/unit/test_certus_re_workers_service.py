"""Unit tests for RE phase orchestration service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import numpy as np

from certus_re_workers import (
    REPhase1Result,
    REPhase2Result,
    REPhase3Result,
    REPhase4Result,
    REPhaseStateService,
    REPhasesService,
    REWorkerRequest,
    _prepend_result_dto,
    _replace_all_with_top_dto,
    _result_dto_at,
    _set_top_result_dto,
    _top_result_dto,
)


class _DummyWorker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._re_phase_ns = SimpleNamespace(
            results=[],
            _re_state={"is_phase4": True},
            _use_sub_c3_shared=True,
            _p2_ctx={"pre": 1},
        )

    def _execute_phase1(self):
        self.calls.append("phase1")
        return [{"id": 1}]

    def _execute_phase1_p4_scan(self) -> None:
        self.calls.append("phase1_p4_scan")

    def _execute_phase2_splines(self) -> None:
        self.calls.append("phase2")

    def _execute_phase3_shakes(self) -> None:
        self.calls.append("phase3")

    def _execute_phase4_beam(self) -> None:
        self.calls.append("phase4")


@pytest.mark.unit
def test_re_phases_service_executes_all_in_order() -> None:
    worker = _DummyWorker()
    service = REPhasesService(worker)

    service.execute_all()

    assert worker.calls == ["phase1", "phase1_p4_scan", "phase2", "phase3", "phase4"]
    assert worker._re_phase_ns.results == [{"id": 1}]
    assert worker._re_phase_ns._re_state["is_phase4"] is False
    assert worker._re_phase_ns._use_sub_c3_shared is False
    assert worker._re_phase_ns._p2_ctx == {}


@pytest.mark.unit
def test_re_phases_service_accepts_injected_phase_contracts() -> None:
    class _Step:
        def __init__(self, name: str):
            self.name = name

        def run(self, service: REPhasesService) -> None:
            service._worker.calls.append(self.name)

    worker = _DummyWorker()
    custom_steps = [_Step("s1"), _Step("s2"), _Step("s3")]
    service = REPhasesService(worker, steps=custom_steps)

    service.execute_all()

    assert worker.calls == ["s1", "s2", "s3"]


@pytest.mark.unit
def test_re_phase_state_service_prepares_phase2_state() -> None:
    worker = _DummyWorker()
    svc = REPhaseStateService()

    svc.prepare_phase2_state(worker)

    assert worker._re_phase_ns._re_state["is_phase4"] is False
    assert worker._re_phase_ns._use_sub_c3_shared is False
    assert worker._re_phase_ns._p2_ctx == {}


@pytest.mark.unit
def test_re_worker_request_from_legacy_copies_payload() -> None:
    legacy = {"re_phase1_maxiter": 123, "seed": 42}
    req = REWorkerRequest.from_legacy(legacy)
    assert req.cfg == legacy
    legacy["re_phase1_maxiter"] = 999
    assert req.cfg["re_phase1_maxiter"] == 123


@pytest.mark.unit
def test_re_worker_request_from_legacy_handles_non_dict() -> None:
    req = REWorkerRequest.from_legacy(None)
    assert req.cfg == {}


@pytest.mark.unit
def test_re_phase1_result_to_legacy_dict_normalizes_types() -> None:
    dto = REPhase1Result(
        label="run-a",
        ep=np.array([10.0, 20.0], dtype=np.float32),
        a=0.1,
        b=0.2,
        f=0.3,
        rmse=1.0,
        rmse_qwot=2.0,
        rmse_combined=3.0,
        nfev=4,
        success=True,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["label"] == "run-a"
    assert isinstance(legacy["ep"], np.ndarray)
    assert legacy["ep"].dtype == np.float64
    assert np.allclose(legacy["ep"], np.array([10.0, 20.0], dtype=np.float64))
    assert legacy["nfev"] == 4
    assert legacy["success"] is True


@pytest.mark.unit
def test_re_phase2_result_to_legacy_dict_without_cauchy() -> None:
    dto = REPhase2Result(
        label="drift",
        ep=np.array([1.0, 2.0], dtype=np.float32),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.01, 0.02], dtype=np.float32),
        re_dl_knots=np.array([0.03, 0.04], dtype=np.float32),
        re_knots_nm=np.array([450.0, 600.0], dtype=np.float32),
        re_spline_lam_node2_nm=600.0,
        rmse=1.1,
        rmse_qwot=2.2,
        rmse_combined=3.3,
        nfev=10,
        success=True,
        nfev_phase1=11,
        nfev_phase2_prefit=12,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["label"] == "drift"
    assert np.allclose(legacy["ep"], np.array([1.0, 2.0], dtype=np.float64))
    assert np.allclose(legacy["re_dH_knots"], [0.01, 0.02])
    assert np.allclose(legacy["re_dL_knots"], [0.03, 0.04])
    assert np.allclose(legacy["re_knots_nm"], [450.0, 600.0])
    assert "re_sub_cauchy_a0" not in legacy


@pytest.mark.unit
def test_re_phase2_result_to_legacy_dict_with_cauchy() -> None:
    dto = REPhase2Result(
        label="drift",
        ep=np.array([1.0], dtype=np.float64),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.01], dtype=np.float64),
        re_dl_knots=np.array([0.02], dtype=np.float64),
        re_knots_nm=np.array([500.0], dtype=np.float64),
        re_spline_lam_node2_nm=500.0,
        rmse=1.0,
        rmse_qwot=2.0,
        rmse_combined=3.0,
        nfev=1,
        success=False,
        nfev_phase1=2,
        nfev_phase2_prefit=3,
        re_sub_cauchy_a0=0.1,
        re_sub_cauchy_a1=0.2,
        re_sub_cauchy_a2=0.3,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["re_sub_cauchy_a0"] == 0.1
    assert legacy["re_sub_cauchy_a1"] == 0.2
    assert legacy["re_sub_cauchy_a2"] == 0.3


@pytest.mark.unit
def test_re_phase3_result_to_legacy_dict_without_cauchy() -> None:
    dto = REPhase3Result(
        label="drift",
        ep=np.array([2.0, 3.0], dtype=np.float32),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.05, 0.06], dtype=np.float32),
        re_dl_knots=np.array([0.07, 0.08], dtype=np.float32),
        re_knots_nm=np.array([500.0, 700.0], dtype=np.float32),
        re_spline_lam_node2_nm=650.0,
        rmse=1.5,
        rmse_qwot=2.5,
        rmse_combined=3.5,
        nfev=20,
        success=True,
        nfev_phase1=21,
        nfev_phase2_prefit=22,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["label"] == "drift"
    assert np.allclose(legacy["ep"], [2.0, 3.0])
    assert np.allclose(legacy["re_dH_knots"], [0.05, 0.06])
    assert np.allclose(legacy["re_dL_knots"], [0.07, 0.08])
    assert np.allclose(legacy["re_knots_nm"], [500.0, 700.0])
    assert "re_sub_cauchy_a0" not in legacy


@pytest.mark.unit
def test_re_phase3_result_to_legacy_dict_with_cauchy() -> None:
    dto = REPhase3Result(
        label="drift",
        ep=np.array([2.0], dtype=np.float64),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.05], dtype=np.float64),
        re_dl_knots=np.array([0.07], dtype=np.float64),
        re_knots_nm=np.array([500.0], dtype=np.float64),
        re_spline_lam_node2_nm=650.0,
        rmse=1.5,
        rmse_qwot=2.5,
        rmse_combined=3.5,
        nfev=20,
        success=False,
        nfev_phase1=21,
        nfev_phase2_prefit=22,
        re_sub_cauchy_a0=0.4,
        re_sub_cauchy_a1=0.5,
        re_sub_cauchy_a2=0.6,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["re_sub_cauchy_a0"] == 0.4
    assert legacy["re_sub_cauchy_a1"] == 0.5
    assert legacy["re_sub_cauchy_a2"] == 0.6


@pytest.mark.unit
def test_re_phase4_result_to_legacy_dict_without_cauchy() -> None:
    dto = REPhase4Result(
        label="drift (P4)",
        ep=np.array([1.0, 2.0], dtype=np.float32),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.1, 0.2], dtype=np.float32),
        re_dl_knots=np.array([0.3, 0.4], dtype=np.float32),
        re_knots_nm=np.array([500.0, 700.0], dtype=np.float32),
        re_spline_lam_node2_nm=650.0,
        rmse=1.0,
        rmse_qwot=2.0,
        rmse_combined=3.0,
        nfev=42,
        success=True,
        nfev_phase1=10,
        nfev_phase2_prefit=11,
        re_p4_aperture_deg=12.5,
        re_p4_beam_ap_knots_nm=np.array([420.0, 680.0], dtype=np.float32),
        re_p4_beam_ap_knots_deg=np.array([11.0, 14.0], dtype=np.float32),
    )
    legacy = dto.to_legacy_dict()
    assert legacy["label"] == "drift (P4)"
    assert np.allclose(legacy["ep"], [1.0, 2.0])
    assert np.allclose(legacy["re_p4_beam_ap_knots_nm"], [420.0, 680.0])
    assert np.allclose(legacy["re_p4_beam_ap_knots_deg"], [11.0, 14.0])
    assert legacy["re_p4_aperture_deg"] == 12.5
    assert "re_sub_cauchy_a0" not in legacy


@pytest.mark.unit
def test_re_phase4_result_to_legacy_dict_with_cauchy() -> None:
    dto = REPhase4Result(
        label="drift (P4)",
        ep=np.array([1.0], dtype=np.float64),
        a=0.0,
        b=0.0,
        f=0.0,
        re_dh_knots=np.array([0.1], dtype=np.float64),
        re_dl_knots=np.array([0.2], dtype=np.float64),
        re_knots_nm=np.array([600.0], dtype=np.float64),
        re_spline_lam_node2_nm=600.0,
        rmse=1.0,
        rmse_qwot=2.0,
        rmse_combined=3.0,
        nfev=1,
        success=False,
        nfev_phase1=2,
        nfev_phase2_prefit=3,
        re_p4_aperture_deg=13.0,
        re_p4_beam_ap_knots_nm=np.array([500.0], dtype=np.float64),
        re_p4_beam_ap_knots_deg=np.array([13.0], dtype=np.float64),
        re_sub_cauchy_a0=0.7,
        re_sub_cauchy_a1=0.8,
        re_sub_cauchy_a2=0.9,
    )
    legacy = dto.to_legacy_dict()
    assert legacy["re_sub_cauchy_a0"] == 0.7
    assert legacy["re_sub_cauchy_a1"] == 0.8
    assert legacy["re_sub_cauchy_a2"] == 0.9


@pytest.mark.unit
def test_re_phase4_result_from_legacy_dict_maps_expected_fields() -> None:
    payload = {
        "label": "legacy-p4",
        "ep": [1.0, 2.0],
        "re_dH_knots": [0.1],
        "re_dL_knots": [0.2],
        "re_knots_nm": [550.0],
        "re_spline_lam_node2_nm": 620.0,
        "rmse": 1.2,
        "rmse_qwot": 2.3,
        "rmse_combined": 3.4,
        "nfev": 99,
        "success": True,
        "nfev_phase1": 9,
        "nfev_phase2_prefit": 8,
        "re_p4_aperture_deg": 14.0,
        "re_p4_beam_ap_knots_nm": [500.0],
        "re_p4_beam_ap_knots_deg": [14.0],
        "re_sub_cauchy_a0": 0.11,
        "re_sub_cauchy_a1": 0.22,
        "re_sub_cauchy_a2": 0.33,
    }
    dto = REPhase4Result.from_legacy_dict(payload)
    assert dto.label == "legacy-p4"
    assert np.allclose(dto.ep, [1.0, 2.0])
    assert dto.nfev == 99
    assert dto.re_sub_cauchy_a0 == 0.11


@pytest.mark.unit
def test_re_phase4_result_from_legacy_dict_supports_pre_p4_payload() -> None:
    payload = {
        "label": "legacy-pre-p4",
        "ep": [1.0],
        "re_dH_knots": [0.01],
        "re_dL_knots": [0.02],
        "re_knots_nm": [600.0],
        "re_spline_lam_node2_nm": 600.0,
        "rmse": 1.0,
        "rmse_qwot": 2.0,
        "rmse_combined": 3.0,
        "nfev": 5,
        "success": True,
        "nfev_phase1": 2,
        "nfev_phase2_prefit": 3,
    }
    dto = REPhase4Result.from_legacy_dict(payload)
    assert dto.re_p4_aperture_deg == 0.0
    assert dto.re_p4_beam_ap_knots_nm.size == 0
    assert dto.re_p4_beam_ap_knots_deg.size == 0


@pytest.mark.unit
def test_top_result_dto_returns_none_for_empty_and_maps_first_item() -> None:
    assert _top_result_dto([]) is None
    dto = _top_result_dto([{"label": "x", "rmse": 1.0, "rmse_combined": 2.0, "ep": [1.0]}])
    assert dto is not None
    assert dto.label == "x"
    assert dto.rmse_combined == 2.0


@pytest.mark.unit
def test_result_dto_at_supports_index_and_bounds() -> None:
    data = [
        {"label": "a", "rmse": 1.0, "rmse_combined": 1.1, "ep": [1.0]},
        {"label": "b", "rmse": 2.0, "rmse_combined": 2.2, "ep": [2.0]},
    ]
    assert _result_dto_at(data, -1) is None
    assert _result_dto_at(data, 2) is None
    dto1 = _result_dto_at(data, 1)
    assert dto1 is not None
    assert dto1.label == "b"
    assert dto1.rmse_combined == 2.2


@pytest.mark.unit
def test_set_top_result_dto_replaces_or_initializes() -> None:
    dto = REPhase4Result.from_legacy_dict({"label": "x", "rmse": 1.0, "rmse_combined": 1.1, "ep": [1.0]})
    rows: list[dict] = []
    _set_top_result_dto(rows, dto)
    assert rows[0]["label"] == "x"
    newer = REPhase4Result.from_legacy_dict({"label": "y", "rmse": 2.0, "rmse_combined": 2.2, "ep": [2.0]})
    _set_top_result_dto(rows, newer)
    assert rows[0]["label"] == "y"
    assert len(rows) == 1


@pytest.mark.unit
def test_prepend_result_dto_adds_front_item() -> None:
    a = REPhase4Result.from_legacy_dict({"label": "a", "rmse": 1.0, "rmse_combined": 1.1, "ep": [1.0]})
    b = REPhase4Result.from_legacy_dict({"label": "b", "rmse": 2.0, "rmse_combined": 2.2, "ep": [2.0]})
    rows = [a.to_legacy_dict()]
    _prepend_result_dto(rows, b)
    assert rows[0]["label"] == "b"
    assert rows[1]["label"] == "a"


@pytest.mark.unit
def test_replace_all_with_top_dto_keeps_single_item() -> None:
    a = REPhase4Result.from_legacy_dict({"label": "a", "rmse": 1.0, "rmse_combined": 1.1, "ep": [1.0]})
    b = REPhase4Result.from_legacy_dict({"label": "b", "rmse": 2.0, "rmse_combined": 2.2, "ep": [2.0]})
    rows = [a.to_legacy_dict(), b.to_legacy_dict()]
    _replace_all_with_top_dto(rows, b)
    assert len(rows) == 1
    assert rows[0]["label"] == "b"

