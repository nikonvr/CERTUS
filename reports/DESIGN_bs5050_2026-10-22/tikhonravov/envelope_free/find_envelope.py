"""Find the global minimum RMSE*(N) for N = 1..34 on the 50/50 beam splitter of Tikhonravov et al. (1996).

    python -u reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_free/find_envelope.py

Problem: T = 0.5 over 400-1200 nm, normal incidence, front face only, n_L = 1.45, n_H = 2.35 constant,
substrate n_sub = 1.52, free thicknesses (d_i >= 0, no 5 nm floor, no total QWOT ceiling).
Searches both alternations (H on substrate and L on substrate) at every N = 1..34 using:
1. All existing optimized 50/50 splitter designs in reports/DESIGN_bs5050_2026-10-22/ and example/example_design/,
2. Multi-scale random restarts + memetic block recombination for both H-first and L-first stacks,
3. Bidirectional continuation across N:
   - Top-down (N -> N-1 by edge removal; N -> N-2 by interior removal + merge and by adjacent pair removal),
   - Bottom-up (N -> N+1 by substrate/air edge insertion; N -> N+2 by needle split and pair insertion).

Every layer of a recorded N-layer solution has physical thickness d_i >= MIN_PHYS_NM (0.1 nm) so no
zero-thickness phantom layer inflates the layer count; any solution where a layer vanishes (< 0.1 nm)
is cleaned and registered at its true physical layer count.
All final designs are polished on the 1601-point grid and verified by `tests/oracle/tmm_reference.py::rt_stack`.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPORT_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

from tmm_reference import rt_stack  # noqa: E402

from certus.core.certus_design_tolerance import rmse_band  # noqa: E402
from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic  # noqa: E402
from certus.physics.gradient_utils import cost_numba_fast  # noqa: E402

L0 = 500.0
N_VAL = {"H": 2.35, "L": 1.45}
N_SUB = 1.52
MIN_PHYS_NM = 0.1  # 1 Angstrom: prevents 0-nm phantom layers from counting as a real layer
MAX_NM = 450.0


def alternating(n: int, first: str) -> str:
    other = "L" if first == "H" else "H"
    return "".join(first if i % 2 == 0 else other for i in range(n))


def clean_stack(ep: np.ndarray, mats: str, min_nm: float = MIN_PHYS_NM) -> tuple[np.ndarray, str]:
    out_ep: list[float] = []
    out_m: list[str] = []
    for d, m in zip(ep, mats, strict=True):
        if float(d) < min_nm:
            continue
        if out_m and out_m[-1] == m:
            out_ep[-1] += float(d)
        else:
            out_ep.append(float(d))
            out_m.append(m)
    return np.asarray(out_ep, dtype=np.float64), "".join(out_m)


class TikhonravovEvaluator:
    def __init__(self, wls: np.ndarray) -> None:
        self.wls = np.ascontiguousarray(wls, dtype=np.float64)
        self.tgt = np.full(len(wls), 0.5, dtype=np.float64)
        self.w = np.ones(len(wls), dtype=np.float64)
        self.n_sub = np.full(len(wls), N_SUB + 0.0j, dtype=np.complex128)
        self.empty_c = np.zeros((len(wls), 0), dtype=np.complex128)
        self.empty_d = np.zeros(0, dtype=np.float64)
        self._cache: dict[str, np.ndarray] = {}
        self.evals = 0

    def n_T(self, mats: str) -> np.ndarray:
        if mats not in self._cache:
            arr = np.array([np.full(len(self.wls), N_VAL[m] + 0.0j, dtype=np.complex128) for m in mats])
            self._cache[mats] = np.ascontiguousarray(arr.T)
        return self._cache[mats]

    def cost(self, ep: np.ndarray, mats: str) -> float:
        self.evals += 1
        return float(
            cost_numba_fast(
                np.ascontiguousarray(ep, dtype=np.float64),
                self.n_T(mats),
                self.n_sub,
                self.wls,
                self.tgt,
                self.w,
                0.0,
                False,
                self.empty_c,
                self.empty_d,
            )
        )

    def rmse(self, ep: np.ndarray, mats: str) -> float:
        return float(np.sqrt(max(self.cost(ep, mats), 0.0)))

    def polish(
        self,
        ep0: np.ndarray,
        mats: str,
        *,
        min_nm: float = 0.0,
        maxiter: int = 800,
        ftol: float = 1e-15,
    ) -> tuple[np.ndarray, float]:
        """L-BFGS-B in optical-thickness coordinates (QWOT at 500 nm)."""
        n = len(mats)
        if n == 0:
            return np.zeros(0, dtype=np.float64), self.rmse(np.zeros(0, dtype=np.float64), "")
        n_T = self.n_T(mats)
        scale = np.array([4.0 * N_VAL[m] / L0 for m in mats], dtype=np.float64)
        inv_scale = 1.0 / scale
        bounds = [(min_nm * s, MAX_NM * s) for s in scale]
        x0 = np.clip(np.asarray(ep0, dtype=np.float64) * scale, [b[0] for b in bounds], [b[1] for b in bounds])

        def f(q: np.ndarray) -> tuple[float, np.ndarray]:
            self.evals += 1
            d = np.ascontiguousarray(q * inv_scale, dtype=np.float64)
            c, g = compute_gradient_all_layers_analytic(
                d, n_T, self.n_sub, self.wls, self.tgt, self.w, 0.0, False, self.empty_c, self.empty_d, None
            )
            return float(c), np.asarray(g, dtype=np.float64) * inv_scale

        res = minimize(
            f,
            x0,
            jac=True,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": maxiter, "ftol": ftol, "gtol": 1e-12},
        )
        ep = np.asarray(res.x, dtype=np.float64) * inv_scale
        return ep, float(np.sqrt(max(float(res.fun), 0.0)))


class SolutionPool:
    """Stores the best designs found for each (N, mats) on the fast grid, then polishes top candidates on 1601 pts."""

    def __init__(self, fast_eval: TikhonravovEvaluator, fine_eval: TikhonravovEvaluator) -> None:
        self.fast = fast_eval
        self.fine = fine_eval
        self.by_parity: dict[tuple[int, str], list[tuple[float, np.ndarray, str]]] = {}

    def consider(self, ep: np.ndarray, mats: str) -> None:
        if len(mats) == 0:
            return
        c_ep, c_mats = clean_stack(ep, mats, MIN_PHYS_NM)
        if 1 <= len(c_mats) <= 34 and len(c_mats) != len(mats):
            ep_c, _ = self.fast.polish(c_ep, c_mats, min_nm=MIN_PHYS_NM, maxiter=500)
            self._insert(ep_c, c_mats)
        if 1 <= len(mats) <= 34:
            if float(ep.min()) < MIN_PHYS_NM:
                ep_b, _ = self.fast.polish(np.maximum(ep, MIN_PHYS_NM), mats, min_nm=MIN_PHYS_NM, maxiter=500)
                self._insert(ep_b, mats)
            else:
                self._insert(ep, mats)

    def _insert(self, ep: np.ndarray, mats: str) -> None:
        n = len(mats)
        if n < 1 or n > 34:
            return
        key = (n, mats[0])
        bucket = self.by_parity.setdefault(key, [])
        r = self.fast.rmse(ep, mats)
        if len(bucket) >= 5 and r >= bucket[-1][0]:
            return
        for idx, (old_r, old_ep, _) in enumerate(bucket):
            if float(np.mean(np.abs(ep - old_ep))) < 0.2:
                if r < old_r:
                    bucket[idx] = (r, ep.copy(), mats)
                    bucket.sort(key=lambda item: item[0])
                return
        bucket.append((r, ep.copy(), mats))
        bucket.sort(key=lambda item: item[0])
        if len(bucket) > 5:
            del bucket[5:]

    def top_for_n(self, n: int, k: int = 3) -> list[tuple[float, np.ndarray, str]]:
        items = []
        for first in ("H", "L"):
            items.extend(self.by_parity.get((n, first), [])[:k])
        items.sort(key=lambda item: item[0])
        return items[:k]

    def finalize_on_fine_grid(self) -> None:
        """Polish top candidates of every (N, first_mat) on the 1601-point grid."""
        for key, bucket in list(self.by_parity.items()):
            refined: list[tuple[float, np.ndarray, str]] = []
            for _, ep, mats in bucket[:3]:
                ep_fine, _ = self.fine.polish(ep, mats, min_nm=MIN_PHYS_NM, maxiter=2000)
                r_fine = self.fine.rmse(ep_fine, mats)
                refined.append((r_fine, ep_fine, mats))
            refined.sort(key=lambda item: item[0])
            self.by_parity[key] = refined

    def best_for_n(self, n: int) -> tuple[float, np.ndarray, str] | None:
        candidates = []
        for first in ("H", "L"):
            bucket = self.by_parity.get((n, first))
            if bucket:
                candidates.append(bucket[0])
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])


def load_existing_seeds(pool: SolutionPool) -> int:
    count = 0
    paths = [
        p
        for p in REPORT_DIR.rglob("*.json")
        if p.name.startswith(("best_", "restart_")) and "envelope_free" not in str(p)
    ] + [
        ROOT / "example" / "example_design" / "JSON-design-reference-tikhonravov-1996-published-design.json",
        ROOT / "example" / "example_design" / "JSON-design-seed-A.json",
    ]
    for path in paths:
        if not path.is_file():
            continue
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            front = cfg.get("front", [])
            if not front:
                continue
            l0 = float(cfg.get("l0", 500.0))
            rows = [r for r in front if float(r.get("qw", 0.0)) > 0.0 and r.get("mat") in N_VAL]
            if not (1 <= len(rows) <= 35):
                continue
            mats = "".join(r["mat"] for r in rows)
            ep = np.array([float(r["qw"]) * l0 / (4.0 * N_VAL[r["mat"]]) for r in rows], dtype=np.float64)
            ep, mats = clean_stack(ep, mats, MIN_PHYS_NM)
            if 1 <= len(mats) <= 34:
                ep_fast, _ = pool.fast.polish(ep, mats, min_nm=0.0, maxiter=600)
                pool.consider(ep_fast, mats)
                count += 1
        except Exception:
            continue
    return count


def best_needle_insertions(
    ev: TikhonravovEvaluator, ep: np.ndarray, mats: str, top_k: int = 2
) -> list[tuple[np.ndarray, str]]:
    """Scan a 1 nm probe layer of opposite material inside every layer (every 4 nm); return top_k candidates."""
    candidates: list[tuple[float, np.ndarray, str]] = []
    probe_nm = 1.0
    step_nm = 4.0
    for j, (d, m) in enumerate(zip(ep, mats, strict=True)):
        if d <= step_nm:
            continue
        new_m = "L" if m == "H" else "H"
        cuts = np.arange(step_nm / 2.0, float(d), step_nm)
        best_layer = (np.inf, None, None)
        for z in cuts:
            trial_ep = np.array([*ep[:j], z, probe_nm, float(d) - z, *ep[j + 1 :]], dtype=np.float64)
            trial_m = mats[:j] + m + new_m + m + mats[j + 1 :]
            c = ev.cost(trial_ep, trial_m)
            if c < best_layer[0]:
                best_layer = (c, trial_ep, trial_m)
        if best_layer[1] is not None:
            candidates.append(best_layer)
    candidates.sort(key=lambda item: item[0])
    return [(ep_c, m_c) for _, ep_c, m_c in candidates[:top_k]]


def run_multistart_and_memetic(pool: SolutionPool, rng: np.random.Generator) -> None:
    """Run multistart and memetic recombination for both H-first and L-first across N = 1..34."""
    for n in range(1, 35):
        starts = 30 if n <= 10 else 24
        children = 0 if n <= 3 else 30
        for first in ("H", "L"):
            mats = alternating(n, first)
            pop: list[tuple[np.ndarray, float]] = []
            for r_known, ep_known, _ in pool.by_parity.get((n, first), []):
                pop.append((ep_known.copy(), r_known))
            for s in range(starts):
                qw_max = 1.25 if s % 3 == 0 else (2.1 if s % 3 == 1 else 3.0)
                qw = rng.uniform(0.05, qw_max, n)
                ep0 = np.array([q * L0 / (4.0 * N_VAL[m]) for q, m in zip(qw, mats, strict=True)], dtype=np.float64)
                ep_p, r_p = pool.fast.polish(ep0, mats, min_nm=0.0, maxiter=500)
                pop.append((ep_p, r_p))
            pop.sort(key=lambda item: item[1])
            pop = pop[:16]

            for _ in range(children):
                if len(pop) < 2:
                    break
                i, j = rng.choice(len(pop), 2, replace=False)
                child = pop[i][0].copy()
                lo, hi = sorted(rng.choice(np.arange(1, n), 2, replace=False)) if n > 2 else (0, 1)
                child[lo:hi] = pop[j][0][lo:hi]
                child *= 1.0 + 0.03 * rng.standard_normal(n)
                ep_c, r_c = pool.fast.polish(np.maximum(child, 0.0), mats, min_nm=0.0, maxiter=500)
                if r_c < pop[-1][1] and all(abs(r_c - m[1]) > 1e-9 for m in pop):
                    pop[-1] = (ep_c, r_c)
                    pop.sort(key=lambda item: item[1])

            for ep_cand, _ in pop[:3]:
                pool.consider(ep_cand, mats)


def cascade_top_down(pool: SolutionPool) -> None:
    """Project solutions from N down to N-1 and N-2."""
    for n in range(34, 1, -1):
        for _, ep, mats in pool.top_for_n(n, k=3):
            # 1) Remove first layer (substrate side) -> N-1
            ep_sub, m_sub = ep[1:].copy(), mats[1:]
            ep_p, _ = pool.fast.polish(ep_sub, m_sub, min_nm=0.0, maxiter=600)
            pool.consider(ep_p, m_sub)

            # 2) Remove last layer (air side) -> N-1
            ep_air, m_air = ep[:-1].copy(), mats[:-1]
            ep_p, _ = pool.fast.polish(ep_air, m_air, min_nm=0.0, maxiter=600)
            pool.consider(ep_p, m_air)

            if n >= 3:
                # 3) Screen interior removals & adjacent pair removals with short 35-iter polish, then full polish top 3
                candidates_n2: list[tuple[float, np.ndarray, str]] = []
                for j in range(1, n - 1):
                    trial = ep.copy()
                    trial[j] = 0.0
                    c_ep, c_mats = clean_stack(trial, mats, 1e-6)
                    if len(c_mats) == n - 2:
                        ep_s, r_s = pool.fast.polish(c_ep, c_mats, min_nm=0.0, maxiter=35)
                        candidates_n2.append((r_s, ep_s, c_mats))
                for j in range(n - 1):
                    trial = np.delete(ep, [j, j + 1])
                    trial_m = mats[:j] + mats[j + 2 :]
                    c_ep, c_mats = clean_stack(trial, trial_m, 1e-6)
                    if len(c_mats) >= 1:
                        ep_s, r_s = pool.fast.polish(c_ep, c_mats, min_nm=0.0, maxiter=35)
                        candidates_n2.append((r_s, ep_s, c_mats))
                candidates_n2.sort(key=lambda item: item[0])
                for _, ep_s, m_s in candidates_n2[:3]:
                    ep_p, _ = pool.fast.polish(ep_s, m_s, min_nm=0.0, maxiter=600)
                    pool.consider(ep_p, m_s)


def cascade_bottom_up(pool: SolutionPool, rng: np.random.Generator) -> None:
    """Grow solutions from N up to N+1 and N+2."""
    for n in range(1, 34):
        for _, ep, mats in pool.top_for_n(n, k=3):
            pre_m = "L" if mats[0] == "H" else "H"
            post_m = "L" if mats[-1] == "H" else "H"

            # 1) Prepend a layer on the substrate side -> N+1
            for qw0 in (0.03, 0.2, 0.7, 1.4):
                d0 = qw0 * L0 / (4.0 * N_VAL[pre_m])
                trial_ep = np.array([d0, *ep], dtype=np.float64)
                trial_m = pre_m + mats
                ep_p, _ = pool.fast.polish(trial_ep, trial_m, min_nm=MIN_PHYS_NM, maxiter=600)
                pool.consider(ep_p, trial_m)
                jittered = trial_ep * (1.0 + 0.04 * rng.standard_normal(n + 1))
                ep_j, _ = pool.fast.polish(np.maximum(jittered, MIN_PHYS_NM), trial_m, min_nm=MIN_PHYS_NM, maxiter=600)
                pool.consider(ep_j, trial_m)

            # 2) Append a layer on the air side -> N+1
            for qw_end in (0.03, 0.2, 0.6, 0.95):
                d_end = qw_end * L0 / (4.0 * N_VAL[post_m])
                trial_ep = np.array([*ep, d_end], dtype=np.float64)
                trial_m = mats + post_m
                ep_p, _ = pool.fast.polish(trial_ep, trial_m, min_nm=MIN_PHYS_NM, maxiter=600)
                pool.consider(ep_p, trial_m)

            if n <= 32:
                # 3) Best needle insertions inside existing layers -> N+2
                for ins_ep, ins_m in best_needle_insertions(pool.fast, ep, mats, top_k=2):
                    ep_p, _ = pool.fast.polish(ins_ep, ins_m, min_nm=MIN_PHYS_NM, maxiter=600)
                    pool.consider(ep_p, ins_m)

                # 4) Prepend a pair on the substrate side -> N+2
                for qw_pair in ((0.1, 0.8), (0.5, 0.7)):
                    p_pre = [
                        qw_pair[0] * L0 / (4.0 * N_VAL[mats[0]]),
                        qw_pair[1] * L0 / (4.0 * N_VAL[pre_m]),
                    ]
                    ep_p, _ = pool.fast.polish(
                        np.array([*p_pre, *ep], dtype=np.float64), mats[0] + pre_m + mats, min_nm=MIN_PHYS_NM, maxiter=600
                    )
                    pool.consider(ep_p, mats[0] + pre_m + mats)


def save_design_file(path: Path, ep: np.ndarray, mats: str, template: dict) -> None:
    out = dict(template)
    out["front"] = [
        {"mat": m, "qw": round(float(4.0 * N_VAL[m] * d / L0), 6), "var": True}
        for m, d in zip(mats, ep, strict=True)
    ]
    out["optim"] = dict(template.get("optim", {}))
    out["optim"]["max_layers"] = len(mats)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t0 = time.perf_counter()
    HERE.mkdir(parents=True, exist_ok=True)

    sigma_grid = 1.0 / np.linspace(1.0 / 1200.0, 1.0 / 400.0, 91)
    wl_grid = np.linspace(400.0, 1200.0, 91)
    wls_fast = np.unique(np.round(np.concatenate([sigma_grid, wl_grid]), 6))
    wls_fine = np.linspace(400.0, 1200.0, 1601)
    wls_art = np.linspace(400.0, 1200.0, 80)

    fast_eval = TikhonravovEvaluator(wls_fast)
    fine_eval = TikhonravovEvaluator(wls_fine)
    pool = SolutionPool(fast_eval, fine_eval)
    rng = np.random.default_rng(20261026)

    _ = fast_eval.polish(np.array([50.0, 80.0]), "HL", maxiter=5)
    _ = fine_eval.polish(np.array([50.0, 80.0]), "HL", maxiter=5)

    n_seeds = load_existing_seeds(pool)
    print(f"[{time.perf_counter() - t0:5.1f}s] Loaded and polished {n_seeds} existing designs.", flush=True)

    run_multistart_and_memetic(pool, rng)
    print(f"[{time.perf_counter() - t0:5.1f}s] Multistart + memetic stage (HL & LH) complete.", flush=True)

    for pass_idx in range(1, 3):
        cascade_top_down(pool)
        cascade_bottom_up(pool, rng)
        print(f"[{time.perf_counter() - t0:5.1f}s] Bidirectional cascade pass {pass_idx}/2 complete.", flush=True)

    pool.finalize_on_fine_grid()
    print(f"[{time.perf_counter() - t0:5.1f}s] Final 1601-point polish complete.", flush=True)

    template_path = REPORT_DIR / "tikhonravov" / "curve" / "config_34.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    prev_csv = REPORT_DIR / "tikhonravov" / "curve" / "curve.csv"
    prev_by_n: dict[int, dict] = {}
    with prev_csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            prev_by_n[int(row["start_layers"])] = row

    def mse_oracle(n_list: list[float], d_arr: np.ndarray, wls: np.ndarray) -> float:
        t = np.array([rt_stack(w, n_list, d_arr, n_sub=N_SUB)[1] for w in wls])
        return float(np.mean((t - 0.5) ** 2))

    rows = []
    for n in range(1, 35):
        best = pool.best_for_n(n)
        assert best is not None, f"No solution for N={n}"
        _, ep_raw, mats = best
        save_path = HERE / f"best_free_{n}.json"
        save_design_file(save_path, ep_raw, mats, template)

        saved = json.loads(save_path.read_text(encoding="utf-8"))
        n_list = [N_VAL[r["mat"]] for r in saved["front"]]
        d = np.array([float(r["qw"]) * L0 / (4.0 * k) for r, k in zip(saved["front"], n_list, strict=True)])
        rmse_1601 = float(np.sqrt(mse_oracle(n_list, d, wls_fine)))
        rmse_80 = float(np.sqrt(mse_oracle(n_list, d, wls_art)))
        band = rmse_band(lambda ep_draw, nl=n_list: mse_oracle(nl, ep_draw, wls_art), d, draws=200)

        r_hl = pool.by_parity.get((n, "H"), [(float("nan"), None, "")])[0][0]
        r_lh = pool.by_parity.get((n, "L"), [(float("nan"), None, "")])[0][0]
        old_rmse = float(prev_by_n[n]["rmse_1601"])
        old_layers = int(prev_by_n[n]["layers"])

        row = {
            "layers": n,
            "first_mat": mats[0],
            "last_mat": mats[-1],
            "rmse_1601": rmse_1601,
            "rmse_80": rmse_80,
            "MF_80": rmse_80 / 0.01,
            "rmse_HL_1601": float(r_hl),
            "rmse_LH_1601": float(r_lh),
            "old_curve_rmse_1601": old_rmse,
            "old_curve_kept_layers": old_layers,
            "mean_80": band.mean,
            "two_sigma_80": band.two_sigma,
            "total_qwot": round(float(sum(4.0 * k * t / L0 for k, t in zip(n_list, d, strict=True))), 4),
            "thinnest_nm": round(float(d.min()), 3),
            "design_file": save_path.name,
        }
        rows.append(row)
        print(
            f"N={n:2d} ({mats[0]}..{mats[-1]}): rmse_1601={rmse_1601:.6e} "
            f"(HL={r_hl:.6e}, LH={r_lh:.6e}) | old={old_rmse:.6e} ({old_layers}L) | "
            f"d_min={d.min():.2f}nm | QWOT={row['total_qwot']:.2f}",
            flush=True,
        )

    csv_path = HERE / "curve_free.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    ink, muted, grid, surface = "#2b2b29", "#6b6a63", "#e4e3dd", "#fcfcfb"
    blue, green, orange = "#8aa8c7", "#1b7f5a", "#eb6834"
    fig, ax = plt.subplots(figsize=(8.4, 5.0), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    x = [r["layers"] for r in rows]
    ax.plot(
        x,
        [r["old_curve_rmse_1601"] for r in rows],
        color=blue,
        lw=1.4,
        ls="--",
        marker="o",
        ms=4.5,
        label="Previous curve.csv (H-first only, 5 nm floor, 1 run/N)",
        zorder=3,
    )
    fewer = [r for r in rows if r["old_curve_kept_layers"] < r["layers"]]
    if fewer:
        ax.plot(
            [r["layers"] for r in fewer],
            [r["old_curve_rmse_1601"] for r in fewer],
            ls="none",
            marker="o",
            ms=5.0,
            mfc=surface,
            mec=blue,
            mew=1.3,
            zorder=4,
        )

    ax.plot(
        x,
        [r["rmse_1601"] for r in rows],
        color=green,
        lw=2.2,
        marker="o",
        ms=5.5,
        markeredgecolor=surface,
        markeredgewidth=1.0,
        label="Global envelope RMSE*(N) (HL & LH, d >= 0.1 nm, cascaded)",
        zorder=5,
    )
    lh_wins = [r for r in rows if r["first_mat"] == "L"]
    if lh_wins:
        ax.plot(
            [r["layers"] for r in lh_wins],
            [r["rmse_1601"] for r in lh_wins],
            ls="none",
            marker="s",
            ms=6.0,
            color="#0f52ba",
            markeredgecolor=surface,
            markeredgewidth=0.9,
            label="L on substrate wins (LH...)",
            zorder=6,
        )

    lo = [min(r["two_sigma_80"], r["mean_80"] * 0.999) for r in rows]
    ax.errorbar(
        x,
        [r["mean_80"] for r in rows],
        yerr=[lo, [r["two_sigma_80"] for r in rows]],
        fmt="_",
        ms=8,
        color=green,
        alpha=0.45,
        elinewidth=1.1,
        capsize=2.5,
        label="Envelope with thickness errors 0.1 % + 0.2 nm: mean ± 2σ",
        zorder=2,
    )
    ax.plot(
        [34],
        [1.276685e-4],
        ls="none",
        marker="D",
        ms=8,
        color=orange,
        markeredgecolor=surface,
        label="Tikhonravov et al. 1996, 34 layers (published 80-pt)",
        zorder=7,
    )
    ax.plot(
        [34],
        [1.765396e-4],
        ls="none",
        marker="D",
        ms=8,
        mfc=surface,
        mec=orange,
        mew=1.5,
        label="Same design, recomputed on 1601 points",
        zorder=7,
    )

    ax.set_yscale("log")
    ax.set_xlabel("Exact number of physical layers N", color=ink, fontsize=9)
    ax.set_ylabel("RMSE of T against 0.5, 400-1200 nm (1601 points)", color=ink, fontsize=9)
    ax.set_title(
        "50/50 splitter (Tikhonravov 1996, n 1.45 / 2.35 on glass 1.52): global envelope RMSE*(N)",
        color=ink,
        fontsize=10,
        loc="left",
    )
    ax.grid(True, which="major", color=grid, lw=0.8)
    ax.tick_params(colors=muted, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(frameon=False, fontsize=7.8, labelcolor=ink, loc="upper right")
    fig.tight_layout()
    png_path = HERE / "curve_comparison.png"
    fig.savefig(png_path, facecolor=surface)
    print(f"Done in {time.perf_counter() - t0:.1f}s. Wrote {csv_path} and {png_path}", flush=True)


if __name__ == "__main__":
    main()
