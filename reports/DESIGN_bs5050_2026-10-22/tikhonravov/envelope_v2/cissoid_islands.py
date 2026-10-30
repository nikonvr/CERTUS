"""OIC 2016 B1 (cissoid): the memetic search of `cissoid_memetic.py` on islands, with restarts (2026-10-30).

Run 1 of `cissoid_memetic.py` (pop 40, one population) reached 0.1009 at generation 350, then the whole population sat
in that one basin (best, median and worst 0.1009 from generation 440): the random designs added every 5 generations
never survive (> 0.3 once polished). Here the same operators (random design, crossover, mutation, feasible polish,
needle-removal cycles) act on ISLANDS separate populations:
- generation g works on island g mod ISLANDS (its children are polished in parallel);
- every MIGRATE generations of an island, its best is copied into the next island (ring), replacing the worst;
- an island is restarted from new random designs when its best has not dropped by 1e-4 relative for STALL of its
  generations, or when its spread (worst / best - 1) falls below 1e-3; the archive keeps every island's best before;
- every DEEP_EVERY generations of an island, its best gets needle-removal cycles (`cissoid_fixedN.cycle`).
The archive (best of each island epoch, best first, oracle MF of the global best) is written every 10 minutes and at
the end, so a stopped run loses nothing.

usage: python cissoid_islands.py MINUTES   (env CISSOID_ISLANDS 6, CISSOID_POP 16 per island, CISSOID_SEED 1,
CISSOID_STALL 60, CISSOID_MIGRATE 25, CISSOID_TAG, plus CISSOID_DIELECTRICS, CISSOID_METALS, CISSOID_MAX_METALS)
outputs: cissoid_islands{_TAG}.csv, cissoid_islands{_TAG}.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_memetic as mm
import cissoid_opt as co
import numpy as np

ISLANDS = int(os.environ.get("CISSOID_ISLANDS", "6"))
POP = int(os.environ.get("CISSOID_POP", "16"))
SEED = int(os.environ.get("CISSOID_SEED", "1"))
STALL = int(os.environ.get("CISSOID_STALL", "60"))
MIGRATE = int(os.environ.get("CISSOID_MIGRATE", "25"))
DEEP_EVERY = int(os.environ.get("CISSOID_DEEP_EVERY", "10"))
DEEP_CYCLES = int(os.environ.get("CISSOID_DEEP_CYCLES", "3"))  # most needle-removal cycles per deep round
TAG = os.environ.get("CISSOID_TAG", "")
OUT = "cissoid_islands" + (f"_{TAG}" if TAG else "")
is_metal = fx.is_metal


def metals_of(m):
    return "".join(v for v in m if is_metal(v)) or "-"


def main() -> None:
    minutes = float(sys.argv[1])
    t_end = time.time() + 60 * minutes
    rng = np.random.default_rng(SEED)
    logf = (co.s.HERE / f"{OUT}.log").open("a", encoding="utf-8")

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    def desc(ind):
        m, x, r = ind
        return f"N {len(m)} metals {metals_of(m)} MF {r:.5f} physical {x.sum():.0f} nm"

    log(f"start: {minutes} min, {ISLANDS} islands x pop {POP}, seed {SEED}, stall {STALL}, migrate {MIGRATE}, "
        f"dielectrics {mm.DIELECTRICS}, metals {mm.METALS} <= {mm.MAX_METALS}, workers {co.WORKERS}")
    pool = ProcessPoolExecutor(co.WORKERS)

    def new_island():
        pop = sorted(pool.map(mm.polish_feasible, [mm.random_design(rng) for _ in range(POP)]), key=lambda t: t[2])
        return {"pop": pop, "gen": 0, "best": pop[0][2], "since": 0, "deep_done": None, "epoch_start": time.time()}

    archive = []  # (mats, d, mf, island, epoch)
    epochs = [0] * ISLANDS
    islands = []
    for k in range(ISLANDS):
        islands.append(new_island())
        log(f"island {k} epoch 0: best {desc(islands[k]['pop'][0])}")
    # env CISSOID_SEEDS: csv specs as in `cissoid_fixedN.py` ("file.csv:k"), polished into island 0 (worst replaced)
    for spec in filter(None, os.environ.get("CISSOID_SEEDS", "").split(",")):
        seed = mm.polish_feasible(mm.tidy(*fx.start_design(spec), rng))
        pop0 = islands[0]["pop"]
        pop0[-1] = seed
        pop0.sort(key=lambda t: t[2])
        log(f"seed {spec} into island 0: {desc(seed)}")

    def archive_add(k):
        m, x, r = islands[k]["pop"][0]
        archive.append((m, x, r, k, epochs[k]))

    def write_csv():
        rows = sorted(archive + [(*isl["pop"][0], k, epochs[k]) for k, isl in enumerate(islands)], key=lambda t: t[2])
        out = [{"rank": j, "island": k, "epoch": e, "layers": len(m), "metals": metals_of(m), "mf_kernel": r,
                "mf_oracle": co.oracle_mf(m, x) if j == 0 else "", "thinnest_nm": float(x.min()),
                "physical_nm": float(x.sum()), "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in x)}
               for j, (m, x, r, k, e) in enumerate(rows)]
        with (co.s.HERE / f"{OUT}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        return out[0]

    best_seen = min(isl["pop"][0][2] for isl in islands)
    batch = 2 * co.WORKERS
    g, last_write = 0, time.time()
    while time.time() < t_end:
        k = g % ISLANDS
        g += 1
        isl = islands[k]
        pop = isl["pop"]
        isl["gen"] += 1
        kids = []
        for _ in range(batch):
            a = min(pop[int(rng.integers(len(pop)))], pop[int(rng.integers(len(pop)))], key=lambda t: t[2])
            if rng.random() < 0.5:
                b = min(pop[int(rng.integers(len(pop)))], pop[int(rng.integers(len(pop)))], key=lambda t: t[2])
                kids.append(mm.crossover(a, b, rng))
            else:
                kids.append(mm.mutate(a[0], a[1], rng))
        for kid in pool.map(mm.polish_feasible, kids):
            if len(kid[0]) > co.N_MAX or kid[1].min() < co.FLOOR - 1e-9:
                continue
            if sum(map(is_metal, kid[0])) > mm.MAX_METALS:
                continue
            if kid[2] < pop[-1][2] and all(abs(kid[2] - p[2]) > 1e-6 * p[2] for p in pop):
                pop[-1] = kid
                pop.sort(key=lambda t: t[2])
        if isl["gen"] % DEEP_EVERY == 0 and pop[0][2] != isl["deep_done"]:
            m, x, r = pop[0]
            t0, n_cyc = time.time(), 0
            for _ in range(DEEP_CYCLES):
                got = fx.cycle(m, x, pool)
                n_cyc += 1
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, x, r = got
            log(f"island {k} gen {isl['gen']}: deep {pop[0][2]:.5f} -> {r:.5f} ({n_cyc} cycles, "
                f"{time.time() - t0:.0f} s, metals {metals_of(m)})")
            isl["deep_done"] = r
            if r < pop[0][2]:
                pop[0] = (m, x, r)
                isl["deep_done"] = r
        if isl["gen"] % MIGRATE == 0:
            dest = islands[(k + 1) % ISLANDS]["pop"]
            if all(abs(pop[0][2] - p[2]) > 1e-6 * p[2] for p in dest) and pop[0][2] < dest[-1][2]:
                dest[-1] = pop[0]
                dest.sort(key=lambda t: t[2])
        if pop[0][2] < isl["best"] * (1 - 1e-4):
            isl["best"], isl["since"] = pop[0][2], 0
        else:
            isl["since"] += 1
        if pop[0][2] < best_seen:
            best_seen = pop[0][2]
            log(f"island {k} epoch {epochs[k]} gen {isl['gen']}: best {desc(pop[0])}")
        if isl["since"] >= STALL or pop[-1][2] / pop[0][2] - 1 < 1e-3:
            why = "stall" if isl["since"] >= STALL else "collapsed"
            log(f"island {k} epoch {epochs[k]} ends ({why}) after {isl['gen']} gens, "
                f"{(time.time() - isl['epoch_start']) / 60:.0f} min: best {desc(pop[0])}")
            archive_add(k)
            epochs[k] += 1
            islands[k] = new_island()
        if time.time() - last_write > 600:
            top = write_csv()
            last_write = time.time()
            log(f"checkpoint: best {top['mf_kernel']:.5f} oracle {top['mf_oracle']:.5f} metals {top['metals']}, "
                f"island bests {' '.join(f'{isl['pop'][0][2]:.4f}' for isl in islands)}")
    pool.shutdown()
    top = write_csv()
    log(f"end after {g} generations, epochs {epochs}: best {top['mf_kernel']:.5f} oracle {top['mf_oracle']:.5f} "
        f"N {top['layers']} metals {top['metals']}")


if __name__ == "__main__":
    main()
