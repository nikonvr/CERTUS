"""Dense resource curves for the RICL article (2026-11-05): the best design at each point of a fine grid.

sweep2 (2026-11-05, evening): sweep.py plus the evolution step of Trubetskov (AO 59, A75, 2020) as a transfer in mode
tot: from the best design of a lower grid TOT, ONE layer is thickened (or a new outer layer added) so that the TOT
reaches the target exactly; every layer is screened by its unrefined MF, the --grow-top best are refined at the
target TOT and the best is filed. With every grid point fed by several lower points, the sweep is a dynamic
programme over the TOT that generalizes his deep gradual evolution (one trajectory) to one best design per TOT.

mode tot : every grid TOT T_k is imposed exactly (equality), N <= nmax, physical floor;
mode n   : every number of layers N is imposed exactly, TOT <= cap (--tot with --tot-le) or free, floor.
Each round: (1) transfer of the best design of the neighbouring grid points (scaled to T_k, or brought to N layers by
needle insertion / end layer / layer removal), (2) random structural moves of engine.mutate on the best design of each
point, (3) fresh random starts at empty points. A point keeps the best design ever filed under it; results are filed
under their actual key (a removal can move a design to another N). The curve is the set of these points: no cap
envelope, no staircase. Oracle MF of every point at the end.

usage: python sweep.py --problem threeline --mode tot --grid 100:15000:50 --nmax 200 --floor 5 --tag T --minutes M
       python sweep.py --problem bs5050 --points 1601 --mode n --grid 1:40:1 --tot 4000 --tot-le --tag T --minutes M
outputs: {tag}_curve.csv (rewritten after every round), {tag}.log
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


def init_worker(problem: str, points: int) -> None:
    global PROB
    PROB = E.make_problem(problem, points=points)


def rules_of(kw: dict) -> E.Rules:
    return E.Rules(**kw)


def to_n(seq: str, d: np.ndarray, n: int, rules: E.Rules, rng: np.random.Generator):
    """Bring a design to exactly n layers: needles (+2) or an end layer (+1), interior (-2) or end (-1) removals,
    each followed by a settle. Gives up after 12 steps (the result is filed under its actual N)."""
    loose = E.Rules(nmax=10**6, tot=rules.tot, floor=rules.floor, iters=rules.iters, tot_le=rules.tot_le)
    seq, d, r = E.settle(PROB, loose, seq, E.scale_tot(seq, d, rules.tot, rules.tot_le))
    for _ in range(12):
        m = len(seq)
        if m == n:
            break
        if m < n:
            p = E.p_function(PROB, seq, d)
            if n - m >= 2:
                inner = [t for t in p if 0 <= t[1] < m and t[2] > rules.floor and d[t[1]] - t[2] > rules.floor]
                if not inner:
                    inner = [t for t in p if 0 <= t[1] < m]
                _g, i, z = min(inner) if inner else min(p)
            else:
                ends = [t for t in p if t[1] in (-1, m)]
                _g, i, z = min(ends)
            s2, d2 = E.insert_needle(seq, d, i, z, max(rules.floor, 1.0))
        elif m - n >= 2:
            order = np.argsort(E.nvec(seq) * d)
            cands = [int(k) for k in order if 0 < k < m - 1][:6]
            best = None
            for k in cands:
                s2, d2 = E.remove_layer(seq, d, k)
                x, r2, _ = E.lm(PROB, s2, d2, rules.tot if not rules.tot_le else None, 0.0, None, 60)
                if best is None or r2 < best[2]:
                    best = (s2, x, r2)
            s2, d2 = best[0], best[1]
        else:
            best = None
            for k in (0, m - 1):
                s2, d2 = E.remove_layer(seq, d, k)
                x, r2, _ = E.lm(PROB, s2, d2, rules.tot if not rules.tot_le else None, 0.0, None, 60)
                if best is None or r2 < best[2]:
                    best = (s2, x, r2)
            s2, d2 = best[0], best[1]
        seq, d, r = E.settle(PROB, loose, s2, E.scale_tot(s2, d2, rules.tot, rules.tot_le))
    return seq, d, r


def fresh(mode: str, key: float, rules: E.Rules, rng: np.random.Generator):
    if mode == "tot":
        m = max(1, int(key / float(rng.uniform(120.0, 200.0))))
    else:
        m = int(key)
    first = "H" if rng.random() < 0.5 else "L"
    seq = "".join(first if k % 2 == 0 else E.other(first) for k in range(m))
    ot = rng.uniform(60.0, 260.0, size=m)
    if mode == "tot":
        ot *= key / ot.sum()
    d = ot / E.nvec(seq)
    return seq, d


def job(kind: str, mode: str, key: float, rkw: dict, design, move: str, seed: int):
    rng = np.random.default_rng(seed)
    rules = rules_of(rkw)
    try:
        if kind == "fresh":
            seq, d = fresh(mode, key, rules, rng)
            out = E.settle(PROB, rules, seq, E.scale_tot(seq, d, rules.tot, rules.tot_le))
            if mode == "tot":
                out = E.cap(PROB, rules, *out, rng)
        elif kind == "transfer":
            seq, d = design
            if mode == "tot":
                seq, d, r = E.settle(PROB, rules, seq, E.scale_tot(seq, d, rules.tot))
                out = E.cap(PROB, rules, seq, d, r, rng)
            else:
                out = to_n(seq, d, int(key), rules, rng)
        else:
            out = E.mutate(PROB, rules, [design], move, rng)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, IndexError):
        out = None
    if out is None:
        return key, None
    seq, d, r = out
    if not np.isfinite(r) or np.min(d) < rules.floor * (1 - 1e-9):
        return key, None
    if rules.tot is not None and E.total_ot(seq, d) > rules.tot * (1 + 1e-6):
        return key, None
    return key, (seq, d, r)


def grow_job(key: float, rkw: dict, design, top: int, seed: int):
    """Trubetskov's evolution step to the target TOT `key`: one layer thickened (or an outer layer added) by the
    missing optical thickness, the `top` best by unrefined MF refined at the target, best returned."""
    rng = np.random.default_rng(seed)
    rules = rules_of(rkw)
    seq, d = design
    try:
        missing = float(key) - E.total_ot(seq, d)
        if missing <= 0.0:
            return key, None
        n = E.nvec(seq)
        cands = []
        for i in range(len(seq)):
            x = d.copy()
            x[i] += missing / n[i]
            cands.append((PROB.rmse(seq, x), seq, x))
        for side in ("top", "bottom"):
            m = E.other(seq[-1] if side == "top" else seq[0])
            s2 = seq + m if side == "top" else m + seq
            x = np.concatenate([d, [missing / E.N_IDX[m]]]) if side == "top" else np.concatenate([[missing / E.N_IDX[m]], d])
            cands.append((PROB.rmse(s2, x), s2, x))
        cands.sort(key=lambda t: t[0])
        best = None
        for _r, s2, x in cands[:top]:
            s3, x3, r3 = E.settle(PROB, rules, s2, x)
            s3, x3, r3 = E.cap(PROB, rules, s3, x3, r3, rng)
            if best is None or r3 < best[2]:
                best = (s3, x3, r3)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, IndexError):
        return key, None
    if best is None or not np.isfinite(best[2]) or np.min(best[1]) < rules.floor * (1 - 1e-9):
        return key, None
    if E.total_ot(best[0], best[1]) > float(key) * (1 + 1e-6):
        return key, None
    return key, best


def oracle_job(seq: str, d: np.ndarray):
    return PROB.oracle_rmse(seq, d)


def read_designs(files):
    out = []
    for f in files:
        if not Path(f).exists():
            print(f"seed file missing, skipped: {f}", flush=True)
            continue
        with open(f, encoding="utf-8-sig", newline="") as h:
            for r in csv.DictReader(h):
                try:
                    seq = r["seq"]
                    d = np.array([float(v) for v in r["d_nm"].split()])
                except (KeyError, ValueError):
                    continue
                if seq and len(seq) == len(d) and set(seq) <= {"H", "L"}:
                    out.append((seq, d))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="threeline")
    ap.add_argument("--points", type=int, default=1601)
    ap.add_argument("--mode", choices=["tot", "n"], required=True)
    ap.add_argument("--grid", required=True, help="start:stop:step (inclusive)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--nmax", type=int, default=200)
    ap.add_argument("--tot", type=float, default=None)
    ap.add_argument("--tot-le", action="store_true")
    ap.add_argument("--floor", type=float, default=0.1)  # owner rule 2026-11-06: search floor 0.1 nm, physical floor only in the final cleaning (audit 2026-11-07)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--moves-per-key", type=int, default=3)
    ap.add_argument("--grow-from", default="1,2,3,5,8", help="mode tot: lower grid offsets feeding the growth step")
    ap.add_argument("--grow-top", type=int, default=4)
    ap.add_argument("--moves", default="jitter:3,needle:3,remove:2,halfwave:1,swap:1,block:2,reverse:1")
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seeds-per-key", type=int, default=3)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--rng", type=int, default=2026)
    a = ap.parse_args()

    lo, hi, st = (float(v) for v in a.grid.split(":"))
    keys = [round(lo + k * st, 6) for k in range(round((hi - lo) / st) + 1)]
    if a.mode == "n":
        keys = [int(k) for k in keys]
    prob = E.make_problem(a.problem, points=a.points)
    rng = np.random.default_rng(a.rng)
    moves = [(m.split(":")[0], float(m.split(":")[1])) for m in a.moves.split(",")]
    mnames = [m for m, _w in moves]
    mw = np.array([w for _m, w in moves])
    mw /= mw.sum()
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    def rkw(key) -> dict:
        if a.mode == "tot":
            return dict(nmax=a.nmax, tot=float(key), floor=a.floor, iters=a.iters)
        return dict(nmax=int(key), tot=a.tot, floor=a.floor, iters=a.iters, tot_le=a.tot_le)

    def key_of(seq: str, d: np.ndarray):
        if a.mode == "n":
            k = len(seq)
            return k if lo <= k <= hi else None
        t = E.total_ot(seq, d)
        k = round(lo + round((t - lo) / st) * st, 6)
        return k if lo <= k <= hi and abs(t - k) <= 1e-6 * k + 1e-6 else None

    best: dict = {}
    tried: set = set()
    say(f"start {vars(a)}; {len(keys)} grid points")

    def write_curve(oracle: dict | None = None) -> None:
        with (HERE / f"{a.tag}_curve.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.writer(h)
            w.writerow(["key", "mf", "mf_oracle", "layers", "tot_nm", "thinnest_nm", "seq", "d_nm"])
            for k in keys:
                if k in best:
                    r, s, d = best[k]
                    o = "" if oracle is None or k not in oracle else f"{prob.scale * oracle[k]:.12g}"
                    w.writerow([k, f"{prob.scale * r:.12g}", o, len(s), f"{E.total_ot(s, d):.6f}",
                                f"{float(np.min(d)):.6f}", s, " ".join(f"{v:.9f}" for v in d)])

    def file(res) -> bool:
        if res is None:
            return False
        seq, d, r = res
        k = key_of(seq, d)
        if k is None:
            return False
        if k not in best or r < best[k][0] * (1 - 1e-10):
            best[k] = (r, seq, d)
            return True
        return False

    deadline = time.time() + 60.0 * a.minutes
    with ProcessPoolExecutor(a.workers, initializer=init_worker, initargs=(a.problem, a.points)) as ex:
        # seeds: for each key, the best few stored designs near it (MF evaluated here at their own TOT)
        designs = read_designs(a.seeds)
        say(f"{len(designs)} seed designs read")
        scored = []
        for seq, d in designs:
            t = E.total_ot(seq, d)
            if a.tot is not None and a.tot_le and t > a.tot * 1.02:
                continue
            scored.append((prob.rmse(seq, d), t, seq, d))
        futs = []
        for k in keys:
            if a.mode == "tot":
                near = [x for x in scored if abs(x[1] - k) <= max(2 * st, 0.01 * k) and len(x[2]) <= a.nmax + 20]
            else:
                near = [x for x in scored if abs(len(x[2]) - k) <= 1]
            near.sort(key=lambda x: x[0])
            for _r, _t, seq, d in near[:a.seeds_per_key]:
                futs.append(ex.submit(job, "transfer", a.mode, k, rkw(k), (seq, d), "", int(rng.integers(1 << 31))))
        for f in futs:
            file(f.result()[1])
        say(f"seeded {len(best)} of {len(keys)} points")
        rnd = 0
        while time.time() < deadline:
            rnd += 1
            tasks = []
            for k in keys:
                for off in (1, -1, 2, -2, 3, -3, 5, -5):
                    if a.mode == "n" and abs(off) > 2:
                        continue
                    src = keys[keys.index(k) + off] if 0 <= keys.index(k) + off < len(keys) else None
                    if src is None or src not in best:
                        continue
                    sig = (k, src, best[src][0])
                    if sig in tried:
                        continue
                    tried.add(sig)
                    tasks.append(("transfer", k, (best[src][1], best[src][2]), ""))
                if k in best:
                    tasks.extend(("move", k, (best[k][1], best[k][2]), mnames[int(rng.choice(len(mnames), p=mw))])
                                 for _ in range(a.moves_per_key))
                elif rnd <= 3:
                    tasks.append(("fresh", k, None, ""))
            grows = []
            if a.mode == "tot":
                offs = [int(v) for v in a.grow_from.split(",") if v]
                for i, k in enumerate(keys):
                    for off in offs:
                        if i - off < 0 or keys[i - off] not in best:
                            continue
                        src = keys[i - off]
                        sig = ("grow", k, src, best[src][0])
                        if sig in tried:
                            continue
                        tried.add(sig)
                        grows.append((k, (best[src][1], best[src][2])))
            n_imp = 0
            pending = {ex.submit(job, kind, a.mode, k, rkw(k), des, mv, int(rng.integers(1 << 31)))
                       for kind, k, des, mv in tasks}
            pending |= {ex.submit(grow_job, k, rkw(k), des, a.grow_top, int(rng.integers(1 << 31)))
                        for k, des in grows}
            while pending and time.time() < deadline:
                done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
                for f in done:
                    n_imp += file(f.result()[1])
            for f in pending:
                f.cancel()
            write_curve()
            vals = [prob.scale * best[k][0] for k in keys if k in best]
            say(f"round {rnd}: {len(tasks)} tasks + {len(grows)} growths, {n_imp} improvements, {len(best)}/{len(keys)} points, "
                f"median MF {np.median(vals):.6g}" if vals else f"round {rnd}: empty")
        say("oracle judging")
        of = {k: ex.submit(oracle_job, best[k][1], best[k][2]) for k in keys if k in best}
        oracle = {k: f.result() for k, f in of.items()}
    write_curve(oracle)
    worst = max((abs(oracle[k] - best[k][0]) / best[k][0] for k in oracle), default=0.0)
    say(f"end: {len(best)} points written, largest relative kernel/oracle difference {worst:.2e}")


if __name__ == "__main__":
    main()
