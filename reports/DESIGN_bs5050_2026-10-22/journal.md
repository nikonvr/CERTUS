# DESIGN, séparatrice 50/50 400–1200 nm — journal des leviers

Cas : `example/example_design/JSON-design-example.json`, T = 0,5 sur 400–1200 nm, incidence normale, face avant seule,
H (TiO₂, n4 2,35 / n7 2,30) et L (SiO₂ 1,46) sur BK7, indices de Cauchy de la fenêtre.
Contraintes de 👤 : H et L seulement, indices inchangés, ≤ 34 couches, ≤ 30 QWOT, première couche libre. Objectif :
RMSE bien sous 1e-3. Synthèse et état : [`bilan.md`](bilan.md).

**Mesure commune.** RMSE pondéré de T sur une grille fixe de 0,5 nm (1601 points), noyau certus, recoupé par l'oracle
`tests/oracle/tmm_reference.py` (`oracle_max_dT` ~1e-14). Outils :
- `scripts/design_bench.py` : `run` lance le vrai workflow de la fenêtre ; `eval` juge un fichier de design.
- `scripts/design_probe.py` : optimise hors fenêtre avec `cost_numba_fast` et `compute_gradient_all_layers_analytic`
  (les noyaux du worker DESIGN), sur la grille fixe ; `--save` écrit un fichier relu par `design_bench.py eval`.
- Convention QWOT ↔ nm de DESIGN : **n4** (indice à 400 nm), pas n(λ₀) ; la sonde l'applique (aller-retour exact à 6e-13).

Données : `best_*.json` (designs) ; les lignes brutes `*.jsonl` et les journaux `*.log` restent locaux (ignorés par git).

## Leviers

| # | levier | implantation | commande | RMSE | couches | évals | statut |
|---|---|---|---|---|---|---|---|
| 0 | workflow DESIGN actuel (PGLOBAL → cleanup → healing → aiguilles, `allow_growth`) | fenêtre, inchangée | `design_bench.py run` ×3 (+1 run de `bench_examples`) | 0,0018 – 0,0042 | 21 – 27 | ~900 k | référence |
| — | ancien design `seed-A` | fichier d'exemple | `design_bench.py eval` | 0,001432 | 20 | — | candidat |
| 1 | départs multiples : N couches alternées, épaisseurs uniformes 0,05–1,2 QWOT, L-BFGS-B (bornes 0–400 nm, ftol 1e-15) sur la grille fixe | `design_probe.py::multistart` | `multistart --layers 26 --starts 200 --seed 1` (H au substrat) | 0,001173 | 25 | 226 k | — |
| 1 | idem | idem | `multistart --layers 32 --starts 200 --seed 1` (H au substrat) | 0,000612 (oracle 0,0006125) | 32 · 24,6 QWOT | 406 k | vérifié |
| 1 | idem | idem | `multistart --layers 34 --starts 200 --seed 1` (H au substrat) | **0,000479** (oracle 0,0004787, écart max 0,22 %) | 34 · 24,7 QWOT | 468 k | vérifié, meilleur |
| 2 | aiguilles : couche de 1 nm essayée tous les 2 nm dans chaque couche, des deux matériaux, + une au sommet ; la meilleure est gardée, polie, couches < 1 nm retirées ; arrêt après 5 insertions sans gain | `design_probe.py::needle`, `best_insertion` | `needle --layers 34 --from JSON-design-seed-A.json` | 0,001172 | 20 · 19,5 QWOT | 2 k | échec : aucune insertion n'aide ; le seul gain vient du repolissage de seed-A sur la grille fixe (0,001432 → 0,001172) |
| 3 | refine : 200 tours alternant saut de bassin (épaisseurs × (1 + 0,05·N(0,1)), polissage) et échange à nombre fixe (retirer la plus fine, réinsérer la meilleure aiguille de 1 nm, polir) ; toute amélioration gardée | `design_probe.py::refine` | `refine --from best_ms34.json --rounds 200 --qwot-max 30` | 0,0003545 (oracle idem) | 33 non nulles · 25,4 QWOT | 385 k | gain ×1,35 sur le départ |
| 4 | départs plus épais, descente en n4·d | `multistart`, `--optical --qw-max 1.6` | `multistart --layers 34 --starts 200 --optical --qw-max 1.6 --seed 2 --qwot-max 30` | 0,000634 | 34 · 25,9 QWOT | 432 k | pas mieux que le levier 1 (une seule graine) |
| 5 | **mémétique** : population de 30 designs polis (le meilleur à 34 c. + 29 départs aléatoires, une seule alternance pour tous) ; un enfant = parent A dont un bloc de couches [lo, hi) est pris dans le parent B, épaisseurs × (1 + 0,02·N(0,1)), poli ; il remplace le pire s'il le bat et n'est pas un doublon | `design_probe.py::memetic` | `memetic --layers 34 --from best_ms34.json --pop 30 --rounds 300 --seed 3 --qwot-max 30` | **0,0001676** (oracle 0,0001676, écart max 0,10 %) | 32 réelles (une H à 0 nm sépare deux L) · 25,6 QWOT | 778 k | vérifié, **meilleur** ; encore en progrès à la fin |

## Dans la fenêtre (DESIGN réel), départ 34 couches QWOT

Fichier `config_34_layers.json` (l'exemple, 34 lignes HL à 1 QWOT ; son `"allow_growth": false` n'a **jamais été appliqué** : la fenêtre ignorait le bloc `optim` des fichiers jusqu'à `a813fa64`, et tous ces runs ont tourné avec la croissance de la fenêtre, active, et ses n100/grappes par défaut ; ils sont restés à 34 couches au plus).
Commande : `design_bench.py run --config config_34_layers.json --kw memetic_children=300 --kw memetic_population=30 …`.
« étape » = coût du mémétique seul (grille de la fenêtre, 140 points) ; « final » = fin du workflow, grille fixe.

| run | changement (commit) | étape (RMSE) | final RMSE | couches · QWOT · plus fine | constat |
|---|---|---|---|---|---|
| win34_memetic300 | `run_optim(..., memetic_children=300)` (2626373a) | non tracée | 0,00373 | 32 · 30,9 · 10,9 nm | journal sur le logger racine, invisible |
| _b | journaux sur le logger `CERTUS` | 0,0125 | 0,00294 | 29 | population tirée dans les bornes élargies (3 QWOT/couche) : ~50 QWOT |
| _init | population tirée dans les bornes globales, polie dans les larges (05d6cff7) | 0,0031 | 0,00154 | 31 · 26,1 · 5,6 nm | polissages courts (~45 appels) |
| _snap | couche < `MIN_THICKNESS` évaluée absente : plus de falaise 1e30 (a3610e03) | **0,00039** | ruiné | — | le workflow atteint 0,000161 (34 c.) puis la règle des 5 nm retire 1 couche sans réoptimiser → 0,001035 ; un autre run : 0,000429 → 0,033 |
| _heal | option `_polish_after_5nm_rule` (093a758f) | — | 0,0049 | 30 | le champion Pareto (avec couches fines) est restauré après la guérison ; fin désaccordée 30 lignes / 32 épaisseurs |
| — | export : ne remet pas un meilleur résultat d'une autre structure (76349415) | | | | cause des fins désaccordées (aussi le run de référence n° 3) |
| _abs5 | couche < 5 nm évaluée et rendue absente (9c1e8d2d) | 0,0034 | **0,000951** (fenêtre 0,000995) | 32 · 24,1 · 5,2 nm | **DESIGN sous 1e-3**, 82 s, conforme à la règle des 5 nm ; le saut à 5 nm raccourcit les polissages |
| _floor5 | borne basse de 5 nm sur chaque couche, `memetic_floor_nm` (45406cde, défaut 5 dans le chemin mémétique) | **0,000303** | **0,000332** (oracle idem, écart max 0,135 %) | 34 · 25,7 · 5,0 nm | coût lisse, polissages complets ; 21 min, 814 k appels |
| m1000_floor5 | 1000 enfants au lieu de 300 | 0,000097 | 0,000155 | 34 · **31,9** · 5,0 nm | hors plafond de 👤 (30 QWOT) ; la grille de la fenêtre (140 pts) sous-estime le RMSE (9,7e-5 contre 1,55e-4) |
| m1000_q30 | plafond `memetic_qwot_max=30` (7a51fdb0) | 0,000165 | 0,0239 | 30 · 26,7 | la décimation Pareto restaure un champion à couche de 4,2 nm, la règle des 5 nm le ruine |
| m1000_q30_champ5 | option `_pareto_champion_respects_5nm` (81353857) | 0,000133 | **0,000147** (écart max 0,072 %) | 34 · **26,8** · 5,0 nm | **record DESIGN conforme à toutes les contraintes**, 7,3 min |
| rec_r2, rec_r3 | répétitions du record (graine libre) | — | 0,000215 ; 0,000172 | 34 · 25,8 | **médiane du record sur 3 runs : 0,000172**, dispersion ±20 % |
| margin30 | marge de Tikhonravov 30 au lieu de 10 (420 points) | 0,000137 | 0,000203 | 34 · 25,8 | pas de gain ; retiré du code ; l'écart fenêtre/grille fixe demeure (question ouverte) |
| pair03 ×3 | mouvement de paires (retirer la paire la plus fine, réinsérer une paire dans une couche), taux 0,3 | — | 0,000140 ; 0,000176 ; 0,000207 | 34 | médiane 0,000176 : pas de gain ; retiré du code |
| m3000 | 3000 enfants | 0,00030 | 0,000399 | 34 · 29,6 | pire : l'étape elle-même finit plus haut (9,0e-8) ; le sort de la population compte plus que sa durée (coût de l'étape de 0,94e-8 à 9e-8 selon la graine) |
| crowd2 ×3 | remplacement par encombrement : un enfant à moins de 2 nm d'écart moyen d'un membre ne peut remplacer que ce membre | 2,5–2,8e-8 (coût) | 0,000237 ; 0,000189 ; 0,000204 | 34 | médiane 0,000204 : pas de gain (étape moins dispersée, pas plus basse) ; retiré du code |
| restart1–3 | redémarrage du workflow depuis son meilleur design (fichier `--save-design`, il entre dans la population comme x0) | — | 0,000189 → 0,000149 → 0,0001479 → 0,0001479 | 34 · 26,6 · 5,0 nm | un seul gain puis plancher : le 3ᵉ tour rend le même design ; tout ce qui a été essayé finit vers 1,5e-4 avec ces contraintes |

Réglage du record (DESIGN, fenêtre) : `run_optim("global", memetic_children=1000, memetic_population=30,
memetic_qwot_max=30)`, fenêtre `_pareto_champion_respects_5nm = True`, départ 34 lignes QWOT (croissance active, voir plus haut).

Balayage du nombre de couches dans la fenêtre (réglage du record, un run par N de départ, 10 à 35) :
`window_sweep/run_window_sweep.sh`, résultats `window_sweep/window_sweep.jsonl`, designs `window_sweep/best_N.json`,
esquisse `sweep/best_by_layers.png` (`sweep/plot_sweep.py`). Sous 1e-3 dès 22 couches réelles (0,00064) ; 26 c. 0,00029 ;
le run N = 34 de ce balayage fait 0,000414 (le record 0,000147 vient d'une autre graine).

Options de la sonde : docstring de `scripts/design_probe.py`. Défauts trouvés : tableau de [`bilan.md`](bilan.md) ; la grille
de Tikhonravov est uniforme en λ (≈ 3 points par frange à 400 nm), sans effet mesuré à 420 points.

## Constats

- Avant `max_layers`, avec `allow_growth`, la cible devenait `MAX_LAYERS` = 100 et rien n'était élagué ; la croissance
  s'arrêtait sur stagnation des aiguilles.
- Les fins désaccordées (tableau et épaisseurs de longueurs différentes) venaient de l'export (`76349415`).
- Paysage très accidenté : à 32 couches, 1 départ sur 200 atteint 6e-4 ; 10ᵉ centile 1,7e-3, médiane 5,5e-3.
- Épaisseur optique totale (QWOT à 500 nm, convention n4) et RMSE : workflow r2 18,7 → 0,0021 ; seed-A 19,3 → 0,0014 ;
  sonde 26 c. 22,5 → 0,0012 ; 32 c. 24,6 → 0,00061 ; 34 c. 24,7 → 0,00048. Plafond de 👤 pour ce cas : 30 QWOT.
- Les fichiers « optimized », « ultra-optimized », « target-achieved » contiennent l'empilement QWOT de départ.

## 2026-10-23, matin : défauts, convergence seule, plancher en fin

| levier / défaut | implantation (commit) | mesure | statut |
|---|---|---|---|
| bloc `optim` des fichiers d'exemple ignoré (la fenêtre lisait `optimization`) | repli sur `optim` (a813fa64) | l'exemple demandait n100 15000 et 100 grappes, la fenêtre tournait à 6000 et 40 | corrigé |
| limites du fichier `max_layers`, `max_total_qwot` | lecture et plafonds (a5844c4d) | seules, l'exemple reste à 26 couches : 0,000951 | — |
| remplissage jusqu'à `max_layers` avant le global | `WorkerManager._fill_to_max_layers` (2e1a5975) | exemple tel quel : **0,000135** (relances 0,000177 → 0,000159 → 0,000135) ; après le correctif de décimation : 0,000165 | **convergence seule** |
| relance automatique | `_restart_from_best`, 5 tours au plus, arrêt si gain < 1 % (867bd7e7) | voir ci-dessus | actif |
| état de la décimation Pareto jamais effacé (effacé sur le gestionnaire, lu sur la fenêtre) | correctif 08f7e7e6 | une guérison lancée après la décimation restaurait le champion par-dessus : 0,000256 → 0,0166 | corrigé |
| plancher en fin (`floor_at_end`, pratique de 👤) | 6f0f51bb, planchers suivant l'empilement 2028fea7 | dans le workflow : 0,0151, 0,035, 0,051 (des couches fines restent après les aiguilles et la règle les retire) | **non fonctionnel dans le workflow** |
| plancher en fin, mesure directe (sonde) | design libre 0,000168 → couches < 5 nm portées à 5 nm → polissage borné à 5 nm | 0,000192, contre 0,000135–0,000165 avec le plancher tout du long | un seul design ; polissage local seulement |
| plancher OT 5 nm (`min_layer_ot_nm`) | f10318b2 | exemple : 0,000166 (30 couches) ; barres ±2σ identiques au plancher physique | sans gain mesurable |
