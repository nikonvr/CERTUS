# Rate : comparaison homogène avec l’ablation (2026-10-14)

Validation terminée : **11/11 OK**, points fixes puis dix groupes indépendants. Profondeurs 300/50/100/300 conservées.
Le pool sans voisins conjoints est entièrement renoté : 5 240 propositions, 5 238 consensus complets, deux incomplets exclus.
Meilleur ablation 900752354, SEEL 0,3619390295 nm ; natif conjoint 0,3600608863 nm sur la recherche (avantage 0,519 %).

| Groupe | Référence (nm) | Natif conjoint (nm) | Ablation (nm) | Gain natif / ablation |
|---|---:|---:|---:|---:|
| control | 0.3967147882 | 0.3600608863 | 0.3619390295 | +0.519 % |
| holdout_202 | 0.3968275691 | 0.3608717921 | 0.3714812359 | +2.856 % |
| holdout_303 | 0.3995131221 | 0.3653610083 | 0.3677244884 | +0.643 % |
| holdout_404 | 0.3997442250 | 0.3663274424 | 0.3607791370 | -1.538 % |
| holdout_505 | 0.3993888246 | 0.3687252866 | 0.3639636050 | -1.308 % |
| holdout_606 | 0.3928222059 | 0.3626817120 | 0.3634107810 | +0.201 % |
| holdout_707 | 0.3972990867 | 0.3721442669 | 0.3579251957 | -3.973 % |
| holdout_808 | 0.3961320607 | 0.3632205049 | 0.3614252540 | -0.497 % |
| holdout_909 | 0.4045376306 | 0.3620838320 | 0.3581325750 | -1.103 % |
| holdout_1010 | 0.3967968906 | 0.3597591248 | 0.3603426568 | +0.162 % |
| holdout_1111 | 0.4004429678 | 0.3664183697 | 0.3587119142 | -2.148 % |

Le natif conjoint ne gagne que sur 4/10 groupes : médiane du gain −0,800 %, moyenne −0,671 %, plage −3,973 à +2,856 %.
L’avantage propre du nouveau voisinage n’est pas confirmé. Les groupes frais pré-déclarés donnent +0,162 % (1010) et −2,148 % (1111).
Le gain contre la référence reste positif pour les deux plans ; ablation 6,39 à 11,47 %, natif 6,33 à 10,49 %.
Aucun plantage observé dans les appels physiques enregistrés. Les anciens groupes ont été réutilisés pour orienter l’exploration ;
les deux nouveaux groupes ont été fixés avant sélection finale et ne servent pas à classer les candidats de la recherche.

Limites : un composant, plans fixes sélectionnés, aucun intervalle de confiance formel, aucune recherche complète sur les graines indépendantes.
Le classement de scores de base et de consensus mélangés est un point à traiter ; les scores et échecs originaux restent conservés.
Aucun défaut activé, aucune intégration de production sur cet avantage marginal, aucun commit ni publication.
