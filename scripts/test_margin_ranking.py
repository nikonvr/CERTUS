"""A/B test : brancher la marge dans le classement final (Poste 5).

    .venv\\Scripts\\python.exe scripts\\test_margin_ranking.py --composant 48c --mode off
    .venv\\Scripts\\python.exe scripts\\test_margin_ranking.py --composant 48c --mode on
    .venv\\Scripts\\python.exe scripts\\test_margin_ranking.py --composant 35c --mode off
    .venv\\Scripts\\python.exe scripts\\test_margin_ranking.py --composant 35c --mode on
    .venv\\Scripts\\python.exe scripts\\test_margin_ranking.py --etat
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    "48c": ("example/example_strat/JSON-strat-example.json", 0.173),
    "35c": ("example/example_strat/JSON-strat-bandpass-3cav.json", 0.482),
}
CACHE = ROOT / "reports" / "test_margin_ranking"
SEED = 42
CRASH_TOL = 0.05
DELTA = 0.051          # resolution du SEEL a N=50


def mesurer(comp: str, actif: bool, execution: str = "fast") -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    cfg, _ = COMPOSANTS[comp]
    t0 = time.perf_counter()
    row: dict = {"composant": comp, "use_margin_ranking": actif, "execution": execution,
                 "verdict": "?",
                 "n_strats": 0, "n_deposables": 0, "crash_min": None,
                 "rmse": None, "seel": None, "margin_in_A": None,
                 "stamp": datetime.now().isoformat(timespec="seconds")}
    try:
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(ROOT / cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText(execution)

        over = {"show_plots": False, "robustness_seed": SEED,
                "monochromator_resolution_nm": 2.0, "search_resolution": False,
                "use_margin_ranking": actif, "execution_mode": execution}
        _c = app.collect_params
        vus = {"n": 0}

        def collect(*ar, **kw):
            p = _c(*ar, **kw)
            p.update(over)
            vus["n"] += 1
            return p

        app.collect_params = collect
        app.run_workflow(23)
        res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None
        row["run_s"] = round(time.perf_counter() - t0, 1)

        if vus["n"] < 2:
            row["verdict"] = "SURCHARGES_NON_APPLIQUEES"
            return row
        strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
        if not strats:
            row["verdict"] = "ECHEC_RESULT_NONE"
            return row

        taux = [float(s.get("crash_rate", 1.0)) for s in strats]
        ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
        row.update({"n_strats": len(strats), "n_deposables": len(ok),
                    "crash_min": round(min(taux) * 100, 2),
                    "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE"})
        if strats:
            best_strat = strats[0]
            sc = float(best_strat.get("robustness_score", 0.0))
            row["rmse"] = sc
            row["seel"] = round(2.0 * math.sqrt(sc), 4) if sc > 0 else None
            cl = best_strat.get("critical_layer") or {}
            row["margin_in_A"] = cl.get("margin_in_A")
            row["best_id"] = best_strat.get("strategy_id")
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:300]
        row["run_s"] = round(time.perf_counter() - t0, 1)
    return row


def etat() -> int:
    print("=" * 82)
    print("A/B TEST : CLASSEMENT PAR LA MARGE (use_margin_ranking)")
    print("=" * 82)
    for comp in COMPOSANTS:
        p_off = CACHE / f"{comp}_off.json"
        p_on = CACHE / f"{comp}_on.json"
        if not p_off.exists() or not p_on.exists():
            print(f"\n{comp} : en attente (off: {p_off.exists()}, on: {p_on.exists()})")
            continue
        roff = json.loads(p_off.read_text(encoding="utf-8"))
        ron = json.loads(p_on.read_text(encoding="utf-8"))
        print(f"\n{comp} :")
        print(f"  OFF (score brut)   : SEEL {roff.get('seel')} nm | crash {roff.get('crash_min')}% | marge {roff.get('margin_in_A')} A | id: {roff.get('best_id')}")
        print(f"  ON  (marge active) : SEEL {ron.get('seel')} nm | crash {ron.get('crash_min')}% | marge {ron.get('margin_in_A')} A | id: {ron.get('best_id')}")
        if roff.get("seel") and ron.get("seel"):
            ec = (ron["seel"] - roff["seel"]) / roff["seel"]
            if abs(ec) <= DELTA:
                print(f"  VERDICT : EGALITE statistique ({ec:+.2%}, sous resolution {DELTA:.1%})")
            else:
                tag = "AMELIORATION" if ec < 0 else "DEGRADATION"
                print(f"  VERDICT : {tag} ({ec:+.2%})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--composant", choices=("48c", "35c"))
    ap.add_argument("--mode", choices=("off", "on"))
    # 🔴 L'A/B du 2026-08-16 a tourne en fast : ecarts +0,46 % et -0,63 %, alors que la
    # resolution y vaut 5,1 %. Il ne pouvait donc PAS detecter un effet reel de 1 a 3 %.
    # En premium (N=150) la resolution tombe a ~3,0 % en SEEL : le test devient capable
    # de trancher. Un ecart sous la resolution reste une EGALITE, jamais un classement.
    ap.add_argument("--exec", dest="execution", default="fast",
                    choices=("fast", "premium", "deep"),
                    help="mode du solveur (defaut fast ; premium pour un test qui tranche)")
    ap.add_argument("--etat", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    if args.etat or not args.composant or not args.mode:
        return etat()

    actif = (args.mode == "on")
    suffixe = "" if args.execution == "fast" else f"_{args.execution}"
    dest = CACHE / f"{args.composant}_{args.mode}{suffixe}.json"
    if dest.exists():
        sys.stderr.write(f"{dest.name} deja mesure." + chr(10))
        return 0
    row = mesurer(args.composant, actif, args.execution)
    dest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{args.composant} ({args.mode}) -> SEEL {row.get('seel')} nm, verdict {row['verdict']}, run_s {row.get('run_s')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
