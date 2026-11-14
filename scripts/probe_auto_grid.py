"""SONDE GRILLE AUTOMATIQUE : la grille qui trouve ses points juge-t-elle et polit-elle comme une grille resolue ?

    python scripts/probe_auto_grid.py [--starts 2] [--sigma 0.05] [--out FICHIER.json]

## POURQUOI

Le record du tri-bande RICL (Tikhonravov et Trubetskov 2012) vaut 1,28e-4 sur sa grille a 1 nm et 4,8e-3 sur 0,1 nm
(audit du 2026-11-13, `reports/audits_2026-11-13/bilan.md` §3.5) : la grille a 1 nm ne voit pas des pics etroits. La
grille automatique de DESIGN (`certus/core/certus_design_auto_grid.py`, ALG-32) part d'un compte de Nyquist et ajoute
des points ou la quadrature du merite l'exige. Cette sonde dit, sur ce cas, ce qu'elle juge et ce qu'elle polit.

## CE QU'ELLE FAIT

Probleme `threeline` du moteur RICL (`reports/RICL_ultimate_2026-11-05/engine.py`) ; merite = moyenne en lambda de
(T - cible)^2 sur les sept bandes (celle des grilles uniformes du moteur), la REFERENCE etant la grille a 0,01 nm.

1. JUGER le record : merite sur 1 nm, 0,1 nm, la grille automatique (base puis raffinee), et la reference.
2. POLIR (L-BFGS-B, gradient exact du noyau de CERTUS) depuis le record et depuis `--starts` departs perturbes
   (epaisseurs x (1 + sigma N(0,1)), graines 1, 2...) : sur 1 nm, sur 0,1 nm, et sur la grille automatique (polir,
   raffiner sur le design obtenu, recommencer tant que la grille change, 4 tours au plus). Chaque design final est juge
   sur la reference ; on rapporte aussi le nombre de points et la duree.

Une mesure a la fois sur la machine (CLAUDE.md §4) ; les durees ne valent que machine libre.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RICL = ROOT / "reports" / "RICL_ultimate_2026-11-05"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(RICL))

import numpy as np  # noqa: E402

LOWER_NM = 0.05
REFERENCE_STEP_NM = 0.01
AUTO_ROUNDS = 4


def target_of(engine, lam: np.ndarray) -> np.ndarray:
    out = np.full(lam.shape, np.nan)
    for lo, hi, t in engine.THREELINE_BANDS:
        out[(lam >= lo) & (lam <= hi)] = t
    return out


def uniform_grid(engine, step: float) -> np.ndarray:
    return np.concatenate([np.linspace(lo, hi, round((hi - lo) / step) + 1) for lo, hi, _t in engine.THREELINE_BANDS])


def problem(engine, lam: np.ndarray, weights: np.ndarray | None = None):
    """Le probleme du moteur sur une grille donnee ; `weights` (somme 1) remplace les poids uniformes."""
    prob = engine.Problem("threeline", lam, target_of(engine, lam), 100.0)
    if weights is not None:
        prob.sqw = np.sqrt(weights / weights.sum())
    return prob


def quadrature_weights(engine, lam: np.ndarray) -> np.ndarray:
    """Poids de la moyenne en lambda sur l'union des bandes : trapeze par bande, rien a travers un trou."""
    w = np.zeros_like(lam)
    for lo, hi, _t in engine.THREELINE_BANDS:
        idx = np.flatnonzero((lam >= lo) & (lam <= hi))
        if idx.size >= 2:
            h = np.diff(lam[idx])
            w[idx[:-1]] += 0.5 * h
            w[idx[1:]] += 0.5 * h
    return w


def merit(engine, seq: str, d: np.ndarray, lam: np.ndarray, uniform: bool) -> float:
    """Moyenne de (T - cible)^2 : par point sur une grille uniforme du moteur, par quadrature sinon."""
    weights = None if uniform else quadrature_weights(engine, lam)
    r, _j = problem(engine, lam, weights).res_jac(seq, d)
    return float(r @ r)


def polish(engine, seq: str, d0: np.ndarray, prob) -> np.ndarray:
    from scipy.optimize import minimize

    def f(d):
        r, j = prob.res_jac(seq, d)
        return float(r @ r), 2.0 * (j.T @ r)

    res = minimize(f, d0, jac=True, method="L-BFGS-B", bounds=[(LOWER_NM, None)] * len(d0),
                   options={"maxiter": 20000, "maxfun": 40000, "ftol": 1e-15, "gtol": 1e-12})
    return np.asarray(res.x)


def auto_grid_polish(engine, seq: str, d0: np.ndarray):
    from certus.core.certus_design_auto_grid import base_grid, refine_grid

    bands = [(float(lo), float(hi)) for lo, hi, _t in engine.THREELINE_BANDS]
    lam = base_grid(bands, engine.total_ot(seq, d0))
    d = d0
    rounds = []
    for round_no in range(AUTO_ROUNDS):
        d = polish(engine, seq, d, problem(engine, lam, quadrature_weights(engine, lam)))

        def squared(x, d=d):
            p = problem(engine, x)
            p.sqw = np.ones_like(x)
            r, _j = p.res_jac(seq, d)
            return (r * r) * x  # moyenne en lambda = integrale en ln(lambda) du residu fois lambda

        refined = refine_grid(bands, lam, squared)
        rounds.append({"points": int(lam.size), "points_after": int(refined.wavelengths.size),
                       "converged": bool(refined.converged)})
        if refined.wavelengths.size == lam.size or round_no == AUTO_ROUNDS - 1:
            break
        lam = refined.wavelengths
    return d, lam, rounds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--starts", type=int, default=2)
    ap.add_argument("--sigma", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "questions_design_2026-11-13" / "probe_auto_grid.json")
    a = ap.parse_args()
    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    import engine
    from _artefact import ecrire_json
    from probe_local_convergence import _record

    from certus.core.certus_design_auto_grid import base_grid, refine_grid

    seq, d_rec, _mf, fichier = _record("*tl*_best.csv")
    d_rec = np.asarray(d_rec, dtype=np.float64)
    ref = uniform_grid(engine, REFERENCE_STEP_NM)

    def judge(d):
        return float(np.sqrt(merit(engine, seq, d, ref, uniform=False)))

    out: dict = {"record_file": fichier, "layers": len(seq), "tot_nm": engine.total_ot(seq, d_rec),
                 "reference_points": int(ref.size), "judge": {}, "polish": []}
    bands = [(float(lo), float(hi)) for lo, hi, _t in engine.THREELINE_BANDS]
    base = base_grid(bands, out["tot_nm"])

    def squared(x):
        p = problem(engine, x)
        p.sqw = np.ones_like(x)
        r, _j = p.res_jac(seq, d_rec)
        return (r * r) * x

    refined = refine_grid(bands, base, squared)
    for name, lam, uni in (("1 nm", uniform_grid(engine, 1.0), True), ("0,1 nm", uniform_grid(engine, 0.1), True),
                           ("auto, base", base, False), ("auto, raffinee", refined.wavelengths, False),
                           ("reference 0,01 nm", ref, False)):
        out["judge"][name] = {"points": int(lam.size), "rmse": float(np.sqrt(merit(engine, seq, d_rec, lam, uni)))}
        print(f"juge {name:>18} : {lam.size:>6} points, RMSE {out['judge'][name]['rmse']:.4e}", flush=True)

    starts = [("record", d_rec)]
    for k in range(1, a.starts + 1):
        rng = np.random.default_rng(k)
        starts.append((f"sigma {a.sigma:g}, graine {k}", np.maximum(d_rec * (1.0 + a.sigma * rng.standard_normal(d_rec.size)), LOWER_NM)))
    for label, d0 in starts:
        row = {"start": label, "start_rmse": judge(d0)}
        for name, step in (("1 nm", 1.0), ("0,1 nm", 0.1)):
            lam = uniform_grid(engine, step)
            t = time.perf_counter()
            d = polish(engine, seq, d0, problem(engine, lam))
            row[name] = {"points": int(lam.size), "rmse_reference": judge(d), "s": round(time.perf_counter() - t, 1)}
        t = time.perf_counter()
        d, lam, rounds = auto_grid_polish(engine, seq, d0)
        row["auto"] = {"points": int(lam.size), "rmse_reference": judge(d), "s": round(time.perf_counter() - t, 1), "rounds": rounds}
        out["polish"].append(row)
        print(f"polit {label} (depart {row['start_rmse']:.3e}) : " + " ; ".join(
            f"{k} {row[k]['points']} pts -> {row[k]['rmse_reference']:.4e} en {row[k]['s']} s" for k in ("1 nm", "0,1 nm", "auto")), flush=True)
    ecrire_json(a.out.resolve(), out)
    print(f"ecrit : {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
