"""Measure the METAL adapter's local polishes through the two window workflows."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import bench_examples as bench
import numpy as np
from _artefact import ecrire_json


def run(module, seed, out, paired, analytic):
    bench.qapp()
    bench.autoanswer_dialogs()
    from certus.metal import pglobal_adapter as adapter
    from certus.physics.gradient_metal import compute_metal_bilayer_gradient_analytic
    from certus.ui.certus_metal_bilayer_gui import CertusMetalBilayerApp

    rows = []
    minimize = adapter.minimize
    optimizer = adapter.PGlobalOptimizer
    apply_config = CertusMetalBilayerApp._apply_config_dict

    def enable_analytic_polish(app, config):
        loaded = {**config, "optimization": {**config.get("optimization", {}), "analytic_polish": True}}
        apply_config(app, loaded)
        if not app._collect_config()["optimization"]["analytic_polish"]:
            raise RuntimeError("The bilayer did not retain the analytic-polish setting")

    def seeded(*args, **kwargs):
        kwargs["config"] = kwargs["config"].with_overrides(random_seed=seed)
        return optimizer(*args, **kwargs)

    def timed(fun, x0, *args, **kwargs):
        if analytic and not callable(kwargs.get("jac")):
            raise RuntimeError("The bilayer gradient did not reach a local polish")
        calls = 0

        def counted(x):
            nonlocal calls
            calls += 1
            return fun(x)

        begin = perf_counter()
        fit = minimize(counted, x0, *args, **kwargs)
        seconds = perf_counter() - begin
        row = {"seconds": seconds, "cost_calls": calls, "iterations": int(fit.nit),
               "mse": float(fit.fun), "success": bool(fit.success), "start": np.asarray(x0).tolist(),
               "tolerance": kwargs["options"]["ftol"]}
        if module == "metal_bilayer":
            # The normal worker binds the spectral arguments in its objective's default tuple.
            spectral_args = fun.__defaults__[0]
            value, grad = compute_metal_bilayer_gradient_analytic(x0, *spectral_args)
            expected = float(fun(x0))
            numeric = np.zeros_like(x0)
            for index in range(len(x0)):
                step = 1e-6 * max(1.0, abs(x0[index]))
                up, down = x0.copy(), x0.copy()
                up[index] += step
                down[index] -= step
                numeric[index] = (fun(up) - fun(down)) / (2.0 * step)
            row.update(start_mse=expected, gradient_mse=float(value),
                       gradient_gap=float(np.max(np.abs(grad - numeric)) / max(np.max(np.abs(numeric)), 1e-20)))
            if paired:
                if not np.isclose(value, expected, rtol=1e-8, atol=1e-12) or row["gradient_gap"] > 1e-3:
                    raise RuntimeError("The bilayer gradient does not match the objective at this start")

                def jac(x):
                    if fun(x) >= 1e12:
                        return np.zeros_like(x)
                    return compute_metal_bilayer_gradient_analytic(x, *spectral_args)[1]

                jac(x0)
                begin = perf_counter()
                candidate = minimize(fun, x0.copy(), *args, **kwargs, jac=jac)
                row["paired"] = {"seconds": perf_counter() - begin, "mse": float(candidate.fun),
                                 "iterations": int(candidate.nit), "cost_calls": int(candidate.nfev),
                                 "gradient_calls": int(candidate.njev), "success": bool(candidate.success)}
        rows.append(row)
        print(f"Polish {len(rows)}: {seconds:.3f}s, {calls} cost calls", flush=True)
        return fit

    with patch.object(adapter, "minimize", timed), patch.object(adapter, "PGlobalOptimizer", seeded), patch.object(
        CertusMetalBilayerApp, "_apply_config_dict", enable_analytic_polish if analytic else apply_config
    ):
        setup, elapsed, score = bench.RUNNERS[module]()
    if score is None or not np.isfinite(score) or not rows:
        raise RuntimeError("The METAL workflow did not return a finite score and local-polish measurements")
    ecrire_json(out, {"module": module, "seed": seed, "analytic": analytic, "setup_seconds": setup, "workflow_seconds": elapsed,
                      "rmse": score, "polishes": rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=("metal_single", "metal_bilayer"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--paired", action="store_true")
    mode.add_argument("--analytic", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.analytic and args.module != "metal_bilayer":
        parser.error("The analytic gradient covers the bilayer objective")
    run(args.module, args.seed, args.out, args.paired, args.analytic)


if __name__ == "__main__":
    main()
