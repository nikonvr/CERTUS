"""Exhaustive final cleaning of 50/50 beamsplitter designs (owner 2026-11-08: "when several layers are under the floor,
test every possible variant").

For a design with k layers under the floor, all 2^k variants are built: each thin layer is either removed (its two
neighbours, of the same material, merge; at an end of the stack it is simply dropped) or kept and raised to the floor.
Variants with more than --nmax layers are discarded. Every variant is refined with SLSQP on the 1601-point RMSE
(residuals and Jacobian from the native kernel certus.physics.design_resonances._res_jac), bounds d >= floor and the
linear constraint TOT <= --tot; the best variant of each design is kept. Designs with more than --kmax thin layers are
skipped (2^k refinements).

usage: python exhaustive_clean_bs.py --designs A.csv [...] --tag T --minutes M [--floor 3] [--nmax 34] [--tot 3923.75]
       [--top 600] [--kmax 8]
outputs: {tag}_clean.csv (mf = RMSE on 1601 points; columns compatible with clean.py outputs), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repository root (certus package), as in engine.py

import numpy as np  # noqa: E402
from scipy.optimize import minimize  # noqa: E402

from certus.physics.design_resonances import TransmissionBand, TransmissionProblem, _res_jac  # noqa: E402

HERE = Path(__file__).resolve().parent
NIDX = {"H": 2.35, "L": 1.45}
LAM = np.linspace(400.0, 1200.0, 1601)
TGT = np.full(LAM.size, 0.5)


def merge(seq, d):
    s, x = [], []
    for m, t in zip(seq, d):
        if s and m == s[-1]:
            x[-1] += t
        else:
            s.append(m)
            x.append(t)
    return "".join(s), np.array(x)


def refine(seq, d0, floor, totmax, iters):
    idx = np.array([NIDX[c] for c in seq])
    prob = TransmissionProblem(idx, 1.52, (TransmissionBand(400.0, 1200.0, 0.5, 0.5),))
    var = np.arange(len(seq), dtype=np.int64)

    def fg(x):
        r, j = _res_jac(prob, x, LAM, TGT, var)
        return float(r @ r), 2.0 * (j.T @ r)

    x0 = np.maximum(np.asarray(d0, float), floor)
    if idx @ x0 > totmax:
        x0 = floor + (x0 - floor) * (totmax - floor * idx.sum()) / (idx @ (x0 - floor))
    sol = minimize(fg, x0, jac=True, method="SLSQP", bounds=[(floor, None)] * len(x0),
                   constraints=[{"type": "ineq", "fun": lambda x: totmax - idx @ x, "jac": lambda x: -idx}],
                   options={"maxiter": iters, "ftol": 1e-22})
    x = np.maximum(sol.x, floor)
    if idx @ x > totmax:
        x = x * totmax / (idx @ x)
    r = _res_jac(prob, x, LAM, TGT, var[:0])[0]
    return x, float(np.sqrt(np.mean(r ** 2)))


def clean_one(seq, d, floor, totmax, nmax):
    thin = [i for i in range(len(d)) if d[i] < floor]
    best = None
    tried = 0
    for r_ in range(len(thin) + 1):
        for rem in itertools.combinations(thin, r_):
            keep = [i for i in range(len(d)) if i not in rem]
            if not keep:
                continue
            s, dd = merge("".join(seq[i] for i in keep), d[keep])
            if len(dd) > nmax:
                continue
            x, v = refine(s, dd, floor, totmax, 300)
            tried += 1
            if best is None or v < best[0]:
                best = (v, s, x)
    if best is None:
        return None
    x, v = refine(best[1], best[2], floor, totmax, 1000)
    return v, best[1], x, len(thin), tried


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--nmax", type=int, default=34)
    ap.add_argument("--tot", type=float, default=3923.75)
    ap.add_argument("--top", type=int, default=600)
    ap.add_argument("--kmax", type=int, default=8)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    log = open(HERE / f"{a.tag}.log", "a", encoding="utf-8")

    def say(m):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    say(f"start {vars(a)}")
    deadline = time.time() + 60 * a.minutes
    cands, seen = [], set()
    for f in a.designs:
        p = HERE / f
        if not p.exists():
            say(f"missing, skipped: {f}")
            continue
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if not (r.get("seq") and r.get("d_nm")):
                continue
            seq = r["seq"].strip()
            d = np.array([float(v) for v in r["d_nm"].split()])
            idx = np.array([NIDX[c] for c in seq])
            k = int((d < a.floor).sum())
            key = (seq, round(float(d.sum()), 3))
            if key in seen or idx @ d > a.tot + 1e-6 or k > a.kmax or len(d) - k > a.nmax:
                continue
            seen.add(key)
            cands.append((float(r.get("mf_oracle") or r.get("mf") or 1e9), seq, d, f"{Path(f).stem}"))
    cands.sort(key=lambda c: c[0])
    cands = cands[:a.top]
    say(f"{len(cands)} designs to clean (every variant of their thin layers)")
    out, best = [], None
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(clean_one, c[1], c[2], a.floor, a.tot, a.nmax): c for c in cands}
        for n, f in enumerate(as_completed(futs), 1):
            c = futs[f]
            res = f.result()
            if res is not None:
                v, s, x, k, tried = res
                idx = np.array([NIDX[ch] for ch in s])
                out.append({"mf": f"{v:.12g}", "mf_oracle": f"{v:.12g}", "layers": len(x), "tot_nm": f"{idx @ x:.6f}",
                            "thinnest_nm": f"{x.min():.6f}", "mf_before_clean": f"{c[0]:.12g}",
                            "source": f"{c[3]} ({k} thin, {tried} variants)", "seq": s,
                            "d_nm": " ".join(f"{t:.9f}" for t in x)})
                if best is None or v < best:
                    best = v
            if n % 20 == 0 or n == len(futs):
                say(f"{n}/{len(futs)} cleaned; best {best:.6e}")
            if time.time() > deadline:
                say("time limit reached")
                for g in futs:
                    g.cancel()
                break
    out.sort(key=lambda r: float(r["mf"]))
    with open(HERE / f"{a.tag}_clean.csv", "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["mf", "mf_oracle", "layers", "tot_nm", "thinnest_nm", "mf_before_clean",
                                          "source", "seq", "d_nm"])
        w.writeheader()
        w.writerows(out)
    say(f"end: {len(out)} designs written; best {best}")


if __name__ == "__main__":
    main()
