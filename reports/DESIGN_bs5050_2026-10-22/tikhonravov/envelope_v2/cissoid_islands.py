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
# env CISSOID_RANDOM: "free" (default, `cissoid_memetic.random_design`), "absorber" (2026-10-30: the 0.08521 record is
# opaque, T = 0: an 84 nm Ni base on the glass side, R = 1 - A, thin metals inside the stack) or "mixed" (half each)
RANDOM = os.environ.get("CISSOID_RANDOM", "free")


def metals_of(m):
    return "".join(v for v in m if is_metal(v)) or "-"


def random_absorber(rng):
    """Opaque metal base (60-100 nm) on the glass, dielectrics up to 6 quarter waves, 1-8 thin metals (3-25 nm)."""
    n = int(rng.integers(30, co.N_MAX + 1))
    mats, d = [str(rng.choice(mm.METALS))], [rng.uniform(60.0, co.HI_METAL)]
    top = float(rng.choice([1.5, 3.0, 6.0]))
    for _ in range(n - 1):
        m = str(rng.choice([x for x in mm.DIELECTRICS if x != mats[-1]]))
        mats.append(m)
        d.append(rng.uniform(400.0, 700.0) / (4 * co.MATS[m]) * rng.uniform(0.5, top))
    for _ in range(int(rng.integers(1, min(mm.MAX_METALS, 8) + 1))):
        i = int(rng.integers(1, len(mats) + 1))
        mats, d = [*mats[:i], str(rng.choice(mm.METALS)), *mats[i:]], [*d[:i], rng.uniform(3.0, 25.0), *d[i:]]
    return mm.tidy(mats, np.array(d), rng)


def random_start(rng, k):
    if RANDOM == "absorber" or (RANDOM == "mixed" and k % 2):
        return random_absorber(rng)
    return mm.random_design(rng)


# env CISSOID_RUIN (2026-10-30): share of a restarted island built by ruin and recreate, a block of 4-12 consecutive
# layers removed from one of the 5 best distinct designs found so far, the deep rounds regrowing it (campaign29: random
# restarts reached 0.09 at best while the record was 0.032); 0 = random starts only, as before
RUIN = float(os.environ.get("CISSOID_RUIN", "0"))


def ruin(design, rng):
    """``design`` without a block of 4-12 consecutive layers (at least 2 layers kept)."""
    m, x, _r = design
    size = int(rng.integers(4, max(4, min(12, len(m) - 2)) + 1))
    i = int(rng.integers(0, max(1, len(m) - size + 1)))
    return mm.tidy([*m[:i], *m[i + size:]], np.concatenate([x[:i], x[i + size:]]), rng)


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

    archive = []  # (mats, d, mf, island, epoch)
    epochs = [0] * ISLANDS
    islands = []

    def donors():
        """The 5 best distinct designs found so far (archive and islands)."""
        found = sorted([(m, x, r) for m, x, r, _k, _e in archive] + [isl["pop"][0] for isl in islands],
                       key=lambda t: t[2])
        out = []
        for t in found:
            if all(abs(t[2] - o[2]) > 1e-6 * o[2] for o in out):
                out.append(t)
        return out[:5]

    def new_island(restart=False):
        best = donors() if RUIN > 0 and restart else []
        n_ruin = round(RUIN * POP) if best else 0
        starts = [ruin(best[int(rng.integers(len(best)))], rng) for _ in range(n_ruin)]
        starts += [random_start(rng, j) for j in range(POP - n_ruin)]
        pop = sorted(pool.map(mm.polish_feasible, starts), key=lambda t: t[2])
        return {"pop": pop, "gen": 0, "best": pop[0][2], "since": 0, "deep_done": None, "epoch_start": time.time()}
    for k in range(ISLANDS):
        islands.append(new_island())
        log(f"island {k} epoch 0: best {desc(islands[k]['pop'][0])}")
    # env CISSOID_SEEDS: csv specs as in `cissoid_fixedN.py` ("file.csv:k"), polished into island 0 (worst replaced)
    # env CISSOID_SEED_SPREAD=1 (2026-10-30): the k-th seed goes to island k, so that each basin gets its own deep rounds
    spread = os.environ.get("CISSOID_SEED_SPREAD", "0") == "1"
    for j, spec in enumerate(filter(None, os.environ.get("CISSOID_SEEDS", "").split(","))):
        seed = mm.polish_feasible(mm.tidy(*fx.start_design(spec), rng))
        target = j % ISLANDS if spread else 0
        pop0 = islands[target]["pop"]
        pop0[-1] = seed
        pop0.sort(key=lambda t: t[2])
        log(f"seed {spec} into island {target}: {desc(seed)}")

    def archive_add(k):
        m, x, r = islands[k]["pop"][0]
        archive.append((m, x, r, k, epochs[k]))

    def write_csv():
        rows = sorted(archive + [(*isl["pop"][0], k, epochs[k]) for k, isl in enumerate(islands)], key=lambda t: t[2])
        full = [co.mf_full(m, x) for m, x, *_rest in rows]  # the contest's 301 points (= mf_kernel on the full grid)
        order = sorted(range(len(rows)), key=lambda j: full[j]) if co.GRID != "full" else range(len(rows))
        rows, full = [rows[j] for j in order], [full[j] for j in order]
        out = [{"rank": j, "island": k, "epoch": e, "layers": len(m), "metals": metals_of(m), "mf_kernel": r,
                "mf_full": full[j], "mf_oracle": co.oracle_mf(m, x) if j == 0 else "", "thinnest_nm": float(x.min()),
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
            if fx.OVERSHOOT:
                t0 = time.time()
                m2, x2, r2 = fx.overshoot(m, x, pool)
                log(f"island {k} gen {isl['gen']}: overshoot {r:.5f} -> {r2:.5f} (N {len(m2)}, "
                    f"{time.time() - t0:.0f} s, metals {metals_of(m2)})")
                if r2 < r and len(m2) <= co.N_MAX and x2.min() >= co.FLOOR - 1e-9:
                    m, x, r = m2, x2, r2
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
            islands[k] = new_island(restart=True)
        if time.time() - last_write > 600:
            top = write_csv()
            last_write = time.time()
            log(f"checkpoint: best {top['mf_kernel']:.5f} oracle {top['mf_oracle']:.5f} metals {top['metals']}, "
                f"island bests {' '.join(f'{isl['pop'][0][2]:.4f}' for isl in islands)}")
    if co.GRID != "full":
        # the search ran on a reduced grid: the 5 best distinct designs are polished on the contest's 301 points
        found = sorted(archive + [(*isl["pop"][0], k, epochs[k]) for k, isl in enumerate(islands)],
                       key=lambda t: co.mf_full(t[0], t[1]))
        best5 = []
        for m, x, *_rest in found:
            if all(abs(co.mf_full(m, x) - co.mf_full(b[0], b[1])) > 1e-6 for b in best5):
                best5.append((m, x))
            if len(best5) == 5:
                break
        for (m0, x0), (m, x, r) in zip(best5, pool.map(co.polish_full, [(m, x, co.FLOOR) for m, x in best5]),
                                       strict=True):
            archive.append((m, x, co.mf(m, x), -1, 0))
            log(f"full-grid polish: {co.mf_full(m0, x0):.5f} -> {r:.5f} (N {len(m)} metals {metals_of(m)})")
    pool.shutdown()
    top = write_csv()
    log(f"end after {g} generations, epochs {epochs}: best {top['mf_kernel']:.5f} oracle {top['mf_oracle']:.5f} "
        f"N {top['layers']} metals {top['metals']}")


if __name__ == "__main__":
    main()
