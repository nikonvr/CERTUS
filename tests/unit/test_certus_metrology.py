"""Unit tests for certus_metrology primitives."""

from __future__ import annotations

import json

import pytest

from certus.core.certus_metrology import (
    RunContext,
    RunManifest,
    ValidationStatus,
    compute_params_hash,
)


@pytest.mark.unit
def test_compute_params_hash_is_deterministic_for_same_payload() -> None:
    payload_a = {"b": 2, "a": 1, "nested": {"x": [3, 4]}}
    payload_b = {"nested": {"x": [3, 4]}, "a": 1, "b": 2}
    assert compute_params_hash(payload_a) == compute_params_hash(payload_b)


@pytest.mark.unit
def test_run_context_create_captures_input_fingerprint(tmp_path) -> None:
    src = tmp_path / "spectrum.csv"
    src.write_text("lambda,T\n500,0.9\n", encoding="utf-8")

    ctx = RunContext.create(
        app_id="CERTUS_INDEX",
        app_version="26_01",
        seed=123,
        input_paths=[str(src)],
        params={"k": 1, "v": [1, 2]},
        warnings=["normalized input"],
        status=ValidationStatus.WARNING_DATA_NORMALIZED,
    )

    assert ctx.app_id == "CERTUS_INDEX"
    assert ctx.seed == 123
    assert ctx.status == ValidationStatus.WARNING_DATA_NORMALIZED
    assert len(ctx.input_fingerprints) == 1
    fp = ctx.input_fingerprints[0]
    assert fp.path.endswith("spectrum.csv")
    assert fp.size > 0
    assert len(fp.sha256) == 64
    assert ctx.params_hash


@pytest.mark.unit
def test_run_manifest_flat_dict_serializes_nested_values() -> None:
    ctx = RunContext.create(
        app_id="CERTUS_TEST",
        app_version="26_01",
        warnings=["w1", "w2"],
        status=ValidationStatus.OK,
    )
    manifest = RunManifest(run_context=ctx)
    flat = manifest.as_flat_dict()
    assert flat["status"] == "OK"
    # warnings are serialized as JSON in flat format
    assert json.loads(flat["warnings"]) == ["w1", "w2"]
