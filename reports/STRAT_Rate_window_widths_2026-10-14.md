# Rate : fenêtres internes, bilan du 14 octobre 2026 à 5 h 04

Recherche terminée : 3 133 propositions, 315 étapes, 1 194 consensus complets admissibles ; 1 939 exclus conservés.
Meilleur 9932265, repris sous 9900006 : fenêtre L35–L37 à 688 nm ; préfixe L1–L5 à 600 nm, fenêtre L11–L12 à 451 nm, partition/fente/témoins conservés.
SEEL 0,3409240518 nm ; gain 14,0632 % contre la référence et 3,6827 % contre le préfixe 600 sur la recherche.

| Groupe | Référence nm | Préfixe 600 nm | Nouvelle fenêtre nm | Gain/réf. | Gain/600 |
|---|---:|---:|---:|---:|---:|
| control | 0.3967147882 | 0.3539592452 | 0.3409240518 | 14.0632 % | 3.6827 % |
| holdout_2121 | 0.4003395972 | 0.3596078309 | 0.3454201653 | 13.7182 % | 3.9453 % |
| holdout_2222 | 0.3985506544 | 0.3573283194 | 0.3418797927 | 14.2192 % | 4.3233 % |
| holdout_2323 | 0.3928929363 | 0.3533635977 | 0.3349944905 | 14.7364 % | 5.1984 % |

Les sept points fixes passent strictement ; chaque plan reçoit trois consensus à 300 tirages, mondes aléatoires partagés. Aucun plantage observé dans les appels physiques enregistrés.
Le gain contre 600 se confirme sur les trois groupes frais prédeclared, de 3,9453 à 5,1984 %. La référence est améliorée de 13,7182 à 14,7364 %.
Mouvements isolés sur 101 : fenêtre L35–L37 à 691 nm → 0,3459403805 nm ; λ688 seule sur L36–L39 → 0,3624981294 nm ; combinaison → 0,3409240518 nm.

Limites : un composant, plans fixes, pas de validation machine ni d’intervalle de confiance formel. Cette mesure établit un gain de plan ; elle ne prouve pas qu’un ajout natif dans ELITE retrouve automatiquement ce plan. Aucun défaut scientifique activé, aucune source physique modifiée, aucun commit/push.
Artefact SHA256 : 3d8fb6f61a2f2f76be24f139cf5c0f66c51f4e65c8230b946186c8a1809d3261. Protocole v8 et sources conservés dans le dossier.
