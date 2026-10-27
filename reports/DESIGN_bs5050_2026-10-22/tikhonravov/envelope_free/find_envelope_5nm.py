"""Compute the strict d >= 5 nm global envelope RMSE*_5nm(N) for N = 1..34 and update curve_free.csv & curve_comparison.png."""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

import tmm_reference as oracle  # noqa: E402

from certus.physics.design_fast_kernels import gauss_newton_refine_normal, prepare_normal_fast_context  # noqa: E402
from certus_physics import Material, compute_gradient_all_layers_analytic  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
CURVE_DIR = OUT_DIR.parent / "curve"
TIKH_DIR = OUT_DIR.parent

L0 = 500.0
N_H = 2.35
N_L = 1.45
N_SUB = 1.52
QWOT_NM = {"H": L0 / (4.0 * N_H), "L": L0 / (4.0 * N_L)}
FLOOR_NM = 5.001  # strict >= 5 nm rule

WLS_FAST = np.unique(
    np.concatenate(
        [
            1.0 / np.linspace(1.0 / 1200.0, 1.0 / 400.0, 110),
            np.linspace(400.0, 1200.0, 130),
        ]
    )
)
WLS_1601 = np.linspace(400.0, 1200.0, 1601)
WLS_80 = np.linspace(400.0, 1200.0, 80)

MATS = {"H": Material(N_H, N_H), "L": Material(N_L, N_L)}
SUB_FAST = np.full(len(WLS_FAST), N_SUB, dtype=np.complex128)
SUB_1601 = np.full(len(WLS_1601), N_SUB, dtype=np.complex128)
TGT_FAST = np.full(len(WLS_FAST), 0.5, dtype=np.float64)
W_FAST = np.ones(len(WLS_FAST), dtype=np.float64)
TGT_1601 = np.full(len(WLS_1601), 0.5, dtype=np.float64)
W_1601 = np.ones(len(WLS_1601), dtype=np.float64)
EMPTY_BACK_FAST = np.empty((len(WLS_FAST), 0), dtype=np.complex128)
EMPTY_BACK_1601 = np.empty((len(WLS_1601), 0), dtype=np.complex128)

_STACK_CACHE: dict[tuple[int, str], dict] = {}


def get_stack_ctx(n: int, first_mat: str) -> dict:
    key = (n, first_mat)
    if key in _STACK_CACHE:
        return _STACK_CACHE[key]
    other = "L" if first_mat == "H" else "H"
    seq = [first_mat if i % 2 == 0 else other for i in range(n)]
    n_fast = np.ascontiguousarray(np.array([MATS[m].get_nk(WLS_FAST) for m in seq]).T)
    n_1601 = np.ascontiguousarray(np.array([MATS[m].get_nk(WLS_1601) for m in seq]).T)
    qwot = np.array([QWOT_NM[m] for m in seq], dtype=np.float64)
    u_lo = FLOOR_NM / qwot
    u_hi = np.full(n, 7.0, dtype=np.float64)
    var_idx = np.arange(n, dtype=np.int64)
    fast_ctx_screen = prepare_normal_fast_context(
        wls=WLS_FAST,
        n_layers_T=n_fast,
        n_sub=SUB_FAST,
        has_back_calc=False,
        n_back_T=EMPTY_BACK_FAST,
        d_back=np.zeros(0, dtype=np.float64),
    )
    fast_ctx_1601 = prepare_normal_fast_context(
        wls=WLS_1601,
        n_layers_T=n_1601,
        n_sub=SUB_1601,
        has_back_calc=False,
        n_back_T=EMPTY_BACK_1601,
        d_back=np.zeros(0, dtype=np.float64),
    )
    ctx = {
        "n": n,
        "first": first_mat,
        "seq": seq,
        "n_fast": n_fast,
        "n_1601": n_1601,
        "fast_ctx_screen": fast_ctx_screen,
        "fast_ctx_1601": fast_ctx_1601,
        "qwot": qwot,
        "u_lo": u_lo,
        "u_hi": u_hi,
        "min_d": np.full(n, FLOOR_NM, dtype=np.float64),
        "max_d": u_hi * qwot,
        "bounds": list(zip(u_lo, u_hi, strict=True)),
        "var_idx": var_idx,
    }
    _STACK_CACHE[key] = ctx
    return ctx


def polish_u(ctx: dict, u0: np.ndarray, *, dense: bool = False, maxiter: int = 800) -> tuple[np.ndarray, float]:
    qwot = ctx["qwot"]
    var_idx = ctx["var_idx"]
    u_start = np.clip(np.asarray(u0, dtype=np.float64), ctx["u_lo"], ctx["u_hi"])
    ep_start = np.ascontiguousarray(u_start * qwot, dtype=np.float64)
    fctx = ctx["fast_ctx_1601"] if dense else ctx["fast_ctx_screen"]
    tv = TGT_1601 if dense else TGT_FAST
    tw = W_1601 if dense else W_FAST
    gn_iters = 180 if dense else 90
    ep_gn, cost_gn = gauss_newton_refine_normal(
        ep_start,
        ctx=fctx,
        tgt_vals=tv,
        tgt_weights=tw,
        var_idx=var_idx,
        lower_bounds=ctx["min_d"],
        max_iter=gn_iters,
    )
    u_opt = ep_gn / qwot
    return u_opt, float(np.sqrt(max(float(cost_gn), 0.0)))


def collapse_stack(seq: list[str], u: np.ndarray, min_nm: float = FLOOR_NM) -> tuple[list[str], np.ndarray]:
    cur_seq = list(seq)
    cur_u = np.asarray(u, dtype=np.float64).copy()
    while len(cur_seq) > 1:
        ep_nm = np.array([cur_u[i] * QWOT_NM[cur_seq[i]] for i in range(len(cur_seq))])
        thin = np.where(ep_nm < min_nm)[0]
        if len(thin) == 0:
            break
        idx = int(thin[np.argmin(ep_nm[thin])])
        del cur_seq[idx]
        cur_u = np.delete(cur_u, idx)
        m_seq: list[str] = []
        m_u: list[float] = []
        for mat, qw in zip(cur_seq, cur_u, strict=True):
            if m_seq and m_seq[-1] == mat:
                m_u[-1] += float(qw)
            else:
                m_seq.append(mat)
                m_u.append(float(qw))
        cur_seq = m_seq
        cur_u = np.array(m_u, dtype=np.float64)
    return cur_seq, cur_u


def main() -> None:
    t0 = time.time()
    rng = np.random.default_rng(20261026)
    best: dict[tuple[int, str], tuple[float, np.ndarray]] = {}

    def consider(n: int, first: str, u_cand: np.ndarray, maxiter: int = 700) -> None:
        if n < 1 or n > 34 or len(u_cand) != n:
            return
        ctx = get_stack_ctx(n, first)
        u_p, r_fast = polish_u(ctx, u_cand, dense=False, maxiter=maxiter)
        cur = best.get((n, first))
        if cur is None or r_fast < cur[0]:
            best[(n, first)] = (r_fast, u_p.copy())

    # 1. Load all existing designs (best_free_*, best_5nm_*, curve/best_*, restart_*)
    seed_files = (
        sorted(OUT_DIR.glob("best_free_*.json"))
        + sorted(OUT_DIR.glob("best_5nm_*.json"))
        + sorted(CURVE_DIR.glob("best_*.json"))
        + sorted(TIKH_DIR.glob("best_*.json"))
        + sorted(TIKH_DIR.glob("restart_*.json"))
    )
    for p in seed_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        front = data.get("front", [])
        if not front:
            continue
        seq = [r["mat"] for r in front]
        u = np.array([float(r["qw"]) for r in front], dtype=np.float64)
        if 1 <= len(seq) <= 34:
            consider(len(seq), seq[0], u, maxiter=800)
        # Also collapse any layers < 5 nm and polish the resulting smaller stack
        c_seq, c_u = collapse_stack(seq, u, min_nm=FLOOR_NM)
        if 1 <= len(c_seq) <= 34:
            consider(len(c_seq), c_seq[0], c_u, maxiter=800)

    print(f"[1/3] Seeds loaded and polished under d >= 5 nm in {time.time() - t0:.1f}s", flush=True)

    # 2. Downward (N+1 -> N, N+2 -> N) and upward (N -> N+1, N -> N+2) cascade pass
    for pass_idx in range(1):
        # Top-down pruning (deleting boundary layers or interior layers and merging neighbors)
        for n in range(34, 1, -1):
            for first in ("H", "L"):
                cur = best.get((n, first))
                if cur is None:
                    continue
                _, u = cur
                ctx = get_stack_ctx(n, first)
                seq = ctx["seq"]
                other = "L" if first == "H" else "H"
                # Remove layer 0 -> N-1 starting with other
                consider(n - 1, other, u[1:], maxiter=700)
                # Remove layer -1 -> N-1 starting with first
                consider(n - 1, first, u[:-1], maxiter=700)
                # Remove interior layer k (merging k-1 and k+1 -> N-2 starting with first)
                if n >= 3:
                    interior = list(range(1, n - 1))
                    interior_sorted = sorted(interior, key=lambda idx: u[idx] * ctx["qwot"][idx])
                    for k in interior_sorted[:6]:
                        u_m = np.empty(n - 2, dtype=np.float64)
                        u_m[: k - 1] = u[: k - 1]
                        u_m[k - 1] = u[k - 1] + u[k + 1]
                        u_m[k:] = u[k + 2 :]
                        consider(n - 2, first, u_m, maxiter=700)
                # Remove both boundary layers 0 and -1 -> N-2 starting with other
                if n >= 3:
                    consider(n - 2, other, u[1:-1], maxiter=700)

        # Bottom-up growth (prepending/appending/splitting thickest cavities)
        for n in range(1, 34):
            for first in ("H", "L"):
                cur = best.get((n, first))
                if cur is None:
                    continue
                _, u = cur
                other = "L" if first == "H" else "H"
                for q_add in (0.12, 0.85, 1.5):
                    consider(n + 1, other, np.insert(u, 0, q_add), maxiter=600)
                    consider(n + 1, first, np.append(u, q_add), maxiter=600)
                if n + 2 <= 34:
                    thickest = np.argsort(u)[::-1][:3]
                    for k in thickest:
                        u_sp = np.empty(n + 2, dtype=np.float64)
                        u_sp[:k] = u[:k]
                        u_sp[k] = 0.48 * u[k]
                        u_sp[k + 1] = 0.12
                        u_sp[k + 2] = 0.48 * u[k]
                        u_sp[k + 3 :] = u[k + 1 :]
                        consider(n + 2, first, u_sp, maxiter=600)

        # Extra basin-hopping perturbations on the N values that differed from curve_free
        for n in (6, 14, 15, 19, 21, 24, 25, 27, 28, 29, 30, 31, 33, 34):
            for first in ("H", "L"):
                cur = best.get((n, first))
                if cur is None:
                    continue
                _, u = cur
                ctx = get_stack_ctx(n, first)
                for _ in range(8):
                    u_jit = u * (1.0 + 0.06 * rng.standard_normal(n))
                    consider(n, first, u_jit, maxiter=700)
                if n >= 4:
                    for _ in range(6):
                        interior = np.arange(1, n - 1)
                        k = int(rng.choice(interior))
                        u_pms = u.copy()
                        merged = min(7.0, float(u[k - 1] + u[k + 1]))
                        if rng.random() < 0.5:
                            u_pms[2 : k + 1] = u[0 : k - 1]
                            u_pms[k + 1] = merged
                            u_pms[0] = ctx["u_lo"][0] * rng.uniform(1.0, 1.5)
                            u_pms[1] = rng.uniform(0.6, 2.2)
                        else:
                            u_pms[k - 1] = merged
                            u_pms[k : n - 2] = u[k + 2 : n]
                            u_pms[n - 2 : n] = rng.uniform(0.5, 1.8, size=2)
                        consider(n, first, u_pms, maxiter=700)

        print(f"[2/3] Cascade pass {pass_idx + 1}/3 done ({time.time() - t0:.1f}s)", flush=True)

    # 3. Final dense 1601-point polish and update curve_free.csv + curve_comparison.png
    rows_free = list(csv.DictReader((OUT_DIR / "curve_free.csv").open(encoding="utf-8")))
    results_5nm: dict[int, dict] = {}
    for n in range(1, 35):
        best_n = None
        for first in ("H", "L"):
            cur = best.get((n, first))
            if cur is None:
                continue
            ctx = get_stack_ctx(n, first)
            u_1601, r_1601 = polish_u(ctx, cur[1], dense=True, maxiter=1500)
            ep_nm = u_1601 * ctx["qwot"]
            if best_n is None or r_1601 < best_n["rmse_1601"]:
                best_n = {
                    "n": n,
                    "first": first,
                    "last": ctx["seq"][-1],
                    "seq": ctx["seq"],
                    "u": u_1601,
                    "ep_nm": ep_nm,
                    "rmse_1601": r_1601,
                    "thinnest_nm": float(np.min(ep_nm)),
                    "total_qwot": float(np.sum(u_1601)),
                }
        assert best_n is not None
        results_5nm[n] = best_n
        # Save best_5nm_N.json
        design_doc = {
            "version": "CERTUS_SUITE_26_05",
            "l0": L0,
            "materials": {
                "H": {"n4": N_H, "n7": N_H, "preset": "Custom"},
                "L": {"n4": N_L, "n7": N_L, "preset": "Custom"},
                "Substrate": {"n4": N_SUB, "n7": N_SUB, "preset": "Custom"},
            },
            "front": [{"mat": m, "qw": round(float(q), 6), "var": True} for m, q in zip(best_n["seq"], best_n["u"], strict=True)],
            "back_en": False,
            "back_coat": False,
            "back": [],
            "targets": [{"on": True, "lmin": 400.0, "lmax": 1200.0, "tmin": 0.5, "tmax": 0.5, "w": 1.0}],
            "oblique_mode": False,
            "optim": {"points_per_target": 108, "max_layers": n},
        }
        (OUT_DIR / f"best_5nm_{n}.json").write_text(json.dumps(design_doc, indent=2), encoding="utf-8")
        print(
            f"N={n:2d}: 5nm=({best_n['first']}..{best_n['last']}) {best_n['rmse_1601']:.6f} "
            f"(d_min={best_n['thinnest_nm']:.2f}nm) | free={float(rows_free[n-1]['rmse_1601']):.6f} "
            f"| old={float(rows_free[n-1]['old_curve_rmse_1601']):.6f}",
            flush=True,
        )

    # Update curve_free.csv with rmse_5nm_1601, first_mat_5nm, last_mat_5nm, thinnest_5nm_nm
    fieldnames = list(rows_free[0].keys())
    for col in ("rmse_5nm_1601", "first_mat_5nm", "last_mat_5nm", "thinnest_5nm_nm"):
        if col not in fieldnames:
            fieldnames.append(col)
    for row in rows_free:
        n = int(row["layers"])
        r5 = results_5nm[n]
        row["rmse_5nm_1601"] = repr(r5["rmse_1601"])
        row["first_mat_5nm"] = r5["first"]
        row["last_mat_5nm"] = r5["last"]
        row["thinnest_5nm_nm"] = f"{r5['thinnest_nm']:.3f}"
    with (OUT_DIR / "curve_free.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_free)

    # Update curve_comparison.png
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = np.array([int(r["layers"]) for r in rows_free])
    old_rmse = np.array([float(r["old_curve_rmse_1601"]) for r in rows_free])
    free_rmse = np.array([float(r["rmse_1601"]) for r in rows_free])
    r5_rmse = np.array([results_5nm[int(n)]["rmse_1601"] for n in ns])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8))
    ax1.semilogy(ns, old_rmse, "o--", color="#c0392b", alpha=0.8, label="Ancienne curve.csv (HL seul, défauts)")
    ax1.semilogy(ns, r5_rmse, "s-", color="#2980b9", lw=2.0, label="Enveloppe stricte d >= 5 nm (HL + LH + N+p->N)")
    ax1.semilogy(ns, free_rmse, "^-", color="#27ae60", lw=1.8, alpha=0.9, label="Enveloppe libre d >= 0.1 nm (HL + LH + N+p->N)")
    ax1.axhline(1.765e-4, color="#7f8c8d", ls=":", label="Tikhonravov 1996 (34 couches, 1.765e-4)")
    ax1.set_xlabel("Nombre de couches N")
    ax1.set_ylabel("RMSE (grille fixe 1601 points, oracle)")
    ax1.set_title("Séparatrice 50/50 (400-1200 nm) : RMSE = f(N)")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=8.5)

    gain_5nm = (old_rmse - r5_rmse) / old_rmse * 100.0
    gain_free = (old_rmse - free_rmse) / old_rmse * 100.0
    ax2.bar(ns - 0.18, gain_5nm, width=0.36, color="#2980b9", alpha=0.85, label="Gain relatif d >= 5 nm (%)")
    ax2.bar(ns + 0.18, gain_free, width=0.36, color="#27ae60", alpha=0.75, label="Gain relatif libre (%)")
    ax2.set_xlabel("Nombre de couches N")
    ax2.set_ylabel("Réduction du RMSE vs curve.csv (%)")
    ax2.set_title("Gain de convergence vers le minimum global")
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8.5)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "curve_comparison.png", dpi=160)
    print(f"[3/3] Completed in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
