"""LA CASE MANQUANTE, PUIS LA COURBE — 👤 2026-08-19, « les deux dans cet ordre ».

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_voie_de_garage.py

## Ce que ce batch tranche, et pourquoi il passe AVANT tout le reste

L'analyse contradictoire du 2026-08-19 (docs/CHANTIER_RATE.md §12) a trouve que **la case
decisive n'avait jamais ete lancee** : `r75x2` en `deep` a **2 nm** n'existe pas. Toute la
queue Rate repose sur du `fast` (N=50) et du `premium` (N=150) a 2 nm, qui rendent zero
deposable en pur optique.

📏 Or a **1 nm**, passer de `fast` a `deep` a fait **0 -> 277 deposables**. Ce n'etait donc
pas la FENTE qui sauvait, c'etait la **PROFONDEUR DE RECHERCHE**. Rien ne dit que `deep` a
2 nm ne ferait pas la meme chose.

🔴 **Si c'est le cas, la queue Rate sur ce composant est une voie de garage**, et il faudra
l'ecrire noir sur blanc plutot que continuer a l'optimiser.

⚠️ **Deux graines, et ce n'est pas du luxe.** Meme configuration a 1 nm : graine 42 rend
**254** deposables, graine 77 en rend **0**. §24-46, basculement categoriel. Une seule graine
ne peut donc rien conclure ici, dans un sens comme dans l'autre.

## Le protocole est celui du run de reference, deliberement

`allow_rate` reste a sa valeur par defaut (vrai, §19) : c'est le protocole du run
`r75x2_deep_s042_res1` qui a rendu les 277, et dont la gagnante etait `ELITE`, pur optique.
Changer le protocole pour la comparaison rendrait la comparaison invalide. On separera pur
optique et Rate **a l'analyse**, pas a la generation.

## Puis la courbe SEEL(n), qui ne depend pas de l'issue ci-dessus

Cellule 3 : la sonde de 👤 -- `n` couches optiques, le reste a epaisseur PARFAITE, pour
`n` de 2 a 75. Elle est bon marche et diagnostique quoi qu'il arrive aux cellules 1 et 2.
"""

from __future__ import annotations

import json
import os
import subprocess
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

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

#: (nom, script, argv, minutes estimees)
#: sonde de blocs : [composant, mode, fente, min_tp, resolution_nm, elargi, graine, par_swing]
CELLULES = [
    ("1_deep_2nm_s042", "probe_blocs_vs_plantage.py",
     ["r75x2", "deep", "0", "0", "2", "0", "42", "0"], 150),
    ("2_deep_2nm_s077", "probe_blocs_vs_plantage.py",
     ["r75x2", "deep", "0", "0", "2", "0", "77", "0"], 150),
    ("3_courbe_SEEL_n", "probe_prefixe_optique.py",
     ["r75x2", "deep", "42"], 120),
]


def main() -> int:
    t0 = time.time()
    jrn = ROOT / "reports" / f"batch_voie_de_garage_{datetime.now():%Y-%m-%d_%H%M}.json"
    bilan: list[dict] = []
    print("=" * 96)
    print(f"BATCH « VOIE DE GARAGE » -- {len(CELLULES)} cellules, "
          f"~{sum(c[3] for c in CELLULES)} min estimees")
    print("=" * 96, flush=True)

    for nom, script, argv, mn in CELLULES:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # 🔴 §21 : au-dela du plafond le banc rend `RESULT=None` et un tableau tronque, ce qui
        # RESSEMBLE a un resultat. Le plafond suit donc l'estimation de la cellule.
        env["CERTUS_BENCH_TIMEOUT_S"] = str(max(5400, mn * 60 * 4))
        print(f"\n{'─' * 96}\n▶ cellule {nom} -- ~{mn} min -- debut "
              f"{datetime.now():%H:%M:%S}\n{'─' * 96}", flush=True)
        t = time.time()
        try:
            r = subprocess.run([PY, str(ROOT / "scripts" / script), *argv],
                               cwd=str(ROOT), env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=mn * 60 * 5)
            code, sortie = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, sortie = -9, "TIMEOUT du pilote"
        dt = (time.time() - t) / 60.0
        print("\n".join(sortie.splitlines()[-35:]), flush=True)
        print(f"◀ cellule {nom} : code={code} en {dt:.1f} min", flush=True)
        bilan.append({"cellule": nom, "script": script, "argv": argv,
                      "code": code, "minutes": round(dt, 1),
                      "verdict": "OK" if code == 0 else "ECHEC"})
        jrn.write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 96)
    print(f"BILAN -- {sum(1 for b in bilan if b['verdict'] == 'OK')}/{len(bilan)} cellules OK "
          f"en {(time.time() - t0) / 60:.0f} min")
    for b in bilan:
        print(f"  {b['verdict']:<6} {b['cellule']:<20} {b['minutes']:>6.1f} min")
    print("=" * 96)
    return 0 if all(b["verdict"] == "OK" for b in bilan) else 1


if __name__ == "__main__":
    sys.exit(main())
