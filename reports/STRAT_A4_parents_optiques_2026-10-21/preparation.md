# A4 — Préparation statique, 21 octobre 2026

Aucun code scientifique modifié, aucun test ni mesure A4 lancé. A3 puis A5 restent prioritaires.
Source lue : `85a9e82f`. Les nombres historiques de la feuille de route décrivent l'ancien modèle d'arrêt.

Le chemin courant borne les parents par `min(elite_parent_top_k, len(strategies_results))`, puis transmet
le début du classement à la génération et au journal des parents. Une option inactive doit conserver
exactement ces objets, leur ordre et les candidats produits ; aucune permutation ou copie profonde au cas zéro.

Implémentation prévue après A5 : un sélecteur dans `certus/core/certus_strat_robustness_rate.py`,
appelé seulement si `elite_optical_parents` est positif. Parmi les résultats classés, remplacer les parents Rate
les moins bien classés par les meilleurs parents optiques absents, jusqu'au quota disponible ; conserver
l'ordre du classement dans la sélection. Si le quota demandé dépasse le nombre habituel de parents,
élargir la sélection au quota disponible plutôt que prétendre satisfaire une garantie tronquée.
Transmettre la même sélection au journal et au générateur. Aucun tri du classement global ni défaut activé.
Compenser les lignes de raccordement dans le module consensus et sa fonction, sans relever leurs plafonds.

La présence d'un parent dans cette sélection ne garantit pas que ses enfants sont évalués : le budget
optique courant peut être épuisé par les premiers parents. Le rapport devra conserver les identités des
parents transmis et les nombres de candidats effectivement issus de chacun. Aucune activation simultanée
de `elite_round_robin` : elle changerait un second levier. Cette limite sera conservée si le quota ne suffit pas.

Contrôles avant mesure : absence et zéro identiques au bit, entrées non modifiées, stabilité de l'ordre,
quota absent ou insuffisant, quota déjà satisfait, quota supérieur au budget de parents et absence de doublons.
Éprouver aussi le raccordement au vrai générateur ; puis C1 et validation complète séquentielle avant commit.

Réserver avant observation six essais : juge de paix graine 42, puis `r75x0.5` graine 101,
chacun avec M = 0, 2, 4, paramètres courants et mêmes banques de consensus explicites.
Vérifier le mode et les paramètres chargés dans le protocole définitif. Le contrôle M = 0 sera neuf.
Pour chaque essai : population retournée, rejets et replis, plans déposables optiques purs, meilleur SEEL
optique pur et global avec provenance du score, plan complet, couches Rate, durée et sources.
L'absence de plan dans une classe donne un SEEL absent. Ces recherches ne constituent pas une confirmation indépendante.

Raccordement statique proposé au 21 octobre, sans application ni exécution : conserver `_elite_parent_count`,
compacter seulement sa signature sur une ligne, ajouter le sélecteur de parents du module Rate et passer sa même
liste au journal et au générateur. Une ligne supplémentaire dans la fonction ELITE porterait son compte à 300 ;
la signature compactée compenserait l'import et la ligne, sans relever le plafond du module.
Vérifier le graphe d'import et les comptes réels avant toute modification, puis prouver le chemin zéro au bit.

Le brouillon non exécuté `scratch/A4_select_elite_parents_draft.py.txt` conserve les objets de résultat,
prend les meilleurs optiques disponibles et retire les moins bien classés des parents Rate ; aucun tri global modifié.
Le quota compte les entrées classées, sans ajouter de règle de diversité ou d'élimination des parents plantés.
Les identités/signatures et la déposition des parents sélectionnés devront donc être consignées pendant l'essai.

Point d'observation des enfants repéré statiquement : le module consensus soumet sa référence locale
`_test_strategy_robustness_task` aux deux étages de réduction puis à l'évaluation complète.
Un observateur expérimental pourra associer les `strategy_id` produits par le vrai générateur à leur
`parent_strategy_id`, puis enregistrer les appels réels avec leurs niveaux de bruit et nombres de tirages.
Conserver les trois comptes séparément : parents sélectionnés, enfants engendrés, enfants réellement évalués.
Ne pas déduire une évaluation complète de la seule présence dans une réduction intermédiaire.
L'observateur devra appeler la fonction d'origine une fois et rendre son résultat intact ; recueillir les
événements des threads dans une file sûre, puis les écrire hors du calcul plutôt que lancer un second calcul.
Cet observateur n'est pas encore écrit ni validé.

Le test rouge/vert devra aussi entrer dans la vraie fonction ELITE, intercepter le générateur après la
sélection et constater que M positif atteint ses parents. Un test qui échoue seulement parce qu'un nouveau
symbole manque ne suffit pas. Comparer absence et zéro sur les candidats complets sérialisés, en plus du
contrôle C1 des noyaux ; une égalité du seul meilleur score ne prouve pas le chemin inactif au bit.
