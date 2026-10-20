# Les leviers de Bonne Mère sur r75, r75x0.5 et r75x2 : lesquels généraliser dans STRAT (2026-10-20)

But : coder dans STRAT les leviers qui gagnent sur plusieurs designs, et pas ceux propres à Bonne Mère. Chaque levier
part du gagnant STRAT de la graine de banc 77 (tête `1384f65f`) et se juge sur l'évaluateur natif de STRAT, comme dans
`reports/STRAT_r75_budget_et_affinage_2026-10-20/` : RMSE² apparié au bruit nominal, graines réservées par usage
(recherche, sélection, confirmation, holdout ouvert une fois, 3 × 1 000 tirages), aucun arrêt ajouté, SEEL STRAT =
2·√P95. Outils : `outils/` ; journaux : `journaux/`. Les SEEL d'une ligne se comparent entre eux : la référence change
avec les graines de holdout.

## 1. Holdout de chaque levier, seul, contre le gagnant STRAT

ΔRMSE² apparié (erreur type 0,4 à 1,4 %), SEEL de départ → d'arrivée (nm), arrêts sur 9 000 tirages.

| levier | 75c | r75x0.5 | r75x2 |
|---|---|---|---|
| λ, balayage et combinaison gloutonne (rapports précédents, 3 graines) | −36 à −49 % ; 0,2453 → 0,2189 | −15,5 à −17,5 % ; 0,4363 → 0,4198 | −11,5 à −18,4 % ; 0,5447 → 0,5212 |
| λ, fenêtres de 8 couches optiques, descente | −43,4 % ; 0,2460 → 0,2200 ; 13 → 0 | −5,1 % ; 0,4400 → 0,4292 | −23,0 % ; 0,5418 → 0,5149 ; 1 → 0 |
| Rate → optique, bascules sélectionnées | aucun candidat | **−49,0 %** ; 0,4370 → **0,3628** (7 couches) | −29,7 % ; 0,5438 → **0,4981** (9 couches) |
| Rate → optique aux frontières, voisinage réoptimisé | −22,0 % ; 0,2488 → 0,2414 ; 14 → 10 | aucune frontière utile | −29,5 % ; 0,5450 → 0,5246 |
| optique → Rate, bascules sélectionnées | −13,8 % ; 0,2485 → 0,2418 ; **10 → 1** | −3,6 % ; 0,4372 → 0,4344 | −8,3 % ; 0,5416 → 0,5291 ; 2 → 0 |
| plafond d'épaisseur Rate (les N plus épaisses en optique) | rien d'admissible | −9,0 % (N = 4) ; 0,4383 → 0,4054 | −0,5 % (N = 1) |
| seconde passe λ, depuis le plan affiné | −25,2 % ; 0,2166 → 0,2071 ; **10 → 14** | −5,1 % ; 0,4246 → 0,4224 | −4,7 % ; 0,5190 → 0,5150 |
| règle Bonne Mère « Rate pour les K couches les plus fines » | perd pour tout K | perd (arrêts) | perd (arrêts) |
| λ commun aux couches 1 à 3 (tête de Bonne Mère) | rien d'admissible | rien | rien (arrêts) |
| fenêtres à cible projetée (tampon 4 couches) | +132,9 % ; 0,2469 → 0,3294 ; 10 → 49 | +608,8 % ; 0,4383 → 0,7098 | +17,0 % ; 0,5450 → 0,5922 |
| STRAT sans Rate (banc deep) | 368 plans sur 658 sans arrêt, meilleur 0,2517 | 0 sur 341 | 0 sur 444 |

Le plancher d'hystérésis et la fente sur r75x2 : `reports/STRAT_r75x2_bascules_fente_sansrate_2026-10-20/`. Précouches
témoin : hors classement, réservées par 👤 aux designs dont la première couche fait moins de 25 nm (aucun des trois :
59, 29,3 et 117 nm) ; évaluateur porté et éprouvé (`outils/precoat.py.txt`, identique au bit sans précouche), non lancé.

## 2. Ce qui se généralise

- **Les leviers qui gagnent sont tous locaux et appariés** : changer le λ d'une couche, ou son mode (Rate ↔ optique),
  garder le changement s'il baisse le RMSE² apparié sans ajouter d'arrêt. Ils gagnent sur les trois designs, dans les
  deux sens de bascule.
- **Le levier dominant dépend du design** : sur 75c (9 couches Rate), le λ ; sur r75x0.5 et r75x2 (55 à 56 couches
  Rate), la bascule Rate → optique. STRAT met trop de couches en Rate sur les designs épais ou fins.
- **Basculer seul ne suffit pas toujours** : sur 75c, aucune bascule Rate → optique ne gagne seule, cinq gagnent
  avec le voisinage réoptimisé.
- **Les règles globales perdent** : seuil d'épaisseur appliqué en bloc, tout-optique, λ commun, cible projetée. Le
  partage « Rate pour les couches fines » de Bonne Mère y est accompagné d'une réoptimisation des λ ; appliqué seul, il
  multiplie les arrêts.
- **La cible projetée trompe l'optimiseur** : en supposant l'aval parfait, elle retient des λ que les erreurs réelles
  de l'aval rendent mauvais. Les mêmes fenêtres jugées sur la cible complète gagnent.

## 3. Le candidat pour STRAT : une recherche locale conjointe (mode, λ)

Deux passes du substrat vers l'air ; pour chaque couche, candidats λ ± 60 nm (pas 10) ou passage en Rate si elle est
optique, passage en optique à 450–750 nm si elle est en Rate ; changement gardé s'il baisse le RMSE² apparié sans
ajouter d'arrêt (`outils/modelam.py.txt`). Graines : recherche 20261022001 (300 tirages), confirmation 20261022101,
holdout 20261022201 (+ 0, 1 000, 2 000 selon le design).

## 4. Recherche conjointe, holdout contre le gagnant STRAT

| design | ΔRMSE² (ET) | SEEL STRAT (nm) | arrêts | changements | couches Rate |
|---|---|---|---|---|---|
| 75c | **−51,6 %** (0,8) | 0,2455 → **0,2132** | 13 → 1 | 48 : λ, 3 → optique, plusieurs → Rate | 9 → 12 |
| r75x0.5 | **−64,8 %** (1,5) | 0,4376 → **0,3467** | 0 → 0 | 26 : 10 λ, 14 → optique, 2 → Rate | 56 → 44 |
| r75x2 | **−48,9 %** (0,9) | 0,5411 → **0,4729** | 0 → 2 | 55 : 18 λ, 30 → optique, 7 → Rate | 55 → 32 |

La confirmation donne les mêmes chiffres à 0,4 point près. Sur les trois designs, la recherche conjointe fait mieux
que le meilleur levier seul (75c −49 %, r75x0.5 −49 %, r75x2 −30 %) : les leviers se cumulent quand on les cherche
ensemble. Coût : 2 345 à 3 830 évaluations de 300 tirages, 18 à 19 min par design sur 16 cœurs. Sur r75x2, 2 arrêts
sur 9 000 tirages au holdout pour 0 à la recherche : le critère « aucun arrêt ajouté » sur 300 tirages laisse passer
des arrêts rares.

Proposition pour STRAT : un étage final optionnel, inactif par défaut (C1), qui applique cette recherche au gagnant ;
graines de recherche distinctes de celles du classement ; critère d'arrêt durci (plus de tirages ou marge sur les
arrêts) avant d'en faire un défaut.

Plans gelés : `plan_recherche_conjointe_<design>.json`. Non mesuré : graines de banc 101 et 202 pour les bascules et la recherche conjointe, dérive de la source (A6), rejeu
des plans gelés dans le banc `scripts/probe_blocs_vs_plantage.py` (l'évaluateur en reste à 2e-5 relatif, mesuré le
2026-10-20 sur les gagnants).
