"""LA COURBE SEEL(n) ET crash(n) -- « a partir de quand l'optique pose probleme ? »

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_prefixe_optique.py [composant] [mode] [graine]

## L'idee, et elle est de 👤 (2026-08-19)

> « 20 couches optiques plus le reste avec des epaisseurs PARFAITES, et on calcule SEEL20 ;
>   puis 21 couches optiques, le reste epaisseurs parfaites, SEEL21 ; idem jusqu'a SEEL75.
>   On regarde ensuite la courbe SEEL = fonction(n) et on en deduit a partir de quand
>   l'optique pose probleme. Du coup c'est ici qu'on introduit le rate pour le reste. »

> « attention, la courbe n'est pas forcement monotone, il faut la tracer ENTIEREMENT pour
>   decider quand le rate est necessaire. »

## Pourquoi cette mesure vaut mieux que tout ce qui a ete tente avant elle

🔑 **C'est une DECOMPOSITION, pas une recherche.** Chaque `n` est UNE mesure, jamais un maximum
sur des candidates. La malediction du vainqueur -- +12,9 % mesures le 15/08, et qui se COMPOSE
a chaque pas d'un glouton -- ne s'applique donc pas. C'est la difference de fond avec toutes
les campagnes de queue.

🟢 **Et elle ne demande aucun code nouveau dans le noyau.**
`_build_layer_wavelengths_from_strategy` initialise `layer_wavelengths` a ZERO et ne remplit que
les couches couvertes par un bloc. Le noyau part alors sur `if wl < 0.1`
(`certus_strat_growth.py`) et rend l'epaisseur EXACTEMENT nominale, marges a 1e18 donc plantage
impossible. Tronquer les blocs a `n` suffit -- par un chemin deja ecrit et deja teste.

## Comment lire les DEUX courbes, et elles ne disent pas la meme chose

    crash(n)   MONOTONE par construction : ajouter une couche optique ne peut qu'ajouter une
               occasion de planter. La falaise y est donc NON AMBIGUE, et c'est elle qui
               commande -- mesure du 2026-08-19 : entre les coupures 58 et 61 le plantage fait
               un facteur 25 pendant que le SEEL reste plat a 9 % pres.

    SEEL(n)    PAS monotone, et c'est ce qui la rend utile. POEM se re-ancre et CORRIGE
               l'erreur amont (protection x34,8, §24-17), donc une couche optique de plus peut
               faire BAISSER l'erreur totale. Ce sont les REMONTEES LOCALES qui designent les
               couches ou la surveillance optique nuit.

⚠️ « PARFAIT » N'EST PAS « RATE ». Une couche Rate herite du facteur A ; une couche parfaite
n'herite de rien. SEEL(n) est donc une BORNE INFERIEURE, pas la prediction de la vraie
strategie. C'est l'interet meme : la difference entre les deux ISOLE le cout de la queue Rate.

    SEEL_parfait(n)                  = le dommage de l'optique sur les n premieres couches
    SEEL_reel(n) - SEEL_parfait(n)   = le cout propre de la queue Rate

L'un croit avec n, l'autre decroit : leur somme a un minimum, et c'est LUI l'optimum cherche.

⚠️ La courbe est CONDITIONNELLE au plan de surveillance. Seules les strategies a surveillance
couche par couche sont balayees -- sur r75x2 c'est la seule architecture qui survive (les 224
strategies a blocs plantent toutes a 100 %).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def _famille(s: dict) -> str:
    """Nom de famille d'une strategie -- `RATE_TAIL52(from 75800)` -> `RATE_TAIL52`."""
    st = s.get("strategy") or {}
    return re.sub(r"\(.*", "", str(st.get("origin") or st.get("origin_name") or "?"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

COMPOSANTS = {
    "35c": "example/example_strat/JSON-strat-bandpass-3cav.json",
    "48c": "example/example_strat/JSON-strat-example.json",
    "75c": "example/example_strat/JSON-strat-random75.json",
    "99c": "example/example_strat/JSON-strat-bandpass-5cav-99c.json",
    "r75x2": "example/example_strat/JSON-strat-random75-x2-fabricable.json",
}


def main() -> int:
    import bench_examples as Bx

    nom = sys.argv[1] if len(sys.argv) > 1 else "r75x2"
    mode = sys.argv[2] if len(sys.argv) > 2 else "deep"
    graine = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    cfg = COMPOSANTS.get(nom)
    if cfg is None:
        print(f"composant inconnu : {nom} (connus : {sorted(COMPOSANTS)})")
        return 2

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText(mode)

    n_couches = len([e for e in str(app.collect_params()["stack_string"]).split(",") if e.strip()])
    # 🔴 « il faut la tracer ENTIEREMENT » -- 👤. On balaie donc TOUT le domaine admissible,
    # de RATE_MIN_LAYER (la borne gravee : sous 2 couches il n'y a pas de rate possible) a
    # l'empilement complet. Aucun arret anticipe, aucun seuil : la decision se prend sur la
    # FORME de la courbe, et une courbe non monotone tronquee ne se lit pas.
    balayage = list(range(2, n_couches + 1))

    over = {
        "robustness_seed": graine,
        "optical_prefix_sweep": balayage,
        # ⚠️ Le balayage de prefixe n'a rien a voir avec le Rate : on ISOLE le cout optique.
        # Laisser des variantes Rate dans la meme population melangerait les deux.
        "allow_rate": False,
    }
    profondeur: dict = {}
    _c = app.collect_params
    vus = {"n": 0}

    def collect(*a, **k):
        p = _c(*a, **k)
        p.update(over)
        vus["n"] += 1
        for _k in ("robustness_num_runs", "n_screen_runs", "dp_top_k"):
            if p.get(_k) is not None:
                profondeur[_k] = p.get(_k)
        return p

    app.collect_params = collect
    print(f"  composant={nom} ({n_couches} couches) mode={mode} graine={graine}")
    print(f"  balayage n = {balayage[0]} .. {balayage[-1]}  ({len(balayage)} valeurs)")
    app.run_workflow(23)
    res = Bx.wait_for(app.worker) if getattr(app, "worker", None) else None

    if vus["n"] < 2:
        print("🔴 SURCHARGES_NON_APPLIQUEES -- rien a analyser.")
        return 1
    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    if not strats:
        print("🔴 ECHEC_RESULT_NONE -- rien a analyser.")
        return 1

    lignes = []
    for s in strats:
        st = s.get("strategy", {}) or {}
        o = str(st.get("origin", st.get("origin_name")) or "")
        if not o.startswith("OPT_PREFIX"):
            continue
        lignes.append({
            "n_opt": int(o[10:].split("(")[0]),
            "origine": o,
            "crash_rate": float(s.get("crash_rate", 1.0)),
            "score": float(s.get("robustness_score", 0.0) or 0.0),
            "critical_layer": s.get("critical_layer") or {},
        })
    lignes.sort(key=lambda z: z["n_opt"])

    out = ROOT / "reports" / f"prefixe_optique_{nom}_{mode}_s{graine:03d}.json"
    out.write_text(json.dumps({
        "composant": nom, "mode": mode, "seed": graine, "n_couches": n_couches,
        "profondeur": profondeur, "stamp": datetime.now().isoformat(timespec="seconds"),
        "n_strats": len(strats), "courbe": lignes,
        # 🔴 CE CHAMP EXISTE POUR QU'UN ARTEFACT VIDE SE DENONCE LUI-MEME.
        "familles_vues": sorted({_famille(s) for s in strats})[:40],
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {len(lignes)} points de courbe -> {out.name}")
    print(f"  (sur {len(strats)} strategies evaluees ; profondeur {profondeur})")

    # 🔴 UNE COURBE VIDE N'EST PAS UN RESULTAT, C'EST UNE PANNE -- et elle doit se voir.
    # 📏 Le 2026-08-19 puis le 2026-08-20, cette sonde a rendu `courbe: []` en 100 min puis
    # en 45,8 min, EN SORTANT AVEC LE CODE 0. Le pilote de batch a donc affiche « OK » deux
    # fois pour deux pannes. C'est le motif que `CLAUDE.md` denonce partout : ca ne produit
    # pas d'erreur, ca produit un resultat plausible.
    if not lignes:
        print("\n" + "=" * 92)
        print("  🔴 COURBE VIDE -- AUCUNE VARIANTE `OPT_PREFIX` DANS LES RESULTATS.")
        print(f"  {len(strats)} strategies evaluees, familles vues :")
        for f in sorted({_famille(s) for s in strats})[:14]:
            print(f"      {f}")
        print("\n  Ce qu'il faut verifier, DANS CET ORDRE :")
        print("   1. le journal porte-t-il une ligne `[PREFIX]` ? Ni l'info ni l'avertissement")
        print("      n'y etaient le 2026-08-20 : `_optical_prefix_variants` sort alors a")
        print("      `if not sweep: return []`, c'est-a-dire que `optical_prefix_sweep`")
        print("      N'ATTEINT PAS le calcul. Le DTO le preserve (verifie a part), donc la")
        print("      perte est ailleurs sur le trajet des parametres.")
        print("   2. si `[PREFIX] aucune strategie a surveillance couche par couche` apparait,")
        print("      c'est l'AUTRE cause : la population ne porte aucune strategie a")
        print("      `n_blocks >= num_layers`, et la courbe est SANS OBJET sur ce plan.")
        print("=" * 92)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
