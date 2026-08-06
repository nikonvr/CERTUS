"""L'erreur spectrale statistique finale, decomposee par bande.

Un RMSE global sur un dichroique ne dit rien : il est domine par le front raide, ou un
deplacement de quelques nanometres produit une variation de T enorme. Ce qui compte pour un
fabricant est different selon la bande :

  400-540 nm  bande passante  ~95 % de T   -> un ecart de 1 point est negligeable
  544-552 nm  front raide                  -> l'ecart mesure un DECALAGE du front
  555-700 nm  bande bloquee   < 0,1 % de T -> un ecart de 0,1 point est DEJA hors spec

On capture donc les epaisseurs reellement simulees (thicknesses_all), on recalcule le spectre
de chaque tirage, et on rend la distribution de l'ecart PAR BANDE — plus le decalage du front,
qui est la vraie grandeur physique sur un dichroique.

    .venv/Scripts/python.exe scripts/probe_spectral_error.py

N'ecrit rien hors reports/. Ne touche a aucun code de production.
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

OUT = ROOT / "reports" / "probe_spectral_error.json"
OPTICS: dict = {}
CAPTURED: list[dict] = []
MAX_STRAT = 12


def install_probe() -> None:
    import numpy as np

    import certus.core.certus_strat_robustness as R
    import certus.workers.certus_strat_workers as W

    orig_opt = R._prepare_robustness_nominal_optics

    def patched_opt(*a, **kw):
        out = orig_opt(*a, **kw)
        if not OPTICS:
            wl, nH, nL, nSub, T_nom = out
            OPTICS.update(
                wl=np.asarray(wl, dtype=np.float64), nH=np.asarray(nH), nL=np.asarray(nL),
                nSub=np.asarray(nSub), T_nom=np.asarray(T_nom, dtype=np.float64),
                p_thick=np.asarray(a[1] if len(a) > 1 else kw["p_thick_nominal"], dtype=np.float64),
            )
            B.emit(f"optiques : {OPTICS['wl'].size} lambda de {OPTICS['wl'][0]:.0f} a {OPTICS['wl'][-1]:.0f} nm")
        return out

    R._prepare_robustness_nominal_optics = patched_opt

    orig_blk = W.run_final_simulation_block

    def patched_blk(*a, **kw):
        out = orig_blk(*a, **kw)
        try:
            items = (out or {}).get("all_strategies_results") if isinstance(out, dict) else None
            for it in items or []:
                if len(CAPTURED) >= MAX_STRAT or not isinstance(it, dict):
                    continue
                per = it.get("results_per_noise") or []
                if not per:
                    continue
                lv = sorted(per, key=lambda r: float(r.get("noise_level", 0.0)))
                r = lv[len(lv) // 2]           # niveau de bruit NOMINAL
                th = r.get("thicknesses_all")
                if not th or len(th) < 10:
                    continue
                st = it.get("strategy") or {}
                CAPTURED.append({
                    "id": st.get("strategy_id"), "n_blocks": st.get("n_blocks"),
                    "score": it.get("robustness_score"), "crash": it.get("crash_rate"),
                    "noise": r.get("noise_level"), "thick": np.asarray(th, dtype=np.float64),
                })
        except Exception as exc:  # noqa: BLE001
            B.emit(f"PROBE_CAPTURE_FAILED={exc!r}")
        return out

    W.run_final_simulation_block = patched_blk
    B.emit("sonde installee")


def analyse() -> dict:
    import numpy as np
    from certus_physics import calculate_RT_batch_kernel

    wl = OPTICS["wl"]
    nH, nL, nSub = OPTICS["nH"], OPTICS["nL"], OPTICS["nSub"]
    d0 = OPTICS["p_thick"]
    _, T_nom = calculate_RT_batch_kernel(wl, nH, nL, nSub, d0.reshape(1, -1))
    T_nom = np.asarray(T_nom, dtype=np.float64)[0]

    # bandes du dichroique, lues sur le spectre nominal lui-meme
    pass_m = (wl >= 400) & (wl <= 540)
    edge_m = (wl > 540) & (wl < 560)
    stop_m = (wl >= 560)
    B.emit(f"bandes : passante {pass_m.sum()} pts | front {edge_m.sum()} | bloquee {stop_m.sum()}")
    B.emit(f"T nominal : passante {T_nom[pass_m].mean()*100:.2f} % | bloquee max {T_nom[stop_m].max()*100:.4f} %")

    def q(a, p):
        return float(np.percentile(a, p))

    rows = []
    for c in CAPTURED:
        D = c["thick"]
        keep = ~np.any(np.abs(D) > 1e4, axis=1)     # ecarte les runs plantes (sentinelle 1e6)
        if keep.sum() < 8:
            continue
        _, T = calculate_RT_batch_kernel(wl, nH, nL, nSub, D[keep])
        T = np.asarray(T, dtype=np.float64)          # (n_runs, n_wl)
        E = T - T_nom[None, :]

        def band(mask):
            rmse = np.sqrt(np.mean(E[:, mask] ** 2, axis=1))
            return {"rmse_median": q(rmse, 50), "rmse_p95": q(rmse, 95),
                    "max_abs_median": q(np.max(np.abs(E[:, mask]), axis=1), 50),
                    "max_abs_p95": q(np.max(np.abs(E[:, mask]), axis=1), 95)}

        # decalage du front : lambda ou T croise 50 % du saut, par run
        lo, hi = T_nom[stop_m].mean(), T_nom[pass_m].mean()
        half = 0.5 * (lo + hi)
        idx_nom = int(np.argmin(np.abs(T_nom - half) + 1e6 * (~edge_m)))
        wl_nom = float(wl[idx_nom])
        shifts = []
        for k in range(T.shape[0]):
            i = int(np.argmin(np.abs(T[k] - half) + 1e6 * (~edge_m)))
            shifts.append(float(wl[i]) - wl_nom)
        shifts = np.asarray(shifts)

        rows.append({
            "id": c["id"], "n_blocks": c["n_blocks"], "score": c["score"], "crash": c["crash"],
            "n_runs_ok": int(keep.sum()), "n_runs_total": int(D.shape[0]),
            "global": band(np.ones_like(wl, dtype=bool)),
            "passante": band(pass_m), "front": band(edge_m), "bloquee": band(stop_m),
            "front_wl_nominal": wl_nom,
            "front_shift_nm": {"median": q(shifts, 50), "p05": q(shifts, 5), "p95": q(shifts, 95),
                               "abs_p95": q(np.abs(shifts), 95)},
        })
    return {"n": len(rows), "strategies": rows}


def main() -> None:
    B.qapp()
    B.autoanswer_dialogs(True)
    from certus_physics import calculate_RT_batch_kernel  # noqa: F401  echec immediat si absent
    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")
    if not CAPTURED or not OPTICS:
        B.emit(f"PROBE_INCOMPLETE captured={len(CAPTURED)} optics={bool(OPTICS)}")
        sys.stdout.flush(); os._exit(0)

    r = analyse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={OUT}  strategies={r['n']}")
    B.emit("")
    B.emit("  ERREUR SPECTRALE, en POINTS DE TRANSMISSION (x100 = %)")
    B.emit("  id        nb  crash | RMSE global med/p95 | passante p95 | FRONT p95 | BLOQUEE p95 max|E| | decalage front p95")
    for s in r["strategies"][:8]:
        g, pa, fr, st = s["global"], s["passante"], s["front"], s["bloquee"]
        B.emit(
            f"  {str(s['id'])[:9]:>9} {s['n_blocks']:>2} {s['crash']:.3f} | "
            f"{g['rmse_median']*100:6.3f}/{g['rmse_p95']*100:6.3f} | "
            f"{pa['rmse_p95']*100:7.3f} | {fr['rmse_p95']*100:8.3f} | "
            f"{st['rmse_p95']*100:7.4f} {st['max_abs_p95']*100:7.4f} | "
            f"{s['front_shift_nm']['abs_p95']:6.2f} nm"
        )
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
