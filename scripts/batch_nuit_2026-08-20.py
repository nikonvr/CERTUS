"""BATCH 2 DE LA NUIT — 👤 2026-08-20 : « continue a elaborer des batchs pour faire avancer
le chantier rate, et lance les directement ».

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_nuit_2026-08-20.py

Enchaine apres le batch du 19, dont les six cellules ont rendu.

## Ce que le batch du 19 a etabli, et qui commande celui-ci

| | |
|---|---|
| le **bruit du SEEL** vaut **2,59 %** sur une difference, mesure sur `r75x2` en `fast` | c'est lui qui rend tout tableau lisible ; sans lui on comparait a un sigma emprunte 2,8x trop grand |
| **la queue Rate achete de la FAISABILITE et la paie en PRECISION** | `r75x2` : 0 deposable sans elle. `75c` : elle coute jusqu'a +19 %, soit 7,4 sigma |

🔴 **ET IL RESTE UN DEFAUT DE PROTOCOLE QUI BLOQUE TOUTE PUBLICATION.** Le resultat phare du
chantier -- *la queue Rate rend `r75x2` fabricable* -- est mesure en **`fast`**, alors que la
comparaison pur optique a laquelle on l'oppose est en **`deep`**. Deux profondeurs differentes,
donc **l'erreur n° 3 du §5 de `CLAUDE.md`** : deux choses changent a la fois. Tant que ce n'est
pas repare, on ne sait pas si la queue sauve le composant ou si c'est la profondeur de recherche
qui manquait -- exactement l'attaque 3 du §12, qu'on croyait refutee.

### 🔑 CELLULES 2 ET 3 — L'EXPERIENCE CENTRALE, et elle isole la regle DANS UN SEUL COMPOSANT

La regle « faisabilite contre precision » repose aujourd'hui sur **deux composants differents**
(`r75x2` et `75c`), donc sur une comparaison qui melange l'effet de la queue et l'effet du
composant. 📏 Or `r75x2` en `deep` a 2 nm offre les deux regimes **a lui seul**, selon la graine :

    graine 42  ->    0 deposable en pur optique   (l'optique ECHOUE)
    graine 77  ->  547 deposables, SEEL 0,569     (l'optique REUSSIT, et tres bien)

**Meme composant, meme mode, meme fente, meme grille de notation. Seule la graine change.**
Y ajouter la meme queue Rate teste la regle toutes choses egales par ailleurs -- ce qu'aucune
mesure du chantier n'a encore fait.

🔵 **LA PREDICTION, posee avant que le batch ne tourne :**

> **A la graine 42 la queue SAUVE (deposables > 0). A la graine 77 elle COUTE (SEEL nettement
> au-dessus de 0,569, au-dela de 2 sigma).**

**Ce qui la refuterait, et chaque cas dit quelque chose de different :**

| observation | ce qu'il faudrait en conclure |
|---|---|
| graine 42, **0 deposable en `deep`** | 🔴 le resultat phare du chantier ne survit pas au changement de profondeur. Les 5 deposables du `fast` etaient un artefact du criblage court, et **la queue Rate ne sauve rien** |
| graine 77, la queue **egale ou bat** 0,569 | la regle « elle paie en precision » est fausse, ou du moins pas generale. Le +19 % du `75c` viendrait alors du composant, pas de la queue |
| les deux graines se comportent **pareil** | ce n'est plus la faisabilite qui commande. Il faudrait chercher ailleurs ce que la queue fait reellement |

⚠️ **Ce que ce batch ne fait PAS** : il ne mesure pas le pur optique en `deep`, deja mesure
(§13 et §14 du dossier). Il ne rejoue que la queue, a la meme profondeur, pour que la
comparaison porte enfin sur une seule difference.

### 🔴 CELLULE 2 — LE CONTROLE QUI MANQUAIT A LA REGLE D'EXCEPTION DE 👤

La cellule 5 du batch du 19 a teste la regle d'exception -- *« sauf les couches avec au moins
2 turning points qui restent en optique »* -- et elle **n'est pas interpretable** : `par_swing=3`
arme DEUX drapeaux, `rate_by_swing` **et** `rate_tail_keep_optical`, alors que la reference a
laquelle on la compare n'en a aucun. C'est l'erreur n° 3 du §5, et elle est de ma main.

📏 Et `rate_by_swing` n'est **pas** inerte sur `r75x2` : il y ajoute **26 origines** nouvelles
(`RATE_L47`, `RATE_L65`). On ne peut donc pas l'ecarter d'un revers de main.

🔑 **`par_swing = 5` est ajoute pour cela** : queue + swing, **sans** reouverture optique. Il ne
differe de `3` que par `keep_optical`, et son nom de fichier porte un `s` la ou `3` porte un `k`
-- donc aucun ecrasement possible. **Comparer 5 a 3 isole enfin la regle de 👤.**

🔵 **Prediction, inchangee depuis le 19** : la regle **degrade ou ne change rien**. Rouvrir une
couche optique au milieu de la queue reintroduit un point de plantage **et** reexpose tout ce qui
la suit. **Ce qui la refuterait** : un gain, qui signifierait que le re-ancrage POEM paie plus
que le point de plantage rouvert -- et ce serait un resultat neuf.

### 🔵 CELLULE 1 — la seconde graine du `75c`, et elle est bon marche

Le resultat du `75c` est a **une seule graine**. Son ecart de 7,4 sigma ne peut pas etre
renverse par une graine (§16), mais la place du coude -- entre les coupures 58 et 64 -- n'est
etablie par rien. Elle passe en premier parce qu'elle coute 37 min : si le batch devait
s'interrompre, c'est elle qu'on veut avoir.

🔵 **Prediction** : meme forme monotone, coude entre 58 et 64, et la queue ne bat jamais le pur
optique. **Ce qui la refuterait** : un coude ailleurs, ou une queue qui gagne.

## Garde-fous

Chaque cellule ecrit un artefact au nom distinct, avec sa configuration effective dedans
(§24-7). Une cellule qui echoue n'arrete pas les suivantes. Les durees sont fondees sur les
mesures du 19 : ~37 min pour une sonde de queue en `fast`, ~117 min pour un `deep` pur optique
sur `r75x2` -- d'ou ~145 min pour un `deep` porteur de trois coupures.
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
SONDE = str(ROOT / "scripts" / "probe_blocs_vs_plantage.py")

#: (nom, argv, coupures, minutes estimees)
#: argv = [composant, mode, fente, min_tp, resolution_nm, elargi, graine, par_swing]
#: par_swing = 2 -> balayage de queue
CELLULES = [
    ("1_75c_1nm_graine77",  ["75c",   "fast", "0", "0", "1", "0", "77", "2"], "46,52,58,64,70", 40),
    ("2_controle_exception", ["r75x2", "fast", "0", "0", "2", "0", "42", "5"], "46,52,58", 40),
    ("3_r75x2_deep_s042",   ["r75x2", "deep", "0", "0", "2", "0", "42", "2"], "49,52,55", 150),
    ("4_r75x2_deep_s077",   ["r75x2", "deep", "0", "0", "2", "0", "77", "2"], "49,52,55", 150),
]


def main() -> int:
    t0 = time.time()
    jrn = ROOT / "reports" / f"batch_nuit_{datetime.now():%Y-%m-%d_%H%M}.json"
    bilan: list[dict] = []
    print("=" * 96)
    print(f"BATCH 2 — {len(CELLULES)} cellules, ~{sum(c[3] for c in CELLULES)} min estimees")
    print(f"journal : {jrn.name}")
    print("=" * 96, flush=True)

    for nom, argv, coupures, mn in CELLULES:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CERTUS_TAIL_CUTS"] = coupures
        env.pop("CERTUS_CONSENSUS_SEEDS", None)   # defaut du JSON, comme au §3bis
        env["CERTUS_BENCH_TIMEOUT_S"] = str(max(5400, mn * 60 * 4))
        print(f"\n{'─' * 96}\n▶ cellule {nom} — coupures {coupures} — ~{mn} min — "
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
        # 🔴 LE JOURNAL COMPLET VA SUR DISQUE, PAS SEULEMENT SA QUEUE.
        # 📏 Defaut trouve le 2026-08-20 : ce pilote CAPTURE tout le journal
        # (`capture_output=True`) puis n'en imprimait que les 30 dernieres lignes -- le
        # reste etait jete. Toute analyse de journal faite sur un run de batch portait donc
        # sur une queue. C'est ainsi que j'ai lu « ELITE n'a rien ajoute a la graine 77 »
        # alors que l'artefact porte 743 strategies ELITE : je ne voyais qu'un round sur N,
        # et j'ai failli en tirer un mecanisme.
        jrnl = ROOT / "reports" / f"journal_{nom}_{datetime.now():%Y%m%d_%H%M%S}.log"
        jrnl.write_text(sortie, encoding="utf-8", errors="replace")
        print(f"  journal complet : {len(sortie.splitlines())} lignes -> {jrnl.name}",
              flush=True)
        print("\n".join(sortie.splitlines()[-30:]), flush=True)
        print(f"◀ cellule {nom} : code={code} en {dt:.1f} min", flush=True)
        bilan.append({"cellule": nom, "argv": argv, "coupures": coupures,
                      "code": code, "minutes": round(dt, 1),
                      "verdict": "OK" if code == 0 else "ECHEC"})
        jrn.write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 96)
    print(f"BILAN — {sum(1 for b in bilan if b['verdict'] == 'OK')}/{len(bilan)} OK "
          f"en {(time.time() - t0) / 60:.0f} min")
    for b in bilan:
        print(f"  {b['verdict']:<6} {b['cellule']:<24} {b['minutes']:>6.1f} min")
    print("=" * 96)
    return 0 if all(b["verdict"] == "OK" for b in bilan) else 1


if __name__ == "__main__":
    sys.exit(main())
