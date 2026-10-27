"""RMSE*(N) of the Tikhonravov 50/50 splitter, pushed from the 2026-10-26 envelope (`../envelope_free/`).

Same problem and judge as `../envelope_free/`: T = 0.5 over 400-1200 nm, nH = 2.35, nL = 1.45, glass 1.52, air,
no back side, 1601 points; RMSE judged by the independent oracle `tests/oracle/tmm_reference.py`.

Residuals and Jacobian come from CERTUS (`design_fast_gauss_newton._res_jac_lossless_normal_kernel`, exact at k = 0),
polished by `scipy.optimize.least_squares` (trf, box d >= floor). Moves on the elites of each N:
perturbation (same N), needle insertion of the other material inside a layer (N + 2), layer added at either end
(N + 1), layer removed with merge of equal neighbours (N - 1 or N - 2). Floors: 0.1 nm ("free") and 5 nm.

usage: python search.py {free,5nm} MINUTES [SEED [CURVE.csv ...]]  (curves of earlier runs are added to the starts)
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import ClassVar

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "oracle")]

import tmm_reference as oracle  # noqa: E402

from certus.physics.design_fast_gauss_newton import _res_jac_lossless_normal_kernel  # noqa: E402
from certus.physics.design_fast_normal import cost_lossless_front_fast  # noqa: E402

OLD = HERE.parent / "envelope_free"
L0 = 500.0
N_IDX = {"H": float(os.environ.get("SEARCH_NH", "2.35")), "L": 1.45}  # env SEARCH_NH: material-lever study only
N_SUB = 1.52
WLS = np.linspace(400.0, 1200.0, 1601)
K0 = 2.0 * np.pi / WLS
SQW = np.full(len(WLS), np.sqrt(1.0 / len(WLS)))
TGT = np.full(len(WLS), 0.5)
NSUB = np.full(len(WLS), N_SUB)
ZB, OB = np.zeros(len(WLS)), np.ones(len(WLS))
N_MAX = 40
#: v3 (2026-10-27): needle scan, thick insertions and dilation; a layer under DEAD nm is not counted as a layer.
THICKEN = os.environ.get("SEARCH_THICKEN", "1") == "1"
KEEP = int(os.environ.get("SEARCH_KEEP", "6"))  # elites kept per N (1 = a single trajectory per N)
DEAD = 1.0
TAG = "v3_" if THICKEN and KEEP == 6 else f"abl_t{int(THICKEN)}k{KEEP}_"  # v2 (first night): curve_{kind}_s1.csv
#: focus (2026-10-27): only parents with N in [lo, hi] are explored, e.g. SEARCH_FOCUS=27-36; every child is archived.
FOCUS = tuple(int(v) for v in os.environ["SEARCH_FOCUS"].split("-")) if os.environ.get("SEARCH_FOCUS") else None
if FOCUS:
    TAG = f"foc{FOCUS[0]}-{FOCUS[1]}_"
#: target (2026-10-27): SEARCH_TARGET=threeline is the three-line filter of Tikhonravov & Trubetskov, AO 51, 7319 (2012)
#: and Trubetskov, AO 59, A75 (2020), Fig. 5: T = 1 at 445-455, 505-515, 635-645 nm, T = 0 at 400-440, 460-500,
#: 520-630, 650-700 nm, 1 nm step, uniform weights (their MF in % = 100 x RMSE), same materials and substrate.
TARGET = os.environ.get("SEARCH_TARGET", "bs5050")
if TARGET == "threeline":
    _bands = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
              (650, 700, 0.0)]
    WLS = np.concatenate([np.arange(a, b + 1, dtype=float) for a, b, _t in _bands])
    TGT = np.concatenate([np.full(b - a + 1, t) for a, b, t in _bands])
    K0 = 2.0 * np.pi / WLS
    SQW = np.full(len(WLS), np.sqrt(1.0 / len(WLS)))
    NSUB = np.full(len(WLS), N_SUB)
    ZB, OB = np.zeros(len(WLS)), np.ones(len(WLS))
    N_MAX = int(os.environ.get("SEARCH_NMAX", "120"))
    TAG = "3line_" + (f"foc{FOCUS[0]}-{FOCUS[1]}_" if FOCUS else "")
#: SEARCH_TARGET=ar: the antireflection problem of Tikhonravov & Trubetskov, AO 51, 7319 (2012), Sec. 4: R = 0 at
#: 380-720 nm, 2 nm step, same materials and substrate, no absorption, so R = 1 - T and the target is T = 1.
elif TARGET == "ar":
    WLS = np.arange(380.0, 721.0, 2.0)
    TGT = np.ones(len(WLS))
    K0 = 2.0 * np.pi / WLS
    SQW = np.full(len(WLS), np.sqrt(1.0 / len(WLS)))
    NSUB = np.full(len(WLS), N_SUB)
    ZB, OB = np.zeros(len(WLS)), np.ones(len(WLS))
    N_MAX = int(os.environ.get("SEARCH_NMAX", "30"))
    TAG = "ar_"


def total_ot(seq: str, d: np.ndarray) -> float:
    return float(np.sum(d * np.array([N_IDX[m] for m in seq])))


def other(m: str) -> str:
    return "L" if m == "H" else "H"


class Stack:
    """Residuals and Jacobian of one material sequence (index 0 = substrate side)."""

    _cache: ClassVar[dict[str, Stack]] = {}

    def __init__(self, seq: str):
        n = np.array([N_IDX[m] for m in seq])
        self.seq = seq
        self.n_real = np.ascontiguousarray(np.tile(n, (len(WLS), 1)))
        self.inv_n = np.ascontiguousarray(1.0 / self.n_real)
        self.var = np.arange(len(seq), dtype=np.int64)

    @classmethod
    def of(cls, seq: str) -> Stack:
        if seq not in cls._cache:
            cls._cache[seq] = cls(seq)
        return cls._cache[seq]

    def res_jac(self, d: np.ndarray):
        return _res_jac_lossless_normal_kernel(
            np.ascontiguousarray(d, dtype=np.float64), self.n_real, self.inv_n, NSUB, K0, False, ZB, OB, TGT, SQW, self.var
        )


def mse_only(seq: str, d: np.ndarray) -> float:
    st = Stack.of(seq)
    return float(cost_lossless_front_fast(np.ascontiguousarray(d, dtype=np.float64), st.n_real, st.inv_n, NSUB, K0, TGT, OB))


def p_scan(seq: str, d: np.ndarray, step: float = 3.0, delta: float = 0.3):
    """Sampled P-function: (dMSE, sequence, thicknesses, needle index, layer) for a needle of the other material at
    every `step` nm inside every layer, in stack order."""
    base = mse_only(seq, d)
    found = []
    for i in range(len(seq)):
        s2 = seq[:i + 1] + other(seq[i]) + seq[i:]
        for z in np.arange(step / 2, d[i], step):
            d2 = np.concatenate([d[:i], [z, delta, d[i] - z], d[i + 1:]])
            found.append((mse_only(s2, d2) - base, s2, d2, i + 1))
    return [(g, s2, d2, j) for g, s2, d2, j in found]


def needle_scan(seq: str, d: np.ndarray, step: float = 3.0, delta: float = 0.3, keep: int = 4):
    """Tikhonravov's needle test: the best places to insert a thin layer of the other material (most negative dMSE)."""
    found = sorted(p_scan(seq, d, step, delta), key=lambda t: t[0])
    return [(s2, d2, j) for g, s2, d2, j in found[:keep] if g < 0.0]


def rmse(seq: str, d: np.ndarray) -> float:
    res, _j, _c = Stack.of(seq).res_jac(d)
    return float(np.sqrt(np.sum(res * res)))


def polish(seq: str, d: np.ndarray, floor: float, max_nfev: int = 400) -> tuple[np.ndarray, float]:
    st = Stack.of(seq)
    memo: dict = {}

    def both(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            r, j, _c = st.res_jac(x)
            memo[key] = (r, j)
        return memo[key]

    x0 = np.maximum(np.asarray(d, dtype=np.float64), floor)
    sol = least_squares(lambda x: both(x)[0], x0, jac=lambda x: both(x)[1], bounds=(floor, np.inf), method="trf",
                        x_scale="jac", ftol=1e-15, xtol=1e-15, gtol=1e-15, max_nfev=max_nfev)
    x = np.maximum(sol.x, floor)
    return x, rmse(seq, x)


def oracle_rmse(seq: str, d: np.ndarray) -> float:
    n = [complex(N_IDX[m], 0.0) for m in seq]
    t = np.array([oracle.rt_stack(w, n, d, complex(1.0), complex(N_SUB))[1] for w in WLS])
    return float(np.sqrt(np.mean((t - TGT) ** 2)))


def normalize(seq: str, d: np.ndarray, floor: float) -> tuple[str, np.ndarray]:
    """Drop layers under the floor and merge equal neighbours (a dead layer is not a layer)."""
    s, x = list(seq), list(np.asarray(d, dtype=np.float64))
    changed = True
    while changed:
        changed = False
        for i in range(len(s)):
            if x[i] < floor * 0.999 and len(s) > 1:
                del s[i], x[i]
                changed = True
                break
        for i in range(len(s) - 1):
            if s[i] == s[i + 1]:
                x[i] += x[i + 1]
                del s[i + 1], x[i + 1]
                changed = True
                break
    return "".join(s), np.array(x)


def load_old(kind: str) -> list[tuple[str, np.ndarray]]:
    out = []
    for n in range(1, 35):
        f = OLD / f"best_{kind}_{n}.json"
        if not f.exists():
            continue
        js = json.loads(f.read_text(encoding="utf-8"))
        seq = "".join(lay["mat"] for lay in js["front"])
        d = np.array([lay["qw"] * L0 / (4.0 * N_IDX[lay["mat"]]) for lay in js["front"]])
        out.append((seq, d))
    return out


class Archive:
    def __init__(self, floor: float, keep: int = 6):
        self.floor, self.keep = floor, keep
        self.by_n: dict[int, list[tuple[float, str, np.ndarray]]] = {}

    def add(self, seq: str, d: np.ndarray, r: float) -> bool:
        if not np.isfinite(r) or len(seq) > N_MAX or np.min(d) < self.floor * 0.999:
            return False
        lst = self.by_n.setdefault(len(seq), [])
        if any(abs(r - r2) <= 1e-9 * r2 for r2, _s, _d in lst):
            return False
        best_before = lst[0][0] if lst else np.inf
        lst.append((r, seq, d.copy()))
        lst.sort(key=lambda t: t[0])
        del lst[self.keep:]
        return r < best_before * (1 - 1e-9)

    def best(self, n: int):
        lst = self.by_n.get(n)
        return lst[0] if lst else None


def moves(seq: str, d: np.ndarray, floor: float, rng: np.random.Generator):
    n = len(seq)
    needle = max(floor, 1.0)
    for sigma in (0.03, 0.1, 0.25):
        yield seq, d * (1.0 + sigma * rng.standard_normal(n))
    for _ in range(6):
        i = int(rng.integers(n))
        f = float(rng.uniform(0.15, 0.85))
        a, b = d[i] * f, d[i] * (1 - f)
        yield seq[:i + 1] + other(seq[i]) + seq[i:], np.concatenate([d[:i], [a, needle, b], d[i + 1:]])
    yield other(seq[0]) + seq, np.concatenate([[needle], d])
    yield seq + other(seq[-1]), np.concatenate([d, [needle]])
    for i in rng.permutation(n)[: min(n, 6)]:
        yield normalize(seq[:i] + seq[i + 1:], np.delete(d, i), 0.0)
    if not THICKEN:
        return
    for i in np.argsort(d)[:3]:  # thinnest layers take the material of a neighbour: total thickness kept (AO 46, 704, §2)
        if 0 < i < n - 1:
            yield normalize(seq[:i] + seq[i - 1] + seq[i + 1:], d, 0.0)
    for s2, d2, j in needle_scan(seq, d):
        d2[j] = needle
        yield s2, d2
    for _ in range(3):  # thick layer inside a layer, or at either end: the total thickness grows
        i, t = int(rng.integers(n)), float(rng.uniform(20.0, 150.0))
        f = float(rng.uniform(0.15, 0.85))
        yield seq[:i + 1] + other(seq[i]) + seq[i:], np.concatenate([d[:i], [d[i] * f, t, d[i] * (1 - f)], d[i + 1:]])
    t = float(rng.uniform(20.0, 150.0))
    yield (other(seq[0]) + seq, np.concatenate([[t], d])) if rng.random() < 0.5 else (seq + other(seq[-1]), np.concatenate([d, [t]]))
    yield seq, d * float(rng.uniform(1.03, 1.10))


def main() -> None:
    kind, minutes = sys.argv[1], float(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    floor = 0.1 if kind == "free" else 5.0
    rng = np.random.default_rng(seed)
    arch = Archive(floor, KEEP)
    t_end = time.time() + 60.0 * minutes
    log = (HERE / f"log_{TAG}{kind}_s{seed}.txt").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    old = {}
    front: dict[int, tuple[float, str, np.ndarray]] = {}  # best design per 100 nm bin of total optical thickness

    def front_add(seq: str, d: np.ndarray, r: float) -> None:
        if len(seq) == 0 or len(seq) > N_MAX or not np.isfinite(r):
            return
        key = int(total_ot(seq, d) // 100)
        if key not in front or r < front[key][0]:
            front[key] = (r, seq, d.copy())

    if TARGET == "bs5050":
        starts = load_old(kind)
    else:  # random alternating stacks: N = 30..100, total optical thickness 5000-14000 nm
        starts = []
        for n in range(30, 101, 5):
            for _ in range(3):
                first = "HL"[int(rng.integers(2))]
                seq = "".join(first if i % 2 == 0 else other(first) for i in range(n))
                ot = rng.uniform(5000.0, 14000.0) / n * np.exp(0.4 * rng.standard_normal(n))
                starts.append((seq, ot / np.array([N_IDX[m] for m in seq])))
    for prev in sys.argv[4:]:
        with (HERE / prev).open(encoding="utf-8") as f:
            starts += [(r["seq"], np.array([float(v) for v in r["d_nm"].split()])) for r in csv.DictReader(f)]
    for seq, d in starts:
        r0 = rmse(seq, d)
        old[len(seq)] = min(r0, old.get(len(seq), np.inf))
        arch.add(seq, d, r0)
        x, r = polish(seq, d, floor)
        arch.add(seq, x, r)
        front_add(seq, x, r)
    say(f"start {kind} seed={seed}: " + " ".join(f"{n}:{arch.best(n)[0]:.4e}" for n in sorted(arch.by_n)))

    rounds = 0
    while time.time() < t_end:
        rounds += 1
        for n in sorted(arch.by_n, reverse=True):
            if time.time() >= t_end:
                break
            if FOCUS and not FOCUS[0] <= n <= FOCUS[1]:
                continue
            lst = arch.by_n.get(n, [])
            for _r0, seq, d in list(lst[:3]):
                for s2, d2 in moves(seq, d, floor, rng):
                    if len(s2) == 0 or len(s2) > N_MAX:
                        continue
                    x, r = polish(s2, d2, floor)
                    s3, x3 = normalize(s2, x, max(floor, DEAD))
                    if s3 != s2:
                        x3, r = polish(s3, x3, floor)
                    front_add(s3, x3, r)
                    if arch.add(s3, x3, r):
                        say(f"r{rounds} N={len(s3)} {r:.5e} (was {old.get(len(s3), np.nan):.5e}) {s3[0]}..{s3[-1]}")
    say(f"end after {rounds} rounds")

    rows = []
    for n in sorted(arch.by_n):
        r, seq, d = arch.best(n)
        ro = oracle_rmse(seq, d)
        rows.append({"layers": n, "rmse_1601_oracle": ro, "rmse_1601_kernel": r, "old": old.get(n, ""),
                     "first_mat": seq[0], "last_mat": seq[-1], "thinnest_nm": float(np.min(d)),
                     "total_qwot": float(np.sum(d * np.array([4 * N_IDX[m] for m in seq]) / L0)),
                     "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)})
    with (HERE / f"curve_{TAG}{kind}_s{seed}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if TARGET != "bs5050":  # MF (in %, = 100 x RMSE) against total optical thickness, oracle-judged
        frows = []
        for key in sorted(front):
            r, seq, d = front[key]
            frows.append({"total_ot_nm": total_ot(seq, d), "layers": len(seq), "mf_oracle": 100 * oracle_rmse(seq, d),
                          "mf_kernel": 100 * r, "thinnest_nm": float(np.min(d)), "seq": seq,
                          "d_nm": " ".join(f"{v:.6f}" for v in d)})
        with (HERE / f"front_{TAG}{kind}_s{seed}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(frows[0]))
            w.writeheader()
            w.writerows(frows)
    say("written")


if __name__ == "__main__":
    main()
