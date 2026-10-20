# STRAT sur r75 : l'affinage apparié sur trois graines de banc (2026-10-20)

Suite de `reports/STRAT_r75_budget_et_affinage_2026-10-20/` (graine 77, même méthode). Pour les graines de banc 101 et 202 :
STRAT complet (`scripts/probe_blocs_vs_plantage.py <comp> deep 0 0 2 0 <graine>`, tête `1384f65f`), gagnant extrait
(`prep.py.txt`), balayage des λ de chaque couche optique, sélection, combinaison gloutonne, gel, confirmation et holdout
(`refine.py.txt`, graines réservées propres à chaque plan, décalage de 1 000 par plan). Journal : `pipeline_journal.txt`.

## Holdout final, bruit nominal (SEEL STRAT = 2·√P95)

| design | graine | gagnant STRAT → affiné | RMSE² | arrêts | changements |
|---|---|---|---|---|---|
| r75 | 77 | 0,2453 → 0,2189 nm (−10,8 %) | −40,7 % | 6 → 5 | 8 |
| r75 | 101 | 0,2444 → 0,2163 nm (−11,5 %) | −36,1 % | 13 → 12 | 7 |
| r75 | 202 | 0,2441 → **0,2141 nm** (−12,3 %) | −49,0 % | 0 → 0 | 8 |
| r75x0.5 | 77 | 0,4363 → 0,4198 nm (−3,8 %) | −15,5 % | 0 → 0 | 1 |
| r75x0.5 | 101 | 0,3966 → 0,3741 nm (−5,7 %) | −17,5 % | 0 → 0 | 1 (couche 35 → 700 nm) |
| r75x0.5 | 202 | 0,3958 → **0,3685 nm** (−6,9 %) | −17,5 % | 0 → 0 | 1 (couche 35 → 695 nm) |
| r75x2 | 77 | 0,5447 → 0,5212 nm (−4,3 %) | −18,4 % | 0 → 0 | 2 |
| r75x2 | 101 | 0,5305 → **0,5091 nm** (−4,0 %) | −13,1 % | 0 → 0 | 2 |
| r75x2 | 202 | 0,5414 → 0,5311 nm (−1,9 %) | −11,5 % | 10 → 0 | 1 |

Les lignes de la graine 77 viennent du rapport précédent. Erreur type du RMSE² : 0,5 à 1,3 %.

## Ce que cela établit

- **9 cas sur 9** : l'affinage apparié gagne au holdout, sans jamais ajouter d'arrêt. C'est un ingrédient général, pas
  un accident de graine : il mérite un étage optionnel dans STRAT (inactif par défaut, C1).
- Le gain décroît avec l'épaisseur du design (≈ −11 % de SEEL sur r75, −4 à −7 % sur r75x0.5, −2 à −4 % sur r75x2), où
  l'erreur d'indice domine et où STRAT met 55 à 65 couches en Rate.
- Sur r75x0.5, deux gagnants STRAT différents (graines 101 et 202) sont corrigés par le même changement, la couche 35
  vers 695–700 nm : un défaut systématique du choix de λ de STRAT pour cette couche.
- Non mesuré : dérive de la source (A6), autres composants (48c, 35c, 99c).
