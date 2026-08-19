"""BATCH DE NUIT — 👤 2026-08-19 : « enchaîne sur un batch pour continuer à comprendre ».

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_nuit_2026-08-19.py

Lancé en autonomie, après le batch « voie de garage ».

## Pourquoi ces cinq cellules, et dans cet ordre

La journée a établi le **mécanisme** du Rate — la position terminale — et réfuté l'attaque
qui le disait inutile. Ce qui reste ouvert n'est plus « est-ce que ça marche » mais **« que
vaut ce qu'on mesure »** et **« le mécanisme est-il général »**.

### 🔴 Cellules 1 à 3 — LE VERROU : la dispersion du score n'a jamais été mesurée

📏 Mesuré le 2026-08-19 : `robustness_seed` **ne touche pas le score**.
`_resolve_consensus_seeds` fait gagner `consensus_seed_list`, et les quatre composants
portent `41,42,43,44,45` tronquée à 3 → **tous** les runs rescorent sur `[41,42,43]`. Deux
graines différentes rendent des scores identiques à **3,2e-11**.

**Conséquence : comparer 0,672 à 0,689 n'a aucun sens tant qu'on ignore le bruit du score.**
Ces trois cellules ne diffèrent QUE par le triplet de consensus. L'étendue de leurs SEEL
**est** la dispersion cherchée.

🔵 **Prédiction, posée avant** : la dispersion sera **du même ordre que les écarts entre
coupures** (0,689 → 0,752, soit 9 %). Si c'est le cas, **aucune coupure n'est distinguable
d'une autre** et il faudra le dire. Si la dispersion est très inférieure (< 2 %), alors les
coupures SONT séparables et le classement du §9 redevient lisible.

### 🔵 Cellule 4 — le mécanisme est-il GÉNÉRAL, ou propre à un composant qui échoue ?

Tout le mécanisme a été établi sur `r75x2`, **où rien ne marche en optique**. Le dossier §7
désigne le banc naturel : **`75c` à 1 nm**, la seule cellule sur 27 où le Rate gagne déjà.

🔵 **Prédiction** : si « position terminale » est un mécanisme et non un artefact, la même
forme doit apparaître — une queue tardive doit battre une queue précoce à SEEL comparable.
**Ce qui la réfuterait** : un optimum au milieu, ou aucune structure.

### 🔵 Cellule 5 — la règle d'exception de 👤, jamais mesurée, et je prédis qu'elle NUIT

> 👤 : *« sauf les couches avec au moins 2 turning points qui restent en optique »*

Trois tentatives ont échoué (contexte de swing absent, configuration qui mentait). Le
mécanisme établi aujourd'hui **prédit qu'elle dégrade** : rouvrir une couche optique au
milieu de la queue réintroduit un point de plantage **et** réexpose tout ce qui la suit.

🔵 **Prédiction** : `rate_tail_keep_optical = 4` rend **moins** de déposables que la queue
pure, ou un SEEL pire. **Ce qui la réfuterait** : un gain, qui signifierait que le
ré-ancrage POEM paie plus que le point de plantage rouvert — et ce serait un résultat neuf.

## Garde-fous

Chaque cellule écrit un artefact au nom distinct — le triplet de consensus et les coupures
entrent tous deux dans le nom. Une cellule qui échoue n'arrête pas les suivantes.
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

#: (nom, argv, coupures, triplet de consensus, minutes estimees)
#: argv = [composant, mode, fente, min_tp, resolution_nm, elargi, graine, par_swing]
CELLULES = [
    ("1_dispersion_cons41-43", ["r75x2", "fast", "0", "0", "2", "0", "42", "2"], "52", "41,42,43", 30),
    ("2_dispersion_cons51-53", ["r75x2", "fast", "0", "0", "2", "0", "42", "2"], "52", "51,52,53", 30),
    ("3_dispersion_cons61-63", ["r75x2", "fast", "0", "0", "2", "0", "42", "2"], "52", "61,62,63", 30),
    ("4_queue_sur_75c_1nm",    ["75c",   "fast", "0", "0", "1", "0", "42", "2"], "46,52,58,64,70", "", 45),
    ("5_regle_exception",      ["r75x2", "fast", "0", "0", "2", "0", "42", "3"], "46,52,58", "", 45),
]


def main() -> int:
    t0 = time.time()
    jrn = ROOT / "reports" / f"batch_nuit_{datetime.now():%Y-%m-%d_%H%M}.json"
    bilan: list[dict] = []
    print("=" * 96)
    print(f"BATCH DE NUIT — {len(CELLULES)} cellules, ~{sum(c[4] for c in CELLULES)} min estimees")
    print("=" * 96, flush=True)

    for nom, argv, coupures, cons, mn in CELLULES:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CERTUS_TAIL_CUTS"] = coupures
        if cons:
            env["CERTUS_CONSENSUS_SEEDS"] = cons
        else:
            env.pop("CERTUS_CONSENSUS_SEEDS", None)
        env["CERTUS_BENCH_TIMEOUT_S"] = str(max(5400, mn * 60 * 4))
        print(f"\n{'─' * 96}\n▶ cellule {nom} — coupures {coupures}"
              f"{' — consensus ' + cons if cons else ''} — ~{mn} min — "
              f"debut {datetime.now():%H:%M:%S}\n{'─' * 96}", flush=True)
        t = time.time()
        try:
            r = subprocess.run([PY, SONDE, *argv], cwd=str(ROOT), env=env,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=mn * 60 * 6)
            code, sortie = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, sortie = -9, "TIMEOUT du pilote"
        dt = (time.time() - t) / 60.0
        print("\n".join(sortie.splitlines()[-30:]), flush=True)
        print(f"◀ cellule {nom} : code={code} en {dt:.1f} min", flush=True)
        bilan.append({"cellule": nom, "argv": argv, "coupures": coupures, "consensus": cons,
                      "code": code, "minutes": round(dt, 1),
                      "verdict": "OK" if code == 0 else "ECHEC"})
        jrn.write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 96)
    print(f"BILAN — {sum(1 for b in bilan if b['verdict'] == 'OK')}/{len(bilan)} OK "
          f"en {(time.time() - t0) / 60:.0f} min")
    for b in bilan:
        print(f"  {b['verdict']:<6} {b['cellule']:<26} {b['minutes']:>6.1f} min")
    print("=" * 96)
    return 0 if all(b["verdict"] == "OK" for b in bilan) else 1


if __name__ == "__main__":
    sys.exit(main())
