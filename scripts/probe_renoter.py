"""RE-NOTER DES PLANS DE SURVEILLANCE DONNES, SOUS DES PARAMETRES DONNES.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_renoter.py <composant> <plans.json> [graine] [mode_contexte]

## 🔑 POURQUOI CET OUTIL EXISTE — il conditionne DEUX questions ouvertes

**(1) Le test de transfert.** Sur `r75x2` a 2 nm, la graine 77 trouve 518 strategies deposables
a SEEL 0,5698 ; la graine 42 n'en trouve AUCUNE sur 1617. La question n'est pas « comment les
retrouver » mais d'abord :

    une strategie trouvee sous la graine 77, rejouee sous le bruit de la graine 42, tient-elle ?

  - elle tient  -> la strategie est bonne EN SOI, seule la RECHERCHE de la graine 42 la rate,
                   et relacher la recherche est la bonne voie ;
  - elle plante -> le 0,5698 est propre a sa realisation, et aucun relachement ne le recuperera.

C'est un quart d'heure de calcul contre plusieurs heures de recherche a l'aveugle.

**(2) La garde de 👤 sur le relachement.** 👤 propose de *« relacher les parametres bruit et
derive d'indice pour trouver les strategies qui seront testees ensuite avec les VRAIS
parametres »*. 🔒 C'est legitime pour **ENGENDRER**, jamais pour **NOTER** -- sinon on obtient un
SEEL flatteur qui ne decrit aucune machine. **Cet outil est l'etage « juger au nominal ».**
Sans lui, la moitie honnete de la methode n'existe pas.

## Comment il s'y prend, et pourquoi ainsi

🔴 IL NE REIMPLEMENTE RIEN. `CLAUDE.md` interdit 7 : deux bugs de signe valant 46 et 82 points
de reflectance sont nes de reimplantations. L'outil **capture** le contexte de pre-calcul d'un
vrai run -- en interceptant `run_final_simulation_block` a son premier appel -- puis rappelle
**la meme fonction de production** avec les plans injectes.

    1. un run COURT construit le contexte (physique : p_thick_nominal, clues_at_wl, indices)
    2. on intercepte `opti_results` au premier appel, on laisse le run finir
    3. on rappelle `run_final_simulation_block` avec `all_strategies` = les plans fournis,
       `expand_variants=False`, et les parametres de NOTATION voulus

Le contexte est de la **physique**, pas de la recherche : il ne depend ni du mode ni de la
graine de notation. Le construire en `fast` et noter en profondeur est donc legitime -- et c'est
ce qui rend l'outil bon marche.

## Le format des plans

Un JSON : soit une liste, soit `{"plans": [...]}`. Chaque plan porte ses blocs.

    [{"nom": "gagnante_s077",
      "blocs": [{"start": 0, "end": 12, "wavelength": 604.0}, ...]}]

📌 Les artefacts de balayage produits depuis le 2026-08-20 portent ce champ `blocs` directement
(correctif `2b2901c` : la sonde lisait `wl` la ou le noyau ecrit `wavelength`, et sortait
`[None, ...]` DE LA BONNE LONGUEUR, donc sans rien signaler). Les artefacts anterieurs sont
muets sur les λ et ne peuvent pas alimenter cet outil.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _artefact import ecrire_json  # noqa: E402

COMPOSANTS = {
    "35c": "example/example_strat/JSON-strat-bandpass-3cav.json",
    "48c": "example/example_strat/JSON-strat-example.json",
    "75c": "example/example_strat/JSON-strat-random75.json",
    "99c": "example/example_strat/JSON-strat-bandpass-5cav-99c.json",
    "r75x2": "example/example_strat/JSON-strat-random75-x2-fabricable.json",
}


def _lire_plans(chemin: Path) -> list[dict[str, Any]]:
    """Lit les plans et VERIFIE qu'ils portent des longueurs d'onde reelles."""
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    plans = brut.get("plans", brut) if isinstance(brut, dict) else brut
    if not isinstance(plans, list) or not plans:
        raise SystemExit(f"🔴 {chemin.name} ne porte aucun plan exploitable.")
    out = []
    for i, p in enumerate(plans):
        blocs = p.get("blocs") or p.get("blocks") or []
        if not blocs:
            raise SystemExit(f"🔴 plan {i} sans blocs.")
        # 🔴 LE CONTROLE QUI AURAIT EVITE 145 MIN PERDUES. Les artefacts d'avant le
        # 2026-08-20 portent des lambda a `None` -- de la BONNE LONGUEUR, donc l'absence ne
        # se voyait pas. On refuse ici, bruyamment, plutot que de noter du vide.
        for b in blocs:
            wl = b.get("wavelength", b.get("wl"))
            if wl is None:
                raise SystemExit(
                    f"🔴 plan {i} : une longueur d'onde vaut `None`. L'artefact d'ou il sort "
                    f"est ANTERIEUR au correctif `2b2901c` et ne porte pas les λ. "
                    f"Il faut rejouer le run qui l'a produit."
                )
        out.append({
            "nom": str(p.get("nom", p.get("origine", f"plan_{i}"))),
            "blocks": [{"start": int(b["start"]), "end": int(b["end"]),
                        "wavelength": float(b.get("wavelength", b.get("wl")))}
                       for b in blocs],
        })
    return out


def main() -> int:
    import bench_examples as Bx

    nom = sys.argv[1] if len(sys.argv) > 1 else "r75x2"
    fichier = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    graine = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    mode_ctx = sys.argv[4] if len(sys.argv) > 4 else "fast"
    if fichier is None or not fichier.is_file():
        raise SystemExit("usage: probe_renoter.py <composant> <plans.json> [graine] [mode_contexte]")
    cfg = COMPOSANTS.get(nom)
    if cfg is None:
        raise SystemExit(f"composant inconnu : {nom} (connus : {sorted(COMPOSANTS)})")

    plans = _lire_plans(fichier)
    print(f"  composant={nom}  plans={len(plans)}  graine de NOTATION={graine}  "
          f"contexte={mode_ctx}")

    # ── 1. capturer le contexte de pre-calcul d'un vrai run ──────────────────────────
    from certus.core import certus_strat_robustness as R
    from certus.workers import certus_strat_workers as W

    capture: dict[str, Any] = {}
    vrai = R.run_final_simulation_block

    def intercepte(opti_results, params, *a, **k):
        if "opti" not in capture:
            capture["opti"] = opti_results
            capture["params"] = params
            print(f"  🟢 contexte capture : {sorted(x for x in opti_results if not x.startswith('_'))[:8]}")
        return vrai(opti_results, params, *a, **k)

    R.run_final_simulation_block = intercepte
    W.run_final_simulation_block = intercepte
    try:
        Bx.qapp()
        Bx.autoanswer_dialogs(True)
        from CERTUS_STRAT import CertusStratApp

        app = CertusStratApp()
        app.load_configuration(str(ROOT / cfg))
        if "execution_mode" in getattr(app, "widgets", {}):
            app.widgets["execution_mode"].setCurrentText(mode_ctx)
        _c = app.collect_params

        def collect(*a, **k):
            p = _c(*a, **k)
            p["robustness_seed"] = graine
            return p

        app.collect_params = collect
        app.run_workflow(23)
        if getattr(app, "worker", None):
            Bx.wait_for(app.worker)
    finally:
        R.run_final_simulation_block = vrai
        W.run_final_simulation_block = vrai

    if "opti" not in capture:
        print("🔴 CONTEXTE NON CAPTURE -- `run_final_simulation_block` n'a jamais ete appele.")
        return 1

    # ── 2. re-noter les plans fournis, avec la MEME fonction de production ───────────
    opti = dict(capture["opti"])
    opti["all_strategies"] = [
        {"strategy_id": 9_000_000 + i, "n_blocks": len(p["blocks"]),
         "blocks": p["blocks"], "origin": f"RENOTE({p['nom']})",
         "avg_cost": float("inf"), "total_cost": float("inf")}
        for i, p in enumerate(plans)
    ]
    params = dict(capture["params"]) if not hasattr(capture["params"], "model_dump") else capture["params"]
    params["robustness_seed"] = graine

    print(f"\n  re-notation de {len(plans)} plan(s) sous la graine {graine}...")
    res = vrai(opti, params, expand_variants=False)
    sorties = (res or {}).get("all_strategies_results", []) or []

    lignes = []
    print(f"\n  {'plan':<34}{'SEEL':>9}{'crash':>9}{'blocs':>7}")
    for s in sorties:
        st = s.get("strategy", {}) or {}
        sc = float(s.get("robustness_score", float("nan")) or float("nan"))
        seel = 2 * math.sqrt(sc) if math.isfinite(sc) and sc >= 0 else None
        cr = float(s.get("crash_rate", 1.0))
        lignes.append({"nom": str(st.get("origin", "?")), "score": sc,
                       "seel": seel, "crash_rate": cr,
                       "n_blocs": len(st.get("blocks") or []),
                       "critical_layer": s.get("critical_layer") or {}})
        print(f"  {str(st.get('origin', '?'))[:33]:<34}"
              f"{(f'{seel:.4f}' if seel else '-'):>9}{100 * cr:>8.2f}%"
              f"{len(st.get('blocks') or []):>7}")

    ecrire_json(
        ROOT / "reports" / f"renotation_{nom}_s{graine:03d}_{fichier.stem}.json",
        {"composant": nom, "graine_notation": graine, "mode_contexte": mode_ctx,
         "source_plans": fichier.name, "n_plans": len(plans),
         "stamp": datetime.now().isoformat(timespec="seconds"), "resultats": lignes},
        racine=ROOT,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
