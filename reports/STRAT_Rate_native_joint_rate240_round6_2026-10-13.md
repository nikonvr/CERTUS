# Rate : essai natif rate240_round6 (2026-10-13)

Lancé à 20 h 31 min 41 s (Paris), contrôleur 19656, calcul 37604. Budget conjoint 480, budget Rate 240, raffinements 6.
Terminé et sauvegardé à 21 h 23 : environ 52 min, **SEEL 0,3600608863 nm**, **gain 9,239 %** contre la référence,
5 412 déposables, meilleur identifiant 901054165, score 0,032410960467156955, dix blocs.
Optique L1–L6 à 632 nm, L11–L12 à 451 nm, L36–L39 à 691 nm ; les autres couches Rate, fente 2 nm.
Une seule modification par rapport à la comparaison consignée dans `prepared.json`. Ordre historique, profondeurs et plafonds conservés.
Sources figées dans `sources/`, SHA256, paramètres et limite de ressources dans `prepared.json`.
`NATIVE_ADAPTER_VERIFY=GO` avant la mesure ; surcharges effectives constatées dans `measurement.log`.
État dans `controller.json`, point de reprise scientifique dans `joint_480_rate240_rounds6_s101/etat.json`.
124 appels au générateur, 38 410 voisins conjoints ; trace sauvegardée.
Artefact SHA256 `944774e4d9ce471d2b2b561f1c6143f5c7be40207187d8ec280c338448cca6d9` ;
trace `78eacaa6451b5d7fac7a78070e82acf10dd02622339e312b8af0140a798227ec`.
Synthèse complète `summary.json`, observations de parents `lineage_observations.json`.

Le quatrième tour retrouve le meilleur local à huit blocs. Le vainqueur global est différent et issu d’un voisinage à dix blocs :
un candidat conjoint 901053250 (préfixe 630) devient parent au tour suivant ; le final emploie 632 sur le préfixe.
Le final n’est pas lui-même un candidat supplémentaire de la trace. Cette observation ne remplace pas l’ablation causale.

Confirmation achevée, 9/9 OK : point fixe puis huit groupes indépendants, profondeurs conservées, aucun plantage observé.
Gain natif contre référence de 6,33 à 10,49 % ; meilleur que le plan local sur sept groupes, moins bon de 0,68 % sur 707.
Les deux nouveaux groupes 808 et 909, fixés avant inspection finale, donnent respectivement 8,31 et 10,49 % de gain.
Rapport associé : `STRAT_Rate_confirmation_native_round6_2026-10-13.md`.
Ablation suivante : mêmes paramètres avec budget conjoint nul, pour distinguer l’effet du générateur de celui des budgets/tours existants.

Une seule mesure à la fois ; arrêt des nouveaux lancements à 9 h Paris, calcul engagé conservé. A2 reste sauvegardée à 3/24.
Aucun défaut scientifique activé, aucun noyau modifié, aucun commit ni publication.
