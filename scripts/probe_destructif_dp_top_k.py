"""PREUVE NON CIRCULAIRE QUE `dp_top_k` ATTEINT LE CALCUL -- par DESTRUCTION.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_destructif_dp_top_k.py [composant]

👤 2026-08-18 : *« une derniere verification stp avec une methodologie differente ? »*

## Pourquoi ce test, alors que l'AST dit deja que la cle est lue

Parce que « la cle est lue quelque part » et « la valeur change le resultat » sont deux
affirmations differentes, et ce depot a paye la difference au moins trois fois :

    fast_auto_blocks       pose ET journalise, aucun code ne le lit
    machine_sampling_dd    expose, present dans 9 configs, 0 des 27 sites d'appel le passe
    dp_yield_weight        porte a 200 sur un bras qui plante a 59 % -> resultat BIT-IDENTIQUE
    strategy_phase_timeout expose a l'utilisateur avec une promesse, lu par personne (§24-50)

Le §12 controle 1 le dit dans ces termes : *« un reglage destructif doit vider la selection --
c'est la seule facon de prouver SANS CIRCULARITE que le parametre atteint le calcul »*. Et le
§12 controle 4 : *« compte les rejets, ne lis pas le code. Un filtre inerte ne produit aucune
erreur -- il produit un resultat plausible. »*

## Le protocole, et le critere est ecrit AVANT

Deux runs COMPLETS du meme composant, meme graine, meme fente, meme mode. Une seule chose
change : `dp_top_k`.

    dp_top_k = 1     valeur DESTRUCTIVE -- la DP ne garde qu'UN groupement par nombre de blocs
    dp_top_k = 100   la valeur du mode deep, celle qui a produit les 2945 strategies sur x2

    REUSSITE : l'offre s'effondre d'un facteur au moins 5. Le parametre atteint donc le calcul,
              et la cellule `dp_top_k = 200` de la campagne mesurera quelque chose de reel.

    ECHEC   : les deux runs rendent le MEME nombre de strategies. `dp_top_k` serait alors le
              cinquieme parametre mort du depot, la cellule de 240 min ne mesurerait RIEN, et
              tout ce que j'ai ecrit sur « la largeur de la recherche » serait a reprendre.

🔑 On teste sur le 35c -- 35 couches, le plus petit des composants -- parce que le test doit
etre bon marche. Ce qu'on verifie est un CABLAGE, pas une physique : il n'a pas a etre fait sur
le composant d'interet.

⚠️ Ce test ne dit PAS que dp_top_k=200 fera mieux que 100. Il dit seulement que la valeur
n'est pas ignoree. C'est le prealable, pas la reponse.
"""

from __future__ import annotations

import json
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
    "35c": "example/example_strat/JSON-strat-bandpass-3cav.json",
    "48c": "example/example_strat/JSON-strat-example.json",
}
SEED = 42


def un_run(cfg: str, dp_top_k: int) -> dict:
    """Un run complet, `dp_top_k` impose APRES collect_params -- comme la campagne le fait."""
    import bench_examples as Bx
    from CERTUS_STRAT import CertusStratApp

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText("fast")

    # 🔑 On ENREGISTRE ce que la DP recoit reellement. Si la surcharge n'atteignait pas le
    # site d'appel, on le verrait ici avant meme de compter les strategies -- et on saurait
    # que l'echec vient du cablage et non du solveur.
    vus_par_la_dp: list[int] = []
    import certus.core.certus_strat_ranking as R

    vraie = R._find_k_best_groupings_dp_sequential

    def espion(*a, **k):
        vus_par_la_dp.append(int(k.get("top_k", a[3] if len(a) > 3 else -1)))
        return vraie(*a, **k)

    R._find_k_best_groupings_dp_sequential = espion

    over = {"show_plots": False, "robustness_seed": SEED, "execution_mode": "fast",
            "monochromator_resolution_nm": 2.0, "search_resolution": False,
            "dp_top_k": int(dp_top_k)}
    _c = app.collect_params

    def collect(*a, **k):
        p = _c(*a, **k)
        p.update(over)
        return p

    app.collect_params = collect
    t0 = time.perf_counter()
    try:
        app.run_workflow(23)
        res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None
    finally:
        R._find_k_best_groupings_dp_sequential = vraie
    dt = time.perf_counter() - t0

    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    return {"dp_top_k_demande": int(dp_top_k),
            "dp_top_k_vu_par_la_DP": sorted(set(vus_par_la_dp)),
            "appels_DP": len(vus_par_la_dp),
            "n_strats": len(strats),
            "n_blocs_distincts": len({(s.get("strategy", {}) or {}).get("n_blocks") for s in strats}),
            "secondes": round(dt, 1)}


def main() -> int:
    nom = sys.argv[1] if len(sys.argv) > 1 else "35c"
    cfg = COMPOSANTS[nom]
    print(f"TEST DESTRUCTIF sur {nom} -- fast, fente 2 nm, graine {SEED}")
    print("critere ecrit d'avance : l'offre doit s'effondrer d'un facteur >= 5\n")

    out = {}
    for k in (1, 100):
        print(f"  run dp_top_k = {k:>3} ...", flush=True)
        r = un_run(cfg, k)
        out[k] = r
        print(f"     la DP a recu {r['dp_top_k_vu_par_la_DP']} sur {r['appels_DP']} appels")
        print(f"     -> {r['n_strats']} strategies, {r['n_blocs_distincts']} nombres de blocs, "
              f"{r['secondes']} s\n", flush=True)

    a, b = out[1], out[100]
    print("=" * 78)
    if b["n_strats"] == 0 or a["n_strats"] == 0:
        print("🟠 NON CONCLUANT -- un des deux runs n'a rendu aucune strategie.")
        verdict = "NON_CONCLUANT"
    elif a["dp_top_k_vu_par_la_DP"] != [1]:
        print(f"🔴 LE CABLAGE EST ROMPU : la DP a recu {a['dp_top_k_vu_par_la_DP']} quand on")
        print("   demandait 1. La surcharge n'atteint pas le site d'appel.")
        verdict = "CABLAGE_ROMPU"
    else:
        fac = b["n_strats"] / a["n_strats"]
        print(f"   dp_top_k = 1   -> {a['n_strats']:>5} strategies")
        print(f"   dp_top_k = 100 -> {b['n_strats']:>5} strategies      facteur {fac:.1f}x")
        if fac >= 5:
            print("\n🟢 REUSSITE. Le reglage destructif effondre l'offre, donc `dp_top_k` atteint")
            print("   bien le calcul. La cellule dp_top_k = 200 mesurera quelque chose de reel.")
            verdict = "ATTEINT_LE_CALCUL"
        else:
            print(f"\n🔴 ECHEC. Facteur {fac:.1f}x seulement, sous le seuil de 5 ecrit d'avance.")
            print("   `dp_top_k` n'est pas le levier que je croyais, et la cellule de 240 min")
            print("   de la campagne est a reconsiderer.")
            verdict = "EFFET_TROP_FAIBLE"
    print("=" * 78)

    p = ROOT / "reports" / f"destructif_dp_top_k_{nom}.json"
    p.write_text(json.dumps({"composant": nom, "verdict": verdict, "runs": out,
                             "stamp": datetime.now().isoformat(timespec="seconds")},
                            indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"consigne dans {p.relative_to(ROOT)}")
    return 0 if verdict == "ATTEINT_LE_CALCUL" else 1


if __name__ == "__main__":
    sys.exit(main())
