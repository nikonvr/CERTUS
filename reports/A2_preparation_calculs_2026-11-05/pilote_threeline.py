"""Controlled A2 pilot using the submitted A1 reference and existing CERTUS kernels.

Run from any directory; --out must be a new directory. This runs one design,
sequentially, with an equal-burst nominal control. No archive is overwritten.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_v2"
A1 = ROOT.parents[1] / "OE_resonances/code"

# Set the complete protocol before any campaign or numerical-library import.
os.environ.update(SEARCH_TARGET="threeline", SEARCH_NH="2.35", TRACK_DETECT="complex",
                  TRACK_STEPS="localmax", TRACK_MULTISTART="dense", TRACK_PEAK="top",
                  OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
sys.path[:0] = [str(CAMPAIGN), str(ROOT)]

import numpy as np  # noqa: E402
import threeline_track as tr  # noqa: E402


def load_reference():
    spec = importlib.util.spec_from_file_location("submitted_a1_reference", A1 / "hidden_resonances.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def state(row):
    return row["seq"], np.array([float(value) for value in row["d_nm"].split()])


def admissible_rounds(rows, ot_max):
    """Budget applies to retained states, not to the optimizer's intermediate trajectory."""
    feasible = []
    for row in rows:
        seq, d = state(row)
        if (len(seq) == len(d) and np.isfinite(d).all() and (d >= tr.gs.FLOOR).all()
                and tr.gs.s.total_ot(seq, d) <= ot_max):
            feasible.append(row)
    if not feasible:
        raise RuntimeError("no retained round satisfies the declared thickness budget")
    return feasible


def audit(reference, seq, d):
    """Count all poles in the same rectangle before the charge's height/width filters."""
    ns = [tr.fl.N_IDX[m] for m in seq]
    bands = [(a, b) for a, b, _target in tr.gs.s._bands]
    def target_fn(lam):
        return float(tr.target([lam])[0])

    all_poles = reference.find_poles(ns, d, bands, target_fn, max_fwhm=10.0, min_height=0.0)
    counts = []
    for a, b in bands:
        found = int(sum(a < (1.0 / pole).real < b and -0.25 < (1.0 / pole).imag < 0.0
                        for _lam, _fw, _height, pole in all_poles))
        counted = reference.count_poles(ns, d, a, b)
        counts.append({"a_nm": a, "b_nm": b, "imag_min_nm": -0.25, "found": found, "counted": counted})
    native = tr.poles(seq, d)
    relevant = reference.find_poles(ns, d, bands, target_fn)
    native_lam = sorted(p[0] for p in native)
    oracle_lam = sorted(p[0] for p in relevant)
    location_agrees = len(native_lam) == len(oracle_lam) and np.allclose(native_lam, oracle_lam, rtol=0, atol=1e-6)
    charged = []
    for lam, fw, _height, pole in native:
        top = tr.top(seq, d, lam, fw)
        oracle_top = reference.top_of_peak(ns, d, lam, fw, target_fn)
        native_height = float(abs(tr.err(seq, d, [top])[0]))
        oracle_height = abs(float(reference.transmittance(ns, d, [oracle_top])[0]) - target_fn(oracle_top))
        charged.append({"pole_lambda_nm": lam, "pole_fwhm_nm": fw, "peak_lambda_nm": top,
                        "peak_height": native_height, "reference_peak_lambda_nm": oracle_top,
                        "reference_peak_height": oracle_height,
                        "e2max_at_this_peak": tr.fl.e2max(ns, d, top)[0],
                        "sigma_real": pole.real, "sigma_imag": pole.imag})
    wl = 2 * np.pi / tr.NOM["k0"]
    native_t = tr.bg.res_jac(seq, d, tr.NOM)[0] / tr.W_NOM + tr.NOM["tgt"]
    oracle_t = reference.transmittance(ns, d, wl)
    diff = float(np.max(np.abs(native_t - oracle_t)))
    top_agrees = all(abs(p["peak_lambda_nm"] - p["reference_peak_lambda_nm"]) < 1e-6
                     and abs(p["peak_height"] - p["reference_peak_height"]) < 1e-9 for p in charged)
    return {"layers": len(d), "ot_nm": tr.gs.s.total_ot(seq, d),
            "nominal_native_reference_max_abs_T": diff,
            "pole_locations_agree": bool(location_agrees), "peak_tops_agree": bool(top_agrees),
            "counts": counts, "charged_peaks": charged,
            "field_scope": "Only the charged real maxima, not a global maximum over wavelength.",
            "validated": bool(diff < 5e-11 and location_agrees and top_agrees
                              and all(r["found"] == r["counted"] for r in counts))}


def manifest(source, args):
    paths = [Path(__file__), source, A1 / "hidden_resonances.py", A1 / "three_line_101_recreated.csv",
             ROOT / "pyproject.toml", ROOT / "requirements.lock"]
    paths += [CAMPAIGN / f"{name}.py" for name in ("search", "cissoid_opt", "complex_plane_detect", "field_grid_link",
                                                 "bs5050_grid", "grid_study", "threeline_track")]
    paths += [ROOT / "certus/physics" / f"{name}.py" for name in ("design_fast_gauss_newton", "design_fast_normal")]
    return {"argv": sys.argv, "python": sys.version, "executable": sys.executable,
            "versions": {name: version(name) for name in ("numpy", "scipy", "numba")},
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "parameters": vars(args), "protocol": {key: os.environ[key] for key in
                ("SEARCH_TARGET", "SEARCH_NH", "TRACK_DETECT", "TRACK_STEPS", "TRACK_MULTISTART", "TRACK_PEAK")},
            "files_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "selection": "Minimum own objective among admissible rounds including round zero; identical burst limits.",
            "budget_scope": "Retained states only; intermediate optimizer states are not OT-constrained."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(CAMPAIGN / "gradual_deep2_cont_seed89_clean2.csv"))
    parser.add_argument("--pick", default="best", help="best by mf_oracle, or zero-based CSV row")
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--ot-max", type=float, default=15000.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.rounds < 0 or not np.isfinite(args.ot_max) or args.ot_max <= 0:
        parser.error("rounds must be nonnegative and ot-max finite and positive")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = Path(args.source).resolve()
    write_json(out / "manifest.json", manifest(source, args))
    reference = load_reference()
    rows101 = read_rows(A1 / "three_line_101_recreated.csv")
    seq101 = "".join(row["material"] for row in rows101)
    d101 = np.array([float(row["thickness_nm"]) for row in rows101])
    check101 = audit(reference, seq101, d101)
    write_json(out / "reference_101.json", check101)
    if not check101["validated"]:
        raise RuntimeError("A1 reference audit failed; pilot not started")
    print("REFERENCE_101=GO", flush=True)
    source_rows = read_rows(source)
    row = min(source_rows, key=lambda r: float(r["mf_oracle"])) if args.pick == "best" else source_rows[int(args.pick)]
    seq, d = state(row)
    admissible_rounds([row], args.ot_max)
    if len(seq) > 120:
        raise RuntimeError("input is outside the declared maximum of 120 layers")
    write_json(out / "initial_design.json", row)
    before = audit(reference, seq, d)
    write_json(out / "before.json", before)
    if not before["validated"]:
        raise RuntimeError("initial independent audit failed; pilot not started")
    summary = {"initial": before, "arms": {}}
    for mode in ("nominal", "height"):
        print(f"START {mode}: {len(d)} layers, {args.rounds} rounds", flush=True)
        rounds = tr.track(mode, seq, d.copy(), rounds=args.rounds, log=True, precise=True)
        write_csv(out / f"{mode}_rounds.csv", rounds)
        feasible = admissible_rounds(rounds, args.ot_max)
        best = min(feasible, key=lambda r: float(r["mf_tracked"]))
        seq_best, d_best = state(best)
        checked = audit(reference, seq_best, d_best)
        write_json(out / f"{mode}_selected_audit.json", checked)
        summary["arms"][mode] = {"selected_round": best["round"], "inadmissible_rounds": len(rounds) - len(feasible),
                                  "rounds": len(rounds), "selected_state": best, "audit": checked,
                                  "resolved_check_relative_difference": abs(float(best["mf_check"])
                                                                            / float(best["mf_resolved"]) - 1)}
        write_json(out / "summary.json", summary)
        if not checked["validated"]:
            raise RuntimeError(f"{mode}: independent audit failed; no validated conclusion")
    print("PILOT=GO (see summary.json; grid convergence is reported separately)", flush=True)


if __name__ == "__main__":
    main()
