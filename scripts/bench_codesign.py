"""Measure paired DESIGN stacks under STRAT. Run one design or one deposition per process."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from time import perf_counter

import bench_examples as bench

ROOT = bench.ROOT
DESIGN = ROOT / "example/example_design/JSON-design-reference-tikhonravov-1996.json"
STRAT = ROOT / "example/example_strat/JSON-strat-example-fast.json"
CALIBRATION_SEED = 2026111501
HOLDOUT_SEEDS = (2026111502, 2026111503, 2026111504)
TUNE_SEED = 42
FLOOR_NM = 25.0


class RequireRobustSelection(logging.Handler):
    """Reject a robust campaign arm if the optimizer falls back to nominal selection."""

    def emit(self, record):
        if "memetic_robust_sigma_nm ignored" in record.getMessage():
            raise RuntimeError(record.getMessage())


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def design_job(seed, robust, out, children):
    from _artefact import ecrire_json

    bench.qapp()
    import numpy as np

    from certus.core.certus_design_cost_context import prepare_design_cost_context
    from certus.physics.gradient_utils import cost_numba_fast
    from certus.workers.certus_design_workers import OptimWorker
    from certus_physics import Layer, Material, Target, warmup_physics

    warmup_physics()
    cfg = read_json(DESIGN)
    l0 = cfg["l0"]
    stack = [Layer(layer["mat"], layer["qw"], layer["var"]) for layer in cfg["front"]]
    mats = {name: Material(spec["n4"], spec["n7"]) for name, spec in cfg["materials"].items()}
    tgts = [Target(**target) for target in cfg["targets"]]
    n_points = cfg["optim"]["points_per_target"]
    wls = np.unique(np.concatenate([1.0 / np.linspace(1.0 / t.lmax, 1.0 / t.lmin, n_points) for t in tgts]))
    ep0 = np.array([layer.qwot * l0 / (4 * mats[layer.mat].n4) for layer in stack])
    request = {
        "mats": mats, "stack": stack, "ep0": ep0, "wls": wls, "tgts": tgts, "l0": l0, "mode": "global",
        "wls_min": min(wls), "wls_max": max(wls), "back": True,
        "memetic_children": children, "memetic_seed": seed,
        "memetic_workers": int(os.environ.get("NUMBA_NUM_THREADS", "1")),
        "memetic_robust_sigma_nm": float(robust), "memetic_floor_nm": FLOOR_NM,
        "final_refine_lower_bounds": True,
    }
    worker = OptimWorker(request)
    results, errors = [], []
    worker.signals.finished.connect(results.append)
    worker.signals.error.connect(errors.append)
    t0 = perf_counter()
    logger = logging.getLogger("CERTUS")
    guard = RequireRobustSelection()
    if robust:
        logger.addHandler(guard)
    try:
        worker.run()
    finally:
        logger.removeHandler(guard)
    if errors or len(results) != 1 or not results[0]["ok"]:
        raise RuntimeError(f"DESIGN failed: {errors}")
    ep = np.asarray(results[0]["ep"])
    if len(ep) != len(stack) or not np.all(np.isfinite(ep) & (ep >= FLOOR_NM - 1e-9)):
        raise RuntimeError("DESIGN result violates the fixed sequence or minimum physical thickness")
    grid = np.linspace(400.0, 1200.0, 1601)
    context = prepare_design_cost_context(mats, stack, grid, tgts, has_back_calc=True)
    vals, weights = context.normal_targets()
    nominal = cost_numba_fast(ep, context.n_front, context.n_sub, grid, vals, weights, 0.0,
                              True, context.n_back, context.d_back)
    ecrire_json(out, {
        "source": DESIGN.name, "seed": seed, "robust_sigma_nm": float(robust), "children": children,
        "sequence": "".join(layer.mat for layer in stack), "d_nm": ep.tolist(),
        "mats": {k: v["n4"] for k, v in cfg["materials"].items()}, "l0": l0, "targets": cfg["targets"],
        "bare_backside": True, "floor_nm": FLOOR_NM,
        "nominal_rmse": float(np.sqrt(nominal)), "seconds": perf_counter() - t0,
    })


def strat_config(design):
    cfg = read_json(STRAT)
    sequence, thickness, mats = design["sequence"], design["d_nm"], design["mats"]
    expected = "HL" * 17
    if sequence != expected or len(thickness) != len(expected):
        raise ValueError("Expected the 34-layer H/L sequence starting with H on the substrate")
    if design.get("bare_backside") is not True:
        raise ValueError("Expected a design optimized with the same bare backside as STRAT")
    if design.get("floor_nm") != FLOOR_NM:
        raise ValueError(f"Expected a design optimized with a {FLOOR_NM:g} nm thickness floor")
    l0 = design["l0"]
    cfg.update(
        h_type_custom=True, l_type_custom=True, nH_r=str(mats["H"]), nL_r=str(mats["L"]),
        substrate_choice="Custom", nSub_custom=str(mats["Substrate"]), l0=str(l0),
        stack_multipliers=[4.0 * mats[m] * d / l0 for m, d in zip(sequence, thickness, strict=True)],
        targets=design["targets"], wl_range_start="400.0", wl_range_end="1200.0", wl_step="1.0",
        scan_wl_min="400.0", scan_wl_max="1200.0", scan_wl_step="1.0", phase_a_scan_limit="801",
        phase_a_seed=TUNE_SEED, robustness_seed=TUNE_SEED, show_plots=False, export_excel=False,
        # Admit lower-swing wavelengths to Phase A; keep the hard margin and T floor.
        strat_local_search=False, dynamics_threshold="0.0",
    )
    return cfg


def replayable_plan(plan):
    from certus.utils.certus_index_utils import NumpyEncoder

    keys = ("strategy_id", "blocks", "rate_layers", "monochromator_resolution_nm", "witness_reset_layers", "origin")
    return json.loads(json.dumps({key: plan[key] for key in keys if key in plan}, cls=NumpyEncoder))


def holdout(design, pre_calc_data, params, plan, runs):
    import numpy as np

    from certus.core.certus_design_cost_context import prepare_design_cost_context
    from certus.core.certus_strat_local_search import native_evaluator, nominal_level_index
    from certus.core.certus_strat_robustness import _prepare_robustness_nominal_optics
    from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel
    from certus.physics.design_fast_kernels import prepare_normal_fast_context
    from certus_physics import Layer, Material, Target

    ep = np.asarray(pre_calc_data["p_thick_nominal"], dtype=np.float64)
    # STRAT's layer table reads back six decimal places of QWOT.
    max_rounding_nm = 0.5e-6 * design["l0"] / (4.0 * min(design["mats"]["H"], design["mats"]["L"]))
    if ep.shape != (34,) or np.max(np.abs(ep - design["d_nm"])) > max_rounding_nm + 1e-10:
        raise RuntimeError("STRAT changed the physical thicknesses while loading the design")
    if params.get("targets") != design["targets"]:
        raise RuntimeError("The DESIGN targets did not reach STRAT")
    clues = pre_calc_data["clues_at_wl"]
    grid, high, low, substrate, nominal_t = _prepare_robustness_nominal_optics(
        params=params, p_thick_nominal=ep.tolist(), opti_results={"clues_at_wl": clues},
    )
    for values, material in ((high, "H"), (low, "L"), (substrate, "Substrate")):
        if not np.allclose(values, design["mats"][material], rtol=0.0, atol=1e-12):
            raise RuntimeError(f"The {material} refractive index did not reach STRAT")
    evaluator = native_evaluator(params, ep.tolist(), clues, {}, thickness=True)
    level = nominal_level_index(params)
    scored = [evaluator(plan, seed, runs) for seed in HOLDOUT_SEEDS]
    rmse_by_level = [np.concatenate([seed[i][0] for seed in scored]) for i in range(len(scored[0]))]
    stopped_by_level = [np.concatenate([seed[i][1] for seed in scored]) for i in range(len(scored[0]))]
    if any(len(errors) != len(HOLDOUT_SEEDS) * runs or not np.isfinite(errors).all() for errors in rmse_by_level):
        raise RuntimeError("Invalid STRAT holdout sample")
    rmse, stops = rmse_by_level[level], stopped_by_level[level]
    ok = ~stops & np.isfinite(rmse)
    _, calibration_stops, calibration_thickness = evaluator(plan, CALIBRATION_SEED, runs)[level]
    if ok.sum() < 2 or (~calibration_stops).sum() < 2:
        raise RuntimeError("Fewer than two completed deposition draws")
    errors = calibration_thickness[~calibration_stops] - ep
    bias = errors.mean(axis=0)
    covariance = np.cov(errors, rowvar=False)
    context = prepare_design_cost_context(
        {m: Material(n, n) for m, n in design["mats"].items()},
        [Layer(m, 0.0) for m in design["sequence"]], grid, [Target(**target) for target in design["targets"]],
        has_back_calc=True,
    )
    values, weights = context.normal_targets()
    fast = prepare_normal_fast_context(
        wls=grid, n_layers_T=context.n_front, n_sub=context.n_sub, has_back_calc=True,
        n_back_T=context.n_back, d_back=context.d_back,
    )
    sqrt_weight = np.sqrt(weights / weights.sum())
    r, jac, _ = _res_jac_lossless_normal_kernel(
        ep, fast["n_layers_real"], fast["inv_n_layers_real"], fast["n_sub_real"], fast["k0_wls"],
        True, fast["rb_prime"], fast["tb"], values, sqrt_weight, np.arange(len(ep), dtype=np.int64),
    )
    np.testing.assert_allclose(r, sqrt_weight * (nominal_t - values), rtol=0.0, atol=1e-12)
    predicted = np.sqrt(float(np.sum((r + jac @ bias)**2) + np.sum((jac.T @ jac) * covariance)))
    p95_by_level = [float(np.percentile(scores, 95)) for scores in rmse_by_level]
    return {
        "holdout_seeds": HOLDOUT_SEEDS, "covariance_seed": CALIBRATION_SEED,
        "covariance_completed": len(errors), "draws_per_seed": runs, "noise_level_index": level,
        "rmse": rmse.tolist(), "stopped": stops.tolist(), "stops": int(stops.sum()),
        "rms_completed": float(np.sqrt(np.mean(rmse[ok]**2))), "p95_all": p95_by_level[level],
        "seel_nm": float(2.0 * np.sqrt(max(p95_by_level))),
        "p95_by_level": p95_by_level, "stops_by_level": [int(stopped.sum()) for stopped in stopped_by_level],
        "nominal_rmse": float(np.linalg.norm(r)), "covariance_predicted_rms": float(predicted),
        "bias_nm": bias.tolist(), "covariance_nm2": covariance.tolist(),
        "plan": replayable_plan(plan), "physical_thickness_nm": ep.tolist(),
        "strategy_id": plan.get("strategy_id"), "blocks": len(plan["blocks"]),
        "rate_layers": len(plan.get("rate_layers") or []),
    }


def strat_job(design_path, out, runs):
    from _artefact import ecrire_json

    bench.qapp()
    bench.autoanswer_dialogs()
    from certus.workers import certus_strat_workers as workers

    design = read_json(design_path)
    cfg_path = out.with_suffix(".strat.json")
    plan_path = out.with_suffix(".plan.json")
    if cfg_path.exists() or plan_path.exists() or out.exists():
        raise FileExistsError(f"Campaign already has a file for {out}")
    cfg_path.write_text(json.dumps(strat_config(design), indent=2), encoding="utf-8")
    os.environ["CERTUS_DESIGN_JSON"] = str(cfg_path.resolve())
    finalizer = workers._finalize_and_export_pipeline_results
    measured = {}

    started = perf_counter()

    def capture(**kwargs):
        result = finalizer(**kwargs)
        plan = result["final_results"]["best_strategy"]
        elapsed = perf_counter() - started
        best_result = result["final_results"]["all_strategies_results"][0]
        provenance = {"design": design_path.name, "design_seed": design["seed"],
                      "robust_sigma_nm": design["robust_sigma_nm"], "plan_seconds": elapsed,
                      "search_crash_eliminated": bool(best_result.get("crash_eliminated"))}
        ecrire_json(plan_path, {**provenance, "plan": replayable_plan(plan)})
        print(f"STRAT plan selected in {elapsed:.1f} s; evaluating disjoint seeds", flush=True)
        measured.update(holdout(design, kwargs["pre_calc_data"], kwargs["params"], plan, runs))
        ecrire_json(out, {**provenance, **measured})
        return result

    workers._finalize_and_export_pipeline_results = capture
    _setup, elapsed, _result = bench.run_strat()
    if not measured or not out.is_file():
        raise RuntimeError("STRAT ended without a deposited-stack comparison")
    print(f"STRAT {elapsed:.1f} s, holdout RMS {measured['rms_completed']:.7g}, stops {measured['stops']}", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("design", "strat"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--robust", action="store_true")
    parser.add_argument("--children", type=int, default=1_000)
    parser.add_argument("--runs", type=int, default=400)
    parser.add_argument("--design", type=Path)
    args = parser.parse_args()
    if args.stage == "strat" and args.design is None:
        parser.error("--design is required for the STRAT stage")
    if args.out.exists():
        parser.error(f"Output already exists: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.stage == "design":
        design_job(args.seed, args.robust, args.out, args.children)
    else:
        strat_job(args.design, args.out, args.runs)


if __name__ == "__main__":
    main()
