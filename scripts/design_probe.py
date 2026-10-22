"""DESIGN probe: optimize a design outside the window, with the kernels of DESIGN, to try levers fast.

    python scripts/design_probe.py multistart --layers 26 --starts 200 [--seed 1] [--out F.jsonl] [--save F.json]
    python scripts/design_probe.py needle --layers 34 [--from F.json] [--seed 1] [--out F.jsonl] [--save F.json]

The cost and its analytic gradient are those of the DESIGN worker (`cost_numba_fast`,
`compute_gradient_all_layers_analytic`), evaluated on the fixed 0.5 nm grid of
`design_bench.py` rather than on the optimization grid of the window. The indices come from
the window's own materials. Normal incidence, front face only; layer 0 is on the substrate side.

multistart  N layers alternating H/L from the substrate, random thicknesses, L-BFGS-B from each
            start, keep the best: an estimate of the best RMSE reachable with N layers.
needle      start from --from (or an H/L quarter-wave pair), insert the 1 nm layer that lowers
            the cost most (every 2 nm, both materials), re-optimize, drop layers under
            --min-layer nm, until N layers or five insertions in a row that do not help.

`--save` writes a DESIGN file (same targets and materials as the config, thicknesses as QWOT at
l0 with n4, the DESIGN convention)

refine      from --from, alternate basin hopping (thicknesses x (1 + sigma N(0,1)), polish) and
            fixed-count needle swaps (drop the thinnest layer, insert the best needle, polish)
            for --rounds rounds, keeping every improvement. --min-nm bounds every layer.
memetic     --pop polished random designs (plus --from); --rounds children, each a block of
            layers from one parent inside the other, jittered 2 %, polished; replaces the worst. that `design_bench.py eval` judges independently.
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

import bench_examples as be  # noqa: E402
import design_bench as db  # noqa: E402

MAX_NM = 400.0
QWOT_PENALTY = 1e-2  # cost added per squared QWOT above --qwot-max; the cost itself is ~1e-6 here


class Problem:
    """Fixed-grid cost of a stack of materials, with the DESIGN kernels."""

    def __init__(self, config_path: Path) -> None:
        import numpy as np

        self.config_path = config_path
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        self.wls, self.tgt, self.w = db.target_grid(self.config)
        app = db.load(config_path)
        mats = app._get_materials()
        self.nk = {name: np.asarray(m.get_nk(self.wls), dtype=np.complex128) for name, m in mats.items()}
        # DESIGN converts QWOT and nm with n4 (the index at 400 nm), not n(l0): certus_design_ui_optimization.py.
        self.n4 = {name: float(getattr(m, "n4", 1.45)) for name, m in mats.items()}
        self.n_sub = np.ascontiguousarray(self.nk["Substrate"])
        self.l0 = float(self.config.get("l0", 500.0))
        self.i0 = int(np.argmin(np.abs(self.wls - self.l0)))
        self.evals = 0
        self._empty_c = np.zeros((len(self.wls), 0), dtype=np.complex128)
        self._empty_d = np.zeros(0, dtype=np.float64)
        self._cache: dict[str, object] = {}
        self.min_nm = 0.0  # lower bound of every layer in polish; > 0 forbids thin layers (no layer can vanish)
        self.optical = False  # polish in optical thickness n4 * d rather than in nm
        self.qw_max = 1.2  # random starts draw each layer uniformly in [0.05, qw_max] QWOT
        self.qwot_max: float | None = None  # ceiling on the total optical thickness (QWOT at l0, n4 convention)

    def n_T(self, mats: str):
        import numpy as np

        if mats not in self._cache:
            self._cache[mats] = np.ascontiguousarray(np.array([self.nk[m] for m in mats], dtype=np.complex128).T)
        return self._cache[mats]

    def cost(self, ep, mats: str) -> float:
        import numpy as np

        from certus.physics.gradient_utils import cost_numba_fast

        self.evals += 1
        return float(
            cost_numba_fast(np.ascontiguousarray(ep, dtype=np.float64), self.n_T(mats), self.n_sub, self.wls,
                            self.tgt, self.w, 0.0, False, self._empty_c, self._empty_d)
        )

    def cost_grad(self, ep, mats: str):
        import numpy as np

        from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic

        self.evals += 1
        c, g = compute_gradient_all_layers_analytic(
            np.ascontiguousarray(ep, dtype=np.float64), self.n_T(mats), self.n_sub, self.wls, self.tgt, self.w,
            0.0, False, self._empty_c, self._empty_d, None,
        )
        return float(c), np.asarray(g, dtype=np.float64)

    def polish(self, ep, mats: str, maxiter: int = 3000):
        """L-BFGS-B on the thicknesses; with `optical`, the variables are n4 * d (same scale for H and L)."""
        import numpy as np
        from scipy.optimize import minimize

        scale = np.array([self.n4[m] for m in mats]) if self.optical else np.ones(len(mats))

        q_per_nm = np.array([4.0 * self.n4[m] / self.l0 for m in mats])

        def f(x):
            d = x / scale
            c, g = self.cost_grad(d, mats)
            if self.qwot_max is not None:
                # Ceiling on the total optical thickness: quadratic penalty on the excess, with its gradient.
                excess = float(q_per_nm @ d) - self.qwot_max
                if excess > 0.0:
                    c += QWOT_PENALTY * excess * excess
                    g = g + 2.0 * QWOT_PENALTY * excess * q_per_nm
            return c, g / scale

        res = minimize(f, np.asarray(ep, dtype=np.float64) * scale, jac=True, method="L-BFGS-B",
                       bounds=[(self.min_nm * k, MAX_NM * k) for k in scale],
                       options={"maxiter": maxiter, "ftol": 1e-15, "gtol": 1e-12})
        return np.asarray(res.x) / scale, float(res.fun)

    def qwot(self, ep, mats: str):
        import numpy as np

        return [float(4.0 * self.n4[m] * d / self.l0) for m, d in zip(mats, np.asarray(ep), strict=True)]

    def save(self, path: Path, ep, mats: str) -> None:
        cfg = dict(self.config)
        cfg["front"] = [{"mat": m, "qw": round(q, 6), "var": True} for m, q in zip(mats, self.qwot(ep, mats), strict=True)]
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def clean(ep, mats: str, min_layer: float):
    """Drop layers thinner than min_layer and merge neighbours of the same material."""
    out_ep, out_m = [], []
    for d, m in zip(ep, mats, strict=True):
        if d < min_layer:
            continue
        if out_m and out_m[-1] == m:
            out_ep[-1] += float(d)
        else:
            out_ep.append(float(d))
            out_m.append(m)
    return out_ep, "".join(out_m)


def alternating(n: int, first: str = "H") -> str:
    other = "L" if first == "H" else "H"
    return "".join(first if i % 2 == 0 else other for i in range(n))


def multistart(p: Problem, n_layers: int, starts: int, rng, first: str = "H") -> dict:
    import numpy as np

    best = (np.inf, None, None)
    finals = []
    for _ in range(starts):
        mats = alternating(n_layers, rng.choice(["H", "L"]) if first == "random" else first)
        qw = rng.uniform(0.05, p.qw_max, n_layers)
        ep0 = np.array([q * p.l0 / (4.0 * p.n4[m]) for q, m in zip(qw, mats, strict=True)])
        ep, c = p.polish(ep0, mats)
        finals.append(float(np.sqrt(c)))
        if c < best[0]:
            best = (c, ep, mats)
    finals = np.sort(np.array(finals))
    return {"ep": best[1], "mats": best[2], "rmse": float(np.sqrt(best[0])),
            "spread": {"best": float(finals[0]), "p10": float(finals[len(finals) // 10]),
                       "median": float(np.median(finals))}}


def best_insertion(p: Problem, ep, mats: str, probe_nm: float, step_nm: float):
    """Try a thin layer of each material at every position; return the best (cost, ep, mats)."""
    import numpy as np

    base = p.cost(ep, mats)
    best = (base, None, None)
    for j, (d, m) in enumerate(zip(ep, mats, strict=True)):
        cuts = np.arange(step_nm / 2.0, d, step_nm)
        for new in ("H", "L"):
            if new == m:
                continue
            for z in cuts:
                trial_ep = [*ep[:j], z, probe_nm, d - z, *ep[j + 1:]]
                trial_m = mats[:j] + m + new + m + mats[j + 1:]
                c = p.cost(trial_ep, trial_m)
                if c < best[0]:
                    best = (c, trial_ep, trial_m)
    # A new layer on top of the stack (air side).
    new = "L" if mats[-1] == "H" else "H"
    c = p.cost([*ep, probe_nm], mats + new)
    if c < best[0]:
        best = (c, [*ep, probe_nm], mats + new)
    return best


def needle(p: Problem, ep, mats: str, n_target: int, min_layer: float, log) -> dict:
    import numpy as np

    ep, c = p.polish(ep, mats)
    ep, mats = clean(ep, mats, min_layer)
    ep, c = p.polish(ep, mats)
    history = [(len(mats), float(np.sqrt(c)))]
    stalls = 0
    while len(mats) < n_target and stalls < 5:
        _c_ins, ep_ins, m_ins = best_insertion(p, np.asarray(ep), mats, probe_nm=1.0, step_nm=2.0)
        if ep_ins is None:
            break
        ep_new, c_new = p.polish(ep_ins, m_ins)
        ep_new, m_new = clean(ep_new, m_ins, min_layer)
        ep_new, c_new = p.polish(ep_new, m_new)
        if c_new < c * (1 - 1e-6):
            ep, mats, c = list(ep_new), m_new, c_new
            stalls = 0
        else:
            stalls += 1
        history.append((len(mats), float(np.sqrt(c))))
        log(f"needle layers={len(mats)} rmse={np.sqrt(c):.6f} evals={p.evals}")
    return {"ep": np.asarray(ep), "mats": mats, "rmse": float(np.sqrt(c)), "history": history}


def refine(p: Problem, ep, mats: str, rounds: int, sigma: float, rng, log) -> dict:
    """Basin hopping and fixed-count needle swaps from a design; keep every improvement.

    Odd rounds: multiply each thickness by (1 + sigma * N(0, 1)), polish. Even rounds: remove the
    thinnest layer (merging its neighbours), insert the best 1 nm needle, polish. Same layer count.
    """
    import numpy as np

    ep, c = p.polish(np.asarray(ep, dtype=float), mats)
    n_target = len(mats)
    trace = [float(np.sqrt(c))]
    for r in range(rounds):
        if r % 2 == 0:
            trial = np.clip(ep * (1.0 + sigma * rng.standard_normal(len(ep))), p.min_nm, MAX_NM)
            t_ep, t_c = p.polish(trial, mats)
            t_m = mats
        else:
            j = int(np.argmin(ep))
            cut_ep, cut_m = clean(np.where(np.arange(len(ep)) == j, 0.0, ep), mats, 1e-9)
            if len(cut_m) < 2:
                continue
            t_ep, t_m = list(cut_ep), cut_m
            while len(t_m) < n_target:
                _c, ins_ep, ins_m = best_insertion(p, np.asarray(t_ep), t_m, probe_nm=max(1.0, p.min_nm), step_nm=2.0)
                if ins_ep is None:
                    break
                t_ep, t_m = ins_ep, ins_m
            if len(t_m) != n_target:
                continue
            t_ep, t_c = p.polish(np.asarray(t_ep), t_m)
        if t_c < c * (1 - 1e-9):
            ep, mats, c = np.asarray(t_ep), t_m, t_c
            log(f"refine round={r} rmse={np.sqrt(c):.7f} layers={len(mats)} evals={p.evals}")
        trace.append(float(np.sqrt(c)))
    return {"ep": ep, "mats": mats, "rmse": float(np.sqrt(c)), "history": trace[:: max(1, len(trace) // 40)]}


def memetic(p: Problem, n_layers: int, pop_size: int, children: int, rng, first: str, log, seeds=(), seed_mats="",
            child_iter: int = 0) -> dict:
    """Population of polished designs; a child takes a block of layers from each parent, then is polished.

    Same layer count and alternation for everyone, so any cut point gives a valid stack. The child
    replaces the worst member when it beats it and is not a copy of a member already there.
    """
    import numpy as np

    # One alternation for the whole population, so that any cut point gives a valid child.
    mats = seed_mats or alternating(n_layers, rng.choice(["H", "L"]) if first == "random" else first)
    n_layers = len(mats)

    def random_design():
        qw = rng.uniform(0.05, p.qw_max, n_layers)
        return np.array([q * p.l0 / (4.0 * p.n4[m]) for q, m in zip(qw, mats, strict=True)])

    pop = [p.polish(np.asarray(s, dtype=float), mats) for s in seeds]
    while len(pop) < pop_size:
        pop.append(p.polish(random_design(), mats))
    for g in range(children):
        i, j = rng.choice(len(pop), 2, replace=False)
        a, b = pop[i][0], pop[j][0]
        lo, hi = sorted(rng.choice(np.arange(1, n_layers), 2, replace=False))
        child = a.copy()
        child[lo:hi] = b[lo:hi]
        child *= 1.0 + 0.02 * rng.standard_normal(n_layers)
        worst = int(np.argmax([m[1] for m in pop]))
        if child_iter:
            # Cheap screening: a short polish first; only a child that already beats the worst gets the full one.
            ep, c = p.polish(np.clip(child, p.min_nm, MAX_NM), mats, maxiter=child_iter)
            if c < pop[worst][1]:
                ep, c = p.polish(ep, mats)
        else:
            ep, c = p.polish(np.clip(child, p.min_nm, MAX_NM), mats)
        duplicate = any(abs(c - m[1]) < 1e-12 * max(c, 1e-30) for m in pop)
        if c < pop[worst][1] and not duplicate:
            pop[worst] = (ep, c)
        if g % 25 == 0:
            costs = sorted(m[1] for m in pop)
            log(f"memetic child={g} best={np.sqrt(costs[0]):.7f} median={np.sqrt(costs[len(costs) // 2]):.7f} evals={p.evals}")
    best = min(pop, key=lambda m: m[1])
    return {"ep": best[0], "mats": mats, "rmse": float(np.sqrt(best[1]))}


def main() -> None:
    import numpy as np

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["multistart", "needle", "refine", "memetic"])
    ap.add_argument("--config", type=Path, default=db.DEFAULT_CONFIG)
    ap.add_argument("--layers", type=int, default=26)
    ap.add_argument("--starts", type=int, default=100)
    ap.add_argument("--from", dest="start_file", type=Path, default=None)
    ap.add_argument("--min-layer", type=float, default=1.0)
    ap.add_argument("--min-nm", type=float, default=0.0, help="lower bound of every layer (manufacturing)")
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--pop", type=int, default=30)
    ap.add_argument("--child-iter", type=int, default=0, help="memetic: short polish of each child before the full one")
    ap.add_argument("--qw-max", type=float, default=1.2, help="random starts: upper QWOT of each layer")
    ap.add_argument("--optical", action="store_true", help="polish in optical thickness n4*d")
    ap.add_argument("--qwot-max", type=float, default=None, help="ceiling on the total optical thickness (QWOT)")
    ap.add_argument("--first", choices=["H", "L", "random"], default="random",
                    help="material of the layer on the substrate (random: drawn at each start)")
    ap.add_argument("--sigma", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--save", type=Path, default=None)
    args = ap.parse_args()

    be.qapp()
    be.autoanswer_dialogs(True)
    import certus_physics

    certus_physics.warmup_physics()
    p = Problem(args.config)
    p.min_nm = args.min_nm
    p.optical = args.optical
    p.qw_max = args.qw_max
    p.qwot_max = args.qwot_max
    rng = np.random.default_rng(args.seed)
    t0 = time.perf_counter()
    if args.mode == "multistart":
        res = multistart(p, args.layers, args.starts, rng, args.first)
    elif args.mode == "memetic":
        seeds, seed_mats = [], ""
        if args.start_file:
            start = db.load(args.start_file)
            seeds = [np.asarray(start.ep_current, dtype=float)]
            seed_mats = "".join(layer.mat for layer in start._get_front_stack())
        res = memetic(p, args.layers, args.pop, args.rounds, rng, args.first, be.emit, seeds, seed_mats, args.child_iter)
    elif args.mode == "refine":
        start = db.load(args.start_file)
        res = refine(p, np.asarray(start.ep_current, dtype=float), "".join(layer.mat for layer in start._get_front_stack()),
                     args.rounds, args.sigma, rng, be.emit)
    else:
        if args.start_file:
            start = db.load(args.start_file)
            ep0 = np.asarray(start.ep_current, dtype=float)
            mats0 = "".join(layer.mat for layer in start._get_front_stack())
        else:
            mats0 = "HL"
            ep0 = np.array([p.l0 / (4 * p.n4[m]) for m in mats0])
        res = needle(p, ep0, mats0, args.layers, args.min_layer, be.emit)
    ep = np.asarray(res["ep"])
    row = {
        "mode": args.mode, "label": args.label, "seed": args.seed, "min_nm": args.min_nm,
        "rmse_grid": float(np.sqrt(p.cost(ep, res["mats"]))),  # without the QWOT penalty
        "rmse_search": res["rmse"],
        "layers": len(res["mats"]), "materials": res["mats"], "total_nm": float(ep.sum()),
        "thinnest_nm": float(ep.min()), "total_qwot": float(sum(p.qwot(ep, res["mats"]))),
        "qw_max": args.qw_max, "optical": args.optical, "qwot_max": args.qwot_max, "child_iter": args.child_iter,
        "pop": args.pop, "rounds": args.rounds, "evals": p.evals, "run_s": round(time.perf_counter() - t0, 1),
        **{k: res[k] for k in ("spread", "history") if k in res},
        "ep": [round(float(x), 4) for x in ep],
    }
    line = json.dumps(row)
    be.emit("ROW=" + line)
    if args.out:
        with args.out.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    if args.save:
        p.save(args.save, ep, res["mats"])
    sys.stdout.flush()
    import os

    os._exit(0)


if __name__ == "__main__":
    main()
