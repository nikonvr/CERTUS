"""PILOTE DU LOT DE 10 A 12 H -- grille resolution x epaisseur optique, puis exploration elargie.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --heures 12
    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --heures 10
    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --etat

👤 2026-08-17 : *« j'aimerai avoir 10 h pour lancer un batch [...] avec de la valeur ajoutee dans
la comprehension slit 1 nm vs 2 nm et 75c dans toutes ses variantes »*, puis *« j'aimerai aussi
que dans strat certains parametres soient augmentes pour tester plus »*.

## Ce que le lot mesure

Une grille RESOLUTION x EPAISSEUR OPTIQUE sur les quatre variantes d'echelle du random75 :
75 couches, structure et materiaux identiques, seule l'epaisseur optique varie.

    Somme QWOT     5 nm   2 nm   1 nm   0,5 nm
    x0,5    57,4    oui    oui    oui    oui
    x1     114,9    oui    oui    oui    oui
    x1,5   172,3     -     oui    oui    oui
    x2     229,8     -     oui    oui    oui

Le 5 nm n'est teste que sur les deux MINCES : sur x1,5 et x2 la courbure le condamne d'avance
(res_lim mesuree a 0,767 et 1,033 nm, `probe_resolution_exigee.py`).

🔒 LA GRILLE EST EXACTE PAR CONSTRUCTION. Le facteur de bruit de la fente multiplie
l'ECHANTILLON, jamais la graine -- contrainte C2, `certus_strat_robustness.py:192`. Deux
resolutions voient donc les MEMES tirages, a l'amplitude pres, et l'ecart entre deux cellules
est attribuable a la resolution seule.

## La prediction que la grille teste, et elle est falsifiable

    biais de fente  ~ B^2        2 nm -> 1 nm : biais / 4
    bruit de lecture             2 nm -> 1 nm : bruit x2   (RESOLUTION_NOISE_FACTOR)

    mince (Somme QWOT faible)  limite par le BRUIT  -> optimum vers la fente LARGE
    epais (Somme QWOT fort)    limite par le BIAIS  -> optimum vers la fente FINE

📏 Deja mesure et coherent : sur x0,5, affiner AGGRAVE -- 48 % a 2 nm, 84 % a 1 nm, 94 % a
0,5 nm. Si l'optimum se deplace vers le fin quand Somme QWOT croit, on tient un mecanisme et une
regle d'atelier : choisir la fente selon l'epaisseur optique totale.

## Pourquoi DEUX phases et pas une

Phase 1 fait varier la RESOLUTION a exploration constante. Phase 2 fait varier l'EXPLORATION a
resolution fixee. Les melanger rendrait un eventuel succes inattribuable -- contrainte C3.

Phase 2 elargit ce qui est GENERE et RETENU (dp_top_k 20 -> 100, limites de candidates x4),
jamais la profondeur d'EVALUATION : `robustness_num_runs` et `n_screen_runs` restent intacts,
sinon les taux de plantage cesseraient d'etre comparables a la grille.

## Les garde-fous

  REPRENABLE       un fichier par cellule ; une cellule deja mesuree n'est jamais relancee
  BUDGET RESPECTE  aucune cellule n'est ENGAGEE s'il ne reste pas sa duree estimee
  ORDONNE          par valeur d'information : si le lot est coupe, l'essentiel est deja acquis
  PAS DE SILENCE   un banc qui deborde rend ECHEC_RESULT_NONE, visible, pas un faux resultat
  PHASE 2 PLAFONNEE son plafond est cale sur le temps restant : si elle deborde, elle est
                   perdue SEULE, la grille est acquise
  10 H OU 12 H     la liste est plus longue que 10 h et le budget coupe tout seul. A 10 h :
                   les 9 cellules de grille + la phase 2 (9,2 h). A 12 h : + les trois
                   cellules de consolidation (11,5 h). Un seul pilote pour les deux.

⚠️ GRAINE UNIQUE (42). La mesure du 2026-08-17 a montre qu'un verdict marginal bascule avec la
graine (§24-46). Toute cellule qui ressortira marginale devra etre rejouee a une seconde graine.

⚠️ MODE FAST. Toute cellule qui rendrait des DEPOSABLES doit etre rejouee en PREMIUM avant
publication -- regle du §8. Ce n'est pas dans ce lot.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

PY = sys.executable
SONDE = "scripts/probe_blocs_vs_plantage.py"
SEED = 42

#: (composant, mode, resolution_nm, elargi, graine, minutes estimees, pourquoi)
#: 🔑 L'ORDRE EST L'ORDRE D'EXECUTION, par valeur d'information DECROISSANTE, et la liste est
#: volontairement PLUS LONGUE que 10 h. Le garde-fou de budget coupe tout seul : le meme
#: pilote sert donc a 10 h comme a 12 h, et c'est le budget qui decide ou s'arreter.
#:
#:   a 10 h : les 9 cellules de grille + la PHASE 2 (555 min)
#:   a 12 h : + les trois cellules de consolidation (690 min)
#:
#: 🔴 LA PHASE 2 EST EN POSITION 10, PAS EN DERNIER, et c'est delibere : placee apres les
#: cellules de consolidation elle ne tournerait jamais a 10 h, alors qu'elle repond a une
#: demande explicite de 👤.
CELLULES = [
    ("r75x2", "fast", 1.0, False, 42, 45, "LA question -- 1 nm n'a jamais ete evalue sur x2"),
    ("r75x2", "fast", 0.5, False, 42, 45, "second point de la courbe sur le cas dur"),
    ("r75x0.5", "fast", 5.0, False, 42, 45, "le bonus de bruit /1,5 sur le cas mince"),
    ("r75x0.5", "fast", 2.0, False, 42, 45, "reference propre du mince, meme sonde"),
    ("r75x1.5", "fast", 1.0, False, 42, 45, "le point limite -- 1 deposable sur 704 a 2 nm"),
    ("75c", "fast", 1.0, False, 42, 45, "le composant qui PASSE -- 1 nm le degrade-t-il ?"),
    ("75c", "fast", 5.0, False, 42, 45, "et une fente large l'ameliore-t-elle ?"),
    ("75c", "fast", 0.5, False, 42, 45, "colonne x1 complete"),
    ("r75x1.5", "fast", 0.5, False, 42, 45, "colonne x1,5 complete"),
    ("r75x2", "deep", 1.0, True, 42, 150, "PHASE 2 -- recherche x5 plus large, resolution fixee"),
    # --- CONSOLIDATION : ne tourne qu'a 12 h ---
    ("r75x0.5", "fast", 1.0, False, 42, 45, "cellule PROPRE la ou on n'a qu'un echantillon biaise"),
    ("r75x0.5", "fast", 0.5, False, 42, 45, "idem, et complete la colonne mince"),
    ("r75x2", "fast", 1.0, False, 77, 45, "SECONDE GRAINE sur la cellule de tete (§24-46)"),
]

# 🔑 POURQUOI x0,5 A 1 nm ET 0,5 nm SONT EN CONSOLIDATION ET NON EN TETE. Le run a recherche
# de fente du 2026-08-17 en donne DEJA la tendance sur ce composant :
#
#     0,50 nm  bruit x5   367 strategies   plantage min 94,00 %
#     1,00 nm  bruit x2    54 strategies   plantage min 84,00 %
#     2,00 nm  bruit x1   375 strategies   plantage min 48,00 %
#
# Affiner AGGRAVE, monotonement. ⚠️ Mais ce sont des echantillons BIAISES -- seules les
# strategies dont les lambda toleraient la largeur ont ete retenues -- donc ils ne valent pas
# une cellule propre. D'ou leur presence en consolidation : la tendance est acquise, la mesure
# propre ne l'est pas.
#
# 🔴 ET LA SECONDE GRAINE EST LA POUR UNE RAISON MESUREE, pas par principe. §24-46 : le meme
# intervalle rend 0/452 deposables a la graine 42 et 70/521 a la graine 77. Un verdict marginal
# sur une seule graine n'etablit rien. Elle porte sur x2 a 1 nm parce que c'est la cellule dont
# le resultat changerait le plus de choses.


def _sortie(nom: str, mode: str, res: float, elargi: bool, graine: int) -> Path:
    suf = ("" if res == 2.0 else f"_res{res:g}") + ("_large" if elargi else "")
    return ROOT / "reports" / f"blocs_vs_plantage_{nom}_{mode}_s{graine:03d}{suf}.json"


def etat() -> int:
    print("=" * 92)
    print("GRILLE RESOLUTION x EPAISSEUR OPTIQUE -- etat")
    print("=" * 92)
    reste = 0
    cumul = 0
    for nom, mode, res, elargi, graine, mn, pourquoi in CELLULES:
        f = _sortie(nom, mode, res, elargi, graine)
        cumul += mn
        if f.exists():
            marque, note = "[FAIT]", f.name
        else:
            marque, note = "[    ]", f"~{mn} min -- {pourquoi}"
            reste += mn
        g = f"g{graine}" if graine != SEED else "    "
        print(f"  {marque} {nom:<9} {mode:<7} {res:>4g} nm  {'elargi' if elargi else '      '} "
              f"{g}  {cumul / 60:>4.1f}h  {note}")
    print(f"\n  reste a mesurer : {reste} min ({reste / 60:.1f} h)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heures", type=float, default=10.0,
                    help="budget d'horloge. Aucune cellule n'est ENGAGEE s'il ne reste pas sa "
                         "duree estimee -- mieux vaut une cellule non lancee qu'une tronquee")
    ap.add_argument("--etat", action="store_true")
    args = ap.parse_args()
    if args.etat:
        return etat()

    budget_s = args.heures * 3600.0
    t0 = time.perf_counter()
    faits, sautes, refuses = 0, 0, 0

    print("=" * 92)
    print(f"LOT : budget {args.heures:g} h | graine {SEED} | {len(CELLULES)} cellules")
    print("=" * 92, flush=True)

    for nom, mode, res, elargi, graine, mn, pourquoi in CELLULES:
        f = _sortie(nom, mode, res, elargi, graine)
        if f.exists():
            print(f"  [SAUTE] {nom} {mode} {res:g} nm g{graine} -- deja mesure ({f.name})", flush=True)
            sautes += 1
            continue

        ecoule = time.perf_counter() - t0
        restant = budget_s - ecoule
        if restant < mn * 60:
            print(f"  [REFUSE] {nom} {mode} {res:g} nm g{graine} -- il reste {restant / 60:.0f} min pour "
                  f"~{mn} min. Non engagee plutot que tronquee.", flush=True)
            refuses += 1
            continue

        # 🔴 Le plafond du banc est cale sur le temps restant, jamais au-dela. Une cellule qui
        # deborderait rendrait ECHEC_RESULT_NONE -- visible -- au lieu d'entamer les suivantes.
        plafond = int(min(21600, max(600, restant * 0.9)))
        env = dict(os.environ, CERTUS_BENCH_TIMEOUT_S=str(plafond))

        print(f"\n{'=' * 92}")
        print(f"  {nom} | {mode} | {res:g} nm | graine {graine} | {'ELARGI' if elargi else 'standard'} | "
              f"plafond {plafond} s | ecoule {ecoule / 3600:.1f} h")
        print(f"  pourquoi : {pourquoi}")
        print("=" * 92, flush=True)

        t1 = time.perf_counter()
        r = subprocess.run(
            [PY, SONDE, nom, mode, "0", "0", str(res), "1" if elargi else "0", str(graine)],
            env=env, cwd=str(ROOT), capture_output=True, text=True,
        )
        dt = time.perf_counter() - t1
        for ligne in (r.stdout or "").splitlines():
            if any(k in ligne for k in ("strategies evaluees", "fente nm", "deposables",
                                        "CONTRAINTE COMMUNE", "aucune couche contrainte",
                                        "consigne", "ECHEC_", "une seule fente", "%")):
                print(f"    {ligne}", flush=True)
        etat_txt = "OK" if f.exists() else "🔴 AUCUN FICHIER PRODUIT"
        print(f"    -> {etat_txt} en {dt / 60:.0f} min (code {r.returncode})", flush=True)
        if not f.exists() and r.stderr:
            print("    stderr :", (r.stderr or "").strip().splitlines()[-3:], flush=True)
        faits += 1

    ecoule = (time.perf_counter() - t0) / 3600.0
    print(f"\n{'=' * 92}")
    print(f"LOT TERMINE en {ecoule:.1f} h -- {faits} mesurees, {sautes} sautees, "
          f"{refuses} non engagees faute de temps")
    print("=" * 92)
    print("\n  Lire la grille :")
    print("    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_grille_resolution.py --etat")
    print("\n  ⚠️ Toute cellule rendant des DEPOSABLES doit etre rejouee en PREMIUM avant")
    print("     publication (§8), et toute cellule MARGINALE a une seconde graine (§24-46).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
