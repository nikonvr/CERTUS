# 99c, isolation des leviers du Rate élargi, graine 42 (2026-10-17)

Mesure exploratoire à une graine, **pas le protocole A9**. Protocole figé avant le lancement : `protocol.json` ; chaîne : `chain.sh` (journaux `*.log` ignorés par Git, conservés localement).
`python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 42`, HEAD `7f3edea8`, code suivi propre. Surcharges de sonde : C1 `elite_rate_max_candidates=240`, C2 `elite_rate_max_candidates=240,elite_rounds=6`.
Les deux bras sortent `exit=0` : C1 29 min 11 s (00:28:03Z à 00:57:14Z), C2 44 min 13 s (00:57:17Z à 01:41:30Z). Les journaux montrent ELITE jusqu'au tour 2 sur 2 (C1) et 6 sur 6 (C2), graines de consensus 41/42/43, 150 tirages.
Artefacts, non suivis et archivés hors dépôt (fin du document) : `reports/blocs_vs_plantage_99c_premium_s042_rate_budget240_seul.json` (17,6 Mo) et `..._rate_budget240_six_tours.json` (19,8 Mo).

## Résultat mesuré
Même graine de recherche (42) et mêmes graines de consensus dans les cinq lignes. `A` et `B` sont les mesures du 2026-10-16 ([bilan](../STRAT_99c_rate_elargi_2026-10-16/bilan.md)). « B natif » est le meilleur plan de B qui ne vient pas de `RATE_POST`, donc le résultat de la recherche avant le raffinement final (le raffinement tourne après la recherche et ne la change pas).

| bras | ce qui change | stratégies / déposables | meilleur score de consensus | pas | meilleur SEEL | pas |
|---|---|---|---|---|---|---|
| A, défauts de production | rien | 4 761 / 4 761 | 0,125451 | | 0,7026 nm | |
| C1 | budget Rate 240 (au lieu de 120) | 4 827 / 4 827 | 0,105463 | −15,93 % | 0,6495 nm | −7,55 % |
| C2 | + six tours (au lieu de deux) | 5 378 / 5 378 | 0,103223 | −2,12 % | 0,6426 nm | −1,07 % |
| B natif | + 480 voisins conjoints | dans B : 6 338 / 6 302 | 0,093363 | −9,55 % | 0,6099 nm | −5,08 % |
| B | + raffinement final | 6 338 / 6 302 | 0,092536 | −0,89 % | 0,6084 nm | −0,25 % |

Part de l'écart entre A et B natif, sur le score de consensus puis sur le SEEL : budget 240 **62,3 %** (57,3 %), six tours **7,0 %** (7,5 %), 480 voisins conjoints **30,7 %** (35,2 %). Cumul à B : −26,24 % (score), −13,41 % (SEEL).

Meilleurs plans : A (consensus) `991650062` `RATE_RESCUE6`, 16 blocs, 93 couches Rate ; A (SEEL) queue Rate L11–L99, 7 blocs. C1 `901350948` ELITE, 13 blocs, 88 couches Rate, **mixte** (Rate L10–L61 et L64–L99, optique L1–L9 et L62–L63). C2 `900451204` ELITE, 4 blocs, 90 couches Rate, mixte (Rate L6, L9–L81 et L84–L99). B natif `901353897` ELITE, 13 blocs, 86 couches Rate. Plantage minimal 0,00 % partout ; **toutes** les stratégies de C1 et de C2 sont déposables. Plans mixtes déposables : 543 (C1) et 1 014 (C2) ; plans de queue : 4 284 et 4 364.

## Lecture prudente (celle du protocole)
1. Le seul repère de bruit est l'écart du score de consensus de B entre deux graines (0,092536 contre 0,096388, soit 4,2 %) : un pas plus petit n'est pas interprété.
2. **Budget Rate 240** : −15,93 %, hors du bruit, la plus grande part de l'écart (62 %). Doubler le nombre de candidats Rate ajoutés par tour, sans toucher au nombre de tours, suffit à obtenir la majeure partie du gain du profil élargi à cette graine.
3. **Six tours** : −2,12 %, sous le bruit : non interprété. Les six tours ont bien tourné ; cette mesure n'y voit rien au-delà du bruit, ce qui n'est pas la même chose que « rien ».
4. **480 voisins conjoints** : −9,55 %, hors du bruit, 31 % de l'écart. Ce pas se lit B natif contre C2, dont la seule différence est `elite_rate_joint_candidates=480`. Le rapport d'expertise du 2026-10-13 notait que la contribution propre de ce voisinage n'était pas confirmée à budgets égaux : à budgets égaux, ce pas va ici dans le sens d'une contribution propre, à une graine.
5. **Raffinement final** : −0,89 %, sous le bruit (déjà lu au bilan du 16 octobre).

## Limites
- Une graine de recherche, un run par bras, aucun intervalle de confiance. La répétition à la graine 101 est lancée : `reports/STRAT_99c_isolation_leviers_graine101_2026-10-17/`.
- Un seul chemin de décomposition (A, C1, C2, B natif) : les leviers interagissent (le budget se dépense à chaque tour), un autre ordre peut attribuer autrement.
- **Charge étrangère pendant C2.** Un processus Python extérieur à ce travail (`studies\bonne_mere\scripts\pglobal_blocks.py`, processus parent 28272, probablement l'application Codex) a démarré à 03:17:46 heure locale (01:17:46Z), tournait pendant les 24 dernières des 44 minutes de C2 et tournait encore à 01:45Z. La recherche n'a aucun budget en temps réel (`time.perf_counter` ne sert qu'aux lignes de journal ; le seul délai est une garde de 600 s sur un segment bloqué, qui n'a pas joué : aucune occurrence de `timeout` dans les deux journaux). La charge change donc les durées, et aucun résultat connu n'en dépend ; je ne l'ai pas vérifié par une répétition. Les durées de C1 et de C2 ne se comparent pas.
- Les 26 lignes `ERROR` de chaque journal sont le même message, `[ROBUSTNESS] NONE of the N strategies holds under 5% of non-terminating depositions` ; le résultat final de chaque bras est néanmoins entièrement déposable.
- L'outil de résumé affiche « arbre modifié » : des documents seulement, le code suivi est identique au commit.
- Un Rate sans dérive de vitesse (A6), pas de groupe frais, pas de confirmation indépendante : c'est le modèle de STRAT, pas une fabrication.
- Aucun défaut n'est changé par cette mesure. Faire de 240 le défaut de `elite_rate_max_candidates` reste une décision de 👤 (`docs/ETAT.md`, §0).

## Archives
Les quatre artefacts de la graine 42 (A, B, C1, C2) sont compressés sans perte hors du dépôt, dans `D:\drivfl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\Archives_CERTUS_20261017\reports\*.json.gz`, avec `manifest.jsonl` (chemin d'origine, octets et SHA256 du brut et du gzip). Chaque gzip a été relu et son SHA256 décompressé comparé à celui du brut avant le retrait du brut. Restaurer : `gzip -dc <archive>.json.gz > reports/<nom>.json`, puis comparer `sha256sum` à `raw_sha256` du manifeste. Le script d'analyse (`analyse_isolation_leviers.py.txt`, lancé par `python -I analyse_isolation_leviers.py.txt A=… C1=… C2=… B=…` sur les artefacts restaurés) et celui d'archivage (`archive_artefacts.sh`) sont dans ce dossier.
