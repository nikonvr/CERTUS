"""RE-SCORE A POPULATION OF PLANS UNDER TWO READING MODELS: the shipped one, and the frozen model of ETAT section 3.

The shipped configuration reads raw readings on the coarse scan (smoothing window 1, threshold `tp_hysteresis_factor`
x A); the frozen reading model of ETAT section 3 reads every 0.125 nm and smooths over 8 readings, with a threshold of
1.00 A. Since D94/D95 the second is exact at every reading, and it agrees with the independent sequential machine of
`scripts/probe_oms_sequentiel.py`. This probe asks what it changes to the RANKING of a population already found:
every plan is scored by the production kernels under both models, the search itself is not rerun (no bifurcation).

Scoring as in `_test_strategy_robustness_task`, reduced: the 95th percentile of the spectral RMSE over terminated
runs (against the nominal spectrum, the index corridor applied in growth and scoring), at the worst of the three noise
levels; a crash rate above 5 % at any level eliminates. Photometric curvature and index corridor are drawn as in
production; the slit bias is LEFT OUT (its profiles are built per strategy inside the pipeline), and so is any Rate
layer or witness swap -- the comparison is between reading models, under the same physics on both sides.

Models (`--models`): `livre` and `fige`, each also with the exact stop (`_exact`, D97), `fige_arret_lisse`, the frozen
model whose stop reading is smoothed like the rest (D99), and `livre_ancres` and `livre_exact_ancres`, the shipped model
with POEM's anchors read at the extremum of their layer instead of the coarse sample (D96), the second with the exact stop
too. `name@factor` sets the turning-point threshold of a model to `factor` x A: `--models livre@1.0,livre@1.66,livre@2.4`
sweeps it.

    python scripts/probe_modele_lecture.py <config.json> <plans.json> [--models livre,fige] [--ranks 0,5,9]
        [--first N] [--runs 300] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# The Numba cache of the compiled kernels is keyed by their sources (ETAT D49): without this call a script reads the one
# next to the sources, where a caller keeps the machine code of an OLD callee of another file.
from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402

CRASH_GATE = 0.05
MODELS = {
    "livre": {"smoothing": 1, "hyst": None, "exact": False},
    "fige": {"smoothing": 8, "hyst": 1.0, "exact": False},
    # D97: the same two reading models, the stop solved on the exact signal instead of the parabola.
    "livre_exact": {"smoothing": 1, "hyst": None, "exact": True},
    "fige_exact": {"smoothing": 8, "hyst": 1.0, "exact": True},
    # D99: the frozen model with the stop reading smoothed like the rest -- the same stop draws divided by sqrt(8), the
    # variance of a mean of 8 independent readings. The kernel draws it raw whatever the smoothing.
    "fige_arret_lisse": {"smoothing": 8, "hyst": 1.0, "exact": False, "stop_scale": 1.0 / np.sqrt(8.0)},
    # D96: the shipped model with POEM's anchors at the extremum of their layer, with the parabola or the exact stop.
    "livre_ancres": {"smoothing": 1, "hyst": None, "exact": False, "anchors": True},
    "livre_exact_ancres": {"smoothing": 1, "hyst": None, "exact": True, "anchors": True},
}


def score_plan(params, thick, blocks, n_runs, A, h_config, model, wls, nH_w, nL_w, nS_w, flat, T_nom, seed):
    from certus.core.certus_strat_robustness import INDEX_CORRIDOR_DEFAULT
    from certus.physics.certus_strat_batch import compute_batch_rmse, corridor_wl_range, simulate_stack_robustness_batch
    from certus.physics.certus_strat_growth import PHOTOMETRIC_CURVATURE_AMP
    from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio

    n = len(thick)
    lw = np.zeros(n)
    nH = np.zeros(n, dtype=complex)
    nL = np.zeros(n, dtype=complex)
    nS = np.zeros(n, dtype=complex)
    for b0, b1, wl in blocks:
        for i in range(int(b0), int(b1)):
            lw[i] = float(wl)
            nH[i] = seq.material_index(params, params["nH_id"], wl)
            nL[i] = seq.material_index(params, params["nL_id"], wl)
            nS[i] = seq.material_index(params, params["nSub_id"], wl)
    corridor = float(params.get("index_corridor", INDEX_CORRIDOR_DEFAULT) or 0.0)
    curvature = float(params.get("photometric_curvature_amp", PHOTOMETRIC_CURVATURE_AMP) or 0.0)
    lo, hi = corridor_wl_range(wls, lw)
    hf = h_config if model["hyst"] is None else model["hyst"]
    out = {"crash_by_level": {}, "p95_by_level": {}}
    worst_p95, worst_crash = 0.0, 0.0
    for level_idx, f in enumerate((0.5, 1.0, 2.0)):
        rng = np.random.default_rng([seed, level_idx])
        stop = model.get("stop_scale", 1.0) * A * f * np.clip(rng.normal(0.0, 1.0 / 3.0, size=(n_runs, n)), -1.0, 1.0)
        res = simulate_stack_robustness_batch(
            np.asarray(thick, dtype=float), lw, nH, nL, nS, stop, compute_probe_offset_nm_from_ratio(params),
            float(params.get("non_monotonic_error_factor", 2.0)), 0, np.full(n, A * f), seed * 7919 + level_idx,
            hf * A * f, 0.0, 0.0, curvature, seed * 31 + level_idx, True, int(model["smoothing"]), corridor,
            seed * 53 + level_idx, lo, hi, None, None, None, bool(model.get("exact", False)),
            bool(model.get("anchors", False)),
        )[0]
        crashed = (res > 1e5).any(axis=1)
        crash = float(np.mean(crashed))
        ok = ~crashed
        p95 = float("inf")
        if ok.any():
            # The scoring kernel draws the corridor by RUN INDEX, as the growth batch does: scoring only the terminated
            # rows would re-index them and give each a foreign corridor. All runs are scored (a crashed row is replaced
            # by the nominal stack, its value unused), and the terminated ones are kept.
            rm_all = compute_batch_rmse(np.ascontiguousarray(np.where(res > 1e5, thick[None, :], res)), wls, nH_w, nL_w,
                                        nS_w, T_nom, flat, None, corridor, seed * 53 + level_idx, lo, hi)
            p95 = float(np.percentile(rm_all[ok], 95))
        out["crash_by_level"][f"{f:g}"] = crash
        out["p95_by_level"][f"{f:g}"] = p95
        worst_p95 = max(worst_p95, p95)
        worst_crash = max(worst_crash, crash)
    out["score"] = worst_p95 if worst_crash <= CRASH_GATE else float("inf")
    out["crash"] = worst_crash
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("plans")
    ap.add_argument("--first", type=int, default=0, help="score only the first N plans (0: all)")
    ap.add_argument("--ranks", default="", help="score only these ranks of the plans file, comma-separated")
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--models", default="livre,fige", help=f"among {', '.join(MODELS)}")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    # `name@factor` is model `name` with the turning-point threshold set to `factor` x A (x the noise level, as the code
    # scales it): `livre@1.0,livre@2.0` sweeps the threshold of the shipped model.
    models = {}
    for m in (x for x in args.models.split(",") if x):
        base, _, factor = m.partition("@")
        models[m] = dict(MODELS[base], **({"hyst": float(factor)} if factor else {}))

    from certus.physics.certus_strat_batch import calculate_RT_batch_kernel

    params = seq.load_params(Path(args.config))
    thick = seq.nominal_thicknesses(params)
    A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    h_config = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    lo, hi = (float(x) for x in params["wl_range"])
    step = float(params.get("wl_step", 1.0) or 1.0)
    wls = np.arange(lo, hi + 0.5 * step, step)
    nH_w = np.array([seq.material_index(params, params["nH_id"], w) for w in wls])
    nL_w = np.array([seq.material_index(params, params["nL_id"], w) for w in wls])
    nS_w = np.array([seq.material_index(params, params["nSub_id"], w) for w in wls])
    flat = np.where((np.arange(len(thick)) % 2 == 0)[None, :], nH_w[:, None], nL_w[:, None]).astype(np.complex128)
    T_nom = calculate_RT_batch_kernel(wls, nH_w, nL_w, nS_w, np.asarray(thick, dtype=float).reshape(1, -1))[1][0]
    plans = json.load(open(args.plans))
    ranks = [int(x) for x in args.ranks.split(",") if x.strip()] or list(range(len(plans)))
    if args.first:
        ranks = ranks[: args.first]
    print(f"config={Path(args.config).name} plans={len(ranks)} runs={args.runs} A={A:g} h={h_config:g} "
          f"python={sys.version.split()[0]}", flush=True)
    rows = []
    t0 = time.perf_counter()
    for count, rank in enumerate(ranks):
        plan = plans[rank]
        row = {"rank": rank, "id": plan.get("id"), "bench_score": plan.get("score"), "blocks": plan["blocks"]}
        for name, model in models.items():
            row[name] = score_plan(params, thick, plan["blocks"], args.runs, A, h_config, model, wls, nH_w, nL_w, nS_w,
                                   flat, T_nom, args.seed)
        rows.append(row)
        if count % 10 == 0:
            print(f"  {count + 1}/{len(ranks)} plans, {time.perf_counter() - t0:.0f} s", flush=True)
            if args.json:
                Path(args.json).write_text(json.dumps({"rows": rows}, indent=0), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps({"rows": rows}, indent=0), encoding="utf-8")
    summarise(rows, list(models))


def summarise(rows: list[dict], names: list[str]) -> None:
    from scipy.stats import spearmanr

    print(f"\n{len(rows)} plans; depositable (crash <= 5 % at every level): "
          + ", ".join(f"{n} {sum(np.isfinite(r[n]['score']) for r in rows)}" for n in names))
    ref = names[0]
    for other in names[1:]:
        finite = [r for r in rows if np.isfinite(r[ref]["score"]) and np.isfinite(r[other]["score"])]
        if len(finite) > 2:
            a = [r[ref]["score"] for r in finite]
            b = [r[other]["score"] for r in finite]
            print(f"Spearman({ref}, {other}) over the {len(finite)} plans depositable under both: {spearmanr(a, b)[0]:.3f}; "
                  f"score ratio {other} / {ref}: median {np.median(np.array(b) / np.array(a)):.3f}")
    for name in names:
        order = sorted(rows, key=lambda r: r[name]["score"])
        print(f"top 5 under {name}: {[(r['rank'], round(r[name]['score'], 6)) for r in order[:5]]}")


if __name__ == "__main__":
    main()
