# CERTUS Master Task List

Date de création: 2026-05-15

## Objectif
Transformer la suite CERTUS en une base logicielle plus lisible, plus robuste, plus testable et plus agréable à utiliser, tout en respectant Python 3.14.5+ et les standards modernes de 2026.

Ce document est volontairement large et priorisé. Il sert de backlog maître pour piloter les refactors, les audits et les améliorations UX / qualité.

## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans la base de documentation et les workflows visibles.
- Plan P0/P1 ciblé créé.
- Audit des modules principaux réalisé.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisé.
- Validation des configurations de release et des entrypoints critiques.
- Modernisation des exceptions, décoration `@safe_ui_action` (config/RE), configuration headless et boost de couverture à 60.73% complétés.
- Passage à 100% de réussite des 62 tests unitaires de `tests/unit/test_certus_ui.py` (résolution des dialogues bloquants par mock et isolation QSettings/MRU).

### Il reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.

---

# P0 — Bloquants structurels et socle de fiabilité

## P0.1 Verrouiller la version Python et la cohérence d’environnement
- [x] Confirmer partout `Python 3.14.5+` comme seule version supportée.
- [x] Vérifier que `pyproject.toml`, `README.md`, les workflows CI et les messages de release convergent.
- [x] Supprimer toute matrice ou garde encore liée à `3.10`, `3.11`, `3.12`, `3.13` ou `3.14.4`.
- [x] Vérifier qu’aucun script de bootstrap ne mentionne une version obsolète.
- [x] Documenter la procédure d’installation officielle.

## P0.2 Fiabiliser la release et la CI
- [x] Vérifier le workflow de release Windows du début à la fin.
- [x] Vérifier le workflow lint et ses conditions de déclenchement.
- [x] Vérifier les checks de lockfile et leur compatibilité avec les hashes.
- [x] Vérifier les artefacts générés par la release.
- [x] Vérifier les smoke tests de release et leur valeur réelle.
- [x] Supprimer les conditions CI qui reposent encore sur des hypothèses anciennes.

## P0.3 Stabiliser `certus_core.py`
- [x] Figer le rôle du core comme couche fondationnelle.
- [x] Réduire les ajouts opportunistes dans le core.
- [x] Documenter précisément les globals et les constantes.
- [x] Tester les chemins de ressources en mode dev et frozen.
- [x] Tester le hash de la base matériaux.
- [x] Tester le comportement sans dépendances optionnelles (`openpyxl`, SVG).
- [x] Vérifier les helpers de timestamps et leur cohérence dans toute la suite.

## P0.4 Rendre les gros entrypoints plus minces
- [x] Auditer et alléger `CERTUS_HUB.py`.
- [x] Auditer et alléger `CERTUS_DESIGN.py`.
- [x] Auditer et alléger `CERTUS_STRAT.py`.
- [x] Auditer et alléger `CERTUS_RE.py`.
- [x] Auditer et alléger `CERTUS_INDEX.py`.
- [x] Auditer et alléger `CERTUS_INDEX_SPLINE.py`.
- [x] Identifier pour chaque fichier ce qui relève du bootstrap, de l’UI, du calcul, du service et du rendu.

## P0.5 Sécuriser les parcours utilisateur critiques
- [x] Vérifier que les chemins principaux de CERTUS restent utilisables sans ambiguïté.
- [x] Vérifier les erreurs bloquantes et leurs messages.
- [x] Vérifier le feedback sur les longs calculs.
- [x] Vérifier les annulations, retries et états intermédiaires.
- [x] Vérifier les messages de chargement, de validation et d’export.

---

# P1 — Architecture cœur, découpage et qualité de conception

## P1.1 Réduire les monolithes hybrides
- [ ] Découper mentalement puis techniquement les responsabilités de chaque gros module.
- [ ] Séparer bootstrap, orchestration, UI et calcul.
- [ ] Réduire les imports globaux au strict nécessaire.
- [ ] Isoler les fonctions de calcul pur des widgets Qt.
- [ ] Préparer des couches service / application / présentation plus nettes.

## P1.2 Clarifier les 10 modules principaux
- [ ] `CERTUS_HUB.py` — le rendre centré sur la navigation et la composition.
- [ ] `CERTUS_DESIGN.py` — extraire les services métier et les workflows lourds.
- [ ] `CERTUS_STRAT.py` — séparer le service, le contexte et les handlers UI.
- [ ] `CERTUS_RE.py` — isoler le calcul RE et la présentation des résultats.
- [ ] `CERTUS_INDEX.py` — séparer les helpers d’index, l’UI et le bootstrap.
- [ ] `CERTUS_INDEX_SPLINE.py` — réduire la densité et centraliser les settings.
- [ ] `CERTUS_METAL_SINGLE.py` — audit architecture / UX / perf.
- [ ] `CERTUS_METAL_BILAYER.py` — audit architecture / UX / perf.
- [ ] `certus_ui.py` — limiter la croissance anarchique.
- [ ] `certus_services.py` — garder la couche fine et stable.

## P1.3 Renforcer les contrats de données
- [ ] Remplacer progressivement les dicts libres par des objets structurés.
- [ ] Uniformiser les DTO entre design, strat, RE et index.
- [ ] Réduire l’usage de `Any` dans les interfaces publiques.
- [ ] Standardiser les noms des modèles `Request` / `Response`.
- [ ] Stabiliser les payloads de worker et les manifests d’exécution.

## P1.4 Mieux séparer calcul et affichage
- [ ] Identifier les fonctions purement numériques dans les modules UI.
- [ ] Déplacer la logique de calcul dans les helpers ou services appropriés.
- [ ] Faire en sorte que les widgets n’embarquent pas la logique métier.
- [ ] Garder les callbacks courts et lisibles.
- [ ] Faire remonter les décisions métier via des structures explicites.

## P1.5 Standardiser la progression et la télémétrie des workflows
- [ ] Uniformiser les barres de progression.
- [ ] Uniformiser les statuts intermédiaires.
- [ ] Uniformiser les messages de phase.
- [ ] Stabiliser les clés de logs de progression.
- [ ] Décorréler autant que possible l’émission de stats du contexte global.

## P1.6 Nettoyer la logique de compatibilité legacy
- [ ] Identifier les adaptations historiques encore indispensables.
- [ ] Marquer clairement ce qui est legacy et ce qui est cible.
- [ ] Éviter les couches de compatibilité silencieuses trop permissives.
- [ ] Documenter les points de transition plutôt que les cacher.

---

# P1 — UX produit et clarté utilisateur

## P1.7 Améliorer le hub CERTUS
- [ ] Vérifier que `CERTUS_HUB.py` sert d’orientation claire et non de fourre-tout.
- [ ] Hiérarchiser les applications principales et secondaires.
- [ ] Réduire la densité visuelle si nécessaire.
- [ ] Vérifier l’accessibilité clavier.
- [ ] Harmoniser les cartes, badges et CTA.
- [ ] Vérifier le comportement de lancement et les états de chargement.

## P1.8 Améliorer les écrans Design et Strat
- [ ] Rendre le chemin “préparer → calculer → valider → exporter” visible.
- [ ] Réduire l’ambiguïté des labels scientifiques.
- [ ] Clarifier les phases de calcul.
- [ ] Rendre les erreurs et warnings actionnables.
- [ ] Réduire la surcharge des tableaux si besoin.

## P1.9 Améliorer RE et Index côté utilisateur
- [ ] Clarifier les résultats intermédiaires et finaux.
- [ ] Rendre les tableaux plus lisibles.
- [ ] Mettre en évidence les zones de confiance ou d’incertitude.
- [ ] Bien distinguer les données nominales, corrélées et corrigées.
- [ ] Éviter les écrans trop denses sans hiérarchie.

## P1.10 Renforcer les feedbacks globaux
- [ ] Message clair lors du chargement de fichiers.
- [ ] Message clair lors de l’échec de validation.
- [ ] Message clair lors d’une opération longue.
- [ ] Message clair à la fin d’un calcul.
- [ ] Message clair lors d’un export.
- [ ] Cohérence des toasts, dialogs et statuts.

## P1.11 Améliorer l’accessibilité et la lisibilité
- [ ] Vérifier les contrastes.
- [ ] Vérifier les tailles de police.
- [ ] Vérifier les libellés clavier et raccourcis.
- [ ] Vérifier la navigation focus.
- [ ] Vérifier les empty states et les états d’erreur.

---

# P1 — Tests et robustesse fonctionnelle

## P1.12 Renforcer la qualité des tests unitaires
- [ ] Identifier les tests qui protègent vraiment les contrats.
- [ ] Éliminer les tests trop couplés à l’implémentation.
- [ ] Créer des tests ciblés sur les helpers purs extraits.
- [ ] Augmenter la précision des assertions.
- [ ] Réduire la flakiness.

## P1.13 Renforcer les tests d’intégration
- [ ] Vérifier les flux RE, Design, Strat et Index de bout en bout.
- [ ] Tester les chemins de chargement et d’export.
- [ ] Vérifier les scénarios de données manquantes ou partielles.
- [ ] Vérifier les chemins de succès et d’échec.

## P1.14 Renforcer les tests de propriété et invariants
- [ ] Vérifier les invariants physiques.
- [ ] Vérifier les bornes de longueurs d’onde.
- [ ] Vérifier les valeurs de n/k et les NaN.
- [ ] Vérifier les cohérences de sommes, RMSE et conversions.
- [ ] Vérifier les comportements de drift correction et reverse engineering.

## P1.15 Renforcer les tests UI
- [ ] Tester les parcours principaux de l’interface.
- [ ] Tester les raccourcis et toasts.
- [ ] Tester les dialogues et états d’attente.
- [ ] Tester les écrans clés du hub, du design, de strat, de RE et de spline.

## P1.16 Renforcer les tests de perf
- [ ] Identifier les hot paths.
- [ ] Garder un petit jeu de benchmarks pertinents.
- [ ] Tester les régressions de démarrage.
- [ ] Tester les régressions de calcul sur les chemins critiques.

---

# P1 — Services headless et exécution industrialisée

## P1.17 Stabiliser `certus_services.py`
- [ ] Garder la couche headless fine et stable.
- [ ] Réduire progressivement l’usage de `Any`.
- [ ] Renforcer la stabilité du manifeste d’exécution.
- [ ] Vérifier la normalisation des paths.
- [ ] Vérifier la cohérence request / response.

## P1.18 Stabiliser `certus_strat_service.py`
- [ ] Séparer orchestration, validation et calcul si besoin.
- [ ] Réduire le couplage au contexte global.
- [ ] Clarifier le statut des validations permissives.
- [ ] Faire remonter clairement les erreurs fatales.
- [ ] Renforcer la testabilité des helpers numériques.

## P1.19 Développer l’usage headless partout où utile
- [ ] Rendre plus de pipelines exécutables sans Qt.
- [ ] Faire converger les modules vers des appels testables.
- [ ] Préparer les pipelines batch / CI.
- [ ] Préparer les usages automatiques et scripts de vérification.

---

# P2 — Refactor ciblé, cohérence et dette technique

## P2.1 Réduire les duplications entre modules
- [ ] Identifier les helpers répétés entre RE, Index, Strat et Design.
- [ ] Identifier les calculs de substrat ou de RMSE dupliqués.
- [ ] Unifier les points de vérité partagés.
- [ ] Éviter les réimplémentations divergentes.

## P2.2 Rationaliser `certus_ui.py`
- [ ] Regrouper les widgets par sous-domaines.
- [ ] Séparer design system, infrastructure UI et utilitaires techniques.
- [ ] Éviter de faire du module UI la poubelle de tout nouvel outil.
- [ ] Documenter les responsabilités réelles de la couche UI.

## P2.3 Rationaliser `certus_core.py`
- [ ] Éviter l’accumulation de responsabilités non fondationnelles.
- [ ] Isoler davantage runtime, paths, logging et erreurs.
- [ ] Maintenir une API minimale et stable.
- [ ] Limiter la croissance du nombre de globals.

## P2.4 Nettoyer les messages et l’outillage
- [ ] Uniformiser les logs et warnings.
- [ ] Uniformiser les titres de fenêtres et panneaux.
- [ ] Uniformiser les noms de fichiers exportés.
- [ ] Uniformiser les messages d’erreur orientés utilisateur.

## P2.5 Améliorer les settings et la persistance d’état
- [ ] Centraliser les clés de configuration persistées.
- [ ] Documenter les révisions des defaults.
- [ ] Éviter la prolifération de clés dans les modules d’UI.
- [ ] Vérifier les migrations de settings si nécessaire.

## P2.6 Consolider les helper modules
- [ ] Vérifier `certus_re_worker_utils.py`.
- [ ] Vérifier `certus_design_worker_utils.py`.
- [ ] Vérifier `certus_index_utils.py`.
- [ ] Vérifier `certus_metal_common.py`.
- [ ] Vérifier les utilitaires de spline, plots, exports et recent files.

---

# P2 — Conformité, style et qualité de code

## P2.7 Densifier le typage
- [ ] Réduire progressivement `Any`.
- [ ] Typiser les handlers et retours publics.
- [ ] Typiser les payloads d’interface.
- [ ] Typiser les structures d’état les plus importantes.

## P2.8 Réduire les fonctions trop longues
- [ ] Identifier les fonctions trop denses.
- [ ] Extraire les sous-étapes métier.
- [ ] Réduire les blocs de conditionnels profonds.
- [ ] Réduire les callbacks qui font trop de choses.

## P2.9 Réduire les effets de bord
- [ ] Limiter les mutations de dictionnaires partagés.
- [ ] Rendre les flux de données plus explicites.
- [ ] Réduire les accès implicites au contexte global.
- [ ] Préférer les objets immuables quand c’est réaliste.

## P2.10 Moderniser le style Python
- [ ] Uniformiser les docstrings.
- [ ] Uniformiser les noms de classes, fonctions et constantes.
- [ ] Harmoniser les imports.
- [ ] Éviter les constructions trop anciennes quand une forme plus nette existe.

---

# P2 — Science, calcul et performance

## P2.11 Auditer les hot paths numériques
- [ ] Identifier les calculs les plus coûteux.
- [ ] Vérifier les kernels Numba et les chemins vectorisés.
- [ ] Vérifier les caches réellement utiles.
- [ ] Vérifier les coûts d’import et d’initialisation.

## P2.12 Auditer les invariants physiques
- [ ] Vérifier l’énergie, les bornes et la stabilité.
- [ ] Vérifier les cas limites sur les couches, substrats et indices.
- [ ] Vérifier les comportements d’oblique, de backside et de spline.
- [ ] Vérifier la cohérence entre modèles analytiques et numériques.

## P2.13 Auditer les conversions et échelles
- [ ] Vérifier les conversions lambda/index.
- [ ] Vérifier les arrondis et la précision.
- [ ] Vérifier les seuils de normalisation.
- [ ] Vérifier les unités visibles et internes.

---

# P2 — Release, packaging et exploitation

## P2.14 Améliorer la reproductibilité des builds
- [ ] Vérifier que les artefacts sont stables.
- [ ] Vérifier que les builds frozen ne dépendent pas d’un état caché.
- [ ] Vérifier les fichiers embarqués et les ressources.
- [ ] Vérifier la mise à jour des manifests et hash de données.

## P2.15 Améliorer l’opérabilité
- [ ] Ajouter si besoin un préflight check de version / dépendances.
- [ ] Ajouter si besoin un diagnostic de démarrage.
- [ ] Rendre les logs plus exploitables en cas d’échec.
- [ ] Mieux séparer bugs applicatifs et problèmes d’environnement.

---

# P3 — Améliorations de confort, polish et dette non bloquante

## P3.1 Raffiner les composants d’UX
- [ ] Améliorer les empty states.
- [ ] Améliorer les toasts.
- [ ] Améliorer les panneaux repliables.
- [ ] Améliorer les stepper / guides / onboarding.
- [ ] Améliorer les micro-interactions du hub.

## P3.2 Raffiner la documentation interne
- [ ] Décrire les responsabilités réelles de chaque grand module.
- [ ] Décrire les chemins critiques.
- [ ] Décrire les conventions de settings, logs et exports.
- [ ] Décrire les règles d’architecture à respecter.

## P3.3 Nettoyer les scripts utilitaires secondaires
- [ ] Vérifier les scripts de benchmark.
- [ ] Vérifier les scripts de smoke.
- [ ] Vérifier les scripts d’audit et de maintenance.
- [ ] Vérifier les petits outils de conversion / export.

## P3.4 Réduire la dette visuelle
- [ ] Harmoniser les palettes.
- [ ] Harmoniser les espacements.
- [ ] Harmoniser les hiérarchies typographiques.
- [ ] Harmoniser la densité des panneaux et tableaux.

---

# Ordre d’exécution conseillé

## Phase 1 — Fiabilité système
1. P0.1 Verrouiller Python et l’environnement
2. P0.2 Fiabiliser la release et la CI
3. P0.3 Stabiliser `certus_core.py`
4. P0.4 Rendre les gros entrypoints plus minces
5. P0.5 Sécuriser les parcours critiques

## Phase 2 — Architecture et services
6. P1.1 Réduire les monolithes hybrides
7. P1.2 Clarifier les 10 modules principaux
8. P1.3 Renforcer les contrats de données
9. P1.17 Stabiliser `certus_services.py`
10. P1.18 Stabiliser `certus_strat_service.py`

## Phase 3 — UX et parcours
11. P1.7 Améliorer le hub CERTUS
12. P1.8 Améliorer Design et Strat
13. P1.9 Améliorer RE et Index
14. P1.10 Renforcer les feedbacks globaux
15. P1.11 Améliorer accessibilité et lisibilité

## Phase 4 — Tests et robustesse
16. P1.12 Renforcer les tests unitaires
17. P1.13 Renforcer les intégrations
18. P1.14 Renforcer les invariants
19. P1.15 Renforcer les tests UI
20. P1.16 Renforcer les tests perf

## Phase 5 — Refactor et dette
21. P2.1 Réduire les duplications
22. P2.2 Rationaliser `certus_ui.py`
23. P2.3 Rationaliser `certus_core.py`
24. P2.4 Nettoyer messages et outillage
25. P2.5 Consolider settings et persistance

## Phase 6 — Optimisation et polish
26. P2.11 Auditer les hot paths numériques
27. P2.12 Auditer les invariants physiques
28. P2.14 Améliorer la reproductibilité des builds
29. P3.1 Raffiner les composants d’UX
30. P3.4 Réduire la dette visuelle

---

# Règle de pilotage

Si une tâche améliore à la fois :
- la stabilité,
- la lisibilité,
- la testabilité,
- et l’expérience utilisateur,

alors elle doit remonter dans la priorité.

Si une tâche est seulement cosmétique, elle passe après les fondations techniques.

Si une tâche introduit du couplage supplémentaire dans un module déjà lourd, elle doit être revue avant exécution.

---

# Résultat attendu

À la fin de ce backlog, CERTUS doit être :
- plus simple à comprendre,
- plus simple à maintenir,
- plus simple à tester,
- plus simple à livrer,
- plus cohérent pour l’utilisateur,
- et plus crédible comme suite logicielle scientifique premium en 2026.

## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisé.
- Validation des configurations de release et des entrypoints critiques.
- Modernisation des exceptions, décoration `@safe_ui_action` (config/RE), configuration headless et boost de couverture à 60.73% complétés.
- Résolution des dialogues bloquants et nettoyage MRU pour le passage au vert des 62 tests unitaires de `tests/unit/test_certus_ui.py`.

### Reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.