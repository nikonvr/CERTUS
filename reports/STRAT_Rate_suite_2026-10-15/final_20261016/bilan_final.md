# CERTUS — bilan du programme borné,16octobre2026

Le programme est clos par l’arrêt précoceR6 fixé avant les mesures48c. Le correctifRMSE est validé ; le raffinement Rate améliore les contrôles propres de trois recherches r75x0.5, mais ne démontre aucun gain sur48c. Les deux autres paires conditionnelles ne sont pas lancées. Quatre pairesR6 sur six possibles sont consommées ; les quotas ne sont pas présentés comme épuisés.

## Résultats retenus et limites

| Phase/cas | Résultat mesuré |
|---|---|
| RMSE | Poids constants positifs dirigés vers le calcul non pondéré ;4régressions rouge/vert,490tableaux non concernés identiques au bit,392cas uniformes alignés. Validation généraleGO et C1froid8008tableaux identiques au bit dans leur corpus. |
| R3h01/h02 | Aucun gain des largeurs seules ni deλfine seule ; preuves et tentatives conservées. Trois pairesR3 consommées, aucuneh04. |
| R4 et h03 | Plan raffiné0,343112379987nm, contre meilleur natif historique0,360060886335nm. Procédureh03 confirmée3/3, gain moyen5,2130% contre son contrôle propre. |
| R5 | Intégration inactive par défaut ; oracle1143,unité5450,UI1324,reste359,Ruff/Mypy/docs/diffGO et C1froid8008identiques. Points fixes12appels300 et mesure intégrée unique terminés sortie0. |
| R6 r75x0.5/77 |3/3gains frais propres ; moyenne1,254075%,médiane1,052324%,pireperte0. |
| R6 r75x0.5/202 |3/3gains frais propres ; moyenne1,288814%,médiane1,416610%,pireperte0. |
| R6 r75x0.5/404 |3/3gains frais propres ; moyenne1,756176%,médiane2,362340%,pireperte0. |
| R6 48c/premium/77/fente recherchée |Même plan complet pour exports officiels et meilleurs consensus des deux bras ; gain0% sur les trois groupes. Arrêt de l’extension. |

Sur r75x0.5, le meilleur local historique9900008 reste à0,334515994638nm, confirmé sur neuf groupes historiques : aucun nouveau meilleur global pour ce composant. Les valeurs de48c ne se comparent pas directement à celles de r75x0.5. Les trois groupes par cas ne donnent pas d’intervalle de confiance ni de probabilité de plantage garantie. Le SEEL et les gains ci-dessus proviennent de consensus homogènes ; aucune comparaison de minima base/consensus mêlés.

R5 retrouve les307plans du raffinement et le gagnant deh03, avec maxécart de consensus2,5535e-15 sur les appels post comparables, mais l’identité globale native active n’est pas prouvée :29/123appels de génération diffèrent. La jointure exploratoire ne capture pas tous les paramètres locaux et ne prouve ni défaut physique contrôlé ni cause de cache. Les108appels post supplémentaires de quatre groupes rejetés restent déclarés ; aucune accélération n’est attribuée aux caches chauds ni au retrait des ancres.

## 48c et décision d’arrêt

Contrôle16008 et variante45772, deux sorties0 ; coordinateur29856 clos le16octobre à05h39Paris. Respectivement3366/3368lignes,677/679consensus complets,58847/58855appels à plusieurs profondeurs. Le post note deux parents en8appels réels150tirages, sans ancres injectées, puis produit0nouvelle proposition. La fenêtre interne sélectionnée de chaque parent traverse plusieurs blocs de suivi ; ce contexte est rejeté par le générateur. La première passe n’améliore pas le plan ; la règle existante arrête avant la passe préfixe. Ce résultat ne prouve pas qu’un autre générateur ou un repli différent échouerait ; ce serait un autre programme.

Un seul plan complet, dédupliqué avant inspection, est renoté sur les trois groupes177100xx préalablement réservés :12appels réels300tirages, trois sorties0, fin à06h02Paris. Identité des quatre rôles et gain0% ; aucune proposition ajoutée ni répétition pour chercher un gain. L’audit de provenance est GO et le critère scientifique n’est pas satisfait. Les paires r75x1.5/deep/42 etr75x2/deep/77 restent non exécutées ; leurs24graines177200xx/177300xx réservées restent non consommées.

## État conservé

Les16sources validéesR5 et les321sources du paquet du contexte géré sont inchangées et vérifiées ; contextes historiques figés. Les options elite_rate_joint_candidates=0 et rate_post_refinement=False restent les valeurs par défaut. Aucun nouveau défaut activé, aucun noyau/objectif/bruit changé depuis la validation, aucun commit/push/publication. Les modifications locales et nouveaux modules non suivis sont conservés, avec leurs sources et empreintes ; un gitdiff seul ne suffit pas à les inventorier.

Tous les plans complets, paramètres, graines, appels, rejets, nonfinis, consensus incomplets, essais de préparation et codes de sortie restent dans reports. Les20claimsR6 correspondent à8natifs et12groupes frais, sans réutilisation de slot. Les228appels fraisR6 sont à300tirages ; les appels natifs48c à150 sont distincts. n_samples compte des scores, pas les tirages. Aucun calcul n’est vivant à la finalisation. Le même suivi est mis en pause après sauvegarde et vérifications documentaires ; aucune échéance ni quota supplémentaire n’est créé. R7 attend les données machine quantitatives absentes.

## Preuves principales

- [Audit final et indexSHA](audit_final.json).
- [Trois cas initiauxR6](../R6_generalization/initial_cases_bilan_20261016.md).
- [Audit frais48c et arrêt](../R6_other_components/c04_48c_s77/fresh_audit.json), [plans complets figés](../R6_other_components/c04_48c_s77/frozen_finalists.json), [protocole d’arrêt fixé avant mesure](../R6_other_components/native_protocol.json).
- [Validation généraleR5](../R5_integration/full_validation_01/validation.json), [limites de l’intégration](../R5_integration/post_numeric_audit_02.json).
- [Confirmation de la procédureh03](../R3_h03_native_postrefinement/confirmation_01/complete_audit_02.json).

Prochaine action utile éventuelle, dans une autorisation distincte : examiner le choix d’une fenêtre interne qui traverse plusieurs blocs avant toute modification du générateur. Aucun essai supplémentaire n’est lancé dans ce programme clos.
