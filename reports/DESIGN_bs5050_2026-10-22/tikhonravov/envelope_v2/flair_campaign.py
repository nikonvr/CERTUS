"""OIC 2016 B1 (cissoid): overnight iterated local search over material swaps, screened by short polishes (2026-11-01).

Why (flair_backtest.out, 2026-11-01): a polish stopped after 10 then 30 iterations ranks swap combinations nearly like
the full polish (Spearman 0.91-0.97 on the 180 singles) and kept past winning pairs near the top of the 15750 pairs,
while the one-step Gauss-Newton estimate did not. So every neighbourhood is screened: all candidates at max_nfev 10, the
best Q1 again at 30, the best Q2 fully polished (max_nfev 300, the search's judge); the oracle decides a record.
Neighbourhoods: N1 every single dielectric swap, N2 every pair, N3/N4 every triple/quadruple of ladder moves (a layer to
its neighbour on F < L < B < M < T < H: 25 of the 28 winning swaps of 2026-10-31; 64-94 % of the 50 best pairs at 30
iterations against 8 % of all pairs), BEAM the 150 best pairs extended one swap at a time up to 5 swaps (all six
dielectrics), INV inversions of neighbouring layers.
Plan: the FLAIR_START stages on the start design; then until the deadline, perturb the best (in turn a forced growth as
cissoid_force_grow.py with a new seed, and a kick of 3-5 ladder moves drawn with the history's weights: recently changed
layers and their neighbours, layers 10-19 and 40-49, the hub layers of the best's 50 best pairs, half the kicks
clustered within 3 layers), descend with N1 + N2 while it gains, keep a better design; every new best also gets BEAM and
N3. After STALL iterations without a record, every other perturbation starts from one of the best near misses. Layer
indices count from 0 (substrate side).
usage: python flair_campaign.py IN.csv HOURS   (env FLAIR_START default "N1,INV,N2,BEAM,N3,N4"; FLAIR_ITERS caps the
       loop; FLAIR_SUBSET samples each neighbourhood (smoke tests); FLAIR_DATA, a folder for the per-candidate csv; the
       CISSOID_* env of dig.sh)
"""

from __future__ import annotations

import csv
import itertools
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cissoid_fixedN as fx
import cissoid_islands as ci
import cissoid_multiswap as ms
import cissoid_opt as co
import numpy as np

LADDER = "FLBMTH"
STALL = 12
# (kept after 10, fully polished), as fractions of all candidates. Backtest: the winning pairs of 0.01375, 0.01316 and
# 0.01299 ranked 1, 2602 and 337 of 15750 at 10 iterations, 1, 491 and 5 at 30: (0.25, 0.05) keeps all three; the
# winning quadruple of 0.01408 ranked 941 and 493 of 20001 random quadruples (4.7 %, 2.5 %): (0.10, 0.03) keeps it
Q_SMALL, Q_BIG = (0.25, 0.05), (0.10, 0.03)
ADD_K, ADD_SIZES = 16, (2, 3, 4, 5)
HOT = set(range(10, 20)) | set(range(40, 50))  # 19 of the 28 winning swaps of 2026-10-31 fell there
RECENT0 = [40, 43, 24, 26, 10, 46, 49, 41, 35, 47]  # layers changed by the last records, newest first
BEAM_WIDTH, BEAM_DEPTH = 150, 5
LAST: dict = {}  # per neighbourhood name, the ranking of its last screen (design key, full and sp30 lists)
DATA = Path(os.environ["FLAIR_DATA"]) if os.environ.get("FLAIR_DATA") else None
SUBSET = int(os.environ.get("FLAIR_SUBSET", "0"))  # > 0: a random subset of each N2-N4 neighbourhood (smoke tests only)
T0 = time.time()


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def journal(msg: str) -> None:
    if SUBSET:  # a smoke test leaves the campaign journal alone
        return
    with (co.s.HERE / "campaign.log").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M')} {msg}\n")


def sp_batch(task) -> list[float]:
    """MF after a polish of max_nfev NFEV of each swap set, on one shared base (one pickled base per batch)."""
    m, d, sets, nfev = task
    return [co.polish_full((*ms.apply(m, d, s), co.FLOOR, nfev))[2] for s in sets]


def sp_design(task):
    m, d, swaps, nfev = task
    return co.polish_full((*ms.apply(m, d, swaps), co.FLOOR, nfev))


def batched(pool, m, d, sets, nfev, size):
    tasks = [(m, d, sets[k:k + size], nfev) for k in range(0, len(sets), size)]
    return np.array([v for part in pool.map(sp_batch, tasks) for v in part])


def ok(m, d) -> bool:
    return len(m) <= co.N_MAX and d.min() >= co.FLOOR - 1e-9


TABU: set = set()  # (layer, material) moves forbidden during a descent: undoing the kick (2026-11-01 night: 20 of 27
# descents undid it and gave the record back bit for bit)


def moves(m, ladder: bool):
    out = []
    for i, x in enumerate(m):
        if x not in LADDER:
            continue
        k = LADDER.index(x)
        ys = [LADDER[j] for j in (k - 1, k + 1) if 0 <= j < len(LADDER)] if ladder else [y for y in LADDER if y != x]
        out += [(i, y) for y in ys if (i, y) not in TABU]
    return out


def metal_trades(m, d):
    """(how, mats, d) of every metal layer deleted, turned into a dielectric (same physical thickness) or into the other
    metal: the record 0.012869 -> 0.012706 came from Ag layer 27 -> H, a move no dielectric swap search contained."""
    out = []
    for i, x in enumerate(m):
        if not fx.is_metal(x):
            continue
        out.append((f"delete {i}{x}", *co.normalize(m[:i] + m[i + 1:], np.delete(d, i), 0.0)))
        out += [(f"{i}{x}->{y}", *co.normalize([*m[:i], y, *m[i + 1:]], d.copy(), 0.0))
                for y in [*LADDER, *fx.METALS] if y != x]
    return out


def combos(mv, n):
    out = [c for c in itertools.combinations(mv, n) if len({i for i, _ in c}) == n]
    return random.Random(n).sample(out, SUBSET) if 0 < SUBSET < len(out) else out


def label_of(swaps) -> str:
    return " ".join(f"{i}{y}" for i, y in swaps)


def dump(stage_name, base, rows) -> None:
    if DATA is None:
        return
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "flair_campaign_cands.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["t_s", "stage", "base", "swaps", "sp10", "sp30", "full"])
        w.writerows([(f"{time.time() - T0:.0f}", stage_name, f"{base:.6f}", *r) for r in rows])


def screen(pool, m, d, base, cands, name):
    """Cascade over swap sets; returns (f, m2, d2, how) of the best fully polished one."""
    t = time.time()
    q1, q2 = Q_BIG if len(cands) > 50000 else Q_SMALL
    f10 = batched(pool, m, d, cands, 10, 32)
    idx1 = np.argsort(f10)[:max(min(len(cands), 200), int(q1 * len(cands)))]
    f30 = batched(pool, m, d, [cands[k] for k in idx1], 30, 8)
    idx2 = idx1[np.argsort(f30)[:max(min(len(idx1), 100), int(q2 * len(cands)))]]
    full = list(pool.map(sp_design, [(m, d, cands[k], 300) for k in idx2], chunksize=4))
    vals = [r[2] if ok(r[0], r[1]) else np.inf for r in full]
    j = int(np.argmin(vals))
    how = label_of(cands[idx2[j]])
    log(f"  {name}: {len(cands)} -> {len(idx1)} -> {len(idx2)} full; best sp10 {f10.min():.5f} sp30 {f30.min():.5f} "
        f"full {vals[j]:.5f} [{how}] vs {base:.5f} ({time.time() - t:.0f} s)")
    f30_of = dict(zip(idx1.tolist(), f30.tolist(), strict=True))
    dump(name, base, [(label_of(cands[k]), f"{f10[k]:.6f}", f"{f30_of[k]:.6f}", f"{v:.6f}")
                      for k, v in zip(idx2.tolist(), vals, strict=True)])
    LAST[name] = {"key": key_of(m, d),
                  "full": sorted(((tuple(cands[k]), v) for k, v in zip(idx2.tolist(), vals, strict=True)),
                                 key=lambda t: t[1]),
                  "sp30": [(tuple(cands[idx1[q]]), float(f30[q])) for q in np.argsort(f30)]}
    return vals[j], full[j][0], full[j][1], how


def key_of(m, d):
    return tuple(m), np.asarray(d).tobytes()


def hub_counts(name="N2", top=50) -> dict[int, int]:
    """Layers most often in the best pairs at 30 iterations (2026-11-01 profile: a few hub layers, 43 above all, sit
    in a third to a half of the 50 best pairs of each design)."""
    out: dict[int, int] = {}
    for c, _v in LAST.get(name, {}).get("sp30", [])[:top]:
        for i, _y in c:
            out[i] = out.get(i, 0) + 1
    return out


def beam(pool, m, d, f):
    """Beam over the number of swaps: the BEAM_WIDTH best pairs (full polish) each extended by every single swap of
    another layer, screened, the best BEAM_WIDTH kept, up to BEAM_DEPTH swaps; all six dielectrics."""
    if LAST.get("N2", {}).get("key") != key_of(m, d):
        stage(pool, "N2", m, d, f)
    width = 3 if SUBSET else BEAM_WIDTH
    level, mv, best = [c for c, _v in LAST["N2"]["full"][:width]], moves(m, ladder=False), None
    for k in range(3, BEAM_DEPTH + 1):
        seen: set = set()
        cands = []
        for c in level:
            used = {i for i, _ in c}
            for x in mv:
                t = tuple(sorted((*c, x)))
                if x[0] not in used and t not in seen:
                    seen.add(t)
                    cands.append(t)
        got = screen(pool, m, d, f, cands, f"BEAM{k}")
        best = got if best is None or got[0] < best[0] else best
        level = [c for c, _v in LAST[f"BEAM{k}"]["full"][:width]]
    return best


def best_of(full, hows):
    vals = [r[2] if ok(r[0], r[1]) else np.inf for r in full]
    j = int(np.argmin(vals))
    return vals[j], full[j][0], full[j][1], hows[j]


def stage(pool, name, m, d, f):
    if name == "MT":
        trades = metal_trades(m, d)
        full = list(pool.map(co.polish_full, [(tm, td, co.FLOOR) for _h, tm, td in trades], chunksize=2))
        return best_of(full, [h for h, _tm, _td in trades])
    if name == "N1":
        sets = [[c] for c in moves(m, ladder=False)]
        full = list(pool.map(sp_design, [(m, d, s, 300) for s in sets], chunksize=4))
        vals = [r[2] if ok(r[0], r[1]) else np.inf for r in full]
        LAST["N1"] = {"key": key_of(m, d),
                      "full": sorted(zip((tuple(s) for s in sets), vals, strict=True), key=lambda t: t[1])}
        return best_of(full, [label_of(s) for s in sets])
    if name == "ADD":
        # the additive regime (backtest: the winning triple of 0.01379 and quadruple of 0.01408 ranked 1 and 3 by the
        # sum of their singles' gains): combinations of the ADD_K best singles, one per layer
        if LAST.get("N1", {}).get("key") != key_of(m, d):
            stage(pool, "N1", m, d, f)
        top, used = [], set()
        for c, _v in LAST["N1"]["full"]:
            if c[0][0] not in used and len(top) < ADD_K:
                used.add(c[0][0])
                top.append(c[0])
        return screen(pool, m, d, f, [c for n in ADD_SIZES for c in itertools.combinations(top, n)], "ADD")
    if name == "INV":
        tasks, hows = [], []
        for i in range(len(m) - 1):
            m2, d2 = list(m), d.copy()
            m2[i], m2[i + 1], d2[i], d2[i + 1] = m[i + 1], m[i], d[i + 1], d[i]
            tasks.append((*co.normalize(m2, d2, 0.0), co.FLOOR))
            hows.append(f"invert {i}-{i + 1}")
        return best_of(list(pool.map(co.polish_full, tasks)), hows)
    if name == "N2":
        return screen(pool, m, d, f, combos(moves(m, ladder=False), 2), "N2")
    if name in ("N3", "N4"):
        return screen(pool, m, d, f, combos(moves(m, ladder=True), int(name[1])), name)
    if name == "BEAM":
        return beam(pool, m, d, f)
    raise ValueError(name)


def descend(pool, m, d, f, names=("N1", "MT", "ADD", "N2"), rounds=6, record=None):
    """Best-improvement descent over the given neighbourhoods; returns (m, d, f, hows). With ``record``, it gives up
    after round r while f > record * (1 + 0.12 / r): a perturbed design that far rarely comes back below the record."""
    hows = []
    for r in range(1, rounds + 1):
        best = min((stage(pool, n, m, d, f) for n in names), key=lambda q: q[0])
        if best[0] >= f * (1 - 1e-4):
            break
        f, m, d = best[0], best[1], best[2]
        hows.append(best[3])
        log(f"  descent: {f:.5f} [{best[3]}]")
        if record is not None and f > record * (1 + 0.12 / r):
            log(f"  descent given up: {f:.5f} after round {r}")
            break
    return m, d, f, hows


class Night:
    def __init__(self, src: str, hours: float):
        r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
        self.m, self.d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
        self.f = self.o = float("inf")
        self.deadline = T0 + hours * 3600.0
        self.recent = list(RECENT0)
        self.near: list[tuple[float, list, np.ndarray]] = []
        self.rng = random.Random(20261101)
        self.p_cache: dict = {}
        self.hub: dict[int, int] = {}

    def left(self) -> float:
        return self.deadline - time.time()

    def better(self, m, d, f) -> bool:
        return ok(m, d) and f < self.f * (1 - 1e-4)

    def record(self, m, d, f, how) -> bool:
        o = co.oracle_mf(m, d)
        if o >= self.o * (1 - 1e-4):
            log(f"  not a record by the oracle: {o:.6f} vs {self.o:.6f}")
            return False
        if len(m) == len(self.m):
            changed = [i for i in range(len(m)) if m[i] != self.m[i]]
            self.recent = (changed + [i for i in self.recent if i not in changed])[:12]
        self.m, self.d, self.f, self.o = list(m), d.copy(), f, o
        row = {"how": how, "layers": len(m), "mf_kernel": f, "mf_full": f, "mf_oracle": o,
               "metals": "".join(x for x in m if x in "AUN"), "physical_nm": float(d.sum()),
               "mats": " ".join(m), "d_nm": " ".join(f"{v:.4f}" for v in d)}
        name = ("smoke_" if SUBSET else "") + "cissoid_record_0p" + f"{o:.5f}"[2:]
        path, k = co.s.HERE / f"{name}.csv", 1
        while path.exists():
            path, k = co.s.HERE / f"{name}_{k}.csv", k + 1
        for p in (path,) if SUBSET else (path, co.s.HERE / "cissoid_record_best.csv"):
            with p.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row))
                w.writeheader()
                w.writerow(row)
        log(f"NEW RECORD {o:.6f} oracle [{how}] -> {path.name}")
        journal(f"flair_campaign NEW RECORD {o:.6f} oracle ({how}), {path.name}")
        return True

    def take_hubs(self) -> None:
        """Hub layers from the last N2 screen, if it ran on the current best."""
        if LAST.get("N2", {}).get("key") == key_of(self.m, self.d):
            self.hub = hub_counts()
            log("hub layers of the best: " + " ".join(f"{i}{self.m[i]}:{c}" for i, c in
                                                      sorted(self.hub.items(), key=lambda t: -t[1])[:8]))

    def kick(self, m, d):
        dl = [i for i, x in enumerate(m) if x in LADDER]
        w = {i: 1.0 + (1.0 if i in HOT else 0.0) for i in dl}
        for rank, i in enumerate(self.recent):
            for j in range(i - 3, i + 4):
                if j in w:
                    w[j] += (1.5 if j == i else 0.75) / (1 + rank / 4)
        for i, c in self.hub.items():  # hub layers of the best's pairs
            if i in w:
                w[i] += c / 4
        k = self.rng.choice([3, 4, 5])
        if self.rng.random() < 0.5:  # clustered, as every winning pair of 2026-10-31 (layers at most 3 apart)
            c = self.rng.choices(dl, weights=[w[i] for i in dl])[0]
            near = [i for i in dl if abs(i - c) <= 3]
            layers = self.rng.sample(near, min(k, len(near)))
        else:
            layers = []
            while len(layers) < k:
                c = self.rng.choices(dl, weights=[w[i] for i in dl])[0]
                if c not in layers:
                    layers.append(c)
        sw = []
        for i in sorted(layers):
            x = LADDER.index(m[i])
            sw.append((i, LADDER[self.rng.choice([j for j in (x - 1, x + 1) if 0 <= j < len(LADDER)])]))
        return sw

    def kicks(self, pool, m, d, n=15):
        """The best of n kicks, each fully polished (smoke test: a single kick often lands at 7-8 times the record)."""
        sets = [self.kick(m, d) for _ in range(n)]
        full = list(pool.map(sp_design, [(m, d, s, 300) for s in sets]))
        f2, m2, d2, how = best_of(full, ["kick " + label_of(s) for s in sets])
        chosen = sets[["kick " + label_of(s) for s in sets].index(how)]
        return m2, d2, f2, how, {(i, m[i]) for i, _y in chosen}

    def needle_points(self, m, d):
        key = (tuple(m), d.tobytes())
        if key not in self.p_cache:
            cands, used = [], set()
            for g, cand, i, z in sorted(co.p_function(m, d)):
                if i not in used and len(cands) < 60:  # 30 gave the same 0.01317 design 5 times in the night
                    used.add(i)
                    cands.append((g, cand, i, z))
            self.p_cache = {key: cands}
        return self.p_cache[key]

    def grow(self, pool, m, d, seed):
        """One trial of cissoid_force_grow.py (2-4 needles among the 30 best P-function points, back to 50 layers,
        cycles, swap round), with its own seed."""
        rng = np.random.default_rng(seed)
        cands = self.needle_points(m, d)
        n_ins = int(rng.choice([2, 3, 4]))
        pick = sorted(rng.choice(len(cands), size=n_ins, replace=False), key=lambda k: -cands[k][2])
        m2, d2 = list(m), d.copy()
        for k in pick:  # from the top of the stack down, so the lower indices stay valid
            _g, cand, i, z = cands[k]
            m2, d2 = co.insert(m2, d2, cand, i, z, rng.uniform(2.0, 4.0) if fx.is_metal(cand) else rng.uniform(8.0, 25.0))
        m2, d2, _r = co.polish((m2, d2, co.FLOOR))
        while len(m2) > co.N_MAX:
            m2, d2, _r = fx.removal(m2, d2, pool)
        m2, d2, r = fx.feasible(m2, d2)
        for _ in range(5):
            got = fx.cycle(m2, d2, pool)
            if got is None or got[2] >= r * (1 - 1e-4):
                break
            m2, d2, r = got
        m2, d2, r, kept = ci.swap_round(m2, d2, r, pool)
        m2, d2, f2 = co.polish_full((m2, d2, co.FLOOR))
        return m2, d2, f2, f"grow {n_ins} needles seed {seed}, {kept} swaps"

    def run(self, start_stages: list[str], iters: int) -> None:
        with ProcessPoolExecutor(co.WORKERS) as pool:
            self.m, self.d, self.f = co.polish_full((self.m, self.d, co.FLOOR))
            self.o = co.oracle_mf(self.m, self.d)
            log(f"start {self.f:.6f} (oracle {self.o:.6f}), N {len(self.m)}, {self.left() / 3600:.1f} h, "
                f"{co.WORKERS} workers, start stages {start_stages}")
            journal(f"flair_campaign started from {self.o:.6f} for {self.left() / 3600:.1f} h (start stages "
                    f"{','.join(start_stages)}, then forced growth / weighted ladder kicks + N1 N2 descent; "
                    f"flair_campaign.out)")
            for name in start_stages:
                if self.left() < 900:
                    break
                try:
                    got = stage(pool, name, self.m, self.d, self.f)
                    log(f"{name} on the best: {got[0]:.5f} [{got[3]}]")
                    if self.better(got[1], got[2], got[0]) and self.record(got[1], got[2], got[0], got[3]):
                        m, d, f, hows = descend(pool, self.m, self.d, self.f)
                        if hows and self.better(m, d, f):
                            self.record(m, d, f, " + ".join(hows))
                except Exception as exc:  # a failed stage must not end the night
                    log(f"{name}: error {type(exc).__name__}: {exc}")
            self.take_hubs()
            stall, it = 0, 0
            while self.left() > 900 and it < iters:
                it += 1
                base, origin = (self.m, self.d), "best"
                if stall >= STALL and self.near and stall % 2 == 0:
                    f_n, m_n, d_n = self.near[(stall // 2) % len(self.near)]
                    base, origin = (m_n, d_n), f"near miss {f_n:.5f}"
                try:
                    if it % 2:
                        m, d, f, how = self.grow(pool, base[0], base[1], 1000 + it)
                    else:
                        m, d, f, how, tabu = self.kicks(pool, base[0], base[1])
                        TABU.update(tabu)  # the descent may not put a kicked layer back
                    log(f"it {it} (from {origin}): {how}: {f:.5f} (best {self.f:.5f})")
                    if f > self.f * 1.25:
                        log(f"it {it}: more than 25 % above the best, no descent")
                        stall += 1
                        continue
                    m, d, f, hows = descend(pool, m, d, f, record=self.f)
                    log(f"it {it}: after descent {f:.5f} ({len(hows)} steps)")
                except Exception as exc:  # one failed iteration must not end the night
                    log(f"it {it}: error {type(exc).__name__}: {exc}")
                    continue
                finally:
                    TABU.clear()
                if self.better(m, d, f) and self.record(m, d, f, " + ".join([how, *hows])):
                    stall = 0
                    for name in ("BEAM", "N3"):  # deeper neighbourhoods around the new best
                        try:
                            got = stage(pool, name, self.m, self.d, self.f)
                            log(f"{name} on the new best: {got[0]:.5f} [{got[3]}]")
                            if self.better(got[1], got[2], got[0]):
                                self.record(got[1], got[2], got[0], got[3])
                        except Exception as exc:
                            log(f"{name} after the record: error {type(exc).__name__}: {exc}")
                    self.take_hubs()
                    continue
                stall += 1
                if ok(m, d) and self.f * 1.001 < f < self.f * 1.02:  # a copy of the best is no near miss
                    self.near = sorted([*self.near, (f, list(m), d.copy())], key=lambda t: t[0])[:4]
            log(f"end after {it} iterations: best {self.o:.6f} oracle ({(time.time() - T0) / 3600:.1f} h)")
            journal(f"flair_campaign done: {it} iterations, best {self.o:.6f} oracle")


def main() -> None:
    src, hours = sys.argv[1], float(sys.argv[2])
    start = [s for s in os.environ.get("FLAIR_START", "N1,ADD,INV,N2,BEAM,N3,N4").split(",") if s]
    Night(src, hours).run(start, int(os.environ.get("FLAIR_ITERS", "100000")))


if __name__ == "__main__":
    main()
