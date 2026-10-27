"""Robustness phase 1: distinct N-layer designs of the free 50/50 problem, nominal and robust, and their sensitivity.

N: env CAT_N (default 20). File prefix: env CAT_PREFIX (default catalog{N}; a smoke test uses another prefix).
Random starts have a total thickness of 0.85 N to 1.3 N QWOT (17-26 at N = 20).

build MINUTES SEED [CURVE.csv ...]   -> {prefix}.csv, nominal local minima
    Starts: the N-layer designs of the given curves, then alternately (a) a random alternating stack with a random total
    thickness of 24-36 QWOT, (b) a catalogue member among the 20 best, perturbed by d * (1 + s z), s in {0.05, 0.15, 0.3}.
    Each start is polished (`search.polish`, floor 0.1 nm); kept only if it still has N layers of at least 1 nm and is not
    a duplicate (same sequence, max |dd| < 0.05 nm).
smooth MINUTES SEED                  -> {prefix}_smooth.csv, minima of the smoothed (robust) cost
    Direct search on E[MSE(d + e)], random optical-thickness errors n_i e_i ~ N(0, s^2): sample average over K fixed
    draws (common random numbers, the same for every design), minimised by trf on the stacked residuals with the exact
    Jacobian, floor 1 nm. Continuation s = 2 -> 1 -> 0.5 nm of optical thickness (the large-s cost is a Gaussian
    smoothing of the MSE, with fewer local minima).
    Starts alternate between random stacks and the 20 best nominal minima of {prefix}.csv.
analyse                              -> {prefix}_analysis.csv, {prefix}_mc.txt, {prefix}_mc.csv, two figures
    Every design: spectrum of J^T J and the second-order prediction sqrt(MSE + sum sigma^2 |J v|^2) for random,
    independent errors on the optical thickness n d of each layer: OT 0.2 / 0.5 / 1 nm and OT 1 % (`models`).
    Thin layers are judged by their optical thickness.
    Monte Carlo (fixed seeds, kernel; first 3 draws of each design and model checked with the oracle) on the 15 best
    nominal, the 15 best predicted under OT 0.5 nm and the 15 best smoothed designs:
      sqrt(E[MSE]) plain and with the quadratic model as control variate (its expectation is exact);
      CVaR95 of the per-draw RMSE; yield P(max |T - 0.5| < SPEC); bPOE of max |T - 0.5| at SPEC (inverse CVaR);
      bootstrap 90 % intervals for all of them;
      active subspace under OT 0.5 nm: eigenvalues of C = E[grad f grad f^T], f = MSE(d + e), with bootstrap, and the
      angle between its first eigenvector and that of J^T J at the nominal point.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

import numpy as np
import search as s
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
N, FLOOR, DEAD = int(os.environ.get("CAT_N", "20")), 0.1, 1.0  # number of layers studied (env CAT_N)
PREFIX = os.environ.get("CAT_PREFIX", f"catalog{N}")
TOT_RANGE = (0.85 * N, 1.3 * N)  # QWOT of the random starts: 17-26 at N = 20
if os.environ.get("CAT_TOT"):  # e.g. CAT_TOT=3,12 (QWOT), for targets other than the 50/50
    TOT_RANGE = tuple(float(v) for v in os.environ["CAT_TOT"].split(","))
CAT, SMOOTH = HERE / f"{PREFIX}.csv", HERE / f"{PREFIX}_smooth.csv"
FIELDS = ["origin", "rmse", "saa", "total_qwot", "thinnest_nm", "seq", "d_nm"]
NW = len(s.WLS)
MC_DRAWS, MC_CHECK, SPEC, BOOT = int(os.environ.get("CAT_DRAWS", "400")), 3, 0.01, 1000
K_SMOOTH, SIGMAS, SEED_DRAWS = 32, (2.0, 1.0, 0.5), 20261027


def qwot(seq: str, d: np.ndarray) -> float:
    return float(np.sum(d * np.array([4 * s.N_IDX[m] for m in seq]) / s.L0))


def read_catalog(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["rmse"] = float(r["rmse"])
        r["d"] = np.array([float(v) for v in r["d_nm"].split()])
    return rows


class Writer:
    def __init__(self, path: Path):
        self.cat = read_catalog(path)
        new = not path.exists()
        self.f = path.open("a", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=FIELDS)
        if new:
            self.w.writeheader()

    def add(self, origin: str, seq: str, d: np.ndarray, r: float, saa: float | str = "") -> bool:
        if any(c["seq"] == seq and np.max(np.abs(c["d"] - d)) < 0.05 for c in self.cat):
            return False
        row = {"origin": origin, "rmse": r, "saa": saa, "total_qwot": qwot(seq, d), "thinnest_nm": float(np.min(d)),
               "seq": seq, "d_nm": " ".join(f"{v:.6f}" for v in d)}
        self.w.writerow(row)
        self.f.flush()
        self.cat.append({**row, "d": d})
        return True


def random_stack(rng: np.random.Generator) -> tuple[str, np.ndarray]:
    first = "HL"[int(rng.integers(2))]
    seq = "".join(first if i % 2 == 0 else s.other(first) for i in range(N))
    q = rng.uniform(0.1, 2.0, N)
    q *= rng.uniform(*TOT_RANGE) / q.sum()
    return seq, q * s.L0 / (4.0 * np.array([s.N_IDX[m] for m in seq]))


def build(minutes: float, seed: int, curves: list[str]) -> None:
    rng = np.random.default_rng(seed)
    out = Writer(CAT)
    stats = {"tried": 0, "kept": 0, "lost_layer": 0, "duplicate": 0}

    def try_start(seq: str, d: np.ndarray, origin: str) -> None:
        stats["tried"] += 1
        x, r = s.polish(seq, d, FLOOR)
        s2, x2 = s.normalize(seq, x, DEAD)
        if len(s2) != N:
            stats["lost_layer"] += 1
            return
        if s2 != seq:
            x2, r = s.polish(s2, x2, FLOOR)
            if np.min(x2) < DEAD:
                stats["lost_layer"] += 1
                return
        stats["kept" if out.add(origin, s2, x2, r) else "duplicate"] += 1

    for c in curves:
        for r in csv.DictReader((HERE / c).open(encoding="utf-8")):
            if int(r["layers"]) == N:
                try_start(r["seq"], np.array([float(v) for v in r["d_nm"].split()]), f"curve:{c}")
    t_start = time.time()
    t_end, k = t_start + 60.0 * minutes, 0
    while time.time() < t_end:
        k += 1
        if k % 2 or len(out.cat) < 5:
            try_start(*random_stack(rng), "random")
        else:
            top = sorted(out.cat, key=lambda c: c["rmse"])[:20]
            c = top[int(rng.integers(len(top)))]
            sig = (0.05, 0.15, 0.3)[int(rng.integers(3))]
            try_start(c["seq"], c["d"] * (1.0 + sig * rng.standard_normal(N)), f"hop{sig}")
        if k % 50 == 0:
            print(f"{k} starts ({(time.time() - t_start) / k:.2f} s each) {stats} catalogue {len(out.cat)}"
                  f" best {min(c['rmse'] for c in out.cat):.4e}", flush=True)
    print(f"end: {stats} catalogue {len(out.cat)}", flush=True)


def saa_fit(seq: str, d: np.ndarray, sigma: float, z: np.ndarray, max_nfev: int = 200) -> tuple[np.ndarray, float]:
    """Minimise mean_k MSE(d + sigma z_k / n) (OT error sigma; thicknesses clipped at 0) by trf on stacked residuals."""
    st, k = s.Stack.of(seq), len(z)
    z = z / np.array([s.N_IDX[m] for m in seq])

    def both(x):
        rs, js = [], []
        for zk in z:
            dk = np.maximum(x + sigma * zk, 0.0)
            r, j, _c = st.res_jac(dk)
            rs.append(r)
            js.append(j * (dk > 0.0))
        return np.concatenate(rs) / np.sqrt(k), np.vstack(js) / np.sqrt(k)

    memo: dict = {}

    def get(x):
        key = x.tobytes()
        if key not in memo:
            memo.clear()
            memo[key] = both(x)
        return memo[key]

    sol = least_squares(lambda x: get(x)[0], np.maximum(d, DEAD), jac=lambda x: get(x)[1], bounds=(DEAD, np.inf),
                        method="trf", x_scale="jac", ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=max_nfev)
    x = np.maximum(sol.x, DEAD)
    r, _j = get(x)
    return x, float(np.sqrt(np.sum(r * r)))


def smooth(minutes: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    z = np.array([np.random.default_rng((SEED_DRAWS, 0, k)).standard_normal(N) for k in range(K_SMOOTH)])
    nominal = sorted(read_catalog(CAT), key=lambda c: c["rmse"])[:20]
    out = Writer(SMOOTH)
    t_end, k, kept = time.time() + 60.0 * minutes, 0, 0
    while time.time() < t_end:
        k += 1
        if k % 2 and nominal:
            c = nominal[(k // 2) % len(nominal)]
            seq, d, origin = c["seq"], c["d"], "smooth<-nominal"
        else:
            (seq, d), origin = random_stack(rng), "smooth<-random"
        t0 = time.time()
        for sig in SIGMAS:
            d, saa = saa_fit(seq, d, sig, z)
        r = s.rmse(seq, d)
        kept += out.add(origin, seq, d, r, saa)
        best = min(float(c["saa"]) for c in out.cat) if out.cat else np.nan
        print(f"{k} {origin} {time.time() - t0:.1f} s: nominal {r:.3e} SAA {saa:.3e}; kept {kept}, best SAA {best:.4e}",
              flush=True)
    print(f"end: {k} starts, kept {kept}", flush=True)


def models(seq: str, d: np.ndarray) -> dict[str, np.ndarray]:
    """Random, independent errors on the optical thickness n d of each layer, as physical-thickness directions with unit
    sigma: e = z @ v, z ~ N(0, I). OT x nm: sigma(n d) = x nm; OT 1%: sigma(n d) = 1 % of n d."""
    inv_n = 1.0 / np.array([s.N_IDX[m] for m in seq])
    return {"OT 0.2nm": np.diag(0.2 * inv_n), "OT 0.5nm": np.diag(0.5 * inv_n), "OT 1nm": np.diag(1.0 * inv_n),
            "OT 1%": 0.01 * np.diag(d)}


def cvar(x: np.ndarray, a: float = 0.95) -> float:
    xs = np.sort(x)[::-1]
    return float(np.mean(xs[:max(1, round((1 - a) * len(xs)))]))


def bpoe(x: np.ndarray, t: float) -> float:
    """Buffered probability that x exceeds t: the largest j/n whose top-j mean is still >= t (0 if max x < t)."""
    xs = np.sort(x)[::-1]
    m = np.cumsum(xs) / np.arange(1, len(xs) + 1)
    ok = np.nonzero(m >= t)[0]
    return float((ok[-1] + 1) / len(xs)) if len(ok) else 0.0


def cv_estimate(mse: np.ndarray, quad: np.ndarray, eq: float) -> float:
    """sqrt(E[MSE]) with the quadratic model as control variate: mean(MSE - quad) + E[quad] (E[quad] exact)."""
    return float(np.sqrt(max(np.mean(mse - quad) + eq, 0.0)))


def quad_expectation(r0: np.ndarray, j0: np.ndarray, v: np.ndarray) -> float:
    """E |r0 + j0 (z @ v)|^2 for z ~ N(0, I): |r0|^2 + |j0 v^T|_F^2."""
    return float(np.sum(r0 * r0)) + float(np.sum((j0 @ v.T) ** 2))


def pareto(points: list[tuple[float, float]]) -> list[int]:
    """Indices of the non-dominated points (both coordinates minimised)."""
    order = sorted(range(len(points)), key=lambda i: points[i])
    front, best_y = [], np.inf
    for i in order:
        if points[i][1] < best_y:
            front.append(i)
            best_y = points[i][1]
    return front


def layer_field(seq: str, d: np.ndarray) -> np.ndarray:
    """Mean over wavelengths of |E|^2 in each layer (average of its two interfaces), normalised to the transmitted
    field; characteristic matrices (Macleod, chap. 2), layer 0 on the substrate side. Used only to test H3."""
    n = np.array([s.N_IDX[m] for m in seq])
    b, c = np.ones(len(s.WLS), complex), np.full(len(s.WLS), s.N_SUB, complex)
    e2 = [np.abs(b) ** 2]
    for j in range(len(seq)):
        ph = s.K0 * n[j] * d[j]
        b, c = np.cos(ph) * b + 1j * np.sin(ph) / n[j] * c, 1j * n[j] * np.sin(ph) * b + np.cos(ph) * c
        e2.append(np.abs(b) ** 2)
    e2 = np.array(e2)
    return 0.5 * (e2[:-1] + e2[1:]).mean(axis=1)


def partial_rank_corr(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Correlation of the ranks a and b after removing their linear dependence on the ranks c."""
    def resid(u):
        coef = np.polyfit(c, u, 1)
        return u - np.polyval(coef, c)
    ra, rb = resid(np.asarray(a, float)), resid(np.asarray(b, float))
    return float(ra @ rb / np.sqrt((ra @ ra) * (rb @ rb)))


def cv_r2(x: np.ndarray, y: np.ndarray, folds: int = 5, seed: int = 0) -> float:
    """Out-of-fold R^2 of an ordinary least-squares fit y ~ x (with intercept)."""
    idx = np.random.default_rng(seed).permutation(len(y))
    pred = np.empty(len(y))
    for f in range(folds):
        test = idx[f::folds]
        train = np.setdiff1d(idx, test)
        a = np.column_stack([np.ones(len(train)), x[train]])
        coef = np.linalg.lstsq(a, y[train], rcond=None)[0]
        pred[test] = np.column_stack([np.ones(len(test)), x[test]]) @ coef
    return float(1.0 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))


def boot(fn, *arrays, b: int = BOOT, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(arrays[0])
    vals = [fn(*(a[idx] for a in arrays)) for idx in (rng.integers(n, size=n) for _ in range(b))]
    return float(np.percentile(vals, 5)), float(np.percentile(vals, 95))


def analyse() -> None:
    cat = [{**c, "kind": "nominal"} for c in read_catalog(CAT)]
    cat += [{**c, "kind": "smooth"} for c in read_catalog(SMOOTH)]
    rows = []
    for i, c in enumerate(cat):
        res, jac, _c = s.Stack.of(c["seq"]).res_jac(c["d"])
        mse0 = float(np.sum(res * res))
        ev = np.linalg.eigvalsh(jac.T @ jac)
        nvec = np.array([s.N_IDX[m] for m in c["seq"]])
        row = {"id": i, "kind": c["kind"], "origin": c["origin"], "rmse": np.sqrt(mse0),
               "total_qwot": float(c["total_qwot"]), "thinnest_nm": float(c["thinnest_nm"]),
               "thinnest_ot_nm": float(np.min(c["d"] * nvec)), "n_ot_under_10nm": int(np.sum(c["d"] * nvec < 10.0)),
               "h_share": c["seq"].count("H") / N,
               # stored electric energy per unit transmitted intensity, sum n^2 |E|^2 d, and the peak field (H3)
               "stored_energy": float(np.sum(nvec ** 2 * layer_field(c["seq"], c["d"]) * c["d"])),
               "field_max": float(np.max(layer_field(c["seq"], c["d"]))),
               "eig_max": ev[-1], "eig_min": ev[0],
               "log10_cond": 0.5 * np.log10(ev[-1] / max(ev[0], 1e-300))}
        for name, v in models(c["seq"], c["d"]).items():
            row[f"pred {name}"] = np.sqrt(mse0 + float(np.sum((jac @ v.T) ** 2)))
        rows.append(row)
    front = set(pareto([(r["rmse"], r["pred OT 0.5nm"]) for r in rows]))
    for r in rows:
        r["pareto OT 0.5nm"] = int(r["id"] in front)
    with (HERE / f"{PREFIX}_analysis.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    from scipy.stats import rankdata, spearmanr
    out = [f"{len(rows)} designs; Spearman rank correlation with the predicted robust cost (OT 0.5nm):"]
    y = [r["pred OT 0.5nm"] for r in rows]
    keys = ("rmse", "thinnest_ot_nm", "n_ot_under_10nm", "total_qwot", "h_share", "stored_energy", "field_max",
            "log10_cond")
    ranks = {k: rankdata([r[k] for r in rows]) for k in keys}
    ry = rankdata(y)
    out.append("   descriptor     rho      partial rho (nominal RMSE held fixed)")
    for key in keys:
        rho, p = spearmanr(ranks[key], ry)
        part = partial_rank_corr(ranks[key], ry, ranks["rmse"]) if key != "rmse" else np.nan
        out.append(f"   {key:14s} {rho:+.2f} (p {p:.1e})  {part:+.2f}")
    x = np.column_stack([ranks[k] for k in keys])
    out.append(f"   all descriptors together, linear model on ranks: 5-fold R^2 {cv_r2(x, ry):.2f}")
    out.append("ranking stability across error models (Spearman of predicted robust costs):")
    for key in ("OT 0.2nm", "OT 1nm", "OT 1%"):
        rho, _p = spearmanr([r[f"pred {key}"] for r in rows], y)
        out.append(f"   OT 0.5nm vs {key:10s} rho {rho:+.2f}")
    out.append(f"Pareto front (nominal, predicted OT 0.5nm): {len(front)} designs")
    out.append("winner of each error model (lowest predicted robust cost):")
    for key in ("OT 0.2nm", "OT 0.5nm", "OT 1nm", "OT 1%"):
        b = min(rows, key=lambda r, key=key: r[f"pred {key}"])
        out.append(f"   {key:9s} id {b['id']} ({b['kind']}) nominal {b['rmse']:.2e} pred {b[f'pred {key}']:.2e}"
                   f" TOT {b['total_qwot']:.1f} thinnest OT {b['thinnest_ot_nm']:.1f} nm")

    nominal = [r for r in rows if r["kind"] == "nominal"]
    chosen: dict[int, str] = {}
    fr = sorted(front, key=lambda i: rows[i]["rmse"])
    for i in fr[:: max(1, len(fr) // 10)][:10]:
        chosen[i] = "pareto"
    for r in sorted(nominal, key=lambda r: r["rmse"])[:15]:
        chosen.setdefault(r["id"], "best nominal")
    for r in sorted(rows, key=lambda r: r["pred OT 0.5nm"])[:15]:
        chosen.setdefault(r["id"], "best predicted OT 0.5nm")
    for r in sorted((r for r in rows if r["kind"] == "smooth"), key=lambda r: float(cat[r["id"]]["saa"]))[:15]:
        chosen.setdefault(r["id"], "best smoothed")
    out.append(f"{len(nominal)} nominal minima, {len(rows) - len(nominal)} smoothed designs; Monte Carlo ({MC_DRAWS} draws,"
               f" bootstrap 90 % intervals) on {len(chosen)}; SPEC max|T-0.5| < {SPEC}")
    mc_rows, sens = [], {}
    for i in sorted(chosen, key=lambda j: rows[j]["pred OT 0.5nm"]):
        t0 = time.time()
        c, r = cat[i], rows[i]
        st = s.Stack.of(c["seq"])
        r0, j0, _c = st.res_jac(c["d"])
        j_ot = j0 / np.array([s.N_IDX[m] for m in c["seq"]])  # derivatives with respect to optical thickness
        h3, _p = spearmanr(layer_field(c["seq"], c["d"]), np.sum(j_ot ** 2, axis=0))
        out.append(f"id {i} [{chosen[i]}, {c['origin']}] nominal {r['rmse']:.3e} TOT {r['total_qwot']:.1f}"
                   f" thinnest OT {r['thinnest_ot_nm']:.1f} nm cond 1e{r['log10_cond']:.1f}"
                   f" H3 rho(field in layer, |J_i|^2) {h3:+.2f}")
        for name, v in models(c["seq"], c["d"]).items():
            z = np.array([np.random.default_rng((SEED_DRAWS, i, k)).standard_normal(len(v)) for k in range(MC_DRAWS)])
            e = z @ v
            mse, dev, quad, grads = np.empty(MC_DRAWS), np.empty(MC_DRAWS), np.empty(MC_DRAWS), []
            for k in range(MC_DRAWS):
                dk = np.maximum(c["d"] + e[k], 0.0)
                res, jac, _c = st.res_jac(dk)
                mse[k], dev[k] = float(np.sum(res * res)), float(np.max(np.abs(res)) * np.sqrt(NW))
                quad[k] = float(np.sum((r0 + j0 @ e[k]) ** 2))
                if name == "OT 0.5nm":
                    grads.append(2.0 * jac.T @ res)
                if k < MC_CHECK and abs(s.oracle_rmse(c["seq"], dk) - np.sqrt(mse[k])) > 1e-3 * np.sqrt(mse[k]):
                    raise SystemExit(f"oracle disagrees with the kernel on id {i}, {name}, draw {k}")
            eq = quad_expectation(r0, j0, v)
            plain = np.sqrt(np.mean(mse))
            cv = cv_estimate(mse, quad, eq)
            cv_ci = boot(lambda a, b, eq=eq: cv_estimate(a, b, eq), mse, quad)
            pl_ci = boot(lambda a: np.sqrt(np.mean(a)), mse)
            cvr = cvar(np.sqrt(mse))
            cvr_ci = boot(lambda a: cvar(np.sqrt(a)), mse)
            yld = float(np.mean(dev < SPEC))
            yld_ci = boot(lambda a: float(np.mean(a < SPEC)), dev)
            bp = bpoe(dev, SPEC)
            bp_ci = boot(lambda a: bpoe(a, SPEC), dev)
            out.append(f"   {name:10s} pred {r[f'pred {name}']:.2e} | MC {plain:.2e} [{pl_ci[0]:.2e},{pl_ci[1]:.2e}]"
                       f" | CV {cv:.2e} [{cv_ci[0]:.2e},{cv_ci[1]:.2e}] | CVaR95 {cvr:.2e} [{cvr_ci[0]:.2e},{cvr_ci[1]:.2e}]"
                       f" | yield {yld:.2f} [{yld_ci[0]:.2f},{yld_ci[1]:.2f}] | bPOE {bp:.2f} [{bp_ci[0]:.2f},{bp_ci[1]:.2f}]")
            mc_rows.append({"id": i, "group": chosen[i], "model": name, "nominal": r["rmse"], "pred": r[f"pred {name}"],
                            "mc": plain, "cv": cv, "cv_lo": cv_ci[0], "cv_hi": cv_ci[1], "cvar95": cvr, "yield": yld,
                            "bpoe": bp, "thinnest_ot_nm": r["thinnest_ot_nm"], "total_qwot": r["total_qwot"]})
            if grads:
                g = np.array(grads)
                lam, vec = np.linalg.eigh(g.T @ g / len(g))
                lam, vec = lam[::-1], vec[:, ::-1]
                lam_ci = boot(lambda a: np.linalg.eigvalsh(a.T @ a / len(a))[-1], g, b=200)
                share = np.cumsum(lam) / np.sum(lam)
                v_jtj = np.linalg.eigh(j0.T @ j0)[1][:, -1]
                top = np.argsort(np.abs(vec[:, 0]))[::-1][:3]
                out.append(f"   active subspace OT 0.5nm: lambda1 {lam[0]:.2e} [{lam_ci[0]:.2e},{lam_ci[1]:.2e}]"
                           f" lambda2/1 {lam[1] / lam[0]:.2e} share(1) {share[0]:.2f} share(3) {share[2]:.2f}"
                           f" |cos(v1, JtJ v1)| {abs(vec[:, 0] @ v_jtj):.2f}"
                           f" v1 layers " + " ".join(f"#{t}({c['seq'][t]},{c['d'][t]:.1f}nm)" for t in top))
        sens[i] = 0.5 * np.sqrt(np.sum(j_ot ** 2, axis=1) * NW)  # rms dT per wavelength, OT 0.5 nm on every layer
        out.append(f"   ({time.time() - t0:.1f} s for this design)")
    out.append("winner of each error model by Monte Carlo (control-variate estimate, selection draws):")
    for key in ("OT 0.2nm", "OT 0.5nm", "OT 1nm", "OT 1%"):
        sel = sorted((m for m in mc_rows if m["model"] == key), key=lambda m: m["cv"])
        out.append(f"   {key:9s} " + ", ".join(f"id {m['id']} {m['cv']:.2e} [{m['cv_lo']:.2e},{m['cv_hi']:.2e}]"
                                             for m in sel[:3]))
    (HERE / f"{PREFIX}_mc.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    with (HERE / f"{PREFIX}_mc.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mc_rows[0]))
        w.writeheader()
        w.writerows(mc_rows)
    print("\n".join(out))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, name in zip(axs, ("OT 0.2nm", "OT 0.5nm", "OT 1%"), strict=True):
        for kind, mk in (("nominal", "o"), ("smooth", "^")):
            sel = [r for r in rows if r["kind"] == kind]
            if sel:
                sc = ax.scatter([r["rmse"] for r in sel], [r[f"pred {name}"] for r in sel], marker=mk, s=14,
                                c=[r["thinnest_ot_nm"] for r in sel], cmap="viridis", vmin=1, vmax=40,
                                label=f"{kind} ({len(sel)})")
        if name == "OT 0.5nm":
            ax.plot([rows[i]["rmse"] for i in fr], [rows[i][f"pred {name}"] for i in fr], "r-", lw=1, label="Pareto front")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("nominal RMSE")
        ax.set_ylabel(f"predicted sqrt(E[MSE]), {name}")
        ax.grid(True, which="both", alpha=.3)
        ax.legend(fontsize=8)
    fig.colorbar(sc, ax=axs[-1], label="thinnest layer, optical thickness (nm)")
    fig.suptitle(f"N = {N}: nominal against robust (o local minima of the MSE, ^ minima of the smoothed cost)")
    fig.tight_layout()
    fig.savefig(HERE / f"{PREFIX}_scatter.png", dpi=130)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    best_nom = min(nominal, key=lambda r: r["rmse"])["id"]
    best_rob = min((j for j in sens), key=lambda j: rows[j]["pred OT 0.5nm"])
    for i, lab in ((best_nom, "best nominal"), (best_rob, "best predicted OT 0.5nm")):
        ax.plot(s.WLS, sens[i], label=f"{lab} (id {i})")
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("rms dT, random OT error 0.5 nm on every layer")
    ax.grid(True, alpha=.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / f"{PREFIX}_sensitivity.png", dpi=130)


def confirm(draws: int) -> None:
    """Out-of-sample check of the finalists on fresh draws (seed base SEED_DRAWS + 1, never used for selection).
    Finalists: the designs non-dominated in (nominal, CV estimate under OT 0.5nm) of {prefix}_mc.csv, plus the 3 best
    CV estimates under each model."""
    cat = [{**c, "kind": "nominal"} for c in read_catalog(CAT)] + [{**c, "kind": "smooth"} for c in read_catalog(SMOOTH)]
    mc = list(csv.DictReader((HERE / f"{PREFIX}_mc.csv").open(encoding="utf-8")))
    e1 = [m for m in mc if m["model"] == "OT 0.5nm"]
    fin = {int(e1[i]["id"]) for i in pareto([(float(m["nominal"]), float(m["cv"])) for m in e1])}
    for name in {m["model"] for m in mc}:
        fin |= {int(m["id"]) for m in sorted((m for m in mc if m["model"] == name), key=lambda m: float(m["cv"]))[:3]}
    out = [f"confirmation on {draws} fresh draws per design and model; {len(fin)} finalists"]
    for i in sorted(fin):
        c = cat[i]
        st = s.Stack.of(c["seq"])
        r0, j0, _c = st.res_jac(c["d"])
        out.append(f"id {i} ({c['kind']}, {c['origin']}) nominal {np.sqrt(np.sum(r0 * r0)):.3e}")
        for name, v in models(c["seq"], c["d"]).items():
            sel = next(float(m["cv"]) for m in mc if int(m["id"]) == i and m["model"] == name)
            z = np.random.default_rng((SEED_DRAWS + 1, i)).standard_normal((draws, len(v)))
            e = z @ v
            mse, dev, quad = np.empty(draws), np.empty(draws), np.empty(draws)
            for k in range(draws):
                res, _j, _c = st.res_jac(np.maximum(c["d"] + e[k], 0.0))
                mse[k], dev[k] = float(np.sum(res * res)), float(np.max(np.abs(res)) * np.sqrt(NW))
                quad[k] = float(np.sum((r0 + j0 @ e[k]) ** 2))
            eq = quad_expectation(r0, j0, v)
            cv = cv_estimate(mse, quad, eq)
            lo, hi = boot(lambda a, b, eq=eq: cv_estimate(a, b, eq), mse, quad, b=300)
            out.append(f"   {name:10s} selection {sel:.3e} -> fresh {cv:.3e} [{lo:.3e},{hi:.3e}]"
                       f" CVaR95 {cvar(np.sqrt(mse)):.3e} yield {np.mean(dev < SPEC):.3f} bPOE {bpoe(dev, SPEC):.3f}")
    (HERE / f"{PREFIX}_confirm.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


def entropy(draws: int) -> None:
    """Local entropy (Baldassi et al., PNAS 2016; Entropy-SGD) against the robust criteria, random OT errors 0.5 nm.

    For the designs of {prefix}_mc.csv, on `draws` fresh draws (seed base SEED_DRAWS + 2):
      soft:  F_tau = -tau log E[exp(-MSE(d + e) / tau)]  (Gaussian-coupled local free energy, MSE units; tau -> inf is the
             mean, tau -> 0 the best point of the neighbourhood);
      hard:  log P(RMSE(d + e) < eps)  (log volume of the good part of the neighbourhood, a flat-ball local entropy).
    For every design: harmonic log volume -1/2 sum log(1 + sigma^2 lambda_i / tau), lambda_i eigenvalues of J^T J in
    optical-thickness coordinates (Wales, harmonic superposition), against the trace (mean) and lambda_max (worst case).
    Spearman correlations -> {prefix}_entropy.txt."""
    from scipy.special import logsumexp
    from scipy.stats import spearmanr
    sig, taus, epss = 0.5, (1e-6, 1e-5, 1e-4), (3e-3, 4e-3, 6e-3)
    cat = [{**c, "kind": "nominal"} for c in read_catalog(CAT)] + [{**c, "kind": "smooth"} for c in read_catalog(SMOOTH)]
    ana = {int(r["id"]): r for r in csv.DictReader((HERE / f"{PREFIX}_analysis.csv").open(encoding="utf-8"))}
    mc = {int(m["id"]): m for m in csv.DictReader((HERE / f"{PREFIX}_mc.csv").open(encoding="utf-8"))
          if m["model"] == "OT 0.5nm"}
    out = [f"local entropy, random OT errors {sig} nm; {len(mc)} designs x {draws} fresh draws; {len(cat)} for harmonic"]

    harm = {}
    for i, c in enumerate(cat):
        _r, j0, _c = s.Stack.of(c["seq"]).res_jac(c["d"])
        j_ot = j0 / np.array([s.N_IDX[m] for m in c["seq"]])
        lam = np.linalg.eigvalsh(j_ot.T @ j_ot)
        harm[i] = {"trace": sig ** 2 * lam.sum(), "lam_max": sig ** 2 * lam[-1],
                   **{f"harm tau{t:g}": -0.5 * float(np.sum(np.log1p(sig ** 2 * np.maximum(lam, 0) / t))) for t in taus}}
    out.append("all designs: Spearman of the harmonic log volume (higher = wider) with")
    for t in taus:
        h = [harm[i][f"harm tau{t:g}"] for i in harm]
        for key in ("trace", "lam_max"):
            rho, _p = spearmanr(h, [harm[i][key] for i in harm])
            out.append(f"   tau {t:g}: -{key:7s} rho {-rho:+.2f}")
        for key in ("rmse", "total_qwot", "thinnest_ot_nm", "stored_energy"):
            rho, _p = spearmanr(h, [float(ana[i][key]) for i in harm])
            out.append(f"   tau {t:g}: {key:14s} rho {rho:+.2f}")

    rows = []
    for i in sorted(mc):
        c = cat[i]
        st = s.Stack.of(c["seq"])
        z = np.random.default_rng((SEED_DRAWS + 2, i)).standard_normal((draws, N)) * sig / np.array(
            [s.N_IDX[m] for m in c["seq"]])
        mse = np.array([float(np.sum(st.res_jac(np.maximum(c["d"] + zk, 0.0))[0] ** 2)) for zk in z])
        row = {"id": i, "mean": float(np.mean(mse)), "cv": float(mc[i]["cv"]), "cvar95": float(mc[i]["cvar95"]),
               "yield": float(mc[i]["yield"]), "nominal": float(mc[i]["nominal"])}
        for t in taus:
            row[f"soft tau{t:g}"] = -t * float(logsumexp(-mse / t) - np.log(draws))
        for e in epss:
            row[f"hard eps{e:g}"] = float(np.log(max(np.mean(np.sqrt(mse) < e), 0.5 / draws)))
        rows.append(row)
    out.append(f"{len(rows)} Monte Carlo designs: Spearman of each local entropy with the robust criteria"
               " (soft: lower F = wider; hard: higher log volume = wider)")
    for key in [f"soft tau{t:g}" for t in taus] + [f"hard eps{e:g}" for e in epss]:
        v = [r[key] for r in rows]
        line = f"   {key:13s}"
        for crit in ("cv", "cvar95", "yield", "nominal"):
            rho, _p = spearmanr(v, [r[crit] for r in rows])
            line += f"  {crit} {rho:+.2f}"
        best = min(rows, key=lambda r, key=key: r[key]) if key.startswith("soft") else max(rows, key=lambda r, key=key: r[key])
        line += f"  | widest: id {best['id']} (best mean is id {min(rows, key=lambda r: r['cv'])['id']})"
        out.append(line)
    (HERE / f"{PREFIX}_entropy.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    if sys.argv[1] == "entropy":
        entropy(int(sys.argv[2]))
    elif sys.argv[1] == "confirm":
        confirm(int(sys.argv[2]))
    elif sys.argv[1] == "build":
        build(float(sys.argv[2]), int(sys.argv[3]), sys.argv[4:])
    elif sys.argv[1] == "smooth":
        smooth(float(sys.argv[2]), int(sys.argv[3]))
    else:
        analyse()
