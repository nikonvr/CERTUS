# CERTUS — bilan du 14 octobre 2026 à 8 h 46 (Paris)

Le meilleur plan fixe mesuré atteint **0,3345159946 nm**, contre **0,3967147882 nm** pour la référence : **15,6785 % de gain** sur `r75x0.5 deep`, graine 101.

Le gain contre la référence se confirme sur **neuf groupes indépendants frais**, de **13,2343 à 15,8693 %**. Aucun plantage observé dans les appels physiques de confirmation enregistrés. Le choix conjoint des fenêtres optiques et de leur longueur d’onde apporte le progrès utile. L’obtention automatique de ce plan par STRAT reste à valider.

| Essai | SEEL nm sur recherche 101 | Lecture |
|---|---:|---|
| Référence | 0,396715 | Point fixe reproduit |
| Équilibrage des familles, plafond 120 | 0,479488 | Régression de 20,86 % ; inactive |
| Budget Rate 240 | 0,382810 | Gain de 3,50 %, confirmé sur deux groupes |
| Budget Rate 360 | 0,382810 | Aucun gain supplémentaire |
| Conjoint natif, Rate 240, six raffinements | 0,360061 | Gain contre référence ; supériorité sur ablation non établie |
| Préfixe L1–L5 à 600 nm | 0,353959 | Gain confirmé |
| Raffinement à 598 nm | 0,351828 | Petit gain incrémental non confirmé |
| Ajout natif de voisins du préfixe, pool renoté | 0,363083 | Moins bon que le préfixe 600 sur trois groupes frais |
| Fenêtre L35–L37 à 688 nm | 0,340924 | Gain confirmé |
| Couplage des deux fenêtres | 0,336008 | Gain incrémental non confirmé, non retenu |
| Préfixe 613 avec fenêtre 688 | **0,334516** | **9/9 gains contre référence** |

Ces nombres sont les minima observés des recherches ; les contrôles indiqués qualifient les gains. Les détails, rejets et essais intermédiaires sont dans [l’expertise](STRAT_Rate_expertise_2026-10-13.md).

Le plan retenu alterne : **L1–L5 optiques à 613 nm**, L6–L10 au Rate, **L11–L12 optiques à 451 nm**, L13–L34 au Rate, **L35–L37 optiques à 688 nm**, puis L38–L75 au Rate. Partition de dix blocs, fente 2 nm et témoins conservés. Original 9910275, identité de rejeu 9900008.

Le dernier passage de 600 à 613 nm est plus modeste : huit gains sur neuf groupes, moyenne **0,3074 %**, médiane **0,4792 %**, une perte de **2,3282 %** sur 3434. Le plan précédent reste conservé comme comparateur ; la supériorité du 613 n’est pas uniforme.

[Plans complets](STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/selected_fixed_plans.json) · [Neuf comparaisons](STRAT_Rate_validation_prefix_after_window_extended_2026-10-14/comparison_table.md).

L’équilibrage initial évince une fenêtre utile sous le plafond. Augmenter seulement le budget aide, puis plafonne. La géométrie et la λ doivent être choisies ensemble : fenêtre L35–L37 à 691 nm → 0,3459403805 nm ; λ 688 seule sur L36–L39 → 0,3624981294 nm ; combinaison → 0,3409240518 nm. Les fenêtres de longueur impaire ont été utiles.

Les ajouts de candidats dans ELITE ne garantissent ni leur sélection ni leur notation complète. Un mélange de scores de base et de consensus a été identifié dans les exports : les pools d’ablation (5 240 plans) et de préfixe natif (5 119) ont été renotés intégralement. Les points fixes échoués et toutes les reprises sont conservés.

Contrats réels, masques Rate, fente/témoins, signatures/identifiants et sources figées vérifiés. Rejeux stricts ; 300 tirages complets et 300 par graine de consensus, trois graines par groupe, mêmes mondes aléatoires C2 et même transport d’indices float32 que le Worker. Les copies du moteur ne changent que leurs choix CLI.

Limites : un composant et des plans fixes, pas de validation machine ou générale, pas d’intervalle de confiance formel. Les variations réelles de vitesse entre dépôts n’ont pas été ajoutées au modèle. Aucun gain de temps attribué au code à partir du cache chaud. Aucun nouveau défaut activé, aucun commit ou push ; validation générale du code encore à terminer.

A2 a repris : **7/24 exécutions sauvegardées**, huitième `r75x1.75_deep_s101_sans` en cours depuis **8 h 38 min 20 s**. Septième avec : 47 min 46 s, SEEL 0,4717267402 nm, 3 800 déposables, verdict/provenance/option effective vérifiés. Paire 101 encore incomplète.

Trois paires exportées complètes : r75x1.5/42, gain 3,2514 % ; r75x1.5/101, 0,1176 % ; r75x1.75/42, 3,6154 %. Écarts inférieurs au repère de dispersion, sans renotation homogène des gagnants fixes A2 ; aucune conclusion globale avant fin de campagne.

16 processeurs logiques, affinité 0xffff, priorité Normal, plafond 15 threads. **Aucun nouveau départ après 9 h Paris**, calcul déjà engagé laissé finir. [État A2](STRAT_ELITE_couches_Rate_autres_composants_2026-10-13/etat.json).

La prochaine étape est une intégration de la recherche locale avec sélection à profondeur homogène, chemin inactif identique, puis vérification du gain natif sur plusieurs graines et composants.

## Suite décidée après ce bilan

Le bilan ci-dessus décrit les résultats et l’état relevés à8 h46. 👤 a ensuite demandé de terminer
les batchs restants, puis de poursuivre en totale autonomie **avec cette IA**. A2 continue donc au-delà
de l’ancienne limite de9 h, depuis son checkpoint, une seule mesure à la fois. La continuation51884
a attendu le contrôleur nocturne sans interrompre sa mesure, puis lancé le contrôleur original24128
à9 h25. À9 h32 : **9/24 sauvegardées**, dixième `35c_deep_s042_sans` active. Son état reste dans
[`STRAT_A2_continuation_2026-10-14/etat.json`](STRAT_A2_continuation_2026-10-14/etat.json).

Le [guide complet de reprise et plan de chantier](../docs/STRAT_Rate_suite_chantier.md) consigne les
améliorations mesurées, les pistes non confirmées, les comparateurs et leurs identités, les artefacts,
les profondeurs/graines/provenances, les pièges de rejeu et un programme borné R0–R7. A2 est prioritaire
jusqu’à24/24 ; préparations statiques pendant son calcul, vérifications runtime et nouvelles mesures
Rate après libération de la machine. R7 attend les données quantitatives de vitesse machine.

La correction d’export R1 est préparée : score de base, score de consensus, métadonnées exactes et resets
des témoins conservés, valeurs manquantes laissées inconnues. Ruff et parsing statique passent ; tests
d’exécution encore différés. Cette préparation documentaire et de traçabilité ne constitue pas un
nouveau gain scientifique. Les sources de mesure A2 et les anciens artefacts restent figés.

Dernière autorisation explicite : poursuite avec cette IA jusqu'au **15 octobre2026 à8 h Paris**
(06:00 UTC). Terminer A2 puis progresser dans R0–R6 avant cette limite ; aucun nouveau test/calcul
après, laisser finir le calcul engagé, sauvegarder le bilan et mettre le suivi en pause.
[Autorisation, protocole borné et commandes courantes](STRAT_Rate_suite_2026-10-14/autonomie_jusqu_20261015_0800/commands.md)
conservés, même automation actualisée et vérifiée. Le guide/ETAT portent l'état actuel ; ce bilan
initial ne déclare pas les phases futures accomplies ni les dernières préparations validées runtime.
