"""A compact evidence archive must remain verifiable and never overwrite another result."""

from __future__ import annotations

import gzip
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.restore_rate_evidence import digest, restore_one, safe_path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "restore_rate_evidence.py"
#: An evidence file that the tracked manifests really list (the example of the README of the publication).
LISTED = "reports/STRAT_Rate_suite_2026-10-15/R5_integration/native/measurement/pipeline_trace.json"


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


def test_a_renamed_parent_folder_does_not_hide_the_archive(tmp_path):
    """The path recorded on 2026-10-16 names a parent folder that has since been renamed (drivefl -> drivfl).

    The archive is still next to the clone: the folder of the same name is found above it. Every file is checked
    against its SHA-256 afterwards, so a wrong folder of that name is refused, not trusted.
    """
    from scripts.restore_rate_evidence import locate_archive_root

    base = tmp_path / "couches"
    archive = base / "Archives_CERTUS_20261016"
    archive.mkdir(parents=True)
    clone = base / "CERTUS" / "certus0310"
    clone.mkdir(parents=True)
    recorded = tmp_path / "former_name" / "couches" / "Archives_CERTUS_20261016"  # does not exist any more

    assert locate_archive_root(recorded, clone) == archive
    assert locate_archive_root(archive, clone) == archive  # the recorded folder, when it exists, is kept


def test_an_archive_that_is_nowhere_is_reported_as_missing(tmp_path):
    from scripts.restore_rate_evidence import locate_archive_root

    clone = tmp_path / "CERTUS" / "certus0310"
    clone.mkdir(parents=True)
    assert locate_archive_root(tmp_path / "gone" / "Archives_CERTUS_20261016", clone) is None


def test_a_missing_archive_root_stops_with_a_message_not_a_traceback(tmp_path):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--verify-only", "--path", LISTED,
         "--archive-root", str(tmp_path / "nowhere" / "Archive_that_exists_nowhere")],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 2, run.stderr[-1500:]
    assert "archive root not found" in run.stderr
    assert "Traceback" not in run.stderr
