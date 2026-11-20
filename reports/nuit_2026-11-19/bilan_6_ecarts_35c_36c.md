# Chantier 6 — d'où viennent les écarts 35c (−29 %) et 36c (+12 %) ? (2026-11-20)

Ordre de 👤 (2026-11-20, 05 h 45) : instruire avant d'adopter les repères. Sources : les journaux bruts des deux runs,
celui du 21/10 (`85a9e82f`, archive `STRAT_A3_reperes_reprise_2026-10-21/preuves_A3_completes_20261021T042912Z.zip`) et
celui du 20/11 (`7a6fca38`, `lot3/*.raw.log`, hors dépôt), lignes `[LOCAL-SEARCH]` et `Best Strategy ID`. Aucun
nouveau calcul.

| banc | meilleur ELITE 21/10 → 20/11 | recherche locale le 21/10 | recherche locale le 20/11 | RESULT 21/10 → 20/11 |
|---|---|---|---|---|
| vrai 35c deep | 0,0602 → 0,0546 | P95 0,1047 → 0,0598, arrêts 0 → 2 : **refusée**, vainqueur inchangé | P95 0,1630 → 0,0402, arrêts 338 → 10 : **gardée** | 0,0602 → 0,0300 |
| 36c deep livré | 0,0358 → 0,0354 | P95 0,0609 → 0,0318, arrêts 10 → 0 : **gardée** | P95 0,0650 → 0,0239, arrêts 1 → 6 : **refusée** ; repli « 14 changements sur 29 » gardé | 0,0262 → 0,0329 |

« arrêts » : dépôts non terminés comptés sur les deux graines fraîches du contrôle (`check on 2 fresh seeds`).

## Lecture

- **L'étage ELITE n'explique pas les écarts** : son meilleur plan bouge de −9 % (35c) et de −1 % (36c).
- **Les deux écarts viennent du contrôle d'acceptation de la recherche locale**, binaire et décidé sur deux graines :
  le 35c d'octobre avait vu son plan refusé (0 → 2 arrêts), celui de cette nuit est gardé (338 → 10) ; le 36c d'octobre
  était gardé (10 → 0), celui de cette nuit est refusé (1 → 6) et remplacé par le repli partiel, apparu depuis.
- Le `RESULT` d'un repère porte donc une composante « recherche locale acceptée ou non » qui bascule d'une version du
  code à l'autre : un écart de 10 à 30 % peut en venir seul, sans que le calcul ait changé de qualité.

## Ce qui reste ouvert

- Le contrôle sur deux graines est-il assez sûr ? Un plan meilleur de 63 % en P95 (36c, 0,0650 → 0,0239) est refusé
  pour 1 → 6 arrêts sur deux graines. Piste : plus de graines au contrôle, ou publier à côté du `RESULT` le meilleur
  ELITE, qui ne dépend pas de ce basculement. Décision de 👤.
