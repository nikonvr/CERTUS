"""Unit tests for CERTUS_DESIGN headless service scaffolding."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_design_services import (
    DesignStrategyRequest,
    DesignStrategyResponse,
    DesignStrategyService,
)
from certus.utils.certus_services import BaseHeadlessRequest, BaseHeadlessResponse, BaseHeadlessService


@pytest.mark.unit
def test_design_strategy_service_wraps_runner_and_manifest(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    calls: list[object] = []

    def runner(payload):
        calls.append(payload)
        return {"ok": True, "payload": payload}

    service = DesignStrategyService(runner=runner)
    req = DesignStrategyRequest(
        config={"mode": "global", "pre_polish": True},
        source_paths=[str(src)],
        seed=17,
        app_version="26_05",
        warnings=["design smoke"],
        status=ValidationStatus.OK,
    )

    resp = service.optimize(req)
    assert calls
    assert isinstance(resp.result, dict)
    assert resp.result["ok"] is True
    assert resp.manifest.run_context.app_id == "CERTUS_DESIGN"
    assert resp.manifest.run_context.seed == 17


@pytest.mark.unit
def test_design_strategy_service_accepts_mapping_payload(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    seen: list[object] = []

    def runner(payload):
        seen.append(payload)
        return {"ok": True}

    payload = {
        "config": {"mode": "local", "cycle_no_gain_patience": 2},
        "source_paths": [str(src)],
        "seed": 99,
        "app_version": "26_05",
        "warnings": ["mapping"],
        "status": "OK",
    }

    service = DesignStrategyService(runner=runner)
    resp = service.optimize(payload)

    assert seen == [{"cfg": {"mode": "local", "cycle_no_gain_patience": 2}, "params": {"mats": {}, "stack": [], "ep0": None, "ep": None, "wls": None, "tgts": None, "l0": None, "mode": "local", "ep_back": None, "oblique_mode": False, "oblique_tgts": [], "local_delta_nm": 2.0, "pre_polish": False, "cycle_rel_gain_min": 0.0002, "cycle_no_gain_patience": 2, "run_seed": 0, "n": None, "sigma": None, "has_back": False, "n_back_T": None, "d_back": None}}]
    assert payload["config"] == {"mode": "local", "cycle_no_gain_patience": 2}
    assert resp.manifest.run_context.app_id == "CERTUS_DESIGN"
    assert resp.manifest.run_context.seed == 99


@pytest.mark.unit
def test_design_strategy_service_legacy_payload_filters_request_metadata(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    request = DesignStrategyService._normalize_request(
        {
            "mode": "global",
            "pre_polish": True,
            "source_paths": [str(src), "", "   "],
            "seed": 5,
            "app_version": "26_05",
            "warnings": ["x"],
            "status": "OK",
        }
    )

    assert request.config == {"mode": "global", "pre_polish": True}
    assert request.source_paths == [str(src)]
    assert request.warnings == ["x"]
    assert request.status == ValidationStatus.OK


@pytest.mark.unit
def test_design_strategy_service_normalizes_flat_payload_to_config(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    seen: list[object] = []

    def runner(payload):
        seen.append(payload)
        return {"ok": True}

    service = DesignStrategyService(runner=runner)
    resp = service.optimize(
        {
            "mode": "global",
            "pre_polish": True,
            "source_paths": [str(src)],
            "seed": 5,
            "app_version": "26_05",
            "warnings": [],
            "status": "OK",
        }
    )

    assert seen == [{"cfg": {"mode": "global", "pre_polish": True}, "params": {"mats": {}, "stack": [], "ep0": None, "ep": None, "wls": None, "tgts": None, "l0": None, "mode": "global", "ep_back": None, "oblique_mode": False, "oblique_tgts": [], "local_delta_nm": 2.0, "pre_polish": True, "cycle_rel_gain_min": 0.0002, "cycle_no_gain_patience": 1, "run_seed": 0, "n": None, "sigma": None, "has_back": False, "n_back_T": None, "d_back": None}}]
    assert resp.manifest.run_context.seed == 5


@pytest.mark.unit
def test_design_strategy_service_accepts_cfg_alias_in_legacy_payload(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    seen: list[object] = []

    def runner(payload):
        seen.append(payload)
        return {"ok": True}

    service = DesignStrategyService(runner=runner)
    resp = service.optimize(
        {
            "cfg": {"mode": "healing", "pre_polish": False, "cycle_no_gain_patience": 4},
            "source_paths": [str(src)],
            "seed": 11,
            "app_version": "26_05",
            "warnings": [],
            "status": "OK",
        }
    )

    assert seen == [{"cfg": {"mode": "healing", "pre_polish": False, "cycle_no_gain_patience": 4}, "params": {"mats": {}, "stack": [], "ep0": None, "ep": None, "wls": None, "tgts": None, "l0": None, "mode": "healing", "ep_back": None, "oblique_mode": False, "oblique_tgts": [], "local_delta_nm": 2.0, "pre_polish": False, "cycle_rel_gain_min": 0.0002, "cycle_no_gain_patience": 4, "run_seed": 0, "n": None, "sigma": None, "has_back": False, "n_back_T": None, "d_back": None}}]
    assert resp.manifest.run_context.seed == 11


@pytest.mark.unit
def test_design_strategy_service_normalize_request_preserves_legacy_metadata() -> None:
    request = DesignStrategyService._normalize_request(
        {
            "config": {"mode": "healing"},
            "source_paths": ["/tmp/a.json", "", "  "],
            "seed": 123,
            "app_id": "CERTUS_DESIGN",
            "app_version": "26_05",
            "warnings": ["legacy"],
            "status": "OK",
        }
    )

    assert request.config == {"mode": "healing"}
    assert request.source_paths == ["/tmp/a.json"]
    assert request.seed == 123
    assert request.app_version == "26_05"
    assert request.warnings == ["legacy"]
    assert request.status == ValidationStatus.OK


@pytest.mark.unit
def test_design_strategy_service_normalize_request_passthroughs_typed_request() -> None:
    req = DesignStrategyRequest(config={"mode": "global"}, source_paths=["/tmp/b.json"], seed=8)
    normalized = DesignStrategyService._normalize_request(req)

    assert normalized is req


@pytest.mark.unit
def test_design_strategy_service_rejects_unknown_status_and_defaults_to_ok(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    service = DesignStrategyService(runner=lambda payload: {"ok": True})
    resp = service.optimize(
        {
            "config": {"mode": "global"},
            "source_paths": [str(src)],
            "seed": 7,
            "app_version": "26_05",
            "warnings": ["x"],
            "status": "NOT_A_VALID_STATUS",
        }
    )

    assert resp.manifest.run_context.status == ValidationStatus.OK
    assert resp.manifest.run_context.seed == 7


@pytest.mark.unit
def test_design_strategy_service_falls_back_to_safe_result_on_non_dict_runner_output(tmp_path) -> None:
    src = tmp_path / "design_input.json"
    src.write_text("{}", encoding="utf-8")

    service = DesignStrategyService(runner=lambda payload: None)
    resp = service.optimize(
        {
            "config": {"mode": "global"},
            "source_paths": [str(src)],
            "seed": 2,
            "app_version": "26_05",
            "warnings": [],
            "status": "OK",
        }
    )

    assert resp.result == {"ok": True, "ep": [], "rmse": 0.0}
    assert resp.manifest.run_context.seed == 2


@pytest.mark.unit
def test_design_strategy_service_build_runner_payload_matches_worker_request() -> None:
    payload = DesignStrategyService._build_runner_payload(
        {
            "mode": "global",
            "pre_polish": True,
            "cycle_no_gain_patience": 3,
        }
    )

    assert payload["cfg"] == {"mode": "global", "pre_polish": True, "cycle_no_gain_patience": 3}
    assert payload["params"]["mode"] == "global"
    assert payload["params"]["pre_polish"] is True
    assert payload["params"]["cycle_no_gain_patience"] == 3


@pytest.mark.unit
def test_design_strategy_service_extract_design_config_accepts_cfg_alias() -> None:
    payload = {
        "cfg": {
            "mode": "healing",
            "pre_polish": False,
            "cycle_no_gain_patience": 4,
            "ignored": "value",
        }
    }

    cfg = DesignStrategyService._extract_design_config(payload)

    assert cfg == {"mode": "healing", "pre_polish": False, "cycle_no_gain_patience": 4}


@pytest.mark.unit
def test_design_strategy_request_defaults_are_safe() -> None:
    """Default request values must remain safe for legacy callers."""
    req = DesignStrategyRequest()

    assert req.app_id == "CERTUS_DESIGN"
    assert req.config == {}
    assert req.source_paths == []
    assert req.warnings == []
    assert req.status == ValidationStatus.OK


@pytest.mark.unit
def test_design_strategy_response_defaults_are_structure_safe() -> None:
    """The response contract must stay simple and serializable."""
    resp = DesignStrategyResponse(result={"ok": True}, manifest=None)  # type: ignore[arg-type]

    assert resp.result == {"ok": True}
    assert resp.manifest is None


@pytest.mark.unit
def test_design_strategy_public_contract_matches_base() -> None:
    req_contract = [f.name for f in fields(BaseHeadlessRequest)]
    resp_contract = [f.name for f in fields(BaseHeadlessResponse)]

    assert [f.name for f in fields(DesignStrategyRequest)] == req_contract
    assert [f.name for f in fields(DesignStrategyResponse)] == resp_contract
    assert issubclass(DesignStrategyService, BaseHeadlessService)
    sig = inspect.signature(DesignStrategyService.optimize)
    assert list(sig.parameters.keys()) == ["self", "request"]
