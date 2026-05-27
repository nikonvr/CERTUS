"""Unit tests for spectral worker DTO boundary."""

from __future__ import annotations

import pytest

from certus.workers.certus_spectral_workers import EvalWorkerRequest, EvalWorkerResult


@pytest.mark.unit
def test_eval_worker_request_from_legacy_copies_payload() -> None:
    legacy = {"seed": 42, "back": True}
    req = EvalWorkerRequest.from_legacy(legacy)
    assert req.cfg == legacy
    legacy["seed"] = 999
    assert req.cfg["seed"] == 42


@pytest.mark.unit
def test_eval_worker_request_from_legacy_handles_non_dict() -> None:
    req = EvalWorkerRequest.from_legacy(None)
    assert req.cfg == {}


@pytest.mark.unit
def test_eval_worker_result_to_legacy_dict_non_oblique() -> None:
    dto = EvalWorkerResult(
        vis={"l": [1], "Ts": [0.5]},
        optimization={"l": [], "Ts": []},
        rmse=None,
        ep=[10.0],
        eval_generation_id=7,
        oblique_mode=False,
    )
    payload = dto.to_legacy_dict()
    assert payload["oblique_mode"] is False
    assert "spectra_vis" not in payload
    assert payload["eval_generation_id"] == 7


@pytest.mark.unit
def test_eval_worker_result_to_legacy_dict_oblique_includes_spectra() -> None:
    dto = EvalWorkerResult.success(
        vis={"l": [1], "Ts": [0.5]},
        optimization={"l": [2], "Ts": [0.6]},
        rmse=0.1,
        ep=[10.0],
        eval_generation_id=None,
        ep_back=[20.0],
        oblique_mode=True,
        spectra_vis={"k": {"T": [0.5]}},
        spectra_optim={"k": {"T": [0.6]}},
        oblique_tgts=["t1"],
    )
    payload = dto.to_legacy_dict()
    assert payload["oblique_mode"] is True
    assert payload["ep_back"] == [20.0]
    assert "spectra_vis" in payload
    assert payload["oblique_tgts"] == ["t1"]
