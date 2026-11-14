"""Profile FIELD's local optimization and cleanup through its window's worker."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import bench_examples as bench
import numpy as np
from _artefact import ecrire_json


def run(seed, out, paired, analytic):
    bench.qapp()
    from certus.ui.certus_field_ui import CertusFieldApp
    from certus.workers import certus_field_workers as workers
    from certus.workers.certus_field_workers_dto import FieldWorkerRequest

    np.random.seed(seed)
    bench.autoanswer_dialogs()
    start_worker = CertusFieldApp._start_worker
    minimize = workers.minimize
    cases, results, inputs, parameters = [], [], [], []

    def optimize(app, request):
        app.auto_calc_timer.stop()
        if analytic:
            saved = {**app._collect_config(), "analytic_gradient": True}
            app._apply_config(saved)
            app.auto_calc_timer.stop()
            request = FieldWorkerRequest(action="optimize", params=app._get_params())
            if not app._collect_config()["analytic_gradient"] or not request.params.analytic_gradient:
                raise RuntimeError("FIELD did not retain and transmit the analytic-gradient setting")
        inputs.append(request.params.model_dump())
        parameters.append(request.params)
        request = FieldWorkerRequest(action="optimize", params=request.params)
        start_worker(app, request)
        app.worker.signals.finished.connect(results.append)

    def timed(fun, x0, *args, **kwargs):
        if analytic and not callable(kwargs.get("jac")):
            raise RuntimeError("The FIELD derivative did not reach the local polish")
        calls = 0
        cost_seconds = 0.0

        def cost(x):
            nonlocal calls, cost_seconds
            calls += 1
            begin = perf_counter()
            value = fun(x)
            cost_seconds += perf_counter() - begin
            return value

        begin = perf_counter()
        fit = minimize(cost, x0, *args, **kwargs)
        cases.append({"start": np.asarray(x0).tolist(), "seconds": perf_counter() - begin,
                      "cost_seconds": cost_seconds, "cost_calls": calls, "cost": float(fit.fun),
                      "iterations": int(fit.nit), "cleanup": "callback" not in kwargs})
        if paired and "callback" in kwargs:
            params = parameters[-1].model_copy(update={"analytic_gradient": True})
            jac = workers._field_gradient_options(fun, params)["jac"]
            jac(x0)
            begin = perf_counter()
            candidate = minimize(fun, x0.copy(), *args, **kwargs, jac=jac)
            cases[-1]["paired"] = {"seconds": perf_counter() - begin, "cost": float(candidate.fun),
                                   "iterations": int(candidate.nit), "cost_calls": int(candidate.nfev),
                                   "gradient_calls": int(candidate.njev), "success": bool(candidate.success)}
        return fit

    with patch.object(CertusFieldApp, "_start_worker", optimize), patch.object(workers, "minimize", timed):
        setup, elapsed, _result = bench.run_field()
    if not cases or len(results) != 1 or not results[0].success:
        raise RuntimeError("FIELD did not return a successful optimization result")
    ecrire_json(out, {"seed": seed, "analytic": analytic, "setup_seconds": setup, "workflow_seconds": elapsed,
                      "inputs": inputs, "polishes": cases, "result": results[0].__dict__})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--paired", action="store_true")
    mode.add_argument("--analytic", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    run(args.seed, args.out, args.paired, args.analytic)


if __name__ == "__main__":
    main()
