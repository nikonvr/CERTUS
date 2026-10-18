"""Read-only integrity and retained-score audit. No optical imports or calculation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import numpy as np

FINAL = Path(__file__).resolve().parents[1]
STUDY = FINAL.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    for name, record in read(FINAL / "manifest_cloture.json")["files"].items():
        path = STUDY / name
        assert path.stat().st_size == record["bytes"], name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], name
    with zipfile.ZipFile(STUDY / "archives/Bonne_Mere_sources_et_metadonnees.zip") as z:
        assert z.testzip() is None
        index = json.loads(z.read("archive_index.json"))
        stored = {record["stored_path"]: record for record in index.values()}
        with tarfile.open(fileobj=io.BytesIO(z.read("sources_dedupliquees.tar.xz")), mode="r:xz") as tar:
            for entry in tar:
                assert entry.isfile() and entry.name in stored
                record = stored[entry.name]
                data = tar.extractfile(entry).read()
                assert len(data) == record["bytes"]
                assert hashlib.sha256(data).hexdigest() == record["sha256"], entry.name
    with (FINAL / "donnees/monitoring_retenu_98operations.csv").open(encoding="utf-8-sig", newline="") as stream:
        monitoring = list(csv.DictReader(stream, delimiter=";"))
    assert len(monitoring) == 98
    assert [float(x["wavelength_nm"]) for x in monitoring[:4]] == [452] * 4
    assert sum(x["mode"] == "Optique" for x in monitoring[2:]) == 70
    assert sum(x["mode"] == "Rate" for x in monitoring[2:]) == 26
    metrics = read(FINAL / "donnees/resultats_452nm.json")
    evidence = read(FINAL / "donnees/preuves_appariees_452nm_index.json")
    cohorts = {x["evaluation"]: x for x in evidence["cases"]}
    with np.load(FINAL / "donnees/preuves_appariees_452nm_3graines.npz", allow_pickle=False) as arrays:
        for number, cohort in cohorts.items():
            for noise, recorded in enumerate(cohort["summary"]["noise_results"]):
                prefix = f"case{number}_noise{noise}_"
                valid = arrays[prefix + "valid"].astype(bool)
                assert arrays[prefix + "physical98_nm"].shape == (1000, 98)
                assert len(valid) == recorded["runs"] == 1000
                assert np.count_nonzero(valid) == recorded["completed"]
                rmse = arrays[prefix + "target_rmse_pp"][valid]
                seel = arrays[prefix + "seel_nm"][valid]
                assert np.isclose(np.mean(rmse), recorded["target_rmse_mean_pp"], rtol=0, atol=2e-12)
                assert np.isclose(np.quantile(rmse, .95), recorded["target_rmse_p95_pp"], rtol=0, atol=2e-12)
                assert np.isclose(np.quantile(seel, .95), recorded["seel_p95_nm"], rtol=0, atol=2e-12)
        failures = []
        for noise, recorded in enumerate(metrics["candidate"]["pooled_statistics"]):
            valid = np.concatenate([arrays[f"case{n}_noise{noise}_valid"].astype(bool) for n in [131, 136, 141]])
            scores = np.concatenate([arrays[f"case{n}_noise{noise}_target_rmse_pp"] for n in [131, 136, 141]])[valid]
            assert np.isclose(np.mean(scores), recorded["target_rmse_mean_pp"], rtol=0, atol=2e-12)
            assert np.isclose(np.quantile(scores, .95), recorded["target_rmse_p95_pp"], rtol=0, atol=2e-12)
            failures.append(int(3000 - np.count_nonzero(valid)))
    assert failures == [0, 0, 1]
    print(json.dumps({"integrity": "PASS", "archived_original_paths": len(index), "unique_source_entries": len(stored),
                      "retained_confirmation_cohorts": 6, "retained_noise_arrays": 18,
                      "monitoring_operations": 98, "component_optical": 70, "component_rate": 26,
                      "first4_common_wavelength_nm": 452, "candidate_failures_per_noise": failures,
                      "independent_candidate_holdout": False, "optical_calculation": False}))


if __name__ == "__main__":
    main()
