"""« AUCUNE_DEPOSABLE » VEUT-IL DIRE « INFAISABLE » ? Non, et [0,66) le prouve.

    .venv\\Scripts\\python.exe scripts\\verif_66_vs_68.py --mode premium

👤 2026-08-15 : *« comment 0-68 peut-il etre deposable 39 fois alors que 0-66 ne trouve
aucun ? Les 39 strategies ne peuvent etre appliquees au 0-66 ??? »*

🔴 L'ARGUMENT DE 👤 EST UNE PREUVE, ET IL FAUT LE LIRE COMME TELLE.

La surveillance de la couche i ne depend QUE des couches 0..i : le signal est celui du
temoin portant les couches deja deposees plus celle qui pousse. Les trois causes de plantage
-- CRASH_LEVEL_UNREACHABLE, CRASH_TP_MISCOUNT, CRASH_NON_MONOTONIC -- sont toutes
per-couche et determinees par 0..i. Le niveau de declenchement lui-meme est calcule sur
l'empilement NOMINAL 0..i (Macleod-Bousquet).

Donc : prendre une strategie de [0,68) qui depose a 0 % de plantage et la TRONQUER apres la
couche 65 donne une strategie de [0,66) qui depose a 0 % de plantage. La troncature ne peut
pas degrader : les couches 0..65 vivent exactement la meme histoire.

    [0,68) a 39 strategies a 0 %  =>  [0,66) en a AU MOINS 39.
    La campagne en rapporte 0. La campagne a donc TORT.

Et les deux runs ne different par rien d'autre : meme jour, meme commit 1f24413, meme
graine 42, meme tranche de bruit (offset 0 sur 99), meme grille spectrale, meme mode fast.

🔑 CONCLUSION QUI EN DECOULE, ET ELLE PORTE SUR TOUTE LA CAMPAGNE :

    « AUCUNE_DEPOSABLE » ne signifie PAS « infaisable ».
    Il signifie « LE SOLVEUR N'EN A PAS TROUVE ».

C'est une defaillance de RECHERCHE, pas de physique. La DP de Phase B optimise un COUT
(celui de Phase A), pas le taux de plantage : elle peut donc conduire ses `top_k`
groupements dans une region ou tout plante, alors qu'une autre region viable existe.
Deux couches de plus deplacent l'optimum de la DP et la font atterrir ailleurs.

## Ce que ce script mesure

Relancer [0,66) avec un budget de recherche PLUS GRAND, tout le reste egal. Si des
strategies deposables apparaissent, la defaillance de recherche est confirmee par
l'experience et pas seulement par le raisonnement.

    fast    : N=50,  dp_top_k=20   <- ce qu'a fait la campagne, verdict 0/319
    premium : N=150, dp_top_k=40
    deep    : N=300, dp_top_k=100

⚠️ Le taux de plantage lu sous fast est quantifie a 10 % (criblage a 10 tirages) : un
« 0,0 % » y veut dire « sous 10 % ». Sous premium il est lisible.
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

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CACHE = ROOT / "reports" / "intervalles_99c"
OUT = ROOT / "reports" / "verif_66_vs_68"
SEED = 42
CRASH_TOL = 0.05
N_LAYERS = 99


def mesurer(a: int, b: int, mode: str) -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    t0 = time.perf_counter()
    row: dict = {"a": a, "b": b, "n": b - a, "mode": mode, "verdict": "?",
                 "n_strats": 0, "n_deposables": 0, "crash_min": None, "seel": None,
                 "stamp": datetime.now().isoformat(timespec="seconds")}
    try:
        cfg = CACHE / f"cfg_{a:03d}_{b:03d}.json"
        if not cfg.exists():
            row["verdict"] = "CONFIG_ABSENTE"
            return row
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText(mode)

        # 🔑 IDENTIQUE A LA CAMPAGNE, sauf le mode. La tranche de bruit surtout : sans
        # elle le flux repart a zero et la comparaison ne porte plus sur la meme chose.
        over = {"show_plots": False, "robustness_seed": SEED,
                "monochromator_resolution_nm": 2.0, "search_resolution": False,
                "noise_layer_offset": a, "noise_total_layers": N_LAYERS,
                "execution_mode": mode}
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
            row["verdict"] = "ECHEC_RESULT_NONE"      # 🔴 pas « aucune strategie »
            return row

        taux = [float(s.get("crash_rate", 1.0)) for s in strats]
        ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
        ok.sort(key=lambda s: float(s.get("robustness_score", 1e18)))
        row.update({"n_strats": len(strats), "n_deposables": len(ok),
                    "crash_min": round(min(taux) * 100, 2),
                    "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE"})
        if ok:
            sc = float(ok[0].get("robustness_score", 0.0))
            row["seel"] = round(2.0 * math.sqrt(sc), 4) if sc > 0 else None
            row["blocs"] = len(ok[0].get("blocks") or [])
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:300]
        row["run_s"] = round(time.perf_counter() - t0, 1)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalle", default="0,66")
    ap.add_argument("--mode", default="premium", choices=("fast", "premium", "deep"))
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    a, b = (int(x) for x in args.intervalle.split(","))
    row = mesurer(a, b, args.mode)
    dest = OUT / f"i_{a:03d}_{b:03d}_{args.mode}.json"
    dest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")

    ref = json.loads((CACHE / f"i_{a:03d}_{b:03d}.json").read_text(encoding="utf-8"))
    print(f"\n[{a},{b}) en fast (campagne) : {ref['verdict']} "
          f"{ref['n_deposables']}/{ref['n_strats']}, plantage min {ref['crash_min']} %")
    print(f"[{a},{b}) en {args.mode:8s}      : {row['verdict']} "
          f"{row['n_deposables']}/{row['n_strats']}, plantage min {row['crash_min']} %")
    if row["n_deposables"] > 0 and ref["n_deposables"] == 0:
        print("\nVERDICT : DEFAILLANCE DE RECHERCHE CONFIRMEE.")
        print("  « AUCUNE_DEPOSABLE » en fast ne veut pas dire infaisable.")
    elif row["verdict"] == "AUCUNE_DEPOSABLE":
        print("\nVERDICT : toujours rien avec plus de budget. L'argument de troncature")
        print("  reste valide en theorie -- donc chercher AILLEURS que dans le budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
