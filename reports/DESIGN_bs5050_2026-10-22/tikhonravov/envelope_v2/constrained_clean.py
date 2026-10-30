"""Constrained three-line problem (N = 51, optical thicknesses 100-350 nm) reached from above (2026-10-29).

The stochastic procedure of 2012 (`constrained.py`) gave 0.875 at best against their 0.464. Here the start is one of
our unconstrained designs (gradual evolution or arm A, TOT 9000-10500 nm, N 60-100); the bounds are imposed at once
(bounded polish), then the cleaner of Trubetskov 2020: remove each layer in turn (the two neighbours merge), polish
within the bounds, keep the best, until N = 51. Last, on the REFINE best results only, the 2012 refinement: K = 6
series of 1000 starts around the design, relative sigma 3 % (MINUTES bounds the removal phase only).

usage: python constrained_clean.py STARTS MINUTES   (STARTS designs, best first; env CONSTRAINED_WORKERS, default 7)
outputs: constrained_clean_threeline_N51.csv (one row per start, oracle MF) and .log
"""

from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("SEARCH_TARGET", "threeline")

import numpy as np  # noqa: E402
import search as s  # noqa: E402
from constrained import M1, SIGMA, WORKERS, K, local  # noqa: E402

N_GOAL = 51
REFINE = 2  # designs refined by the 2012 series, best first; the series run past the deadline
SOURCES = [("gradual_classic.csv", 1.0), ("gradual_deep4.csv", 1.0), ("gradual_deep4_cont.csv", 1.0),
           ("gradual_classic_beam1.csv", 1.0), ("curve_3line_none_foc70-100_free_s1.csv", 100.0)]


def candidates() -> list[tuple[float, str, np.ndarray, str]]:
    """(MF %, seq, d, source) of the unconstrained designs with TOT 9000-10500 nm and N 60-100."""
    out = []
    for name, scale in SOURCES:
        path = s.HERE / name
        if not path.exists():
            continue
        for row in csv.DictReader(path.open(encoding="utf-8")):
            seq, d = row["seq"], np.array([float(v) for v in row["d_nm"].split()])
            tot = s.total_ot(seq, d)
            mf = scale * float(row.get("mf_oracle") or row["rmse_1601_oracle"])
            if 9000 <= tot <= 10500 and 60 <= len(seq) <= 100:
                out.append((mf, seq, d, name))
    out.sort(key=lambda t: t[0])
    best, bins = [], set()  # the best design of each 300 nm TOT bin, for diversity
    for t in out:
        b = int(s.total_ot(t[1], t[2]) // 300)
        if b not in bins:
            bins.add(b)
            best.append(t)
    return best


def removals(seq: str, d: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Every design with one layer removed; interior removal merges the two neighbours (N - 2)."""
    out, n = [], len(seq)
    for i in range(n):
        if 0 < i < n - 1:
            if n - 2 < N_GOAL:
                continue
            seq2 = seq[: i - 1] + seq[i - 1] + seq[i + 2 :]
            d2 = np.concatenate([d[: i - 1], [d[i - 1] + d[i + 1]], d[i + 2 :]])
        else:
            seq2, d2 = seq[:i] + seq[i + 1 :], np.delete(d, i)
        out.append((seq2, d2))
    return out


def ot(seq: str, d: np.ndarray) -> np.ndarray:
    return d * np.array([s.N_IDX[m] for m in seq])


def main() -> None:
    n_starts, minutes = int(sys.argv[1]), float(sys.argv[2])
    deadline = time.time() + 60 * minutes
    rng = np.random.default_rng(20261029)
    pool = ProcessPoolExecutor(WORKERS)
    name = f"constrained_clean_{s.TARGET}_N{N_GOAL}"
    log = (s.HERE / f"{name}.log").open("w", encoding="utf-8")

    def say(msg: str) -> None:
        log.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        log.flush()

    reached = []
    for k, (mf0, seq, d, src) in enumerate(candidates()[:n_starts]):
        if time.time() >= deadline:
            break
        say(f"start {k}: {src} N {len(seq)} TOT {s.total_ot(seq, d):.1f} MF {mf0:.4f} (unconstrained)")
        r, d = local((seq, ot(seq, d)))
        say(f"  bounded polish: N {len(seq)} MF {100 * r:.4f}")
        while len(seq) > N_GOAL and time.time() < deadline:
            cands = removals(seq, d)
            res = list(pool.map(local, [(q, ot(q, x)) for q, x in cands], chunksize=2))
            j = min(range(len(res)), key=lambda i: res[i][0])
            seq, (r, d) = cands[j][0], res[j]
            say(f"  remove -> N {len(seq)} MF {100 * r:.4f} TOT {s.total_ot(seq, d):.1f}")
        if len(seq) != N_GOAL:
            say(f"  stopped at N {len(seq)} (deadline)")
            continue
        reached.append((r, k, mf0, src, seq, d))
    rows = []
    for r, k, mf0, src, seq, d in sorted(reached, key=lambda t: t[0])[:REFINE]:
        say(f"refine start {k}: MF {100 * r:.4f}")
        for series in range(K):
            starts = ot(seq, d) * (1 + SIGMA * rng.standard_normal((M1, N_GOAL)))
            r1, d1 = min(pool.map(local, [(seq, x) for x in starts], chunksize=8), key=lambda t: t[0])
            if r1 < r:
                r, d = r1, d1
            say(f"  series {series + 1}: MF {100 * r:.4f}")
        o = ot(seq, d)
        ro = s.oracle_rmse(seq, d)
        rows.append({"start": k, "source": src, "mf_start": mf0, "layers": len(seq), "mf_kernel": 100 * r,
                     "mf_oracle": 100 * ro, "total_ot_nm": s.total_ot(seq, d), "ot_min": float(o.min()),
                     "ot_max": float(o.max()), "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
        say(f"start {k} best: MF oracle {100 * ro:.4f} TOT {s.total_ot(seq, d):.1f} OT {o.min():.2f}-{o.max():.2f}")
        with (s.HERE / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    pool.shutdown()


if __name__ == "__main__":
    main()
