"""Parallel memetic run (steady state) of engine.py under explicit resources; RICL 2026-11-05.

usage:
  python run.py --problem threeline --tag T --minutes M --nmax 101 --tot 14171 --floor 5 --seeds a.csv b.csv ...
  (fixed-N constrained problem: --fixed HLHL... --otlo 100 --othi 350, no --tot)
Seeds: CSV files with columns seq and d_nm (physical nm, layer 0 on the substrate side), optional name; every row is
a seed, unless --seed-best K keeps the K best rows of each file (by an mf column if present).
Lineage: every design carries the names of the seeds it descends from ("roots").
Outputs (in this folder): {tag}_best.csv (every new best, full precision, oracle checked), {tag}_elites.csv
(population snapshot), {tag}.log (progress and move statistics). Workers: --workers (default cpu - 1).
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import engine as E
import numpy as np

HERE = Path(__file__).resolve().parent
PROB = None
RULES = None


def init_worker(problem: str, points: int, rules_kw: dict) -> None:
    global PROB, RULES
    PROB = E.make_problem(problem, points=points)
    RULES = E.Rules(**rules_kw)


def task(move: str, parents, seed: int):
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    try:
        out = E.mutate(PROB, RULES, parents, move, rng)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, IndexError):
        out = None
    dt = time.perf_counter() - t0
    if out is None:
        return move, None, dt
    seq, d, r = out
    if not E.admissible(RULES, seq, d):
        return move, None, dt
    return move, (seq, d, r), dt


def settle_task(seq: str, d: np.ndarray, seed: int):
    rng = np.random.default_rng(seed)
    d = E.scale_tot(seq, d, RULES.tot)
    s2, d2, r2 = E.settle(PROB, RULES, seq, d)
    if RULES.fixed_seq is None:
        s2, d2, r2 = E.cap(PROB, RULES, s2, d2, r2, rng)
    if not E.admissible(RULES, s2, d2):
        return None
    return s2, d2, r2


def polish_task(seq: str, d: np.ndarray):
    lb, ub = RULES.bounds(seq)
    x, r, _ = E.lm(PROB, seq, d, RULES.tot, lb, ub, 3000, 1e-15)
    if not E.admissible(RULES, seq, x):
        return seq, d, PROB.rmse(seq, d)
    return seq, x, r


def read_seeds(files, best_k: int):
    out = []
    for f in files:
        stem = Path(f).stem
        if not Path(f).exists():
            print(f"seed file missing, skipped: {f}", flush=True)
            continue
        with open(f, encoding="utf-8-sig", newline="") as h:
            rows = list(csv.DictReader(h))
        key = next((k for k in ("mf", "mf_oracle", "mf_kernel", "mf_nominal", "rmse") if rows and k in rows[0]),
                   None)
        if best_k and key:
            rows = sorted(rows, key=lambda r: float(r[key]) if r[key] not in ("", "nan") else 1e9)[:best_k]
        for k, r in enumerate(rows):
            seq = r["seq"]
            d = np.array([float(v) for v in r["d_nm"].split()])
            if len(seq) == len(d) and len(seq) > 0:
                out.append((seq, d, r.get("name") or f"{stem}#{k}"))
    return out


class Population:
    """Elites sorted by MF; a child entering the same basin as an elite (same sequence, thicknesses within 2 nm)
    replaces it only if better."""

    def __init__(self, size: int):
        self.size = size
        self.items: list[tuple[float, str, np.ndarray, str]] = []

    def add(self, seq: str, d: np.ndarray, r: float, roots: str = "") -> bool:
        if not np.isfinite(r):
            return False
        for k, (r0, s0, d0, _f0) in enumerate(self.items):
            if s0 == seq and abs(r0 - r) <= 1e-7 * r0 + 1e-15:
                return False
            if s0 == seq and len(d0) == len(d) and np.max(np.abs(d0 - d)) < 2.0:
                if r < r0:
                    self.items[k] = (r, seq, d, roots)
                    self.items.sort(key=lambda t: t[0])
                    return True
                return False
        if len(self.items) >= self.size and r >= self.items[-1][0]:
            return False
        self.items.append((r, seq, d, roots))
        self.items.sort(key=lambda t: t[0])
        del self.items[self.size:]
        return True

    def pick(self, rng: np.random.Generator):
        k = min(int(len(self.items) * rng.random() ** 2), len(self.items) - 1)
        return self.items[k]


def join_roots(parents) -> str:
    names = set()
    for p in parents:
        names.update(x for x in p[3].split("+") if x)
    return "+".join(sorted(names))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="threeline")
    ap.add_argument("--points", type=int, default=1601)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--nmax", type=int, default=101)
    ap.add_argument("--tot", type=float, default=None)
    ap.add_argument("--floor", type=float, default=0.1)  # owner rule 2026-11-06: search floor 0.1 nm, physical floor only in the final cleaning (audit 2026-11-07)
    ap.add_argument("--otlo", type=float, default=None)
    ap.add_argument("--othi", type=float, default=None)
    ap.add_argument("--fixed", default=None)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seed-best", type=int, default=0)
    ap.add_argument("--moves", default="jitter:3,needle:3,remove:2,halfwave:1,cross:2,swap:1")
    ap.add_argument("--rng", type=int, default=12345)
    a = ap.parse_args()

    rules_kw = dict(nmax=a.nmax, tot=a.tot, floor=a.floor, otlo=a.otlo, othi=a.othi, fixed_seq=a.fixed,
                    iters=a.iters)
    prob = E.make_problem(a.problem, points=a.points)
    moves = [(m.split(":")[0], float(m.split(":")[1])) for m in a.moves.split(",")]
    names = [m for m, _w in moves]
    weights = np.array([w for _m, w in moves])
    weights /= weights.sum()
    rng = np.random.default_rng(a.rng)
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    say(f"start {vars(a)}")
    best_path = HERE / f"{a.tag}_best.csv"
    pop = Population(a.pop)
    best = [np.inf]
    deadline = time.time() + 60.0 * a.minutes
    stats = {m: [0, 0, 0.0] for m in names}  # tried, entered, seconds
    pend_polish: dict = {}

    def record(seq: str, d: np.ndarray, r: float, origin: str, roots: str) -> None:
        o = prob.oracle_rmse(seq, d)
        row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "origin": origin, "roots": roots, "layers": len(seq),
               "tot_nm": f"{E.total_ot(seq, d):.6f}", "thinnest_nm": f"{float(np.min(d)):.6f}",
               "mf": f"{prob.scale * r:.12g}", "mf_oracle": f"{prob.scale * o:.12g}", "seq": seq,
               "d_nm": " ".join(f"{v:.9f}" for v in d)}
        new = not best_path.exists()
        with best_path.open("a", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
        say(f"BEST {prob.scale * r:.9g} (oracle {prob.scale * o:.9g}) N {len(seq)} TOT {E.total_ot(seq, d):.3f} "
            f"thinnest {float(np.min(d)):.2f} nm via {origin} from {roots}")

    def snapshot() -> None:
        with (HERE / f"{a.tag}_elites.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.writer(h)
            w.writerow(["rank", "mf", "layers", "tot_nm", "thinnest_nm", "roots", "seq", "d_nm"])
            for k, (r, s, d, f) in enumerate(pop.items):
                w.writerow([k, f"{prob.scale * r:.12g}", len(s), f"{E.total_ot(s, d):.6f}", f"{float(np.min(d)):.6f}",
                            f, s, " ".join(f"{v:.9f}" for v in d)])

    def consider(seq: str, d: np.ndarray, r: float, origin: str, roots: str, ex: ProcessPoolExecutor) -> bool:
        entered = pop.add(seq, d, r, roots)
        if r < best[0] * (1 - 1e-9):
            best[0] = r
            pend_polish[ex.submit(polish_task, seq, d)] = roots
            record(seq, d, r, origin, roots)
        return entered

    with ProcessPoolExecutor(a.workers, initializer=init_worker, initargs=(a.problem, a.points, rules_kw)) as ex:
        seeds = read_seeds(a.seeds, a.seed_best)
        say(f"{len(seeds)} seeds")
        futs = [(ex.submit(settle_task, s, d, int(rng.integers(1 << 31))), name) for s, d, name in seeds]
        for f, name in futs:
            out = f.result()
            if out is not None:
                consider(*out, "seed", name, ex)
        if not pop.items:
            say("no admissible seed")
            return
        say(f"population {len(pop.items)} after seeds; best {prob.scale * best[0]:.9g}")
        inflight: dict = {}
        last_snap = last_stat = time.time()
        n_done = 0
        while time.time() < deadline:
            while len(inflight) < 2 * a.workers:
                mv = names[int(rng.choice(len(names), p=weights))]
                par = [pop.pick(rng)]
                if mv == "cross":
                    par.append(pop.pick(rng))
                f = ex.submit(task, mv, [(p[1], p[2]) for p in par], int(rng.integers(1 << 31)))
                inflight[f] = (mv, join_roots(par))
            done, _ = wait(list(inflight), timeout=30, return_when=FIRST_COMPLETED)
            for f in done:
                mv, roots = inflight.pop(f)
                move, out, dt = f.result()
                stats[move][0] += 1
                stats[move][2] += dt
                n_done += 1
                if out is not None and consider(*out, move, roots, ex):
                    stats[move][1] += 1
            for f in [f for f in pend_polish if f.done()]:
                roots = pend_polish.pop(f)
                s, d, r = f.result()
                consider(s, d, r, "polish", roots, ex)
            if time.time() - last_snap > 300:
                snapshot()
                last_snap = time.time()
            if time.time() - last_stat > 900:
                txt = " ".join(f"{m}:{v[0]}/{v[1]}/{v[2] / max(v[0], 1):.1f}s" for m, v in stats.items())
                say(f"done {n_done} best {prob.scale * best[0]:.9g} pop [{prob.scale * pop.items[0][0]:.6g}.."
                    f"{prob.scale * pop.items[-1][0]:.6g}] moves {txt}")
                last_stat = time.time()
        for f in inflight:
            f.cancel()
        for f, roots in list(pend_polish.items()):
            s, d, r = f.result()
            consider(s, d, r, "polish", roots, ex)
        snapshot()
    txt = " ".join(f"{m}:{v[0]}/{v[1]}/{v[2] / max(v[0], 1):.1f}s" for m, v in stats.items())
    say(f"end best {prob.scale * best[0]:.9g} moves {txt}")


if __name__ == "__main__":
    main()
