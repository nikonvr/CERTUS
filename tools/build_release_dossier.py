#!/usr/bin/env python3
"""Build a release dossier archive scaffold (#54)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_release_dossier(version_tag: str) -> Path:
    reports_dir = Path("reports")
    out_dir = Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)

    staging = out_dir / f"release_dossier_{version_tag}"
    staging.mkdir(parents=True, exist_ok=True)

    _write_json(
        staging / "build_manifest.json",
        {
            "version_tag": version_tag,
            "notes": "Scaffold dossier. Add CI/test/benchmark snapshots incrementally.",
        },
    )

    changelog = reports_dir / "CERTUS_CHANGELOG_ROADMAP.md"
    if changelog.exists():
        (staging / "CHANGELOG_ROADMAP.md").write_text(changelog.read_text(encoding="utf-8"), encoding="utf-8")

    out_zip = out_dir / f"release_dossier_{version_tag}.zip"
    with zipfile.ZipFile(out_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in staging.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(staging))
    return out_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CERTUS release dossier zip.")
    parser.add_argument("version_tag", help="Version tag (e.g., v26.01.0)")
    args = parser.parse_args()

    out = build_release_dossier(args.version_tag)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
