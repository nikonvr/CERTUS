"""Native-backend 109-layer pilot, judged with the archived independent protocol."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

os.environ.update(SEARCH_TARGET="threeline", SEARCH_NH="2.35", OPENBLAS_NUM_THREADS="1")
ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_v2"
BEFORE = ROOT / "reports/A2_preparation_calculs_2026-11-05/pilote_109"
sys.path[:0] = [str(ROOT), str(CAMPAIGN)]

import field_grid_link as fl  # noqa: E402
import grid_study as gs  # noqa: E402
import numpy as np  # noqa: E402

from certus.physics.design_resonances import (  # noqa: E402
    ResonanceSettings,
    TransmissionBand,
    TransmissionProblem,
    analyze_resonances,
    refine_resonances,
)


def encode(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "pilote_natif_109")
    parser.add_argument("--mode", choices=("charge", "nominal"), default="charge")
    args = parser.parse_args()
    out = args.out
    out.mkdir(exist_ok=False)
    initial = json.loads((BEFORE / "initial_design.json").read_text())
    seq = initial["seq"]
    d = np.array([float(v) for v in initial["d_nm"].split()])
    problem = TransmissionProblem(np.array([fl.N_IDX[m] for m in seq]), 1.52,
                                  tuple(TransmissionBand(a, b, t) for a, b, t in gs.s._bands))
    settings = ResonanceSettings(rounds=40, burst=30, max_ot_nm=15000.,
                                 height_threshold=1. if args.mode == "nominal" else 1e-3)
    reference_path = ROOT.parents[1] / "OE_resonances/code/hidden_resonances.py"
    sources = [Path(__file__).resolve(), reference_path,
               ROOT / "certus/physics/design_resonances.py", ROOT / "certus/core/certus_design_resonances.py",
               ROOT / "certus/physics/certus_tmm_oblique.py", ROOT / "certus/physics/design_fast_gauss_newton.py",
               BEFORE / "initial_design.json", BEFORE / "nominal_rounds.csv"]
    manifest = {"mode": args.mode, "settings": asdict(settings), "python": sys.version,
                "executable": sys.executable, "versions": {m: version(m) for m in ("numpy", "scipy", "numba")},
                "sources_sha256":
                {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def progress(rnd, analysis):
        print(f"round {rnd}: nominal {100 * analysis.nominal_mf:.6g} %, "
              f"charged {100 * analysis.charged_mf:.6g} %, {len(analysis.charged_peaks)} peaks", flush=True)

    result = refine_resonances(problem, d, settings=settings, progress=progress)
    spec = importlib.util.spec_from_file_location("submitted_a1_reference", reference_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    wl, target = problem.grid()
    reference_nominal = reference.merit(problem.indices, result.thicknesses, wl, target)
    assert abs(reference_nominal - 100 * result.final.nominal_mf) < 1e-8
    reference_counts = [reference.count_poles(problem.indices, result.thicknesses, b.lower_nm, b.upper_nm)
                        for b in problem.bands]
    assert reference_counts == [c.counted for c in result.final.counts]
    payload = asdict(result)
    (out / "native_result.json").write_text(json.dumps(payload, default=encode, indent=2) + "\n")
    rows = []
    for rnd, (analysis, state) in enumerate(zip(result.history, result.round_thicknesses, strict=True)):
        row = {"round": rnd, "mf_nominal": 100 * analysis.nominal_mf, "mf_tracked": 100 * analysis.charged_mf,
               "mf_resolved": gs.mf(seq, state, gs.GRIDS["resolved"]),
               "mf_check": gs.mf(seq, state, gs.GRIDS["check"]), "seq": seq,
               "d_nm": " ".join(format(v, ".17g") for v in state)}
        rows.append(row)
    csv_name = "nominal_rounds.csv" if args.mode == "nominal" else "height_rounds.csv"
    with (out / csv_name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    selected = rows[result.selected_round]
    diagnostic = analyze_resonances(problem, result.thicknesses, settings=ResonanceSettings())
    fields = [{"wavelength_nm": p.peak_wavelength_nm, "height": p.height,
               "e2max_at_this_peak": fl.e2max(problem.indices.real, result.thicknesses, p.peak_wavelength_nm)[0]}
              for p in diagnostic.charged_peaks]
    summary = {"selected_round": result.selected_round, "selected_state": selected,
               "ot_nm": float(result.thicknesses @ problem.indices.real), "fields_at_charged_peaks": fields,
               "counts_before": [asdict(c) for c in result.initial.counts],
               "counts_after": [asdict(c) for c in result.final.counts],
               "mode": args.mode, "reference_nominal_percent": reference_nominal,
               "reference_counts": reference_counts,
               "pairing": "Same input, native backend and prescribed limits; nominal mode disables peak charges."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("NATIVE_PILOT=GO", json.dumps({"mode": args.mode, "selected_round": result.selected_round,
                                        "nominal": selected["mf_nominal"], "resolved": selected["mf_resolved"],
                                        "check": selected["mf_check"], "ot_nm": summary["ot_nm"],
                                        "fields": fields, "reference_counts": reference_counts}), flush=True)


if __name__ == "__main__":
    main()
