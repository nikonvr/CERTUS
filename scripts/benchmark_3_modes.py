"""Benchmark exhaustif 35 couches et 48 couches dans les 3 modes : FAST, PREMIUM, DEEP."""

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

import bench_examples as B
from CERTUS_STRAT import CertusStratApp
import math

def score_to_seel_nm(score: float, quantize: bool = True) -> float:
    """Calcul du SEEL à 0.01 nm près."""
    if score is None or score < 0 or math.isnan(score):
        return 0.0
    seel = 2.0 * math.sqrt(score)
    if quantize:
        return round(seel * 100.0) / 100.0
    return seel


def log_print(msg: str):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()


def run_single_mode(stack_path: str, mode: str):
    name = Path(stack_path).name
    log_print("\n" + "=" * 80)
    log_print(f"BENCHMARK: {name} | MODE: {mode.upper()}")
    log_print("=" * 80)

    B.qapp()
    B.autoanswer_dialogs(True)

    app = CertusStratApp()
    app.load_configuration(str(ROOT / stack_path))
    B.attach_console_logging(app)

    if "execution_mode" in app.widgets:
        app.widgets["execution_mode"].setCurrentText(mode)

    params = app.collect_params()
    params["execution_mode"] = mode
    params["show_plots"] = False

    log_print(
        f"Configuration appliquée ({mode.upper()}) :\n"
        f"  * dp_top_k = {params.get('dp_top_k')}\n"
        f"  * k_keep_survivors = {params.get('k_keep_survivors')}\n"
        f"  * n_screen_runs = {params.get('n_screen_runs')}\n"
        f"  * robustness_num_runs = {params.get('robustness_num_runs')}\n"
        f"  * elite_rounds = {params.get('elite_rounds')}"
    )

    t0 = time.perf_counter()
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None
    elapsed = time.perf_counter() - t0

    best_strat = {}
    best_rmse = None
    best_crash = None
    best_blocks = None
    best_seel_quant = None
    best_seel_cont = None
    total_strats = 0

    if res and isinstance(res, dict):
        final_results = res.get("final_results", {})
        strats = final_results.get("all_strategies_results", [])
        total_strats = len(strats)
        if strats:
            best = strats[0]
            best_rmse = best.get("robustness_score", None)
            best_crash = best.get("crash_rate", 0.0)
            best_strat = best.get("strategy", {})
            best_blocks = best_strat.get("n_blocks", len(best_strat.get("blocks", [])))
            if best_rmse is not None:
                best_seel_quant = score_to_seel_nm(best_rmse, quantize=True)
                best_seel_cont = score_to_seel_nm(best_rmse, quantize=False)

    log_print(
        f"\n---> {name} [{mode.upper()}] TERMINÉ en {elapsed:.2f} s\n"
        f"     Optimum : {best_blocks} blocs | RMSE P95 = {best_rmse:.5f} | Crash = {best_crash*100:.1f}%\n"
        f"     SEEL (quantifié 0.1nm) = {best_seel_quant:.1f} nm (continu {best_seel_cont:.2f} nm)\n"
        f"     Total stratégies évaluées = {total_strats}"
    )

    return {
        "component": "48c (Dichroïque)" if "example" in name else "35c (Passe-bande)",
        "file": name,
        "mode": mode.upper(),
        "duration_s": round(elapsed, 2),
        "best_blocks": best_blocks,
        "rmse_p95": round(best_rmse, 5) if best_rmse is not None else None,
        "seel_0p1nm": best_seel_quant,
        "seel_cont_nm": round(best_seel_cont, 3) if best_seel_cont is not None else None,
        "crash_rate_pct": round(best_crash * 100, 1) if best_crash is not None else None,
        "total_strats": total_strats,
    }


def main():
    runs = [
        ("example/example_strat/JSON-strat-example.json", "fast"),
        ("example/example_strat/JSON-strat-example.json", "premium"),
        ("example/example_strat/JSON-strat-example.json", "deep"),
        ("example/example_strat/JSON-strat-bandpass-3cav.json", "fast"),
        ("example/example_strat/JSON-strat-bandpass-3cav.json", "premium"),
        ("example/example_strat/JSON-strat-bandpass-3cav.json", "deep"),
    ]

    all_results = []
    for path, mode in runs:
        res = run_single_mode(path, mode)
        all_results.append(res)

    log_print("\n" + "=" * 80)
    log_print("TABLEAU RÉCAPITULATIF DES 3 MODES SUR 35C ET 48C")
    log_print("=" * 80)

    import pandas as pd
    df = pd.DataFrame(all_results)
    log_print(df.to_string(index=False))

    # Save to JSON for report integration
    out_json = ROOT / "reports" / "benchmark_3_modes_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    log_print(f"\nRésultats sauvegardés dans {out_json}")


if __name__ == "__main__":
    main()
