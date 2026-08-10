"""The final statistical spectral error, broken down by band.

A global RMSE on a dichroic says nothing: it is dominated by the steep front, or a
displacement of a few nanometers produces an enormous variation of T. What counts for a
fabricant est different selon la bande :

  400-540 nm  bande passante  ~95 % de T   -> un ecart de 1 point est negligeable
  544-552 nm  front raide                  -> l'ecart mesure un DECALAGE du front
  555-700 nm  bande bloquee   < 0,1 % de T -> un ecart de 0,1 point est DEJA hors spec

We therefore capture the thicknesses actually simulated (thicknesses_all), we recalculate the spectrum
de chaque tirage, et on rend la distribution de l'ecart PAR BANDE — plus le decalage du front,
qui est la vraie grandeur physique sur un dichroique.

    .venv/Scripts/python.exe scripts/probe_spectral_error.py

Does not write anything except reports/. Do not touch any production codes.
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

#: Lightweight record of EVERY strategy the pipeline scored -- id, blocks, score,
#: crash rate, runs. A few dozen bytes each, so there is no reason to cap it.
#:
#: 🔴 WHY THIS EXISTS. `CAPTURED` keeps the first MAX_STRAT strategies **in iteration
#: order**, not the best ones. It is an arbitrary PREFIX. Reading a ranking out of it
#: -- "which strategy wins", "does the winner change with N", "does Phase A discard
#: what Phase B would crown" -- measures the capture order and nothing else, and it
#: does so while producing a perfectly readable curve. The winner of 10 is a 2-block
#: strategy that appears in no report for exactly this reason.
#:
#: So: RANKING keeps everything and is the only thing a ranking question may be asked
#: of; CAPTURED keeps the heavy per-run thickness matrices for a bounded few, which is
#: all the spectral band analysis needs.
RANKING: list[dict] = []


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

    # SEEL is already computed in the headless path, so capture it rather than
    # recompute it: the calibration is not free (900 spectra) and recomputing would
    # also risk drawing a different one.
    try:
        import certus.utils.certus_strat_service as S

        orig_seel = S.calculate_seel_analysis

        def patched_seel(*a, **kw):
            data = orig_seel(*a, **kw)
            if isinstance(data, dict) and "seel" not in OPTICS:
                OPTICS["seel"] = dict(data)
                B.emit(f"SEEL capture : fit_k={data.get('fit_k')} alpha={data.get('fit_alpha')}")
            return data

        S.calculate_seel_analysis = patched_seel
    except Exception as exc:  # noqa: BLE001 -- the readout must never break the run
        B.emit(f"PROBE_SEEL_HOOK_FAILED={exc!r}")

    orig_blk = W.run_final_simulation_block

    def patched_blk(*a, **kw):
        out = orig_blk(*a, **kw)
        try:
            items = (out or {}).get("all_strategies_results") if isinstance(out, dict) else None
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                st = it.get("strategy") or {}
                per = it.get("results_per_noise") or []

                # Every strategy, unconditionally. This is what a ranking may be read
                # from -- and the ONLY thing that may.
                RANKING.append({
                    "id": st.get("strategy_id"),
                    "n_blocks": st.get("n_blocks"),
                    "score": it.get("robustness_score"),
                    "crash": it.get("crash_rate"),
                    "wavelengths": [float(b.get("wavelength", 0.0)) for b in (st.get("blocks") or [])],
                    "n_runs_ok": max((int(r.get("n_runs_ok", 0)) for r in per), default=0),
                    "n_runs_total": max((int(r.get("n_runs_total", 0)) for r in per), default=0),
                })

                # Heavy part: the per-run thickness matrices the band analysis needs.
                # Bounded, and explicitly a SAMPLE -- never a ranking.
                if len(CAPTURED) >= MAX_STRAT or not per:
                    continue
                lv = sorted(per, key=lambda r: float(r.get("noise_level", 0.0)))
                r = lv[len(lv) // 2]           # niveau de bruit NOMINAL
                th = r.get("thicknesses_all")
                if not th or len(th) < 10:
                    continue
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

    #dichroic bands, read on the nominal spectrum itself
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
    # The ranking, sorted by the score the pipeline itself used, best first. This is
    # the only field a ranking question may be asked of -- `strategies` below is a
    # bounded sample kept in capture order, not a ranking. See RANKING's comment.
    ranked = sorted(
        (r for r in RANKING if r.get("score") is not None),
        key=lambda r: float(r["score"]),
    )
    return {
        "n": len(rows),
        "strategies": rows,
        "n_ranked": len(ranked),
        "ranking": ranked,
        "winner": ranked[0] if ranked else None,
    }


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
