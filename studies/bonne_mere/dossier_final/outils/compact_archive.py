"""Deduplicate archival bytes and preserve a mapping of every original path."""
import hashlib
import json
import zipfile
from pathlib import Path

study = Path(__file__).resolve().parents[2]
final = study / "dossier_final"
manifest = json.loads((final / "inventaire_avant_reduction.json").read_text(encoding="utf-8"))
source = study / "archives/Bonne_Mere_sources_et_metadonnees.zip"
target = study / "archives/Bonne_Mere_archive_compacte.zip"
index = {}
unique = {}
with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_LZMA) as new:
    for entry in old.infolist():
        data = old.read(entry.filename)
        digest = hashlib.sha256(data).hexdigest()
        canonical = unique.get(digest)
        if canonical is None:
            canonical = entry.filename
            unique[digest] = canonical
            new.writestr(canonical, data)
        index[entry.filename] = {"stored_path": canonical, "sha256": digest, "bytes": len(data)}
    new.writestr("archive_index.json", json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8"))
with zipfile.ZipFile(target) as check:
    assert check.testzip() is None
    for name, item in index.items():
        assert hashlib.sha256(check.read(item["stored_path"])).hexdigest() == item["sha256"], name
manifest["archive"] = target.relative_to(study).as_posix()
manifest["archive_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
manifest["archive_bytes"] = target.stat().st_size
manifest["archive_storage"] = "ZIP LZMA with exact-byte deduplication; archive_index.json maps every original path to its stored entry. Use restaurer_archive.py to restore aliases."
manifest["archive_unique_entries"] = len(unique)
(final / "inventaire_avant_reduction.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with zipfile.ZipFile(study / "archives/Bonne_Mere_inventaire_avant_reduction.zip", "w", zipfile.ZIP_LZMA) as out:
    out.write(final / "inventaire_avant_reduction.json", "inventaire_avant_reduction.json")
print(json.dumps({"archive_bytes": target.stat().st_size, "original_entries": len(index), "unique_entries": len(unique), "sha256": manifest["archive_sha256"], "every_restored_path_verified": True}), flush=True)
