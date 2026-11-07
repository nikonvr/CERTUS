"""OIC 2016 B1 (cissoid): local moves around the record (2026-10-31, the owner's attack plan, phase 1).

Single swaps are exhausted on the record (campaign swapA kept none after 12:54), so each move here goes further:
1. pair swaps: the 20 best single swaps (even losing ones), every pair of them applied together, polished;
2. swap then grow: each of the 8 best single swaps, then an overshoot (grow to 60 layers, remove back to 50) and cycles;
3. grow then reduce (owner: let the stack grow, then reduce): overshoot to 55, 60, 65, 70 from the record, cycles, swaps;
4. kicks: KICKS random perturbations (`cissoid_fixedN.kick`), each polished, cycled, swapped.
Every result is judged by the 301-point polish and the oracle; a better design is written to OUT at once.
usage: python cissoid_phase1.py IN.csv OUT.csv [KICKS]   (env as for cissoid_islands.py; CISSOID_GRID for the search)
"""

from __future__ import annotations

import csv
import itertools
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_islands as ci
import cissoid_memetic as mm
import cissoid_opt as co
import numpy as np


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    kicks = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    r0 = next(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))
    m0, d0 = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    rng = np.random.default_rng(31)
    t_start = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m0, d0, f0 = co.polish_full((m0, d0, co.FLOOR))
        best = {"mf": f0, "how": "start"}
        print(f"start: 301-point MF {f0:.5f}, oracle {co.oracle_mf(m0, d0):.5f}", flush=True)

        def judge(how, m, d):
            """301-point polish of a feasible design; writes it if it beats the best."""
            if len(m) > co.N_MAX:
                return None
            m, d, f = co.polish_full((m, d, co.FLOOR))
            if len(m) > co.N_MAX or d.min() < co.FLOOR - 1e-9:
                return None
            if f < best["mf"] * (1 - 1e-4):
                o = co.oracle_mf(m, d)
                best.update(mf=f, how=how)
                print(f"  NEW BEST {how}: 301-point MF {f:.5f}, oracle {o:.5f}, N {len(m)}, M {m.count('M')} "
                      f"({time.time() - t_start:.0f} s)", flush=True)
                row = {"how": how, "layers": len(m), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
                       "m_count": m.count("M"), "metals": "".join(x for x in m if x in "AUN"),
                       "physical_nm": float(d.sum()), "thinnest_nm": float(d.min()), "mats": " ".join(m),
                       "d_nm": " ".join(f"{v:.4f}" for v in d)}
                with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(row))
                    w.writeheader()
                    w.writerow(row)
            return f

        def refine(how, m, d):
            """cycles while they gain, then the swap round, on the search grid; then judged."""
            m, d, r = fx.feasible(m, d)
            for _ in range(5):
                got = fx.cycle(m, d, pool)
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, d, r = got
            m, d, r, _kept = ci.swap_round(m, d, r, pool)
            return judge(how, m, d)

        # 1. pair swaps
        singles = ci.swap_tasks(m0, d0)
        scored = sorted(zip(pool.map(mm.polish_feasible, singles), range(len(singles)), strict=True),
                        key=lambda t: t[0][2])
        print(f"1. {len(singles)} single swaps, best search MF {scored[0][0][2]:.5f}", flush=True)
        # the same order as `swap_tasks`
        names = [(i, b) for i, a in enumerate(m0) for b in (mm.METALS if ci.is_metal(a) else mm.DIELECTRICS) if b != a]
        top = [names[k] for _, k in scored[:20]]
        pairs = []
        for (i, a), (j, b) in itertools.combinations(top, 2):
            if i == j:
                continue
            m, d = list(m0), d0.copy()
            for k, y in ((i, a), (j, b)):
                if not ci.is_metal(m[k]):
                    d[k] *= co.MATS[m[k]] / co.MATS[y]
                m[k] = y
            pairs.append((f"pair {i}{a} {j}{b}", *co.normalize(m, np.maximum(d, co.FLOOR), 0.0)))
        res = list(pool.map(mm.polish_feasible, [(m, d) for _, m, d in pairs]))
        order = sorted(range(len(pairs)), key=lambda k: res[k][2])
        print(f"1. {len(pairs)} pairs, best search MF {res[order[0]][2]:.5f} ({pairs[order[0]][0]})", flush=True)
        for k in order[:5]:
            judge(pairs[k][0], res[k][0], res[k][1])
        # 2. swap then grow
        fx.OVERSHOOT[:] = [60]
        for (m, d, _r), k in scored[:8]:
            i, b = names[k]
            m2, d2, _r2 = fx.overshoot(m, d, pool)
            f = refine(f"swap {i}{b} + grow 60", m2, d2)
            print(f"2. swap {i}{b} + grow 60: {f}", flush=True)
        # 3. grow then reduce
        for top_n in (55, 60, 65, 70):
            fx.OVERSHOOT[:] = [top_n]
            m2, d2, _r2 = fx.overshoot(m0, d0, pool)
            f = refine(f"grow {top_n}", m2, d2)
            print(f"3. grow {top_n}: {f}", flush=True)
        # 4. kicks
        for n in range(kicks):
            m2, d2 = fx.kick(m0, d0, rng)
            f = refine(f"kick {n}", m2, d2)
            print(f"4. kick {n}: {f}", flush=True)
    print(f"end: best {best['mf']:.5f} by {best['how']} ({time.time() - t_start:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
