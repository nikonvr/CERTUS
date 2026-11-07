"""50/50 beamsplitter and three-line filter, each optimized on its nominal wavelength grid and on a resolved one
(2026-11-01, owner: the results optimized on each grid and judged on both, the MF curves for both grids).

Grids (same bands and targets, only the sampling changes):
  bs5050:    nominal 80 points from 400 to 1200 nm (the authors' Eq. 3), resolved 1601, check 16 001;
  threeline: nominal 1 nm in the bands (277 points, search.py), resolved 0.001 nm (270 007), check 0.0002 nm.
The three-line step: our best design (109 layers) gives 0.0145 % on 1 nm, 0.058 % on 0.1 nm, 0.269 % on 0.05 nm, 0.350 %
on 0.01 nm, 0.3772 % on 0.005 nm, 0.3777 % on 0.002 nm; Trubetskov's (101 layers) 0.0128 % -> 0.348 %: resonances of
0.011-0.014 nm FWHM between the 1 nm points (ours 405.47 nm 55 %, 425.25 nm 33 %, 414.39 nm 16 %; his 402.53 nm 61 %).
Polished on 0.005 nm it gives 0.116 % there but 0.171 % on 0.001 nm (the resonances narrowed to 0.003-0.004 nm);
polished on 0.001 nm, 0.157 % on 0.001 and on 0.0002 nm (threeline_refine_probe.out): 0.001 nm resolves it.
The study's designs (article_figures.designs) were optimized on 1601 points (50/50) and on the 277 points (three-line):
`repolish` judges them all, polishes on the other grid (same layers, trf, floor 0.1 nm as the "free" searches) every
50/50 design and, for the three-line filter, the KEEP best of each N and of each 100 nm TOT bin on either grid, and
judges them again, to grid_{kind}_repolish.csv (seq and d_nm: the repolished design, a start file for search.py with
SEARCH_POINTS or SEARCH_STEP). `judge OUT FILES` judges every design of the csv files on the three grids.
MF: RMSE for the 50/50, 100 x RMSE for the three-line filter, as in article_figures.
usage: SEARCH_TARGET=bs5050 python grid_study.py repolish
       SEARCH_TARGET=threeline python grid_study.py judgeall | resolve
       SEARCH_TARGET=threeline python grid_study.py judge OUT.csv FILE.csv ...
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import article_figures as af
import bs5050_grid as bg
import numpy as np
import search as s
from scipy.optimize import least_squares

from certus.physics.design_fast_normal import cost_lossless_front_fast

WORKERS = int(os.environ.get("GRID_WORKERS", "15"))
FLOOR, CHUNK, KEEP = 0.1, 20000, 2
SCALE = 100.0 if s.TARGET in ("threeline", "semicircle", "mshape", "highpass") else 1.0


def band_grid(step: float):
    """The three-line bands of search.py sampled every ``step`` nm: (wavelengths, target)."""
    w = [np.linspace(a, b, round((b - a) / step) + 1) for a, b, _t in s._bands]
    return np.concatenate(w), np.concatenate([s.band_values(x, t) for x, (_a, _b, t) in zip(w, s._bands, strict=True)])


def kernel_grid(wls, tgt):
    g = bg.kernel_grid(len(wls))
    g.update(k0=2.0 * np.pi / wls, tgt=np.asarray(tgt, dtype=float))
    return g


if s.TARGET == "bs5050":
    GRIDS = {"nominal": bg.kernel_grid(80), "resolved": bg.kernel_grid(1601), "check": bg.kernel_grid(16001)}
    POLISH_ON, NFEV = "nominal", 2000  # the study's designs were optimized on the resolved grid
else:
    GRIDS = {name: kernel_grid(*band_grid(h)) for name, h in (("nominal", 1.0), ("resolved", 0.001), ("check", 0.0002))}
    POLISH_ON, NFEV = "resolved", 300  # the study's designs were optimized on the nominal grid


def mf(seq, d, g) -> float:
    """The problem's MF on grid g, without the Jacobian, by chunks of at most CHUNK wavelengths."""
    n = np.array([s.N_IDX[m] for m in seq])
    d = np.ascontiguousarray(d, dtype=np.float64)
    sq = 0.0
    for idx in np.array_split(np.arange(len(g["k0"])), -(-len(g["k0"]) // CHUNK)):
        n_real = np.ascontiguousarray(np.tile(n, (len(idx), 1)))
        sq += len(idx) * cost_lossless_front_fast(d, n_real, 1.0 / n_real, g["nsub"][idx], g["k0"][idx], g["tgt"][idx],
                                                  g["ob"][idx])
    return SCALE * float(np.sqrt(sq / len(g["k0"])))


def polish(seq, d, g):
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = bg.res_jac(seq, x, g)[:2]
        return memo[key]

    sol = least_squares(lambda x: both(x)[0], np.maximum(d, FLOOR), jac=lambda x: both(x)[1], bounds=(FLOOR, np.inf),
                        method="trf", x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=NFEV)
    return np.maximum(sol.x, FLOOR)


def layers(d) -> int:
    """N as article_figures counts it: a 50/50 layer under 1 nm is not a layer."""
    return sum(1 for x in d if x > s.DEAD) if s.TARGET == "bs5050" else len(d)


def judge_one(task, names=("nominal", "resolved", "check")):
    seq, d = task
    return [mf(seq, d, GRIDS[g]) for g in names]


def judge_two(task):
    return judge_one(task, ("nominal", "resolved"))


def repolish_one(task):
    seq, d = task
    x = polish(seq, d, GRIDS[POLISH_ON])
    return x, judge_one((seq, x))


def chosen(src, before) -> list[int]:
    """Every design for the 50/50; for the three-line filter the KEEP best of each N and of each 100 nm TOT bin, by
    the MF on either grid."""
    if s.TARGET == "bs5050":
        return list(range(len(src)))
    keep = set()
    for key in (lambda k: layers(src[k][2]), lambda k: int(s.total_ot(src[k][1], src[k][2]) // 100)):
        groups: dict = {}
        for k in range(len(src)):
            groups.setdefault(key(k), []).append(k)
        for ks in groups.values():
            for j in range(2):
                keep.update(sorted(ks, key=lambda k, j=j: before[k][j])[:KEEP])
    return sorted(keep)


def write(path, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def repolish() -> None:
    src = af.designs()
    t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as pool:
        before = list(pool.map(judge_two, [(seq, d) for _f, seq, d in src], chunksize=8))
        pick = chosen(src, before)
        print(f"{s.TARGET}: {len(src)} designs judged, {len(pick)} to polish on the {POLISH_ON} grid "
              f"({time.time() - t0:.0f} s)", flush=True)
        res = list(pool.map(repolish_one, [(src[k][1], src[k][2]) for k in pick], chunksize=1))
    rows = []
    for k, (x, after) in zip(pick, res, strict=True):
        f, seq, d = src[k]
        row = {"source": f, "layers_before": layers(d), "layers": layers(x),
               "tot_before": f"{s.total_ot(seq, d):.1f}", "tot": f"{s.total_ot(seq, x):.1f}",
               "mf_nominal_before": f"{before[k][0]:.6e}", "mf_resolved_before": f"{before[k][1]:.6e}"}
        row.update({f"mf_{g}": f"{v:.6e}" for g, v in zip(GRIDS, after, strict=True)})
        row.update(seq=seq, d_nm=" ".join(f"{v:.6f}" for v in x))
        rows.append(row)
    write(f"grid_{s.TARGET}_repolish.csv", rows)
    write(f"grid_{s.TARGET}_judged.csv", [{"source": f, "layers": layers(d), "tot": f"{s.total_ot(seq, d):.1f}",
                                           "mf_nominal": f"{b[0]:.6e}", "mf_resolved": f"{b[1]:.6e}"}
                                          for (f, seq, d), b in zip(src, before, strict=True)])
    print(f"{s.TARGET}: {len(rows)} designs polished on the {POLISH_ON} grid ({time.time() - t0:.0f} s)", flush=True)


def judge(out, files) -> None:
    src = [(f, seq, d) for f in files for seq, d in af.load_rows(f)]
    with ProcessPoolExecutor(WORKERS) as pool:
        res = list(pool.map(judge_one, [(seq, d) for _f, seq, d in src], chunksize=4))
    rows = []
    for (f, seq, d), vals in zip(src, res, strict=True):
        row = {"source": f, "layers": layers(d), "tot": f"{s.total_ot(seq, d):.1f}"}
        row.update({f"mf_{g}": f"{v:.6e}" for g, v in zip(GRIDS, vals, strict=True)})
        row.update(seq=seq, d_nm=" ".join(f"{v:.6f}" for v in d))
        rows.append(row)
    write(out, rows)
    print(f"{s.TARGET}: {len(rows)} designs judged -> {out}", flush=True)


def judge_all() -> None:
    """judge_two on every design of the study, to grid_{kind}_judged.csv (no polish)."""
    src = af.designs()
    with ProcessPoolExecutor(WORKERS) as pool:
        before = list(pool.map(judge_two, [(seq, d) for _f, seq, d in src], chunksize=8))
    write(f"grid_{s.TARGET}_judged.csv", [{"source": f, "layers": layers(d), "tot": f"{s.total_ot(seq, d):.1f}",
                                           "mf_nominal": f"{b[0]:.6e}", "mf_resolved": f"{b[1]:.6e}",
                                           "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)}
                                          for (f, seq, d), b in zip(src, before, strict=True)])
    print(f"{s.TARGET}: {len(src)} designs judged -> grid_{s.TARGET}_judged.csv", flush=True)


def candidates(nmin=50, nmax=120, totmax=15000.0) -> list[dict]:
    """The steps of the resolved envelopes of grid_{kind}_judged.csv (best resolved MF with N' <= N, and with
    OT' <= OT), within the paper's budget and from N = nmin on, best first."""
    rows = [r for r in csv.DictReader(open(f"grid_{s.TARGET}_judged.csv", encoding="utf-8"))
            if nmin <= int(r["layers"]) <= nmax and float(r["tot"]) <= totmax]
    pick: dict = {}
    for key in (lambda r: int(r["layers"]), lambda r: float(r["tot"])):
        best = np.inf
        for r in sorted(rows, key=lambda r, key=key: (key(r), float(r["mf_resolved"]))):
            if float(r["mf_resolved"]) < best:
                best = float(r["mf_resolved"])
                pick[(r["seq"], r["d_nm"])] = r
    return sorted(pick.values(), key=lambda r: float(r["mf_resolved"]))


def resolve(nmin=50, nmax=120, totmax=15000.0) -> None:
    """Polish on the resolved grid the candidates of `candidates`, best first; each result is appended to
    grid_{kind}_resolved.csv as it ends (MF on the three grids), so that a stopped run keeps what it did. (2026-11-01:
    stopped before its first design ended -- one polish on 270 007 points takes about 40 min; threeline_track.py
    replaces it.)"""
    todo = candidates(nmin, nmax, totmax)
    out = f"grid_{s.TARGET}_resolved.csv"
    t0 = time.time()
    print(f"{s.TARGET}: {len(todo)} designs to polish on the {POLISH_ON} grid -> {out}", flush=True)
    with ProcessPoolExecutor(WORKERS) as pool:
        futs = {pool.submit(repolish_one, (r["seq"], np.array([float(v) for v in r["d_nm"].split()]))): r for r in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            r, (x, after) = futs[fut], fut.result()
            row = {"source": r["source"], "layers": r["layers"], "tot_before": r["tot"],
                   "tot": f"{s.total_ot(r['seq'], x):.1f}", "mf_nominal_before": r["mf_nominal"],
                   "mf_resolved_before": r["mf_resolved"]}
            row.update({f"mf_{g}": f"{v:.6e}" for g, v in zip(GRIDS, after, strict=True)})
            row.update(seq=r["seq"], d_nm=" ".join(f"{v:.6f}" for v in x))
            new = not os.path.exists(out)
            with open(out, "a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row))
                if new:
                    w.writeheader()
                w.writerow(row)
            print(f"  {k}/{len(todo)} N {r['layers']}: resolved {float(r['mf_resolved']):.4f} -> {after[1]:.4f} "
                  f"(check {after[2]:.4f}, nominal {after[0]:.4f}) ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "repolish":
        repolish()
    elif sys.argv[1] == "judgeall":
        judge_all()
    elif sys.argv[1] == "resolve":
        resolve()
    else:
        judge(sys.argv[2], sys.argv[3:])
