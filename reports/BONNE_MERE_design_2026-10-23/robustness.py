"""Robustness of the Bonne Mere candidates to thickness errors: RMSE (pp) over seeded random draws.

Each draw adds an independent error to every layer. All designs see the same draws (one matrix of
errors, the first n columns for an n-layer design), so their ranking does not depend on luck.
Candidates: the best compliant rows (thinnest >= 5 nm) of each results*.jsonl given, plus design files.
The study modules redirect stdout: the table goes to --out.

python reports/BONNE_MERE_design_2026-10-23/robustness.py --study STUDY --out FILE --jsonl results_silica_98.jsonl ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_NUM_THREADS", "8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAWS = {"gauss_sigma_0.4": ("normal", 0.4), "gauss_2sigma_0.4": ("normal", 0.2), "uniform_pm_0.4": ("uniform", 0.4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jsonl", nargs="*", default=[])
    ap.add_argument("--design", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=15, help="best compliant rows taken from each jsonl")
    ap.add_argument("--substrate-id", type=int, default=0)
    ap.add_argument("--draws", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    sys.path.insert(0, str(REPO))
    sys.path.insert(1, str(args.study / "scripts"))
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    import numpy as np
    from local_comparisons import VariantModel

    retained = json.loads((REPO / "studies/bonne_mere/dossier_final/donnees/design_retenu_96_saphir.json").read_text(encoding="utf-8"))
    candidates = []
    for name in args.jsonl:
        rows = [json.loads(line) for line in (HERE / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = sorted((r for r in rows if r["thinnest_nm"] >= 4.999), key=lambda r: r["rmse_pp"])[:args.top]
        candidates += [(f"{name}:{r['stage']}", np.array(r["ep"]), np.array(r["symbols"], dtype=np.int64)) for r in rows]
    for name in args.design:
        d = json.loads((HERE / name).read_text(encoding="utf-8"))
        candidates.append((name, np.array(d["thickness_nm"]), np.array(d["material_indices"], dtype=np.int64)))

    rng = np.random.default_rng(args.seed)
    width = max(len(ep) for _, ep, _ in candidates)
    unit = {"normal": rng.standard_normal((args.draws, width)), "uniform": rng.uniform(-1.0, 1.0, (args.draws, width))}
    results = []
    for label, ep, sym in candidates:
        model = VariantModel(sym, args.substrate_id, retained["target_upper_nm"])

        def rmse(e, model=model):
            _, t = model.spectrum(np.maximum(e, 0.0))
            return float(100.0 * np.sqrt(np.mean((t - model.target) ** 2)))

        row = {"candidate": label, "layers": len(ep), "thinnest_nm": float(ep.min()), "first4_nm": [round(float(x), 1) for x in ep[:4]],
               "nominal_pp": rmse(ep)}
        for law, (kind, scale) in LAWS.items():
            values = np.array([rmse(ep + scale * unit[kind][k, :len(ep)]) for k in range(args.draws)])
            row[law] = {"mean": float(values.mean()), "std": float(values.std()), "p95": float(np.percentile(values, 95))}
        results.append(row)
        with args.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    os._exit(0)


if __name__ == "__main__":
    main()
