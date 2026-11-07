"""Beam cleaning of cissoid designs to the contest floor (3 nm) and cap (50 layers), applied at the very end (RICL
2026-11-06, owner: "le 0.0948 doit pouvoir être amélioré"). The greedy cleaner of clean_multi.py removes one sub-floor
layer at a time, keeping only the best after a short refinement; this one keeps the B best partial designs at every
removal step, tries every sub-floor layer as a candidate, and refines each candidate longer. The floor is applied only
here; the search that produced the designs ran with a 0.1 nm minimum.

usage: python clean_beam.py --designs CIS_c50_curve.csv --tot-lo 5600 --tot-hi 9100 --tag T --minutes M [--beam 4]
       [--top 12] [--short 150] [--full 400]
outputs: {tag}_clean.csv (cleaned designs: key, mf, mf_oracle, layers, thinnest, physical, mats, d_nm), {tag}.log
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ["CIS_AXIS"] = "phys"
import engine_multi as M  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent


def beam_clean(seq, d, tot, floor, nmax, beam, short, full):
    x, _r, _ = M.lm(seq, d, tot, 0.0, full)
    seq, x = M.normalize(seq, x, 1e-3)
    states = [(M.mf(seq, x), seq, x)]
    for _ in range(400):
        nxt = []
        for _r0, s, xx in states:
            thin = [int(i) for i in np.flatnonzero(xx < floor * 0.999)]
            if len(s) > nmax:
                thin = list(dict.fromkeys(thin + [int(i) for i in np.argsort(xx)[:25]]))
            if not thin:
                nxt.append((_r0, s, xx))
                continue
            for i in thin:
                s2, d2 = M.remove_layer(s, xx, i)
                s2, d2 = M.normalize(s2, d2, 1e-3)
                x2, r2, _ = M.lm(s2, d2, tot, 0.0, short)
                nxt.append((r2, s2, x2))
        if all(not (np.flatnonzero(xx < floor * 0.999).size or len(s) > nmax) for _r0, s, xx in nxt):
            states = sorted(nxt, key=lambda t: t[0])[:beam]
            break
        nxt.sort(key=lambda t: t[0])
        seen, keep = set(), []
        for r2, s2, x2 in nxt:
            key = (s2, round(float(r2), 10))
            if key in seen:
                continue
            seen.add(key)
            keep.append((r2, s2, x2))
            if len(keep) >= beam:
                break
        states = keep
    best = None
    for _r0, s, xx in states:
        x3, r3, _ = M.lm(s, xx, tot, floor, full)
        if len(s) <= nmax and (best is None or r3 < best[2]):
            best = (s, x3, r3)
    return best


def task(seq, d, tot, floor, nmax, beam, short, full, key, src):
    out = beam_clean(seq, d, tot, floor, nmax, beam, short, full)
    if out is None:
        return None
    s, x, r = out
    return key, s, x, r, src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", nargs="+", required=True)
    ap.add_argument("--tot-lo", type=float, required=True)
    ap.add_argument("--tot-hi", type=float, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--nmax", type=int, default=50)
    ap.add_argument("--beam", type=int, default=4)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--short", type=int, default=150)
    ap.add_argument("--full", type=int, default=400)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    deadline = time.time() + 60 * a.minutes
    log = (HERE / f"{a.tag}.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)

    rows = []
    for p in a.designs:
        with (HERE / p).open(encoding="utf-8") as h:
            for r in csv.DictReader(h):
                t = float(r.get("physical_nm") or sum(float(v) for v in r["d_nm"].split()))
                if not (a.tot_lo <= t <= a.tot_hi) or not r.get("mats") or not r.get("d_nm"):
                    continue
                s = "".join(r["mats"].split())
                d = np.array([float(v) for v in r["d_nm"].split()])
                if len(s) != len(d):
                    continue
                rows.append((float(r.get("mf") or 1e9), t, s, d, p))
    rows.sort(key=lambda z: z[0])
    jobs = []
    keys = {}
    for _mf, t, s, d, p in rows:
        k = round(t)
        if keys.get(k, 0) >= 2:  # up to two starting designs per thickness
            continue
        keys[k] = keys.get(k, 0) + 1
        jobs.append((s, d, t, k, p))
        if len(jobs) >= a.top:
            break
    say(f"{len(rows)} designs read, {len(jobs)} starting designs; beam {a.beam}, floor {a.floor}, nmax {a.nmax}")
    out = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(task, s, d, t, a.floor, a.nmax, a.beam, a.short, a.full, k, p) for s, d, t, k, p in jobs]
        for f in as_completed(futs):
            res = f.result()
            if res is not None:
                key, s, x, r, src = res
                o = M.oracle_mf(s, x)
                out.append((o, key, s, x, r, src))
                say(f"done key {key}: contest MF {100 * r:.5f} oracle {100 * o:.5f} N {len(s)} thinnest {x.min():.3f}")
            if time.time() > deadline:
                say("deadline reached")
                break
    out.sort(key=lambda z: z[0])
    with (HERE / f"{a.tag}_clean.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["key", "mf", "mf_oracle", "layers", "thinnest_nm", "physical_nm", "mats", "d_nm"])
        for o, key, s, x, r, _src in out:
            w.writerow([key, f"{100 * r:.12g}", f"{100 * o:.12g}", len(s), f"{x.min():.6f}", f"{x.sum():.4f}",
                        " ".join(s), " ".join(f"{v:.9f}" for v in x)])
    say(f"end: {len(out)} cleaned; best oracle {100 * out[0][0]:.5f} at {out[0][1]} nm" if out else "end: none")


if __name__ == "__main__":
    main()
