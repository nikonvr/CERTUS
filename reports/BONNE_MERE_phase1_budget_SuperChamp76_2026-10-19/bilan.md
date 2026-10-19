# Bonne Mère — phase 1 : budget d'erreur de SuperChamp76 (2026-10-19)

Demande de 👤 : ablation appariée des sources d'erreur, attribution par couche et queue de distribution du plan
`SuperChamp76_StrictOT50_HybridMicroWin` (76 optiques / 20 Rate), sur des graines de diagnostic neuves. Banc :
`rejeu_ablation.py.txt`, le banc validé de `reports/BONNE_MERE_rejeu_SuperChamp76_2026-10-19/` augmenté de trois options
(paramètres STRAT surchargés, facteur sur les trois bruits optiques, épaisseurs tirées sauvegardées). Tête `3724238f`,
arbre `certus/` propre pendant les 27 exécutions. Graines de diagnostic 20261019501, 502 et 503 (1 000 tirages chacune) :
elles ne servent à aucune sélection.

## 1. Ablation appariée (3 000 tirages par ligne, mêmes tirages d'une ligne à l'autre)

Au bruit 0,05 :

| configuration | arrêts | SEEL rms (nm) | SEEL P95 (nm) | ΔSEEL² apparié (nm²) | excès de MSE sur le plancher (pp²) |
|---|---|---|---|---|---|
| référence | 0 | 0,3358 | 0,4704 | — | 0,2221 |
| corridor d'indice à 0 | 0 | 0,2088 | 0,2710 | −0,0691 ± 0,0010 | 0,0862 |
| biais de fente coupé | 0 | 0,3248 | 0,4598 | −0,0073 ± 0,0002 | 0,2077 |
| bruit d'ancre POEM coupé | 0 | 0,3184 | 0,4543 | −0,0114 ± 0,0003 | 0,1997 |
| bruit optique ÷ 100 | **787** | 0,3160 (aboutis) | 0,4684 | −0,0110 ± 0,0010 | 0,1968 |
| les quatre coupés | 0 | 0,0844 | 0,1392 | −0,1056 ± 0,0010 | 0,0141 |

- **L'erreur d'indice domine** : le corridor (±0,005, affine en λ, tiré par passage) porte 61 % du SEEL² (0,069 sur
  0,113 nm²) ; sans lui, le SEEL P95 passe de 0,470 à 0,271 nm. Sa part est la même aux trois bruits (−0,068 à −0,069 nm²).
- Le bruit d'ancre POEM croît avec le bruit (−0,003, −0,011, −0,049 nm² aux trois niveaux) ; la fente pèse 6 %.
- Tout coupé, il reste un SEEL rms de 0,084 nm et 0,014 pp² d'excès : le biais propre à l'algorithme d'arrêt (6 % du
  SEEL²). Ce contrôle montre aussi que chaque interrupteur atteint le calcul.
- Les deux autres niveaux de bruit et les ΔSEEL² complets sont dans `analyse_budget_attribution_queue.txt`.

## 2. Un bruit optique faible fait échouer le dépôt (défaut du modèle d'arrêt à instruire)

Bruit optique divisé par 100, arrêts sur 3 000 tirages aux trois niveaux :

| configuration | arrêts |
|---|---|
| tout actif | 936 / 787 / 596 |
| corridor à 0 | 76 / 11 / 0 |
| ancre POEM coupée | 935 / 788 / 594 |
| fente coupée | 0 / 0 / 0 |
| les quatre coupés | 0 / 0 / 0 |

2 318 des 2 319 arrêts tombent sur **op 88** (composant 86, contrôle optique à 535 nm), les 87 restants sans corridor
aussi. Dans le modèle, avec la fente de 2 nm et un signal presque sans bruit, le contrôleur ne déclare plus le point
tournant de cette couche : un appareil plus silencieux échouerait plus souvent. Je n'ai pas cherché le mécanisme
(hystérésis, parabole des trois sondes, D98) ; c'est un sujet pour STRAT en général, pas seulement pour ce plan.

## 3. Attribution par couche (bruit 0,05, référence, 3 000 tirages)

Régression du SEEL² sur les erreurs d'épaisseur (e_k, e_k²), R² validé croisé 0,945. Parts additives (covariance de
chaque terme avec la prédiction, somme = R² = 0,953) : op 43 8,9 %, op 58 7,0 %, op 77 6,6 %, op 87 6,6 %, op 36 5,3 %,
op 25 4,5 %, op 19 4,2 %, op 32 4,1 %, op 65 4,1 %, op 23 3,8 %. **Aucune couche ne domine** (sur le plan 452 nm, op 57
pesait 45,7 %). Les 20 couches Rate pèsent environ 1 %. Paires compensées : op 64 et 65 (corrélation des erreurs
−0,78), op 58 et 59 (−0,43).

Écart-type de l'erreur d'épaisseur de quatre couches lourdes selon la source coupée (nm) :

| configuration | op 65 | op 58 | op 64 | op 77 | biais moyen op 58 |
|---|---|---|---|---|---|
| référence | 0,325 | 0,818 | 0,440 | 0,354 | +0,304 |
| corridor à 0 | 0,191 | 0,146 | 0,297 | 0,128 | +0,280 |
| fente coupée | 0,322 | 0,803 | 0,436 | 0,351 | +0,075 |
| les quatre coupés | 0,027 | 0,015 | 0,016 | 0,084 | +0,031 |

Op 58 (SiO₂, contrôlée à 465 nm) est la couche la plus sensible à l'indice (×5,6), et son biais vient de la fente.

## 4. Queue (bruit 0,05)

SEEL P50 0,316, P90 0,432, P95 0,470, P99 0,546, P99,9 0,623, maximum 0,661 nm ; 7 tirages au-dessus de 0,6 nm, aucun
au-dessus de 0,7 nm. Dans les 30 pires tirages, op 58 a une erreur moyenne de 1,55 nm (0,71 sur l'ensemble), op 77,
op 32, op 64 et op 36 le double de leur moyenne.

## Ce que cela dit pour la suite

- La marge de la stratégie est dans la **sensibilité à l'erreur d'indice** : choisir les λ de contrôle qui rendent
  l'arrêt peu sensible à n, en commençant par op 58, 77, 43, 87 et 65. Un levier hors stratégie a la même cible :
  mieux connaître l'indice des H800 (corridor plus étroit).
- Le Rate n'est plus un levier sur ce plan (1 %) ; le bruit optique non plus (bruit ÷ 100 : −10 % du SEEL²).
- Le défaut op 88 à bruit faible est à instruire avant de retenir un plan : un plan robuste doit aboutir aussi quand
  l'appareil est plus silencieux que prévu.
- Non mesuré : la dérive de vitesse de la source (pas dans le modèle, valeur attendue de 👤), une erreur d'indice
  systématique plutôt qu'aléatoire.

## Fichiers

`runs/<config>_s<graine>/summary.json` pour les 27 exécutions ; tirages bruts (épaisseurs comprises) des trois
exécutions de référence seulement (`runs/ref_*/component_scores.npz`, 1,8 Mo chacune) ; les autres se régénèrent en
10 s chacune avec `rejeu_ablation.py.txt`. Analyses : `analyse_phase1.py.txt`, `analyse_phase1b.py.txt` et leurs
sorties `.txt`.
