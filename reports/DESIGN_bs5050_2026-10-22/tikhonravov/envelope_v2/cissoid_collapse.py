"""OIC 2016 B1 (cissoid): reduce a design to 50 layers by merging, not deleting (2026-11-01).

Why: the pseudo-rugates (cissoid_rugate.py) reach MF 0.0044 with 99 layers and 0.0076 with 74 (two dielectrics), but
deleting layers down to 50 gave 0.026-0.05; the 8-material record holds 0.012869 at 50. An intermediate index stands
for a fine F/H group in one layer (Herpin, in reverse). Each step tries every window of 2-4 consecutive dielectric
layers replaced by ONE layer of each of the six dielectrics, its thickness fitted to the window's characteristic
matrix on the 301 points, plus the deletion of each of the CANDIDATES thinnest layers; screened by a 30-iteration
polish, the 6 best polished fully, the best kept; until N <= 50. Then cycles (all dielectrics) and a feasible polish.
usage: python cissoid_collapse.py IN.csv STEP OUT.csv   (STEP: the "step" of the IN row, e.g. "stage 75"; "" = last)
"""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_herpin as hp
import cissoid_opt as co
import numpy as np
from scipy.optimize import minimize_scalar

DIEL = "FLBMTH"
CANDIDATES = 40


def single_for(ms, ts):
    """(material, thickness) of the one dielectric layer whose characteristic matrix best matches the window's."""
    target = hp.char([co.MATS[x].real for x in ms], ts)
    best = None
    ot = sum(co.MATS[x].real * t for x, t in zip(ms, ts, strict=True))
    for y in DIEL:
        n = co.MATS[y].real

        def err(t, n=n):
            return float(np.sum(np.abs(hp.char([n], [t]) - target) ** 2))

        r = minimize_scalar(err, bounds=(0.0, 2.0 * ot / n), method="bounded")
        if best is None or r.fun < best[2]:
            best = (y, float(r.x), r.fun)
    return best


def candidates(m, d):
    out = []
    for k in (2, 3, 4):
        for i in range(len(m) - k + 1):
            win = m[i:i + k]
            if any(x not in DIEL for x in win):
                continue
            y, t, _e = single_for(win, d[i:i + k])
            out.append((f"merge {i}-{i + k - 1} -> {y}{t:.1f}",
                        *co.normalize([*m[:i], y, *m[i + k:]], np.concatenate([d[:i], [t], d[i + k:]]), 0.0)))
    ot = [abs(co.MATS[x]) * t for x, t in zip(m, d, strict=True)]
    out.extend((f"delete {i}{m[i]}", *co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0))
               for i in np.argsort(ot)[:CANDIDATES])
    return out


def main() -> None:
    src, step, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    r0 = next(r for r in rows if r["step"] == step) if step else rows[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0, out = time.time(), []

    def keep_row(tag, m, d, f):
        o = co.oracle_mf(m, d)
        out.append({"step": tag, "layers": len(m), "mf_full": f, "mf_oracle": o, "mats": " ".join(m),
                    "d_nm": " ".join(f"{v:.4f}" for v in d)})
        with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"{tag}: N {len(m)}, MF {f:.5f}, oracle {o:.5f}, materials {''.join(sorted(set(m)))} "
              f"({time.time() - t0:.0f} s)", flush=True)

    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, f = co.polish_full((m, d, 0.0))
        keep_row("start", m, d, f)
        while len(m) > co.N_MAX:
            cands = candidates(m, d)
            quick = list(pool.map(co.polish_full, [(cm, cd, 0.0, 30) for _h, cm, cd in cands], chunksize=4))
            order = np.argsort([q[2] for q in quick])[:6]
            full = list(pool.map(co.polish_full, [(cands[k][1], cands[k][2], 0.0) for k in order]))
            j = int(np.argmin([q[2] for q in full]))
            m, d, f = full[j]
            print(f"  {cands[order[j]][0]}: N {len(m)}, MF {f:.5f} ({len(cands)} tried, {time.time() - t0:.0f} s)",
                  flush=True)
        m, d, f = fx.feasible(m, d)
        keep_row("collapsed to <= 50", m, d, f)
        for c in range(10):
            got = fx.cycle(m, d, pool)
            if got is None or got[2] >= f * (1 - 1e-4):
                break
            m, d, f = got
            print(f"  cycle {c + 1}: N {len(m)}, MF {f:.5f} ({time.time() - t0:.0f} s)", flush=True)
        m, d, f = co.polish_full((m, d, co.FLOOR))
        keep_row("final", m, d, f)
        print("record to beat 0.012869", flush=True)


if __name__ == "__main__":
    main()
