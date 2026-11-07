"""Resonance finishing from the complex wavelength plane (RICL 2026-11-06, owner's choice over a 0.1 nm grid).

The three-line designs are searched and cleaned on the nominal 277 points; the native DESIGN resonance treatment
(`certus.physics.design_resonances.refine_resonances`, method of the companion OE paper) then locates the
transmission poles at complex wavelength, follows each to its real maximum and charges the error there, so that
resonances of any width are seen while the grid stays the nominal one. A 0.1 nm grid would cost x10 and still miss
peaks about 0.01 nm wide (Trubetskov 2020 deep: 0.099 % at 0.1 nm, 0.298 % at 0.01 nm, 0.348 % at 0.001 nm).

No layer is added or removed: the treatment refines the thicknesses of a CLEANED design with the physical floor as
lower bound and the TOT as upper bound (max_ot_nm), so the floor rule (applied once, at the end) is respected.
Every result is judged on both grids: nominal (277 points) and resolved (0.001 nm, CERTUS cost kernel by chunks).

usage: python resfinish.py --designs A.csv [...] --tag T --minutes M [--floor 5] [--rounds 40] [--per-key 4]
       [--keys 100:14500:50 | --tot 14171 --tot-window 30] [--nmax 101]
  per key (TOT rounded to the grid, or the single --tot), the --per-key best nominal candidates are treated;
  the one with the lowest RESOLVED score is kept.
outputs: {tag}_curve.csv (key, nominal and resolved MF before/after, layers, TOT, design), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import engine as E  # noqa: E402
import numpy as np  # noqa: E402
from kick import BANDS, INDEX  # noqa: E402

from certus.physics.design_fast_normal import cost_lossless_front_fast  # noqa: E402
from certus.physics.design_resonances import ResonanceSettings, TransmissionProblem, refine_resonances  # noqa: E402

HERE = Path(__file__).resolve().parent
NOM = None
RES = None


def init() -> None:
    global NOM, RES
    NOM = E.threeline(1.0)
    RES = E.threeline(0.001)


def resolved(seq: str, d: np.ndarray, chunk: int = 20000) -> float:
    n = E.nvec(seq)
    total = 0.0
    for a in range(0, len(RES.wls), chunk):
        w = RES.wls[a:a + chunk]
        nr = np.ascontiguousarray(np.tile(n, (len(w), 1)))
        mse = cost_lossless_front_fast(np.ascontiguousarray(d), nr, np.ascontiguousarray(1.0 / nr),
                                       np.full(len(w), E.N_SUB), 2 * np.pi / w, RES.tgt[a:a + chunk], np.ones(len(w)))
        total += float(mse) * len(w)
    return 100.0 * math.sqrt(total / len(RES.wls))


def _treat(seq, d, floor, rounds, tot):
    prob = TransmissionProblem(np.array([INDEX[m] for m in seq]), E.N_SUB, BANDS)
    ref = refine_resonances(prob, np.maximum(d, floor), settings=ResonanceSettings(rounds=rounds, burst=30,
                                                                                  max_ot_nm=tot + 1e-6),
                            lower_bounds=np.full(len(seq), floor))
    return np.asarray(ref.thicknesses, dtype=float)


def task(key, seq, d, floor, rounds, src, attempts=4):
    """Treat the design; when the native tool fails (e.g. no isolated maximum near a tracked pole) or leaves the
    resolved score unchanged, retry from the design perturbed by a relative 1e-4 (seeded), keeping the best."""
    tot = E.total_ot(seq, d)
    nom0, res0 = 100 * NOM.rmse(seq, d), resolved(seq, d)
    t0 = time.time()
    rng = np.random.default_rng(abs(hash((seq, round(tot, 3)))) % (1 << 31))
    best_x, best_r, notes = d, res0, []
    for k in range(attempts):
        start = d if k == 0 else np.maximum(d * (1 + 1e-4 * rng.standard_normal(len(d))), floor)
        start = start * min(1.0, tot / E.total_ot(seq, start))
        try:
            x = _treat(seq, start, floor, rounds, tot)
        except Exception as exc:  # noqa: BLE001  (native tool: e.g. _NoErrorMaximum near a tracked pole)
            notes.append(f"try{k}: {type(exc).__name__}")
            continue
        r = resolved(seq, x)
        notes.append(f"try{k}: {r:.4f}")
        if r < best_r:
            best_x, best_r = x, r
        if best_r < 0.7 * res0:
            break
    status = ("ok " if best_r < res0 else "unchanged ") + "; ".join(notes)
    return key, seq, best_x, nom0, res0, 100 * NOM.rmse(seq, best_x), best_r, src, status, time.time() - t0


def read(paths):
    out = []
    for p in paths:
        path = HERE / p
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as h:
            for k, r in enumerate(csv.DictReader(h)):
                if r.get("seq") and r.get("d_nm"):
                    d = np.array([float(v) for v in r["d_nm"].split()])
                    out.append((float(r["mf"]), r["seq"], d, f"{Path(p).stem}#{k}"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--floor", type=float, default=5.0)
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--per-key", type=int, default=4)
    ap.add_argument("--keys", default="100:14500:50")
    ap.add_argument("--tot", type=float, default=None)
    ap.add_argument("--tot-window", type=float, default=30.0)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--by", choices=["tot", "n"], default="tot", help="group by TOT (keys grid) or by layer count")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    deadline = time.time() + 60 * a.minutes
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    say(f"start {vars(a)}")
    lo, hi, st = (float(v) for v in a.keys.split(":"))
    groups: dict = {}
    for mf, s, d, src in read(a.designs):
        if len(s) > a.nmax or d.min() < a.floor * (1 - 1e-9):
            continue  # only cleaned, admissible designs are finished
        t = E.total_ot(s, d)
        if a.by == "n":
            k = len(s)
        elif a.tot is not None:
            if abs(t - a.tot) > a.tot_window or t > a.tot + 1e-6:
                continue
            k = a.tot
        else:
            k = round(lo + round((t - lo) / st) * st, 6)
            if not lo <= k <= hi or abs(t - k) > 0.5:
                continue
        groups.setdefault(k, []).append((mf, s, d, src))
    jobs = []
    for k, c in sorted(groups.items()):
        c.sort(key=lambda z: z[0])
        seen = []
        for mf, s, d, src in c:
            if any(s == s2 and abs(mf - m2) <= 1e-6 * mf for m2, s2 in seen):
                continue
            seen.append((mf, s))
            jobs.append((k, s, d, src))
            if len(seen) >= a.per_key:
                break
    say(f"{len(groups)} keys, {len(jobs)} designs to finish")
    best: dict = {}
    n = 0
    with ProcessPoolExecutor(a.workers, initializer=init) as ex:
        futs = [ex.submit(task, k, s, d, a.floor, a.rounds, src) for k, s, d, src in jobs]
        for f in as_completed(futs):
            k, s, x, n0, r0, n1, r1, src, status, dt = f.result()
            n += 1
            if k not in best or r1 < best[k][6]:
                best[k] = (k, s, x, n0, r0, n1, r1, src, status)
            if n % 25 == 0 or n == len(jobs):
                say(f"{n}/{len(jobs)}; last key {k}: resolved {r0:.4f} -> {r1:.4f} %, nominal {n0:.4f} -> "
                    f"{n1:.4f} % ({dt:.0f} s, {status})")
            if time.time() > deadline:
                say("deadline: cancelling the rest")
                for g in futs:
                    g.cancel()
                break
    with (HERE / f"{a.tag}_curve.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["key", "mf", "mf_resolved", "mf_nominal_before", "mf_resolved_before", "layers", "tot_nm",
                    "thinnest_nm", "source", "status", "seq", "d_nm"])
        for k in sorted(best):
            k, s, x, n0, r0, n1, r1, src, status = best[k]
            w.writerow([k, f"{n1:.12g}", f"{r1:.12g}", f"{n0:.12g}", f"{r0:.12g}", len(s), f"{E.total_ot(s, x):.6f}",
                        f"{x.min():.6f}", src, status, s, " ".join(f"{v:.9f}" for v in x)])
    say(f"end: {len(best)} keys written")


if __name__ == "__main__":
    main()
