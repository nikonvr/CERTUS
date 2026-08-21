"""LIRE LA COURBE SEEL(n) ET crash(n) -- et refuser de la sur-interpreter.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_courbe_prefixe.py [artefact...]

## Les deux courbes ne disent pas la meme chose, et ne se lisent pas pareil

    crash(n)   MONOTONE par construction. La croissance est causale : les couches 0..n-1 se
               comportent a l'identique que la couche n soit optique ou parfaite, et ajouter
               une couche optique ne peut qu'ajouter une occasion de planter. La falaise y est
               donc NON AMBIGUE, et c'est elle qui commande -- mesure du 2026-08-19, le crash
               fait un facteur 25 la ou le SEEL reste plat a 9 % pres.

    SEEL(n)    PAS monotone, et 👤 a insiste : « il faut la tracer ENTIEREMENT ». POEM se
               re-ancre et CORRIGE l'erreur amont (protection x34,8, §24-17), donc une couche
               optique de plus peut faire BAISSER l'erreur totale. Ce sont les REMONTEES
               LOCALES qui designent les couches ou la surveillance optique nuit.

## 🔴 CE QUE CE LECTEUR REFUSE DE FAIRE

**Afficher un SEEL la ou ca plante.** Un score rendu quand la strategie ne va pas au bout est
un SCORE DE REPLI, pas une performance -- §21 : *« comparer deux configurations sur des scores
de repli revient a comparer deux facons d'echouer »*. Le 0,86 nm du 99c a circule des mois pour
cette raison. Au-dela du seuil de plantage, la colonne SEEL affiche `repli`, pas un nombre.

**Designer un optimum.** Il rend la forme ; la decision est au physicien.
"""

from __future__ import annotations

import glob
import json
import math
import os
import sys
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CRASH_TOL = 0.05
#: Une remontee est signalee au-dela de ce seuil relatif. 🔴 Ce n'est PAS un test de
#: signification : la dispersion du score n'a jamais ete mesuree sur ce composant (le
#: consensus le fige sur ses propres graines, §10 du dossier). C'est un repere de LECTURE.
SEUIL_REMONTEE = 0.02

BARRES = "▁▂▃▄▅▆▇█"


def spark(vals: list[float | None]) -> str:
    reels = [v for v in vals if v is not None]
    if not reels:
        return ""
    lo, hi = min(reels), max(reels)
    if hi - lo < 1e-15:
        return BARRES[0] * len(vals)
    return "".join(" " if v is None else BARRES[min(7, int(7 * (v - lo) / (hi - lo)))]
                   for v in vals)


def lire(p: str) -> None:
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    c = d.get("courbe") or []
    if not c:
        print(f"  {os.path.basename(p)} : COURBE VIDE")
        print("  🔴 Verifier le journal : si `[PREFIX] ... SANS OBJET` y figure, la population")
        print("     ne portait aucune strategie a surveillance couche par couche.")
        return
    c.sort(key=lambda z: z["n_opt"])
    print(f"\n{'=' * 96}\n  {os.path.basename(p)}")
    print(f"  composant={d.get('composant')} mode={d.get('mode')} graine={d.get('seed')} "
          f"couches={d.get('n_couches')}  profondeur={d.get('profondeur')}")
    print("=" * 96)

    ns = [x["n_opt"] for x in c]
    crash = [x["crash_rate"] for x in c]
    seel = [2 * math.sqrt(x["score"]) if x["crash_rate"] < CRASH_TOL else None for x in c]

    print(f"\n  crash(n)  {spark([v for v in crash])}   de {100 * min(crash):.1f} % "
          f"a {100 * max(crash):.1f} %")
    print(f"  SEEL(n)   {spark(seel)}   (blanc = plantage > {100 * CRASH_TOL:.0f} %, "
          f"donc score de REPLI, non affiche)")

    # --- la falaise, sur la courbe qui est monotone --------------------------------------
    franchi = next((n for n, k in zip(ns, crash) if k >= CRASH_TOL), None)
    if franchi is None:
        print(f"\n  🟢 le plantage ne franchit JAMAIS {100 * CRASH_TOL:.0f} % sur "
              f"n = {ns[0]}..{ns[-1]} : l'optique tient sur tout l'empilement.")
    else:
        i = ns.index(franchi)
        av = f"{100 * crash[i - 1]:.2f} %" if i else "-"
        print(f"\n  🔴 LA FALAISE : le plantage franchit {100 * CRASH_TOL:.0f} % a n = {franchi}"
              f"  ({av} a n = {franchi - 1} -> {100 * crash[i]:.2f} % a n = {franchi})")
        print(f"     C'est LA que la surveillance optique cesse d'etre tenable, et c'est donc")
        print(f"     la que le Rate doit prendre le relais.")

    # --- les remontees de SEEL, sur la courbe qui ne l'est pas ----------------------------
    print(f"\n  {'n':>5}{'crash':>9}{'SEEL':>9}{'d(SEEL)':>10}   remarque")
    print("  " + "-" * 74)
    prec = None
    remontees = []
    for n, k, s in zip(ns, crash, seel):
        if s is None:
            print(f"  {n:>5}{100 * k:>8.2f}%{'repli':>9}{'-':>10}   "
                  f"{'plante : aucun score exploitable' if k >= CRASH_TOL else ''}")
            prec = None
            continue
        d_rel = None if prec is None else (s - prec) / prec
        note = ""
        if d_rel is not None and d_rel > SEUIL_REMONTEE:
            note = f"🔺 REMONTEE +{100 * d_rel:.1f} % -- l'optique nuit a cette couche"
            remontees.append((n, d_rel))
        elif d_rel is not None and d_rel < -SEUIL_REMONTEE:
            note = f"🟢 baisse {100 * d_rel:.1f} % -- POEM compense en se re-ancrant"
        print(f"  {n:>5}{100 * k:>8.2f}%{s:>9.3f}"
              f"{('-' if d_rel is None else f'{100 * d_rel:+.1f}%'):>10}   {note}")
        prec = s

    print(f"\n  🔑 {len(remontees)} remontee(s) au-dela de {100 * SEUIL_REMONTEE:.0f} % : "
          f"{[n for n, _ in remontees[:12]]}")
    print("  ⚠️ Ce seuil est un repere de LECTURE, pas un test de signification : la dispersion")
    print("     du score n'a jamais ete mesuree sur ce composant -- le consensus le fige sur")
    print("     ses propres graines (§10 du dossier). Ne pas lire une remontee isolee comme")
    print("     un fait ; lire la FORME, comme 👤 l'a demande.")


def main() -> int:
    motifs = sys.argv[1:] or ["reports/prefixe_optique_*.json"]
    vus = 0
    for m in motifs:
        for p in sorted(glob.glob(str(ROOT / m)) or glob.glob(m)):
            lire(p)
            vus += 1
    if not vus:
        print("  aucun artefact de courbe -- la sonde n'a pas encore rendu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
