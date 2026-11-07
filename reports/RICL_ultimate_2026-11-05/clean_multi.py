"""Final cleaning of floor-free cissoid designs (RICL 2026-11-06): the contest floor (3 nm) and layer cap (50) are
applied ONCE, at the very end (author's rule), at the design's own constrained thickness (--axis phys: total physical
thickness). Same algorithm as clean.py: while a layer is under the floor or N > nmax, try removing each candidate,
refine each shortly at the imposed thickness, keep the best, refine fully; finally refine with the floor as bound.

usage: python clean_multi.py --designs CIS_free_curve.csv [...] --tag T --minutes M [--axis phys] [--floor 3]
       [--nmax 50] [--top 400]
outputs: {tag}_clean.csv (one row per cleaned design, oracle MF, columns usable as seeds and by the plots), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# before engine_multi is imported (inherited by the workers); default axis here: physical thickness
os.environ["CIS_AXIS"] = sys.argv[sys.argv.index("--axis") + 1] if "--axis" in sys.argv else "phys"

if "--judge" in sys.argv:  # resolved grid (e.g. exact10: 3001 points against the exact cissoid), set before import
    os.environ["CISSOID_JUDGE"] = sys.argv[sys.argv.index("--judge") + 1]

import engine_multi as M  # noqa: E402
import numpy as np  # noqa: E402
from cissoid_ultimate import read_designs  # noqa: E402

HERE = Path(__file__).resolve().parent


def final_clean(seq: str, d: np.ndarray, tot: float, floor: float, nmax: int, width: int = 12, short: int = 40,
                full: int = 250):
    x, r, _ = M.lm(seq, d, tot, 0.0, full)
    seq, x = M.normalize(seq, x, 1e-3)
    for _ in range(300):
        thin = [int(i) for i in np.flatnonzero(x < floor * 0.999)]
        if len(seq) > nmax:
            cands = list(dict.fromkeys(thin + [int(i) for i in np.argsort(x)[:width]]))
        elif thin:
            cands = sorted(thin, key=lambda i: x[i])[:width]
        else:
            break
        best = None
        for i in cands:
            s2, d2 = M.remove_layer(seq, x, i)
            x2, r2, _ = M.lm(s2, d2, tot, 0.0, short)
            if best is None or r2 < best[2]:
                best = (s2, x2, r2)
        seq, x, r = best
        x, r, _ = M.lm(seq, x, tot, 0.0, full)
        seq, x = M.normalize(seq, x, 1e-3)
    x, r, _ = M.lm(seq, x, tot, floor, full)
    return seq, x, r


def task(seq, d, tot, floor, nmax):
    s, x, r = final_clean(seq, d, tot, floor, nmax)
    ok = M.admissible(M.Rules(nmax=nmax, floor=floor, tot=tot), s, x)
    return s, x, r, (M.oracle_mf(s, x) if ok else float("nan")), ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--judge", default="", help="CISSOID_JUDGE (e.g. exact10); empty = the contest's 301 points")
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--axis", choices=["diel_ot", "phys"], default="phys")
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--nmax", type=int, default=50)
    ap.add_argument("--top", type=int, default=400)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    deadline = time.time() + 60.0 * a.minutes
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    say(f"start {vars(a)}; axis {M.AXIS}")
    ds = read_designs([str(HERE / f) for f in a.designs])
    jobs = sorted(((M.mf(s, d), s, d, nm) for s, d, nm in ds), key=lambda t: t[0])[:a.top]
    say(f"{len(ds)} designs read, {len(jobs)} to clean")
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(task, s, d, M.diel_ot(s, d), a.floor, a.nmax): (mf0, nm) for mf0, s, d, nm in jobs}
        for f in as_completed(futs):
            mf0, nm = futs[f]
            s, x, _r, o, ok = f.result()
            if ok:
                rows.append((o, s, x, mf0, nm))
            if len(rows) % 20 == 0:
                say(f"{len(rows)} cleaned")
            if time.time() > deadline:
                say("deadline: cancelling the rest")
                for g in futs:
                    g.cancel()
                break
    rows.sort(key=lambda t: M.diel_ot(t[1], t[2]))
    with (HERE / f"{a.tag}_clean.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["key", "mf", "mf_oracle", "layers", "metals", "diel_ot_nm", "physical_nm", "thinnest_nm",
                    "mf_before_clean", "source", "mats", "d_nm"])
        for o, s, x, mf0, nm in rows:
            w.writerow([f"{M.diel_ot(s, x):.4f}", f"{o:.12g}", f"{o:.12g}", len(s), sum(M.is_metal(c) for c in s),
                        f"{M.diel_ot(s, x):.4f}", f"{float(x.sum()):.4f}", f"{float(x.min()):.6f}", f"{mf0:.9g}", nm,
                        " ".join(s), " ".join(f"{v:.9f}" for v in x)])
    say(f"end: {len(rows)} admissible designs written")


if __name__ == "__main__":
    main()
