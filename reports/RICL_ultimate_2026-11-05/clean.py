"""Final cleaning of floor-free designs (RICL 2026-11-06): the physical floor and the layer cap are applied ONCE, at
the very end, as in practice (author's experience; Trubetskov, AO 59, A75, 2020). During the search, layers may be
as thin as the optimizer likes; only layers that collapse to ~0 are removed.

final_clean: refine at the imposed TOT; then, while a layer is under the floor or N > nmax, try removing each
candidate (layers under the floor, the `width` thinnest in OT when N > nmax), refine each shortly, keep the best,
refine fully; at the end refine with the floor as a lower bound. TOT is kept exactly throughout.

usage: python clean.py --designs A.csv [B.csv ...] --tag T --minutes M [--tot 14171] [--tot-window 600]
       [--floor 5] [--nmax 101] [--top 200]
  --tot given: every design whose TOT is within the window is rescaled to --tot, then cleaned (record seeds);
  --tot absent: every design is cleaned at its own TOT (curve seeds).
outputs: {tag}_best.csv (oracle-checked best), {tag}_clean.csv (all cleaned designs, sorted), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import engine as E
import numpy as np

HERE = Path(__file__).resolve().parent
PROB = None


def init(problem: str) -> None:
    global PROB
    PROB = E.make_problem(problem)


def final_clean(prob, seq: str, d: np.ndarray, tot: float, floor: float, nmax: int, width: int = 12,
                short: int = 60, full: int = 300):
    x, r, _ = E.lm(prob, seq, d, tot, 0.0, None, full)
    seq, x = E.normalize(seq, x, 1e-3)
    for _ in range(400):
        thin = [int(i) for i in np.flatnonzero(x < floor * 0.999)]
        if len(seq) > nmax:
            ot = E.nvec(seq) * x
            cands = list(dict.fromkeys(thin + [int(i) for i in np.argsort(ot)[:width]]))
        elif thin:
            ot = E.nvec(seq) * x
            cands = sorted(thin, key=lambda i: ot[i])[:width]
        else:
            break
        best = None
        for i in cands:
            s2, d2 = E.remove_layer(seq, x, i)
            s2, d2 = E.normalize(s2, d2, 1e-3)
            x2, r2, _ = E.lm(prob, s2, d2, tot, 0.0, None, short)
            if best is None or r2 < best[2]:
                best = (s2, x2, r2)
        seq, x, r = best
        x, r, _ = E.lm(prob, seq, x, tot, 0.0, None, full)
        seq, x = E.normalize(seq, x, 1e-3)
    x, r, _ = E.lm(prob, seq, x, tot, floor, None, full)
    return seq, x, r


def task(seq: str, d: np.ndarray, tot: float, floor: float, nmax: int):
    return final_clean(PROB, seq, d, tot, floor, nmax)


def read_designs(paths):
    out = []
    for p in paths:
        path = HERE / p
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as h:
            for r in csv.DictReader(h):
                if not r.get("seq") or not r.get("d_nm"):
                    continue
                out.append((float(r["mf"]), r["seq"], np.array([float(v) for v in r["d_nm"].split()]), p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="threeline")
    ap.add_argument("--designs", nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--tot", type=float, default=None)
    ap.add_argument("--tot-window", type=float, default=600.0)
    ap.add_argument("--floor", type=float, default=5.0)
    ap.add_argument("--nmax", type=int, default=101)
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    deadline = time.time() + 60.0 * a.minutes
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    say(f"start {vars(a)}")
    SC = E.make_problem(a.problem).scale  # reported MF = scale x RMSE (100 three-line, 1 for the 50/50)
    designs = read_designs(a.designs)
    jobs = []
    for mf, s, d, src in designs:
        t = E.total_ot(s, d)
        if a.tot is not None:
            if abs(t - a.tot) > a.tot_window:
                continue
            d = d * (a.tot / t)
            t = a.tot
        jobs.append((mf, s, d, t, src))
    jobs.sort(key=lambda j: j[0])
    jobs = jobs[:a.top]
    say(f"{len(designs)} designs read, {len(jobs)} to clean")
    done = []
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(a.problem,)) as ex:
        futs = {ex.submit(task, s, d, t, a.floor, a.nmax): (mf, src) for mf, s, d, t, src in jobs}
        for f in as_completed(futs):
            mf0, src = futs[f]
            s, x, r = f.result()
            done.append((r, s, x, mf0, src))
            if len(done) % 10 == 0 or len(done) == len(jobs):
                b = min(done, key=lambda z: z[0])
                say(f"{len(done)}/{len(jobs)} cleaned; best {SC * b[0]:.5f} % N {len(b[1])} "
                    f"TOT {E.total_ot(b[1], b[2]):.1f} thinnest {b[2].min():.2f}")
            if time.time() > deadline:
                say("deadline: cancelling the rest")
                for g in futs:
                    g.cancel()
                break
    done.sort(key=lambda z: z[0])
    prob = E.make_problem(a.problem)
    with (HERE / f"{a.tag}_clean.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["mf", "layers", "tot_nm", "thinnest_nm", "mf_before_clean", "source", "seq", "d_nm"])
        for r, s, x, mf0, src in done:
            w.writerow([f"{SC * r:.12g}", len(s), f"{E.total_ot(s, x):.6f}", f"{x.min():.6f}", mf0, src, s,
                        " ".join(f"{v:.9f}" for v in x)])
    if done:
        r, s, x, _mf0, src = done[0]
        oracle = SC * prob.oracle_rmse(s, x)
        with (HERE / f"{a.tag}_best.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.writer(h)
            w.writerow(["mf", "mf_oracle", "layers", "tot_nm", "thinnest_nm", "roots", "seq", "d_nm"])
            w.writerow([f"{SC * r:.12g}", f"{oracle:.12g}", len(s), f"{E.total_ot(s, x):.6f}", f"{x.min():.6f}",
                        src, s, " ".join(f"{v:.9f}" for v in x)])
        say(f"end best {SC * r:.6f} % (oracle {oracle:.6f}) N {len(s)} TOT {E.total_ot(s, x):.1f} "
            f"thinnest {x.min():.3f}")
    else:
        say("end: nothing cleaned")


if __name__ == "__main__":
    main()
