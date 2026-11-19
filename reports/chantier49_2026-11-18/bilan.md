# Chantier 49 — STRAT sur la Bonne Mère, graine 42 : bilan

Composant : la Bonne Mère, 90 couches H800 Nb₂O₅ / H800 SiO₂ sur silice, 400–728,85 nm, couloir d'indice 0,005, réglage
STRAT DEEP de la campagne du 23 octobre ([banc](bench_bonne_mere.py)). Périmètre (👤, 18 novembre) : une graine STRAT,
42, sans plafond de durée ; graines 101 et 202 abandonnées.

## Résultat

Plans choisis par STRAT (master `b217c138`), notés hors de STRAT sur les graines disjointes 2026111801–03, 400 tirages
chacune ([rescore_plan.py](rescore_plan.py), sorties `runs/*.rescore*.json` ; les deux notations, la seconde sur `b42af149`, rendent les mêmes chiffres).

| design | durée STRAT | blocs | couches au Rate | arrêts | P95 aux bruits 0,025 / 0,05 / 0,1 % | SEEL (nm) |
|---|---:|---:|---:|---:|---|---:|
| nominal (`best_design_needle_swap_90_nominal`) | 13 415 s | 90 | 64 / 90 | 0 / 0 / 0 | 0,005781 / 0,005849 / 0,006737 | **0,1642** |
| robuste (`best_design_robust_opt_90`) | 11 895 s | 40 | 75 / 90 | 0 / 0 / 0 | 0,005024 / 0,005470 / 0,007187 | **0,1696** |

- Le robuste n'est pas meilleur : SEEL +3,3 %. Il gagne aux deux bruits faibles et perd au plus fort (0,1 %), qui fixe le
  SEEL. L'écart est du même ordre que la dispersion d'une graine de tirage à l'autre (rejeu 41/42/43 à 300 tirages, bruit
  0,1 % : P95 étalé de 4,7 % pour le nominal et 6,5 % pour le robuste, soit 2,3 % et 3,2 % sur le SEEL) : la mesure ne
  les sépare pas nettement. La variabilité d'une graine
  STRAT à l'autre n'est pas mesurée (une seule graine).
- Les deux plans ne laissent aucun arrêt sur 1 200 tirages, et le Rate y domine (71 % et 83 % des couches).

## Ce qui garantit les chiffres

- Rejeu de la phase 4 de STRAT, graine 42 à 300 tirages, sur le plan consigné : P95 identiques à ceux du rapport de STRAT
  (`runs/strat_reports/`) à 1e-15 près en relatif (nominal 0,005855 / 0,006025 / 0,006720 ; robuste 0,005057 / 0,005543
  / 0,006947). Paramètres, épaisseurs, indices et plan sont donc ceux du run.
- À l'arrivée : plage 400–728,85 nm, couloir 0,005, substrat silice, épaisseurs à l'arrondi de six décimales de QWOT de la
  table de STRAT près (écart relatif max 5,4e-6 et 3,8e-6).
- Le robuste a été renoté sur `b42af149`, après la fusion du chantier 21 (SPLINE seul, que STRAT n'appelle pas) ; le rejeu
  le confirme.

## Incidents

- Les runs STRAT ont fini, puis le contrôle d'épaisseur du banc les a refusés (tolérance relative 1e-9, plus stricte que
  l'arrondi de la table de STRAT). Tolérance corrigée ; plans renotés sans refaire STRAT.
- `export_excel=False` du fichier de fenêtre n'arrive pas au worker (`certus/ui/certus_strat_ui_state.py:1119` le force) :
  rapports écrits à la racine de `reports/`, rangés dans `runs/strat_reports/`.
- L'erreur `'StratParamsDTO' object has no attribute 'setdefault'` du premier essai n'est pas revenue dans les runs finis.
- Les journaux des runs (380 et 430 Mo) restent hors du dépôt.

## Pour les chantiers suivants

- **24 (mérite robuste)** : le robuste reste défavorable sous le modèle de référence (SEEL 0,1696 contre 0,1642 nm).
- **31 (épaisseurs et plan ensemble)** : écart d'épaisseurs laissé par chaque plan au bruit 0,05 %, tirages achevés
  (`runs/*.rescore2.json`) :

  | design | RMS d'erreur d'épaisseur | RMS du biais par couche | biais max (couche) | part du biais dans l'erreur quadratique |
  |---|---:|---:|---:|---:|
  | nominal | 0,1603 nm | 0,0422 nm | 0,272 nm (85) | 6,9 % |
  | robuste | 0,1694 nm | 0,0272 nm | 0,122 nm (34) | 2,6 % |

  L'erreur laissée est presque toute aléatoire : une précompensation des épaisseurs ne viserait que le biais, au plus
  6,9 % de l'erreur quadratique, soit environ 3,5 % sur son RMS.
- **32 (critère de contrôlabilité)** : deux plans ne permettent pas de corréler marges et dynamiques au SEEL.
