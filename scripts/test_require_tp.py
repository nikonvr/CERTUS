"""A/B : exiger un point tournant en Phase A ameliore-t-il le SEEL du 48c et du 35c ?

    .venv\\Scripts\\python.exe scripts\\test_require_tp.py --composant 48c --mode off
    .venv\\Scripts\\python.exe scripts\\test_require_tp.py --composant 48c --mode on
    .venv\\Scripts\\python.exe scripts\\test_require_tp.py --etat

👤 2026-08-15 : *« evidemment toute proposition doit etre validee par l'experience numerique.
Et voir sur le 35c, 48c avec un seul testglass s'il y a amelioration. »*

🔑 POURQUOI CES DEUX COMPOSANTS-LA. Ce sont les seuls ou le monitoring fonctionne deja a 0 %
de plantage avec UN SEUL verre temoin, et ou l'on a une reference solide. Une amelioration s'y
verrait ; sur le 99c tout est masque par le plantage.

    48c : 0,173 nm  (6 blocs)      35c : 0,482 nm  (6 blocs, mode DEEP)

🔴 LE BRAS « off » EST RECALCULE, PAS RECOPIE. Les references ci-dessus viennent d'un rapport
du 2026-08-14 en modes FAST/PREMIUM/DEEP ; ce banc-ci tourne en FAST avec fente 2 nm forcee.
Comparer un `on` d'aujourd'hui a un `off` d'hier melangerait l'effet du critere et celui du
protocole. Les deux bras tournent donc ICI, meme jour, meme machine, meme graine.

🔴 CE QUE MESURE L'EXCLUSION SECHE. `require_turning_point` retire les candidates sans AUCUN
point tournant -- 130 sur 6440 pour le 48c, 87 sur 4863 pour le 35c
(`reports/tp_admissibilite.json`). C'est le CAS EXTREME : si meme lui ne bouge pas le SEEL,
un cout doux ne le bougera pas davantage et la proposition est reglee.

    amelioration    -> le critere merite un cout, et on cherchera sa forme
    degradation     -> ces candidates SERVENT ; le couperet est nuisible
    ecart < 5,1 %   -> EGALITE, on ne conclut rien (resolution du SEEL a N=50)
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

COMPOSANTS = {
    "48c": ("example/example_strat/JSON-strat-example.json", 0.173),
    "35c": ("example/example_strat/JSON-strat-bandpass-3cav.json", 0.482),
}
CACHE = ROOT / "reports" / "test_require_tp"
SEED = 42
CRASH_TOL = 0.05
DELTA = 0.051          # resolution du SEEL a N=50


def mesurer(comp: str, actif: bool) -> dict:
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    cfg, _ = COMPOSANTS[comp]
    t0 = time.perf_counter()
    row: dict = {"composant": comp, "require_turning_point": actif, "verdict": "?",
                 "n_strats": 0, "n_deposables": 0, "crash_min": None,
                 "rmse": None, "seel": None, "tp_drops": 0,
                 "stamp": datetime.now().isoformat(timespec="seconds")}
    try:
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        app = CertusStratApp()
        app.load_configuration(str(ROOT / cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText("fast")

        over = {"show_plots": False, "robustness_seed": SEED,
                "monochromator_resolution_nm": 2.0, "search_resolution": False,
                "require_turning_point": actif}
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

        # 🔴 Erreur n.5 : le banc rend None sous charge et ca RESSEMBLE a un resultat.
        if vus["n"] < 2:
            row["verdict"] = "SURCHARGES_NON_APPLIQUEES"
            return row
        strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
        if not strats:
            row["verdict"] = "ECHEC_RESULT_NONE"
            return row

        taux = [float(s.get("crash_rate", 1.0)) for s in strats]
        ok = [s for s in strats if float(s.get("crash_rate", 1.0)) < CRASH_TOL]
        ok.sort(key=lambda s: float(s.get("robustness_score", 1e18)))
        row.update({"n_strats": len(strats), "n_deposables": len(ok),
                    "crash_min": round(min(taux) * 100, 2),
                    "verdict": "DEPOSABLE" if ok else "AUCUNE_DEPOSABLE"})
        if ok:
            sc = float(ok[0].get("robustness_score", 0.0))
            row["rmse"] = sc
            row["seel"] = round(2.0 * math.sqrt(sc), 4) if sc > 0 else None
            row["blocs"] = len(ok[0].get("blocks") or [])
            row["origine"] = str(ok[0].get("origin", ""))[:60]
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "EXCEPTION"
        row["erreur"] = repr(exc)[:300]
        row["run_s"] = round(time.perf_counter() - t0, 1)
    return row


def etat() -> int:
    print("=" * 84)
    print("A/B — EXIGER UN POINT TOURNANT EN PHASE A")
    print("=" * 84)
    print("\n  composant  critere  verdict      deposables   SEEL      blocs  duree")
    paires = {}
    for comp in COMPOSANTS:
        for mode in ("off", "on"):
            p = CACHE / f"{comp}_{mode}.json"
            if p.exists():
                r = json.loads(p.read_text(encoding="utf-8"))
                paires.setdefault(comp, {})[mode] = r
                s = f"{r['seel']:.4f}" if r.get("seel") else "   -   "
                print(f"  {comp:9s}  {mode:<7s} {r['verdict']:<12s} "
                      f"{r['n_deposables']:4d}/{r['n_strats']:<5d} {s}  "
                      f"{r.get('blocs', '-'):>5}  {r.get('run_s', 0):6.0f} s")
    print("\n" + "=" * 84)
    print("VERDICT")
    print("=" * 84)
    for comp, d in paires.items():
        if "off" in d and "on" in d and d["off"].get("seel") and d["on"].get("seel"):
            a, b = d["off"]["seel"], d["on"]["seel"]
            ec = (b - a) / a
            if abs(ec) <= DELTA:
                v = f"🟡 EGALITE ({ec:+.1%}, sous la resolution de {DELTA:.1%}) -- rien a conclure"
            elif ec < 0:
                v = f"🟢 AMELIORATION {ec:+.1%} -- le critere merite un cout"
            else:
                v = f"🔴 DEGRADATION {ec:+.1%} -- ces candidates SERVENT"
            print(f"  {comp} : off {a:.4f} nm -> on {b:.4f} nm   {v}")
        else:
            print(f"  {comp} : incomplet")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--composant", choices=sorted(COMPOSANTS))
    ap.add_argument("--mode", choices=("on", "off"))
    ap.add_argument("--etat", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    if args.etat or not args.composant:
        return etat()

    dest = CACHE / f"{args.composant}_{args.mode}.json"
    if dest.exists():
        sys.stderr.write(f"{dest.name} deja mesure.\n")
        return 0
    row = mesurer(args.composant, args.mode == "on")
    dest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stderr.write(f"{args.composant} {args.mode} : {row['verdict']} | "
                     f"{row['n_deposables']}/{row['n_strats']} | SEEL {row.get('seel')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
