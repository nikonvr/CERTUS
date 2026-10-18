"""Preserve compact research evidence before the authorized size cleanup.

Only metadata, hashing and ZIP operations. No optical import or deletion.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

FINAL = Path(__file__).resolve().parents[1]
STUDY = FINAL.parent
ROOT = STUDY.parents[1]
ARCHIVES = STUDY / "archives"
TEXT = {".json", ".jsonl", ".md", ".py", ".txt", ".log", ".toml", ".yaml", ".yml"}
ORIGINAL_TOP = {"code_certus", "design", "materials", "reports", "runtime_ui_support", "scripts", "sources", "target"}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ARCHIVES.mkdir(exist_ok=True)
    assert (FINAL / "Bonne_Mere_Dossier_Complet.docx").is_file()
    assert (FINAL / "donnees/preuves_appariees_452nm_3graines.npz").is_file()
    files = sorted(p for p in STUDY.rglob("*") if p.is_file() and p.relative_to(STUDY).parts[0] not in {"dossier_final", "archives"})
    archive = ARCHIVES / "Bonne_Mere_sources_et_metadonnees.zip"
    inventory = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as out:
        for path in files:
            rel = path.relative_to(STUDY)
            parts = rel.parts
            preserve = (parts[0] in ORIGINAL_TOP and (path.suffix.lower() in TEXT or parts[0] in {"sources", "target", "materials"} or (parts[0] == "design" and path.suffix.lower() == ".csv") or path.name in {"selected_deposition_plan.csv", "source_document_spectrum.csv"}))
            preserve = preserve and not any(x in parts for x in {"__pycache__", ".pytest_cache", ".ruff_cache", "cache_numba"})
            if len(parts) == 1 and path.suffix.lower() in {".md", ".json"}:
                preserve = True
            item = {"path": rel.as_posix(), "bytes": path.stat().st_size,
                    "preserved_in_zip": preserve,
                    "raw_arrays_compacted_separately": rel.as_posix().startswith("reports/strat70_lambda4_2026-10-18/attempt_01/case_") and any(f"case_{n:06d}/" in rel.as_posix() for n in [130, 131, 135, 136, 140, 141]) and path.suffix.lower() in {".npz", ".gz"}}
            if preserve:
                item["sha256"] = sha(path)
                out.write(path, rel.as_posix())
            inventory.append(item)
        # Explicitly preserve the old project resumption text, before updating it.
        out.write(ROOT / "docs/ETAT.md", "contexte_projet/ETAT_avant_cloture.md")
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        for item in inventory:
            if item["preserved_in_zip"]:
                assert hashlib.sha256(check.read(item["path"])).hexdigest() == item["sha256"]
    manifest = {"date": "2026-10-18", "archive": archive.relative_to(STUDY).as_posix(),
                "archive_sha256": sha(archive), "archive_bytes": archive.stat().st_size,
                "zip_crc_and_all_original_entry_sha256": "PASS",
                "inventory": inventory,
                "original_total_bytes": sum(x["bytes"] for x in inventory),
                "retained_original_files": sum(x["preserved_in_zip"] for x in inventory),
                "original_files": len(inventory),
                "scope": "Compact archive within certus0310. Not a full backup of all raw candidate simulations.",
                "authorization": "Fabien requested closing Bonne Mere, cleaning the research and keeping certus0310 under 1000000000 bytes INCLUDING Bonne Mere; no external archive.",
                "candidate452_evidence": "donnees/preuves_appariees_452nm_3graines.npz contains lossless physical98, validity, RMSE and SEEL for all six paired confirmation cohorts.",
                "omitted": "Other raw NPZ, native pickle, NPY, bulk per-case CSV, caches, old rendered outputs and temporary artifacts are removed by the separate reviewed PowerShell cleanup."}
    (FINAL / "inventaire_avant_reduction.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Inventory can be large; compress it too while retaining a short visible manifest.
    inventory_path = FINAL / "inventaire_avant_reduction.json"
    with zipfile.ZipFile(ARCHIVES / "Bonne_Mere_inventaire_avant_reduction.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        out.write(inventory_path, inventory_path.name)
    print(json.dumps({k: v for k, v in manifest.items() if k != "inventory"}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
