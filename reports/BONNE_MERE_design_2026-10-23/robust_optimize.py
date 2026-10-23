"""Optimize a Bonne Mere design for its mean RMSE under thickness errors instead of its nominal RMSE.

Objective: mean over K fixed training draws of RMSE(ep + delta_k), delta_k Gaussian, independent per layer
(2 sigma = 0.4 nm by default), with its exact gradient (the analytic Jacobian at each perturbed design).
The training draws use another seed than robustness.py, so the judgement there is out of sample.
L-BFGS-B, layers kept >= --floor (none by default: the owner removes thin layers by hand).
With --hop-min, basin hops come first: thicknesses x (1 + 0.03 N(0,1)) around the best design, a nominal polish,
then the hop is kept if its mean RMSE over the training draws is lower; the final robust polish starts from the best hop.

python reports/BONNE_MERE_design_2026-10-23/robust_optimize.py --study STUDY --start best_design_silica_98.json --tag _98
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
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FLOOR_NM = 0.0
MAX_NM = 1000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", type=Path, required=True)
    ap.add_argument("--start", required=True, help="design file in this folder")
    ap.add_argument("--tag", required=True, help="suffix of best_design_robust_opt*.json and its log")
    ap.add_argument("--draws", type=int, default=64)
    ap.add_argument("--sigma", type=float, default=0.2, help="nm (2 sigma = 0.4 nm)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--floor", type=float, default=FLOOR_NM, help="lowest thickness, nm")
    ap.add_argument("--maxiter", type=int, default=400)
    ap.add_argument("--hop-min", type=float, default=0.0, help="minutes of basin hops judged on the training mean")
    ap.add_argument("--time-only", action="store_true", help="time one objective call and stop")
    args = ap.parse_args()
    sys.path.insert(0, str(REPO))
    sys.path.insert(1, str(args.study / "scripts"))
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    import numpy as np
    from local_comparisons import VariantModel
    from scipy.optimize import minimize

    from certus.physics.gradient_oblique import compute_oblique_backside_bundle_analytic

    start = json.loads((HERE / args.start).read_text(encoding="utf-8"))
    ep0 = np.array(start["thickness_nm"], dtype=np.float64)
    model = VariantModel(np.array(start["material_indices"], dtype=np.int64), start["substrate_id"], start["target_upper_nm"])
    var = np.arange(len(ep0), dtype=np.int64)
    deltas = args.sigma * np.random.default_rng(args.seed).standard_normal((args.draws, len(ep0)))
    log = (HERE / f"robust_opt{args.tag}.log").open("a", encoding="utf-8")
    t0 = time.monotonic()
    calls = [0]

    def rmse_and_grad(ep):
        _, _, t, jac = compute_oblique_backside_bundle_analytic(np.ascontiguousarray(ep), model.layers, model.substrate,
                                                               model.wls, var, 0.0, True)
        r = t - model.target
        rmse = np.sqrt(np.mean(r * r))
        return rmse, (np.asarray(jac).T @ r) / (len(r) * rmse)

    def objective(ep):
        calls[0] += 1
        total, grad = 0.0, np.zeros_like(ep)
        for d in deltas:
            v, g = rmse_and_grad(np.maximum(ep + d, 0.0))
            total += v
            grad += g
        return 100.0 * total / len(deltas), 100.0 * grad / len(deltas)

    def write(line: str) -> None:
        log.write(line + "\n")
        log.flush()

    objective(ep0)
    t1 = time.monotonic()
    value0, _ = objective(ep0)
    write(f"start {args.start}: nominal {100 * rmse_and_grad(ep0)[0]:.6f} pp, training mean {value0:.6f} pp, "
          f"{len(ep0)} layers, {args.draws} draws, sigma {args.sigma} nm, one objective {time.monotonic() - t1:.2f} s")
    if args.time_only:
        _, grad = objective(ep0)
        for k in (0, len(ep0) // 2, len(ep0) - 1):
            step = np.zeros_like(ep0)
            step[k] = 1e-4
            fd = (objective(ep0 + step)[0] - objective(ep0 - step)[0]) / 2e-4
            write(f"gradient check layer {k}: analytic {grad[k]:.6e} finite difference {fd:.6e}")
        os._exit(0)

    def training_mean(ep):
        values = [np.sqrt(np.mean((model.spectrum(np.maximum(ep + d, 0.0))[1] - model.target) ** 2)) for d in deltas]
        return 100.0 * float(np.mean(values))

    def nominal_cost_grad(ep):
        _, _, t, jac = compute_oblique_backside_bundle_analytic(np.ascontiguousarray(ep), model.layers, model.substrate,
                                                               model.wls, var, 0.0, True)
        r = t - model.target
        return float(np.mean(r * r)), (2.0 / len(r)) * (np.asarray(jac).T @ r)

    if args.hop_min > 0:
        rng = np.random.default_rng(args.seed + 1)
        best_ep, best_value, hop = ep0.copy(), training_mean(ep0), 0
        write(f"hops: start training mean {best_value:.6f} pp")
        while time.monotonic() - t0 < 60.0 * args.hop_min:
            hop += 1
            trial = np.clip(best_ep * (1.0 + 0.03 * rng.standard_normal(len(best_ep))), args.floor, MAX_NM)
            trial = np.asarray(minimize(nominal_cost_grad, trial, jac=True, method="L-BFGS-B", bounds=[(args.floor, MAX_NM)] * len(trial),
                                        options={"maxiter": 400, "ftol": 1e-14, "gtol": 1e-10}).x)
            value = training_mean(trial)
            if value < best_value:
                best_ep, best_value = trial, value
                running = dict(start)
                running.update({"n_layers": len(trial), "thickness_nm": [float(x) for x in trial], "hop": hop,
                                "training_mean_rmse_pp": value})
                (HERE / f"running_best{args.tag}.json").write_text(json.dumps(running, indent=2), encoding="utf-8")
            write(f"hop {hop} training mean {value:.6f} pp nominal {100 * np.sqrt(nominal_cost_grad(trial)[0]):.6f} pp "
                  f"best {best_value:.6f} pp t={(time.monotonic() - t0) / 60:.1f} min")
        ep0 = best_ep

    def callback(ep):
        write(f"iter call={calls[0]} training mean {objective(ep)[0]:.6f} pp nominal {100 * rmse_and_grad(ep)[0]:.6f} pp "
              f"t={(time.monotonic() - t0) / 60:.1f} min")

    res = minimize(objective, np.clip(ep0, args.floor, MAX_NM), jac=True, method="L-BFGS-B", callback=callback,
                   bounds=[(args.floor, MAX_NM)] * len(ep0), options={"maxiter": args.maxiter, "ftol": 1e-12, "gtol": 1e-8})
    ep = np.asarray(res.x)
    out = dict(start)
    out.update({"n_layers": len(ep), "thickness_nm": [float(x) for x in ep],
                "rmse_percentage_points": float(100 * rmse_and_grad(ep)[0]),
                "robust_training": {"mean_rmse_pp": float(res.fun), "draws": args.draws, "sigma_nm": args.sigma,
                                    "seed": args.seed, "start": args.start, "floor_nm": args.floor,
                                    "hop_min": args.hop_min}})
    (HERE / f"best_design_robust_opt{args.tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    write(f"END {res.message} training mean {res.fun:.6f} pp nominal {out['rmse_percentage_points']:.6f} pp "
          f"thinnest {ep.min():.3f} nm t={(time.monotonic() - t0) / 60:.1f} min")
    os._exit(0)


if __name__ == "__main__":
    main()
