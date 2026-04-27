"""Unit tests for CERTUS_DESIGN worker DTOs."""

from __future__ import annotations

import pytest

from certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)


@pytest.mark.unit
def test_optim_worker_request_from_legacy_copies_payload() -> None:
    legacy = {"seed": 12, "n_iter": 50}
    req = OptimWorkerRequest.from_legacy(legacy)
    assert req.cfg == legacy
    legacy["seed"] = 99
    assert req.cfg["seed"] == 12


@pytest.mark.unit
def test_optim_worker_request_from_legacy_handles_non_dict() -> None:
    req = OptimWorkerRequest.from_legacy(None)
    assert req.cfg == {}


@pytest.mark.unit
def test_color_worker_request_from_legacy_copies_payload() -> None:
    legacy = {"runs": 10}
    req = ColorWorkerRequest.from_legacy(legacy)
    assert req.cfg == legacy
    legacy["runs"] = 11
    assert req.cfg["runs"] == 10


@pytest.mark.unit
def test_needle_worker_request_from_legacy_handles_non_dict() -> None:
    req = NeedleWorkerRequest.from_legacy(None)
    assert req.cfg == {}


@pytest.mark.unit
def test_color_worker_result_to_legacy_dict_success_shape() -> None:
    dto = ColorWorkerResult(ok=True, lab_nom=[50.0, 0.0, 0.0], labs=[[50.1, 0.2, -0.1]])
    payload = dto.to_legacy_dict()
    assert payload["ok"] is True
    assert "lab_nom" in payload
    assert "labs" in payload


@pytest.mark.unit
def test_color_worker_result_to_legacy_dict_failure_shape() -> None:
    dto = ColorWorkerResult.failure()
    payload = dto.to_legacy_dict()
    assert payload == {"ok": False}


@pytest.mark.unit
def test_optim_worker_result_to_legacy_dict_success_shape() -> None:
    dto = OptimWorkerResult.success(ep=[10.0, 20.0], rmse=0.123)
    payload = dto.to_legacy_dict()
    assert payload["ok"] is True
    assert payload["ep"] == [10.0, 20.0]
    assert payload["rmse"] == 0.123


@pytest.mark.unit
def test_optim_worker_result_to_legacy_dict_failure_shape() -> None:
    dto = OptimWorkerResult.failure()
    payload = dto.to_legacy_dict()
    assert payload == {"ok": False}


@pytest.mark.unit
def test_needle_worker_result_to_legacy_dict_action_only() -> None:
    dto = NeedleWorkerResult.action_only("none")
    payload = dto.to_legacy_dict()
    assert payload == {"action": "none"}


@pytest.mark.unit
def test_needle_worker_result_from_legacy_split_payload() -> None:
    dto = NeedleWorkerResult.from_legacy(
        {"action": "split", "layer_idx": 3, "depth": 12.5, "needle_mat": "H", "cost": 0.01}
    )
    payload = dto.to_legacy_dict()
    assert payload["action"] == "split"
    assert payload["layer_idx"] == 3
    assert payload["needle_mat"] == "H"
