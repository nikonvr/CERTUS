"""Apply solid LZMA compression to deduplicated archival sources."""
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

study = Path(__file__).resolve().parents[2]
archives = study / "archives"
final = study / "dossier_final"
source = archives / "Bonne_Mere_archive_compacte.zip"
solid = archives / "sources_dedupliquees.tar.xz"
with zipfile.ZipFile(source) as z:
    index = json.loads(z.read("archive_index.json"))
    stored = {item["stored_path"]: item for item in index.values()}
    with tarfile.open(solid, "w:xz", preset=7) as tar:
        for name in stored:
            data = z.read(name)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 1792288800
            tar.addfile(info, io.BytesIO(data))
with tarfile.open(solid, "r:xz") as tar:
    hashes = {}
    for entry in tar:
        assert entry.isfile()
        data = tar.extractfile(entry).read()
        hashes[entry.name] = hashlib.sha256(data).hexdigest()
    for name, record in index.items():
        assert hashes[record["stored_path"]] == record["sha256"], name
out_path = archives / "Bonne_Mere_sources_finales.zip"
with zipfile.ZipFile(out_path, "w") as z:
    z.write(solid, "sources_dedupliquees.tar.xz", compress_type=zipfile.ZIP_STORED)
    z.writestr("archive_index.json", json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
with zipfile.ZipFile(out_path) as z:
    assert z.testzip() is None
manifest_path = final / "inventaire_avant_reduction.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["archive_sha256"] = hashlib.sha256(out_path.read_bytes()).hexdigest()
manifest["archive_bytes"] = out_path.stat().st_size
manifest["archive"] = "archives/Bonne_Mere_sources_et_metadonnees.zip"
manifest["archive_storage"] = "ZIP contains sources_dedupliquees.tar.xz (solid LZMA) plus archive_index.json. Use restaurer_archive.py for original paths and aliases."
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with zipfile.ZipFile(archives / "Bonne_Mere_inventaire_avant_reduction.zip", "w", zipfile.ZIP_LZMA) as z:
    z.write(manifest_path, manifest_path.name)
print(json.dumps({"final_zip_bytes": out_path.stat().st_size, "unique_entries": len(stored), "original_paths": len(index), "all_original_hashes_verified": True}), flush=True)
