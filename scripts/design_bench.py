"""DESIGN bench: run the real workflow headless, then judge the result on a fixed grid.

    python scripts/design_bench.py run  [--config FILE] [--label L] [--out FILE.jsonl] [--kw KEY=VALUE ...] [--set NAME=VALUE ...]
    python scripts/design_bench.py eval FILE.json [FILE.json ...] [--out FILE.jsonl]

`run` loads a design file, launches the global workflow (PGLOBAL, cleanup, healing, needle,
prune, polish) exactly as `bench_examples.py design` does, and waits for its end. `eval` only
loads each file and judges the stack it holds, without optimizing.

Each stack is judged the same way, whatever grid the optimizer used: normal incidence, front
face only (semi-infinite substrate), one point every 0.5 nm over the span of the targets, and
the weighted RMSE against them. T is computed twice, by the certus kernel and by the independent
oracle `tests/oracle/tmm_reference.py`; `oracle_max_dT` is their largest gap, which must stay
near 1e-12. The RMSE of the window (`rmse_app`, on the optimization grid) is reported beside it.

One JSON line per stack: rmse_grid, max_dev (largest |T - target|), layers, total physical and
optical thickness, thinnest layer, cost and gradient evaluations, wall time. Only one run per
process: repeat with a shell loop, so that each run starts cold. PGLOBAL draws a new Sobol
scramble at each run (no fixed seed), so repeats measure the spread of the workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

import bench_examples as be  # noqa: E402  (sets the offscreen platform, keeps the real stdout)

DEFAULT_CONFIG = ROOT / "example" / "example_design" / "JSON-design-example.json"
GRID_STEP_NM = 0.5
COUNTS = {"cost": 0, "grad": 0}


def count_evaluations() -> None:
    """Count the cost and gradient kernel calls made through the DESIGN wrappers."""
    from certus.core import certus_design_core as dc

    cost, grad = dc.cost_numba_fast, dc.compute_gradient_all_layers_analytic

    def cost_counted(*a, **k):
        COUNTS["cost"] += 1
        return cost(*a, **k)

    def grad_counted(*a, **k):
        COUNTS["grad"] += 1
        return grad(*a, **k)

    dc.cost_numba_fast = cost_counted
    dc.compute_gradient_all_layers_analytic = grad_counted


def target_grid(config: dict):
    """Fixed grid over the active targets, with the target value and weight at each point."""
    import numpy as np

    wls, vals, weights = [], [], []
    for t in config.get("targets", []):
        if not t.get("on", t.get("active", True)):
            continue
        lmin, lmax = float(t["lmin"]), float(t["lmax"])
        n = round((lmax - lmin) / GRID_STEP_NM) + 1
        w = np.linspace(lmin, lmax, n)
        lo, hi = float(t.get("tmin", t.get("val_min"))), float(t.get("tmax", t.get("val_max")))
        wls.append(w)
        vals.append(lo + (hi - lo) * (w - lmin) / max(lmax - lmin, 1e-12))
        weights.append(np.full(n, float(t.get("w", t.get("weight", 1.0)))))
    return np.concatenate(wls), np.concatenate(vals), np.concatenate(weights)


def judge(app, config: dict) -> dict:
    """Judge the stack held by the window on the fixed grid."""
    import numpy as np
    from tmm_reference import rt_stack

    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside

    if config.get("oblique_mode"):
        raise SystemExit("oblique designs are not judged by this bench")
    wls, tgt, w = target_grid(config)
    stack = app._get_front_stack()
    ep = np.ascontiguousarray(np.asarray(app.ep_current, dtype=np.float64))
    mats = app._get_materials()
    nk = {name: np.asarray(m.get_nk(wls)) for name, m in mats.items()}
    n_sub = np.ascontiguousarray(nk["Substrate"].astype(np.complex128))
    if len(stack) != len(ep):
        # The table and the thicknesses of the window disagree: report it rather than judge a guess.
        return {"error": "table_and_thicknesses_disagree", "table_layers": len(stack), "ep_layers": len(ep),
                "materials": "".join(layer.mat for layer in stack), "ep": [round(float(x), 4) for x in ep]}
    n_layers = np.array([nk[layer.mat] for layer in stack], dtype=np.complex128)  # index 0 = substrate side

    _r, t_certus = calculate_RT_no_backside(ep, np.ascontiguousarray(n_layers.T), n_sub, wls)
    t_oracle = np.array(
        [rt_stack(wl, n_layers[:, i], ep, n_sub=n_sub[i])[1] for i, wl in enumerate(wls)]
    )

    def rmse(t):
        return float(np.sqrt(np.sum(w * (t - tgt) ** 2) / np.sum(w)))

    l0 = float(config.get("l0", 500.0))
    i0 = int(np.argmin(np.abs(wls - l0)))
    present = ep > 1e-9
    return {
        "rmse_grid": rmse(t_certus),
        "rmse_grid_oracle": rmse(t_oracle),
        "oracle_max_dT": float(np.max(np.abs(t_certus - t_oracle))),
        "max_dev": float(np.max(np.abs(t_certus - tgt))),
        "grid_points": len(wls),
        "layers": int(np.count_nonzero(present)),
        "materials": "".join(layer.mat for layer, p in zip(stack, present, strict=True) if p),
        "total_nm": float(np.sum(ep)),
        "total_qwot_at_l0": float(np.sum(4.0 * n_layers[:, i0].real * ep / l0)),
        "thinnest_nm": float(np.min(ep[present])) if present.any() else None,
        "ep": [round(float(x), 4) for x in ep],
    }


def save_design(app, config: dict, path: Path) -> None:
    """Write the window's final stack into a copy of the configuration (QWOT with n4, as DESIGN does)."""
    import numpy as np

    mats = app._get_materials()
    l0 = float(config.get("l0", 500.0))
    ep = np.asarray(app.ep_current, dtype=float)
    out = dict(config)
    out["front"] = [{"mat": layer.mat, "qw": round(4.0 * float(mats[layer.mat].n4) * float(d) / l0, 6), "var": True}
                    for layer, d in zip(app._get_front_stack(), ep, strict=True)]
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def load(path: Path):
    from CERTUS_DESIGN import CertusDesignApp

    app = CertusDesignApp()
    app._post_load_config = lambda *a: None  # no summary dialog; see bench_examples.run_design
    window_log = app.log

    def log_too(msg: str, lvl: str = "INFO") -> None:  # the workflow speaks only to the window's log panel
        ep = getattr(app, "ep_current", None)
        state = f"rows={app.front_table.rowCount()} ep={len(ep) if ep is not None else None}"
        be.emit(f"LOG [{lvl}] ({state}) {msg}")
        window_log(msg, lvl)

    app.log = log_too
    app.load_config(str(path))
    app._last_config_file = str(path)
    return app


def wait_for_workflow(app) -> tuple[int, float]:
    """Wait until the optimization thread has been quiet for 20 s after at least one pass."""
    from PyQt6.QtCore import QEventLoop, QTimer

    passes = {"n": 0, "quiet": 0.0, "elapsed": 0.0}
    app.optimization_finished_signal.connect(lambda: passes.update(n=passes["n"] + 1))
    loop = QEventLoop()
    tick_ms = 250

    def tick() -> None:
        passes["elapsed"] += tick_ms / 1000.0
        th = getattr(app, "optim_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        passes["quiet"] = 0.0 if running else passes["quiet"] + tick_ms / 1000.0
        if (passes["quiet"] >= 20.0 and passes["n"] > 0) or passes["elapsed"] >= 3600.0:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(tick_ms)
    loop.exec()
    timer.stop()
    return passes["n"], passes["quiet"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["run", "eval"])
    p.add_argument("files", nargs="*", type=Path)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--label", default="")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--kw", action="append", default=[], metavar="KEY=VALUE",
                   help="extra argument of run_optim('global', ...), e.g. memetic_children=300 (repeatable)")
    p.add_argument("--save-design", type=Path, default=None,
                   help="run: write the final design of the window as a DESIGN file (QWOT with n4)")
    p.add_argument("--set", dest="attrs", action="append", default=[], metavar="NAME=VALUE",
                   help="window attribute set after loading, e.g. _polish_after_5nm_rule=true (repeatable)")
    args = p.parse_args()
    window_attrs = {}
    for item in args.attrs:
        key, _, value = item.partition("=")
        window_attrs[key] = json.loads(value)
    run_kwargs = {}
    for item in args.kw:
        key, _, value = item.partition("=")
        run_kwargs[key] = json.loads(value)

    be.qapp()
    be.autoanswer_dialogs(True)
    import certus_physics

    certus_physics.warmup_physics()

    rows = []
    if args.mode == "eval":
        for f in args.files or [args.config]:
            config = json.loads(f.read_text(encoding="utf-8"))
            rows.append({"mode": "eval", "file": f.name, **judge(load(f), config)})
    else:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        count_evaluations()
        app = load(args.config)
        for key, value in window_attrs.items():
            setattr(app, key, value)
        t0 = time.perf_counter()
        app.run_optim("global", **run_kwargs)
        n_passes, quiet = wait_for_workflow(app)
        run_s = time.perf_counter() - t0 - quiet
        rows.append(
            {
                "mode": "run",
                "label": args.label,
                "file": args.config.name,
                "kwargs": run_kwargs,
                "window_attrs": window_attrs,
                "rmse_app": float(getattr(app, "_workflow_best_rmse", float("nan"))),
                "table_layers": app.front_table.rowCount(),
                **judge(app, config),
                "passes": n_passes,
                "cost_evals": COUNTS["cost"],
                "grad_evals": COUNTS["grad"],
                "run_s": round(run_s, 1),
                "timeout": run_s >= 3600.0 - 1.0,
            }
        )
        if args.save_design:
            save_design(app, config, args.save_design)

    for row in rows:
        line = json.dumps(row)
        be.emit("ROW=" + line)
        if args.out:
            with args.out.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    be.emit("DONE")
    sys.stdout.flush()
    import os

    os._exit(0)


if __name__ == "__main__":
    main()
