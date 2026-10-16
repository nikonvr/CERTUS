# Préparation de l’intégration, lecture seule — 13 octobre 2026, 22 h

L’ablation est encore active : aucune modification de production ni test à cette étape.
Avant d’intégrer le générateur, comparer l’artefact sans voisins conjoints ; le gain combiné ne suffit pas à attribuer un effet au code.

`_generate_elite_candidate_strategies` possède déjà `_push_candidate` : déduplication, contrat de blocs,
identifiants contigus, héritage Rate/fente/témoins. Une intégration doit réutiliser ce constructeur après les deux boucles historiques,
avec budget conjoint séparé nul par défaut. Le chemin inactif conserve sorties, ordre et curseur ; pas de patch dynamique en production.
Le générateur pur mesuré peut rejoindre le module Rate existant ; ni noyau TMM, ni tirage, ni bruit Rate supplémentaire.
Le paramètre doit arriver via `_apply_elite_refinement_if_enabled` et garder les profondeurs et plafonds du pipeline.

Contraintes avant livraison : consensus est déjà à 1 500 lignes et sa fonction ELITE à 300 ; respecter les plafonds sans nouvelle dette.
Tests ciblés d’inactivité exacte, héritage, doublons, ordre, routage et régression de mutation tardive hors mesure ; puis oracle et suites complètes.
Comparer le chemin intégré activé au candidat expérimental mesuré avant toute conclusion. Aucun commit avant validation complète.
Le gain sur ce composant, même sur huit groupes de graines, ne suffit pas à activer un nouveau défaut scientifique.
