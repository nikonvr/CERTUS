from __future__ import annotations

from certus.utils.certus_dto import BaseHeadlessRequestModel, IndexFitRequestModel


def test_base_headless_request_model_accepts_run_id() -> None:
    dto = BaseHeadlessRequestModel(config={"a": 1}, run_id="run-123")

    assert dto.run_id == "run-123"
    assert dto.source_paths == []
    assert dto.status == "OK"


def test_index_fit_request_model_inherits_run_id_field() -> None:
    dto = IndexFitRequestModel(config={"a": 1}, run_id="index-run")

    assert dto.app_id == "CERTUS_INDEX"
    assert dto.run_id == "index-run"
