"""Lancement de STRAT sur le filtre 5 cavités 99 couches en mode DEEP Extrême."""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import math

import numpy as np

import bench_examples as B
from CERTUS_STRAT import CertusStratApp


def score_to_seel_nm(score: float, quantize: bool = True) -> float:
    if score is None or score < 0 or math.isnan(score):
        return 0.0
    seel = 2.0 * math.sqrt(score)
    if quantize:
        return round(seel * 100.0) / 100.0
    return seel


def main():
    json_rel = "example/example_strat/JSON-strat-bandpass-5cav-99c-deep.json"
    json_path = ROOT / json_rel

    sys.stderr.write("=" * 80 + "\n")
    sys.stderr.write(f"LANCEMENT DU SOLVEUR STRAT : 5 CAVITÉS 99 COUCHES [MODE DEEP EXTRÊME]\n")
    sys.stderr.write(f"Configuration : {json_path.name}\n")
    sys.stderr.write("=" * 80 + "\n\n")

    B.qapp()
    B.autoanswer_dialogs(True)

    app = CertusStratApp()
    app.load_configuration(str(json_path))
    B.attach_console_logging(app)

    params = app.collect_params()
    params["show_plots"] = False
    mode = params.get("execution_mode", "deep")

    sys.stderr.write(
        f"Paramètres du solveur ({mode.upper()}) :\n"
        f"  * dp_top_k             : {params.get('dp_top_k')}\n"
        f"  * k_keep_survivors     : {params.get('k_keep_survivors')}\n"
        f"  * n_screen_runs        : {params.get('n_screen_runs')}\n"
        f"  * robustness_num_runs  : {params.get('robustness_num_runs')}\n"
        f"  * mining_limit         : {params.get('mining_candidates_limit')}\n"
        f"  * elite_rounds         : {params.get('elite_rounds')}\n"
        f"  * allow_rate           : {params.get('allow_rate')}\n"
        f"  * search_resolution    : {params.get('search_resolution')}\n\n"
    )

    t0 = time.perf_counter()
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None
    elapsed = time.perf_counter() - t0

    sys.stderr.write("\n" + "=" * 80 + "\n")
    sys.stderr.write(f"SOLVEUR STRAT TERMINÉ en {elapsed:.2f} s ({elapsed/60:.2f} min)\n")
    sys.stderr.write("=" * 80 + "\n")

    if res and isinstance(res, dict):
        final_results = res.get("final_results", {})
        strats = final_results.get("all_strategies_results", [])
        sys.stderr.write(f"Nombre total de stratégies évaluées : {len(strats)}\n\n")

        if strats:
            best = strats[0]
            best_rmse = best.get("robustness_score", None)
            best_crash = best.get("crash_rate", 0.0)
            best_strat = best.get("strategy", {})
            best_blocks = best_strat.get("n_blocks", len(best_strat.get("blocks", [])))
            best_id = best_strat.get("id", "N/A")
            origin = best_strat.get("origin", "N/A")

            seel_q = score_to_seel_nm(best_rmse, quantize=True)
            seel_c = score_to_seel_nm(best_rmse, quantize=False)

            sys.stderr.write("=== MEILLEURE STRATÉGIE RETENUE (MODE DEEP) ===\n")
            sys.stderr.write(f"  * ID Stratégie     : {best_id} (Origine: {origin})\n")
            sys.stderr.write(f"  * Découpage        : {best_blocks} blocs\n")
            sys.stderr.write(f"  * RMSE Robuste P95 : {best_rmse:.6f}\n")
            sys.stderr.write(f"  * SEEL (0.01 nm)   : {seel_q:.2f} nm (continu {seel_c:.3f} nm)\n")
            sys.stderr.write(f"  * Taux de Plantage : {best_crash * 100:.1f} %\n\n")

            sys.stderr.write("Top 5 Stratégies :\n")
            for i, st in enumerate(strats[:5]):
                s_strat = st.get("strategy", {})
                s_rmse = st.get("robustness_score", 0.0)
                s_crash = st.get("crash_rate", 0.0)
                s_blocks = s_strat.get("n_blocks", len(s_strat.get("blocks", [])))
                s_id = s_strat.get("id", "N/A")
                s_orig = s_strat.get("origin", "N/A")
                sys.stderr.write(
                    f"  #{i+1}: ID={s_id:<6} | {s_orig:<10} | {s_blocks} blocs | "
                    f"RMSE={s_rmse:.5f} | SEEL={score_to_seel_nm(s_rmse):.2f} nm | Crash={s_crash*100:.1f}%\n"
                )

            # Save results report JSON
            out_json = ROOT / "reports" / "run_strat_5cav_99c_deep_results.json"
            summary_data = {
                "component": "5-Cavity 99 Layers Bandpass (DEEP Mode)",
                "duration_s": round(elapsed, 2),
                "total_strats": len(strats),
                "best_strategy": {
                    "id": best_id,
                    "origin": origin,
                    "n_blocks": best_blocks,
                    "rmse_p95": best_rmse,
                    "seel_nm": seel_q,
                    "crash_rate_pct": best_crash * 100,
                    "strategy_details": best_strat,
                },
                "top5": [
                    {
                        "id": s.get("strategy", {}).get("id"),
                        "origin": s.get("strategy", {}).get("origin"),
                        "n_blocks": s.get("strategy", {}).get("n_blocks"),
                        "rmse": s.get("robustness_score"),
                        "crash_rate": s.get("crash_rate"),
                    }
                    for s in strats[:5]
                ],
            }
            def _json_default(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (np.floating, np.integer)):
                    return obj.item()
                return str(obj)

            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2, default=_json_default)
            sys.stderr.write(f"\nRapport détaillé sauvegardé dans : {out_json}\n")


if __name__ == "__main__":
    main()
