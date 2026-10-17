"""Restore the SHA-verified, losslessly archived Rate evidence after a clone."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path

PUBLICATION = Path("reports/STRAT_Rate_publication_2026-10-16")


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024 * 1024):
            checksum.update(data)
    return checksum.hexdigest()


def safe_path(root: Path, name: str) -> Path:
    candidate = root / name
    if Path(name).is_absolute() or not candidate.resolve().is_relative_to((root / "reports").resolve()):
        raise ValueError(f"Evidence path must stay inside reports: {name}")
    return candidate


def restore_one(root: Path, entry: dict, *, verify_only: bool = False, archive_root: Path | None = None) -> bool:
    raw = safe_path(root, entry["raw_path"])
    archive = safe_path(archive_root if archive_root is not None else root, entry["gzip_path"])
    if raw == archive or digest(archive) != entry["gzip_sha256"]:
        raise ValueError("Archive identity mismatch")
    if raw.exists() and digest(raw) != entry["raw_sha256"]:
        raise FileExistsError(f"Existing evidence differs; preserve it: {raw}")
    if raw.exists() and not verify_only:
        return False
    temporary = raw.with_name(raw.name + ".restoring")
    output = None
    created = False
    try:
        if not verify_only:
            raw.parent.mkdir(parents=True, exist_ok=True)
            output = temporary.open("xb")
            created = True
        checksum = hashlib.sha256()
        total = 0
        with gzip.open(archive, "rb") as stream:
            while data := stream.read(1024 * 1024):
                checksum.update(data)
                total += len(data)
                if output is not None:
                    output.write(data)
        if checksum.hexdigest() != entry["raw_sha256"] or total != entry["raw_bytes"]:
            raise ValueError("Decompressed evidence identity mismatch")
        if output is not None:
            output.close()
            output = None
            # Hard-link creation refuses an existing destination atomically on every platform.
            os.link(temporary, raw)
        return not verify_only
    finally:
        if output is not None:
            output.close()
        if created:
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--path", help="Restore or verify only this exact repository-relative evidence path")
    parser.add_argument("--archive-root", type=Path, help="Local external archive root, overriding archive_location.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    entries = []
    for name in ("manifest.json", "compact_manifest.json", "historical_manifest.json"):
        manifest = root / PUBLICATION / name
        if manifest.exists():
            entries.extend(json.loads(manifest.read_text(encoding="utf-8"))["archives"])
    if args.path:
        entries = [entry for entry in entries if entry["raw_path"] == args.path]
    if not entries:
        parser.error("No matching archived evidence")
    archive_root = args.archive_root
    location = root / PUBLICATION / "archive_location.json"
    if archive_root is None and location.exists():
        archive_root = Path(json.loads(location.read_text(encoding="utf-8"))["archive_root"])
    restored = sum(restore_one(root, entry, verify_only=args.verify_only, archive_root=archive_root) for entry in entries)
    print(f"EVIDENCE=GO files={len(entries)} restored={restored} verify_only={args.verify_only}")


if __name__ == "__main__":
    main()
