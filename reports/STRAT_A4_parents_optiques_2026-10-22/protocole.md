# A4 — protocole fixé avant mesure (2026-10-22)

Six bancs successifs : `48c premium 1 0 2 0 42 0`, puis `r75x0.5 deep 0 0 2 0 101 0`, chacun avec
`elite_optical_parents=0`, `2`, `4`. La seule autre surcharge, commune aux six bancs, est
`strat_local_search=true` : l'étage livré reste actif, avec son coût supplémentaire.

Le quota réserve en tête les meilleurs parents sans Rate, à score fini et non éliminés pour plantage.
Le reste de la sélection conserve l'ordre du classement. Le quota est borné par les parents optiques disponibles ;
le nombre total de parents peut dépasser `elite_parent_top_k` si M l'exige. Le budget de candidats et l'ordre
des mouvements ne changent pas. Réserver un parent ne garantit pas qu'il produise un enfant avant épuisement du budget.

Les six bancs utilisent le même commit, un arbre suivi propre et une seule mesure sur la machine. Le lanceur
`campagne.py.txt` appelle la sonde officielle et vérifie `config`, provenance et journal du quota avant de résumer
avec `scripts/resumer_artefact_sonde.py`. Déposable signifie ici plantage < 5 % au pire des trois bruits, comme ce résumé.

Table demandée : meilleur SEEL global, meilleur SEEL optique pur, nombre de plans optiques purs déposables, durée,
commit et surcharges effectives. Les nombres de plans sont ceux de la population finale retournée, pas ceux des parents.
Les journaux `[ELITE-OPTICAL-PARENTS]` et `[ELITE-PARENTS]` renseignent la sélection effective.

Une graine par composant : comparaison descriptive, sans affirmation de supériorité ni changement de défaut.
La confirmation indépendante et l'interprétation physique reviennent à Claude. A9 reste conditionnée au GO écrit par le propriétaire.
