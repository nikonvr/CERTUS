"""What is missing from the cost of PD: sensitivities, or covariance?

Mesure du 2026-08-05 : rho(total_cost, robustness_score) = -0,04. Le cout de la DP ne predit
not the spectral response. It remains to be seen WHY, and the answer decides the entire project.

To first order, delta_T(lambda) = sum_i S_i(lambda) . delta_d_i , so

    Var[delta_T(lambda)] = somme_i somme_j S_i(lambda) S_j(lambda) Cov[delta_d_i, delta_d_j]

The current cost is sum_i P95(|delta_d_i|): it only uses the DIAGONAL, in value
absolute, without spectral weighting. Two ingredients are missing. We add them ONE BY ONE:

    cout_0 = somme_i P95(|delta_d_i|)               le cout actuel
    cost_1 = sum_i ||S_i|| . P95(|delta_d_i|) + sensitivities, ALWAYS diagonal
    cout_2 = sqrt( moy_lambda Var[delta_T_lin] )    + covariance : le modele lineaire complet
    verite = robustness_score  (Monte-Carlo, TMM complet)

VERDICT ATTENDU :
  rho(cout_1) high -> only the sensitivities were missing. A SEPARABLE cost, therefore
                        compatible with the DP as it is, can work.
  rho(cout_1) nul et rho(cout_2) eleve
                     -> it is the COVARIANCE which carries the information, that is to say
                        self-compensation. No diagonal cost will ever work, and the DP
                        must carry an error status or give up classifying.
  rho(cout_2) faible -> le modele lineaire lui-meme ne tient pas ; tout raisonnement
                        analytique sur la propagation est a jeter.

We also measure rho(rmse_lin, rmse_true): the validity of the linearization, prior to everything.

    .venv/Scripts/python.exe scripts/probe_cost_decomposition.py

Does not write anything except reports/. Does not modify any behavior.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402

OUT = ROOT / "reports" / "probe_cost_decomposition.json"
MAX_STRAT = 200
OPTICS: dict = {}
CAPTURED: list[dict] = []


def install_probe() -> None:
    import numpy as np

    import certus.core.certus_strat_robustness as R
    import certus.workers.certus_strat_workers as W

    #--- 1. capture nominal optical arrays (once) ----------------------
    orig_optics = R._prepare_robustness_nominal_optics

    def patched_optics(*a, **kw):
        out = orig_optics(*a, **kw)
        if not OPTICS:
            wl_arr, nH, nL, nSub, T_nom = out
            OPTICS.update(
                wl=np.asarray(wl_arr, dtype=np.float64),
                nH=np.asarray(nH),
                nL=np.asarray(nL),
                nSub=np.asarray(nSub),
                T_nom=np.asarray(T_nom, dtype=np.float64),
                p_thick=np.asarray(a[1] if len(a) > 1 else kw.get("p_thick_nominal"), dtype=np.float64),
            )
            B.emit(f"optiques captees : {OPTICS['wl'].size} lambda, {OPTICS['p_thick'].size} couches")
        return out

    R._prepare_robustness_nominal_optics = patched_optics

    # --- 2. capter les epaisseurs simulees, au niveau de bruit nominal -------------
    orig_block = W.run_final_simulation_block

    def patched_block(*a, **kw):
        out = orig_block(*a, **kw)
        try:
            items = out.get("all_strategies_results") if isinstance(out, dict) else None
            for it in items or []:
                if len(CAPTURED) >= MAX_STRAT or not isinstance(it, dict):
                    continue
                strat = it.get("strategy") or {}
                per_noise = it.get("results_per_noise") or []
                if not per_noise:
                    continue
                # niveau de bruit NOMINAL = le median des niveaux testes (facteurs 0,5/1/2)
                lv = sorted(per_noise, key=lambda r: float(r.get("noise_level", 0.0)))
                r = lv[len(lv) // 2]
                th = r.get("thicknesses_all")
                if not th or len(th) < 10:
                    continue
                CAPTURED.append(
                    {
                        "strategy_id": strat.get("strategy_id"),
                        "n_blocks": strat.get("n_blocks"),
                        "total_cost": strat.get("total_cost"),
                        "robustness_score": it.get("robustness_score"),
                        "crash_rate": it.get("crash_rate"),
                        "noise_level": r.get("noise_level"),
                        "thick": np.asarray(th, dtype=np.float32),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - une sonde ne tue jamais le calcul
            B.emit(f"PROBE_CAPTURE_FAILED={exc!r}")
        return out

    W.run_final_simulation_block = patched_block
    B.emit("sonde installee (optiques + epaisseurs simulees)")


def sensitivity_matrix(delta_nm: float = 0.1):
    """S[lambda, i] = dT(lambda)/dd_i, par differences finies centrees."""
    import numpy as np

    from certus_physics import calculate_RT_vectorized_real_HL

    wl = OPTICS["wl"]
    nH, nL, nSub = OPTICS["nH"], OPTICS["nL"], OPTICS["nSub"]
    d0 = OPTICS["p_thick"].astype(np.float64)
    n_layers = d0.size

    S = np.empty((wl.size, n_layers), dtype=np.float64)
    for i in range(n_layers):
        dp, dm = d0.copy(), d0.copy()
        dp[i] += delta_nm
        dm[i] -= delta_nm
        _, Tp = calculate_RT_vectorized_real_HL(wl, nH, nL, nSub, dp)
        _, Tm = calculate_RT_vectorized_real_HL(wl, nH, nL, nSub, dm)
        S[:, i] = (np.asarray(Tp, dtype=np.float64) - np.asarray(Tm, dtype=np.float64)) / (2.0 * delta_nm)
    return S


def analyse() -> dict:
    import numpy as np
    from scipy import stats

    S = sensitivity_matrix()  # (n_wl, n_layers)
    w_layer = np.linalg.norm(S, axis=0)  # ||S_i|| : poids de sensibilite par couche
    d0 = OPTICS["p_thick"].astype(np.float64)

    rows = []
    for c in CAPTURED:
        score = c.get("robustness_score")
        cost0_dp = c.get("total_cost")
        if score is None or cost0_dp is None:
            continue
        score, cost0_dp = float(score), float(cost0_dp)
        if not (np.isfinite(score) and np.isfinite(cost0_dp) and score > 0):
            continue

        D = c["thick"].astype(np.float64) - d0[None, :]  # (n_runs, n_layers)
        if D.shape[1] != d0.size:
            continue
        # les runs plantes portent la sentinelle 1e6 : on les ecarte
        keep = ~np.any(np.abs(D) > 1e4, axis=1)
        if keep.sum() < 8:
            continue
        D = D[keep]

        p95_abs = np.percentile(np.abs(D), 95, axis=0)  # (n_layers,)
        cout_0 = float(np.sum(p95_abs))
        cout_1 = float(np.sum(w_layer * p95_abs))

        dT = D @ S.T  # (n_runs, n_wl) — modele lineaire
        cout_2 = float(np.sqrt(np.mean(np.var(dT, axis=0))))
        rmse_lin = np.sqrt(np.mean(dT**2, axis=1))  # (n_runs,)
        k = max(1, int(np.ceil(0.05 * rmse_lin.size)))
        cvar_lin = float(np.mean(np.sort(rmse_lin)[-k:]))

        rows.append(
            {
                "n_blocks": c.get("n_blocks"),
                "score": score,
                "cost_dp": cost0_dp,
                "cout_0": cout_0,
                "cout_1": cout_1,
                "cout_2": cout_2,
                "cvar_lin": cvar_lin,
            }
        )

    def _rho(xs, ys):
        if len(xs) < 8:
            return None
        r = stats.spearmanr(xs, ys)
        return {"rho": float(r.statistic), "p": float(r.pvalue), "n": len(xs)}

    by_nb: dict = {}
    for r in rows:
        by_nb.setdefault(r["n_blocks"], []).append(r)

    groups = []
    for nb, rs in sorted(by_nb.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < 8:
            continue
        y = [r["score"] for r in rs]
        groups.append(
            {
                "n_blocks": nb,
                "n": len(rs),
                "rho_cost_dp": _rho([r["cost_dp"] for r in rs], y),
                "rho_cout_0_somme_p95": _rho([r["cout_0"] for r in rs], y),
                "rho_cout_1_avec_sensibilites": _rho([r["cout_1"] for r in rs], y),
                "rho_cout_2_avec_covariance": _rho([r["cout_2"] for r in rs], y),
                "rho_cvar_lineaire": _rho([r["cvar_lin"] for r in rs], y),
            }
        )

    return {"n_strategies": len(rows), "groupes": groups}


def main() -> None:
    B.qapp()
    B.autoanswer_dialogs(True)

    #IMMEDIATE FAILURE. A first version imported calculate_RT_vectorized_real_HL
    #from the wrong module; the ImportError only occurred AFTER the calculation and
    #costs an hour. Everything the analysis needs is checked BEFORE running
    #anything.
    from certus_physics import calculate_RT_vectorized_real_HL  # noqa: F401
    from scipy import stats  # noqa: F401

    B.emit("dependances de l'analyse verifiees avant le calcul")

    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")

    if not CAPTURED or not OPTICS:
        B.emit(f"PROBE_INCOMPLETE captured={len(CAPTURED)} optics={bool(OPTICS)}")
        sys.stdout.flush()
        os._exit(0)

    r = analyse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={OUT}   strategies={r['n_strategies']}")
    B.emit("")
    B.emit("  rho de Spearman avec le VRAI score (robustness_score), par n_blocks")
    B.emit("  cout_0 = somme P95|dd|   cout_1 = + sensibilites (diagonal)   cout_2 = + covariance")
    for g in r["groupes"]:
        def _f(k):
            v = g[k]
            return f"{v['rho']:+.3f}" if v else "  n/a "

        B.emit(
            f"  n_blocks={g['n_blocks']:>2} n={g['n']:>3} | "
            f"cost_dp={_f('rho_cost_dp')} cout_0={_f('rho_cout_0_somme_p95')} "
            f"cout_1={_f('rho_cout_1_avec_sensibilites')} "
            f"cout_2={_f('rho_cout_2_avec_covariance')} "
            f"cvar_lin={_f('rho_cvar_lineaire')}"
        )

    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
