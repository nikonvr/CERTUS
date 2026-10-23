"""Re-optimize the Bonne Mère design with the levers of the 2026-10-22/23 DESIGN campaign.

    python reports/BONNE_MERE_design_2026-10-23/reoptimize.py --study STUDY [--max-layers 110] [--budget-min 120]
        [--substrate-id 0] [--tag _silica] [--start FILE]

STUDY is the study restored from studies/bonne_mere/archives (dossier_final/outils/restaurer_archive.py): its
scripts/local_comparisons.py gives the optics of the retained design (H800 Nb2O5 / SiO2 on catalogue sapphire 3,
incoherent back side, the 601-point retained target), which reproduces the reference 1.4590693866 pp.
Levers, each judged on that RMSE (percentage points):
  1. free polish of the 96 retained layers (lower bound 0 instead of 5 nm);
  2. floor at the end (owner's practice): layers under 5 nm raised to 5 nm, polish bounded below by 5 nm;
  3. growth by needle pairs up to --max-layers (owner: at most 110): the best split of a layer by a 1 nm layer
     of the other material, free polish, floor at the end, one row per layer count;
  4. basin hopping (thicknesses x (1 + 0.03 N(0,1)), free polish, floor) around the best design while time remains.
Writes results.jsonl and best_design.json next to this file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("NUMBA_NUM_THREADS", "8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FLOOR_NM = 5.0
MAX_NM = 1000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", type=Path, required=True)
    ap.add_argument("--max-layers", type=int, default=110)
    ap.add_argument("--budget-min", type=float, default=120.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--substrate-id", type=int, default=None, help="catalogue id (0 fused silica, 3 sapphire)")
    ap.add_argument("--tag", default="", help="suffix of results.jsonl and best_design.json")
    ap.add_argument("--start", type=Path, default=None, help="start design (thickness_nm, material_indices); default: the retained one")
    args = ap.parse_args()
    sys.path.insert(0, str(REPO))
    sys.path.insert(1, str(args.study / "scripts"))
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    import numpy as np
    from local_comparisons import VariantModel
    from scipy.optimize import minimize

    from certus.physics.gradient_oblique import compute_oblique_backside_bundle_analytic

    t_start = time.monotonic()
    design = json.loads((REPO / "studies/bonne_mere/dossier_final/donnees/design_retenu_96_saphir.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(args.seed)
    substrate_id = design["substrate_id"] if args.substrate_id is None else args.substrate_id
    out = HERE / f"results{args.tag}.jsonl"

    class Problem:
        def __init__(self, symbols):
            self.symbols = np.asarray(symbols, dtype=np.int64)
            self.model = VariantModel(self.symbols, substrate_id, design["target_upper_nm"])
            self.var = np.arange(len(self.symbols), dtype=np.int64)
            self.calls = 0

        def rmse_pp(self, ep) -> float:
            _, t = self.model.spectrum(np.asarray(ep, dtype=np.float64))
            return float(100.0 * np.sqrt(np.mean((t - self.model.target) ** 2)))

        def cost_grad(self, ep):
            self.calls += 1
            _, _, t, jac = compute_oblique_backside_bundle_analytic(np.ascontiguousarray(ep, dtype=np.float64), self.model.layers,
                                                                   self.model.substrate, self.model.wls, self.var, 0.0, True)
            r = t - self.model.target
            return float(np.mean(r * r)), (2.0 / len(r)) * (np.asarray(jac).T @ r)

        def polish(self, ep, lower: float, maxiter: int = 400):
            res = minimize(self.cost_grad, np.clip(np.asarray(ep, dtype=float), lower, MAX_NM), jac=True, method="L-BFGS-B",
                           bounds=[(lower, MAX_NM)] * len(ep), options={"maxiter": maxiter, "ftol": 1e-14, "gtol": 1e-10})
            return np.asarray(res.x)

        def floor_at_end(self, ep):
            return self.polish(np.maximum(ep, FLOOR_NM), FLOOR_NM)

    def record(stage: str, prob: Problem, ep) -> float:
        value = prob.rmse_pp(ep)
        row = {"stage": stage, "layers": len(ep), "rmse_pp": value, "thinnest_nm": float(np.min(ep)),
               "total_nm": float(np.sum(ep)), "minutes": round((time.monotonic() - t_start) / 60.0, 1),
               "calls": prob.calls, "ep": [round(float(x), 4) for x in ep],
               "symbols": [int(s) for s in prob.symbols]}
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{stage:28s} layers={len(ep):3d} rmse={value:.6f} pp thinnest={np.min(ep):7.3f} nm t={row['minutes']} min", flush=True)
        return value

    def time_left() -> bool:
        return (time.monotonic() - t_start) / 60.0 < args.budget_min

    start = design if args.start is None else json.loads(args.start.read_text(encoding="utf-8"))
    ep0 = np.asarray(start["thickness_nm"], dtype=float)
    prob = Problem(start["material_indices"])
    best = (record("0 retained (reference)", prob, ep0), ep0, prob)

    free = prob.polish(ep0, 0.0)
    record("1 free polish", prob, free)
    floored = prob.floor_at_end(free)
    value = record("2 floor at the end", prob, floored)
    if value < best[0]:
        best = (value, floored, prob)

    import importlib.util

    from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact

    # The study's scripts load its frozen copy of CERTUS (code_certus), whose optics give the reference 1.459 pp;
    # the cached back-side needle scan is newer, so it is loaded from this repository's file.
    spec = importlib.util.spec_from_file_location("repo_certus_opt_needle", REPO / "certus/physics/certus_opt_needle.py")
    needle_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(needle_module)
    needle_scan_cached_backside = needle_module.needle_scan_cached_backside

    no_back, no_d = None, np.zeros(0)

    def needle(prob_, ep_, symbols_):
        """Best 1 nm needle every 2 nm with the cached back-side scan (DESIGN's kernel); the least harmful if none helps."""
        nonlocal no_back
        layers = np.ascontiguousarray(np.asarray(prob_.model.layers, dtype=np.complex128))
        col = {s: layers[:, k] for k, s in enumerate(symbols_)}
        needle_t = np.ascontiguousarray(np.stack([col[1 - s] for s in symbols_], axis=1))
        n_sub = np.ascontiguousarray(np.asarray(prob_.model.substrate, dtype=np.complex128))
        if no_back is None:
            no_back = np.zeros((layers.shape[0], 0), dtype=np.complex128)
        wls = np.asarray(prob_.model.wls, dtype=np.float64)
        _rf, tf, rfp, rbp, tb = calc_spectrum_full_exact(wls, np.asarray(ep_, dtype=float), layers, no_d, no_back, n_sub)
        t_full = tf * tb / np.maximum(1.0 - rfp * rbp, 1e-12)
        _, t_model = prob_.model.spectrum(np.asarray(ep_, dtype=float))
        assert np.max(np.abs(t_full - t_model)) < 1e-9, "the back-side model of the study and CERTUS disagree"
        t0 = time.perf_counter()
        layer, depth, _cost = needle_scan_cached_backside(wls, layers, needle_t, n_sub, np.asarray(ep_, dtype=float),
                                                          np.asarray(prob_.model.target, dtype=float), np.ones(len(wls)),
                                                          2.0, 1.0, np.ones(len(ep_), dtype=np.int64), rbp, tb)
        scan_s = time.perf_counter() - t0
        j, z = int(layer), float(depth)
        new_ep = np.concatenate([ep_[:j], [z, 1.0, ep_[j] - z], ep_[j + 1:]])
        new_sym = [*symbols_[:j], symbols_[j], 1 - symbols_[j], symbols_[j], *symbols_[j + 1:]]
        return new_ep, new_sym, scan_s

    ep, symbols = free.copy(), [int(s) for s in prob.symbols]
    while len(symbols) + 2 <= args.max_layers and time_left():
        cand = Problem(symbols)
        grown_ep, symbols, scan_s = needle(cand, ep, symbols)
        grown = Problem(symbols)
        ep = grown.polish(grown_ep, 0.0)
        record(f"3 grown free ({len(symbols)}, scan {scan_s:.2f} s)", grown, ep)
        floored = grown.floor_at_end(ep)
        value = record(f"3 grown + floor ({len(symbols)})", grown, floored)
        if value < best[0]:
            best = (value, floored, grown)

    hop = 0
    while time_left():
        hop += 1
        _value, ep_b, pb = best
        trial = ep_b * (1.0 + 0.03 * rng.standard_normal(len(ep_b)))
        free_t = pb.polish(trial, 0.0)
        floored = pb.floor_at_end(free_t)
        value = record(f"4 hop {hop}", pb, floored)
        if value < best[0]:
            best = (value, floored, pb)

    value, ep_b, pb = best
    (HERE / f"best_design{args.tag}.json").write_text(json.dumps({
        "n_layers": len(ep_b), "thickness_nm": [float(x) for x in ep_b], "material_indices": [int(s) for s in pb.symbols],
        "materials": design["materials"], "substrate_id": substrate_id, "target_upper_nm": design["target_upper_nm"],
        "rmse_percentage_points": value, "reference_rmse_percentage_points": design["reference_rmse_percentage_points"],
        "order": design["order"], "backside": design["backside"]}, indent=2), encoding="utf-8")
    print(f"BEST rmse={value:.6f} pp layers={len(ep_b)} (reference {design['reference_rmse_percentage_points']:.6f})", flush=True)


if __name__ == "__main__":
    main()
