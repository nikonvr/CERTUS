"""Unit tests for CERTUS_STRAT worker DTOs."""

from __future__ import annotations

import pytest

from certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult


@pytest.mark.unit
def test_worker_thread_request_from_legacy_copies_payload() -> None:
    params = {"seed": 123, "mode": "fast"}
    opti_results = {"rmse": 0.1}
    req = WorkerThreadRequest.from_legacy(
        step=2,
        params=params,
        opti_results=opti_results,
    )
    assert req.step == 2
    assert req.params == params
    assert req.opti_results == opti_results
    params["seed"] = 999
    opti_results["rmse"] = 9.9
    assert req.params["seed"] == 123
    assert req.opti_results["rmse"] == 0.1


@pytest.mark.unit
def test_worker_thread_request_from_legacy_handles_non_dict_params() -> None:
    req = WorkerThreadRequest.from_legacy(step=0, params=None)
    assert req.step == 0
    assert req.params == {}


@pytest.mark.unit
def test_worker_thread_result_step0_to_legacy_dict() -> None:
    dto = WorkerThreadResult.for_step_0(
        nominal_results={"a": 1},
        seel_data={"b": 2},
    )
    payload = dto.to_legacy_dict()
    assert payload["nominal_results"] == {"a": 1}
    assert payload["seel_data"] == {"b": 2}


@pytest.mark.unit
def test_worker_thread_result_step2_to_legacy_dict() -> None:
    dto = WorkerThreadResult.for_step_2(opti_results={"score": 0.2})
    payload = dto.to_legacy_dict()
    assert payload == {"opti_results": {"score": 0.2}}


@pytest.mark.unit
def test_worker_thread_result_step23_to_legacy_dict() -> None:
    dto = WorkerThreadResult.for_step_23(
        opti_results={"blocks": [1, 2]},
        final_results={"best": "A"},
    )
    payload = dto.to_legacy_dict()
    assert payload["opti_results"] == {"blocks": [1, 2]}
    assert payload["final_results"] == {"best": "A"}


@pytest.mark.unit
def test_worker_thread_result_step3_to_legacy_dict() -> None:
    dto = WorkerThreadResult.for_step_3(final_results={"summary": "ok"})
    payload = dto.to_legacy_dict()
    assert payload == {"final_results": {"summary": "ok"}}


@pytest.mark.unit
def test_worker_thread_result_step33_to_legacy_dict() -> None:
    dto = WorkerThreadResult.for_step_33(
        opti_results={"ctx": 1},
        final_results={"external": True},
    )
    payload = dto.to_legacy_dict()
    assert payload["opti_results"] == {"ctx": 1}
    assert payload["final_results"] == {"external": True}
