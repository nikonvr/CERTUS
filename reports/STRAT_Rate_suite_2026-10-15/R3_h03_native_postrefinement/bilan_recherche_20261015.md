# R3_h03 — recherche native avec post-raffinement automatique

La troisième et dernière paire est terminée et auditéeGO. Le contrôle natif et le natif de la
variante ont chacun exporté5408stratégies, dont1075consensus complets. Leur meilleur consensus
est0,0324177708681504, SEEL0,36009871351145034nm. Les deux voies utilisent exactement la même
politiqueλfine/largeurs1..7 ; le facteur étudié est le post-raffinement final de la variante.
Durées exports compris : contrôle2667,831662s ; variante2630,782963s. Les codes de sortie des deux
enfants sont0 et le coordinateur est terminé. Ces durées ne mesurent aucune accélération du code.

Le planificateur a sélectionné seul deux parents,900754638 et900754520, parmi les consensus complets
de la seule sortie native. Les deux voies ayant les mêmes parents complets, la renotation commune
les a dédupliqués sans les injecter d’une voie dans l’autre. Le groupeparents a noté ces deux plans
et les trois ancres à profondeur300/base101/consensus41/42/43, dans un slot distinct.

Le post-raffinement a proposé305plans nouveaux, tous passés au contrat, dans36groupes :52doublons
et23cas de frontière/épuisement conservés. Renotationparents et recherche totalisent1333appels réels
à300tirages ;113bases non finies et13consensus incomplets restent enregistrés. Faisceau2, deux passes,
plafond300par passe/600au total et72groupes respectés ; aucun budgetR4réaffecté.

Le gagnant98000284, descendant du parent900754520, atteint le consensus0,029431526325033333,
SEEL**0,34311237998669375nm** : gain de recherche**4,7171325216%** contre le contrôle propre deh03.
Passeinterne :0,0324177708681504→0,03192907040069526 ; passepréfixe :0,029431526325033333.
Fenêtres optiques[0,5)à628nm,[10,12)à451nm,[34,37)à686nm ; les plans complets, partitions,
masquesRate, fente et témoins sont conservés dans frozen_finalists.json et les groupes, pas résumés
à ces fenêtres pour établir l’identité d’un plan. Le score est égal à celui du gagnantR4 ; cela ne
permet pas de confondre leurs plans complets ou leurs lignées.

L’incumbent est resté dans le pool. Le gagnant a été obtenu par la chaîne expérimentale automatique,
sans injection du gagnantR4 ni des plans locaux comme parents. La preuve porte sur cette recherche
native de graine101, avec un coût de notation supplémentaire explicite ; aucune conclusion à budget
identique et aucune généralisation à d’autres graines ou composants ne sont acquises.

Le meilleur local9900008 reste devant :0,3345159946382285nm, contre0,34311237998669375nm après
raffinement, soit un écart défavorable de2,5698%. Référence historique0,3967147882193691nm.
La nouvelle confirmation est conditionnée au gagnant figé avant inspection, avec trois groupes
réellement nouveaux et six plans appariés. Les groupesR4déjà inspectés ne servent pas de nouvelle
preuve indépendante pour la procédure choisie après eux.

Preuves : audit_control.json, audit_variant.json, complete_audit_01.json ; post/parent_selection.json,
post/checkpoint.json, post/frozen_search_winners.json et tous groupes/claims. Sources et protocole
figés, callbacks physiques et transportWorkerfloat32 inchangés. Aucun incident scientifique ni rejeu
de mesure sur cette paire. R3a consommé ses trois paires ; aucun quatrième essai autorisé. R5/R6
restent conditionnels à la confirmation et à la validation de l’intégration ; aucun défaut activé,
commit, push ou publication.
