"""Change basin at a constant layer count: insert a needle (+2 layers), then remove a thin layer (-2 layers).

One move tries both orders, each with the --remove-choices thinnest interior layers: needle then removal (the best
1 nm needle by the cached back-side scan, DESIGN's kernel, nominal polish, remove the layer and merge its two
neighbours, nominal polish) and removal then needle. Every result is judged on its mean RMSE over the training draws
(2 sigma = 0.4 nm by default, same draws as robust_optimize.py), or on its nominal RMSE with --judge nominal;
the best is kept if it lowers that score. After a move that does not improve, the next one starts from the best design x (1 + 0.03 N(0,1)).
No thickness floor (owner's decision), except the two layers next to the substrate: no needle in them and they
stay >= --first-two-min (25 nm by default), so the design needs no precoat (owner). The best design is written at each improvement; the final robust polish is
robust_optimize.py on the output file.

python reports/BONNE_MERE_design_2026-10-23/needle_swap.py --study STUDY --start best_design_robust_opt_90.json --tag _90
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("NUMBA_NUM_THREADS", "8")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MAX_NM = 1000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", type=Path, required=True)
    ap.add_argument("--start", required=True, help="design file in this folder")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, default=45.0)
    ap.add_argument("--draws", type=int, default=128)
    ap.add_argument("--sigma", type=float, default=0.2, help="nm (2 sigma = 0.4 nm)")
    ap.add_argument("--seed", type=int, default=7, help="training draws; same default as robust_optimize.py")
    ap.add_argument("--first-two-min", type=float, default=25.0, help="nm, lowest thickness of layers 1 and 2")
    ap.add_argument("--judge", choices=["robust", "nominal"], default="robust",
                    help="keep a move on the mean RMSE under errors, or on the nominal RMSE")
    ap.add_argument("--remove-choices", type=int, default=3)
    args = ap.parse_args()
    sys.path.insert(0, str(REPO))
    sys.path.insert(1, str(args.study / "scripts"))
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    import numpy as np
    from local_comparisons import VariantModel
    from scipy.optimize import minimize

    from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact
    from certus.physics.gradient_oblique import compute_oblique_backside_bundle_analytic

    spec = importlib.util.spec_from_file_location("repo_certus_opt_needle", REPO / "certus/physics/certus_opt_needle.py")
    needle_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = needle_module  # Numba's cache looks the module up by name
    spec.loader.exec_module(needle_module)

    start = json.loads((HERE / args.start).read_text(encoding="utf-8"))
    n_layers = len(start["thickness_nm"])
    # same draws as robust_optimize.py for the same seed and layer count
    deltas = args.sigma * np.random.default_rng(args.seed).standard_normal((args.draws, n_layers))
    rng = np.random.default_rng(args.seed + 2)
    models: dict[tuple, object] = {}
    log = (HERE / f"needle_swap{args.tag}.log").open("a", encoding="utf-8")
    t0 = time.monotonic()

    def write(line: str) -> None:
        log.write(line + "\n")
        log.flush()

    def model_of(sym):
        key = tuple(int(s) for s in sym)
        if key not in models:
            models[key] = VariantModel(np.array(key, dtype=np.int64), start["substrate_id"], start["target_upper_nm"])
        return models[key]

    def nominal(ep, sym):
        m = model_of(sym)
        return 100.0 * float(np.sqrt(np.mean((m.spectrum(np.asarray(ep, dtype=float))[1] - m.target) ** 2)))

    def training_mean(ep, sym):
        m = model_of(sym)
        return 100.0 * float(np.mean([np.sqrt(np.mean((m.spectrum(np.maximum(ep + d, 0.0))[1] - m.target) ** 2)) for d in deltas]))

    def score(ep, sym):
        return training_mean(ep, sym) if args.judge == "robust" else nominal(ep, sym)

    def polish(ep, sym):
        m = model_of(sym)
        var = np.arange(len(ep), dtype=np.int64)

        def cost_grad(x):
            _, _, t, jac = compute_oblique_backside_bundle_analytic(np.ascontiguousarray(x), m.layers, m.substrate, m.wls, var, 0.0, True)
            r = t - m.target
            return float(np.mean(r * r)), (2.0 / len(r)) * (np.asarray(jac).T @ r)

        lower = np.zeros(len(ep))
        lower[:2] = args.first_two_min
        return np.asarray(minimize(cost_grad, np.clip(ep, lower, MAX_NM), jac=True, method="L-BFGS-B", bounds=[(lo, MAX_NM) for lo in lower],
                                   options={"maxiter": 400, "ftol": 1e-14, "gtol": 1e-10}).x)

    def needle(ep, sym, banned=()):
        m = model_of(sym)
        layers = np.ascontiguousarray(np.asarray(m.layers, dtype=np.complex128))
        col = {s: layers[:, k] for k, s in enumerate(sym)}
        needle_t = np.ascontiguousarray(np.stack([col[1 - s] for s in sym], axis=1))
        n_sub = np.ascontiguousarray(np.asarray(m.substrate, dtype=np.complex128))
        wls = np.asarray(m.wls, dtype=np.float64)
        _rf, _tf, _rfp, rbp, tb = calc_spectrum_full_exact(wls, ep, layers, np.zeros(0), np.zeros((layers.shape[0], 0), dtype=np.complex128), n_sub)
        mask = np.ones(len(ep), dtype=np.int64)
        mask[:2] = 0  # no needle in the two layers next to the substrate
        for k in banned:
            if 0 <= k < len(mask):
                mask[k] = 0
        j, z, _ = needle_module.needle_scan_cached_backside(wls, layers, needle_t, n_sub, ep, np.asarray(m.target, dtype=float),
                                                            np.ones(len(wls)), 2.0, 1.0, mask, rbp, tb)
        j, z = int(j), float(z)
        return (np.concatenate([ep[:j], [z, 1.0, ep[j] - z], ep[j + 1:]]),
                [*sym[:j], sym[j], 1 - sym[j], sym[j], *sym[j + 1:]], j)

    def remove(ep, sym, i):
        return (np.concatenate([ep[:i - 1], [ep[i - 1] + ep[i + 1]], ep[i + 2:]]), [*sym[:i - 1], sym[i - 1], *sym[i + 2:]])

    best_ep = np.array(start["thickness_nm"], dtype=float)
    best_sym = [int(s) for s in start["material_indices"]]
    best_value = score(best_ep, best_sym)
    write(f"start {args.start}: {n_layers} layers, nominal {nominal(best_ep, best_sym):.6f} pp, {args.judge} {best_value:.6f} pp")
    move, stuck = 0, False
    while time.monotonic() - t0 < 60.0 * args.minutes:
        move += 1
        ep = best_ep * (1.0 + 0.03 * rng.standard_normal(len(best_ep))) if stuck else best_ep.copy()
        trials = []
        grown_ep, grown_sym, j = needle(ep, best_sym)
        grown_ep = polish(grown_ep, grown_sym)
        # the needle and its two neighbours are not removed again: that would undo the move
        for i in [i for i in np.argsort(grown_ep) if 0 < i < len(grown_ep) - 1 and not j - 1 <= i <= j + 3][:args.remove_choices]:
            ep_r, sym_r = remove(grown_ep, grown_sym, int(i))
            ep_r = polish(ep_r, sym_r)
            trials.append((score(ep_r, sym_r), ep_r, sym_r, f"needle in {j + 1} then removed {int(i) + 1}"))
        for i in [i for i in np.argsort(ep) if 0 < i < len(ep) - 1][:args.remove_choices]:
            ep_s, sym_s = remove(ep, best_sym, int(i))
            ep_s = polish(ep_s, sym_s)
            ep_r, sym_r, jj = needle(ep_s, sym_s, banned=(int(i) - 2, int(i) - 1, int(i)))  # not back into the merged layer
            ep_r = polish(ep_r, sym_r)
            trials.append((score(ep_r, sym_r), ep_r, sym_r, f"removed {int(i) + 1} then needle in {jj + 1}"))
        value, ep_r, sym_r, how = min(trials, key=lambda t: t[0])
        stuck = value > best_value * (1.0 - 1e-4)  # a gain under 0.01 % also calls for a perturbation
        if value < best_value:
            best_ep, best_sym, best_value = ep_r, sym_r, value
            out = dict(start)
            out.update({"n_layers": len(ep_r), "thickness_nm": [float(x) for x in ep_r], "material_indices": sym_r,
                        "rmse_percentage_points": nominal(ep_r, sym_r),
                        "needle_swap": {"judge": args.judge, "score_pp": value, "move": move, "draws": args.draws, "sigma_nm": args.sigma,
                                        "seed": args.seed, "start": args.start, "how": how}})
            (HERE / f"best_design_needle_swap{args.tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        write(f"move {move} {how}: {args.judge} {value:.6f} pp nominal "
              f"{nominal(ep_r, sym_r):.6f} pp first two {ep_r[0]:.1f} {ep_r[1]:.1f} nm thinnest {np.min(ep_r):.2f} nm best {best_value:.6f} pp "
              f"t={(time.monotonic() - t0) / 60:.1f} min")
    write(f"END best {args.judge} {best_value:.6f} pp after {move} moves")
    os._exit(0)


if __name__ == "__main__":
    main()
