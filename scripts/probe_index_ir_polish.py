"""Time paired INDEX infrared polishes on the starts used by the normal worker."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import bench_examples as bench
import numpy as np
from _artefact import ecrire_json

REJECTED_COST = 1e12


def run_polishes(obj, start, args, kwargs, minimize):
    """Use the worker's bounds and tolerances for both arms. Return only its reference result."""
    callback = kwargs.get("callback")
    options = {key: value for key, value in kwargs.items() if key != "callback"}
    start_mse = float(obj(start))
    if start_mse < REJECTED_COST:
        obj.gradient(start)

    def one(analytic):
        calls = {"cost": 0, "gradient": 0}

        def cost(x):
            calls["cost"] += 1
            return obj(x)

        def jac(x):
            calls["gradient"] += 1
            if obj(x) >= REJECTED_COST:
                return np.zeros_like(x)
            return obj.gradient(x)

        start_time = perf_counter()
        result = minimize(cost, start.copy(), *args, **options, jac=jac if analytic else None)
        if not np.isfinite(result.fun):
            raise RuntimeError("Non-finite polish cost")
        return result, {"seconds": perf_counter() - start_time, "mse": float(result.fun),
                        "iterations": int(result.nit), "success": bool(result.success),
                        "message": str(result.message), **calls}

    ref, fd = one(False)
    _candidate, grad = one(True)
    if callback is not None:
        callback(ref.x)
    return ref, {"start_mse": start_mse, "finite_difference": fd, "gradient": grad}


def run(seed, book, out, analytic):
    from PyQt6.QtCore import QEventLoop, QTimer
    from scipy import optimize
    from scipy.optimize import minimize

    bench.qapp()
    from certus.core.certus_index_objectives import IRGlobalObjective
    from certus.workers.certus_index_workers import IRGlobalModelWorker
    from CERTUS_INDEX import CertusIndexApp
    from certus_physics import warmup_physics

    bench.autoanswer_dialogs()
    warmup_physics()
    app = CertusIndexApp()
    bench.attach_console_logging(app)
    app.load_file(str(book.resolve()))
    if analytic:
        saved = app._collect_config()
        saved["optimization"]["ir_analytic_polish"] = True
        app._apply_config(saved)
        if not app._collect_config()["optimization"]["ir_analytic_polish"]:
            raise RuntimeError("INDEX did not retain the loaded analytic-polish setting")
    cases = []
    ir_started = []
    result = {}
    loop = QEventLoop()
    configure = app._configure_and_start_optimization_worker
    run_ir = IRGlobalModelWorker.run
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def with_seed(config):
        if not config.lambda_min < 2200.0 or not config.lambda_max > 2500.0:
            raise ValueError("This workbook did not select the two-stage IR workflow")
        config.random_seed = seed
        if config.ir_analytic_polish != analytic:
            raise RuntimeError("The analytic-polish setting did not reach the worker configuration")
        configure(config)

    def compare(fun, x0, *args, **kwargs):
        if not (isinstance(fun, IRGlobalObjective) and kwargs.get("method") == "L-BFGS-B"
                and kwargs.get("options", {}).get("maxiter") in (3000, 5000)):
            return minimize(fun, x0, *args, **kwargs)
        if analytic:
            if kwargs.get("jac") != fun.polish_gradient:
                raise RuntimeError("The analytic gradient did not reach the worker polish")
            started = perf_counter()
            fitted = minimize(fun, x0, *args, **kwargs)
            stage = 0 if kwargs["options"]["maxiter"] == 3000 else 2
            cases.append({"stage": stage, "seconds": perf_counter() - started, "mse": float(fitted.fun)})
            return fitted
        ref, metrics = run_polishes(fun, x0, args, kwargs, minimize)
        stage = 0 if kwargs["options"]["maxiter"] == 3000 else 2
        cases.append({"stage": stage, "start": x0.tolist(), **metrics})
        print(f"Stage {stage}: {metrics}", flush=True)
        return ref

    def instrument_ir(worker):
        ir_started.append(True)
        worker.finished.connect(on_result)
        worker.error.connect(on_error)
        # SciPy is reached through the same module by the worker. The context covers only this run.
        with patch.object(optimize, "minimize", compare):
            run_ir(worker)

    def on_result(payload):
        result["ir_seconds"] = float(payload.execution_time)
        result["final_mse"] = float(payload.final_mse)
        loop.quit()

    def on_error(error):
        result["error"] = str(error)
        loop.quit()

    app._configure_and_start_optimization_worker = with_seed
    with patch.object(IRGlobalModelWorker, "run", instrument_ir):
        app.run_optimization()
        first = getattr(app, "_worker", None)
        if first is None:
            raise RuntimeError("INDEX did not start")
        first.error.connect(on_error)
        timer.start(bench.DEFAULT_TIMEOUT_MS)
        loop.exec()
        timer.stop()
    if not ir_started or "ir_seconds" not in result or [case["stage"] for case in cases] != [0, 2]:
        raise RuntimeError(f"INDEX did not return both infrared polishes: {result}")
    ecrire_json(out, {"source": book.name, "seed": seed, "analytic": analytic, "polishes": cases, **result})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--analytic", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    run(args.seed, args.book, args.out, args.analytic)


if __name__ == "__main__":
    main()
