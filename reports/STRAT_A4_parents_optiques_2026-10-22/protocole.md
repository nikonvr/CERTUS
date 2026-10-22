# A4 — protocole v2 fixé avant la nouvelle campagne (2026-10-22)

Six bancs successifs : `48c premium 1 0 2 0 42 0`, puis `r75x0.5 deep 0 0 2 0 101 0`, chacun avec
`elite_optical_parents=0`, `2`, `4`. La seule autre surcharge, commune aux six bancs, est
`strat_local_search=true` : l'étage livré reste actif, avec son coût supplémentaire.

Un pool optique est réservé avant le filtre de score fini, par risque de plantage puis score de repli natif.
ELITE prend d'abord les parents optiques du classement courant et complète avec ce pool, y compris des parents rejetés.
Leurs enfants passent les portes habituelles. Le classement final garde son filtre de validité.
Le reste de la sélection conserve l'ordre du classement. Le quota est borné par les parents optiques évalués disponibles ;
le nombre total de parents peut dépasser `elite_parent_top_k` si M l'exige. Le budget de candidats et l'ordre
des mouvements ne changent pas. Réserver un parent ne garantit pas qu'il produise un enfant avant épuisement du budget.

Les six bancs utilisent le même commit, un arbre suivi propre et une seule mesure sur la machine. Le lanceur
`campagne.py.txt` appelle la sonde officielle et vérifie `config`, provenance et journal du quota avant de résumer
avec `scripts/resumer_artefact_sonde.py`. Déposable signifie ici plantage < 5 % au pire des trois bruits, comme ce résumé.

Table demandée : meilleur SEEL global, meilleur SEEL optique pur, nombre de plans optiques purs déposables, durée,
commit et surcharges effectives. Les nombres de plans sont ceux de la population finale retournée, pas ceux des parents.
Les journaux `[ELITE-OPTICAL-PARENTS]` et `[ELITE-PARENTS]` renseignent la sélection effective.

La première tentative, conservée dans `tentative_01/`, a été interrompue après le banc M=0 et pendant M=2 :
la réserve cherchait des parents déjà filtrés et restait à zéro. Les six bancs v2 sont refaits au même commit,
avec des tags `A4parentsv2M*`. Les résultats v1 ne sont pas mélangés à cette table.

Une graine par composant : comparaison descriptive, sans affirmation de supériorité ni changement de défaut.
La confirmation indépendante et l'interprétation physique reviennent à Claude. A9 reste conditionnée au GO écrit par le propriétaire.
