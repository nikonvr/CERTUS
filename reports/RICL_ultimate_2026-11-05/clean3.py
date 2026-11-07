"""Cleaning to the contest floor with the three owner options for each layer under the floor (owner 2026-11-07):
delete (its thickness goes to a neighbour), thicken (set to the floor), or change material (set to the floor in
another material). Each option is refined at fixed total thickness with the floor as bound; the best is kept.
Applied only at the end of a search; the layer count is capped at nmax by deletion of the least harmful layer."""
import os
import sys

os.environ.setdefault("CIS_AXIS", "phys")
import engine_multi as M  # noqa: E402
import numpy as np  # noqa: E402


def refine(s, x, tot, floor, it=250):
    x2, _, _ = M.lm(s, x, tot, floor, it)
    return x2

def options(s, x, i, floor):
    out = []
    s2, x2 = M.remove_layer(s, x, i)
    out.append(("delete", s2, x2))
    y = x.copy()
    y[i] = floor
    out.append(("thicken", s, y))
    diels = [m for m in "FLBMTH"]
    for m in M.MATS:
        if m == s[i] or m == "U":
            continue
        t = s[:i] + m + s[i + 1:]
        y = x.copy()
        y[i] = floor
        out.append((f"swap->{m}", t, y))
        # the adjacent dielectrics follow the change: each neighbour (left, right, both) is also swapped to a dielectric
        if m in "FLBMTH":
            nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(s) and s[j] in diels]
            for j in nbs:
                for m2 in diels:
                    if m2 == s[j]:
                        continue
                    t2 = t[:j] + m2 + t[j + 1:]
                    out.append((f"swap->{m}+nb{j}->{m2}", t2, y.copy()))
    return out

def clean3(s, x, tot, floor=3.0, nmax=50, rounds=200):
    tot = float(x.sum()) if tot is None else tot
    s, x = M.normalize(s, x, 1e-3)
    x = refine(s, x, tot, 0.0)
    for _ in range(rounds):
        thin = [int(i) for i in np.flatnonzero(x < floor * 0.999)]
        if not thin and len(s) <= nmax:
            break
        if thin:
            i = min(thin, key=lambda k: x[k])
            best = None
            for name, s2, x2 in options(s, x, i, floor):
                s2, x2 = M.normalize(s2, x2, 1e-3)
                y = refine(s2, x2, tot, 0.0, 120)
                r = M.oracle_mf(s2, y)
                if best is None or r < best[0]:
                    best = (r, name, s2, y)
            _, name, s, x = best
        else:
            # too many layers: delete the least useful one (the thinnest after refinement)
            i = int(np.argmin(x))
            s, x = M.normalize(*M.remove_layer(s, x, i), 1e-3)
        x = refine(s, x, tot, 0.0)
    x = refine(s, x, tot, floor, 400)
    return s, x

if __name__ == "__main__":
    import csv
    src, outp = sys.argv[1], sys.argv[2]
    r = list(csv.DictReader(open(src, encoding="utf-8")))[-1]
    s = r["mats"].replace(" ", "")
    x = np.array([float(v) for v in r["d_nm"].split()])
    s2, x2 = clean3(s, x, float(x.sum()))
    print("cleaned: oracle", round(M.oracle_mf(s2, x2), 5), "N", len(s2), "thinnest", round(x2.min(), 3), "physical", round(x2.sum(), 1))
    with open(outp, "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["mf_oracle", "layers", "thinnest_nm", "physical_nm", "mats", "d_nm"])
        w.writerow([M.oracle_mf(s2, x2), len(s2), x2.min(), x2.sum(), s2, " ".join(f"{v:.9f}" for v in x2)])
