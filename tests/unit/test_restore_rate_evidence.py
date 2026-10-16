"""A compact evidence archive must remain verifiable and never overwrite another result."""

from __future__ import annotations

import gzip
import hashlib

import pytest

from scripts.restore_rate_evidence import digest, restore_one, safe_path


@pytest.fixture
def evidence(tmp_path):
    directory = tmp_path / "reports"
    directory.mkdir()
    data = b'{"measurement": [1.0, 2.0, 3.0]}\r\n'
    archive = directory / "evidence.json.gz"
    archive.write_bytes(gzip.compress(data, mtime=0))
    entry = {"raw_path": "reports/raw.json", "gzip_path": "reports/evidence.json.gz",
             "raw_bytes": len(data), "raw_sha256": hashlib.sha256(data).hexdigest(),
             "gzip_sha256": digest(archive)}
    return tmp_path, data, entry


def test_restoration_preserves_the_original_bytes_and_is_idempotent(evidence):
    root, data, entry = evidence
    assert restore_one(root, entry)
    assert (root / entry["raw_path"]).read_bytes() == data
    assert not restore_one(root, entry)
    assert not list(root.rglob("*.restoring"))


def test_verification_checks_the_archive_without_creating_a_raw_file(evidence):
    root, _, entry = evidence
    assert not restore_one(root, entry, verify_only=True)
    assert not (root / entry["raw_path"]).exists()


def test_a_different_existing_result_is_preserved(evidence):
    root, _, entry = evidence
    raw = root / entry["raw_path"]
    raw.write_bytes(b"another result")
    with pytest.raises(FileExistsError):
        restore_one(root, entry)
    assert raw.read_bytes() == b"another result"


@pytest.mark.parametrize("name", ["../outside.json", "docs/ETAT.md", "/outside.json"])
def test_an_evidence_path_cannot_leave_reports(tmp_path, name):
    with pytest.raises(ValueError, match="inside reports"):
        safe_path(tmp_path, name)


def test_a_corrupt_archive_is_rejected_before_any_restoration(evidence):
    root, _, entry = evidence
    (root / entry["gzip_path"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Archive identity"):
        restore_one(root, entry)
    assert not (root / entry["raw_path"]).exists()


def test_a_wrong_decompressed_checksum_leaves_no_partial_result(evidence):
    root, _, entry = evidence
    entry["raw_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Decompressed"):
        restore_one(root, entry)
    assert not (root / entry["raw_path"]).exists()
    assert not list(root.rglob("*.restoring"))


def test_evidence_can_stay_in_an_explicit_external_archive(evidence, tmp_path):
    archive_root, data, entry = evidence
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    assert restore_one(checkout, entry, archive_root=archive_root)
    assert (checkout / entry["raw_path"]).read_bytes() == data
    assert (archive_root / entry["gzip_path"]).exists()
