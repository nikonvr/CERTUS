"""OIC 2016 B1 (cissoid): trade slots at constant N = 50: a needle paid by freeing the cheapest slots elsewhere.

Audit of 0.012210 (2026-11-01, cissoid_layer_value.py): freeing a slot costs +1.76 % (merge 35L+36F into F) or +3.62 %
(delete Ag 9), everything else >= +39 %; the best needle (F inside the 1591 nm H layer 6) gains -6.0 % but takes 2
slots (it splits the layer). A fixed-N cycle frees at most the slot next to the needle, so it never tries this.
Each of the NEEDLES // 2 best needles (polished gain, one per material and layer) is combined with every set of up to 3
of the FREES cheapest freeings (disjoint layers) that brings N back to 49-50 (counted on the result: deleting a metal
between two equal dielectrics frees 2 slots); each design is polished on the 301 points; the best trades of 4 distinct
needle layers get a swap descent (N1, metal trades, ADD, N2 of flair_campaign); a design better than the start is
written to OUT as soon as it is found.
usage: python cissoid_slot_trade.py IN.csv OUT.csv
"""

from __future__ import annotations

import csv
import itertools
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import cissoid_collapse as cc
import cissoid_fixedN as fx
import cissoid_opt as co
import flair_campaign as fc
import numpy as np

NEEDLES, FREES = 16, 8


def freeings(m, d):
    out = [(("del", i), f"delete {i}{m[i]}") for i in range(len(m))]
    out += [(("merge", i), f"merge {i}{m[i]}+{i + 1}{m[i + 1]}") for i in range(len(m) - 1)
            if m[i] in cc.DIEL and m[i + 1] in cc.DIEL]
    return out


def apply_free(m, d, op):
    kind, i = op
    if kind == "del":
        return m[:i] + m[i + 1:], np.delete(d, i)
    y, t, _e = cc.single_for(m[i:i + 2], d[i:i + 2])
    return [*m[:i], y, *m[i + 2:]], np.concatenate([d[:i], [t], d[i + 2:]])


def layers_of(op):
    return {op[1]} if op[0] == "del" else {op[1], op[1] + 1}


def trades(pool, m, d, base, t0, n_needles=NEEDLES // 2):
    """Every kept needle paid by every set of up to 3 cheap freeings that brings N back to 49-50; returns
    (designs, hows, polished results, MF values), invalid designs at +inf."""
    frees = freeings(m, d)
    costs = list(pool.map(co.polish_full, [(*co.normalize(*apply_free(m, d, op), 0.0), co.FLOOR) for op, _h in frees]))
    order = np.argsort([q[2] for q in costs])[:FREES]
    cheap = [frees[k] for k in order]
    print(f"base {base:.6f}; cheapest freeings: " + ", ".join(f"{h} {100 * (costs[k][2] / base - 1):+.2f} %"
                                                               for k, (_op, h) in zip(order, cheap, strict=True)))
    p = sorted(g for part in pool.map(fx._p_one, [(m, d, c) for c in co.NEEDLE_MATS]) for g in part)
    needles, seen = [], set()
    for g, cand, i, z in p:  # one per (material, layer): the gradient alone repeats one layer at nearby depths
        if g >= 0 or len(needles) >= 3 * NEEDLES:
            break
        if (cand, i) not in seen:
            seen.add((cand, i))
            needles.append((cand, i, z))
    # ranked by the polished gain of the grown design (the -6 % needle of cissoid_layer_value was not a top gradient)
    grown = list(pool.map(co.polish_full, [(*co.normalize(*co.insert(m, d, c, i, z, 3.0 if fx.is_metal(c) else 10.0),
                                                          0.5), co.FLOOR) for c, i, z in needles]))
    needles = [needles[k] for k in np.argsort([q[2] for q in grown])[:n_needles]]
    print("needles kept: " + ", ".join(f"{c}@{i} z={z:.0f}" for c, i, z in needles), flush=True)
    designs, hows = [], []
    for cand, i, z in needles:
        m1, d1 = co.insert(m, d, cand, i, z, 3.0 if fx.is_metal(cand) else 10.0)
        m1, d1 = co.normalize(m1, d1, 0.5)  # an insertion at z = 0 adds one layer, inside a layer two
        extra = len(m1) - len(m)
        for r in range(1, 4):
            for combo in itertools.combinations(cheap, r):
                used = [layers_of(op) for op, _h in combo]
                if any(a & b for a, b in itertools.combinations(used, 2)):
                    continue
                mm, dd = list(m1), d1.copy()
                # free from the top down, shifting indices above the needle by the layers it added
                for op, _h in sorted(combo, key=lambda t: -t[0][1]):
                    k = op[1] + (extra if op[1] >= i else 0)
                    mm, dd = apply_free(mm, dd, (op[0], k))
                mm, dd = co.normalize(mm, dd, 0.0)
                # the real count: deleting a metal between two equal dielectrics frees 2 slots (fixed 2026-11-01
                # 10:50, it counted 1 and rejected those trades)
                if not co.N_MAX - 1 <= len(mm) <= co.N_MAX:
                    continue
                designs.append((mm, dd, co.FLOOR))
                hows.append(f"needle {cand}@{i} z={z:.0f} + " + " + ".join(h for _op, h in combo))
    res = list(pool.map(co.polish_full, designs, chunksize=2))
    vals = [q[2] if len(q[0]) <= co.N_MAX and q[1].min() >= co.FLOOR - 1e-9 else np.inf for q in res]
    print(f"{len(designs)} trades ({time.time() - t0:.0f} s); best:", flush=True)
    for k in np.argsort(vals)[:6]:
        print(f"  {hows[k]}: N {len(res[k][0])}, MF {vals[k]:.6f} ({100 * (vals[k] / base - 1):+.2f} %)", flush=True)
    return designs, hows, res, vals


def distinct_needles(hows, vals, count):
    """Indices of the best trades, one per needle layer (on 0.012210 the 5 best were one needle in 5 materials)."""
    picked, seen = [], set()
    for k in np.argsort(vals):
        where = hows[k].split()[1].split("@")[1]
        if np.isfinite(vals[k]) and where not in seen:
            seen.add(where)
            picked.append(int(k))
        if len(picked) == count:
            break
    return picked


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    r0 = list(csv.DictReader((co.s.HERE / src).open(encoding="utf-8")))[-1]
    m, d = r0["mats"].split(), np.array([float(v) for v in r0["d_nm"].split()])
    t0 = time.time()
    with ProcessPoolExecutor(co.WORKERS) as pool:
        m, d, base = co.polish_full((m, d, co.FLOOR))
        _designs, hows, res, vals = trades(pool, m, d, base, t0)
        best = None
        for k in distinct_needles(hows, vals, 4):
            mm, dd, ff = res[k]
            mm, dd, ff, steps = fc.descend(pool, mm, dd, ff, names=("N1", "MT", "ADD", "N2"), rounds=4)
            print(f"  {hows[k]} + descent {steps}: MF {ff:.6f} ({time.time() - t0:.0f} s)", flush=True)
            if best is None or ff < best[2]:
                best = (mm, dd, ff, hows[k] + (" + " + " + ".join(steps) if steps else ""))
            if ff < base * (1 - 1e-4) and fc.ok(mm, dd):  # keep every gain at once: a later crash must not lose it
                save(dst, *best)
        mm, dd, ff, how = best
        if ff < base * (1 - 1e-4) and fc.ok(mm, dd):
            o = save(dst, mm, dd, ff, how)
            print(f"GAIN: oracle {o:.6f} vs {base:.6f} [{how}] -> {dst}", flush=True)
        else:
            print(f"no gain: best {ff:.6f} vs {base:.6f}", flush=True)


def save(dst, mm, dd, ff, how) -> float:
    o = co.oracle_mf(mm, dd)
    with (co.s.HERE / dst).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["how", "layers", "mf_full", "mf_oracle", "mats", "d_nm"])
        w.writeheader()
        w.writerow({"how": how, "layers": len(mm), "mf_full": ff, "mf_oracle": o, "mats": " ".join(mm),
                    "d_nm": " ".join(f"{v:.4f}" for v in dd)})
    return o


if __name__ == "__main__":
    main()
