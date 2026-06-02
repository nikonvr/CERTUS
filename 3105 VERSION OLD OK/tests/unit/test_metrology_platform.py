"""Tests unitaires : certus_metrology — RunContext, Manifest, hashing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from certus.core.certus_metrology import (
    ValidationStatus,
    InputFingerprint,
    SoftwareEnv,
    RunContext,
    RunManifest,
    compute_params_hash,
    _sha256_file,
    _default_run_id,
    _get_version,
    _detect_locale,
    _detect_cpu_brand,
    _detect_threading_layer,
    _detect_pyqt_version,
)


# ── ValidationStatus ──


class TestValidationStatus:
    def test_ok_value(self) -> None:
        assert ValidationStatus.OK.value == "OK"

    def test_all_members_are_strings(self) -> None:
        for member in ValidationStatus:
            assert isinstance(member.value, str)

    def test_member_count(self) -> None:
        assert len(ValidationStatus) >= 5


# ── InputFingerprint ──


class TestInputFingerprint:
    def test_from_path(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        fp = InputFingerprint.from_path(str(f))
        assert fp.sha256
        assert fp.size == 11
        assert fp.path.endswith("test.txt")

    def test_sha256_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "det.txt"
        f.write_text("data", encoding="utf-8")
        fp1 = InputFingerprint.from_path(str(f))
        fp2 = InputFingerprint.from_path(str(f))
        assert fp1.sha256 == fp2.sha256


# ── SoftwareEnv ──


class TestSoftwareEnv:
    def test_detect(self) -> None:
        env = SoftwareEnv.detect()
        assert env.python
        assert env.numpy != ""
        assert env.os != ""

    def test_certus_version_present(self) -> None:
        env = SoftwareEnv.detect()
        assert env.certus_version


# ── RunContext ──


class TestRunContext:
    def test_create_minimal(self) -> None:
        ctx = RunContext.create(app_id="test", app_version="1.0")
        assert ctx.app_id == "test"
        assert ctx.run_id.startswith("run_")
        assert ctx.status == ValidationStatus.OK

    def test_create_with_seed(self) -> None:
        ctx = RunContext.create(app_id="test", app_version="1.0", seed=42)
        assert ctx.seed == 42

    def test_create_with_warnings(self) -> None:
        ctx = RunContext.create(
            app_id="test", app_version="1.0", warnings=["w1", "w2"]
        )
        assert len(ctx.warnings) == 2

    def test_create_with_params_hash(self) -> None:
        ctx = RunContext.create(
            app_id="test", app_version="1.0", params={"k": "v"}
        )
        assert ctx.params_hash != ""

    def test_create_with_input_paths(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n", encoding="utf-8")
        ctx = RunContext.create(
            app_id="test", app_version="1.0", input_paths=[str(f)]
        )
        assert len(ctx.input_fingerprints) == 1

    def test_create_with_nonexistent_input_paths(self) -> None:
        ctx = RunContext.create(
            app_id="test", app_version="1.0", input_paths=["/nonexistent/file.csv"]
        )
        assert len(ctx.input_fingerprints) == 0


# ── RunManifest ──


class TestRunManifest:
    def test_to_dict(self) -> None:
        ctx = RunContext.create(app_id="test", app_version="1.0")
        manifest = RunManifest(run_context=ctx)
        d = manifest.to_dict()
        assert "run_id" in d
        assert "status" in d
        assert d["status"] == "OK"

    def test_to_json(self) -> None:
        ctx = RunContext.create(app_id="test", app_version="1.0")
        manifest = RunManifest(run_context=ctx)
        j = manifest.to_json()
        parsed = json.loads(j)
        assert "run_id" in parsed

    def test_as_flat_dict(self) -> None:
        ctx = RunContext.create(app_id="test", app_version="1.0")
        manifest = RunManifest(run_context=ctx)
        flat = manifest.as_flat_dict()
        assert isinstance(flat, dict)
        assert "run_id" in flat


# ── compute_params_hash ──


class TestComputeParamsHash:
    def test_deterministic(self) -> None:
        h1 = compute_params_hash({"a": 1, "b": 2})
        h2 = compute_params_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_for_different_params(self) -> None:
        h1 = compute_params_hash({"a": 1})
        h2 = compute_params_hash({"a": 2})
        assert h1 != h2


# ── Helper functions ──


class TestHelperFunctions:
    def test_sha256_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hash.txt"
        f.write_text("test", encoding="utf-8")
        h = _sha256_file(str(f))
        assert len(h) == 64

    def test_default_run_id(self) -> None:
        rid = _default_run_id()
        assert rid.startswith("run_")

    def test_get_version_numpy(self) -> None:
        v = _get_version("numpy")
        assert v != "unknown"

    def test_get_version_nonexistent(self) -> None:
        v = _get_version("nonexistent_module_xyz")
        assert v == "unknown"

    def test_detect_locale(self) -> None:
        loc = _detect_locale()
        assert isinstance(loc, str)

    def test_detect_cpu_brand(self) -> None:
        brand = _detect_cpu_brand()
        assert isinstance(brand, str)

    def test_detect_threading_layer(self) -> None:
        layer = _detect_threading_layer()
        assert isinstance(layer, str)

    def test_detect_pyqt_version(self) -> None:
        v = _detect_pyqt_version()
        assert isinstance(v, str)
