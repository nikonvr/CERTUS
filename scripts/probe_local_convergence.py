"""SONDE CONVERGENCE LOCALE : cinq polisseurs sur les deux problemes RICL (separateur 50/50, tri-bande).

    python scripts/probe_local_convergence.py [--starts 10] [--out FICHIER.json]

## POURQUOI

Audit du 2026-11-13 (reports/audits_2026-11-13), demande de 👤 : converger plus vite localement. Deux idees a eprouver
AVANT de toucher un noyau : travailler en epaisseur optique, et l'acceleration geodesique de Levenberg-Marquardt
(Transtrum et Sethna, 2012). Les deux problemes sont ceux de l'article RICL (`reports/RICL_ultimate_2026-11-05/engine.py`,
Tikhonravov et al. 1996, 2012 ; nH = 2,35, nL = 1,45, substrat 1,52, incidence normale) : `bs5050` et `threeline`.

## CE QU'ELLE FAIT

Pour chaque probleme, elle prend le design record du dossier RICL (meilleur merite, sans couche sous 1 nm), le perturbe
(epaisseurs x (1 + sigma N(0,1)), sigma 1 % et 5 %, graine fixe) et polit chaque depart avec :

- `lbfgs_nm`      L-BFGS-B sur les epaisseurs en nm (le polisseur du memetique de DESIGN) ;
- `lbfgs_ot`      L-BFGS-B sur les epaisseurs optiques n d ;
- `lbfgs_jacobi`  L-BFGS-B sur d x sqrt(diag(J^T J)) du depart (preconditionnement diagonal) ;
- `lm`            Levenberg-Marquardt a amortissement de Marquardt, la regle du noyau de CERTUS (ALG-07) ;
- `lm_geo`        le meme avec l'acceleration geodesique (pas v + a/2, refuse si 2|a|/|v| > 0,75) ;
- `lm_nielsen`    Levenberg-Marquardt a amortissement de Nielsen (rapport gain reel / gain predit), la regle du
                  moteur RICL (`engine.lm`) ; `lm_nielsen_geo` : le meme avec l'acceleration geodesique.

- `lbfgs_then_lm` L-BFGS-B puis une finition de Nielsen (200 iterations au plus) ; `lm_then_lbfgs` : une amorce de
                  Nielsen (60 iterations au plus) puis L-BFGS-B.

- `lm_resonance`  (tri-bande) le polisseur a longueurs d'onde complexes de CERTUS, `refine_resonances`, 10 tours.

Sur le tri-bande, chaque design final est aussi juge sur la grille a 0,1 nm (`rmse resolu`) : c'est l'erreur qui
compte, la grille a 1 nm pouvant ignorer des pics etroits. La cible des departs ignore `lm_resonance`.

`--methods` restreint la liste ; la cible d'un depart est alors le meilleur des methodes DEMANDEES.

Residus et Jacobien exacts : le noyau de CERTUS, par `engine.Problem.res_jac`. L'unite de cout est UNE evaluation
(residus + Jacobien) : le decompte est deterministe, il ne depend pas de la machine. La cible d'un depart est le
meilleur merite final de toutes les methodes sur ce depart ; on rapporte le nombre d'evaluations pour l'atteindre a
0,1 % pres, la part des departs qui l'atteignent, et le merite final.

🔴 `lm_geo` paie une evaluation de plus par essai de pas (comptee pleine, alors qu'il ne lui faut que les residus :
borne pessimiste). Deux problemes, des departs proches d'un record : rien sur la recherche globale.
"""

from __future__ import annotations

import argparse
import csv
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

LOWER_NM = 0.05
#: `threeline_fine` : les memes bandes sur une grille resolue (0,1 nm) ; meme record de depart que `threeline`.
RECORDS = {"bs5050": "B_conv*_best.csv", "threeline": "*tl*_best.csv", "threeline_fine": "*tl*_best.csv"}
METHODES = ("lbfgs_nm", "lbfgs_ot", "lbfgs_jacobi", "lm", "lm_geo", "lm_nielsen", "lm_nielsen_geo",
            "lbfgs_then_lm", "lm_then_lbfgs", "lm_resonance")
#: Tours du polisseur a longueurs d'onde complexes (`refine_resonances`), chacun de 30 evaluations au plus.
RESONANCE_ROUNDS = 10
#: Budgets des enchainements : iterations de Levenberg-Marquardt en finition, puis en amorce.
FINISH_LM_ITERS = 200
HEAD_LM_ITERS = 60
GEODESIC_FD_STEP = 0.1
GEODESIC_MAX_RATIO = 0.75


def _record(motif: str) -> tuple[str, list[float], float, str]:
    """(sequence, epaisseurs, merite, fichier) du meilleur design des fichiers `motif`, sans couche sous 1 nm si possible."""
    lignes = []
    for f in sorted(RICL.glob(motif)):
        with f.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    lignes.append((float(row["mf"]), float(row["thinnest_nm"]), row["seq"], row["d_nm"], f.name))
                except (KeyError, ValueError):
                    continue
    if not lignes:
        raise SystemExit(f"🔴 aucun record lisible pour {motif} dans {RICL}")
    epaisses = [x for x in lignes if x[1] >= 1.0] or lignes
    mf, _fin, seq, d, nom = min(epaisses)
    return seq, [float(v) for v in d.split()], mf, nom


def _lm(np, resjac, x0, lb, geodesic: bool, max_iter: int = 5000):
    """Levenberg-Marquardt a amortissement de Marquardt et bornes inferieures, comme le noyau de CERTUS (ALG-07)."""
    from scipy.linalg import LinAlgError, cho_factor, cho_solve

    x = np.maximum(np.asarray(x0, dtype=np.float64), lb)
    r, jac = resjac(x)
    cost, n_eval, lam = float(r @ r), 1, 1e-5
    hist = [(1, cost)]
    for _ in range(max_iter):
        g, h = jac.T @ r, jac.T @ jac
        held = (x <= lb + 1e-12) & (g > 0.0)
        if held.any():
            g = g.copy()
            g[held] = 0.0
            h[held, :] = 0.0
            h[:, held] = 0.0
            h[held, held] = 1.0
        if np.abs(g).max() < 1e-14:
            break
        accepted = False
        for _sub in range(12):
            a_mat = h + np.diag(lam * np.maximum(np.diag(h), 1e-12) + 1e-15)
            try:
                cf = cho_factor(a_mat)
            except LinAlgError:
                lam *= 10.0
                continue
            step = cho_solve(cf, -g)
            if geodesic:
                xh = x + GEODESIC_FD_STEP * step
                v_norm = float(np.linalg.norm(step))
                if (xh >= lb).all() and v_norm > 0.0:
                    rh, _jh = resjac(xh)
                    n_eval += 1
                    r_vv = 2.0 / GEODESIC_FD_STEP * ((rh - r) / GEODESIC_FD_STEP - jac @ step)
                    rhs = -(jac.T @ r_vv)
                    rhs[held] = 0.0
                    acc = cho_solve(cf, rhs)
                    if 2.0 * float(np.linalg.norm(acc)) / v_norm > GEODESIC_MAX_RATIO:
                        lam *= 8.0
                        if lam > 1e8:
                            break
                        continue
                    step = step + 0.5 * acc
            xc = np.maximum(x + step, lb)
            if np.abs(xc - x).max() < 1e-12:
                break
            rc, jc = resjac(xc)
            n_eval += 1
            cc = float(rc @ rc)
            if cc < cost:
                x, r, jac, cost = xc, rc, jc, cc
                lam = max(lam * 0.3, 1e-14)
                hist.append((n_eval, cost))
                accepted = True
                break
            lam *= 8.0
            if lam > 1e8:
                break
        if not accepted:
            break
    return x, cost, n_eval, hist


def _lm_nielsen(np, resjac, x0, lb, geodesic: bool, max_iter: int = 5000, ftol: float = 1e-13):
    """Levenberg-Marquardt a amortissement de Nielsen (rapport gain reel / gain predit), la regle du moteur RICL."""
    x = np.maximum(np.asarray(x0, dtype=np.float64), lb)
    r, jac = resjac(x)
    f, n_eval = float(r @ r), 1
    hist = [(1, f)]
    mu, nu, small = 1e-3, 2.0, 0
    m = len(x)
    for _ in range(max_iter):
        g, a = jac.T @ r, jac.T @ jac
        da = np.diag(a).copy()
        free = ~((x <= lb + 1e-12) & (g > 0.0))
        fi = np.flatnonzero(free)
        if fi.size == 0:
            break
        b = a[np.ix_(fi, fi)].copy()
        b[np.diag_indices_from(b)] += mu * (da[fi] + 1e-12 * float(da.max()))
        try:
            sf = np.linalg.solve(b, -g[fi])
            if geodesic:
                step_v = np.zeros(m)
                step_v[fi] = sf
                xh = x + GEODESIC_FD_STEP * step_v
                v_norm = float(np.linalg.norm(sf))
                if (xh >= lb).all() and v_norm > 0.0:
                    rh, _jh = resjac(xh)
                    n_eval += 1
                    r_vv = 2.0 / GEODESIC_FD_STEP * ((rh - r) / GEODESIC_FD_STEP - jac @ step_v)
                    acc = np.linalg.solve(b, -(jac.T @ r_vv)[fi])
                    if 2.0 * float(np.linalg.norm(acc)) / v_norm > GEODESIC_MAX_RATIO:
                        mu *= nu
                        nu *= 2.0
                        if mu > 1e16:
                            break
                        continue
                    sf = sf + 0.5 * acc
        except np.linalg.LinAlgError:
            mu *= nu
            nu *= 2.0
            continue
        step = np.zeros(m)
        step[fi] = sf
        xn = np.maximum(x + step, lb)
        dx = xn - x
        pred = -(2.0 * float(dx @ g) + float(dx @ a @ dx))
        rn, jn = resjac(xn)
        n_eval += 1
        fn = float(rn @ rn)
        if fn < f and pred > 0.0:
            rho, gain = (f - fn) / pred, (f - fn) / f
            x, r, jac, f = xn, rn, jn, fn
            hist.append((n_eval, f))
            mu *= max(1.0 / 3.0, 1.0 - (2.0 * rho - 1.0) ** 3)
            nu = 2.0
            small = small + 1 if gain < ftol else 0
            if small >= 3:
                break
        else:
            mu *= nu
            nu *= 2.0
            if mu > 1e16:
                break
    return x, f, n_eval, hist


def _lm_resonance(np, engine, seq, x0, lb, rounds: int = RESONANCE_ROUNDS):
    """`certus.physics.design_resonances.refine_resonances` : la grille du probleme, plus un residu par pic etroit suivi
    a son maximum mobile (poles aux longueurs d'onde complexes, article OE_resonances). Tri-bande seulement."""
    from certus.physics.design_resonances import (
        ResonanceSettings,
        TransmissionBand,
        TransmissionProblem,
        refine_resonances,
    )

    bands = tuple(TransmissionBand(float(a), float(b), float(t), 1.0) for a, b, t in engine.THREELINE_BANDS)
    problem = TransmissionProblem(engine.nvec(seq).astype(np.complex128), engine.N_SUB, bands)
    x0 = np.maximum(np.asarray(x0, dtype=np.float64), max(lb, 0.1))
    try:
        res = refine_resonances(problem, x0, settings=ResonanceSettings(rounds=rounds),
                                lower_bounds=np.full(len(x0), max(lb, 0.1) * 0.999))
    except (RuntimeError, ValueError) as exc:  # un audit de poles refuse : le depart est rendu tel quel
        print(f"    lm_resonance refuse : {exc}")
        return x0, float("inf"), 0, []
    return res.thicknesses, float(res.final.nominal_mf) ** 2, rounds * 30, []


def _lbfgs(np, resjac, x0, lb, scale):
    """L-BFGS-B sur u = scale * d, tolerances du polissage memetique de DESIGN."""
    from scipy.optimize import minimize

    hist: list[tuple[int, float]] = []
    state = {"n": 0, "best": float("inf")}

    def f(u):
        r, jac = resjac(u / scale)
        state["n"] += 1
        c = float(r @ r)
        if c < state["best"]:
            state["best"] = c
            hist.append((state["n"], c))
        return c, (2.0 * (jac.T @ r)) / scale

    x0 = np.maximum(np.asarray(x0, dtype=np.float64), lb)
    res = minimize(f, x0 * scale, jac=True, method="L-BFGS-B", bounds=[(lb * s, 1e5 * s) for s in scale],
                   options={"maxiter": 20000, "maxfun": 60000, "ftol": 1e-15, "gtol": 1e-12})
    return res.x / scale, state["best"], state["n"], hist


def _evals_to(hist, cible: float) -> int | None:
    for n, c in hist:
        if c <= cible:
            return n
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Cinq polisseurs locaux sur les deux problemes RICL.")
    ap.add_argument("--starts", type=int, default=10, help="departs par niveau de perturbation (defaut 10)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--methods", nargs="+", default=list(METHODES), choices=METHODES)
    ap.add_argument("--problems", nargs="+", default=["bs5050", "threeline"], choices=list(RECORDS))
    a = ap.parse_args()

    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    import engine  # reports/RICL_ultimate_2026-11-05 (fixe NUMBA_NUM_THREADS=1 a l'import)
    import numpy as np
    from _artefact import ecrire_json

    sortie: dict = {"starts": a.starts, "lower_nm": LOWER_NM, "problems": {}}
    methodes = tuple(a.methods)
    sortie["methods"] = list(methodes)
    for nom in a.problems:
        motif = RECORDS[nom]
        prob = engine.make_problem(nom)
        seq, d_rec, _mf_rec, fichier = _record(motif)
        d_rec = np.asarray(d_rec, dtype=np.float64)
        n_idx = engine.nvec(seq)

        def resjac(d, prob=prob, seq=seq):
            return prob.res_jac(seq, d)

        resjac(d_rec)  # amorce (compilation)
        # Le juge de l'erreur RESOLUE : le tri-bande sur la grille a 0,1 nm (les pics etroits y sont vus).
        fine = engine.make_problem("threeline_fine") if nom == "threeline" else None
        rmse_rec = prob.rmse(seq, d_rec)
        print(f"\n== {nom} : {len(seq)} couches, {len(prob.wls)} longueurs d'onde, record {fichier} "
              f"(rmse {rmse_rec:.6g}, plus fine {d_rec.min():.2f} nm)")
        bloc: dict = {"layers": len(seq), "wavelengths": len(prob.wls), "record_file": fichier, "record_rmse": rmse_rec,
                      "levels": {}}
        rng = np.random.default_rng(20261113)
        for sigma in (0.01, 0.05):
            lignes = {m: {"evals": [], "evals_to_target": [], "final_rmse": [], "ms": [], "resolved_rmse": []}
                      for m in methodes}
            for _k in range(a.starts):
                x0 = np.maximum(d_rec * (1.0 + sigma * rng.standard_normal(len(d_rec))), LOWER_NM)
                _r0, j0 = resjac(x0)
                jacobi = np.sqrt(np.maximum(np.einsum("mi,mi->i", j0, j0), 1e-300))
                jacobi = jacobi / jacobi.mean()
                essais = {}
                for m in methodes:
                    t0 = time.perf_counter()
                    if m == "lbfgs_nm":
                        res = _lbfgs(np, resjac, x0, LOWER_NM, np.ones(len(x0)))
                    elif m == "lbfgs_ot":
                        res = _lbfgs(np, resjac, x0, LOWER_NM, n_idx)
                    elif m == "lbfgs_jacobi":
                        res = _lbfgs(np, resjac, x0, LOWER_NM, jacobi)
                    elif m == "lbfgs_then_lm":  # le polissage actuel, puis une finition de Nielsen
                        x1, c1, n1, h1 = _lbfgs(np, resjac, x0, LOWER_NM, np.ones(len(x0)))
                        x2, c2, n2, h2 = _lm_nielsen(np, resjac, x1, LOWER_NM, geodesic=False, max_iter=FINISH_LM_ITERS)
                        res = (x2, min(c1, c2), n1 + n2, h1 + [(n1 + n, c) for n, c in h2 if c < c1])
                    elif m == "lm_then_lbfgs":  # une amorce de Nielsen bornee, puis L-BFGS-B
                        x1, c1, n1, h1 = _lm_nielsen(np, resjac, x0, LOWER_NM, geodesic=False, max_iter=HEAD_LM_ITERS)
                        x2, c2, n2, h2 = _lbfgs(np, resjac, x1, LOWER_NM, np.ones(len(x0)))
                        res = (x2, min(c1, c2), n1 + n2, h1 + [(n1 + n, c) for n, c in h2 if c < c1])
                    elif m == "lm_resonance":
                        if not nom.startswith("threeline"):
                            continue
                        res = _lm_resonance(np, engine, seq, x0, LOWER_NM)
                    elif m in ("lm", "lm_geo"):
                        res = _lm(np, resjac, x0, LOWER_NM, geodesic=(m == "lm_geo"))
                    else:
                        res = _lm_nielsen(np, resjac, x0, LOWER_NM, geodesic=(m == "lm_nielsen_geo"))
                    essais[m] = (*res, 1e3 * (time.perf_counter() - t0))
                cible = min(e[1] for m, e in essais.items() if m != "lm_resonance") * 1.001 + 1e-30
                for m, (x_fin, cost, n_eval, hist, ms) in essais.items():
                    lignes[m]["resolved_rmse"].append(fine.rmse(seq, x_fin) if fine is not None else None)
                    lignes[m]["evals"].append(n_eval)
                    lignes[m]["evals_to_target"].append(_evals_to(hist, cible))
                    lignes[m]["final_rmse"].append(float(np.sqrt(cost)))
                    lignes[m]["ms"].append(ms)
            print(f"  sigma {100 * sigma:g} % · {a.starts} departs")
            print(f"  {'methode':<14}{'atteint':>9}{'eval->cible':>13}{'eval total':>12}{'rmse final':>13}{'ms':>9}"
                  f"{'rmse resolu':>13}")
            for m in methodes:
                li = lignes[m]
                if not li["final_rmse"]:
                    continue
                resolu = [v for v in li["resolved_rmse"] if v is not None]
                ok = [v for v in li["evals_to_target"] if v is not None]
                med = float(np.median(ok)) if ok else float("nan")
                print(f"  {m:<14}{len(ok):>6}/{a.starts:<2}{med:>13.0f}{np.median(li['evals']):>12.0f}"
                      f"{np.median(li['final_rmse']):>13.6g}{np.median(li['ms']):>9.0f}"
                      + (f"{np.median(resolu):>13.6g}" if resolu else ""))
            bloc["levels"][f"sigma_{sigma:g}"] = lignes
        sortie["problems"][nom] = bloc
    if a.out:
        print(f"\nconsigne dans {ecrire_json(a.out.resolve(), sortie, racine=ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
