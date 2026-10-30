"""OIC 2016 B1 (cissoid): random starts and global memetic search under the contest rules, metals as genes (2026-10-30).

The owner's guidance (2026-10-30): random starts with global optimization, after CERTUS DESIGN, the hard part being the
metal insertion. A metal needle is strongly non-linear (0.001 nm of Ag already reverses the first-order gain), so here
metals are not inserted by needles: the number of metal layers (0 to MAX_METALS), their material, position and
thickness are genes, drawn at random and changed by mutations; every individual is polished locally (trf, d >= 3 nm).

- Individual: <= 50 layers, each >= 3 nm, dielectrics among DIELECTRICS (default F, M, H: the owner's choice), at most
  MAX_METALS metal layers (Ag, Au, Ni).
- Random design: N in [30, 50]; dielectrics drawn without two equal neighbours, thickness a quarter wave at a random
  wavelength in 400-700 nm times a factor in [0.5, 1.5] (half the designs) or [0.5, 3] (the contest winner is 8056 nm
  thick, quarter waves give about 3500 nm); 0 to MAX_METALS metal layers at random positions, 3-25 nm.
- Children: crossover (bottom of A and top of B cut at the same physical depth) or mutation (thickness noise; one
  dielectric changed; metal added, removed, changed, moved anywhere, or its thickness redrawn); polished in parallel;
  a child replaces the worst individual if better and not a duplicate (MF within 1e-6 relative).
- Every DEEP_EVERY generations, the best individual gets needle-removal cycles (`cissoid_fixedN.cycle`).
Draws come from one generator seeded by SEED (reproducible for a given worker count).

usage: python cissoid_memetic.py MINUTES [SEEDS]   (SEEDS: comma-separated csv specs as in `cissoid_fixedN.py`, put in
the first population; env CISSOID_POP (default 28), CISSOID_SEED (default 1), CISSOID_DIELECTRICS, CISSOID_MAX_METALS,
CISSOID_TAG (output suffix, default none))
outputs: cissoid_memetic{_TAG}.csv (final population, best first, oracle MF of the best), cissoid_memetic{_TAG}.log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_fixedN as fx
import cissoid_opt as co
import numpy as np

POP = int(os.environ.get("CISSOID_POP", "28"))
SEED = int(os.environ.get("CISSOID_SEED", "1"))
DEEP_EVERY = 10
TAG = os.environ.get("CISSOID_TAG", "")
OUT = "cissoid_memetic" + (f"_{TAG}" if TAG else "")
DIELECTRICS, METALS, MAX_METALS = fx.DIELECTRICS, fx.METALS, co.MAX_METALS
is_metal = fx.is_metal


def tidy(mats, d, rng):
    """Merge equal neighbours, keep <= MAX_METALS metals (thinnest dropped) and <= 50 layers (thinnest dropped)."""
    mats, d = co.normalize(list(mats), np.maximum(np.asarray(d, dtype=float), co.FLOOR), 0.0)
    while sum(map(is_metal, mats)) > MAX_METALS:
        i = min((k for k, m in enumerate(mats) if is_metal(m)), key=lambda k: d[k])
        mats, d = co.normalize(mats[:i] + mats[i + 1:], np.delete(d, i), 0.0)
    while len(mats) > co.N_MAX:
        i = int(np.argmin(d))
        mats, d = co.normalize(mats[:i] + mats[i + 1:], np.delete(d, i), 0.0)
    return mats, d


def random_design(rng):
    n = int(rng.integers(30, co.N_MAX + 1))
    mats, d = [], []
    top = 1.5 if rng.random() < 0.5 else 3.0
    for _ in range(n):
        m = str(rng.choice([x for x in DIELECTRICS if not mats or x != mats[-1]]))
        mats.append(m)
        d.append(rng.uniform(400.0, 700.0) / (4 * co.MATS[m]) * rng.uniform(0.5, top))
    d = np.array(d)
    for _ in range(int(rng.integers(0, MAX_METALS + 1))):
        mats, d = add_metal(mats, d, rng)
    return tidy(mats, d, rng)


def add_metal(mats, d, rng):
    i = int(rng.integers(0, len(mats) + 1))
    return [*mats[:i], str(rng.choice(METALS)), *mats[i:]], np.insert(d, i, rng.uniform(3.0, 25.0))


def mutate(mats, d, rng):
    mats, d = list(mats), d.copy()
    metal = [i for i, m in enumerate(mats) if is_metal(m)]
    diel = [i for i, m in enumerate(mats) if not is_metal(m)]
    kind = int(rng.integers(6))
    if kind == 0 or not diel:
        d = d * (1.0 + 0.05 * rng.standard_normal(len(d)))
    elif kind == 1:
        i = int(rng.choice(diel))
        mats[i] = str(rng.choice([m for m in DIELECTRICS if m != mats[i]] or DIELECTRICS))
    elif kind == 2 and len(metal) < MAX_METALS:
        mats, d = add_metal(mats, d, rng)
    elif kind == 3 and metal:
        i = int(rng.choice(metal))
        if rng.random() < 0.5:  # remove it
            mats, d = mats[:i] + mats[i + 1:], np.delete(d, i)
        else:  # change its material
            mats[i] = str(rng.choice([m for m in METALS if m != mats[i]]))
    elif kind == 4 and metal:  # move it anywhere
        i = int(rng.choice(metal))
        m, x = mats.pop(i), d[i]
        d = np.delete(d, i)
        j = int(rng.integers(0, len(mats) + 1))
        mats, d = [*mats[:j], m, *mats[j:]], np.insert(d, j, x)
    elif metal:  # redraw its thickness
        d[int(rng.choice(metal))] = rng.uniform(3.0, 25.0)
    else:
        mats, d = add_metal(mats, d, rng)
    return tidy(mats, d, rng)


def crossover(a, b, rng):
    za, zb = np.cumsum(a[1]), np.cumsum(b[1])
    cut = rng.uniform(0.2, 0.8) * min(za[-1], zb[-1])
    ia = int(np.searchsorted(za, cut))
    ib = int(np.searchsorted(zb, cut))
    mats = [*a[0][:ia], a[0][ia], b[0][ib], *b[0][ib + 1:]]
    d = np.concatenate([a[1][:ia], [cut - (za[ia - 1] if ia else 0.0), zb[ib] - cut], b[1][ib + 1:]])
    return tidy(mats, d, rng)


def polish_feasible(task):
    mats, d = task
    return co.polish((mats, np.maximum(d, co.FLOOR), co.FLOOR))


def main() -> None:
    minutes = float(sys.argv[1])
    seeds = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
    t_end = time.time() + 60 * minutes
    rng = np.random.default_rng(SEED)
    logf = (co.s.HERE / f"{OUT}.log").open("a", encoding="utf-8")

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    def desc(ind):
        m, x, r = ind
        return f"N {len(m)} metals {''.join(v for v in m if is_metal(v)) or '-'} MF {r:.5f} physical {x.sum():.0f} nm"

    log(f"start: {minutes} min, pop {POP}, seed {SEED}, dielectrics {DIELECTRICS}, metals <= {MAX_METALS}, "
        f"workers {co.WORKERS}, seeds {seeds}")
    pool = ProcessPoolExecutor(co.WORKERS)
    starts = [tidy(*fx.start_design(s), rng) for s in seeds]
    starts += [random_design(rng) for _ in range(POP - len(starts))]
    pop = sorted(pool.map(polish_feasible, starts), key=lambda t: t[2])
    log(f"first population: best {desc(pop[0])}, median MF {pop[len(pop) // 2][2]:.4f}")
    gen, best_seen, deep_done = 0, pop[0][2], None
    batch = 2 * co.WORKERS
    while time.time() < t_end:
        gen += 1
        kids = []
        for _ in range(batch):
            a = min(pop[int(rng.integers(len(pop)))], pop[int(rng.integers(len(pop)))], key=lambda t: t[2])
            if rng.random() < 0.5:
                b = min(pop[int(rng.integers(len(pop)))], pop[int(rng.integers(len(pop)))], key=lambda t: t[2])
                kids.append(crossover(a, b, rng))
            else:
                kids.append(mutate(a[0], a[1], rng))
        if gen % 5 == 0:  # fresh blood
            kids[-2:] = [random_design(rng), random_design(rng)]
        for kid in pool.map(polish_feasible, kids):
            if len(kid[0]) > co.N_MAX or kid[1].min() < co.FLOOR - 1e-9:
                continue
            if kid[2] < pop[-1][2] and all(abs(kid[2] - p[2]) > 1e-6 * p[2] for p in pop):
                pop[-1] = kid
                pop.sort(key=lambda t: t[2])
        if gen % DEEP_EVERY == 0 and pop[0][2] != deep_done:
            m, x, r = pop[0]
            for _ in range(3):
                got = fx.cycle(m, x, pool)
                if got is None or got[2] >= r * (1 - 1e-4):
                    break
                m, x, r = got
            deep_done = r
            if r < pop[0][2]:
                pop[0] = (m, x, r)
                deep_done = r
                log(f"gen {gen}: deep cycles -> {desc(pop[0])}")
        if pop[0][2] < best_seen:
            best_seen = pop[0][2]
            log(f"gen {gen}: best {desc(pop[0])}")
        if gen % 20 == 0:
            log(f"gen {gen}: best {pop[0][2]:.5f}, median {pop[len(pop) // 2][2]:.4f}, worst {pop[-1][2]:.4f}")
    pool.shutdown()
    rows = [{"rank": k, "layers": len(m), "metals": "".join(v for v in m if is_metal(v)), "mf_kernel": r,
             "mf_oracle": co.oracle_mf(m, x) if k == 0 else "", "thinnest_nm": float(x.min()),
             "physical_nm": float(x.sum()), "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in x)}
            for k, (m, x, r) in enumerate(pop)]
    with (co.s.HERE / f"{OUT}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log(f"end after {gen} generations: best {desc(pop[0])}, oracle {rows[0]['mf_oracle']:.5f}")


if __name__ == "__main__":
    main()
