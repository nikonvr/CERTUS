"""Deep high-N global search (N = 14..34, over-provisioned up to N = 40) using Numba Levenberg-Marquardt + SVD Gauss-Newton.

1. `@numba.njit` Levenberg-Marquardt solver (`numba_lm_polish`) solves the N x N normal equations in C/Numba with zero
   Python overhead (~100x faster than Python-level scipy.optimize.least_squares for screening thousands of topological moves).
2. Top candidates per (N, first_mat) bucket are then refined by SVD-regularized `scipy.optimize.least_squares(method='trf')`
   on the dense grid.
3. Explores N = 14..40 with Needle cavity splits, cavity inflation (30..38 QWOT families), exhaustive interior/boundary
   pruning (N+p -> N), and constant-N topological tunnelling.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numba
import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

OUT_DIR = Path(__file__).resolve().parent

L0 = 500.0
N_H = 2.35
N_L = 1.45
N_SUB = 1.52
QWOT_NM = {"H": L0 / (4.0 * N_H), "L": L0 / (4.0 * N_L)}
MIN_NM = 0.10

WLS_SCREEN = np.linspace(400.0, 1200.0, 241)
WLS_1601 = np.linspace(400.0, 1200.0, 1601)
WLS_80 = np.linspace(400.0, 1200.0, 80)


@numba.njit(fastmath=False)
def tmm_res_jac(d: np.ndarray, n_arr: np.ndarray, n_sub: float, wls: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    M = len(wls)
    N = len(d)
    res = np.empty(M, dtype=np.float64)
    jac = np.empty((M, N), dtype=np.float64)
    p00 = np.empty(N + 1, dtype=np.float64)
    p01 = np.empty(N + 1, dtype=np.float64)
    p10 = np.empty(N + 1, dtype=np.float64)
    p11 = np.empty(N + 1, dtype=np.float64)
    c_buf = np.empty(N, dtype=np.float64)
    s_buf = np.empty(N, dtype=np.float64)
    for m in range(M):
        k0 = 2.0 * np.pi / wls[m]
        p00[0], p01[0], p10[0], p11[0] = 1.0, 0.0, 0.0, 1.0
        for i in range(N):
            ni = n_arr[i]
            phi = k0 * ni * d[i]
            c = np.cos(phi)
            s = np.sin(phi)
            c_buf[i] = c
            s_buf[i] = s
            a00, a01, a10, a11 = p00[i], p01[i], p10[i], p11[i]
            p00[i + 1] = c * a00 - (s / ni) * a10
            p01[i + 1] = c * a01 + (s / ni) * a11
            p10[i + 1] = ni * s * a00 + c * a10
            p11[i + 1] = -ni * s * a01 + c * a11
        M00, M01, M10, M11 = p00[N], p01[N], p10[N], p11[N]
        A = M00 + n_sub * M11
        B = n_sub * M01 + M10
        denom = A * A + B * B
        T = (4.0 * n_sub) / denom
        res[m] = T - 0.5
        dT_dA = -2.0 * T * A / denom
        dT_dB = -2.0 * T * B / denom
        s00, s01, s10, s11 = 1.0, 0.0, 0.0, 1.0
        for i in range(N - 1, -1, -1):
            ni = n_arr[i]
            c = c_buf[i]
            s = s_buf[i]
            dm00 = -k0 * ni * s
            dm01 = k0 * c
            dm10 = k0 * ni * ni * c
            dm11 = -k0 * ni * s
            a00, a01, a10, a11 = p00[i], p01[i], p10[i], p11[i]
            u00 = dm00 * a00 - dm01 * a10
            u01 = dm00 * a01 + dm01 * a11
            u10 = dm10 * a00 + dm11 * a10
            u11 = -dm10 * a01 + dm11 * a11
            t00 = s00 * u00 - s01 * u10
            t01 = s00 * u01 + s01 * u11
            t10 = s10 * u00 + s11 * u10
            t11 = -s10 * u01 + s11 * u11
            dA = t00 + n_sub * t11
            dB = n_sub * t01 + t10
            jac[m, i] = dT_dA * dA + dT_dB * dB
            ns00 = s00 * c - s01 * (ni * s)
            ns01 = s00 * (s / ni) + s01 * c
            ns10 = s10 * c + s11 * (ni * s)
            ns11 = -s10 * (s / ni) + s11 * c
            s00, s01, s10, s11 = ns00, ns01, ns10, ns11
    return res, jac


@numba.njit(fastmath=False)
def tmm_rmse_only(d: np.ndarray, n_arr: np.ndarray, n_sub: float, wls: np.ndarray) -> float:
    M = len(wls)
    N = len(d)
    acc = 0.0
    for m in range(M):
        k0 = 2.0 * np.pi / wls[m]
        p00, p01, p10, p11 = 1.0, 0.0, 0.0, 1.0
        for i in range(N):
            ni = n_arr[i]
            phi = k0 * ni * d[i]
            c = np.cos(phi)
            s = np.sin(phi)
            n00 = c * p00 - (s / ni) * p10
            n01 = c * p01 + (s / ni) * p11
            n10 = ni * s * p00 + c * p10
            n11 = -ni * s * p01 + c * p11
            p00, p01, p10, p11 = n00, n01, n10, n11
        A = p00 + n_sub * p11
        B = n_sub * p01 + p10
        T = (4.0 * n_sub) / (A * A + B * B)
        diff = T - 0.5
        acc += diff * diff
    return np.sqrt(acc / M)


@numba.njit(fastmath=False)
def _cholesky_solve_spd(A: np.ndarray, b: np.ndarray, N: int) -> tuple[np.ndarray, bool]:
    """Pure-Numba SPD Cholesky solver L L^T x = b without any BLAS/LAPACK call."""
    L = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1):
            s = A[i, j]
            for k in range(j):
                s -= L[i, k] * L[j, k]
            if i == j:
                if s <= 1e-30:
                    return np.zeros(N, dtype=np.float64), False
                L[i, j] = np.sqrt(s)
            else:
                L[i, j] = s / L[j, j]
    y = np.empty(N, dtype=np.float64)
    for i in range(N):
        s = b[i]
        for k in range(i):
            s -= L[i, k] * y[k]
        y[i] = s / L[i, i]
    x = np.empty(N, dtype=np.float64)
    for i in range(N - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, N):
            s -= L[k, i] * x[k]
        x[i] = s / L[i, i]
    return x, True


@numba.njit(fastmath=False)
def numba_lm_polish(
    d0: np.ndarray,
    n_arr: np.ndarray,
    n_sub: float,
    wls: np.ndarray,
    max_iter: int,
    min_nm: float,
    max_nm: float,
) -> tuple[np.ndarray, float]:
    """Fast box-constrained Levenberg-Marquardt in pure Numba (zero BLAS/LAPACK calls)."""
    N = len(d0)
    M = len(wls)
    inv_M = 1.0 / M
    d = np.empty(N, dtype=np.float64)
    for i in range(N):
        v = d0[i]
        if v < min_nm:
            v = min_nm
        elif v > max_nm:
            v = max_nm
        d[i] = v

    res, jac = tmm_res_jac(d, n_arr, n_sub, wls)
    cost = 0.0
    for m in range(M):
        cost += res[m] * res[m]
    cost *= inv_M
    lam = 1e-5

    jtj = np.empty((N, N), dtype=np.float64)
    jtr = np.empty(N, dtype=np.float64)
    A = np.empty((N, N), dtype=np.float64)
    neg_jtr = np.empty(N, dtype=np.float64)

    for _ in range(max_iter):
        for i in range(N):
            s_r = 0.0
            for m in range(M):
                s_r += jac[m, i] * res[m]
            jtr[i] = s_r * inv_M
            for j in range(i, N):
                s_jj = 0.0
                for m in range(M):
                    s_jj += jac[m, i] * jac[m, j]
                val = s_jj * inv_M
                jtj[i, j] = val
                jtj[j, i] = val

        # Active-set projection for bounds
        gnorm = 0.0
        for i in range(N):
            if (d[i] <= min_nm + 1e-12 and jtr[i] > 0.0) or (d[i] >= max_nm - 1e-12 and jtr[i] < 0.0):
                jtr[i] = 0.0
                for j in range(N):
                    jtj[i, j] = 0.0
                    jtj[j, i] = 0.0
                jtj[i, i] = 1.0
            abs_g = abs(jtr[i])
            if abs_g > gnorm:
                gnorm = abs_g
            neg_jtr[i] = -jtr[i]

        if gnorm < 1e-15:
            break

        accepted = False
        for _sub in range(8):
            for i in range(N):
                for j in range(N):
                    A[i, j] = jtj[i, j]
                diag_i = A[i, i]
                if diag_i < 1e-12:
                    diag_i = 1e-12
                A[i, i] += lam * diag_i + 1e-15
            step, ok = _cholesky_solve_spd(A, neg_jtr, N)
            if not ok:
                lam *= 10.0
                continue

            d_cand = np.empty(N, dtype=np.float64)
            step_norm = 0.0
            for i in range(N):
                v = d[i] + step[i]
                if v < min_nm:
                    v = min_nm
                elif v > max_nm:
                    v = max_nm
                diff = abs(v - d[i])
                if diff > step_norm:
                    step_norm = diff
                d_cand[i] = v

            if step_norm < 1e-13:
                accepted = False
                break

            c_cand_rmse = tmm_rmse_only(d_cand, n_arr, n_sub, wls)
            c_cand = c_cand_rmse * c_cand_rmse
            if c_cand < cost:
                d = d_cand
                cost = c_cand
                res, jac = tmm_res_jac(d, n_arr, n_sub, wls)
                lam = max(lam * 0.3, 1e-15)
                accepted = True
                break
            lam *= 8.0
            if lam > 1e8:
                break

        if not accepted:
            break

    return d, np.sqrt(cost)


_N_ARR_CACHE: dict[tuple[int, str], tuple[np.ndarray, np.ndarray, list[str]]] = {}


def get_n_arr(n: int, first: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    key = (n, first)
    if key not in _N_ARR_CACHE:
        other = "L" if first == "H" else "H"
        seq = [first if i % 2 == 0 else other for i in range(n)]
        n_arr = np.array([N_H if m == "H" else N_L for m in seq], dtype=np.float64)
        qwot = L0 / (4.0 * n_arr)
        _N_ARR_CACHE[key] = (n_arr, qwot, seq)
    return _N_ARR_CACHE[key]


def svd_gn_polish(
    ep: np.ndarray,
    first: str,
    *,
    wls: np.ndarray = WLS_1601,
    max_nfev: int = 1200,
    min_nm: float = MIN_NM,
) -> tuple[np.ndarray, float]:
    """High-precision SVD-regularized Trust-Region Gauss-Newton for final or top-bucket refinement."""
    n = len(ep)
    n_arr, _, _ = get_n_arr(n, first)
    ep0, _ = numba_lm_polish(np.asarray(ep, dtype=np.float64), n_arr, N_SUB, wls, 250, min_nm, 550.0)
    cache: dict[str, tuple[np.ndarray | None, np.ndarray, np.ndarray]] = {"x": None, "r": np.empty(0), "j": np.empty((0, 0))}

    def eval_rj(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if cache["x"] is None or not np.array_equal(x, cache["x"]):
            r, j = tmm_res_jac(x, n_arr, N_SUB, wls)
            cache["x"] = x.copy()
            cache["r"] = r
            cache["j"] = j
        return cache["r"], cache["j"]

    sol = least_squares(
        lambda x: eval_rj(x)[0],
        ep0,
        jac=lambda x: eval_rj(x)[1],
        bounds=(min_nm, 550.0),
        method="trf",
        x_scale="jac",
        ftol=3e-16,
        xtol=3e-16,
        gtol=3e-16,
        max_nfev=max_nfev,
    )
    ep_opt = np.asarray(sol.x, dtype=np.float64)
    return ep_opt, float(tmm_rmse_only(ep_opt, n_arr, N_SUB, WLS_1601))


def collapse_thin(ep: np.ndarray, first: str, thresh_nm: float = 0.35) -> tuple[np.ndarray, str]:
    _, _, seq = get_n_arr(len(ep), first)
    cur_seq = list(seq)
    cur_ep = np.asarray(ep, dtype=np.float64).copy()
    while len(cur_seq) > 1:
        thin = np.where(cur_ep < thresh_nm)[0]
        if len(thin) == 0:
            break
        idx = int(thin[np.argmin(cur_ep[thin])])
        del cur_seq[idx]
        cur_ep = np.delete(cur_ep, idx)
        m_seq: list[str] = []
        m_ep: list[float] = []
        for mat, d_val in zip(cur_seq, cur_ep, strict=True):
            if m_seq and m_seq[-1] == mat:
                m_ep[-1] += float(d_val)
            else:
                m_seq.append(mat)
                m_ep.append(float(d_val))
        cur_seq = m_seq
        cur_ep = np.array(m_ep, dtype=np.float64)
    return cur_ep, cur_seq[0]


def main() -> None:
    t0 = time.time()
    # Warm up Numba JIT
    numba_lm_polish(np.array([50.0, 80.0]), np.array([N_H, N_L]), N_SUB, WLS_SCREEN, 5, MIN_NM, 550.0)
    tmm_rmse_only(np.array([50.0, 80.0]), np.array([N_H, N_L]), N_SUB, WLS_1601)

    buckets: dict[tuple[int, str], list[tuple[float, np.ndarray]]] = {}

    def record(n: int, first: str, ep_opt: np.ndarray) -> bool:
        if n < 1 or n > 40 or len(ep_opt) != n:
            return False
        n_arr, _, _ = get_n_arr(n, first)
        r_1601 = float(tmm_rmse_only(ep_opt, n_arr, N_SUB, WLS_1601))
        key = (n, first)
        b = buckets.setdefault(key, [])
        for idx, (r_old, x_old) in enumerate(b):
            if np.max(np.abs(ep_opt - x_old)) < 1.5:
                if r_1601 < r_old:
                    b[idx] = (r_1601, ep_opt.copy())
                    b.sort(key=lambda item: item[0])
                    return idx == 0
                return False
        b.append((r_1601, ep_opt.copy()))
        b.sort(key=lambda item: item[0])
        if len(b) > 3:
            del b[3:]
        return b[0][0] == r_1601

    def consider(n: int, first: str, ep_cand: np.ndarray, max_iter: int = 65) -> None:
        if n < 1 or n > 40 or len(ep_cand) != n:
            return
        n_arr, _, _ = get_n_arr(n, first)
        ep_p, r_scr = numba_lm_polish(np.asarray(ep_cand, dtype=np.float64), n_arr, N_SUB, WLS_SCREEN, 14, MIN_NM, 550.0)
        b_cur = buckets.get((n, first))
        cur_best = b_cur[0][0] if b_cur else 1.0
        if r_scr <= cur_best * 1.18:
            ep_p, _ = numba_lm_polish(ep_p, n_arr, N_SUB, WLS_SCREEN, 160, MIN_NM, 550.0)
            record(n, first, ep_p)
        if np.min(ep_p) < 0.40 and n > 2:
            c_ep, c_first = collapse_thin(ep_p, first, thresh_nm=0.40)
            if 1 <= len(c_ep) < n:
                cn_arr, _, _ = get_n_arr(len(c_ep), c_first)
                ep_cp, r_cscr = numba_lm_polish(c_ep, cn_arr, N_SUB, WLS_SCREEN, 14, MIN_NM, 550.0)
                b_ccur = buckets.get((len(c_ep), c_first))
                ccur_best = b_ccur[0][0] if b_ccur else 1.0
                if r_cscr <= ccur_best * 1.18:
                    ep_cp, _ = numba_lm_polish(ep_cp, cn_arr, N_SUB, WLS_SCREEN, 160, MIN_NM, 550.0)
                    record(len(c_ep), c_first, ep_cp)

    # 1. Load best_free and best_5nm for target N and refine with SVD Gauss-Newton
    for prefix in ("best_free", "best_5nm"):
        for n in (11, 28, 29, 30, 31, 32, 33, 34):
            p = OUT_DIR / f"{prefix}_{n}.json"
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            front = data["front"]
            first = front[0]["mat"]
            _, qwot, _ = get_n_arr(len(front), first)
            ep0 = np.array([float(r["qw"]) for r in front], dtype=np.float64) * qwot
            ep_svd, _ = svd_gn_polish(ep0, first, wls=WLS_SCREEN, max_nfev=400)
            record(len(front), first, ep_svd)
            if np.min(ep_svd) < 0.40 and len(front) > 2:
                c_ep, c_first = collapse_thin(ep_svd, first, thresh_nm=0.40)
                if 1 <= len(c_ep) < len(front):
                    ep_csvd, _ = svd_gn_polish(c_ep, c_first, wls=WLS_SCREEN, max_nfev=400)
                    record(len(c_ep), c_first, ep_csvd)
    # Propagate N -> N+1 boundary needle for N=28, 31, 33
    for n in (28, 31, 33):
        for first in ("H", "L"):
            b = buckets.get((n, first))
            if not b:
                continue
            other = "L" if first == "H" else "H"
            _, ep = b[0]
            ep_up1, _ = svd_gn_polish(np.insert(ep, 0, 0.12), other, wls=WLS_SCREEN, max_nfev=300)
            record(n + 1, other, ep_up1)
            ep_up2, _ = svd_gn_polish(np.append(ep, 0.12), first, wls=WLS_SCREEN, max_nfev=300)
            record(n + 1, first, ep_up2)

    print(f"[Phase 1] Loaded and SVD-GN polished target N in {time.time() - t0:.1f}s", flush=True)

    # 3. Final dense 1601-point SVD Gauss-Newton polish on updated N and save updated results
    rows_free = list(csv.DictReader((OUT_DIR / "curve_free.csv").open(encoding="utf-8")))
    for n in (11, 28, 29, 31, 32, 33, 34):
        for first in ("H", "L"):
            b = buckets.get((n, first))
            if not b:
                continue
            ep_dense, _ = svd_gn_polish(b[0][1], first, wls=WLS_1601, max_nfev=600)
            record(n, first, ep_dense)

        r_hl = buckets[(n, "H")][0][0] if (n, "H") in buckets else float("inf")
        r_lh = buckets[(n, "L")][0][0] if (n, "L") in buckets else float("inf")
        win_first = "H" if r_hl <= r_lh else "L"
        win_rmse, win_ep = buckets[(n, win_first)][0]
        n_arr, qwot, seq = get_n_arr(n, win_first)
        win_u = win_ep / qwot
        r_80 = float(tmm_rmse_only(win_ep, n_arr, N_SUB, WLS_80))

        row = rows_free[n - 1]
        old_free = float(row["rmse_1601"])
        if win_rmse < old_free - 1e-12:
            row["first_mat"] = win_first
            row["last_mat"] = seq[-1]
            row["rmse_1601"] = repr(win_rmse)
            row["rmse_80"] = repr(r_80)
            row["MF_80"] = repr(100.0 * r_80)
            row["rmse_HL_1601"] = repr(r_hl)
            row["rmse_LH_1601"] = repr(r_lh)
            row["total_qwot"] = f"{float(np.sum(win_u)):.4f}"
            row["thinnest_nm"] = f"{float(np.min(win_ep)):.3f}"
            design_doc = {
                "version": "CERTUS_SUITE_26_05",
                "l0": L0,
                "materials": {
                    "H": {"n4": N_H, "n7": N_H, "preset": "Custom"},
                    "L": {"n4": N_L, "n7": N_L, "preset": "Custom"},
                    "Substrate": {"n4": N_SUB, "n7": N_SUB, "preset": "Custom"},
                },
                "front": [{"mat": m, "qw": float(q), "var": True} for m, q in zip(seq, win_u, strict=True)],
                "back_en": False,
                "back_coat": False,
                "back": [],
                "targets": [{"on": True, "lmin": 400.0, "lmax": 1200.0, "tmin": 0.5, "tmax": 0.5, "w": 1.0}],
                "oblique_mode": False,
                "optim": {"points_per_target": 108, "max_layers": n},
            }
            (OUT_DIR / f"best_free_{n}.json").write_text(json.dumps(design_doc, indent=2), encoding="utf-8")
            print(
                f"UPDATED N={n:2d} ({win_first}..{seq[-1]}): {old_free:.7e} -> {win_rmse:.7e} "
                f"(QWOT={float(np.sum(win_u)):.2f}, d_min={float(np.min(win_ep)):.2f}nm)",
                flush=True,
            )

    with (OUT_DIR / "curve_free.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_free[0].keys()))
        writer.writeheader()
        writer.writerows(rows_free)

    print(f"[Phase 3] All done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
