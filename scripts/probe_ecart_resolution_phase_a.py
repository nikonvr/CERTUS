"""LA PHASE A LAISSE-T-ELLE DE LA RESOLUTION SPECTRALE SUR LA TABLE ?

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_ecart_resolution_phase_a.py <composant> [observability.json]

## D'ou vient la question

📏 Mesure du 2026-08-17. Sur `r75x2`, le journal `[SLIT]` annonce que TOUTES les resolutions
autres que celle du run sont ecartees par la courbure, pour 100 % des strategies :

    [SLIT] A18 recherche de fente : 32 strategies x 4 fentes -> 32 candidates
           saute par la courbure : 5 nm x32, 1 nm x32, 0.5 nm x32

Or `probe_resolution_exigee.py` mesure que le DESIGN de x2 tolere **1,033 nm** : en choisissant
les lambda pour leur courbure, 1 nm et 0,5 nm seraient admissibles. Les deux sont vrais, et
l'ecart est le sujet :

    ce que le design AUTORISE   la plus grande res_lim sur les lambda admissibles, par couche
    ce que la recherche RETIENT la lambda choisie par la Phase A pour son COUT, jamais pour sa
                                courbure spectrale

## Pourquoi cette sonde plutot qu'un terme de cout en Phase A

Le cout de Phase A vaut `rmse + gain_weight * gain * err_prev_nm`
(`certus/utils/certus_strat_service.py:1385`) -- il est libelle en NANOMETRES d'erreur
d'epaisseur. Y ajouter un terme de courbure demanderait un poids sans echelle naturelle, et le
depot a exactement un precedent : `dp_yield_weight`, ajoute pour la meme bonne raison, s'est
revele n'atteindre JAMAIS le calcul (§24-33), sans que personne s'en apercoive pendant des
semaines.

🔑 Donc on MESURE l'ecart avant de choisir un poids. C'est le controle 4 de §12 -- compter ce
qu'une regle changerait avant de la faire changer quoi que ce soit -- et §22 : les heuristiques
sont des diagnostics, pas des filtres.

🔒 ET AUCUNE LIGNE DE `certus/` N'EST TOUCHEE. Les deux grandeurs existent deja en artefacts :
`res_lim(couche, lambda)` vient de `probe_resolution_exigee`, et la lambda retenue par couche
vient du champ `best_wl` des `reports/STRAT_observability_*.json`. La correlation se calcule
hors ligne.

## Ce que la sortie signifie

    res_lim au meilleur choix   ce que la couche permettrait au mieux
    res_lim au choix reel       ce que la lambda retenue tolere
    ratio                       1,0 = la Phase A a choisi la meilleure courbure disponible
                                0,3 = elle a pris une lambda trois fois plus exigeante

Un ratio median proche de 1 signifie qu'il n'y a rien a gagner : la Phase A choisit deja bien,
et un terme de cout serait inerte. Un ratio faible chiffre ce qui est laisse sur la table, et
donne l'ECHELLE que le poids devrait avoir.

⚠️ CE QUE LA SONDE NE DIT PAS. Qu'une lambda a meilleure courbure serait MEILLEURE tout court :
elle a ete ecartee pour son cout, qui mesure autre chose. L'ecart est une opportunite a
evaluer, pas une erreur a corriger.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(
        "pre", ROOT / "scripts" / "probe_resolution_exigee.py")
    pre = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pre)
    spec2 = importlib.util.spec_from_file_location(
        "pm", ROOT / "scripts" / "profil_monitorabilite.py")
    pm = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(pm)
    connus = {**pm.COMPOSANTS, **pre.COMPOSANTS_ECHELLE}
    return pre, pm, connus[nom]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage : probe_ecart_resolution_phase_a.py <composant> [observability.json]")
        return 2
    nom = sys.argv[1]
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    pre, pm, cfg = _charger(nom)

    obs_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if obs_path is None:
        cands = sorted((ROOT / "reports").glob("STRAT_observability_*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            print("🔴 aucun STRAT_observability_*.json dans reports/ -- lancer un run d'abord.")
            return 1
        obs_path = cands[0]
    obs = json.loads(obs_path.read_text(encoding="utf-8"))
    couches = obs.get("layers") or []
    print(f"observabilite : {obs_path.name}  ({len(couches)} couches)")

    p = pm.profil(cfg)
    r = pre.resolution_exigee(cfg, p["adm_tp"])
    lams = np.asarray(r["lams"], dtype=np.float64)
    res = r["res_lim"]
    N = r["N"]

    if len(couches) != N:
        print(f"🔴 {len(couches)} couches dans l'observabilite contre {N} dans le design : "
              "l'artefact ne correspond pas a ce composant. Passer le bon fichier en 2e argument.")
        return 1

    lignes = []
    for k, c in enumerate(couches):
        wl = c.get("best_wl")
        if wl is None:
            continue
        j = int(np.argmin(np.abs(lams - float(wl))))
        reel = float(res[k, j])
        adm = p["adm_tp"][k]
        best = float(np.where(adm, res[k], -np.inf).max()) if adm.any() else float("nan")
        if not np.isfinite(best) or best <= 0:
            continue
        lignes.append((k, float(wl), reel, best, reel / best))

    if not lignes:
        print("🔴 aucune couche exploitable.")
        return 1

    ratios = np.array([x[4] for x in lignes])
    print(f"\n  {len(lignes)} couches comparees")
    print(f"  ratio res_lim(choix reel) / res_lim(meilleur choix) :")
    print(f"     mediane {np.median(ratios):.3f}   moyenne {ratios.mean():.3f}   "
          f"min {ratios.min():.3f}   max {ratios.max():.3f}")
    print(f"     couches sous 0,50 : {(ratios < 0.5).sum()} / {len(ratios)}")
    print(f"     couches sous 0,25 : {(ratios < 0.25).sum()} / {len(ratios)}")

    print(f"\n  les 12 couches ou la Phase A laisse le plus :")
    print(f"    {'couche':>7} {'lambda':>8} {'res_lim reel':>13} {'res_lim max':>12} {'ratio':>7}")
    for k, wl, reel, best, ratio in sorted(lignes, key=lambda x: x[4])[:12]:
        print(f"    {k:>7} {wl:>7.0f}n {reel:>11.3f}nm {best:>10.3f}nm {ratio:>7.3f}")

    med = float(np.median(ratios))
    print()
    if med > 0.8:
        print("  🟢 La Phase A choisit deja des lambda a bonne courbure. Un terme de cout")
        print("     serait quasi inerte -- ne pas l'ecrire.")
    elif med > 0.4:
        print(f"  🟠 Ecart modere (mediane {med:.2f}). Un terme de cout pourrait gagner, mais")
        print("     l'echelle du gain est a mesurer avant d'ecrire quoi que ce soit.")
    else:
        print(f"  🔴 Ecart important (mediane {med:.2f}) : la Phase A laisse un facteur")
        print(f"     {1 / med:.1f} de resolution sur la table. La piste du cout est fondee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
