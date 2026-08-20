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


def _renoter(opti, params, plans, nom, graine, mode_ctx, fichier) -> None:
    """Note les plans fournis avec la fonction de PRODUCTION, et ecrit AVANT d'afficher."""
    from certus.core.certus_strat_robustness import run_final_simulation_block as vrai

    opti["all_strategies"] = [
        {"strategy_id": 9_000_000 + i, "n_blocks": len(p["blocks"]),
         "blocks": p["blocks"], "origin": f"RENOTE({p['nom']})",
         "avg_cost": float("inf"), "total_cost": float("inf")}
        for i, p in enumerate(plans)
    ]
    # ⚠️ PIEGE 2 : `params` n'est pas toujours un dictionnaire -- sur certains chemins c'est
    # un StratParamsDTO. `params["cle"] = v` fonctionne, `params.setdefault(...)` leve.
    params["robustness_seed"] = graine
    # 🔴 La profondeur est EXPLICITE et consignee (§24-7). Sans cela l'appel prenait le
    # defaut de signature -- 150 -- quelle que soit la profondeur voulue, sans le dire.
    n_runs = int(params.get("robustness_num_runs") or 150)
    print(f"\n  re-notation de {len(plans)} plan(s) sous la graine {graine}, "
          f"N = {n_runs} tirages...", flush=True)
    res = vrai(opti, params, num_runs=n_runs, expand_variants=False)
    sorties = (res or {}).get("all_strategies_results", []) or []

    # 🔴 ON NE GARDE QUE LES PLANS INJECTES, ET ON DIT CEUX QUI MANQUENT.
    #
    # 📏 Mesure du 2026-08-20 : 5 plans injectes, 2 ressortis. Les trois qui plantaient
    # (100 %, 92 %, 98 %) ont ete ELIMINES par la porte de plantage et ont disparu de la
    # sortie SANS UN MOT. Et la fonction rend en plus les strategies ELITE qu'elle engendre,
    # donc 33 resultats pour 5 entrees : sans filtrage, on lirait des chiffres qui ne
    # concernent pas les plans demandes.
    #
    # 🔑 C'EST FATAL POUR LE TEST DE TRANSFERT. Si les strategies de la graine 77 plantent
    # sous la graine 42, elles s'evanouiraient au lieu d'etre rapportees comme plantant --
    # et « aucun resultat » ne se distinguerait plus de « l'outil est casse ». Un plan
    # absent est donc consigne EXPLICITEMENT, avec la seule chose qu'on sache de lui.
    attendus = {f"RENOTE({p['nom']})" for p in plans}
    lignes = []
    vus = set()
    for s in sorties:
        st = s.get("strategy", {}) or {}
        org = str(st.get("origin", "?"))
        if org not in attendus:
            continue  # une ELITE engendree par la fonction, pas un plan demande
        vus.add(org)
        sc = float(s.get("robustness_score", float("nan")) or float("nan"))
        seel = 2 * math.sqrt(sc) if math.isfinite(sc) and sc >= 0 else None
        lignes.append({"nom": org, "score": sc, "seel": seel,
                       "crash_rate": float(s.get("crash_rate", 1.0)),
                       "n_blocs": len(st.get("blocks") or []),
                       "critical_layer": s.get("critical_layer") or {},
                       "statut": "note"})
    for manquant in sorted(attendus - vus):
        lignes.append({"nom": manquant, "score": None, "seel": None, "crash_rate": None,
                       "n_blocs": None, "critical_layer": {},
                       "statut": "ELIMINE_PAR_LA_PORTE_DE_PLANTAGE"})

    # 🔑 SAUVER D'ABORD, AFFICHER ENSUITE. L'affichage est un confort, la sauvegarde est le
    # livrable -- vingt minutes ont ete perdues le 2026-08-20 pour l'ordre inverse.
    ecrire_json(
        ROOT / "reports" / f"renotation_{nom}_s{graine:03d}_{fichier.stem}.json",
        {"composant": nom, "graine_notation": graine, "mode_contexte": mode_ctx,
         "source_plans": fichier.name, "n_plans": len(plans),
         "profondeur": {"robustness_num_runs": n_runs},
         "parametres_de_notation": {
             k: params.get(k) for k in
             ("poem_anchor_noise", "index_corridor", "tp_hysteresis_factor",
              "photometric_curvature_amp", "affine_scale_amp", "affine_offset_amp",
              "poem_enabled", "slit_bias_enabled", "monochromator_resolution_nm",
              "allow_rate", "phase_a_seed")},
         "stamp": datetime.now().isoformat(timespec="seconds"), "resultats": lignes},
        racine=ROOT,
    )
    n_elim = sum(1 for r in lignes if r["statut"] != "note")
    print(f"\n  {len(lignes) - n_elim} plan(s) note(s), "
          f"{n_elim} ELIMINE(S) par la porte de plantage", flush=True)
    print(f"\n  {'plan':<40}{'SEEL':>9}{'crash':>9}{'blocs':>7}   statut", flush=True)
    for r in lignes:
        se = f"{r['seel']:.4f}" if r["seel"] else "-"
        cr = f"{100 * r['crash_rate']:.2f}%" if r["crash_rate"] is not None else "-"
        nb = str(r["n_blocs"]) if r["n_blocs"] is not None else "-"
        marq = "" if r["statut"] == "note" else "  🔴 ELIMINE (plantage > tolerance)"
        print(f"  {r['nom'][:39]:<40}{se:>9}{cr:>9}{nb:>7}{marq}", flush=True)


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
    #
    # 🔴 CINQ MODULES IMPORTENT `run_final_simulation_block`, PAS DEUX. Verifie le
    # 2026-08-20 : `certus_strat_robustness` (la source), `certus_strat_pipeline`,
    # `certus_strat_workers`, `certus_strat_workers_external` et
    # `certus_strat_workers_robustness`. Un `from X import f` cree une liaison PROPRE au
    # module importateur : patcher la source ne touche PAS les copies deja liees.
    # N'en patcher que deux, c'est risquer de ne rien capturer selon le chemin emprunte --
    # et de le decouvrir APRES avoir paye le run.
    from certus.core import certus_strat_pipeline as P
    from certus.core import certus_strat_robustness as R
    from certus.workers import certus_strat_workers as W
    from certus.workers import certus_strat_workers_external as WE
    from certus.workers import certus_strat_workers_robustness as WR

    MODULES = (R, P, W, WE, WR)
    capture: dict[str, Any] = {}
    vrai = R.run_final_simulation_block

    def intercepte(opti_results, params, *a, **k):
        # 🔴 LA RE-NOTATION SE FAIT ICI, DANS LE CONTEXTE VIVANT — pas apres le workflow.
        #
        # 📏 Mesure du 2026-08-20, DEUX essais perdus : appeler
        # `run_final_simulation_block` depuis le thread principal APRES la fin du worker Qt
        # tue le processus, SANS trace, sans exception, sans code d'erreur. Le journal
        # s'arrete net sur la ligne « [SLIT] 5/5 strategies » et il ne reste rien. Ce n'est
        # pas une erreur Python : c'est un arret brutal, et le diagnostiquer couterait plus
        # cher que de l'eviter.
        #
        # 🔑 Ici, tout est initialise et vivant : on note, on ECRIT, puis on laisse le
        # workflow continuer. Meme si le processus meurt ensuite, le livrable est sur le
        # disque -- c'est la meme regle que « sauver avant d'afficher », poussee d'un cran.
        if "fait" not in capture:
            capture["fait"] = True
            print(f"  🟢 contexte capture : "
                  f"{sorted(x for x in opti_results if not x.startswith('_'))[:8]}", flush=True)
            try:
                _renoter(dict(opti_results), params, plans, nom, graine, mode_ctx, fichier)
            except Exception as e:  # noqa: BLE001 -- on ne doit JAMAIS tuer le run porteur
                import traceback
                print(f"  🔴 re-notation en echec : {type(e).__name__}: {e}", flush=True)
                traceback.print_exc()
        return vrai(opti_results, params, *a, **k)

    poses = []
    for m in MODULES:
        if getattr(m, "run_final_simulation_block", None) is not None:
            m.run_final_simulation_block = intercepte
            poses.append(m.__name__.rsplit(".", 1)[-1])
    print(f"  interception posee sur {len(poses)} module(s) : {', '.join(poses)}")
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
        for m in MODULES:
            if getattr(m, "run_final_simulation_block", None) is intercepte:
                m.run_final_simulation_block = vrai

    if "fait" not in capture:
        print("🔴 RE-NOTATION JAMAIS DECLENCHEE -- `run_final_simulation_block` n'a pas ete "
              "appele. Verifier que le composant produit bien des strategies.", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
