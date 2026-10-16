# R4 — recherche terminée et auditée,15 octobre2026

**La branche native améliore son résultat de recherche de4,7071% enSEEL ; la branche locale ne gagne pas.** Cette conclusion porte sur les graines de recherche101/41/42/43. La confirmation indépendante est engagée séparément, sans résultat revendiqué ici. L’intégration automatique au moteur reste à démontrer.

| Plan/comparateur | Score consensus300/41/42/43 | SEEL,nm |
|---|---:|---:|
| Référence900951015 |0,039345655798|0,3967147882|
| Natif fort901054165 |0,032410960467|0,3600608863|
| Parent natifh02,900754638 |0,032417770868|0,3600987135|
| R4 gagnant97000497 |0,029431526325|0,3431123800|
| Meilleur local9900008 |0,027975237667|0,3345159946|

Le gagnantR4 reste **2,5698% moins bon que le meilleur local disponible**. Il améliore la référence de13,5116%, sans remplacer le meilleur résultat historique. Son score de base101 est0,03034599236653493 ; ce score n’est pas le consensus du tableau.

## Périmètre et coût observés

62 groupes terminés,518 propositions nouvelles acceptées par les contrats,2198 appels physiques réels300tirages. Ancres900951015/9900006/9900008 dans chaque groupe, tolérances historiquesrel1e-7/abs1e-10 ; aucun nouveau calcul de physique ni modification de son objectif. Formule de consensusmean_std/poids0,35 et transportWorkerfloat32 conservés.

Compteurs :72 doublons reconnus,46 propositions de frontière/flux épuisé consignées ;206 propositions ont une base non finie,11 un consensus incomplet. Les rejets restent dans les artefacts et n’entrent pas dans le faisceau. Une absence de consensus n’est jamais renommée consensus ni comparée par simple minimum à un score de base.

Branche locale :195 propositions à la passe interne, aucun gain au-delà de9900008 ; arrêt sans passe préfixe et sans confirmation fraîche. Branche native :210 propositions internes puis113 au préfixe, soit323 ; le budget inutilisé n’est pas transféré. Les plafonds1200global/300par branche-passe/2passes/faisceau4 restent respectés. Les temps de groupes ne constituent pas une preuve d’accélération du code : caches réutilisés et coûts différents selon les rejets.

## Résultat et provenance de la branche native

Le gagnant97000497 descend du parent900754638, issu de la varianteh02, pas du contrôle901054165. Après raffinement interne puis préfixe, les fenêtres optiques sont[0,5) à628nm,[10,12) à451nm,[34,37) à686nm ; les autres couches restentRate. Fente2nm, témoinsNone et partitions héritées ; aucune valeur628/686 ni fenêtre34 propre au composant n’est injectée dans le générateur.

Le meilleur descendant de la seule lignée901054165 atteint0,03107472632657162 : il est conservé comme diagnostic distinct. Le gagnant global vient de deux parents natifs préalablement sortis par deux voiesh02 ; cela ne prouve pas encore qu’un lancement natif unique découvrira le même plan. Le passage automatique doit être mesuré et validé avant intégration retenue.

La recherche confirme une piste structurée : rendre les bonnes géométries accessibles et les noter complètement après la recherche évite leur élimination au tri précoce. Le gain observé combine deux passes alternées, il ne prouve pas à lui seul que chaque changement isolé est causal. Les scores de recherche ont servi à choisir le plan : ils exigent une vérification indépendante.

## Audit et reprises

`complete_audit_01.json` estGO : sources/scripts/copies/protocole/manifestes, plans complets et provenance, budgets, appels réels, ancres et sorties vérifiés sur tous les groupes. Le code de sortie du groupe046 n’a pas été conservé après défaillance du parent ; il reste inconnu. Son artefact complet,39 appels réels, ancres et sources sont audités avant adoption. Les autres sorties scientifiques sont enregistrées0. Aucun groupe consommé n’a été refait.

Les incidents de persistance sont conservés : `controller_repair_01.md` et `checkpoint_repair_01/reprise.md`. Le second checkpoint temporaire différait uniquement par le groupe pending ; adoption vérifiée puis enveloppe de sauvegarde bornée, sans changement des générateurs ou sources numériques figés. Les deux groupes de queue061/062 terminent la recherche. Les contrôleurs historiques restent présents ; le dernier état est désigné par `controller_current.json`.

## Confirmation engagée, aucune conclusion indépendante encore

`confirmation_01/seed_reservation.json` fige trois groupes,12 graines distinctes dont la recherche préalable dans lesJSON de reports ne trouvait aucun usage. Sept plans sont figés avant inspection : trois comparateurs locaux/référence, les deux parents natifs, le gagnant principal97000497 et le meilleur descendant de la lignée de contrôle. Ce dernier est un diagnostic préannoncé, il ne remplacera pas silencieusement le gagnant principal après les résultats frais.

Chaque groupe impose28 appels réels300tirages, mêmes graines pour tous les plans du groupe, source et contexte identiques ; aucune nouvelle proposition. Les attentes numériques historiques sont retirées pour les nouvelles graines, les plans complets restent stricts. Replayer/garde copiés, quatre callbacks physiquesAST identiques àR4/R0,22 vérificationsGO sans exécution de graines fraîches. Coordinateur43976 au lancement ; lire son état et les processus réels avant toute action.

Décision prévue : moyenne et médiane des gains appariés positives, au moins2/3 victoires et aucun nouveau rejet physique ; viser3/3 favorables. Au plus trois groupes frais supplémentaires si petit/hétérogène, réservés avant inspection. Rapporter pire perte et limites, aucun intervalle de confiance inventé. Aucun résultat frais n’est inclus dans ce bilan de recherche.

R5/R6 restent conditionnels à la preuve native et sa confirmation ; aucun défaut activé, commit/push/publication. La limite16octobre06:00UTC reste applicable à chaque nouveau test/mesure. R7 attend les données quantitatives machine absentes.
