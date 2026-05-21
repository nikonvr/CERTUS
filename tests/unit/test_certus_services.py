"""Unit tests for headless service scaffolding."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

import certus_services as cs
from certus_metrology import ValidationStatus
from certus_services import (
    BaseHeadlessService,
    BaseHeadlessRequest,
    BaseHeadlessResponse,
    IndexFitRequest,
    IndexFitResponse,
    IndexFitService,
    REFitRequest,
    REFitResponse,
    REFitService,
    SubstrateIndexRequest,
    SubstrateIndexResponse,
    SubstrateIndexService,
)


@pytest.mark.unit
def test_index_fit_service_delegates_to_runner_and_wraps_manifest(tmp_path) -> None:
    src = tmp_path / "input.csv"
    src.write_text("lambda,T\n500,0.91\n", encoding="utf-8")

    calls: list[object] = []

    def runner(cfg):
        calls.append(cfg)
        return {"ok": True, "cfg": cfg}

    service = IndexFitService(runner=runner)
    req = IndexFitRequest(
        config={"mode": "TLU"},
        source_paths=[str(src)],
        seed=123,
        app_version="26_01",
        warnings=["normalized"],
        status=ValidationStatus.WARNING_DATA_NORMALIZED,
    )

    resp = service.fit(req)
    assert calls == [{"mode": "TLU"}]
    assert resp.result["ok"] is True
    assert resp.manifest.run_context.app_id == "CERTUS_INDEX"
    assert resp.manifest.run_context.seed == 123
    assert resp.manifest.run_context.status == ValidationStatus.WARNING_DATA_NORMALIZED
    assert len(resp.manifest.run_context.input_fingerprints) == 1


@pytest.mark.unit
def test_substrate_index_service_wraps_manifest_with_status(tmp_path) -> None:
    src = tmp_path / "substrate.xlsx"
    src.write_text("dummy", encoding="utf-8")

    def runner(cfg):
        return {"ok": True, "cfg": cfg}

    service = SubstrateIndexService(runner=runner)
    req = SubstrateIndexRequest(
        config={"fit": "sellmeier"},
        source_paths=[str(src)],
        seed=12345,
        app_version="26_01",
        warnings=["sellmeier skipped on one column"],
        status=ValidationStatus.WARNING_UNCERTAINTY_NOT_COMPUTED,
    )
    resp = service.fit(req)
    assert resp.result["ok"] is True
    assert resp.manifest.run_context.app_id == "CERTUS_SUBSTRATE_INDEX"
    assert resp.manifest.run_context.seed == 12345
    assert (
        resp.manifest.run_context.status
        == ValidationStatus.WARNING_UNCERTAINTY_NOT_COMPUTED
    )


@pytest.mark.unit
def test_re_fit_service_wraps_manifest(tmp_path) -> None:
    src = tmp_path / "re_input.xlsx"
    src.write_text("dummy", encoding="utf-8")

    def runner(cfg):
        return {"ok": True, "cfg": cfg}

    service = REFitService(runner=runner)
    req = REFitRequest(
        config={"phase_count": 4},
        source_paths=[str(src)],
        seed=None,
        app_version="26_01",
        warnings=["header inferred"],
        status=ValidationStatus.OK,
    )
    resp = service.fit(req)
    assert resp.result["ok"] is True
    assert resp.manifest.run_context.app_id == "CERTUS_RE"
    assert resp.manifest.run_context.seed is None
    assert resp.manifest.run_context.status == ValidationStatus.OK


@pytest.mark.unit
def test_index_fit_manifest_fingerprints_multiple_existing_paths(tmp_path) -> None:
    src_spec = tmp_path / "input_spectrum.csv"
    src_spec.write_text("lambda,T\n500,0.91\n", encoding="utf-8")
    src_db = tmp_path / "indices.xlsx"
    src_db.write_text("dummy-db", encoding="utf-8")

    service = IndexFitService(runner=lambda cfg: {"ok": True, "cfg": cfg})
    req = IndexFitRequest(
        config={"mode": "TLU"},
        source_paths=[str(src_spec), str(src_db), str(tmp_path / "missing.txt")],
        seed=7,
        app_version="26_01",
        status=ValidationStatus.OK,
    )
    resp = service.fit(req)
    fps = resp.manifest.run_context.input_fingerprints
    assert len(fps) == 2
    assert [fp.path for fp in fps] == [str(src_spec), str(src_db)]
    assert all(isinstance(fp.sha256, str) and len(fp.sha256) == 64 for fp in fps)


@pytest.mark.unit
def test_manifest_source_paths_are_normalized_before_fingerprinting(tmp_path) -> None:
    src = tmp_path / "input.csv"
    src.write_text("lambda,T\n500,0.91\n", encoding="utf-8")

    service = IndexFitService(runner=lambda cfg: {"ok": True, "cfg": cfg})
    req = IndexFitRequest(
        config={"mode": "TLU"},
        source_paths=["", "   ", str(src), f" {src} ", str(src)],
        seed=11,
        app_version="26_01",
        status=ValidationStatus.OK,
    )
    resp = service.fit(req)
    fps = resp.manifest.run_context.input_fingerprints
    assert len(fps) == 1
    assert fps[0].path == str(src)


@pytest.mark.unit
def test_service_accepts_mapping_payload_and_normalizes_status(tmp_path) -> None:
    src = tmp_path / "input.csv"
    src.write_text("lambda,T\n500,0.91\n", encoding="utf-8")

    service = IndexFitService(runner=lambda cfg: {"cfg": cfg})
    resp = service.fit(
        {
            "config": {"mode": "TLU"},
            "source_paths": [str(src)],
            "seed": 42,
            "app_id": "CERTUS_INDEX",
            "app_version": "26_01",
            "warnings": ["mapping payload"],
            "status": "not-a-known-status",
        }
    )

    assert resp.result == {"cfg": {"mode": "TLU"}}
    assert resp.manifest.run_context.seed == 42
    assert resp.manifest.run_context.status == ValidationStatus.OK
    assert len(resp.manifest.run_context.input_fingerprints) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("service_cls", "request_cls", "app_id"),
    [
        (IndexFitService, IndexFitRequest, "CERTUS_INDEX"),
        (SubstrateIndexService, SubstrateIndexRequest, "CERTUS_SUBSTRATE_INDEX"),
        (REFitService, REFitRequest, "CERTUS_RE"),
    ],
)
def test_seeded_service_smoke_is_deterministic_for_stable_fields(
    tmp_path, service_cls, request_cls, app_id
) -> None:
    src = tmp_path / f"{app_id.lower()}_input.csv"
    src.write_text("lambda,T\n500,0.91\n", encoding="utf-8")

    def runner(cfg):
        return {"ok": True, "cfg": cfg}

    service = service_cls(runner=runner)
    req = request_cls(
        config={"dataset": "smoke", "seed": 20260425},
        source_paths=[str(src)],
        seed=20260425,
        app_version="26_01",
        status=ValidationStatus.OK,
    )

    resp_a = service.fit(req)
    resp_b = service.fit(req)

    assert resp_a.result == resp_b.result
    assert resp_a.manifest.run_context.app_id == app_id
    assert resp_b.manifest.run_context.app_id == app_id
    assert resp_a.manifest.run_context.seed == 20260425
    assert resp_b.manifest.run_context.seed == 20260425
    assert resp_a.manifest.run_context.params_hash == resp_b.manifest.run_context.params_hash
    assert len(resp_a.manifest.run_context.input_fingerprints) == 1
    assert len(resp_b.manifest.run_context.input_fingerprints) == 1
    assert (
        resp_a.manifest.run_context.input_fingerprints[0].sha256
        == resp_b.manifest.run_context.input_fingerprints[0].sha256
    )


@pytest.mark.unit
def test_headless_services_public_contract_is_normalized() -> None:
    req_contract = [f.name for f in fields(BaseHeadlessRequest)]
    resp_contract = [f.name for f in fields(BaseHeadlessResponse)]

    for req_cls in (IndexFitRequest, SubstrateIndexRequest, REFitRequest):
        assert [f.name for f in fields(req_cls)] == req_contract

    for resp_cls in (IndexFitResponse, SubstrateIndexResponse, REFitResponse):
        assert [f.name for f in fields(resp_cls)] == resp_contract

    for svc_cls in (IndexFitService, SubstrateIndexService, REFitService):
        sig = inspect.signature(svc_cls.fit)
        assert list(sig.parameters.keys()) == ["self", "request"]


@pytest.mark.unit
def test_future_headless_services_must_follow_contract() -> None:
    service_classes = [
        obj
        for name, obj in vars(cs).items()
        if inspect.isclass(obj)
        and name.endswith("Service")
        and name != "BaseHeadlessService"
        and obj.__module__ == "certus_services"
    ]
    assert service_classes, "Aucun service headless détecté dans certus_services"

    for svc_cls in service_classes:
        assert issubclass(svc_cls, BaseHeadlessService), (
            f"{svc_cls.__name__} doit hériter de BaseHeadlessService"
        )
        base = svc_cls.__name__.removesuffix("Service")
        req_name = f"{base}Request"
        resp_name = f"{base}Response"
        req_cls = getattr(cs, req_name, None)
        resp_cls = getattr(cs, resp_name, None)
        assert inspect.isclass(req_cls), f"Type requis manquant: {req_name}"
        assert inspect.isclass(resp_cls), f"Type requis manquant: {resp_name}"
        assert issubclass(req_cls, BaseHeadlessRequest), (
            f"{req_name} doit hériter de BaseHeadlessRequest"
        )
        assert issubclass(resp_cls, BaseHeadlessResponse), (
            f"{resp_name} doit hériter de BaseHeadlessResponse"
        )

        fit_sig = inspect.signature(svc_cls.fit)
        assert list(fit_sig.parameters.keys()) == ["self", "request"], (
            f"Signature fit invalide pour {svc_cls.__name__}"
        )
