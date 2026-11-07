"""OIC 2016 B1 cissoid, RICL 2026-11-05: memetic record hunt (mode run) and dense curves (mode n / dot).

mode run : steady-state memetic search under the contest rules (N <= 50, d >= 3 nm), lineage kept as in run.py;
mode n   : best design for every exact N of the grid (dense curve MF(N));
mode dot : best design for every dielectric optical thickness of the grid (equality), N <= 50 (dense MF(OT_d));
           with --axis phys, every total physical thickness instead (the axis of the contest results).
Engine: engine_multi.py (CERTUS kernel through cissoid_opt.py, independent oracle for the records and the curves).

usage: python cissoid_ultimate.py --mode run --tag T --minutes M [--seeds files...] [--pop 60]
       python cissoid_ultimate.py --mode n --grid 1:50:1 --tag T --minutes M
       python cissoid_ultimate.py --mode dot --grid 1000:24000:250 --tag T --minutes M
Seeds: every cissoid_*.csv of envelope_v2 with columns mats and d_nm (plus the files given).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

if "--axis" in sys.argv:  # must be set before engine_multi is imported (inherited by the worker processes)
    os.environ["CIS_AXIS"] = sys.argv[sys.argv.index("--axis") + 1]

if "--judge" in sys.argv:  # resolved grid (e.g. exact10: 3001 points against the exact cissoid), set before import
    os.environ["CISSOID_JUDGE"] = sys.argv[sys.argv.index("--judge") + 1]

import engine_multi as M  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
MOVES = "jitter:3,needle:3,needle_diel:1,substitute:3,remove:2,swap:2,block:1,cross:2"


def read_designs(files):
    out = []
    for f in files:
        try:
            h = open(f, encoding="utf-8-sig", newline="")
        except OSError:
            continue
        with h:
            for k, r in enumerate(csv.DictReader(h)):
                raw = r.get("mats") or r.get("seq") or ""
                seq = "".join(raw.split())
                try:
                    d = np.array([float(v) for v in (r.get("d_nm") or "").split()])
                except ValueError:
                    continue
                if seq and len(seq) == len(d) and set(seq) <= set(M.MATS) and np.all(np.isfinite(d)) and "U" not in seq:
                    out.append((seq, d, f"{Path(f).stem}#{k}"))
    return out


def job(kind: str, rkw: dict, parents, move: str, seed: int, target):
    rng = np.random.default_rng(seed)
    rules = M.Rules(**rkw)
    try:
        if kind == "settle":
            seq, d = parents[0]
            if rules.tot is not None and M.otvec(seq).any():
                d = M.rescale(seq, d, rules.tot)
            out = M.cap(rules, *M.settle(rules, seq, d), rng)
        elif kind == "to_n":
            seq, d = parents[0]
            n = int(target)
            out = M.settle(rules, seq, d)
            for _ in range(10):
                if len(out[0]) >= n:
                    break
                nxt = M.needle_step(rules, out[0], out[1], rng)
                if nxt is None:
                    break
                out = nxt
            out = M.cap(rules, *out, rng)
        else:
            out = M.mutate(rules, parents, move, rng)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError, IndexError, ZeroDivisionError):
        out = None
    if out is None or not np.isfinite(out[2]) or not M.admissible(rules, out[0], out[1]):
        return None
    return out


def oracle_job(seq, d):
    return M.oracle_mf(seq, d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["run", "n", "dot"], required=True)
    ap.add_argument("--grid", default="1:50:1")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--judge", default="", help="CISSOID_JUDGE (e.g. exact10); empty = the contest's 301 points")
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--nmax", type=int, default=50)
    ap.add_argument("--floor", type=float, default=0.1)  # owner rule 2026-11-06: search floor 0.1 nm, 3 nm only in clean_multi.py (audit 2026-11-07)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--moves", default=MOVES)
    ap.add_argument("--moves-per-key", type=int, default=3)
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seeds-per-key", type=int, default=3)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--rng", type=int, default=2016)
    ap.add_argument("--only-seeds", action="store_true", help="start from --seeds alone (no archive)")
    ap.add_argument("--prefix", default="", help="first layers (from the substrate) that must stay in this sequence")
    ap.add_argument("--exclude", default="U", help="materials forbidden in every design (default U = gold only; owner 2026-11-06)")
    ap.add_argument("--window", default="", help="physical thickness window lo:hi (nm)")
    ap.add_argument("--axis", choices=["diel_ot", "phys"], default="diel_ot",
                    help="mode dot: dielectric optical thickness or total physical thickness")
    a = ap.parse_args()
    a.window = tuple(float(v) for v in a.window.split(":")) if a.window else None
    rng = np.random.default_rng(a.rng)
    mv = [(x.split(":")[0], float(x.split(":")[1])) for x in a.moves.split(",")]
    names, w = [x for x, _ in mv], np.array([y for _, y in mv])
    w /= w.sum()
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    files = list(a.seeds) if a.only_seeds else sorted(str(p) for p in M.ENV.glob("cissoid_*.csv")) + list(a.seeds)
    designs = read_designs(files)
    say(f"start {vars(a)}; {len(designs)} seed designs")
    deadline = time.time() + 60.0 * a.minutes

    def fmt(seq, d):
        return " ".join(seq), " ".join(f"{v:.9f}" for v in d)

    with ProcessPoolExecutor(a.workers) as ex:
        if a.mode == "run":
            pop: list = []  # (mf, seq, d, roots)
            best = [np.inf]
            best_path = HERE / f"{a.tag}_best.csv"

            def add(seq, d, r, roots) -> bool:
                for k, (r0, s0, d0, _f) in enumerate(pop):
                    if s0 == seq and (abs(r0 - r) <= 1e-7 * r0 or (len(d0) == len(d) and np.max(np.abs(d0 - d)) < 1.0)):
                        if r < r0:
                            pop[k] = (r, seq, d, roots)
                            pop.sort(key=lambda t: t[0])
                            return True
                        return False
                if len(pop) >= a.pop and r >= pop[-1][0]:
                    return False
                pop.append((r, seq, d, roots))
                pop.sort(key=lambda t: t[0])
                del pop[a.pop:]
                return True

            def consider(out, origin, roots) -> bool:
                if out is None:
                    return False
                seq, d, r = out
                if a.prefix and not seq.startswith(a.prefix):  # locked first layers (2026-11-06)
                    return False
                if a.exclude and any(c in a.exclude for c in seq):  # e.g. U (gold)
                    return False
                if a.window and not (a.window[0] <= float(d.sum()) <= a.window[1]):  # physical thickness window
                    return False
                ok = add(seq, d, r, roots)
                if r < best[0] * (1 - 1e-9):
                    best[0] = r
                    o = M.oracle_mf(seq, d)
                    m_s, d_s = fmt(seq, d)
                    row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "origin": origin, "roots": roots,
                           "layers": len(seq), "metals": sum(M.is_metal(c) for c in seq),
                           "diel_ot_nm": f"{M.diel_ot(seq, d):.4f}", "physical_nm": f"{float(d.sum()):.4f}",
                           "thinnest_nm": f"{float(d.min()):.6f}", "mf": f"{r:.12g}", "mf_oracle": f"{o:.12g}",
                           "mats": m_s, "d_nm": d_s}
                    new = not best_path.exists()
                    with best_path.open("a", newline="", encoding="utf-8") as h:
                        wr = csv.DictWriter(h, fieldnames=list(row))
                        if new:
                            wr.writeheader()
                        wr.writerow(row)
                    say(f"BEST {r:.9g} (oracle {o:.9g}) N {len(seq)} via {origin} from {roots}")
                return ok

            rkw = dict(nmax=a.nmax, floor=a.floor)
            designs.sort(key=lambda t: M.mf(t[0], t[1]) if len(t[0]) <= 60 else 1e9)
            futs = [(ex.submit(job, "settle", rkw, [(s, d)], "", int(rng.integers(1 << 31)), None), nm)
                    for s, d, nm in designs[: 3 * a.pop]]
            for f, nm in futs:
                consider(f.result(), "seed", nm.split("#")[0])
            say(f"population {len(pop)}; best {best[0]:.9g}")
            inflight: dict = {}
            stats = {x: [0, 0] for x in names}
            last = time.time()
            while time.time() < deadline and pop:
                while len(inflight) < 2 * a.workers:
                    m = names[int(rng.choice(len(names), p=w))]
                    par = [pop[min(int(len(pop) * rng.random() ** 2), len(pop) - 1)]]
                    if m == "cross":
                        par.append(pop[min(int(len(pop) * rng.random() ** 2), len(pop) - 1)])
                    roots = "+".join(sorted({x for p in par for x in p[3].split("+") if x}))
                    f = ex.submit(job, "move", rkw, [(p[1], p[2]) for p in par], m, int(rng.integers(1 << 31)), None)
                    inflight[f] = (m, roots)
                done, _ = wait(list(inflight), timeout=30, return_when=FIRST_COMPLETED)
                for f in done:
                    m, roots = inflight.pop(f)
                    stats[m][0] += 1
                    stats[m][1] += consider(f.result(), m, roots)
                if time.time() - last > 900:
                    say(f"best {best[0]:.9g} pop [{pop[0][0]:.6g}..{pop[-1][0]:.6g}] "
                        + " ".join(f"{k}:{v[0]}/{v[1]}" for k, v in stats.items()))
                    last = time.time()
                    with (HERE / f"{a.tag}_elites.csv").open("w", newline="", encoding="utf-8") as h:
                        wr = csv.writer(h)
                        wr.writerow(["rank", "mf", "layers", "roots", "mats", "d_nm"])
                        for k, (r, s, d, f2) in enumerate(pop):
                            wr.writerow([k, f"{r:.12g}", len(s), f2, *fmt(s, d)])
            for f in inflight:
                f.cancel()
            with (HERE / f"{a.tag}_elites.csv").open("w", newline="", encoding="utf-8") as h:
                wr = csv.writer(h)
                wr.writerow(["rank", "mf", "layers", "roots", "mats", "d_nm"])
                for k, (r, s, d, f2) in enumerate(pop):
                    wr.writerow([k, f"{r:.12g}", len(s), f2, *fmt(s, d)])
            say(f"end best {best[0]:.9g}")
            return

        lo, hi, st = (float(v) for v in a.grid.split(":"))
        keys = [round(lo + k * st, 6) for k in range(round((hi - lo) / st) + 1)]
        if a.mode == "n":
            keys = [int(k) for k in keys]

        def rkw_of(k) -> dict:
            return dict(nmax=int(k), floor=a.floor) if a.mode == "n" else dict(nmax=a.nmax, floor=a.floor,
                                                                              tot=float(k))

        def key_of(seq, d):
            if a.mode == "n":
                return len(seq) if lo <= len(seq) <= hi else None
            t = M.diel_ot(seq, d)
            k = round(lo + round((t - lo) / st) * st, 6)
            return k if lo <= k <= hi and abs(t - k) <= 1e-6 * k else None

        best: dict = {}

        def file(out) -> bool:
            if out is None:
                return False
            seq, d, r = out
            if a.exclude and any(c in a.exclude for c in seq):  # gold excluded (owner 2026-11-06)
                return False
            k = key_of(seq, d)
            if k is None:
                return False
            if k not in best or r < best[k][0] * (1 - 1e-10):
                best[k] = (r, seq, d)
                return True
            return False

        def write(oracle=None) -> None:
            with (HERE / f"{a.tag}_curve.csv").open("w", newline="", encoding="utf-8") as h:
                wr = csv.writer(h)
                wr.writerow(["key", "mf", "mf_oracle", "layers", "metals", "diel_ot_nm", "physical_nm", "thinnest_nm",
                             "mats", "d_nm"])
                for k in keys:
                    if k in best:
                        r, s, d = best[k]
                        o = "" if oracle is None or k not in oracle else f"{oracle[k]:.12g}"
                        wr.writerow([k, f"{r:.12g}", o, len(s), sum(M.is_metal(c) for c in s),
                                     f"{M.diel_ot(s, d):.4f}", f"{float(d.sum()):.4f}", f"{float(d.min()):.6f}",
                                     *fmt(s, d)])

        scored = [(M.mf(s, d), s, d) for s, d, _nm in designs if len(s) <= 60]
        futs = []
        for k in keys:
            if a.mode == "n":
                near = [x for x in scored if abs(len(x[1]) - k) <= 2]
            else:
                near = [x for x in scored if abs(M.diel_ot(x[1], x[2]) - k) <= max(2 * st, 0.02 * k)]
                if len(near) < a.seeds_per_key:  # sparse region: also the nearest designs, rescaled by settle
                    near += sorted(scored, key=lambda x: abs(M.diel_ot(x[1], x[2]) - k))[:2 * a.seeds_per_key]
            near.sort(key=lambda x: x[0])
            for _r, s, d in near[:a.seeds_per_key]:
                kind = "to_n" if a.mode == "n" else "settle"
                futs.append(ex.submit(job, kind, rkw_of(k), [(s, d)], "", int(rng.integers(1 << 31)), k))
        for f in futs:
            file(f.result())
        write()  # curve visible right after seeding (2026-11-06: resolved rounds take ~30 min)
        say(f"seeded {len(best)} of {len(keys)} points")
        tried: set = set()
        rnd = 0
        while time.time() < deadline:
            rnd += 1
            tasks = []
            for i, k in enumerate(keys):
                for off in (1, -1, 2, -2, 3, -3):
                    if not 0 <= i + off < len(keys) or keys[i + off] not in best:
                        continue
                    src = keys[i + off]
                    sig = (k, src, best[src][0])
                    if sig in tried:
                        continue
                    tried.add(sig)
                    kind = "to_n" if a.mode == "n" else "settle"
                    tasks.append((kind, k, [(best[src][1], best[src][2])], ""))
                if k in best:
                    for _ in range(a.moves_per_key):
                        m = names[int(rng.choice(len(names), p=w))]
                        par = [(best[k][1], best[k][2])]
                        if m == "cross":
                            o = keys[min(len(keys) - 1, max(0, i + int(rng.integers(-3, 4))))]
                            par.append((best[o][1], best[o][2]) if o in best else par[0])
                        tasks.append(("move", k, par, m))
            n_imp = 0
            pending = {ex.submit(job, kind, rkw_of(k), par, m, int(rng.integers(1 << 31)), k)
                       for kind, k, par, m in tasks}
            while pending and time.time() < deadline:
                done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
                for f in done:
                    n_imp += file(f.result())
            for f in pending:
                f.cancel()
            write()
            say(f"round {rnd}: {len(tasks)} tasks, {n_imp} improvements, {len(best)}/{len(keys)} points")
        of = {k: ex.submit(oracle_job, best[k][1], best[k][2]) for k in keys if k in best}
        oracle = {k: f.result() for k, f in of.items()}
    write(oracle)
    say(f"end: {len(best)} points")


if __name__ == "__main__":
    main()
