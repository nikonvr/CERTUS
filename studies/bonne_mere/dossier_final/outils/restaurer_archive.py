"""Restore preserved text/source bytes on explicit demand, without any computation.

Usage: python restaurer_archive.py --destination PATH [--prefix reports/campaign/]
Does not overwrite files, run launchers or restore omitted bulky simulations.
"""
import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    study = Path(__file__).resolve().parents[2]
    dest = Path(args.destination).resolve()
    archive = study / "archives/Bonne_Mere_sources_et_metadonnees.zip"
    count = 0
    with zipfile.ZipFile(archive) as z:
        index = json.loads(z.read("archive_index.json"))
        with tarfile.open(fileobj=io.BytesIO(z.read("sources_dedupliquees.tar.xz")), mode="r:xz") as tar:
            contents = {entry.name: tar.extractfile(entry).read() for entry in tar if entry.isfile()}
        for name, record in index.items():
            if not name.startswith(args.prefix):
                continue
            parts = PurePosixPath(name)
            if parts.is_absolute() or ".." in parts.parts or ":" in name or "\\" in name:
                raise ValueError(f"Unsafe archived path: {name}")
            path = (dest / Path(*parts.parts)).resolve()
            if not path.is_relative_to(dest):
                raise ValueError(f"Path escapes destination: {name}")
            data = contents[record["stored_path"]]
            assert hashlib.sha256(data).hexdigest() == record["sha256"], name
            if path.exists():
                assert path.is_file() and path.read_bytes() == data, f"Will not overwrite {path}"
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            count += 1
    print(json.dumps({"restored_original_paths": count, "destination": str(dest), "optical_calculation": False}))


if __name__ == "__main__":
    main()
