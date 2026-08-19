"""BATCH RATE SUR LE 75c x2 -- 👤 2026-08-19, « entre 2 et 4 h », lancé en son absence.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_rate_2026-08-19.py

## Pourquoi ces cellules-la, et pas d'autres

Deux corrections de code sont tombees le 2026-08-19, toutes deux sur instruction de 👤, et
toutes deux changent le vivier ou l'arithmetique du Rate :

    1. la DERNIERE couche devient candidate (elle etait exclue -- 0 placement sur 24 581),
       et les couches 0 et 1 sont refusees explicitement au lieu de degrader en silence ;
    2. le facteur de rate ne se calcule plus QUE sur les couches optiquement deposees.

🔴 C1 : **toute mesure Rate anterieure decrit un autre solveur.** La premiere cellule est donc
un REJEU a l'identique de la campagne de queue, sans quoi rien d'autre n'est interpretable.

## Ce que chaque cellule DECIDE -- ecrit avant de lancer

┌───┬────────────────────────────────┬──────────────────────────────────────────────────────┐
│ 1 │ s042, coupures 46..64          │ le correctif deplace-t-il la falaise ? PREDICTION :  │
│   │                                │ oui, vers des queues plus COURTES. Le vivier de      │
│   │                                │ references ne grossit plus dans la queue, donc une   │
│   │                                │ longue queue est desormais penalisee.                │
├───┼────────────────────────────────┼──────────────────────────────────────────────────────┤
│ 2 │ s077, memes coupures           │ §24-46 : un verdict sur un intervalle marginal n'est │
│   │                                │ pas determine par une graine. Sans cette cellule,    │
│   │                                │ rien de la cellule 1 n'est publiable.                │
├───┼────────────────────────────────┼──────────────────────────────────────────────────────┤
│ 3 │ premium s042, coupures 52..58  │ le 4,00 % est 2/50 en `fast` : la granularite        │
│   │                                │ minimale au-dessus de zero, pas une mesure. A        │
│   │                                │ N = 150 il devient 6/150 et le SEEL perd un facteur  │
│   │                                │ sqrt(3) de bruit -- de quoi enfin departager les     │
│   │                                │ coupures, ce que `fast` ne peut pas faire.           │
└───┴────────────────────────────────┴──────────────────────────────────────────────────────┘

⚠️ Ce que ce batch NE fait PAS, et pourquoi :

  · pas de `rate_tail_keep_optical` (la regle d'exception de 👤). Trois tentatives ont
    echoue et je ne lance pas une 4e a l'aveugle en son absence : une cellule qui meurt
    coute 40 min pour rien. Elle passe apres, avec un essai de mise en route court.
  · pas d'autre composant. 👤 a demande le 75c x2.
  · pas de mode `deep`. A N = 300 une seule cellule mangerait le budget entier.

## Garde-fous

  · chaque cellule ecrit un artefact au nom DISTINCT (le suffixe porte mode, graine et
    coupures), donc aucune ne peut en ecraser une autre -- c'est la panne du 2026-08-19 ;
  · une cellule qui echoue n'arrete pas les suivantes, et son echec est consigne ;
  · le plafond du banc suit l'estimation de la cellule (§21 : au-dela, `RESULT=None`
    ressemble a un resultat) ;
  · rien d'autre ne doit tourner : le pipeline sature tous les coeurs en `prange`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SONDE = str(ROOT / "scripts" / "probe_blocs_vs_plantage.py")

#: (nom, argv de la sonde, coupures, minutes estimees)
#: argv = [composant, mode, fente, min_tp, resolution_nm, elargi, graine, par_swing]
#: par_swing = 2 -> balayage de queue sur CERTUS_TAIL_CUTS
CELLULES = [
    ("1_s042_46-64", ["r75x2", "fast", "0", "0", "2", "0", "42", "2"],
     "46,49,52,55,58,61,64", 60),
    ("2_s077_46-64", ["r75x2", "fast", "0", "0", "2", "0", "77", "2"],
     "46,49,52,55,58,61,64", 60),
    ("3_premium_s042_52-58", ["r75x2", "premium", "0", "0", "2", "0", "42", "2"],
     "52,55,58", 75),
]


def main() -> int:
    t0 = time.time()
    jrn = ROOT / "reports" / f"batch_rate_{datetime.now():%Y-%m-%d_%H%M}.json"
    bilan: list[dict] = []
    print("=" * 96)
    print(f"BATCH RATE 75c x2 -- {len(CELLULES)} cellules, "
          f"~{sum(c[3] for c in CELLULES)} min estimees")
    print(f"journal : {jrn.name}")
    print("=" * 96, flush=True)

    for nom, argv, coupures, mn in CELLULES:
        env = dict(os.environ)
        env["CERTUS_TAIL_CUTS"] = coupures
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # 🔴 §21 : le plafond du banc suit l'estimation de la cellule. Il etait en dur a
        # 1800 s, et au-dela le banc rend `RESULT=None` avec un tableau tronque -- ce qui
        # RESSEMBLE a un resultat. Quatre fois l'estimation laisse de la marge sans
        # transformer une cellule bloquee en attente infinie.
        env["CERTUS_BENCH_TIMEOUT_S"] = str(max(5400, mn * 60 * 4))
        print(f"\n{'─' * 96}\n▶ cellule {nom} -- coupures {coupures} -- ~{mn} min "
              f"-- debut {datetime.now():%H:%M:%S}\n{'─' * 96}", flush=True)
        t = time.time()
        try:
            r = subprocess.run([PY, SONDE, *argv], cwd=str(ROOT), env=env,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=mn * 60 * 5)
            code, sortie = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, sortie = -9, "TIMEOUT du pilote"
        dt = (time.time() - t) / 60.0
        # On garde la fin de la sortie : c'est la que la sonde imprime ses tableaux.
        queue = "\n".join(sortie.splitlines()[-40:])
        print(queue, flush=True)
        print(f"◀ cellule {nom} : code={code} en {dt:.1f} min", flush=True)
        bilan.append({"cellule": nom, "argv": argv, "coupures": coupures,
                      "code": code, "minutes": round(dt, 1),
                      "verdict": "OK" if code == 0 else "ECHEC"})
        jrn.write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 96)
    print(f"BILAN -- {sum(1 for b in bilan if b['verdict'] == 'OK')}/{len(bilan)} cellules OK "
          f"en {(time.time() - t0) / 60:.0f} min")
    for b in bilan:
        print(f"  {b['verdict']:<6} {b['cellule']:<24} {b['minutes']:>6.1f} min")
    print("=" * 96)
    return 0 if all(b["verdict"] == "OK" for b in bilan) else 1


if __name__ == "__main__":
    sys.exit(main())
