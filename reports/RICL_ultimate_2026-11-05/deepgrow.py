"""Deep gradual evolution with a beam, from the bare substrate (RICL 2026-11-05 night, "win at all costs").

Faithful to Trubetskov, AO 59, A75 (2020), Sec. 3, and widened: no starting design, no published design anywhere.
Growth floor: --grow-floor (2026-11-06; physical floor applied once at the end by clean.py).
Evolution step: EVERY layer (and a new outer layer on either side) is thickened alone to the next local minimum of the
one-parameter MF; EVERY candidate is refined at its new TOT (exact equality, engine.lm), then deep needle steps (all
distinct P-function minima refined, best kept while it improves) and removal of layers under the floor. The beam keeps
the B best distinct children of all parents at every step (B = 1 is the published deep search). Every design reached
is written (seeds for the TOT dynamic programme).

usage: python deepgrow.py --tag T --minutes M --beam 8 --tot-max 15500 [--floor 5] [--nmax 140]
outputs: {tag}_designs.csv (every beam member of every step), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import engine as E
import numpy as np

HERE = Path(__file__).resolve().parent
PROB = None
SCAN, SCAN_MAX = 2.0, 400.0  # nm optical: scan step and largest increase of one layer


def init(problem: str) -> None:
    global PROB
    PROB = E.make_problem(problem)


def refine_at(seq: str, d: np.ndarray, tot: float, floor: float, nmax: int):
    rules = E.Rules(nmax=nmax, tot=tot, floor=floor, iters=300)
    s, x, r = E.settle(PROB, rules, seq, d)
    s, x, r = E.cap(PROB, rules, s, x, r, np.random.default_rng(0))
    return s, x, r


def grow_candidates(seq: str, d: np.ndarray):
    """Every layer thickened to the next local minimum of the one-parameter MF, and a new outer layer of the other
    material on either side grown the same way. Returns [(seq, d)]."""
    out = []
    n = E.nvec(seq)
    for i in range(-1, len(seq) + 1):
        if i == -1:
            s2, x0, k = E.other(seq[0]) + seq, np.concatenate([[0.0], d]), 0
        elif i == len(seq):
            s2, x0, k = seq + E.other(seq[-1]), np.concatenate([d, [0.0]]), len(seq)
        else:
            s2, x0, k = seq, d.copy(), i
        nk = E.N_IDX[s2[k]]
        prev2 = prev1 = None
        for step in np.arange(SCAN, SCAN_MAX + SCAN / 2, SCAN):
            x = x0.copy()
            x[k] += step / nk
            mf = PROB.rmse(s2, x)
            if prev2 is not None and prev1[0] < prev2[0] and prev1[0] <= mf:
                out.append((s2, prev1[1]))
                break
            prev2, prev1 = prev1, (mf, x)
        del n
    return out


def child_task(seq: str, d: np.ndarray, floor: float, nmax: int):
    tot = E.total_ot(seq, d)
    return refine_at(seq, d, tot, floor, nmax)


def needle_task(seq: str, d: np.ndarray, i: int, z: float, floor: float, nmax: int):
    tot = E.total_ot(seq, d)
    s2, d2 = E.insert_needle(seq, d, i, z, 0.5)
    return refine_at(s2, E.scale_tot(s2, d2, tot), tot, floor, nmax)


def deep_needles(ex, seq, d, r, floor, nmax, deadline):
    """Deep needle steps at constant TOT: all distinct P minima are refined, the best kept while it improves."""
    while time.time() < deadline:
        p = sorted(E.p_function(PROB_MASTER, seq, d))
        cands, used = [], set()
        for g, i, z in p:
            if g >= 0 or len(cands) >= 24:
                break
            if i not in used:
                used.add(i)
                cands.append((i, z))
        if not cands:
            return seq, d, r
        res = list(ex.map(needle_task, *zip(*[(seq, d, i, z, floor, nmax) for i, z in cands], strict=True)))
        best = min(res, key=lambda t: t[2])
        if best[2] >= r * (1 - 1e-4):
            return seq, d, r
        seq, d, r = best
    return seq, d, r


PROB_MASTER = None


def main() -> None:
    global PROB_MASTER
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="threeline")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--beam", type=int, default=8)
    ap.add_argument("--tot-max", type=float, default=15500.0)
    ap.add_argument("--floor", type=float, default=5.0)
    ap.add_argument("--resume", default=None, help="designs CSV of a previous run: start from its last beam")
    ap.add_argument("--grow-floor", type=float, default=None,
                    help="floor during growth (default: --floor); final cleaning to --floor is done by clean.py")
    ap.add_argument("--nmax", type=int, default=140)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    PROB_MASTER = E.make_problem(a.problem)
    if a.grow_floor is not None:
        a.floor = a.grow_floor  # growth floor; the physical floor is applied once at the end (clean.py)
    deadline = time.time() + 60.0 * a.minutes
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")
    out_path = HERE / f"{a.tag}_designs.csv"

    def say(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    def write(step, beam):
        new = not out_path.exists()
        with out_path.open("a", newline="", encoding="utf-8") as h:
            w = csv.writer(h)
            if new:
                w.writerow(["step", "rank", "tot_nm", "layers", "mf", "thinnest_nm", "seq", "d_nm"])
            for k, (s, x, r) in enumerate(beam):
                w.writerow([step, k, f"{E.total_ot(s, x):.6f}", len(s), f"{100 * r:.12g}", f"{x.min():.6f}", s,
                            " ".join(f"{v:.9f}" for v in x)])

    say(f"start {vars(a)}")
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(a.problem,)) as ex:
        beam = []
        step = 0
        if a.resume:  # continue a previous run from its last written beam (same rules)
            with (HERE / a.resume).open(encoding="utf-8") as h:
                rows = list(csv.DictReader(h))
            step = max(int(r["step"]) for r in rows)
            beam.extend((r["seq"], np.array([float(v) for v in r["d_nm"].split()]), float(r["mf"]) / 100.0)
                        for r in rows if int(r["step"]) == step)
            say(f"resumed {len(beam)} beam members from step {step} of {a.resume}")
        else:
            for m in "HL":
                d0 = np.array([100.0 / E.N_IDX[m]])
                beam.append(refine_at_master(m, d0, a.floor, a.nmax))
        beam.sort(key=lambda t: t[2])
        while time.time() < deadline:
            step += 1
            kids = []
            for seq, d, _r in beam:
                cands = grow_candidates_master(seq, d)
                kids += list(ex.map(child_task, *zip(*[(s, x, a.floor, a.nmax) for s, x in cands], strict=True))) \
                    if cands else []
            if not kids:
                say("no growth candidate")
                break
            kids.sort(key=lambda t: t[2])
            chosen = []
            for s, x, r in kids:
                if all(not (s == c[0] and abs(r - c[2]) <= 1e-6 * r) for c in chosen):
                    chosen.append((s, x, r))
                if len(chosen) >= a.beam:
                    break
            beam = [deep_needles(ex, s, x, r, a.floor, a.nmax, deadline) for s, x, r in chosen]
            beam.sort(key=lambda t: t[2])
            write(step, beam)
            s, x, r = beam[0]
            say(f"step {step}: best TOT {E.total_ot(s, x):.1f} N {len(s)} MF {100 * r:.5f} thinnest {x.min():.2f} "
                f"(beam TOT {min(E.total_ot(b[0], b[1]) for b in beam):.0f}-"
                f"{max(E.total_ot(b[0], b[1]) for b in beam):.0f})")
            if E.total_ot(beam[0][0], beam[0][1]) >= a.tot_max:
                break
    say("end")


def refine_at_master(seq, d, floor, nmax):
    rules = E.Rules(nmax=nmax, tot=E.total_ot(seq, d), floor=floor, iters=300)
    return E.settle(PROB_MASTER, rules, seq, d)


def grow_candidates_master(seq, d):
    global PROB
    PROB = PROB_MASTER
    return grow_candidates(seq, d)


if __name__ == "__main__":
    main()
